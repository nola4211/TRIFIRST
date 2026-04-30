"""Utilities for authenticating with and syncing activities from the Strava API.

OAuth2 is a standard login flow that lets one app access another app's data without sharing your password.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"



# --- OAuth functions ---

class StravaIntegrationError(Exception):
    """Raised when Strava API or integration operations fail."""


def authorize_url(client_id: str) -> str:
    """Build the Strava OAuth2 authorization URL for the given client ID.

    The generated URL requests the ``activity:read_all`` scope and uses
    ``response_type=code`` so the user can be redirected back with an
    authorization code.

    Args:
        client_id: Strava application client ID.

    Returns:
        Fully formed Strava authorization URL.
    """
    query = urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "activity:read_all",
        }
    )
    return f"{STRAVA_AUTHORIZE_URL}?{query}"


def _post_token(payload: dict[str, Any]) -> dict[str, Any]:
    """Post to the Strava token endpoint and return normalized token fields.

    Args:
        payload: Form payload for the Strava token endpoint.

    Returns:
        Dictionary containing ``access_token``, ``refresh_token``, and ``expires_at``.

    Raises:
        StravaIntegrationError: If the request fails or response payload is invalid.
    """
    try:
        response = httpx.post(STRAVA_TOKEN_URL, data=payload, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        message = exc.response.text.strip()
        raise StravaIntegrationError(
            f"Strava token request failed ({exc.response.status_code}): {message}"
        ) from exc
    except httpx.HTTPError as exc:
        raise StravaIntegrationError(f"Could not reach Strava token endpoint: {exc}") from exc

    data = response.json()
    required_fields = ("access_token", "refresh_token", "expires_at")
    missing = [field for field in required_fields if field not in data]
    if missing:
        raise StravaIntegrationError(
            f"Strava token response missing required fields: {', '.join(missing)}"
        )

    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": int(data["expires_at"]),
    }


def exchange_token(client_id: str, client_secret: str, code: str) -> dict[str, Any]:
    """Exchange an OAuth authorization code for Strava tokens.

    Args:
        client_id: Strava application client ID.
        client_secret: Strava application client secret.
        code: OAuth2 authorization code returned by Strava.

    Returns:
        Token dictionary with ``access_token``, ``refresh_token``, and ``expires_at``.
    """
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }
    return _post_token(payload)


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    """Refresh a Strava access token using a refresh token.

    Args:
        client_id: Strava application client ID.
        client_secret: Strava application client secret.
        refresh_token: Existing Strava refresh token.

    Returns:
        Token dictionary with ``access_token``, ``refresh_token``, and ``expires_at``.
    """
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    return _post_token(payload)



# --- Token storage functions ---
def save_tokens(user_id: int, token_dict: dict[str, Any], db_conn: sqlite3.Connection) -> None:
    """Insert or update Strava tokens for a user.

    Args:
        user_id: Local TriFirst user ID.
        token_dict: Token dictionary containing ``access_token``, ``refresh_token``, and
            ``expires_at``.
        db_conn: Open SQLite connection.

    Raises:
        StravaIntegrationError: If required token fields are missing.
    """
    required_fields = ("access_token", "refresh_token", "expires_at")
    missing = [field for field in required_fields if field not in token_dict]
    if missing:
        raise StravaIntegrationError(
            f"Cannot save tokens: missing fields {', '.join(missing)}"
        )

    cursor = db_conn.execute("SELECT id FROM strava_tokens WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        db_conn.execute(
            """
            UPDATE strava_tokens
            SET access_token = ?, refresh_token = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (
                token_dict["access_token"],
                token_dict["refresh_token"],
                int(token_dict["expires_at"]),
                user_id,
            ),
        )
    else:
        db_conn.execute(
            """
            INSERT INTO strava_tokens (user_id, access_token, refresh_token, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                token_dict["access_token"],
                token_dict["refresh_token"],
                int(token_dict["expires_at"]),
            ),
        )
    db_conn.commit()


def load_tokens(user_id: int, db_conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Load Strava tokens for a user.

    Args:
        user_id: Local TriFirst user ID.
        db_conn: Open SQLite connection.

    Returns:
        Token dictionary with ``access_token``, ``refresh_token``, and ``expires_at`` if found;
        otherwise ``None``.
    """
    row = db_conn.execute(
        """
        SELECT access_token, refresh_token, expires_at
        FROM strava_tokens
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    if row is None:
        return None

    return {
        "access_token": row["access_token"],
        "refresh_token": row["refresh_token"],
        "expires_at": int(row["expires_at"]),
    }


def get_valid_token(
    user_id: int,
    db_conn: sqlite3.Connection,
    client_id: str,
    client_secret: str,
) -> str:
    """Get a valid Strava access token, refreshing it if needed.

    A token is refreshed when it expires within 5 minutes.

    Args:
        user_id: Local TriFirst user ID.
        db_conn: Open SQLite connection.
        client_id: Strava application client ID.
        client_secret: Strava application client secret.

    Returns:
        Valid Strava access token.

    Raises:
        StravaIntegrationError: If tokens are missing or refresh fails.
    """
    tokens = load_tokens(user_id, db_conn)
    if tokens is None:
        raise StravaIntegrationError(
            f"No Strava tokens found for user_id={user_id}. Please connect Strava first."
        )

    now_ts = int(datetime.now(timezone.utc).timestamp())
    if int(tokens["expires_at"]) <= now_ts + 300:
        refreshed = refresh_access_token(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=tokens["refresh_token"],
        )
        save_tokens(user_id, refreshed, db_conn)
        return str(refreshed["access_token"])

    return str(tokens["access_token"])



# --- Activity sync functions ---
def fetch_activities(
    access_token: str,
    after_timestamp: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch all Strava activities for an athlete using paginated requests.

    Args:
        access_token: Valid Strava access token.
        after_timestamp: Optional UNIX timestamp to fetch only activities after this date.

    Returns:
        List of raw activity dictionaries as returned by Strava.

    Raises:
        StravaIntegrationError: If any request fails.
    """
    all_activities: list[dict[str, Any]] = []
    page = 1

    while True:
        # Pagination means we request results page by page until no full page is left.
        params: dict[str, Any] = {"per_page": 100, "page": page}
        if after_timestamp is not None:
            params["after"] = int(after_timestamp)

        try:
            response = httpx.get(
                STRAVA_ACTIVITIES_URL,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = exc.response.text.strip()
            raise StravaIntegrationError(
                f"Failed to fetch Strava activities ({exc.response.status_code}): {message}"
            ) from exc
        except httpx.HTTPError as exc:
            raise StravaIntegrationError(f"Could not reach Strava activities endpoint: {exc}") from exc

        page_activities = response.json()
        if not isinstance(page_activities, list):
            raise StravaIntegrationError("Unexpected Strava activities response format.")

        all_activities.extend(page_activities)
        if len(page_activities) < 100:
            break

        page += 1

    return all_activities


def parse_activity(raw: dict[str, Any], user_id: int) -> dict[str, Any] | None:
    """Parse a raw Strava activity into the local ``activities`` schema shape.

    Args:
        raw: Raw Strava activity payload.
        user_id: Local TriFirst user ID.

    Returns:
        Parsed activity dictionary matching local schema columns, or ``None`` when activity
        type is not supported.

    Raises:
        StravaIntegrationError: If required fields are missing from a supported activity.
    """
    activity_type_map = {
        "Swim": "swim",
        "Ride": "bike",
        "VirtualRide": "bike",
        "Run": "run",
    }

    mapped_type = activity_type_map.get(raw.get("type"))
    if mapped_type is None:
        return None

    if "start_date_local" not in raw or "elapsed_time" not in raw or "distance" not in raw:
        raise StravaIntegrationError(
            "Raw Strava activity is missing one of: start_date_local, elapsed_time, distance"
        )

    start_date_local = str(raw["start_date_local"])
    date_part = start_date_local.split("T")[0]

    avg_hr = raw.get("average_heartrate")

    return {
        "user_id": user_id,
        "source": "strava",
        "activity_type": mapped_type,
        "date": date_part,
        "duration_mins": float(raw["elapsed_time"]) / 60.0,
        "distance_km": float(raw["distance"]) / 1000.0,
        "avg_hr": int(avg_hr) if avg_hr is not None else None,
    }


def sync_activities(
    user_id: int,
    db_conn: sqlite3.Connection,
    client_id: str,
    client_secret: str,
) -> int:
    """Synchronize Strava activities into the local activities table.

    This function obtains a valid token, fetches all athlete activities, parses supported
    activities, and inserts new rows while skipping duplicates identified by
    ``user_id + date + activity_type + source``.

    Args:
        user_id: Local TriFirst user ID.
        db_conn: Open SQLite connection.
        client_id: Strava application client ID.
        client_secret: Strava application client secret.

    Returns:
        Number of newly inserted activities.
    """
    access_token = get_valid_token(user_id, db_conn, client_id, client_secret)
    raw_activities = fetch_activities(access_token)

    inserted_count = 0
    for raw in raw_activities:
        parsed = parse_activity(raw, user_id)
        if parsed is None:
            continue

                # This duplicate check skips inserting an activity we already saved earlier.
        duplicate = db_conn.execute(
            """
            SELECT 1
            FROM activities
            WHERE user_id = ? AND date = ? AND activity_type = ? AND source = ?
            LIMIT 1
            """,
            (
                parsed["user_id"],
                parsed["date"],
                parsed["activity_type"],
                parsed["source"],
            ),
        ).fetchone()

        if duplicate:
            continue

        db_conn.execute(
            """
            INSERT INTO activities (
                user_id,
                source,
                activity_type,
                date,
                duration_mins,
                distance_km,
                avg_hr
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                parsed["user_id"],
                parsed["source"],
                parsed["activity_type"],
                parsed["date"],
                parsed["duration_mins"],
                parsed["distance_km"],
                parsed["avg_hr"],
            ),
        )
        inserted_count += 1

    db_conn.commit()
    return inserted_count
