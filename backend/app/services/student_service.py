
from datetime import datetime, timezone
from typing import Any

from app.database.supabase_client import get_supabase_client


TABLE_NAME = "students"

# Only these fields can be changed through ordinary student CRUD.
# Enrollment and recognition-related fields are managed separately.
EDITABLE_STUDENT_FIELDS = {
    "name",
    "roll_no",
    "branch",
    "role",
    "year_of_study",
}

ALLOWED_ROLES = {"student", "admin"}

REQUIRED_STUDENT_FIELDS = (
    "name",
    "roll_no",
    "branch",
)


# =========================================================
# 1. COMMON HELPERS
# =========================================================

def _clean_text(value: Any, field_name: str) -> str:
    """Validate and normalize a required text field."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    cleaned = value.strip()

    if not cleaned:
        raise ValueError(f"{field_name} is required.")

    return cleaned


def _validate_year_of_study(value: Any) -> int | None:
    """
    Validate year_of_study.

    Accepted values: 1, 2, 3, 4.
    None is permitted for students without a specified year.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        raise ValueError(
            "Year of study must be an integer between 1 and 4."
        )

    # Accept integers and numeric strings, but not decimal values.
    if isinstance(value, int):
        year = value

    elif isinstance(value, str):
        normalized = value.strip()

        if not normalized.isdigit():
            raise ValueError(
                "Year of study must be an integer between 1 and 4."
            )

        year = int(normalized)

    else:
        raise ValueError(
            "Year of study must be an integer between 1 and 4."
        )

    if year not in {1, 2, 3, 4}:
        raise ValueError(
            "Year of study must be between 1 and 4."
        )

    return year


def _validate_role(value: Any) -> str:
    """Validate the student role."""

    if not isinstance(value, str):
        raise ValueError(
            "Role must be either student or admin."
        )

    role = value.strip().lower()

    if role not in ALLOWED_ROLES:
        raise ValueError(
            "Role must be either student or admin."
        )

    return role


def _prepare_student_fields(
    student_data: dict[str, Any],
    *,
    require_all: bool,
) -> dict[str, Any]:
    """
    Validate and normalize permitted student fields.

    Creation:
        name, roll_no and branch are mandatory.
        role defaults to student.

    Update:
        Only supplied fields are validated and returned.
    """

    if not isinstance(student_data, dict):
        raise ValueError("Student data must be a valid object.")

    unsupported_fields = (
        set(student_data) - EDITABLE_STUDENT_FIELDS
    )

    if unsupported_fields:
        raise ValueError(
            "Unsupported student fields: "
            + ", ".join(sorted(unsupported_fields))
        )

    cleaned: dict[str, Any] = {}

    # Validate required student details.
    for field in REQUIRED_STUDENT_FIELDS:

        if field in student_data:
            cleaned[field] = _clean_text(
                student_data[field],
                field.replace("_", " ").title(),
            )

        elif require_all:
            raise ValueError(
                f"{field.replace('_', ' ').title()} is required."
            )

    # Role validation.
    if "role" in student_data:
        cleaned["role"] = _validate_role(
            student_data["role"]
        )

    elif require_all:
        cleaned["role"] = "student"

    # Academic year validation.
    if "year_of_study" in student_data:
        cleaned["year_of_study"] = _validate_year_of_study(
            student_data["year_of_study"]
        )

    return cleaned


def _current_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


# =========================================================
# 2. LIST STUDENTS
# =========================================================

def list_students(
    limit: int = 100,
    offset: int = 0,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    """
    Retrieve students with pagination.

    active_only=True returns only active student records.

    Enrollment status is not used as an active-status substitute.
    """

    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("Limit must be an integer.")

    if limit < 1 or limit > 500:
        raise ValueError("Limit must be between 1 and 500.")

    if isinstance(offset, bool) or not isinstance(offset, int):
        raise ValueError("Offset must be an integer.")

    if offset < 0:
        raise ValueError("Offset cannot be negative.")

    if not isinstance(active_only, bool):
        raise ValueError("active_only must be a boolean.")

    client = get_supabase_client()

    query = (
        client.table(TABLE_NAME)
        .select("*")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    if active_only:
        query = query.eq("is_active", True)

    response = query.execute()

    return response.data or []


# =========================================================
# 3. GET STUDENT BY UUID
# =========================================================

def get_student_by_id(
    student_id: str,
) -> dict[str, Any] | None:
    """Retrieve one student using their UUID."""

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("id", str(student_id))
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None


# =========================================================
# 4. GET STUDENT BY ROLL NUMBER
# =========================================================

def get_student_by_roll_no(
    roll_no: str,
) -> dict[str, Any] | None:
    """Retrieve one student using their normalized roll number."""

    if not isinstance(roll_no, str):
        raise ValueError("Roll number must be a string.")

    normalized_roll_no = roll_no.strip()

    if not normalized_roll_no:
        return None

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("roll_no", normalized_roll_no)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None


# =========================================================
# 5. VALIDATE STUDENT DATA
# =========================================================

def validate_student_data(
    student_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate complete student details.

    Retained for compatibility with other service modules.
    """

    return _prepare_student_fields(
        student_data,
        require_all=True,
    )


# =========================================================
# 6. REGISTER STUDENT
# =========================================================

def create_student(
    student_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Create a student record using ordinary student details.

    Database defaults manage:
        - id
        - is_active
        - enrollment_status
        - created_at
        - updated_at
        - face_enrolled_at

    Face images, embeddings and enrollment are managed by
    face_enrollment_service.
    """

    cleaned_data = validate_student_data(student_data)

    roll_no = cleaned_data["roll_no"]

    # Preliminary duplicate check.
    existing_student = get_student_by_roll_no(roll_no)

    if existing_student:
        raise ValueError(
            f"A student with roll number {roll_no} already exists."
        )

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .insert(cleaned_data)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Student registration failed."
        )

    return response.data[0]


# =========================================================
# 7. UPDATE STUDENT DETAILS
# =========================================================

def update_student(
    student_id: str,
    student_data: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Partially update ordinary student details.

    Only explicitly supplied fields are updated.

    This function never modifies:
        - is_active
        - enrollment_status
        - face_enrolled_at
        - gallery_label
        - face images
        - face embeddings
        - recognition events
    """

    # Verify student existence first.
    existing_student = get_student_by_id(student_id)

    if not existing_student:
        return None

    cleaned_data = _prepare_student_fields(
        student_data,
        require_all=False,
    )

    if not cleaned_data:
        raise ValueError(
            "Provide at least one student field to update."
        )

    # Check roll number only if it is being changed.
    if "roll_no" in cleaned_data:

        duplicate = get_student_by_roll_no(
            cleaned_data["roll_no"]
        )

        if (
            duplicate
            and str(duplicate["id"]) != str(student_id)
        ):
            raise ValueError(
                f"Roll number {cleaned_data['roll_no']} "
                "belongs to another student."
            )

    cleaned_data["updated_at"] = _current_timestamp()

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .update(cleaned_data)
        .eq("id", str(student_id))
        .execute()
    )

    return response.data[0] if response.data else None


# =========================================================
# 8. ACTIVATE / DEACTIVATE STUDENT
# =========================================================

def update_student_status(
    student_id: str,
    is_active: bool,
) -> dict[str, Any] | None:
    """
    Activate or deactivate a student.

    Inactive students must be excluded from the recognition gallery.

    Deactivation does not delete:
        - Student information
        - Face images
        - Face embeddings
        - Historical recognition events
    """

    if not isinstance(is_active, bool):
        raise ValueError(
            "is_active must be a boolean."
        )

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .update({
            "is_active": is_active,
            "updated_at": _current_timestamp(),
        })
        .eq("id", str(student_id))
        .execute()
    )

    return response.data[0] if response.data else None
