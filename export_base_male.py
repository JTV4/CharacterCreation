"""
export_base_male.py
===================
Builds viewer/public/models/BaseMale.glb — a single Mixamo-skinned male
mesh — by joining the 12 BaseMaleV2 body regions while keeping the
shared armature and vertex weights.

This fills the viewer `male` gender slot (male_v2 uses the modular GLB).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python export_base_male.py
"""

import bpy
import os

SRC = os.path.abspath("viewer/public/models/BaseMaleV2.glb")
DEST = os.path.abspath("viewer/public/models/BaseMale.glb")
DEST_RIG = os.path.abspath("rig/CharacterMesh/BaseMale.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC)
bpy.context.view_layer.update()

armature = next(o for o in bpy.data.objects if o.type == "ARMATURE")
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
print(f"Loaded {len(meshes)} region meshes + armature '{armature.name}' "
      f"({len(armature.data.bones)} bones)")

bpy.ops.object.select_all(action="DESELECT")
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.join()

joined = bpy.context.active_object
joined.name = "BaseMale"
joined.data.name = "BaseMale"

# Drop empty orphan mesh datablocks from the join
for m in list(bpy.data.meshes):
    if m.users == 0:
        bpy.data.meshes.remove(m)

wverts = [joined.matrix_world @ v.co for v in joined.data.vertices]
zs = [p.z for p in wverts]
xs = [p.x for p in wverts]
print(f"Joined mesh: {len(joined.data.vertices)} verts, "
      f"{len(joined.data.polygons)} faces")
print(f"  world X: {min(xs):.3f}..{max(xs):.3f}")
print(f"  world Z: {min(zs):.3f}..{max(zs):.3f}")
print(f"  vertex groups: {len(joined.vertex_groups)}")

bpy.ops.object.select_all(action="DESELECT")
joined.select_set(True)
armature.select_set(True)
bpy.context.view_layer.objects.active = armature

for dest in (DEST, DEST_RIG):
    bpy.ops.export_scene.gltf(
        filepath=dest,
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
    print(f"Exported → {dest}")
