"""
diagnose_armpit.py  — inspect shell_upper_body armpit vertex weights
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python diagnose_armpit.py
"""
import bpy

GLB = ("/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
       "/viewer/public/equipment/shell_upper_body.glb")

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=GLB)

# Get the real shell mesh (not Icosphere)
m = next(o for o in bpy.data.objects
         if o.type == 'MESH' and len(o.vertex_groups) > 0)
md = m.data
vgs = {vg.index: vg.name for vg in m.vertex_groups}
print(f"\nUsing mesh: {m.name}  ({len(md.vertices)} verts, {len(vgs)} vgroups)")

xs=[v.co.x for v in md.vertices]; ys=[v.co.y for v in md.vertices]; zs=[v.co.z for v in md.vertices]
print(f"Bounds X:{min(xs):.3f}..{max(xs):.3f} Y:{min(ys):.3f}..{max(ys):.3f} Z:{min(zs):.3f}..{max(zs):.3f}")

ARM_BONES   = {"upperarm_L","upperarm_R","clavicle_L","clavicle_R"}
TORSO_BONES = {"spine_01","spine_02","spine_03","pelvis"}

results = []
for v in md.vertices:
    x, y, z = v.co.x, v.co.y, v.co.z
    weights = {}
    for g in v.groups:
        if g.group in vgs and g.weight > 0.005:
            weights[vgs[g.group]] = round(g.weight, 4)

    arm_w   = sum(w for b, w in weights.items() if b in ARM_BONES)
    torso_w = sum(w for b, w in weights.items() if b in TORSO_BONES)

    # Armpit: meaningful blend of arm and torso influence
    if arm_w > 0.05 and torso_w > 0.05:
        results.append({
            "co": (round(x,4), round(y,4), round(z,4)),
            "arm_total":   round(arm_w, 3),
            "torso_total": round(torso_w, 3),
            "top_weights": sorted(weights.items(), key=lambda kv: -kv[1])[:5],
        })

results.sort(key=lambda r: r["arm_total"], reverse=True)
print(f"\n=== Armpit transition vertices: {len(results)} ===")
for r in results[:30]:
    print(f"  co={r['co']}  arm={r['arm_total']:.2f}  torso={r['torso_total']:.2f}  "
          f"{dict(r['top_weights'])}")

if results:
    avg_arm   = sum(r["arm_total"]   for r in results) / len(results)
    avg_torso = sum(r["torso_total"] for r in results) / len(results)
    print(f"\nAverages: arm={avg_arm:.2f}  torso={avg_torso:.2f}  over {len(results)} verts")
