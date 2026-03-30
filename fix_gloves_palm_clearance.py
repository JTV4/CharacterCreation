"""
fix_gloves_palm_clearance.py
=============================
Fixes three issues on shell_gloves.glb:

1. Inner palm / inner finger clipping (arm at side, idle pose)
   Palm-side vertices (Y < 0) are concave — normals pointed inward during
   extraction, leaving insufficient clearance. Fix: push all inner-palm
   vertices in the global -Y direction (away from the body).

2. Pinky–ring dorsal gap (white skin visible between fingers from above)
   The dorsal web space between pinky and ring is concave on the top surface,
   creating a visible hole when viewed from the dorsal side. Fix: push dorsal
   web vertices in the global +Y direction (outward from hand center).

3. General dorsal finger coverage (middle/ring/index inter-finger gaps)
   Same dorsal-surface concavity across all inter-finger web spaces. Covered
   by a broad dorsal push centred on the finger zone (X > 0.65 / X < -0.65).

Two-pass strategy — no weights changed:
  Pass 1 (-Y):  inner palm + inner finger pads  → 22 mm peak, σ=7 cm
  Pass 2 (+Y):  dorsal finger web spaces         → 12 mm peak, σ=4 cm

Geometry basis (from diagnosis):
  Left hand:  X 0.45–0.85, Y -0.129..+0.097, Z 1.343..1.453
  Right hand: mirror (X negative)
  Pinky tips: Z ≈ 1.343–1.355 (lowest Z)
  Pinky–ring web centre: (±0.78, +0.01, 1.358)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python fix_gloves_palm_clearance.py
"""

import bpy
import bmesh
import math

BASE    = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN  = f"{BASE}/viewer/public/equipment/shell_gloves.glb"
GLB_OUT = GLB_IN

# ── Pass 1: inner palm push (-Y) ──────────────────────────────────────────────
# Centres on each palm, wide sigma to cover wrist → all fingertips.
PALM_CENTRES = [
    ( 0.62, -0.050, 1.390),   # left  palm
    (-0.62, -0.050, 1.390),   # right palm
]
PALM_PUSH   = 0.022   # 22 mm at peak
PALM_SIGMA  = 0.070   # 7 cm — covers palm + all finger inner pads
PALM_CUTOFF = 3.5     # hard cutoff at 3.5σ ≈ 24.5 cm

# ── Pass 2: dorsal web-space push (+Y) ────────────────────────────────────────
# Centred on each inter-finger dorsal web. Tight sigma, small push.
# Four web spaces per hand (pinky–ring, ring–middle, middle–index, index–thumb)
DORSAL_CENTRES = [
    # Left hand web centres  (X, Y, Z)
    ( 0.780,  0.010, 1.358),  # left  pinky–ring
    ( 0.760,  0.010, 1.370),  # left  ring–middle
    ( 0.740,  0.010, 1.382),  # left  middle–index
    ( 0.700,  0.010, 1.395),  # left  index–thumb side
    # Right hand (mirror X)
    (-0.780,  0.010, 1.358),  # right pinky–ring
    (-0.760,  0.010, 1.370),  # right ring–middle
    (-0.740,  0.010, 1.382),  # right middle–index
    (-0.700,  0.010, 1.395),  # right index–thumb side
]
DORSAL_PUSH   = 0.012   # 12 mm at peak
DORSAL_SIGMA  = 0.040   # 4 cm — tight, only the web space
DORSAL_CUTOFF = 3.0     # hard cutoff at 3σ = 12 cm


def gauss(px, py, pz, cx, cy, cz, sig):
    d2 = (px-cx)**2 + (py-cy)**2 + (pz-cz)**2
    return math.exp(-d2 / (2.0 * sig**2))


# ── 1. Load ───────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and len(o.vertex_groups) > 0]
armatures  = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"[gloves_fix] Loaded: {[o.name for o in mesh_objs]}")

for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    # ── Pass 1: inner palm (-Y) ───────────────────────────────────────────────
    palm_moved = 0
    palm_cutoff_d = PALM_SIGMA * PALM_CUTOFF
    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        if y >= 0.005:   # only body-facing (palm) side
            continue
        best_g = 0.0
        for (cx, cy, cz) in PALM_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < palm_cutoff_d:
                best_g = max(best_g, gauss(x, y, z, cx, cy, cz, PALM_SIGMA))
        if best_g < 0.01:
            continue
        v.co.y -= PALM_PUSH * best_g
        palm_moved += 1

    # ── Pass 2: dorsal web space (+Y) ─────────────────────────────────────────
    dorsal_moved = 0
    dorsal_cutoff_d = DORSAL_SIGMA * DORSAL_CUTOFF
    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        # Only dorsal-side vertices (Y > -0.01) in the finger zone (|X| > 0.65)
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
        dorsal_moved += 1

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"  [{obj.name}] Pass 1 (-Y palm): {palm_moved} verts  "
          f"peak={PALM_PUSH*1000:.0f}mm  σ={PALM_SIGMA*100:.0f}cm")
    print(f"  [{obj.name}] Pass 2 (+Y dorsal): {dorsal_moved} verts  "
          f"peak={DORSAL_PUSH*1000:.0f}mm  σ={DORSAL_SIGMA*100:.0f}cm")

# ── 2. Export ─────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objs + armatures:
    obj.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[gloves_fix] Exporting → {GLB_OUT}")
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
print("[gloves_fix] Done ✓")
