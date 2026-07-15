---
description: Log or review a strategy pivot
argument-hint: [insight / decision, or "review"]
---

Log or review entries in `strategy_log`, and optionally propose an update to
CLAUDE.md Section 3 ("What works").

## If reviewing (`$ARGUMENTS` is empty, "review", or a question)

Run `python scripts/db.py list-strategy` and summarise the log for the user —
chronological, most recent first. If they ask whether Section 3 of CLAUDE.md
still matches the logged evidence, compare and flag any drift.

## If logging a new pivot

1. From `$ARGUMENTS` and any follow-up questions, establish:
   - `insight` — what was observed (should cite evidence: a query result from
     `python scripts/db.py top-posts` / `bottom-posts`, a report finding, etc.
     Do not log an insight that isn't backed by something checkable —
     CLAUDE.md Section 5's fact-check rule applies to strategy claims too.)
   - `decision` — what changes as a result (e.g. "shift ratio to 2 carousels
     : 1 reel per week")
   - `evidence` — the specific numbers/query that support it
2. Run:
   ```
   python scripts/db.py add-strategy --insight "..." --decision "..." --evidence "..."
   ```
3. If the decision should change the "What works" section, propose the exact
   edit to CLAUDE.md Section 3 and show it to the user — do not apply it
   without confirmation, since that section drives future agent behaviour.
