"""
generate_building1_whole_construction.py
========================================
Age-of-Empires style construction stages for the EXACT authored
Building1Whole GLB (walls + hinged door + round-tile roof).

Stages (viewer labels):
  INIT       — chalk footprint + one group of resource piles used to
               build the cottage (Sycamore logs, Iron ore, Raw/Cooked
               Catfish, Clay).  No building mesh on site.
  P1         — foundation / rock base rising (low Z cut) + short scaffolding
  P2         — walls mid-height, jagged masonry top + scaffolding
  P3         — walls + door in, roof half-up, scaffolding remains
  Completed  — exact source building (3 meshes preserved)

Source (default):
  ~/Desktop/Building1Whole_jal0l1 (1).glb

Outputs (Desktop + viewer):
  Construction/Building1Whole_INIT.glb
  Construction/Building1Whole_P1.glb
  Construction/Building1Whole_P2.glb
  Construction/Building1Whole_P3.glb
  Building1Whole.glb                  (Completed — exact source, normalized)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_building1_whole_construction.py
  # optional filters after -- : init | p1 | p2 | p3 | complete
  # optional source path: -- /path/to/source.glb
"""

from __future__ import annotations

import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SRC = os.path.expanduser("~/Desktop/Building1Whole_jal0l1 (1).glb")
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
DESKTOP_OUT = os.path.join(SOURCE_DIR, "Construction")
VIEWER_OUT = os.path.join(ROOT, "viewer/public/buildings/Construction")
VIEWER_COMPLETE = os.path.join(ROOT, "viewer/public/buildings")

os.makedirs(DESKTOP_OUT, exist_ok=True)
os.makedirs(VIEWER_OUT, exist_ok=True)
os.makedirs(VIEWER_COMPLETE, exist_ok=True)
os.makedirs(SOURCE_DIR, exist_ok=True)

RNG_SEED = 20260727

# Height fractions of (z_max - z_min) for progressive cuts.
# Tuned for this cottage: rock/plinth → mid walls → partial roof.
CUT_FRACTIONS = {
    "P1": 0.18,   # foundation / rock base kick-wall
    "P2": 0.42,   # walls mid-height (below eave)
    "P3": 0.72,   # roof going up
}

# Jagged masonry re-cuts (AoE unfinished look)
RECUT = {
    "P1": (0, 0.0, 0.00),
    "P2": (4, 8.0, 0.12),
    "P3": (2, 4.0, 0.06),
}


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_material(name: str, color_rgb, roughness: float = 0.85) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (*color_rgb, 1.0)
        principled.inputs["Roughness"].default_value = roughness
    return mat


def import_joined(src: str) -> bpy.types.Object:
    """Import GLB, bake TRS, join all meshes (for bisect stages)."""
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No meshes in {src}")
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.active_object


def import_multi(src: str) -> list[bpy.types.Object]:
    """Import GLB keeping separate meshes (Completed)."""
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No meshes in {src}")
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def compute_bounds(obj: bpy.types.Object):
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def compute_bounds_multi(objs: list[bpy.types.Object]):
    coords = []
    for obj in objs:
        coords.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
    xs = [v.x for v in coords]
    ys = [v.y for v in coords]
    zs = [v.z for v in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def find_walkable_floor_z(obj: bpy.types.Object) -> float | None:
    lowest = None
    for f in obj.data.polygons:
        if f.normal.z > 0.85:
            if lowest is None or f.center.z < lowest:
                lowest = f.center.z
    return lowest


def bisect_keep_below(obj: bpy.types.Object, plane_co: Vector, plane_no: Vector) -> None:
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.bisect_plane(
        bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        dist=1e-4,
        plane_co=plane_co,
        plane_no=plane_no,
        use_snap_center=False,
        clear_outer=True,
        clear_inner=False,
    )
    bm.to_mesh(me)
    bm.free()
    me.update()


def normalize_transform(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def export_single(obj: bpy.types.Object, path: str) -> None:
    normalize_transform(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
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


def export_multi(objs: list[bpy.types.Object], path: str) -> None:
    for o in objs:
        normalize_transform(o)
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


def add_scaffolding(bounds, z_min: float, z_max: float, tag: str) -> list:
    (x_min, x_max), (y_min, y_max), _ = bounds
    offset = 0.18
    pole_radius = 0.05
    pole_top = z_max + 0.40
    wood_mat = make_material(f"scaffold_wood_{tag}", (0.42, 0.26, 0.13), 0.90)
    created = []
    corners = [
        (x_min - offset, y_min - offset),
        (x_max + offset, y_min - offset),
        (x_max + offset, y_max + offset),
        (x_min - offset, y_max + offset),
    ]
    pole_height = max(0.5, pole_top - z_min)
    pole_mid_z = z_min + pole_height / 2.0
    for cx, cy in corners:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=pole_radius, depth=pole_height, location=(cx, cy, pole_mid_z),
        )
        pole = bpy.context.active_object
        pole.name = f"scaffold_pole_{tag}"
        pole.data.materials.clear()
        pole.data.materials.append(wood_mat)
        created.append(pole)

    for frac in (0.40, 0.90):
        cb_z = z_min + pole_height * frac
        cb_len = (x_max - x_min) + 2 * offset
        bpy.ops.mesh.primitive_cylinder_add(
            radius=pole_radius * 0.7,
            depth=cb_len,
            location=(0.0, y_max + offset, cb_z),
            rotation=(0.0, math.pi / 2.0, 0.0),
        )
        cb = bpy.context.active_object
        cb.name = f"scaffold_crossbar_{tag}"
        cb.data.materials.clear()
        cb.data.materials.append(wood_mat)
        created.append(cb)
        if frac == 0.40:
            bpy.ops.mesh.primitive_cylinder_add(
                radius=pole_radius * 0.6,
                depth=math.hypot(x_max - x_min + 2 * offset, pole_height * 0.5),
                location=(0.0, y_min - offset, z_min + pole_height * 0.4),
                rotation=(0.0, math.pi / 2.0 + math.radians(20), 0.0),
            )
            brace = bpy.context.active_object
            brace.name = f"scaffold_brace_{tag}"
            brace.data.materials.clear()
            brace.data.materials.append(wood_mat)
            created.append(brace)
    return created


def join_all(target: bpy.types.Object, extras: list) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    for o in extras:
        o.select_set(True)
    bpy.context.view_layer.objects.active = target
    if extras:
        bpy.ops.object.join()
    return bpy.context.active_object


def add_box(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    mat: bpy.types.Material,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


# Resource piles placed on INIT (viewer/public/buildings copies).
INIT_PILE_PATHS = {
    "sycamore_logs": os.path.join(VIEWER_COMPLETE, "LogPile_Sycamore.glb"),
    "iron_ore": os.path.join(VIEWER_COMPLETE, "OrePile_Iron.glb"),
    "raw_catfish": os.path.join(VIEWER_COMPLETE, "RawFishPile_Catfish.glb"),
    "cooked_catfish": os.path.join(VIEWER_COMPLETE, "FishPile_Catfish.glb"),
    "clay": os.path.expanduser("~/Desktop/Models/Rocks/Clay.glb"),
    "grind_coins": os.path.join(VIEWER_COMPLETE, "CoinPile_Grind.glb"),
}


def import_pile_object(path: str, name: str) -> bpy.types.Object:
    """Import a pile GLB into the current scene, join to one mesh, sit on Z=0."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()

    meshes: list[bpy.types.Object] = []
    for o in list(bpy.data.objects):
        if o in before:
            continue
        if o.type == "MESH" and not o.name.lower().startswith("icosphere"):
            meshes.append(o)
        else:
            bpy.data.objects.remove(o, do_unlink=True)

    if not meshes:
        raise RuntimeError(f"No mesh in pile {path}")

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
    return obj


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
    inset: float = 0.10,
) -> float:
    """Place pile and shrink/nudge so its XY AABB stays inside the box."""
    bx0, bx1 = x_min + inset, x_max - inset
    by0, by1 = y_min + inset, y_max - inset
    bw = max(0.05, bx1 - bx0)
    bh = max(0.05, by1 - by0)

    px = max(bx0 + 0.05 * bw, min(bx1 - 0.05 * bw, px))
    py = max(by0 + 0.05 * bh, min(by1 - 0.05 * bh, py))

    pile.location = (px, py, z0)
    pile.rotation_euler = (0.0, 0.0, yaw)
    pile.scale = (scale, scale, scale)
    bpy.context.view_layer.update()

    (ox0, ox1), (oy0, oy1), _ = compute_bounds(pile)
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
        (ox0, ox1), (oy0, oy1), _ = compute_bounds(pile)

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
    inset: float = 0.05,
) -> float:
    """Final safety: uniform-scale joined INIT so it fits the structure XY."""
    bx0, bx1 = x_min + inset, x_max - inset
    by0, by1 = y_min + inset, y_max - inset
    bw = max(0.05, bx1 - bx0)
    bh = max(0.05, by1 - by0)
    (ox0, ox1), (oy0, oy1), _ = compute_bounds(obj)
    ow = max(1e-6, ox1 - ox0)
    oh = max(1e-6, oy1 - oy0)
    s = min(1.0, bw / ow, bh / oh)
    if s >= 0.999:
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
            for v in obj.data.vertices:
                v.co.x += dx
                v.co.y += dy
            obj.data.update()
        return 1.0

    ocx = 0.5 * (ox0 + ox1)
    ocy = 0.5 * (oy0 + oy1)
    tcx = 0.5 * (bx0 + bx1)
    tcy = 0.5 * (by0 + by1)
    for v in obj.data.vertices:
        v.co.x = tcx + (v.co.x - ocx) * s
        v.co.y = tcy + (v.co.y - ocy) * s
    obj.data.update()
    return s


def build_init(src: str) -> None:
    """AoE INIT — resource piles INSIDE the same XY footprint as Completed."""
    print("\n=== INIT — Resource Piles Staging ===")
    tmp = import_joined(src)
    bounds = compute_bounds(tmp)
    (x_min, x_max), (y_min, y_max), (z_min, _z_max) = bounds
    fw = x_max - x_min
    fd = y_max - y_min
    cx = 0.5 * (x_min + x_max)
    cy = 0.5 * (y_min + y_max)
    hx = fw * 0.5
    hy = fd * 0.5
    print(f"  footprint X[{x_min:.2f},{x_max:.2f}] Y[{y_min:.2f},{y_max:.2f}]")
    print(
        "  piles: Sycamore logs, Iron ore, Raw Catfish, Cooked Catfish, "
        "Clay, GrindCoin pile"
    )
    print("  (piles clamped to structure footprint)")

    clear_scene()
    created: list = []

    z0 = z_min
    # Compact two-row layout (fractions of half-width/depth).
    placements = [
        ("sycamore_logs", "pile_sycamore_logs", -0.32, -0.32, 0.0, 0.28),
        ("iron_ore", "pile_iron_ore", 0.32, -0.30, 0.2, 0.28),
        ("clay", "pile_clay", -0.38, 0.32, 0.1, 0.40),
        ("grind_coins", "pile_grind_coins", 0.00, 0.36, 0.35, 0.38),
        ("raw_catfish", "pile_raw_catfish", 0.26, 0.36, 0.5, 0.38),
        ("cooked_catfish", "pile_cooked_catfish", 0.42, 0.32, -0.4, 0.38),
    ]
    margin = 0.55
    for key, name, nx, ny, yaw, scale in placements:
        path = INIT_PILE_PATHS[key]
        px = cx + max(-margin, min(margin, nx)) * hx
        py = cy + max(-margin, min(margin, ny)) * hy
        pile = import_pile_object(path, name)
        used = place_pile_in_box(
            pile, px, py, z0, yaw, scale, x_min, x_max, y_min, y_max
        )
        print(
            f"  + {name} ← {os.path.basename(path)} "
            f"@ ({pile.location.x:.2f},{pile.location.y:.2f}) scale={used:.2f}"
        )
        bpy.ops.object.select_all(action="DESELECT")
        pile.select_set(True)
        bpy.context.view_layer.objects.active = pile
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        created.append(pile)

    print(f"  pieces: {len(created)}")

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = "Building1Whole_INIT"
    fit_s = shrink_joined_to_footprint(result, x_min, x_max, y_min, y_max)
    if fit_s < 0.999:
        print(f"  INIT group shrink-to-footprint ×{fit_s:.3f}")

    (rx0, rx1), (ry0, ry1), (rz0, rz1) = compute_bounds(result)
    print(
        f"  INIT bounds X[{rx0:.2f},{rx1:.2f}] ({rx1 - rx0:.2f})  "
        f"Y[{ry0:.2f},{ry1:.2f}] ({ry1 - ry0:.2f})  "
        f"(target footprint {fw:.2f} × {fd:.2f})"
    )
    if (rx1 - rx0) > fw + 0.05 or (ry1 - ry0) > fd + 0.05:
        print("  WARN: INIT still larger than structure footprint")

    for out_dir in (DESKTOP_OUT, VIEWER_OUT):
        path = os.path.join(out_dir, "Building1Whole_INIT.glb")
        export_single(result, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def build_progress(src: str, stage: str) -> None:
    """P1 / P2 / P3 — bisect source + scaffolding."""
    print(f"\n=== {stage} — Construction ===")
    building = import_joined(src)
    building.name = f"Building1Whole_{stage}"
    bounds = compute_bounds(building)
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
    H = z_max - z_min
    floor_z = find_walkable_floor_z(building)

    cut_z = z_min + CUT_FRACTIONS[stage] * H
    # P1: never cut below floor + kick
    if stage == "P1" and floor_z is not None:
        cut_z = max(cut_z, floor_z + 0.12)

    print(f"  bounds Z[{z_min:.2f},{z_max:.2f}] H={H:.2f} floor={floor_z}")
    print(f"  cut Z={cut_z:.2f} ({(cut_z - z_min) / H * 100:.0f}% of H)")

    bisect_keep_below(building, Vector((0, 0, cut_z)), Vector((0, 0, 1)))

    n_recuts, max_ang_deg, max_dz_frac = RECUT[stage]
    if n_recuts:
        rng = random.Random(RNG_SEED + hash(stage) % 1000)
        max_angle = math.radians(max_ang_deg)
        max_dz = max_dz_frac * H
        for _ in range(n_recuts):
            axis_theta = rng.uniform(0, 2 * math.pi)
            axis = Vector((math.cos(axis_theta), math.sin(axis_theta), 0.0))
            tilt = rng.uniform(-max_angle, max_angle)
            n = Vector((
                math.sin(tilt) * axis.y,
                -math.sin(tilt) * axis.x,
                math.cos(tilt),
            )).normalized()
            dz = rng.uniform(-max_dz, max_dz)
            co = Vector((
                rng.uniform(x_min, x_max) * 0.25,
                rng.uniform(y_min, y_max) * 0.25,
                cut_z + dz,
            ))
            bisect_keep_below(building, co, n)
        print(f"  jagged re-cuts: {n_recuts}")

    scaffold_top = cut_z + (RECUT[stage][2] * H)
    extras = add_scaffolding(bounds, z_min, scaffold_top, tag=stage.lower())
    print(f"  scaffolding pieces: {len(extras)}")
    result = join_all(building, extras)
    result.name = f"Building1Whole_{stage}"
    print(f"  verts={len(result.data.vertices)} faces={len(result.data.polygons)}")

    for out_dir in (DESKTOP_OUT, VIEWER_OUT):
        path = os.path.join(out_dir, f"Building1Whole_{stage}.glb")
        export_single(result, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def build_completed(src: str) -> None:
    """Completed — exact source meshes, normalized TRS."""
    print("\n=== Completed — Exact source ===")
    meshes = import_multi(src)
    # Friendly names by role (bounds heuristic)
    for o in meshes:
        zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
        zmax = max(zs)
        name_l = o.name.lower()
        if "door" in name_l:
            o.name = "Building1_Door"
        elif "roof" in name_l or zmax > 5.0:
            o.name = "Building1_Roof"
        else:
            o.name = "Building1_Walls"
    bounds = compute_bounds_multi(meshes)
    print(f"  meshes: {[m.name for m in meshes]}")
    print(f"  bounds {bounds}")

    for out_dir in (SOURCE_DIR, VIEWER_COMPLETE):
        path = os.path.join(out_dir, "Building1Whole.glb")
        export_multi(meshes, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def main() -> None:
    src = DEFAULT_SRC
    args: list[str] = []
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]
    # First non-flag path-looking arg can override source
    filters: set[str] = set()
    for a in args:
        if a.endswith(".glb") or a.endswith(".gltf") or "/" in a or a.startswith("~"):
            src = os.path.expanduser(a)
        else:
            filters.add(a.lower())

    if not os.path.isfile(src):
        raise FileNotFoundError(src)

    print(f"Source: {src}")
    print(f"Size:   {os.path.getsize(src) / 1024 / 1024:.2f} MB")

    def want(*keys: str) -> bool:
        if not filters:
            return True
        return any(k in filters for k in keys)

    if want("init"):
        build_init(src)
    if want("p1"):
        build_progress(src, "P1")
    if want("p2"):
        build_progress(src, "P2")
    if want("p3"):
        build_progress(src, "P3")
    if want("complete", "completed"):
        build_completed(src)
    print("\nDONE — Building1Whole AoE construction stages exported.")


if __name__ == "__main__":
    main()
