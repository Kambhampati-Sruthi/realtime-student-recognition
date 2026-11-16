import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.api.routes.students import router as students_router
from app.api.routes.recognition import router as recognition_router
from app.api.routes.enrollment import router as enrollment_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.history import router as history_router
from app.api.routes.monitoring import router as monitoring_router


app = FastAPI(
    title=settings.APP_NAME,
    description="YOLO11 and DeepFace real-time recognition system",
    version="1.0.0",
)

# Build clean CORS allowlist without None/empty strings
allowed_origins = [
    origin
    for origin in [
        getattr(settings, "FRONTEND_ORIGIN", None),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    if origin
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads/data directory if present so saved student images can be previewed in UI
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Register API routers
app.include_router(students_router, prefix="/api")
app.include_router(recognition_router, prefix="/api")
app.include_router(enrollment_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "message": "Real-Time Person Recognition API",
        "status": "online",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "device": settings.DEVICE,
        "application": settings.APP_NAME,
    }