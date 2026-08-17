"""
generate_robe_v1.py
===================
Generates a robe mesh for Female V2 covering hip to ankle.

Strategy: duplicate an existing body region (to inherit its exact armature
binding and transform), replace its geometry with a clean procedural cone,
then transfer bone weights from the body via KD-tree. This ensures the
GLTF export produces a skinned mesh identical in structure to the shell
pieces that already work in the viewer.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_robe_v1.py
"""

import os
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

SRC_GLB = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
OUT_DIR = os.path.abspath("viewer/public/equipment/Female/Robes")
os.makedirs(OUT_DIR, exist_ok=True)

ROBE_REGIONS = [
    "base_body_leg_upper",
    "base_body_leg_thigh",
    "base_body_leg_knee",
    "base_body_leg_shin",
    "base_body_leg_ankle",
]

HIP_Z   = 1.066
ANKLE_Z = 0.100

NUM_SEGS  = 64
NUM_RINGS = 100

WEIGHT_NEIGHBORS = 12  # blend weights from N nearest body vertices
WEIGHT_POWER     = 1.5 # inverse-distance power (lower = wider, smoother blend)

INFLATE   = 0.6   # cm clearance from body (same as leg shells)
FLARE     = 6.0   # cm additional radial expansion at ankle

FOLD_AMP  = 0.0   # no fold creases — smooth surface

OVAL_X    = 1.35  # X-axis stretch at bottom (wider between legs)

MIN_RING_RATIO = 0.90  # clamp radii to 90% of ring max (fills groin gap)

BUCKET = 1.0

# ── 1. Load BaseFemaleV2 ─────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

print(f"Loaded {len(region_meshes)} region meshes")

sample = region_meshes[ROBE_REGIONS[0]]
mat_inv = sample.matrix_world.inverted()

def w2l_y(wz):
    return (mat_inv @ Vector((0, 0, wz))).y

TOP_Y = w2l_y(HIP_Z)
BOT_Y = w2l_y(ANKLE_Z)
HEIGHT = TOP_Y - BOT_Y
print(f"Robe local Y range: {BOT_Y:.1f} → {TOP_Y:.1f} (height {HEIGHT:.1f} cm)")

# ── 2. Create a joined body reference for radius sampling + weight transfer ───
copies = []
for rname in ROBE_REGIONS:
    src = region_meshes.get(rname)
    if not src:
        continue
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    bpy.ops.object.duplicate(linked=False)
    copies.append(bpy.context.active_object)

bpy.ops.object.select_all(action="DESELECT")
for c in copies:
    c.select_set(True)
bpy.context.view_layer.objects.active = copies[0]
bpy.ops.object.join()
body_ref = bpy.context.active_object
body_ref.name = "body_ref_temp"

body_vgroups = [vg.name for vg in body_ref.vertex_groups]
print(f"Body reference: {len(body_ref.data.vertices)} verts, {len(body_vgroups)} vertex groups")

# ── 3. Compute body radius per (height, angle) for body-conforming top ────────
body_radius_2d = {}   # (y_bucket, angle_sector) -> max radius
body_radius_max = {}  # y_bucket -> max radius (for circular fallback)

for v in body_ref.data.vertices:
    by = round(v.co.y / BUCKET) * BUCKET
    r = math.sqrt(v.co.x ** 2 + v.co.z ** 2)
    angle = math.atan2(v.co.z, v.co.x)
    if angle < 0:
        angle += 2 * math.pi
    sector = int(angle / (2 * math.pi) * NUM_SEGS) % NUM_SEGS

    key = (by, sector)
    body_radius_2d[key] = max(body_radius_2d.get(key, 0), r)
    body_radius_max[by] = max(body_radius_max.get(by, 0), r)

hip_max = max((v for k, v in body_radius_max.items() if k > TOP_Y - 5), default=15.0)
ankle_max = max((v for k, v in body_radius_max.items() if k < BOT_Y + 5), default=10.0)
print(f"Body radii: hip_max={hip_max:.1f} cm, ankle_max={ankle_max:.1f} cm")

def get_circular_radius(y):
    """Smooth linear envelope for the circular flared portion."""
    t = max(0.0, min(1.0, (y - BOT_Y) / HEIGHT)) if HEIGHT > 0.01 else 0.5
    return ankle_max + (hip_max - ankle_max) * t

def get_body_contour_radius(y, sector):
    """Body surface radius at a specific height and angle, with fallback."""
    by = round(y / BUCKET) * BUCKET
    for dy in [0, BUCKET, -BUCKET, 2 * BUCKET, -2 * BUCKET]:
        key = (by + dy, sector)
        if key in body_radius_2d:
            return body_radius_2d[key]
    for dy in [0, BUCKET, -BUCKET]:
        for ds in [1, -1, 2, -2]:
            key = (by + dy, (sector + ds) % NUM_SEGS)
            if key in body_radius_2d:
                return body_radius_2d[key]
    return get_circular_radius(y)

def smooth_ring(radii, passes=3):
    """Moving-average smooth a ring of radius values to remove noise."""
    r = list(radii)
    n = len(r)
    for _ in range(passes):
        smoothed = []
        for i in range(n):
            avg = (r[(i - 1) % n] + r[i] + r[(i + 1) % n]) / 3.0
            smoothed.append(avg)
        r = smoothed
    return r

# ── 4. Duplicate body_ref to inherit the correct armature binding ─────────────
# This is critical: the duplicated object has the exact same matrix_local,
# parent, armature modifier, and vertex group setup as the original body
# regions. The GLTF export will produce a properly skinned mesh.
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.duplicate(linked=False)
robe = bpy.context.active_object
robe.name = "robe_v1"
robe.data.name = "robe_v1"

# ── 5. Replace geometry with procedural cone ──────────────────────────────────
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(robe.data)

# Delete all existing geometry
bmesh.ops.delete(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], context="VERTS")

# Build the cone: body-conforming at top, oval+flare at bottom
verts_by_ring = []
for j in range(NUM_RINGS):
    t = j / (NUM_RINGS - 1)  # 0 = bottom, 1 = top
    y = BOT_Y + t * HEIGHT

    flare_amount = FLARE * (1.0 - t) ** 1.5
    circ_r = get_circular_radius(y) + INFLATE + flare_amount

    conform = t ** 0.6

    raw_radii = []
    for i in range(NUM_SEGS):
        body_r = get_body_contour_radius(y, i)
        tight_r = body_r + INFLATE
        raw_radii.append(tight_r * conform + circ_r * (1.0 - conform))

    # Fade the "skirt-shaping" effects (uniformity clamp, ring smoothing)
    # OUT as we approach the top of the robe.  At the waist (t == 1) the
    # robe must conform exactly to body + INFLATE per sector so it lines up
    # with `shell_v1_leg_upper` at the same Y.  Lower down (t → 0) the
    # full clamp and smoothing kick in to give a clean flared skirt shape.
    shape_strength = 1.0 - t

    ring_max = max(raw_radii)
    ring_floor = ring_max * MIN_RING_RATIO * shape_strength
    raw_radii = [max(r, ring_floor) for r in raw_radii]

    smoothed = smooth_ring(raw_radii, passes=6)
    radii = [smoothed[i] * shape_strength + raw_radii[i] * (1.0 - shape_strength)
             for i in range(NUM_SEGS)]

    # Oval stretch factor: 1.0 at top, OVAL_X at bottom (X-axis = side-to-side)
    oval = 1.0 + (OVAL_X - 1.0) * (1.0 - t)

    ring = []
    for i in range(NUM_SEGS):
        angle = 2 * math.pi * i / NUM_SEGS
        r = radii[i] + FOLD_AMP * math.sin(10 * angle)
        x = r * math.cos(angle) * oval
        z = r * math.sin(angle)
        v = bm.verts.new((x, y, z))
        ring.append(v)
    verts_by_ring.append(ring)

for j in range(NUM_RINGS - 1):
    for i in range(NUM_SEGS):
        i_next = (i + 1) % NUM_SEGS
        bm.faces.new([
            verts_by_ring[j][i],
            verts_by_ring[j][i_next],
            verts_by_ring[j + 1][i_next],
            verts_by_ring[j + 1][i],
        ])

# NOTE: Both ring ends are intentionally LEFT OPEN (no triangle-fan caps).
# The robe behaves like the leg shells / leggings - a hollow tube the
# character's hips and legs pass through.  The viewer renders the wall as
# DoubleSide so the inside surface is visible when looking up into the robe.

bm.normal_update()

for f in bm.faces:
    f.smooth = True

bmesh.update_edit_mesh(robe.data)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()

print(f"Procedural robe: {len(robe.data.vertices)} verts, {len(robe.data.polygons)} faces")

# ── 6. Smooth weight transfer via N-nearest inverse-distance blending ─────────
for vg in robe.vertex_groups:
    vg.remove(range(len(robe.data.vertices)))

kd = KDTree(len(body_ref.data.vertices))
for i, v in enumerate(body_ref.data.vertices):
    kd.insert(v.co, i)
kd.balance()

vg_names = [vg.name for vg in body_ref.vertex_groups]
vg_lookup = {name: idx for idx, name in enumerate(vg_names)}

transferred = 0
for rv_idx, rv in enumerate(robe.data.vertices):
    neighbors = kd.find_n(rv.co, WEIGHT_NEIGHBORS)

    inv_weights = []
    for co, idx, dist in neighbors:
        w = 1.0 / (dist ** WEIGHT_POWER + 1e-8)
        inv_weights.append((idx, w))

    total_inv = sum(w for _, w in inv_weights)

    blended = {}
    for body_idx, inv_w in inv_weights:
        factor = inv_w / total_inv
        for vg in body_ref.vertex_groups:
            try:
                bw = vg.weight(body_idx)
            except RuntimeError:
                continue
            if bw > 0.0001:
                blended[vg.name] = blended.get(vg.name, 0.0) + bw * factor

    # Normalize so total weight sums to 1.0
    wtotal = sum(blended.values())
    if wtotal > 0:
        for name, w in blended.items():
            nw = w / wtotal
            if nw > 0.0001:
                robe.vertex_groups[name].add([rv_idx], nw, 'REPLACE')
                transferred += 1

print(f"Transferred {transferred} blended weight entries")

# ── 7. Clean up temporary body reference ──────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.delete(use_global=False)

# ── 8. Export ─────────────────────────────────────────────────────────────────
out_path = os.path.join(OUT_DIR, "robe_v1.glb")

bpy.ops.object.select_all(action="DESELECT")
robe.select_set(True)
if armature:
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

bpy.ops.export_scene.gltf(
    filepath=out_path,
    export_format="GLB",
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_skins=True,
    export_all_influences=True,
    export_def_bones=True,
    export_animations=False,
    export_materials="EXPORT",
)

print(f"\nRobe exported: {out_path}")
print(f"  Vertices: {len(robe.data.vertices)}")
print(f"  Faces:    {len(robe.data.polygons)}")
