"""
generate_ore_piles.py
=====================
Build square-pyramid ore piles from Exodus-SDK7 mining ore chunks.

Stack (bottom → top):
  3×3  →  2×2 nested in the valleys  →  1 on top
  (9 + 4 + 1 = 14 chunks)

Sources:
  ~/Documents/GitHub/Exodus-SDK7/assets/models/Mining/ore/
  Note: coal uses steel_ore.glb (same single-chunk format; no coal_ore
  in that folder).

Outputs (Desktop + viewer):
  OrePile_Iron.glb
  OrePile_Coal.glb
  OrePile_Gold.glb
  OrePile_Titanium.glb
  OrePile_Tungsten.glb
  OrePile_Luminous.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_ore_piles.py
"""

from __future__ import annotations

import math
import os
import random

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
ORE_DIR = os.path.expanduser(
    "~/Documents/GitHub/Exodus-SDK7/assets/models/Mining/ore"
)
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

# (source filename, export stem, display label)
# Coal → steel_ore.glb (dark chunk in the ore folder; no coal_ore.glb)
ORE_VARIANTS = [
    ("iron_ore.glb", "OrePile_Iron", "Iron"),
    ("steel_ore.glb", "OrePile_Coal", "Coal"),
    ("gold_ore.glb", "OrePile_Gold", "Gold"),
    ("tiantium_ore.glb", "OrePile_Titanium", "Titanium"),
    ("tungsten_ore.glb", "OrePile_Tungsten", "Tungsten"),
    ("luminous_ore.glb", "OrePile_Luminous", "Luminous"),
]

# Square pyramid layers: n×n at bottom → … → 1×1
LAYER_SIZES = (3, 2, 1)
RNG_SEED = 20260727


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def world_bounds(obj: bpy.types.Object):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def normalize_chunk(obj: bpy.types.Object) -> tuple[float, float, float]:
    """Bake TRS, center X/Y, sit on Z=0.  Returns (sx, sy, sz)."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    (x0, x1), (y0, y1), (z0, z1) = world_bounds(obj)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    for v in obj.data.vertices:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= z0
    obj.data.update()
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(obj)
    return (x1 - x0), (y1 - y0), (z1 - z0)


def import_chunk(path: str) -> bpy.types.Object:
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh in {path}")
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    proto = bpy.context.active_object
    proto.name = "OrePrototype"
    for img in bpy.data.images:
        if img.packed_file is None:
            try:
                img.pack()
            except Exception:
                pass
    return proto


def duplicate_chunk(proto: bpy.types.Object, name: str) -> bpy.types.Object:
    dup = proto.copy()
    dup.data = proto.data.copy()
    dup.name = name
    bpy.context.collection.objects.link(dup)
    return dup


def build_square_pyramid(
    proto: bpy.types.Object,
    sx: float,
    sy: float,
    sz: float,
    seed: int,
) -> bpy.types.Object:
    """3×3 → 2×2 (nested in valleys) → 1 on top."""
    rng = random.Random(seed)
    created: list[bpy.types.Object] = []

    spacing_x = sx * 0.92
    spacing_y = sy * 0.92
    # Nest upper cubes into the grooves; slight vertical overlap
    rise = sz * 0.72

    for layer_i, n in enumerate(LAYER_SIZES):
        # Center an n×n grid on origin; nest by half-cell vs layer below
        total_x = (n - 1) * spacing_x
        total_y = (n - 1) * spacing_y
        x0 = -0.5 * total_x
        y0 = -0.5 * total_y
        z = layer_i * rise  # underside (local min Z = 0 on proto)

        for ix in range(n):
            for iy in range(n):
                chunk = duplicate_chunk(proto, f"ore_L{layer_i}_{ix}_{iy}")
                yaw = rng.uniform(-0.25, 0.25)
                chunk.location = Vector((
                    x0 + ix * spacing_x + rng.uniform(-0.02, 0.02),
                    y0 + iy * spacing_y + rng.uniform(-0.02, 0.02),
                    z + rng.uniform(0.0, 0.02),
                ))
                chunk.rotation_euler = (
                    rng.uniform(-0.08, 0.08),
                    rng.uniform(-0.08, 0.08),
                    yaw,
                )
                created.append(chunk)

    proto.hide_set(True)
    proto.hide_render = True

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    pile = bpy.context.active_object
    pile.name = "OrePile"

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    (_x), (_y), (z0, _z1) = world_bounds(pile)
    if abs(z0) > 1e-4:
        for v in pile.data.vertices:
            v.co.z -= z0
        pile.data.update()
    return pile


def export_glb(obj: bpy.types.Object, path: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
    )


def build_one(src_name: str, out_stem: str, label: str, index: int) -> None:
    path = os.path.join(ORE_DIR, src_name)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    print(f"\n=== {label} ore pile ({src_name}) ===")
    proto = import_chunk(path)
    sx, sy, sz = normalize_chunk(proto)
    print(f"  chunk {sx:.3f} × {sy:.3f} × {sz:.3f} m")
    pile = build_square_pyramid(proto, sx, sy, sz, seed=RNG_SEED + index * 31)
    pile.name = out_stem
    if proto.name in bpy.data.objects:
        bpy.data.objects.remove(proto, do_unlink=True)

    (x0, x1), (y0, y1), (z0, z1) = world_bounds(pile)
    n_chunks = sum(n * n for n in LAYER_SIZES)
    print(
        f"  pile X[{x0:.2f},{x1:.2f}] Y[{y0:.2f},{y1:.2f}] "
        f"Z[{z0:.2f},{z1:.2f}]  chunks={n_chunks} (3×3+2×2+1)"
    )
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, f"{out_stem}.glb")
        export_glb(pile, out_path)
        print(f"  -> {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")


def main() -> None:
    print(f"Ore source: {ORE_DIR}")
    for i, (src, stem, label) in enumerate(ORE_VARIANTS):
        build_one(src, stem, label, i)
    print("\nDONE — 6 ore piles exported.")


if __name__ == "__main__":
    main()
