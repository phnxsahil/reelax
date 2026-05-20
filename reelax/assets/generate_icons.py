from PIL import Image, ImageDraw
from pathlib import Path
import subprocess, sys

OUT = Path(__file__).parent / "icons"
OUT.mkdir(exist_ok=True)

BG    = (10, 10, 16, 255)
GREEN = (0, 210, 115, 255)
DIM   = (0, 150, 80, 160)


def draw_icon(size: int) -> Image.Image:
    """The reelax Rx icon — R with film-reel hole + X = prescription for coding monotony."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d   = ImageDraw.Draw(img)

    corner = max(6, int(size * 0.22))
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=corner, fill=BG)

    sc = size / 100.0
    lw = max(2, int(sc * 6.5))

    # Stem
    sx  = 20 * sc
    top = 16 * sc
    bot = 82 * sc
    d.line([(sx, top), (sx, bot)], fill=GREEN, width=lw)

    # Bowl
    bowl_cx = 36 * sc
    bowl_cy = 36 * sc
    bowl_r  = 16 * sc

    d.line([(sx, bowl_cy - bowl_r), (bowl_cx, bowl_cy - bowl_r)], fill=GREEN, width=lw)
    mid_y = bowl_cy + bowl_r
    d.line([(sx, mid_y), (bowl_cx, mid_y)], fill=GREEN, width=lw)
    d.arc(
        [bowl_cx - bowl_r, bowl_cy - bowl_r, bowl_cx + bowl_r, bowl_cy + bowl_r],
        start=270, end=90, fill=GREEN, width=lw,
    )

    if size >= 24:
        hr = bowl_r * 0.36
        d.ellipse(
            [bowl_cx - hr, bowl_cy - hr, bowl_cx + hr, bowl_cy + hr],
            outline=DIM, width=max(1, int(sc * 2)),
        )

    # Leg
    d.line([(bowl_cx, mid_y), (52 * sc, bot)], fill=GREEN, width=lw)

    # X
    x1 = 60 * sc; x2 = 82 * sc
    yt = 48 * sc; yb = 82 * sc
    d.line([(x1, yt), (x2, yb)], fill=GREEN, width=lw)
    d.line([(x2, yt), (x1, yb)], fill=GREEN, width=lw)

    return img


def generate_all():
    sizes = [16, 24, 32, 48, 64, 128, 256, 512]

    for s in sizes:
        path = OUT / f"reelax_{s}.png"
        draw_icon(s).save(path)
        print(f"  {s}px  -> {path.name}")

    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_imgs  = [draw_icon(s) for s in ico_sizes]
    ico_path  = OUT / "reelax.ico"
    ico_imgs[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=ico_imgs[1:],
    )
    print(f"  ICO    -> {ico_path.name}")

    iconset = OUT / "reelax.iconset"
    iconset.mkdir(exist_ok=True)
    icns_map = {
        "icon_16x16": 16,    "icon_16x16@2x": 32,
        "icon_32x32": 32,    "icon_32x32@2x": 64,
        "icon_128x128": 128, "icon_128x128@2x": 256,
        "icon_256x256": 256, "icon_256x256@2x": 512,
        "icon_512x512": 512,
    }
    for name, s in icns_map.items():
        draw_icon(s).save(iconset / f"{name}.png")

    icns_path = OUT / "reelax.icns"
    if sys.platform == "darwin":
        try:
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)],
                check=True,
            )
            print(f"  ICNS   -> {icns_path.name}")
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"  ICNS skipped ({e})")
    else:
        print("  ICNS   -> run on macOS: iconutil -c icns reelax.iconset -o reelax.icns")

    print(f"\nAll icons in: {OUT}")


if __name__ == "__main__":
    print("Generating reelax icon system...")
    generate_all()
