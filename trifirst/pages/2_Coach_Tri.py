from __future__ import annotations

from datetime import date

import pandas as pd
import requests
import streamlit as st

API_BASE_URL = "http://localhost:8000"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

st.set_page_config(page_title="Coach Tri", page_icon="🏅", layout="wide")

if "user_id" not in st.session_state:
    st.warning("Please log in to access this page.")
    st.page_link("pages/0_Login.py", label="Go to Login →")
    st.stop()

USER_ID = st.session_state["user_id"]


def api_get(path: str):
    try:
        response = requests.get(f"{API_BASE_URL}{path}", timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        st.error(f"API request failed for {path}: {exc}")
        return None


with st.sidebar:
    with st.expander("🔗 Connect Garmin", expanded=False):
        credentials_payload = api_get(f"/garmin/credentials/{USER_ID}") or {}
        existing_email = credentials_payload.get("email", "") if credentials_payload.get("connected") else ""
        garmin_email = st.text_input("Email", value=existing_email, key="garmin_email_input")
        garmin_password = st.text_input("Password", type="password", key="garmin_password_input")
        if st.button("Save Garmin Credentials", key="save_garmin_credentials_btn"):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/garmin/credentials",
                    json={"user_id": USER_ID, "email": garmin_email, "password": garmin_password},
                    timeout=20,
                )
                response.raise_for_status()
                st.success("Garmin credentials saved")
                credentials_payload = api_get(f"/garmin/credentials/{USER_ID}") or {}
            except requests.RequestException as exc:
                st.error(f"Could not save Garmin credentials: {exc}")

        if credentials_payload.get("connected"):
            st.success("✅ Connected")
        else:
            st.warning("⚠️ Not connected")

    if st.button("🔄 Sync Strava", key="coach_sync_strava"):
        try:
            response = requests.post(f"{API_BASE_URL}/sync/strava", json={"user_id": USER_ID}, timeout=45)
            response.raise_for_status()
            payload = response.json()
            st.success(f"Strava sync complete ({payload.get('activities_added', 0)} activities added)")
        except requests.RequestException as exc:
            st.error(f"Could not sync Strava: {exc}")

    if st.button("🔄 Sync Garmin", key="coach_sync_garmin"):
        try:
            response = requests.post(f"{API_BASE_URL}/sync/garmin", json={"user_id": USER_ID, "days": 7}, timeout=45)
            response.raise_for_status()
            payload = response.json()
            st.success(f"Garmin sync complete ({payload.get('days_synced', 0)} days synced)")
        except requests.RequestException as exc:
            st.error(f"Could not sync Garmin: {exc}")

# Load chat history from database on first load
if "coach_chat_history" not in st.session_state:
    history = api_get(f"/coach/history/{USER_ID}")
    st.session_state.coach_chat_history = [
        {"role": row.get("role", "assistant"), "content": row.get("message", "")} for row in (history or [])
    ]

if "athlete_profile" not in st.session_state:
    st.session_state.athlete_profile = api_get(f"/athlete-profile/{USER_ID}") or {}

left_col, right_col = st.columns([2, 1])

with left_col:
    st.title("🏅 Coach Tri")
    st.caption("Your personal AI triathlon coach")

    # Chat input at the TOP — processes new messages first
    user_message = st.chat_input("Message Coach Tri...")
    if user_message:
        with st.spinner("Coach Tri is thinking..."):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/coach/chat",
                    json={"user_id": USER_ID, "message": user_message},
                    timeout=30,
                )
                response.raise_for_status()
                coach_reply = response.json().get("response", "No response received.")
            except requests.RequestException as exc:
                coach_reply = f"I couldn't reach the coach service: {exc}"
                st.error(f"Chat request failed: {exc}")

        # Append both messages to history
        st.session_state.coach_chat_history.append({"role": "user", "content": user_message})
        st.session_state.coach_chat_history.append({"role": "assistant", "content": coach_reply})

    # Show last 5 messages only (most recent at bottom for natural chat flow)
    recent_messages = st.session_state.coach_chat_history[-10:]  # 5 exchanges = 10 messages
    for entry in recent_messages:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])

    # Show how many older messages are hidden
    total = len(st.session_state.coach_chat_history)
    if total > 10:
        st.caption(f"Showing last 5 exchanges. {(total - 10) // 2} older exchanges not shown.")

with right_col:
    st.subheader("📋 About You")
    profile = st.session_state.athlete_profile or {}
    selected_days = [d for d in (profile.get("preferred_training_days") or "").split(",") if d in DAYS]

    with st.form("athlete_profile_form"):
        injury_history = st.text_area(
            "Injury history",
            value=profile.get("injury_history") or "",
            placeholder="e.g. Left knee tendinitis in 2024, fully recovered",
        )
        physical_limitations = st.text_area(
            "Physical limitations",
            value=profile.get("physical_limitations") or "",
            placeholder="e.g. Lower back tightness, avoid high impact on consecutive days",
        )
        preferred_days = st.multiselect("Preferred training days", options=DAYS, default=selected_days)
        training_notes = st.text_area(
            "Schedule notes",
            value=profile.get("training_days_notes") or "",
            placeholder="e.g. Can only do long rides on weekends, work until 7pm weekdays",
        )
        if st.form_submit_button("Save"):
            try:
                response = requests.post(
                    f"{API_BASE_URL}/athlete-profile",
                    json={
                        "user_id": USER_ID,
                        "injury_history": injury_history or None,
                        "physical_limitations": physical_limitations or None,
                        "preferred_training_days": ",".join(preferred_days) or None,
                        "training_days_notes": training_notes or None,
                    },
                    timeout=20,
                )
                response.raise_for_status()
                st.success("Profile saved")
                st.session_state.athlete_profile = api_get(f"/athlete-profile/{USER_ID}") or {}
            except requests.RequestException as exc:
                st.error(f"Could not save profile: {exc}")

    st.divider()

    race_goal = api_get(f"/race-goal/{USER_ID}") or {}
    activities = api_get(f"/activities/{USER_ID}") or []
    garmin_stats = api_get(f"/garmin/stats/{USER_ID}") or []

    days_until = "N/A"
    if race_goal.get("race_date"):
        days_until = (pd.to_datetime(race_goal["race_date"]).date() - date.today()).days

    week_start = pd.Timestamp.today().normalize() - pd.Timedelta(days=pd.Timestamp.today().weekday())
    act_df = pd.DataFrame(activities)
    swim_km = bike_km = run_km = 0.0
    if not act_df.empty:
        act_df["date"] = pd.to_datetime(act_df["date"], errors="coerce")
        week_df = act_df[act_df["date"] >= week_start]
        swim_km = float(week_df.loc[week_df["activity_type"] == "swim", "distance_km"].fillna(0).sum())
        bike_km = float(week_df.loc[week_df["activity_type"] == "bike", "distance_km"].fillna(0).sum())
        run_km = float(week_df.loc[week_df["activity_type"] == "run", "distance_km"].fillna(0).sum())

    latest_bb = "N/A"
    latest_rhr = "N/A"
    if garmin_stats:
        latest = garmin_stats[0]
        latest_bb = latest.get("body_battery_high") if latest.get("body_battery_high") is not None else "N/A"
        latest_rhr = latest.get("resting_hr") if latest.get("resting_hr") is not None else "N/A"

    st.markdown("### Summary")
    st.info(
        f"Days until race: **{days_until}**\n\n"
        f"This week — Swim: **{swim_km:.1f}km**, Bike: **{bike_km:.1f}km**, Run: **{run_km:.1f}km**\n\n"
        f"Body battery: **{latest_bb}**  |  Resting HR: **{latest_rhr}**"
    )


st.sidebar.divider()
if st.sidebar.button("🚪 Logout", key="logout_btn"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.switch_page("pages/0_Login.py")
