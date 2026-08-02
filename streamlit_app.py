"""PubCam Content Agent - app entry point. Launch: python -m streamlit run streamlit_app.py"""
import streamlit as st

from app_lib import REPO_ROOT, render_smeaton, render_theme_css

st.set_page_config(
    page_title="PubCam Content Agent",
    page_icon=str(REPO_ROOT / "assets" / "pubcam.png"),
    layout="wide",
)
render_theme_css()
st.logo(str(REPO_ROOT / "assets" / "pubcam.png"), size="large")

page = st.navigation({
    "": [
        st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("app_pages/chat.py", title="Chat", icon=":material/forum:"),
    ],
    "Do": [
        st.Page("app_pages/build.py", title="Post builder", icon=":material/construction:"),
        st.Page("app_pages/reel_builder.py", title="Reel builder", icon=":material/movie:"),
        st.Page("app_pages/score.py", title="Score posts", icon=":material/calculate:"),
        st.Page("app_pages/ideas.py", title="Ideas", icon=":material/lightbulb:"),
        st.Page("app_pages/trends.py", title="Trends", icon=":material/travel_explore:"),
        st.Page("app_pages/schedule.py", title="Schedule", icon=":material/event_upcoming:"),
        st.Page("app_pages/agent.py", title="Agent", icon=":material/smart_toy:"),
    ],
    "Understand": [
        st.Page("app_pages/dashboard.py", title="Dashboard", icon=":material/analytics:"),
        st.Page("app_pages/strategy.py", title="Strategy log", icon=":material/history_edu:"),
        st.Page("app_pages/notes.py", title="Notes", icon=":material/sticky_note_2:"),
        st.Page("app_pages/help.py", title="How to use", icon=":material/help:"),
    ],
})

with st.sidebar:
    render_smeaton(page.title)

if page.title != "Home":
    st.title(page.title)

page.run()
