---
description: Log a content idea or reference reel you spotted elsewhere
argument-hint: [link or description]
---

Log a content idea into the `ideas` table (`source = 'capture'`).

## Steps

1. If `$ARGUMENTS` is a link, note it in `notes` and, if you can fetch it,
   summarise what it is (platform, format, what makes it worth capturing). If
   `$ARGUMENTS` is a description rather than a link, work with that directly.
   If `$ARGUMENTS` is empty, ask the user what they saw.
2. Fill in the required fields — ask the user for anything you can't infer:
   - `title` — short, specific (e.g. "Reel: DJ transitions overlaid on venue walkthrough")
   - `venue_fit` — which venue partner(s) this suits, or "multi-venue" / "unclear"
   - `format` — reel / carousel / image / collab
   - `notes` — source link, why it's worth doing, any fact that would need
     checking before this could ship (CLAUDE.md Section 5 — never fabricate
     prices or event details; if the idea depends on one, say so explicitly
     in notes rather than stating it as fact)
3. Run:
   ```
   python scripts/db.py add-idea --title "..." --source capture --venue-fit "..." --format "..." --notes "..."
   ```
4. Confirm to the user what was logged and its id. It lands in `backlog` —
   remind them it needs `/strategy` or manual approval (via
   `python scripts/db.py update-idea --id N --status approved`) before
   `schedule-builder`/`/plan-week` will pick it up.

Do not mark an idea `approved` yourself during `/capture` — that's a
deliberate human decision (CLAUDE.md Section 5).
