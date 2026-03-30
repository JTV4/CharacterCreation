"""
split_base_female_v2.py
========================
Splits BaseFemale.glb into 12 hideable body regions using true bisect cuts.

All cut positions are specified in WORLD space (Z-up, meters) and
automatically converted to local/edit-mode space before cutting. This
handles the 0.01 armature scale and Y↔Z axis swap from the GLTF import.

Body / leg regions → bisect_plane at Z (horizontal cuts)
Arm / hand regions → bisect_plane at X (vertical cuts at elbow & wrist),
                     processed left + right independently then joined.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python split_base_female_v2.py
"""

import os
import bpy
import bmesh
from mathutils import Vector

SRC = os.path.abspath("rig/CharacterMesh/BaseFemale.glb")
OUT = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")

# ── User-defined cut positions (WORLD space: Z-up, meters) ───────────────────
NECK_Z       = 1.486
WAIST_Z      = 1.24
HIP_Z        = 1.066
MID_THIGH_Z  = 0.796
ABOVE_KNEE_Z = 0.572
BELOW_KNEE_Z = 0.436
MID_SHIN_Z   = 0.27
ANKLE_Z      = 0.10

# Arm joint positions (exact world coords from user's Blender markers)
ELBOW_L = (0.305,  0.002, 1.412)
WRIST_L = (0.645,  0.002, 1.396)
ELBOW_R = (-0.305, 0.04,  1.412)
WRIST_R = (-0.645, -0.002, 1.396)

# ── Z ranges for body regions (world Z, meters) ──────────────────────────────
INF = float("inf")
Z_RANGES = {
    "base_body_head":        (NECK_Z,       INF),
    "base_body_upper_torso": (WAIST_Z,      NECK_Z),
    "base_body_lower_torso": (HIP_Z,        WAIST_Z),
    "base_body_leg_upper":   (MID_THIGH_Z,  HIP_Z),
    "base_body_leg_thigh":   (ABOVE_KNEE_Z, MID_THIGH_Z),
    "base_body_leg_knee":    (BELOW_KNEE_Z, ABOVE_KNEE_Z),
    "base_body_leg_shin":    (MID_SHIN_Z,   BELOW_KNEE_Z),
    "base_body_leg_ankle":   (ANKLE_Z,      MID_SHIN_Z),
    "base_body_foot":        (-INF,         ANKLE_Z),
}
BODY_REGIONS = set(Z_RANGES.keys())
ARM_REGIONS  = {"base_body_arm_upper", "base_body_arm_lower", "base_body_hands"}

REGION_ORDER = [
    "base_body_head",
    "base_body_upper_torso",
    "base_body_lower_torso",
    "base_body_arm_upper",
    "base_body_arm_lower",
    "base_body_hands",
    "base_body_leg_upper",
    "base_body_leg_thigh",
    "base_body_leg_knee",
    "base_body_leg_shin",
    "base_body_leg_ankle",
    "base_body_foot",
]

# ── Bone name sets ────────────────────────────────────────────────────────────
ARM_UPPER_BONES = {"mixamorig:LeftArm", "mixamorig:RightArm",
                   "mixamorig:LeftShoulder", "mixamorig:RightShoulder"}
ARM_LOWER_BONES = {"mixamorig:LeftForeArm", "mixamorig:RightForeArm"}
HAND_BONES = {
    "mixamorig:LeftHand",   "mixamorig:RightHand",
    "mixamorig:LeftHandThumb1",  "mixamorig:LeftHandThumb2",
    "mixamorig:LeftHandThumb3",  "mixamorig:LeftHandThumb4",
    "mixamorig:LeftHandIndex1",  "mixamorig:LeftHandIndex2",
    "mixamorig:LeftHandIndex3",  "mixamorig:LeftHandIndex4",
    "mixamorig:LeftHandMiddle1", "mixamorig:LeftHandMiddle2",
    "mixamorig:LeftHandMiddle3", "mixamorig:LeftHandMiddle4",
    "mixamorig:LeftHandRing1",   "mixamorig:LeftHandRing2",
    "mixamorig:LeftHandRing3",   "mixamorig:LeftHandRing4",
    "mixamorig:LeftHandPinky1",  "mixamorig:LeftHandPinky2",
    "mixamorig:LeftHandPinky3",  "mixamorig:LeftHandPinky4",
    "mixamorig:RightHandThumb1", "mixamorig:RightHandThumb2",
    "mixamorig:RightHandThumb3", "mixamorig:RightHandThumb4",
    "mixamorig:RightHandIndex1", "mixamorig:RightHandIndex2",
    "mixamorig:RightHandIndex3", "mixamorig:RightHandIndex4",
    "mixamorig:RightHandMiddle1","mixamorig:RightHandMiddle2",
    "mixamorig:RightHandMiddle3","mixamorig:RightHandMiddle4",
    "mixamorig:RightHandRing1",  "mixamorig:RightHandRing2",
    "mixamorig:RightHandRing3",  "mixamorig:RightHandRing4",
    "mixamorig:RightHandPinky1", "mixamorig:RightHandPinky2",
    "mixamorig:RightHandPinky3", "mixamorig:RightHandPinky4",
}
ALL_ARM_BONES = ARM_UPPER_BONES | ARM_LOWER_BONES | HAND_BONES

ARM_TERRITORY_THRESHOLD = 0.10
ARM_EXCLUDE_SOFT = 0.50
ARM_EXCLUDE_HARD = 0.20

# ── Helpers ───────────────────────────────────────────────────────────────────
def world_to_local_point(mat_inv, world_pt):
    return mat_inv @ Vector(world_pt)

def world_to_local_normal(mat_inv, world_normal):
    n = mat_inv.to_3x3() @ Vector(world_normal)
    n.normalize()
    return n

def bisect_clean(bm, local_point, local_normal):
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bmesh.ops.bisect_plane(
        bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=local_point,
        plane_no=local_normal,
        clear_outer=True,
        clear_inner=False,
    )

def ensure_smooth(bm):
    """Mark all faces as smooth-shaded to preserve the original mesh appearance."""
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.smooth = True

# ── 1. Load scene ─────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=SRC)
bpy.context.view_layer.update()

src_mesh = next(
    o for o in bpy.data.objects
    if o.type == "MESH" and len(o.vertex_groups) > 10
)
armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
print(f"Source mesh: {src_mesh.name}  ({len(src_mesh.data.vertices)} verts)")

mat_world = src_mesh.matrix_world
mat_inv   = mat_world.inverted()

# Print coordinate conversions
print(f"\nCoordinate conversion (world → local):")
for label, pt in [("Elbow L", ELBOW_L), ("Wrist L", WRIST_L),
                   ("Elbow R", ELBOW_R), ("Wrist R", WRIST_R)]:
    lp = world_to_local_point(mat_inv, pt)
    print(f"  {label:10s} world ({pt[0]:.3f},{pt[1]:.3f},{pt[2]:.3f}) → local ({lp.x:.2f},{lp.y:.2f},{lp.z:.2f})")

# ── 2. Pre-classify vertices ─────────────────────────────────────────────────
vg_arm_upper = {vg.index for vg in src_mesh.vertex_groups if vg.name in ARM_UPPER_BONES}
vg_arm_lower = {vg.index for vg in src_mesh.vertex_groups if vg.name in ARM_LOWER_BONES}
vg_hand      = {vg.index for vg in src_mesh.vertex_groups if vg.name in HAND_BONES}
vg_all_arm   = {vg.index for vg in src_mesh.vertex_groups if vg.name in ALL_ARM_BONES}
vg_arm_only  = vg_arm_upper | vg_arm_lower

arm_upper_w = {}
arm_lower_w = {}
hand_w      = {}
all_arm_w   = {}
arm_only_w  = {}

for v in src_mesh.data.vertices:
    au = sum(g.weight for g in v.groups if g.group in vg_arm_upper)
    al = sum(g.weight for g in v.groups if g.group in vg_arm_lower)
    ha = sum(g.weight for g in v.groups if g.group in vg_hand)
    arm_upper_w[v.index] = au
    arm_lower_w[v.index] = al
    hand_w[v.index]      = ha
    all_arm_w[v.index]   = au + al + ha
    arm_only_w[v.index]  = au + al

# Arm territory: all vertices with significant arm+hand influence
arm_territory = {vi for vi, w in all_arm_w.items() if w >= ARM_TERRITORY_THRESHOLD}

# Body exclusion sets
hand_vi = {vi for vi, w in hand_w.items() if w >= 0.25}
arm_exclude_soft = {vi for vi, w in arm_only_w.items() if w >= ARM_EXCLUDE_SOFT} | hand_vi
arm_exclude_hard = {vi for vi, w in arm_only_w.items() if w >= ARM_EXCLUDE_HARD} | hand_vi
print(f"\nArm territory: {len(arm_territory)} verts")
print(f"Arm exclusion — soft: {len(arm_exclude_soft)}, hard: {len(arm_exclude_hard)}")

# ── 3. Build body/leg regions ─────────────────────────────────────────────────
new_objects = []

for region_name in REGION_ORDER:
    if region_name in ARM_REGIONS:
        continue  # handled separately below

    bpy.ops.object.select_all(action="DESELECT")
    src_mesh.select_set(True)
    bpy.context.view_layer.objects.active = src_mesh
    bpy.ops.object.duplicate(linked=False)
    copy = bpy.context.active_object
    copy.name = region_name
    copy.data.name = region_name

    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(copy.data)
    bm.verts.ensure_lookup_table()

    z_min, z_max = Z_RANGES[region_name]

    SHOULDER_REGIONS = {"base_body_head", "base_body_upper_torso"}
    exclude_set = arm_exclude_soft if region_name in SHOULDER_REGIONS else arm_exclude_hard
    del_arm = [v for v in bm.verts if v.index in exclude_set]
    if del_arm:
        bmesh.ops.delete(bm, geom=del_arm, context="VERTS")

    if z_max < INF:
        lp = world_to_local_point(mat_inv, (0, 0, z_max))
        ln = world_to_local_normal(mat_inv, (0, 0, 1))
        bisect_clean(bm, tuple(lp), tuple(ln))

    if z_min > -INF:
        lp = world_to_local_point(mat_inv, (0, 0, z_min))
        ln = world_to_local_normal(mat_inv, (0, 0, -1))
        bisect_clean(bm, tuple(lp), tuple(ln))

    ensure_smooth(bm)
    bmesh.update_edit_mesh(copy.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    vcount = len(copy.data.vertices)
    print(f"  {region_name}: {vcount} verts")
    new_objects.append(copy)

# ── 4. Build arm regions (bisect at elbow/wrist, left+right independently) ───
def build_arm_half(region_name, side):
    """
    Build one half (left or right) of an arm region.
    Uses bone weights to isolate arm territory, then bisect for clean cuts.
    """
    bpy.ops.object.select_all(action="DESELECT")
    src_mesh.select_set(True)
    bpy.context.view_layer.objects.active = src_mesh
    bpy.ops.object.duplicate(linked=False)
    half = bpy.context.active_object

    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(half.data)
    bm.verts.ensure_lookup_table()

    # Remove non-arm vertices
    del_verts = [v for v in bm.verts if v.index not in arm_territory]
    if del_verts:
        bmesh.ops.delete(bm, geom=del_verts, context="VERTS")

    # Split at the midline to isolate this side
    midline = world_to_local_point(mat_inv, (0, 0, 0))
    if side == "left":
        # Remove the right side (X < 0 in world → remove negative-X half)
        ln = world_to_local_normal(mat_inv, (-1, 0, 0))
    else:
        # Remove the left side (X > 0 in world → remove positive-X half)
        ln = world_to_local_normal(mat_inv, (1, 0, 0))
    bisect_clean(bm, tuple(midline), tuple(ln))

    # Determine cut points and normals for this side
    if side == "left":
        elbow_lp = world_to_local_point(mat_inv, ELBOW_L)
        wrist_lp = world_to_local_point(mat_inv, WRIST_L)
        outward  = world_to_local_normal(mat_inv, (1, 0, 0))   # away from body
        inward   = world_to_local_normal(mat_inv, (-1, 0, 0))  # toward body
    else:
        elbow_lp = world_to_local_point(mat_inv, ELBOW_R)
        wrist_lp = world_to_local_point(mat_inv, WRIST_R)
        outward  = world_to_local_normal(mat_inv, (-1, 0, 0))
        inward   = world_to_local_normal(mat_inv, (1, 0, 0))

    if region_name == "base_body_arm_upper":
        # Keep shoulder to elbow: remove everything past elbow
        bisect_clean(bm, tuple(elbow_lp), tuple(outward))

    elif region_name == "base_body_arm_lower":
        # Keep elbow to wrist: remove inside of elbow, remove outside of wrist
        bisect_clean(bm, tuple(elbow_lp), tuple(inward))
        bisect_clean(bm, tuple(wrist_lp), tuple(outward))

    elif region_name == "base_body_hands":
        # Keep past wrist: remove inside of wrist
        bisect_clean(bm, tuple(wrist_lp), tuple(inward))

    ensure_smooth(bm)
    bmesh.update_edit_mesh(half.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    return half


for region_name in ["base_body_arm_upper", "base_body_arm_lower", "base_body_hands"]:
    left_half  = build_arm_half(region_name, "left")
    right_half = build_arm_half(region_name, "right")

    # Join left + right into one object
    bpy.ops.object.select_all(action="DESELECT")
    left_half.select_set(True)
    right_half.select_set(True)
    bpy.context.view_layer.objects.active = left_half
    bpy.ops.object.join()

    result = left_half
    result.name = region_name
    result.data.name = region_name

    vcount = len(result.data.vertices)
    print(f"  {region_name}: {vcount} verts (bilateral bisect)")
    new_objects.append(result)

# ── 5. Clean up ───────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
keep_set = set(new_objects)
if armature:
    keep_set.add(armature)
for o in list(bpy.data.objects):
    if o not in keep_set:
        o.select_set(True)
bpy.ops.object.delete(use_global=False)

# ── 6. Export ─────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
for o in new_objects:
    o.select_set(True)
if armature:
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

bpy.ops.export_scene.gltf(
    filepath=OUT,
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
print(f"\nExported → {OUT}")
