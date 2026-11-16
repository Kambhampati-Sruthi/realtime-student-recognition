
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.services.face_enrollment_service import (
    EnrollmentError,
    enroll_student,
)


router = APIRouter(
    prefix="/enrollment",
    tags=["Student Enrollment"],
)


MAX_IMAGE_SIZE = 5 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_SOURCE_TYPES = {
    "id_card",
    "face",
}


@router.post("/students")
async def enroll_student_endpoint(
    roll_no: str = Form(...),
    name: str = Form(...),
    branch: str = Form(...),
    source_type: str = Form(...),
    year_of_study: Optional[int] = Form(None),
    image: UploadFile = File(...),
):
    """
    Register a student and enroll their face.

    Supported enrollment sources:
        1. id_card: Full student ID-card image.
        2. face: Direct face photograph or camera capture.

    Both sources use the same face enrollment service.
    """

    try:
        # Validate text fields.
        roll_no = roll_no.strip()
        name = name.strip()
        branch = branch.strip()
        source_type = source_type.strip().lower()

        if not roll_no:
            raise EnrollmentError("Roll number is required.")

        if not name:
            raise EnrollmentError("Student name is required.")

        if not branch:
            raise EnrollmentError("Branch is required.")

        if source_type not in ALLOWED_SOURCE_TYPES:
            raise EnrollmentError(
                "Invalid source type. Use 'id_card' or 'face'."
            )

        if year_of_study is not None and year_of_study not in (1, 2, 3, 4):
            raise EnrollmentError(
                "Year of study must be between 1 and 4."
            )

        # Validate image MIME type.
        mime_type = (image.content_type or "").lower().strip()

        if mime_type not in ALLOWED_MIME_TYPES:
            raise EnrollmentError(
                "Only JPEG, PNG, and WebP images are supported."
            )

        # Read at most 5 MB + 1 byte to detect oversized uploads.
        image_bytes = await image.read(MAX_IMAGE_SIZE + 1)

        if not image_bytes:
            raise EnrollmentError("Uploaded image is empty.")

        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise EnrollmentError(
                "Image size must not exceed 5 MB."
            )

        # Run synchronous AI processing and Supabase operations
        # outside the asynchronous event loop.
        result = await run_in_threadpool(
            enroll_student,
            roll_no=roll_no,
            name=name,
            branch=branch,
            source_type=source_type,
            year_of_study=year_of_study,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

        return result

    except EnrollmentError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        # Keep detailed exception information in backend logs.
        import logging

        logging.exception("Student enrollment failed")

        raise HTTPException(
            status_code=500,
            detail="Student enrollment failed. Check backend logs.",
        ) from exc

    finally:
        await image.close()
