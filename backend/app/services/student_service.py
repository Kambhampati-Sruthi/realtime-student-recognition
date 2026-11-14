
from datetime import datetime, timezone
from typing import Any

from app.database.supabase_client import get_supabase_client


TABLE_NAME = "students"


def list_students(
    limit: int = 100,
    offset: int = 0,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    """Retrieve students with pagination."""

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


def get_student_by_id(student_id: str) -> dict[str, Any] | None:
    """Find a student using their database UUID."""

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("id", student_id)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None


def get_student_by_roll_no(roll_no: str) -> dict[str, Any] | None:
    """Find a student using their roll number."""

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .select("*")
        .eq("roll_no", roll_no.strip())
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None


def create_student(student_data: dict[str, Any]) -> dict[str, Any]:
    """Register a student after checking for duplicate roll numbers."""

    roll_no = student_data["roll_no"].strip()

    existing_student = get_student_by_roll_no(roll_no)

    if existing_student:
        raise ValueError(
            f"A student with roll number {roll_no} already exists."
        )

    cleaned_data = {
        **student_data,
        "roll_no": roll_no,
        "name": student_data["name"].strip(),
        "branch": (
            student_data["branch"].strip()
            if student_data.get("branch")
            else None
        ),
    }

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .insert(cleaned_data)
        .execute()
    )

    if not response.data:
        raise RuntimeError("Student registration failed.")

    return response.data[0]


def update_student(
    student_id: str,
    student_data: dict[str, Any],
) -> dict[str, Any] | None:
    """Update a student's details."""

    existing_student = get_student_by_id(student_id)

    if not existing_student:
        return None

    roll_no = student_data["roll_no"].strip()

    duplicate = get_student_by_roll_no(roll_no)

    if duplicate and duplicate["id"] != student_id:
        raise ValueError(
            f"Roll number {roll_no} belongs to another student."
        )

    cleaned_data = {
        **student_data,
        "roll_no": roll_no,
        "name": student_data["name"].strip(),
        "branch": (
            student_data["branch"].strip()
            if student_data.get("branch")
            else None
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .update(cleaned_data)
        .eq("id", student_id)
        .execute()
    )

    return response.data[0] if response.data else None


def update_student_status(
    student_id: str,
    is_active: bool,
) -> dict[str, Any] | None:
    """Activate or deactivate a student without deleting their record."""

    client = get_supabase_client()

    response = (
        client.table(TABLE_NAME)
        .update({
            "is_active": is_active,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", student_id)
        .execute()
    )

    return response.data[0] if response.data else None
