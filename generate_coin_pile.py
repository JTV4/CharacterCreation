"""
generate_coin_pile.py
=====================
Messy stacked pile of GrindCoins for INIT staging / Resources.

Source:
  viewer/public/buildings/GrindCoin.glb
  (authored by generate_grind_coin.py — already flat on Z, ~1 m Ø)

Outputs:
  ~/Desktop/Models/Buildings/CoinPile_Grind.glb
  viewer/public/buildings/CoinPile_Grind.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_coin_pile.py
"""

from __future__ import annotations

import math
import os
import random

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
COIN_SRC = os.path.join(VIEWER_DIR, "GrindCoin.glb")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

OUT_NAME = "CoinPile_Grind.glb"
COINS_PER_PILE = 16
RNG_SEED = 20260727


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def world_bounds(obj: bpy.types.Object):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def import_coin(path: str) -> bpy.types.Object:
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
    proto.name = "CoinPrototype"

    # GrindScape coin arrives with the thin axis on Y (face in XZ).
    # Remap vertices so the coin lies flat: thin axis → Z.
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(proto)
    sx, sy, sz = x1 - x0, y1 - y0, z1 - z0
    dims = sorted([(sx, "x"), (sy, "y"), (sz, "z")])
    thin_axis = dims[0][1]
    print(f"  raw span {sx:.3f}×{sy:.3f}×{sz:.3f}  thin={thin_axis}")

    me = proto.data
    if thin_axis == "y":
        # (x, y, z) → (x, z, y)  then we'll re-center
        for v in me.vertices:
            v.co.y, v.co.z = v.co.z, v.co.y
    elif thin_axis == "x":
        # (x, y, z) → (z, y, x)
        for v in me.vertices:
            v.co.x, v.co.z = v.co.z, v.co.x
    me.update()

    # Center XY, sit on Z=0
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(proto)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    for v in me.vertices:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= z0
    me.update()
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(proto)
    print(
        f"  flat span {(x1 - x0):.3f}×{(y1 - y0):.3f}×{(z1 - z0):.3f}  "
        f"(Ø≈{max(x1 - x0, y1 - y0):.3f}, thick≈{z1 - z0:.3f})"
    )

    for img in bpy.data.images:
        if img.packed_file is None:
            try:
                img.pack()
            except Exception:
                pass
    return proto


def duplicate_coin(proto: bpy.types.Object, name: str) -> bpy.types.Object:
    dup = proto.copy()
    dup.data = proto.data.copy()
    dup.name = name
    bpy.context.collection.objects.link(dup)
    return dup


def build_coin_pile(proto: bpy.types.Object, seed: int) -> bpy.types.Object:
    """Staggered treasure heap — mostly flat coins with light tilt/yaw."""
    rng = random.Random(seed)
    (_x0, _x1), (_y0, _y1), (z0, z1) = world_bounds(proto)
    # After normalize: diameter ≈ max(X,Y), thickness ≈ Z
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(proto)
    diameter = max(x1 - x0, y1 - y0)
    thick = z1 - z0
    print(f"  flat coin Ø={diameter:.3f} m  thick={thick:.3f} m")

    created: list[bpy.types.Object] = []
    # Layers: 7 → 5 → 3 → 1
    layers = (7, 5, 3, 1)
    rise = thick * 0.92
    pile_r = diameter * 0.42

    idx = 0
    for layer_i, n in enumerate(layers):
        for j in range(n):
            if idx >= COINS_PER_PILE:
                break
            # Polar scatter within shrinking radius per layer
            layer_r = pile_r * (1.0 - 0.18 * layer_i)
            if n == 1:
                r, theta = 0.0, 0.0
            else:
                r = layer_r * math.sqrt(rng.uniform(0.05, 1.0))
                theta = (2.0 * math.pi * j / n) + rng.uniform(-0.35, 0.35)
            x = r * math.cos(theta) + rng.uniform(-0.03, 0.03) * diameter
            y = r * math.sin(theta) + rng.uniform(-0.03, 0.03) * diameter
            z = layer_i * rise + rng.uniform(0.0, thick * 0.15)

            coin = duplicate_coin(proto, f"coin_{idx}")
            # Mostly face-up; small tilt so the pile isn't a perfect cylinder stack
            pitch = rng.uniform(-0.18, 0.18)
            roll = rng.uniform(-0.18, 0.18)
            yaw = rng.uniform(0.0, 2.0 * math.pi)
            if rng.random() < 0.12:
                # Occasional steeper lean on the outer coins
                pitch += rng.choice((-1.0, 1.0)) * rng.uniform(0.25, 0.55)

            coin.location = Vector((x, y, z))
            coin.rotation_euler = (pitch, roll, yaw)
            s = rng.uniform(0.94, 1.04)
            coin.scale = (s, s, s)
            created.append(coin)
            idx += 1

    proto.hide_set(True)
    proto.hide_render = True

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    pile = bpy.context.active_object
    pile.name = "CoinPile_Grind"

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(pile)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    for v in pile.data.vertices:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= z0
    pile.data.update()
    print(
        f"  pile {x1 - x0:.2f}×{y1 - y0:.2f}×{z1 - z0:.2f} m  "
        f"coins={len(created)}"
    )
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


def main() -> None:
    if not os.path.isfile(COIN_SRC):
        raise FileNotFoundError(
            f"{COIN_SRC}\nRun generate_grind_coin.py first."
        )

    print("=== Coin pile ===")
    print(f"  source ← {COIN_SRC} (authored GrindCoin)")

    proto = import_coin(COIN_SRC)
    pile = build_coin_pile(proto, seed=RNG_SEED)

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, OUT_NAME)
        export_glb(pile, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")

    print("DONE")


if __name__ == "__main__":
    main()
