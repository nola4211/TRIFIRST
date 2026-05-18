"""Login and registration page for TriFirst."""

from __future__ import annotations

import requests
import streamlit as st

API_BASE_URL = "http://localhost:8000"

# Configure the unauthenticated login page before rendering widgets.
st.set_page_config(page_title="TriFirst", page_icon="🏊", layout="centered")

# Redirect authenticated users away from login and into the dashboard.
if "user_id" in st.session_state and "username" in st.session_state:
    st.switch_page("pages/1_Dashboard.py")

st.markdown("<h1 style='text-align: center;'>🏊🚴🏃 TriFirst</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Your personal Ironman training companion</p>", unsafe_allow_html=True)

login_tab, register_tab = st.tabs(["Login", "Create Account"])

# Login tab authenticates existing users and stores session identity.
with login_tab:
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login", key="login_button"):
        try:
            response = requests.post(
                f"{API_BASE_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=15,
            )
            if response.status_code == 200:
                payload = response.json()
                st.session_state["user_id"] = payload["user_id"]
                st.session_state["name"] = payload["name"]
                st.session_state["username"] = payload["username"]
                st.switch_page("pages/1_Dashboard.py")
            else:
                st.error("Invalid username or password")
        except requests.RequestException:
            st.error("Invalid username or password")

# Registration tab creates an account and immediately signs in the user.
with register_tab:
    name = st.text_input("Name", key="reg_name")
    email = st.text_input("Email", key="reg_email")
    reg_username = st.text_input("Username", key="reg_username")
    reg_password = st.text_input("Password", type="password", key="reg_password")
    confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm_password")
    age = st.number_input("Age (optional)", min_value=0, value=None, step=1)

    if st.button("Register", key="register_button"):
        if reg_password != confirm_password:
            st.error("Passwords do not match")
        else:
            try:
                response = requests.post(
                    f"{API_BASE_URL}/auth/register",
                    json={
                        "name": name,
                        "email": email,
                        "username": reg_username,
                        "password": reg_password,
                        "age": age,
                    },
                    timeout=15,
                )
                if response.status_code == 200:
                    login_response = requests.post(
                        f"{API_BASE_URL}/auth/login",
                        json={"username": reg_username, "password": reg_password},
                        timeout=15,
                    )
                    login_response.raise_for_status()
                    payload = login_response.json()
                    st.session_state["user_id"] = payload["user_id"]
                    st.session_state["name"] = payload["name"]
                    st.session_state["username"] = payload["username"]
                    st.switch_page("pages/1_Dashboard.py")
                else:
                    detail = response.json().get("detail", "Could not create account")
                    st.error(detail)
            except requests.RequestException as exc:
                st.error(f"Could not create account: {exc}")
