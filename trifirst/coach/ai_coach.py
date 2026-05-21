"""AI coaching module for generating personalized beginner triathlon guidance."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from groq import Groq

from trifirst.config import GROQ_API_KEY


# Build a plain-text summary of the user's profile and training so the AI can give personalized advice.
def build_user_context(user_id: int, db_conn) -> str:
    """Build a formatted training-context summary for a user from persisted data.

    Args:
        user_id: The user identifier used to query profile and training tables.
        db_conn: An active SQLite connection.

    Returns:
        A multi-line context summary string for prompt injection.
    """
    # Fetch the base user profile used to personalize prompts.
    user_row = db_conn.execute(
        "SELECT name, age FROM users WHERE id = %s",
        (user_id,),
    ).fetchone()

    # Fetch the latest race goal to determine target distance and timeline.
    race_goal_row = db_conn.execute(
        """
        SELECT race_name, race_date, race_distance
        FROM race_goals
        WHERE user_id = %s
        ORDER BY race_date DESC, id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


    # Fetch injury, limitation, and scheduling context for coaching safety.
    athlete_profile_row = db_conn.execute(
        """
        SELECT injury_history, physical_limitations, preferred_training_days, training_days_notes
        FROM athlete_profile
        WHERE user_id = %s
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    # Fetch the latest self-reported discipline levels and available hours.
    fitness_row = db_conn.execute(
        """
        SELECT swim_level, bike_level, run_level, weekly_hours_available
        FROM fitness_background
        WHERE user_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    # Fetch recent activities to ground advice in current training data.
    activities = db_conn.execute(
        """
        SELECT date, activity_type, distance_km, duration_mins, avg_hr
        FROM activities
        WHERE user_id = %s AND date >= NOW() - INTERVAL '30 days'
        ORDER BY date DESC, id DESC
        """,
        (user_id,),
    ).fetchall()


    now_utc = datetime.now(timezone.utc)
    week_start = (now_utc - timedelta(days=now_utc.weekday())).date().isoformat()
    # Fetch current-week discipline totals for concise prompt context.
    weekly_volume = db_conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN activity_type = 'swim' THEN distance_km ELSE 0 END), 0) AS swim_km,
            COALESCE(SUM(CASE WHEN activity_type = 'bike' THEN distance_km ELSE 0 END), 0) AS bike_km,
            COALESCE(SUM(CASE WHEN activity_type = 'run' THEN distance_km ELSE 0 END), 0) AS run_km
        FROM activities
        WHERE user_id = %s AND date >= %s
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


    if athlete_profile_row:
        lines.append("Athlete profile:")
        lines.append(f"- Injury history: {athlete_profile_row['injury_history']}")
        lines.append(f"- Physical limitations: {athlete_profile_row['physical_limitations']}")
        lines.append(f"- Preferred training days: {athlete_profile_row['preferred_training_days']}")
        lines.append(f"- Training schedule notes: {athlete_profile_row['training_days_notes']}")
    else:
        lines.append("Athlete profile: not yet completed")

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

    lines.append(
        "Weekly volume summary (km): "
        f"swim={weekly_volume['swim_km']}, bike={weekly_volume['bike_km']}, run={weekly_volume['run_km']}"
    )

    return "\n".join(lines)


def chat(user_id: int, message: str, db_conn) -> str:
    """Generate and persist an AI coaching response for a user message.

    Args:
        user_id: The user identifier for context lookup and message history.
        message: The new user message text.
        db_conn: An active SQLite connection.

    Returns:
        The assistant response text from the Groq model.
    """
    # Fetch recent conversation history so Coach Tri stays contextual.
    history_rows = db_conn.execute(
        """
        SELECT role, message
        FROM (
            SELECT role, message, timestamp, id
            FROM coach_messages
            WHERE user_id = %s
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

    "You are Coach Tri. You are a direct, no-nonsense triathlon coach who talks like a real person — "
    "not a chatbot, not a corporate wellness app. You use casual, conversational language. "
    "You say things like 'here's what I'd do' and 'honestly' and 'look' — not 'certainly' or 'great question'. "
    "Never use filler phrases like 'certainly', 'of course', 'absolutely', 'great question', or 'I hope this helps'. "
    "Never use bullet points or numbered lists — talk in sentences like a real coach would in person. "
    "Keep responses under 4 sentences unless the athlete explicitly asks for more detail. "
    "Give ONE clear recommendation, not a menu of options. "
    "Always reference 2-3 specific numbers from the athlete's actual data before giving advice. "
    "Use the athlete's name occasionally but not every message. "
    "End with a short direct question to keep the conversation going.\n\n"

    "### CALENDAR INTEGRATION\n"
    "You have a calendar feature. When the athlete asks for a training plan, schedule, "
    "or what workouts to do this week, tell them you're putting together a plan and sending "
    "it to their calendar for review. Say something like: 'I've put together a plan for you — "
    "check your Calendar page to review and confirm the workouts.' "
    "Never say you don't have calendar access — you do. "
    "Never say you're text-based or can't schedule workouts.\n\n"

    "### HEART RATE ZONE SCIENCE\n"
    "Use Coggan's 5-zone model: Zone 1 (<68% max HR, recovery), Zone 2 (69-83%, aerobic base — "
    "the most important zone for triathlon, should be 80% of all training), Zone 3 (84-94%, tempo — "
    "the 'junk miles' zone, avoid for beginners), Zone 4 (95-105%, threshold — hard but sustainable "
    "for 20-60 mins), Zone 5 (>106%, VO2 max — short hard efforts). "
    "For beginners, Zone 2 is everything. If the athlete can't hold a conversation, they're going too hard. "
    "A common mistake: beginners train Zone 3 constantly — too hard to build aerobic base, too easy to get fit. "
    "Maffetone Method: max aerobic HR = 180 minus age. Use this as a Zone 2 ceiling for beginners. "
    "HR drift: if avg_hr is rising week over week at the same pace, the athlete is accumulating fatigue. "
    "Cardiac efficiency: as fitness improves, same pace = lower HR. Track this in the athlete's data.\n\n"

    "### PERIODIZATION SCIENCE\n"
    "Triathlon training follows 4 phases — always know which phase the athlete is in based on race_date: "
    "BASE (12+ weeks out): high volume, low intensity, Zone 2 only, build aerobic engine. "
    "BUILD (8-12 weeks out): introduce threshold work, brick workouts, race-specific efforts. "
    "PEAK (4-8 weeks out): highest training stress, longest long rides and runs, tune-up races. "
    "TAPER (0-3 weeks out): cut volume 40-60%, maintain intensity, let body absorb the training. "
    "Taper week before race: 50% volume reduction, short sharp efforts to stay sharp. "
    "Recovery weeks: every 3rd or 4th week should be a recovery week with 30-40% volume reduction. "
    "10% rule: never increase weekly volume by more than 10% week over week. "
    "Always calculate which phase the athlete is in from their race_date and today's date, "
    "and tailor every recommendation to that phase.\n\n"

    "### SPORTS PSYCHOLOGY\n"
    "Race anxiety is normal and physiologically identical to excitement — teach athletes to reframe it. "
    "Pre-race routine: same warm-up, same music, same breakfast creates neural anchors that reduce anxiety. "
    "The swim start is the most anxiety-inducing moment in triathlon — seed yourself at the back or sides. "
    "Mantras work: a short phrase repeated during hard efforts reduces perceived exertion by up to 18% "
    "(Brick et al., 2016). Suggest the athlete develops a personal mantra. "
    "Chunking: never think about the full race distance — break it into small segments. "
    "In training, missed sessions cause guilt spirals that compound — address this directly and immediately. "
    "Identity-based motivation: 'I am a triathlete' is more powerful than 'I am training for a triathlon'. "
    "When an athlete seems discouraged, acknowledge it directly before pivoting to solutions.\n\n"

    "### INJURY PREVENTION & BIOMECHANICS\n"
    "Most common triathlon injuries and causes: "
    "Runner's knee (IT band syndrome): too much too soon, weak hips — fix with hip strengthening and cadence work. "
    "Swimmer's shoulder: dropped elbow on catch, overreaching — fix with high elbow drill. "
    "Achilles tendinitis: running off the bike on tired legs, sudden mileage increase — "
    "fix with eccentric heel drops and gradual progression. "
    "Lower back pain on bike: saddle too low or too far forward, weak core — get a bike fit. "
    "Saddle sores: wrong shorts, wrong saddle, chamois cream — address immediately or they get worse. "
    "Red flags that require rest: sharp localized pain, pain that worsens during exercise, "
    "swelling, pain that disrupts sleep. "
    "Run cadence: 170-180 steps per minute reduces injury risk regardless of pace. "
    "Swim: most beginners over-rotate and cross the centerline — causes shoulder injury over time. "
    "If the athlete mentions any pain, address it immediately and conservatively before any other advice.\n\n"

    "### HOW TO RESPOND\n"
    "Step 1: Look at the athlete's actual data in the context above. "
    "Step 2: Reference 2-3 specific numbers ('your last 3 runs averaged 6:45/km at 158bpm'). "
    "Step 3: Give ONE direct recommendation grounded in the science above. "
    "Step 4: End with one short question. "
    "Never say 'based on your data' as an opener — just start with the insight. "
    "Sound like a coach texting their athlete, not a report being generated. "
    "If the athlete asks for a training plan, generate a specific week-by-week plan "
    "using their race_date, fitness_background, weekly_hours_available, and actual pace data. "
    "Make the plan concrete: specific distances, specific days based on their preferred_training_days, "
    "specific effort levels using the zone system above."
    )

    # Conversation history is previous messages; we include it so replies stay consistent and contextual.
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend({"role": row["role"], "content": row["message"]} for row in history_rows)
    messages.append({"role": "user", "content": message})

    client = Groq(api_key=GROQ_API_KEY)
    # This calls the Groq API to generate the assistant's next message from our prompt + history.
    completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
    assistant_text = completion.choices[0].message.content or ""

    lowered = message.lower()
    plan_keywords = ["plan", "schedule", "week", "workouts", "calendar", "what should i do"]
    if any(keyword in lowered for keyword in plan_keywords):
        proposed = propose_workouts(user_id, message, db_conn)
        if proposed:
            # Save coach-proposed workouts for calendar review and confirmation.
            pending_cursor = db_conn.execute(
                """
                INSERT INTO pending_workouts (user_id, proposed_by, workouts_json, message)
                VALUES (%s, 'coach', %s, %s)
                """,
                (user_id, json.dumps(proposed), message),
            )
            pending_id = pending_cursor.lastrowid
            assistant_text = f"{assistant_text.rstrip()}\n\nPENDING_WORKOUTS_ID:{pending_id}"

    # Persist the user chat message in the conversation history.
    db_conn.execute(
        "INSERT INTO coach_messages (user_id, role, message) VALUES (%s, 'user', %s)",
        (user_id, message),
    )
    # Persist the assistant response in the conversation history.
    db_conn.execute(
        "INSERT INTO coach_messages (user_id, role, message) VALUES (%s, 'assistant', %s)",
        (user_id, assistant_text),
    )
    db_conn.commit()

    return assistant_text


def propose_workouts(user_id: int, message: str, db_conn) -> list[dict[str, object]]:
    """Generate a structured workout proposal list from Coach Tri.

    Args:
        user_id: User id used to build training context.
        message: Athlete request that triggered schedule generation.
        db_conn: Active SQLite connection.

    Returns:
        List of proposed workout dictionaries, or an empty list when parsing fails.
    """
    user_context = build_user_context(user_id, db_conn)
    prompt = (
        "You are Coach Tri. Build a 7-day triathlon training schedule using the athlete context and request. "
        "Respond ONLY with a JSON array of workout objects with this exact schema:\n"
        "[\n"
        "  {\n"
        '    "id": 1,\n'
        '    "date": "YYYY-MM-DD",\n'
        '    "activity_type": "swim|bike|run|brick|rest",\n'
        '    "title": "short title",\n'
        '    "description": "2-3 sentence coaching note",\n'
        '    "duration_mins": 45,\n'
        '    "distance_km": 8.0,\n'
        '    "intensity": "easy|moderate|hard|race"\n'
        "  }\n"
        "]\n"
        "Use null only for distance_km when unknown. Do not include markdown, explanation, or extra keys."
    )

    client = Groq(api_key=GROQ_API_KEY)
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": f"Athlete context:\n{user_context}"},
            {"role": "user", "content": f"{prompt}\nAthlete request: {message}"},
        ],
    )
    content = (completion.choices[0].message.content or "").strip()
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        return []
    return []


def _most_recent_completed_week_window(today_utc: datetime | None = None) -> tuple[str, str]:
    """Return ISO dates for the most recent completed Monday-Sunday week.

    Args:
        today_utc: Optional current UTC datetime for deterministic tests.

    Returns:
        Tuple containing Monday start date and Sunday end date as ISO strings.
    """
    now_utc = today_utc or datetime.now(timezone.utc)
    this_monday = (now_utc - timedelta(days=now_utc.weekday())).date()
    week_start = this_monday - timedelta(days=7)
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def generate_weekly_digest(user_id: int, db_conn) -> str:
    """Generate and persist an AI weekly digest for the most recent completed week.

    Args:
        user_id: User id whose completed week should be summarized.
        db_conn: Active SQLite connection.

    Returns:
        Generated digest text from the AI model.
    """
    week_start, week_end = _most_recent_completed_week_window()

    # Fetch the athlete name used in the generated weekly digest.
    user_row = db_conn.execute("SELECT name FROM users WHERE id = %s", (user_id,)).fetchone()
    athlete_name = user_row["name"] if user_row and user_row["name"] else "Athlete"

    # Fetch aggregate swim, bike, and run totals for the completed week.
    discipline_rows = db_conn.execute(
        """
        SELECT
            activity_type,
            COALESCE(SUM(distance_km), 0) AS total_km,
            COALESCE(SUM(duration_mins), 0) / 60.0 AS total_hours,
            COUNT(*) AS session_count
        FROM activities
        WHERE user_id = %s AND date BETWEEN %s AND %s
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

    # Fetch the next race goal to include days remaining in the weekly digest.
    race_goal_row = db_conn.execute(
        """
        SELECT race_name, race_date, race_distance
        FROM race_goals
        WHERE user_id = %s
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
        "If no activities were logged, stay encouraging and focus on a clear next-week recommendation. Do not reference daily check-in data."
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

    # Save the generated weekly digest and aggregate totals for dashboard history.
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
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, week_start, swim_km, bike_km, run_km, total_hours, ai_summary_text),
    )
    db_conn.commit()

    return ai_summary_text
