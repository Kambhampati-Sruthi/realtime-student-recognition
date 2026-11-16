
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


@lru_cache(maxsize=1)
def load_recognition_config():
    """
    Load the existing recognition configuration.

    The configuration remains local because it contains model and
    recognition thresholds, not student identity data.
    """
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(
            f"Recognition configuration not found: {CONFIG_PATH}"
        )

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if not isinstance(config, dict):
        raise ValueError(
            "Recognition configuration must be a JSON object."
        )

    required = [
        "min_face_height",
        "min_face_width",
        "min_face_aspect_ratio",
        "min_similarity",
        "min_margin",
        "voting_window",
        "required_votes",
        "face_check_interval",
        "lost_track_timeout",
        "yolo_confidence",
        "yolo_image_size",
    ]

    missing = [key for key in required if key not in config]

    if missing:
        raise ValueError(
            f"Missing recognition configuration: {missing}"
        )

    if int(config["required_votes"]) < 1:
        raise ValueError("required_votes must be at least 1.")

    if int(config["voting_window"]) < int(config["required_votes"]):
        raise ValueError(
            "voting_window cannot be smaller than required_votes."
        )

    return config


@lru_cache(maxsize=1)
def load_face_gallery():
    """
    Load the legacy static gallery.

    Retained for compatibility with existing tools and diagnostics.
    Live recognition should use load_gallery_student_mapping(), which
    reads current student embeddings from Supabase.
    """
    required_files = [
        GALLERY_PATH,
        MANIFEST_PATH,
        CONFIG_PATH,
    ]

    for file_path in required_files:
        if not file_path.is_file():
            raise FileNotFoundError(
                f"Required gallery file not found: {file_path}"
            )

    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    config = load_recognition_config()

    if manifest.get("gallery_type") != "test_gallery_no_blur":
        raise ValueError("Unexpected gallery type.")

    identity_count = manifest.get("identity_count")
    embedding_dimension = manifest.get("embedding_dimension")
    arrays_metadata = manifest.get("arrays")

    if not isinstance(identity_count, int) or identity_count <= 0:
        raise ValueError("Invalid identity count in gallery manifest.")

    if embedding_dimension != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSION}-dimensional embeddings."
        )

    if not isinstance(arrays_metadata, dict):
        raise ValueError("Invalid arrays metadata in gallery manifest.")

    if len(arrays_metadata) != identity_count:
        raise ValueError(
            "Identity count does not match manifest arrays."
        )

    gallery = {}
    seen_labels = set()

    with np.load(GALLERY_PATH, allow_pickle=False) as archive:
        if set(archive.files) != set(arrays_metadata.keys()):
            raise ValueError(
                "NPZ archive keys do not match gallery manifest."
            )

        for label, metadata in arrays_metadata.items():
            normalized_label = label.strip().casefold()

            if not normalized_label:
                raise ValueError("Empty gallery identity label.")

            if normalized_label in seen_labels:
                raise ValueError(
                    f"Duplicate gallery identity: {label}"
                )

            seen_labels.add(normalized_label)

            embeddings = np.asarray(
                archive[label],
                dtype=np.float32,
            )

            if embeddings.ndim != 2:
                raise ValueError(
                    f"Invalid embedding array for {label}."
                )

            if embeddings.shape[1] != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Invalid embedding dimension for {label}."
                )

            if embeddings.shape[0] == 0:
                raise ValueError(
                    f"No embeddings available for {label}."
                )

            if not np.all(np.isfinite(embeddings)):
                raise ValueError(
                    f"Non-finite embedding values for {label}."
                )

            norms = np.linalg.norm(
                embeddings,
                axis=1,
                keepdims=True,
            )

            if np.any(norms <= 1e-12):
                raise ValueError(
                    f"Zero-magnitude embedding for {label}."
                )

            embeddings = embeddings / norms

            expected_shape = metadata.get("shape")

            if expected_shape is not None:
                if list(embeddings.shape) != list(expected_shape):
                    raise ValueError(
                        f"Embedding shape mismatch for {label}."
                    )

            gallery[label] = embeddings.astype(np.float32)

    if len(gallery) != identity_count:
        raise ValueError(
            "Loaded gallery identity count is incorrect."
        )

    return gallery, manifest, config


def clear_gallery_caches():
    """Clear cached local gallery and recognition configuration."""
    load_face_gallery.cache_clear()
    load_recognition_config.cache_clear()


def get_gallery_summary():
    """
    Return legacy static-gallery information without exposing embeddings.
    """
    gallery, manifest, config = load_face_gallery()

    return {
        "status": "loaded",
        "gallery_type": manifest["gallery_type"],
        "identity_count": len(gallery),
        "total_embeddings": sum(
            embeddings.shape[0]
            for embeddings in gallery.values()
        ),
        "embedding_dimension": manifest["embedding_dimension"],
        "identities": list(gallery.keys()),
        "recognition_model": config.get("recognition_model"),
        "device": config.get("device"),
    }
