
import logging
from typing import Any, Iterator

import numpy as np

from app.database.supabase_client import get_supabase_client
from app.services.gallery_service import EMBEDDING_DIMENSION


logger = logging.getLogger(__name__)


# =========================================================
# CONFIGURATION
# =========================================================

STUDENTS_TABLE = "students"
EMBEDDINGS_TABLE = "student_face_embeddings"

PAGE_SIZE = 500
STUDENT_ID_BATCH_SIZE = 100

MODEL_NAME = "ArcFace"


# =========================================================
# 1. LABEL NORMALIZATION
# =========================================================

def normalize_gallery_label(label: Any) -> str:
    """Normalize identity labels for case-insensitive matching."""

    if not isinstance(label, str):
        return ""

    return label.strip().casefold()


# =========================================================
# 2. PAGINATED DATABASE FETCHING
# =========================================================

def _fetch_all(
    query: Any,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """
    Fetch all matching Supabase records using pagination.

    Prevents silently loading only the first page of records.
    """

    if page_size < 1:
        raise ValueError("Page size must be greater than zero.")

    records: list[dict[str, Any]] = []
    start = 0

    while True:
        response = (
            query
            .range(start, start + page_size - 1)
            .execute()
        )

        page = response.data or []

        records.extend(page)

        if len(page) < page_size:
            break

        start += page_size

    return records


def _chunks(
    items: list[str],
    chunk_size: int,
) -> Iterator[list[str]]:
    """Split student IDs into smaller database query batches."""

    for index in range(0, len(items), chunk_size):
        yield items[index:index + chunk_size]


# =========================================================
# 3. EMBEDDING VALIDATION
# =========================================================

def _normalize_embedding(
    raw_embedding: Any,
    student_id: str,
) -> np.ndarray:
    """
    Validate and L2-normalize one stored ArcFace embedding.

    Expected shape:
        (512,)

    Returns:
        float32 normalized NumPy array.
    """

    try:
        embedding = np.asarray(
            raw_embedding,
            dtype=np.float32,
        ).reshape(-1)

    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Invalid embedding stored for student {student_id}."
        ) from exc

    if embedding.shape != (EMBEDDING_DIMENSION,):
        raise ValueError(
            f"Student {student_id} has embedding shape "
            f"{embedding.shape}; expected "
            f"({EMBEDDING_DIMENSION},)."
        )

    if not np.all(np.isfinite(embedding)):
        raise ValueError(
            f"Student {student_id} has non-finite embedding values."
        )

    norm = float(np.linalg.norm(embedding))

    if norm <= 1e-12:
        raise ValueError(
            f"Student {student_id} has a zero-magnitude embedding."
        )

    normalized = embedding / norm

    return normalized.astype(np.float32)


# =========================================================
# 4. FETCH ACTIVE ENROLLED STUDENTS
# =========================================================

def _fetch_active_enrolled_students(
    supabase: Any,
) -> list[dict[str, Any]]:
    """
    Fetch students eligible for face recognition.

    Eligibility:
        is_active = True
        enrollment_status = enrolled
    """

    query = (
        supabase.table(STUDENTS_TABLE)
        .select(
            "id,"
            "roll_no,"
            "name,"
            "branch,"
            "year_of_study,"
            "role,"
            "is_active,"
            "gallery_label,"
            "enrollment_status"
        )
        .eq("is_active", True)
        .eq("enrollment_status", "enrolled")
        .order("roll_no")
    )

    return _fetch_all(query)


# =========================================================
# 5. FETCH STUDENT EMBEDDINGS
# =========================================================

def _fetch_student_embeddings(
    supabase: Any,
    student_ids: list[str],
) -> list[dict[str, Any]]:
    """
    Fetch ArcFace embeddings for the supplied student IDs.

    Uses smaller ID batches to avoid oversized PostgREST
    requests when the number of enrolled students increases.

    Supports multiple enrollment images per student.
    """

    if not student_ids:
        return []

    all_embedding_rows: list[dict[str, Any]] = []

    for student_id_batch in _chunks(
        student_ids,
        STUDENT_ID_BATCH_SIZE,
    ):

        query = (
            supabase.table(EMBEDDINGS_TABLE)
            .select(
                "student_id,"
                "embedding,"
                "model_name,"
                "embedding_dimension"
            )
            .in_("student_id", student_id_batch)
            .eq("model_name", MODEL_NAME)
            .eq(
                "embedding_dimension",
                EMBEDDING_DIMENSION,
            )
            .order("student_id")
        )

        batch_rows = _fetch_all(query)

        all_embedding_rows.extend(batch_rows)

    return all_embedding_rows


# =========================================================
# 6. BUILD EMBEDDINGS BY STUDENT
# =========================================================

def _group_embeddings_by_student(
    embedding_rows: list[dict[str, Any]],
) -> dict[str, list[np.ndarray]]:
    """
    Validate and group embeddings by student UUID.

    Invalid individual embedding records are logged and skipped.
    Other valid students can still be recognized.
    """

    embeddings_by_student: dict[str, list[np.ndarray]] = {}

    invalid_count = 0

    for row in embedding_rows:

        student_id = row.get("student_id")

        if not student_id:
            logger.warning(
                "Skipping embedding record without student_id."
            )
            invalid_count += 1
            continue

        student_id = str(student_id)

        try:
            embedding = _normalize_embedding(
                row.get("embedding"),
                student_id,
            )

        except ValueError as exc:
            logger.warning(
                "Skipping invalid embedding for student %s: %s",
                student_id,
                exc,
            )
            invalid_count += 1
            continue

        embeddings_by_student.setdefault(
            student_id,
            [],
        ).append(embedding)

    if invalid_count:
        logger.warning(
            "Skipped %s invalid embedding records.",
            invalid_count,
        )

    return embeddings_by_student


# =========================================================
# 7. BUILD RECOGNITION GALLERY
# =========================================================

def load_gallery_student_mapping() -> dict[str, dict[str, Any]]:
    """
    Load active, enrolled students and their ArcFace embeddings
    directly from Supabase.

    Eligibility requirements:
        1. Student must exist in the students table.
        2. is_active must be True.
        3. enrollment_status must be enrolled.
        4. Student must have at least one valid ArcFace embedding.

    Gallery label:
        Uses gallery_label when available.
        Otherwise uses roll_no.

    Returns:
        {
            "student-roll-number": {
                "student_id": "...",
                "name": "...",
                "roll_no": "...",
                "branch": "...",
                "year_of_study": 3,
                "role": "student",
                "is_active": True,
                "enrollment_status": "enrolled",
                "gallery_label": "...",
                "embeddings": numpy.ndarray
            }
        }

    Embedding array shape:
        (number_of_embeddings, 512)
    """

    supabase = get_supabase_client()

    # -----------------------------------------------------
    # STEP 1: Load eligible student records.
    # -----------------------------------------------------

    students = _fetch_active_enrolled_students(supabase)

    if not students:
        raise ValueError(
            "No active, enrolled students were found in Supabase."
        )

    # -----------------------------------------------------
    # STEP 2: Collect valid student UUIDs.
    # -----------------------------------------------------

    student_ids = []

    for student in students:

        student_id = student.get("id")

        if not student_id:
            logger.warning(
                "Skipping student record without a valid UUID."
            )
            continue

        student_ids.append(str(student_id))

    if not student_ids:
        raise ValueError(
            "Supabase returned no valid student IDs."
        )

    # -----------------------------------------------------
    # STEP 3: Load stored ArcFace embeddings.
    # -----------------------------------------------------

    embedding_rows = _fetch_student_embeddings(
        supabase,
        student_ids,
    )

    if not embedding_rows:
        raise ValueError(
            "No ArcFace embeddings were found for active enrolled students."
        )

    # -----------------------------------------------------
    # STEP 4: Validate and group embeddings.
    # -----------------------------------------------------

    embeddings_by_student = _group_embeddings_by_student(
        embedding_rows
    )

    # -----------------------------------------------------
    # STEP 5: Construct final recognition mapping.
    # -----------------------------------------------------

    recognition_mapping: dict[str, dict[str, Any]] = {}

    seen_labels: dict[str, str] = {}

    students_without_embeddings = 0

    for student in students:

        student_id = str(student.get("id") or "")

        if not student_id:
            continue

        student_embeddings = embeddings_by_student.get(
            student_id,
            [],
        )

        # Never recognize a student without valid stored
        # face embeddings.
        if not student_embeddings:
            students_without_embeddings += 1
            continue

        # Use gallery_label if configured.
        # Otherwise use the unique student roll number.
        gallery_label = (
            student.get("gallery_label")
            or student.get("roll_no")
        )

        if (
            not isinstance(gallery_label, str)
            or not gallery_label.strip()
        ):
            logger.warning(
                "Skipping student %s because no usable gallery label exists.",
                student_id,
            )
            continue

        gallery_label = gallery_label.strip()

        normalized_label = normalize_gallery_label(
            gallery_label
        )

        if not normalized_label:
            continue

        # Prevent two students from sharing the same
        # case-insensitive recognition identity.
        if normalized_label in seen_labels:

            raise ValueError(
                "Duplicate gallery identity labels found in Supabase: "
                f"{gallery_label!r} and "
                f"{seen_labels[normalized_label]!r}."
            )

        seen_labels[normalized_label] = gallery_label

        # Ensure all returned embeddings have the expected
        # shape and data type.
        embedding_matrix = np.stack(
            student_embeddings,
            axis=0,
        ).astype(np.float32)

        recognition_mapping[gallery_label] = {
            "student_id": student_id,
            "name": student["name"],
            "roll_no": student["roll_no"],
            "branch": student.get("branch"),
            "year_of_study": student.get("year_of_study"),
            "role": student.get("role"),
            "is_active": True,
            "enrollment_status": "enrolled",
            "gallery_label": gallery_label,
            "embeddings": embedding_matrix,
        }

    # -----------------------------------------------------
    # STEP 6: Final gallery validation.
    # -----------------------------------------------------

    if not recognition_mapping:
        raise ValueError(
            "No active enrolled students have usable Supabase embeddings."
        )

    total_embeddings = sum(
        item["embeddings"].shape[0]
        for item in recognition_mapping.values()
    )

    logger.info(
        "Supabase recognition gallery loaded successfully: "
        "%s identities, %s embeddings, dimension %s.",
        len(recognition_mapping),
        total_embeddings,
        EMBEDDING_DIMENSION,
    )

    if students_without_embeddings:
        logger.warning(
            "%s active enrolled students were excluded because "
            "they have no valid embeddings.",
            students_without_embeddings,
        )

    return recognition_mapping


# =========================================================
# 8. GALLERY SUMMARY
# =========================================================

def get_gallery_student_summary() -> dict[str, Any]:
    """
    Return safe gallery information without exposing embeddings.

    Only active and enrolled students with valid embeddings
    are included in this summary.
    """

    mapping = load_gallery_student_mapping()

    identities = []

    total_embeddings = 0

    for label, item in mapping.items():

        embedding_count = int(
            item["embeddings"].shape[0]
        )

        total_embeddings += embedding_count

        identities.append({
            "gallery_label": label,
            "student_id": item["student_id"],
            "name": item["name"],
            "roll_no": item["roll_no"],
            "branch": item["branch"],
            "year_of_study": item["year_of_study"],
            "role": item["role"],
            "is_active": item["is_active"],
            "enrollment_status": item["enrollment_status"],
            "embedding_count": embedding_count,
            "embedding_shape": list(
                item["embeddings"].shape
            ),
        })

    return {
        "status": "success",
        "source": "supabase",
        "identity_count": len(mapping),
        "active_identities": len(mapping),
        "total_embeddings": total_embeddings,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "model_name": MODEL_NAME,
        "identities": identities,
    }
