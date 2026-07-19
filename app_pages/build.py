import streamlit as st

from app_lib import VENUE_OPTIONS, query, render_quality_toggle, run_agent_action

st.write(
    "Type a rough idea - get a finished PubCam-layout carousel: SAVE-THIS "
    "hook cover, one item per slide, the screenshot-and-send payoff slide, "
    "outro, and a caption."
)
st.caption(
    "Takes a couple of minutes. The build lands in **Ideas** with its brief "
    "attached - approve it there when you're happy. Facts it can't verify are "
    "marked [CHECK] rather than made up."
)
render_quality_toggle()

with st.form("build_post"):
    idea = st.text_input(
        "Your idea", placeholder="e.g. cheapest parmas in the gong / where to watch the footy Sunday"
    )
    col1, col2 = st.columns(2)
    venue_fit = col1.selectbox("Venue fit", ["multi-venue"] + [v for v in VENUE_OPTIONS if v != "multi-venue"])
    details = col2.text_input("Anything it must include (optional)", placeholder="e.g. include Heyday, mention Wednesday special")
    submitted = st.form_submit_button("Build the carousel", type="primary", icon=":material/construction:")

if submitted and idea.strip():
    prompt = (
        f"Run the build-post skill for this idea: \"{idea.strip()}\". "
        f"Venue fit: {venue_fit}."
    )
    if details.strip():
        prompt += f" Must include: {details.strip()}."
    prompt += (
        " Non-interactive (never ask questions). Save via scripts/db.py add-idea"
        " + add-brief and print the full build as your final message."
    )
    run_agent_action(f"Building carousel: {idea.strip()[:40]}", prompt)
    st.page_link("app_pages/ideas.py", label="See it in Ideas", icon=":material/lightbulb:")

st.subheader("Recent builds")
recent = query(
    "SELECT ideas.id, ideas.title, ideas.status, briefs.content"
    " FROM briefs JOIN ideas ON briefs.idea_id = ideas.id"
    " ORDER BY briefs.id DESC LIMIT 5"
)
if recent.empty:
    st.caption("Nothing built yet.")
for _, row in recent.iterrows():
    with st.expander(f"#{row['id']} · {row['title']} · {row['status']}"):
        st.markdown(row["content"])
