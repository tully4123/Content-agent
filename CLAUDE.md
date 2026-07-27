# PubCam Content Agent

This file is the agent's brain. Read it in full before doing any content, scoring,
scheduling, or reporting work in this repo.

## 1. Who we are

PubCam is a Wollongong nightlife media brand. Content is built on a collab-post
model with venue partners rather than single-venue promo.

**Venue partners:** The Icon, Illawarra Hotel, Heyday (formal names). Day to
day, tracking/reporting uses PubCam's own shorthand from `PubCam_Post_Tracker`
(Google Drive): **Icon, Illawarra, Heyday**, plus **PubCam original** for
pubcam.au's own (often multi-venue) posts.

**Competitors:** Bondi Lines, LineSkip, What's On Wollongong
*(TODO — confirm this list is complete/current)*

**Tracked Instagram accounts → venue mapping** (Meta Business Suite exports
identify posts by account, not venue — see `scripts/score_posts.py`
`ACCOUNT_TO_VENUE`; names match `PubCam_Post_Tracker`'s "BY VENUE" summary):

| Account | Venue |
|---|---|
| pubcam.au | PubCam original |
| heydaywollongong | Heyday |
| socialsundays_ | Illawarra |
| illa_afterdark | Illawarra |
| afterglowshq | Illawarra |

*(TODO — confirm afterglowshq is correctly mapped to Illawarra; this was an
inference from caption content, not a confirmed fact.)* New accounts that
show up in an export without a mapping fall back to using the raw username as
venue and print a warning — add them to `ACCOUNT_TO_VENUE` when that happens.
No account currently maps to "Icon" — `PubCam_Post_Tracker` shows 0 Icon
posts too, so this isn't a gap introduced by this repo.

**External resources (Google Drive, read access confirmed 2026-07-15):**

- `PubCam_Post_Tracker` (PubCam/Business/Trackers & Spreadsheets) — the
  existing manual post-by-post tracker this repo's `posts` table is meant to
  replace. Columns include Hook (first line), Reach Ratio, Save Rate, "Fits
  Formula?", "Why It Worked / Didn't" — richer than our current schema;
  worth mining if `/report` needs more texture than weighted_score/percentile.
- `PubCam Post Performance Model v2` (same folder) — source of truth for the
  scoring formula (Section 4). Also documents rating bands and the "log
  posts once 7+ days old" rule, both ported into `score_posts.py`.
- `wollongong-june-nightlife` (same folder) — a live events/recurring-nights
  calendar (venues, times, "Insta Slide Notes"). This is exactly the "venue
  calendar" input the (not-yet-built) `idea-generator` skill needs — check
  here before inventing event details, and never state a price/time from
  memory when this sheet (or a fresher one) has it.

## 2. Editorial voice

TODO — paste the existing PubCam voice guidelines here. Until this is filled in,
do not generate final captions/copy from scratch; draft options and flag them as
voice-unverified.

## 3. What works (living section)

This section is the agent's running memory of validated strategy. Update it only
when `/report` or `strategy_log` evidence supports a change — do not edit it on a
hunch.

Current strategy truths (seed values from the build spec — verify against actual
performance data before relying on them):

- Multi-venue carousel guides outperform single-venue promo reels.
- DM-share-optimised carousels are a strong format.
- 8–12 slide carousels are the sweet spot.
- Collab format is underleveraged for follower conversion.

## 4. Scoring model

**STATUS: CONFIRMED.** Ported from the real "PubCam Post Performance Model
v2" Google Sheet (Drive: PubCam/Business/Trackers & Spreadsheets), read
2026-07-15. This is the actual formula PubCam already uses, not a guess.

Implemented in [scripts/score_posts.py](scripts/score_posts.py) as a config
dict (`WEIGHTS`):

```
weighted_score = (likes * 1 + comments * 3 + saves * 4 + shares * 5 + follows * 6)
                  / reach * 1000
```

**Percentile is global** — every scored post is ranked against ALL other
scored posts in `posts`, not within its own format. This matches the source
sheet ("Score /100 = percentile rank against all your other posts"); a reel
and a carousel are compared directly.

**Rating bands** (also from the source sheet, stored in `posts.rating`):
90–100 A+ Banger, 75–89 A Strong, 50–74 B Solid, 25–49 C Below par (rework),
0–24 D Retire this approach.

**Scoring is pubcam.au-only.** The source sheet's own import instructions say
to skip posts not posted by pubcam.au: "collab posts from venue accounts have
hidden reach/saves and will score wrong." `score_posts.py` follows this —
posts from any other tracked account (or any post missing Reach) get
`scoring_excluded = 1` and `exclusion_reason = '[Collab post - limited
insights]'` (the exact tag `PubCam_Post_Tracker` already uses for these
rows). They're stored for reference but get no `weighted_score`/`percentile`
and must never be compared against real-reach pubcam.au scores.

**Age caveat:** the source sheet recommends only scoring posts once they're
7+ days old, since engagement is still accruing before that. `score_posts.py`
prints a caution (not a hard block) for any scored post younger than that —
treat those scores as provisional.

## 5. Rules

- **Never fabricate venue prices or event details.** If a post idea, caption, or
  report claim includes a price, date, or event detail, it must cite a source
  and the date that source was checked.
- Any idea containing an unverified factual claim is blocked from moving past
  `backlog` status in the `ideas` table — it cannot reach `approved` until the
  claim is fact-checked and the source is logged in `notes`.
- The agent proposes content and schedules; it never publishes. Posting is
  always a human action.
- When updating "What works" (Section 3), cite the evidence (e.g. a query
  against `posts`/`strategy_log`) that justifies the change.

## 6. Workflow definitions

Slash commands (see `.claude/commands/`):

- `/capture` — log a content idea or reference reel spotted elsewhere. Writes
  to `ideas` with `source = 'capture'`. **Implemented.**
- `/plan-week` — generate/update next week's schedule from approved ideas via
  the `schedule-builder` skill. **Implemented.**
- `/report` — performance summary vs. strategy, may propose edits to
  Section 3. **Implemented.**
- `/strategy` — log or review a strategy pivot in `strategy_log`.
  **Implemented.**

Skills (see `.claude/skills/`):

- `score-posts` — ingests a Meta Business Suite CSV from `inbox/`, computes
  weighted scores + percentiles, writes to `db/pubcam.db`. **Implemented.**
- `schedule-builder` — proposes a weekly schedule from approved ideas
  (`scripts/build_schedule.py`), dry-run by default. **Implemented** (cadence/
  ratio config is still a placeholder — see Section 4's Reach caveat sibling
  note and `config/schedule_slots.json`).
- `trend-sweep` — web research pass for PubCam-relevant content trends,
  writes candidates to `trends` (via `db.py add-trend`). **Implemented**
  (agent workflow; Phase 4 automation not yet wired).
- `idea-generator` — turns top/bottom posts + open trends + venue calendar
  into concrete post ideas with hook lines, written to the backlog.
  **Implemented** (hook lines are drafts until Section 2 voice is filled in).
- `develop-idea` — builds a production brief (hooks, shot list/slide layout,
  caption, improvement angles, fact-check list) for an approved idea, saved
  to the `briefs` table. Triggered automatically by the app when an idea is
  approved. **Implemented.**
- `build-post` — one-shot: rough idea in, finished PubCam-layout carousel
  out (default template: SAVE-THIS hook cover, one item per slide,
  screenshot-and-send payoff slide, outro, caption), saved as idea + brief
  in a single run. Optionally follows a dropped-in reference post's
  structure instead of the default (see `post_refs` below) — the default
  is a proven fallback, not a mandate. Triggered by the app's Post builder
  page. **Implemented.**
  [scripts/render_carousel.py](scripts/render_carousel.py) then turns that
  brief into actual 1080x1350 PNG slides in PubCam's real carousel style -
  full-bleed photo, dark scrim, Playfair Display/Sacramento type, the
  "PubCam." signature mark (fonts bundled in `assets/fonts/`, not a system
  dependency) - a deterministic script, not an agent call, so it's instant
  and free. Photos come from `assets/venue_photos/` - a shared library,
  organised by subfolder-per-venue or descriptive filenames, matched to
  each slide's venue/headline by word overlap (an exact per-slide override
  still works too, at `renders/idea_<id>/photos/slide_NN.jpg`). Slides
  with no match fall back to a dark placeholder with a "Photo needed"
  note. Photo files aren't committed (`.gitignore`); only
  `assets/venue_photos/README.md` and the folder are. Only understands
  build-post's `**Slide N (kind)**` format. **Implemented.**
- `build-reel` — one-shot: a saved reference reel (video file and/or link,
  plus the user's notes on what to copy — hook, pacing, structure) in,
  PubCam-branded reel script out (hooks, shot list with text overlays,
  caption), saved as idea + brief, linked back to the `reel_refs` row it
  came from. No vision step — works from the notes, not the video pixels.
  Triggered by the app's Reel builder page. **Implemented.**
- `competitor-scan` — scaffolded, not yet implemented (Phase 3, needs Meta
  developer app).

Weekly cadence (target, once Phase 4 automation is in place):

- Monday 8am — trend sweep + idea backlog refresh.
- Friday 9am — pull insights, score the week, write report.
- Monday morning (human) — `/plan-week`, approve/kill ideas.

## 7. Database

SQLite at `db/pubcam.db`, schema in [db/schema.sql](db/schema.sql). Tables:
`posts`, `ideas`, `schedule`, `trends`, `briefs`, `strategy_log`, `reel_refs`
(saved reference reels for `build-reel`), `post_refs` (saved reference post
structures for `build-post`) — both link to `ideas.id` once built.
Initialise/reset with `python db/init_db.py` (safe to re-run on an existing
database — `CREATE TABLE IF NOT EXISTS` only adds what's missing).

**Start with `python scripts/db.py digest`** when you need the current
picture - it returns posts/ideas/trends/schedule in one compact call
(~500 tokens) instead of 4+ separate list commands. Only run targeted list
commands for details the digest clips.

Use [scripts/db.py](scripts/db.py) for reads/writes to `ideas`, `schedule`,
and `strategy_log` (run `python scripts/db.py --help` for subcommands) rather
than hand-rolling SQL — it's what `/capture`, `/strategy`, and
`schedule-builder` are built on. `posts` writes go through
[scripts/score_posts.py](scripts/score_posts.py) only.

`config/schedule_slots.json` holds the recurring posting slots and
carousel:reel ratio `schedule-builder` uses — currently a placeholder, see
Section 4.
