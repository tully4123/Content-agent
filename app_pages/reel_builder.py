import streamlit as st

from app_lib import (
    REEL_PROMPT,
    VENUE_OPTIONS,
    VIDEO_EXTS,
    delete_reel_reference,
    list_reel_references,
    reel_reference_file,
    render_quality_toggle,
    run_agent_action,
    save_reel_reference,
)

st.write(
    "Drop in a reel you like - a video file, a link, or both - and a note on "
    "what you actually want copied. Get back a PubCam-branded script in that "
    "style: hook, shot list, text overlays, caption."
)
st.caption(
    "The agent never watches the video - there's no vision step in this "
    "pipeline. It works entirely from your note, so be specific: not \"like "
    "this one\" but \"the countdown-style text reveal\" or \"the way it cuts on "
    "every beat drop.\" Facts it can't verify (trending sounds included) come "
    "back marked [CHECK] rather than made up."
)
render_quality_toggle()

with st.form("build_reel", clear_on_submit=True):
    ref_file = st.file_uploader("Video file (optional)", type=VIDEO_EXTS)
    source_url = st.text_input("Source link (optional)", placeholder="e.g. a link to the reel you saw")
    venue_fit = st.selectbox("Venue fit", ["multi-venue"] + [v for v in VENUE_OPTIONS if v != "multi-venue"])
    notes = st.text_area(
        "What do you want copied?",
        placeholder="e.g. the countdown text-overlay style, cutting on every beat, "
        "ending on a group-chat-bait line",
    )
    submitted = st.form_submit_button("Build the reel", type="primary", icon=":material/movie:")

if submitted:
    if not notes.strip():
        st.error("Add a note on what you want copied - the build works from this, not the file.")
    elif not ref_file and not source_url.strip():
        st.error("Attach a video file or a source link - at least one.")
    else:
        ref_id = save_reel_reference(source_url.strip(), venue_fit, notes.strip(), ref_file)
        st.success(f"Saved reference #{ref_id}. Building the script now...")
        prompt = REEL_PROMPT.format(ref_id=ref_id, venue=venue_fit)
        run_agent_action(f"Building reel from reference #{ref_id}", prompt)
        st.page_link("app_pages/ideas.py", label="See it in Ideas", icon=":material/lightbulb:")

st.subheader("Reference library")
refs = list_reel_references()
if refs.empty:
    st.caption("No reference reels saved yet.")
for _, row in refs.iterrows():
    status = "no build yet"
    if row["idea_title"]:
        status = f"#{int(row['idea_id'])} · {row['idea_title']} · {row['idea_status']}"
        if not row["has_brief"]:
            status += " (brief pending)"
    with st.expander(f"Ref #{row['id']} · {row['venue_fit'] or 'unset'} · {status}"):
        st.markdown(f"**What to copy:** {row['notes']}")
        if row["source_url"]:
            st.markdown(f"**Source:** {row['source_url']}")
        video_path = reel_reference_file(int(row["id"]))
        if video_path:
            st.video(str(video_path))
        col1, col2 = st.columns(2)
        if not row["idea_title"] and col1.button(
            "Build from this reference", icon=":material/movie:", key=f"build_{row['id']}"
        ):
            prompt = REEL_PROMPT.format(ref_id=int(row["id"]), venue=row["venue_fit"] or "multi-venue")
            run_agent_action(f"Building reel from reference #{row['id']}", prompt)
            st.rerun()
        if col2.button("Delete reference", icon=":material/delete:", key=f"del_{row['id']}"):
            delete_reel_reference(int(row["id"]))
            st.rerun()
