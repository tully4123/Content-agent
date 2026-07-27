import io
import zipfile

import streamlit as st

from app_lib import (
    IMAGE_EXTS,
    PHOTO_FOLDER_OPTIONS,
    PHOTO_LIBRARY,
    POST_REF_LINE,
    VENUE_OPTIONS,
    delete_photo,
    delete_post_reference,
    list_photo_library,
    list_post_references,
    post_reference_file,
    query,
    render_carousel_images,
    render_quality_toggle,
    run_agent_action,
    save_post_reference,
    save_slide_override,
    save_uploaded_photos,
)


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
        cols[i % 4].image(str(img_path), caption=img_path.stem, width="stretch")
    st.download_button(
        "Download all slides (.zip)",
        data=_zip_images(images),
        file_name=f"pubcam_carousel_idea_{idea_id}.zip",
        mime="application/zip",
        icon=":material/download:",
        key=f"zip_{idea_id}",
    )
    with st.expander("Got a real photo for one of these slides?"):
        oc1, oc2 = st.columns([1, 3])
        slide_n = oc1.number_input(
            "Slide #", min_value=1, max_value=len(images), step=1, key=f"ovr_n_{idea_id}"
        )
        ovr_file = oc2.file_uploader(
            "Photo", type=["jpg", "jpeg", "png", "webp"], key=f"ovr_f_{idea_id}"
        )
        if ovr_file and st.button("Save + re-render", icon=":material/sync:", key=f"ovr_btn_{idea_id}"):
            save_slide_override(idea_id, int(slide_n), ovr_file)
            st.session_state[f"show_render_{idea_id}"] = True
            st.rerun()


def _render_button(idea_id: int, title: str, key: str) -> None:
    """A render button that stays 'on' across reruns (session_state), so a
    photo saved from the override uploader below can trigger an immediate
    re-render without the grid disappearing."""
    render_key = f"show_render_{idea_id}"
    if st.button("Render carousel images", icon=":material/image:", key=key):
        st.session_state[render_key] = True
    if st.session_state.get(render_key):
        _render_and_show(idea_id, title)


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
    with st.expander("Copy a specific post structure (optional)"):
        st.caption(
            "Leave this empty for PubCam's proven default layout (SAVE-THIS "
            "cover, one item per slide, payoff, outro). Fill it in to build "
            "to a different structure instead - a Q&A, a ranked countdown, a "
            "this-or-that, whatever it is. The agent never analyses the "
            "image, only your description of the structure."
        )
        ref_image = st.file_uploader("Reference image (optional)", type=IMAGE_EXTS, key="ref_image")
        ref_url = st.text_input("Reference link (optional)", placeholder="e.g. a link to the post")
        ref_notes = st.text_area(
            "Structure to copy",
            placeholder="e.g. numbered countdown 5 to 1, each slide reveals the next rank with a big number",
        )
    submitted = st.form_submit_button("Build the carousel", type="primary", icon=":material/construction:")

if submitted and idea.strip():
    if (ref_image or ref_url.strip()) and not ref_notes.strip():
        st.error("Describe the structure you want copied, or clear the reference section for the default layout.")
    else:
        prompt = (
            f"Run the build-post skill for this idea: \"{idea.strip()}\". "
            f"Venue fit: {venue_fit}."
        )
        if details.strip():
            prompt += f" Must include: {details.strip()}."
        if ref_notes.strip():
            ref_id = save_post_reference(ref_url.strip(), ref_notes.strip(), ref_image)
            prompt += POST_REF_LINE.format(ref_id=ref_id)
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
        "Draws every slide as a 1080x1350 PNG in PubCam's real carousel style - "
        "photo, dark scrim, script signature. Photos come from assets/venue_photos/ "
        "- it picks the right one per venue automatically, or a placeholder with a "
        "note on what to shoot if nothing matches yet. Takes a couple of seconds, "
        "costs nothing (no agent call, just Pillow drawing the brief)."
    )
    _render_button(nid, ntitle, key="render_just_built")

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
        _render_button(int(row["id"]), row["title"], key=f"render_{row['id']}")

st.divider()
st.subheader("Reference post library")
st.caption(
    "Every structure you've saved from 'Copy a specific post structure' "
    "above. Build from one again, or just browse for inspiration."
)
post_refs = list_post_references()
if post_refs.empty:
    st.caption("No reference posts saved yet.")
for _, row in post_refs.iterrows():
    status = "no build yet"
    if row["idea_title"]:
        status = f"#{int(row['idea_id'])} · {row['idea_title']} · {row['idea_status']}"
        if not row["has_brief"]:
            status += " (brief pending)"
    with st.expander(f"Ref #{row['id']} · {status}"):
        st.markdown(f"**Structure:** {row['notes']}")
        if row["source_url"]:
            st.markdown(f"**Source:** {row['source_url']}")
        image_path = post_reference_file(int(row["id"]))
        if image_path:
            st.image(str(image_path), width="stretch")
        pcol1, pcol2 = st.columns(2)
        if not row["idea_title"] and pcol1.button(
            "Build from this reference", icon=":material/construction:", key=f"buildref_{row['id']}"
        ):
            prompt = (
                f"Run the build-post skill for this idea: \"{row['notes']}\". Venue fit: multi-venue."
                + POST_REF_LINE.format(ref_id=int(row["id"]))
                + " Non-interactive (never ask questions). Save via scripts/db.py add-idea"
                  " + add-brief and print the full build as your final message."
            )
            run_agent_action(f"Building carousel from reference #{row['id']}", prompt)
            st.rerun()
        if pcol2.button("Delete reference", icon=":material/delete:", key=f"delref_{row['id']}"):
            delete_post_reference(int(row["id"]))
            st.rerun()

st.divider()
st.subheader("Photo library")
st.caption(
    "Upload real venue photos here - renders automatically pick the right one "
    "per slide by matching venue/headline against the folder you upload to "
    "(word overlap, no exact filenames needed). Nothing uploaded yet for a "
    "slide? It renders on a placeholder until you add one - see "
    "assets/venue_photos/README.md."
)
lib_col1, lib_col2 = st.columns([1, 2])
lib_folder = lib_col1.selectbox("Venue / folder", PHOTO_FOLDER_OPTIONS)
lib_uploads = lib_col2.file_uploader(
    "Photos", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="lib_uploader"
)
if st.button("Add to library", icon=":material/upload:", disabled=not lib_uploads):
    n = save_uploaded_photos(lib_folder, lib_uploads)
    st.success(f"Saved {n} photo(s) to assets/venue_photos/{lib_folder}/")
    st.rerun()

library = list_photo_library()
if not library:
    st.caption("No photos in the library yet - builds will use placeholder backgrounds until you add some.")
for folder_name, files in sorted(library.items()):
    with st.expander(f"{folder_name} ({len(files)})"):
        cols = st.columns(4)
        for i, fname in enumerate(files):
            with cols[i % 4]:
                st.image(str(PHOTO_LIBRARY / folder_name / fname), caption=fname, width="stretch")
                if st.button("Remove", icon=":material/delete:", key=f"del_{folder_name}_{fname}"):
                    delete_photo(folder_name, fname)
                    st.rerun()
