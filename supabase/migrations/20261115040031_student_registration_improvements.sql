-- Prevent duplicate recognition events when camera_id is NULL.
-- Existing duplicates are checked before creating the unique index.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.recognition_events
        WHERE camera_id IS NULL
        GROUP BY session_id, track_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Duplicate recognition events exist for NULL camera_id. Resolve duplicates before applying this migration.';
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS
    idx_recognition_events_session_track_no_camera
ON public.recognition_events (session_id, track_id)
WHERE camera_id IS NULL;
