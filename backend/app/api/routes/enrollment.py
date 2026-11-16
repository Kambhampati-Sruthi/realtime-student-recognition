import logging
from typing import Optional

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from starlette.concurrency import run_in_threadpool

from app.services.face_enrollment_service import (
    EnrollmentError,
    enroll_student,
)


logger = logging.getLogger(__name__)

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

ALLOWED_ROLES = {
    "student",
    "faculty",
    "staff",
}


@router.post("/students")
@router.post("/students/")
async def enroll_student_endpoint(
    roll_no: str = Form(...),
    name: str = Form(...),
    branch: str = Form(...),
    role: str = Form("student"),
    source_type: str = Form(...),
    year_of_study: Optional[int] = Form(None),
    image: UploadFile = File(...),
):
    try:
        # Validate text fields.
        roll_no = roll_no.strip()
        name = name.strip()
        branch = branch.strip()
        role = role.strip().lower()
        source_type = source_type.strip().lower()

        if not roll_no:
            raise HTTPException(
                status_code=400,
                detail="Roll number / ID is required.",
            )

        if not name:
            raise HTTPException(
                status_code=400,
                detail="Name is required.",
            )

        if not branch:
            raise HTTPException(
                status_code=400,
                detail="Branch / Department is required.",
            )

        if role not in ALLOWED_ROLES:
            raise HTTPException(
                status_code=400,
                detail="Role must be 'student', 'faculty', or 'staff'.",
            )

        if len(roll_no) > 50:
            raise HTTPException(
                status_code=400,
                detail="Roll number / ID cannot exceed 50 characters.",
            )

        if len(name) > 150:
            raise HTTPException(
                status_code=400,
                detail="Name cannot exceed 150 characters.",
            )

        if len(branch) > 100:
            raise HTTPException(
                status_code=400,
                detail="Branch / Department cannot exceed 100 characters.",
            )

        if source_type not in ALLOWED_SOURCE_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Source type must be 'id_card' or 'face'.",
            )

        # Conditional Year of Study validation: only required for students
        if role == "student":
            if year_of_study is None or year_of_study not in (1, 2, 3, 4):
                raise HTTPException(
                    status_code=400,
                    detail="Year of study must be between 1 and 4 for students.",
                )
        else:
            year_of_study = None

        # Validate file type.
        mime_type = (image.content_type or "").lower().strip()

        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=415,
                detail="Upload a JPEG, PNG, or WebP image.",
            )

        # Read at most 5 MB + 1 byte.
        image_bytes = await image.read(MAX_IMAGE_SIZE + 1)

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty.",
            )

        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Image size must not exceed 5 MB.",
            )

        # Perform CPU-heavy face processing outside the event loop.
        result = await run_in_threadpool(
            enroll_student,
            roll_no=roll_no,
            name=name,
            branch=branch,
            role=role,
            source_type=source_type,
            year_of_study=year_of_study,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

        logger.info(
            "Enrollment completed for roll number / ID %s with role %s",
            roll_no,
            role,
        )

        return result

    except HTTPException:
        raise

    except EnrollmentError as exc:
        logger.warning(
            "Enrollment rejected for roll number / ID %s: %s",
            roll_no,
            str(exc),
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected enrollment failure for roll number / ID %s",
            roll_no,
        )

        raise HTTPException(
            status_code=500,
            detail="Enrollment failed. Check the backend logs.",
        ) from exc

    finally:
        await image.close()