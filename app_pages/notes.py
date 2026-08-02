import streamlit as st

from app_lib import all_note_tags, delete_note, get_note, list_notes, save_note

st.write(
    "Freeform knowledge base - venue info, old Notion pages, half-formed "
    "ideas, whatever's useful to remember."
)
st.caption(
    "The agent reads every note here as real context (CLAUDE.md), same "
    "trust level as the Google Drive sheets it already checks. Nothing "
    "here is auto-generated - it's exactly what you write."
)

if "notes_editing" not in st.session_state:
    st.session_state.notes_editing = None  # None = grid; "" = new note; a filename = editing that note

editing = st.session_state.notes_editing

if editing is not None:
    is_new = editing == ""
    note = {"title": "", "tags": [], "body": ""} if is_new else get_note(editing)
    if note is None:
        st.error("That note no longer exists.")
        st.session_state.notes_editing = None
        st.rerun()

    if st.button("Back to notes", icon=":material/arrow_back:"):
        st.session_state.notes_editing = None
        st.rerun()

    title = st.text_input("Title", value=note["title"], placeholder="e.g. The Icon - contact notes")
    tags_str = st.text_input(
        "Tags (comma-separated, optional)", value=", ".join(note["tags"]), placeholder="e.g. venue, icon"
    )
    body = st.text_area("Note", value=note["body"], height=420, placeholder="Write anything...")

    col1, col2 = st.columns([1, 1])
    if col1.button("Save", type="primary", icon=":material/save:", disabled=not title.strip()):
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        fname = None if is_new else editing
        save_note(fname, title.strip(), tags, body)
        st.session_state.notes_editing = None
        st.toast(f"Saved '{title.strip()}'")
        st.rerun()
    if not is_new and col2.button("Delete", icon=":material/delete:"):
        delete_note(editing)
        st.session_state.notes_editing = None
        st.rerun()

else:
    if st.button("New note", type="primary", icon=":material/add:"):
        st.session_state.notes_editing = ""
        st.rerun()

    search = st.text_input(
        "Search", placeholder="Search notes...", label_visibility="collapsed", key="notes_search"
    )
    tags = all_note_tags()
    tag_filter = st.pills("Filter by tag", tags, selection_mode="single") if tags else None

    notes = list_notes(query_text=search, tag=tag_filter)
    if not notes:
        st.caption(
            "No notes yet - hit 'New note' to start, or drop markdown files "
            "straight into ops/notes/ and they'll show up here."
        )

    cols = st.columns(3)
    for i, n in enumerate(notes):
        with cols[i % 3], st.container(border=True):
            st.markdown(f"**{n['title']}**")
            if n["tags"]:
                st.caption(" · ".join(n["tags"]))
            preview = n["body"][:140].replace("\n", " ").strip()
            st.caption(preview + ("..." if len(n["body"]) > 140 else "") or "_empty_")
            st.caption(n["updated_at"].strftime("Edited %d %b %Y"))
            if st.button("Open", key=f"open_{n['filename']}", icon=":material/edit:"):
                st.session_state.notes_editing = n["filename"]
                st.rerun()
