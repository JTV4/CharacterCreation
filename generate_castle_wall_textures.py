"""
generate_castle_wall_textures.py
================================
Stylized base-color maps for Castle Wall Window Frame
(wood frame + leaded diamond glass).

Outputs:
  castle_wall_textures/WindowWood_BaseColor.png
  castle_wall_textures/WindowGlass_BaseColor.png

Run:
  python3 generate_castle_wall_textures.py
"""

from __future__ import annotations

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "castle_wall_textures")
N = 512


def _noise_rgb(img: Image.Image, amp: int, rng: random.Random) -> None:
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


def make_window_wood(path: str, rng: random.Random) -> None:
    wood = Image.new("RGB", (N, N), (92, 62, 36))
    draw = ImageDraw.Draw(wood)
    planks = 8
    pw = N // planks
    base_cols = [
        (110, 74, 42),
        (88, 58, 34),
        (120, 80, 46),
        (78, 52, 30),
        (102, 68, 40),
        (95, 64, 38),
        (115, 78, 44),
        (85, 56, 32),
    ]
    for i in range(planks):
        x0 = i * pw
        x1 = N if i == planks - 1 else (i + 1) * pw
        c = base_cols[i % len(base_cols)]
        draw.rectangle([x0, 0, x1, N], fill=c)
        draw.line([(x1 - 1, 0), (x1 - 1, N)], fill=(48, 30, 16), width=2)
        for _ in range(14):
            gx = rng.randint(x0 + 2, x1 - 3)
            shade = rng.randint(-18, 14)
            gc = (
                max(0, min(255, c[0] + shade)),
                max(0, min(255, c[1] + shade // 2)),
                max(0, min(255, c[2] + shade // 3)),
            )
            draw.line([(gx, 0), (gx + rng.randint(-2, 2), N)], fill=gc, width=1)
        if rng.random() < 0.55:
            kx = rng.randint(x0 + 6, x1 - 6)
            ky = rng.randint(40, N - 40)
            kr = rng.randint(4, 9)
            draw.ellipse(
                [kx - kr, ky - kr // 2, kx + kr, ky + kr // 2],
                outline=(55, 34, 18),
                width=2,
            )
            draw.ellipse(
                [kx - kr // 2, ky - kr // 3, kx + kr // 2, ky + kr // 3],
                fill=(70, 44, 24),
            )

    overlay = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(0, N, 3):
        a = 10 + (y % 7)
        od.line(
            [(0, y), (N, y + int(2 * math.sin(y * 0.08)))],
            fill=(0, 0, 0, a),
            width=1,
        )
    wood = Image.alpha_composite(wood.convert("RGBA"), overlay).convert("RGB")
    _noise_rgb(wood, 8, rng)
    wood = wood.filter(ImageFilter.SMOOTH)
    wood.save(path)


def make_window_glass(path: str, rng: random.Random) -> None:
    glass = Image.new("RGBA", (N, N), (40, 70, 95, 255))
    gd = ImageDraw.Draw(glass)
    cell = 48
    for row in range(-2, N // (cell // 2) + 3):
        for col in range(-2, N // cell + 3):
            cx = col * cell + (cell // 2 if row % 2 else 0)
            cy = row * (cell // 2)
            pts = [
                (cx, cy - cell // 2),
                (cx + cell // 2, cy),
                (cx, cy + cell // 2),
                (cx - cell // 2, cy),
            ]
            t = rng.randint(-22, 28)
            r = max(20, min(90, 55 + t // 2))
            g = max(60, min(140, 105 + t))
            b = max(80, min(170, 130 + t // 2))
            if rng.random() < 0.12:
                r, g, b = min(255, r + 40), max(40, g - 10), max(40, b - 30)
            elif rng.random() < 0.10:
                r, g, b = max(20, r - 15), min(255, g + 25), min(255, b + 10)
            gd.polygon(pts, fill=(r, g, b, 255))

    lead = (28, 30, 34, 255)
    step = cell // 2
    for k in range(-N, N * 2, step):
        gd.line([(k, 0), (k + N, N)], fill=lead, width=3)
        gd.line([(k + N, 0), (k, N)], fill=lead, width=3)

    hi = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hi)
    for i in range(5):
        x = 40 + i * 90 + rng.randint(-10, 10)
        hd.line([(x, 0), (x + 30, N)], fill=(220, 235, 255, 28), width=10)
    glass = Image.alpha_composite(glass, hi)

    px = glass.load()
    for y in range(N):
        for x in range(N):
            r, g, b, a = px[x, y]
            d = rng.randint(-6, 6)
            px[x, y] = (
                max(0, min(255, r + d)),
                max(0, min(255, g + d)),
                max(0, min(255, b + d)),
                a,
            )

    glass = glass.filter(ImageFilter.SMOOTH_MORE)
    glass.save(path)


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(42)
    wood_path = os.path.join(OUT, "WindowWood_BaseColor.png")
    glass_path = os.path.join(OUT, "WindowGlass_BaseColor.png")
    make_window_wood(wood_path, rng)
    make_window_glass(glass_path, rng)
    print(f"  -> {wood_path}")
    print(f"  -> {glass_path}")


if __name__ == "__main__":
    main()
