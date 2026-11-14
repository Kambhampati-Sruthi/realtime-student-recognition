
import cv2
import time

from app.services.recognition_service import recognition_engine


def main():

    print("\n====================================")
    print(" LIVE CAMERA RECOGNITION TEST")
    print("====================================")

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("ERROR: Unable to open webcam.")
        return

    session_id = None

    try:

        print("\nStarting AI recognition session...")

        session_id = recognition_engine.start_session()

        print("Session started.")
        print("Keep one enrolled student's face visible.")
        print("Press Q to stop the test.")

        last_process_time = 0

        while True:

            success, frame = camera.read()

            if not success:
                print("ERROR: Unable to read webcam frame.")
                break

            current_time = time.monotonic()

            # Match the frontend's approximate 500 ms interval.
            if current_time - last_process_time >= 0.5:

                last_process_time = current_time

                # Match frontend's maximum frame width.
                height, width = frame.shape[:2]

                if width > 640:
                    new_height = int(height * 640 / width)
                    frame = cv2.resize(frame, (640, new_height))

                # Match frontend JPEG quality.
                success, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, 72]
                )

                if not success:
                    continue

                decoded_frame = cv2.imdecode(
                    encoded,
                    cv2.IMREAD_COLOR
                )

                # Run the actual application recognition engine.
                result = recognition_engine.process_frame(
                    decoded_frame,
                    session_id
                )

                print("\n-------------------------------")
                print(
                    "Processing:",
                    result["processing_ms"],
                    "ms"
                )

                if not result["people"]:
                    print("No people detected.")

                for person in result["people"]:

                    print(
                        "Track:",
                        person["track_id"],
                        "| Status:",
                        person["status"],
                        "| Similarity:",
                        person["similarity"],
                        "| Margin:",
                        person["margin"],
                        "| Votes:",
                        person["votes"]
                    )

                    student = person.get("student")

                    if student:
                        print("RECOGNIZED STUDENT:")
                        print("Name:", student["name"])
                        print("Roll number:", student["roll_no"])
                        print("Branch:", student["branch"])
                        print("Role:", student["role"])

            # Display camera preview.
            display_frame = frame.copy()

            cv2.putText(
                display_frame,
                "Live Recognition Test - Press Q to exit",
                (15, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2
            )

            cv2.imshow(
                "AI Student Recognition Test",
                display_frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except Exception as exc:

        print("\nLIVE RECOGNITION ERROR:")
        print(repr(exc))

    finally:

        camera.release()
        cv2.destroyAllWindows()

        if session_id is not None:
            recognition_engine.stop_session(session_id)

        print("\nLive camera test completed.")


if __name__ == "__main__":
    main()
