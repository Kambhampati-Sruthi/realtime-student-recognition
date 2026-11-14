
import os

# Select the TensorFlow backend before importing DeepFace.
os.environ["DEEPFACE_BACKEND_ENGINE"] = "tensorflow"

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from deepface import DeepFace
from retinaface import RetinaFace
from ultralytics import YOLO

from app.config import settings


# ---------------------------------------------------------
# PATH CONFIGURATION
# ---------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[2]

YOLO_PATH = Path(settings.YOLO_MODEL_PATH)

if not YOLO_PATH.is_absolute():
    YOLO_PATH = BACKEND_DIR / YOLO_PATH


# ---------------------------------------------------------
# MODEL INITIALIZATION
# ---------------------------------------------------------

@lru_cache(maxsize=1)
def initialize_ai_models() -> dict[str, Any]:
    """
    Initialize all AI models once and reuse them.

    Models:
        1. YOLO11n person detector
        2. RetinaFace face detector
        3. ArcFace facial recognition model

    The application is configured for CPU inference.
    """

    if settings.DEVICE.lower() != "cpu":
        raise ValueError(
            "This project is currently configured for CPU inference."
        )

    print("\n========== AI MODEL INITIALIZATION ==========")

    # 1. Load YOLO11n.
    if not YOLO_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO model not found: {YOLO_PATH}"
        )

    print("\nLoading YOLO11n...")

    person_model = YOLO(str(YOLO_PATH))

    if person_model.names.get(0) != "person":
        raise RuntimeError(
            "YOLO model class 0 is not person."
        )

    print("YOLO11n loaded successfully.")

    # 2. Initialize RetinaFace.
    print("\nInitializing RetinaFace...")

    face_detector = RetinaFace.build_model()

    if face_detector is None:
        raise RuntimeError(
            "RetinaFace initialization failed."
        )

    print("RetinaFace initialized successfully.")

    # 3. Initialize ArcFace.
    print("\nInitializing ArcFace...")

    face_recognition_model = DeepFace.build_model(
        model_name="ArcFace",
        task="facial_recognition"
    )

    if face_recognition_model is None:
        raise RuntimeError(
            "ArcFace initialization failed."
        )

    print("ArcFace initialized successfully.")

    print("\nAll AI models initialized successfully.")
    print("Inference device: CPU")
    print("=============================================\n")

    return {
        "person_detector": person_model,
        "face_detector": face_detector,
        "face_recognition": face_recognition_model,
        "device": "cpu",
    }


# ---------------------------------------------------------
# FACE EMBEDDING EXTRACTION
# ---------------------------------------------------------

def embed_faces(image_bgr: np.ndarray) -> list:
    """
    Extract normalized ArcFace embeddings from a BGR image.

    This follows the original notebook's embed_faces()
    implementation.

    Returns:
        List of:
            (embedding, facial_area)

        embedding:
            float32 array of shape (512,)

        facial_area:
            (x, y, width, height)
    """

    if image_bgr is None or not isinstance(image_bgr, np.ndarray):
        raise ValueError("Invalid input image.")

    if image_bgr.size == 0:
        raise ValueError("Input image is empty.")

    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError(
            "Expected a three-channel BGR image."
        )

    # Ensure models are initialized before inference.
    initialize_ai_models()

    try:
        representations = DeepFace.represent(
            img_path=image_bgr,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
            align=True
        )

    except ValueError:
        # Preserve the original notebook's no-face behavior.
        return []

    output = []

    for representation in representations:

        embedding = np.array(
            representation["embedding"],
            dtype=np.float32
        )

        if embedding.shape != (512,):
            raise ValueError(
                f"Unexpected embedding shape: {embedding.shape}"
            )

        if not np.isfinite(embedding).all():
            raise ValueError(
                "Embedding contains invalid values."
            )

        norm = np.linalg.norm(embedding)

        if norm == 0:
            continue

        # Same L2 normalization as the original notebook.
        embedding = embedding / norm

        facial_area = representation["facial_area"]

        area = (
            int(facial_area["x"]),
            int(facial_area["y"]),
            int(facial_area["w"]),
            int(facial_area["h"])
        )

        output.append((embedding, area))

    return output


# ---------------------------------------------------------
# MODEL STATUS
# ---------------------------------------------------------

def get_ai_model_status() -> dict:
    """
    Return model initialization status without
    exposing model weights or internal objects.
    """

    models = initialize_ai_models()

    return {
        "status": "loaded",
        "person_detector": "YOLO11n",
        "face_detector": "RetinaFace",
        "face_recognition": "ArcFace",
        "embedding_dimension": 512,
        "device": models["device"],
    }
