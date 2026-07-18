import streamlit as st

from app_lib import execute, query

st.caption(
    "The running record of what PubCam believes and why. Entries need evidence - "
    "a number, a query result, a report finding - not a hunch."
)

with st.form("add_strategy", clear_on_submit=True):
    insight = st.text_input("Insight - what was observed")
    decision = st.text_input("Decision - what changes as a result")
    evidence = st.text_input("Evidence - the specific numbers behind it")
    if st.form_submit_button("Log it") and insight.strip():
        if not evidence.strip():
            st.error("Evidence is required - CLAUDE.md Section 5 applies to strategy claims too.")
        else:
            execute(
                "INSERT INTO strategy_log (insight, decision, evidence) VALUES (?, ?, ?)",
                (insight.strip(), decision.strip(), evidence.strip()),
            )
            st.success("Logged.")

log = query("SELECT date, insight, decision, evidence FROM strategy_log ORDER BY id DESC")
if log.empty:
    st.caption("No entries yet.")
else:
    st.dataframe(log, width="stretch", hide_index=True)
