
import numpy as np

from app.database.supabase_client import get_supabase_client
from app.services.gallery_service import EMBEDDING_DIMENSION


STUDENTS_TABLE = "students"
EMBEDDINGS_TABLE = "student_face_embeddings"

PAGE_SIZE = 500
MODEL_NAME = "ArcFace"


def normalize_gallery_label(label):
    """Normalize identity labels for case-insensitive matching."""
    if not isinstance(label, str):
        return ""

    return label.strip().casefold()


def _fetch_all(query, page_size=PAGE_SIZE):
    """Fetch all rows using explicit PostgREST range pagination."""
    records = []
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


def _normalize_embedding(raw_embedding, student_id):
    """Validate and L2-normalize one saved ArcFace embedding."""
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
            f"Student {student_id} has an embedding with shape "
            f"{embedding.shape}; expected (512,)."
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

    return (embedding / norm).astype(np.float32)


def load_gallery_student_mapping():
    """
    Load active, enrolled students and their ArcFace embeddings
    directly from Supabase.

    Only students with enrollment_status='enrolled', is_active=True,
    and at least one valid ArcFace embedding are included.

    Returns:
        {
            "student-gallery-label": {
                "student_id": "...",
                "name": "...",
                "roll_no": "...",
                "branch": "...",
                "role": "student",
                "is_active": True,
                "gallery_label": "...",
                "embeddings": numpy.ndarray  # shape (N, 512)
            }
        }
    """
    supabase = get_supabase_client()

    student_query = (
        supabase.table(STUDENTS_TABLE)
        .select(
            "id,roll_no,name,branch,role,is_active,"
            "gallery_label,enrollment_status"
        )
        .eq("is_active", True)
        .eq("enrollment_status", "enrolled")
        .order("roll_no")
    )

    students = _fetch_all(student_query)

    if not students:
        raise ValueError(
            "No active, enrolled students were found in Supabase."
        )

    student_ids = [
        str(student["id"])
        for student in students
        if student.get("id")
    ]

    if not student_ids:
        raise ValueError(
            "Supabase returned student records without valid IDs."
        )

    embedding_query = (
        supabase.table(EMBEDDINGS_TABLE)
        .select(
            "student_id,embedding,model_name,embedding_dimension"
        )
        .in_("student_id", student_ids)
        .eq("model_name", MODEL_NAME)
        .eq("embedding_dimension", EMBEDDING_DIMENSION)
        .order("student_id")
    )

    embedding_rows = _fetch_all(embedding_query)

    if not embedding_rows:
        raise ValueError(
            "No ArcFace embeddings were found for active enrolled students."
        )

    embeddings_by_student = {}

    for row in embedding_rows:
        student_id = str(row["student_id"])

        embedding = _normalize_embedding(
            row.get("embedding"),
            student_id,
        )

        embeddings_by_student.setdefault(
            student_id,
            [],
        ).append(embedding)

    recognition_mapping = {}
    seen_labels = {}

    for student in students:
        student_id = str(student["id"])

        student_embeddings = embeddings_by_student.get(student_id)

        # An enrolled student without embeddings must not be
        # recognized using fabricated or unrelated embeddings.
        if not student_embeddings:
            continue

        gallery_label = (
            student.get("gallery_label")
            or student.get("roll_no")
        )

        if not isinstance(gallery_label, str) or not gallery_label.strip():
            raise ValueError(
                f"Student {student_id} has no usable gallery label."
            )

        gallery_label = gallery_label.strip()
        normalized_label = normalize_gallery_label(gallery_label)

        if normalized_label in seen_labels:
            raise ValueError(
                "Duplicate gallery identity labels found in Supabase: "
                f"{gallery_label!r} and "
                f"{seen_labels[normalized_label]!r}."
            )

        seen_labels[normalized_label] = gallery_label

        recognition_mapping[gallery_label] = {
            "student_id": student_id,
            "name": student["name"],
            "roll_no": student["roll_no"],
            "branch": student.get("branch"),
            "role": student.get("role"),
            "is_active": bool(student.get("is_active")),
            "gallery_label": gallery_label,
            "embeddings": np.stack(
                student_embeddings,
                axis=0,
            ).astype(np.float32),
        }

    if not recognition_mapping:
        raise ValueError(
            "No enrolled students have usable Supabase embeddings."
        )

    return recognition_mapping


def get_gallery_student_summary():
    """Return safe gallery information without exposing embeddings."""
    mapping = load_gallery_student_mapping()

    return {
        "status": "success",
        "source": "supabase",
        "identity_count": len(mapping),
        "active_identities": len(mapping),
        "total_embeddings": sum(
            item["embeddings"].shape[0]
            for item in mapping.values()
        ),
        "embedding_dimension": EMBEDDING_DIMENSION,
        "identities": [
            {
                "gallery_label": label,
                "name": item["name"],
                "roll_no": item["roll_no"],
                "branch": item["branch"],
                "is_active": item["is_active"],
                "embedding_shape": list(
                    item["embeddings"].shape
                ),
            }
            for label, item in mapping.items()
        ],
    }
