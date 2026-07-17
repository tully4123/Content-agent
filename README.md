# pubcam-agent

Terminal-based content tracker + strategy agent for PubCam, driven by Claude Code.

## What this is

[PubCam](https://www.instagram.com/pubcam.au/) is a nightlife media brand in
Wollongong, Australia that runs collab content with local venue partners. This
repo is its content operations system: instead of a web app or SaaS tool, the
whole thing is a local folder that Claude Code operates as an agent — a SQLite
database, a set of Python scripts, and Claude Code skills/commands that wire
them into workflows.

What it does:

- **Scores every Instagram post** using PubCam's weighted engagement model
  (shares and new follows count most, likes least; score = weighted engagement
  ÷ reach, percentile-ranked against all post history). Feed it a Meta
  Business Suite CSV export and it flags what's working and what to retire.
- **Keeps an ideas backlog** — spotted a good reel format elsewhere? `/capture`
  logs it. Performance insights and trend research feed the same backlog.
- **Builds the weekly posting schedule** from approved ideas, respecting venue
  mix and format ratio, with a human approving every step — the agent proposes,
  a person posts.
- **Writes performance reports** that check results against the brand's
  running strategy assumptions and propose updates when the data disagrees.
- **Syncs the schedule to Google Drive** so the rest of the team sees it
  without touching a terminal.

The design principle: Claude Code *is* the agent, and the repo is its brain.
[CLAUDE.md](CLAUDE.md) holds the brand context, scoring model, and hard rules
(e.g. never state a venue price or event detail without a verified source);
the skills in [.claude/skills/](.claude/skills/) define the workflows; SQLite
holds the state. No hosting, no server — it runs on a laptop.

Start here: [CLAUDE.md](CLAUDE.md) — the agent's brain (brand voice, venues,
scoring model, rules, workflow definitions).

## Status: Phase 1 + Phase 2 core loop

Built:
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

A local Streamlit app over the same database — dashboard with scores and
per-format chart, CSV upload + one-click scoring, idea capture with
approve/kill buttons, schedule view, and the strategy log.

```
pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows, double-click **PubCam Agent.bat** instead (edit the Python path
inside if yours differs from `C:\Python314`). The app and the Claude Code
agent read and write the same `db/pubcam.db`, so they never drift apart:
use the app for day-to-day checking and approvals, the agent for planning,
reports, and research.
