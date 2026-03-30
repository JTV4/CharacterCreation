"""Quick check: what vertex groups does base_female.glb have?"""
import bpy
GLB = "viewer/public/equipment/base_female.glb"
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB)
all_objs = list(bpy.data.objects)
print("Objects:", [(o.name, o.type) for o in all_objs])
meshes = [o for o in all_objs if o.type == 'MESH']
for m in meshes:
    print(f"  {m.name}: {len(m.vertex_groups)} vgroups")
    if m.vertex_groups:
        names = sorted(g.name for g in m.vertex_groups)
        print("  Groups:", names[:20])
