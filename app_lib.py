"""Shared plumbing for the PubCam app: db access, palette, agent runner, Smeaton."""
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).parent
DB_PATH = REPO_ROOT / "db" / "pubcam.db"
INBOX_DIR = REPO_ROOT / "inbox"
SCORE_SCRIPT = REPO_ROOT / "scripts" / "score_posts.py"
SMEATON_PATH = REPO_ROOT / "assets" / "smeaton.png"

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


# ---------------------------------------------------------------- agent runner

AGENT_TOOLS = "Read,Glob,Grep,Edit,Write,Bash,WebSearch,WebFetch"

# Cost control: app-triggered runs default to Haiku ($1/$5 per MTok vs $5/$25
# for Opus - roughly 5x cheaper per token). The "High quality" toggle in the
# app switches back to the default model for runs where judgment matters most.
AGENT_MODEL_FAST = "claude-haiku-4-5"
AGENT_MAX_TURNS = "20"
CHAT_MAX_TURNS = "10"

FRUGAL_NOTE = (
    " Be token-frugal: load context with `python scripts/db.py digest` (one "
    "call - do not run separate list commands unless you need a detail digest "
    "lacks), keep tool calls to the minimum, and keep your final summary short."
)


def _agent_cmd_base(claude: str, max_turns: str) -> list[str]:
    cmd = [claude, "--output-format", "stream-json", "--verbose",
           "--allowedTools", AGENT_TOOLS, "--max-turns", max_turns]
    if not st.session_state.get("hq_mode", False):
        cmd += ["--model", AGENT_MODEL_FAST]
    return cmd


def render_quality_toggle() -> None:
    st.toggle(
        "High quality mode",
        key="hq_mode",
        help="Off (default): runs use Haiku - fast and roughly 5x cheaper per token. "
             "On: runs use your default Claude model - smarter, slower, costs more. "
             "Turn on for briefs or reports you'll rely on heavily.",
    )

BRIEF_PROMPT = (
    "Run the develop-idea skill for idea id {id}, non-interactively (never ask "
    "questions). Save the brief with scripts/db.py add-brief and print the full "
    "brief as your final message."
)

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

    cmd = _agent_cmd_base(claude, AGENT_MAX_TURNS) + ["-p", prompt + FRUGAL_NOTE]
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


def run_agent_chat(prompt: str, resume_session: str | None) -> tuple[str, str | None]:
    """One chat turn against headless Claude in this repo. Returns (reply, session_id).

    Uses --resume so the conversation keeps its context across turns without
    accidentally resuming an unrelated headless run's session.
    """
    claude = shutil.which("claude")
    if not claude:
        return ("Claude Code CLI not found on PATH. Install with: npm install -g @anthropic-ai/claude-code", None)

    cmd = _agent_cmd_base(claude, CHAT_MAX_TURNS) + ["-p", prompt + FRUGAL_NOTE]
    if resume_session:
        cmd += ["--resume", resume_session]

    session_id = resume_session
    texts: list[str] = []
    proc = subprocess.Popen(
        cmd, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
    )
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            session_id = event.get("session_id", session_id)
        elif event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text" and block.get("text", "").strip():
                    texts.append(block["text"])
    rc = proc.wait()
    if not texts:
        return (f"(no reply - run exited with code {rc}; try again)", session_id)
    return (texts[-1], session_id)


# ---------------------------------------------------------------- Smeaton

SMEATON_TIPS = {
    "Home": [
        "This page is your pre-Instagram ritual: check what needs you, what's hot, what's going out - THEN open Instagram to post, not to scroll for ideas.",
        "The 'needs you' card is the to-do list. Clear it and the whole pipeline keeps moving on its own.",
        "Time-sensitive trends die fast - if one's flagged here, it's this week or never.",
    ],
    "Dashboard": [
        "Hover the dots on the score chart - each one is a post. The dashed line is your 5-post average: if it's climbing, whatever you changed is working.",
        "Click-drag on the chart to zoom into a stretch of weeks. Double-click to zoom back out.",
        "Filter to just carousels with the pills above the chart - that's where your biggest wins live so far.",
        "The insights card recalculates every time you score a new CSV. Friday's upload literally changes what I tell you here.",
    ],
    "Score posts": [
        "Meta Business Suite -> Insights -> Content -> Export. Pick the widest date range - re-scoring old posts is safe, nothing duplicates.",
        "Posts younger than 7 days get held back on purpose - young posts score unfairly low and would pollute the rankings.",
        "If scoring fails with a 'missing columns' error, Meta probably renamed a header. Paste the error to Claude Code and it's a one-line fix.",
    ],
    "Ideas": [
        "Approving an idea builds its production brief automatically - hooks, shot list, caption, the lot. Give it a few minutes, then find it under 'Approved & developed'.",
        "Every brief ends with a 'Before you post' checklist - that's the fact-check list. Nothing ships until those boxes are ticked.",
        "Approve sparingly - the schedule builder takes approved ideas in order. A tight, good backlog beats a huge messy one.",
        "When you capture an idea, put WHY it caught your eye in the notes. Future-you (and the agent) will thank you.",
        "Anything mentioning a price or event date needs a source before it ships - that's the house rule.",
    ],
    "Trends": [
        "Open trends feed the idea generator. If a trend looks wrong for PubCam, hit 'Mark acted' to retire it without making ideas from it.",
        "Always peek at the source link before building on a trend - see the format in action, not just my description of it.",
        "Trends go stale fast. If something's been open for 3+ weeks, it probably missed its moment.",
    ],
    "Schedule": [
        "Mark posts as posted here right after publishing - it keeps the weekly report honest about what actually went out.",
        "Ask Claude Code to '/sync-drive' after committing a week - Jack and Dakota get the schedule without touching any of this.",
    ],
    "Strategy log": [
        "This is the brand's memory. One honest entry per real decision beats ten vague ones.",
        "No evidence, no entry - the form will hold you to it. A number, a query result, or a report finding all count.",
    ],
    "Agent": [
        "Runs take 2-5 minutes - keep the tab open and watch the progress line. Results land in the database, so nothing is lost if you navigate after it finishes.",
        "Monday combo: Trend sweep, then Generate ideas, then approve on the Ideas page, then Plan week. Four buttons, week sorted.",
        "Buttons never approve or publish anything. Worst case a run wastes five minutes - it can't wreck your schedule.",
    ],
    "How to use": [
        "New here? Read the weekly routine table first - everything else hangs off it.",
        "You can ask Claude Code anything about your data in plain English - 'which venue converts followers best?' works.",
    ],
}


def render_smeaton(page: str) -> None:
    tips = SMEATON_TIPS.get(page, [])
    if not tips:
        return
    key = f"smeaton_{page}"
    idx = st.session_state.get(key, 0) % len(tips)
    with st.chat_message("assistant", avatar=str(SMEATON_PATH)):
        st.markdown(f"**Smeaton says:** {tips[idx]}")
    if len(tips) > 1 and st.button("Another tip", icon=":material/autorenew:", key=f"{key}_btn"):
        st.session_state[key] = idx + 1
        st.rerun()
