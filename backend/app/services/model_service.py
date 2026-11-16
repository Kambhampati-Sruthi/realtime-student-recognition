
import os

# This project uses CPU-only inference.
# These must be set before importing TensorFlow or DeepFace.
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.config import settings

from deepface import DeepFace
from ultralytics import YOLO


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[2]

YOLO_PATH = Path(settings.YOLO_MODEL_PATH)

if not YOLO_PATH.is_absolute():
    YOLO_PATH = BACKEND_DIR / YOLO_PATH

DEVICE = str(settings.DEVICE).strip().lower()

EMBEDDING_DIMENSION = 512
FACE_RECOGNITION_MODEL = "ArcFace"
FACE_DETECTOR_BACKEND = "retinaface"

# DeepFace uses BGR NumPy images supplied by OpenCV.
IMAGE_CHANNELS = 3


# ---------------------------------------------------------
# MODEL INITIALIZATION
# ---------------------------------------------------------

@lru_cache(maxsize=1)
def initialize_ai_models() -> dict[str, Any]:
    """
    Initialize all application AI models once.

    Models:
        1. YOLO11n - person detection and tracking.
        2. RetinaFace - face detection and alignment.
        3. ArcFace - 512-dimensional face embeddings.

    Inference:
        CPU only.

    Returns:
        Dictionary containing initialized model objects.
    """

    if DEVICE != "cpu":
        raise RuntimeError(
            "This application is configured for CPU-only inference. "
            "Set DEVICE=cpu in the application configuration."
        )

    print("\n========== AI MODEL INITIALIZATION ==========")

    # -----------------------------------------------------
    # 1. YOLO11n PERSON DETECTION
    # -----------------------------------------------------

    if not YOLO_PATH.is_file():
        raise FileNotFoundError(
            f"YOLO model file not found: {YOLO_PATH}"
        )

    print("\nLoading YOLO11n person detector...")

    person_detector = YOLO(str(YOLO_PATH))

    person_detector.to("cpu")

    model_names = person_detector.names

    if isinstance(model_names, dict):
        person_class_name = model_names.get(0)
    elif isinstance(model_names, (list, tuple)):
        person_class_name = (
            model_names[0]
            if len(model_names) > 0
            else None
        )
    else:
        person_class_name = None

    if person_class_name != "person":
        raise RuntimeError(
            "YOLO model class 0 must represent 'person'. "
            f"Received: {person_class_name}"
        )

    print("YOLO11n loaded successfully.")
    print("YOLO inference device: CPU")

    # -----------------------------------------------------
    # 2. RETINAFACE INITIALIZATION
    # -----------------------------------------------------

    print("\nInitializing RetinaFace...")

    from retinaface import RetinaFace

    face_detector = RetinaFace.build_model()

    if face_detector is None:
        raise RuntimeError(
            "RetinaFace initialization failed."
        )

    print("RetinaFace initialized successfully.")

    # -----------------------------------------------------
    # 3. ARCFACE INITIALIZATION
    # -----------------------------------------------------

    print("\nInitializing ArcFace...")

    face_recognition_model = DeepFace.build_model(
        model_name=FACE_RECOGNITION_MODEL,
        task="facial_recognition",
    )

    if face_recognition_model is None:
        raise RuntimeError(
            "ArcFace initialization failed."
        )

    print("ArcFace initialized successfully.")
    print(f"Embedding dimension: {EMBEDDING_DIMENSION}")

    # -----------------------------------------------------
    # 4. RETURN INITIALIZED MODELS
    # -----------------------------------------------------

    models = {
        "person_detector": person_detector,
        "face_detector": face_detector,
        "face_recognition": face_recognition_model,
        "device": "cpu",
    }

    print("\nAll AI models initialized successfully.")
    print("Inference device: CPU")
    print("=============================================\n")

    return models


# ---------------------------------------------------------
# INPUT VALIDATION
# ---------------------------------------------------------

def _validate_face_input(image_bgr: np.ndarray):
    """
    Validate the OpenCV BGR image supplied to the face pipeline.
    """

    if image_bgr is None:
        raise ValueError("Input image is None.")

    if not isinstance(image_bgr, np.ndarray):
        raise ValueError(
            "Input must be a NumPy image array."
        )

    if image_bgr.size == 0:
        raise ValueError("Input image is empty.")

    if image_bgr.ndim != 3:
        raise ValueError(
            "Expected a three-dimensional image."
        )

    if image_bgr.shape[2] != IMAGE_CHANNELS:
        raise ValueError(
            "Expected a three-channel BGR image."
        )

    if image_bgr.dtype != np.uint8:
        raise ValueError(
            "Expected an 8-bit unsigned BGR image."
        )

    height, width = image_bgr.shape[:2]

    if height < 1 or width < 1:
        raise ValueError("Invalid image dimensions.")


# ---------------------------------------------------------
# NO-FACE ERROR HANDLING
# ---------------------------------------------------------

def _is_no_face_error(exc: Exception) -> bool:
    """
    Identify expected face-detection failures.

    Other model errors must not be silently treated as
    images containing no faces.
    """

    message = str(exc).lower()

    no_face_indicators = (
        "face could not be detected",
        "no face detected",
        "no face was detected",
        "cannot detect face",
        "face detection failed",
        "failed to detect face",
    )

    return any(
        indicator in message
        for indicator in no_face_indicators
    )


# ---------------------------------------------------------
# FACIAL AREA VALIDATION
# ---------------------------------------------------------

def _extract_facial_area(
    representation: dict,
    image_width: int,
    image_height: int,
):
    """
    Convert DeepFace facial_area into:

        (x, y, width, height)

    Coordinates are clipped to the image boundaries.
    """

    facial_area = representation.get("facial_area")

    if not isinstance(facial_area, dict):
        return None

    try:
        x = int(round(float(facial_area["x"])))
        y = int(round(float(facial_area["y"])))
        width = int(round(float(facial_area["w"])))
        height = int(round(float(facial_area["h"])))

    except (KeyError, TypeError, ValueError, OverflowError):
        return None

    if width <= 0 or height <= 0:
        return None

    # Clip the face rectangle to the image boundaries.
    left = max(0, x)
    top = max(0, y)

    right = min(
        image_width,
        x + width,
    )

    bottom = min(
        image_height,
        y + height,
    )

    clipped_width = right - left
    clipped_height = bottom - top

    if clipped_width <= 0 or clipped_height <= 0:
        return None

    return (
        left,
        top,
        clipped_width,
        clipped_height,
    )


# ---------------------------------------------------------
# ARCFACE EMBEDDING VALIDATION
# ---------------------------------------------------------

def _normalize_embedding(raw_embedding) -> np.ndarray:
    """
    Validate and L2-normalize one ArcFace embedding.

    Output:
        float32 NumPy array with shape (512,).
    """

    embedding = np.asarray(
        raw_embedding,
        dtype=np.float32,
    ).reshape(-1)

    if embedding.shape != (EMBEDDING_DIMENSION,):
        raise ValueError(
            "Unexpected ArcFace embedding dimension. "
            f"Expected {EMBEDDING_DIMENSION}, "
            f"received {embedding.shape}."
        )

    if not np.isfinite(embedding).all():
        raise ValueError(
            "ArcFace embedding contains invalid numerical values."
        )

    norm = float(np.linalg.norm(embedding))

    if norm <= 1e-12:
        raise ValueError(
            "ArcFace returned a zero-magnitude embedding."
        )

    normalized = embedding / norm

    return normalized.astype(np.float32)


# ---------------------------------------------------------
# FACE DETECTION + EMBEDDING EXTRACTION
# ---------------------------------------------------------

def embed_faces(image_bgr: np.ndarray) -> list:
    """
    Detect faces using RetinaFace and extract ArcFace embeddings.

    Input:
        Three-channel uint8 BGR image.

    Output:
        List of tuples:

            [
                (embedding, facial_area),
                ...
            ]

        embedding:
            float32 NumPy array, shape (512,)

        facial_area:
            (x, y, width, height)

    Features:
        - RetinaFace face detection.
        - Face alignment.
        - ArcFace feature extraction.
        - L2-normalized embeddings.
        - Multiple-face support.
        - Invalid face detections are skipped.

    An empty list is returned when no face is detected.
    Other model errors are propagated.
    """

    # -----------------------------------------------------
    # 1. Validate input
    # -----------------------------------------------------

    _validate_face_input(image_bgr)

    image_height, image_width = image_bgr.shape[:2]

    # -----------------------------------------------------
    # 2. Ensure models are initialized
    # -----------------------------------------------------

    initialize_ai_models()

    # -----------------------------------------------------
    # 3. RetinaFace + ArcFace inference
    # -----------------------------------------------------

    try:
        representations = DeepFace.represent(
            img_path=image_bgr,
            model_name=FACE_RECOGNITION_MODEL,
            detector_backend=FACE_DETECTOR_BACKEND,
            enforce_detection=True,
            align=True,
        )

    except ValueError as exc:

        if _is_no_face_error(exc):
            return []

        raise

    if not representations:
        return []

    # DeepFace may return one dictionary or a list of dictionaries,
    # depending on the version and inference result.
    if isinstance(representations, dict):
        representations = [representations]

    # -----------------------------------------------------
    # 4. Validate every detected face and embedding
    # -----------------------------------------------------

    output = []

    for representation in representations:

        if not isinstance(representation, dict):
            continue

        raw_embedding = representation.get("embedding")

        if raw_embedding is None:
            continue

        facial_area = _extract_facial_area(
            representation,
            image_width,
            image_height,
        )

        if facial_area is None:
            continue

        embedding = _normalize_embedding(raw_embedding)

        output.append(
            (
                embedding,
                facial_area,
            )
        )

    return output


# ---------------------------------------------------------
# PERSON DETECTOR ACCESS
# ---------------------------------------------------------

def get_person_detector():
    """
    Return the initialized YOLO11n person detector.

    Recognition service can use this model for:
        - Person detection.
        - ByteTrack tracking.
        - Real-time person bounding boxes.

    Face detection and recognition remain separate operations.
    """

    models = initialize_ai_models()

    return models["person_detector"]


# ---------------------------------------------------------
# FACE MODEL STATUS
# ---------------------------------------------------------

def get_ai_model_status() -> dict:
    """
    Return the application AI model status.

    This function initializes the models if they have not
    already been initialized.
    """

    models = initialize_ai_models()

    return {
        "status": "loaded",
        "person_detector": "YOLO11n",
        "face_detector": "RetinaFace",
        "face_recognition": "ArcFace",
        "embedding_dimension": EMBEDDING_DIMENSION,
        "device": models["device"],
        "yolo_model_path": str(YOLO_PATH),
    }
