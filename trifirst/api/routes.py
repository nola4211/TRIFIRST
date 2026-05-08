"""FastAPI route definitions for TriFirst API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException  # HTTPException returns a clean HTTP error response (like 404 or 400).
from fastapi.responses import RedirectResponse
from pydantic import BaseModel  # BaseModel validates request JSON and converts it into typed Python objects.
from passlib.context import CryptContext

from trifirst.config import (
    APP_NAME,
    DATABASE_PATH,
    STRAVA_CLIENT_ID,
    STRAVA_CLIENT_SECRET,
)
from trifirst.database.db import get_connection
from trifirst.coach.ai_coach import chat, generate_weekly_digest, _most_recent_completed_week_window
from trifirst.integrations.garmin import GarminClient
from trifirst.integrations.strava import (
    authorize_url,
    exchange_token,
    save_tokens,
    sync_activities,
)

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Imported per API contract; useful for debugging configuration in this module scope.
_ = DATABASE_PATH



class RegisterRequest(BaseModel):
    """Request body for creating a new user account."""

    name: str
    email: str
    username: str
    password: str
    age: int | None = None


class LoginRequest(BaseModel):
    """Request body for user login."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Response body returned for successful login."""

    user_id: int
    name: str
    username: str
    message: str


class SyncRequest(BaseModel):
    """Request body for syncing Strava activities."""

    user_id: int




class GarminSyncRequest(BaseModel):
    """Request body for syncing Garmin wellness metrics."""

    user_id: int
    days: int = 7


class GarminCredentialsRequest(BaseModel):
    """Request body for storing Garmin credentials per user."""

    user_id: int
    email: str
    password: str

class ChatRequest(BaseModel):
    """Request body for AI coaching chat."""

    user_id: int
    message: str




class DigestGenerateRequest(BaseModel):
    """Request body for generating a weekly digest."""

    user_id: int

class RaceGoalRequest(BaseModel):
    """Request body for saving a race goal."""

    user_id: int
    race_name: str
    race_date: str
    race_distance: str
    goal_finish_time: str | None = None



class AthleteProfileRequest(BaseModel):
    """Request body for creating/updating athlete profile."""

    user_id: int
    injury_history: str | None = None
    physical_limitations: str | None = None
    preferred_training_days: str | None = None
    training_days_notes: str | None = None


class FitnessBackgroundRequest(BaseModel):
    """Request body for saving fitness background."""

    user_id: int
    swim_level: str
    bike_level: str
    run_level: str
    weekly_hours_available: float



@router.post("/auth/register")
def register_user(payload: RegisterRequest) -> dict[str, int | str]:
    """Create a new user account with a securely hashed password."""
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (payload.username, payload.email),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username or email already taken")

        password_hash = pwd_context.hash(payload.password)
        cursor = connection.execute(
            """
            INSERT INTO users (name, email, username, password_hash, age)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.name, payload.email, payload.username, password_hash, payload.age),
        )
        connection.commit()

    return {"message": "Account created", "user_id": cursor.lastrowid}


@router.post("/auth/login", response_model=LoginResponse)
def login_user(payload: LoginRequest) -> LoginResponse:
    """Authenticate a user by username and password."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name, username, password_hash FROM users WHERE username = ?",
            (payload.username,),
        ).fetchone()

    if not row or not row["password_hash"] or not pwd_context.verify(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return LoginResponse(
        user_id=row["id"],
        name=row["name"],
        username=row["username"],
        message="Login successful",
    )


@router.get("/auth/user/{user_id}")
def get_auth_user(user_id: int) -> dict[str, object]:
    """Return account details for a single user by id."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT name, username, email, age FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return dict(row)


# Health endpoint used by monitoring tools and uptime checks to confirm the API is running.
@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a health status response."""
    return {"status": "ok", "app": APP_NAME}


# Starts Strava connection flow; typically called when a user clicks "Connect Strava".
@router.get("/auth/strava")
def auth_strava(user_id: int = 1) -> RedirectResponse:
    """Redirect the user to Strava OAuth authorization."""
    return RedirectResponse(authorize_url(STRAVA_CLIENT_ID, state=str(user_id)))


# Receives Strava redirect after login and stores tokens for this user.
@router.get("/auth/strava/callback")
def auth_strava_callback(code: str, state: str | None = None) -> dict[str, int | str]:
    """Exchange Strava auth code for tokens and save them for the user."""
    token_dict = exchange_token(STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, code)
    try:
        user_id = int(state) if state is not None else 1
    except (TypeError, ValueError):
        user_id = 1

    with get_connection() as connection:
        save_tokens(user_id, token_dict, connection)

    return {"message": "Strava connected successfully", "user_id": user_id}


# Called by the frontend sync button to import recent Strava activities.
@router.post("/sync/strava")
def sync_strava_activities(payload: SyncRequest) -> dict[str, int | str]:
    """Sync Strava activities into the local database."""
    with get_connection() as connection:
        activities_added = sync_activities(
            payload.user_id,
            connection,
            STRAVA_CLIENT_ID,
            STRAVA_CLIENT_SECRET,
        )

    return {"message": "Sync complete", "activities_added": activities_added}


# Called by dashboard screens to load a user's activity list.
@router.get("/activities/{user_id}")
def get_user_activities(user_id: int) -> list[dict[str, object]]:
    """Return all activities for a user ordered by newest date first."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, source, activity_type, date, duration_mins, distance_km, avg_hr,
                   perceived_effort, notes
            FROM activities
            WHERE user_id = ?
            ORDER BY date DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


# Called by chat UI to send a message and get a coach reply.
@router.post("/coach/chat")
def coach_chat(payload: ChatRequest) -> dict[str, str]:
    """Generate a coaching response for a user chat message."""
    with get_connection() as connection:
        response_text = chat(payload.user_id, payload.message, connection)
    return {"response": response_text}


# Called by profile form to save the user's target race details.
@router.post("/race-goal")
def save_race_goal(payload: RaceGoalRequest) -> dict[str, str]:
    """Save a race goal for a user."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO race_goals (user_id, race_name, race_date, race_distance, goal_finish_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.user_id,
                payload.race_name,
                payload.race_date,
                payload.race_distance,
                payload.goal_finish_time,
            ),
        )
        connection.commit()
    return {"message": "Race goal saved"}


# Called by profile form to save beginner skill levels and hours available.
@router.post("/fitness-background")
def save_fitness_background(payload: FitnessBackgroundRequest) -> dict[str, str]:
    """Save fitness background for a user."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO fitness_background (
                user_id,
                swim_level,
                bike_level,
                run_level,
                weekly_hours_available
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.user_id,
                payload.swim_level,
                payload.bike_level,
                payload.run_level,
                payload.weekly_hours_available,
            ),
        )
        connection.commit()
    return {"message": "Fitness background saved"}


# Called by the profile UI to pre-fill the latest saved race goal.
@router.get("/race-goal/{user_id}")
def get_race_goal(user_id: int) -> dict[str, object] | None:
    """Return most recent race goal for a user."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT user_id, race_name, race_date, race_distance, goal_finish_time
            FROM race_goals
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


# Called by the profile UI to pre-fill the latest fitness background values.
@router.get("/fitness-background/{user_id}")
def get_fitness_background(user_id: int) -> dict[str, object] | None:
    """Return most recent fitness background for a user."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT user_id, swim_level, bike_level, run_level, weekly_hours_available
            FROM fitness_background
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


@router.post("/digest/generate")
def generate_digest(payload: DigestGenerateRequest) -> dict[str, str]:
    """Generate and save an AI weekly digest for the most recent completed week."""
    with get_connection() as connection:
        digest_text = generate_weekly_digest(payload.user_id, connection)
    week_start_date, _ = _most_recent_completed_week_window()
    return {"digest": digest_text, "week_start_date": week_start_date}


@router.get("/digest/{user_id}")
def get_weekly_digests(user_id: int) -> list[dict[str, object]]:
    """Return the 4 most recent weekly digests for a user."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                user_id,
                week_start_date,
                total_swim_km,
                total_bike_km,
                total_run_km,
                total_hours,
                ai_summary_text,
                generated_at
            FROM weekly_summaries
            WHERE user_id = ?
            ORDER BY week_start_date DESC, id DESC
            LIMIT 4
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


@router.post("/sync/garmin")
def sync_garmin_stats(payload: GarminSyncRequest) -> dict[str, int | str]:
    """Sync Garmin daily recovery stats for a user."""
    with get_connection() as connection:
        credential_row = connection.execute(
            """
            SELECT email, password
            FROM garmin_credentials
            WHERE user_id = ?
            LIMIT 1
            """,
            (payload.user_id,),
        ).fetchone()
        if not credential_row:
            raise HTTPException(
                status_code=400,
                detail="No Garmin credentials found for this user. Save credentials first.",
            )

    client = GarminClient(credential_row["email"], credential_row["password"])
    client.connect()

    with get_connection() as connection:
        days_synced = client.sync_stats(payload.user_id, connection, payload.days)

    return {"message": "Garmin sync complete", "days_synced": days_synced}


@router.post("/garmin/credentials")
def save_garmin_credentials(payload: GarminCredentialsRequest) -> dict[str, str]:
    """Upsert Garmin credentials for a user."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO garmin_credentials (user_id, email, password)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                email = excluded.email,
                password = excluded.password
            """,
            (payload.user_id, payload.email, payload.password),
        )
        connection.commit()
    return {"message": "Garmin credentials saved"}


@router.get("/garmin/credentials/{user_id}")
def get_garmin_credentials(user_id: int) -> dict[str, object]:
    """Return Garmin connection status (and email when connected) for a user."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT email
            FROM garmin_credentials
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        return {"connected": False}
    return {"email": row["email"], "connected": True}


@router.get("/garmin/stats/{user_id}")
def get_garmin_stats(user_id: int) -> list[dict[str, object]]:
    """Return last 14 days of Garmin wellness stats for a user."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT user_id, date, body_battery_high, body_battery_low, resting_hr,
                   avg_sleep_hr, hrv_avg, hrv_status, body_battery_change,
                   avg_resting_hr_7day, steps, updated_at
            FROM garmin_daily_stats
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 14
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


@router.post("/athlete-profile")
def save_athlete_profile(payload: AthleteProfileRequest) -> dict[str, str]:
    """Upsert athlete profile details for a user."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO athlete_profile (
                user_id, injury_history, physical_limitations, preferred_training_days, training_days_notes
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                injury_history = excluded.injury_history,
                physical_limitations = excluded.physical_limitations,
                preferred_training_days = excluded.preferred_training_days,
                training_days_notes = excluded.training_days_notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                payload.user_id,
                payload.injury_history,
                payload.physical_limitations,
                payload.preferred_training_days,
                payload.training_days_notes,
            ),
        )
        connection.commit()
    return {"message": "Profile saved"}


@router.get("/athlete-profile/{user_id}")
def get_athlete_profile(user_id: int) -> dict[str, object] | None:
    """Return athlete profile for a user if present."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT user_id, injury_history, physical_limitations, preferred_training_days, training_days_notes, updated_at
            FROM athlete_profile
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


@router.get("/coach/history/{user_id}")
def get_coach_history(user_id: int) -> list[dict[str, object]]:
    """Return the last 10 coach messages ordered oldest to newest."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT role, message, timestamp
            FROM (
                SELECT role, message, timestamp, id
                FROM coach_messages
                WHERE user_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 10
            )
            ORDER BY timestamp ASC, id ASC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


@router.get("/race-calculator/{user_id}")
def get_race_calculator(user_id: int) -> dict[str, object]:
    """Return race calculator defaults based on recent activities and latest race goal."""
    with get_connection() as connection:
        activity_rows = connection.execute(
            """
            SELECT activity_type, duration_mins, distance_km
            FROM activities
            WHERE user_id = ?
              AND activity_type IN ('swim', 'bike', 'run')
              AND distance_km > 0
              AND duration_mins > 0
              AND date >= date('now', '-90 days')
            """,
            (user_id,),
        ).fetchall()

        race_goal = connection.execute(
            """
            SELECT race_distance, race_name, race_date
            FROM race_goals
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    swim_paces = []
    bike_speeds = []
    run_paces = []
    counts = {"swim": 0, "bike": 0, "run": 0}

    for row in activity_rows:
        activity_type = row["activity_type"]
        duration_mins = float(row["duration_mins"])
        distance_km = float(row["distance_km"])

        if activity_type == "swim":
            swim_paces.append((duration_mins / distance_km) / 10)
            counts["swim"] += 1
        elif activity_type == "bike":
            bike_speeds.append((distance_km / duration_mins) * 60)
            counts["bike"] += 1
        elif activity_type == "run":
            run_paces.append(duration_mins / distance_km)
            counts["run"] += 1

    def _average(values: list[float]) -> float | None:
        return (sum(values) / len(values)) if values else None

    return {
        "race_distance": race_goal["race_distance"] if race_goal else None,
        "race_name": race_goal["race_name"] if race_goal else None,
        "race_date": race_goal["race_date"] if race_goal else None,
        "avg_swim_pace_per_100m": _average(swim_paces),
        "avg_bike_speed_kmh": _average(bike_speeds),
        "avg_run_pace_per_km": _average(run_paces),
        "activity_counts": counts,
    }
