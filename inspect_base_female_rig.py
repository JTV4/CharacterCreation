"""Inspect rig/CharacterMesh/BaseFemale.glb bounds and armpit weights."""
import bpy, math

GLB = "rig/CharacterMesh/BaseFemale.glb"
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB)

for m in bpy.data.objects:
    if m.type != 'MESH' or not m.vertex_groups:
        continue
    vgs = {vg.index: vg.name for vg in m.vertex_groups}
    xs = [v.co.x for v in m.data.vertices]
    ys = [v.co.y for v in m.data.vertices]
    zs = [v.co.z for v in m.data.vertices]
    print(f"Mesh: {m.name}  verts={len(m.data.vertices)}")
    print(f"  Bounds X:{min(xs):.3f}..{max(xs):.3f}  Y:{min(ys):.3f}..{max(ys):.3f}  Z:{min(zs):.3f}..{max(zs):.3f}")

    # Try different armpit zones to find where arm/torso blend
    for x_thresh, z_lo, z_hi in [
        (0.3, 1.20, 1.50),    # Z-up, original range
        (0.3, 0.50, 0.80),    # Z-up, shifted if character is at origin
        (30,  120,  150),     # cm scale
        (0.3, -0.30, 0.30),   # Y-up, armpit might be in Y axis
    ]:
        zone = [v for v in m.data.vertices
                if 0.04 < abs(v.co.x) < x_thresh and z_lo < v.co.z < z_hi]
        if zone:
            print(f"  Zone |X|<{x_thresh} Z {z_lo}-{z_hi}: {len(zone)} verts")
            arm_kw = ['Arm','arm','shoulder','Shoulder','clavicle','Clavicle']
            torso_kw = ['Spine','spine','Hips','hips']
            results = []
            for v in zone:
                w = {vgs[g.group]: round(g.weight,4) for g in v.groups if g.weight > 0.01}
                arm   = sum(val for k,val in w.items() if any(kw in k for kw in arm_kw))
                torso = sum(val for k,val in w.items() if any(kw in k for kw in torso_kw))
                results.append({"co":(round(v.co.x,3),round(v.co.y,3),round(v.co.z,3)),
                                "arm":arm,"torso":torso,"w":w})
            results.sort(key=lambda r:r["arm"],reverse=True)
            print(f"  Top 8 by arm weight:")
            for r in results[:8]:
                print(f"    co={r['co']}  arm={r['arm']:.3f}  torso={r['torso']:.3f}  {r['w']}")
            if results:
                avg_arm=sum(r["arm"] for r in results)/len(results)
                avg_torso=sum(r["torso"] for r in results)/len(results)
                zero_torso=sum(1 for r in results if r["torso"]<0.01)
                print(f"  Avg arm={avg_arm:.3f} torso={avg_torso:.3f}  zero_torso={zero_torso}")
            break
