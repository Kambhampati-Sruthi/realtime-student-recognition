
import time

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np

from app.config import settings

from app.services.model_service import (
    embed_faces,
    initialize_ai_models,
)

from app.services.gallery_service import load_recognition_config

from app.services.gallery_student_service import (
    load_gallery_student_mapping,
)

from app.database.supabase_client import get_supabase_client


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

    # Database event tracking.

    recognition_event_id: str | None = None

    event_student_id: str | None = None

    first_seen_at: str | None = None

    last_event_update: float = 0.0

    last_event_attempt: float = 0.0


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
        Active enrolled students and their ArcFace embeddings from Supabase.

    Temporal voting:
        Confirms identity across multiple face checks.

    Supabase:
        Automatically stores confirmed recognition events.
    """

    def __init__(self):

        self.session_id = None

        self.models = None

        self.student_mapping = None

        self.config = None

        self.track_states = {}

        self.supabase = None

        self.last_heartbeat = 0.0

        self.last_gallery_refresh = 0.0

    # ---------------------------------------------------------
    # 1. START RECOGNITION SESSION
    # ---------------------------------------------------------

    def start_session(self):

        if self.session_id is not None:

            raise RuntimeError(
                "A recognition session is already active."
            )

        print("\n========== RECOGNITION SESSION ==========")

        session_created = False

        try:

            print("[SESSION] Initializing AI models...")

            self.models = initialize_ai_models()

            print("[SESSION] Connecting to Supabase...")

            self.supabase = get_supabase_client()

            if self.supabase is None:

                raise RuntimeError(
                    "Supabase client could not be initialized."
                )

            print("[SESSION] Loading recognition configuration...")

            self.config = load_recognition_config()

            print("[SESSION] Loading enrolled student embeddings...")

            self.student_mapping = load_gallery_student_mapping()

            if not self.student_mapping:

                raise RuntimeError(
                    "Student gallery is empty. Enroll students and generate face embeddings before starting recognition."
                )

            active_count = sum(
                1
                for item in self.student_mapping.values()
                if item.get("is_active", False)
                and item.get("embeddings") is not None
                and len(item.get("embeddings", [])) > 0
            )

            if active_count == 0:

                raise RuntimeError(
                    "No active enrolled students with face embeddings are available for recognition."
                )

            self._validate_recognition_config(self.config)

            self.track_states = {}

            self._reset_tracker()

            # recognition_sessions.id has no database default, so the
            # application generates and explicitly inserts the UUID.
            self.session_id = str(uuid4())

            now = datetime.now(timezone.utc).isoformat()

            self.supabase.table("recognition_sessions").insert({
                "id": self.session_id,
                "camera_id": None,
                "started_at": now,
                "last_heartbeat": now,
                "status": "active",
            }).execute()

            session_created = True

            monotonic_now = time.monotonic()
            self.last_heartbeat = monotonic_now
            self.last_gallery_refresh = monotonic_now

            print("[SESSION] Recognition session started and saved to Supabase.")

            print(
                f"[SESSION] Active enrolled identities: {active_count}"
            )

            print(
                f"[SESSION] Voting configuration: "
                f"{self.config['required_votes']} valid votes "
                f"within {self.config['voting_window']} checks"
            )

            print(
                f"[SESSION] Supabase persistence: "
                f"{'configured' if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY else 'NOT CONFIGURED'}"
            )

            print("=========================================\n")

            return self.session_id

        except Exception as exc:

            print("[SESSION ERROR] Could not start recognition session:", repr(exc))

            if session_created and self.supabase is not None and self.session_id:

                try:

                    now = datetime.now(timezone.utc).isoformat()

                    self.supabase.table("recognition_sessions").update({
                        "status": "error",
                        "stopped_at": now,
                        "last_heartbeat": now,
                    }).eq("id", self.session_id).execute()

                except Exception as db_exc:

                    print("[DATABASE ERROR] Could not mark failed session:", repr(db_exc))

            self.track_states.clear()
            self.session_id = None
            self.student_mapping = None
            self.config = None
            self.supabase = None
            self.last_heartbeat = 0.0
            self.last_gallery_refresh = 0.0

            raise

    def _validate_recognition_config(self, config):

        required_config = [
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

        if not isinstance(config, dict):

            raise RuntimeError("Recognition configuration must be a dictionary.")

        missing_config = [key for key in required_config if key not in config]

        if missing_config:

            raise RuntimeError(
                f"Missing recognition configuration: {missing_config}"
            )

        if int(config["required_votes"]) < 1:

            raise RuntimeError("Required votes must be at least 1.")

        if int(config["voting_window"]) < int(config["required_votes"]):

            raise RuntimeError(
                "Voting window cannot be smaller than required votes."
            )

    def _maintain_session(self):

        """Persist a heartbeat and periodically reload enrolled identities."""

        if self.supabase is None or self.session_id is None:

            return

        now_monotonic = time.monotonic()

        if now_monotonic - self.last_heartbeat >= 5.0:

            try:

                now = datetime.now(timezone.utc).isoformat()

                self.supabase.table("recognition_sessions").update({
                    "last_heartbeat": now,
                }).eq("id", self.session_id).eq("status", "active").execute()

                self.last_heartbeat = now_monotonic

            except Exception as exc:

                print("[DATABASE WARNING] Session heartbeat failed:", repr(exc))

        if now_monotonic - self.last_gallery_refresh >= 30.0:

            try:

                refreshed_mapping = load_gallery_student_mapping()

                # An empty mapping is meaningful: it can mean all students
                # were deactivated or their enrollments were removed.
                self.student_mapping = refreshed_mapping or {}

                refreshed_config = load_recognition_config()

                self._validate_recognition_config(refreshed_config)

                self.config = refreshed_config
                self.last_gallery_refresh = now_monotonic

                print("[GALLERY] Student embeddings and recognition configuration refreshed.")

            except Exception as exc:

                print("[GALLERY WARNING] Dynamic gallery refresh failed; retaining the previous gallery:", repr(exc))

    # ---------------------------------------------------------
    # 2. STOP RECOGNITION SESSION
    # ---------------------------------------------------------

    def stop_session(self, session_id):

        if session_id != self.session_id:

            return

        print("\n[SESSION] Stopping recognition session...")

        if self.supabase is not None and self.session_id:

            try:

                now = datetime.now(timezone.utc).isoformat()

                self.supabase.table("recognition_sessions").update({
                    "status": "stopped",
                    "stopped_at": now,
                    "last_heartbeat": now,
                }).eq("id", self.session_id).eq("status", "active").execute()

                print("[DATABASE] Recognition session marked as stopped.")

            except Exception as exc:

                print("[DATABASE ERROR] Could not update stopped session:", repr(exc))

        self.track_states.clear()
        self._reset_tracker()

        self.session_id = None
        self.student_mapping = None
        self.config = None
        self.supabase = None
        self.last_heartbeat = 0.0
        self.last_gallery_refresh = 0.0

        print("[SESSION] Recognition session stopped.")

    # ---------------------------------------------------------
    # 3. RESET BYTETRACK
    # ---------------------------------------------------------

    def _reset_tracker(self):

        if not self.models:

            return

        model = self.models.get("person_detector")

        if model is None:

            return

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
        Extract a face embedding from the complete YOLO
        person bounding box.

        Returns:
            embedding,
            diagnostic_status,
            face_dimensions,
            error
        """

        image_height, image_width = frame.shape[:2]

        x1, y1, x2, y2 = map(int, bbox)

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

        if person_width < 50 or person_height < 90:

            print(
                "[FACE DEBUG] Rejected: Person crop too small."
            )

            return None, "person_crop_too_small", None, None

        # Use the complete person bounding box.

        person_crop = frame[y1:y2, x1:x2]

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

        # Validate the embedding.

        embedding = np.asarray(
            embedding,
            dtype=np.float32
        ).reshape(-1)

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

        embedding_norm = np.linalg.norm(embedding)

        if embedding_norm <= 1e-12:

            print(
                "[FACE DEBUG] Embedding has zero magnitude."
            )

            return (
                None,
                "invalid_embedding_norm",
                face_dimensions,
                None
            )

        # Normalize embedding.

        embedding = embedding / embedding_norm

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
                f"Expected 512-dimensional embedding, "
                f"got {embedding.shape}"
            )

        norm = np.linalg.norm(embedding)

        if norm <= 1e-12 or not np.isfinite(norm):

            return None

        embedding = embedding / norm

        scores = []

        for label, student in self.student_mapping.items():

            if not student.get("is_active", False):

                continue

            reference_embeddings = np.asarray(
                student["embeddings"],
                dtype=np.float32
            )

            if (
                reference_embeddings.ndim != 2
                or reference_embeddings.shape[1] != 512
                or reference_embeddings.shape[0] == 0
            ):

                print(
                    f"[MATCH WARNING] Invalid gallery embeddings: {label}"
                )

                continue

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

        ranked = self._rank_identity(embedding)

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
    # 7. GET STUDENT DETAILS
    # ---------------------------------------------------------

    def _get_student_details(self, label):

        if label is None or self.student_mapping is None:

            return None

        student = self.student_mapping.get(label)

        if not student:

            return None

        if not student.get("is_active", False):

            return None

        return {
            "student_id": student["student_id"],
            "name": student["name"],
            "roll_no": student["roll_no"],
            "branch": student["branch"],
            "role": student["role"],
            "gallery_label": student["gallery_label"],
        }

    # ---------------------------------------------------------
    # 8. SAVE OR UPDATE RECOGNITION EVENT
    # ---------------------------------------------------------

    def _save_recognition_event(
        self,
        state,
        track_id,
        student_details,
        similarity,
    ):

        """Insert a recognition event once, then update its last_seen."""

        if not student_details:

            return False

        if self.supabase is None or not self.session_id:

            print("[DATABASE ERROR] Supabase client or recognition session is missing.")

            return False

        student_id = student_details.get("student_id")

        if not student_id:

            print("[DATABASE ERROR] Student UUID is missing.")

            return False

        now = datetime.now(timezone.utc).isoformat()

        try:

            if state.recognition_event_id is None:

                payload = {
                    "student_id": student_id,
                    "session_id": self.session_id,
                    "track_id": str(track_id),
                    "camera_id": None,
                    "first_seen": state.first_seen_at or now,
                    "last_seen": now,
                    "similarity_score": float(similarity or 0.0),
                }

                response = self.supabase.table("recognition_events").insert(payload).execute()
                records = getattr(response, "data", None) or []

                if not records or not records[0].get("id"):

                    raise RuntimeError(
                        "Supabase did not return the inserted recognition event ID."
                    )

                state.recognition_event_id = records[0]["id"]
                state.event_student_id = student_id
                state.first_seen_at = payload["first_seen"]
                state.last_event_update = time.monotonic()

                print("\n[DATABASE] RECOGNITION EVENT INSERTED")
                print(f"[DATABASE] Student: {student_details['name']}")
                print(f"[DATABASE] Roll number: {student_details['roll_no']}")
                print(f"[DATABASE] Event ID: {state.recognition_event_id}")

                return True

            payload = {
                "last_seen": now,
                "similarity_score": float(similarity or 0.0),
            }

            if state.event_student_id != student_id:

                payload["student_id"] = student_id

            self.supabase.table("recognition_events").update(payload).eq(
                "id", state.recognition_event_id
            ).execute()

            state.event_student_id = student_id
            state.last_event_update = time.monotonic()

            print(
                f"[DATABASE] Recognition event updated: {student_details['name']}"
            )

            return True

        except Exception as exc:

            print("\n[DATABASE ERROR] Recognition event operation failed:")
            print(repr(exc))

            return False

    # ---------------------------------------------------------
    # 10. PROCESS CAMERA FRAME
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

        self._maintain_session()

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

                coordinates = boxes.xyxy.cpu().numpy()

                tracker_ids = None

                if boxes.id is not None:

                    tracker_ids = (
                        boxes.id.int().cpu().tolist()
                    )

                for index, bbox in enumerate(coordinates):

                    x1, y1, x2, y2 = map(int, bbox)

                    # Temporal voting requires a stable track ID.

                    if (
                        tracker_ids is None
                        or index >= len(tracker_ids)
                    ):

                        people.append({

                            "track_id": None,

                            "bbox": [
                                x1,
                                y1,
                                x2,
                                y2
                            ],

                            "status": "tracking",

                            "student": None,

                            "last_candidate": None,

                            "similarity": None,

                            "margin": None,

                            "votes": 0,

                            "required_votes": int(
                                self.config["required_votes"]
                            ),

                            "face_status": "no_track_id",

                            "face_dimensions": None,

                            "face_error": None,

                        })

                        print(
                            "[TRACKER] Person detected without Track ID."
                        )

                        continue

                    track_id = int(
                        tracker_ids[index]
                    )

                    # Retrieve or create track state.

                    state = self.track_states.get(track_id)

                    if state is None:

                        print(
                            f"\n[TRACKER] New track: {track_id}"
                        )

                        state = TrackState(

                            last_seen=current_time,

                            first_seen_at=datetime.now(timezone.utc).isoformat(),

                            votes=deque(
                                maxlen=int(
                                    self.config["voting_window"]
                                )
                            ),

                        )

                        self.track_states[track_id] = state

                    state.last_seen = current_time

                    # Perform face recognition at configured interval.

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
                            face_error,
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

                    # Get confirmed student details.

                    student_details = self._get_student_details(
                        state.confirmed_label
                    )

                    # -------------------------------------------------
                    # AUTOMATIC SUPABASE PERSISTENCE
                    # -------------------------------------------------

                    if student_details is not None:

                        should_save_event = (

                            state.recognition_event_id is None

                            and (
                                current_time - state.last_event_attempt
                                >= 5.0
                                or state.last_event_attempt == 0.0
                            )

                        )

                        should_update_event = (

                            state.recognition_event_id is not None

                            and (
                                current_time - state.last_event_update
                                >= 2.0
                            )

                        )

                        if (
                            should_save_event
                            or should_update_event
                        ):

                            state.last_event_attempt = current_time

                            self._save_recognition_event(

                                state=state,

                                track_id=track_id,

                                student_details=student_details,

                                similarity=state.last_similarity,

                            )

                    # Determine recognition status.

                    if student_details is not None:

                        status = "recognized"

                    elif state.last_candidate is not None:

                        status = "pending"

                    elif state.last_face_status == "not_checked":

                        status = "tracking"

                    else:

                        status = "unknown"

                    # Count votes for the best candidate.

                    vote_counts = Counter(
                        vote
                        for vote in state.votes
                        if vote is not None
                    )

                    candidate_votes = (
                        vote_counts.get(
                            state.confirmed_label
                            or state.last_candidate,
                            0
                        )
                    )

                    # Include information required by frontend.

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

                        "last_candidate": state.last_candidate,

                        "similarity": state.last_similarity,

                        "margin": state.last_margin,

                        "votes": candidate_votes,

                        "required_votes": int(
                            self.config["required_votes"]
                        ),

                        "face_status": state.last_face_status,

                        "face_dimensions": state.last_face_dimensions,

                        "face_error": state.last_error,

                        "recognition_event_id": (
                            state.recognition_event_id
                        ),

                    })

        # -----------------------------------------------------
        # 11. REMOVE EXPIRED TRACKS
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
        # 12. PROCESSING STATISTICS
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


# ---------------------------------------------------------
# SHARED RECOGNITION ENGINE INSTANCE
# ---------------------------------------------------------

recognition_engine = RecognitionEngine()
