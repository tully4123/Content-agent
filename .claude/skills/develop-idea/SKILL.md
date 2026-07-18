---
name: develop-idea
description: Build a full production brief for an approved idea - hook options, script/shot list or slide layout, caption draft, improvement angles, fact-check list. Saved to the briefs table. Use when an idea is approved (the app triggers this automatically) or the user asks to develop/build out an idea.
---

# develop-idea

Input: an idea id. Output: a production brief the team could shoot from today,
saved to the `briefs` table and shown to the user.

## Steps

1. Load context cheaply - two calls only:
   ```
   python scripts/db.py digest
   python scripts/db.py list-ideas --status approved
   ```
   (digest gives the performance picture; the list call gives this idea's
   full title/notes - the hook or evidence noted at capture time is the
   seed.) Add `top-posts --format <fmt> --limit 3` ONLY if the digest's top
   posts don't already cover the idea's format.
2. Write the brief as markdown with EXACTLY these sections:

   ```markdown
   # <idea title>
   *Format: <format> | Venue: <venue_fit> | Idea #<id> | Brief drafted <date>*

   ## Hooks (pick one)
   - 3 hook options: first line on screen / opening caption. Punchy,
     PubCam-casual. Mark each with the angle it plays (curiosity / value /
     FOMO).

   ## Build
   - For a REEL: numbered shot list (5-10 shots) - what to film, rough
     duration, any text overlay per shot, suggested cut style. Note if
     trending audio applies (cite the trend id if one inspired this).
   - For a CAROUSEL: slide-by-slide layout (aim 8-12 slides - CLAUDE.md
     Section 3) - slide text + visual per slide, with the save/share payoff
     slide called out.
   - For a PHOTO/COLLAB: composition, who's tagged, collab mechanics.

   ## Caption draft
   - One caption ready to paste, plus CTA line (save/share/comment bait
     matched to what this format converts best).

   ## Make it hit harder
   - 3-4 specific improvement angles: timing (day/slot), collab tag
     opportunities, cross-post to venue account, remix potential, a
     follow-up post it could set up.

   ## Before you post
   - Every fact in this brief that needs verification (prices, times,
     event dates, venue details) as a checklist. If notes contained
     'NEEDS FACT-CHECK', it appears here. If nothing needs checking,
     say so explicitly.
   ```

3. Voice: CLAUDE.md Section 2 is still TODO - until filled in, write hooks/
   captions in the register visible in the top posts' own captions (casual,
   emoji-light, direct address, local slang OK) and add one line at the top
   of the brief: "*Voice guidelines pending - wording is a draft.*"
4. NEVER invent prices, event dates, or venue details (CLAUDE.md Section 5).
   Where one is needed, write `[CHECK: ...]` in place and list it in
   "Before you post".
5. Save the brief: write it to a temp file, then
   ```
   python scripts/db.py add-brief --idea-id <id> --file <tempfile>
   ```
6. Print the full brief for the user, then note: it's saved to the idea and
   visible on the app's Ideas page under the idea.

## Non-interactive rule

When run headlessly (from the app's approve button), never ask questions -
make the best call from the idea notes and top-post patterns, and flag
uncertainty in the brief itself.
