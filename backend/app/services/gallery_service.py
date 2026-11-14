
import json
from functools import lru_cache
from pathlib import Path

import numpy as np


# Resolve the backend directory independently of the
# terminal's current working directory.
BACKEND_DIR = Path(__file__).resolve().parents[2]

GALLERY_DIR = BACKEND_DIR / "artifacts" / "gallery"

GALLERY_PATH = GALLERY_DIR / "face_gallery.npz"
MANIFEST_PATH = GALLERY_DIR / "gallery_manifest.json"
CONFIG_PATH = GALLERY_DIR / "recognition_config.json"


@lru_cache(maxsize=1)
def load_face_gallery():
    """
    Load and validate the existing ArcFace embeddings.

    Returns:
        dict[str, np.ndarray]:
            {
                "Amulya": array of shape (5, 512),
                "Haritha": array of shape (5, 512),
                ...
            }
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

    # Read gallery metadata.
    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    # Read recognition configuration.
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = json.load(file)

    if manifest.get("gallery_type") != "test_gallery_no_blur":
        raise ValueError("Unexpected gallery type.")

    identity_count = manifest.get("identity_count")
    embedding_dimension = manifest.get("embedding_dimension")
    arrays_metadata = manifest.get("arrays")

    if not isinstance(identity_count, int) or identity_count <= 0:
        raise ValueError("Invalid identity count in gallery manifest.")

    if not isinstance(embedding_dimension, int) or embedding_dimension <= 0:
        raise ValueError("Invalid embedding dimension in gallery manifest.")

    if not isinstance(arrays_metadata, dict):
        raise ValueError("Invalid arrays metadata in gallery manifest.")

    if len(arrays_metadata) != identity_count:
        raise ValueError("Identity count does not match manifest arrays.")

    gallery = {}
    seen_labels = set()

    # Load the NPZ archive safely without allowing pickled objects.
    with np.load(GALLERY_PATH, allow_pickle=False) as archive:

        if set(archive.files) != set(arrays_metadata.keys()):
            raise ValueError(
                "NPZ archive keys do not match gallery manifest."
            )

        for array_key, metadata in arrays_metadata.items():

            gallery_label = metadata.get("gallery_label")

            if not isinstance(gallery_label, str) or not gallery_label.strip():
                raise ValueError(
                    f"Invalid gallery label for {array_key}."
                )

            gallery_label = gallery_label.strip()

            if gallery_label in seen_labels:
                raise ValueError(
                    f"Duplicate gallery label: {gallery_label}"
                )

            seen_labels.add(gallery_label)

            embeddings = np.array(
                archive[array_key],
                dtype=np.float32,
                copy=True,
            )

            expected_count = metadata.get("embedding_count")
            expected_dimension = metadata.get("embedding_dimension")

            if embeddings.ndim != 2:
                raise ValueError(
                    f"{gallery_label}: embeddings must be a 2D array."
                )

            if embeddings.shape != (
                expected_count,
                expected_dimension,
            ):
                raise ValueError(
                    f"{gallery_label}: embedding shape mismatch. "
                    f"Found {embeddings.shape}."
                )

            if embeddings.shape[1] != embedding_dimension:
                raise ValueError(
                    f"{gallery_label}: unexpected embedding dimension."
                )

            if not np.isfinite(embeddings).all():
                raise ValueError(
                    f"{gallery_label}: embeddings contain invalid values."
                )

            gallery[gallery_label] = embeddings

    if len(gallery) != identity_count:
        raise ValueError("Loaded gallery identity count is incorrect.")

    return gallery, manifest, config


def get_gallery_summary():
    """
    Return a summary without exposing the embedding values.
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
