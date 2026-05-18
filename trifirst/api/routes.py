"""FastAPI route definitions for TriFirst API endpoints."""

from __future__ import annotations

import json
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




class ChatRequest(BaseModel):
    """Request body for AI coaching chat."""

    user_id: int
    message: str




class DigestGenerateRequest(BaseModel):
    """Request body for generating a weekly digest."""

    user_id: int


class ScheduledWorkoutRequest(BaseModel):
    user_id: int
    date: str
    activity_type: str
    title: str
    description: str | None = None
    duration_mins: int | None = None
    distance_km: float | None = None
    intensity: str | None = None
    source: str = "manual"


class WorkoutStatusUpdate(BaseModel):
    status: str


class PendingWorkoutsRequest(BaseModel):
    user_id: int
    workouts_json: str
    message: str | None = None


class ConfirmWorkoutsRequest(BaseModel):
    user_id: int
    pending_id: int
    selected_ids: list[int]

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


@router.get("/calendar/{user_id}")
def get_calendar(user_id: int, month: str) -> list[dict[str, object]]:
    """Return scheduled workouts and completed activities for a given month."""
    month_prefix = f"{month}%"
    with get_connection() as connection:
        scheduled_rows = connection.execute(
            """
            SELECT id, user_id, date, activity_type, title, description, duration_mins,
                   distance_km, intensity, status, source, confirmed_at, created_at
            FROM scheduled_workouts
            WHERE user_id = ? AND date LIKE ?
            """,
            (user_id, month_prefix),
        ).fetchall()
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
def create_scheduled_workout(payload: ScheduledWorkoutRequest) -> dict[str, int | str]:
    with get_connection() as connection:
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
def update_scheduled_workout(workout_id: int, payload: WorkoutStatusUpdate) -> dict[str, str]:
    with get_connection() as connection:
        connection.execute(
            "UPDATE scheduled_workouts SET status = ? WHERE id = ?",
            (payload.status, workout_id),
        )
        connection.commit()
    return {"message": "Workout updated"}


@router.delete("/calendar/workout/{workout_id}")
def delete_scheduled_workout(workout_id: int) -> dict[str, str]:
    with get_connection() as connection:
        connection.execute("DELETE FROM scheduled_workouts WHERE id = ?", (workout_id,))
        connection.commit()
    return {"message": "Workout deleted"}


@router.post("/calendar/pending")
def save_pending_workouts(payload: PendingWorkoutsRequest) -> dict[str, int | str]:
    with get_connection() as connection:
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
def get_pending_workouts(user_id: int) -> dict[str, object] | None:
    with get_connection() as connection:
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
    return dict(row) if row else None


@router.delete("/calendar/pending/{pending_id}")
def delete_pending_workouts(pending_id: int) -> dict[str, str]:
    with get_connection() as connection:
        connection.execute("DELETE FROM pending_workouts WHERE id = ?", (pending_id,))
        connection.commit()
    return {"message": "Pending workouts deleted"}


@router.post("/calendar/confirm")
def confirm_pending_workouts(payload: ConfirmWorkoutsRequest) -> dict[str, int | str]:
    with get_connection() as connection:
        pending = connection.execute(
            "SELECT workouts_json FROM pending_workouts WHERE id = ? AND user_id = ?",
            (payload.pending_id, payload.user_id),
        ).fetchone()
        if not pending:
            raise HTTPException(status_code=404, detail="Pending workouts not found")

        workouts = json.loads(pending["workouts_json"])
        selected = [w for w in workouts if int(w.get("id", -1)) in payload.selected_ids]
        for workout in selected:
            connection.execute(
                """
                INSERT INTO scheduled_workouts (
                    user_id, date, activity_type, title, description, duration_mins, distance_km, intensity, source, confirmed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'coach', CURRENT_TIMESTAMP)
                """,
                (
                    payload.user_id,
                    workout.get("date"),
                    workout.get("activity_type"),
                    workout.get("title"),
                    workout.get("description"),
                    workout.get("duration_mins"),
                    workout.get("distance_km"),
                    workout.get("intensity"),
                ),
            )
        connection.execute("DELETE FROM pending_workouts WHERE id = ?", (payload.pending_id,))
        connection.commit()
    return {"message": "Workouts confirmed", "count": len(selected)}
