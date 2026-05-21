-- Full PostgreSQL schema for the TriFirst application.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    age INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS race_goals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    race_name TEXT NOT NULL,
    race_date TEXT NOT NULL,
    race_distance TEXT NOT NULL CHECK (race_distance IN ('sprint', 'olympic', '70.3', 'full')),
    goal_finish_time TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS fitness_background (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    swim_level TEXT NOT NULL CHECK (swim_level IN ('none', 'beginner', 'intermediate')),
    bike_level TEXT NOT NULL CHECK (bike_level IN ('none', 'beginner', 'intermediate')),
    run_level TEXT NOT NULL CHECK (run_level IN ('none', 'beginner', 'intermediate')),
    weekly_hours_available REAL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS activities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('strava', 'manual')),
    activity_type TEXT NOT NULL CHECK (activity_type IN ('swim', 'bike', 'run')),
    date TEXT NOT NULL,
    duration_mins REAL,
    distance_km REAL,
    avg_hr INTEGER,
    perceived_effort INTEGER CHECK (perceived_effort BETWEEN 1 AND 10),
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS strava_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS weekly_summaries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    week_start_date TEXT NOT NULL,
    total_swim_km REAL DEFAULT 0,
    total_bike_km REAL DEFAULT 0,
    total_run_km REAL DEFAULT 0,
    total_hours REAL DEFAULT 0,
    ai_summary_text TEXT,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS coach_messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    message TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS athlete_profile (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    injury_history TEXT,
    physical_limitations TEXT,
    preferred_training_days TEXT,
    training_days_notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS scheduled_workouts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    activity_type TEXT NOT NULL CHECK (activity_type IN ('swim', 'bike', 'run', 'brick', 'rest')),
    title TEXT NOT NULL,
    description TEXT,
    duration_mins INTEGER,
    distance_km REAL,
    intensity TEXT CHECK (intensity IN ('easy', 'moderate', 'hard', 'race')),
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'skipped')),
    source TEXT NOT NULL DEFAULT 'coach' CHECK (source IN ('coach', 'manual')),
    confirmed_at TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS pending_workouts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    proposed_by TEXT NOT NULL DEFAULT 'coach',
    workouts_json TEXT NOT NULL,
    message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users (id)
);
