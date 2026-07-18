import datetime as dt

import streamlit as st

from app_lib import execute, query

rows = query(
    "SELECT schedule.id, schedule.target_date, schedule.slot, schedule.venue,"
    "       ideas.title AS idea, ideas.format, schedule.status"
    " FROM schedule LEFT JOIN ideas ON schedule.idea_id = ideas.id"
    " ORDER BY schedule.target_date"
)
if rows.empty:
    st.info(
        "No schedule yet. Approve some ideas, then run **Plan week** on the Agent "
        "page (or /plan-week in Claude Code) - committing the proposal happens in "
        "Claude Code once you confirm it."
    )
    st.stop()

upcoming = rows[rows["target_date"] >= dt.date.today().isoformat()]
st.subheader("Upcoming")
st.dataframe(upcoming, width="stretch", hide_index=True)

with st.expander("Full schedule history"):
    st.dataframe(rows, width="stretch", hide_index=True)

st.subheader("Mark a slot posted")
open_rows = rows[rows["status"] != "posted"]
if open_rows.empty:
    st.caption("Nothing open.")
    st.stop()
labels = {f"#{r.id} · {r.target_date} · {r.idea}": int(r.id) for r in open_rows.itertuples()}
chosen = st.selectbox("Slot", list(labels))
if st.button("Mark posted", icon=":material/check_circle:"):
    execute("UPDATE schedule SET status = 'posted' WHERE id = ?", (labels[chosen],))
    st.rerun()
