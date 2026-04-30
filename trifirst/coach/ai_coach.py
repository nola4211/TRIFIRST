"""AI coaching module for generating personalized beginner triathlon guidance."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from groq import Groq

from trifirst.config import GROQ_API_KEY


# Build a plain-text summary of the user's profile and training so the AI can give personalized advice.
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

        # We build user context so the AI answers based on this athlete's real data, not generic advice.
    user_context = build_user_context(user_id, db_conn)

        # The system prompt is the main instruction that sets the AI's role, tone, and safety rules.
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

        # Conversation history is previous messages; we include it so replies stay consistent and contextual.
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": row["role"], "content": row["message"]} for row in history_rows)
    messages.append({"role": "user", "content": message})

    client = Groq(api_key=GROQ_API_KEY)
        # This calls the Groq API to generate the assistant's next message from our prompt + history.
    completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
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


def _most_recent_completed_week_window(today_utc: datetime | None = None) -> tuple[str, str]:
    """Return ISO dates for the most recent completed Monday-Sunday week."""
    now_utc = today_utc or datetime.now(timezone.utc)
    this_monday = (now_utc - timedelta(days=now_utc.weekday())).date()
    week_start = this_monday - timedelta(days=7)
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def generate_weekly_digest(user_id: int, db_conn: sqlite3.Connection) -> str:
    """Generate and persist an AI weekly digest for the most recent completed week."""
    week_start, week_end = _most_recent_completed_week_window()

    user_row = db_conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    athlete_name = user_row["name"] if user_row and user_row["name"] else "Athlete"

    discipline_rows = db_conn.execute(
        """
        SELECT
            activity_type,
            COALESCE(SUM(distance_km), 0) AS total_km,
            COALESCE(SUM(duration_mins), 0) / 60.0 AS total_hours,
            COUNT(*) AS session_count
        FROM activities
        WHERE user_id = ? AND date BETWEEN ? AND ?
        GROUP BY activity_type
        """,
        (user_id, week_start, week_end),
    ).fetchall()

    by_discipline = {
        row["activity_type"]: {
            "total_km": float(row["total_km"] or 0),
            "total_hours": float(row["total_hours"] or 0),
            "session_count": int(row["session_count"] or 0),
        }
        for row in discipline_rows
    }

    swim_km = by_discipline.get("swim", {}).get("total_km", 0.0)
    bike_km = by_discipline.get("bike", {}).get("total_km", 0.0)
    run_km = by_discipline.get("run", {}).get("total_km", 0.0)
    total_hours = sum(item["total_hours"] for item in by_discipline.values())
    total_sessions = sum(item["session_count"] for item in by_discipline.values())

    checkin_row = db_conn.execute(
        """
        SELECT
            AVG(sleep_quality) AS avg_sleep_quality,
            AVG(energy) AS avg_energy,
            AVG(soreness) AS avg_soreness,
            AVG(life_stress) AS avg_life_stress
        FROM daily_checkins
        WHERE user_id = ? AND date BETWEEN ? AND ?
        """,
        (user_id, week_start, week_end),
    ).fetchone()

    race_goal_row = db_conn.execute(
        """
        SELECT race_name, race_date, race_distance
        FROM race_goals
        WHERE user_id = ?
        ORDER BY race_date ASC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    days_until_race = None
    if race_goal_row and race_goal_row["race_date"]:
        race_date = datetime.fromisoformat(race_goal_row["race_date"]).date()
        days_until_race = (race_date - datetime.now(timezone.utc).date()).days

    summary = {
        "athlete_name": athlete_name,
        "week_start_date": week_start,
        "week_end_date": week_end,
        "activities": {
            "swim": by_discipline.get("swim", {"total_km": 0.0, "total_hours": 0.0, "session_count": 0}),
            "bike": by_discipline.get("bike", {"total_km": 0.0, "total_hours": 0.0, "session_count": 0}),
            "run": by_discipline.get("run", {"total_km": 0.0, "total_hours": 0.0, "session_count": 0}),
            "total_hours": total_hours,
            "total_sessions": total_sessions,
        },
        "checkins": {
            "avg_sleep_quality": float(checkin_row["avg_sleep_quality"]) if checkin_row and checkin_row["avg_sleep_quality"] is not None else None,
            "avg_energy": float(checkin_row["avg_energy"]) if checkin_row and checkin_row["avg_energy"] is not None else None,
            "avg_soreness": float(checkin_row["avg_soreness"]) if checkin_row and checkin_row["avg_soreness"] is not None else None,
            "avg_life_stress": float(checkin_row["avg_life_stress"]) if checkin_row and checkin_row["avg_life_stress"] is not None else None,
        },
        "race_goal": {
            "race_name": race_goal_row["race_name"] if race_goal_row else None,
            "race_date": race_goal_row["race_date"] if race_goal_row else None,
            "race_distance": race_goal_row["race_distance"] if race_goal_row else None,
            "days_remaining": days_until_race,
        },
    }

    system_prompt = (
        "You are Coach Tri writing a weekly training recap. "
        "Be encouraging and specific, using actual values from the provided summary data. "
        "Structure your response with exactly these 3 short sections and headings: "
        "1) This Week, 2) What's Working, 3) Focus for Next Week. "
        "In 'This Week', describe what the athlete did in 2-3 sentences. "
        "In 'What's Working', give one positive observation. "
        "In 'Focus for Next Week', give one specific actionable recommendation. "
        "Use the athlete's name naturally. Keep the total response under 150 words. "
        "If no activities were logged, stay encouraging and focus on a clear next-week recommendation."
    )

    user_prompt = f"Weekly summary data:\n{summary}"

    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    ai_summary_text = (completion.choices[0].message.content or "").strip()

    db_conn.execute(
        """
        INSERT INTO weekly_summaries (
            user_id,
            week_start_date,
            total_swim_km,
            total_bike_km,
            total_run_km,
            total_hours,
            ai_summary_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, week_start, swim_km, bike_km, run_km, total_hours, ai_summary_text),
    )
    db_conn.commit()

    return ai_summary_text
