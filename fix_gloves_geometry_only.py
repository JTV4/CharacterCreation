"""
fix_gloves_geometry_only.py
============================
Geometry-only fix for shell_gloves.glb.  Weights are NOT touched.

The original proximity-based shell weights are correct enough for the rig.
All previous weight-assignment attempts made deformation worse.

Three targeted geometry passes:

  Pass 1  — Inner palm -Y push (22 mm peak)
    Pushes inner-palm vertices (Y < 0.005) outward in the global -Y direction.
    Fixes palm/inner-hand clipping when arm hangs in idle.
    Wide sigma (7 cm) covers wrist through finger bases.
    Centre per hand: (±0.62, -0.050, 1.390)

  Pass 2  — Dorsal inter-finger web +Y push (12 mm peak)
    Pushes dorsal web-space vertices (Y > -0.01, |X| > 0.65) in +Y.
    Closes the visible gap between pinky and ring fingers (and other webs)
    that appears when viewed from the dorsal side.
    Four Gaussian centres per hand targeting each inter-finger space.

  Pass 3  — Finger-shaft radial inflate (4 mm peak at tips)
    For vertices in the finger shaft zone (|X| > 0.67), pushes each vertex
    radially outward from the finger cross-section centroid in the YZ plane.
    This adds pose-independent clearance in ALL radial directions, addressing
    idle-pose inner-finger clipping without making fingers look massive.
    The small amount (4 mm) is nearly invisible in T-pose.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_gloves_geometry_only.py
"""

import bpy
import bmesh
import math

BASE    = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN  = f"{BASE}/viewer/public/equipment/shell_gloves.glb"
GLB_OUT = GLB_IN

# ── Pass 1: inner palm -Y ─────────────────────────────────────────────────────
PALM_CENTRES = [
    ( 0.62, -0.050, 1.390),
    (-0.62, -0.050, 1.390),
]
PALM_PUSH   = 0.022
PALM_SIGMA  = 0.070
PALM_CUTOFF = 3.5

# ── Pass 2: dorsal web-space +Y ───────────────────────────────────────────────
DORSAL_CENTRES = [
    ( 0.780,  0.010, 1.358),
    ( 0.760,  0.010, 1.370),
    ( 0.740,  0.010, 1.382),
    ( 0.700,  0.010, 1.395),
    (-0.780,  0.010, 1.358),
    (-0.760,  0.010, 1.370),
    (-0.740,  0.010, 1.382),
    (-0.700,  0.010, 1.395),
]
DORSAL_PUSH   = 0.012
DORSAL_SIGMA  = 0.040
DORSAL_CUTOFF = 3.0

# ── Pass 3: finger-shaft radial inflate ───────────────────────────────────────
INFLATE_PEAK   = 0.004   # 4 mm base — subtle, not visible in T-pose
KNUCKLE_X      = 0.67
FINGER_PEAK_X  = 0.77
SLICE_HALF     = 0.012

# ── Pass 4: targeted inner-surface push for middle finger + pinky ─────────────
# Small clipping remains on these two fingers in idle even after the 4mm radial.
# A half-radial push (inner side only) of 9 mm adds clearance just on the
# body-facing side without enlarging the dorsal profile.
# Z-bands from geometry diagnosis:
#   Pinky:  Z < 1.360       Middle: 1.374 ≤ Z < 1.387
INNER_PUSH          = 0.011   # 11 mm extra on inner (below-centroid) surface
INNER_FINGER_SIGMA  = 0.055   # 5.5 cm — broad enough to cover all 4 fingers
INNER_CUTOFF        = 3.0

# Two centres per hand cover ALL four fingers in Z (pinky–ring and middle–index)
# Placed at mid-shaft X ≈ 0.775, palm-facing Y, finger-zone Z centres.
INNER_FINGER_CENTRES = [
    # Left pinky + ring  (Z ≈ 1.343–1.374)
    ( 0.775, -0.070, 1.358),
    # Left middle + index (Z ≈ 1.374–1.410)
    ( 0.775, -0.070, 1.390),
    # Right hand mirrors
    (-0.775, -0.070, 1.358),
    (-0.775, -0.070, 1.390),
]


def gauss(px, py, pz, cx, cy, cz, sig):
    d2 = (px-cx)**2 + (py-cy)**2 + (pz-cz)**2
    return math.exp(-d2 / (2.0 * sig**2))


# ── Load ──────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and o.vertex_groups]
armatures  = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"Loaded: {[o.name for o in mesh_objs]}")

for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    all_verts = list(bm.verts)

    # ── Pass 1: inner palm -Y ─────────────────────────────────────────────────
    palm_cutoff_d = PALM_SIGMA * PALM_CUTOFF
    p1_moved = 0
    for v in all_verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        if y >= 0.005:
            continue
        best_g = 0.0
        for (cx, cy, cz) in PALM_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < palm_cutoff_d:
                best_g = max(best_g, gauss(x, y, z, cx, cy, cz, PALM_SIGMA))
        if best_g < 0.01:
            continue
        v.co.y -= PALM_PUSH * best_g
        p1_moved += 1

    # ── Pass 2: dorsal web +Y ─────────────────────────────────────────────────
    dorsal_cutoff_d = DORSAL_SIGMA * DORSAL_CUTOFF
    p2_moved = 0
    for v in all_verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        if y < -0.01 or abs(x) < 0.65:
            continue
        best_g = 0.0
        for (cx, cy, cz) in DORSAL_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < dorsal_cutoff_d:
                best_g = max(best_g, gauss(x, y, z, cx, cy, cz, DORSAL_SIGMA))
        if best_g < 0.01:
            continue
        v.co.y += DORSAL_PUSH * best_g
        p2_moved += 1

    # ── Pass 3: finger-shaft radial inflate ───────────────────────────────────
    left_f  = [v for v in all_verts if  v.co.x >  KNUCKLE_X]
    right_f = [v for v in all_verts if  v.co.x < -KNUCKLE_X]
    p3_moved = 0
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
            t = max(0.0, min(1.0,
                    (abs_x - KNUCKLE_X) / (FINGER_PEAK_X - KNUCKLE_X)))
            push = INFLATE_PEAK * t
            v.co.y += (dy / mag) * push
            v.co.z += (dz / mag) * push
            p3_moved += 1

    # ── Pass 4: targeted inner-surface push for middle + pinky ───────────────
    inner_cutoff_d = INNER_FINGER_SIGMA * INNER_CUTOFF
    p4_moved = 0
    for side_verts in [left_f, right_f]:
        for v in side_verts:
            x, y, z = v.co.x, v.co.y, v.co.z
            # Compute cross-section centroid for this X slice
            nearby = [u for u in side_verts if abs(u.co.x - x) <= SLICE_HALF]
            if not nearby:
                continue
            ctr_y = sum(u.co.y for u in nearby) / len(nearby)
            # Only push the INNER half (below centroid)
            if y >= ctr_y:
                continue
            best_g = 0.0
            for (cx, cy, cz) in INNER_FINGER_CENTRES:
                d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
                if d < inner_cutoff_d:
                    best_g = max(best_g, gauss(x, y, z, cx, cy, cz,
                                               INNER_FINGER_SIGMA))
            if best_g < 0.01:
                continue
            # Push radially outward (primarily -Y since vertex is below centroid)
            dy = y - ctr_y
            dz = z - (sum(u.co.z for u in nearby) / len(nearby))
            mag = math.sqrt(dy*dy + dz*dz)
            if mag < 0.002:
                continue
            v.co.y += (dy / mag) * INNER_PUSH * best_g
            v.co.z += (dz / mag) * INNER_PUSH * best_g
            p4_moved += 1

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"  [{obj.name}]  P1(palm -Y):{p1_moved}  P2(dorsal +Y):{p2_moved}  "
          f"P3(radial):{p3_moved}  P4(inner mid+pink):{p4_moved}")

# ── Export ────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for o in mesh_objs + armatures:
    o.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\nExporting → {GLB_OUT}")
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
print("Done ✓")
