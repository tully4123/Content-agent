"""Render a build-post brief's carousel slides into PNG images.

Reads the "**Slide N (kind)**" blocks the `build-post` skill writes into
`briefs.content`, and draws each one onto a 1080x1350 PNG in the PubCam
navy/amber template - a basic, postable-as-is carousel, not a mockup.

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

W, H = 1080, 1350
MARGIN = 90

# Same brand colours as scripts/make_icon.py - keep these two files in sync.
NAVY = (16, 42, 67)
AMBER = (240, 166, 29)
AMBER_DEEP = (214, 138, 10)
FOAM = (250, 248, 242)
INK_MUTED = (150, 163, 184)
CHECK_RED = (214, 90, 78)

FONT_BOLD = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]
FONT_REG = [r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]
FONT_ITALIC = [r"C:\Windows\Fonts\segoeuii.ttf", r"C:\Windows\Fonts\ariali.ttf"]

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    key = (candidates[0], size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for path in candidates:
        if Path(path).exists():
            font = ImageFont.truetype(path, size)
            _FONT_CACHE[key] = font
            return font
    font = ImageFont.load_default(size)
    _FONT_CACHE[key] = font
    return font


# ------------------------------------------------------------------ parsing

SLIDE_RE = re.compile(r"\*\*Slide\s+(\d+)\s*(?:\(([^)]*)\))?\*\*[ \t]*\n((?:-[^\n]*\n?)+)")
FIELD_RE = re.compile(r"^-\s*([^:]+):\s*(.*)$")

# The system fonts we draw with have no colour-emoji glyphs, so pictographs
# render as tofu boxes. Strip them from rendered text (captions elsewhere
# keep the emoji - this only affects the PNGs).
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


# ------------------------------------------------------------------ drawing helpers

def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
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


def _fit_font_and_wrap(draw, text, font_paths, max_width, start_size, min_size, max_lines):
    size = start_size
    while size >= min_size:
        font = _font(font_paths, size)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= max_lines:
            return font, lines
        size -= 4
    font = _font(font_paths, min_size)
    return font, _wrap(draw, text, font, max_width)


def _draw_centered_lines(draw, lines, font, cx, top_y, fill, line_height=None):
    if line_height is None:
        ascent, descent = font.getmetrics()
        line_height = int((ascent + descent) * 1.18)
    y = top_y
    for line in lines:
        draw.text((cx, y), line, font=font, fill=fill, anchor="ma")
        y += line_height
    return y


def _new_canvas():
    img = Image.new("RGB", (W, H), NAVY)
    return img, ImageDraw.Draw(img)


# ------------------------------------------------------------------ slide renderers

def draw_cover(headline: str) -> Image.Image:
    img, d = _new_canvas()
    d.text((MARGIN, 72), "PUBCAM", font=_font(FONT_BOLD, 34), fill=AMBER)
    d.rectangle([MARGIN, 122, MARGIN + 120, 128], fill=AMBER)

    max_w = W - 2 * MARGIN
    font, lines = _fit_font_and_wrap(d, headline.upper() or "SAVE THIS", FONT_BOLD, max_w, 104, 56, 6)
    line_h = int(font.size * 1.2)
    top = (H - len(lines) * line_h) // 2
    _draw_centered_lines(d, lines, font, W // 2, top, FOAM, line_h)

    tag = "SWIPE FOR THE LIST →"
    d.text((W // 2, H - 110), tag, font=_font(FONT_BOLD, 28), fill=AMBER, anchor="mm")
    return img


def draw_item(index: int, total: int, headline: str, detail: str, visual_note: str, flagged: bool) -> Image.Image:
    img, d = _new_canvas()
    badge_d = 96
    bx, by = MARGIN, 90
    d.ellipse([bx, by, bx + badge_d, by + badge_d], fill=AMBER)
    d.text((bx + badge_d / 2, by + badge_d / 2), str(index), font=_font(FONT_BOLD, 46), fill=NAVY, anchor="mm")
    d.text((bx + badge_d + 28, by + badge_d / 2), f"{index} OF {total}", font=_font(FONT_BOLD, 26), fill=AMBER, anchor="lm")

    if flagged:
        label = "NEEDS FACT-CHECK"
        lf = _font(FONT_BOLD, 22)
        tw = d.textlength(label, font=lf)
        px0 = W - MARGIN - tw - 44
        py0 = by + 8
        d.rounded_rectangle([px0, py0, W - MARGIN, py0 + 48], radius=24, outline=CHECK_RED, width=3)
        d.text(((px0 + W - MARGIN) / 2, py0 + 24), label, font=lf, fill=CHECK_RED, anchor="mm")

    max_w = W - 2 * MARGIN
    hfont, hlines = _fit_font_and_wrap(d, headline or "-", FONT_BOLD, max_w, 76, 46, 3)
    h_line_h = int(hfont.size * 1.2)
    dfont, dlines, d_line_h = None, [], 0
    if detail:
        dfont, dlines = _fit_font_and_wrap(d, detail, FONT_REG, max_w, 40, 28, 4)
        d_line_h = int(dfont.size * 1.3)

    block_h = len(hlines) * h_line_h + (36 if dlines else 0) + len(dlines) * d_line_h
    top = max(260, (H - block_h) // 2 + 20)
    bottom = _draw_centered_lines(d, hlines, hfont, W // 2, top, FOAM, h_line_h)
    if dlines:
        detail_color = CHECK_RED if flagged else AMBER
        _draw_centered_lines(d, dlines, dfont, W // 2, bottom + 36, detail_color, d_line_h)

    if visual_note:
        vfont, vlines = _fit_font_and_wrap(d, f"Shot: {visual_note}", FONT_ITALIC, max_w, 24, 18, 2)
        v_line_h = int(vfont.size * 1.3)
        vy = H - 60 - len(vlines) * v_line_h
        _draw_centered_lines(d, vlines, vfont, W // 2, vy, INK_MUTED, v_line_h)
    return img


def draw_payoff(headline: str, items: list[tuple[str, str]]) -> Image.Image:
    img, d = _new_canvas()
    max_w = W - 2 * MARGIN
    hfont, hlines = _fit_font_and_wrap(d, headline or "Send this to the group chat", FONT_BOLD, max_w, 68, 44, 2)
    y = _draw_centered_lines(d, hlines, hfont, W // 2, 90, AMBER, int(hfont.size * 1.2)) + 30
    d.line([MARGIN, y, W - MARGIN, y], fill=AMBER_DEEP, width=3)
    y += 40

    bottom_margin = 90
    n = max(len(items), 1)
    avail = max(H - bottom_margin - y, n * 30)
    line_h = avail / n
    size = int(min(40, max(18, line_h * 0.55)))

    for idx, (label, detail) in enumerate(items):
        text = f"{idx + 1}. {label}" + (f" — {detail}" if detail else "")
        s = size
        font = _font(FONT_BOLD, s)
        while d.textlength(text, font=font) > max_w and s > 14:
            s -= 1
            font = _font(FONT_BOLD, s)
        ly = y + idx * line_h + line_h / 2
        d.text((MARGIN, ly), text, font=font, fill=FOAM, anchor="lm")
    return img


def draw_outro(headline: str) -> Image.Image:
    img, d = _new_canvas()
    logo_path = REPO_ROOT / "assets" / "pubcam.png"
    if logo_path.exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((260, 260))
        img.paste(logo, ((W - logo.width) // 2, 320), logo)

    max_w = W - 2 * MARGIN
    font, lines = _fit_font_and_wrap(d, headline or "Follow @pubcam.au", FONT_BOLD, max_w, 56, 34, 4)
    _draw_centered_lines(d, lines, font, W // 2, 660, FOAM, int(font.size * 1.25))
    d.text((W // 2, H - 100), "@pubcam.au", font=_font(FONT_BOLD, 30), fill=AMBER, anchor="mm")
    return img


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

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    item_i = 0
    for s in slides:
        if s["kind"] == "cover":
            img = draw_cover(s["headline"])
        elif s["kind"] == "payoff":
            img = draw_payoff(s["headline"], payoff_items)
        elif s["kind"] == "outro":
            img = draw_outro(s["headline"])
        else:
            item_i += 1
            img = draw_item(item_i, len(items), s["headline"], s["detail"], s["visual_note"], s["flagged"])
        path = out_dir / f"slide_{s['number']:02d}.png"
        img.save(path)
        paths.append(path)
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
