
import os

# Select the TensorFlow backend before importing DeepFace.
os.environ["DEEPFACE_BACKEND_ENGINE"] = "tensorflow"

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from deepface import DeepFace
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
    Initialize the application AI models once.

    Models:
        1. YOLO11n person detector
        2. RetinaFace face detector
        3. ArcFace facial recognition model

    This application currently uses CPU inference.
    """

    if settings.DEVICE.lower() != "cpu":
        raise ValueError(
            "This project is currently configured for CPU inference."
        )

    print("\n========== AI MODEL INITIALIZATION ==========")

    # 1. YOLO11n.
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

    # 2. RetinaFace.
    print("\nInitializing RetinaFace...")

    from retinaface import RetinaFace

    face_detector = RetinaFace.build_model()

    if face_detector is None:
        raise RuntimeError(
            "RetinaFace initialization failed."
        )

    print("RetinaFace initialized successfully.")

    # 3. ArcFace.
    print("\nInitializing ArcFace...")

    face_recognition_model = DeepFace.build_model(
        model_name="ArcFace",
        task="facial_recognition",
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
    Extract RetinaFace-detected ArcFace embeddings.

    Input:
        Three-channel BGR image.

    Output:
        List of:
            (embedding, facial_area)

        embedding:
            float32 array with shape (512,)

        facial_area:
            (x, y, width, height)

    Every returned embedding is L2-normalized.
    """

    if image_bgr is None:
        raise ValueError("Input image is None.")

    if not isinstance(image_bgr, np.ndarray):
        raise ValueError("Input must be a NumPy image array.")

    if image_bgr.size == 0:
        raise ValueError("Input image is empty.")

    if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError(
            "Expected a three-channel BGR image."
        )

    # Ensure the application models are initialized.
    initialize_ai_models()

    try:
        representations = DeepFace.represent(
            img_path=image_bgr,
            model_name="ArcFace",
            detector_backend="retinaface",
            enforce_detection=True,
            align=True,
        )

    except ValueError as exc:
        error_message = str(exc).lower()

        no_face_indicators = (
            "face could not be detected",
            "no face detected",
            "no face was detected",
            "cannot detect face",
            "face detection failed",
        )

        if any(
            indicator in error_message
            for indicator in no_face_indicators
        ):
            return []

        # Do not hide unrelated model/input errors.
        raise

    if not representations:
        return []

    output = []

    for representation in representations:
        raw_embedding = representation.get("embedding")

        if raw_embedding is None:
            raise ValueError(
                "ArcFace returned a representation without an embedding."
            )

        embedding = np.asarray(
            raw_embedding,
            dtype=np.float32,
        )

        if embedding.shape != (512,):
            raise ValueError(
                f"Unexpected embedding shape: {embedding.shape}"
            )

        if not np.isfinite(embedding).all():
            raise ValueError(
                "Embedding contains invalid numerical values."
            )

        norm = float(np.linalg.norm(embedding))

        if norm <= 1e-12:
            continue

        embedding = embedding / norm

        facial_area = representation.get("facial_area")

        if not facial_area:
            raise ValueError(
                "ArcFace did not return facial-area information."
            )

        area = (
            int(facial_area["x"]),
            int(facial_area["y"]),
            int(facial_area["w"]),
            int(facial_area["h"]),
        )

        output.append((embedding, area))

    return output


# ---------------------------------------------------------
# MODEL STATUS
# ---------------------------------------------------------

def get_ai_model_status() -> dict:
    """
    Return model initialization status without exposing
    model weights or internal model objects.
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
