"""
diagnose_base_female_vgroups.py
List all vertex groups (bone names) in base_female.glb and their vert counts.
"""
import bpy

GLB = "viewer/public/equipment/base_female.glb"
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=GLB)

mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.vertex_groups)
print(f"Mesh: {mesh.name}, verts: {len(mesh.data.vertices)}")
print("Vertex groups (bone names):")
for vg in mesh.vertex_groups:
    count = sum(1 for v in mesh.data.vertices
                if any(g.group == vg.index for g in v.groups))
    print(f"  [{vg.index:3d}] {vg.name:<35} {count} verts")
