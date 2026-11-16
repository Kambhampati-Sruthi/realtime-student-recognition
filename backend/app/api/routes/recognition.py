
import asyncio

import cv2
import numpy as np

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.recognition_service import recognition_engine


router = APIRouter(
    prefix="/recognition",
    tags=["Recognition"],
)

# Only one camera session is permitted at a time.
camera_lock = asyncio.Lock()


@router.websocket("/ws")
async def recognition_websocket(websocket: WebSocket):

    await websocket.accept()

    # -----------------------------------------------------
    # 1. PREVENT MULTIPLE CAMERA SESSIONS
    # -----------------------------------------------------

    if camera_lock.locked():

        await websocket.send_json({
            "type": "error",
            "message": "Another camera session is already active.",
        })

        await websocket.close(code=1013)

        return

    await camera_lock.acquire()

    session_id = None

    try:

        # -------------------------------------------------
        # 2. INITIALIZE RECOGNITION SESSION
        # -------------------------------------------------

        print("[WEBSOCKET] Initializing recognition session...")

        session_id = await asyncio.to_thread(
            recognition_engine.start_session
        )

        await websocket.send_json({
            "type": "connected",
            "message": "AI recognition camera connected.",
            "session_id": session_id,
        })

        print(
            f"[WEBSOCKET] Session connected: {session_id}"
        )

        # -------------------------------------------------
        # 3. RECEIVE CAMERA FRAMES
        # -------------------------------------------------

        while True:

            frame_bytes = await websocket.receive_bytes()

            if not frame_bytes:
                continue

            # Limit incoming frame size.

            if len(frame_bytes) > 2 * 1024 * 1024:

                await websocket.send_json({
                    "type": "error",
                    "message": "Camera frame is too large.",
                })

                continue

            # -------------------------------------------------
            # 4. DECODE FRAME
            # -------------------------------------------------

            image_array = np.frombuffer(
                frame_bytes,
                dtype=np.uint8,
            )

            frame = cv2.imdecode(
                image_array,
                cv2.IMREAD_COLOR,
            )

            if frame is None:

                await websocket.send_json({
                    "type": "error",
                    "message": "Unable to decode camera frame.",
                })

                continue

            # -------------------------------------------------
            # 5. RUN AI RECOGNITION
            # -------------------------------------------------

            result = await asyncio.to_thread(
                recognition_engine.process_frame,
                frame,
                session_id,
            )

            # -------------------------------------------------
            # 6. SEND RECOGNITION RESULTS TO FRONTEND
            # -------------------------------------------------

            await websocket.send_json(result)

    except WebSocketDisconnect:

        print(
            "[WEBSOCKET] Camera WebSocket disconnected."
        )

    except Exception as exc:

        print(
            f"[WEBSOCKET] Recognition error: "
            f"{type(exc).__name__}: {exc}"
        )

        try:

            await websocket.send_json({
                "type": "error",
                "message": str(exc),
            })

        except Exception:

            pass

    finally:

        # -------------------------------------------------
        # 7. STOP RECOGNITION SESSION
        # -------------------------------------------------

        try:

            if session_id is not None:

                print(
                    "[WEBSOCKET] Stopping recognition session..."
                )

                await asyncio.to_thread(
                    recognition_engine.stop_session,
                    session_id,
                )

        except Exception as exc:

            print(
                f"[WEBSOCKET] Session cleanup error: {exc}"
            )

        finally:

            # Always release the camera lock.

            if camera_lock.locked():

                camera_lock.release()

            print(
                "[WEBSOCKET] Camera session released."
            )
