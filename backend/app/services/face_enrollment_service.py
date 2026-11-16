
import uuid
from datetime import datetime, timezone

import cv2
import numpy as np

from app.database.supabase_client import get_supabase_client
from app.services.model_service import embed_faces


BUCKET_NAME = "student-faces"
MAX_IMAGE_BYTES = 5 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

EMBEDDING_DIMENSION = 512
MODEL_NAME = "ArcFace"


class EnrollmentError(Exception):
    """Raised when face enrollment cannot be completed."""


def _decode_image(image_bytes: bytes) -> np.ndarray:
    if not image_bytes:
        raise EnrollmentError("The uploaded image is empty.")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise EnrollmentError("Image size must not exceed 5 MB.")

    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)

    if image is None:
        raise EnrollmentError(
            "The uploaded file is not a valid image."
        )

    return image


def _detect_largest_face(image: np.ndarray):
    """Detect the largest usable face using the shared face pipeline."""
    detections = embed_faces(image)

    if not detections:
        raise EnrollmentError(
            "No face was detected. Upload a clearer, front-facing image."
        )

    valid_faces = []

    for item in detections:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue

        box = item[1]

        if box is None or len(box) != 4:
            continue

        x, y, width, height = [int(value) for value in box]

        if width <= 0 or height <= 0:
            continue

        valid_faces.append(
            (width * height, x, y, width, height)
        )

    if not valid_faces:
        raise EnrollmentError(
            "A usable face could not be extracted."
        )

    _, x, y, width, height = max(
        valid_faces,
        key=lambda item: item[0],
    )

    return x, y, width, height


def _crop_face(image: np.ndarray) -> np.ndarray:
    """Crop the largest face with a 40% margin and minimum 160px side."""
    image_height, image_width = image.shape[:2]

    x, y, face_width, face_height = _detect_largest_face(image)

    margin = int(0.4 * face_width)

    left = max(0, x - margin)
    top = max(0, y - margin)
    right = min(image_width, x + face_width + margin)
    bottom = min(image_height, y + face_height + margin)

    face = image[top:bottom, left:right]

    if face.size == 0:
        raise EnrollmentError("Face cropping failed.")

    minimum_side = min(face.shape[:2])

    if minimum_side < 160:
        scale = 160.0 / minimum_side

        new_width = max(
            1,
            int(face.shape[1] * scale),
        )

        new_height = max(
            1,
            int(face.shape[0] * scale),
        )

        face = cv2.resize(
            face,
            (new_width, new_height),
            interpolation=cv2.INTER_CUBIC,
        )

    return face


def _create_five_variations(face: np.ndarray):
    """
    Generate exactly five variations.

    1. Original
    2. Horizontal flip
    3. Downsampled and restored
    4. Darker
    5. Brighter

    No Gaussian blur is applied.
    """
    original = face.copy()

    flipped = cv2.flip(original, 1)

    smaller_width = max(
        1,
        int(original.shape[1] * 0.75),
    )

    smaller_height = max(
        1,
        int(original.shape[0] * 0.75),
    )

    smaller = cv2.resize(
        original,
        (smaller_width, smaller_height),
        interpolation=cv2.INTER_AREA,
    )

    downsampled = cv2.resize(
        smaller,
        (original.shape[1], original.shape[0]),
        interpolation=cv2.INTER_CUBIC,
    )

    darker = np.clip(
        original.astype(np.float32) * 0.80,
        0,
        255,
    ).astype(np.uint8)

    brighter = np.clip(
        original.astype(np.float32) * 1.20,
        0,
        255,
    ).astype(np.uint8)

    return [
        original,
        flipped,
        downsampled,
        darker,
        brighter,
    ]


def _extract_embedding(image: np.ndarray) -> list[float]:
    detections = embed_faces(image)

    if not detections:
        raise EnrollmentError(
            "ArcFace could not generate an embedding for an image variation."
        )

    embedding = np.asarray(
        detections[0][0],
        dtype=np.float32,
    ).reshape(-1)

    if embedding.shape != (EMBEDDING_DIMENSION,):
        raise EnrollmentError(
            "Expected a 512-dimensional embedding, "
            f"received {embedding.shape}."
        )

    if not np.all(np.isfinite(embedding)):
        raise EnrollmentError(
            "The generated embedding contains invalid values."
        )

    norm = float(np.linalg.norm(embedding))

    if norm <= 1e-12:
        raise EnrollmentError(
            "The generated embedding has zero magnitude."
        )

    embedding = embedding / norm

    return embedding.astype(np.float32).tolist()


def _get_or_create_student(
    supabase,
    roll_no: str,
    name: str,
    branch: str,
    year_of_study: int | None,
):
    """
    Find the student by unique roll number or create a pending record.

    Existing student details are deliberately not changed here.
    They are updated only after all enrollment data has been saved.
    """
    result = (
        supabase.table("students")
        .select("*")
        .eq("roll_no", roll_no)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0], False

    insert_data = {
        "roll_no": roll_no,
        "name": name,
        "branch": branch,
        "role": "student",
        "is_active": True,
        "gallery_label": roll_no,
        "enrollment_status": "pending",
    }

    if year_of_study is not None:
        insert_data["year_of_study"] = year_of_study

    created = (
        supabase.table("students")
        .insert(insert_data)
        .execute()
    )

    if not created.data:
        raise EnrollmentError(
            "Unable to create the pending student record."
        )

    return created.data[0], True


def _cleanup_enrollment(
    supabase,
    *,
    student_id: str,
    image_id: str,
    storage_path: str,
    uploaded: bool,
    was_created: bool,
):
    """
    Best-effort cleanup of records created by this enrollment attempt.

    Existing student records are never deleted.
    """
    cleanup_errors = []

    try:
        (
            supabase.table("student_face_embeddings")
            .delete()
            .eq("image_id", image_id)
            .execute()
        )
    except Exception as exc:
        cleanup_errors.append(
            f"embedding cleanup: {type(exc).__name__}"
        )

    try:
        (
            supabase.table("student_face_images")
            .delete()
            .eq("id", image_id)
            .execute()
        )
    except Exception as exc:
        cleanup_errors.append(
            f"image metadata cleanup: {type(exc).__name__}"
        )

    if uploaded:
        try:
            supabase.storage.from_(BUCKET_NAME).remove(
                [storage_path]
            )
        except Exception as exc:
            cleanup_errors.append(
                f"Storage cleanup: {type(exc).__name__}"
            )

    if was_created:
        try:
            (
                supabase.table("students")
                .delete()
                .eq("id", student_id)
                .execute()
            )
        except Exception as exc:
            cleanup_errors.append(
                f"new student cleanup: {type(exc).__name__}"
            )

    return cleanup_errors


def enroll_student(
    *,
    roll_no: str,
    name: str,
    branch: str,
    image_bytes: bytes,
    mime_type: str,
    source_type: str,
    year_of_study: int | None = None,
):
    roll_no = roll_no.strip()
    name = name.strip()
    branch = branch.strip()
    source_type = source_type.strip().lower()
    mime_type = mime_type.strip().lower()

    if not roll_no or not name or not branch:
        raise EnrollmentError(
            "Roll number, name and branch are required."
        )

    if source_type not in {"face", "id_card"}:
        raise EnrollmentError(
            "source_type must be 'face' or 'id_card'."
        )

    if mime_type not in ALLOWED_MIME_TYPES:
        raise EnrollmentError(
            "Only JPEG, PNG and WebP images are supported."
        )

    if (
        year_of_study is not None
        and year_of_study not in (1, 2, 3, 4)
    ):
        raise EnrollmentError(
            "Year of study must be between 1 and 4."
        )

    # ---------------------------------------------------------
    # 1. Decode, detect and crop
    # ---------------------------------------------------------

    image = _decode_image(image_bytes)

    face = _crop_face(image)

    variations = _create_five_variations(face)

    if len(variations) != 5:
        raise EnrollmentError(
            "Exactly five image variations are required."
        )

    # ---------------------------------------------------------
    # 2. Generate all embeddings before database writes
    # ---------------------------------------------------------

    embeddings = [
        _extract_embedding(variation)
        for variation in variations
    ]

    if len(embeddings) != 5:
        raise EnrollmentError(
            "Exactly five embeddings are required."
        )

    # ---------------------------------------------------------
    # 3. Prepare Supabase records
    # ---------------------------------------------------------

    supabase = get_supabase_client()

    student, was_created = _get_or_create_student(
        supabase,
        roll_no,
        name,
        branch,
        year_of_study,
    )

    student_id = str(student["id"])

    # Use a stable, unique label for the recognition gallery.
    gallery_label = (
        student.get("gallery_label")
        or roll_no
    )

    image_id = str(uuid.uuid4())

    storage_path = f"{student_id}/{image_id}.jpg"

    uploaded = False
    final_student_update_attempted = False

    enrolled_at = datetime.now(timezone.utc).isoformat()

    try:
        # -----------------------------------------------------
        # 4. Store the original uploaded image in private Storage
        # -----------------------------------------------------

        success, encoded = cv2.imencode(
            ".jpg",
            image,
            [
                int(cv2.IMWRITE_JPEG_QUALITY),
                95,
            ],
        )

        if not success:
            raise EnrollmentError(
                "Unable to encode the original image."
            )

        supabase.storage.from_(BUCKET_NAME).upload(
            storage_path,
            encoded.tobytes(),
            {
                "content-type": "image/jpeg",
                "upsert": "false",
            },
        )

        uploaded = True

        # -----------------------------------------------------
        # 5. Store image metadata
        # -----------------------------------------------------

        image_record = {
            "id": image_id,
            "student_id": student_id,
            "storage_path": storage_path,
            "source_type": source_type,
        }

        image_result = (
            supabase.table("student_face_images")
            .insert(image_record)
            .execute()
        )

        if not image_result.data:
            raise EnrollmentError(
                "Unable to save face-image metadata."
            )

        # -----------------------------------------------------
        # 6. Store all five ArcFace embeddings
        # -----------------------------------------------------

        embedding_records = []

        for index, embedding in enumerate(
            embeddings,
            start=1,
        ):
            embedding_records.append({
                "student_id": student_id,
                "image_id": image_id,
                "variation_index": index,
                "embedding": embedding,
                "model_name": MODEL_NAME,
                "embedding_dimension": EMBEDDING_DIMENSION,
            })

        embedding_result = (
            supabase.table("student_face_embeddings")
            .insert(embedding_records)
            .execute()
        )

        if len(embedding_result.data or []) != 5:
            raise EnrollmentError(
                "All five embeddings were not saved."
            )

        # -----------------------------------------------------
        # 7. Finalize student enrollment last
        # -----------------------------------------------------

        update_data = {
            "name": name,
            "branch": branch,
            "role": student.get("role") or "student",
            "is_active": True,
            "gallery_label": gallery_label,
            "enrollment_status": "enrolled",
            "face_enrolled_at": enrolled_at,
            "updated_at": enrolled_at,
        }

        if year_of_study is not None:
            update_data["year_of_study"] = year_of_study

        final_student_update_attempted = True

        status_result = (
            supabase.table("students")
            .update(update_data)
            .eq("id", student_id)
            .execute()
        )

        if not status_result.data:
            raise EnrollmentError(
                "Unable to finalize student enrollment."
            )

        return {
            "success": True,
            "message": "Student enrolled successfully.",
            "student": status_result.data[0],
            "student_id": student_id,
            "roll_no": roll_no,
            "name": name,
            "gallery_label": gallery_label,
            "source_type": source_type,
            "image_id": image_id,
            "storage_path": storage_path,
            "embedding_count": 5,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "enrollment_status": "enrolled",
            "created": was_created,
        }

    except Exception as exc:
        cleanup_errors = _cleanup_enrollment(
            supabase,
            student_id=student_id,
            image_id=image_id,
            storage_path=storage_path,
            uploaded=uploaded,
            was_created=was_created,
        )

        # If finalization may have reached Supabase but the response
        # failed, restore the previous student fields when possible.
        if final_student_update_attempted and not was_created:
            restore_fields = {
                key: student.get(key)
                for key in (
                    "name",
                    "branch",
                    "role",
                    "is_active",
                    "gallery_label",
                    "enrollment_status",
                    "face_enrolled_at",
                    "year_of_study",
                )
            }

            restore_fields["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            try:
                (
                    supabase.table("students")
                    .update(restore_fields)
                    .eq("id", student_id)
                    .execute()
                )
            except Exception as restore_exc:
                cleanup_errors.append(
                    "student restore: "
                    f"{type(restore_exc).__name__}"
                )

        if cleanup_errors:
            print(
                "[ENROLLMENT CLEANUP WARNING] "
                + "; ".join(cleanup_errors)
            )

        if isinstance(exc, EnrollmentError):
            raise

        raise EnrollmentError(
            "Enrollment could not be completed. "
            f"Reason: {type(exc).__name__}: {exc}"
        ) from exc
