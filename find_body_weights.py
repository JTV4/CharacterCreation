"""Find which body GLB has vertex groups with armpit data."""
import bpy

for path in [
    "viewer/public/equipment/base_female.glb",
    "viewer/public/equipment/base_female_with_skin_texture.glb",
    "viewer/public/equipment/game/base_female.glb",
    "viewer/public/models/BaseFemale.glb",
    "rig/CharacterMesh/BaseFemale.glb",
]:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    try:
        bpy.ops.import_scene.gltf(filepath=path)
    except Exception as e:
        print(f"FAIL {path}: {e}")
        continue
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    for m in meshes:
        vgs = [vg.name for vg in m.vertex_groups]
        zone = [v for v in m.data.vertices
                if 0.04 < abs(v.co.x) < 0.30 and 1.20 < v.co.z < 1.50]
        print(f"{path.split('/')[-1]}: vgroups={len(vgs)} armpit_zone={len(zone)} sample={vgs[:4]}")
