
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.student import (
    StudentCreate,
    StudentResponse,
    StudentStatusUpdate,
    StudentUpdate,
)
from app.services import student_service


router = APIRouter(
    prefix="/students",
    tags=["Students"],
)


def handle_database_error(exc: Exception) -> None:
    """Convert duplicate database errors into a clear HTTP response."""

    # PostgreSQL error code 23505 means unique constraint violation.
    if getattr(exc, "code", None) == "23505":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A student with this roll number is already registered.",
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="A database error occurred while processing the student.",
    )


@router.get("/", response_model=list[StudentResponse])
def get_students(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    active_only: bool = False,
):
    """Retrieve students with pagination."""

    try:
        return student_service.list_students(
            limit=limit,
            offset=offset,
            active_only=active_only,
        )
    except Exception as exc:
        handle_database_error(exc)


@router.get("/roll-no/{roll_no}", response_model=StudentResponse)
def get_student_by_roll_number(roll_no: str):
    """Find a registered student by roll number."""

    student = student_service.get_student_by_roll_no(roll_no)

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student found with this roll number.",
        )

    return student


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: UUID):
    """Retrieve one student using their UUID."""

    student = student_service.get_student_by_id(str(student_id))

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found.",
        )

    return student


@router.post(
    "/",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_student(student_data: StudentCreate):
    """Register a new student."""

    try:
        return student_service.create_student(
            student_data.model_dump()
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        handle_database_error(exc)


@router.put("/{student_id}", response_model=StudentResponse)
def edit_student(
    student_id: UUID,
    student_data: StudentUpdate,
):
    """Update an existing student's details."""

    try:
        student = student_service.update_student(
            str(student_id),
            student_data.model_dump(),
        )

        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found.",
            )

        return student

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

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
    """Activate or deactivate a student."""

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
