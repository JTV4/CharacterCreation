"""
generate_skirt_v1.py
====================
Generates a skirt mesh for Female V2 covering hip to mid-thigh.
Same technique as the robe: body-conforming top, oval flare at bottom,
smooth N-nearest weight blending.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_skirt_v1.py
"""

import os
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

SRC_GLB = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
OUT_DIR = os.path.abspath("viewer/public/equipment/Female/Skirts")
os.makedirs(OUT_DIR, exist_ok=True)

SKIRT_REGIONS = [
    "base_body_leg_upper",
    "base_body_leg_thigh",
]

HIP_Z       = 1.066
MID_THIGH_Z = 0.796

NUM_SEGS  = 64
NUM_RINGS = 40

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER     = 1.5

INFLATE   = 0.6
FLARE     = 3.0

FOLD_AMP  = 0.0

OVAL_X    = 1.25

MIN_RING_RATIO = 0.90

BUCKET = 1.0

# ── 1. Load BaseFemaleV2 ─────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

print(f"Loaded {len(region_meshes)} region meshes")

sample = region_meshes[SKIRT_REGIONS[0]]
mat_inv = sample.matrix_world.inverted()

def w2l_y(wz):
    return (mat_inv @ Vector((0, 0, wz))).y

TOP_Y = w2l_y(HIP_Z)
BOT_Y = w2l_y(MID_THIGH_Z)
HEIGHT = TOP_Y - BOT_Y
print(f"Skirt local Y range: {BOT_Y:.1f} → {TOP_Y:.1f} (height {HEIGHT:.1f} cm)")

# ── 2. Create a joined body reference for radius sampling + weight transfer ───
copies = []
for rname in SKIRT_REGIONS:
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
body_radius_2d = {}
body_radius_max = {}

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
thigh_max = max((v for k, v in body_radius_max.items() if k < BOT_Y + 5), default=12.0)
print(f"Body radii: hip_max={hip_max:.1f} cm, thigh_max={thigh_max:.1f} cm")

def get_circular_radius(y):
    t = max(0.0, min(1.0, (y - BOT_Y) / HEIGHT)) if HEIGHT > 0.01 else 0.5
    return thigh_max + (hip_max - thigh_max) * t

def get_body_contour_radius(y, sector):
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
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.duplicate(linked=False)
skirt = bpy.context.active_object
skirt.name = "skirt_v1"
skirt.data.name = "skirt_v1"

# ── 5. Replace geometry with procedural cone ──────────────────────────────────
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(skirt.data)

bmesh.ops.delete(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], context="VERTS")

verts_by_ring = []
for j in range(NUM_RINGS):
    t = j / (NUM_RINGS - 1)
    y = BOT_Y + t * HEIGHT

    flare_amount = FLARE * (1.0 - t) ** 1.5
    circ_r = get_circular_radius(y) + INFLATE + flare_amount

    conform = t ** 0.6

    raw_radii = []
    for i in range(NUM_SEGS):
        body_r = get_body_contour_radius(y, i)
        tight_r = body_r + INFLATE
        raw_radii.append(tight_r * conform + circ_r * (1.0 - conform))

    ring_max = max(raw_radii)
    ring_floor = ring_max * MIN_RING_RATIO
    raw_radii = [max(r, ring_floor) for r in raw_radii]

    radii = smooth_ring(raw_radii, passes=6)

    oval = 1.0 + (OVAL_X - 1.0) * (1.0 - t)

    ring = []
    for i in range(NUM_SEGS):
        angle = 2 * math.pi * i / NUM_SEGS
        r = radii[i]
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

# Cap bottom
bot_ring = verts_by_ring[0]
bot_center = bm.verts.new((0, BOT_Y, 0))
for i in range(NUM_SEGS):
    i_next = (i + 1) % NUM_SEGS
    bm.faces.new([bot_center, bot_ring[i_next], bot_ring[i]])

# Cap top
top_ring = verts_by_ring[-1]
top_center = bm.verts.new((0, TOP_Y, 0))
for i in range(NUM_SEGS):
    i_next = (i + 1) % NUM_SEGS
    bm.faces.new([top_center, top_ring[i], top_ring[i_next]])

bm.normal_update()

for f in bm.faces:
    f.smooth = True

bmesh.update_edit_mesh(skirt.data)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()

print(f"Procedural skirt: {len(skirt.data.vertices)} verts, {len(skirt.data.polygons)} faces")

# ── 6. Smooth weight transfer via N-nearest inverse-distance blending ─────────
for vg in skirt.vertex_groups:
    vg.remove(range(len(skirt.data.vertices)))

kd = KDTree(len(body_ref.data.vertices))
for i, v in enumerate(body_ref.data.vertices):
    kd.insert(v.co, i)
kd.balance()

transferred = 0
for rv_idx, rv in enumerate(skirt.data.vertices):
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

    wtotal = sum(blended.values())
    if wtotal > 0:
        for name, w in blended.items():
            nw = w / wtotal
            if nw > 0.0001:
                skirt.vertex_groups[name].add([rv_idx], nw, 'REPLACE')
                transferred += 1

print(f"Transferred {transferred} blended weight entries")

# ── 7. Clean up temporary body reference ──────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.delete(use_global=False)

# ── 8. Export ─────────────────────────────────────────────────────────────────
out_path = os.path.join(OUT_DIR, "skirt_v1.glb")

bpy.ops.object.select_all(action="DESELECT")
skirt.select_set(True)
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

print(f"\nSkirt exported: {out_path}")
print(f"  Vertices: {len(skirt.data.vertices)}")
print(f"  Faces:    {len(skirt.data.polygons)}")
