"""
generate_rock_path.py
=====================
A curved stepping-stone walk path — 10 flat walkable stones down the
middle plus 4 smaller edge rocks scattered off to the sides for
organic-cluster feel.  Same clean-handoff contract as every other
asset in the repo:

  - Single joined mesh (all 14 stones welded together), one draw
    call in-engine.
  - Origin at (0, 0, 0) = START of path at ground level; path
    extends +Y for PATH_LENGTH metres, bowing +X at the midpoint.
  - Root scale = (1, 1, 1) with all per-stone transforms baked into
    vertex data before export.
  - Single material slot `rock_stone` — SAME name as the existing
    Small/Medium/Large/Huge rocks, so texturing the rock family once
    covers the whole environment set.
  - Flat-shaded (chunky faceted look) — same weathered-stone
    aesthetic as the standalone rocks.

Design decisions
----------------
* **Stepping stones are FLAT, not spherical.**  Same generate-hull
  algorithm as generate_rocks.py, but half-extents in Z are ~1/3 of
  half-extents in XY (5–9 cm tall vs 20–28 cm radius).  This gives a
  disc-y "flat river-stone" silhouette that reads as walkable at
  first glance.
* **Path curve is a single sin(πt) arc.**  One gentle bow rather
  than an S-curve — reads as intentional garden design without
  looking too pretty.  Amplitude 0.5 m fits a 1 m-wide path corridor
  with headroom on both sides.
* **Stones use a per-stone RNG.**  Each stone gets a unique random
  seed derived from the master path RNG, so re-running the script
  produces the identical path every time, but each stone still looks
  uniquely shaped.
* **Slight Y-jitter breaks up the grid.**  Even spacing along the
  arc would look mechanical; ±6 cm Y-offset per stone makes the
  path feel hand-placed.
* **Side rocks are 40 % the volume of stepping stones.**  Small
  enough to read as "natural scatter around the path" rather than
  "second row of walkable stones".

Outputs:
  ~/Desktop/Models/Buildings/RockPath.glb
  viewer/public/buildings/RockPath.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_rock_path.py
"""

import math
import os
import random

import bpy
import bmesh
from mathutils import Vector


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

OUT_NAME   = "RockPath.glb"
PATH_SEED  = 42            # master seed — change to regenerate a whole new path


# ── Path curve ───────────────────────────────────────────────────────────

PATH_LENGTH     = 5.0      # total length along +Y (metres)
CURVE_AMPLITUDE = 0.5      # peak sideways bow along +X (metres)

def _path_point(t: float) -> tuple[float, float]:
    """t in [0, 1] → (x, y) on the path curve.
    Single arc: y goes linearly from 0 → PATH_LENGTH while x follows
    sin(πt) so the path starts and ends on the centreline, peaking
    at +CURVE_AMPLITUDE in +X at t=0.5."""
    y = t * PATH_LENGTH
    x = math.sin(t * math.pi) * CURVE_AMPLITUDE
    return (x, y)


# ── Stepping stones (main path) ──────────────────────────────────────────

NUM_STEPPING_STONES = 10
STEP_HALF_XY_MIN    = 0.20     # smallest walkable stone radius
STEP_HALF_XY_MAX    = 0.28     # largest walkable stone radius
STEP_HALF_Z_MIN     = 0.05     # thin flat stone
STEP_HALF_Z_MAX     = 0.09     # slightly thicker stone
STEP_Y_JITTER       = 0.06     # ± Y-offset per stone from ideal arc position
STEP_NUM_POINTS     = 20       # hull points per stone
STEP_JITTER         = 0.18     # radial hull perturbation

# ── Side rocks (decorative scatter) ──────────────────────────────────────

NUM_SIDE_ROCKS      = 4
SIDE_HALF_XY_MIN    = 0.10
SIDE_HALF_XY_MAX    = 0.15
SIDE_HALF_Z_MIN     = 0.05
SIDE_HALF_Z_MAX     = 0.08
SIDE_T_RANGE        = (0.10, 0.90)   # keep side rocks off the very ends
SIDE_OFFSET_MIN     = 0.55           # min distance from path centerline
SIDE_OFFSET_MAX     = 0.95           # max distance from path centerline
SIDE_NUM_POINTS     = 14
SIDE_JITTER         = 0.22           # chunkier per-stone since they're small


# ── Materials ─────────────────────────────────────────────────────────────
# SAME material name as the standalone rocks in generate_rocks.py — so
# whatever tileable stone material the artist wires into `rock_stone`
# gets applied consistently across every rock in the world.

MATERIAL_COLORS = {
    "rock_stone": (0.45, 0.42, 0.38),
}


def make_material(name: str) -> bpy.types.Material:
    """Fetch-or-create the material.  Using `bpy.data.materials.get`
    first ensures every stone shares the SAME material instance, so
    when we `object.join()` at the end the joined mesh ends up with
    exactly one material slot rather than 14."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        color = MATERIAL_COLORS.get(name, (0.5, 0.5, 0.5))
        principled.inputs["Base Color"].default_value = (*color, 1.0)
        if "Specular IOR Level" in principled.inputs:
            principled.inputs["Specular IOR Level"].default_value = 0.15
        elif "Specular" in principled.inputs:
            principled.inputs["Specular"].default_value = 0.15
        if "Roughness" in principled.inputs:
            principled.inputs["Roughness"].default_value = 0.85
    return mat


# ── Stone builder (adapted from generate_rocks.py) ───────────────────────

def _uniform_point_on_sphere(rng: random.Random) -> tuple[float, float, float]:
    z = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    r_xy = math.sqrt(max(0.0, 1.0 - z * z))
    return (r_xy * math.cos(phi), r_xy * math.sin(phi), z)


def build_stone(name: str,
                half: tuple[float, float, float],
                num_points: int,
                jitter: float,
                seed: int) -> bpy.types.Object:
    """Build one convex-hull stone, centred on origin at ground level.
    Same algorithm as generate_rocks.build_rock — see that file for
    the full commentary on the technique."""
    rng = random.Random(seed)
    hx, hy, hz = half

    pts = []
    for _ in range(num_points):
        ux, uy, uz = _uniform_point_on_sphere(rng)
        r = 1.0 + rng.uniform(-jitter, jitter)
        pts.append(Vector((ux * r * hx, uy * r * hy, uz * r * hz)))

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    obj  = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    bm.verts.ensure_lookup_table()

    result = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    unused_set = set()
    for key in ("geom_interior", "geom_unused"):
        for g in result.get(key, []):
            unused_set.add(g)
    if unused_set:
        bmesh.ops.delete(bm, geom=list(unused_set), context="VERTS")

    # Recentre: X/Y on 0, Z_min = 0 (stone sits on ground).
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    min_z = min(zs)
    for v in bm.verts:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= min_z

    for f in bm.faces:
        f.smooth = False
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj.data.materials.append(make_material("rock_stone"))
    return obj


# ── Path assembly ────────────────────────────────────────────────────────

def build_path(rng: random.Random) -> list:
    """Place every stone at its final world position and return the
    list of objects, ready to be joined."""
    stones = []

    # 10 stepping stones along the arc
    for i in range(NUM_STEPPING_STONES):
        t = i / (NUM_STEPPING_STONES - 1) if NUM_STEPPING_STONES > 1 else 0.5
        x, y = _path_point(t)
        y += rng.uniform(-STEP_Y_JITTER, STEP_Y_JITTER)

        hx = rng.uniform(STEP_HALF_XY_MIN, STEP_HALF_XY_MAX)
        hy = rng.uniform(STEP_HALF_XY_MIN, STEP_HALF_XY_MAX)
        hz = rng.uniform(STEP_HALF_Z_MIN,  STEP_HALF_Z_MAX)
        yaw = rng.uniform(0.0, 2.0 * math.pi)
        seed = rng.randint(1, 1_000_000)

        stone = build_stone(f"step_{i:02d}", (hx, hy, hz),
                            STEP_NUM_POINTS, STEP_JITTER, seed)
        stone.location = Vector((x, y, 0.0))
        stone.rotation_euler = (0.0, 0.0, yaw)
        stones.append(stone)

    # 4 smaller edge rocks scattered off to the sides.  The side
    # direction is randomised per rock so both sides of the path get
    # some scatter, and offset distance is randomised inside a
    # comfortable off-path band that clears the stepping stones.
    for i in range(NUM_SIDE_ROCKS):
        t = rng.uniform(*SIDE_T_RANGE)
        px, py = _path_point(t)
        side = rng.choice([-1.0, +1.0])
        offset = rng.uniform(SIDE_OFFSET_MIN, SIDE_OFFSET_MAX)
        x = px + side * offset
        y = py + rng.uniform(-0.15, 0.15)

        hx = rng.uniform(SIDE_HALF_XY_MIN, SIDE_HALF_XY_MAX)
        hy = rng.uniform(SIDE_HALF_XY_MIN, SIDE_HALF_XY_MAX)
        hz = rng.uniform(SIDE_HALF_Z_MIN,  SIDE_HALF_Z_MAX)
        yaw = rng.uniform(0.0, 2.0 * math.pi)
        seed = rng.randint(1, 1_000_000)

        stone = build_stone(f"side_{i:02d}", (hx, hy, hz),
                            SIDE_NUM_POINTS, SIDE_JITTER, seed)
        stone.location = Vector((x, y, 0.0))
        stone.rotation_euler = (0.0, 0.0, yaw)
        stones.append(stone)

    return stones


# ── Join + export ────────────────────────────────────────────────────────

def join_all(created: list, final_name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    if len(created) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = final_name
    return obj


def normalize_transform(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def export_glb(obj: bpy.types.Object, out_path: str) -> None:
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


def compute_bounds(obj: bpy.types.Object):
    mw = obj.matrix_world
    verts = [mw @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
    return ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs)))


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Source output: {os.path.join(SOURCE_DIR, OUT_NAME)}")
    print(f"Viewer output: {os.path.join(VIEWER_DIR, OUT_NAME)}")
    print(f"Path: {NUM_STEPPING_STONES} stepping stones + {NUM_SIDE_ROCKS} side rocks "
          f"along a {PATH_LENGTH:.1f} m arc (amplitude {CURVE_AMPLITUDE:.2f} m)")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    rng = random.Random(PATH_SEED)
    stones = build_path(rng)
    print(f"Built {len(stones)} stones")

    path = join_all(stones, final_name="rock_path")

    n_verts = len(path.data.vertices)
    n_faces = len(path.data.polygons)
    n_tris  = sum(len(p.vertices) - 2 for p in path.data.polygons)
    n_slots = len(path.data.materials)
    slot_names = ", ".join(m.name if m else "<none>" for m in path.data.materials)

    (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(path)
    print(f"Final mesh: verts={n_verts}, faces={n_faces}, tris={n_tris}")
    print(f"Material slots ({n_slots}): {slot_names}")
    print(f"Bounds: X[{x_min:+.2f}, {x_max:+.2f}]  "
          f"Y[{y_min:+.2f}, {y_max:+.2f}]  "
          f"Z[{z_min:+.2f}, {z_max:+.2f}]  "
          f"(footprint {x_max - x_min:.2f} × {y_max - y_min:.2f} m)")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, OUT_NAME)
        export_glb(path, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0 if os.path.exists(out_path) else 0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    print("\nDONE — rock walk path exported.")


if __name__ == "__main__":
    main()
