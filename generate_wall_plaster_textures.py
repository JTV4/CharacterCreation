"""
generate_wall_plaster_textures.py
=================================
Build a fresh Warm Clay / Walnut palette for Wall_Plaster_Straight_Base
by recoloring the source albedos (preserves trim-sheet UV bands) and
resizing supporting normal/roughness maps to 1024².

Requires the source GLB textures already extracted, OR pass --from-glb
to pull them from Downloads/Wall_Plaster_Straight_Base.glb via Blender
first (see texture_wall_plaster_straight.py which embeds the same
recolor path).

Outputs:
  wall_plaster_textures/WP_*_BaseColor.png
  wall_plaster_textures/WP_*_Normal.png
  wall_plaster_textures/WP_*_Roughness.png / WP_Plaster_ORM.png

Run (after extracting source maps to /tmp/wall_plaster_src):
  python3 generate_wall_plaster_textures.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("WALL_PLASTER_SRC", "/tmp/wall_plaster_src")
OUT = os.path.join(ROOT, "wall_plaster_textures")
SIZE = 1024


def to_arr(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0


def from_arr(a: np.ndarray) -> Image.Image:
    a = np.clip(a, 0, 1)
    return Image.fromarray((a * 255).astype(np.uint8))


def luminance(a: np.ndarray) -> np.ndarray:
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def recolor_by_luma(
    a: np.ndarray,
    dark: tuple[float, float, float],
    mid: tuple[float, float, float],
    light: tuple[float, float, float],
    contrast: float = 1.05,
) -> np.ndarray:
    L = np.clip((luminance(a) - 0.5) * contrast + 0.5, 0, 1)
    t1 = np.clip(L * 2.0, 0, 1)[..., None]
    t2 = np.clip((L - 0.5) * 2.0, 0, 1)[..., None]
    low = np.array(dark)[None, None, :] * (1 - t1) + np.array(mid)[None, None, :] * t1
    high = np.array(mid)[None, None, :] * (1 - t2) + np.array(light)[None, None, :] * t2
    out = np.where(L[..., None] < 0.5, low, high)
    detail = a - luminance(a)[..., None]
    return np.clip(out + detail * 0.35, 0, 1)


def hue_shift_rgb(a: np.ndarray, degrees: float, sat_mul: float = 1.0) -> np.ndarray:
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    df = mx - mn + 1e-8
    h = np.zeros_like(mx)
    mask = mx == r
    h[mask] = ((g - b) / df)[mask] % 6
    mask = (mx == g) & ~(mx == r)
    h[mask] = ((b - r) / df)[mask] + 2
    mask = (mx == b) & ~(mx == r) & ~(mx == g)
    h[mask] = ((r - g) / df)[mask] + 4
    h = (h / 6.0 + degrees / 360.0) % 1.0
    s = np.clip(df / (mx + 1e-8) * sat_mul, 0, 1)
    v = mx
    i = np.floor(h * 6).astype(np.int32) % 6
    f = h * 6 - np.floor(h * 6)
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    out = np.zeros_like(a)
    for m, chans in [
        (i == 0, (v, t, p)),
        (i == 1, (q, v, p)),
        (i == 2, (p, v, t)),
        (i == 3, (p, q, v)),
        (i == 4, (t, p, v)),
        (i == 5, (v, p, q)),
    ]:
        for c, channel in enumerate(chans):
            out[..., c] = np.where(m, channel, out[..., c])
    return out


def main() -> None:
    if not os.path.isdir(SRC):
        print(f"Missing source maps at {SRC}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(OUT, exist_ok=True)

    pl = to_arr(Image.open(os.path.join(SRC, "T_Plaster_BaseColor.png")))
    pl2 = hue_shift_rgb(
        recolor_by_luma(
            pl,
            dark=(0.55, 0.42, 0.34),
            mid=(0.86, 0.74, 0.60),
            light=(0.96, 0.90, 0.80),
            contrast=0.95,
        ),
        8,
        sat_mul=1.05,
    )
    from_arr(pl2).resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(
        os.path.join(OUT, "WP_Plaster_BaseColor.png")
    )

    br = to_arr(Image.open(os.path.join(SRC, "T_Brick_BaseColor.png")))
    br2 = hue_shift_rgb(
        recolor_by_luma(
            br,
            dark=(0.28, 0.18, 0.14),
            mid=(0.62, 0.32, 0.24),
            light=(0.82, 0.52, 0.38),
            contrast=1.1,
        ),
        -5,
        sat_mul=1.15,
    )
    from_arr(br2).resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(
        os.path.join(OUT, "WP_Brick_BaseColor.png")
    )

    wd = to_arr(Image.open(os.path.join(SRC, "T_WoodTrim_BaseColor.png")))
    h = wd.shape[0]
    bands = [
        (0, int(h * 0.22), (0.35, 0.22, 0.12), (0.62, 0.42, 0.24), (0.78, 0.58, 0.36)),
        (int(h * 0.22), int(h * 0.48), (0.12, 0.07, 0.05), (0.28, 0.16, 0.10), (0.42, 0.26, 0.16)),
        (int(h * 0.48), int(h * 0.72), (0.20, 0.12, 0.07), (0.48, 0.30, 0.16), (0.68, 0.46, 0.26)),
        (int(h * 0.72), h, (0.18, 0.20, 0.18), (0.38, 0.40, 0.36), (0.58, 0.60, 0.54)),
    ]
    wd2 = wd.copy()
    for y0, y1, dark, mid, light in bands:
        wd2[y0:y1] = recolor_by_luma(wd[y0:y1], dark, mid, light, contrast=1.08)
    from_arr(wd2).resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(
        os.path.join(OUT, "WP_WoodTrim_BaseColor.png")
    )

    for name, outname in [
        ("T_Plaster_Normal.png", "WP_Plaster_Normal.png"),
        ("T_Plaster_ORM.png", "WP_Plaster_ORM.png"),
        ("T_Brick_Normal.png", "WP_Brick_Normal.png"),
        ("T_Brick_Roughness.png", "WP_Brick_Roughness.png"),
        ("T_WoodTrim_Normal.png", "WP_WoodTrim_Normal.png"),
        ("T_WoodTrim_Roughness.png", "WP_WoodTrim_Roughness.png"),
    ]:
        Image.open(os.path.join(SRC, name)).resize(
            (SIZE, SIZE), Image.Resampling.LANCZOS
        ).save(os.path.join(OUT, outname))

    print(f"Wrote textures → {OUT}")


if __name__ == "__main__":
    main()
