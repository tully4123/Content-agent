import streamlit as st

from app_lib import execute, query

st.caption(
    "Raw material from trend sweeps - content formats spotted in the wild, each "
    "with the source it came from. *Generate ideas* (Agent page) turns open "
    "trends into concrete post concepts and marks them acted-on."
)

trends = query("SELECT * FROM trends ORDER BY acted_on, id DESC")
if trends.empty:
    st.info("Nothing here yet - press **Run trend sweep** on the Agent page.")
    st.stop()

open_n = int((trends["acted_on"] == 0).sum())
st.markdown(f":blue-badge[{open_n} open] :green-badge[{len(trends) - open_n} acted on]")

for _, t in trends.iterrows():
    with st.container(border=True):
        head, action_col = st.columns([5, 1])
        with head:
            title = str(t["description"]).split(":")[0].strip("'\" ")
            badge = ":green-badge[acted on]" if t["acted_on"] else ":blue-badge[open]"
            st.markdown(f"**{title}**  {badge}  ·  {t['platform']}  ·  spotted {t['date_spotted']}")
            st.write(t["description"])
            st.markdown(f":material/lightbulb: *Why it fits PubCam:* {t['relevance_note']}")
            if t["source_url"]:
                st.markdown(f":material/link: [Source]({t['source_url']})")
        with action_col:
            if not t["acted_on"] and st.button("Mark acted", key=f"trend{t['id']}"):
                execute("UPDATE trends SET acted_on = 1 WHERE id = ?", (int(t["id"]),))
                st.rerun()
