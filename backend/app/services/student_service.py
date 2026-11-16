
from datetime import datetime, timezone
from typing import Any

from app.database.supabase_client import get_supabase_client


TABLE_NAME = "students"


# =========================================================
# 1. LIST STUDENTS
# =========================================================

def list_students(
    limit: int = 100,
    offset: int = 0,
    active_only: bool = False,
) -> list[dict[str, Any]]:

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
# 2. GET STUDENT BY UUID
# =========================================================

def get_student_by_id(
    student_id: str,
) -> dict[str, Any] | None:

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("id", student_id)
        .limit(1)
        .execute()
    )

    return (
        response.data[0]
        if response.data
        else None
    )


# =========================================================
# 3. GET STUDENT BY ROLL NUMBER
# =========================================================

def get_student_by_roll_no(
    roll_no: str,
) -> dict[str, Any] | None:

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("roll_no", roll_no.strip())
        .limit(1)
        .execute()
    )

    return (
        response.data[0]
        if response.data
        else None
    )


# =========================================================
# 4. VALIDATE STUDENT DATA
# =========================================================

def validate_student_data(
    student_data: dict[str, Any],
) -> dict[str, Any]:

    name = str(
        student_data.get("name") or ""
    ).strip()

    roll_no = str(
        student_data.get("roll_no") or ""
    ).strip()

    branch = str(
        student_data.get("branch") or ""
    ).strip()

    role = str(
        student_data.get("role") or "student"
    ).strip().lower()

    if not name:

        raise ValueError(
            "Student name is required."
        )

    if not roll_no:

        raise ValueError(
            "Student roll number is required."
        )

    if not branch:

        raise ValueError(
            "Student branch is required."
        )

    if role not in {"student", "admin"}:

        raise ValueError(
            "Role must be either student or admin."
        )

    return {
        **student_data,
        "name": name,
        "roll_no": roll_no,
        "branch": branch,
        "role": role,
    }


# =========================================================
# 5. REGISTER STUDENT
# =========================================================

def create_student(
    student_data: dict[str, Any],
) -> dict[str, Any]:

    cleaned_data = validate_student_data(
        student_data
    )

    roll_no = cleaned_data["roll_no"]

    existing_student = get_student_by_roll_no(
        roll_no
    )

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
# 6. UPDATE STUDENT DETAILS
# =========================================================

def update_student(
    student_id: str,
    student_data: dict[str, Any],
) -> dict[str, Any] | None:

    existing_student = get_student_by_id(
        student_id
    )

    if not existing_student:
        return None

    cleaned_data = validate_student_data(
        student_data
    )

    roll_no = cleaned_data["roll_no"]

    duplicate = get_student_by_roll_no(
        roll_no
    )

    if (
        duplicate
        and duplicate["id"] != student_id
    ):

        raise ValueError(
            f"Roll number {roll_no} belongs to another student."
        )

    cleaned_data["updated_at"] = (
        datetime.now(timezone.utc).isoformat()
    )

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .update(cleaned_data)
        .eq("id", student_id)
        .execute()
    )

    return (
        response.data[0]
        if response.data
        else None
    )


# =========================================================
# 7. ACTIVATE / DEACTIVATE STUDENT
# =========================================================

def update_student_status(
    student_id: str,
    is_active: bool,
) -> dict[str, Any] | None:

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .update({
            "is_active": is_active,
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
        })
        .eq("id", student_id)
        .execute()
    )

    return (
        response.data[0]
        if response.data
        else None
    )
