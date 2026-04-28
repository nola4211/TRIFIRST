"""Streamlit frontend for the TriFirst training dashboard."""

from __future__ import annotations

from datetime import date

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

# Fetch core data once for page sections
activities_payload = api_get(f"/activities/{USER_ID}")
activities = activities_payload if isinstance(activities_payload, list) else []
activities_df = pd.DataFrame(activities)

# Section 2 — Training Stats
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

# Section 3 — Recent Activities Table
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

# Section 4 — Weekly Volume Chart
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

# Section 5 — Coach Tri Chat
st.subheader("💬 Chat with Coach Tri")

if "chat_history" not in st.session_state:
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

# Section 6 — Daily Check-in (sidebar)
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
