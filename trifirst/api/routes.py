"""FastAPI route definitions for TriFirst API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException  # HTTPException returns a clean HTTP error response (like 404 or 400).
from fastapi.responses import RedirectResponse
from pydantic import BaseModel  # BaseModel validates request JSON and converts it into typed Python objects.

from trifirst.config import APP_NAME, DATABASE_PATH, STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET
from trifirst.database.db import get_connection
from trifirst.coach.ai_coach import chat
from trifirst.integrations.strava import (
    authorize_url,
    exchange_token,
    save_tokens,
    sync_activities,
)

router = APIRouter()

# Imported per API contract; useful for debugging configuration in this module scope.
_ = DATABASE_PATH


class SyncRequest(BaseModel):
    """Request body for syncing Strava activities."""

    user_id: int


class CheckinRequest(BaseModel):
    """Request body for saving a daily check-in."""

    user_id: int
    date: str
    sleep_quality: int
    soreness: int
    energy: int
    life_stress: int
    notes: str | None = None


class ChatRequest(BaseModel):
    """Request body for AI coaching chat."""

    user_id: int
    message: str


class RaceGoalRequest(BaseModel):
    """Request body for saving a race goal."""

    user_id: int
    race_name: str
    race_date: str
    race_distance: str
    goal_finish_time: str | None = None


class FitnessBackgroundRequest(BaseModel):
    """Request body for saving fitness background."""

    user_id: int
    swim_level: str
    bike_level: str
    run_level: str
    weekly_hours_available: float


# Health endpoint used by monitoring tools and uptime checks to confirm the API is running.
@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a health status response."""
    return {"status": "ok", "app": APP_NAME}


# Starts Strava connection flow; typically called when a user clicks "Connect Strava".
@router.get("/auth/strava")
def auth_strava() -> RedirectResponse:
    """Redirect the user to Strava OAuth authorization."""
    return RedirectResponse(authorize_url(STRAVA_CLIENT_ID))


# Receives Strava redirect after login and stores tokens for this user.
@router.get("/auth/strava/callback")
def auth_strava_callback(code: str, state: str | None = None) -> dict[str, int | str]:
    """Exchange Strava auth code for tokens and save them for the user."""
    del state  # reserved for future CSRF validation once real user auth is implemented

    token_dict = exchange_token(STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, code)
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


# Called by the daily check-in form to save wellness feedback.
@router.post("/checkin")
def save_checkin(payload: CheckinRequest) -> dict[str, str]:
    """Save a daily check-in for a user."""
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO daily_checkins (
                user_id,
                date,
                sleep_quality,
                soreness,
                energy,
                life_stress,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.user_id,
                payload.date,
                payload.sleep_quality,
                payload.soreness,
                payload.energy,
                payload.life_stress,
                payload.notes,
            ),
        )
        connection.commit()

    return {"message": "Check-in saved"}


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
