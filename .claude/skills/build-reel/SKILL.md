---
name: build-reel
description: Turn a saved reference reel (a video/link the user dropped in, plus their notes on what to copy) into a PubCam-branded reel script - hook, shot list, text overlays, caption - saved as an idea + brief in one run. Use when the user builds from a reference in the app's Reel builder page.
---

# build-reel

Input: a `reel_refs` row id - a reference the user saved (a video file and/or a
source URL, plus their own notes on what they liked and want copied: the hook
style, pacing, structure, a specific mechanic). Output: a shootable reel script
in that style, using PubCam's own venues and content, saved to the database.

**You cannot watch the video file.** There is no vision step in this pipeline -
work from the user's notes describing what to copy, not from the file itself.
If the notes are thin (e.g. just "like this"), do your best with the source
URL and flag in the brief that the style read is a guess from limited
information.

## Steps

1. Load context cheaply - two calls:
   ```
   python scripts/db.py digest
   python scripts/db.py get-reel-ref --id <ref_id>
   ```
   The digest's top reel performers and open backlog stop you duplicating an
   existing idea or reinventing a format PubCam's own data already validates.
2. If `source_url` is set and looks fetchable (a public article, YouTube,
   TikTok - not an Instagram permalink, which reliably blocks fetches), ONE
   WebFetch to see what it's about. Skip silently if it fails or isn't set -
   never block on this.
3. Write the brief as markdown, reusing develop-idea's REEL section structure:

   ```markdown
   # <short title for the reel>
   *Format: reel | Venue: <venue_fit> | Built from reel_ref #<ref_id> | <date>*

   *Style reference: <one line - what this reel is copying from the saved
   reference, per the user's notes. e.g. "the countdown-style text-overlay
   reveal, per the saved note."> Voice guidelines pending - wording is a draft.*

   ## Hooks (pick one)
   - 3 hook options: first 1-2 seconds on screen. Punchy, matches the
     reference's opening beat where the notes describe one.

   ## Shot list
   - Numbered shots (5-10), each with: rough duration, what to film, any
     on-screen text overlay, cut style. Follow the structure/pacing the
     reference notes describe - that's the whole point of building from a
     reference, don't default to a generic template if the notes are
     specific.
   - Trending audio: only name a specific sound if the source URL or notes
     actually said so. Otherwise write `[CHECK: pick a current trending
     sound - don't invent one]`.

   ## Caption draft
   - One caption ready to paste, plus CTA line.

   ## Make it hit harder
   - 2-3 angles specific to this reel: timing, collab tag, remix potential.

   ## Before you post
   - Every `[CHECK: ...]` from the brief, plus: venue/price/date facts
     (CLAUDE.md Section 5 - never invent these).
   ```
4. Save as idea + brief, then link the reference back to the new idea:
   ```
   python scripts/db.py add-idea --title "Reel: <short title>" --source capture --venue-fit "<fit>" --format reel --notes "<one-line summary + style reference + NEEDS FACT-CHECK items>"
   python scripts/db.py add-brief --idea-id <new id> --file <tempfile>
   python scripts/db.py link-reel-ref --id <ref_id> --idea-id <new id>
   ```
5. Print the full build as your final message, and note: it's saved in Ideas
   (backlog - approve it there to queue it for scheduling; the brief is
   already attached).

## Rules

- Shell-quote titles/notes containing `$` the same way build-post does.
- Non-interactive: never ask questions; make the best grounded call from the
  notes and flag gaps in the brief itself.
- Do not approve the idea yourself (CLAUDE.md Section 5).
- Keep it cheap: digest + get-reel-ref + at most one WebFetch + the three
  save/link calls is the whole footprint.
