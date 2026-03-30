"""
diagnose_upperbody_v1.py
Inspect UpperbodyTestV1.glb armpit vertex weights.
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python diagnose_upperbody_v1.py
"""
import bpy

GLB = "viewer/public/equipment/Female/Upperbody/UpperbodyTestV1.glb"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=GLB)

mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH' and len(o.vertex_groups) > 0]

for m in mesh_objs:
    vgs = {vg.index: vg.name for vg in m.vertex_groups}
    xs = [v.co.x for v in m.data.vertices]
    ys = [v.co.y for v in m.data.vertices]
    zs = [v.co.z for v in m.data.vertices]
    print(f"MESH: {m.name}  verts={len(m.data.vertices)}  vgroups={len(vgs)}")
    print(f"  Bounds X:{min(xs):.3f}..{max(xs):.3f}  Y:{min(ys):.3f}..{max(ys):.3f}  Z:{min(zs):.3f}..{max(zs):.3f}")
    print(f"  Vertex groups: {list(vgs.values())}")

    # Armpit zone
    armpit_verts = [v for v in m.data.vertices
                    if 0.05 < abs(v.co.x) < 0.35 and 1.20 < v.co.z < 1.50]
    print(f"\n  Armpit-zone vertices: {len(armpit_verts)}")

    arm_kw = ['arm','shoulder','clavicle','Arm','Shoulder','Clavicle']
    torso_kw = ['Spine','spine','Hips','hips','pelvis','Neck','neck']

    results = []
    for v in armpit_verts:
        w = {vgs[g.group]: round(g.weight, 4) for g in v.groups if g.group in vgs and g.weight > 0.01}
        arm_total   = sum(val for k, val in w.items() if any(kw.lower() in k.lower() for kw in arm_kw))
        torso_total = sum(val for k, val in w.items() if any(kw.lower() in k.lower() for kw in torso_kw))
        results.append({
            "co": (round(v.co.x, 3), round(v.co.y, 3), round(v.co.z, 3)),
            "arm": arm_total, "torso": torso_total, "w": w
        })

    results.sort(key=lambda r: r["arm"], reverse=True)
    print("  Top 25 by arm weight:")
    for r in results[:25]:
        print(f"    co={r['co']}  arm={r['arm']:.3f}  torso={r['torso']:.3f}  {r['w']}")
