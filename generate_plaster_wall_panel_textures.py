"""
generate_plaster_wall_panel_textures.py
=======================================
Fresh stylized maps for the NEW plaster panel wall (not derived from
Wall_Plaster_Straight_Base).  Cool limestone plaster, slate stone base,
charcoal timber.

Outputs (1024²):
  wall_plaster_panel_textures/Panel_Plaster_BaseColor.png
  wall_plaster_panel_textures/Panel_Stone_BaseColor.png
  wall_plaster_panel_textures/Panel_Wood_BaseColor.png

Run:
  python3 generate_plaster_wall_panel_textures.py
"""

from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "wall_plaster_panel_textures")
N = 1024


def _noise(img: Image.Image, amp: int, rng: random.Random) -> None:
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            d = rng.randint(-amp, amp)
            px[x, y] = (
                max(0, min(255, r + d)),
                max(0, min(255, g + d)),
                max(0, min(255, b + d)),
            )


def make_plaster(path: str, rng: random.Random) -> None:
    """Cool limestone plaster — soft mottling, faint trowel arcs."""
    base = (214, 210, 200)
    img = Image.new("RGB", (N, N), base)
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(90):
        x0 = rng.randint(-40, N)
        y0 = rng.randint(-40, N)
        w = rng.randint(80, 220)
        h = rng.randint(40, 120)
        shade = rng.randint(-18, 14)
        col = (
            max(0, min(255, base[0] + shade)),
            max(0, min(255, base[1] + shade + rng.randint(-4, 4))),
            max(0, min(255, base[2] + shade + rng.randint(-6, 2))),
            rng.randint(28, 55),
        )
        draw.ellipse([x0, y0, x0 + w, y0 + h], fill=col)
    # faint diagonal trowel strokes
    for i in range(18):
        y = int(i * N / 18) + rng.randint(-8, 8)
        a = 18 + (i % 5)
        draw.line(
            [(0, y), (N, y + int(12 * math.sin(i * 0.7)))],
            fill=(180, 176, 168, a),
            width=3,
        )
    img = img.convert("RGB")
    _noise(img, 6, rng)
    img = img.filter(ImageFilter.SMOOTH_MORE)
    img.save(path)


def make_stone(path: str, rng: random.Random) -> None:
    """Slate / cool grey ashlar — running bond, soft bevels."""
    img = Image.new("RGB", (N, N), (52, 56, 60))
    draw = ImageDraw.Draw(img)
    rows, cols = 8, 6
    bh, bw = N // rows, N // cols
    mortar = (36, 38, 42)
    draw.rectangle([0, 0, N, N], fill=mortar)
    for row in range(rows):
        off = (bw // 2) if row % 2 else 0
        for col in range(-1, cols + 1):
            x0 = col * bw + off
            y0 = row * bh
            x1 = x0 + bw - 3
            y1 = y0 + bh - 3
            t = rng.randint(-16, 18)
            fill = (
                max(0, min(255, 78 + t)),
                max(0, min(255, 82 + t + rng.randint(-4, 4))),
                max(0, min(255, 88 + t + rng.randint(-2, 6))),
            )
            hi = (
                min(255, fill[0] + 28),
                min(255, fill[1] + 28),
                min(255, fill[2] + 30),
            )
            draw.rounded_rectangle([x0, y0, x1, y1], radius=6, fill=fill)
            # soft top-left bevel hint
            draw.line([(x0 + 4, y0 + 3), (x1 - 4, y0 + 3)], fill=hi, width=2)
            draw.line([(x0 + 3, y0 + 4), (x0 + 3, y1 - 4)], fill=hi, width=1)
    _noise(img, 7, rng)
    img = img.filter(ImageFilter.SMOOTH)
    img.save(path)


def make_wood(path: str, rng: random.Random) -> None:
    """Charcoal-stained timber with vertical grain + rare knots."""
    img = Image.new("RGB", (N, N), (42, 32, 26))
    draw = ImageDraw.Draw(img)
    planks = 7
    pw = N // planks
    tones = [
        (58, 42, 32),
        (48, 34, 26),
        (64, 46, 34),
        (40, 30, 24),
        (54, 38, 28),
        (46, 33, 25),
        (60, 44, 33),
    ]
    for i in range(planks):
        x0 = i * pw
        x1 = N if i == planks - 1 else (i + 1) * pw
        c = tones[i % len(tones)]
        draw.rectangle([x0, 0, x1, N], fill=c)
        draw.line([(x1 - 1, 0), (x1 - 1, N)], fill=(22, 16, 12), width=2)
        for _ in range(16):
            gx = rng.randint(x0 + 2, max(x0 + 3, x1 - 3))
            shade = rng.randint(-12, 10)
            gc = (
                max(0, min(255, c[0] + shade)),
                max(0, min(255, c[1] + shade // 2)),
                max(0, min(255, c[2] + shade // 3)),
            )
            draw.line([(gx, 0), (gx + rng.randint(-1, 1), N)], fill=gc, width=1)
        if rng.random() < 0.4:
            kx = rng.randint(x0 + 8, x1 - 8)
            ky = rng.randint(60, N - 60)
            kr = rng.randint(5, 10)
            draw.ellipse(
                [kx - kr, ky - kr // 2, kx + kr, ky + kr // 2],
                outline=(28, 20, 14),
                width=2,
            )
    _noise(img, 5, rng)
    img = img.filter(ImageFilter.SMOOTH)
    img.save(path)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(19)
    make_plaster(os.path.join(OUT, "Panel_Plaster_BaseColor.png"), rng)
    make_stone(os.path.join(OUT, "Panel_Stone_BaseColor.png"), rng)
    make_wood(os.path.join(OUT, "Panel_Wood_BaseColor.png"), rng)
    for name in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, name)
        print(f"  -> {p} ({os.path.getsize(p) // 1024} KB)")


if __name__ == "__main__":
    main()
