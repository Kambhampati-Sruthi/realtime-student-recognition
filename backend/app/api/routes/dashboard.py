
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from app.database.supabase_client import get_supabase_client


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _count(query):
    result = query.execute()
    return int(result.count or 0)


def _get_recent_events(supabase, limit: int = 10):
    result = (
        supabase.table("recognition_events")
        .select(
            "id, student_id, session_id, track_id, "
            "first_seen, last_seen, similarity_score, created_at"
        )
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    events = result.data or []

    student_ids = list({
        event["student_id"]
        for event in events
        if event.get("student_id")
    })

    students_by_id = {}

    if student_ids:
        students_result = (
            supabase.table("students")
            .select("id, name, roll_no, branch, year_of_study")
            .in_("id", student_ids)
            .execute()
        )

        students_by_id = {
            student["id"]: student
            for student in (students_result.data or [])
        }

    output = []

    for event in events:
        student = students_by_id.get(event.get("student_id"), {})

        output.append({
            "event_id": event.get("id"),
            "student_id": event.get("student_id"),
            "student_name": student.get("name", "Unknown"),
            "roll_no": student.get("roll_no", ""),
            "branch": student.get("branch", ""),
            "year_of_study": student.get("year_of_study"),
            "session_id": event.get("session_id"),
            "track_id": event.get("track_id"),
            "first_seen": event.get("first_seen"),
            "last_seen": event.get("last_seen"),
            "similarity_score": event.get("similarity_score"),
            "created_at": event.get("created_at"),
        })

    return output


def _get_activity(supabase, days: int):
    now = datetime.now(timezone.utc)
    start_date = (
        now - timedelta(days=days - 1)
    ).replace(hour=0, minute=0, second=0, microsecond=0)

    result = (
        supabase.table("recognition_events")
        .select("created_at")
        .gte("created_at", start_date.isoformat())
        .lte("created_at", now.isoformat())
        .limit(10000)
        .execute()
    )

    counts = Counter()

    for event in result.data or []:
        created_at = event.get("created_at")

        if not created_at:
            continue

        try:
            parsed = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            )
            day = parsed.astimezone(timezone.utc).date().isoformat()
            counts[day] += 1
        except (ValueError, TypeError):
            continue

    activity = []

    for offset in range(days):
        day = (start_date + timedelta(days=offset)).date()
        day_string = day.isoformat()

        activity.append({
            "date": day_string,
            "count": counts.get(day_string, 0),
        })

    return activity


@router.get("/summary")
def get_dashboard_summary():
    try:
        supabase = get_supabase_client()

        now = datetime.now(timezone.utc)
        today_start = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        total_students = _count(
            supabase.table("students")
            .select("id", count="exact", head=True)
        )

        active_students = _count(
            supabase.table("students")
            .select("id", count="exact", head=True)
            .eq("is_active", True)
        )

        today_recognitions = _count(
            supabase.table("recognition_events")
            .select("id", count="exact", head=True)
            .gte("created_at", today_start.isoformat())
            .lte("created_at", now.isoformat())
        )

        total_events = _count(
            supabase.table("recognition_events")
            .select("id", count="exact", head=True)
        )

        active_sessions = _count(
            supabase.table("recognition_sessions")
            .select("id", count="exact", head=True)
            .eq("status", "active")
        )

        configured_cameras = _count(
            supabase.table("cameras")
            .select("id", count="exact", head=True)
            .eq("is_active", True)
        )

        recent_events = _get_recent_events(supabase, limit=10)
        activity = _get_activity(supabase, days=7)

        return {
            "success": True,
            "generated_at": now.isoformat(),
            "metrics": {
                "total_students": total_students,
                "active_students": active_students,
                "today_recognitions": today_recognitions,
                "total_events": total_events,
                "active_cameras": active_sessions,
                "configured_cameras": configured_cameras,
            },
            "activity": activity,
            "recent_events": recent_events,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to load dashboard data: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc


@router.get("/activity")
def get_dashboard_activity(
    days: int = Query(default=7, ge=1, le=90),
):
    try:
        supabase = get_supabase_client()

        return {
            "success": True,
            "days": days,
            "activity": _get_activity(supabase, days),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to load recognition activity: {exc}",
        ) from exc
