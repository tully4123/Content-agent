import datetime as dt

import streamlit as st

from app_lib import query, render_hero

today = dt.date.today()
hour = dt.datetime.now().hour
greeting = "Morning" if hour < 12 else ("Afternoon" if hour < 18 else "Evening")
render_hero("PubCam HQ", f"{greeting} · {today.strftime('%A %d %B %Y')}")
st.write("")

# ---- pulse row
scored = query(
    "SELECT weighted_score, posted_at FROM posts"
    " WHERE scoring_excluded = 0 AND weighted_score IS NOT NULL ORDER BY posted_at"
)
backlog_n = int(query("SELECT COUNT(*) AS n FROM ideas WHERE status = 'backlog'")["n"][0])
unbriefed = query(
    "SELECT COUNT(*) AS n FROM ideas WHERE status IN ('approved', 'scheduled')"
    " AND id NOT IN (SELECT idea_id FROM briefs)"
)["n"][0]
open_trends = query("SELECT COUNT(*) AS n FROM trends WHERE acted_on = 0")["n"][0]

with st.container(horizontal=True):
    if len(scored) >= 10:
        recent = scored["weighted_score"].tail(5).mean()
        earlier = scored["weighted_score"].iloc[:-5].mean()
        st.metric("Last 5 posts avg", f"{recent:.0f}", delta=f"{recent - earlier:+.0f} vs before",
                  border=True, chart_data=scored["weighted_score"].tail(10).tolist(), chart_type="line")
    st.metric("Ideas needing a decision", backlog_n, border=True)
    st.metric("Approved, no brief yet", int(unbriefed), border=True)
    st.metric("Open trends", int(open_trends), border=True)

# ---- needs you
left, right = st.columns(2)

with left, st.container(border=True):
    st.markdown("**:material/pending_actions: Needs you**")
    nothing = True
    if backlog_n:
        st.markdown(f"- **{backlog_n} idea(s)** waiting for approve/kill")
        st.page_link("app_pages/ideas.py", label="Decide now", icon=":material/arrow_forward:")
        nothing = False
    proposed = query("SELECT COUNT(*) AS n FROM schedule WHERE status = 'proposed'")["n"][0]
    if proposed:
        st.markdown(f"- **{int(proposed)} proposed schedule slot(s)** to confirm or adjust")
        st.page_link("app_pages/schedule.py", label="Review schedule", icon=":material/arrow_forward:")
        nothing = False
    stale = query(
        "SELECT COUNT(*) AS n FROM trends WHERE acted_on = 0 AND date_spotted <= date('now', '-21 days')"
    )["n"][0]
    if stale:
        st.markdown(f"- **{int(stale)} trend(s)** older than 3 weeks - use or retire them")
        st.page_link("app_pages/trends.py", label="Tidy trends", icon=":material/arrow_forward:")
        nothing = False
    if nothing:
        st.caption("All clear. Sweep for trends or generate ideas to keep the pipeline fed.")
        st.page_link("app_pages/agent.py", label="Run something", icon=":material/smart_toy:")

with right, st.container(border=True):
    st.markdown("**:material/local_fire_department: Hot right now**")
    hot = query(
        "SELECT id, description, relevance_note FROM trends WHERE acted_on = 0 ORDER BY id DESC LIMIT 3"
    )
    if hot.empty:
        st.caption("No open trends - run a trend sweep from the Agent page.")
    for _, t in hot.iterrows():
        title = str(t["description"]).split(":")[0].strip("'\" ")
        st.markdown(f"- **{title}** - {str(t['relevance_note'])[:100]}...")
    st.page_link("app_pages/trends.py", label="All trends", icon=":material/arrow_forward:")

# ---- this week
with st.container(border=True):
    st.markdown("**:material/event_upcoming: Going out this week**")
    week_end = (today + dt.timedelta(days=7)).isoformat()
    upcoming = query(
        "SELECT schedule.target_date, schedule.slot, ideas.title, ideas.format, schedule.status,"
        "       (SELECT COUNT(*) FROM briefs WHERE briefs.idea_id = ideas.id) AS has_brief"
        " FROM schedule JOIN ideas ON schedule.idea_id = ideas.id"
        " WHERE schedule.target_date BETWEEN ? AND ? AND schedule.status != 'posted'"
        " ORDER BY schedule.target_date",
        (today.isoformat(), week_end),
    )
    if upcoming.empty:
        st.caption("Nothing scheduled in the next 7 days. Approve some ideas, then run Plan week.")
        st.page_link("app_pages/agent.py", label="Plan the week", icon=":material/calendar_month:")
    for _, s in upcoming.iterrows():
        brief_note = ":green-badge[brief ready]" if s["has_brief"] else ":orange-badge[no brief]"
        st.markdown(f"- **{s['target_date']}** {s['slot'] or ''} - {s['title']} ({s['format']}) {brief_note}")
    if not upcoming.empty:
        st.page_link("app_pages/ideas.py", label="Open the briefs", icon=":material/description:")

st.caption(
    "The ritual: clear 'Needs you', check what's hot, open the brief for whatever "
    "posts today - then go make it. Instagram is the last stop, not the first."
)
