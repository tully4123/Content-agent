---
name: schedule-builder
description: Generate a proposed weekly posting schedule from approved ideas, respecting recurring slots and format ratio from config/schedule_slots.json. Use when the user asks to build/propose next week's schedule (also invoked by /plan-week).
---

# schedule-builder

## Steps

1. Run a dry run first:
   ```
   python scripts/build_schedule.py [--week-start YYYY-MM-DD]
   ```
   (`--week-start` defaults to next Monday; must be a Monday if given.)
2. Show the proposed schedule to the user. Call out:
   - Any slot with `note:` — means either no approved idea existed in that
     slot's target format (backlog idea used instead) or slots ran out of
     approved ideas entirely.
   - Any approved ideas left over that didn't fit this week.
3. **Do not commit without explicit confirmation.** Once the user approves
   (or asks for changes and you re-run the dry run), commit with:
   ```
   python scripts/build_schedule.py --week-start YYYY-MM-DD --commit
   ```
   This inserts `schedule` rows (`status='proposed'`) and flips the used
   ideas to `status='scheduled'`.

## Known limitations (be upfront about these when presenting a proposal)

- `config/schedule_slots.json` (`recurring_slots`, `default_format_ratio`) is
  a **placeholder** — the actual posting cadence and carousel:reel ratio
  haven't been confirmed. Ask the user to confirm or correct it before
  relying on this for real scheduling; update CLAUDE.md Section 4's "What
  works" section to match once it's confirmed.
- Ideas are assigned FIFO by `id`; `priority` on the `ideas` table isn't used
  yet (no defined priority scale exists). If priority ordering matters, sort
  the backlog manually before running this, or ask the user how they want
  priority defined and extend `scripts/build_schedule.py`.
- Venue-adjacency smoothing is a single best-effort pass, not an optimizer —
  spot-check the proposal rather than trusting it blindly on a large backlog.
