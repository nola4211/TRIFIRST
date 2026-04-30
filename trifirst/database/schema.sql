-- Full SQLite schema for the TriFirst application.

-- Stores basic user profile details.
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    age INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Stores each user's target race and goal details.
CREATE TABLE IF NOT EXISTS race_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    race_name TEXT NOT NULL,
    race_date TEXT NOT NULL,
    race_distance TEXT NOT NULL CHECK (race_distance IN ('sprint', 'olympic', '70.3', 'full')), -- Allowed values: sprint, olympic, 70.3, full
    goal_finish_time TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Stores each user's self-reported current fitness level.
CREATE TABLE IF NOT EXISTS fitness_background (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    swim_level TEXT NOT NULL CHECK (swim_level IN ('none', 'beginner', 'intermediate')), -- Allowed values: none, beginner, intermediate
    bike_level TEXT NOT NULL CHECK (bike_level IN ('none', 'beginner', 'intermediate')), -- Allowed values: none, beginner, intermediate
    run_level TEXT NOT NULL CHECK (run_level IN ('none', 'beginner', 'intermediate')), -- Allowed values: none, beginner, intermediate
    weekly_hours_available REAL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Stores workouts imported from apps or added manually.
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('strava', 'garmin', 'manual')), -- Allowed values: strava, garmin, manual
    activity_type TEXT NOT NULL CHECK (activity_type IN ('swim', 'bike', 'run')), -- Allowed values: swim, bike, run
    date TEXT NOT NULL,
    duration_mins REAL,
    distance_km REAL,
    avg_hr INTEGER,
    perceived_effort INTEGER CHECK (perceived_effort BETWEEN 1 AND 10), -- Allowed values: any whole number from 1 to 10
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Stores Strava API tokens for each user.
CREATE TABLE IF NOT EXISTS strava_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Stores daily wellness check-in answers from each user.
CREATE TABLE IF NOT EXISTS daily_checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    sleep_quality INTEGER CHECK (sleep_quality BETWEEN 1 AND 5), -- Allowed values: any whole number from 1 to 5
    soreness INTEGER CHECK (soreness BETWEEN 1 AND 5), -- Allowed values: any whole number from 1 to 5
    energy INTEGER CHECK (energy BETWEEN 1 AND 5), -- Allowed values: any whole number from 1 to 5
    life_stress INTEGER CHECK (life_stress BETWEEN 1 AND 5), -- Allowed values: any whole number from 1 to 5
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Stores per-week training totals and optional AI-generated summary text.
CREATE TABLE IF NOT EXISTS weekly_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    week_start_date TEXT NOT NULL,
    total_swim_km REAL DEFAULT 0,
    total_bike_km REAL DEFAULT 0,
    total_run_km REAL DEFAULT 0,
    total_hours REAL DEFAULT 0,
    ai_summary_text TEXT,
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Stores chat messages between the user and the AI coach.
CREATE TABLE IF NOT EXISTS coach_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')), -- Allowed values: user, assistant
    message TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);
