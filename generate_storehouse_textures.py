"""
generate_storehouse_textures.py
===============================
Seamless stylized BaseColor maps for the Pioneering Storehouse.

These are authored tileables (not diffusion images): wrap-safe noise,
no baked lighting, GrindScape warm-medieval palette.

Outputs (1024²) in storehouse_textures/:
  Storehouse_Plaster_BaseColor.png
  Storehouse_Wood_BaseColor.png
  Storehouse_Stone_BaseColor.png
  Storehouse_Tiles_BaseColor.png
  Storehouse_DoorWood_BaseColor.png
  Storehouse_Metal_BaseColor.png
  Storehouse_Glass_BaseColor.png
  _sheet.png

Run:
  python3 generate_storehouse_textures.py
"""

from __future__ import annotations

import math
import os
import random

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "storehouse_textures")
N = 1024


def _fade(t: np.ndarray) -> np.ndarray:
    return t * t * (3.0 - 2.0 * t)


def value_noise(n: int, cells_x: int, cells_y: int, rng: np.random.Generator) -> np.ndarray:
    grid = rng.random((cells_y, cells_x), dtype=np.float32) * 2.0 - 1.0
    ys = np.linspace(0.0, cells_y, n, endpoint=False, dtype=np.float32)
    xs = np.linspace(0.0, cells_x, n, endpoint=False, dtype=np.float32)
    y0 = np.floor(ys).astype(np.int32)
    x0 = np.floor(xs).astype(np.int32)
    fy = _fade((ys - y0.astype(np.float32))[:, None])
    fx = _fade((xs - x0.astype(np.float32))[None, :])
    y1 = (y0 + 1) % cells_y
    x1 = (x0 + 1) % cells_x
    y0 = y0 % cells_y
    x0 = x0 % cells_x
    v00 = grid[y0][:, x0]
    v10 = grid[y0][:, x1]
    v01 = grid[y1][:, x0]
    v11 = grid[y1][:, x1]
    return (v00 * (1.0 - fx) + v10 * fx) * (1.0 - fy) + (
        v01 * (1.0 - fx) + v11 * fx
    ) * fy


def fbm(
    n: int,
    rng: np.random.Generator,
    octaves: tuple[tuple[int, int, float], ...],
) -> np.ndarray:
    acc = np.zeros((n, n), dtype=np.float32)
    amp_sum = 0.0
    for cx, cy, amp in octaves:
        acc += amp * value_noise(n, cx, cy, rng)
        amp_sum += amp
    return acc / amp_sum


def to_img(rgb: np.ndarray) -> Image.Image:
    clipped = np.clip(rgb, 0, 255).astype(np.uint8)
    return Image.fromarray(clipped, mode="RGB")


def save(img: Image.Image, name: str) -> str:
    path = os.path.join(OUT, name)
    img.save(path)
    return path


def make_plaster(rng: np.random.Generator) -> Image.Image:
    """Warm lime plaster — mottled, faint trowel, hairline cracks."""
    base = np.array([214, 198, 176], dtype=np.float32)
    mott = fbm(N, rng, ((4, 4, 1.0), (8, 8, 0.55), (16, 16, 0.3), (48, 48, 0.12)))
    fine = value_noise(N, 96, 96, rng)
    trowel = np.sin(
        (np.linspace(0, 18 * math.pi, N, dtype=np.float32)[:, None])
        + 0.35 * value_noise(N, 6, 6, rng)
    )
    rgb = base[None, None, :] + mott[:, :, None] * 18.0 + fine[:, :, None] * 6.0
    rgb += trowel[:, :, None] * np.array([6.0, 5.0, 3.0])
    # cooler pits
    pits = value_noise(N, 24, 24, rng)
    rgb += np.clip(pits, -1.0, -0.55)[:, :, None] * np.array([10.0, 8.0, 6.0])
    img = to_img(rgb).filter(ImageFilter.SMOOTH)
    return img.convert("RGB")


def _wood_map(
    rng: np.random.Generator,
    *,
    horizontal: bool,
    tones: list[tuple[int, int, int]],
) -> np.ndarray:
    planks = len(tones)
    pw = N // planks
    yy, xx = np.indices((N, N), dtype=np.int32)
    across = yy if horizontal else xx
    along = xx if horizontal else yy
    plank_i = np.minimum(across // pw, planks - 1)
    colors = np.array(tones, dtype=np.float32)
    rgb = colors[plank_i]

    grain = fbm(
        N,
        rng,
        (
            (6 if horizontal else 28, 28 if horizontal else 6, 1.0),
            (12 if horizontal else 56, 56 if horizontal else 12, 0.45),
            (24 if horizontal else 90, 90 if horizontal else 24, 0.2),
        ),
    )
    # stretch already via anisotropic cells; add ring-ish waves along grain
    rings = np.sin((along.astype(np.float32) * 0.045) + grain * 3.2)
    rgb = rgb + (grain * 14.0 + rings * 5.0)[:, :, None]

    local = across % pw
    edge_dist = np.minimum(local, pw - 1 - local).astype(np.float32)
    groove = np.clip(1.0 - edge_dist / 3.5, 0.0, 1.0)
    rgb = rgb - groove[:, :, None] * np.array([28.0, 22.0, 16.0])
    hi = ((edge_dist >= 3) & (edge_dist <= 6)).astype(np.float32)
    rgb = rgb + hi[:, :, None] * np.array([10.0, 8.0, 5.0])

    wear = fbm(N, rng, ((5, 5, 1.0), (20, 20, 0.4)))
    rgb = rgb + np.clip(wear, 0.25, 1.0)[:, :, None] * 4.0
    return rgb


def _stamp_knots(rgb: np.ndarray, rng: random.Random, count: int) -> None:
    for _ in range(count):
        cx = rng.randint(40, N - 40)
        cy = rng.randint(40, N - 40)
        rx = rng.randint(7, 14)
        ry = rng.randint(4, 8)
        yy, xx = np.ogrid[0:N, 0:N]
        # wrap-safe distance via minimum image
        dx = np.minimum(np.abs(xx - cx), N - np.abs(xx - cx)) / rx
        dy = np.minimum(np.abs(yy - cy), N - np.abs(yy - cy)) / ry
        d = np.sqrt(dx * dx + dy * dy)
        ring = np.exp(-((d - 0.75) ** 2) * 18.0)
        core = np.clip(1.0 - d, 0.0, 1.0)
        rgb -= core[:, :, None] * np.array([22.0, 16.0, 10.0])
        rgb -= ring[:, :, None] * np.array([16.0, 12.0, 8.0])


def make_wood(rng: np.random.Generator) -> Image.Image:
    tones = [
        (86, 56, 36),
        (72, 46, 30),
        (98, 64, 40),
        (64, 42, 28),
        (90, 58, 38),
        (78, 50, 32),
        (104, 68, 42),
        (70, 44, 29),
    ]
    rgb = _wood_map(rng, horizontal=False, tones=tones)
    _stamp_knots(rgb, random.Random(int(rng.integers(1, 9000))), 7)
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_door_wood(rng: np.random.Generator) -> Image.Image:
    tones = [
        (74, 48, 30),
        (62, 40, 26),
        (84, 54, 34),
        (58, 38, 24),
        (78, 50, 32),
        (68, 44, 28),
    ]
    rgb = _wood_map(rng, horizontal=True, tones=tones)
    _stamp_knots(rgb, random.Random(int(rng.integers(1, 9000))), 5)
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_stone(rng: np.random.Generator) -> Image.Image:
    """Warm sandstone ashlar — darker than plaster so the plinth reads."""
    mortar = np.array([86, 76, 62], dtype=np.float32)
    rgb = np.broadcast_to(mortar, (N, N, 3)).copy()
    rows, cols = 8, 5
    bh, bw = N // rows, N // cols
    joint = 5
    block_rng = random.Random(int(rng.integers(1, 9000)))
    for row in range(rows):
        off = bw // 2 if row % 2 else 0
        for col in range(-1, cols + 1):
            x0 = col * bw + off
            y0 = row * bh
            x1 = x0 + bw - joint
            y1 = y0 + bh - joint
            t = block_rng.randint(-18, 16)
            fill = np.array(
                [
                    142 + t,
                    128 + t + block_rng.randint(-8, 4),
                    102 + t + block_rng.randint(-8, 2),
                ],
                dtype=np.float32,
            )
            # draw with wrap
            for dx in (-N, 0, N):
                xa, xb = x0 + dx, x1 + dx
                if xb < 0 or xa >= N:
                    continue
                xs = max(0, xa)
                xe = min(N, xb)
                ys = max(0, y0)
                ye = min(N, y1)
                if xe <= xs or ye <= ys:
                    continue
                rgb[ys:ye, xs:xe] = fill
                # bevel
                h = 3
                rgb[ys : min(ye, ys + h), xs:xe] += np.array([22.0, 20.0, 16.0])
                rgb[ys:ye, xs : min(xe, xs + 2)] += np.array([14.0, 12.0, 10.0])
                rgb[max(ys, ye - 3) : ye, xs:xe] -= np.array([18.0, 16.0, 14.0])
                rgb[ys:ye, max(xs, xe - 2) : xe] -= np.array([12.0, 10.0, 8.0])

    mott = fbm(N, rng, ((8, 8, 1.0), (24, 24, 0.4), (64, 64, 0.15)))
    rgb = rgb + mott[:, :, None] * 10.0
    speckle = value_noise(N, 80, 80, rng)
    rgb += np.where(speckle < -0.72, -18.0, 0.0)[:, :, None]
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_tiles(rng: np.random.Generator) -> Image.Image:
    """Column-aligned beaver-tail tiles (same read as Building1, with tint)."""
    rows, cols = 8, 10
    tw = N / cols
    th = N / rows
    yy, xx = np.indices((N, N), dtype=np.float32)
    col = np.floor(xx / tw).astype(np.int32) % cols
    row = np.floor(yy / th).astype(np.int32) % rows
    lx = xx - col.astype(np.float32) * tw
    ly = yy - row.astype(np.float32) * th
    cx = tw * 0.5
    r = tw * 0.48
    body = (lx > 1.5) & (lx < tw - 1.5) & (ly > 2.0) & (ly < th - r)
    dx = lx - cx
    dy = ly - (th - r)
    scallop = (dx * dx + dy * dy) <= (r * r)
    inside = body | scallop

    tint = (((row * 13 + col * 7) % 11) - 5).astype(np.float32)
    base = np.array([168.0, 76.0, 44.0], dtype=np.float32)
    rgb = np.broadcast_to(np.array([42.0, 24.0, 18.0], dtype=np.float32), (N, N, 3)).copy()
    fill = base[None, None, :] + tint[:, :, None] * np.array([3.2, 1.4, 0.8])
    # top highlight / bottom shade inside each tile
    hi = np.clip((8.0 - ly) / 8.0, 0.0, 1.0)
    shade = np.clip((ly - (th - r - 4.0)) / 10.0, 0.0, 1.0)
    fill = fill + hi[:, :, None] * np.array([22.0, 12.0, 6.0])
    fill = fill - shade[:, :, None] * np.array([18.0, 10.0, 6.0])
    rgb[inside] = fill[inside]
    rgb += value_noise(N, 36, 36, rng)[:, :, None] * 5.0
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_metal(rng: np.random.Generator) -> Image.Image:
    base = np.array([58, 52, 48], dtype=np.float32)
    mott = fbm(N, rng, ((6, 6, 1.0), (18, 18, 0.45), (50, 50, 0.2)))
    rgb = base[None, None, :] + mott[:, :, None] * 16.0
    rust = np.clip(value_noise(N, 12, 12, rng) - 0.35, 0.0, 1.0)
    rgb += rust[:, :, None] * np.array([28.0, 8.0, -4.0])
    # scratches
    scratch = (np.abs(value_noise(N, 80, 8, rng)) < 0.04).astype(np.float32)
    rgb += scratch[:, :, None] * 22.0
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_glass(rng: np.random.Generator) -> Image.Image:
    base = np.array([92, 122, 128], dtype=np.float32)
    wave = fbm(N, rng, ((3, 3, 1.0), (10, 10, 0.4)))
    rgb = base[None, None, :] + wave[:, :, None] * np.array([18.0, 14.0, 10.0])
    streak = np.sin(np.linspace(0, 7 * math.pi, N, dtype=np.float32)[None, :] + wave * 1.2)
    rgb += streak[:, :, None] * np.array([16.0, 18.0, 20.0])
    dirt = np.clip(value_noise(N, 20, 20, rng) - 0.4, 0.0, 1.0)
    rgb -= dirt[:, :, None] * 18.0
    return to_img(rgb).filter(ImageFilter.SMOOTH_MORE)


def make_sheet(paths: list[str]) -> None:
    thumb = 256
    cols = 4
    rows = 2
    sheet = Image.new("RGB", (cols * thumb, rows * thumb), (28, 28, 30))
    labels = [
        "plaster",
        "wood",
        "stone",
        "tiles",
        "door",
        "metal",
        "glass",
    ]
    for i, path in enumerate(paths):
        im = Image.open(path).convert("RGB").resize((thumb, thumb), Image.Resampling.LANCZOS)
        x = (i % cols) * thumb
        y = (i // cols) * thumb
        sheet.paste(im, (x, y))
    save(sheet, "_sheet.png")
    _ = labels


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(20260916)
    jobs = [
        ("Storehouse_Plaster_BaseColor.png", make_plaster),
        ("Storehouse_Wood_BaseColor.png", make_wood),
        ("Storehouse_Stone_BaseColor.png", make_stone),
        ("Storehouse_Tiles_BaseColor.png", make_tiles),
        ("Storehouse_DoorWood_BaseColor.png", make_door_wood),
        ("Storehouse_Metal_BaseColor.png", make_metal),
        ("Storehouse_Glass_BaseColor.png", make_glass),
    ]
    paths = []
    for name, fn in jobs:
        img = fn(rng)
        path = save(img, name)
        paths.append(path)
        print(f"  -> {path} ({os.path.getsize(path) // 1024} KB)")
    make_sheet(paths)
    print(f"  -> {os.path.join(OUT, '_sheet.png')}")


if __name__ == "__main__":
    main()
