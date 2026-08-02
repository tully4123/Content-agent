# Marketing ops layer — proposal

Status: **deferred.** What actually got built first is much smaller: a
Notion-style notes centre — one markdown file per note under
[ops/notes/](../ops/notes/), managed from the app's Notes page or by hand,
referenced from CLAUDE.md as a context source. No CLI or task/performance-
log machinery. Everything below is the fuller system, still here for
if/when that's actually wanted; it hasn't been built.

## 0. The one decision that affects existing, working code

`scripts/score_posts.py` already implements the exact model this brief
asks for — weighted engagement formula, global percentile rank, rating
bands — confirmed against the real "PubCam Post Performance Model v2"
sheet, and the whole Streamlit app (Dashboard, `db.py digest`,
`voice-sample`, the Post builder's fact-check context) already reads its
output from `db/pubcam.db`'s `posts` table.

The brief's rule is "no external database, no server" for the ops layer.
I don't think that's asking to rip out SQLite from a working app — I think
it's asking for the ops layer's **source of truth** to be files. Those are
compatible if SQLite stops being a store of record and becomes a
**rebuildable cache**:

- `ops/performance-log/*.json` becomes the source of truth — git-diffable,
  hand-readable, works offline, no server.
- `score_posts.py` gets refactored to write there instead of (well, now:
  as well as) directly to SQLite.
- `db/pubcam.db`'s `posts` table becomes a generated artifact, rebuilt
  from the JSON log on demand — the existing app keeps working unchanged,
  and the database could be deleted and regenerated from the JSON files
  at any time without losing anything. That's the actual test of "is this
  a cache or a store of record."

The alternative — two independent implementations of the same scoring
formula, one in Python writing JSON, one in Python writing SQL — is a
correctness risk (they will eventually disagree) for no real benefit. I'd
rather refactor the one that exists than duplicate it.

**One consequence of this**: I'm proposing percentile and rating band are
**never stored** in the JSON files — only computed live, at report/query
time, from the full historical log. Percentile is a function of the
*entire* pool (every scored post ranks against every other one, per
CLAUDE.md §4), so it can't correctly live as a static field on one
record — adding one new post shifts everyone else's percentile too. The
`weighted_score` itself is safe to store (it's a pure function of that
post's own metrics), but percentile/rating are computed fresh each time,
same as a `git blame` is computed, not stored. At the current data volume
(dozens to low hundreds of posts) this is instant.

Flag anything in this section you want done differently before I build
against it — everything below assumes this resolution.

## 1. Directory structure

```
ops/
  weekly-plan/
    _recurring-template.md     standing recurring tasks, materialised into new weeks
    2026-08-03.md               one file per week, named by week-start Monday
    2026-08-10.md
  venues/
    the-icon.md
    illawarra-hotel.md
    heyday.md
    pubcam.md                   PubCam's own-brand content, treated as a "venue"
    the-grand.md                prospect
    debutant.md                 prospect
  performance-log/
    2026-06-28.json              one file per ingestion, named by ingestion date
    2026-07-19.json
scripts/
  ops.py                        new CLI (separate from db.py — different data, different job)
```

`ops/` sits alongside `db/`, `scripts/`, `app_pages/` at the repo root.

## 2. Format choice per file type

The brief allows markdown and JSON; not YAML. Given "hand-editable is a
hard requirement," I'm splitting by who actually writes each file:

- **Weekly plan + venue records + recurring template: markdown.** These
  are hand-authored/hand-edited by a person. A stray markdown typo breaks
  nothing outside itself; a stray missing JSON comma breaks the whole
  file's parse. I'm using the same "heading + `- Key: value` lines" block
  convention this repo already uses for carousel briefs (`build-post`'s
  slide format) — it's proven to be both easy to hand-edit and reliable to
  parse, so the ops layer stays consistent with how the rest of the repo
  already does this rather than inventing a second convention.
- **Performance log: JSON.** These records are produced by ingesting a
  CSV, not typed by hand — JSON's rigidity is a feature here, not a
  hand-editing risk, and it's what "structured data to query across
  venues and formats" actually wants.

## 3. Worked example — weekly plan

`ops/weekly-plan/2026-08-03.md`:

```markdown
# Week of 2026-08-03

## Post the Icon price index carousel

- Type: Social Post
- Venue: The Icon
- Day: Monday
- Time slot: After 3pm
- Status: Not started
- Recurring: no
- Notes: Confirm current menu prices with the venue before publishing.

## Film Heyday weekend crowd

- Type: In-Venue Filming
- Venue: Heyday
- Day: Weekend
- Time slot: After 3pm
- Status: Not started
- Recurring: no
- Notes:

## Weekly performance check-in

- Type: Performance Check-in
- Venue: PubCam
- Day: Monday
- Time slot: All day
- Status: Not started
- Recurring: yes
- Notes: Score the week's CSV export, review top/bottom posts.
```

`Week` isn't repeated per-task — it's the file itself (name + `# Week of
...` heading), so there's exactly one place it can go stale.

The recurring template it's materialised from,
`ops/weekly-plan/_recurring-template.md`:

```markdown
# Recurring tasks

Materialised into every new week by `scripts/ops.py scaffold-week`. Edit
here to add/remove/change a standing recurring task — hand-editing a
single week's copy of a recurring task won't change future weeks.

## Weekly performance check-in

- Type: Performance Check-in
- Venue: PubCam
- Day: Monday
- Time slot: All day
- Status: Recurring
- Recurring: yes
- Notes: Score the week's CSV export, review top/bottom posts.
```

This is why the brief's `Status` enum has a `Recurring` value distinct
from the `Recurring` boolean field: `Status: Recurring` marks a row in the
*template* as a standing definition, not an actionable task. When
`scaffold-week` materialises it into an actual week, the copy gets
`Status: Not started` (a real, actionable status) and keeps `Recurring:
yes` as provenance — that's the field doing its own, different job.

## 4. Worked example — venue record

`ops/venues/the-icon.md`. Every field left genuinely blank where the
answer isn't known — nothing here is invented:

```markdown
# The Icon

Status: active partner

## Contact
- Decision maker:
- Best way to reach them:

## Recurring nights & events
-

## Content supply
- They can supply:
- We capture:

## Filming access
- Can we film freely without per-visit approval?

## Instagram
- Handle:
- Reshares our collab posts?

## Highlights
<!-- Hand-picked standout posts worth remembering *why* they worked.
     Reference the post_id from the performance log - don't copy full
     stats here, that's what `ops.py report --venue "The Icon"` is for. -->
-
```

The "what's performed there" requirement is deliberately **not** a
hand-maintained list in this file — that would drift out of sync with the
performance log the moment a new CSV is scored. It's a live query
(`report --venue`). The "Highlights" section is the one place for
genuinely hand-written color a query can't produce ("this worked *because*
—"), referencing a `post_id`, not duplicating its numbers.

## 5. Performance log

`ops/performance-log/2026-07-26.json` — one file per ingestion run:

```json
{
  "ingested_at": "2026-07-26",
  "source_csv": "Jun-19-2026_Jul-16-2026_1447919373764443.csv",
  "posts": [
    {
      "post_id": "18098948665937513",
      "account": "pubcam.au",
      "venue": "PubCam",
      "format": "carousel",
      "posted_at": "2026-06-28",
      "caption": "Save this post for next time you are going out on a budget, the cheapest schooners in Wollongong 🔥 #pubcam #wollongongnightlife",
      "reach": 12253,
      "likes": 0,
      "comments": 0,
      "saves": 102,
      "shares": 686,
      "follows": 36,
      "weighted_score": 365.14,
      "scoring_excluded": false,
      "exclusion_reason": null
    }
  ]
}
```

No `percentile`/`rating` fields — see §0. Re-ingesting a CSV is safe:
`ingest-csv` checks every row's `post_id` against **every** existing
performance-log file first; if it's already recorded (numbers have
changed since a re-export, or it's just cleared the 7-day hold), it's
updated in place in whichever file it already lives in. Only genuinely new
posts get appended to today's file. Old batch files do sometimes get a
diff from this — that's correct, the underlying data changed, the diff
should show it.

## 6. CLI (`scripts/ops.py`)

```
scaffold-week [--week-start YYYY-MM-DD]     materialise recurring tasks into a new week (defaults: next Monday)
add-task --week <date> --task "..." --type "..." --venue "..." --day "..." --slot "..." [--notes "..."]
update-task --week <date> --task "<title>" [--status ...] [--notes ...]
complete-task --week <date> --task "<title>"
show-week [--week <date>] [--venue <name>]   pretty-printed table to the terminal
ingest-csv <path>                             score a Meta export, upsert into the performance log
report top-posts [--venue] [--format] [--limit]
report by-venue
report by-format
```

`show-week`/`report` print tables to the terminal — the on-disk files stay
in the plain block format from §3 for reliable hand-editing; the CLI is
what gives you the scannable table view, not the file itself.

This is a new, separate script from `scripts/db.py` — different data
(files vs. `db/pubcam.db`), different job. It doesn't touch `ideas`,
`briefs`, `schedule`, or `trends` — the content-generation pipeline
(Post/Reel builder, `develop-idea`, etc.) is out of scope for this brief
and stays exactly as it is.

## 7. What I'm not building

Matching the brief's own discipline about the Notion audit: no fields
beyond what's listed, no speculative "gap rating"-style scoring, no
attempt to backfill venue contact info that isn't already known. Blank
stays blank.

## 8. Sign-off

If §0's cache/source-of-truth resolution and the formats above look
right, say so and I'll scaffold `ops/` (including the six venue files,
genuinely blank), refactor `score_posts.py` to write the JSON log first
and rebuild SQLite from it, and build `scripts/ops.py`. If anything here
should change, tell me which section and I'll revise before writing
anything executable.
