import os
import platform
import time
from pathlib import Path

from fastapi import APIRouter

from app.config import settings
from app.database.supabase_client import get_supabase_client


router = APIRouter(prefix="/monitoring", tags=["System Monitoring"])

PROCESS_STARTED_AT = time.time()
BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _model_path(path: str | Path) -> Path:
    candidate = Path(path)

    if not candidate.is_absolute():
        candidate = BACKEND_ROOT / candidate

    return candidate


def _check_file(name: str, path: Path) -> dict:
    available = path.is_file()

    return {
        "name": name,
        "status": "online" if available else "warning",
        "available": available,
        "location": str(path),
        "details": (
            "Required file is available."
            if available
            else "File was not found at the configured location."
        ),
    }


def _get_resource_usage() -> dict:
    usage = {
        "cpu_percent": None,
        "memory_percent": None,
        "memory_used_mb": None,
    }

    try:
        import psutil

        process = psutil.Process(os.getpid())
        memory = psutil.virtual_memory()

        usage["cpu_percent"] = psutil.cpu_percent(interval=None)
        usage["memory_percent"] = memory.percent
        usage["memory_used_mb"] = round(
            process.memory_info().rss / (1024 * 1024),
            2,
        )

    except ImportError:
        pass

    except Exception:
        # Monitoring should still respond if resource inspection fails.
        pass

    return usage


@router.get("/status")
def get_system_status():
    checks = []

    checks.append({
        "name": "FastAPI Backend",
        "status": "online",
        "available": True,
        "details": "Backend process is responding.",
    })

    uptime = int(time.time() - PROCESS_STARTED_AT)

    # These checks verify file availability only.
    # They do not reload models or run inference.
    yolo_path = _model_path(settings.YOLO_MODEL_PATH)

    checks.append(
        _check_file("YOLO11 Model", yolo_path)
    )

    checks.append(
        _check_file(
            "ArcFace Weights",
            BACKEND_ROOT / "models" / "deepface" / "arcface_weights.h5",
        )
    )

    checks.append(
        _check_file(
            "RetinaFace Weights",
            BACKEND_ROOT / "models" / "deepface" / "retinaface.h5",
        )
    )

    gallery_path = BACKEND_ROOT / "artifacts" / "gallery"

    checks.append(
        _check_file(
            "Face Gallery",
            gallery_path / "face_gallery.npz",
        )
    )

    checks.append(
        _check_file(
            "Gallery Manifest",
            gallery_path / "gallery_manifest.json",
        )
    )

    database_connected = False
    active_sessions = None
    active_cameras = None
    database_error = None

    try:
        supabase = get_supabase_client()

        # Lightweight connectivity check.
        supabase.table("students").select("id").limit(1).execute()

        database_connected = True

        session_result = (
            supabase.table("recognition_sessions")
            .select("id", count="exact", head=True)
            .eq("status", "active")
            .execute()
        )

        active_sessions = session_result.count or 0

        camera_result = (
            supabase.table("cameras")
            .select("id", count="exact", head=True)
            .eq("is_active", True)
            .execute()
        )

        active_cameras = camera_result.count or 0

    except Exception as exc:
        database_error = f"{type(exc).__name__}: {exc}"

    checks.append({
        "name": "Supabase Database",
        "status": "online" if database_connected else "error",
        "available": database_connected,
        "details": (
            "Database connection successful."
            if database_connected
            else database_error
        ),
    })

    if active_sessions is not None:
        checks.append({
            "name": "Recognition Sessions",
            "status": "online",
            "available": True,
            "details": f"{active_sessions} active session(s).",
            "value": active_sessions,
        })
    else:
        checks.append({
            "name": "Recognition Sessions",
            "status": "unknown",
            "available": False,
            "details": "Session status could not be retrieved.",
        })

    if active_cameras is not None:
        checks.append({
            "name": "Configured Cameras",
            "status": "online",
            "available": True,
            "details": f"{active_cameras} active configured camera(s).",
            "value": active_cameras,
        })
    else:
        checks.append({
            "name": "Configured Cameras",
            "status": "unknown",
            "available": False,
            "details": "Camera information could not be retrieved.",
        })

    runtime = {
        "python_version": platform.python_version(),
        "operating_system": platform.platform(),
        "device": settings.DEVICE,
        "uptime_seconds": uptime,
        "yolo_confidence": settings.YOLO_CONFIDENCE,
        "yolo_image_size": settings.YOLO_IMAGE_SIZE,
        "face_check_interval": settings.FACE_CHECK_INTERVAL,
        "lost_timeout": settings.LOST_TIMEOUT,
        "minimum_similarity": settings.MIN_SIMILARITY,
        "minimum_margin": settings.MIN_MARGIN,
        "vote_window": settings.VOTE_WINDOW,
        "required_votes": settings.REQUIRED_VOTES,
    }

    return {
        "success": True,
        "overall_status": _calculate_overall_status(checks),
        "checked_at": time.time(),
        "checks": checks,
        "runtime": runtime,
        "resources": _get_resource_usage(),
    }


def _calculate_overall_status(checks: list[dict]) -> str:
    statuses = {
        item.get("status")
        for item in checks
    }

    if "error" in statuses:
        return "error"

    if "warning" in statuses or "unknown" in statuses:
        return "warning"

    return "online"