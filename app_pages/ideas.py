import streamlit as st

from app_lib import BRIEF_PROMPT, FORMAT_OPTIONS, VENUE_OPTIONS, execute, query, run_agent_action

with st.form("add_idea", clear_on_submit=True):
    st.subheader("Capture a new idea")
    title = st.text_input("Title (short and specific)")
    col1, col2 = st.columns(2)
    venue_fit = col1.selectbox("Venue fit", VENUE_OPTIONS)
    fmt = col2.selectbox("Format", FORMAT_OPTIONS)
    notes = st.text_area(
        "Notes - source link, why it's worth doing, and any fact that needs "
        "checking before this could ship (prices/event details need a source)"
    )
    if st.form_submit_button("Add to backlog") and title.strip():
        execute(
            "INSERT INTO ideas (title, source, venue_fit, format, status, notes)"
            " VALUES (?, 'capture', ?, ?, 'backlog', ?)",
            (title.strip(), venue_fit, fmt, notes.strip()),
        )
        st.success(f"Logged: {title.strip()}")

st.subheader("Waiting for a decision (backlog)")
backlog = query("SELECT * FROM ideas WHERE status = 'backlog' ORDER BY id")
if backlog.empty:
    st.caption("Backlog is empty.")
for _, idea in backlog.iterrows():
    with st.container(border=True):
        info, approve_col, kill_col = st.columns([6, 1, 1])
        info.markdown(f"**#{idea['id']} - {idea['title']}**")
        info.caption(f"{idea['format']} · {idea['venue_fit']} · {idea['notes'] or 'no notes'}")
        if approve_col.button("Approve", key=f"ap{idea['id']}", type="primary"):
            execute("UPDATE ideas SET status = 'approved' WHERE id = ?", (int(idea["id"]),))
            has_brief = query(
                "SELECT COUNT(*) AS n FROM briefs WHERE idea_id = ?", (int(idea["id"]),)
            )["n"][0]
            if has_brief:
                st.success("Approved - this idea already has its brief (see below).")
            else:
                st.toast(f"Approved #{idea['id']} - building the production brief now...")
                run_agent_action(
                    f"Production brief for idea #{idea['id']}",
                    BRIEF_PROMPT.format(id=idea["id"]),
                )
                st.success("Brief saved - it lives under this idea in 'Approved & developed' below.")
        if kill_col.button("Kill", key=f"ki{idea['id']}"):
            execute("UPDATE ideas SET status = 'killed' WHERE id = ?", (int(idea["id"]),))
            st.rerun()

st.subheader("Approved & developed")
developed = query(
    "SELECT ideas.id, ideas.title, ideas.status, ideas.format, ideas.venue_fit,"
    "       briefs.content, briefs.created_at AS brief_date"
    " FROM ideas LEFT JOIN briefs ON briefs.idea_id = ideas.id"
    " WHERE ideas.status IN ('approved', 'scheduled', 'posted')"
    " ORDER BY ideas.id DESC"
)
if developed.empty:
    st.caption("Nothing approved yet - approve a backlog idea and its brief builds itself.")
for _, row in developed.iterrows():
    label = f"#{row['id']} · {row['title']} · {row['format']} · {row['status']}"
    with st.expander(label):
        if row["content"]:
            st.markdown(row["content"])
        else:
            st.caption("No brief yet for this idea.")
            if st.button("Build brief", key=f"brief{row['id']}", icon=":material/construction:"):
                run_agent_action(
                    f"Production brief for idea #{row['id']}",
                    BRIEF_PROMPT.format(id=row["id"]),
                )
                st.rerun()

with st.expander("Killed ideas"):
    killed = query("SELECT id, title, format, venue_fit, source, created_at"
                   " FROM ideas WHERE status = 'killed' ORDER BY id DESC")
    st.dataframe(killed, width="stretch", hide_index=True)
