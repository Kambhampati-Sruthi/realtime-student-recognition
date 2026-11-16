
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.student import (
    StudentCreate,
    StudentResponse,
    StudentStatusUpdate,
    StudentUpdate,
)
from app.services import student_service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/students",
    tags=["Students"],
)


def handle_database_error(exc: Exception) -> None:
    """
    Convert database errors into safe HTTP responses.

    Internal database details must never be exposed to the frontend.
    """

    error_code = getattr(exc, "code", None)

    # PostgreSQL unique constraint violation.
    if error_code == "23505":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with this roll number is already registered.",
        ) from exc

    logger.error(
        "Student database operation failed: %s",
        type(exc).__name__,
        exc_info=True,
    )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="A database error occurred while processing the student.",
    ) from exc


def handle_validation_error(exc: ValueError) -> None:
    """
    Convert service validation errors into appropriate HTTP responses.
    """

    message = str(exc)

    conflict_keywords = (
        "already exists",
        "belongs to another student",
        "already registered",
    )

    if any(keyword in message.lower() for keyword in conflict_keywords):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
        ) from exc

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message,
    ) from exc


@router.get(
    "/",
    response_model=list[StudentResponse],
)
def get_students(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    active_only: bool = False,
):
    """
    Retrieve student records with pagination.

    Returns available student information, including enrollment status
    and year of study when those fields are present in StudentResponse.
    """

    try:
        return student_service.list_students(
            limit=limit,
            offset=offset,
            active_only=active_only,
        )

    except HTTPException:
        raise

    except Exception as exc:
        handle_database_error(exc)


@router.get(
    "/roll-no/{roll_no}",
    response_model=StudentResponse,
)
def get_student_by_roll_number(roll_no: str):
    """Retrieve a student using their roll number."""

    try:
        student = student_service.get_student_by_roll_no(
            roll_no.strip()
        )

        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No student found with this roll number.",
            )

        return student

    except HTTPException:
        raise

    except Exception as exc:
        handle_database_error(exc)


@router.get(
    "/{student_id}",
    response_model=StudentResponse,
)
def get_student(student_id: UUID):
    """Retrieve a student using their UUID."""

    try:
        student = student_service.get_student_by_id(
            str(student_id)
        )

        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found.",
            )

        return student

    except HTTPException:
        raise

    except Exception as exc:
        handle_database_error(exc)


@router.post(
    "/",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_student(student_data: StudentCreate):
    """
    Create a student record containing student details only.

    Face-photo and ID-card registration must use:
        POST /api/enrollment/students

    The enrollment endpoint handles:
        - Image validation
        - Face detection and cropping
        - Five face variations
        - ArcFace embedding generation
        - Supabase Storage upload
        - Face image and embedding persistence
        - Enrollment status update
    """

    try:
        student_payload = student_data.model_dump(
            exclude_none=True
        )

        return student_service.create_student(
            student_payload
        )

    except ValueError as exc:
        handle_validation_error(exc)

    except HTTPException:
        raise

    except Exception as exc:
        handle_database_error(exc)


@router.put(
    "/{student_id}",
    response_model=StudentResponse,
)
def edit_student(
    student_id: UUID,
    student_data: StudentUpdate,
):
    """
    Update ordinary student details.

    Only explicitly supplied, non-None fields are updated.

    Enrollment information, face images, embeddings, and recognition
    records are not modified by this endpoint.
    """

    try:
        # Important:
        # exclude_unset=True prevents omitted fields from being included.
        # exclude_none=True prevents explicit None values from clearing
        # existing database values.
        update_payload = student_data.model_dump(
            exclude_unset=True,
            exclude_none=True,
        )

        if not update_payload:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide at least one student field to update.",
            )

        student = student_service.update_student(
            str(student_id),
            update_payload,
        )

        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found.",
            )

        return student

    except ValueError as exc:
        handle_validation_error(exc)

    except HTTPException:
        raise

    except Exception as exc:
        handle_database_error(exc)


@router.patch(
    "/{student_id}/status",
    response_model=StudentResponse,
)
def change_student_status(
    student_id: UUID,
    status_data: StudentStatusUpdate,
):
    """
    Activate or deactivate a student.

    Deactivated students must not be included in the active
    face-recognition gallery.
    """

    try:
        student = student_service.update_student_status(
            str(student_id),
            status_data.is_active,
        )

        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found.",
            )

        return student

    except HTTPException:
        raise

    except Exception as exc:
        handle_database_error(exc)
