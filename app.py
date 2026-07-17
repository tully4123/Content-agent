"""
PubCam Content Agent - local app interface.

Streamlit front-end over the same db/pubcam.db the Claude Code agent uses.
Launch with "PubCam Agent.bat" or: python -m streamlit run app.py

The app is the dashboard/approval layer; strategy work (reports, planning
conversations, trend research) stays with the agent in Claude Code. Both sides
read and write the same database, so nothing gets out of sync.
"""
import datetime as dt
import json
import shutil
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

def compute_insights(scored: pd.DataFrame) -> list[str]:
    """Data-derived observations, honest about sample sizes. No invented claims."""
    insights = []
    df = scored.copy()
    df["posted_dt"] = pd.to_datetime(df["posted_at"], errors="coerce")
    df = df.sort_values("posted_dt")

    fmt = df.groupby("format")["weighted_score"].agg(["mean", "count"])
    if len(fmt) > 1:
        top = fmt["mean"].idxmax()
        ratio = fmt["mean"].max() / fmt["mean"].drop(top).max()
        insights.append(
            f"**{top.capitalize()}s lead**: avg score {fmt['mean'].max():.0f} vs "
            f"{fmt['mean'].drop(top).max():.0f} for the next format ({ratio:.1f}x) - "
            f"across {int(fmt['count'][top])} {top}s."
        )

    df["save_rate"] = df["saves"] / df["reach"] * 100
    top_saver = df.loc[df["save_rate"].idxmax()]
    insights.append(
        f"**Most saved**: \"{str(top_saver['caption'])[:60]}...\" - "
        f"{top_saver['save_rate']:.1f}% of reached accounts saved it. Save-heavy guides "
        "are your DM-share engine."
    )

    if len(df) >= 10:
        recent = df.tail(5)["weighted_score"].mean()
        earlier = df.iloc[:-5]["weighted_score"].mean()
        direction = "up" if recent > earlier else "down"
        insights.append(
            f"**Momentum {direction}**: last 5 posts average {recent:.0f} vs {earlier:.0f} "
            f"for everything before - {'keep doing what changed' if direction == 'up' else 'worth a look at what changed'}."
        )

    followers = df.loc[df["follows"].idxmax()]
    insights.append(
        f"**Best follower converter**: \"{str(followers['caption'])[:60]}...\" "
        f"brought {int(followers['follows'])} new follows from {int(followers['reach']):,} reach."
    )
    return insights


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

    scored["posted_dt"] = pd.to_datetime(scored["posted_at"], errors="coerce")
    chrono = scored.sort_values("posted_dt")
    score_series = chrono["weighted_score"].round(1).tolist()
    reach_series = chrono["reach"].tolist()

    with st.container(horizontal=True):
        st.metric("Scored posts", len(scored), border=True)
        st.metric("Average score", f"{scored['weighted_score'].mean():.1f}", border=True,
                  chart_data=score_series, chart_type="line")
        best = scored.loc[scored["weighted_score"].idxmax()]
        st.metric("Best score", f"{best['weighted_score']:.1f}", border=True,
                  help=str(best["caption"])[:120])
        st.metric("A-grade posts", int(scored["rating"].isin(["A", "A+"]).sum()), border=True)
        st.metric("Total reach", f"{int(scored['reach'].sum()):,}", border=True,
                  chart_data=reach_series, chart_type="bar")

    st.caption(
        f"pubcam.au posts only - {excluded_n} partner-account posts are excluded from scoring "
        "(limited insights; their Reach/Saves aren't comparable). See CLAUDE.md Section 4."
    )

    st.subheader("Score over time")
    pick_formats = st.pills(
        "Formats", sorted(scored["format"].unique()),
        default=sorted(scored["format"].unique()), selection_mode="multi",
        label_visibility="collapsed",
    )
    ts = chrono[chrono["format"].isin(pick_formats or [])].copy()
    if ts.empty:
        st.caption("Pick at least one format.")
    else:
        ts["rolling"] = ts["weighted_score"].rolling(5, min_periods=1).mean()
        ts["caption_short"] = ts["caption"].astype(str).str.slice(0, 70)
        domain_ts = [f for f in FORMAT_COLORS if f in set(ts["format"])]
        points = (
            alt.Chart(ts)
            .mark_circle(size=90)
            .encode(
                x=alt.X("posted_dt:T", title=None),
                y=alt.Y("weighted_score:Q", title="Weighted score"),
                color=alt.Color(
                    "format:N", title="Format",
                    scale=alt.Scale(domain=domain_ts, range=[FORMAT_COLORS[f] for f in domain_ts]),
                ),
                tooltip=[
                    alt.Tooltip("posted_dt:T", title="Posted"),
                    alt.Tooltip("caption_short:N", title="Caption"),
                    alt.Tooltip("format:N", title="Format"),
                    alt.Tooltip("weighted_score:Q", title="Score", format=".1f"),
                    alt.Tooltip("rating:N", title="Rating"),
                    alt.Tooltip("reach:Q", title="Reach", format=","),
                    alt.Tooltip("saves:Q", title="Saves"),
                    alt.Tooltip("shares:Q", title="Shares"),
                ],
            )
        )
        trend = (
            alt.Chart(ts)
            .mark_line(strokeWidth=2, color=INK_SECONDARY, strokeDash=[6, 3])
            .encode(x="posted_dt:T", y="rolling:Q",
                    tooltip=[alt.Tooltip("rolling:Q", title="5-post rolling avg", format=".1f")])
        )
        st.altair_chart((points + trend).properties(height=320).interactive(), width="stretch")
        st.caption("Dots = individual posts (hover for detail). Dashed line = 5-post rolling average - the trend line.")

    left, right = st.columns(2)
    with left, st.container(border=True):
        st.markdown("**:material/insights: What the data says**")
        for line in compute_insights(scored):
            st.markdown(f"- {line}")
        st.caption(f"Computed live from your {len(scored)} scored posts - small sample, treat as signals not laws.")

    with right, st.container(border=True):
        st.markdown("**:material/tips_and_updates: Tips right now**")
        open_trends = query("SELECT description FROM trends WHERE acted_on = 0 ORDER BY id DESC LIMIT 3")
        if not open_trends.empty:
            st.markdown("- **Open trends waiting**: " + "; ".join(
                d.split(":")[0].strip("'\" ") for d in open_trends["description"]
            ) + " - press *Generate ideas* on the Agent page to turn them into posts.")
        backlog_n = query("SELECT COUNT(*) AS n FROM ideas WHERE status = 'backlog'")["n"][0]
        if backlog_n:
            st.markdown(f"- **{backlog_n} idea(s) in the backlog** need an approve/kill decision on the Ideas page.")
        st.markdown("- **Working theory** (from CLAUDE.md, verify with more data): multi-venue guide "
                    "carousels outperform single-venue promo; save-optimised posts travel via DMs.")
        st.markdown("- **Friday habit**: fresh CSV in, score, then check this page's trend line.")

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


# ---------------------------------------------------------------- Trends

def page_trends() -> None:
    st.title("Trends")
    st.caption(
        "Raw material from trend sweeps - content formats spotted in the wild, each "
        "with the source it came from. *Generate ideas* (Agent page) turns open "
        "trends into concrete post concepts and marks them acted-on."
    )

    trends = query("SELECT * FROM trends ORDER BY acted_on, id DESC")
    if trends.empty:
        st.info("Nothing here yet - press **Run trend sweep** on the Agent page.")
        return

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


# ---------------------------------------------------------------- Agent

AGENT_TOOLS = "Read,Glob,Grep,Edit,Write,Bash,WebSearch,WebFetch"

AGENT_ACTIONS = {
    "Trend sweep": {
        "icon": ":material/travel_explore:",
        "desc": "Research the web for content trends PubCam could use; log the best to the trends table.",
        "prompt": (
            "Run the trend-sweep skill end to end, non-interactively (never ask questions). "
            "Log keepers with scripts/db.py add-trend. Finish with a plain-language summary of "
            "what you logged, what you rejected and why, and anything time-sensitive."
        ),
    },
    "Generate ideas": {
        "icon": ":material/lightbulb:",
        "desc": "Turn top/bottom posts + open trends + the calendar into concrete post ideas in the backlog.",
        "prompt": (
            "Run the idea-generator skill end to end, non-interactively (never ask questions). "
            "Write ideas to the backlog with scripts/db.py add-idea. Finish with the batch grouped "
            "by venue, hooks first, and remind that ideas need approval on the Ideas page."
        ),
    },
    "Weekly report": {
        "icon": ":material/assessment:",
        "desc": "Performance summary vs. strategy, written to reports/.",
        "prompt": (
            "Run the /report workflow non-interactively (never ask questions). Write the report to "
            "reports/ with today's date. Propose any CLAUDE.md Section 3 changes in the output text "
            "only - do not edit CLAUDE.md. Finish by printing the report's headline findings."
        ),
    },
    "Plan week (dry run)": {
        "icon": ":material/calendar_month:",
        "desc": "Propose next week's schedule from approved ideas. Proposal only - committing stays in Claude Code.",
        "prompt": (
            "Run scripts/build_schedule.py as a dry run for the next week (do NOT use --commit under "
            "any circumstances). Present the proposed schedule and any caveats. If there are no "
            "approved ideas, say so and list the backlog instead."
        ),
    },
}


def run_agent_action(name: str, prompt: str) -> None:
    claude = shutil.which("claude")
    if not claude:
        st.error("Claude Code CLI not found on PATH. Install with: npm install -g @anthropic-ai/claude-code")
        return

    cmd = [
        claude, "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--allowedTools", AGENT_TOOLS,
    ]
    final_text: list[str] = []
    with st.status(f"Running {name}... (usually 2-5 minutes, leave this tab open)", expanded=True) as status:
        progress = st.empty()
        proc = subprocess.Popen(
            cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
        )
        activity: list[str] = []
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "assistant":
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "tool_use":
                        activity.append(f"using {block.get('name', 'tool')}...")
                    elif block.get("type") == "text" and block.get("text", "").strip():
                        final_text.append(block["text"])
                        activity.append(block["text"][:120].replace("\n", " ") + "...")
                progress.caption(activity[-1] if activity else "working...")
            elif event.get("type") == "result":
                if event.get("subtype") != "success":
                    final_text.append(f"\n[Run ended with: {event.get('subtype')}]")
        rc = proc.wait()
        status.update(
            label=f"{name} {'finished' if rc == 0 else 'FAILED'}",
            state="complete" if rc == 0 else "error", expanded=False,
        )
    if final_text:
        st.markdown(final_text[-1])
        with st.expander("Full agent output"):
            st.markdown("\n\n---\n\n".join(final_text))
    elif rc != 0:
        st.error("The agent run failed with no output. Try again, or run this from Claude Code directly.")


def page_agent() -> None:
    st.title("Agent")
    st.write(
        "One-click agent runs - the same workflows you'd trigger by talking to "
        "Claude Code, powered by the same brain (CLAUDE.md + skills)."
    )
    st.caption(
        "Runs use your Claude subscription and take a few minutes each. One at a "
        "time. Anything needing a decision (approving ideas, committing a "
        "schedule) still comes back to you - buttons never approve or publish."
    )

    for name, action in AGENT_ACTIONS.items():
        with st.container(border=True):
            st.markdown(f"**{name}**")
            st.caption(action["desc"])
            if st.button(f"Run {name.lower()}", icon=action["icon"], key=f"agent_{name}"):
                run_agent_action(name, action["prompt"])


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
    with st.expander("Trends — what's working out in the wild"):
        st.markdown(
            """
- Every trend a sweep finds lands here with its source link and a note on
  why it fits PubCam.
- **Open** trends are waiting to be used; *Generate ideas* consumes them
  and flips them to **acted on**. You can also mark one acted manually.
"""
        )
    with st.expander("Agent — one-click agent runs"):
        st.markdown(
            """
- Buttons for the agent workflows: **trend sweep**, **generate ideas**,
  **weekly report**, and **plan week (dry run)** - no terminal needed.
- Each run takes a few minutes and uses your Claude subscription. Keep the
  tab open while it works.
- Buttons never approve ideas, commit schedules, or publish anything -
  decisions always come back to you.
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
    "Trends": page_trends,
    "Schedule": page_schedule,
    "Strategy log": page_strategy,
    "Agent": page_agent,
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
