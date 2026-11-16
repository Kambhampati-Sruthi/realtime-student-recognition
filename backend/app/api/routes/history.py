from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from app.database.supabase_client import get_supabase_client


router = APIRouter(prefix="/history", tags=["Recognition History"])


def _get_matching_student_ids(supabase, search_term: str) -> list[str]:
    """Find students by name or roll number without building a raw OR filter."""
    pattern = f"%{search_term}%"

    name_result = (
        supabase.table("students")
        .select("id")
        .ilike("name", pattern)
        .limit(500)
        .execute()
    )

    roll_result = (
        supabase.table("students")
        .select("id")
        .ilike("roll_no", pattern)
        .limit(500)
        .execute()
    )

    matching_ids = {
        item["id"]
        for item in (name_result.data or []) + (roll_result.data or [])
        if item.get("id")
    }

    return list(matching_ids)


@router.get("/events")
def get_recognition_history(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    student_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date cannot be later than end_date.",
            )

        supabase = get_supabase_client()

        query = (
            supabase.table("recognition_events")
            .select(
                "id, student_id, session_id, track_id, camera_id, "
                "first_seen, last_seen, similarity_score, created_at",
                count="exact",
            )
        )

        if start_date:
            start = datetime.combine(
                start_date,
                time.min,
                tzinfo=timezone.utc,
            )
            query = query.gte("created_at", start.isoformat())

        if end_date:
            end_exclusive = datetime.combine(
                end_date + timedelta(days=1),
                time.min,
                tzinfo=timezone.utc,
            )
            query = query.lt("created_at", end_exclusive.isoformat())

        if student_id:
            query = query.eq("student_id", student_id)

        if search and search.strip():
            matching_ids = _get_matching_student_ids(
                supabase,
                search.strip(),
            )

            if not matching_ids:
                return {
                    "success": True,
                    "events": [],
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "total": 0,
                    },
                }

            query = query.in_("student_id", matching_ids)

        result = (
            query
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        events = result.data or []

        student_ids = {
            event["student_id"]
            for event in events
            if event.get("student_id")
        }

        students_by_id = {}

        if student_ids:
            students_result = (
                supabase.table("students")
                .select(
                    "id, name, roll_no, branch, role, year_of_study"
                )
                .in_("id", list(student_ids))
                .execute()
            )

            students_by_id = {
                student["id"]: student
                for student in (students_result.data or [])
            }

        output = []

        for event in events:
            student = students_by_id.get(
                event.get("student_id"),
                {},
            )

            output.append({
                "event_id": event.get("id"),
                "student_id": event.get("student_id"),
                "student_name": student.get("name", "Unknown"),
                "roll_no": student.get("roll_no", ""),
                "branch": student.get("branch", ""),
                "role": student.get("role", ""),
                "year_of_study": student.get("year_of_study"),
                "session_id": event.get("session_id"),
                "track_id": event.get("track_id"),
                "camera_id": event.get("camera_id"),
                "first_seen": event.get("first_seen"),
                "last_seen": event.get("last_seen"),
                "similarity_score": event.get("similarity_score"),
                "created_at": event.get("created_at"),
            })

        return {
            "success": True,
            "events": output,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": result.count or 0,
            },
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to retrieve recognition history: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc


@router.get("/summary")
def get_history_summary():
    try:
        supabase = get_supabase_client()

        now = datetime.now(timezone.utc)

        today_start = now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        week_start = today_start - timedelta(days=6)

        today_result = (
            supabase.table("recognition_events")
            .select("id", count="exact", head=True)
            .gte("created_at", today_start.isoformat())
            .execute()
        )

        week_result = (
            supabase.table("recognition_events")
            .select("id", count="exact", head=True)
            .gte("created_at", week_start.isoformat())
            .execute()
        )

        total_result = (
            supabase.table("recognition_events")
            .select("id", count="exact", head=True)
            .execute()
        )

        return {
            "success": True,
            "today": today_result.count or 0,
            "last_seven_days": week_result.count or 0,
            "all_time": total_result.count or 0,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unable to retrieve history summary: "
                f"{type(exc).__name__}: {exc}"
            ),
        ) from exc