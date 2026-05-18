"""FastAPI route definitions for TriFirst API endpoints."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Literal, TypeVar

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator

from trifirst.coach.ai_coach import chat, generate_weekly_digest, _most_recent_completed_week_window
from trifirst.config import APP_NAME, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET
from trifirst.database.db import get_connection
from trifirst.integrations.strava import (
    StravaIntegrationError,
    authorize_url,
    exchange_token,
    save_tokens,
    sync_activities,
)

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
F = TypeVar("F", bound=Callable[..., Any])

# Shared validation choices used by request models and calendar confirmation cleanup.
RaceDistance = Literal["sprint", "olympic", "70.3", "full"]
Intensity = Literal["easy", "moderate", "hard", "race"]
ActivityType = Literal["swim", "bike", "run", "brick", "rest"]
WorkoutStatus = Literal["scheduled", "completed", "skipped"]


def _validate_date_string(value: str) -> str:
    """Validate an ISO calendar date string.

    Args:
        value: Candidate date string to validate.

    Returns:
        The original date string when it matches ``YYYY-MM-DD``.
    """
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format") from exc
    return value


def api_endpoint(func: F) -> F:
    """Wrap route handlers with consistent HTTP error handling.

    Args:
        func: FastAPI route function to execute.

    Returns:
        A wrapped route function that preserves explicit HTTP errors and converts
        expected integration/database failures into meaningful HTTPException responses.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Execute a route handler and translate known exceptions into HTTP errors."""
        try:
            return func(*args, **kwargs)
        except HTTPException:
            raise
        except StravaIntegrationError as exc:
            raise HTTPException(status_code=502, detail=f"Strava operation failed: {exc}") from exc
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail=f"Database operation failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Stored workout proposal JSON is invalid") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected API error: {exc}") from exc

    return wrapper  # type: ignore[return-value]


# --- Request and response models ---
class RegisterRequest(BaseModel):
    """Request body for creating a new user account."""

    name: str = Field(min_length=1)
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9]+$")
    password: str = Field(min_length=8)
    age: int | None = Field(default=None, ge=0)


class LoginRequest(BaseModel):
    """Request body for user login."""

    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9]+$")
    password: str = Field(min_length=8)


class LoginResponse(BaseModel):
    """Response body returned for successful login."""

    user_id: int
    name: str
    username: str
    message: str


class SyncRequest(BaseModel):
    """Request body for syncing Strava activities."""

    user_id: int


class ChatRequest(BaseModel):
    """Request body for AI coaching chat."""

    user_id: int
    message: str = Field(min_length=1)


class DigestGenerateRequest(BaseModel):
    """Request body for generating a weekly digest."""

    user_id: int


class ScheduledWorkoutRequest(BaseModel):
    """Request body for creating a scheduled workout."""

    user_id: int
    date: str
    activity_type: ActivityType
    title: str = Field(min_length=1)
    description: str | None = None
    duration_mins: int | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    intensity: Intensity | None = None
    source: Literal["manual", "coach"] = "manual"

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        """Validate scheduled workout dates as ISO calendar dates."""
        return _validate_date_string(value)


class WorkoutStatusUpdate(BaseModel):
    """Request body for updating a scheduled workout status."""

    status: WorkoutStatus


class PendingWorkoutsRequest(BaseModel):
    """Request body for saving a coach-generated workout proposal."""

    user_id: int
    workouts_json: str
    message: str | None = None


class ConfirmWorkoutsRequest(BaseModel):
    """Request body for confirming selected pending workouts."""

    user_id: int
    pending_id: int
    selected_ids: list[int]


class RaceGoalRequest(BaseModel):
    """Request body for saving a race goal."""

    user_id: int
    race_name: str = Field(min_length=1)
    race_date: str
    race_distance: RaceDistance
    goal_finish_time: str | None = None

    @field_validator("race_date")
    @classmethod
    def validate_race_date(cls, value: str) -> str:
        """Validate race goal dates as ISO calendar dates."""
        return _validate_date_string(value)


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
    swim_level: Literal["none", "beginner", "intermediate"]
    bike_level: Literal["none", "beginner", "intermediate"]
    run_level: Literal["none", "beginner", "intermediate"]
    weekly_hours_available: float = Field(ge=0)


# --- Authentication endpoints ---
@router.post("/auth/register")
@api_endpoint
def register_user(payload: RegisterRequest) -> dict[str, int | str]:
    """Create a new user account with a securely hashed password.

    Args:
        payload: Validated registration details.

    Returns:
        Success message and the new user id.
    """
    with get_connection() as connection:
        # Fetch any existing account that conflicts with the requested username or email.
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (payload.username, str(payload.email)),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username or email already taken")

        password_hash = pwd_context.hash(payload.password)
        # Insert the new user with a hashed password only; never persist plaintext passwords.
        cursor = connection.execute(
            """
            INSERT INTO users (name, email, username, password_hash, age)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.name, str(payload.email), payload.username, password_hash, payload.age),
        )
        connection.commit()

    return {"message": "Account created", "user_id": cursor.lastrowid}


@router.post("/auth/login", response_model=LoginResponse)
@api_endpoint
def login_user(payload: LoginRequest) -> LoginResponse:
    """Authenticate a user by username and password.

    Args:
        payload: Validated login credentials.

    Returns:
        Login response with user identity fields.
    """
    with get_connection() as connection:
        # Fetch password hash and account fields for the submitted username.
        row = connection.execute(
            "SELECT id, name, username, password_hash FROM users WHERE username = ?",
            (payload.username,),
        ).fetchone()

    if not row or not row["password_hash"] or not pwd_context.verify(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return LoginResponse(user_id=row["id"], name=row["name"], username=row["username"], message="Login successful")


@router.get("/auth/user/{user_id}")
@api_endpoint
def get_auth_user(user_id: int) -> dict[str, object]:
    """Return account details for a single user by id.

    Args:
        user_id: User id to look up.

    Returns:
        Public user account fields.
    """
    with get_connection() as connection:
        # Fetch public account details for the requested user.
        row = connection.execute("SELECT name, username, email, age FROM users WHERE id = ?", (user_id,)).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


@router.get("/health")
@api_endpoint
def health_check() -> dict[str, str]:
    """Return a health status response.

    Args:
        None.

    Returns:
        Health status and application name.
    """
    return {"status": "ok", "app": APP_NAME}


# --- Strava integration endpoints ---
@router.get("/auth/strava")
@api_endpoint
def auth_strava(user_id: int) -> RedirectResponse:
    """Redirect the user to Strava OAuth authorization.

    Args:
        user_id: Authenticated TriFirst user id stored in OAuth state.

    Returns:
        Redirect response to Strava's authorization URL.
    """
    return RedirectResponse(authorize_url(STRAVA_CLIENT_ID, state=str(user_id)))


@router.get("/auth/strava/callback")
@api_endpoint
def auth_strava_callback(code: str, state: str) -> dict[str, int | str]:
    """Exchange a Strava auth code for tokens and save them for the user.

    Args:
        code: OAuth code returned by Strava.
        state: User id originally sent to Strava as OAuth state.

    Returns:
        Success message and user id.
    """
    try:
        user_id = int(state)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Strava OAuth state") from exc

    token_dict = exchange_token(STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, code)
    with get_connection() as connection:
        save_tokens(user_id, token_dict, connection)

    return {"message": "Strava connected successfully", "user_id": user_id}


@router.post("/sync/strava")
@api_endpoint
def sync_strava_activities(payload: SyncRequest) -> dict[str, int | str]:
    """Sync Strava activities into the local database.

    Args:
        payload: User id whose Strava activities should be synced.

    Returns:
        Success message and count of inserted activities.
    """
    with get_connection() as connection:
        activities_added = sync_activities(payload.user_id, connection, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET)
    return {"message": "Sync complete", "activities_added": activities_added}


# --- Activity and profile endpoints ---
@router.get("/activities/{user_id}")
@api_endpoint
def get_user_activities(user_id: int) -> list[dict[str, object]]:
    """Return all activities for a user ordered by newest date first.

    Args:
        user_id: User id whose activities should be returned.

    Returns:
        List of persisted activity dictionaries.
    """
    with get_connection() as connection:
        # Fetch all activity rows for the user, newest first for dashboard display.
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


@router.post("/race-goal")
@api_endpoint
def save_race_goal(payload: RaceGoalRequest) -> dict[str, str]:
    """Save a race goal for a user.

    Args:
        payload: Race goal fields to persist.

    Returns:
        Success message.
    """
    with get_connection() as connection:
        # Insert the latest race goal snapshot for the user.
        connection.execute(
            """
            INSERT INTO race_goals (user_id, race_name, race_date, race_distance, goal_finish_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.user_id, payload.race_name, payload.race_date, payload.race_distance, payload.goal_finish_time),
        )
        connection.commit()
    return {"message": "Race goal saved"}


@router.get("/race-goal/{user_id}")
@api_endpoint
def get_race_goal(user_id: int) -> dict[str, object]:
    """Return the most recent race goal for a user.

    Args:
        user_id: User id whose race goal should be loaded.

    Returns:
        Race goal dictionary.
    """
    with get_connection() as connection:
        # Fetch the most recently saved race goal for the user.
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
    if not row:
        raise HTTPException(status_code=404, detail="Race goal not found")
    return dict(row)


@router.post("/fitness-background")
@api_endpoint
def save_fitness_background(payload: FitnessBackgroundRequest) -> dict[str, str]:
    """Save fitness background for a user.

    Args:
        payload: Fitness background fields to persist.

    Returns:
        Success message.
    """
    with get_connection() as connection:
        # Insert the latest fitness background snapshot for the user.
        connection.execute(
            """
            INSERT INTO fitness_background (user_id, swim_level, bike_level, run_level, weekly_hours_available)
            VALUES (?, ?, ?, ?, ?)
            """,
            (payload.user_id, payload.swim_level, payload.bike_level, payload.run_level, payload.weekly_hours_available),
        )
        connection.commit()
    return {"message": "Fitness background saved"}


@router.get("/fitness-background/{user_id}")
@api_endpoint
def get_fitness_background(user_id: int) -> dict[str, object]:
    """Return the most recent fitness background for a user.

    Args:
        user_id: User id whose fitness background should be loaded.

    Returns:
        Fitness background dictionary.
    """
    with get_connection() as connection:
        # Fetch the most recently saved fitness background row for the user.
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
    if not row:
        raise HTTPException(status_code=404, detail="Fitness background not found")
    return dict(row)


@router.post("/athlete-profile")
@api_endpoint
def save_athlete_profile(payload: AthleteProfileRequest) -> dict[str, str]:
    """Upsert athlete profile details for a user.

    Args:
        payload: Athlete profile fields to save.

    Returns:
        Success message.
    """
    with get_connection() as connection:
        # Upsert one athlete profile row per user.
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
@api_endpoint
def get_athlete_profile(user_id: int) -> dict[str, object]:
    """Return athlete profile for a user.

    Args:
        user_id: User id whose athlete profile should be loaded.

    Returns:
        Athlete profile dictionary.
    """
    with get_connection() as connection:
        # Fetch the single athlete profile row for the user.
        row = connection.execute(
            """
            SELECT user_id, injury_history, physical_limitations, preferred_training_days, training_days_notes, updated_at
            FROM athlete_profile
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Athlete profile not found")
    return dict(row)


# --- Coach and digest endpoints ---
@router.post("/coach/chat")
@api_endpoint
def coach_chat(payload: ChatRequest) -> dict[str, str]:
    """Generate a coaching response for a user chat message.

    Args:
        payload: User id and message text for Coach Tri.

    Returns:
        Assistant response text.
    """
    with get_connection() as connection:
        response_text = chat(payload.user_id, payload.message, connection)
    return {"response": response_text}


@router.get("/coach/history/{user_id}")
@api_endpoint
def get_coach_history(user_id: int) -> list[dict[str, object]]:
    """Return the last 10 coach messages ordered oldest to newest.

    Args:
        user_id: User id whose coach history should be loaded.

    Returns:
        List of chat message dictionaries.
    """
    with get_connection() as connection:
        # Fetch the ten newest chat messages, then reorder them chronologically.
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


@router.post("/digest/generate")
@api_endpoint
def generate_digest(payload: DigestGenerateRequest) -> dict[str, str]:
    """Generate and save an AI weekly digest for the most recent completed week.

    Args:
        payload: User id for digest generation.

    Returns:
        Generated digest and its week start date.
    """
    with get_connection() as connection:
        digest_text = generate_weekly_digest(payload.user_id, connection)
    week_start_date, _ = _most_recent_completed_week_window()
    return {"digest": digest_text, "week_start_date": week_start_date}


@router.get("/digest/{user_id}")
@api_endpoint
def get_weekly_digests(user_id: int) -> list[dict[str, object]]:
    """Return the 4 most recent weekly digests for a user.

    Args:
        user_id: User id whose digests should be loaded.

    Returns:
        List of weekly digest dictionaries.
    """
    with get_connection() as connection:
        # Fetch the latest four generated weekly summaries for dashboard display.
        rows = connection.execute(
            """
            SELECT id, user_id, week_start_date, total_swim_km, total_bike_km, total_run_km,
                   total_hours, ai_summary_text, generated_at
            FROM weekly_summaries
            WHERE user_id = ?
            ORDER BY week_start_date DESC, id DESC
            LIMIT 4
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


# --- Race calculator and calendar endpoints ---
@router.get("/race-calculator/{user_id}")
@api_endpoint
def get_race_calculator(user_id: int) -> dict[str, object]:
    """Return race calculator defaults based on recent activities and latest race goal.

    Args:
        user_id: User id whose race calculator inputs should be loaded.

    Returns:
        Calculator defaults derived from recent training data.
    """
    with get_connection() as connection:
        # Fetch recent swim, bike, and run efforts to estimate calculator defaults.
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
        # Fetch the latest race goal to select race distance defaults.
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

    swim_paces: list[float] = []
    bike_speeds: list[float] = []
    run_paces: list[float] = []
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
        """Return an arithmetic average for non-empty numeric lists.

        Args:
            values: Numeric values to average.

        Returns:
            Average value, or ``None`` when no values are available.
        """
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


@router.get("/calendar/{user_id}")
@api_endpoint
def get_calendar(user_id: int, month: str) -> list[dict[str, object]]:
    """Return scheduled workouts and completed activities for a given month.

    Args:
        user_id: User id whose calendar should be loaded.
        month: Month prefix in ``YYYY-MM`` format.

    Returns:
        Combined scheduled workout and activity entries.
    """
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must use YYYY-MM format") from exc

    month_prefix = f"{month}%"
    with get_connection() as connection:
        # Fetch scheduled workout calendar entries for the requested month.
        scheduled_rows = connection.execute(
            """
            SELECT id, user_id, date, activity_type, title, description, duration_mins,
                   distance_km, intensity, status, source, confirmed_at, created_at
            FROM scheduled_workouts
            WHERE user_id = ? AND date LIKE ?
            """,
            (user_id, month_prefix),
        ).fetchall()
        # Fetch synced Strava activities that should appear as completed calendar entries.
        activity_rows = connection.execute(
            """
            SELECT id, user_id, date, activity_type, duration_mins, distance_km, source
            FROM activities
            WHERE user_id = ? AND date LIKE ? AND source = 'strava'
            """,
            (user_id, month_prefix),
        ).fetchall()

    combined = [dict(row) | {"record_type": "scheduled_workout"} for row in scheduled_rows]
    combined.extend(
        {
            "id": row["id"],
            "user_id": row["user_id"],
            "date": row["date"],
            "activity_type": row["activity_type"],
            "title": f"Completed {row['activity_type'].title()}",
            "description": None,
            "duration_mins": row["duration_mins"],
            "distance_km": row["distance_km"],
            "intensity": None,
            "status": "completed",
            "source": "strava",
            "record_type": "activity",
        }
        for row in activity_rows
    )
    combined.sort(key=lambda item: item["date"])
    return combined


@router.post("/calendar/workout")
@api_endpoint
def create_scheduled_workout(payload: ScheduledWorkoutRequest) -> dict[str, int | str]:
    """Create a scheduled workout calendar entry.

    Args:
        payload: Scheduled workout fields.

    Returns:
        Success message and created workout id.
    """
    with get_connection() as connection:
        # Insert a manual or coach-generated scheduled workout.
        cursor = connection.execute(
            """
            INSERT INTO scheduled_workouts (
                user_id, date, activity_type, title, description, duration_mins, distance_km, intensity, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.user_id,
                payload.date,
                payload.activity_type,
                payload.title,
                payload.description,
                payload.duration_mins,
                payload.distance_km,
                payload.intensity,
                payload.source,
            ),
        )
        connection.commit()
    return {"message": "Workout scheduled", "id": cursor.lastrowid}


@router.patch("/calendar/workout/{workout_id}")
@api_endpoint
def update_scheduled_workout(workout_id: int, payload: WorkoutStatusUpdate) -> dict[str, str]:
    """Update a scheduled workout's status.

    Args:
        workout_id: Scheduled workout id to update.
        payload: New workout status.

    Returns:
        Success message.
    """
    with get_connection() as connection:
        # Update the status of a single scheduled workout by id.
        cursor = connection.execute("UPDATE scheduled_workouts SET status = ? WHERE id = ?", (payload.status, workout_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Scheduled workout not found")
        connection.commit()
    return {"message": "Workout updated"}


@router.delete("/calendar/workout/{workout_id}")
@api_endpoint
def delete_scheduled_workout(workout_id: int) -> dict[str, str]:
    """Delete a scheduled workout.

    Args:
        workout_id: Scheduled workout id to delete.

    Returns:
        Success message.
    """
    with get_connection() as connection:
        # Delete a single scheduled workout by id.
        cursor = connection.execute("DELETE FROM scheduled_workouts WHERE id = ?", (workout_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Scheduled workout not found")
        connection.commit()
    return {"message": "Workout deleted"}


@router.post("/calendar/pending")
@api_endpoint
def save_pending_workouts(payload: PendingWorkoutsRequest) -> dict[str, int | str]:
    """Save a pending coach workout proposal.

    Args:
        payload: Pending workout JSON and optional source message.

    Returns:
        Success message and pending proposal id.
    """
    json.loads(payload.workouts_json)
    with get_connection() as connection:
        # Insert a pending workout proposal created by Coach Tri.
        cursor = connection.execute(
            """
            INSERT INTO pending_workouts (user_id, proposed_by, workouts_json, message)
            VALUES (?, 'coach', ?, ?)
            """,
            (payload.user_id, payload.workouts_json, payload.message),
        )
        connection.commit()
    return {"message": "Pending workouts saved", "id": cursor.lastrowid}


@router.get("/calendar/pending/{user_id}")
@api_endpoint
def get_pending_workouts(user_id: int) -> dict[str, object]:
    """Return the newest pending workout proposal for a user.

    Args:
        user_id: User id whose pending proposal should be loaded.

    Returns:
        Pending workout proposal dictionary.
    """
    with get_connection() as connection:
        # Fetch the newest pending workout proposal for the user.
        row = connection.execute(
            """
            SELECT id, user_id, proposed_by, workouts_json, message, created_at
            FROM pending_workouts
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Pending workouts not found")
    return dict(row)


@router.delete("/calendar/pending/{pending_id}")
@api_endpoint
def delete_pending_workouts(pending_id: int) -> dict[str, str]:
    """Delete a pending workout proposal.

    Args:
        pending_id: Pending proposal id to delete.

    Returns:
        Success message.
    """
    with get_connection() as connection:
        # Delete a single pending workout proposal by id.
        cursor = connection.execute("DELETE FROM pending_workouts WHERE id = ?", (pending_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Pending workouts not found")
        connection.commit()
    return {"message": "Pending workouts deleted"}


@router.post("/calendar/confirm")
@api_endpoint
def confirm_pending_workouts(payload: ConfirmWorkoutsRequest) -> dict[str, int | str]:
    """Convert selected pending workouts into scheduled workouts.

    Args:
        payload: Pending proposal id, user id, and selected proposal item ids.

    Returns:
        Success message and number of confirmed workouts.
    """
    with get_connection() as connection:
        # Fetch the pending proposal before converting selected entries.
        pending = connection.execute(
            "SELECT workouts_json FROM pending_workouts WHERE id = ? AND user_id = ?",
            (payload.pending_id, payload.user_id),
        ).fetchone()
        if not pending:
            raise HTTPException(status_code=404, detail="Pending workouts not found")

        workouts = json.loads(pending["workouts_json"])
        selected = [workout for workout in workouts if int(workout.get("id", -1)) in payload.selected_ids]
        for workout in selected:
            # Insert each selected proposed workout into the confirmed schedule.
            connection.execute(
                """
                INSERT INTO scheduled_workouts (
                    user_id, date, activity_type, title, description, duration_mins, distance_km, intensity, source, confirmed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'coach', CURRENT_TIMESTAMP)
                """,
                (
                    payload.user_id,
                    _validate_date_string(str(workout.get("date"))),
                    workout.get("activity_type"),
                    workout.get("title"),
                    workout.get("description"),
                    workout.get("duration_mins"),
                    workout.get("distance_km"),
                    workout.get("intensity"),
                ),
            )
        # Delete the pending proposal after selected entries are confirmed.
        connection.execute("DELETE FROM pending_workouts WHERE id = ?", (payload.pending_id,))
        connection.commit()
    return {"message": "Workouts confirmed", "count": len(selected)}
