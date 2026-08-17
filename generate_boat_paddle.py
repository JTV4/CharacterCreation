"""
generate_boat_paddle.py
=======================
A single-blade wooden canoe paddle — companion asset to the wooden
rowboat.  Same clean-handoff contract as every other asset in the repo:

  - Origin at world (0, 0, 0) — blade TIP, X-centered, on the ground.
  - Root scale = (1, 1, 1) with transforms baked into vertex data.
  - Single joined mesh, one draw call in-engine.
  - Three named material slots (blade / shaft / grip) so texture
    assignment later is per-part-type — the varnished shaft, the flat
    dyed blade, and the worn palm-grip typically want different maps.

Coordinate convention
---------------------
  +X = blade wide direction / T-grip long direction
  +Y = paddle length, blade TIP at y=0 up to GRIP top at y=1.40
  +Z = up (the paddle lies FLAT on the ground)
  Origin at the blade tip, centred on X, centred on Z (so the
  centerline of the paddle sits at z=0, with the thickest part — the
  T-grip — extending ±0.02 above/below).  Anything holding the paddle
  can position it by offsetting from the tip; anything laying it down
  can offset up by GRIP_ZSIZE/2 so nothing dips below ground.

Parts (poly counts approximate, before join)
--------------------------------------------
  BLADE  — extruded 8-vert leaf outline    (16 verts, 32 tris)
  SHAFT  — 8-sided cylinder along +Y        (18 verts, 28 tris)
  GRIP   — single box, T-shape at the top   ( 8 verts, 12 tris)
  Total joined mesh: ~42 verts, ~72 tris.

Outputs:
  ~/Desktop/Models/Buildings/BoatPaddle.glb
  viewer/public/buildings/BoatPaddle.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_boat_paddle.py
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

OUT_NAME = "BoatPaddle.glb"


# ── Geometry constants ───────────────────────────────────────────────────
# All measurements in metres; overall paddle is 1.40 m long, which is
# a typical adult solo-canoe paddle length.

# Blade outline (X, Y) walked CCW when viewed from +Z so the top face
# comes out with the +Z normal.  Beavertail-ish leaf shape: narrow at
# the tip, widest at the mid-lower band, tapering to a rounded throat.
BLADE_OUTLINE: list[tuple[float, float]] = [
    (+0.000, 0.000),   # tip
    (+0.070, 0.050),   # lower right (blade starts widening)
    (+0.090, 0.200),   # mid right (widest section)
    (+0.090, 0.380),   # upper right (still wide)
    (+0.000, 0.500),   # throat (where blade meets shaft)
    (-0.090, 0.380),
    (-0.090, 0.200),
    (-0.070, 0.050),
]
BLADE_THICKNESS = 0.012                        # 12 mm — typical carved-blade
BLADE_Z_CENTER  = 0.0                          # centreline at z=0

# Shaft (cylinder along +Y from throat to grip bottom, slight overlap
# with both so the join reads seamless without any modifier work).
SHAFT_Y_BOTTOM = 0.480                         # 2 cm overlap into blade throat
SHAFT_Y_TOP    = 1.360                         # 1 cm overlap into grip
SHAFT_RADIUS   = 0.016                         # 32 mm diameter
SHAFT_SIDES    = 8                             # low-poly cylinder — silhouette
                                                # reads as round at hand distance

# Grip (T-shape) at the top of the shaft.
GRIP_Y_BOTTOM = 1.350
GRIP_Y_TOP    = 1.400
GRIP_XSIZE    = 0.120                          # 12 cm wide (X — matches how a
                                                # hand grips the top of a canoe paddle)
GRIP_YSIZE    = GRIP_Y_TOP - GRIP_Y_BOTTOM     # 0.05 m
GRIP_ZSIZE    = 0.040                          # 40 mm thick — chunky enough
                                                # to look grip-able


# ── Materials ─────────────────────────────────────────────────────────────
# Same palette family as the wooden boat so the two read as "matched
# set" side-by-side in the viewer.

MATERIAL_COLORS = {
    "paddle_blade": (0.60, 0.48, 0.35),  # flat leaf — mid warm brown
    "paddle_shaft": (0.65, 0.52, 0.38),  # varnished, slightly lighter
    "paddle_grip":  (0.55, 0.44, 0.32),  # worn palm-grip, slightly darker
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


# ── Blade (extruded 2D outline via bmesh) ────────────────────────────────

def build_blade(created: list) -> bpy.types.Object:
    """Build the blade as a manually-woven mesh (top face + bottom face
    + side quads).  bmesh.ops.extrude_face_region would work too, but
    manual winding lets us guarantee correct outward-facing normals
    without a post-flip pass — important because untextured game assets
    that render backfaces look distractingly matte/dark on the wrong
    side.

    Winding cheatsheet (assuming BLADE_OUTLINE is CCW when viewed from
    +Z):
      - Top face:    top_verts in outline order        → normal +Z ✓
      - Bottom face: bot_verts REVERSED               → normal −Z ✓
      - Side quads:  [bot[i], bot[j], top[j], top[i]] → normal outward ✓
    """
    mesh = bpy.data.meshes.new("paddle_blade_mesh")
    obj  = bpy.data.objects.new("paddle_blade", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    z_bot = BLADE_Z_CENTER - BLADE_THICKNESS / 2.0
    z_top = BLADE_Z_CENTER + BLADE_THICKNESS / 2.0

    bot_verts = [bm.verts.new(Vector((x, y, z_bot))) for (x, y) in BLADE_OUTLINE]
    top_verts = [bm.verts.new(Vector((x, y, z_top))) for (x, y) in BLADE_OUTLINE]

    bm.faces.new(top_verts)                      # top face — normal +Z
    bm.faces.new(list(reversed(bot_verts)))      # bottom face — normal −Z

    n = len(BLADE_OUTLINE)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([bot_verts[i], bot_verts[j], top_verts[j], top_verts[i]])

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj.data.materials.append(make_material("paddle_blade"))
    created.append(obj)
    return obj


# ── Shaft (cylinder primitive rotated to +Y) ─────────────────────────────

def build_shaft(created: list) -> bpy.types.Object:
    """Round cylindrical shaft.  Blender's cylinder primitive defaults
    to +Z axis, so we rotate +π/2 around X to align it with +Y.  A
    rotation of −π/2 would work too — cylinders are symmetric — but +π/2
    is the conventional "lay down" rotation."""
    length   = SHAFT_Y_TOP - SHAFT_Y_BOTTOM
    center_y = (SHAFT_Y_TOP + SHAFT_Y_BOTTOM) / 2.0

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=SHAFT_SIDES,
        radius=SHAFT_RADIUS,
        depth=length,
        location=(0.0, center_y, 0.0),
        rotation=(math.pi / 2.0, 0.0, 0.0),
    )
    obj = bpy.context.active_object
    obj.name = "paddle_shaft"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    obj.data.materials.clear()
    obj.data.materials.append(make_material("paddle_shaft"))
    created.append(obj)
    return obj


# ── T-grip (box primitive) ───────────────────────────────────────────────

def build_grip(created: list) -> bpy.types.Object:
    """T-shape at the top of the paddle.  Wide in X (matches how a hand
    grips the top of a canoe paddle — knuckles across, palm covering the
    top), thin in Y and Z.  A single box does the job at this scale;
    fancy palm-grip contouring is left as a future texture/normal-map
    concern."""
    center_y = (GRIP_Y_TOP + GRIP_Y_BOTTOM) / 2.0
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(0.0, center_y, 0.0),
    )
    obj = bpy.context.active_object
    obj.name = "paddle_grip"
    obj.scale = (GRIP_XSIZE, GRIP_YSIZE, GRIP_ZSIZE)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(make_material("paddle_grip"))
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

    bpy.ops.wm.read_factory_settings(use_empty=True)

    created: list = []
    build_blade(created)
    build_shaft(created)
    build_grip(created)

    print(f"Pieces built: {len(created)}")
    paddle = join_all(created, final_name="boat_paddle")

    n_verts = len(paddle.data.vertices)
    n_faces = len(paddle.data.polygons)
    n_tris  = sum(len(p.vertices) - 2 for p in paddle.data.polygons)
    n_slots = len(paddle.data.materials)
    slot_names = ", ".join(m.name if m else "<none>" for m in paddle.data.materials)

    (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(paddle)
    print(f"Final mesh: verts={n_verts}, faces={n_faces}, tris={n_tris}")
    print(f"Material slots ({n_slots}): {slot_names}")
    print(f"Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  "
          f"Z[{z_min:+.3f}, {z_max:+.3f}]")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, OUT_NAME)
        export_glb(paddle, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0 if os.path.exists(out_path) else 0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    print("\nDONE — boat paddle exported.")


if __name__ == "__main__":
    main()
