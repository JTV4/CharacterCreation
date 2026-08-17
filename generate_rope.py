"""
generate_rope.py
================
A flat-coiled hemp rope — the "nautical flake" you leave sitting on a
dock plank next to the boat and paddle.  Same clean-handoff contract
as every other asset in the repo:

  - Origin at world (0, 0, 0) — CENTRE of the coil hole, at ground level.
  - Root scale = (1, 1, 1) with transforms baked into vertex data.
  - Single joined mesh, one draw call in-engine.
  - Single material slot `rope_hemp` — the artist can swap this for a
    braided-fibre tileable when they get to texturing.
  - Smooth shading on the tube sides, flat shading on the two end
    caps, so silhouette reads round but caps still look cleanly cut.

Coordinate convention
---------------------
  +X, +Y = ground plane (coil lies flat)
  +Z     = up
  Origin at (0, 0, 0), coil centred, rope BOTTOM at z=0 (so it sits ON
  the ground rather than embedded in it).

Geometry approach
-----------------
Build a tube by sweeping a small hex cross-section along a
parametric Archimedean spiral:

    r(θ) = R_INNER + (2·ROPE_RADIUS / 2π) · θ

The radial growth per turn equals the rope diameter, so adjacent
coils sit tangent to each other (a tight, believable flake).  At each
sample point we compute the tangent to the curve, then place a hex
ring in the plane perpendicular to that tangent, using the fixed +Z
world-up as the ring's "normal" reference.  That gives a consistent
local frame all the way around the spiral with no accumulated twist
artifacts — the equivalent of a "Follow Path" bevel with a fixed up
axis.

Outputs:
  ~/Desktop/Models/Buildings/Rope.glb
  viewer/public/buildings/Rope.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_rope.py
"""

import math
import os

import bpy
import bmesh
from mathutils import Vector


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

OUT_NAME = "Rope.glb"


# ── Geometry constants ───────────────────────────────────────────────────
# All measurements in metres.

# Rope tube (the little hex cross-section swept along the spiral)
ROPE_RADIUS      = 0.015           # 15 mm → 30 mm diameter hemp mooring rope
ROPE_RING_SIDES  = 6               # hex — reads as round with smooth shading

# Flat spiral coil parameters
COIL_TURNS       = 6
R_INNER          = 0.060           # inner-hole radius (the "eye" of the flake)
                                    # tight enough that a hand could pick up
                                    # the coil by the hole
SAMPLES_PER_TURN = 12              # spiral resolution — 30° per sample
COIL_Z_BOTTOM    = 0.0             # rope bottom sits on ground
COIL_Z_CENTER    = COIL_Z_BOTTOM + ROPE_RADIUS

# Derived: outer coil radius grows by rope diameter per turn so
# adjacent coils are tangent (touching, not overlapping).
_DR_PER_RAD      = (2.0 * ROPE_RADIUS) / (2.0 * math.pi)  # = ROPE_RADIUS / π
R_OUTER          = R_INNER + COIL_TURNS * (2.0 * ROPE_RADIUS)


# ── Materials ─────────────────────────────────────────────────────────────
# Single slot — rope is a uniform material at game scale.  Warm hemp
# tan by default; the artist can swap in a tileable braid texture later.

MATERIAL_COLORS = {
    "rope_hemp": (0.72, 0.58, 0.38),
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
    return mat


# ── Spiral parametrisation ───────────────────────────────────────────────

def _spiral_frame(theta: float):
    """Return (position, tangent, up, binormal) at parameter theta.

    We use a FIXED world-up (+Z) as the ring's up reference rather than
    a parallel-transport frame.  For a flat spiral in the XY plane
    this is the natural choice — the ring's local +Y axis stays pointed
    at +Z world all the way around, so there's no accumulated twist,
    and adjacent rings align cleanly for smooth-shaded side quads.
    """
    r  = R_INNER + _DR_PER_RAD * theta
    cs = math.cos(theta)
    sn = math.sin(theta)

    pos = Vector((r * cs, r * sn, COIL_Z_CENTER))

    # dP/dθ = (r'·cos − r·sin, r'·sin + r·cos, 0)
    tx = _DR_PER_RAD * cs - r * sn
    ty = _DR_PER_RAD * sn + r * cs
    tangent = Vector((tx, ty, 0.0)).normalized()

    up = Vector((0.0, 0.0, 1.0))
    # binormal = tangent × up → radial-outward direction in XY plane
    binormal = tangent.cross(up).normalized()

    return pos, tangent, up, binormal


# ── Rope tube (bmesh) ────────────────────────────────────────────────────

def build_rope(created: list) -> bpy.types.Object:
    """Sweep a hex ring along the flat spiral to make the rope tube."""
    mesh = bpy.data.meshes.new("rope_mesh")
    obj  = bpy.data.objects.new("rope", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    total_samples = COIL_TURNS * SAMPLES_PER_TURN + 1
    theta_max     = COIL_TURNS * 2.0 * math.pi
    d_theta       = theta_max / (total_samples - 1)

    # Build every ring first, storing verts per ring
    rings: list[list] = []
    for i in range(total_samples):
        theta = i * d_theta
        pos, _tangent, up, binormal = _spiral_frame(theta)

        ring = []
        for k in range(ROPE_RING_SIDES):
            phi = 2.0 * math.pi * k / ROPE_RING_SIDES
            offset = (math.cos(phi) * binormal + math.sin(phi) * up) * ROPE_RADIUS
            ring.append(bm.verts.new(pos + offset))
        rings.append(ring)

    # Side quads between consecutive rings (smooth-shaded)
    for i in range(total_samples - 1):
        r0 = rings[i]
        r1 = rings[i + 1]
        for k in range(ROPE_RING_SIDES):
            kn = (k + 1) % ROPE_RING_SIDES
            f = bm.faces.new([r0[k], r0[kn], r1[kn], r1[k]])
            f.smooth = True

    # End caps.  The inner-end ring (θ=0) has its cap pointing in the
    # −tangent direction, so we must REVERSE the ring order to flip
    # the polygon's normal outward.  The outer-end ring (θ=θ_max) has
    # its cap pointing in the +tangent direction, matching the ring's
    # native winding — no reversal needed.  Caps stay flat-shaded so
    # they read as cleanly cut rope ends rather than fading into the
    # tube.
    cap_start = bm.faces.new(list(reversed(rings[0])))
    cap_start.smooth = False
    cap_end = bm.faces.new(rings[-1])
    cap_end.smooth = False

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj.data.materials.append(make_material("rope_hemp"))
    created.append(obj)
    return obj


# ── Join + export (same contract as every other generator) ───────────────

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
    print(f"Coil: {COIL_TURNS} turns, r ∈ [{R_INNER:.3f}, {R_OUTER:.3f}] m")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    created: list = []
    build_rope(created)

    print(f"Pieces built: {len(created)}")
    rope = join_all(created, final_name="rope_coil")

    n_verts = len(rope.data.vertices)
    n_faces = len(rope.data.polygons)
    n_tris  = sum(len(p.vertices) - 2 for p in rope.data.polygons)
    n_slots = len(rope.data.materials)
    slot_names = ", ".join(m.name if m else "<none>" for m in rope.data.materials)
    n_smooth = sum(1 for p in rope.data.polygons if p.use_smooth)

    (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(rope)
    print(f"Final mesh: verts={n_verts}, faces={n_faces}, tris={n_tris}")
    print(f"Material slots ({n_slots}): {slot_names}")
    print(f"Smooth-shaded faces: {n_smooth} / {n_faces} "
          f"(caps flat, tube smooth)")
    print(f"Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  "
          f"Z[{z_min:+.3f}, {z_max:+.3f}]")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, OUT_NAME)
        export_glb(rope, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0 if os.path.exists(out_path) else 0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    print("\nDONE — coiled rope exported.")


if __name__ == "__main__":
    main()
