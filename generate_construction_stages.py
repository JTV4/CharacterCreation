"""
generate_construction_stages.py
================================
Slice every source building GLB at three progressively higher Z-cuts
to produce foundation → half-walls → nearly-complete construction
sequences, and attach scaffolding cylinders around the perimeter of
the two upper stages so the WIP look reads clearly.

Runs over ALL buildings listed in `BUILDING_IDS` below.  Building6 is
deliberately excluded per user request.

Per-building auto-detection
---------------------------
Every source building in this project follows the SAME baked-mesh
pattern (verified by `inspect_all_buildings.py`):

  - Single merged mesh with one baked_material.
  - A base plate at z=0 with all faces pointing DOWN (-Z).  This plate
    is backface-culled from any above-ground camera, so if the Stage-1
    cut sits at or below the walkable floor's height the resulting
    slice renders as an invisible plate + wireframe wall stubs.
  - A walkable floor slightly above z=0 (measured range: z ≈ 0.08 to
    0.13).  This is the LOWEST +Z-facing face.
  - Walls / windows / roof stacked above, up to some z_max in the
    range 1.5 – 2.76 m depending on the building.

Because the walkable floor height varies per building, Stage-1's cut
Z is auto-computed as `max(0.10 * H + z_min, floor_z + 0.10)`:
that's whichever is HIGHER of "10 % of building height" and "10 cm
above the walkable floor" — guaranteeing the floor is included with a
visible kick-wall on top.  Stages 2 (50 %) and 3 (85 %) are far above
the floor for every building, so they stay simple height-fractions.

Stages
------
  Stage 0  — GROUND BREAKING: cleared dirt plot + corner survey stakes
             + string outline + small dirt pile (no source geometry;
             everything is built from primitives sized to the source
             building's XY bounding box).
  Stage 1  — foundation slab + wooden floor visible
  Stage 2  — half walls, JAGGED top       (+ 4 tilted re-cuts for
                                             masonry-course unevenness)
  Stage 3  — near-complete, no roof       (+ 1 subtle tilted re-cut)

Scaffolding (Stages 2 & 3)
--------------------------
Four vertical wooden poles at the corners of the (slightly expanded)
building footprint, plus two horizontal crossbars on the front face
at mid- and top-height, and one diagonal brace on the back face for
visual variety.  Simple cylinder primitives with a warm-brown
material — enough to read as "construction site" from any camera angle
without competing with the building silhouette.

Transform normalization
-----------------------
Every exported GLB is passed through `normalize_transform()` before
being written, which bakes the object's location / rotation / scale
into its vertex data.  This guarantees the resulting file opens in
Blender or Three.js with `location=(0,0,0)`, `rotation=(0,0,0)`, and
`scale=(1,1,1)`.  That includes the "Complete" mirror of each source
building, which is why we re-export it through Blender instead of
using a `shutil.copy2` (the source ships with a non-1 root scale on
some buildings, e.g. Building1 = 1.1794).

Per-building scale factor
-------------------------
`BUILDING_SCALES` maps every building id to a uniform visual scale
factor.  `BUILDING_AXIS_MULTIPLIERS` (optional) maps a building id to
a `(mx, my, mz)` tuple applied ON TOP of that uniform scale, so a
building can be squished or stretched non-uniformly (e.g. Building 1
uses `(0.70, 0.50, 0.70)` on top of its `3.2` base).  The composed
per-axis scale is baked into the vertex data of Complete + Stage0..3
via `apply_building_scale()`, so exported GLBs still have
scale=(1,1,1) on their root but render at the user-requested size.
Applying the SAME factors to a building AND all its stages guarantees
switching stages in the viewer never changes on-screen size —
critical for the "swap stages" UX.

Outputs (script writes BOTH locations, so the viewer stays in sync
with the Desktop asset library):
  ~/Desktop/Models/Buildings/Construction/BuildingNStageK.glb
  viewer/public/buildings/BuildingN.glb                  (normalized re-export
                                                          of source, scale=1)
  viewer/public/buildings/Construction/BuildingNStageK.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_construction_stages.py
"""

import os
import math
import random
import bpy
import bmesh
from mathutils import Vector

BUILDING_IDS = (1, 2, 3, 4, 5, 7, 8)   # deliberately skips 6

# Per-building UNIFORM scale factor.  Baked into vertex data of every
# exported GLB (Complete + all 4 stages of that building) so the
# finished files still have scale=(1,1,1) on their root — matching the
# "transforms applied" contract established earlier — while rendering
# at the user-requested visual size.  A building AND its stages always
# use the same factor so switching stages in the viewer never changes
# size.
BUILDING_SCALES = {
    1: 3.2,
    2: 3.0,
    3: 2.6,
    4: 3.0,
    5: 1.9,
    7: 2.3,
    8: 2.3,
}

# Optional per-axis multiplier applied ON TOP of BUILDING_SCALES, so a
# building can be squished / stretched non-uniformly (e.g. flattened Y,
# shorter Z) without touching its uniform base scale.  Effective scale
# for a building becomes (base * mx, base * my, base * mz), which is
# baked into vertex data the same way as the uniform case.  Buildings
# not listed here default to (1.0, 1.0, 1.0) — pure uniform scaling.
#
# Note: non-uniform scale turns the round scaffolding poles / stakes /
# strings into ellipses in cross-section.  At the ~2–5 cm radii used
# here that's not visually noticeable, but if a future building needs
# very extreme axis multipliers, revisit `add_scaffolding` and
# `build_stage_zero` to compensate.
BUILDING_AXIS_MULTIPLIERS = {
    1: (0.70, 0.50, 0.70),
}

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
DESKTOP_OUT_DIR = os.path.join(SOURCE_DIR, "Construction")
VIEWER_OUT_DIR = os.path.abspath("viewer/public/buildings/Construction")
VIEWER_SOURCE_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(DESKTOP_OUT_DIR, exist_ok=True)
os.makedirs(VIEWER_OUT_DIR, exist_ok=True)
os.makedirs(VIEWER_SOURCE_DIR, exist_ok=True)

RNG_SEED = 20260714  # reproducible jagged tops across re-runs

# Stage-1 cut Z is auto-computed per building; stages 2 & 3 use a
# straight fraction of building height because they're well above the
# walkable-floor threshold on every source model.
STAGE_FRACTIONS_2_3 = {
    2: 0.50,
    3: 0.85,
}

# Stage-1 auto-cut parameters (see module docstring for the rationale).
STAGE1_MIN_FRACTION_OF_H = 0.10   # never cut lower than 10% of H
STAGE1_FLOOR_KICK        = 0.10   # keep at least 10 cm of wall above floor

# Number of extra tilted re-cuts to apply after the main horizontal cut
# for each stage, to create "masonry course" unevenness.  Stage 1 has
# none (a clean flat slab reads as foundation); Stage 2 gets the most
# aggressive unevenness; Stage 3 is subtly wavy.
STAGE_RECUT_COUNT = {1: 0, 2: 4, 3: 1}
STAGE_RECUT_MAX_ANGLE_DEG = {1: 0.0, 2: 8.0, 3: 3.0}
STAGE_RECUT_MAX_Z_OFFSET  = {1: 0.0, 2: 0.15, 3: 0.05}   # as fraction of H


# ── Helpers ───────────────────────────────────────────────────────────────

def import_source(src_glb: str) -> bpy.types.Object:
    """Wipe the scene and import a building GLB.  Bakes parent transforms
    into world space and joins all meshes.  Returns the resulting mesh."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src_glb)
    bpy.context.view_layer.update()

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No meshes found in {src_glb}")

    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.active_object


def compute_bounds(obj: bpy.types.Object):
    """World-space bounding box after transforms are applied."""
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
    return (
        (min(xs), max(xs)),
        (min(ys), max(ys)),
        (min(zs), max(zs)),
    )


def find_walkable_floor_z(obj: bpy.types.Object) -> float | None:
    """Return the Z of the LOWEST +Z-facing face (walkable floor).

    `None` if the mesh has no upward-facing horizontal faces — in that
    case the caller falls back to a pure height fraction.
    """
    lowest = None
    for f in obj.data.polygons:
        if f.normal.z > 0.85:
            if lowest is None or f.center.z < lowest:
                lowest = f.center.z
    return lowest


def bisect_keep_below(obj: bpy.types.Object, plane_co: Vector, plane_no: Vector) -> None:
    """Bisect the mesh with a plane and delete everything ABOVE it."""
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


def add_scaffolding(bounds, z_min: float, z_max: float, tag: str) -> list:
    """Corner poles + horizontal crossbars + one diagonal brace.

    Returns the list of created objects so the caller can join them.
    Poles sit ~15 cm outside the footprint so they read as external
    scaffolding, not embedded structure.
    """
    (x_min, x_max), (y_min, y_max), _ = bounds
    offset = 0.15
    pole_radius = 0.045
    pole_top = z_max + 0.35

    wood_mat = make_material(f"scaffold_wood_{tag}", (0.42, 0.26, 0.13), 0.90)

    created = []
    corners = [
        (x_min - offset, y_min - offset),
        (x_max + offset, y_min - offset),
        (x_max + offset, y_max + offset),
        (x_min - offset, y_max + offset),
    ]

    pole_height = pole_top - z_min
    pole_mid_z = z_min + pole_height / 2.0

    for (cx, cy) in corners:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=pole_radius,
            depth=pole_height,
            location=(cx, cy, pole_mid_z),
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


def join_all_into(target: bpy.types.Object, extras: list) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    for o in extras:
        o.select_set(True)
    bpy.context.view_layer.objects.active = target
    if extras:
        bpy.ops.object.join()
    return bpy.context.active_object


def normalize_transform(obj: bpy.types.Object) -> None:
    """Bake `obj`'s location/rotation/scale into its vertex data so the
    root transform is identity.  Guarantees every exported GLB opens in
    Blender / Three.js with scale=(1,1,1) and origin at world (0,0,0)."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def effective_scale(building_id: int) -> tuple[float, float, float]:
    """Compose the uniform base scale with the optional per-axis
    multiplier to get the final (sx, sy, sz) applied to a building."""
    base = BUILDING_SCALES.get(building_id, 1.0)
    mx, my, mz = BUILDING_AXIS_MULTIPLIERS.get(building_id, (1.0, 1.0, 1.0))
    return (base * mx, base * my, base * mz)


def apply_building_scale(obj: bpy.types.Object, building_id: int) -> None:
    """Bake the user-requested per-building scale into `obj`'s vertex
    data.  Supports non-uniform (sx, sy, sz) via `BUILDING_AXIS_MULTIPLIERS`.
    Called ONCE per stage (before the two-directory export loop) so
    re-exporting the same object to Desktop + viewer doesn't
    double-apply the scale.

    Sequence:
      1. `normalize_transform` — reset root to identity so the scale is
         applied around a well-defined origin regardless of the object's
         current transform state (Stage-0 joins can leave a non-origin
         location behind).
      2. Set `obj.scale = (sx, sy, sz)`.
      3. `normalize_transform` — bake the scale into vertex data,
         returning the root to identity so every export downstream
         satisfies the "scale=1, transforms applied" contract.
    """
    sx, sy, sz = effective_scale(building_id)
    if sx == 1.0 and sy == 1.0 and sz == 1.0:
        return
    normalize_transform(obj)
    obj.scale = (sx, sy, sz)
    normalize_transform(obj)


def export_glb(obj: bpy.types.Object, out_path: str) -> None:
    """Export `obj` as a self-contained GLB with root transform baked
    into the mesh (scale=1, origin at world 0,0,0)."""
    normalize_transform(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
    )


def stage_cut_z(stage_num: int, z_min: float, z_max: float, floor_z: float | None) -> float:
    """Return the absolute Z of the horizontal bisect plane for a stage."""
    H = z_max - z_min
    if stage_num == 1:
        min_by_fraction = z_min + STAGE1_MIN_FRACTION_OF_H * H
        if floor_z is not None:
            min_by_floor = floor_z + STAGE1_FLOOR_KICK
            return max(min_by_fraction, min_by_floor)
        return min_by_fraction
    return z_min + STAGE_FRACTIONS_2_3[stage_num] * H


def build_stage_zero(src_glb: str, building_id: int) -> None:
    """Build the GROUND-BREAKING stage: a prepared construction site
    sized to the building's XY footprint, with no source geometry.

    Layout (all sized off the source building's world bounds):
      - Dirt plot:  shallow flat cuboid, 30 cm larger than the footprint
                    on each side, sitting from z=0 to z=+0.04.
      - Corner stakes:  4 wooden cylinders at the bbox corners, 30 cm
                        tall, with a bright orange marker cap on top for
                        visibility from any camera angle.
      - String outline:  4 thin yellow cylinders connecting adjacent
                         stakes at ~26 cm, showing where the walls will
                         eventually rise.
      - Dirt pile:  one small cone-shaped mound outside the +X edge of
                    the footprint, representing spoil from initial
                    excavation.
    """
    print(f"\n{'-'*68}\nBuilding{building_id}  Stage 0 (Ground Breaking)\n{'-'*68}")

    # Load source purely to measure the footprint, then wipe the scene
    # and build everything from primitives.  Bounds are plain floats,
    # so they survive the read_factory_settings() wipe.
    _tmp = import_source(src_glb)
    bounds = compute_bounds(_tmp)
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
    print(f"  Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  Z[{z_min:+.3f}, {z_max:+.3f}]")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    created: list[bpy.types.Object] = []

    dirt_mat  = make_material("stage0_dirt",   (0.28, 0.19, 0.11), 0.95)
    wood_mat  = make_material("stage0_wood",   (0.42, 0.26, 0.13), 0.90)
    orange_mat = make_material("stage0_marker", (1.00, 0.35, 0.00), 0.60)
    string_mat = make_material("stage0_string", (0.95, 0.83, 0.20), 0.50)

    # ── Dirt plot (ground) ─────────────────────────────────────────────
    dirt_pad  = 0.30
    dirt_thick = 0.04
    dirt_sx = (x_max - x_min) + 2 * dirt_pad
    dirt_sy = (y_max - y_min) + 2 * dirt_pad
    dirt_cx = (x_min + x_max) / 2.0
    dirt_cy = (y_min + y_max) / 2.0
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(dirt_cx, dirt_cy, z_min + dirt_thick / 2.0),
    )
    dirt = bpy.context.active_object
    dirt.scale = (dirt_sx, dirt_sy, dirt_thick)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    dirt.name = "stage0_dirt_plot"
    dirt.data.materials.clear()
    dirt.data.materials.append(dirt_mat)
    created.append(dirt)

    # ── Corner survey stakes + orange marker caps ─────────────────────
    stake_height = 0.30
    stake_radius = 0.020
    stake_bottom = z_min + dirt_thick   # sit on top of the dirt
    stake_top    = stake_bottom + stake_height
    stake_mid    = (stake_bottom + stake_top) / 2.0

    corners = (
        (x_min, y_min),
        (x_max, y_min),
        (x_max, y_max),
        (x_min, y_max),
    )
    marker_h = 0.06
    for (cx, cy) in corners:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=stake_radius,
            depth=stake_height,
            location=(cx, cy, stake_mid),
        )
        stake = bpy.context.active_object
        stake.name = "stage0_stake"
        stake.data.materials.clear()
        stake.data.materials.append(wood_mat)
        created.append(stake)

        bpy.ops.mesh.primitive_cylinder_add(
            radius=stake_radius * 1.6,
            depth=marker_h,
            location=(cx, cy, stake_top + marker_h / 2.0 - 0.015),
        )
        cap = bpy.context.active_object
        cap.name = "stage0_stake_cap"
        cap.data.materials.clear()
        cap.data.materials.append(orange_mat)
        created.append(cap)

    # ── String outline connecting adjacent stakes ─────────────────────
    string_z      = stake_top - 0.04
    string_radius = 0.006
    edges = (
        ((x_min, y_min), (x_max, y_min)),
        ((x_max, y_min), (x_max, y_max)),
        ((x_max, y_max), (x_min, y_max)),
        ((x_min, y_max), (x_min, y_min)),
    )
    for (p1, p2) in edges:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        mid_x = (p1[0] + p2[0]) / 2.0
        mid_y = (p1[1] + p2[1]) / 2.0
        # A cylinder is oriented along +Z by default.  Rotating by
        # +90° around Y lays it flat along +X; rotating around Z by
        # `angle` then aims it at the target point in the XY plane.
        angle = math.atan2(dy, dx)
        bpy.ops.mesh.primitive_cylinder_add(
            radius=string_radius,
            depth=length,
            location=(mid_x, mid_y, string_z),
            rotation=(0.0, math.pi / 2.0, angle),
        )
        s = bpy.context.active_object
        s.name = "stage0_string"
        s.data.materials.clear()
        s.data.materials.append(string_mat)
        created.append(s)

    # ── Dirt pile outside the +X edge of the footprint ─────────────────
    # Small truncated cone; sized proportionally to the building so it
    # stays visually balanced across small and large buildings.
    site_span = max(x_max - x_min, y_max - y_min)
    pile_radius = min(0.55, 0.18 * site_span)
    pile_h      = 0.5 * pile_radius
    pile_cx = x_max + dirt_pad + pile_radius * 0.9
    pile_cy = y_min + (y_max - y_min) * 0.25
    bpy.ops.mesh.primitive_cone_add(
        vertices=20,
        radius1=pile_radius,
        radius2=pile_radius * 0.15,
        depth=pile_h,
        location=(pile_cx, pile_cy, z_min + pile_h / 2.0),
    )
    pile = bpy.context.active_object
    pile.name = "stage0_dirt_pile"
    pile.data.materials.clear()
    pile.data.materials.append(dirt_mat)
    created.append(pile)

    # ── Join all pieces + export ──────────────────────────────────────
    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    if len(created) > 1:
        bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = f"building{building_id}_stage0"

    print(f"  Pieces joined: {len(created)}   "
          f"final verts={len(result.data.vertices)}, "
          f"faces={len(result.data.polygons)}")

    apply_building_scale(result, building_id)

    filename = f"Building{building_id}Stage0.glb"
    for out_dir in (DESKTOP_OUT_DIR, VIEWER_OUT_DIR):
        out_path = os.path.join(out_dir, filename)
        export_glb(result, out_path)
        print(f"  -> {out_path}")


def build_stage(src_glb: str, building_id: int, stage_num: int) -> None:
    print(f"\n{'-'*68}\nBuilding{building_id}  Stage {stage_num}\n{'-'*68}")

    building = import_source(src_glb)
    building.name = f"building{building_id}_stage{stage_num}"

    bounds = compute_bounds(building)
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
    H = z_max - z_min

    floor_z = find_walkable_floor_z(building)
    cut_z = stage_cut_z(stage_num, z_min, z_max, floor_z)
    frac_of_H = (cut_z - z_min) / H if H > 0 else 0.0

    print(f"  Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  Z[{z_min:+.3f}, {z_max:+.3f}]  H={H:.3f}")
    print(f"  Walkable floor Z: {floor_z}")
    print(f"  Cut Z: {cut_z:+.3f} ({frac_of_H*100:.1f}% of H)")

    bisect_keep_below(building, Vector((0, 0, cut_z)), Vector((0, 0, 1)))
    print(f"  After primary cut: {len(building.data.vertices)} verts, "
          f"{len(building.data.polygons)} faces")

    n_recuts = STAGE_RECUT_COUNT[stage_num]
    if n_recuts > 0:
        # Seed per-building AND per-stage so different buildings look
        # different but the same building stays reproducible across
        # re-runs (important when the user is iterating on other params).
        rng = random.Random(RNG_SEED + building_id * 100 + stage_num)
        max_angle = math.radians(STAGE_RECUT_MAX_ANGLE_DEG[stage_num])
        max_dz = STAGE_RECUT_MAX_Z_OFFSET[stage_num] * H
        for _ in range(n_recuts):
            axis_theta = rng.uniform(0, 2 * math.pi)
            axis = Vector((math.cos(axis_theta), math.sin(axis_theta), 0.0))
            tilt = rng.uniform(-max_angle, max_angle)
            n = Vector((
                math.sin(tilt) * axis.y,
                -math.sin(tilt) * axis.x,
                math.cos(tilt),
            )).normalized()
            dz = rng.uniform(-max_dz, +max_dz)
            co = Vector((
                rng.uniform(x_min, x_max) * 0.3,
                rng.uniform(y_min, y_max) * 0.3,
                cut_z + dz,
            ))
            bisect_keep_below(building, co, n)
        print(f"  After {n_recuts} jagged re-cut(s): "
              f"{len(building.data.vertices)} verts, "
              f"{len(building.data.polygons)} faces")

    if stage_num >= 2:
        top_of_walls = cut_z + (STAGE_RECUT_MAX_Z_OFFSET[stage_num] * H)
        extras = add_scaffolding(bounds, z_min, top_of_walls, tag=f"b{building_id}s{stage_num}")
        print(f"  Added {len(extras)} scaffolding pieces")
        building = join_all_into(building, extras)

    apply_building_scale(building, building_id)

    filename = f"Building{building_id}Stage{stage_num}.glb"
    for out_dir in (DESKTOP_OUT_DIR, VIEWER_OUT_DIR):
        out_path = os.path.join(out_dir, filename)
        export_glb(building, out_path)
        print(f"  -> {out_path}")


def normalize_source(src_glb: str, building_id: int) -> None:
    """Re-export the source building through Blender with all root
    transforms baked into the mesh (scale=1, origin at 0,0,0), so the
    viewer's Complete GLB has an identity transform matching every
    stage output.  Previously this step was a plain `shutil.copy2`,
    which preserved the source's non-1 root scale (Building1.glb ships
    with scale=1.1794 on its mesh root).  Loading that in Blender
    alongside a stage GLB showed a scale mismatch on the N-panel and
    made the models feel "different sizes" even though they rendered
    at the same world extent in Three.js.
    """
    print(f"\n{'-'*68}\nBuilding{building_id}  Complete (normalizing source)\n{'-'*68}")
    building = import_source(src_glb)
    building.name = f"building{building_id}_complete"
    bounds = compute_bounds(building)
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
    print(f"  Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  Z[{z_min:+.3f}, {z_max:+.3f}]")

    apply_building_scale(building, building_id)
    sx, sy, sz = effective_scale(building_id)
    if (sx, sy, sz) != (1.0, 1.0, 1.0):
        b2 = compute_bounds(building)
        (x0, x1), (y0, y1), (z0, z1) = b2
        print(f"  Scaled (X={sx:.3f}, Y={sy:.3f}, Z={sz:.3f}): "
              f"X[{x0:+.3f}, {x1:+.3f}]  "
              f"Y[{y0:+.3f}, {y1:+.3f}]  Z[{z0:+.3f}, {z1:+.3f}]")

    filename = f"Building{building_id}.glb"
    viewer_out = os.path.join(VIEWER_SOURCE_DIR, filename)
    export_glb(building, viewer_out)
    print(f"  -> {viewer_out}")


def process_building(building_id: int) -> None:
    src_glb = os.path.join(SOURCE_DIR, f"Building{building_id}.glb")
    if not os.path.exists(src_glb):
        print(f"\n[SKIP] Building{building_id}.glb not found at {src_glb}")
        return

    print(f"\n{'='*72}\n=== BUILDING {building_id}\n{'='*72}")
    print(f"Source: {src_glb}")

    normalize_source(src_glb, building_id)
    build_stage_zero(src_glb, building_id)
    for stage in (1, 2, 3):
        build_stage(src_glb, building_id, stage)


def main():
    print(f"Source dir:     {SOURCE_DIR}")
    print(f"Desktop output: {DESKTOP_OUT_DIR}")
    print(f"Viewer output:  {VIEWER_OUT_DIR}")
    print(f"Buildings:      {list(BUILDING_IDS)}")

    for bid in BUILDING_IDS:
        process_building(bid)

    print(f"\n{'='*72}\nALL BUILDINGS COMPLETE\n{'='*72}")


if __name__ == "__main__":
    main()
