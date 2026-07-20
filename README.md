# pubcam-agent

Terminal-based content tracker + strategy agent for PubCam, driven by Claude Code.

## What this is

[PubCam](https://www.instagram.com/pubcam.au/) is a nightlife media brand in
Wollongong, Australia that runs collab content with local venue partners. This
repo is its full content operations system: a local Streamlit app (the daily
home base) plus a Claude Code agent, sharing one SQLite database. Everything
runs on a laptop — no hosting, no SaaS.

The loop it runs: **trends → ideas → your approval → auto-built production
briefs → weekly schedule → post → score → insights feed the next round.**

What it does today:

- **Home-base app** (`streamlit_app.py`) — open it before Instagram: what
  needs a decision, what's trending, what's going out this week, and how the
  last posts performed. Includes an in-app **Chat** with the agent.
- **Post builder** — type a rough idea ("cheapest parmas in the gong") and
  get a complete carousel in the proven PubCam layout: SAVE-THIS hook cover,
  one item per slide, screenshot-and-send payoff slide, caption. One click
  renders it as actual PNGs in PubCam's real carousel style (photo, dark
  scrim, script signature) — drawing from a venue photo library
  (`assets/venue_photos/`) that auto-matches the right shot per slide.
- **Auto-built production briefs** — approving any idea generates its brief
  (hooks, shot list or slide layout, caption draft, fact-check checklist).
- **Scores every Instagram post** with PubCam's confirmed weighted engagement
  model (shares/follows weighted most, ÷ reach, percentile-ranked, A+–D
  ratings) from a Meta Business Suite CSV.
- **Sweeps the web for content trends** it could adapt (source URLs required,
  nothing invented) and **turns trends + performance data into new ideas**.
- **Plans the weekly schedule** from approved ideas and **writes performance
  reports** that test the brand's strategy assumptions against real numbers.
- **Runs cheap by default** — app-triggered agent runs use Haiku with a
  single ~500-token `digest` context call and turn caps; a High quality
  toggle switches to the full model when the output matters.

The design principles: Claude Code *is* the agent and [CLAUDE.md](CLAUDE.md)
is its brain (brand context, scoring model, hard rules); the agent proposes
and a human approves — nothing is published or scheduled without your click;
no fact ships unverified — prices and event details come back as [CHECK]
items, never guesses; and the app, chat, and terminal all share one database,
so they never disagree.

Start here: [CLAUDE.md](CLAUDE.md) — the agent's brain (brand voice, venues,
scoring model, rules, workflow definitions).

## Status: v1.0.1+ — full daily-driver loop

Built:
- Streamlit app as the primary interface: Home, Chat, Post builder, Score
  posts, Ideas (approve → auto-brief), Trends, Schedule, Agent buttons,
  Dashboard (trend lines + live insights), Strategy log, built-in help,
  and Smeaton the mascot with page-aware tips
- `build-post` skill — one-shot idea → PubCam-layout carousel (idea + brief)
- `scripts/render_carousel.py` — brief → actual PNG carousel slides in
  PubCam's real style (photo, dark scrim, Playfair Display/Sacramento
  type, signature mark); auto-picks the right shot per venue from
  `assets/venue_photos/`, falling back to a placeholder with zero code
  changes needed either way
- `develop-idea` skill — production briefs on approval (briefs table)
- Cost controls: Haiku default for app runs, `db.py digest` (~500-token
  whole-database context), compact outputs, turn caps, HQ-mode toggle
- Repo scaffold, CLAUDE.md, SQLite schema (`db/`)
- `score-posts` skill — scores a Meta Business Suite CSV from `inbox/`.
  Methodology (weights, global percentile, rating bands, pubcam.au-only
  scoring) is **confirmed**, ported directly from the real "PubCam Post
  Performance Model v2" Google Sheet — not guessed.
- `/capture` — log an idea to the backlog
- `/strategy` — log a strategy pivot, propose CLAUDE.md Section 3 edits
- `schedule-builder` skill + `/plan-week` — proposes a weekly schedule from
  approved ideas (`scripts/build_schedule.py`), dry-run by default, commits
  only on confirmation
- `/report` — performance summary vs. strategy
- `scripts/export_schedule.py` — schedule table → markdown/CSV
- `drive-sync` skill + `/sync-drive` — pushes the schedule to Google Drive
  (PubCam/Business/Trackers & Spreadsheets) as a Sheet. Creates a new file
  each run rather than truly updating in place (see that skill's caveat) —
  built but not yet live-tested against real schedule data.
- `trend-sweep` skill — web research pass for PubCam-relevant content
  trends, logs candidates to the `trends` table with source URLs
- `idea-generator` skill — top/bottom posts + open trends + venue calendar
  → concrete post ideas with draft hook lines, written to the backlog
- Streamlit app (`app.py` / `PubCam Agent.bat`) — dashboard, CSV scoring,
  idea approve/kill, schedule, strategy log, built-in help

Still open before this is trustworthy day-to-day:

- Editorial voice guidelines (CLAUDE.md Section 2 is a TODO).
- Real posting cadence + format ratio (placeholder in
  `config/schedule_slots.json` — currently guessed at Tue/Thu/Sat and
  2 carousel : 1 reel; the confirmed scoring model doesn't specify this).
- Confirm `afterglowshq` → Illawarra mapping (CLAUDE.md Section 1, inferred
  from captions, not confirmed).
- Phase 3 (Instagram Graph API insights + competitor-scan — needs a Meta
  developer app) and Phase 4 (scheduled automation of trend-sweep/scoring) —
  see individual `SKILL.md` files under `.claude/skills/` and the stub
  scripts in `scripts/`.
- `PubCam_Post_Tracker` (Google Drive) has richer columns (Hook, Reach
  Ratio, Save Rate, "Fits Formula?", "Why It Worked / Didn't") than this
  repo's `posts` table — worth mining for `/report` later.

## Quick start

```
python db/init_db.py                 # create/reset db/pubcam.db from schema.sql
# drop a Meta Business Suite CSV export into inbox/
python scripts/score_posts.py        # scores the newest CSV in inbox/

python scripts/db.py add-idea --title "..." --source capture --venue-fit "..." --format reel --notes "..."
python scripts/db.py update-idea --id 1 --status approved
python scripts/build_schedule.py --week-start 2026-07-20        # dry run
python scripts/build_schedule.py --week-start 2026-07-20 --commit
python scripts/export_schedule.py --week-start 2026-07-20
```

Or from the terminal inside Claude Code: `/capture`, `/plan-week`,
`/report`, `/strategy`, `/sync-drive`.

## App interface

A local Streamlit app over the same database, structured as a home base:
Home (what needs you today), Chat with the agent, scoring, ideas with
auto-built production briefs, trends, schedule, dashboard with trend lines,
and one-click agent runs. App-triggered agent runs default to Haiku for
cost (a 'High quality mode' toggle switches back to the default model).
Themed in `.streamlit/config.toml` — soft neutral surfaces, one confident
navy accent, pill buttons, rounded cards.

```
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

On Windows, double-click **PubCam Agent.bat** instead (edit the Python path
inside if yours differs from `C:\Python314`). The app and the Claude Code
agent read and write the same `db/pubcam.db`, so they never drift apart:
use the app for day-to-day checking and approvals, the agent for planning,
reports, and research.
