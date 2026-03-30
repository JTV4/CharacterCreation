"""
diagnose_glove_weights.py
Checks which bones drive the finger vertices in shell_gloves.glb.
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python diagnose_glove_weights.py
"""
import bpy, math

GLB = "viewer/public/equipment/shell_gloves.glb"
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB)
obj = next(o for o in bpy.data.objects if o.type == 'MESH' and len(o.vertex_groups) > 0)

vg_names = {g.index: g.name for g in obj.vertex_groups}
print("Vertex groups:", sorted(vg_names.values()))

verts = list(obj.data.vertices)

# Left hand finger zones by Z (from diagnosis: fingers spread Z 1.343..1.453)
# Pinky Z<1.358, Ring 1.358-1.372, Middle 1.372-1.385, Index>1.385, Thumb>1.40
finger_zones = {
    'Pinky':  lambda x,y,z: x > 0.70 and z < 1.360,
    'Ring':   lambda x,y,z: x > 0.70 and 1.360 <= z < 1.374,
    'Middle': lambda x,y,z: x > 0.70 and 1.374 <= z < 1.387,
    'Index':  lambda x,y,z: x > 0.70 and z >= 1.387,
}

print("\nLeft hand finger weight breakdown (top 4 bones per zone):")
for fname, pred in finger_zones.items():
    fverts = [v for v in verts if pred(v.co.x, v.co.y, v.co.z)]
    if not fverts:
        print(f"  {fname}: NO VERTS FOUND")
        continue
    # Accumulate weight per bone
    bone_w = {}
    for v in fverts:
        for g in v.groups:
            name = vg_names.get(g.group, f'grp{g.group}')
            bone_w[name] = bone_w.get(name, 0.0) + g.weight
    total = sum(bone_w.values())
    ranked = sorted(bone_w.items(), key=lambda kv: -kv[1])[:6]
    print(f"\n  {fname} ({len(fverts)} verts):")
    for bone, w in ranked:
        pct = 100.0 * w / total if total > 0 else 0
        print(f"    {bone:<35s} {pct:5.1f}%")

# Also show the palm zone
palm_verts = [v for v in verts if 0.45 < v.co.x < 0.70 and v.co.y < 0.0]
if palm_verts:
    bone_w = {}
    for v in palm_verts:
        for g in v.groups:
            name = vg_names.get(g.group, f'grp{g.group}')
            bone_w[name] = bone_w.get(name, 0.0) + g.weight
    total = sum(bone_w.values())
    ranked = sorted(bone_w.items(), key=lambda kv: -kv[1])[:6]
    print(f"\n  Palm inner ({len(palm_verts)} verts):")
    for bone, w in ranked:
        pct = 100.0 * w / total if total > 0 else 0
        print(f"    {bone:<35s} {pct:5.1f}%")
