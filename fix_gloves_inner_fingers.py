"""
fix_gloves_inner_fingers.py
============================
Targeted fix for inner finger (palm-side) clipping in idle pose.

The broad palm Gaussian in fix_gloves_palm_clearance.py falls off too fast
to effectively push the inner finger shafts (which are ~15 cm from the palm
centre). This script adds a second dedicated inner-finger push:

  - Target: all inner-finger vertices (Y < 0, |X| > 0.68) on both hands
  - Push:   global -Y direction (away from body), 16 mm flat at the inner
            finger zone, ramping down to 0 at X = 0.68 (knuckle boundary)
  - Per-finger centres (left hand): one per finger with tight sigma (3 cm)
    so each finger gets targeted clearance without bulging its neighbours.

Applied ON TOP of the current (already-fixed) glb — additive push.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_gloves_inner_fingers.py
"""

import bpy
import bmesh
import math

BASE    = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN  = f"{BASE}/viewer/public/equipment/shell_gloves.glb"
GLB_OUT = GLB_IN

# Inner-finger centres: one per finger per hand.
# Placed at the mid-shaft, Y on the inner (palm) face, Z at each finger's band.
# Geometry from diagnosis:
#   Pinky:  Z ≈ 1.348  (lowest Z)
#   Ring:   Z ≈ 1.362
#   Middle: Z ≈ 1.374  (clipping finger reported by user)
#   Index:  Z ≈ 1.386
#   Thumb:  Z ≈ 1.400  (approx, thumb is shorter/inner)
FINGER_CENTRES = [
    # Left hand  (X > 0)
    ( 0.800, -0.070, 1.348),   # pinky
    ( 0.790, -0.070, 1.362),   # ring
    ( 0.785, -0.075, 1.374),   # middle  ← user-reported
    ( 0.770, -0.070, 1.386),   # index
    ( 0.720, -0.055, 1.400),   # thumb
    # Right hand (X < 0, mirror)
    (-0.800, -0.070, 1.348),
    (-0.790, -0.070, 1.362),
    (-0.785, -0.075, 1.374),
    (-0.770, -0.070, 1.386),
    (-0.720, -0.055, 1.400),
]

PUSH_AMOUNT = 0.016   # 16 mm at peak
SIGMA       = 0.038   # 3.8 cm — covers each finger shaft without bleeding wide
CUTOFF      = 3.0     # hard cutoff at 3σ ≈ 11.4 cm


def gauss(px, py, pz, cx, cy, cz, sig):
    d2 = (px-cx)**2 + (py-cy)**2 + (pz-cz)**2
    return math.exp(-d2 / (2.0 * sig**2))


# ── Load ──────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and len(o.vertex_groups) > 0]
armatures  = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"[inner_fingers] Loaded: {[o.name for o in mesh_objs]}")

cutoff_d = SIGMA * CUTOFF

for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    moved = 0
    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z

        # Only inner (palm-facing) vertices in the finger shaft zone
        if y >= 0.0 or abs(x) < 0.68:
            continue

        best_g = 0.0
        for (cx, cy, cz) in FINGER_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < cutoff_d:
                best_g = max(best_g, gauss(x, y, z, cx, cy, cz, SIGMA))

        if best_g < 0.01:
            continue

        v.co.y -= PUSH_AMOUNT * best_g
        moved += 1

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"  [{obj.name}] Pushed {moved} inner-finger vertices in -Y "
          f"(peak={PUSH_AMOUNT*1000:.0f}mm, sigma={SIGMA*100:.1f}cm)")

# ── Export ────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objs + armatures:
    obj.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[inner_fingers] Exporting → {GLB_OUT}")
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
print("[inner_fingers] Done ✓")
