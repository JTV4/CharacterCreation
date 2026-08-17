"""
generate_building_whole_construction.py
=======================================
Age-of-Empires style construction stages for BuildingNWhole GLBs
(Buildings 2–8 from ~/Desktop/Buildings/NewBuildings/Completed).

Same pipeline as generate_building1_whole_construction.py:
  INIT       — chalk footprint + resource piles (Sycamore logs, Iron ore,
               Raw/Cooked Catfish, Clay).  No building mesh.
  P1 / P2 / P3 — Z-bisect + scaffolding
  Completed  — exact source building

Sources:
  Preferred (Blender-importable): Completed_decoded/BuildingNWhole.glb
  Fallback: Completed/BuildingNWhole.glb
  Completed stage prefers the original Completed/ file when present
  (keeps meshopt compression for the viewer).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_building_whole_construction.py -- 2 3 4 5 6 7 8
  # optional stage filters: init | p1 | p2 | p3 | complete
  # e.g. -- 3 5 init p1
"""

from __future__ import annotations

import math
import os
import random
import shutil
import sys

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
COMPLETED_DIR = os.path.expanduser(
    "~/Desktop/Buildings/NewBuildings/Completed"
)
DECODED_DIR = os.path.expanduser(
    "~/Desktop/Buildings/NewBuildings/Completed_decoded"
)
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
DESKTOP_OUT = os.path.join(SOURCE_DIR, "Construction")
VIEWER_OUT = os.path.join(ROOT, "viewer/public/buildings/Construction")
VIEWER_COMPLETE = os.path.join(ROOT, "viewer/public/buildings")

os.makedirs(DESKTOP_OUT, exist_ok=True)
os.makedirs(VIEWER_OUT, exist_ok=True)
os.makedirs(VIEWER_COMPLETE, exist_ok=True)
os.makedirs(SOURCE_DIR, exist_ok=True)

RNG_SEED = 20260727

CUT_FRACTIONS = {
    "P1": 0.18,
    "P2": 0.42,
    "P3": 0.72,
}

RECUT = {
    "P1": (0, 0.0, 0.00),
    "P2": (4, 8.0, 0.12),
    "P3": (2, 4.0, 0.06),
}

# Pile placement as fractions of half-width / half-depth.
# Compact two-row layout kept well inside the structure; place_pile_in_box
# further shrinks/nudges so every pile AABB fits the footprint.
# (key, name, nx, ny, yaw, uniform_scale)
#   px = cx + nx*(fw/2), py = cy + ny*(fd/2)
PILE_LAYOUT = [
    ("sycamore_logs", "pile_sycamore_logs", -0.32, -0.32, 0.0, 0.28),
    ("iron_ore", "pile_iron_ore", 0.32, -0.30, 0.2, 0.28),
    ("clay", "pile_clay", -0.38, 0.32, 0.1, 0.40),
    ("grind_coins", "pile_grind_coins", 0.00, 0.36, 0.35, 0.38),
    ("raw_catfish", "pile_raw_catfish", 0.26, 0.36, 0.5, 0.38),
    ("cooked_catfish", "pile_cooked_catfish", 0.42, 0.32, -0.4, 0.38),
]

INIT_PILE_PATHS = {
    "sycamore_logs": os.path.join(VIEWER_COMPLETE, "LogPile_Sycamore.glb"),
    "iron_ore": os.path.join(VIEWER_COMPLETE, "OrePile_Iron.glb"),
    "raw_catfish": os.path.join(VIEWER_COMPLETE, "RawFishPile_Catfish.glb"),
    "cooked_catfish": os.path.join(VIEWER_COMPLETE, "FishPile_Catfish.glb"),
    "clay": os.path.join(VIEWER_COMPLETE, "Clay.glb"),
    "grind_coins": os.path.join(VIEWER_COMPLETE, "CoinPile_Grind.glb"),
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


def resolve_src(building_id: int, prefer_decoded: bool = True) -> str:
    decoded = os.path.join(DECODED_DIR, f"Building{building_id}Whole.glb")
    original = os.path.join(COMPLETED_DIR, f"Building{building_id}Whole.glb")
    if prefer_decoded and os.path.isfile(decoded):
        return decoded
    if os.path.isfile(original):
        return original
    if os.path.isfile(decoded):
        return decoded
    raise FileNotFoundError(
        f"No Building{building_id}Whole.glb in Completed or Completed_decoded"
    )


def import_joined(src: str) -> bpy.types.Object:
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
    """Lowest large-ish +Z face — the main ground floor, not a roof ledge."""
    candidates: list[tuple[float, float]] = []  # (z, area)
    for f in obj.data.polygons:
        if f.normal.z > 0.85:
            candidates.append((f.center.z, f.area))
    if not candidates:
        return None
    # Prefer the lowest Z band that still has meaningful floor area
    # (ignores tiny underground ledges).
    candidates.sort(key=lambda t: t[0])
    z_min_face = candidates[0][0]
    band = [
        (z, a) for z, a in candidates
        if z <= z_min_face + 0.35
    ]
    # Area-weighted average in the lowest band
    total_a = sum(a for _, a in band) or 1.0
    return sum(z * a for z, a in band) / total_a


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


def bisect_keep_above(obj: bpy.types.Object, plane_co: Vector) -> None:
    """Discard everything below plane_co (keep the side along +Z)."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.bisect_plane(
        bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        dist=1e-4,
        plane_co=plane_co,
        plane_no=Vector((0.0, 0.0, 1.0)),
        use_snap_center=False,
        clear_outer=False,
        clear_inner=True,  # remove below the floor
    )
    bm.to_mesh(me)
    bm.free()
    me.update()


def sit_on_ground(obj: bpy.types.Object) -> None:
    """Shift mesh so its lowest vertex sits at Z=0.

    Bake location/rotation/scale into verts first.  Otherwise zeroing
    ``location`` drops any XY offset that lived on the object transform
    (INIT pads join into a dirt box whose origin is at footprint centre).
    """
    normalize_transform(obj)
    (_x), (_y), (z0, _z1) = compute_bounds(obj)
    if abs(z0) < 1e-6:
        return
    for v in obj.data.vertices:
        v.co.z -= z0
    obj.data.update()
    obj.location = (0.0, 0.0, 0.0)


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

    # Prefer centers well inside the box (not on the rim).
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

    # Max half-extent allowed at this center.
    max_hw = max(0.02, min(cx_p - bx0, bx1 - cx_p))
    max_hh = max(0.02, min(cy_p - by0, by1 - cy_p))
    fit = min(1.0, (2.0 * max_hw) / ow, (2.0 * max_hh) / oh)
    # Also never exceed the full box (small buildings).
    fit = min(fit, bw / ow, bh / oh)

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
        # Still nudge if slightly overhanging.
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


def import_pile_object(path: str, name: str) -> bpy.types.Object:
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


def build_init(building_id: int, src: str) -> None:
    """INIT pad aligned to the same floor / XY as P1–P3 / Completed.

    Uses the walkable-floor plane (not raw mesh z_min) so underground legs
    don't sink the chalk pad ~metres below the construction stages.
    """
    tag = f"Building{building_id}Whole"
    print(f"\n=== {tag} INIT — Resource Piles Staging ===")
    tmp = import_joined(src)
    bounds = compute_bounds(tmp)
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
    floor_z = find_walkable_floor_z(tmp)
    print(f"  raw Z[{z_min:.2f},{z_max:.2f}] floor={floor_z}")

    # Match P-stage footprint: strip underground, then measure XY.
    if floor_z is not None and z_min < floor_z - 0.02:
        bisect_keep_above(tmp, Vector((0.0, 0.0, floor_z)))
        bounds = compute_bounds(tmp)
        (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
        print(f"  footprint after floor strip Z[{z_min:.2f},{z_max:.2f}]")

    fw = x_max - x_min
    fd = y_max - y_min
    cx = 0.5 * (x_min + x_max)
    cy = 0.5 * (y_min + y_max)
    hx = fw * 0.5
    hy = fd * 0.5
    # Ground plane = floor (same as P stages before sit_on_ground).
    ground_z = z_min if floor_z is None else z_min
    print(f"  footprint X[{x_min:.2f},{x_max:.2f}] Y[{y_min:.2f},{y_max:.2f}]")
    print(
        "  piles: Sycamore logs, Iron ore, Raw Catfish, Cooked Catfish, "
        "Clay, GrindCoin pile"
    )

    clear_scene()
    created: list = []

    # Resources only — in-game terrain is the floor (no dirt pad / chalk).
    z0 = ground_z
    # Keep pile centers well inside the structure footprint.
    margin = 0.55
    for key, name, nx, ny, yaw, scale in PILE_LAYOUT:
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

    if not created:
        raise RuntimeError(f"INIT for {tag}: no resource piles imported")

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = f"{tag}_INIT"
    fit_s = shrink_joined_to_footprint(result, x_min, x_max, y_min, y_max)
    if fit_s < 0.999:
        print(f"  INIT group shrink-to-footprint ×{fit_s:.3f}")
    # Same final origin as P1–P3: bake XY, then put lowest vertex at Z=0.
    sit_on_ground(result)

    (rx0, rx1), (ry0, ry1), (rz0, rz1) = compute_bounds(result)
    print(
        f"  INIT bounds {rx1 - rx0:.2f} × {ry1 - ry0:.2f} "
        f"(target footprint {fw:.2f} × {fd:.2f})  "
        f"Z[{rz0:.3f},{rz1:.3f}]  cx={(rx0+rx1)/2:.3f} cy={(ry0+ry1)/2:.3f}"
    )
    if (rx1 - rx0) > fw + 0.05 or (ry1 - ry0) > fd + 0.05:
        print("  WARN: INIT still larger than structure footprint")

    for out_dir in (DESKTOP_OUT, VIEWER_OUT):
        path = os.path.join(out_dir, f"{tag}_INIT.glb")
        export_single(result, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def build_progress(building_id: int, src: str, stage: str) -> None:
    tag = f"Building{building_id}Whole"
    print(f"\n=== {tag} {stage} — Construction ===")
    building = import_joined(src)
    building.name = f"{tag}_{stage}"
    bounds = compute_bounds(building)
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
    floor_z = find_walkable_floor_z(building)
    print(f"  raw Z[{z_min:.2f},{z_max:.2f}] floor={floor_z}")

    # Many authored buildings have legs / foundations that dig below the
    # walkable floor.  Strip that underground geometry first so the stage
    # base IS the floor, and scaffolding poles don't hang under ground.
    if floor_z is not None and z_min < floor_z - 0.02:
        print(f"  stripping below floor ({floor_z:.3f}) — was {z_min:.3f}")
        bisect_keep_above(building, Vector((0.0, 0.0, floor_z)))
        bounds = compute_bounds(building)
        (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
        print(f"  after strip Z[{z_min:.2f},{z_max:.2f}]")

    H = max(1e-3, z_max - z_min)
    # Progressive cuts measured from the floor upward.
    cut_z = z_min + CUT_FRACTIONS[stage] * H
    if stage == "P1":
        cut_z = max(cut_z, z_min + 0.35)  # keep a readable foundation band

    print(f"  cut Z={cut_z:.2f} ({(cut_z - z_min) / H * 100:.0f}% of H above floor)")

    bisect_keep_below(building, Vector((0, 0, cut_z)), Vector((0, 0, 1)))

    n_recuts, max_ang_deg, max_dz_frac = RECUT[stage]
    if n_recuts:
        rng = random.Random(RNG_SEED + building_id * 17 + hash(stage) % 1000)
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

    # Scaffolding stands ON the floor (post-strip z_min), never underground.
    scaffold_top = cut_z + (RECUT[stage][2] * H)
    extras = add_scaffolding(
        bounds, z_min, scaffold_top, tag=f"{building_id}_{stage.lower()}",
    )
    print(f"  scaffolding pieces: {len(extras)}")
    result = join_all(building, extras)
    result.name = f"{tag}_{stage}"
    sit_on_ground(result)
    (_x), (_y), (z0, z1) = compute_bounds(result)
    print(
        f"  verts={len(result.data.vertices)} faces={len(result.data.polygons)} "
        f"final Z[{z0:.3f},{z1:.3f}]"
    )

    for out_dir in (DESKTOP_OUT, VIEWER_OUT):
        path = os.path.join(out_dir, f"{tag}_{stage}.glb")
        export_single(result, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def build_completed(building_id: int) -> None:
    """Export Completed with walkable floor at Z=0 (same origin as INIT/P*).

    Keeps underground legs (for planting into terrain) but shifts so the
    floor plane matches P1–P3 / INIT.
    """
    tag = f"Building{building_id}Whole"
    print(f"\n=== {tag} Completed ===")
    src = resolve_src(building_id, prefer_decoded=True)

    # Floor estimate from a joined copy
    joined = import_joined(src)
    floor_z = find_walkable_floor_z(joined)
    print(f"  floor_z={floor_z}")

    meshes = import_multi(src)
    for o in meshes:
        zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
        zmax = max(zs)
        name_l = o.name.lower()
        if "door" in name_l:
            o.name = f"Building{building_id}_Door"
        elif "roof" in name_l or zmax > 5.0:
            o.name = f"Building{building_id}_Roof"
        else:
            o.name = f"Building{building_id}_Walls"

    if floor_z is not None:
        print(f"  shifting floor {floor_z:.3f} → 0")
        for o in meshes:
            for v in o.data.vertices:
                v.co.z -= floor_z
            o.data.update()

    bounds = compute_bounds_multi(meshes)
    print(f"  meshes: {[m.name for m in meshes]}")
    print(f"  bounds {bounds}")
    for out_dir in (SOURCE_DIR, VIEWER_COMPLETE):
        path = os.path.join(out_dir, f"{tag}.glb")
        export_multi(meshes, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def process_building(building_id: int, filters: set[str]) -> None:
    src = resolve_src(building_id, prefer_decoded=True)
    print(f"\n######## Building {building_id} ########")
    print(f"Source: {src}")
    print(f"Size:   {os.path.getsize(src) / 1024 / 1024:.2f} MB")

    def want(*keys: str) -> bool:
        if not filters:
            return True
        return any(k in filters for k in keys)

    if want("init"):
        build_init(building_id, src)
    if want("p1"):
        build_progress(building_id, src, "P1")
    if want("p2"):
        build_progress(building_id, src, "P2")
    if want("p3"):
        build_progress(building_id, src, "P3")
    if want("complete", "completed"):
        build_completed(building_id)


def main() -> None:
    args: list[str] = []
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1:]

    building_ids: list[int] = []
    filters: set[str] = set()
    for a in args:
        if a.isdigit():
            building_ids.append(int(a))
        else:
            filters.add(a.lower())

    if not building_ids:
        building_ids = [2, 3, 4, 5, 6, 7, 8]

    for bid in building_ids:
        if bid == 1:
            print("Skipping Building 1 (use generate_building1_whole_construction.py)")
            continue
        process_building(bid, filters)

    print("\nDONE — BuildingNWhole AoE construction stages exported.")


if __name__ == "__main__":
    main()
