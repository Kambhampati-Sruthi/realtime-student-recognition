
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # Application
    APP_NAME: str = "Real-Time Person Recognition"
    DEBUG: bool = True

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Frontend
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # AI model
    YOLO_MODEL_PATH: str = "models/yolo11n.pt"
    DEVICE: str = "cpu"

    # YOLO configuration
    YOLO_CONFIDENCE: float = 0.35
    YOLO_IMAGE_SIZE: int = 640

    # Recognition configuration
    FACE_CHECK_INTERVAL: float = 1.5
    LOST_TIMEOUT: float = 7.0

    MIN_SIMILARITY: float = 0.38
    MIN_MARGIN: float = 0.055

    VOTE_WINDOW: int = 5
    REQUIRED_VOTES: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
