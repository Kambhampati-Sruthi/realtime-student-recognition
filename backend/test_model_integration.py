
import cv2
import numpy as np

from pathlib import Path

from app.services.model_service import (
    initialize_ai_models,
    embed_faces
)

from app.services.recognition_service import recognition_engine


BASE_DIR = Path(__file__).resolve().parent

ID_CARD_DIR = BASE_DIR / "data" / "idcard"

STUDENT_IMAGES = {
    "Amulya": ID_CARD_DIR / "Amulya.jpeg",
    "Haritha": ID_CARD_DIR / "Haritha.jpeg",
    "Manasa": ID_CARD_DIR / "Manasa.jpeg",
    "Mounika": ID_CARD_DIR / "Mounika.jpeg",
    "Revathi": ID_CARD_DIR / "Revathi.jpeg",
    "Sruthi": ID_CARD_DIR / "Sruthi.jpeg",
    "Taruni": ID_CARD_DIR / "Taruni.jpeg",
}


def main():

    print("\n====================================")
    print(" AI MODEL INTEGRATION TEST")
    print("====================================")

    session_id = None

    try:

        # 1. Initialize YOLO, RetinaFace and ArcFace
        print("\n[1] Initializing AI models...")

        models = initialize_ai_models()

        print("YOLO11n: LOADED")
        print("RetinaFace: LOADED")
        print("ArcFace: LOADED")

        # 2. Load existing gallery and Supabase mapping
        print("\n[2] Loading student gallery mapping...")

        session_id = recognition_engine.start_session()

        print("Gallery mapping: LOADED")
        print("Active identities:", len(
            recognition_engine.student_mapping
        ))

        # 3. Test each ID card
        print("\n[3] Testing student ID cards...")

        passed = 0
        failed = 0

        for expected_name, image_path in STUDENT_IMAGES.items():

            print("\n------------------------------------")
            print("Expected student:", expected_name)
            print("Image:", image_path.name)

            if not image_path.is_file():
                print("RESULT: IMAGE NOT FOUND")
                failed += 1
                continue

            image = cv2.imread(str(image_path))

            if image is None:
                print("RESULT: IMAGE COULD NOT BE READ")
                failed += 1
                continue

            print("Image dimensions:", image.shape)

            # RetinaFace detection + ArcFace embedding
            try:
                faces = embed_faces(image)

            except Exception as exc:
                print("FACE PROCESSING ERROR:", repr(exc))
                failed += 1
                continue

            if not faces:
                print("RESULT: NO FACE DETECTED")
                failed += 1
                continue

            print("Faces detected:", len(faces))

            # Test every detected face
            best_result = None

            for embedding, face_area in faces:

                x, y, w, h = face_area

                print("Face dimensions:", w, "x", h)
                print("Embedding shape:", embedding.shape)

                if embedding.shape != (512,):
                    print("INVALID EMBEDDING DIMENSION")
                    continue

                # Compare with the existing seven-person gallery
                ranked = recognition_engine._rank_identity(
                    embedding
                )

                if ranked is None:
                    continue

                print("Predicted identity:", ranked["label"])
                print("Similarity:", round(
                    ranked["similarity"], 4
                ))
                print("Margin:", round(
                    ranked["margin"], 4
                ))

                if (
                    best_result is None
                    or ranked["similarity"] >
                    best_result["similarity"]
                ):
                    best_result = ranked

            if best_result is None:
                print("RESULT: MATCHING FAILED")
                failed += 1
                continue

            if best_result["label"].casefold() == expected_name.casefold():
                print("RESULT: CORRECT IDENTITY")
                passed += 1
            else:
                print("RESULT: IDENTITY MISMATCH")
                failed += 1

        print("\n====================================")
        print(" TEST SUMMARY")
        print("====================================")
        print("Passed:", passed)
        print("Failed:", failed)
        print("Total:", len(STUDENT_IMAGES))

    finally:

        if session_id is not None:
            recognition_engine.stop_session(session_id)

        print("\nAI model integration test completed.")


if __name__ == "__main__":
    main()
