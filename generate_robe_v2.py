"""
generate_robe_v2.py
===================
Generates the V2 robe skirt mesh for Female V2 using the SAME strategy as
`generate_equipment_shell_v1.py`: duplicate a body region and deform its
vertices into the robe silhouette.  Unlike the shell generator (which
inflates each vertex by ~8 mm along its normal), this script vertically
stretches the source region down to ankle height and projects each
vertex radially to a wide A-line cone.  The resulting GLB inherits
everything that lets the shells texture cleanly in Meshy:

    - body-anatomical UV unwrap (single coherent island), not a
      synthetic cylindrical strip
    - the body's existing skin material (Meshy retextures cleanly when
      the mesh already has an organic-looking material as a prior)
    - bone weights & vertex groups (no KD-tree transfer needed — the
      verts ARE body verts, just moved in space)
    - shell-tier vertex density instead of the 9.6 K mathematical cone
      that Meshy was reading as a glazed lampshade

Source region: `base_body_lower_torso` ONLY
-------------------------------------------
The first iteration of this approach used the four leg regions
(`leg_upper`, `leg_thigh`, `leg_knee`, `leg_shin`) — but those regions
split into two separate cylinders below the hip, so radial projection
produced two disjoint half-shells with ~74° gaps at the inner-thigh
angles (front + back).  `lower_torso` is the only body region that is
a SINGLE CLOSED TUBE end-to-end: top ring at z=1.24 (waist), bottom
ring at z=1.066 (hip), uniform cylindrical topology in between, no
forks, no separate components.  Stretching it vertically gives a robe
that is guaranteed seamless all the way around.

Geometry pipeline
-----------------
1. Duplicate `base_body_lower_torso`.
2. Sample its bottom edge ring (verts at  y = Y_ORIG_BOT = TOP_Y) to
   capture the body's actual oval-ish silhouette at the waist.
3. Vertical remap:  the bottom ring stays at TOP_Y (waist), the top
   ring stretches DOWN to BOT_Y (hem).  This inverts the region — its
   former top becomes the robe's hem — and stretches it ~4.5×
   vertically.  Triangles get tall, but topology stays closed.
4. Radial projection:  per-vertex,  preserve angle  θ  from centroid;
   replace radius with  waist_radii[θ] * t + hem_radii[θ] * (1 - t)
   where  t = (y_new - BOT_Y) / HEIGHT.  At the waist (t = 1) the
   silhouette hugs the body's hip oval;  at the hem (t = 0) it
   expands to  hem_radii[θ] = waist_radii[θ] + FLARE  — same oval
   shape as the waist (wider on the sides than front/back), just
   uniformly offset outward.  This avoids the perfect-circle hem
   that reads as a turned ceramic cone.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_robe_v2.py
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

# Geometry source.  Must be a single closed tube (no forks / no separate
# connected components) — otherwise radial projection produces gaps.
# `lower_torso` is the only such region in the leg vicinity.
ROBE_REGIONS = [
    "base_body_lower_torso",
]

# Weight rebind source.  After projection the robe spans waist → ankle,
# so its lower verts need leg-bone weights — but lower_torso only has
# spine/hip weights.  We KD-tree-transfer weights from these regions so
# each robe vert inherits weights from the nearest body vertex in 3-D
# space (right side of robe → right leg bones, hem-height verts → shin
# / foot bones, etc.).
WEIGHT_REF_REGIONS = [
    "base_body_lower_torso",
    "base_body_leg_upper",
    "base_body_leg_thigh",
    "base_body_leg_knee",
    "base_body_leg_shin",
    "base_body_leg_ankle",
]

WAIST_Z = 1.066   # top of base_body_leg_upper / shell_v1_leg_upper
HEM_Z   = 0.280   # top of leg_ankle

NUM_SEGS = 96     # angular sampling resolution for the waist silhouette
INFLATE  = 0.0    # cm — outward offset at the waist (0 = sit on body)
FLARE    = 20.0   # cm — additional radial expansion at the hem

WEIGHT_NEIGHBORS = 12   # K-nearest body verts per robe vert
WEIGHT_POWER     = 1.5  # inverse-distance exponent (higher = more local)

# Tolerance band for vertex deletion at the seams.  A tiny positive
# margin keeps the body region's natural boundary ring (verts that sit
# right at WAIST_Z / HEM_Z) so the seam stays continuous.
SEAM_KEEP = 0.5   # cm


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

print(f"Loaded {len(region_meshes)} region meshes")

sample = region_meshes[ROBE_REGIONS[0]]
mat_inv = sample.matrix_world.inverted()


def w2l_y(wz: float) -> float:
    """World-Z (height) → local Y in the duplicated body-region frame."""
    return (mat_inv @ Vector((0, 0, wz))).y


TOP_Y = w2l_y(WAIST_Z)
BOT_Y = w2l_y(HEM_Z)
HEIGHT = TOP_Y - BOT_Y
print(f"Robe local Y range: {BOT_Y:.1f} → {TOP_Y:.1f} (height {HEIGHT:.1f} cm)")


# ── 1a. Build weight_ref (lower_torso + ALL leg regions, original pose) ────
# This is the source we'll KD-tree query for bone weights AFTER projection.
# It stays at original body positions — never deformed — so robe verts
# can find their nearest leg-anatomy vertex in 3-D space and inherit that
# vertex's bone weights.
ref_copies = []
for rname in WEIGHT_REF_REGIONS:
    src = region_meshes.get(rname)
    if not src:
        print(f"  WARNING: {rname} not found in BaseFemaleV2")
        continue
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    bpy.ops.object.duplicate(linked=False)
    ref_copies.append(bpy.context.active_object)

bpy.ops.object.select_all(action="DESELECT")
for c in ref_copies:
    c.select_set(True)
bpy.context.view_layer.objects.active = ref_copies[0]
bpy.ops.object.join()
weight_ref = bpy.context.active_object
weight_ref.name = "weight_ref_temp"

print(f"Weight reference: {len(weight_ref.data.vertices)} verts, "
      f"{len(weight_ref.vertex_groups)} vertex groups")


# ── 1b. Duplicate the geometry source (lower_torso) ────────────────────────
copies = []
for rname in ROBE_REGIONS:
    src = region_meshes.get(rname)
    if not src:
        print(f"  WARNING: {rname} not found in BaseFemaleV2")
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
robe = bpy.context.active_object
robe.name = "robe_v2"
robe.data.name = "robe_v2"

print(f"Joined body geometry: {len(robe.data.vertices)} verts, "
      f"{len(robe.data.polygons)} faces, "
      f"{len(robe.vertex_groups)} vertex groups, "
      f"{len(robe.data.materials)} materials, "
      f"{len(robe.data.uv_layers)} UV layers")


# ── 2. Measure lower_torso's natural y range (for vertical stretch) ─────────
# lower_torso's bottom ring sits at  y = TOP_Y  (it IS the body's hip
# boundary edge with leg_upper).  Its top ring sits higher up at the
# upper_torso boundary.  We're going to remap [Y_ORIG_BOT, Y_ORIG_TOP]
# → [TOP_Y, BOT_Y]  so the bottom ring stays put as the waistband and
# the top ring stretches down to become the hem.
ys = [v.co.y for v in robe.data.vertices]
Y_ORIG_BOT = min(ys)   # ≈ TOP_Y, hip ring (lower_torso ↔ leg_upper boundary)
Y_ORIG_TOP = max(ys)   # waist ring (lower_torso ↔ upper_torso boundary)
print(f"lower_torso original y range: [{Y_ORIG_BOT:.2f}, {Y_ORIG_TOP:.2f}]  "
      f"(stretch factor: {(TOP_Y - BOT_Y) / (Y_ORIG_TOP - Y_ORIG_BOT):.2f}x)")


def remap_y(y: float) -> float:
    """Map original lower_torso y (bottom = TOP_Y, top = Y_ORIG_TOP) to
    robe y (waist = TOP_Y, hem = BOT_Y).  Linear stretch + inversion."""
    t = (y - Y_ORIG_BOT) / (Y_ORIG_TOP - Y_ORIG_BOT)
    return TOP_Y - t * (TOP_Y - BOT_Y)


# ── 3. Sample the body's boundary ring at the waist ─────────────────────────
# Collect verts within ±SEAM_KEEP of  Y_ORIG_BOT  (the bottom ring of
# lower_torso, which IS the waist boundary in original coordinates).
# Centroid + per-vertex polar coords describe the body's actual oval-ish
# silhouette at the waistband — the cone hugs this at t = 1.
boundary_verts = [
    v for v in robe.data.vertices if abs(v.co.y - Y_ORIG_BOT) < SEAM_KEEP
]
if not boundary_verts:
    raise RuntimeError(f"No body vertices near hip ring Y={Y_ORIG_BOT:.3f}")

cx = sum(v.co.x for v in boundary_verts) / len(boundary_verts)
cz = sum(v.co.z for v in boundary_verts) / len(boundary_verts)

boundary_polar = []
for v in boundary_verts:
    dx = v.co.x - cx
    dz = v.co.z - cz
    ang = math.atan2(dz, dx)
    if ang < 0:
        ang += 2.0 * math.pi
    boundary_polar.append((ang, math.hypot(dx, dz)))

print(f"Boundary ring: {len(boundary_verts)} verts  "
      f"centroid=({cx:.2f},{cz:.2f})  "
      f"r=[{min(r for _, r in boundary_polar):.2f}, "
      f"{max(r for _, r in boundary_polar):.2f}]")


def smooth_ring(values, passes: int = 3):
    r = list(values)
    n = len(r)
    for _ in range(passes):
        r = [(r[(i - 1) % n] + r[i] + r[(i + 1) % n]) / 3.0 for i in range(n)]
    return r


def bin_to_sectors(polar_pts, n_sectors: int):
    """Bin (angle, radius) points into n_sectors angular bins (max-radius
    per bin) and fill empty sectors via angular nearest-neighbour."""
    sector_r = [0.0] * n_sectors
    filled   = [False] * n_sectors
    for ang, r in polar_pts:
        s = int(ang / (2.0 * math.pi) * n_sectors) % n_sectors
        if r > sector_r[s]:
            sector_r[s] = r
            filled[s]   = True
    for i in range(n_sectors):
        if filled[i]:
            continue
        for offset in range(1, n_sectors // 2 + 1):
            for ds in (offset, -offset):
                idx = (i + ds) % n_sectors
                if filled[idx]:
                    sector_r[i] = sector_r[idx]
                    filled[i]   = True
                    break
            if filled[i]:
                break
    return sector_r


waist_raw   = bin_to_sectors(boundary_polar, NUM_SEGS)
waist_smth  = smooth_ring(waist_raw, passes=2)
waist_radii = [
    max(waist_smth[i], waist_raw[i]) + INFLATE for i in range(NUM_SEGS)
]

# Per-sector hem radii.  Each sector's hem = its waist radius + FLARE,
# which preserves the body's natural waist oval (wider on the sides
# than front-to-back) all the way down — the hem keeps the same shape
# as the waist, just expanded outward by a uniform amount.  Reads as
# "fabric draping from a hip" rather than a turned ceramic cone.
hem_radii = [waist_radii[i] + FLARE for i in range(NUM_SEGS)]
print(f"Waist radii: min={min(waist_radii):.2f}  max={max(waist_radii):.2f}  "
      f"(oval ratio {max(waist_radii)/min(waist_radii):.2f})")
print(f"Hem radii:   min={min(hem_radii):.2f}  max={max(hem_radii):.2f}  "
      f"(oval ratio {max(hem_radii)/min(hem_radii):.2f})")


# ── 4. Vertical stretch + radial projection ────────────────────────────────
# Per-vertex transform:
#   1. Compute angle θ from centroid using ORIGINAL (x, z) — these are
#      the body's silhouette at this vertex's height.
#   2. Remap y:  Y_ORIG_BOT → TOP_Y (waist),  Y_ORIG_TOP → BOT_Y (hem).
#   3. Compute cone radius at the new y, blended per-sector between the
#      body waist silhouette (t = 1) and the uniform hem circle (t = 0).
#   4. Replace x, z with the projected position;  keep θ exact, replace
#      r.
#
# No vertex deletion is needed — lower_torso is fully within the source
# range we're remapping from, and after remap every vertex is within
# [BOT_Y, TOP_Y].  Topology stays closed end-to-end.
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(robe.data)
bm.verts.ensure_lookup_table()

projected = 0
for v in bm.verts:
    dx = v.co.x - cx
    dz = v.co.z - cz
    angle = math.atan2(dz, dx)
    if angle < 0:
        angle += 2.0 * math.pi

    new_y = remap_y(v.co.y)
    t = (new_y - BOT_Y) / HEIGHT
    t = max(0.0, min(1.0, t))

    sector = int(angle / (2.0 * math.pi) * NUM_SEGS) % NUM_SEGS
    target_r = waist_radii[sector] * t + hem_radii[sector] * (1.0 - t)

    v.co.x = cx + target_r * math.cos(angle)
    v.co.y = new_y
    v.co.z = cz + target_r * math.sin(angle)
    projected += 1

bm.normal_update()
for f in bm.faces:
    f.smooth = True

bmesh.update_edit_mesh(robe.data)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()

print(f"Projected {projected} verts (no deletion — single closed tube)")
print(f"Robe geometry: {len(robe.data.vertices)} verts, "
      f"{len(robe.data.polygons)} faces, "
      f"{len(robe.data.materials)} materials, "
      f"{len(robe.data.uv_layers)} UV layers")


# ── 5. Rebind weights via KD-tree against the leg anatomy ──────────────────
# After projection the robe spans waist → ankle, but it still carries
# only lower_torso's weights (spine / hip).  That's why the legs poke
# straight through during animation — robe verts at knee / shin height
# never get told to follow the leg bones.
#
# For each robe vertex we now find the K-nearest body vertices in
# weight_ref (which contains the FULL leg anatomy at the original body
# pose), and inverse-distance-blend their bone weights.  Verts on the
# right side of the cone end up nearest to the right leg → right-leg
# bones;  hem-height verts end up nearest to leg_shin / leg_ankle →
# Knee / Leg / Foot bones.  This is the same KD-tree pipeline that
# rigs gloves and other skinned equipment from body anatomy.
for vg in robe.vertex_groups:
    vg.remove(range(len(robe.data.vertices)))

kd = KDTree(len(weight_ref.data.vertices))
for i, v in enumerate(weight_ref.data.vertices):
    kd.insert(v.co, i)
kd.balance()

# Pre-cache weight_ref vertex group names by index for speed.  Each
# weight_ref vertex stores its weights as v.groups[*].group → weight.
ref_vgroup_names = [vg.name for vg in weight_ref.vertex_groups]

transferred = 0
for rv_idx, rv in enumerate(robe.data.vertices):
    neighbors = kd.find_n(rv.co, WEIGHT_NEIGHBORS)

    inv_weights = [
        (idx, 1.0 / (dist ** WEIGHT_POWER + 1e-8))
        for _, idx, dist in neighbors
    ]
    total_inv = sum(w for _, w in inv_weights)
    if total_inv <= 0:
        continue

    blended: dict[str, float] = {}
    for body_idx, inv_w in inv_weights:
        factor = inv_w / total_inv
        for g in weight_ref.data.vertices[body_idx].groups:
            bw = g.weight
            if bw <= 0.0001:
                continue
            name = ref_vgroup_names[g.group]
            blended[name] = blended.get(name, 0.0) + bw * factor

    wtotal = sum(blended.values())
    if wtotal <= 0:
        continue

    for name, w in blended.items():
        nw = w / wtotal
        if nw < 0.0001:
            continue
        if name in robe.vertex_groups:
            robe.vertex_groups[name].add([rv_idx], nw, "REPLACE")
        else:
            new_vg = robe.vertex_groups.new(name=name)
            new_vg.add([rv_idx], nw, "REPLACE")
        transferred += 1

print(f"Rebound weights: {transferred} entries from leg anatomy")


# ── 6. Clean up weight_ref before export ───────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
weight_ref.select_set(True)
bpy.context.view_layer.objects.active = weight_ref
bpy.ops.object.delete(use_global=False)


# ── 7. Export — match shell_v1 export settings exactly ─────────────────────
# Notably:  NO  export_all_influences=True.  The shells use the default
# 4-influence skinning, and that's part of what makes Meshy classify them
# as character clothing instead of a hero prop.  Same for materials: we
# keep whatever the body region had (skin) instead of injecting a custom
# Principled BSDF — Meshy uses the existing material as a prior.
out_path = os.path.join(OUT_DIR, "robe_v2.glb")

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
    export_def_bones=True,
    export_animations=False,
    export_materials="EXPORT",
)

print(f"\nRobe V2 exported: {out_path}")
print(f"  Vertices:    {len(robe.data.vertices)}")
print(f"  Faces:       {len(robe.data.polygons)}")
print(f"  UV layers:   {len(robe.data.uv_layers)}")
print(f"  Materials:   {len(robe.data.materials)}")
print(f"  Vert groups: {len(robe.vertex_groups)}")
