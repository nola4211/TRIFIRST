"""Main entrypoint for TriFirst Streamlit app."""
import streamlit as st

pages = [
    st.Page("pages/1_Dashboard.py", title="Dashboard", icon="📊"),
    st.Page("pages/2_Coach_Tri.py", title="Coach Tri", icon="🏅"),
]

pg = st.navigation(pages)
pg.run()