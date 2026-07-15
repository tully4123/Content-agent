---
description: Performance summary vs. strategy
argument-hint: [optional focus, e.g. "carousels" or "Heyday"]
---

Produce a performance report and, where evidence supports it, propose
updates to CLAUDE.md Section 3 ("What works").

## Steps

1. If there's a new CSV in `inbox/` that hasn't been scored yet, run the
   `score-posts` skill first.
2. Pull the current picture (scored = pubcam.au posts only; see CLAUDE.md
   Section 4):
   ```
   python scripts/db.py top-posts --limit 10
   python scripts/db.py bottom-posts --limit 10
   ```
   For the excluded posts (`scoring_excluded = 1`, tagged
   `[Collab post - limited insights]` — Heyday/Illawarra accounts etc.),
   query `posts` directly for raw engagement if the user wants a read on
   those, but never compare their numbers against a `weighted_score` as if
   on the same scale — they were excluded because their Reach/Saves aren't
   reliable (CLAUDE.md Section 4).
3. Compare what you see against CLAUDE.md Section 3's current strategy
   truths (multi-venue carousels vs. single-venue reels, DM-share carousels,
   8-12 slide sweet spot, collab underleveraged). Does the data support,
   contradict, or say nothing about each claim?
4. If `$ARGUMENTS` names a focus (a format, a venue), lead with that; still
   cover the overall picture.
5. Write the report to `reports/YYYY-MM-DD-report.md` (use today's date).
   Structure: headline findings (with rating letters, e.g. "A+"), strategy-
   truth confirmations/contradictions, a note on excluded posts if relevant.
6. If you found evidence that should update Section 3 or log a pivot, don't
   edit CLAUDE.md directly — propose the exact wording change and/or a
   `python scripts/db.py add-strategy ...` call, and ask the user to confirm
   (this is what `/strategy` is for; you can hand off to it).
7. Do not state a specific numeric claim (price, follower count, event
   detail, etc.) as fact unless it's a direct read from `posts`/`schedule`
   or the `wollongong-june-nightlife` Drive sheet (CLAUDE.md Section 1) —
   CLAUDE.md Section 5.
