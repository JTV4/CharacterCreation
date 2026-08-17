"""
generate_meat_stacks.py
=======================
Vertical stacks of creature-drop meats (raw + cooked).

Sources:
  ~/Documents/GitHub/Exodus-SDK7/assets/models/CreatureDrops/
    Raw_Beef / Cooked_Beef
    Raw_Lamb / Cooked_Lamb
    Raw_Chicken / Cooked_Chicken

Outputs (Desktop + viewer):
  MeatStack_RawBeef.glb
  MeatStack_CookedBeef.glb
  MeatStack_RawLamb.glb
  MeatStack_CookedLamb.glb
  MeatStack_RawChicken.glb
  MeatStack_CookedChicken.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_meat_stacks.py
"""

from __future__ import annotations

import math
import os
import random

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
MEAT_DIR = os.path.expanduser(
    "~/Documents/GitHub/Exodus-SDK7/assets/models/CreatureDrops"
)
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

# Source meshes are authored at a large unit scale — normalize so the
# longest axis of one piece is TARGET_LONG metres before stacking.
TARGET_LONG = 0.48
STACK_COUNT = 10
RNG_SEED = 20260728

MEAT_VARIANTS = [
    ("Raw_Beef.glb", "MeatStack_RawBeef", "Raw Beef"),
    ("Cooked_Beef.glb", "MeatStack_CookedBeef", "Cooked Beef"),
    ("Raw_Lamb.glb", "MeatStack_RawLamb", "Raw Lamb"),
    ("Cooked_Lamb.glb", "MeatStack_CookedLamb", "Cooked Lamb"),
    ("Raw_Chicken.glb", "MeatStack_RawChicken", "Raw Chicken"),
    ("Cooked_Chicken.glb", "MeatStack_CookedChicken", "Cooked Chicken"),
    ("Raw_Deer.glb", "MeatStack_RawDeer", "Raw Deer"),
    ("Cooked_Deer.glb", "MeatStack_CookedDeer", "Cooked Deer"),
]


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def world_bounds(obj: bpy.types.Object):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def import_meat(path: str) -> bpy.types.Object:
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    for o in list(bpy.data.objects):
        if o.type == "ARMATURE" or (
            o.type == "MESH" and o.name.lower().startswith("icosphere")
        ):
            bpy.data.objects.remove(o, do_unlink=True)
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
    proto.name = "MeatPrototype"
    for img in bpy.data.images:
        if img.packed_file is None:
            try:
                img.pack()
            except Exception:
                pass
    return proto


def normalize_meat(obj: bpy.types.Object) -> tuple[float, float, float]:
    """Scale to TARGET_LONG, center X/Y, sit on Z=0. Returns (sx,sy,sz)."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    (x0, x1), (y0, y1), (z0, z1) = world_bounds(obj)
    longest = max(x1 - x0, y1 - y0, z1 - z0)
    if longest <= 1e-6:
        raise RuntimeError("Degenerate meat mesh")
    scale = TARGET_LONG / longest
    for v in obj.data.vertices:
        v.co *= scale
    obj.data.update()

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


def duplicate(proto: bpy.types.Object, name: str) -> bpy.types.Object:
    dup = proto.copy()
    dup.data = proto.data.copy()
    dup.name = name
    bpy.context.collection.objects.link(dup)
    return dup


def build_stack(
    proto: bpy.types.Object,
    sx: float,
    sy: float,
    sz: float,
    seed: int,
) -> bpy.types.Object:
    """Vertical stack with light horizontal/yaw jitter (not a neat cube)."""
    rng = random.Random(seed)
    created: list[bpy.types.Object] = []
    rise = sz * 0.78  # slight nest between pieces

    for i in range(STACK_COUNT):
        piece = duplicate(proto, f"meat_{i}")
        # Alternate lean so the stack reads as piled, not cloned
        yaw = rng.uniform(-0.45, 0.45) + (math.pi * 0.5 if i % 2 else 0.0)
        piece.location = Vector((
            rng.uniform(-sx * 0.08, sx * 0.08),
            rng.uniform(-sy * 0.08, sy * 0.08),
            i * rise + rng.uniform(0.0, sz * 0.02),
        ))
        piece.rotation_euler = (
            rng.uniform(-0.08, 0.08),
            rng.uniform(-0.08, 0.08),
            yaw,
        )
        s = rng.uniform(0.96, 1.04)
        piece.scale = (s, s, s)
        created.append(piece)

    proto.hide_set(True)
    proto.hide_render = True

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    stack = bpy.context.active_object
    stack.name = "MeatStack"

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    (_x), (_y), (z0, _z1) = world_bounds(stack)
    if abs(z0) > 1e-4:
        for v in stack.data.vertices:
            v.co.z -= z0
        stack.data.update()
    return stack


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
    path = os.path.join(MEAT_DIR, src_name)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    print(f"\n=== {label} stack ({src_name}) ===")
    proto = import_meat(path)
    sx, sy, sz = normalize_meat(proto)
    print(f"  piece {sx:.3f} × {sy:.3f} × {sz:.3f} m (scaled)")
    stack = build_stack(proto, sx, sy, sz, seed=RNG_SEED + index * 37)
    stack.name = out_stem
    if proto.name in bpy.data.objects:
        bpy.data.objects.remove(proto, do_unlink=True)

    (x0, x1), (y0, y1), (z0, z1) = world_bounds(stack)
    print(
        f"  stack X[{x0:.2f},{x1:.2f}] Y[{y0:.2f},{y1:.2f}] "
        f"Z[{z0:.2f},{z1:.2f}]  pieces={STACK_COUNT}"
    )
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, f"{out_stem}.glb")
        export_glb(stack, out_path)
        print(f"  -> {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")


def main() -> None:
    import sys

    print(f"Meat source: {MEAT_DIR}")
    filters: set[str] = set()
    if "--" in sys.argv:
        filters = {a.lower() for a in sys.argv[sys.argv.index("--") + 1:]}

    for i, (src, stem, label) in enumerate(MEAT_VARIANTS):
        if filters and not any(k in src.lower() or k in label.lower() for k in filters):
            continue
        build_one(src, stem, label, i)
    print("\nDONE — meat stacks exported.")


if __name__ == "__main__":
    main()
