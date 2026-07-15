---
description: Generate next week's posting schedule from approved ideas
argument-hint: [optional week-start date, YYYY-MM-DD Monday]
---

Run the weekly planning flow:

1. Run `python scripts/db.py list-ideas --status backlog` and show the user
   what's waiting for a decision — give them the chance to approve/kill
   before building the schedule (`python scripts/db.py update-idea --id N
   --status approved|killed`).
2. Invoke the `schedule-builder` skill (dry run) for the target week — use
   `$ARGUMENTS` as `--week-start` if provided, otherwise default (next
   Monday).
3. Walk the user through the proposal, note any caveats it surfaces
   (placeholder cadence/ratio, leftover approved ideas, format-mismatch
   slots).
4. If they approve, commit it (`--commit`). If they want changes (swap a
   slot, different idea), make the change and re-run the dry run before
   committing.
5. After committing, ask if they want it pushed to Drive for Jack and
   Dakota (`drive-sync` skill / `/sync-drive`). Don't run it automatically —
   it creates a new file visible to the team each time (see that skill's
   caveat about not being able to edit/delete existing Drive files).
