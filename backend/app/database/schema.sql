
-- =========================================
-- 1. STUDENTS TABLE
-- =========================================

CREATE TABLE IF NOT EXISTS public.students (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    roll_no TEXT UNIQUE NOT NULL,

    name TEXT NOT NULL,

    branch TEXT,

    role TEXT DEFAULT 'student',

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- =========================================
-- 2. CAMERAS TABLE
-- =========================================

CREATE TABLE IF NOT EXISTS public.cameras (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    camera_name TEXT NOT NULL,

    location TEXT,

    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- =========================================
-- 3. RECOGNITION EVENTS TABLE
-- =========================================

CREATE TABLE IF NOT EXISTS public.recognition_events (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    student_id UUID NOT NULL
        REFERENCES public.students(id),

    session_id UUID NOT NULL,

    track_id TEXT NOT NULL,

    camera_id UUID
        REFERENCES public.cameras(id),

    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    similarity_score REAL,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (session_id, camera_id, track_id)
);


-- =========================================
-- 4. INDEXES FOR FASTER QUERIES
-- =========================================

CREATE INDEX IF NOT EXISTS idx_students_roll_no
ON public.students(roll_no);

CREATE INDEX IF NOT EXISTS idx_events_student
ON public.recognition_events(student_id);

CREATE INDEX IF NOT EXISTS idx_events_first_seen
ON public.recognition_events(first_seen DESC);

CREATE INDEX IF NOT EXISTS idx_events_camera
ON public.recognition_events(camera_id);


-- =========================================
-- 5. ENABLE ROW LEVEL SECURITY
-- =========================================

ALTER TABLE public.students
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.cameras
ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.recognition_events
ENABLE ROW LEVEL SECURITY;
