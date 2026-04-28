"""FastAPI route definitions for TriFirst API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

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


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a health status response."""
    return {"status": "ok", "app": APP_NAME}


@router.get("/auth/strava")
def auth_strava() -> RedirectResponse:
    """Redirect the user to Strava OAuth authorization."""
    return RedirectResponse(authorize_url(STRAVA_CLIENT_ID))


@router.get("/auth/strava/callback")
def auth_strava_callback(code: str, state: str | None = None) -> dict[str, int | str]:
    """Exchange Strava auth code for tokens and save them for the user."""
    del state  # reserved for future CSRF validation once real user auth is implemented

    token_dict = exchange_token(STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, code)
    user_id = 1

    with get_connection() as connection:
        save_tokens(user_id, token_dict, connection)

    return {"message": "Strava connected successfully", "user_id": user_id}


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


@router.post("/coach/chat")
def coach_chat(payload: ChatRequest) -> dict[str, str]:
    """Generate a coaching response for a user chat message."""
    with get_connection() as connection:
        response_text = chat(payload.user_id, payload.message, connection)
    return {"response": response_text}