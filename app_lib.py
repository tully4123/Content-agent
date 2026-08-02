"""Shared plumbing for the PubCam app: db access, palette, agent runner, Smeaton."""
import datetime as dt
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).parent
DB_PATH = REPO_ROOT / "db" / "pubcam.db"
INBOX_DIR = REPO_ROOT / "inbox"
SCORE_SCRIPT = REPO_ROOT / "scripts" / "score_posts.py"
RENDER_SCRIPT = REPO_ROOT / "scripts" / "render_carousel.py"
RENDER_DIR = REPO_ROOT / "renders"
SMEATON_PATH = REPO_ROOT / "assets" / "smeaton.png"
PHOTO_LIBRARY = REPO_ROOT / "assets" / "venue_photos"
PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")
REEL_REF_DIR = REPO_ROOT / "reference_reels"
VIDEO_EXTS = ["mp4", "mov", "webm", "m4v"]
POST_REF_DIR = REPO_ROOT / "reference_posts"
IMAGE_EXTS = ["jpg", "jpeg", "png", "webp"]
NOTES_DIR = REPO_ROOT / "ops" / "notes"

# Folder choices for the library uploader - the real venues (matched to
# slides by word overlap in render_carousel.py) plus a general bucket for
# cover/payoff/outro shots that aren't tied to one venue.
PHOTO_FOLDER_OPTIONS = ["Heyday", "Illawarra", "The Icon", "PubCam original", "General"]

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

# ---------------------------------------------------------------- theme polish

_THEME_CSS = """
<style>
/* Elevated cards for every bordered container (Needs you / Hot right now /
   Agent action cards / etc.) - a soft shadow instead of a flat hairline so
   the app reads less like a form and more like a native dashboard. */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px !important;
    transition: box-shadow 0.15s ease, transform 0.15s ease;
    box-shadow: 0 1px 2px rgba(16, 42, 67, 0.05), 0 6px 20px rgba(16, 42, 67, 0.07);
}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {
    box-shadow: 0 2px 4px rgba(16, 42, 67, 0.07), 0 10px 28px rgba(16, 42, 67, 0.10);
}
@media (prefers-color-scheme: dark) {
    div[data-testid="stVerticalBlockBorderWrapper"] {
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.35), 0 6px 20px rgba(0, 0, 0, 0.30);
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.40), 0 10px 28px rgba(0, 0, 0, 0.38);
    }
}

/* Metric tiles (the pulse row) - rounded, slightly raised, room to breathe */
div[data-testid="stMetric"] {
    border-radius: 16px !important;
    padding: 14px 16px !important;
}

/* Chat bubbles - softer, more app-like than square Streamlit default */
div[data-testid="stChatMessage"] {
    border-radius: 20px;
    padding: 4px 6px;
}

/* page_link rows get a gentle hover nudge, matching button feel */
a[data-testid="stPageLink-NavLink"], div[data-testid="stPageLink"] a {
    transition: transform 0.12s ease;
}
a[data-testid="stPageLink-NavLink"]:hover, div[data-testid="stPageLink"] a:hover {
    transform: translateX(2px);
}

/* Tighten the default gap between the page title and first block a touch */
div[data-testid="stAppViewBlockContainer"] > div:first-child {
    padding-top: 0.25rem;
}

/* Smeaton - fades/slides in fresh on every render (each new tip replays
   this, since Streamlit remounts the node), with a small idle bob on the
   avatar so he reads as alive, not a static image. */
div[class*="st-key-smeaton_box"] {
    animation: smeaton-in 0.35s ease-out;
}
@keyframes smeaton-in {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
div[class*="st-key-smeaton_box"] img {
    animation: smeaton-bob 3.2s ease-in-out infinite;
    transform-origin: 50% 85%;
}
@keyframes smeaton-bob {
    0%, 100% { transform: rotate(0deg) translateY(0); }
    50% { transform: rotate(-4deg) translateY(-2px); }
}
@media (prefers-reduced-motion: reduce) {
    div[class*="st-key-smeaton_box"], div[class*="st-key-smeaton_box"] img {
        animation: none;
    }
}

/* The pulse dot marks a live, data-driven Smeaton nudge (vs. a static tip) */
.smeaton-pulse-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #F0A61D;
    margin-right: 6px;
    vertical-align: middle;
    animation: smeaton-pulse 1.6s ease-in-out infinite;
}
@keyframes smeaton-pulse {
    0% { box-shadow: 0 0 0 0 rgba(240, 166, 29, 0.55); }
    70% { box-shadow: 0 0 0 8px rgba(240, 166, 29, 0); }
    100% { box-shadow: 0 0 0 0 rgba(240, 166, 29, 0); }
}
</style>
"""


def render_theme_css() -> None:
    """Inject the shared visual-polish layer. Call once, near the top of
    streamlit_app.py - every page inherits it since Streamlit CSS is global."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str) -> None:
    """Branded gradient banner - PubCam navy - used at the top of Home in
    place of a plain st.title, so the app's one 'front door' feels designed
    rather than default Streamlit."""
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(135deg, #0B2036 0%, #102A43 55%, #1F4A75 100%);
            border-radius: 20px;
            padding: 30px 34px;
            margin-bottom: 8px;
            box-shadow: 0 10px 30px rgba(16, 42, 67, 0.30);
        ">
            <div style="color: #FFFFFF; font-size: 27px; font-weight: 700; letter-spacing: -0.01em;">
                {title}
            </div>
            <div style="color: #C9D6E3; font-size: 14px; margin-top: 5px;">
                {subtitle}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

REEL_PROMPT = (
    "Run the build-reel skill for reel reference id {ref_id}. Venue fit: {venue}. "
    "Non-interactive (never ask questions). Save via scripts/db.py add-idea + "
    "add-brief, link it back with scripts/db.py link-reel-ref --id {ref_id} "
    "--idea-id <the new idea id>, and print the full build as your final message."
)

POST_REF_LINE = (
    " Follow the structure from post reference id {ref_id} instead of the "
    "default template - read its notes first with `scripts/db.py get-post-ref "
    "--id {ref_id}`, then link it back afterward with `scripts/db.py "
    "link-post-ref --id {ref_id} --idea-id <the new idea id>`."
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


# ---------------------------------------------------------------- carousel renderer

def render_carousel_images(idea_id: int) -> tuple[bool, str, list[Path]]:
    """Renders the newest brief for an idea into slide PNGs (renders/idea_<id>/).

    Deterministic Pillow drawing, not an agent run - runs in a couple of
    seconds and costs nothing. Only understands build-post's carousel format;
    see scripts/render_carousel.py.
    """
    proc = subprocess.run(
        [sys.executable, str(RENDER_SCRIPT), "--idea-id", str(idea_id)],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out_dir = RENDER_DIR / f"idea_{idea_id}"
    images = sorted(out_dir.glob("slide_*.png")) if out_dir.exists() else []
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "Render failed."
        return False, message, images
    return True, proc.stdout.strip(), images


# ---------------------------------------------------------------- photo library

def list_photo_library() -> dict[str, list[str]]:
    """Current assets/venue_photos/ contents grouped by folder, for the
    Post builder's library gallery."""
    if not PHOTO_LIBRARY.exists():
        return {}
    groups: dict[str, list[str]] = {}
    for p in sorted(PHOTO_LIBRARY.rglob("*")):
        if p.suffix.lower() not in PHOTO_EXTS:
            continue
        folder = p.relative_to(PHOTO_LIBRARY).parent
        key = str(folder) if str(folder) != "." else "(ungrouped)"
        groups.setdefault(key, []).append(p.name)
    return groups


def save_uploaded_photos(folder: str, uploaded_files) -> int:
    """Save uploaded photos into assets/venue_photos/<folder>/ so
    render_carousel.py's word-overlap matching picks them up automatically
    on the next render. Returns how many were saved."""
    if not uploaded_files:
        return 0
    dest = PHOTO_LIBRARY / folder
    dest.mkdir(parents=True, exist_ok=True)
    saved = 0
    for f in uploaded_files:
        name = Path(f.name).name  # strip any path components from the original filename
        (dest / name).write_bytes(f.getbuffer())
        saved += 1
    return saved


def delete_photo(folder: str, filename: str) -> None:
    path = PHOTO_LIBRARY / folder / filename
    if path.exists():
        path.unlink()


def save_reel_reference(source_url: str, venue_fit: str, notes: str, uploaded_file) -> int:
    """Log a reference reel (Reel builder's drop zone) and, if a video file
    was attached, save it under reference_reels/<id>/. Returns the new
    reel_refs id."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO reel_refs (source_url, file_name, venue_fit, notes) VALUES (?, ?, ?, ?)",
            (source_url or None, uploaded_file.name if uploaded_file else None, venue_fit, notes),
        )
        conn.commit()
        ref_id = cur.lastrowid
    finally:
        conn.close()
    if uploaded_file:
        dest_dir = REEL_REF_DIR / str(ref_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / Path(uploaded_file.name).name).write_bytes(uploaded_file.getbuffer())
    return ref_id


def list_reel_references() -> pd.DataFrame:
    return query(
        "SELECT reel_refs.*, ideas.title AS idea_title, ideas.status AS idea_status,"
        " EXISTS(SELECT 1 FROM briefs WHERE briefs.idea_id = reel_refs.idea_id) AS has_brief"
        " FROM reel_refs LEFT JOIN ideas ON reel_refs.idea_id = ideas.id"
        " ORDER BY reel_refs.id DESC"
    )


def reel_reference_file(ref_id: int) -> Path | None:
    d = REEL_REF_DIR / str(ref_id)
    if not d.exists():
        return None
    files = [f for f in d.iterdir() if f.is_file()]
    return files[0] if files else None


def delete_reel_reference(ref_id: int) -> None:
    execute("DELETE FROM reel_refs WHERE id = ?", (ref_id,))
    d = REEL_REF_DIR / str(ref_id)
    if d.exists():
        shutil.rmtree(d)


def save_post_reference(source_url: str, notes: str, uploaded_file) -> int:
    """Log a reference post structure (Post builder's 'copy a specific
    structure' section) and, if an image was attached, save it under
    reference_posts/<id>/. Returns the new post_refs id."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO post_refs (source_url, file_name, notes) VALUES (?, ?, ?)",
            (source_url or None, uploaded_file.name if uploaded_file else None, notes),
        )
        conn.commit()
        ref_id = cur.lastrowid
    finally:
        conn.close()
    if uploaded_file:
        dest_dir = POST_REF_DIR / str(ref_id)
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / Path(uploaded_file.name).name).write_bytes(uploaded_file.getbuffer())
    return ref_id


def list_post_references() -> pd.DataFrame:
    return query(
        "SELECT post_refs.*, ideas.title AS idea_title, ideas.status AS idea_status,"
        " EXISTS(SELECT 1 FROM briefs WHERE briefs.idea_id = post_refs.idea_id) AS has_brief"
        " FROM post_refs LEFT JOIN ideas ON post_refs.idea_id = ideas.id"
        " ORDER BY post_refs.id DESC"
    )


def post_reference_file(ref_id: int) -> Path | None:
    d = POST_REF_DIR / str(ref_id)
    if not d.exists():
        return None
    files = [f for f in d.iterdir() if f.is_file()]
    return files[0] if files else None


def delete_post_reference(ref_id: int) -> None:
    execute("DELETE FROM post_refs WHERE id = ?", (ref_id,))
    d = POST_REF_DIR / str(ref_id)
    if d.exists():
        shutil.rmtree(d)


def save_slide_override(idea_id: int, slide_number: int, uploaded_file) -> Path:
    """Save an exact photo for one slide of one build - takes priority over
    the shared library for that slide (see render_carousel.py's photo
    priority order)."""
    dest_dir = RENDER_DIR / f"idea_{idea_id}" / "photos"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(uploaded_file.name).suffix.lower() or ".jpg"
    for existing_ext in PHOTO_EXTS:
        stale = dest_dir / f"slide_{slide_number:02d}{existing_ext}"
        if stale.exists() and existing_ext != ext:
            stale.unlink()
    dest = dest_dir / f"slide_{slide_number:02d}{ext}"
    dest.write_bytes(uploaded_file.getbuffer())
    return dest


# ---------------------------------------------------------------- notes
#
# One markdown file per note, in ops/notes/ - plain "# Title" then an
# optional "Tags: a, b" line then freeform body. No sidecar index; title,
# tags, and last-edited all come straight from the file itself (mtime for
# the date), so the files stay the single source of truth whether you edit
# them here in the app or by hand.

def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "note"


def _parse_note(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = path.stem.replace("-", " ").title()
    body_start = 0
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body_start = 1

    i = body_start
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    tags: list[str] = []
    if i < len(lines) and lines[i].lower().startswith("tags:"):
        tags = [t.strip() for t in lines[i].split(":", 1)[1].split(",") if t.strip()]
        body_start = i + 1

    body = "\n".join(lines[body_start:]).strip("\n")
    return {
        "filename": path.name,
        "title": title,
        "tags": tags,
        "body": body,
        "updated_at": dt.datetime.fromtimestamp(path.stat().st_mtime),
    }


def list_notes(query_text: str = "", tag: str | None = None) -> list[dict]:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    notes = [_parse_note(p) for p in NOTES_DIR.glob("*.md")]
    if tag:
        notes = [n for n in notes if tag in n["tags"]]
    if query_text.strip():
        q = query_text.strip().lower()
        notes = [
            n for n in notes
            if q in n["title"].lower() or q in n["body"].lower() or any(q in t.lower() for t in n["tags"])
        ]
    notes.sort(key=lambda n: n["updated_at"], reverse=True)
    return notes


def get_note(filename: str) -> dict | None:
    path = NOTES_DIR / filename
    return _parse_note(path) if path.exists() else None


def save_note(filename: str | None, title: str, tags: list[str], body: str) -> str:
    """Create a note (filename=None) or overwrite an existing one. Editing
    a title never renames the file - the filename is assigned once, at
    creation, so nothing else that might reference it ever goes stale."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        base = _slugify(title)
        candidate = f"{base}.md"
        n = 2
        while (NOTES_DIR / candidate).exists():
            candidate = f"{base}-{n}.md"
            n += 1
        filename = candidate
    tags_line = f"Tags: {', '.join(tags)}\n\n" if tags else ""
    content = f"# {title}\n\n{tags_line}{body.strip()}\n"
    (NOTES_DIR / filename).write_text(content, encoding="utf-8")
    return filename


def delete_note(filename: str) -> None:
    path = NOTES_DIR / filename
    if path.exists():
        path.unlink()


def all_note_tags() -> list[str]:
    tags: set[str] = set()
    for n in list_notes():
        tags.update(n["tags"])
    return sorted(tags)


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
    "Post builder": [
        "Give me the rough idea, get the whole carousel: hook cover, one item per slide, the group-chat payoff slide, outro, caption. You just design and post it.",
        "Anything I can't verify comes back marked [CHECK] - tick those off before it ships. I never invent prices.",
        "Builds land in Ideas as backlog with the brief attached - approving them won't rebuild anything.",
        "Flip on High quality mode for builds you'll actually shoot - the hooks come out sharper.",
        "Hit 'Render carousel images' and I'll draw every slide as an actual PNG - PubCam's real photo-and-signature style, free and instant, no agent call needed.",
        "Drop venue photos into assets/venue_photos/ and I'll pick the right one for each slide automatically - no photo yet, no worries, it renders on a placeholder until one turns up.",
        "Want a different structure than the usual SAVE-THIS layout? Open 'Copy a specific post structure', drop in an example and describe it (a Q&A, a countdown, whatever it is) - I'll build to that instead. Leave it empty for the proven default.",
    ],
    "Reel builder": [
        "Drop in a video and write what you actually want copied - the hook, the pacing, a specific mechanic. I never watch the file, only your note, so the more specific it is the closer the script lands.",
        "A source link works too if you don't have the file - I'll try one fetch to see what it's about, best-effort, never a blocker.",
        "Builds land in Ideas as backlog, same as everything else - approve it there when you're happy.",
        "No trending sound gets named unless your note or the link actually said so - otherwise it comes back flagged [CHECK] rather than made up.",
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
    "Notes": [
        "Anything you write here, I actually read as context (CLAUDE.md) - not decoration. A note on a venue's contact or a pricing quirk shapes what I build next.",
        "Tags are just a comma-separated line under the title - filter by one with the pills above the grid.",
        "These are plain markdown files in ops/notes/ - open one in any text editor if you'd rather type there than in the browser. Same file either way.",
    ],
}


def _dynamic_smeaton_tip(page: str) -> str | None:
    """A live-data nudge for pages where a real number beats a canned tip.
    None if nothing's actionable right now - the caller falls back to the
    regular rotating tips."""
    try:
        if page == "Home":
            n = int(query("SELECT COUNT(*) AS n FROM ideas WHERE status='backlog'")["n"][0])
            if n >= 5:
                return f"{n} ideas are sitting in the backlog - clear a few before they go stale."
        elif page == "Ideas":
            n = int(query("SELECT COUNT(*) AS n FROM ideas WHERE status='backlog'")["n"][0])
            if n:
                return f"{n} idea{'s' if n != 1 else ''} waiting on you right now - approve or kill them below."
        elif page == "Trends":
            n = int(query(
                "SELECT COUNT(*) AS n FROM trends WHERE acted_on=0 AND date_spotted <= date('now','-21 days')"
            )["n"][0])
            if n:
                return f"{n} trend{'s' if n != 1 else ''} been open 3+ weeks - use {'them' if n != 1 else 'it'} or retire {'them' if n != 1 else 'it'}, going cold."
        elif page == "Post builder":
            n = int(query("SELECT COUNT(*) AS n FROM post_refs WHERE idea_id IS NULL")["n"][0])
            if n:
                return f"{n} reference post{'s' if n != 1 else ''} saved but not built yet - the library at the bottom is waiting on you."
        elif page == "Reel builder":
            n = int(query("SELECT COUNT(*) AS n FROM reel_refs WHERE idea_id IS NULL")["n"][0])
            if n:
                return f"{n} reference reel{'s' if n != 1 else ''} saved but not built yet - the library at the bottom is waiting on you."
        elif page == "Schedule":
            n = int(query(
                "SELECT COUNT(*) AS n FROM schedule WHERE status != 'posted'"
                " AND target_date BETWEEN date('now') AND date('now','+7 days')"
            )["n"][0])
            if n:
                return f"{n} post{'s' if n != 1 else ''} going out in the next 7 days - open the brief and get shooting."
        elif page == "Dashboard":
            scored = query(
                "SELECT weighted_score FROM posts WHERE scoring_excluded=0"
                " AND weighted_score IS NOT NULL ORDER BY posted_at"
            )
            if len(scored) >= 10:
                recent = scored["weighted_score"].tail(5).mean()
                earlier = scored["weighted_score"].iloc[:-5].mean()
                delta = recent - earlier
                if abs(delta) >= 5:
                    mood = "climbing" if delta > 0 else "dipping"
                    advice = "keep doing whatever you changed" if delta > 0 else "worth a look at what shifted"
                    return f"Your last 5 posts are {mood} ({delta:+.0f} vs before) - {advice}."
    except Exception:
        return None
    return None


def render_smeaton(page: str) -> None:
    tips = SMEATON_TIPS.get(page, [])
    dynamic_tip = _dynamic_smeaton_tip(page)
    if not tips and not dynamic_tip:
        return

    key = f"smeaton_{page}"
    dyn_key = f"{key}_dyn_seen"
    idx = st.session_state.get(key, 0) % len(tips) if tips else 0
    show_dynamic = bool(dynamic_tip) and not st.session_state.get(dyn_key, False)

    with st.container(key=f"smeaton_box_{page.replace(' ', '_')}"):
        with st.chat_message("assistant", avatar=str(SMEATON_PATH)):
            if show_dynamic:
                st.markdown(
                    f"<span class='smeaton-pulse-dot'></span>**Smeaton says:** {dynamic_tip}",
                    unsafe_allow_html=True,
                )
            elif tips:
                st.markdown(f"**Smeaton says:** {tips[idx]}")
            else:
                st.markdown("**Smeaton says:** All clear here - nothing urgent.")

        has_more = (tips and len(tips) > 1) or show_dynamic
        if has_more and st.button("Another tip", icon=":material/autorenew:", key=f"{key}_btn"):
            if show_dynamic:
                st.session_state[dyn_key] = True
            else:
                st.session_state[key] = idx + 1
            st.rerun()
