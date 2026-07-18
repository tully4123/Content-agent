---
name: idea-generator
description: Turn performance data + open trends + the venue calendar into concrete post ideas with hook lines, written to the ideas backlog. Use when the user asks for post ideas or to refresh the backlog (Monday cadence, after trend-sweep).
---

# idea-generator

## Goal

Concrete, executable post concepts - each one something PubCam could film or
build this week, with a working hook line. Not themes, not "content pillars".

## Steps

1. Gather ALL inputs with one cheap call (do NOT run separate top-posts/
   list-trends/list-ideas commands - digest covers them at a fraction of the
   tokens):
   ```
   python scripts/db.py digest
   ```
   Only follow up with a targeted query (e.g. `list-trends` for one trend's
   full description and source URL) when the digest line isn't enough.
2. Add calendar context for the next 2-3 weeks: season (winter fireplace
   season, footy finals, uni semester/holidays, public holidays, State of
   Origin windows). If unsure whether an event is real/dated correctly,
   verify with WebSearch or leave it out - never build an idea on a guessed
   date (CLAUDE.md Section 5).
3. Generate 4-8 ideas. Good sources of shape:
   - **Double down**: a top-post format pointed at a new subject (the
     cheapest-schooners carousel pattern applied to feeds, function rooms,
     Sunday sessions...)
   - **Trend adaptation**: an open trend from step 1 recast for a venue
     partner or a PubCam guide
   - **Fix the flop**: a bottom-post subject that deserved better, in a
     format that historically works
4. Each idea needs:
   - `title`: format + concept in one line
   - a hook line (first words on screen / opening caption) in `notes`
   - `venue_fit`: PubCam original / Heyday / Illawarra / The Icon / multi-venue
   - `format`: reel / carousel / photo / collab
   - in `notes`: which evidence inspired it (post id, trend id, or calendar
     moment) and any fact that MUST be checked before posting (prices,
     dates, event details) flagged as `NEEDS FACT-CHECK: ...`
5. Write them:
   ```
   python scripts/db.py add-idea --title "..." --source performance-insight --venue-fit "..." --format "..." --notes "..."
   ```
   Use `--source trend-sweep` for trend-derived ideas, `--source
   performance-insight` for data-derived ones.
6. If an idea consumed a trend, mark it:
   ```
   python scripts/db.py mark-trend --id N --acted-on
   ```
7. Show the user the batch, grouped by venue, hooks first. Remind them ideas
   land in `backlog` and need approval (app Ideas page or
   `python scripts/db.py update-idea --id N --status approved`) before
   /plan-week picks them up. Never approve your own ideas (CLAUDE.md
   Section 5).

## Voice caveat

CLAUDE.md Section 2 (editorial voice) is still TODO. Until it's filled in,
mark hook lines as drafts - format/concept is the deliverable, exact wording
gets a human pass.
