"""
verify_armpit_fix.py
Check inner armpit crease (|X| < 0.22) after the fix.
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python verify_armpit_fix.py
"""
import bpy

GLB = "viewer/public/equipment/Female/Upperbody/UpperbodyTestV1.glb"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=GLB)

m = next(o for o in bpy.data.objects if o.type == 'MESH' and len(o.vertex_groups) > 0)
vgs = {vg.index: vg.name for vg in m.vertex_groups}

arm_kw   = ['upperarm','clavicle']
torso_kw = ['spine','pelvis']

# Inner crease: |X| < 0.22, Z 1.25-1.50 — the fold that clips
inner_verts = [v for v in m.data.vertices
               if abs(v.co.x) < 0.22 and 1.25 < v.co.z < 1.50]

print(f"Inner crease vertices (|X|<0.22, Z 1.25-1.50): {len(inner_verts)}")
results = []
for v in inner_verts:
    w = {vgs[g.group]: round(g.weight, 4) for g in v.groups
         if g.group in vgs and g.weight > 0.005}
    arm   = sum(val for k,val in w.items() if any(kw in k for kw in arm_kw))
    torso = sum(val for k,val in w.items() if any(kw in k for kw in torso_kw))
    results.append({"co": (round(v.co.x,3), round(v.co.y,3), round(v.co.z,3)),
                    "arm": arm, "torso": torso, "w": w})

results.sort(key=lambda r: r["arm"], reverse=True)
print("Showing top 30 by arm weight (most problematic):")
for r in results[:30]:
    print(f"  co={r['co']}  arm={r['arm']:.3f}  torso={r['torso']:.3f}  {r['w']}")

if results:
    avg_arm   = sum(r["arm"]   for r in results) / len(results)
    avg_torso = sum(r["torso"] for r in results) / len(results)
    print(f"\nInner crease averages: arm={avg_arm:.3f}  torso={avg_torso:.3f}  over {len(results)} verts")
    print(f"(Before fix these were arm≈1.0, torso≈0.0)")
