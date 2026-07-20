import io
import zipfile

import streamlit as st

from app_lib import VENUE_OPTIONS, query, render_carousel_images, render_quality_toggle, run_agent_action


def _zip_images(images):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img_path in images:
            zf.write(img_path, arcname=img_path.name)
    buf.seek(0)
    return buf


def _render_and_show(idea_id: int, title: str) -> None:
    with st.spinner("Drawing slides..."):
        ok, message, images = render_carousel_images(idea_id)
    if not ok:
        st.error(message)
        return
    if not images:
        st.warning("No slides came out of that render.")
        return
    cols = st.columns(4)
    for i, img_path in enumerate(images):
        cols[i % 4].image(str(img_path), caption=img_path.stem, use_container_width=True)
    st.download_button(
        "Download all slides (.zip)",
        data=_zip_images(images),
        file_name=f"pubcam_carousel_idea_{idea_id}.zip",
        mime="application/zip",
        icon=":material/download:",
        key=f"zip_{idea_id}",
    )


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

    newest = query("SELECT id, title FROM ideas ORDER BY id DESC LIMIT 1")
    if not newest.empty:
        new_id, new_title = int(newest.iloc[0]["id"]), newest.iloc[0]["title"]
        st.session_state["just_built_id"] = new_id
        st.session_state["just_built_title"] = new_title

if "just_built_id" in st.session_state:
    nid, ntitle = st.session_state["just_built_id"], st.session_state["just_built_title"]
    st.subheader("Turn it into images")
    st.caption(
        "Draws every slide as a 1080x1350 PNG in the PubCam navy/amber template - "
        "basic, postable-as-is cards. Takes a couple of seconds, costs nothing "
        "(no agent call, just Pillow drawing the brief)."
    )
    if st.button("Render carousel images", icon=":material/image:", key="render_just_built"):
        _render_and_show(nid, ntitle)

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
        if st.button("Render carousel images", icon=":material/image:", key=f"render_{row['id']}"):
            _render_and_show(int(row["id"]), row["title"])
