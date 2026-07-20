"""Render a build-post brief's carousel slides into PNG images.

Reads the "**Slide N (kind)**" blocks the `build-post` skill writes into
`briefs.content`, and draws each one in PubCam's real carousel style: a
full-bleed photo, a dark scrim for legibility, and Playfair Display /
Sacramento typography with the "PubCam." signature mark - matching the
brand's actual Instagram carousels, not a generic template.

Photos, in priority order:
1. renders/idea_<id>/photos/slide_<NN>.jpg (or .png/.jpeg/.webp) - an exact
   override for one slide of one build.
2. assets/venue_photos/ - a shared library the renderer picks from
   automatically. Organise it however's convenient: subfolders per venue
   (assets/venue_photos/Heyday/*.jpg) or just descriptively named files in
   one folder (heyday_bar_1.jpg) - matching is by word overlap between the
   folder/file name and the slide's venue/headline, so "Heyday" matches
   "heyday_bar_1.jpg" or a "Heyday/" folder either way. Cover/payoff/outro
   slides (no single venue) get a photo from the library too, picked to
   avoid repeats within the same build.
3. A dark placeholder background with a small "Photo needed" note, if
   neither above has anything usable - so a build is postable-as-a-mockup
   immediately and upgrades to real photography with zero code changes.

Usage:
    python scripts/render_carousel.py --idea-id 6
    python scripts/render_carousel.py --brief-id 2

Output: renders/idea_<id>/slide_01.png, slide_02.png, ...

Only understands the build-post skill's slide format (see that SKILL.md).
Freeform briefs from develop-idea won't have "**Slide N**" blocks and will
raise a clear error rather than guessing at a layout.
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "db" / "pubcam.db"
RENDER_DIR = REPO_ROOT / "renders"
FONT_DIR = REPO_ROOT / "assets" / "fonts"
PHOTO_LIBRARY = REPO_ROOT / "assets" / "venue_photos"

W, H = 1080, 1350
MARGIN = 90

ACCENT = (224, 90, 66)          # warm coral - the signature dot + fact-check flag colour
INK_SHADOW = (8, 9, 12)
WHITE = (255, 255, 255)
BODY_WHITE = (238, 238, 233)
NOTE_MUTED = (172, 178, 192)

SERIF = FONT_DIR / "PlayfairDisplay-Regular.ttf"
SERIF_MEDIUM = FONT_DIR / "PlayfairDisplay-Medium.ttf"
SERIF_SEMIBOLD = FONT_DIR / "PlayfairDisplay-SemiBold.ttf"
SERIF_ITALIC = FONT_DIR / "PlayfairDisplay-Italic.ttf"
SCRIPT = FONT_DIR / "Sacramento-Regular.ttf"

PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    key = (str(path), size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    font = ImageFont.truetype(str(path), size)
    _FONT_CACHE[key] = font
    return font


# ------------------------------------------------------------------ parsing

SLIDE_RE = re.compile(r"\*\*Slide\s+(\d+)\s*(?:\(([^)]*)\))?\*\*[ \t]*\n((?:-[^\n]*\n?)+)")
FIELD_RE = re.compile(r"^-\s*([^:]+):\s*(.*)$")

# The bundled fonts have no colour-emoji glyphs, so pictographs render as
# tofu boxes. Strip them from rendered text (captions elsewhere keep the
# emoji - this only affects the PNGs).
_EMOJI_RANGES = "".join([
    chr(0x1F000), "-", chr(0x1FFFF),
    chr(0x2600), "-", chr(0x27BF),
    chr(0x1F1E6), "-", chr(0x1F1FF),
    chr(0xFE0F),
])
EMOJI_RE = re.compile("[" + _EMOJI_RANGES + "]+")


def _clean(value: str) -> str:
    value = value.strip().strip('"').strip("'").strip()
    value = EMOJI_RE.sub("", value)
    return re.sub(r"\s{2,}", " ", value).strip()


def parse_slides(content: str) -> list[dict]:
    content = content.replace("\r\n", "\n")
    slides = []
    for m in SLIDE_RE.finditer(content):
        number = int(m.group(1))
        label = (m.group(2) or "").strip().lower()
        kind = "item"
        if "cover" in label:
            kind = "cover"
        elif "payoff" in label:
            kind = "payoff"
        elif "outro" in label:
            kind = "outro"

        fields = {}
        for line in m.group(3).splitlines():
            fm = FIELD_RE.match(line.strip())
            if fm:
                fields[fm.group(1).strip().lower()] = _clean(fm.group(2))

        headline = fields.get("text") or fields.get("venue") or ""
        detail = fields.get("detail") or ""
        visual_note = fields.get("visual note") or fields.get("visual") or ""
        flagged = "[check" in (headline + " " + detail).lower()

        slides.append(dict(number=number, kind=kind, headline=headline,
                            detail=detail, visual_note=visual_note, flagged=flagged))
    return slides


# ------------------------------------------------------------------ photo + background

def _find_photo(photos_dir: Path, number: int) -> Path | None:
    if not photos_dir.exists():
        return None
    for ext in PHOTO_EXTS:
        candidate = photos_dir / f"slide_{number:02d}{ext}"
        if candidate.exists():
            return candidate
    return None


def _cover_crop(img: Image.Image) -> Image.Image:
    img = img.convert("RGB")
    src_w, src_h = img.size
    target_ratio = W / H
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))
    return img.resize((W, H), Image.LANCZOS)


def _placeholder_background() -> Image.Image:
    """Moody dark gradient standing in for a photo that hasn't been shot yet."""
    top, bottom = (20, 28, 40), (6, 7, 10)
    img = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / H
        img.putpixel((0, y), tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3)))
    return img.resize((W, H))


def _scrim(bg: Image.Image, base_alpha: int, bottom_alpha: int, bottom_frac: float) -> Image.Image:
    """Darken a background so overlaid white text stays legible - a flat dim
    plus extra darkening toward the bottom, where captions sit (matches the
    brand's real carousels)."""
    overlay = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        extra = 0.0 if t < (1 - bottom_frac) else (t - (1 - bottom_frac)) / bottom_frac
        overlay.putpixel((0, y), int(base_alpha + extra * (bottom_alpha - base_alpha)))
    overlay = overlay.resize((W, H))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(black, bg, overlay)


def _background(photo: Path | None, base_alpha: int, bottom_alpha: int, bottom_frac: float) -> Image.Image:
    bg = _cover_crop(Image.open(photo)) if photo else _placeholder_background()
    return _scrim(bg, base_alpha, bottom_alpha, bottom_frac)


# ------------------------------------------------------------------ photo library matching

_STOPWORDS = {"the", "hotel", "bar", "pub", "and", "of", "a", "an", "spot", "venue", "check"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in _STOPWORDS and len(w) > 2}


def _library_photos() -> list[Path]:
    if not PHOTO_LIBRARY.exists():
        return []
    return sorted(p for p in PHOTO_LIBRARY.rglob("*") if p.suffix.lower() in PHOTO_EXTS)


def _match_library_photo(headline: str, used: set) -> Path | None:
    """Best library photo for this venue/headline by word overlap between
    the headline and the photo's folder + file name. None if nothing shares
    a meaningful word - the caller then falls back to a generic pick."""
    target = _words(headline)
    if not target:
        return None
    scored = []
    for p in _library_photos():
        tags = _words(p.parent.name) | _words(p.stem)
        overlap = len(target & tags)
        if overlap:
            scored.append((overlap, p in used, str(p), p))
    if not scored:
        return None
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    return scored[0][3]


def _generic_photo(seed: str, used: set) -> Path | None:
    """Any library photo, for slides with no single venue (cover/payoff/
    outro) or as a last resort - deterministic per seed, avoids repeats
    within one build where possible."""
    photos = _library_photos()
    if not photos:
        return None
    pool = [p for p in photos if p not in used] or photos
    return pool[abs(hash(seed)) % len(pool)]


def _pick_photo(photos_dir: Path, number: int, seed_text: str, prefer_match: bool, used: set) -> Path | None:
    manual = _find_photo(photos_dir, number)
    if manual:
        return manual
    photo = _match_library_photo(seed_text, used) if prefer_match else None
    if photo is None:
        photo = _generic_photo(f"{number}:{seed_text}", used)
    if photo:
        used.add(photo)
    return photo


# ------------------------------------------------------------------ text helpers

def _wrap(draw, text, font, max_width) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines, cur = [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if not cur or draw.textlength(trial, font=font) <= max_width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _fit_font_and_wrap(draw, text, font_path, max_width, start_size, min_size, max_lines):
    size = start_size
    while size >= min_size:
        font = _font(font_path, size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 4
    font = _font(font_path, min_size)
    return font, _wrap(draw, text, font, max_width)


def _draw_lines(draw, lines, font, x, top_y, fill, line_height=None, anchor="la", shadow=True):
    if line_height is None:
        ascent, descent = font.getmetrics()
        line_height = int((ascent + descent) * 1.3)
    y = top_y
    for line in lines:
        if shadow:
            draw.text((x + 2, y + 3), line, font=font, fill=INK_SHADOW, anchor=anchor)
        draw.text((x, y), line, font=font, fill=fill, anchor=anchor)
        y += line_height
    return y


def _signature(draw, cx, top_y, size) -> int:
    """The 'PubCam.' script wordmark with its coral dot. Returns bottom y."""
    font = _font(SCRIPT, size)
    text = "PubCam"
    text_w = draw.textlength(text, font=font)
    x = cx - text_w / 2
    draw.text((x + 2, top_y + 3), text, font=font, fill=INK_SHADOW, anchor="la")
    draw.text((x, top_y), text, font=font, fill=WHITE, anchor="la")
    dot_r = max(5, size // 14)
    dot_x = x + text_w + size * 0.14
    dot_y = top_y + size * 0.62
    draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=ACCENT)
    return int(top_y + size * 0.9)


# ------------------------------------------------------------------ slide renderers

def draw_cover(headline: str, photo: Path | None) -> Image.Image:
    bg = _background(photo, base_alpha=45, bottom_alpha=165, bottom_frac=0.7)
    d = ImageDraw.Draw(bg)

    max_w = W - 2 * 130
    font, lines = _fit_font_and_wrap(d, headline or "Save this", SERIF, max_w, 78, 46, 4)
    line_h = int(font.size * 1.35)
    top = int(H * 0.40) - (len(lines) * line_h) // 2
    y = top
    for line in lines:
        d.text((W / 2 + 2, y + 3), line, font=font, fill=INK_SHADOW, anchor="ma")
        d.text((W / 2, y), line, font=font, fill=WHITE, anchor="ma")
        y += line_h

    _signature(d, W / 2, H - 168, 68)
    return bg


def draw_item(headline: str, detail: str, visual_note: str, flagged: bool, photo: Path | None) -> Image.Image:
    bg = _background(photo, base_alpha=32, bottom_alpha=190, bottom_frac=0.5)
    d = ImageDraw.Draw(bg)

    if not photo and visual_note:
        note_font = _font(SERIF_ITALIC, 24)
        note_lines = _wrap(d, f"Photo needed - {visual_note}", note_font, W - 2 * MARGIN)[:2]
        _draw_lines(d, note_lines, note_font, MARGIN, 76, NOTE_MUTED, shadow=False)

    max_w = W - 2 * MARGIN
    hfont, hlines = _fit_font_and_wrap(d, headline or "-", SERIF_MEDIUM, max_w, 60, 38, 2)
    h_line_h = int(hfont.size * 1.25)

    dfont, dlines, d_line_h = None, [], 0
    if detail:
        dfont, dlines = _fit_font_and_wrap(d, detail, SERIF, max_w, 34, 24, 3)
        d_line_h = int(dfont.size * 1.35)

    block_h = len(hlines) * h_line_h + (18 if dlines else 0) + len(dlines) * d_line_h
    top = H - 120 - block_h
    bottom = _draw_lines(d, hlines, hfont, MARGIN, top, WHITE, h_line_h)
    if dlines:
        detail_color = ACCENT if flagged else BODY_WHITE
        _draw_lines(d, dlines, dfont, MARGIN, bottom + 18, detail_color, d_line_h)
    return bg


def draw_payoff(headline: str, items: list[tuple[str, str]], photo: Path | None) -> Image.Image:
    bg = _background(photo, base_alpha=55, bottom_alpha=200, bottom_frac=0.85)
    d = ImageDraw.Draw(bg)

    max_w = W - 2 * MARGIN
    hfont, hlines = _fit_font_and_wrap(d, headline or "Send this to the group chat", SERIF_ITALIC, max_w, 54, 36, 2)
    y = 110
    for line in hlines:
        d.text((W / 2 + 2, y + 3), line, font=hfont, fill=INK_SHADOW, anchor="ma")
        d.text((W / 2, y), line, font=hfont, fill=WHITE, anchor="ma")
        y += int(hfont.size * 1.3)
    y += 40

    bottom_margin = 100
    n = max(len(items), 1)
    avail = max(H - bottom_margin - y, n * 30)
    line_h = avail / n
    base_size = int(min(32, max(18, line_h * 0.5)))

    for idx, (label, detail) in enumerate(items):
        text = label + (f" — {detail}" if detail else "")
        color = ACCENT if "[check" in text.lower() else BODY_WHITE
        size = base_size
        font = _font(SERIF, size)
        while d.textlength(text, font=font) > max_w and size > 14:
            size -= 1
            font = _font(SERIF, size)
        ly = y + idx * line_h + line_h / 2
        d.text((MARGIN + 2, ly + 2), text, font=font, fill=INK_SHADOW, anchor="lm")
        d.text((MARGIN, ly), text, font=font, fill=color, anchor="lm")
    return bg


def draw_outro(headline: str, photo: Path | None) -> Image.Image:
    bg = _background(photo, base_alpha=65, bottom_alpha=170, bottom_frac=0.8)
    d = ImageDraw.Draw(bg)

    sig_bottom = _signature(d, W / 2, int(H * 0.42), 100)

    max_w = W - 2 * 150
    font, lines = _fit_font_and_wrap(d, headline or "Follow @pubcam.au", SERIF_ITALIC, max_w, 36, 26, 3)
    y = sig_bottom + 60
    for line in lines:
        d.text((W / 2 + 2, y + 3), line, font=font, fill=INK_SHADOW, anchor="ma")
        d.text((W / 2, y), line, font=font, fill=BODY_WHITE, anchor="ma")
        y += int(font.size * 1.3)
    return bg


# ------------------------------------------------------------------ orchestration

def render_brief(idea_id: int, content: str, out_dir: Path) -> list[Path]:
    slides = parse_slides(content)
    if not slides:
        raise SystemExit(
            "No '**Slide N**' blocks found in this brief - render_carousel.py only "
            "understands the build-post skill's carousel format."
        )
    items = [s for s in slides if s["kind"] == "item"]
    payoff_items = [(s["headline"], s["detail"]) for s in items]

    photos_dir = out_dir / "photos"
    out_dir.mkdir(parents=True, exist_ok=True)
    used: set = set()
    missing_photos = []
    library_picks = []
    paths = []
    for s in slides:
        n = s["number"]
        if s["kind"] == "cover":
            photo = _pick_photo(photos_dir, n, s["headline"], prefer_match=False, used=used)
            img = draw_cover(s["headline"], photo)
        elif s["kind"] == "payoff":
            photo = _pick_photo(photos_dir, n, "group chat", prefer_match=False, used=used)
            img = draw_payoff(s["headline"], payoff_items, photo)
        elif s["kind"] == "outro":
            photo = _pick_photo(photos_dir, n, "pubcam outro", prefer_match=False, used=used)
            img = draw_outro(s["headline"], photo)
        else:
            photo = _pick_photo(photos_dir, n, s["headline"], prefer_match=True, used=used)
            img = draw_item(s["headline"], s["detail"], s["visual_note"], s["flagged"], photo)

        if photo is None:
            missing_photos.append(n)
        elif not _find_photo(photos_dir, n):
            library_picks.append((n, photo.name))
        path = out_dir / f"slide_{n:02d}.png"
        img.save(path)
        paths.append(path)

    if library_picks:
        for n, name in library_picks:
            print(f"slide_{n:02d}: used {name} from the photo library")
    if missing_photos:
        photos_dir.mkdir(parents=True, exist_ok=True)
        nums = ", ".join(f"slide_{n:02d}.jpg" for n in missing_photos)
        print(f"Placeholder background used for: {nums}")
        print(f"Add photos to {PHOTO_LIBRARY} (or drop an exact override into {photos_dir}) and re-run to swap them in.")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--idea-id", type=int, help="Render the newest brief for this idea id")
    ap.add_argument("--brief-id", type=int, help="Render this exact brief id")
    args = ap.parse_args()
    if not args.idea_id and not args.brief_id:
        ap.error("pass --idea-id or --brief-id")

    conn = sqlite3.connect(DB_PATH)
    try:
        if args.brief_id:
            row = conn.execute("SELECT id, idea_id, content FROM briefs WHERE id = ?", (args.brief_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT id, idea_id, content FROM briefs WHERE idea_id = ? ORDER BY id DESC LIMIT 1",
                (args.idea_id,),
            ).fetchone()
    finally:
        conn.close()

    if not row:
        raise SystemExit("No brief found for that id.")
    brief_id, idea_id, content = row

    out_dir = RENDER_DIR / f"idea_{idea_id}"
    paths = render_brief(idea_id, content, out_dir)
    print(f"Wrote {len(paths)} slide(s) to {out_dir} (from brief #{brief_id})")
    for p in paths:
        print(" -", p.name)


if __name__ == "__main__":
    main()
