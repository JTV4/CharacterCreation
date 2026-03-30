"""
create_morph_targets.py
=======================
Adds a 'groin_kick' morph target (blend shape) to shell_lower_body.glb.

How it works
------------
At morph influence = 0 (T-pose) the mesh is completely unchanged.
At morph influence = 1 (73 deg thigh kick) the inner groin vertices are pushed
forward/outward by PUSH_AMOUNT along their rest-pose normals, using a Gaussian
falloff.  After the skinning deformation is applied on top, the corrected
vertices stay outside the body surface.

The morph is driven at runtime by the thigh bone X-rotation in Three.js --
no geometry change to the base mesh, no weight changes.

Confirmed target zone from mesh diagnostic:
  inner crotch: Z=[0.78, 0.94], |X|<0.07, Y~0.03-0.07 (front-facing)
  dominant bones: thigh_L ~50%, thigh_R ~50%, pelvis ~2%

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python create_morph_targets.py
"""

import bpy
import math

GLB_IN  = (
    "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
    "/viewer/public/equipment/shell_lower_body.glb"
)
GLB_OUT = GLB_IN

# Target zone (confirmed from diagnostic)
GROIN_CENTRE   = (0.0, 0.04, 0.85)
FALLOFF_RADIUS = 0.055               # 1-sigma, 5.5 cm
CUTOFF_MULT    = 2.0                 # hard cutoff at 11 cm
X_MAX          = 0.07                # inner thigh only

PUSH_AMOUNT    = 0.035               # 35 mm at Gaussian peak

# ── 1. Import ─────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
print(f"[morph] Importing {GLB_IN}")
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and o.name != 'Icosphere']
armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"[morph] Meshes: {[o.name for o in mesh_objs]}")
print(f"[morph] Armatures: {[o.name for o in armatures]}")

cx, cy, cz = GROIN_CENTRE
cutoff = FALLOFF_RADIUS * CUTOFF_MULT

for obj in mesh_objs:
    bpy.context.view_layer.objects.active = obj
    mesh = obj.data

    # Basis key must exist before adding corrective keys
    if not mesh.shape_keys:
        obj.shape_key_add(name='Basis', from_mix=False)
        print(f"  [{obj.name}] Added Basis shape key")

    sk = obj.shape_key_add(name='groin_kick', from_mix=False)
    sk.value = 0.0
    sk.slider_min = 0.0
    sk.slider_max = 1.0

    moved = 0
    for i, v in enumerate(mesh.vertices):
        if abs(v.co.x) > X_MAX:
            continue
        dx = v.co.x - cx
        dy = v.co.y - cy
        dz = v.co.z - cz
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist >= cutoff:
            continue

        gauss = math.exp(-(dist**2) / (2.0 * FALLOFF_RADIUS**2))

        # Push direction: vertex normal, clamped to have positive Y
        # so we always push forward/outward, never into the body.
        nx, ny, nz = v.normal.x, v.normal.y, v.normal.z
        if ny < 0.1:
            ny = 0.1
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length < 0.001:
            nx, ny, nz = 0.0, 1.0, 0.0
        else:
            nx, ny, nz = nx/length, ny/length, nz/length

        amount = PUSH_AMOUNT * gauss
        # shape key stores absolute position (Basis position + delta)
        sk.data[i].co.x = v.co.x + nx * amount
        sk.data[i].co.y = v.co.y + ny * amount
        sk.data[i].co.z = v.co.z + nz * amount
        moved += 1

    print(f"  [{obj.name}] 'groin_kick': {moved} verts affected "
          f"(peak={PUSH_AMOUNT*1000:.0f}mm, sigma={FALLOFF_RADIUS*100:.0f}cm)")

# ── 2. Export: select only mesh + armature (exclude Icosphere) ────────────────
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objs + armatures:
    obj.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[morph] Exporting to {GLB_OUT} ...")
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format='GLB',
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_skins=True,
    export_morph=True,
    export_morph_normal=False,
    export_morph_tangent=False,
    export_all_influences=True,
    export_def_bones=True,
    export_animations=False,
    export_materials='EXPORT',
)
print("[morph] Done ✓")
