"""
generate_base_male_v2.py
========================
Generates a male base mesh by morphing the female BaseFemale.glb into male
proportions while preserving the Mixamo skeleton and all bone weights, then
splits into 12 hideable body regions matching the Female V2 structure.

The morph applies:
  - Z-height-dependent lateral (X) and depth (Y) scaling
  - Asymmetric front/back Y scaling to flatten the chest
  - Non-uniform height (Z) remapping for longer legs and torso
  - Arm-specific radial thickening with smooth body/arm blending

Output: viewer/public/models/BaseMaleV2.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_base_male_v2.py
"""

import os
import bpy
import bmesh
from mathutils import Vector

SRC = os.path.abspath("rig/CharacterMesh/BaseFemale.glb")
OUT = os.path.abspath("viewer/public/models/BaseMaleV2.glb")

# ── Morph profiles ────────────────────────────────────────────────────────────
# Each row: (female_z, male_z, x_scale, y_scale_front, y_scale_back)
#   x_scale:       lateral scaling around centerline X=0
#   y_scale_front: depth scaling for front-facing vertices (chest side)
#   y_scale_back:  depth scaling for back-facing vertices
MORPH_PROFILES = [
    # female_z  male_z   x_scl  y_front y_back
    (-0.10,     -0.10,   1.12,  1.12,   1.12),   # below ground (safety)
    ( 0.00,      0.00,   1.12,  1.12,   1.12),   # feet
    ( 0.10,      0.11,   1.10,  1.10,   1.10),   # ankle
    ( 0.27,      0.30,   1.12,  1.12,   1.12),   # mid shin
    ( 0.436,     0.48,   1.10,  1.10,   1.10),   # below knee
    ( 0.572,     0.62,   1.08,  1.08,   1.08),   # above knee
    ( 0.796,     0.86,   1.06,  1.06,   1.06),   # mid thigh
    ( 1.066,     1.14,   0.82,  0.96,   1.00),   # hip (narrower for V-taper)
    ( 1.15,      1.23,   0.88,  0.96,   1.02),   # above hip
    ( 1.24,      1.33,   1.08,  0.88,   1.06),   # waist (wider, straighter)
    ( 1.36,      1.46,   1.25,  0.68,   1.02),   # chest (broad, flatten front)
    ( 1.486,     1.58,   1.35,  0.72,   1.04),   # shoulders (broad)
    ( 1.52,      1.60,   1.28,  1.12,   1.12),   # neck base (trapezius)
    ( 1.55,      1.62,   1.22,  1.18,   1.18),   # neck (thick, minimal Z stretch)
    ( 1.65,      1.71,   1.10,  1.05,   1.05),   # jaw
    ( 1.85,      1.90,   1.03,  1.03,   1.03),   # top of head (barely taller)
    ( 2.50,      2.55,   1.00,  1.00,   1.00),   # above head (safety)
]

ARM_THICKEN    = 1.25
ARM_CENTER_Z   = 1.40
ARM_BLEND_LOW  = 0.10
ARM_BLEND_HIGH = 0.40
Y_BLEND_WIDTH  = 0.05

# ── Bone classifications ─────────────────────────────────────────────────────
ARM_UPPER_BONES = {
    "mixamorig:LeftArm", "mixamorig:RightArm",
    "mixamorig:LeftShoulder", "mixamorig:RightShoulder",
}
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
ARM_REGIONS = {"base_body_arm_upper", "base_body_arm_lower", "base_body_hands"}


# ── Interpolation helpers ─────────────────────────────────────────────────────
def _interp(profiles, fz, col):
    if fz <= profiles[0][0]:
        return profiles[0][col]
    if fz >= profiles[-1][0]:
        return profiles[-1][col]
    for i in range(len(profiles) - 1):
        z0, z1 = profiles[i][0], profiles[i + 1][0]
        if z0 <= fz <= z1:
            t = (fz - z0) / (z1 - z0) if z1 > z0 else 0.0
            return profiles[i][col] + t * (profiles[i + 1][col] - profiles[i][col])
    return profiles[-1][col]


def remap_z(fz):
    return _interp(MORPH_PROFILES, fz, 1)

def x_scale_at(fz):
    return _interp(MORPH_PROFILES, fz, 2)

def y_front_at(fz):
    return _interp(MORPH_PROFILES, fz, 3)

def y_back_at(fz):
    return _interp(MORPH_PROFILES, fz, 4)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ── Morph functions ───────────────────────────────────────────────────────────
FRONT_SIGN = 1.0  # set at runtime after detecting front direction


def morph_body(wp):
    fz = wp.z
    new_z = remap_z(fz)
    new_x = wp.x * x_scale_at(fz)

    yf = y_front_at(fz)
    yb = y_back_at(fz)
    blend = 0.5 + 0.5 * clamp((wp.y * FRONT_SIGN) / Y_BLEND_WIDTH, -1.0, 1.0)
    sy = yb + blend * (yf - yb)
    new_y = wp.y * sy

    return Vector((new_x, new_y, new_z))


def morph_arm(wp, sh_offset):
    sign = 1.0 if wp.x > 0 else -1.0
    new_x = wp.x + sh_offset * sign
    new_y = wp.y * ARM_THICKEN
    new_z = ARM_CENTER_Z + (wp.z - ARM_CENTER_Z) * ARM_THICKEN
    return Vector((new_x, new_y, new_z))


# ── Bisect / split helpers ───────────────────────────────────────────────────
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
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.smooth = True


# ══════════════════════════════════════════════════════════════════════════════
#  1. Load scene
# ══════════════════════════════════════════════════════════════════════════════
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


# ══════════════════════════════════════════════════════════════════════════════
#  2. Classify vertices by arm bone weight
# ══════════════════════════════════════════════════════════════════════════════
vg_arm_upper = {vg.index for vg in src_mesh.vertex_groups if vg.name in ARM_UPPER_BONES}
vg_arm_lower = {vg.index for vg in src_mesh.vertex_groups if vg.name in ARM_LOWER_BONES}
vg_hand      = {vg.index for vg in src_mesh.vertex_groups if vg.name in HAND_BONES}
vg_all_arm   = {vg.index for vg in src_mesh.vertex_groups if vg.name in ALL_ARM_BONES}
vg_arm_only  = vg_arm_upper | vg_arm_lower

all_arm_w  = {}
arm_upper_w = {}
arm_lower_w = {}
hand_w     = {}
arm_only_w = {}

for v in src_mesh.data.vertices:
    au = sum(g.weight for g in v.groups if g.group in vg_arm_upper)
    al = sum(g.weight for g in v.groups if g.group in vg_arm_lower)
    ha = sum(g.weight for g in v.groups if g.group in vg_hand)
    arm_upper_w[v.index] = au
    arm_lower_w[v.index] = al
    hand_w[v.index]      = ha
    all_arm_w[v.index]   = au + al + ha
    arm_only_w[v.index]  = au + al


# ══════════════════════════════════════════════════════════════════════════════
#  3. Detect front direction (which Y sign is the chest/face side)
# ══════════════════════════════════════════════════════════════════════════════
chest_max_y = -999.0
chest_min_y =  999.0
for v in src_mesh.data.vertices:
    if all_arm_w[v.index] > 0.10:
        continue
    wp = mat_world @ v.co
    if 1.30 < wp.z < 1.45:
        if wp.y > chest_max_y:
            chest_max_y = wp.y
        if wp.y < chest_min_y:
            chest_min_y = wp.y

if abs(chest_max_y) > abs(chest_min_y):
    FRONT_SIGN = 1.0
else:
    FRONT_SIGN = -1.0
print(f"Front direction: {'+ Y' if FRONT_SIGN > 0 else '- Y'}  "
      f"(chest Y range: {chest_min_y:.4f} to {chest_max_y:.4f})")


# ══════════════════════════════════════════════════════════════════════════════
#  4. Compute shoulder offset from armature
# ══════════════════════════════════════════════════════════════════════════════
female_shoulder_l_x = 0.12
female_shoulder_r_x = -0.12
if armature:
    for bone in armature.data.bones:
        if bone.name == "mixamorig:LeftArm":
            pos = armature.matrix_world @ bone.head_local
            female_shoulder_l_x = pos.x
        elif bone.name == "mixamorig:RightArm":
            pos = armature.matrix_world @ bone.head_local
            female_shoulder_r_x = pos.x

shoulder_z = 1.486
sx_at_shoulder = x_scale_at(shoulder_z)
male_shoulder_l_x = female_shoulder_l_x * sx_at_shoulder
male_shoulder_r_x = female_shoulder_r_x * sx_at_shoulder
shoulder_offset = abs(male_shoulder_l_x) - abs(female_shoulder_l_x)
print(f"Shoulder L: {female_shoulder_l_x:.4f} → {male_shoulder_l_x:.4f}  "
      f"(offset={shoulder_offset:.4f}, x_scale={sx_at_shoulder:.3f})")


# ══════════════════════════════════════════════════════════════════════════════
#  5. Morph all vertices
# ══════════════════════════════════════════════════════════════════════════════
print("\nMorphing vertices to male proportions...")
for v in src_mesh.data.vertices:
    wp = mat_world @ v.co

    aw = all_arm_w[v.index]
    arm_t = clamp((aw - ARM_BLEND_LOW) / (ARM_BLEND_HIGH - ARM_BLEND_LOW), 0.0, 1.0)

    body_p = morph_body(wp)
    arm_p  = morph_arm(wp, shoulder_offset)

    new_wp = body_p * (1.0 - arm_t) + arm_p * arm_t
    v.co = mat_inv @ new_wp

src_mesh.data.update()

# Verify morph extents
verts_world = [mat_world @ v.co for v in src_mesh.data.vertices]
z_min_v = min(v.z for v in verts_world)
z_max_v = max(v.z for v in verts_world)
x_min_v = min(v.x for v in verts_world)
x_max_v = max(v.x for v in verts_world)
print(f"Morphed {len(src_mesh.data.vertices)} vertices")
print(f"  Height: {z_min_v:.3f} to {z_max_v:.3f}  (span={z_max_v - z_min_v:.3f})")
print(f"  Width:  {x_min_v:.3f} to {x_max_v:.3f}  (span={x_max_v - x_min_v:.3f})")


# ══════════════════════════════════════════════════════════════════════════════
#  6. Compute male cut positions
# ══════════════════════════════════════════════════════════════════════════════
NECK_Z       = remap_z(1.486)
WAIST_Z      = remap_z(1.24)
HIP_Z        = remap_z(1.066)
MID_THIGH_Z  = remap_z(0.796)
ABOVE_KNEE_Z = remap_z(0.572)
BELOW_KNEE_Z = remap_z(0.436)
MID_SHIN_Z   = remap_z(0.27)
ANKLE_Z      = remap_z(0.10)

print(f"\nMale cut positions (world Z):")
for label, z in [("Neck", NECK_Z), ("Waist", WAIST_Z), ("Hip", HIP_Z),
                  ("Mid-thigh", MID_THIGH_Z), ("Above-knee", ABOVE_KNEE_Z),
                  ("Below-knee", BELOW_KNEE_Z), ("Mid-shin", MID_SHIN_Z),
                  ("Ankle", ANKLE_Z)]:
    print(f"  {label:12s}: {z:.3f}")

# Arm cuts: shifted by shoulder offset, Z barely changes from thickening
arm_z_elbow = ARM_CENTER_Z + (1.412 - ARM_CENTER_Z) * ARM_THICKEN
arm_z_wrist = ARM_CENTER_Z + (1.396 - ARM_CENTER_Z) * ARM_THICKEN
ELBOW_L = ( 0.305 + shoulder_offset,  0.002, arm_z_elbow)
WRIST_L = ( 0.645 + shoulder_offset,  0.002, arm_z_wrist)
ELBOW_R = (-0.305 - shoulder_offset,  0.04,  arm_z_elbow)
WRIST_R = (-0.645 - shoulder_offset, -0.002, arm_z_wrist)

SHOULDER_L_X = male_shoulder_l_x
SHOULDER_R_X = male_shoulder_r_x

print(f"\nShoulder cut X: left={SHOULDER_L_X:.4f}, right={SHOULDER_R_X:.4f}")
print(f"Elbow L: ({ELBOW_L[0]:.3f}, {ELBOW_L[1]:.3f}, {ELBOW_L[2]:.3f})")
print(f"Wrist L: ({WRIST_L[0]:.3f}, {WRIST_L[1]:.3f}, {WRIST_L[2]:.3f})")


# ══════════════════════════════════════════════════════════════════════════════
#  7. Prepare arm classification for splitting
# ══════════════════════════════════════════════════════════════════════════════
arm_territory    = {vi for vi, w in all_arm_w.items() if w >= ARM_TERRITORY_THRESHOLD}
hand_vi          = {vi for vi, w in hand_w.items() if w >= 0.25}
arm_exclude_soft = {vi for vi, w in arm_only_w.items() if w >= ARM_EXCLUDE_SOFT} | hand_vi
arm_exclude_hard = {vi for vi, w in arm_only_w.items() if w >= ARM_EXCLUDE_HARD} | hand_vi
print(f"\nArm territory: {len(arm_territory)} verts")
print(f"Arm exclusion — soft: {len(arm_exclude_soft)}, hard: {len(arm_exclude_hard)}")


# ══════════════════════════════════════════════════════════════════════════════
#  8. Split into 12 body regions
# ══════════════════════════════════════════════════════════════════════════════
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

print("\nSplitting into regions...")
new_objects = []

# ── Body / leg regions ────────────────────────────────────────────────────────
for region_name in REGION_ORDER:
    if region_name in ARM_REGIONS:
        continue

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

    if region_name == "base_body_upper_torso":
        exclude_set = None
    elif region_name == "base_body_head":
        exclude_set = arm_exclude_soft
    else:
        exclude_set = arm_exclude_hard
    if exclude_set:
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

    if region_name == "base_body_upper_torso":
        lp = world_to_local_point(mat_inv, (SHOULDER_L_X, 0, 0))
        ln = world_to_local_normal(mat_inv, (1, 0, 0))
        bisect_clean(bm, tuple(lp), tuple(ln))
        lp = world_to_local_point(mat_inv, (SHOULDER_R_X, 0, 0))
        ln = world_to_local_normal(mat_inv, (-1, 0, 0))
        bisect_clean(bm, tuple(lp), tuple(ln))

    ensure_smooth(bm)
    bmesh.update_edit_mesh(copy.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    vcount = len(copy.data.vertices)
    print(f"  {region_name}: {vcount} verts")
    new_objects.append(copy)


# ── Arm regions (bilateral bisect) ───────────────────────────────────────────
def build_arm_half(region_name, side):
    bpy.ops.object.select_all(action="DESELECT")
    src_mesh.select_set(True)
    bpy.context.view_layer.objects.active = src_mesh
    bpy.ops.object.duplicate(linked=False)
    half = bpy.context.active_object

    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(half.data)
    bm.verts.ensure_lookup_table()

    del_verts = [v for v in bm.verts if v.index not in arm_territory]
    if del_verts:
        bmesh.ops.delete(bm, geom=del_verts, context="VERTS")

    midline = world_to_local_point(mat_inv, (0, 0, 0))
    if side == "left":
        ln = world_to_local_normal(mat_inv, (-1, 0, 0))
    else:
        ln = world_to_local_normal(mat_inv, (1, 0, 0))
    bisect_clean(bm, tuple(midline), tuple(ln))

    if side == "left":
        elbow_lp = world_to_local_point(mat_inv, ELBOW_L)
        wrist_lp = world_to_local_point(mat_inv, WRIST_L)
        outward  = world_to_local_normal(mat_inv, (1, 0, 0))
        inward   = world_to_local_normal(mat_inv, (-1, 0, 0))
    else:
        elbow_lp = world_to_local_point(mat_inv, ELBOW_R)
        wrist_lp = world_to_local_point(mat_inv, WRIST_R)
        outward  = world_to_local_normal(mat_inv, (-1, 0, 0))
        inward   = world_to_local_normal(mat_inv, (1, 0, 0))

    if region_name == "base_body_arm_upper":
        if side == "left":
            shoulder_lp = world_to_local_point(mat_inv, (SHOULDER_L_X, 0, 0))
        else:
            shoulder_lp = world_to_local_point(mat_inv, (SHOULDER_R_X, 0, 0))
        bisect_clean(bm, tuple(shoulder_lp), tuple(inward))
        bisect_clean(bm, tuple(elbow_lp), tuple(outward))

    elif region_name == "base_body_arm_lower":
        bisect_clean(bm, tuple(elbow_lp), tuple(inward))
        bisect_clean(bm, tuple(wrist_lp), tuple(outward))

    elif region_name == "base_body_hands":
        bisect_clean(bm, tuple(wrist_lp), tuple(inward))

    ensure_smooth(bm)
    bmesh.update_edit_mesh(half.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    return half


for region_name in ["base_body_arm_upper", "base_body_arm_lower", "base_body_hands"]:
    left_half  = build_arm_half(region_name, "left")
    right_half = build_arm_half(region_name, "right")

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


# ══════════════════════════════════════════════════════════════════════════════
#  9. Clean up
# ══════════════════════════════════════════════════════════════════════════════
bpy.ops.object.select_all(action="DESELECT")
keep_set = set(new_objects)
if armature:
    keep_set.add(armature)
for o in list(bpy.data.objects):
    if o not in keep_set:
        o.select_set(True)
bpy.ops.object.delete(use_global=False)


# ══════════════════════════════════════════════════════════════════════════════
# 10. Export
# ══════════════════════════════════════════════════════════════════════════════
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

print(f"\n{'='*60}")
print(f"Exported → {OUT}")
print(f"  Regions: {len(new_objects)}")
for o in new_objects:
    print(f"    {o.name}: {len(o.data.vertices)} verts")
print(f"{'='*60}")
