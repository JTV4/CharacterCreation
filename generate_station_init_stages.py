"""
generate_station_init_stages.py
===============================
Compact AoE-style INIT pads for indoor/outdoor workstations.

Each INIT is chalk footprint + small resource piles (NOT the finished
station mesh).  Piles are heavily scaled so they fit inside a building
(~2–2.5 m pad), unlike the building-scale resource heaps.

Stations / materials (every pad also gets GrindCoins):
  Furnace                 — sycamore logs, iron ore, clay
  Anvil                   — iron ore
  Tanning Rack            — sycamore logs, iron ore
  Crafting Workbench      — sycamore logs, iron ore
  Manufacturing Workbench — sycamore logs, iron ore
  Spinning Wheel          — sycamore logs, clay
  Cow Pasture             — sycamore logs  (slightly larger outdoor pad)

Outputs → viewer/public/buildings/Construction/ + Desktop mirror.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_station_init_stages.py
"""

from __future__ import annotations

import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(ROOT, "viewer/public/buildings")
VIEWER_OUT = os.path.join(VIEWER, "Construction")
DESKTOP_OUT = os.path.expanduser("~/Desktop/Models/Buildings/Construction")
DESKTOP_NAMED = os.path.expanduser("~/Desktop/Buildings")

os.makedirs(VIEWER_OUT, exist_ok=True)
os.makedirs(DESKTOP_OUT, exist_ok=True)

# Source piles / coin (viewer copies).
PILE_SRC = {
    "logs": os.path.join(VIEWER, "LogPile_Sycamore.glb"),
    "ore": os.path.join(VIEWER, "OrePile_Iron.glb"),
    "clay": os.path.join(VIEWER, "Clay.glb"),
    "coin": os.path.join(VIEWER, "GrindCoin.glb"),
}

# Indoor pads are small; pasture is a bit larger.
# materials: subset of ("logs","ore","clay") — coins always added.
STATIONS = [
    {
        "id": "furnace",
        "folder": "Furnace",
        "out": "Furnace_INIT.glb",
        "pad": (2.4, 2.0),
        "materials": ("logs", "ore", "clay"),
        "pile_scale": 0.18,
    },
    {
        "id": "anvil",
        "folder": "Anvil",
        "out": "Anvil_INIT.glb",
        "pad": (2.0, 1.8),
        "materials": ("ore",),
        "pile_scale": 0.18,
    },
    {
        "id": "tanning_rack",
        "folder": "Tanning Rack",
        "out": "TanningRack_INIT.glb",
        "pad": (2.4, 2.0),
        "materials": ("logs", "ore"),
        "pile_scale": 0.18,
    },
    {
        "id": "crafting_workbench",
        "folder": "Crafting Workbench",
        "out": "CraftingWorkbench_INIT.glb",
        "pad": (2.4, 2.0),
        "materials": ("logs", "ore"),
        "pile_scale": 0.18,
    },
    {
        "id": "manufacturing_workbench",
        "folder": "Manufacturing Workbench",
        "out": "ManufacturingWorkbench_INIT.glb",
        "pad": (2.4, 2.0),
        "materials": ("logs", "ore"),
        "pile_scale": 0.18,
    },
    {
        "id": "spinning_wheel",
        "folder": "Spinning Wheel",
        "out": "SpinningWheel_INIT.glb",
        "pad": (2.2, 2.0),
        "materials": ("logs", "clay"),
        "pile_scale": 0.18,
    },
    {
        "id": "cow_pasture",
        "folder": "Cow Pasture",
        "out": "CowPasture_INIT.glb",
        "pad": (4.0, 3.5),
        "materials": ("logs",),
        "pile_scale": 0.28,  # outdoor — slightly larger
    },
]


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_material(name: str, color_rgb, roughness: float = 0.9) -> bpy.types.Material:
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    p = mat.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value = (*color_rgb, 1.0)
        p.inputs["Roughness"].default_value = roughness
        p.inputs["Metallic"].default_value = 0.0
    return mat


def add_box(name, center, size, mat) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def compute_bounds(obj: bpy.types.Object):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def import_and_normalize(path: str, name: str) -> bpy.types.Object:
    """Import GLB mesh(es), join, center XY, sit on Z=0.

    No decimate — aggressive collapse was shredding ore/log piles into
    unreadable triangle soup on the workstation INIT pads.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    meshes = [
        o for o in bpy.data.objects
        if o not in before and o.type == "MESH"
        and not o.name.lower().startswith("icosphere")
    ]
    for o in list(bpy.data.objects):
        if o in before:
            continue
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
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
    obj = bpy.context.active_object
    obj.name = name

    (x0, x1), (y0, y1), (z0, _z1) = compute_bounds(obj)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    for v in obj.data.vertices:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= z0
    obj.data.update()
    obj.location = (0.0, 0.0, 0.0)
    print(f"    import {name}: {len(obj.data.vertices)} verts")

    for img in bpy.data.images:
        if img.packed_file is None:
            try:
                img.pack()
            except Exception:
                pass
    return obj


def make_mini_coin_pile(scale: float = 0.22) -> bpy.types.Object:
    """4 small GrindCoins with a clear air gap — no shared XY/Z so faces
    never z-fight (flashing) when two coins occupy the same plane."""
    proto = import_and_normalize(PILE_SRC["coin"], "coin_proto")
    proto.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    (_x0, _x1), (_y0, _y1), (_z0, z1) = compute_bounds(proto)
    thick = max(z1, 1e-4)
    diam = max(
        compute_bounds(proto)[0][1] - compute_bounds(proto)[0][0],
        compute_bounds(proto)[1][1] - compute_bounds(proto)[1][0],
    )
    # Center-to-center spacing > diameter so rims never touch.
    spacing = diam * 1.20
    # Vertical stack gap so top/bottom faces never coplanar.
    z_gap = thick * 1.25

    # Triangle on the ground + one on top in the pocket — all separated.
    offsets = [
        (-spacing * 0.55, -spacing * 0.30, 0.0, 0.15),
        (spacing * 0.55, -spacing * 0.30, 0.0, 0.85),
        (0.0, spacing * 0.55, 0.0, -0.55),
        (0.0, 0.0, z_gap, 1.25),
    ]
    created = []
    for i, (x, y, z, yaw) in enumerate(offsets):
        if i == 0:
            c = proto
        else:
            c = proto.copy()
            c.data = proto.data.copy()
            bpy.context.collection.objects.link(c)
        c.name = f"mini_coin_{i}"
        c.location = (x, y, z)
        # Yaw only — no pitch/roll (tilted faces were coplanar-fighting).
        c.rotation_euler = (0.0, 0.0, yaw)
        created.append(c)

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    pile = bpy.context.active_object
    pile.name = "mini_coins"

    (x0, x1), (y0, y1), (z0, _z1) = compute_bounds(pile)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    for v in pile.data.vertices:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= z0
    pile.data.update()
    pile.location = (0.0, 0.0, 0.0)
    return pile


def place_scaled_pile(
    key: str, name: str, loc: tuple[float, float, float],
    yaw: float, scale: float,
) -> bpy.types.Object:
    obj = import_and_normalize(PILE_SRC[key], name)
    obj.scale = (scale, scale, scale)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.location = loc
    obj.rotation_euler = (0.0, 0.0, yaw)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def layout_for(materials: tuple[str, ...], pad_w: float, pad_d: float):
    """Return list of (key, name, x, y, yaw) for materials + coins on pad."""
    # Front-ish row for mats, coins tucked front-center / side.
    slots = []
    n = len(materials)
    # Spread materials across the back half of the pad
    xs = []
    if n == 1:
        xs = [0.0]
    elif n == 2:
        xs = [-pad_w * 0.22, pad_w * 0.22]
    else:
        xs = [-pad_w * 0.28, 0.0, pad_w * 0.28]
    for i, key in enumerate(materials):
        slots.append((key, f"pile_{key}", xs[i], pad_d * 0.12, 0.15 * i))
    # Coins always present — front-center, clear of mats
    slots.append(("coins", "pile_coins", 0.0, -pad_d * 0.22, 0.4))
    return slots


def build_init(spec: dict) -> str:
    clear_scene()
    pad_w, pad_d = spec["pad"]
    scale = spec["pile_scale"]
    print(f"\n=== {spec['folder']} INIT  pad={pad_w}×{pad_d} m  scale={scale} ===")
    print(f"  materials: {', '.join(spec['materials'])} + grind_coins")

    created = []
    dirt = make_material("init_dirt", (0.32, 0.24, 0.16), 0.95)
    chalk = make_material("init_chalk", (0.82, 0.78, 0.68), 0.88)

    dirt_thick = 0.04
    created.append(add_box(
        "init_ground",
        center=(0.0, 0.0, dirt_thick * 0.5),
        size=(pad_w, pad_d, dirt_thick),
        mat=dirt,
    ))
    chalk_w, chalk_h = 0.05, 0.015
    zc = dirt_thick + chalk_h * 0.5
    hw, hd = pad_w * 0.5, pad_d * 0.5
    for center, size in (
        ((0.0, -hd, zc), (pad_w, chalk_w, chalk_h)),
        ((0.0, hd, zc), (pad_w, chalk_w, chalk_h)),
        ((-hw, 0.0, zc), (chalk_w, pad_d, chalk_h)),
        ((hw, 0.0, zc), (chalk_w, pad_d, chalk_h)),
    ):
        created.append(add_box("chalk_line", center=center, size=size, mat=chalk))

    z0 = dirt_thick
    for key, name, x, y, yaw in layout_for(spec["materials"], pad_w, pad_d):
        if key == "coins":
            # Mini coin pile sized for the pad
            coin_scale = 0.20 if pad_w < 3.0 else 0.28
            pile = make_mini_coin_pile(scale=coin_scale)
            pile.name = name
            pile.location = (x, y, z0)
            pile.rotation_euler = (0.0, 0.0, yaw)
            bpy.ops.object.select_all(action="DESELECT")
            pile.select_set(True)
            bpy.context.view_layer.objects.active = pile
            bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
            created.append(pile)
            print(f"  + {name} (mini coins) @ ({x:.2f},{y:.2f})")
        else:
            pile = place_scaled_pile(key, name, (x, y, z0), yaw, scale)
            created.append(pile)
            print(f"  + {name} @ ({x:.2f},{y:.2f}) scale={scale}")

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = spec["out"].replace(".glb", "")

    (x0, x1), (y0, y1), (z0b, z1) = compute_bounds(result)
    print(
        f"  bounds {x1 - x0:.2f}×{y1 - y0:.2f}×{z1 - z0b:.2f} m  "
        f"(pad target {pad_w}×{pad_d})"
    )

    # Export
    paths = []
    for out_dir in (VIEWER_OUT, DESKTOP_OUT):
        path = os.path.join(out_dir, spec["out"])
        bpy.ops.object.select_all(action="DESELECT")
        result.select_set(True)
        bpy.context.view_layer.objects.active = result
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
        paths.append(path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")

    # Named Desktop folder (INIT only)
    folder = os.path.join(DESKTOP_NAMED, spec["folder"])
    os.makedirs(folder, exist_ok=True)
    named = os.path.join(folder, "INIT.glb")
    import shutil
    shutil.copy2(paths[0], named)
    print(f"  -> {named}")
    return paths[0]


def main() -> None:
    # Optional filter: -- furnace anvil ...
    filters: set[str] = set()
    if "--" in sys.argv:
        filters = {a.lower() for a in sys.argv[sys.argv.index("--") + 1:]}

    for src in PILE_SRC.values():
        if not os.path.isfile(src):
            raise FileNotFoundError(src)

    written = []
    for spec in STATIONS:
        if filters and spec["id"] not in filters and spec["folder"].lower() not in filters:
            continue
        written.append(build_init(spec))

    print(f"\nDONE — {len(written)} station INIT pads exported.")


if __name__ == "__main__":
    main()
