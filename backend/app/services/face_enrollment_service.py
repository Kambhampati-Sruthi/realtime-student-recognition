
import logging
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath

import cv2
import numpy as np

from app.database.supabase_client import get_supabase_client
from app.services.model_service import embed_faces


logger = logging.getLogger(__name__)

BUCKET_NAME = "student-faces"
MAX_IMAGE_BYTES = 5 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

EMBEDDING_DIMENSION = 512
MODEL_NAME = "ArcFace"
EXPECTED_VARIATIONS = 5

MIN_FACE_SIZE = 160
FACE_MARGIN_RATIO = 0.40


class EnrollmentError(Exception):
    """Raised when face enrollment cannot be completed."""


# ---------------------------------------------------------
# Image validation and decoding
# ---------------------------------------------------------

def _validate_student_details(
    roll_no: str,
    name: str,
    branch: str,
    source_type: str,
    mime_type: str,
    year_of_study: int | None,
):
    if not all(
        isinstance(value, str)
        for value in (roll_no, name, branch, source_type, mime_type)
    ):
        raise EnrollmentError("Invalid student registration details.")

    if not roll_no or not name or not branch:
        raise EnrollmentError(
            "Roll number, name and branch are required."
        )

    if len(roll_no) > 50:
        raise EnrollmentError("Roll number cannot exceed 50 characters.")

    if len(name) > 150:
        raise EnrollmentError("Name cannot exceed 150 characters.")

    if len(branch) > 100:
        raise EnrollmentError("Branch cannot exceed 100 characters.")

    if source_type not in {"face", "id_card"}:
        raise EnrollmentError(
            "Registration source must be 'face' or 'id_card'."
        )

    if mime_type not in ALLOWED_MIME_TYPES:
        raise EnrollmentError(
            "Only JPEG, PNG and WebP images are supported."
        )

    if year_of_study is not None:
        if (
            isinstance(year_of_study, bool)
            or not isinstance(year_of_study, int)
            or year_of_study not in (1, 2, 3, 4)
        ):
            raise EnrollmentError(
                "Year of study must be an integer between 1 and 4."
            )


def _decode_image(image_bytes: bytes) -> np.ndarray:
    if not image_bytes:
        raise EnrollmentError("The uploaded image is empty.")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise EnrollmentError("Image size must not exceed 5 MB.")

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)

    image = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise EnrollmentError(
            "The uploaded file is not a valid image."
        )

    height, width = image.shape[:2]

    if width < 32 or height < 32:
        raise EnrollmentError(
            "The uploaded image resolution is too small."
        )

    if width > 8000 or height > 8000:
        raise EnrollmentError(
            "The uploaded image dimensions are too large."
        )

    return image


# ---------------------------------------------------------
# Face detection and cropping
# ---------------------------------------------------------

def _get_valid_face_detections(image: np.ndarray):
    """
    Run the shared RetinaFace/ArcFace pipeline.

    Expected model_service output:
        [(embedding, (x, y, width, height)), ...]

    Invalid detections are ignored.
    """
    detections = embed_faces(image)

    if not detections:
        return []

    valid_faces = []

    image_height, image_width = image.shape[:2]

    for item in detections:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue

        embedding, box = item[0], item[1]

        if box is None or len(box) != 4:
            continue

        try:
            x, y, width, height = [
                int(round(float(value)))
                for value in box
            ]
        except (TypeError, ValueError, OverflowError):
            continue

        if width <= 0 or height <= 0:
            continue

        if x < 0 or y < 0:
            continue

        if x >= image_width or y >= image_height:
            continue

        width = min(width, image_width - x)
        height = min(height, image_height - y)

        if width <= 0 or height <= 0:
            continue

        valid_faces.append({
            "embedding": embedding,
            "box": (x, y, width, height),
            "area": width * height,
        })

    return valid_faces


def _detect_largest_face(image: np.ndarray):
    """Return the bounding box of the largest detected face."""
    faces = _get_valid_face_detections(image)

    if not faces:
        raise EnrollmentError(
            "No face was detected. Upload a clearer, front-facing image."
        )

    largest_face = max(
        faces,
        key=lambda face: face["area"],
    )

    return largest_face["box"]


def _crop_face(image: np.ndarray) -> np.ndarray:
    """
    Crop the largest face with a 40% margin.

    Ensure the smaller crop dimension is at least 160 pixels.
    """
    image_height, image_width = image.shape[:2]

    x, y, face_width, face_height = _detect_largest_face(image)

    margin_x = int(face_width * FACE_MARGIN_RATIO)
    margin_y = int(face_height * FACE_MARGIN_RATIO)

    left = max(0, x - margin_x)
    top = max(0, y - margin_y)

    right = min(
        image_width,
        x + face_width + margin_x,
    )

    bottom = min(
        image_height,
        y + face_height + margin_y,
    )

    face = image[top:bottom, left:right]

    if face.size == 0:
        raise EnrollmentError("Face cropping failed.")

    minimum_side = min(face.shape[:2])

    if minimum_side < MIN_FACE_SIZE:
        scale = MIN_FACE_SIZE / float(minimum_side)

        new_width = max(
            1,
            int(round(face.shape[1] * scale)),
        )

        new_height = max(
            1,
            int(round(face.shape[0] * scale)),
        )

        face = cv2.resize(
            face,
            (new_width, new_height),
            interpolation=cv2.INTER_CUBIC,
        )

    return face


# ---------------------------------------------------------
# Five image variations
# ---------------------------------------------------------

def _create_five_variations(face: np.ndarray) -> list[np.ndarray]:
    """
    Generate exactly five variations:

    1. Original
    2. Horizontal flip
    3. Downsampled and restored
    4. Darker
    5. Brighter

    Gaussian blur is deliberately not used.
    """
    original = face.copy()

    flipped = cv2.flip(
        original,
        1,
    )

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

    variations = [
        original,
        flipped,
        downsampled,
        darker,
        brighter,
    ]

    if len(variations) != EXPECTED_VARIATIONS:
        raise EnrollmentError(
            "Exactly five image variations are required."
        )

    return variations


# ---------------------------------------------------------
# ArcFace embedding extraction
# ---------------------------------------------------------

def _extract_embedding(image: np.ndarray) -> list[float]:
    """
    Generate one normalized 512-dimensional ArcFace embedding.

    If multiple faces are detected in a variation, use the
    largest valid face.
    """
    faces = _get_valid_face_detections(image)

    if not faces:
        raise EnrollmentError(
            "ArcFace could not generate an embedding for an image variation."
        )

    largest_face = max(
        faces,
        key=lambda face: face["area"],
    )

    embedding = np.asarray(
        largest_face["embedding"],
        dtype=np.float32,
    ).reshape(-1)

    if embedding.shape != (EMBEDDING_DIMENSION,):
        raise EnrollmentError(
            "Expected a 512-dimensional ArcFace embedding."
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

    normalized = embedding / norm

    return normalized.astype(np.float32).tolist()


# ---------------------------------------------------------
# Student record management
# ---------------------------------------------------------

def _find_student_by_roll_no(supabase, roll_no: str):
    result = (
        supabase.table("students")
        .select("*")
        .eq("roll_no", roll_no)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def _get_or_create_student(
    supabase,
    roll_no: str,
    name: str,
    branch: str,
    year_of_study: int | None,
):
    """
    Find an existing student or create a pending student.

    Existing student details are not changed here.
    Final updates happen only after image and embeddings are saved.

    A duplicate-insert race is handled by checking the roll number
    again after an insert failure.
    """
    existing_student = _find_student_by_roll_no(
        supabase,
        roll_no,
    )

    if existing_student:
        return existing_student, False

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

    try:
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

    except EnrollmentError:
        raise

    except Exception:
        # Another registration request may have created the same
        # roll number between our initial lookup and insert.
        existing_student = _find_student_by_roll_no(
            supabase,
            roll_no,
        )

        if existing_student:
            return existing_student, False

        raise


# ---------------------------------------------------------
# Storage and database cleanup
# ---------------------------------------------------------

def _cleanup_enrollment(
    supabase,
    *,
    student_id: str,
    image_id: str,
    storage_path: str,
    storage_upload_attempted: bool,
    was_created: bool,
):
    """
    Best-effort rollback of records from this enrollment attempt.

    Never deletes a student record that existed before this attempt.
    """
    cleanup_errors = []

    # Delete embeddings first because they reference image metadata.
    try:
        (
            supabase.table("student_face_embeddings")
            .delete()
            .eq("image_id", image_id)
            .execute()
        )
    except Exception as exc:
        cleanup_errors.append(
            f"Embedding cleanup failed: {type(exc).__name__}"
        )

    # Delete image metadata.
    try:
        (
            supabase.table("student_face_images")
            .delete()
            .eq("id", image_id)
            .execute()
        )
    except Exception as exc:
        cleanup_errors.append(
            f"Image metadata cleanup failed: {type(exc).__name__}"
        )

    # Remove the unique Storage object even if upload returned
    # an error after the remote service may have accepted it.
    if storage_upload_attempted:
        try:
            supabase.storage.from_(BUCKET_NAME).remove(
                [storage_path]
            )
        except Exception as exc:
            cleanup_errors.append(
                f"Storage cleanup failed: {type(exc).__name__}"
            )

    # Delete only a student created by this enrollment attempt.
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
                f"New student cleanup failed: {type(exc).__name__}"
            )

    return cleanup_errors


# ---------------------------------------------------------
# Main enrollment operation
# ---------------------------------------------------------

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
    """
    Register a student using either:

    1. A complete ID-card image.
    2. A direct face photograph.

    The original uploaded image is saved in private Supabase Storage.

    Database records:
        students
        student_face_images
        student_face_embeddings

    Five normalized ArcFace embeddings are generated for each
    registration image.
    """

    # -----------------------------------------------------
    # 1. Normalize and validate registration details
    # -----------------------------------------------------

    if not isinstance(roll_no, str):
        raise EnrollmentError("Invalid roll number.")

    if not isinstance(name, str):
        raise EnrollmentError("Invalid student name.")

    if not isinstance(branch, str):
        raise EnrollmentError("Invalid branch.")

    if not isinstance(source_type, str):
        raise EnrollmentError("Invalid registration source.")

    if not isinstance(mime_type, str):
        raise EnrollmentError("Invalid image content type.")

    roll_no = roll_no.strip()
    name = name.strip()
    branch = branch.strip()
    source_type = source_type.strip().lower()
    mime_type = mime_type.strip().lower()

    _validate_student_details(
        roll_no,
        name,
        branch,
        source_type,
        mime_type,
        year_of_study,
    )

    if not isinstance(image_bytes, bytes):
        raise EnrollmentError("Invalid uploaded image data.")

    # -----------------------------------------------------
    # 2. Decode the original uploaded image
    # -----------------------------------------------------

    image = _decode_image(image_bytes)

    # -----------------------------------------------------
    # 3. Extract the largest face
    # -----------------------------------------------------

    face = _crop_face(image)

    # -----------------------------------------------------
    # 4. Generate exactly five variations
    # -----------------------------------------------------

    variations = _create_five_variations(face)

    # -----------------------------------------------------
    # 5. Generate all embeddings before database writes
    # -----------------------------------------------------

    embeddings = [
        _extract_embedding(variation)
        for variation in variations
    ]

    if len(embeddings) != EXPECTED_VARIATIONS:
        raise EnrollmentError(
            "Exactly five embeddings are required."
        )

    # -----------------------------------------------------
    # 6. Prepare Supabase records
    # -----------------------------------------------------

    supabase = get_supabase_client()

    student, was_created = _get_or_create_student(
        supabase,
        roll_no,
        name,
        branch,
        year_of_study,
    )

    student_id = str(student["id"])

    gallery_label = (
        student.get("gallery_label")
        or roll_no
    )

    image_id = str(uuid.uuid4())

    image_extension = ALLOWED_MIME_TYPES[mime_type]

    storage_path = str(
        PurePosixPath(student_id)
        / f"{image_id}{image_extension}"
    )

    storage_upload_attempted = False
    final_student_update_attempted = False

    enrolled_at = datetime.now(timezone.utc).isoformat()

    # -----------------------------------------------------
    # 7. Persist image, metadata, embeddings and student status
    # -----------------------------------------------------

    try:
        # -------------------------------------------------
        # 7A. Upload the original image bytes
        # -------------------------------------------------

        # Important:
        # Store the exact uploaded file bytes, not the cropped
        # face and not an image re-encoded by OpenCV.
        storage_upload_attempted = True

        supabase.storage.from_(BUCKET_NAME).upload(
            storage_path,
            image_bytes,
            {
                "content-type": mime_type,
                "upsert": "false",
            },
        )

        # -------------------------------------------------
        # 7B. Save image metadata
        # -------------------------------------------------

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
                "Unable to save registration image metadata."
            )

        # -------------------------------------------------
        # 7C. Save all five ArcFace embeddings
        # -------------------------------------------------

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

        saved_embeddings = embedding_result.data or []

        if len(saved_embeddings) != EXPECTED_VARIATIONS:
            raise EnrollmentError(
                "All five face embeddings were not saved."
            )

        # -------------------------------------------------
        # 7D. Finalize student enrollment
        # -------------------------------------------------

        # This is intentionally the final database operation.
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

        enrolled_student = status_result.data[0]

        logger.info(
            "Student enrollment completed: roll_no=%s, image_id=%s",
            roll_no,
            image_id,
        )

        # -------------------------------------------------
        # 8. Return frontend-compatible response
        # -------------------------------------------------

        return {
            "success": True,
            "message": "Student enrolled successfully.",
            "student": enrolled_student,
            "student_id": student_id,
            "roll_no": roll_no,
            "name": name,
            "gallery_label": gallery_label,
            "source_type": source_type,
            "image_id": image_id,
            "storage_path": storage_path,
            "embedding_count": EXPECTED_VARIATIONS,
            "embedding_dimension": EMBEDDING_DIMENSION,
            "enrollment_status": "enrolled",
            "created": was_created,
        }

    except Exception as exc:

        # -------------------------------------------------
        # 9. Roll back this enrollment attempt
        # -------------------------------------------------

        cleanup_errors = _cleanup_enrollment(
            supabase,
            student_id=student_id,
            image_id=image_id,
            storage_path=storage_path,
            storage_upload_attempted=storage_upload_attempted,
            was_created=was_created,
        )

        # If an existing student's final update may have reached
        # Supabase but the response failed, restore their old values.
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
                    "Student restoration failed: "
                    f"{type(restore_exc).__name__}"
                )

        if cleanup_errors:
            logger.error(
                "Enrollment rollback had errors for roll_no=%s: %s",
                roll_no,
                "; ".join(cleanup_errors),
            )

        if isinstance(exc, EnrollmentError):
            raise

        logger.exception(
            "Student enrollment failed for roll_no=%s",
            roll_no,
        )

        raise EnrollmentError(
            "Student enrollment could not be completed. "
            "Please verify the image and try again."
        ) from exc
