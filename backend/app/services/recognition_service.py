
import time

from collections import Counter, deque
from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np

from app.services.model_service import (
    embed_faces,
    initialize_ai_models,
)

from app.services.gallery_service import load_face_gallery

from app.services.gallery_student_service import (
    load_gallery_student_mapping,
)


@dataclass
class TrackState:

    last_seen: float

    last_face_check: float = 0.0

    votes: deque = field(default_factory=deque)

    confirmed_label: str | None = None

    last_candidate: str | None = None

    last_similarity: float | None = None

    last_margin: float | None = None

    last_face_status: str = "not_checked"

    last_face_dimensions: list | None = None

    last_error: str | None = None


class RecognitionEngine:
    """
    CPU-based real-time student recognition engine.

    YOLO11n:
        Person detection.

    ByteTrack:
        Persistent person tracking.

    RetinaFace:
        Face detection.

    ArcFace:
        512-dimensional face embeddings.

    Existing gallery:
        Seven enrolled student identities.

    Temporal voting:
        Confirms a student identity across multiple face checks.
    """

    def __init__(self):

        self.session_id = None

        self.models = None

        self.student_mapping = None

        self.config = None

        self.track_states = {}

    # ---------------------------------------------------------
    # 1. START RECOGNITION SESSION
    # ---------------------------------------------------------

    def start_session(self):

        if self.session_id is not None:

            raise RuntimeError(
                "A recognition session is already active."
            )

        print("\n========== RECOGNITION SESSION ==========")

        print("[SESSION] Initializing AI models...")

        self.models = initialize_ai_models()

        print("[SESSION] Loading gallery configuration...")

        _, _, self.config = load_face_gallery()

        print("[SESSION] Loading Supabase student mapping...")

        self.student_mapping = load_gallery_student_mapping()

        active_count = sum(
            1
            for item in self.student_mapping.values()
            if item["is_active"]
        )

        if active_count == 0:

            raise RuntimeError(
                "No active students are available for recognition."
            )

        self.track_states = {}

        self.session_id = str(uuid4())

        self._reset_tracker()

        print("[SESSION] Recognition session started.")

        print(f"[SESSION] Active identities: {active_count}")

        print("=========================================\n")

        return self.session_id

    # ---------------------------------------------------------
    # 2. STOP RECOGNITION SESSION
    # ---------------------------------------------------------

    def stop_session(self, session_id):

        if session_id != self.session_id:

            return

        print("\n[SESSION] Stopping recognition session...")

        self.track_states.clear()

        self._reset_tracker()

        self.session_id = None

        self.student_mapping = None

        self.config = None

        print("[SESSION] Recognition session stopped.")

    # ---------------------------------------------------------
    # 3. RESET BYTETRACK
    # ---------------------------------------------------------

    def _reset_tracker(self):

        if not self.models:

            return

        model = self.models["person_detector"]

        predictor = getattr(
            model,
            "predictor",
            None
        )

        if predictor is None:

            return

        trackers = getattr(
            predictor,
            "trackers",
            []
        )

        for tracker in trackers:

            try:

                tracker.reset()

            except Exception as exc:

                print(
                    "[TRACKER] Reset warning:",
                    repr(exc)
                )

    # ---------------------------------------------------------
    # 4. EXTRACT LIVE FACE EMBEDDING
    # ---------------------------------------------------------

    def _extract_live_embedding(self, frame, bbox):

        """
        Extract a face embedding from the COMPLETE YOLO
        person bounding box.

        The original upper-65% crop has been replaced because
        live testing showed that it truncates the detected face.

        Returns:
            embedding,
            diagnostic_status,
            face_dimensions,
            error
        """

        image_height, image_width = frame.shape[:2]

        x1, y1, x2, y2 = map(int, bbox)

        # Keep bounding box inside the frame.

        x1 = max(0, min(x1, image_width))

        x2 = max(0, min(x2, image_width))

        y1 = max(0, min(y1, image_height))

        y2 = max(0, min(y2, image_height))

        person_width = x2 - x1

        person_height = y2 - y1

        print(
            f"\n[FACE DEBUG] Person dimensions: "
            f"{person_width} x {person_height}"
        )

        # Minimum person crop validation.

        if person_width < 50 or person_height < 90:

            print(
                "[FACE DEBUG] Rejected: Person crop too small."
            )

            return None, "person_crop_too_small", None, None

        # -----------------------------------------------------
        # CORRECTION:
        # USE THE COMPLETE PERSON BOUNDING BOX.
        # -----------------------------------------------------

        person_crop = frame[
            y1:y2,
            x1:x2
        ]

        if person_crop.size == 0:

            print(
                "[FACE DEBUG] Rejected: Empty person crop."
            )

            return None, "empty_person_crop", None, None

        print(
            f"[FACE DEBUG] Complete person crop: "
            f"{person_crop.shape[1]} x {person_crop.shape[0]}"
        )

        # RetinaFace detection and ArcFace embedding.

        try:

            faces = embed_faces(person_crop)

        except Exception as exc:

            error_message = (
                f"{type(exc).__name__}: {exc}"
            )

            print(
                "[FACE DEBUG] DeepFace processing error:",
                error_message
            )

            return (
                None,
                "embedding_error",
                None,
                error_message
            )

        if not faces:

            print(
                "[FACE DEBUG] No face detected by RetinaFace."
            )

            return None, "no_face_detected", None, None

        print(
            f"[FACE DEBUG] Faces detected: {len(faces)}"
        )

        # Select the largest detected face.

        embedding, face_area = max(
            faces,
            key=lambda item: item[1][2] * item[1][3]
        )

        face_x, face_y, face_w, face_h = face_area

        face_dimensions = [
            int(face_w),
            int(face_h)
        ]

        print(
            f"[FACE DEBUG] Largest face: "
            f"{face_w} x {face_h}"
        )

        # Original configured thresholds.

        min_height = int(
            self.config["min_face_height"]
        )

        min_width = int(
            self.config["min_face_width"]
        )

        min_ratio = float(
            self.config["min_face_aspect_ratio"]
        )

        print(
            f"[FACE DEBUG] Required face dimensions: "
            f"{min_width} x {min_height}"
        )

        # Face height validation.

        if face_h < min_height:

            print(
                f"[FACE DEBUG] Rejected: "
                f"Face height {face_h} < {min_height}"
            )

            return (
                None,
                "face_too_short",
                face_dimensions,
                None
            )

        # Face width validation.

        if face_w < min_width:

            print(
                f"[FACE DEBUG] Rejected: "
                f"Face width {face_w} < {min_width}"
            )

            return (
                None,
                "face_too_narrow",
                face_dimensions,
                None
            )

        # Face aspect ratio validation.

        aspect_ratio = face_h / max(face_w, 1)

        print(
            f"[FACE DEBUG] Aspect ratio: "
            f"{aspect_ratio:.3f}"
        )

        if aspect_ratio < min_ratio:

            print(
                f"[FACE DEBUG] Rejected: "
                f"Aspect ratio {aspect_ratio:.3f} < {min_ratio}"
            )

            return (
                None,
                "invalid_face_aspect_ratio",
                face_dimensions,
                None
            )

        # Validate embedding.

        embedding = np.asarray(
            embedding,
            dtype=np.float32
        )

        if embedding.shape != (512,):

            print(
                "[FACE DEBUG] Invalid embedding shape:",
                embedding.shape
            )

            return (
                None,
                "invalid_embedding_shape",
                face_dimensions,
                None
            )

        if not np.isfinite(embedding).all():

            print(
                "[FACE DEBUG] Embedding contains invalid values."
            )

            return (
                None,
                "invalid_embedding",
                face_dimensions,
                None
            )

        print(
            "[FACE DEBUG] FACE ACCEPTED"
        )

        return (
            embedding,
            "accepted",
            face_dimensions,
            None
        )

    # ---------------------------------------------------------
    # 5. RANK STUDENT IDENTITY
    # ---------------------------------------------------------

    def _rank_identity(self, embedding):

        embedding = np.asarray(
            embedding,
            dtype=np.float32
        ).reshape(-1)

        if embedding.shape != (512,):

            raise ValueError(
                f"Expected 512-dimensional embedding, got {embedding.shape}"
            )

        norm = np.linalg.norm(embedding)

        if norm == 0 or not np.isfinite(norm):

            return None

        embedding = embedding / norm

        scores = []

        for label, student in self.student_mapping.items():

            if not student["is_active"]:

                continue

            reference_embeddings = np.asarray(
                student["embeddings"],
                dtype=np.float32
            )

            similarities = (
                reference_embeddings @ embedding
            )

            score = float(
                np.max(similarities)
            )

            scores.append(
                (label, score)
            )

        if not scores:

            return None

        scores.sort(
            key=lambda item: item[1],
            reverse=True
        )

        top_label, top_score = scores[0]

        second_score = (
            scores[1][1]
            if len(scores) > 1
            else 0.0
        )

        margin = top_score - second_score

        return {
            "label": top_label,
            "similarity": top_score,
            "margin": margin,
        }

    # ---------------------------------------------------------
    # 6. TEMPORAL IDENTITY VOTING
    # ---------------------------------------------------------

    def _update_identity(self, state, embedding):

        ranked = self._rank_identity(
            embedding
        )

        if ranked is None:

            state.votes.append(None)

            state.last_candidate = None

            return

        similarity = ranked["similarity"]

        margin = ranked["margin"]

        state.last_similarity = similarity

        state.last_margin = margin

        min_similarity = float(
            self.config["min_similarity"]
        )

        min_margin = float(
            self.config["min_margin"]
        )

        valid_match = (
            similarity >= min_similarity
            and margin >= min_margin
        )

        candidate = (
            ranked["label"]
            if valid_match
            else None
        )

        state.votes.append(candidate)

        state.last_candidate = candidate

        valid_votes = [
            vote
            for vote in state.votes
            if vote is not None
        ]

        vote_counts = Counter(valid_votes)

        if vote_counts:

            best_label, best_count = (
                vote_counts.most_common(1)[0]
            )

        else:

            best_label = None

            best_count = 0

        required_votes = int(
            self.config["required_votes"]
        )

        print(
            f"[MATCH DEBUG] Candidate: {candidate}"
        )

        print(
            f"[MATCH DEBUG] Similarity: {similarity:.4f}"
        )

        print(
            f"[MATCH DEBUG] Margin: {margin:.4f}"
        )

        print(
            f"[MATCH DEBUG] Valid votes: "
            f"{best_count}/{required_votes}"
        )

        if not valid_match:

            print(
                "[MATCH DEBUG] Rejected by similarity or margin."
            )

        if (
            best_label is not None
            and best_count >= required_votes
        ):

            state.confirmed_label = best_label

            print(
                f"[MATCH DEBUG] IDENTITY CONFIRMED: "
                f"{best_label}"
            )

    # ---------------------------------------------------------
    # 7. PROCESS CAMERA FRAME
    # ---------------------------------------------------------

    def process_frame(self, frame, session_id):

        if session_id != self.session_id:

            raise RuntimeError(
                "Invalid or expired recognition session."
            )

        if (
            not isinstance(frame, np.ndarray)
            or frame.size == 0
            or frame.ndim != 3
            or frame.shape[2] != 3
        ):

            raise ValueError(
                "Invalid BGR camera frame."
            )

        start_time = time.perf_counter()

        current_time = time.monotonic()

        model = self.models["person_detector"]

        # YOLO11 person detection and ByteTrack.

        results = model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],
            conf=float(
                self.config["yolo_confidence"]
            ),
            imgsz=int(
                self.config["yolo_image_size"]
            ),
            device="cpu",
            verbose=False,
        )

        people = []

        if results:

            result = results[0]

            boxes = result.boxes

            if boxes is not None and len(boxes) > 0:

                coordinates = (
                    boxes.xyxy.cpu().numpy()
                )

                track_ids = (
                    boxes.id.int().cpu().tolist()
                    if boxes.id is not None
                    else None
                )

                for index, bbox in enumerate(coordinates):

                    x1, y1, x2, y2 = map(
                        int,
                        bbox
                    )

                    # Without a tracker ID, temporal voting
                    # cannot safely maintain identity state.

                    if (
                        track_ids is None
                        or index >= len(track_ids)
                    ):

                        people.append({
                            "track_id": None,
                            "bbox": [x1, y1, x2, y2],
                            "status": "tracking",
                            "face_status": "no_track_id",
                            "student": None,
                            "similarity": None,
                            "margin": None,
                            "votes": 0,
                        })

                        print(
                            "[TRACKER] Person detected without Track ID."
                        )

                        continue

                    track_id = int(
                        track_ids[index]
                    )

                    # Create or retrieve track state.

                    state = self.track_states.get(
                        track_id
                    )

                    if state is None:

                        print(
                            f"\n[TRACKER] New track: {track_id}"
                        )

                        state = TrackState(
                            last_seen=current_time,
                            votes=deque(
                                maxlen=int(
                                    self.config["voting_window"]
                                )
                            ),
                        )

                        self.track_states[track_id] = state

                    state.last_seen = current_time

                    # Run face recognition at the configured interval.

                    face_interval = float(
                        self.config["face_check_interval"]
                    )

                    if (
                        current_time - state.last_face_check
                        >= face_interval
                    ):

                        state.last_face_check = current_time

                        (
                            embedding,
                            face_status,
                            face_dimensions,
                            face_error
                        ) = self._extract_live_embedding(
                            frame,
                            bbox
                        )

                        state.last_face_status = face_status

                        state.last_face_dimensions = face_dimensions

                        state.last_error = face_error

                        if embedding is not None:

                            self._update_identity(
                                state,
                                embedding
                            )

                        else:

                            state.last_candidate = None

                            state.votes.append(None)

                    # Resolve confirmed student details.

                    student_details = None

                    status = "unknown"

                    if state.confirmed_label is not None:

                        student = self.student_mapping.get(
                            state.confirmed_label
                        )

                        if student and student["is_active"]:

                            student_details = {
                                "student_id": student["student_id"],
                                "name": student["name"],
                                "roll_no": student["roll_no"],
                                "branch": student["branch"],
                                "role": student["role"],
                                "gallery_label": student["gallery_label"],
                            }

                            status = "recognized"

                    elif state.last_candidate is not None:

                        status = "pending"

                    # Include diagnostics in the API response.

                    people.append({

                        "track_id": track_id,

                        "bbox": [
                            x1,
                            y1,
                            x2,
                            y2
                        ],

                        "status": status,

                        "student": student_details,

                        "similarity": state.last_similarity,

                        "margin": state.last_margin,

                        "votes": sum(
                            1
                            for vote in state.votes
                            if vote is not None
                        ),

                        "face_status": state.last_face_status,

                        "face_dimensions": state.last_face_dimensions,

                        "face_error": state.last_error,

                    })

        # -----------------------------------------------------
        # 8. REMOVE EXPIRED TRACKS
        # -----------------------------------------------------

        lost_timeout = float(
            self.config["lost_track_timeout"]
        )

        expired_tracks = [

            track_id

            for track_id, state in self.track_states.items()

            if current_time - state.last_seen > lost_timeout

        ]

        for track_id in expired_tracks:

            print(
                f"[TRACKER] Removing expired track: {track_id}"
            )

            del self.track_states[track_id]

        # -----------------------------------------------------
        # 9. PROCESSING STATISTICS
        # -----------------------------------------------------

        processing_ms = (
            time.perf_counter() - start_time
        ) * 1000

        return {

            "type": "recognition_result",

            "frame_width": int(
                frame.shape[1]
            ),

            "frame_height": int(
                frame.shape[0]
            ),

            "people": people,

            "processing_ms": round(
                processing_ms,
                2
            ),

        }


# Shared recognition engine instance.

recognition_engine = RecognitionEngine()
