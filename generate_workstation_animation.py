"""
generate_workstation_animation.py
=================================
Modular 10-stage assemble for GrindScape Workstations (compact props).

Unlike buildings (material-rich Wholes), most stations are single-material
meshes — so pieces are produced by loose-part split + Z-band slicing so
the viewer can still play foundation → complete drop-in animation.

Stages (viewer bookmarks, 10 total):
  1 INIT       — required resource piles only (no station mesh)
  2–10         — modular pieces unlock bottom→top (foundation…complete)

Sources: viewer/public/buildings/Workstations/<Name>.glb
Outputs: viewer/public/buildings/Construction/ + Desktop mirror

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_workstation_animation.py
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_workstation_animation.py -- furnace anvil
"""

from __future__ import annotations

import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(ROOT, "viewer/public/buildings")
SRC_DIR = os.path.join(VIEWER, "Workstations")
VIEWER_OUT = os.path.join(VIEWER, "Construction")
DESKTOP_OUT = os.path.expanduser("~/Desktop/Models/Buildings/Construction")

os.makedirs(VIEWER_OUT, exist_ok=True)
os.makedirs(DESKTOP_OUT, exist_ok=True)

DROP_Z = 1.15
OUTWARD = 0.22
TARGET_PIECES = 9
MIN_PIECE_VERTS = 8

STAGE_ORDER = [
    "foundation",
    "walls_a",
    "walls_b",
    "walls_c",
    "walls_d",
    "gable",
    "framing",
    "eaves",
    "complete",
]

# Resource pile sources (viewer copies).
PILE_PATHS = {
    "sycamore_logs": os.path.join(VIEWER, "LogPile_Sycamore.glb"),
    "poplar_logs": os.path.join(VIEWER, "LogPile_Poplar.glb"),
    "iron_ore": os.path.join(VIEWER, "OrePile_Iron.glb"),
    "clay": os.path.join(VIEWER, "Clay.glb"),
    "grind_coins": os.path.join(VIEWER, "CoinPile_Grind.glb"),
    "raw_catfish": os.path.join(VIEWER, "RawFishPile_Catfish.glb"),
    "flax": os.path.join(VIEWER, "Flax.glb"),
    "cow_hide": os.path.join(VIEWER, "CowHide.glb"),
}

# Compact INIT layouts — fractions of half-width/depth, indoor pile scale.
# (key, name, nx, ny, yaw, scale)
def _layout(*entries: tuple) -> list[tuple]:
    return list(entries)


STATIONS: list[dict] = [
    {
        "id": "manufacturing_workbench",
        "structureName": "Manufacturing Workbench",
        "source": "ManufacturingWorkbench.glb",
        "outGlb": "ManufacturingWorkbenchAnimation_Modular.glb",
        "outManifest": "manufacturing_workbench_animation_manifest.json",
        "initGlb": "ManufacturingWorkbench_INIT.glb",
        # Logs, Ore, Coins
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.35, -0.20, 0.0, 0.16),
            ("iron_ore", "pile_iron_ore", 0.35, -0.18, 0.2, 0.16),
            ("grind_coins", "pile_grind_coins", 0.0, 0.32, 0.35, 0.28),
        ),
    },
    {
        "id": "chronocrafting_workbench",
        "structureName": "Chronocrafting Workbench",
        "source": "ChronocraftingWorkbench.glb",
        "outGlb": "ChronocraftingWorkbenchAnimation_Modular.glb",
        "outManifest": "chronocrafting_workbench_animation_manifest.json",
        "initGlb": "ChronocraftingWorkbench_INIT.glb",
        # Sycamore Logs & Coins
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.28, 0.0, 0.0, 0.16),
            ("grind_coins", "pile_grind_coins", 0.30, 0.05, 0.35, 0.28),
        ),
    },
    {
        "id": "cooking_range",
        "structureName": "Cooking Range",
        "source": "CookingRange.glb",
        "outGlb": "CookingRangeAnimation_Modular.glb",
        "outManifest": "cooking_range_animation_manifest.json",
        "initGlb": "CookingRange_INIT.glb",
        # Clay, raw catfish, Coins
        "init_piles": _layout(
            ("clay", "pile_clay", -0.32, -0.10, 0.1, 0.35),
            ("raw_catfish", "pile_raw_catfish", 0.28, -0.08, 0.4, 0.28),
            ("grind_coins", "pile_grind_coins", 0.0, 0.30, 0.35, 0.28),
        ),
    },
    {
        "id": "furnace",
        "structureName": "Furnace",
        "source": "Furnace.glb",
        "outGlb": "FurnaceAnimation_Modular.glb",
        "outManifest": "furnace_animation_manifest.json",
        "initGlb": "Furnace_INIT.glb",
        # Clay, Coins, Sycamore Logs
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.35, -0.22, 0.0, 0.16),
            ("clay", "pile_clay", 0.32, -0.18, 0.1, 0.35),
            ("grind_coins", "pile_grind_coins", 0.0, 0.30, 0.35, 0.28),
        ),
    },
    {
        "id": "spinning_wheel",
        "structureName": "Spinning Wheel",
        "source": "SpinningWheel.glb",
        "outGlb": "SpinningWheelAnimation_Modular.glb",
        "outManifest": "spinning_wheel_animation_manifest.json",
        "initGlb": "SpinningWheel_INIT.glb",
        # Flax, Sycamore Logs, Coins
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.32, -0.18, 0.0, 0.16),
            ("flax", "pile_flax", 0.30, -0.12, 0.2, 0.55),
            ("grind_coins", "pile_grind_coins", 0.0, 0.32, 0.35, 0.28),
        ),
    },
    {
        "id": "anvil",
        "structureName": "Anvil",
        "source": "Anvil.glb",
        "outGlb": "AnvilAnimation_Modular.glb",
        "outManifest": "anvil_animation_manifest.json",
        "initGlb": "Anvil_INIT.glb",
        # Iron Ore + Coins
        "init_piles": _layout(
            ("iron_ore", "pile_iron_ore", -0.22, 0.0, 0.2, 0.16),
            ("grind_coins", "pile_grind_coins", 0.26, 0.05, 0.35, 0.28),
        ),
    },
    {
        "id": "tanning_rack",
        "structureName": "Tanning Rack",
        "source": "TanningRack.glb",
        "outGlb": "TanningRackAnimation_Modular.glb",
        "outManifest": "tanning_rack_animation_manifest.json",
        "initGlb": "TanningRack_INIT.glb",
        # Cow Hide, Sycamore Logs, Coins
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.35, -0.22, 0.0, 0.16),
            ("cow_hide", "pile_cow_hide", 0.30, -0.10, 0.15, 0.45),
            ("grind_coins", "pile_grind_coins", 0.0, 0.32, 0.35, 0.28),
        ),
    },
    {
        "id": "bank_chest",
        "structureName": "Bank Chest",
        "source": "BankChest.glb",
        "outGlb": "BankChestAnimation_Modular.glb",
        "outManifest": "bank_chest_animation_manifest.json",
        "initGlb": "BankChest_INIT.glb",
        # Coins & Poplar Logs
        "init_piles": _layout(
            ("poplar_logs", "pile_poplar_logs", -0.28, 0.0, 0.0, 0.16),
            ("grind_coins", "pile_grind_coins", 0.30, 0.05, 0.35, 0.28),
        ),
    },
    {
        "id": "bridge4",
        "structureName": "Bridge",
        "source": "Bridge4.glb",
        "outGlb": "Bridge4Animation_Modular.glb",
        "outManifest": "bridge4_animation_manifest.json",
        "initGlb": "Bridge4_INIT.glb",
        # Build along span (Y) — one bank → the other.
        "assemble_axis": "Y",
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.35, -0.55, 0.0, 0.22),
            ("sycamore_logs", "pile_sycamore_logs_b", 0.35, -0.55, 0.2, 0.22),
            ("grind_coins", "pile_grind_coins", 0.0, -0.35, 0.35, 0.32),
        ),
    },
    {
        "id": "well",
        "structureName": "Well",
        "source": "Well.glb",
        "outGlb": "WellAnimation_Modular.glb",
        "outManifest": "well_animation_manifest.json",
        "initGlb": "Well_INIT.glb",
        "assemble_axis": "Z",
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.32, -0.18, 0.0, 0.16),
            ("clay", "pile_clay", 0.30, -0.12, 0.1, 0.35),
            ("grind_coins", "pile_grind_coins", 0.0, 0.30, 0.35, 0.28),
        ),
    },
    {
        "id": "fishing_dock",
        "structureName": "Fishing Dock",
        "source": "FishingDock.glb",
        "outGlb": "FishingDockAnimation_Modular.glb",
        "outManifest": "fishing_dock_animation_manifest.json",
        "initGlb": "FishingDock_INIT.glb",
        # Build shore → water along the pier (Y).
        "assemble_axis": "Y",
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.32, -0.55, 0.0, 0.20),
            ("sycamore_logs", "pile_sycamore_logs_b", 0.32, -0.55, 0.15, 0.20),
            ("grind_coins", "pile_grind_coins", 0.0, -0.32, 0.35, 0.30),
        ),
    },
    {
        "id": "dock",
        "structureName": "Dock",
        "source": "Dock.glb",
        "outGlb": "DockAnimation_Modular.glb",
        "outManifest": "dock_animation_manifest.json",
        "initGlb": "Dock_INIT.glb",
        # Build shore → water along the pier (Y).
        "assemble_axis": "Y",
        "init_piles": _layout(
            ("sycamore_logs", "pile_sycamore_logs", -0.32, -0.50, 0.0, 0.14),
            ("sycamore_logs", "pile_sycamore_logs_b", 0.32, -0.50, 0.15, 0.14),
            ("grind_coins", "pile_grind_coins", 0.0, -0.28, 0.35, 0.26),
        ),
    },
]


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def world_bounds(obj: bpy.types.Object):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def bake_trs(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def sit_on_ground_and_center(obj: bpy.types.Object) -> None:
    bake_trs(obj)
    (x0, x1), (y0, y1), (z0, _z1) = world_bounds(obj)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    for v in obj.data.vertices:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= z0
    obj.data.update()
    obj.location = (0.0, 0.0, 0.0)


def import_joined(path: str) -> bpy.types.Object:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    meshes = [
        o
        for o in bpy.data.objects
        if o not in before
        and o.type == "MESH"
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
    sit_on_ground_and_center(obj)
    return obj


def separate_loose(obj: bpy.types.Object) -> list[bpy.types.Object]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.mesh.separate(type="LOOSE")
    return [o for o in bpy.context.selected_objects if o.type == "MESH"]


def split_by_axis_bands(
    obj: bpy.types.Object, bands: int, *, axis: str = "Z"
) -> list[bpy.types.Object]:
    """Bisect obj into `bands` slabs along X, Y, or Z."""
    if bands <= 1 or len(obj.data.vertices) < MIN_PIECE_VERTS * 2:
        return [obj]

    (x0, x1), (y0, y1), (z0, z1) = world_bounds(obj)
    if axis.upper() == "X":
        a0, a1 = x0, x1
        plane_no = (1.0, 0.0, 0.0)

        def plane_co(cut: float):
            return (cut, 0.0, 0.0)
    elif axis.upper() == "Y":
        a0, a1 = y0, y1
        plane_no = (0.0, 1.0, 0.0)

        def plane_co(cut: float):
            return (0.0, cut, 0.0)
    else:
        a0, a1 = z0, z1
        plane_no = (0.0, 0.0, 1.0)

        def plane_co(cut: float):
            return (0.0, 0.0, cut)

    span = a1 - a0
    if span < 0.08:
        return [obj]

    pieces: list[bpy.types.Object] = []
    remaining = obj
    for i in range(bands - 1):
        cut = a0 + span * ((i + 1) / bands)
        bpy.ops.object.select_all(action="DESELECT")
        remaining.select_set(True)
        bpy.context.view_layer.objects.active = remaining

        bpy.ops.object.duplicate()
        lower = bpy.context.active_object
        bpy.ops.object.select_all(action="DESELECT")
        lower.select_set(True)
        bpy.context.view_layer.objects.active = lower
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.bisect(
            plane_co=plane_co(cut),
            plane_no=plane_no,
            clear_inner=False,
            clear_outer=True,
            use_fill=True,
        )
        bpy.ops.object.mode_set(mode="OBJECT")

        bpy.ops.object.select_all(action="DESELECT")
        remaining.select_set(True)
        bpy.context.view_layer.objects.active = remaining
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.bisect(
            plane_co=plane_co(cut),
            plane_no=plane_no,
            clear_inner=True,
            clear_outer=False,
            use_fill=True,
        )
        bpy.ops.object.mode_set(mode="OBJECT")

        if len(lower.data.vertices) >= 3:
            pieces.append(lower)
        else:
            bpy.data.objects.remove(lower, do_unlink=True)

    if len(remaining.data.vertices) >= 3:
        pieces.append(remaining)
    else:
        bpy.data.objects.remove(remaining, do_unlink=True)

    return pieces


def split_by_z_bands(obj: bpy.types.Object, bands: int) -> list[bpy.types.Object]:
    """Bisect obj into `bands` horizontal slabs (lowest → highest)."""
    return split_by_axis_bands(obj, bands, axis="Z")


def piece_centroid(obj: bpy.types.Object) -> Vector:
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(obj)
    return Vector((0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)))


def even_batches(ids: list[str], n: int) -> list[list[str]]:
    if n <= 0:
        return []
    if not ids:
        return [[] for _ in range(n)]
    # Contiguous Z-order chunks across n stages.
    size = math.ceil(len(ids) / n)
    batches = [ids[i * size : (i + 1) * size] for i in range(n)]
    while len(batches) < n:
        batches.append([])
    return batches[:n]


def build_manifest(
    pieces: list[tuple[str, str, bpy.types.Object]],
    *,
    source_name: str,
    structure_name: str,
    sort_axis: str = "Z",
) -> dict:
    axis = sort_axis.upper()
    enriched = []
    for pid, cat, obj in pieces:
        c = piece_centroid(obj)
        enriched.append((pid, cat, obj, c))
    # Order along assemble axis (Z = bottom→top, X/Y = one side→other).
    if axis == "X":
        enriched.sort(key=lambda t: (t[3].x, t[3].z, t[3].y))
    elif axis == "Y":
        enriched.sort(key=lambda t: (t[3].y, t[3].z, t[3].x))
    else:
        enriched.sort(key=lambda t: (t[3].z, t[3].x, t[3].y))

    piece_defs = []
    ordered_ids: list[str] = []
    for stagger, (pid, cat, obj, c) in enumerate(enriched):
        ordered_ids.append(pid)
        if axis == "Y":
            # Spawn slightly upstream along the span so pieces settle forward.
            outward = Vector((0.0, -1.0 if c.y >= 0 else 1.0, 0.0))
        elif axis == "X":
            outward = Vector((-1.0 if c.x >= 0 else 1.0, 0.0, 0.0))
        else:
            outward = Vector((c.x, c.y, 0.0))
            if outward.length > 1e-4:
                outward.normalize()
            else:
                outward = Vector((1.0, 0.0, 0.0))
        piece_defs.append(
            {
                "id": pid,
                "category": cat,
                "staggerIndex": stagger,
                "spawnOffset": [
                    round(outward.x * OUTWARD, 4),
                    round(outward.y * OUTWARD, 4),
                    round(DROP_Z, 4),
                ],
                "spawnYawDeg": round(10.0 * math.sin(stagger * 0.7), 2),
                "durationSec": 0.40,
            }
        )

    batches = even_batches(ordered_ids, 9)
    cumulative: list[str] = []
    stages: dict[str, list[str]] = {}
    for key, add in zip(STAGE_ORDER, batches):
        for p in add:
            if p not in cumulative:
                cumulative.append(p)
        stages[key] = list(cumulative)
    stages["complete"] = list(ordered_ids)

    return {
        "source": source_name,
        "structureName": structure_name,
        "coordinateSystem": "Z-up",
        "assembleAxis": axis,
        "pieces": piece_defs,
        "stages": stages,
        "stageOrder": list(STAGE_ORDER),
        "tween": {
            "staggerSec": 0.06,
            "ease": "easeOutCubic",
            "startScale": 0.92,
        },
    }


def export_pieces(objs: list[bpy.types.Object], path: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
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


def _import_centered_pile(path: str, name: str) -> bpy.types.Object | None:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    meshes = [
        o
        for o in bpy.data.objects
        if o not in before
        and o.type == "MESH"
        and not o.name.lower().startswith("icosphere")
    ]
    for o in list(bpy.data.objects):
        if o in before:
            continue
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    if not meshes:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    pile = bpy.context.active_object
    pile.name = name
    (x0, x1), (y0, y1), (z0, _z1) = world_bounds(pile)
    for v in pile.data.vertices:
        v.co.x -= 0.5 * (x0 + x1)
        v.co.y -= 0.5 * (y0 + y1)
        v.co.z -= z0
    pile.data.update()
    pile.location = (0.0, 0.0, 0.0)
    return pile


def place_pile_in_box(
    pile: bpy.types.Object,
    px: float,
    py: float,
    z0: float,
    yaw: float,
    scale: float,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    inset: float = 0.04,
) -> float:
    bx0, bx1 = x_min + inset, x_max - inset
    by0, by1 = y_min + inset, y_max - inset
    bw = max(0.05, bx1 - bx0)
    bh = max(0.05, by1 - by0)
    # Expand tiny footprints so piles still have room.
    if bw < 1.2:
        mid = 0.5 * (bx0 + bx1)
        bx0, bx1 = mid - 0.6, mid + 0.6
        bw = 1.2
    if bh < 1.0:
        mid = 0.5 * (by0 + by1)
        by0, by1 = mid - 0.5, mid + 0.5
        bh = 1.0
    px = max(bx0 + 0.08 * bw, min(bx1 - 0.08 * bw, px))
    py = max(by0 + 0.08 * bh, min(by1 - 0.08 * bh, py))
    pile.location = (px, py, z0)
    pile.rotation_euler = (0.0, 0.0, yaw)
    pile.scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    (ox0, ox1), (oy0, oy1), _ = world_bounds(pile)
    ow = max(1e-6, ox1 - ox0)
    oh = max(1e-6, oy1 - oy0)
    cx_p = 0.5 * (ox0 + ox1)
    cy_p = 0.5 * (oy0 + oy1)
    max_hw = max(0.02, min(cx_p - bx0, bx1 - cx_p))
    max_hh = max(0.02, min(cy_p - by0, by1 - cy_p))
    fit = min(1.0, (2.0 * max_hw) / ow, (2.0 * max_hh) / oh, bw / ow, bh / oh)
    if fit < 0.999:
        scale *= fit
        pile.scale = (scale, scale, scale)
        bpy.context.view_layer.update()
        (ox0, ox1), (oy0, oy1), _ = world_bounds(pile)
    dx = dy = 0.0
    if ox0 < bx0:
        dx = bx0 - ox0
    elif ox1 > bx1:
        dx = bx1 - ox1
    if oy0 < by0:
        dy = by0 - oy0
    elif oy1 > by1:
        dy = by1 - oy1
    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
        pile.location.x += dx
        pile.location.y += dy
        bpy.context.view_layer.update()
    return scale


def shrink_joined_to_footprint(
    obj: bpy.types.Object,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    inset: float = 0.02,
) -> float:
    bx0, bx1 = x_min + inset, x_max - inset
    by0, by1 = y_min + inset, y_max - inset
    # Pad tiny station footprints for resource display.
    bw = max(1.2, bx1 - bx0)
    bh = max(1.0, by1 - by0)
    tcx = 0.5 * (x_min + x_max)
    tcy = 0.5 * (y_min + y_max)
    bx0, bx1 = tcx - 0.5 * bw, tcx + 0.5 * bw
    by0, by1 = tcy - 0.5 * bh, tcy + 0.5 * bh
    (ox0, ox1), (oy0, oy1), _ = world_bounds(obj)
    ow = max(1e-6, ox1 - ox0)
    oh = max(1e-6, oy1 - oy0)
    s = min(1.0, bw / ow, bh / oh)
    if s >= 0.999:
        return 1.0
    ocx = 0.5 * (ox0 + ox1)
    ocy = 0.5 * (oy0 + oy1)
    for v in obj.data.vertices:
        v.co.x = tcx + (v.co.x - ocx) * s
        v.co.y = tcy + (v.co.y - ocy) * s
    obj.data.update()
    return s


def export_init(
    footprint: tuple[tuple[float, float], tuple[float, float]],
    piles: list[tuple],
    init_name: str,
) -> None:
    (x_min, x_max), (y_min, y_max) = footprint
    # Ensure a usable pad around tiny props.
    fw = max(1.6, x_max - x_min)
    fd = max(1.4, y_max - y_min)
    cx = 0.5 * (x_min + x_max)
    cy = 0.5 * (y_min + y_max)
    x_min, x_max = cx - 0.5 * fw, cx + 0.5 * fw
    y_min, y_max = cy - 0.5 * fd, cy + 0.5 * fd
    hx, hy = 0.5 * fw, 0.5 * fd

    clear_scene()
    created: list[bpy.types.Object] = []
    for key, name, nx, ny, yaw, scale in piles:
        path = PILE_PATHS.get(key)
        if not path or not os.path.isfile(path):
            print(f"  warn INIT skip missing pile: {key}")
            continue
        px = cx + max(-0.55, min(0.55, nx)) * hx
        py = cy + max(-0.55, min(0.55, ny)) * hy
        pile = _import_centered_pile(path, name)
        if pile is None:
            continue
        used = place_pile_in_box(
            pile, px, py, 0.0, yaw, scale, x_min, x_max, y_min, y_max
        )
        bake_trs(pile)
        zs = [v.co.z for v in pile.data.vertices]
        if zs:
            z0 = min(zs)
            for v in pile.data.vertices:
                v.co.z -= z0
            pile.data.update()
        created.append(pile)
        (wx0, wx1), (wy0, wy1), _ = world_bounds(pile)
        print(
            f"  INIT + {name} @ ({0.5*(wx0+wx1):.2f},{0.5*(wy0+wy1):.2f}) "
            f"scale={used:.2f}"
        )

    if not created:
        print("  warn INIT: no piles")
        return

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    if len(created) > 1:
        bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = init_name.replace(".glb", "")
    fit = shrink_joined_to_footprint(result, x_min, x_max, y_min, y_max)
    if fit < 0.999:
        print(f"  INIT shrink ×{fit:.3f}")

    for out_dir in (VIEWER_OUT, DESKTOP_OUT):
        path = os.path.join(out_dir, init_name)
        bpy.ops.object.select_all(action="DESELECT")
        result.select_set(True)
        bpy.context.view_layer.objects.active = result
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
        print(f"  -> {path} ({os.path.getsize(path)/1024:.1f} KB)")


def classify_band(t: float) -> str:
    """Map 0→1 progress along assemble axis to a category label."""
    if t < 0.18:
        return "Floor"
    if t < 0.72:
        return "Wall"
    if t < 0.88:
        return "Trim"
    return "Roof"


def axis_progress(c: Vector, axis: str, a0: float, a1: float) -> float:
    if axis == "X":
        v = c.x
    elif axis == "Y":
        v = c.y
    else:
        v = c.z
    if a1 <= a0:
        return 0.0
    return max(0.0, min(1.0, (v - a0) / (a1 - a0)))


def process_station(meta: dict) -> None:
    src = os.path.join(SRC_DIR, meta["source"])
    if not os.path.isfile(src):
        raise FileNotFoundError(src)

    print(f"\n######## {meta['structureName']} ########")
    print(f"Source: {src}")
    clear_scene()
    joined = import_joined(src)
    joined.name = meta["id"]
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(joined)
    print(
        f"  footprint X[{x0:.2f},{x1:.2f}] Y[{y0:.2f},{y1:.2f}] "
        f"Z[{z0:.2f},{z1:.2f}]"
    )
    footprint = ((x0, x1), (y0, y1))

    assemble_axis = (meta.get("assemble_axis") or "Z").upper()
    # Auto-pick longest horizontal span for bridges if not set explicitly
    # beyond Z default — bridge meta sets Y.
    if assemble_axis == "AUTO":
        spans = {"X": x1 - x0, "Y": y1 - y0, "Z": z1 - z0}
        assemble_axis = max(spans, key=spans.get)

    parts = split_by_axis_bands(joined, TARGET_PIECES, axis=assemble_axis)
    print(f"  {assemble_axis}-split: {len(parts)} pieces")

    # Drop empties / tiny shards.
    cleaned_objs: list[bpy.types.Object] = []
    for o in parts:
        if len(o.data.vertices) < MIN_PIECE_VERTS:
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        cleaned_objs.append(o)

    if not cleaned_objs:
        raise RuntimeError(f"No pieces for {meta['id']}")

    # If we over-culled, fall back to fewer larger bands.
    if len(cleaned_objs) < 3:
        clear_scene()
        joined = import_joined(src)
        parts = split_by_axis_bands(joined, max(3, len(cleaned_objs) or 3), axis=assemble_axis)
        cleaned_objs = [o for o in parts if len(o.data.vertices) >= 3]
        print(f"  fallback re-split: {len(cleaned_objs)} pieces")

    # Sort along assemble axis and name BA_* pieces.
    def sort_key(o: bpy.types.Object):
        c = piece_centroid(o)
        if assemble_axis == "X":
            return (c.x, c.z, c.y)
        if assemble_axis == "Y":
            return (c.y, c.z, c.x)
        return (c.z, c.x, c.y)

    cleaned_objs.sort(key=sort_key)
    first_c = piece_centroid(cleaned_objs[0])
    last_c = piece_centroid(cleaned_objs[-1])
    if assemble_axis == "X":
        a0, a1 = first_c.x, last_c.x
    elif assemble_axis == "Y":
        a0, a1 = first_c.y, last_c.y
    else:
        a0 = world_bounds(cleaned_objs[0])[2][0]
        a1 = world_bounds(cleaned_objs[-1])[2][1]

    counters = {"Floor": 0, "Wall": 0, "Trim": 0, "Roof": 0}
    cleaned: list[tuple[str, str, bpy.types.Object]] = []
    for o in cleaned_objs:
        c = piece_centroid(o)
        cat = classify_band(axis_progress(c, assemble_axis, a0, a1))
        counters[cat] = counters.get(cat, 0) + 1
        pid = f"BA_{cat}_{counters[cat]:02d}"
        o.name = pid
        bake_trs(o)
        o.location = (0.0, 0.0, 0.0)
        o.rotation_euler = (0.0, 0.0, 0.0)
        o.scale = (1.0, 1.0, 1.0)
        cleaned.append((pid, cat, o))
        (_a), (_b), (pz0, pz1) = world_bounds(o)
        print(
            f"    {pid:14} verts={len(o.data.vertices):4d} "
            f"axis={assemble_axis}@{axis_progress(c, assemble_axis, a0, a1):.2f} "
            f"Z[{pz0:.2f},{pz1:.2f}]"
        )

    manifest = build_manifest(
        cleaned,
        source_name=meta["source"],
        structure_name=meta["structureName"],
        sort_axis=assemble_axis,
    )
    objs = [o for _, _, o in cleaned]

    for out_dir in (VIEWER_OUT, DESKTOP_OUT):
        glb_path = os.path.join(out_dir, meta["outGlb"])
        export_pieces(objs, glb_path)
        print(f"  -> {glb_path} ({os.path.getsize(glb_path)/1024:.1f} KB)")
        man_path = os.path.join(out_dir, meta["outManifest"])
        with open(man_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        print(f"  -> {man_path}")

    export_init(footprint, meta["init_piles"], meta["initGlb"])


def parse_ids() -> list[str]:
    args: list[str] = []
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1 :]
    if not args or any(a.lower() == "all" for a in args):
        return [s["id"] for s in STATIONS]
    wanted = {a.lower().replace("-", "_") for a in args}
    out = []
    for s in STATIONS:
        sid = s["id"]
        aliases = {
            sid,
            sid.replace("_", ""),
            s["source"].replace(".glb", "").lower(),
        }
        if wanted & aliases or any(w in sid for w in wanted):
            out.append(sid)
    return out or [s["id"] for s in STATIONS]


def main() -> None:
    ids = parse_ids()
    print("=== Workstation modular animation ===")
    print(f"Stations: {ids}")
    by_id = {s["id"]: s for s in STATIONS}
    for sid in ids:
        process_station(by_id[sid])
    print("\nDONE — workstation modular assets exported.")


if __name__ == "__main__":
    main()
