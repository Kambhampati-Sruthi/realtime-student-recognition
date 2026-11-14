
import asyncio

import cv2
import numpy as np

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.recognition_service import recognition_engine


router = APIRouter(
    prefix="/recognition",
    tags=["Recognition"],
)

# One active camera session at a time.
camera_lock = asyncio.Lock()


@router.websocket("/ws")
async def recognition_websocket(websocket: WebSocket):

    await websocket.accept()

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
        # Initialize the AI session.
        session_id = await asyncio.to_thread(
            recognition_engine.start_session
        )

        await websocket.send_json({
            "type": "connected",
            "message": "AI recognition camera connected.",
            "session_id": session_id,
        })

        while True:

            frame_bytes = await websocket.receive_bytes()

            if not frame_bytes:
                continue

            # Protect the backend from excessively large frames.
            if len(frame_bytes) > 2 * 1024 * 1024:
                await websocket.send_json({
                    "type": "error",
                    "message": "Camera frame is too large.",
                })
                continue

            image_array = np.frombuffer(
                frame_bytes,
                dtype=np.uint8
            )

            frame = cv2.imdecode(
                image_array,
                cv2.IMREAD_COLOR
            )

            if frame is None:
                await websocket.send_json({
                    "type": "error",
                    "message": "Unable to decode camera frame.",
                })
                continue

            result = await asyncio.to_thread(
                recognition_engine.process_frame,
                frame,
                session_id,
            )

            await websocket.send_json(result)

    except WebSocketDisconnect:
        print("Camera WebSocket disconnected.")

    except Exception as exc:
        print(
            f"Recognition WebSocket error: {exc}"
        )

        try:
            await websocket.send_json({
                "type": "error",
                "message": "Recognition processing failed.",
            })
        except Exception:
            pass

    finally:

        if session_id is not None:
            await asyncio.to_thread(
                recognition_engine.stop_session,
                session_id,
            )

        camera_lock.release()
