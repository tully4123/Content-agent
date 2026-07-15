---
name: score-posts
description: Ingest a Meta Business Suite CSV from inbox/, compute weighted engagement scores and global percentiles (pubcam.au posts only), write results to db/pubcam.db, and report over/underperformers. Use when the user drops a new export into inbox/ or asks to score/rescore posts.
---

# score-posts

## When to use this

- A new Meta Business Suite CSV export has been dropped into `inbox/`.
- The user asks to "score posts", "run the weekly scoring", or similar.
- Called as part of the Friday cadence (see CLAUDE.md Section 6): pull
  insights → score-posts → report.

## Steps

1. Check `inbox/` for CSV files. If the user named a specific file, use it;
   otherwise use the most recently modified `*.csv`.
2. Run:
   ```
   python scripts/score_posts.py [path/to/file.csv]
   ```
3. Read the printed summary (overperformers / underperformers, rating
   letters, excluded-post count, young-post caution).
4. Summarise results for the user in plain language: which posts/venues/
   formats over- and under-performed, and any pattern worth a candidate
   `strategy_log` entry — but don't write to `strategy_log` yourself, hand
   that off to `/strategy`.
5. Do not fabricate or infer venue pricing/event details from the CSV data —
   captions are for context only, not a source of truth (CLAUDE.md Section
   5). Check `wollongong-june-nightlife` in Drive (CLAUDE.md Section 1) for
   real event/price details rather than guessing.

## Notes

- The script upserts on `post_id`, so re-running against the same export is
  safe and idempotent.
- **Scoring is confirmed methodology**, ported from the real "PubCam Post
  Performance Model v2" Google Sheet — see CLAUDE.md Section 4 for the full
  writeup (weights, global percentile, rating bands, age caveat).
- **Only pubcam.au posts get scored.** Posts from any other tracked account
  are stored with `scoring_excluded = 1` and tagged with the source sheet's
  own convention, `[Collab post - limited insights]` — reference data, not
  ranked. Never compare an excluded post's raw engagement against a scored
  post's weighted_score as if they were on the same scale.
- Percentile is **global** (all scored posts together), not within-format —
  a reel and a carousel are directly compared. This differs from earlier
  versions of this script; if you see old notes/reports saying "within
  format," they're stale.
- If the CSV headers don't match any known alias in
  `scripts/score_posts.py` (`COLUMN_ALIASES`), the script raises a clear
  error listing the headers it found. Add the new header spelling to the
  alias list rather than renaming the export.
- Real Meta Business Suite exports identify posts by `Account username`, not
  venue. The script maps username → venue via `ACCOUNT_TO_VENUE` in
  `scripts/score_posts.py` (mirrored in CLAUDE.md Section 1, names match
  `PubCam_Post_Tracker`'s existing venue labels). If it prints a "no venue
  mapping" warning for a new account, add it to that dict.
