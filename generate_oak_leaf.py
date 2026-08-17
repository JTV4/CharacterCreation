"""
generate_oak_leaf.py
====================
A large oak leaf, English/white-oak silhouette — 5 rounded lobes per
side, deep sinuses between them, a short petiole at the base.  Same
clean-handoff contract as every other asset in the repo:

  - Origin at world (0, 0, 0) = PETIOLE BASE at ground level; the leaf
    extends up +Y from there.  A game engine can drop the leaf onto
    the ground with a single translation, or attach it to a twig by
    parenting the twig's tip transform to this origin.
  - Root scale = (1, 1, 1) with transforms baked into vertex data.
  - Single joined mesh, one draw call in-engine.
  - TWO named material slots — `leaf_top` for the sun-facing face,
    `leaf_underside` for the shaded face + the paper-thin side strip.
    Real leaves have very different colour and gloss between top and
    bottom, and a scattered leaf viewed from above vs below should
    read differently at a glance.

Coordinate convention
---------------------
  +X = leaf width
  +Y = leaf length, petiole base at y=0 → blade tip near y=+0.32
  +Z = up
  Leaf lies FLAT: bottom face at z=0, top face at z=+LEAF_THICKNESS.

Silhouette
----------
Right side of the blade is defined once as a walk from base to tip
through 17 points (rising shoulders, lobe peaks, sinus lows), then
mirrored across x=0 to build the left side.  The tip is a single
midline vertex.  The petiole caps the base with two axial verts on
each side.

Outline point count grows the lobes a bit rounder than a naive
"peak-sinus-peak-sinus" walk would — the extra shoulder points on
either side of each peak keep the lobes reading as ROUNDED rather
than triangular, which is the visual signature of oak vs a jagged
maple or a smooth cherry leaf.

Outputs:
  ~/Desktop/Models/Buildings/OakLeaf.glb
  viewer/public/buildings/OakLeaf.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_oak_leaf.py
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

OUT_NAME = "OakLeaf.glb"


# ── Geometry constants ───────────────────────────────────────────────────

PETIOLE_LENGTH     = 0.030   # 3 cm stem
PETIOLE_HALF_WIDTH = 0.005   # 10 mm total stem width
LEAF_THICKNESS     = 0.002   # 2 mm — thick enough to read in silhouette,
                              # thin enough to still look like a leaf edge-on

# Right-side blade outline (X, Y).  Y=0 at BLADE BASE (not petiole
# base); the outline is shifted up by PETIOLE_LENGTH at build time so
# the whole leaf sits in y ≥ 0.  X values are all positive; the left
# side of the leaf is built by mirroring these across x=0.
#
# Reading top-to-bottom: base flare → 5 lobes with shoulders on each
# side of the peak → tip approach → (midline tip vertex added
# separately).  Each lobe follows a "sinus low → rising shoulder →
# peak → descending shoulder → sinus low" cadence so the lobes read
# as rounded rather than triangular.
BLADE_RIGHT_SIDE: list[tuple[float, float]] = [
    (0.020, 0.020),   # blade base right (slight flare from petiole)
    (0.035, 0.045),   # rising toward lobe 1
    (0.045, 0.060),   # lobe 1 peak (bottom lobe)
    (0.030, 0.085),   # sinus 1 (deep notch)
    (0.050, 0.100),   # rising shoulder toward lobe 2
    (0.065, 0.115),   # lobe 2 peak
    (0.050, 0.130),   # descending shoulder
    (0.045, 0.145),   # sinus 2
    (0.065, 0.160),   # rising shoulder toward lobe 3
    (0.075, 0.175),   # lobe 3 peak (WIDEST — mid-blade)
    (0.065, 0.190),   # descending shoulder
    (0.055, 0.205),   # sinus 3
    (0.058, 0.220),   # rising toward lobe 4
    (0.055, 0.235),   # lobe 4 peak
    (0.040, 0.250),   # sinus 4
    (0.030, 0.265),   # rising toward lobe 5 (tip-flanking)
    (0.020, 0.280),   # descending toward the tip
]
BLADE_TIP_Y = 0.290              # midline tip Y (from blade base)


# ── Materials ────────────────────────────────────────────────────────────
# Distinct top vs underside — the artist will typically paint these as
# two different tileable colour+normal maps rather than a single
# double-sided texture, because oak's underside is noticeably paler
# and shows the vein pattern more prominently.

MATERIAL_COLORS = {
    "leaf_top":       (0.14, 0.30, 0.08),   # deep summer green
    "leaf_underside": (0.45, 0.55, 0.22),   # paler yellow-green
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
        # Leaves are matte — kill the default 0.5 specular so unlit
        # previews don't get a mirror-shine spot on every facet.
        if "Specular IOR Level" in principled.inputs:
            principled.inputs["Specular IOR Level"].default_value = 0.20
        elif "Specular" in principled.inputs:
            principled.inputs["Specular"].default_value = 0.20
        if "Roughness" in principled.inputs:
            principled.inputs["Roughness"].default_value = 0.75
    return mat


# ── Outline construction ─────────────────────────────────────────────────

def _build_outline() -> list[tuple[float, float]]:
    """Full closed outline as a list of (X, Y), walked CCW when viewed
    from +Z so the top-face normal comes out correctly.

    Order: bottom-right of petiole → up the right side of petiole →
    up the right side of the blade → tip → down the left side of the
    blade → down the left side of the petiole → close.
    """
    outline: list[tuple[float, float]] = []

    # Right side of petiole (base to junction with blade)
    outline.append((+PETIOLE_HALF_WIDTH, 0.0))
    outline.append((+PETIOLE_HALF_WIDTH, PETIOLE_LENGTH))

    # Right side of blade (shift Y by PETIOLE_LENGTH so blade base = petiole top)
    for (x, y) in BLADE_RIGHT_SIDE:
        outline.append((+x, PETIOLE_LENGTH + y))

    # Midline tip
    outline.append((0.0, PETIOLE_LENGTH + BLADE_TIP_Y))

    # Left side of blade — mirror in X, walk in REVERSE order so we
    # come DOWN the leaf from tip to base
    for (x, y) in reversed(BLADE_RIGHT_SIDE):
        outline.append((-x, PETIOLE_LENGTH + y))

    # Left side of petiole (junction back down to base)
    outline.append((-PETIOLE_HALF_WIDTH, PETIOLE_LENGTH))
    outline.append((-PETIOLE_HALF_WIDTH, 0.0))

    return outline


# ── Leaf builder (bmesh, per-face material assignment) ───────────────────

def build_leaf(created: list) -> bpy.types.Object:
    """Extruded outline with distinct materials on top vs underside.

    Winding cheatsheet (same as paddle blade — outline is CCW from +Z):
      - Top face:    top_verts in outline order        → normal +Z ✓
      - Bottom face: bot_verts REVERSED               → normal −Z ✓
      - Side quads:  [bot[i], bot[j], top[j], top[i]] → normal outward ✓
    Bottom face + all side quads get `leaf_underside` (material 0);
    only the top face gets `leaf_top` (material 1).
    """
    outline = _build_outline()
    n = len(outline)

    mesh = bpy.data.meshes.new("oak_leaf_mesh")
    obj  = bpy.data.objects.new("oak_leaf", mesh)
    bpy.context.collection.objects.link(obj)

    # Attach BOTH materials to the mesh BEFORE building faces so
    # bmesh face.material_index refers to the correct slot.  Slot 0 =
    # underside, slot 1 = top — this ordering is arbitrary but must
    # match the material_index assignments below.
    obj.data.materials.append(make_material("leaf_underside"))
    obj.data.materials.append(make_material("leaf_top"))
    MAT_UNDERSIDE = 0
    MAT_TOP       = 1

    bm = bmesh.new()

    z_bot = 0.0
    z_top = LEAF_THICKNESS

    bot_verts = [bm.verts.new(Vector((x, y, z_bot))) for (x, y) in outline]
    top_verts = [bm.verts.new(Vector((x, y, z_top))) for (x, y) in outline]

    f_top = bm.faces.new(top_verts)
    f_top.material_index = MAT_TOP

    f_bot = bm.faces.new(list(reversed(bot_verts)))
    f_bot.material_index = MAT_UNDERSIDE

    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new([bot_verts[i], bot_verts[j], top_verts[j], top_verts[i]])
        f.material_index = MAT_UNDERSIDE

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

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
    build_leaf(created)

    print(f"Pieces built: {len(created)}")
    leaf = join_all(created, final_name="oak_leaf")

    n_verts = len(leaf.data.vertices)
    n_faces = len(leaf.data.polygons)
    n_tris  = sum(len(p.vertices) - 2 for p in leaf.data.polygons)
    n_slots = len(leaf.data.materials)
    slot_names = ", ".join(m.name if m else "<none>" for m in leaf.data.materials)

    # Per-slot face breakdown
    per_slot = [0] * max(n_slots, 1)
    for p in leaf.data.polygons:
        per_slot[p.material_index] += 1

    (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(leaf)
    print(f"Final mesh: verts={n_verts}, faces={n_faces}, tris={n_tris}")
    print(f"Material slots ({n_slots}): {slot_names}")
    for i, m in enumerate(leaf.data.materials):
        mname = m.name if m else "<none>"
        print(f"    slot {i} '{mname}': {per_slot[i]} face(s)")
    print(f"Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  "
          f"Z[{z_min:+.3f}, {z_max:+.3f}]")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, OUT_NAME)
        export_glb(leaf, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0 if os.path.exists(out_path) else 0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    print("\nDONE — oak leaf exported.")


if __name__ == "__main__":
    main()
