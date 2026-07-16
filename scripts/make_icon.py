"""Generates assets/pubcam.ico - a beer-schooner app icon for the desktop shortcut."""
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).parent.parent / "assets"

NAVY = (16, 42, 67, 255)        # night-sky background
AMBER = (240, 166, 29, 255)     # beer
AMBER_DEEP = (214, 138, 10, 255)
FOAM = (250, 248, 242, 255)
GLASS_EDGE = (255, 255, 255, 90)


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256  # design at 256, scale everything

    # rounded-square background
    d.rounded_rectangle([8 * s, 8 * s, 248 * s, 248 * s], radius=52 * s, fill=NAVY)

    # glass body (slightly tapered schooner)
    glass = [(88 * s, 78 * s), (172 * s, 78 * s), (166 * s, 200 * s), (94 * s, 200 * s)]
    d.polygon(glass, fill=AMBER)
    # darker base third for depth
    d.polygon([(92 * s, 160 * s), (168 * s, 160 * s), (166 * s, 200 * s), (94 * s, 200 * s)],
              fill=AMBER_DEEP)

    # handle
    d.arc([160 * s, 100 * s, 210 * s, 170 * s], start=-70, end=70,
          fill=FOAM, width=max(1, int(12 * s)))

    # foam cap - overlapping blobs above the rim
    d.ellipse([80 * s, 56 * s, 128 * s, 96 * s], fill=FOAM)
    d.ellipse([108 * s, 46 * s, 156 * s, 90 * s], fill=FOAM)
    d.ellipse([136 * s, 56 * s, 182 * s, 96 * s], fill=FOAM)

    # glass shine
    d.line([(102 * s, 96 * s), (99 * s, 190 * s)], fill=GLASS_EDGE, width=max(1, int(8 * s)))
    return img


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    base = draw_icon(256)
    out = ASSETS / "pubcam.ico"
    base.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    base.save(ASSETS / "pubcam.png")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
