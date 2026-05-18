from __future__ import annotations

import calendar
import json
from datetime import date, datetime

import requests
import streamlit as st

API_BASE_URL = "http://localhost:8000"
ACTIVITY_EMOJI = {"swim": "🏊", "bike": "🚴", "run": "🏃", "brick": "🧱", "rest": "💤"}

st.set_page_config(page_title="Training Calendar", page_icon="📅", layout="wide")

if "user_id" not in st.session_state:
    st.warning("Please log in to access this page.")
    st.page_link("pages/0_Login.py", label="Go to Login →")
    st.stop()

USER_ID = st.session_state["user_id"]


def api_get(path: str, params: dict | None = None):
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def load_calendar(month_str: str) -> list[dict]:
    return api_get(f"/calendar/{USER_ID}", params={"month": month_str})


if "selected_month" not in st.session_state:
    st.session_state.selected_month = date.today().replace(day=1)
if "selected_date" not in st.session_state:
    st.session_state.selected_date = date.today().isoformat()

selected_month = st.session_state.selected_month
month_str = selected_month.strftime("%Y-%m")

st.title("📅 Training Calendar")
nav1, nav2, nav3 = st.columns([1, 2, 1])
with nav1:
    if st.button("⬅️ Prev Month"):
        y = selected_month.year - (1 if selected_month.month == 1 else 0)
        m = 12 if selected_month.month == 1 else selected_month.month - 1
        st.session_state.selected_month = date(y, m, 1)
        st.rerun()
with nav2:
    st.subheader(selected_month.strftime("%B %Y"))
with nav3:
    if st.button("Next Month ➡️"):
        y = selected_month.year + (1 if selected_month.month == 12 else 0)
        m = 1 if selected_month.month == 12 else selected_month.month + 1
        st.session_state.selected_month = date(y, m, 1)
        st.rerun()

try:
    entries = load_calendar(month_str)
except requests.RequestException as exc:
    st.error(f"Could not load calendar: {exc}")
    entries = []

by_date: dict[str, list[dict]] = {}
for item in entries:
    by_date.setdefault(item["date"], []).append(item)

cal = calendar.Calendar(firstweekday=0)
for week in cal.monthdatescalendar(selected_month.year, selected_month.month):
    cols = st.columns(7)
    for idx, day in enumerate(week):
        with cols[idx]:
            day_key = day.isoformat()
            in_month = day.month == selected_month.month
            label = f"**{day.day}**" if in_month else f"_{day.day}_"
            if st.button(label, key=f"day_{day_key}"):
                st.session_state.selected_date = day_key
            for workout in by_date.get(day_key, []):
                emoji = ACTIVITY_EMOJI.get(workout.get("activity_type"), "🏋️")
                title = workout.get("title", "Workout")
                status = workout.get("status", "scheduled")
                if workout.get("source") == "strava" or status == "completed":
                    st.markdown(f":green[{emoji} {title}]")
                elif status == "skipped":
                    st.markdown(f":gray[~~{emoji} {title}~~]")
                else:
                    st.markdown(f":blue[{emoji} {title}]")

st.divider()
selected_date = st.session_state.selected_date
st.subheader(f"Details for {selected_date}")
daily = by_date.get(selected_date, [])
if not daily:
    st.info("No workouts logged for this day yet.")

for workout in daily:
    with st.container(border=True):
        st.markdown(f"### {ACTIVITY_EMOJI.get(workout.get('activity_type'), '🏋️')} {workout.get('title', 'Workout')}")
        st.write(workout.get("description") or "No description")
        st.caption(f"Duration: {workout.get('duration_mins') or '-'} mins • Distance: {workout.get('distance_km') or '-'} km")
        status = workout.get("status", "scheduled")
        if workout.get("record_type") == "scheduled_workout":
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Mark Complete", key=f"complete_{workout['id']}"):
                    requests.patch(f"{API_BASE_URL}/calendar/workout/{workout['id']}", json={"status": "completed"}, timeout=20).raise_for_status()
                    st.rerun()
            with c2:
                if st.button("Mark Skipped", key=f"skip_{workout['id']}"):
                    requests.patch(f"{API_BASE_URL}/calendar/workout/{workout['id']}", json={"status": "skipped"}, timeout=20).raise_for_status()
                    st.rerun()
            with c3:
                if st.button("Delete", key=f"delete_{workout['id']}"):
                    requests.delete(f"{API_BASE_URL}/calendar/workout/{workout['id']}", timeout=20).raise_for_status()
                    st.rerun()
        elif status == "completed":
            st.success("✅ Completed via Strava")

with st.form("add_workout_form"):
    st.markdown("### Add Workout")
    w_date = st.date_input("Date", value=datetime.fromisoformat(selected_date).date())
    activity = st.selectbox("Activity", ["swim", "bike", "run", "brick", "rest"])
    title = st.text_input("Title")
    description = st.text_area("Description")
    duration = st.number_input("Duration (mins)", min_value=0, step=5)
    distance = st.number_input("Distance (km)", min_value=0.0, step=0.5)
    intensity = st.selectbox("Intensity", ["easy", "moderate", "hard", "race"])
    if st.form_submit_button("Add Workout"):
        requests.post(
            f"{API_BASE_URL}/calendar/workout",
            json={
                "user_id": USER_ID,
                "date": w_date.isoformat(),
                "activity_type": activity,
                "title": title,
                "description": description or None,
                "duration_mins": int(duration) if duration else None,
                "distance_km": float(distance) if distance else None,
                "intensity": intensity,
                "source": "manual",
            },
            timeout=20,
        ).raise_for_status()
        st.success("Workout added")
        st.rerun()

pending = None
try:
    pending = api_get(f"/calendar/pending/{USER_ID}")
except requests.RequestException:
    pending = None

if pending:
    proposed = json.loads(pending["workouts_json"])
    st.warning(f"🏅 Coach Tri has proposed {len(proposed)} workouts — review and confirm")
    selected_ids: list[int] = []
    for workout in proposed:
        with st.container(border=True):
            emoji = ACTIVITY_EMOJI.get(workout.get("activity_type"), "🏋️")
            checked = st.checkbox(
                f"{workout.get('date')} {emoji} {workout.get('title')} ({workout.get('duration_mins')} mins, {workout.get('intensity')})",
                value=True,
                key=f"pending_{pending['id']}_{workout.get('id')}",
            )
            st.caption(workout.get("description") or "")
            if checked:
                selected_ids.append(int(workout.get("id")))

    b1, b2 = st.columns(2)
    with b1:
        if st.button("✅ Confirm Selected"):
            requests.post(
                f"{API_BASE_URL}/calendar/confirm",
                json={"user_id": USER_ID, "pending_id": pending["id"], "selected_ids": selected_ids},
                timeout=20,
            ).raise_for_status()
            st.success("Workouts confirmed")
            st.rerun()
    with b2:
        if st.button("❌ Dismiss All"):
            requests.delete(f"{API_BASE_URL}/calendar/pending/{pending['id']}", timeout=20).raise_for_status()
            st.info("Dismissed pending workouts")
            st.rerun()

with st.sidebar:
    if st.button("🔄 Sync Strava", key="calendar_sync_strava"):
        response = requests.post(f"{API_BASE_URL}/sync/strava", json={"user_id": USER_ID}, timeout=45)
        response.raise_for_status()
        st.success("Strava sync complete")
    st.page_link("pages/2_Coach_Tri.py", label="💬 Ask Coach Tri to plan your week →")
    if st.button("🚪 Logout", key="calendar_logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("pages/0_Login.py")
