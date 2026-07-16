"""
PubCam Content Agent - local app interface.

Streamlit front-end over the same db/pubcam.db the Claude Code agent uses.
Launch with "PubCam Agent.bat" or: python -m streamlit run app.py

The app is the dashboard/approval layer; strategy work (reports, planning
conversations, trend research) stays with the agent in Claude Code. Both sides
read and write the same database, so nothing gets out of sync.
"""
import datetime as dt
import sqlite3
import subprocess
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).parent
DB_PATH = REPO_ROOT / "db" / "pubcam.db"
INBOX_DIR = REPO_ROOT / "inbox"
SCORE_SCRIPT = REPO_ROOT / "scripts" / "score_posts.py"

# Categorical slots from the validated reference palette (dataviz skill),
# assigned in fixed order; light-mode steps. Magenta is sub-3:1 on light
# surfaces, so bars carry direct value labels (relief rule).
FORMAT_COLORS = {
    "carousel": "#2a78d6",
    "reel": "#008300",
    "photo": "#e87ba4",
    "collab": "#eda100",
}
INK_SECONDARY = "#52514e"

VENUE_OPTIONS = ["PubCam original", "Heyday", "Illawarra", "The Icon", "multi-venue", "unclear"]
FORMAT_OPTIONS = ["reel", "carousel", "photo", "collab"]

st.set_page_config(page_title="PubCam Content Agent", page_icon="🍻", layout="wide")


def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- Dashboard

def page_dashboard() -> None:
    st.title("Dashboard")

    scored = query(
        "SELECT post_id, venue, format, caption, posted_at, reach, likes, comments,"
        "       saves, shares, follows, weighted_score, percentile, rating"
        " FROM posts WHERE scoring_excluded = 0 AND weighted_score IS NOT NULL"
    )
    excluded_n = query("SELECT COUNT(*) AS n FROM posts WHERE scoring_excluded = 1")["n"][0]

    if scored.empty:
        st.info("No scored posts yet. Go to **Score posts** and load a Meta Business Suite CSV.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scored posts", len(scored))
    c2.metric("Average score", f"{scored['weighted_score'].mean():.1f}")
    best = scored.loc[scored["weighted_score"].idxmax()]
    c3.metric("Best score", f"{best['weighted_score']:.1f}", help=str(best["caption"])[:120])
    c4.metric("A-grade posts (A/A+)", int(scored["rating"].isin(["A", "A+"]).sum()))

    st.caption(
        f"pubcam.au posts only - {excluded_n} partner-account posts are excluded from scoring "
        "(limited insights; their Reach/Saves aren't comparable). See CLAUDE.md Section 4."
    )

    st.subheader("Average score by format")
    by_format = (
        scored.groupby("format", as_index=False)
        .agg(avg_score=("weighted_score", "mean"), posts=("post_id", "count"))
    )
    by_format["avg_score"] = by_format["avg_score"].round(1)
    by_format["label"] = by_format.apply(lambda r: f"{r.avg_score}  ({r.posts} posts)", axis=1)

    domain = [f for f in FORMAT_COLORS if f in set(by_format["format"])]
    bars = (
        alt.Chart(by_format)
        .mark_bar(cornerRadiusEnd=4, height=26)
        .encode(
            x=alt.X("avg_score:Q", title="Average weighted score", axis=alt.Axis(grid=True)),
            y=alt.Y("format:N", title=None, sort="-x"),
            color=alt.Color(
                "format:N",
                scale=alt.Scale(domain=domain, range=[FORMAT_COLORS[f] for f in domain]),
                legend=None,  # single dimension, direct-labeled - the axis names each bar
            ),
            tooltip=["format", "avg_score", "posts"],
        )
    )
    labels = (
        alt.Chart(by_format)
        .mark_text(align="left", dx=6, color=INK_SECONDARY)
        .encode(x="avg_score:Q", y=alt.Y("format:N", sort="-x"), text="label:N")
    )
    st.altair_chart((bars + labels).properties(height=40 * len(by_format) + 40), width="stretch")

    st.subheader("All scored posts")
    ratings = ["A+", "A", "B", "C", "D"]
    pick = st.multiselect("Filter by rating", ratings, default=ratings)
    table = scored[scored["rating"].isin(pick)].sort_values("weighted_score", ascending=False)
    table = table[["rating", "format", "venue", "caption", "posted_at", "reach",
                   "saves", "shares", "follows", "weighted_score", "percentile"]]
    st.dataframe(table, width="stretch", hide_index=True)

    with st.expander(f"Excluded posts ({excluded_n}) - partner accounts, raw numbers only"):
        ex = query(
            "SELECT account, venue, format, caption, posted_at, views, likes, comments, shares"
            " FROM posts WHERE scoring_excluded = 1 ORDER BY posted_at DESC"
        )
        st.dataframe(ex, width="stretch", hide_index=True)
        st.caption("Never compare these raw numbers against weighted scores - different measurement basis.")


# ---------------------------------------------------------------- Score posts

def page_score() -> None:
    st.title("Score posts")
    st.write(
        "Export the post-performance CSV from Meta Business Suite "
        "(Insights → Content → Export), upload it here, then score it."
    )

    uploaded = st.file_uploader("Drop the Meta Business Suite CSV here", type="csv")
    if uploaded is not None:
        dest = INBOX_DIR / uploaded.name
        dest.write_bytes(uploaded.getvalue())
        st.success(f"Saved to inbox/{uploaded.name}")

    csvs = sorted(INBOX_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not csvs:
        st.info("No CSVs in inbox/ yet.")
        return

    newest = csvs[0]
    st.write(f"Newest file in inbox: **{newest.name}**")
    if st.button("Score newest CSV", type="primary"):
        result = subprocess.run(
            [sys.executable, str(SCORE_SCRIPT)],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )
        if result.returncode == 0:
            st.success("Scoring complete.")
        else:
            st.error("Scoring failed - output below.")
        st.code(result.stdout + result.stderr)


# ---------------------------------------------------------------- Ideas

def page_ideas() -> None:
    st.title("Ideas backlog")

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

    st.divider()
    st.subheader("Waiting for a decision (backlog)")
    backlog = query("SELECT * FROM ideas WHERE status = 'backlog' ORDER BY id")
    if backlog.empty:
        st.caption("Backlog is empty.")
    for _, idea in backlog.iterrows():
        with st.container(border=True):
            info, approve_col, kill_col = st.columns([6, 1, 1])
            info.markdown(f"**#{idea['id']} - {idea['title']}**")
            info.caption(f"{idea['format']} · {idea['venue_fit']} · {idea['notes'] or 'no notes'}")
            if approve_col.button("Approve", key=f"ap{idea['id']}"):
                execute("UPDATE ideas SET status = 'approved' WHERE id = ?", (int(idea["id"]),))
                st.rerun()
            if kill_col.button("Kill", key=f"ki{idea['id']}"):
                execute("UPDATE ideas SET status = 'killed' WHERE id = ?", (int(idea["id"]),))
                st.rerun()

    st.subheader("Everything else")
    other = query("SELECT id, title, status, format, venue_fit, source, created_at"
                  " FROM ideas WHERE status != 'backlog' ORDER BY id DESC")
    st.dataframe(other, width="stretch", hide_index=True)


# ---------------------------------------------------------------- Schedule

def page_schedule() -> None:
    st.title("Schedule")
    rows = query(
        "SELECT schedule.id, schedule.target_date, schedule.slot, schedule.venue,"
        "       ideas.title AS idea, ideas.format, schedule.status"
        " FROM schedule LEFT JOIN ideas ON schedule.idea_id = ideas.id"
        " ORDER BY schedule.target_date"
    )
    if rows.empty:
        st.info(
            "No schedule yet. Approve some ideas here, then run **/plan-week** in "
            "Claude Code - the agent proposes the week and commits it to this same "
            "database once you confirm."
        )
        return

    upcoming = rows[rows["target_date"] >= dt.date.today().isoformat()]
    st.subheader("Upcoming")
    st.dataframe(upcoming, width="stretch", hide_index=True)

    with st.expander("Full schedule history"):
        st.dataframe(rows, width="stretch", hide_index=True)

    st.subheader("Mark a slot posted")
    open_rows = rows[rows["status"] != "posted"]
    if open_rows.empty:
        st.caption("Nothing open.")
        return
    labels = {f"#{r.id} · {r.target_date} · {r.idea}": int(r.id) for r in open_rows.itertuples()}
    chosen = st.selectbox("Slot", list(labels))
    if st.button("Mark posted"):
        execute("UPDATE schedule SET status = 'posted' WHERE id = ?", (labels[chosen],))
        st.rerun()


# ---------------------------------------------------------------- Strategy

def page_strategy() -> None:
    st.title("Strategy log")
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


# ---------------------------------------------------------------- Shell

PAGES = {
    "Dashboard": page_dashboard,
    "Score posts": page_score,
    "Ideas": page_ideas,
    "Schedule": page_schedule,
    "Strategy log": page_strategy,
}

with st.sidebar:
    st.markdown("## 🍻 PubCam Agent")
    choice = st.radio("Go to", list(PAGES), label_visibility="collapsed")
    st.divider()
    st.caption(
        "Approvals and posting stay human. For reports, planning and trend "
        "research, open Claude Code in this folder - both use the same database."
    )

PAGES[choice]()
