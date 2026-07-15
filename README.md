# pubcam-agent

Terminal-based content tracker + strategy agent for PubCam, driven by Claude Code.

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

Still open before this is trustworthy day-to-day:

- Editorial voice guidelines (CLAUDE.md Section 2 is a TODO).
- Real posting cadence + format ratio (placeholder in
  `config/schedule_slots.json` — currently guessed at Tue/Thu/Sat and
  2 carousel : 1 reel; the confirmed scoring model doesn't specify this).
- Confirm `afterglowshq` → Illawarra mapping (CLAUDE.md Section 1, inferred
  from captions, not confirmed).
- Phase 3 (Instagram Graph API insights + competitor-scan) and Phase 4
  (cron automation + trend-sweep) — see individual `SKILL.md` files under
  `.claude/skills/` and the stub scripts in `scripts/`.
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
