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


# ---------------------------------------------------------------- Help

def page_help() -> None:
    st.title("How to use this app")

    st.markdown(
        """
This app is the point-and-click side of the PubCam content agent. It shares one
database with the Claude Code agent (the terminal side), so anything you do here
— approving an idea, scoring a CSV — the agent sees instantly, and vice versa.

**The split:** the app is for checking numbers and making decisions;
the agent (Claude Code opened in this folder) is for thinking work —
planning the week, writing reports, researching trends.
"""
    )

    st.subheader("Your weekly routine")
    st.markdown(
        """
| When | What | Where |
|---|---|---|
| **Friday** | Export the post CSV from Meta Business Suite → drag it into **Score posts** → click Score | This app |
| **Friday** | Ask for `/report` — how the week did vs. strategy | Claude Code |
| **Anytime** | Spotted a good post idea? Log it in **Ideas** (30 seconds) | This app |
| **Monday** | Approve/kill backlog ideas in **Ideas** | This app |
| **Monday** | Run `/plan-week` — the agent proposes the schedule from your approved ideas | Claude Code |
| **Through the week** | Post as scheduled, then **Mark posted** in Schedule | You + this app |
"""
    )

    st.subheader("What each page does")
    with st.expander("Dashboard — how did our content perform?"):
        st.markdown(
            """
- Headline numbers, average score per format, and every scored post ranked.
- Only **pubcam.au** posts get scores. Posts from partner accounts (Heyday,
  Illawarra handles) appear under *Excluded posts* with raw numbers only —
  their insights are limited, so scoring them would be comparing apples to
  oranges.
- Use the rating filter to see just the A+ posts (steal from your own
  winners) or just the Ds (spot what to stop doing).
"""
        )
    with st.expander("Score posts — feed in fresh numbers"):
        st.markdown(
            """
1. In Meta Business Suite: **Insights → Content → Export → CSV** (pick your
   date range).
2. Drag the downloaded file into the upload box.
3. Click **Score newest CSV**. Posts are scored, ranked, and appear on the
   Dashboard immediately.

Re-scoring the same file is safe — posts update in place, no duplicates.
Posts younger than 7 days are held back so scores compare fairly.
"""
        )
    with st.expander("Ideas — the backlog that feeds everything"):
        st.markdown(
            """
- Capture anything worth trying: a format you saw elsewhere, a venue moment
  coming up, a spin on a past winner. More captures = better weeks.
- **Approve** moves an idea into the pool `/plan-week` draws from.
  **Kill** archives it. Nothing gets scheduled without your approval.
- If an idea depends on a price or event detail, write that in the notes —
  it must be fact-checked before the post ships. The agent enforces this.
"""
        )
    with st.expander("Schedule — what's going out and when"):
        st.markdown(
            """
- Shows the week the agent proposed and you confirmed via `/plan-week`.
- After you publish a post on Instagram, use **Mark posted** here so the
  system knows the slot is done.
- Want the team to see it? Ask the agent to `/sync-drive` — it pushes the
  schedule to Google Drive for Jack and Dakota.
"""
        )
    with st.expander("Strategy log — what we believe and why"):
        st.markdown(
            """
- The running record of strategy decisions ("carousels over reels 2:1",
  etc.) with the evidence behind each one.
- Entries **require evidence** — a number, a query, a report finding. The
  form will refuse a hunch. This is what keeps the agent's advice honest.
"""
        )

    st.subheader("What the numbers mean")
    st.markdown(
        """
| Term | Meaning |
|---|---|
| **Weighted score** | Engagement where actions are weighted by value — a share (×5) or new follow (×6) is worth far more than a like (×1) — divided by reach. Measures how hard the post worked *per person who saw it*. |
| **Percentile** | Where the post ranks against all scored PubCam posts. 90 = beat 90% of them. |
| **Rating** | The percentile as a grade: A+ (top 10%), A, B, C, D (bottom 25%). |
| **Excluded** | Partner-account post with limited insights — raw numbers only, never compared against weighted scores. |
"""
    )

    st.subheader("Tricks to get the most out of it")
    st.markdown(
        """
1. **Capture ruthlessly** — every "we could do that" moment goes in Ideas
   immediately, with a note on *why* it caught your eye.
2. **Fresh CSV every Friday** — stale data gives stale advice.
3. **Ask the agent questions the app can't answer** — "what do my A+ posts
   have in common?", "which venue converts followers best?" It can query
   everything behind these pages.
4. **Log strategy shifts** the moment you make them — that's how the system
   learns your thinking instead of just your numbers.
5. **Trust the caveats** — anything marked excluded or placeholder is
   deliberately not comparable. The system never quietly guesses.
"""
    )


# ---------------------------------------------------------------- Shell

PAGES = {
    "Dashboard": page_dashboard,
    "Score posts": page_score,
    "Ideas": page_ideas,
    "Schedule": page_schedule,
    "Strategy log": page_strategy,
    "How to use": page_help,
}

with st.sidebar:
    st.markdown("## 🍻 PubCam Agent")
    choice = st.radio("Go to", list(PAGES), label_visibility="collapsed")
    st.divider()
    st.caption(
        "New here? Start with **How to use** below. Approvals and posting stay "
        "human. For reports, planning and trend research, open Claude Code in "
        "this folder - both use the same database."
    )

PAGES[choice]()
