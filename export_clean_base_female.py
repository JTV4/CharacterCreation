"""
export_clean_base_female.py

Imports viewer/public/models/BaseFemale.glb (armature scale=0.01,
bone positions in cm units) and exports a CLEAN version where:
  - Armature scale = 1.0
  - Bone positions in actual meters (0–1.75m range)
  - Mesh vertices in actual meters
  - Icosphere helper removed

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python export_clean_base_female.py
"""

import bpy, os

SRC  = os.path.abspath("viewer/public/models/BaseFemale.glb")
DEST = os.path.abspath("viewer/public/models/BaseFemaleClean.glb")

# ── 1. Import ────────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
bpy.context.view_layer.update()

# ── 2. Remove the Icosphere bone-shape helper ────────────────────────────────
for obj in list(bpy.data.objects):
    if obj.type == 'MESH' and obj.name.lower().startswith('ico'):
        bpy.data.objects.remove(obj, do_unlink=True)

# ── 3. Find armature + mesh ──────────────────────────────────────────────────
arm_obj  = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
mesh_obj = next(o for o in bpy.data.objects if o.type == 'MESH')

print(f"Armature: {arm_obj.name}  scale={tuple(round(s,4) for s in arm_obj.scale)}")
print(f"Mesh:     {mesh_obj.name}  scale={tuple(round(s,4) for s in mesh_obj.scale)}")

# ── 4. Apply armature scale (bakes 0.01 into bone positions) ─────────────────
bpy.ops.object.select_all(action='DESELECT')
arm_obj.select_set(True)
bpy.context.view_layer.objects.active = arm_obj
bpy.ops.object.transform_apply(scale=True)
print(f"Armature scale after apply: {tuple(round(s,4) for s in arm_obj.scale)}")

# ── 5. Scale mesh object down by 0.01 and apply ───────────────────────────────
# The mesh vertices were stored 100× too large (armature used to compensate).
# Setting scale=0.01 and applying bakes 0.01 into vertex positions.
bpy.ops.object.select_all(action='DESELECT')
mesh_obj.select_set(True)
bpy.context.view_layer.objects.active = mesh_obj
mesh_obj.scale = (0.01, 0.01, 0.01)
bpy.ops.object.transform_apply(scale=True)
bpy.context.view_layer.update()

# ── 6. Verify ─────────────────────────────────────────────────────────────────
verts = mesh_obj.data.vertices
wverts = [mesh_obj.matrix_world @ v.co for v in verts]
zs = [p.z for p in wverts]
xs = [p.x for p in wverts]
print(f"Mesh world X range: {min(xs):.3f} to {max(xs):.3f}  (expect ~-0.84 to 0.84)")
print(f"Mesh world Z range: {min(zs):.3f} to {max(zs):.3f}  (expect ~0 to 1.75)")
print(f"Mesh scale after apply: {tuple(round(s,4) for s in mesh_obj.scale)}")

# ── 7. Export ─────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=DEST,
    export_format="GLB",
    use_selection=False,
    export_apply=True,
    export_yup=True,
    export_skins=True,
    export_animations=False,
)
print(f"\nExported clean file to: {DEST}")
