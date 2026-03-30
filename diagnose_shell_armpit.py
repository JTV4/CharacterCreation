"""
diagnose_shell_armpit.py
Inspect shell_upper_body.glb armpit vertex weights.
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python diagnose_shell_armpit.py
"""
import bpy

GLB = "viewer/public/equipment/shell_upper_body.glb"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=GLB)

m = next(o for o in bpy.data.objects if o.type == 'MESH' and len(o.vertex_groups) > 0)
vgs = {vg.index: vg.name for vg in m.vertex_groups}

xs = [v.co.x for v in m.data.vertices]
ys = [v.co.y for v in m.data.vertices]
zs = [v.co.z for v in m.data.vertices]
print(f"MESH: {m.name}  verts={len(m.data.vertices)}")
print(f"  Bounds X:{min(xs):.3f}..{max(xs):.3f}  Y:{min(ys):.3f}..{max(ys):.3f}  Z:{min(zs):.3f}..{max(zs):.3f}")
print(f"  Vertex groups: {list(vgs.values())}")

arm_kw   = ['upperarm', 'clavicle']
torso_kw = ['spine', 'pelvis']

# Broad armpit scan to find the real crease coordinates
armpit_verts = [v for v in m.data.vertices
                if 0.04 < abs(v.co.x) < 0.40 and 1.20 < v.co.z < 1.55]
print(f"\n  Armpit scan zone (|X| 0.04-0.40, Z 1.20-1.55): {len(armpit_verts)} verts")

results = []
for v in armpit_verts:
    w = {vgs[g.group]: round(g.weight, 4) for g in v.groups
         if g.group in vgs and g.weight > 0.005}
    arm   = sum(val for k, val in w.items() if any(kw in k for kw in arm_kw))
    torso = sum(val for k, val in w.items() if any(kw in k for kw in torso_kw))
    results.append({
        "co": (round(v.co.x,3), round(v.co.y,3), round(v.co.z,3)),
        "arm": arm, "torso": torso, "w": w
    })

# Sort by arm weight descending to find worst vertices
results.sort(key=lambda r: r["arm"], reverse=True)
print("\n  Top 30 MOST arm-weighted (no/low torso = clipping risk):")
for r in results[:30]:
    print(f"    co={r['co']}  arm={r['arm']:.3f}  torso={r['torso']:.3f}  {r['w']}")

if results:
    avg_arm   = sum(r["arm"]   for r in results) / len(results)
    avg_torso = sum(r["torso"] for r in results) / len(results)
    zero_torso = sum(1 for r in results if r["torso"] < 0.01)
    print(f"\n  Zone average: arm={avg_arm:.3f}  torso={avg_torso:.3f}")
    print(f"  Vertices with zero torso weight: {zero_torso} / {len(results)}")
