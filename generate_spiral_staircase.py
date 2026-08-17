"""
generate_spiral_staircase.py
============================
Build a game-optimized, UNTEXTURED spiral staircase GLB from Blender
primitives.  Same clean-handoff contract as the bridge / castle wall
generators:

  - Origin at world (0, 0, 0), ground plane at z = 0.
  - Single joined mesh per variant.
  - Baked TRS so downstream bounding-box maths stay honest.
  - Named material slots so a texture artist can paint each part-type
    once without re-splitting the mesh.

Two variants (exported as separate GLBs, registered as stages of one
sidebar entry):

  1. SpiralStaircaseOpen.glb  — open spiral: square central post +
                                wedge treads.  No rail.  Compact and
                                cheap (~400 tris).
  2. SpiralStaircase.glb      — same core, plus outer balusters and a
                                piecewise handrail that follows the
                                outer tread edge (~900 tris).

Geometry
--------
Steps are annular wedges (pie slices with an inner hole cut for the
post).  Each successive step is raised by STEP_RISE and rotated by
STEP_ANGLE around +Z.  The walkable tread spans r ∈ [R_INNER, R_OUTER].

Coordinate convention
---------------------
  +X / +Y = horizontal plane (spiral winds CCW looking down +Z).
  +Z = up.
  Origin at ground level on the central post centre-line.

Outputs:
  ~/Desktop/Models/Buildings/SpiralStaircaseOpen.glb
  ~/Desktop/Models/Buildings/SpiralStaircase.glb
  viewer/public/buildings/SpiralStaircaseOpen.glb
  viewer/public/buildings/SpiralStaircase.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_spiral_staircase.py
"""

from __future__ import annotations

import math
import os

import bpy
import bmesh


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)


# ── Spiral parameters ─────────────────────────────────────────────────────

STEP_COUNT = 12                 # one full turn of 12 treads
STEP_ANGLE = math.radians(30.0) # 360° / 12
STEP_RISE = 0.22                # vertical rise per tread (m)
STEP_THICKNESS = 0.10           # tread slab thickness (m)

R_INNER = 0.28                  # inner tread radius (clears the post)
R_OUTER = 1.35                  # outer tread radius (walkable width ≈ 1.07 m)
ARC_SEGMENTS = 6                # straight edges along the outer/inner arc
                                # of each wedge — keeps the pie silhouette
                                # readable without eating the poly budget

# Central square post — sits inside R_INNER with a small clearance gap.
POST_SIDE = 0.36                # square cross-section
POST_OVERHANG = 0.15            # post top sticks this far above last tread

# Handrail / balusters (railed variant only).
BALUSTER_HEIGHT = 0.85
BALUSTER_SIZE = 0.05            # square cross-section
RAIL_SIZE = 0.06                # square handrail cross-section
RAIL_INSET = 0.04               # rail sits slightly inside the outer edge


# ── Materials ─────────────────────────────────────────────────────────────

MATERIAL_COLORS = {
    "stair_steps":    (0.42, 0.42, 0.45),   # cool grey stone treads
    "stair_post":     (0.38, 0.26, 0.15),   # warm brown central post
    "stair_baluster": (0.45, 0.32, 0.18),   # slightly lighter wood
    "stair_rail":     (0.48, 0.34, 0.19),   # handrail wood
}


def make_material(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        color = MATERIAL_COLORS.get(name, (0.5, 0.5, 0.5))
        principled.inputs["Base Color"].default_value = (*color, 1.0)
        if "step" in name:
            principled.inputs["Roughness"].default_value = 0.85
        else:
            principled.inputs["Roughness"].default_value = 0.7
    return mat


# ── Scene helpers ─────────────────────────────────────────────────────────

def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials):
        for datablock in list(block):
            block.remove(datablock)


def add_box(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    material_name: str,
    obj_name: str,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = obj_name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(make_material(material_name))
    return obj


def join_group(objects: list[bpy.types.Object], name: str) -> bpy.types.Object:
    """Join a list of mesh objects into one, preserving material slots."""
    if not objects:
        raise ValueError("join_group called with empty object list")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    return joined


def normalize_transform(obj: bpy.types.Object) -> None:
    """Bake location/rotation/scale into mesh data, then re-centre origin
    at world (0,0,0) without moving the geometry in world space."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # Keep geometry where it is; put object origin at world origin so
    # the asset drops in at (0,0,0) with its feet on the ground plane.
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")


def export_glb(obj: bpy.types.Object, out_path: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        use_selection=True,
        export_format="GLB",
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
    )


def mesh_stats(obj: bpy.types.Object) -> tuple[int, int, int, list[str]]:
    mesh = obj.data
    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    mats = [slot.material.name for slot in obj.material_slots if slot.material]
    return len(mesh.vertices), len(mesh.polygons), tris, mats


def bounds_str(obj: bpy.types.Object) -> str:
    xs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not xs:
        return "(empty)"
    min_x = min(v.x for v in xs); max_x = max(v.x for v in xs)
    min_y = min(v.y for v in xs); max_y = max(v.y for v in xs)
    min_z = min(v.z for v in xs); max_z = max(v.z for v in xs)
    return (
        f"X[{min_x:+.3f}, {max_x:+.3f}]  "
        f"Y[{min_y:+.3f}, {max_y:+.3f}]  "
        f"Z[{min_z:+.3f}, {max_z:+.3f}]"
    )


# ── Geometry builders ─────────────────────────────────────────────────────

def _annular_wedge_bmesh(
    angle_start: float,
    angle_end: float,
    z_bottom: float,
    z_top: float,
    r_inner: float,
    r_outer: float,
    arc_segments: int,
    material_name: str,
    obj_name: str,
) -> bpy.types.Object:
    """Build one tread as an extruded annular sector (pie slice with
    the centre cut out for the post).  Arc edges are discretised into
    `arc_segments` straight segments so the outer silhouette reads as
    a smooth curve without a high poly count."""
    bm = bmesh.new()

    # Sample the arc from angle_start → angle_end inclusive.
    # n_pts = arc_segments + 1 points along each radius.
    n_pts = arc_segments + 1
    outer_bottom: list = []
    outer_top: list = []
    inner_bottom: list = []
    inner_top: list = []

    for i in range(n_pts):
        t = i / arc_segments
        ang = angle_start + (angle_end - angle_start) * t
        c, s = math.cos(ang), math.sin(ang)
        outer_bottom.append(bm.verts.new((r_outer * c, r_outer * s, z_bottom)))
        outer_top.append(bm.verts.new((r_outer * c, r_outer * s, z_top)))
        inner_bottom.append(bm.verts.new((r_inner * c, r_inner * s, z_bottom)))
        inner_top.append(bm.verts.new((r_inner * c, r_inner * s, z_top)))

    # Top face (walkable tread) — outer arc forward, then inner arc back.
    top_loop = list(outer_top) + list(reversed(inner_top))
    bm.faces.new(top_loop)

    # Bottom face — reverse winding so the normal points down.
    bot_loop = list(outer_bottom) + list(reversed(inner_bottom))
    bm.faces.new(list(reversed(bot_loop)))

    # Outer curved wall.
    for i in range(arc_segments):
        bm.faces.new([
            outer_bottom[i], outer_bottom[i + 1],
            outer_top[i + 1], outer_top[i],
        ])

    # Inner curved wall (faces the post).
    for i in range(arc_segments):
        bm.faces.new([
            inner_bottom[i + 1], inner_bottom[i],
            inner_top[i], inner_top[i + 1],
        ])

    # Radial end faces (the two "cut" sides of the pie slice).
    bm.faces.new([
        outer_bottom[0], outer_top[0],
        inner_top[0], inner_bottom[0],
    ])
    bm.faces.new([
        outer_bottom[-1], inner_bottom[-1],
        inner_top[-1], outer_top[-1],
    ])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    mesh = bpy.data.meshes.new(f"{obj_name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(obj_name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(make_material(material_name))
    return obj


def build_central_post(total_height: float) -> bpy.types.Object:
    return add_box(
        center=(0.0, 0.0, total_height / 2.0),
        size=(POST_SIDE, POST_SIDE, total_height),
        material_name="stair_post",
        obj_name="stair_post",
    )


def build_steps() -> list[bpy.types.Object]:
    steps: list[bpy.types.Object] = []
    for i in range(STEP_COUNT):
        ang0 = i * STEP_ANGLE
        ang1 = (i + 1) * STEP_ANGLE
        # Bottom of tread i sits at i * STEP_RISE; the first tread's
        # bottom is at z=0 so the staircase rests on the ground.
        z_bot = i * STEP_RISE
        z_top = z_bot + STEP_THICKNESS
        steps.append(_annular_wedge_bmesh(
            angle_start=ang0,
            angle_end=ang1,
            z_bottom=z_bot,
            z_top=z_top,
            r_inner=R_INNER,
            r_outer=R_OUTER,
            arc_segments=ARC_SEGMENTS,
            material_name="stair_steps",
            obj_name=f"stair_step_{i:02d}",
        ))
    return steps


def _outer_edge_point(step_index: float, radius: float) -> tuple[float, float, float]:
    """World-space point on the outer spiral at a fractional step index.
    z rides the TOP of each tread so balusters / rails sit on the
    walkable surface."""
    ang = step_index * STEP_ANGLE
    # For integer step indices, land on the START edge of that tread;
    # for half-integers, land mid-tread.  z always follows the tread
    # whose floor the point sits on (floor of step_index).
    tread_i = int(math.floor(step_index + 1e-9))
    tread_i = max(0, min(STEP_COUNT - 1, tread_i))
    z = tread_i * STEP_RISE + STEP_THICKNESS
    return (radius * math.cos(ang), radius * math.sin(ang), z)


def build_balusters_and_rail() -> list[bpy.types.Object]:
    """One baluster at the outer-start corner of every tread, plus a
    piecewise handrail connecting consecutive baluster tops.  Also a
    final baluster at the outer-end of the last tread so the rail
    doesn't dead-end mid-air."""
    created: list[bpy.types.Object] = []
    r_rail = R_OUTER - RAIL_INSET

    # Baluster positions: start of each tread + end of last tread.
    baluster_indices = list(range(STEP_COUNT)) + [STEP_COUNT]
    baluster_tops: list[tuple[float, float, float]] = []

    for bi, step_i in enumerate(baluster_indices):
        # Cap the index used for z / angle sampling.
        sample_i = min(step_i, STEP_COUNT - 1 + 0.999)
        if step_i >= STEP_COUNT:
            # End of last tread.
            px = r_rail * math.cos(STEP_COUNT * STEP_ANGLE)
            py = r_rail * math.sin(STEP_COUNT * STEP_ANGLE)
            pz = (STEP_COUNT - 1) * STEP_RISE + STEP_THICKNESS
        else:
            px, py, pz = _outer_edge_point(float(step_i), r_rail)

        bal_z_center = pz + BALUSTER_HEIGHT / 2.0
        created.append(add_box(
            center=(px, py, bal_z_center),
            size=(BALUSTER_SIZE, BALUSTER_SIZE, BALUSTER_HEIGHT),
            material_name="stair_baluster",
            obj_name=f"stair_baluster_{bi:02d}",
        ))
        baluster_tops.append((px, py, pz + BALUSTER_HEIGHT))

    # Handrail segments between consecutive baluster tops.  Each
    # segment is a box stretched along the chord, then rotated in
    # yaw + pitch to align with the chord direction.
    for i in range(len(baluster_tops) - 1):
        a = baluster_tops[i]
        b = baluster_tops[i + 1]
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 1e-6:
            continue
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, (a[2] + b[2]) / 2.0)
        yaw = math.atan2(dy, dx)
        # Pitch: angle above the horizontal XY plane.  A default cube
        # stretched along local +X needs a rotation of (0, -pitch, yaw)
        # in Blender's XYZ Euler so +X lands on the chord direction.
        horiz = math.sqrt(dx * dx + dy * dy)
        pitch = math.atan2(dz, horiz)
        created.append(add_box(
            center=mid,
            size=(length, RAIL_SIZE, RAIL_SIZE),
            material_name="stair_rail",
            obj_name=f"stair_rail_{i:02d}",
            rotation=(0.0, -pitch, yaw),
        ))

    return created


# ── Build + export ────────────────────────────────────────────────────────

def _post_height() -> float:
    last_tread_top = (STEP_COUNT - 1) * STEP_RISE + STEP_THICKNESS
    return last_tread_top + POST_OVERHANG


def build_and_export(with_rail: bool, out_name: str) -> None:
    clear_scene()
    created: list[bpy.types.Object] = []
    created.append(build_central_post(_post_height()))
    created.extend(build_steps())
    if with_rail:
        created.extend(build_balusters_and_rail())

    label = "spiral_staircase" if with_rail else "spiral_staircase_open"
    joined = join_group(created, label)
    normalize_transform(joined)

    verts, faces, tris, mats = mesh_stats(joined)
    print(f"  [{label}] verts={verts}, faces={faces}, tris={tris}, "
          f"materials={len(mats)}: {', '.join(mats)}")
    print(f"  [{label}] bounds: {bounds_str(joined)}")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, out_name)
        export_glb(joined, path)
        size_kb = os.path.getsize(path) / 1024.0
        print(f"  -> {path} ({size_kb:.1f} KB)")


def main() -> None:
    total_h = _post_height()
    print(f"Source output dir: {SOURCE_DIR}")
    print(f"Viewer output dir: {VIEWER_DIR}")
    print(
        f"Spiral: {STEP_COUNT} steps × {math.degrees(STEP_ANGLE):.0f}° / "
        f"{STEP_RISE:.2f} m rise → one full turn, post height {total_h:.2f} m, "
        f"tread r=[{R_INNER:.2f}, {R_OUTER:.2f}] m"
    )

    print("\n=== Spiral Staircase (Open) ===")
    build_and_export(with_rail=False, out_name="SpiralStaircaseOpen.glb")

    print("\n=== Spiral Staircase (Railed) ===")
    build_and_export(with_rail=True, out_name="SpiralStaircase.glb")

    print("\nDONE — spiral staircase (2 variants) exported.")


if __name__ == "__main__":
    main()
