"""AI coaching module for generating personalized beginner triathlon guidance."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from groq import Groq

from trifirst.config import GROQ_API_KEY


def build_user_context(user_id: int, db_conn: sqlite3.Connection) -> str:
    """Build a formatted training-context summary for a user from persisted data.

    Args:
        user_id: The user identifier used to query profile and training tables.
        db_conn: An active SQLite connection.

    Returns:
        A multi-line context summary string for prompt injection.
    """
    user_row = db_conn.execute(
        "SELECT name, age FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    race_goal_row = db_conn.execute(
        """
        SELECT race_name, race_date, race_distance
        FROM race_goals
        WHERE user_id = ?
        ORDER BY race_date DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    fitness_row = db_conn.execute(
        """
        SELECT swim_level, bike_level, run_level, weekly_hours_available
        FROM fitness_background
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    activities = db_conn.execute(
        """
        SELECT date, activity_type, distance_km, duration_mins, avg_hr
        FROM activities
        WHERE user_id = ? AND date >= date('now', '-30 day')
        ORDER BY date DESC, id DESC
        """,
        (user_id,),
    ).fetchall()

    checkins = db_conn.execute(
        """
        SELECT date, sleep_quality, energy, soreness, life_stress
        FROM daily_checkins
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT 7
        """,
        (user_id,),
    ).fetchall()

    now_utc = datetime.now(timezone.utc)
    week_start = (now_utc - timedelta(days=now_utc.weekday())).date().isoformat()
    weekly_volume = db_conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN activity_type = 'swim' THEN distance_km ELSE 0 END), 0) AS swim_km,
            COALESCE(SUM(CASE WHEN activity_type = 'bike' THEN distance_km ELSE 0 END), 0) AS bike_km,
            COALESCE(SUM(CASE WHEN activity_type = 'run' THEN distance_km ELSE 0 END), 0) AS run_km
        FROM activities
        WHERE user_id = ? AND date >= ?
        """,
        (user_id, week_start),
    ).fetchone()

    name = user_row["name"] if user_row else "Athlete"
    age = user_row["age"] if user_row and user_row["age"] is not None else "unknown"

    lines = [f"User: {name} (age: {age})"]

    if race_goal_row:
        lines.append(
            "Race goal: "
            f"{race_goal_row['race_name']} on {race_goal_row['race_date']} "
            f"({race_goal_row['race_distance']})"
        )
    else:
        lines.append("Race goal: none recorded")

    if fitness_row:
        lines.append(
            "Fitness background: "
            f"swim={fitness_row['swim_level']}, bike={fitness_row['bike_level']}, "
            f"run={fitness_row['run_level']}, "
            f"weekly_hours_available={fitness_row['weekly_hours_available']}"
        )
    else:
        lines.append("Fitness background: none recorded")

    lines.append("Last 30 days activities:")
    if activities:
        for row in activities:
            lines.append(
                f"- {row['date']}: {row['activity_type']}, "
                f"distance_km={row['distance_km']}, duration_mins={row['duration_mins']}, avg_hr={row['avg_hr']}"
            )
    else:
        lines.append("- No activities logged")

    lines.append("Last 7 daily check-ins:")
    if checkins:
        for row in checkins:
            lines.append(
                f"- {row['date']}: sleep_quality={row['sleep_quality']}, energy={row['energy']}, "
                f"soreness={row['soreness']}, life_stress={row['life_stress']}"
            )
    else:
        lines.append("- No check-ins logged")

    lines.append(
        "Weekly volume summary (km): "
        f"swim={weekly_volume['swim_km']}, bike={weekly_volume['bike_km']}, run={weekly_volume['run_km']}"
    )

    return "\n".join(lines)


def chat(user_id: int, message: str, db_conn: sqlite3.Connection) -> str:
    """Generate and persist an AI coaching response for a user message.

    Args:
        user_id: The user identifier for context lookup and message history.
        message: The new user message text.
        db_conn: An active SQLite connection.

    Returns:
        The assistant response text from the Groq model.
    """
    history_rows = db_conn.execute(
        """
        SELECT role, message
        FROM (
            SELECT role, message, timestamp, id
            FROM coach_messages
            WHERE user_id = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT 20
        )
        ORDER BY timestamp ASC, id ASC
        """,
        (user_id,),
    ).fetchall()

    user_context = build_user_context(user_id, db_conn)

    system_prompt = (
        "Athlete context:\n"
        f"{user_context}\n\n"
        "You are Coach Tri, a friendly and encouraging coach for beginner triathletes. "
        "Use simple, plain English and avoid jargon unless you explain it clearly in one short phrase. "
        "You coach all three disciplines: swim, bike, and run. "
        "You understand common race formats and distances: Sprint, Olympic, 70.3 (Half Ironman), and Full Ironman. "
        "Prioritize consistency over intensity for beginners and recommend safe, sustainable progress. "
        "Always tailor advice to the athlete's fitness background, recent training, and race timeline in the context above. "
        "Keep each response concise and actionable, with a maximum of 3 to 4 sentences unless the athlete asks for more detail. "
        "Use the athlete's actual name occasionally to make responses personal and supportive."
    )

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": row["role"], "content": row["message"]} for row in history_rows)
    messages.append({"role": "user", "content": message})

    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(model="llama3-70b-8192", messages=messages)
    assistant_text = completion.choices[0].message.content or ""

    db_conn.execute(
        "INSERT INTO coach_messages (user_id, role, message) VALUES (?, 'user', ?)",
        (user_id, message),
    )
    db_conn.execute(
        "INSERT INTO coach_messages (user_id, role, message) VALUES (?, 'assistant', ?)",
        (user_id, assistant_text),
    )
    db_conn.commit()

    return assistant_text
