import streamlit as st

from app_lib import SMEATON_PATH, render_quality_toggle, run_agent_chat

st.caption(
    "Talk to the agent right here - it knows your posts, ideas, trends, and "
    "schedule, and can write to them. Ask about PubCam's posting style and "
    "it'll ground the answer in real top-performing captions, not a guess. "
    "Replies take 30s-3min depending on how much digging the question needs."
)
render_quality_toggle()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

if not st.session_state.chat_messages:
    with st.container(horizontal=True):
        st.markdown("**Try:**")
        for suggestion in [
            "Generate 3 post ideas for this week",
            "What should I post on Wednesday?",
            "Which format is winning right now?",
            "Suggest a caption in PubCam's own style",
        ]:
            if st.button(suggestion, key=f"sug_{suggestion[:20]}"):
                st.session_state.chat_seed = suggestion
                st.rerun()

for msg in st.session_state.chat_messages:
    avatar = str(SMEATON_PATH) if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask about your content, or tell it what to do...", submit_mode="disable")
if not prompt and "chat_seed" in st.session_state:
    prompt = st.session_state.pop("chat_seed")

if prompt:
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=str(SMEATON_PATH)):
        with st.spinner("Smeaton's thinking (this can take a couple of minutes)..."):
            wrapped = (
                f"{prompt}\n\n"
                "(Context: you are answering inside the PubCam app chat. Be concise and "
                "conversational. If asked for post ideas, use the idea-generator skill's "
                "approach and save them to the backlog with scripts/db.py add-idea, then "
                "list what you saved. Never approve ideas or commit schedules - suggest "
                "the user does that on the Ideas page. Never invent prices or event "
                "details - flag them as needing a check. If the question touches PubCam's "
                "voice, tone, or a caption, run `python scripts/db.py voice-sample` first - "
                "it returns full real captions from top-scoring posts, not the clipped "
                "versions in digest - and ground your answer in those actual patterns "
                "(opening line, emoji use, sign-off, hashtags) rather than guessing at a "
                "voice; CLAUDE.md Section 2 has more on this. Don't just answer what was "
                "literally asked - where a concrete next move is obvious from the data "
                "[a specific idea worth trying, a format that's underused, a post that's "
                "overdue], say so.)"
            )
            reply, session_id = run_agent_chat(wrapped, st.session_state.chat_session)
            st.session_state.chat_session = session_id
        st.markdown(reply)
    st.session_state.chat_messages.append({"role": "assistant", "content": reply})

if st.session_state.chat_messages:
    if st.button("New conversation", icon=":material/restart_alt:"):
        st.session_state.chat_messages = []
        st.session_state.chat_session = None
        st.rerun()
