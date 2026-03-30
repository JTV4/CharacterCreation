"""
fix_gloves_weights_and_inflate.py  (v2 — explicit positional weight assignment)
==================================================================================
Root-cause fix for glove finger clipping AND deformation quality.

PROBLEM:
  Glove finger weights are completely scrambled:
    Middle finger zone:  thumb_03_L 20%,  index_01_L 14%,  middle_02_L only 7%
    Ring finger zone:    index_03_L 13%,  ring_01_L only 8%
  Wrong bones drive each finger → bad deformation AND clipping in idle.

SOLUTION — two passes:

  Pass 1: Positional weight assignment (hand/finger zone, |X| > 0.60)
    Each vertex is assigned correct bone weights purely from its (X, Z) position:
      • Z-band   → which finger  (pinky / ring / middle / index)
      • |X| ramp → which segment (_01=base, _02=middle, _03=tip)
    Palm zone (|X| 0.60–0.67): blend hand_L / lowerarm_L by X
    Only the finger/hand region is touched; thumb zone and forearm are left alone.

  Pass 2: Radial inflate — 6 mm at fingertips (|X| > 0.77), tapering to 0 at knuckle
    Pushes each vertex outward from the finger cross-section centroid (YZ plane).
    Adds minimal, pose-independent geometric clearance without bulging.

Finger Z-bands (from geometry diagnosis of shell_gloves.glb):
    Pinky:  Z < 1.360
    Ring:   1.360 ≤ Z < 1.374
    Middle: 1.374 ≤ Z < 1.387
    Index:  1.387 ≤ Z < 1.410  (above this = wrist)

Segment X-ranges (finger tips extend to X ≈ 0.85):
    _01 (base):   |X| 0.67 – 0.74   (linear blend into _02)
    _02 (middle): |X| 0.74 – 0.81   (linear blend into _03)
    _03 (tip):    |X| > 0.81

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_gloves_weights_and_inflate.py
"""

import bpy
import bmesh
import math

BASE   = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN = f"{BASE}/viewer/public/equipment/shell_gloves.glb"
GLB_OUT = GLB_IN

# ── Finger Z-band boundaries ──────────────────────────────────────────────────
Z_PINKY_MAX  = 1.360
Z_RING_MAX   = 1.374
Z_MIDDLE_MAX = 1.387
Z_INDEX_MAX  = 1.410   # above this = wrist/forearm, don't touch

# ── Segment X boundaries (using |X|) ─────────────────────────────────────────
X_FINGER_START = 0.67   # inner edge of finger shaft (knuckle)
X_SEG01_END    = 0.74   # _01/_02 blend centre
X_SEG02_END    = 0.81   # _02/_03 blend centre

# ── Palm zone ─────────────────────────────────────────────────────────────────
X_PALM_START   = 0.60   # inner edge of palm zone (lowerarm dominated)
X_PALM_END     = X_FINGER_START  # outer edge = knuckle


def finger_from_z(z):
    """Return finger name (None if outside known bands)."""
    if z < Z_PINKY_MAX:
        return 'pinky'
    elif z < Z_RING_MAX:
        return 'ring'
    elif z < Z_MIDDLE_MAX:
        return 'middle'
    elif z < Z_INDEX_MAX:
        return 'index'
    return None   # wrist/forearm area — skip


def segment_weights(abs_x):
    """Return (w01, w02, w03) based on finger X position."""
    if abs_x <= X_SEG01_END:
        t = max(0.0, min(1.0, (abs_x - X_FINGER_START) / (X_SEG01_END - X_FINGER_START)))
        return (1.0 - t, t, 0.0)
    else:
        t = max(0.0, min(1.0, (abs_x - X_SEG01_END) / (X_SEG02_END - X_SEG01_END)))
        return (0.0, 1.0 - t, t)


# ── Load ──────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_IN)

glove_obj = next(o for o in bpy.data.objects
                 if o.type == 'MESH' and o.vertex_groups)
armatures  = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"[fix] Loaded: {glove_obj.name}  "
      f"({len(glove_obj.data.vertices)} verts, "
      f"{len(glove_obj.vertex_groups)} vgroups)")

# Collect all vertex group names that exist in the glove
vg_by_name = {g.name: g for g in glove_obj.vertex_groups}

# Bones we will be writing — ensure they all exist
ALL_FINGER_BONES = (
    ['index_01_L', 'index_02_L', 'index_03_L',
     'middle_01_L', 'middle_02_L', 'middle_03_L',
     'ring_01_L',   'ring_02_L',   'ring_03_L',
     'pinky_01_L',  'pinky_02_L',  'pinky_03_L',
     'hand_L', 'lowerarm_L'] +
    ['index_01_R', 'index_02_R', 'index_03_R',
     'middle_01_R', 'middle_02_R', 'middle_03_R',
     'ring_01_R',   'ring_02_R',   'ring_03_R',
     'pinky_01_R',  'pinky_02_R',  'pinky_03_R',
     'hand_R', 'lowerarm_R']
)
for bname in ALL_FINGER_BONES:
    if bname not in vg_by_name:
        vg = glove_obj.vertex_groups.new(name=bname)
        vg_by_name[bname] = vg
        print(f"  Created missing vgroup: {bname}")

# Bones whose old weights we will CLEAR in the modified zone
# (prevent old wrong weights from lingering)
CLEAR_BONES = [b for b in vg_by_name if any(
    k in b for k in ['index', 'middle', 'ring', 'pinky',
                      'thumb', 'hand_', 'lowerarm']
)]

# ── Pass 1 — Positional weight assignment ─────────────────────────────────────
mesh_data = glove_obj.data
modified = 0
skipped  = 0

for v in mesh_data.vertices:
    x, y, z = v.co.x, v.co.y, v.co.z
    abs_x = abs(x)
    side  = '_L' if x > 0 else '_R'
    vi    = v.index

    if abs_x >= X_FINGER_START:
        # ── Finger shaft zone ────────────────────────────────────────────
        fname = finger_from_z(z)
        if fname is None:
            skipped += 1
            continue

        w01, w02, w03 = segment_weights(abs_x)

        b01 = f'{fname}_01{side}'
        b02 = f'{fname}_02{side}'
        b03 = f'{fname}_03{side}'

        # Clear all hand/finger old weights for this vertex
        for bname in CLEAR_BONES:
            if bname in vg_by_name:
                vg_by_name[bname].remove([vi])

        # Assign new clean weights
        if w01 > 0.001:
            vg_by_name[b01].add([vi], w01, 'REPLACE')
        if w02 > 0.001:
            vg_by_name[b02].add([vi], w02, 'REPLACE')
        if w03 > 0.001:
            vg_by_name[b03].add([vi], w03, 'REPLACE')

        modified += 1

    elif abs_x >= X_PALM_START:
        # ── Palm zone — blend hand_L / lowerarm_L ────────────────────────
        t      = (abs_x - X_PALM_START) / (X_PALM_END - X_PALM_START)
        w_hand = max(0.0, min(1.0, t))          # 0 at wrist, 1 at knuckle
        w_fore = 1.0 - w_hand

        bhand = f'hand{side}'
        bfore = f'lowerarm{side}'

        for bname in CLEAR_BONES:
            if bname in vg_by_name:
                vg_by_name[bname].remove([vi])

        vg_by_name[bhand].add([vi], w_hand, 'REPLACE')
        if w_fore > 0.001:
            vg_by_name[bfore].add([vi], w_fore, 'REPLACE')

        modified += 1
    else:
        skipped += 1

print(f"[fix] Assigned weights: {modified} verts modified, {skipped} skipped")

# ── Verify: middle finger zone ────────────────────────────────────────────────
print("\n[verify] Middle finger (X>0.70, Z 1.374-1.387) after fix:")
vg_idx_map = {g.index: g.name for g in glove_obj.vertex_groups}
bone_w = {}
mid_count = 0
for v in mesh_data.vertices:
    if v.co.x > 0.70 and 1.374 <= v.co.z < 1.387:
        mid_count += 1
        for g in v.groups:
            bn = vg_idx_map.get(g.group, '?')
            bone_w[bn] = bone_w.get(bn, 0.0) + g.weight
total = sum(bone_w.values())
ranked = sorted(bone_w.items(), key=lambda kv: -kv[1])[:6]
print(f"  ({mid_count} verts)")
for bone, w in ranked:
    print(f"    {bone:<30s} {100*w/total:5.1f}%")

# ── Pass 2 — Radial inflate (6 mm peak) ──────────────────────────────────────
INFLATE_PEAK  = 0.006
KNUCKLE_X     = 0.67
FINGER_PEAK_X = 0.77
SLICE_HALF    = 0.012

bm = bmesh.new()
bm.from_mesh(mesh_data)
bm.verts.ensure_lookup_table()

all_bm = list(bm.verts)
left_f  = [v for v in all_bm if  v.co.x >  KNUCKLE_X]
right_f = [v for v in all_bm if  v.co.x < -KNUCKLE_X]

inflate_moved = 0
for side_verts in [left_f, right_f]:
    for v in side_verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        nearby = [u for u in side_verts if abs(u.co.x - x) <= SLICE_HALF]
        if not nearby:
            continue
        ctr_y = sum(u.co.y for u in nearby) / len(nearby)
        ctr_z = sum(u.co.z for u in nearby) / len(nearby)
        dy = y - ctr_y
        dz = z - ctr_z
        mag = math.sqrt(dy*dy + dz*dz)
        if mag < 0.002:
            continue
        abs_x = abs(x)
        t = max(0.0, min(1.0, (abs_x - KNUCKLE_X) / (FINGER_PEAK_X - KNUCKLE_X)))
        push = INFLATE_PEAK * t
        v.co.y += (dy / mag) * push
        v.co.z += (dz / mag) * push
        inflate_moved += 1

bm.normal_update()
bm.to_mesh(mesh_data)
bm.free()
mesh_data.update()
print(f"\n[inflate] Radially inflated {inflate_moved} verts "
      f"(peak={INFLATE_PEAK*1000:.0f}mm, pose-independent)")

# ── Export ────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for o in [glove_obj] + armatures:
    o.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[export] → {GLB_OUT}")
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format='GLB',
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_skins=True,
    export_all_influences=True,
    export_def_bones=True,
    export_animations=False,
    export_materials='EXPORT',
)
print("[export] Done ✓")
