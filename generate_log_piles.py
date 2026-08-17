"""
generate_log_piles.py
=====================
Build five pyramid log piles from Exodus-SDK7 woodchopping logs.

Each pile: bottom layer 4 → 3 → 2 → 1 on top (10 logs), hexagonal nest.

Sources:
  ~/Documents/GitHub/Exodus-SDK7/assets/models/Woodchopping/logs/*.glb

Outputs (Desktop + viewer):
  LogPile_Pine.glb
  LogPile_Poplar.glb
  LogPile_Sycamore.glb
  LogPile_BlueWillow.glb
  LogPile_WeepingWillow.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_log_piles.py
"""

from __future__ import annotations

import math
import os
import random

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.expanduser(
    "~/Documents/GitHub/Exodus-SDK7/assets/models/Woodchopping/logs"
)
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

# (source filename, export stem, display label)
LOG_VARIANTS = [
    ("Pine_Log.glb", "LogPile_Pine", "Pine"),
    ("Poplar_Log.glb", "LogPile_Poplar", "Poplar"),
    ("Sycamore_Log.glb", "LogPile_Sycamore", "Sycamore"),
    ("BlueWillowLog.glb", "LogPile_BlueWillow", "Blue Willow"),
    ("weeiping_willow.glb", "LogPile_WeepingWillow", "Weeping Willow"),
]

LAYER_COUNTS = (4, 3, 2, 1)  # bottom → top
RNG_SEED = 20260727


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def world_bounds(obj: bpy.types.Object):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def normalize_log(obj: bpy.types.Object) -> tuple[float, float, float]:
    """Bake TRS, center on X/Y, sit on Z=0.

    Returns (length, width, height) where width is the across-pile
    diameter (Y) used for side-by-side spacing, and height is how tall
    one log sits on the ground (Z) — used for layer rise / nesting.
    """
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


def import_log_prototype(path: str) -> bpy.types.Object:
    """Import a log GLB and join its meshes into one prototype object."""
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
    proto.name = "LogPrototype"
    # Pack images so bark textures survive export
    for img in bpy.data.images:
        if img.packed_file is None and img.filepath:
            try:
                img.pack()
            except Exception:
                pass
    return proto


def duplicate_log(proto: bpy.types.Object, name: str) -> bpy.types.Object:
    dup = proto.copy()
    dup.data = proto.data.copy()
    dup.name = name
    bpy.context.collection.objects.link(dup)
    return dup


def build_pyramid_pile(
    proto: bpy.types.Object,
    width: float,
    height: float,
    seed: int,
) -> bpy.types.Object:
    """Place 4+3+2+1 logs in a hexagonal pyramid nest, join into one mesh.

    Prototype local space has min Z = 0 (sits on ground), so each
    instance's `location.z` is the height of that log's underside.
    """
    rng = random.Random(seed)
    created: list[bpy.types.Object] = []
    # Side-by-side spacing from across-pile width.
    spacing = width * 0.98
    # These source logs are slightly taller than wide (end-cap atlas), so
    # rise from height with a light nest (~25% overlap) instead of a pure
    # circle hex-pack that would bury layers in the oversized Z extent.
    rise = height * 0.75

    for layer_i, count in enumerate(LAYER_COUNTS):
        total_w = (count - 1) * spacing
        y0 = -0.5 * total_w
        # Nest into valleys of the layer below
        y_off = (spacing * 0.5) if (layer_i % 2 == 1) else 0.0
        # Underside of this layer
        z = layer_i * rise
        for i in range(count):
            log = duplicate_log(proto, f"log_L{layer_i}_{i}")
            yaw = rng.uniform(-0.035, 0.035)
            roll = rng.uniform(-0.025, 0.025)
            log.location = Vector((
                rng.uniform(-0.03, 0.03),
                y0 + i * spacing + y_off,
                z + rng.uniform(-0.005, 0.005),
            ))
            log.rotation_euler = (roll, 0.0, yaw)
            created.append(log)

    # Hide / remove prototype from join
    proto.hide_set(True)
    proto.hide_render = True

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    pile = bpy.context.active_object
    pile.name = "LogPile"

    # Bake TRS; ensure sits on Z=0
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
    path = os.path.join(LOG_DIR, src_name)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    print(f"\n=== {label} pile ({src_name}) ===")
    proto = import_log_prototype(path)
    length, width, height = normalize_log(proto)
    print(f"  log length={length:.3f}m  width={width:.3f}m  height={height:.3f}m")
    pile = build_pyramid_pile(proto, width, height, seed=RNG_SEED + index * 17)
    pile.name = out_stem
    # Remove leftover prototype
    if proto.name in bpy.data.objects:
        bpy.data.objects.remove(proto, do_unlink=True)

    (x0, x1), (y0, y1), (z0, z1) = world_bounds(pile)
    print(
        f"  pile bounds X[{x0:.2f},{x1:.2f}] Y[{y0:.2f},{y1:.2f}] "
        f"Z[{z0:.2f},{z1:.2f}]  logs=10 (4+3+2+1)"
    )
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, f"{out_stem}.glb")
        export_glb(pile, out_path)
        print(f"  -> {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")


def main() -> None:
    print(f"Log source: {LOG_DIR}")
    for i, (src, stem, label) in enumerate(LOG_VARIANTS):
        build_one(src, stem, label, i)
    print("\nDONE — 5 log piles exported.")


if __name__ == "__main__":
    main()
