
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes.students import router as students_router
from app.api.routes.recognition import router as recognition_router


app = FastAPI(
    title=settings.APP_NAME,
    description="YOLO11 and DeepFace real-time recognition system",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Student management REST APIs.
app.include_router(
    students_router,
    prefix="/api"
)

# Real-time AI recognition WebSocket.
app.include_router(
    recognition_router,
    prefix="/api"
)


@app.get("/")
async def root():
    return {
        "message": "Real-Time Person Recognition API",
        "status": "online"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "device": settings.DEVICE,
        "application": settings.APP_NAME
    }
