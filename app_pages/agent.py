import streamlit as st

from app_lib import AGENT_ACTIONS, render_quality_toggle, run_agent_action

st.write(
    "One-click agent runs - the same workflows you'd trigger by talking to "
    "Claude Code, powered by the same brain (CLAUDE.md + skills)."
)
st.caption(
    "Runs use your Claude subscription and take a few minutes each. One at a "
    "time. Anything needing a decision (approving ideas, committing a "
    "schedule) still comes back to you - buttons never approve or publish."
)
render_quality_toggle()

for name, action in AGENT_ACTIONS.items():
    with st.container(border=True):
        st.markdown(f"**{name}**")
        st.caption(action["desc"])
        if st.button(f"Run {name.lower()}", icon=action["icon"], key=f"agent_{name}"):
            run_agent_action(name, action["prompt"])
