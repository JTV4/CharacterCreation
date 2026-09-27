"""
generate_pioneer_male_textures.py
=================================
Seamless stylized BaseColor maps for the Pioneering Male.

Authored tileables (not diffusion): wrap-safe noise, no baked lighting,
same warm medieval palette as the storehouse.

Outputs (1024²) in pioneer_male_textures/:
  Pioneer_Skin_BaseColor.png
  Pioneer_Hair_BaseColor.png
  Pioneer_Linen_BaseColor.png
  Pioneer_Wool_BaseColor.png
  Pioneer_Leather_BaseColor.png
  Pioneer_Metal_BaseColor.png
  Pioneer_Eye_BaseColor.png
  _sheet.png

Run:
  python3 generate_pioneer_male_textures.py
"""

from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "pioneer_male_textures")
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


def fbm(n: int, rng: np.random.Generator, octaves: tuple[tuple[int, int, float], ...]) -> np.ndarray:
    acc = np.zeros((n, n), dtype=np.float32)
    amp_sum = 0.0
    for cx, cy, amp in octaves:
        acc += amp * value_noise(n, cx, cy, rng)
        amp_sum += amp
    return acc / amp_sum


def to_img(rgb: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))


def save(img: Image.Image, name: str) -> str:
    path = os.path.join(OUT, name)
    img.save(path)
    return path


def make_skin(rng: np.random.Generator) -> Image.Image:
    base = np.array([206.0, 164.0, 128.0], dtype=np.float32)
    mott = fbm(rng=rng, n=N, octaves=((4, 4, 1.0), (10, 10, 0.45), (28, 28, 0.2), (70, 70, 0.08)))
    rgb = base[None, None, :] + mott[:, :, None] * np.array([16.0, 12.0, 8.0])
    # faint warmer cheeks / cooler pits
    rgb += np.clip(mott, 0.15, 1.0)[:, :, None] * np.array([6.0, 2.0, 0.0])
    speckle = value_noise(N, 90, 90, rng)
    rgb += np.where(speckle < -0.78, -10.0, 0.0)[:, :, None]
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_hair(rng: np.random.Generator) -> Image.Image:
    base = np.array([46.0, 30.0, 22.0], dtype=np.float32)
    grain = fbm(N, rng, ((8, 48, 1.0), (16, 90, 0.4), (28, 140, 0.18)))
    rgb = base[None, None, :] + grain[:, :, None] * np.array([14.0, 9.0, 6.0])
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_linen(rng: np.random.Generator) -> Image.Image:
    """Warm ochre tunic — faint warp/weft."""
    base = np.array([186.0, 132.0, 78.0], dtype=np.float32)
    mott = fbm(N, rng, ((5, 5, 1.0), (14, 14, 0.4), (40, 40, 0.15)))
    yy, xx = np.indices((N, N))
    weave = 0.55 * np.sin(xx * 0.22) + 0.45 * np.sin(yy * 0.22)
    rgb = base[None, None, :] + mott[:, :, None] * 12.0 + weave[:, :, None] * np.array([8.0, 6.0, 3.0])
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_wool(rng: np.random.Generator) -> Image.Image:
    base = np.array([52.0, 46.0, 40.0], dtype=np.float32)
    mott = fbm(N, rng, ((6, 6, 1.0), (18, 18, 0.4), (48, 48, 0.18)))
    yy, xx = np.indices((N, N))
    weave = 0.4 * np.sin(xx * 0.35) + 0.4 * np.sin(yy * 0.35)
    rgb = base[None, None, :] + mott[:, :, None] * 10.0 + weave[:, :, None] * 4.0
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_leather(rng: np.random.Generator) -> Image.Image:
    base = np.array([92.0, 58.0, 36.0], dtype=np.float32)
    mott = fbm(N, rng, ((4, 4, 1.0), (12, 12, 0.45), (36, 36, 0.2)))
    rgb = base[None, None, :] + mott[:, :, None] * np.array([16.0, 10.0, 6.0])
    scratch = (np.abs(value_noise(N, 70, 10, rng)) < 0.035).astype(np.float32)
    rgb += scratch[:, :, None] * 14.0
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_metal(rng: np.random.Generator) -> Image.Image:
    base = np.array([62.0, 56.0, 50.0], dtype=np.float32)
    mott = fbm(N, rng, ((6, 6, 1.0), (20, 20, 0.4)))
    rust = np.clip(value_noise(N, 12, 12, rng) - 0.4, 0.0, 1.0)
    rgb = base[None, None, :] + mott[:, :, None] * 14.0 + rust[:, :, None] * np.array([22.0, 6.0, -2.0])
    return to_img(rgb).filter(ImageFilter.SMOOTH)


def make_eye(rng: np.random.Generator) -> Image.Image:
    """Off-white sclera with a cool-grey hint — iris is geometry, not this map."""
    base = np.array([232.0, 228.0, 220.0], dtype=np.float32)
    mott = fbm(N, rng, ((3, 3, 1.0), (10, 10, 0.35)))
    rgb = base[None, None, :] + mott[:, :, None] * 8.0
    return to_img(rgb).filter(ImageFilter.SMOOTH_MORE)


def make_sheet(paths: list[str]) -> None:
    thumb = 256
    cols = 4
    sheet = Image.new("RGB", (cols * thumb, 2 * thumb), (28, 28, 30))
    for i, path in enumerate(paths):
        im = Image.open(path).convert("RGB").resize((thumb, thumb), Image.Resampling.LANCZOS)
        sheet.paste(im, ((i % cols) * thumb, (i // cols) * thumb))
    save(sheet, "_sheet.png")


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(20260916)
    jobs = [
        ("Pioneer_Skin_BaseColor.png", make_skin),
        ("Pioneer_Hair_BaseColor.png", make_hair),
        ("Pioneer_Linen_BaseColor.png", make_linen),
        ("Pioneer_Wool_BaseColor.png", make_wool),
        ("Pioneer_Leather_BaseColor.png", make_leather),
        ("Pioneer_Metal_BaseColor.png", make_metal),
        ("Pioneer_Eye_BaseColor.png", make_eye),
    ]
    paths = []
    for name, fn in jobs:
        path = save(fn(rng), name)
        paths.append(path)
        print(f"  -> {path} ({os.path.getsize(path) // 1024} KB)")
    make_sheet(paths)
    print(f"  -> {os.path.join(OUT, '_sheet.png')}")


if __name__ == "__main__":
    main()
