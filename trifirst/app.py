"""Main entrypoint for TriFirst Streamlit app."""
import streamlit as st

pages = [
    st.Page("pages/0_Login.py", title="Login", icon="🔑"),
    st.Page("pages/1_Dashboard.py", title="Dashboard", icon="📊"),
    st.Page("pages/2_Coach_Tri.py", title="Coach Tri", icon="🏅"),
    st.Page("pages/3_Calendar.py", title="Calendar", icon="📅"),
]

pg = st.navigation(pages)
pg.run()
