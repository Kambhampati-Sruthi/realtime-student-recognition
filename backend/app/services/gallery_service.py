import json
from functools import lru_cache
from pathlib import Path

import numpy as np


BACKEND_DIR = Path(__file__).resolve().parents[2]
GALLERY_DIR = BACKEND_DIR / "artifacts" / "gallery"

GALLERY_PATH = GALLERY_DIR / "face_gallery.npz"
MANIFEST_PATH = GALLERY_DIR / "gallery_manifest.json"
CONFIG_PATH = GALLERY_DIR / "recognition_config.json"

EMBEDDING_DIMENSION = 512

DEFAULT_RECOGNITION_CONFIG = {
    "min_face_height": 40,
    "min_face_width": 40,
    "min_face_aspect_ratio": 0.65,
    "min_similarity": 0.55,
    "min_margin": 0.08,
    "voting_window": 5,
    "required_votes": 3,
    "face_check_interval": 0.5,
    "lost_track_timeout": 3.0,
    "yolo_confidence": 0.45,
    "yolo_image_size": 640,
    "recognition_model": "ArcFace",
    "device": "cpu",
}


@lru_cache(maxsize=1)
def load_recognition_config() -> dict:
    """
    Load recognition thresholds from local JSON if available,
    falling back safely to validated production defaults so cloud
    deployments without local artifacts never crash.
    """
    if CONFIG_PATH.is_file():
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            loaded = json.load(file)
        if not isinstance(loaded, dict):
            raise ValueError("Recognition configuration must be a JSON object.")
        config = {**DEFAULT_RECOGNITION_CONFIG, **loaded}
    else:
        config = dict(DEFAULT_RECOGNITION_CONFIG)

    if int(config["required_votes"]) < 1:
        raise ValueError("required_votes must be at least 1.")

    if int(config["voting_window"]) < int(config["required_votes"]):
        raise ValueError("voting_window cannot be smaller than required_votes.")

    return config


@lru_cache(maxsize=1)
def load_face_gallery():
    """
    Load the legacy static gallery if present on disk.
    Live recognition uses load_gallery_student_mapping() from Supabase.
    """
    required_files = [GALLERY_PATH, MANIFEST_PATH]
    for file_path in required_files:
        if not file_path.is_file():
            raise FileNotFoundError(f"Required gallery file not found: {file_path}")

    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    config = load_recognition_config()

    identity_count = manifest.get("identity_count")
    embedding_dimension = manifest.get("embedding_dimension")
    arrays_metadata = manifest.get("arrays")

    if not isinstance(identity_count, int) or identity_count <= 0:
        raise ValueError("Invalid identity count in gallery manifest.")
    if embedding_dimension != EMBEDDING_DIMENSION:
        raise ValueError(f"Expected {EMBEDDING_DIMENSION}-dimensional embeddings.")
    if not isinstance(arrays_metadata, dict) or len(arrays_metadata) != identity_count:
        raise ValueError("Invalid arrays metadata in gallery manifest.")

    gallery = {}
    seen_labels = set()

    with np.load(GALLERY_PATH, allow_pickle=False) as archive:
        if set(archive.files) != set(arrays_metadata.keys()):
            raise ValueError("NPZ archive keys do not match gallery manifest.")

        for label, metadata in arrays_metadata.items():
            normalized_label = label.strip().casefold()
            if not normalized_label or normalized_label in seen_labels:
                raise ValueError(f"Invalid or duplicate gallery identity: {label}")
            seen_labels.add(normalized_label)

            embeddings = np.asarray(archive[label], dtype=np.float32)
            if (
                embeddings.ndim != 2
                or embeddings.shape[1] != EMBEDDING_DIMENSION
                or embeddings.shape[0] == 0
                or not np.all(np.isfinite(embeddings))
            ):
                raise ValueError(f"Invalid embedding array for {label}.")

            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            if np.any(norms <= 1e-12):
                raise ValueError(f"Zero-magnitude embedding for {label}.")

            gallery[label] = (embeddings / norms).astype(np.float32)

    return gallery, manifest, config


def clear_gallery_caches():
    """Clear cached local gallery and recognition configuration."""
    load_face_gallery.cache_clear()
    load_recognition_config.cache_clear()


def get_gallery_summary() -> dict:
    """
    Return Supabase gallery summary for monitoring/diagnostics without
    requiring legacy local .npz files.
    """
    from app.services.gallery_student_service import load_gallery_student_mapping

    config = load_recognition_config()
    mapping = load_gallery_student_mapping() or {}
    active_students = {
        label: item
        for label, item in mapping.items()
        if item.get("is_active", False)
    }
    total_embeddings = sum(
        int(np.asarray(item["embeddings"]).shape[0])
        for item in active_students.values()
        if item.get("embeddings") is not None
    )

    return {
        "status": "loaded" if active_students else "empty",
        "source": "supabase",
        "identity_count": len(active_students),
        "total_embeddings": total_embeddings,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "identities": list(active_students.keys()),
        "recognition_model": config.get("recognition_model", "ArcFace"),
        "device": config.get("device", "cpu"),
    }