
import cv2
from ultralytics import YOLO
from pathlib import Path

MODEL_PATH = Path("models/yolo11n.pt")
CONFIDENCE = 0.35
IMAGE_SIZE = 640

def main():
    if not MODEL_PATH.exists():
        print(f"ERROR: Model not found: {MODEL_PATH}")
        return

    print("Loading YOLO11n...")
    model = YOLO(str(MODEL_PATH))
    print("YOLO11n loaded.")

    print("Opening webcam...")
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camera.isOpened():
        print("ERROR: Unable to open webcam.")
        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print("Webcam opened.")
    print("Stand in front of the camera.")
    print("Press Q to quit.")

    frame_count = 0

    try:
        while True:
            success, frame = camera.read()

            if not success:
                print("ERROR: Unable to read webcam frame.")
                break

            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                classes=[0],
                conf=CONFIDENCE,
                imgsz=IMAGE_SIZE,
                device="cpu",
                verbose=False
            )

            frame_count += 1
            detection_count = 0

            if results and results[0].boxes is not None:
                boxes = results[0].boxes

                if boxes.xyxy is not None:
                    for box in boxes:
                        coordinates = box.xyxy[0].cpu().numpy().astype(int)
                        confidence = float(box.conf[0].cpu().item())

                        x1, y1, x2, y2 = coordinates
                        detection_count += 1

                        cv2.rectangle(
                            frame,
                            (x1, y1),
                            (x2, y2),
                            (0, 255, 0),
                            2
                        )

                        label = f"Person {confidence:.2f}"

                        cv2.putText(
                            frame,
                            label,
                            (x1, max(y1 - 10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 0),
                            2
                        )

            cv2.putText(
                frame,
                f"Detections: {detection_count}",
                (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 255),
                2
            )

            if frame_count % 30 == 0:
                print(
                    f"Frame {frame_count}: "
                    f"{detection_count} person(s) detected"
                )

            cv2.imshow("YOLO11n Webcam Detection Test", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        print("Webcam test completed.")


if __name__ == "__main__":
    main()
