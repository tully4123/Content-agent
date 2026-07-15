---
name: drive-sync
description: Push the current schedule (and optionally the ideas backlog) to Google Drive as a Sheet, so Jack and Dakota can see it without the terminal. Use when the user asks to sync/share the schedule, or as the optional final step of /plan-week.
---

# drive-sync

Target folder: **PubCam / Business / Trackers & Spreadsheets**
(`parentId = '1rj3_PMv7xpi6Me44NR0dnVc6kTff6nVL'`) — confirmed 2026-07-15 as
where the existing `PubCam_Post_Tracker` and Performance Model sheets live.

## Known limitation — read this before running

The Google Drive MCP connection can **create new files** and **read/search**
existing ones, but it **cannot edit an existing file's content or delete
files**. There is no true "sync into one living tracker." What this actually
does each run: create a brand-new Google Sheet with a fixed title
(`PubCam Schedule - Latest`), so it's always findable by name — but if one
already exists from a previous run, it is **not replaced**. Always search
first and tell the user about the old one so they can trash it manually.

## Steps

1. Generate the current schedule as CSV:
   ```
   python scripts/export_schedule.py --format csv
   ```
   Read the resulting file's contents.
2. Search for a previous sync:
   ```
   search_files query: title = 'PubCam Schedule - Latest' and parentId = '1rj3_PMv7xpi6Me44NR0dnVc6kTff6nVL'
   ```
   If found, note its `viewUrl` — you'll surface this to the user after
   creating the new one, since you can't delete it yourself.
3. Create the new Sheet:
   ```
   create_file:
     title: "PubCam Schedule - Latest"
     parentId: "1rj3_PMv7xpi6Me44NR0dnVc6kTff6nVL"
     textContent: <the CSV content from step 1>
     contentMimeType: "text/csv"
   ```
   (CSV auto-converts to a native Google Sheet — don't set
   `disableConversionToGoogleType`.)
4. Report back to the user: the new file's `viewUrl`, and — if step 2 found
   a prior version — that link too, with an explicit note that they should
   trash the old one themselves (link: `https://drive.google.com/file/d/<id>/view`
   or open it and use Drive's trash action).
5. Do not run this automatically/unattended — it's visible to Jack and
   Dakota (a shared surface), so only run it when the user explicitly asks
   or confirms at the end of `/plan-week`.

## Notes

- Do not create a new folder or guess at a different target — this folder
  was confirmed by inspecting the user's actual Drive structure, not
  invented.
- If the user later wants the ideas backlog synced too, follow the same
  pattern with `python scripts/db.py list-ideas` output converted to CSV and
  a title like `PubCam Ideas Backlog - Latest`.
