"""
generate_fish_piles.py
======================
Messy "tossed heap" piles of cooked fish — one pile per cooked type.
Burnt variants are skipped.

Sources:
  ~/Documents/GitHub/Exodus-SDK7/assets/models/Cooking/CookedFish/
    Bass.glb, Catfish.glb, Gar.glb, Trout.glb, Walleye.glb

Outputs (Desktop + viewer):
  FishPile_Bass.glb
  FishPile_Catfish.glb
  FishPile_Gar.glb
  FishPile_Trout.glb
  FishPile_Walleye.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_fish_piles.py
"""

from __future__ import annotations

import math
import os
import random

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
FISH_DIR = os.path.expanduser(
    "~/Documents/GitHub/Exodus-SDK7/assets/models/Cooking/CookedFish"
)
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

# Cooked only — no burnt_*
FISH_VARIANTS = [
    ("Bass.glb", "FishPile_Bass", "Bass"),
    ("Catfish.glb", "FishPile_Catfish", "Catfish"),
    ("Gar.glb", "FishPile_Gar", "Gar"),
    ("Trout.glb", "FishPile_Trout", "Trout"),
    ("Walleye.glb", "FishPile_Walleye", "Walleye"),
]

FISH_PER_PILE = 14
RNG_SEED = 20260727


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def world_bounds(obj: bpy.types.Object):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def normalize_fish(obj: bpy.types.Object) -> tuple[float, float, float]:
    """Bake TRS, center X/Y, sit underside on Z=0.  Returns (sx, sy, sz)."""
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


def import_fish(path: str) -> bpy.types.Object:
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
    proto.name = "FishPrototype"
    for img in bpy.data.images:
        if img.packed_file is None:
            try:
                img.pack()
            except Exception:
                pass
    return proto


def duplicate_fish(proto: bpy.types.Object, name: str) -> bpy.types.Object:
    dup = proto.copy()
    dup.data = proto.data.copy()
    dup.name = name
    bpy.context.collection.objects.link(dup)
    return dup


def build_tossed_pile(
    proto: bpy.types.Object,
    sx: float,
    sy: float,
    sz: float,
    seed: int,
) -> bpy.types.Object:
    """Scatter fish into a loose heap — random yaw/tilt, overlapping mound."""
    rng = random.Random(seed)
    created: list[bpy.types.Object] = []

    # Footprint of the heap scales with the longest fish axis
    long = max(sx, sy)
    short = min(sx, sy)
    pile_r = long * 0.55

    for i in range(FISH_PER_PILE):
        # Density higher near center; later fish sit higher (tossed on top)
        t = i / max(1, FISH_PER_PILE - 1)
        r = pile_r * math.sqrt(rng.random()) * (0.45 + 0.55 * t)
        theta = rng.uniform(0.0, 2.0 * math.pi)
        x = r * math.cos(theta)
        y = r * math.sin(theta)
        # Soft mound: center taller, plus per-fish stack offset
        mound = (1.0 - min(1.0, r / max(pile_r, 1e-3))) ** 1.4
        z = sz * (0.08 + 0.55 * t + 0.35 * mound) + rng.uniform(0.0, sz * 0.06)

        fish = duplicate_fish(proto, f"fish_{i}")
        # Mostly lying flat-ish, but clearly tossed (not a neat stack)
        pitch = rng.uniform(-0.55, 0.55)
        roll = rng.uniform(-0.70, 0.70)
        yaw = rng.uniform(0.0, 2.0 * math.pi)
        # Occasional belly-up flip
        if rng.random() < 0.22:
            roll += math.pi

        fish.location = Vector((x, y, z))
        fish.rotation_euler = (pitch, roll, yaw)
        # Tiny scale jitter so the heap reads less cloned
        s = rng.uniform(0.92, 1.06)
        fish.scale = (s, s, s)
        created.append(fish)

    proto.hide_set(True)
    proto.hide_render = True

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    pile = bpy.context.active_object
    pile.name = "FishPile"

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
    path = os.path.join(FISH_DIR, src_name)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    print(f"\n=== {label} fish pile ({src_name}) ===")
    proto = import_fish(path)
    sx, sy, sz = normalize_fish(proto)
    print(f"  fish {sx:.3f} × {sy:.3f} × {sz:.3f} m")
    pile = build_tossed_pile(proto, sx, sy, sz, seed=RNG_SEED + index * 41)
    pile.name = out_stem
    if proto.name in bpy.data.objects:
        bpy.data.objects.remove(proto, do_unlink=True)

    (x0, x1), (y0, y1), (z0, z1) = world_bounds(pile)
    print(
        f"  pile X[{x0:.2f},{x1:.2f}] Y[{y0:.2f},{y1:.2f}] "
        f"Z[{z0:.2f},{z1:.2f}]  fish={FISH_PER_PILE} (tossed heap)"
    )
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, f"{out_stem}.glb")
        export_glb(pile, out_path)
        print(f"  -> {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")


def main() -> None:
    print(f"Cooked fish source: {FISH_DIR}")
    for i, (src, stem, label) in enumerate(FISH_VARIANTS):
        build_one(src, stem, label, i)
    print("\nDONE — cooked fish piles exported (burnt skipped).")


if __name__ == "__main__":
    main()
