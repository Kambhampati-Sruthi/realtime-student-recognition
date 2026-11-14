
import cv2
import time
import numpy as np

from app.services.model_service import (
    initialize_ai_models,
    embed_faces
)


# ==========================================
# ORIGINAL COLAB CONFIGURATION
# ==========================================

CONFIDENCE = 0.35
IMAGE_SIZE = 640

MIN_FACE_HEIGHT = 110
MIN_FACE_WIDTH = 100
MIN_FACE_ASPECT_RATIO = 0.70

TEST_DURATION = 60
CHECK_INTERVAL = 1.5


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def is_face_inside_person(face_area, person_box):

    fx, fy, fw, fh = face_area
    x1, y1, x2, y2 = person_box

    face_center_x = fx + fw / 2
    face_center_y = fy + fh / 2

    return (
        x1 <= face_center_x <= x2
        and y1 <= face_center_y <= y2
    )


def draw_person_box(image, box):

    x1, y1, x2, y2 = map(int, box)

    height = y2 - y1

    upper_y2 = y1 + int(height * 0.65)

    # Complete person bounding box: GREEN
    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2
    )

    # Upper 65% crop: YELLOW
    cv2.rectangle(
        image,
        (x1, y1),
        (x2, upper_y2),
        (0, 255, 255),
        2
    )

    cv2.putText(
        image,
        "YOLO PERSON",
        (x1, max(y1 - 10, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 0),
        2
    )


def draw_face_box(image, area, label="RETINAFACE"):

    x, y, w, h = area

    cv2.rectangle(
        image,
        (x, y),
        (x + w, y + h),
        (255, 0, 0),
        2
    )

    cv2.putText(
        image,
        label,
        (x, max(y - 8, 20)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 0, 0),
        2
    )


def print_face_information(embedding, area, source):

    x, y, w, h = area

    face_h = h
    face_w = w

    aspect_ratio = face_h / max(face_w, 1)

    print(f"\nSOURCE: {source}")
    print("FACE AREA:", area)

    print("FACE WIDTH:", face_w)
    print("FACE HEIGHT:", face_h)

    print("ASPECT RATIO:", round(aspect_ratio, 3))

    print("EMBEDDING SHAPE:", embedding.shape)

    print(
        "EMBEDDING NORM:",
        round(float(np.linalg.norm(embedding)), 4)
    )

    print(
        "PASSES HEIGHT:",
        face_h >= MIN_FACE_HEIGHT
    )

    print(
        "PASSES WIDTH:",
        face_w >= MIN_FACE_WIDTH
    )

    print(
        "PASSES ASPECT RATIO:",
        aspect_ratio >= MIN_FACE_ASPECT_RATIO
    )

    if (
        face_h >= MIN_FACE_HEIGHT
        and face_w >= MIN_FACE_WIDTH
        and aspect_ratio >= MIN_FACE_ASPECT_RATIO
    ):

        print("[RESULT] FACE PASSED ORIGINAL COLAB FILTERS.")

    else:

        print(
            "[RESULT] FACE DETECTED, "
            "BUT REJECTED BY SIZE FILTERS."
        )


# ==========================================
# MAIN DIAGNOSTIC
# ==========================================

def main():

    print("\n========================================")
    print("LIVE RETINAFACE + ARCFACE DIAGNOSTIC")
    print("========================================")

    print("\nInitializing AI models...")

    models = initialize_ai_models()

    person_model = models["person_detector"]

    print("\nYOLO11n initialized.")
    print("RetinaFace initialized.")
    print("ArcFace initialized.")

    print("Inference device:", models["device"])

    print("\nOpening webcam...")

    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camera.isOpened():

        camera.release()
        camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        raise RuntimeError("Unable to open webcam.")

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    start_time = time.time()
    last_check = 0

    frame_count = 0

    full_frame_face_count = 0
    person_crop_face_count = 0
    full_person_face_count = 0
    valid_embedding_count = 0

    try:

        while time.time() - start_time < TEST_DURATION:

            success, frame = camera.read()

            if not success or frame is None:

                print("[CAMERA ERROR] Unable to read frame.")
                continue

            frame_count += 1

            display_frame = frame.copy()

            # ==================================
            # YOLO PERSON DETECTION
            # ==================================

            try:

                result = person_model.track(
                    frame,
                    persist=True,
                    tracker="bytetrack.yaml",
                    classes=[0],
                    conf=CONFIDENCE,
                    imgsz=IMAGE_SIZE,
                    device="cpu",
                    verbose=False
                )[0]

                boxes = result.boxes

                if boxes is None or len(boxes) == 0:

                    cv2.putText(
                        display_frame,
                        "NO PERSON DETECTED",
                        (20, 35),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2
                    )

                    cv2.imshow(
                        "YOLO and RetinaFace Diagnostic",
                        display_frame
                    )

                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                    continue

                person_boxes = (
                    boxes.xyxy.cpu().numpy().astype(int)
                )

            except Exception as error:

                print("[YOLO ERROR]", repr(error))
                continue

            # ==================================
            # DRAW YOLO PERSON BOXES
            # ==================================

            for index, box in enumerate(person_boxes):

                draw_person_box(display_frame, box)

                cv2.putText(
                    display_frame,
                    f"Person {index + 1}",
                    (20, 65 + index * 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

            # ==================================
            # PERIODIC FACE DIAGNOSTICS
            # ==================================

            if time.time() - last_check >= CHECK_INTERVAL:

                last_check = time.time()

                print("\n----------------------------------------")
                print("FRAME:", frame_count)
                print("FRAME DIMENSIONS:", frame.shape)

                # ==================================
                # TEST 1: FULL FRAME FACE DETECTION
                # ==================================

                print("\n[TEST 1] FULL FRAME FACE DETECTION")

                full_frame_faces = []

                try:

                    full_frame_faces = embed_faces(frame)

                    print(
                        "Faces detected:",
                        len(full_frame_faces)
                    )

                    full_frame_face_count += len(
                        full_frame_faces
                    )

                    for embedding, area in full_frame_faces:

                        print_face_information(
                            embedding,
                            area,
                            "FULL FRAME"
                        )

                        draw_face_box(
                            display_frame,
                            area,
                            "FULL FRAME FACE"
                        )

                        if embedding.shape == (512,):

                            valid_embedding_count += 1

                except Exception as error:

                    print(
                        "[FULL FRAME ERROR]",
                        repr(error)
                    )

                # ==================================
                # TEST 2: PERSON CROPS
                # ==================================

                print("\n[TEST 2] PERSON CROP DETECTION")

                frame_h, frame_w = frame.shape[:2]

                for index, box in enumerate(person_boxes):

                    x1, y1, x2, y2 = map(int, box)

                    x1 = max(0, min(x1, frame_w - 1))
                    y1 = max(0, min(y1, frame_h - 1))

                    x2 = max(0, min(x2, frame_w))
                    y2 = max(0, min(y2, frame_h))

                    person_width = x2 - x1
                    person_height = y2 - y1

                    print(
                        f"\n[PERSON {index + 1}] "
                        f"width={person_width}, "
                        f"height={person_height}"
                    )

                    if (
                        person_width < 50
                        or person_height < 90
                    ):

                        print("PERSON BOX TOO SMALL.")
                        continue

                    # ==================================
                    # ORIGINAL UPPER 65% CROP
                    # ==================================

                    upper_y2 = y1 + int(
                        person_height * 0.65
                    )

                    person_crop = frame[
                        y1:upper_y2,
                        x1:x2
                    ]

                    print(
                        "UPPER 65% CROP:",
                        person_crop.shape
                    )

                    try:

                        crop_faces = embed_faces(
                            person_crop
                        )

                        print(
                            "Faces in upper crop:",
                            len(crop_faces)
                        )

                        person_crop_face_count += len(
                            crop_faces
                        )

                        for embedding, area in crop_faces:

                            print_face_information(
                                embedding,
                                area,
                                "UPPER 65% CROP"
                            )

                    except Exception as error:

                        print(
                            "[UPPER CROP ERROR]",
                            repr(error)
                        )

                    # ==================================
                    # COMPLETE PERSON CROP
                    # ==================================

                    complete_person_crop = frame[
                        y1:y2,
                        x1:x2
                    ]

                    print(
                        "\nCOMPLETE PERSON CROP:",
                        complete_person_crop.shape
                    )

                    try:

                        complete_faces = embed_faces(
                            complete_person_crop
                        )

                        print(
                            "Faces in complete person crop:",
                            len(complete_faces)
                        )

                        full_person_face_count += len(
                            complete_faces
                        )

                        for embedding, area in complete_faces:

                            print_face_information(
                                embedding,
                                area,
                                "COMPLETE PERSON CROP"
                            )

                            if embedding.shape == (512,):

                                valid_embedding_count += 1

                            fx, fy, fw, fh = area

                            # Convert crop coordinates
                            # into full-frame coordinates.
                            absolute_area = (
                                x1 + fx,
                                y1 + fy,
                                fw,
                                fh
                            )

                            draw_face_box(
                                display_frame,
                                absolute_area,
                                "PERSON CROP FACE"
                            )

                    except Exception as error:

                        print(
                            "[COMPLETE PERSON ERROR]",
                            repr(error)
                        )

                    # ==================================
                    # FACE-PERSON ASSOCIATION
                    # ==================================

                    print(
                        "\n[TEST 3] FACE-PERSON ASSOCIATION"
                    )

                    for embedding, area in full_frame_faces:

                        inside = is_face_inside_person(
                            area,
                            (x1, y1, x2, y2)
                        )

                        print(
                            "Face inside person box:",
                            inside
                        )

                        if inside:

                            print(
                                "[RESULT] FACE CENTER "
                                "IS INSIDE YOLO BOX."
                            )

                        else:

                            print(
                                "[RESULT] FACE CENTER "
                                "IS OUTSIDE YOLO BOX."
                            )

                print("\nDIAGNOSTIC FRAME COMPLETED.")

            # ==================================
            # DISPLAY LIVE DIAGNOSTIC
            # ==================================

            cv2.putText(
                display_frame,
                "Press Q to quit",
                (15, frame_h - 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2
            )

            cv2.imshow(
                "YOLO and RetinaFace Diagnostic",
                display_frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):

                break

    finally:

        camera.release()
        cv2.destroyAllWindows()

        print("\n========================================")
        print("DIAGNOSTIC COMPLETED")
        print("========================================")

        print("Frames processed:", frame_count)

        print(
            "Full-frame face detections:",
            full_frame_face_count
        )

        print(
            "Upper crop face detections:",
            person_crop_face_count
        )

        print(
            "Complete person crop face detections:",
            full_person_face_count
        )

        print(
            "Valid 512-D embeddings:",
            valid_embedding_count
        )


if __name__ == "__main__":

    main()
