"""Dashboard page for TriFirst Streamlit app."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

API_BASE_URL = "http://localhost:8000"
ACTIVITY_EMOJI = {"swim": "🏊", "bike": "🚴", "run": "🏃"}
DISCIPLINE_COLORS = {"swim": "#1f77b4", "bike": "#ff7f0e", "run": "#d62728"}


# Configure dashboard page metadata before rendering Streamlit widgets.
st.set_page_config(layout="wide", page_title="TriFirst", page_icon="🏊")

# Require an authenticated Streamlit session for dashboard access.
if "user_id" not in st.session_state:
    st.warning("Please log in to access this page.")
    st.page_link("pages/0_Login.py", label="Go to Login →")
    st.stop()

USER_ID = st.session_state["user_id"]


def api_get(path: str):
    """Send a GET request to the API and return decoded JSON.

    Args:
        path: API path beginning with a slash.

    Returns:
        Decoded JSON payload, or None when the request fails.
    """
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

# Profile expander lets athletes maintain race and fitness context.
with st.expander("⚙️ My Profile", expanded=False):
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

# --- Load activity data ---
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

col1.metric("Total activities logged", total_activities)
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

# --- Race day calculator ---
st.subheader("🏁 Race Day Calculator")
race_calc_payload = api_get(f"/race-calculator/{USER_ID}")
race_calc = race_calc_payload if isinstance(race_calc_payload, dict) else {}

if not race_calc.get("race_distance"):
    st.info("Set a race goal in My Profile to use the calculator")
else:
    race_name = race_calc.get("race_name") or "Your race"
    race_date = race_calc.get("race_date") or "Unknown date"
    st.markdown(f"**{race_name} — {race_date}**")

    counts = race_calc.get("activity_counts") or {}
    swim_default = float(race_calc.get("avg_swim_pace_per_100m") or 3.0)
    bike_default = float(race_calc.get("avg_bike_speed_kmh") or 20.0)
    run_default = float(race_calc.get("avg_run_pace_per_km") or 7.0)

    input_col1, input_col2, input_col3 = st.columns(3)
    with input_col1:
        swim_pace = st.number_input("Swim pace (min per 100m)", min_value=0.1, value=swim_default, step=0.1)
        st.caption(f"Based on {counts.get('swim', 0)} activities")
    with input_col2:
        bike_speed = st.number_input("Bike speed (km/h)", min_value=0.1, value=bike_default, step=0.1)
        st.caption(f"Based on {counts.get('bike', 0)} activities")
    with input_col3:
        run_pace = st.number_input("Run pace (min per km)", min_value=0.1, value=run_default, step=0.1)
        st.caption(f"Based on {counts.get('run', 0)} activities")

    race_distances = {
        "sprint": {"swim": 0.75, "bike": 20.0, "run": 5.0, "transition": 10},
        "olympic": {"swim": 1.5, "bike": 40.0, "run": 10.0, "transition": 10},
        "70.3": {"swim": 1.9, "bike": 90.0, "run": 21.1, "transition": 20},
        "full": {"swim": 3.8, "bike": 180.0, "run": 42.2, "transition": 20},
    }

    selected = race_distances.get(str(race_calc.get("race_distance")).lower(), race_distances["sprint"])
    swim_mins = (selected["swim"] * 10) * swim_pace
    bike_mins = (selected["bike"] / bike_speed) * 60
    run_mins = selected["run"] * run_pace
    transition_mins = selected["transition"]
    total_mins = swim_mins + bike_mins + run_mins + transition_mins

    def fmt_hhmm(minutes: float) -> str:
        """Format minutes as an H:MM duration string.

        Args:
            minutes: Duration in minutes.

        Returns:
            Duration formatted as hours and two-digit minutes.
        """
        total = int(round(minutes))
        hours = total // 60
        mins = total % 60
        return f"{hours}:{mins:02d}"

    out1, out2, out3, out4 = st.columns(4)
    out1.metric("🏊 Swim", fmt_hhmm(swim_mins))
    out2.metric("🚴 Bike", fmt_hhmm(bike_mins))
    out3.metric("🏃 Run", fmt_hhmm(run_mins))
    out4.metric("🏁 Total", fmt_hhmm(total_mins))

    with st.expander("🍌 Nutrition & Hydration Plan"):
        carbs_per_hour = 90 if total_mins > 150 else 60
        total_carbs_needed = min(total_mins * 1.0, (total_mins / 60) * carbs_per_hour)
        total_fluid_needed = total_mins * 0.6
        num_gels = round(total_carbs_needed / 25)
        bottles = round(total_fluid_needed / 500)
        gel_interval = max(20, int(round((bike_mins + run_mins) / max(num_gels, 1))))

        plan_df = pd.DataFrame(
            [
                {"Item": "Total carbohydrates needed", "Recommendation": f"{total_carbs_needed:.0f} grams"},
                {"Item": "Estimated fluid needed", "Recommendation": f"{total_fluid_needed:.0f} ml ({bottles} bottles)"},
                {"Item": "Suggested gels", "Recommendation": f"{num_gels} gels (one every {gel_interval} mins on the bike/run)"},
                {"Item": "Pre-race meal", "Recommendation": "High carb meal 2-3 hours before start"},
                {"Item": "Race morning", "Recommendation": "Light snack 30-60 mins before (banana, toast)"},
                {"Item": "On the bike", "Recommendation": "Start eating at 20 mins, eat every 20-30 mins"},
                {"Item": "On the run", "Recommendation": "Gel every 30-40 mins, sip at every aid station"},
            ]
        )
        st.table(plan_df)
        st.caption("These are estimates based on your predicted finish time. Always test your nutrition in training first.")

# --- Coach Tri ---
st.page_link("pages/2_Coach_Tri.py", label="💬 Chat with Coach Tri →")

# --- Sidebar sync buttons ---
st.sidebar.title("⚙️ TriFirst")
st.sidebar.link_button(
    "🔗 Connect Strava",
    url=f"{API_BASE_URL}/auth/strava?user_id={USER_ID}",
)

# Sidebar actions use the shared sync and logout pattern.
if st.sidebar.button("🔄 Sync Strava", key="sync_strava_btn"):
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

st.sidebar.divider()
if st.sidebar.button("🚪 Logout", key="logout_btn"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.switch_page("pages/0_Login.py")
