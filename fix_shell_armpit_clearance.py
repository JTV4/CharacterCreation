"""
fix_shell_armpit_clearance.py
==============================
Fixes armpit clipping on shell_upper_body.glb by pushing the inner armpit
crease OUTWARD from the body — away from the spine center — using the global
X axis rather than vertex normals.

Why vertex-normal inflation fails at the armpit:
  The inner armpit is concave.  Its vertex normals point INWARD (toward the
  spine), so inflating along normals moves the crease INTO the body, not away.
  This causes visible bumps and pinching when combined with a Gaussian falloff.

Why directional (X-axis) inflation works:
  Pushing the left armpit in +X and the right in -X moves all crease vertices
  away from the spine in a consistent direction.  No normals involved → no
  pinching → smooth, invisible result in T-pose.

Parameters tuned conservatively:
  - PUSH_AMOUNT 0.018 m (18 mm) at the Gaussian peak
  - SIGMA 0.07 m (7 cm) – tight enough to affect only the crease
  - Weights are NOT changed

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python fix_shell_armpit_clearance.py
"""

import bpy
import bmesh
import math

BASE    = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN  = f"{BASE}/viewer/public/equipment/shell_upper_body.glb"
GLB_OUT = GLB_IN

# ── Armpit crease centre (Z-up, metre) ────────────────────────────────────────
# The inner crease sits at |X| ≈ 0.22, Z ≈ 1.37 based on diagnosis.
# We place the Gaussian centre slightly inside the arm (at |X| 0.18) so it
# covers the crease fold without reaching the outer sleeve.
ARMPIT_CENTRES = [
    ( 0.18, 0.01, 1.37),   # left  armpit crease centre
    (-0.18, 0.01, 1.37),   # right armpit crease centre
]

PUSH_AMOUNT = 0.018   # 18 mm push in the ±X direction at the Gaussian peak
SIGMA       = 0.07    # 7 cm half-width — affects inner crease only
CUTOFF_MULT = 3.0     # hard boundary at 3σ = 21 cm


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
print(f"[clearance] Loaded: {[o.name for o in mesh_objs]}")

cutoff_d = SIGMA * CUTOFF_MULT

for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    moved = 0
    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z

        best_g   = 0.0
        best_side = 0  # +1 = left (push +X), -1 = right (push -X)

        for (cx, cy, cz) in ARMPIT_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < cutoff_d:
                g = gauss(x, y, z, cx, cy, cz, SIGMA)
                if g > best_g:
                    best_g    = g
                    best_side = 1 if cx > 0 else -1

        if best_g < 0.01:
            continue

        # Push outward along the global X axis — left arm goes +X, right goes -X.
        # This moves the inner crease AWAY from the spine without touching normals.
        push = PUSH_AMOUNT * best_g * best_side
        v.co.x += push
        moved += 1

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"  [{obj.name}] Pushed {moved} armpit vertices outward "
          f"(peak={PUSH_AMOUNT*1000:.0f}mm, sigma={SIGMA*100:.0f}cm)")

# ── 2. Export ─────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objs + armatures:
    obj.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[clearance] Exporting → {GLB_OUT}")
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
print("[clearance] Done ✓")
