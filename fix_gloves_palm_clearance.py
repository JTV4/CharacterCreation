"""
fix_gloves_palm_clearance.py
=============================
Fixes two issues on shell_gloves.glb:

1. Inner palm clipping when arm hangs at side
   The palm-side vertices (Y < 0) are concave. Their normals pointed inward
   during normal-offset extraction, leaving the inner palm too close to the
   hand surface. Fix: push inner palm vertices outward in the -Y direction
   (away from the dorsum) using a Gaussian falloff centred on each palm.

2. Middle finger inner-surface gap
   Same concave-inflation issue on the finger pads. Covered by the same
   palm push since it extends to the fingertips.

Strategy: directional push in global -Y for all inner-palm vertices (Y < 0)
on both hands. Weights untouched.

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

# ── Palm centres (Z-up, metres) ───────────────────────────────────────────────
# Left hand palm:  X ≈ +0.58, Y ≈ -0.05, Z ≈ 1.40
# Right hand palm: X ≈ -0.58, Y ≈ -0.05, Z ≈ 1.40
# Wide sigma covers wrist-to-fingertip range (~15 cm across the hand).
PALM_CENTRES = [
    ( 0.60, -0.045, 1.40),   # left  hand inner palm
    (-0.60, -0.045, 1.40),   # right hand inner palm
]

PUSH_AMOUNT = 0.014   # 14 mm push in -Y at peak (palm has less clearance than torso)
SIGMA       = 0.06    # 6 cm half-width — covers palm + finger inner surfaces
CUTOFF_MULT = 3.5     # hard cutoff at 3.5σ ≈ 21 cm (reaches all fingers)


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

cutoff_d = SIGMA * CUTOFF_MULT

for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    moved = 0
    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z

        # Only push inner-palm-side vertices (Y < 0 means palm/body-facing side)
        if y >= 0:
            continue

        best_g = 0.0
        for (cx, cy, cz) in PALM_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < cutoff_d:
                g = gauss(x, y, z, cx, cy, cz, SIGMA)
                best_g = max(best_g, g)

        if best_g < 0.01:
            continue

        # Push outward in -Y (away from dorsum, out of body contact zone).
        v.co.y -= PUSH_AMOUNT * best_g
        moved += 1

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"  [{obj.name}] Pushed {moved} inner-palm vertices in -Y "
          f"(peak={PUSH_AMOUNT*1000:.0f}mm, sigma={SIGMA*100:.0f}cm)")

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
