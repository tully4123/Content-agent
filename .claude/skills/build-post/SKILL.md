---
name: build-post
description: Turn a rough one-line idea into a finished PubCam-layout carousel build (slide-by-slide, caption, fact-check list), saved as an idea + brief in one run. Optionally follows a dropped-in reference post's structure instead of the default template. Use when the user gives a basic post idea and wants it built out immediately (the app's Post builder page triggers this).
---

# build-post

Input: a rough idea in plain words (e.g. "cheapest parmas in the gong",
"where to watch the footy Sunday"), and optionally a `post_ref` id if the
user dropped in a reference post to copy the structure of. Output: a
complete carousel build the team could design and post today, saved to the
database.

## The PubCam carousel layout (default template)

Used whenever no `post_ref` is given. Derived from PubCam's proven top
performers (the cheapest-schooners and date-night guides - both A+,
save/share monsters). Follow it exactly; do not invent a new structure:

1. **Cover slide** - bold hook with save-framing. Top performers open with
   a direct command: "SAVE THIS..." / "Save this post for...". One line,
   high contrast, no clutter.
2. **Item slides (slides 2 to N-2, aim 8-12 slides total)** - ONE item per
   slide (one venue, one deal, one spot). Each slide: item name + one
   detail line + visual note for the designer. Prices/times/details you
   cannot verify are written as `[CHECK: ...]`, never invented.
3. **Payoff slide (second-last)** - the full list on one clean graphic:
   every item + key detail on a single slide. This is the
   screenshot-and-send-to-the-group-chat slide - it must stand alone in a
   DM. Text: "Send this to the group chat 📍" or similar.
4. **Outro slide** - PubCam logo, "Follow @pubcam.au" + one line on what's
   coming next.

**Caption** (default pattern): open with the save command ("Save this
for..."), one line of what the guide covers, close with group-chat share
bait. End with #pubcam #wollongongnightlife. Voice: casual, direct address,
emoji light (CLAUDE.md Section 2 is still TODO - mark wording as draft).

## Building from a reference structure (post_ref given)

If a `post_ref` id is passed in, this build is not the default template -
the user dropped in a post they liked (an image and/or a link) and wrote a
note describing its structure. Read it first:

```
python scripts/db.py get-post-ref --id <post_ref_id>
```

`notes` is the structure to copy - a Q&A format, a ranked countdown, a
this-or-that comparison, whatever it is. If `source_url` is set and looks
fetchable, ONE WebFetch to see what it's about - skip silently on failure
or if it's an Instagram permalink (reliably blocked), never block on it.
There's no vision step here either - a `notes`-described image isn't
analysed, only read as written.

Build to that structure instead of the default template above - the
default is PubCam's proven fallback, not a mandate, once the user has shown
you what they actually want. Still required regardless of structure:
- The same **Slide N (kind)** format below (the renderer depends on it) -
  map the reference's beats onto Cover / item / Payoff / Outro slides
  however they best fit. A countdown reference might use N item slides
  counting down instead of one item per venue; a Q&A reference might put
  the question in Text/Venue and the answer in Detail. Only add a Payoff
  slide if the referenced structure actually has a summary beat - it's not
  mandatory outside the default template.
- PubCam's own venues/content, and the same fact-check discipline (CLAUDE.md
  Section 5) - never invent a price, date, or detail the reference used;
  mark anything unverifiable `[CHECK: ...]`.
- The save/share caption spirit, unless copying the reference's own caption
  style is explicitly part of what the notes asked for.

After saving the idea + brief (step 3 below), link the reference back:
```
python scripts/db.py link-post-ref --id <post_ref_id> --idea-id <new id>
```

If no `post_ref` id is passed, skip this whole section and follow the
default template above.

## Steps

1. `python scripts/db.py digest` - one call for context (top performers,
   open trends, existing backlog - don't duplicate an existing idea; if the
   requested idea closely matches one, build THAT idea instead and say so).
   If a `post_ref` id was given, also run `get-post-ref` per above.
2. Build the carousel per the default layout above, or the reference
   structure if a `post_ref` was given. Item selection: use only
   venues/facts you can ground - PubCam's venue partners (The Icon,
   Illawarra Hotel, Heyday) can anchor the list; wider Wollongong venues
   are fine if the item detail is marked `[CHECK: ...]`. NEVER invent
   prices, times, or event details (CLAUDE.md Section 5).
3. Save it as an idea + brief in one run:
   ```
   python scripts/db.py add-idea --title "Carousel: <short title>" --source capture --venue-fit "<fit>" --format carousel --notes "<one-line summary + NEEDS FACT-CHECK items>"
   ```
   then write the full build to a temp markdown file and:
   ```
   python scripts/db.py add-brief --idea-id <new id> --file <tempfile>
   ```
   If a `post_ref` id was given, also run the `link-post-ref` call above now
   that you have the new idea id.
   The brief markdown: title line, the slides numbered with text + visual
   note each, the caption, and a final "## Before you post" checklist of
   every `[CHECK: ...]` item.
4. Print the full build as your final message, and note: it's saved in the
   Ideas page (backlog - approve it there to queue it for scheduling; the
   brief is already attached). The app can then render the slides as actual
   PNGs (`scripts/render_carousel.py`) - see the exact format rule below,
   it depends on this.

## Slide format (exact - the renderer parses this)

`scripts/render_carousel.py` turns this brief straight into PNG images, so
the per-slide format below is a contract, not a style suggestion:

```
**Slide <N> (Cover|Payoff|Outro)**   <- omit the "(...)" for ordinary item slides
- Text: "..."          <- cover/payoff/outro headline
- Venue: ...           <- item slides: use Venue instead of Text for the headline
- Detail: ...          <- item slides: the one detail line
- Visual: ...          <- or "Visual note:" - designer's shot note, either key works
```

Always start each field with `- Key: value` on its own line, one blank line
between slides, and put `[CHECK: ...]` inline in Text/Venue/Detail (never in
Visual) so the renderer's fact-check highlighting catches it. Don't rename
the keys or collapse a slide onto one line - a slide the renderer can't
parse just gets silently skipped from the images.

## Rules

- **Shell quoting:** titles and notes often contain `$` (prices). Always
  single-quote those arguments (`--title 'Carousel: feeds under $20'`) so
  the shell doesn't expand them into garbage.

- Non-interactive: never ask questions; make the best grounded call and
  flag uncertainty in the build itself.
- Do not approve the idea yourself (CLAUDE.md Section 5).
- Keep it cheap: digest + add-idea + add-brief (+ get-post-ref/link-post-ref
  when a reference is given) is the whole database footprint; no web
  research unless the idea explicitly needs a current fact verified, or a
  reference's source_url is being read (max 1 search either way).
