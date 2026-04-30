"""Streamlit frontend for the TriFirst training dashboard."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE_URL = "http://localhost:8000"
USER_ID = 1
ACTIVITY_EMOJI = {"swim": "🏊", "bike": "🚴", "run": "🏃"}
DISCIPLINE_COLORS = {"swim": "#1f77b4", "bike": "#ff7f0e", "run": "#d62728"}


st.set_page_config(layout="wide", page_title="TriFirst", page_icon="🏊")


def api_get(path: str):
    """GET helper with graceful error handling."""
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"API request failed for {path}: {exc}")
        return None


# Section 1 — Header
st.title("🏊🚴🏃 TriFirst")
st.caption("Your personal Ironman training companion")

with st.expander("⚙️ My Profile", expanded=False):  # st.expander creates a collapsible panel to hide optional content.
    race_goal_payload = api_get(f"/race-goal/{USER_ID}")
    fitness_payload = api_get(f"/fitness-background/{USER_ID}")

    race_distance_options = {
        "Sprint": "sprint",
        "Olympic": "olympic",
        "70.3": "70.3",
        "Full Ironman": "full",
    }
    db_to_race_label = {value: label for label, value in race_distance_options.items()}

    level_options = {
        "Never swum": "none",
        "Beginner": "beginner",
        "Intermediate": "intermediate",
    }
    db_to_level_label = {value: label for label, value in level_options.items()}

    st.subheader("🏁 My Race Goal")
    default_race_date = date.today() + timedelta(days=180)
    existing_race = race_goal_payload if isinstance(race_goal_payload, dict) else {}
    existing_race_date = existing_race.get("race_date")
    try:
        loaded_race_date = date.fromisoformat(existing_race_date) if existing_race_date else default_race_date
    except ValueError:
        loaded_race_date = default_race_date
    race_label_default = db_to_race_label.get(existing_race.get("race_distance"), "Sprint")

    with st.form("race_goal_form"):
        race_name = st.text_input("Race name", value=existing_race.get("race_name", ""))
        race_date = st.date_input("Race date", value=loaded_race_date)
        race_distance_label = st.selectbox(
            "Race distance",
            options=list(race_distance_options.keys()),
            index=list(race_distance_options.keys()).index(race_label_default),
        )
        goal_finish_time = st.text_input(
            "Goal finish time (optional)",
            value=existing_race.get("goal_finish_time") or "",
            placeholder="12:00:00",
        )
        save_race_goal = st.form_submit_button("Save race goal")

        if save_race_goal:
            try:
                response = requests.post(
                    f"{API_BASE_URL}/race-goal",
                    json={
                        "user_id": USER_ID,
                        "race_name": race_name,
                        "race_date": race_date.isoformat(),
                        "race_distance": race_distance_options[race_distance_label],
                        "goal_finish_time": goal_finish_time or None,
                    },
                    timeout=15,
                )
                response.raise_for_status()
                st.success("Race goal saved")
                days_until_race = (race_date - date.today()).days
                st.info(f"{days_until_race} days until race day 🏁")
            except requests.RequestException as exc:
                st.error(f"Could not save race goal: {exc}")

    st.subheader("💪 My Fitness Background")
    existing_fitness = fitness_payload if isinstance(fitness_payload, dict) else {}
    swim_default = db_to_level_label.get(existing_fitness.get("swim_level"), "Never swum")
    bike_default = db_to_level_label.get(existing_fitness.get("bike_level"), "Never swum")
    run_default = db_to_level_label.get(existing_fitness.get("run_level"), "Never swum")

    with st.form("fitness_background_form"):
        swim_level = st.selectbox(
            "Swim level",
            options=list(level_options.keys()),
            index=list(level_options.keys()).index(swim_default),
        )
        bike_level = st.selectbox(
            "Bike level",
            options=list(level_options.keys()),
            index=list(level_options.keys()).index(bike_default),
        )
        run_level = st.selectbox(
            "Run level",
            options=list(level_options.keys()),
            index=list(level_options.keys()).index(run_default),
        )
        weekly_hours_available = st.number_input(
            "Weekly hours available",
            min_value=0.0,
            max_value=20.0,
            value=float(existing_fitness.get("weekly_hours_available") or 0.0),
            step=0.5,
        )
        save_fitness_background = st.form_submit_button("Save fitness background")

        if save_fitness_background:
            try:
                response = requests.post(
                    f"{API_BASE_URL}/fitness-background",
                    json={
                        "user_id": USER_ID,
                        "swim_level": level_options[swim_level],
                        "bike_level": level_options[bike_level],
                        "run_level": level_options[run_level],
                        "weekly_hours_available": weekly_hours_available,
                    },
                    timeout=15,
                )
                response.raise_for_status()
                st.success("Fitness background saved")
            except requests.RequestException as exc:
                st.error(f"Could not save fitness background: {exc}")

# --- Load activity data used by multiple UI sections ---
activities_payload = api_get(f"/activities/{USER_ID}")
activities = activities_payload if isinstance(activities_payload, list) else []
activities_df = pd.DataFrame(activities)

# --- Training stats cards ---
col1, col2, col3 = st.columns(3)

total_activities = len(activities)
total_km = float(activities_df["distance_km"].fillna(0).sum()) if not activities_df.empty else 0.0
counts = (
    activities_df["activity_type"].value_counts().to_dict() if "activity_type" in activities_df.columns else {}
)
swim_count = counts.get("swim", 0)
bike_count = counts.get("bike", 0)
run_count = counts.get("run", 0)

col1.metric("Total activities logged", total_activities)  # st.metric shows a single key number in a dashboard card.
col2.metric("Total km (all disciplines)", f"{total_km:.1f}")
col3.metric("Swim / Bike / Run", f"{swim_count} / {bike_count} / {run_count}")

# --- Recent activities table ---
st.subheader("Recent Activities")

if activities_df.empty:
    st.info("No activities yet. Sync Strava to get started.")
else:
    table_df = activities_df.copy()
    table_df["date"] = pd.to_datetime(table_df["date"], errors="coerce")
    table_df = table_df.sort_values("date", ascending=False)

    table_df["activity_type"] = table_df["activity_type"].fillna("").map(
        lambda activity: f"{ACTIVITY_EMOJI.get(activity, '❓')} {activity}"
    )

    display_cols = ["date", "activity_type", "distance_km", "duration_mins", "avg_hr"]
    for col in display_cols:
        if col not in table_df.columns:
            table_df[col] = None

    st.dataframe(table_df[display_cols].head(10), use_container_width=True, hide_index=True)

# --- Weekly volume chart ---
st.subheader("Weekly Volume")

if activities_df.empty:
    st.info("No activity data available to build weekly chart.")
else:
    weekly_df = activities_df.copy()
    weekly_df["date"] = pd.to_datetime(weekly_df["date"], errors="coerce")
    weekly_df = weekly_df.dropna(subset=["date"])

    if weekly_df.empty:
        st.info("No valid activity dates available for weekly chart.")
    else:
        iso = weekly_df["date"].dt.isocalendar()
        weekly_df["week"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)

        weekly_volume = (
            weekly_df.groupby(["week", "activity_type"], as_index=False)["distance_km"].sum().rename(
                columns={"activity_type": "discipline", "distance_km": "km"}
            )
        )

        # Plotly is used here to build an interactive weekly distance chart.
        figure = px.bar(
            weekly_volume,
            x="week",
            y="km",
            color="discipline",
            barmode="group",
            color_discrete_map=DISCIPLINE_COLORS,
            category_orders={"discipline": ["swim", "bike", "run"]},
        )
        figure.update_layout(xaxis_title="Week", yaxis_title="Kilometers")
        st.plotly_chart(figure, use_container_width=True)

# --- Weekly AI digest ---
st.subheader("📰 Weekly Digest")

if "weekly_digests" not in st.session_state:
    payload = api_get(f"/digest/{USER_ID}")
    st.session_state.weekly_digests = payload if isinstance(payload, list) else []

if st.button("✨ Generate This Week's Digest"):
    with st.spinner("Generating your weekly digest..."):
        try:
            response = requests.post(
                f"{API_BASE_URL}/digest/generate",
                json={"user_id": USER_ID},
                timeout=45,
            )
            response.raise_for_status()
            st.success("Weekly digest generated!")
        except requests.RequestException as exc:
            st.error(f"Could not generate digest: {exc}")

    refreshed = api_get(f"/digest/{USER_ID}")
    st.session_state.weekly_digests = refreshed if isinstance(refreshed, list) else []

digests = st.session_state.weekly_digests
if digests:
    latest_digest = digests[0]
    header = f"Week of {latest_digest.get('week_start_date', 'Unknown date')}"
    st.markdown(f"**{header}**")
    st.info(latest_digest.get("ai_summary_text") or "No digest text available.")

    if len(digests) > 1:
        with st.expander("Previous weeks"):
            for digest in digests[1:]:
                st.markdown(f"**Week of {digest.get('week_start_date', 'Unknown date')}**")
                st.write(digest.get("ai_summary_text") or "No digest text available.")
else:
    st.info("No digest yet — click Generate to get your first weekly summary!")

# --- Coach Tri chat interface ---
st.subheader("💬 Chat with Coach Tri")

if "chat_history" not in st.session_state:  # st.session_state keeps values between reruns (like simple memory).
    st.session_state.chat_history = []

for entry in st.session_state.chat_history:
    with st.chat_message(entry["role"]):
        st.markdown(entry["content"])

user_message = st.chat_input("Ask Coach Tri anything...")
if user_message:
    st.session_state.chat_history.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.markdown(user_message)

    with st.spinner("Coach Tri is thinking..."):
        try:
            response = requests.post(
                f"{API_BASE_URL}/coach/chat",
                json={"user_id": USER_ID, "message": user_message},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            coach_reply = payload.get("response", "No response received.")
        except requests.RequestException as exc:
            coach_reply = f"I couldn't reach the coach service: {exc}"
            st.error(f"Chat request failed: {exc}")

    st.session_state.chat_history.append({"role": "assistant", "content": coach_reply})
    with st.chat_message("assistant"):
        st.markdown(coach_reply)

# --- Daily check-in sidebar ---
st.sidebar.title("📋 Daily Check-in")

checkin_date = st.sidebar.date_input("Date", value=date.today())
sleep_quality = st.sidebar.slider("Sleep quality", 1, 5, 3)
energy = st.sidebar.slider("Energy", 1, 5, 3)
soreness = st.sidebar.slider("Soreness", 1, 5, 3)
life_stress = st.sidebar.slider("Life stress", 1, 5, 3)

if st.sidebar.button("Save check-in"):
    try:
        response = requests.post(
            f"{API_BASE_URL}/checkin",
            json={
                "user_id": USER_ID,
                "date": checkin_date.isoformat(),
                "sleep_quality": sleep_quality,
                "energy": energy,
                "soreness": soreness,
                "life_stress": life_stress,
                "notes": None,
            },
            timeout=15,
        )
        response.raise_for_status()
        st.sidebar.success("Check-in saved successfully.")
    except requests.RequestException as exc:
        st.sidebar.error(f"Could not save check-in: {exc}")

if st.sidebar.button("🔄 Sync Strava"):
    try:
        response = requests.post(
            f"{API_BASE_URL}/sync/strava",
            json={"user_id": USER_ID},
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        activities_added = payload.get("activities_added", 0)
        st.sidebar.success(f"Sync complete. Added {activities_added} activities.")
    except requests.RequestException as exc:
        st.sidebar.error(f"Strava sync failed: {exc}")
