
import sys
from pathlib import Path

import cv2
import numpy as np


# ---------------------------------------------------------
# 1. BACKEND PATH
# ---------------------------------------------------------

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ---------------------------------------------------------
# 2. IMPORT EXISTING SERVICES
# ---------------------------------------------------------

from app.services.model_service import embed_faces
from app.services.gallery_service import load_face_gallery


# ---------------------------------------------------------
# 3. CONFIGURATION
# ---------------------------------------------------------

CARD_PATH = BACKEND_DIR / "data" / "idcard" / "Amulya.jpeg"

BLUR_INDEX = 3

EXPECTED_IDENTITY = "Amulya"


# ---------------------------------------------------------
# 4. ORIGINAL NOTEBOOK: CARD FACE EXTRACTION
# ---------------------------------------------------------

def card_face(card_bgr):
    """
    Reproduce the original notebook's card_face() function.

    - Upscaling factors: 1, 2, 3
    - Largest face selection
    - 40% margin
    - Minimum crop dimension: 160 pixels
    """

    for scale in (1, 2, 3):

        if scale == 1:
            resized = card_bgr

        else:
            resized = cv2.resize(
                card_bgr,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC
            )

        faces = embed_faces(resized)

        if not faces:
            continue

        _, (x, y, w, h) = max(
            faces,
            key=lambda item: item[1][2] * item[1][3]
        )

        margin = int(0.4 * w)

        face = resized[
            max(y - margin, 0):y + h + margin,
            max(x - margin, 0):x + w + margin
        ]

        if face.size == 0:
            continue

        if min(face.shape[:2]) < 160:

            factor = 160 / min(face.shape[:2])

            face = cv2.resize(
                face,
                None,
                fx=factor,
                fy=factor,
                interpolation=cv2.INTER_CUBIC
            )

        return face

    return None


# ---------------------------------------------------------
# 5. ORIGINAL NOTEBOOK: IMAGE VARIATIONS
# ---------------------------------------------------------

def variants(face):

    h, w = face.shape[:2]

    small = cv2.resize(
        face,
        (max(w // 2, 32), max(h // 2, 32))
    )

    return [
        face,

        cv2.flip(face, 1),

        cv2.resize(
            small,
            (w, h),
            interpolation=cv2.INTER_LINEAR
        ),

        cv2.GaussianBlur(
            face,
            (0, 0),
            2.0
        ),

        cv2.convertScaleAbs(
            face,
            alpha=0.8,
            beta=-10
        ),

        cv2.convertScaleAbs(
            face,
            alpha=1.1,
            beta=15
        )
    ]


# ---------------------------------------------------------
# 6. ORIGINAL NOTEBOOK: IDENTITY RANKING
# ---------------------------------------------------------

def rank_identity_scores(embedding, gallery):

    embedding = np.asarray(
        embedding,
        dtype=np.float32
    ).reshape(-1)

    norm = np.linalg.norm(embedding)

    if norm == 0:
        raise ValueError("Invalid zero-length embedding.")

    embedding = embedding / norm

    scores = {}

    for name, reference_embeddings in gallery.items():

        similarities = reference_embeddings @ embedding

        scores[name] = float(np.max(similarities))

    return sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )


# ---------------------------------------------------------
# 7. MAIN COMPATIBILITY TEST
# ---------------------------------------------------------

def main():

    print("\n============================================")
    print("ARCFACE EMBEDDING COMPATIBILITY TEST")
    print("============================================")

    # Verify ID card image.
    if not CARD_PATH.is_file():
        raise FileNotFoundError(
            f"ID card image not found: {CARD_PATH}"
        )

    # Load existing gallery.
    gallery, manifest, config = load_face_gallery()

    print("\nExisting gallery loaded.")

    print("Gallery type:", manifest["gallery_type"])
    print("Identities:", len(gallery))
    print("Embedding dimension:", manifest["embedding_dimension"])

    # Read original ID card.
    card = cv2.imread(str(CARD_PATH))

    if card is None:
        raise RuntimeError("Could not read Amulya.jpeg")

    print("\nID card image:", CARD_PATH.name)
    print("Original dimensions:", card.shape)

    # Extract card portrait using original notebook logic.
    print("\nExtracting ID card face...")

    face = card_face(card)

    if face is None:
        raise RuntimeError(
            "Could not extract face from the ID card."
        )

    print("Face crop dimensions:", face.shape)

    # Generate the original six variations.
    face_variations = variants(face)

    print("\nGenerated variations:", len(face_variations))

    # Use the exact original gallery's recognition thresholds.
    min_similarity = float(config.get("min_similarity", 0.38))
    min_margin = float(config.get("min_margin", 0.055))

    print("\nRecognition thresholds:")
    print("Minimum similarity:", min_similarity)
    print("Minimum margin:", min_margin)

    results = []

    print("\n============================================")
    print("TESTING NON-BLUR VARIATIONS")
    print("============================================")

    for index, variation in enumerate(face_variations):

        # Exclude only GaussianBlur, exactly as the final gallery does.
        if index == BLUR_INDEX:
            print("\nVariation 4: GaussianBlur - SKIPPED")
            continue

        print(f"\nProcessing variation {index + 1}...")

        detected_faces = embed_faces(variation)

        if not detected_faces:
            print("No face detected in this variation.")

            results.append({
                "variation": index + 1,
                "success": False
            })

            continue

        # Select largest detected face.
        embedding, _ = max(
            detected_faces,
            key=lambda item: item[1][2] * item[1][3]
        )

        if embedding.shape != (512,):
            raise ValueError(
                f"Unexpected embedding shape: {embedding.shape}"
            )

        # Rank against all seven saved identities.
        scores = rank_identity_scores(
            embedding,
            gallery
        )

        best_name, best_score = scores[0]
        second_name, second_score = scores[1]

        margin = best_score - second_score

        threshold_pass = (
            best_score >= min_similarity
            and margin >= min_margin
        )

        expected_identity_top = (
            best_name.casefold() == EXPECTED_IDENTITY.casefold()
        )

        print("Embedding shape:", embedding.shape)

        print(
            f"Top identity: {best_name} "
            f"({best_score:.4f})"
        )

        print(
            f"Second identity: {second_name} "
            f"({second_score:.4f})"
        )

        print(f"Similarity margin: {margin:.4f}")

        print("Expected identity is top-ranked:", expected_identity_top)
        print("Original thresholds passed:", threshold_pass)

        results.append({
            "variation": index + 1,
            "success": True,
            "best_identity": best_name,
            "best_score": best_score,
            "margin": margin,
            "threshold_pass": threshold_pass,
            "expected_identity_top": expected_identity_top
        })

    # -----------------------------------------------------
    # 8. FINAL SUMMARY
    # -----------------------------------------------------

    successful = [
        item for item in results
        if item["success"]
    ]

    expected_matches = [
        item for item in successful
        if item["expected_identity_top"]
    ]

    threshold_matches = [
        item for item in successful
        if item["threshold_pass"]
    ]

    print("\n============================================")
    print("COMPATIBILITY TEST SUMMARY")
    print("============================================")

    print("Expected identity:", EXPECTED_IDENTITY)
    print("Non-blur variations:", 5)
    print("Successful embeddings:", len(successful))
    print("Correct top-ranked identities:", len(expected_matches))
    print("Variations passing original thresholds:", len(threshold_matches))

    if len(successful) == 5 and len(expected_matches) == 5:
        print("\nCOMPATIBILITY RESULT: PASS")

    else:
        print("\nCOMPATIBILITY RESULT: REVIEW REQUIRED")

    print("\nExisting gallery was not modified.")
    print("No embeddings were saved.")
    print("No camera was opened.")

    print("============================================")


if __name__ == "__main__":
    main()
