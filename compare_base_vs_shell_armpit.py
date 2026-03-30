"""
compare_base_vs_shell_armpit.py
================================
Compares armpit weights between the rig base female (cm scale, Y-up)
and the shell (meter scale, Z-up) to understand the divergence.

Base female: Y-up, centimetre units. Armpit ≈ |X| 15-40, Y 120-150, Z -15..15
Shell:       Z-up, metre units.    Armpit ≈ |X| 0.04-0.30, Z 1.20-1.50

Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python compare_base_vs_shell_armpit.py
"""
import bpy

BASE_DIR  = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
BODY_GLB  = f"{BASE_DIR}/rig/CharacterMesh/BaseFemale.glb"
SHELL_GLB = f"{BASE_DIR}/viewer/public/equipment/shell_upper_body.glb"

ARM_KW   = ['Arm','arm','Shoulder','shoulder','Clavicle','clavicle','upperarm','clavicle']
TORSO_KW = ['Spine','spine','Hips','hips','pelvis']

# ── BASE FEMALE (Y-up, cm) ────────────────────────────────────────────────────
print("=== BASE FEMALE (rig/CharacterMesh/BaseFemale.glb) ===")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=BODY_GLB)

for m in bpy.data.objects:
    if m.type != 'MESH' or not m.vertex_groups:
        continue
    vgs = {vg.index: vg.name for vg in m.vertex_groups}
    # Base is Y-up cm: armpit is |X| 15-40cm, Y 115-145cm
    zone = [v for v in m.data.vertices
            if 15 < abs(v.co.x) < 40 and 115 < v.co.y < 145]
    print(f"  Mesh: {m.name}  total_verts={len(m.data.vertices)}  armpit_zone={len(zone)}")

    results = []
    for v in zone:
        w = {vgs[g.group]: round(g.weight,4) for g in v.groups if g.weight > 0.005}
        arm   = sum(val for k,val in w.items() if any(kw in k for kw in ARM_KW))
        torso = sum(val for k,val in w.items() if any(kw in k for kw in TORSO_KW))
        results.append({"co":(round(v.co.x,1),round(v.co.y,1),round(v.co.z,1)),
                        "arm":arm,"torso":torso,"w":w})
    results.sort(key=lambda r: r["arm"], reverse=True)
    print("  Top 15 by arm weight:")
    for r in results[:15]:
        print(f"    co={r['co']}  arm={r['arm']:.3f}  torso={r['torso']:.3f}  {r['w']}")
    if results:
        avg_arm   = sum(r["arm"]   for r in results) / len(results)
        avg_torso = sum(r["torso"] for r in results) / len(results)
        zero_torso = sum(1 for r in results if r["torso"] < 0.01)
        print(f"\n  Average: arm={avg_arm:.3f}  torso={avg_torso:.3f}")
        print(f"  Zero-torso verts: {zero_torso} / {len(results)}")

# ── SHELL (Z-up, m) ──────────────────────────────────────────────────────────
print("\n=== SHELL UPPER BODY ===")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=SHELL_GLB)

for m in bpy.data.objects:
    if m.type != 'MESH' or not m.vertex_groups:
        continue
    vgs = {vg.index: vg.name for vg in m.vertex_groups}
    zone = [v for v in m.data.vertices
            if 0.04 < abs(v.co.x) < 0.30 and 1.20 < v.co.z < 1.50]
    print(f"  Mesh: {m.name}  total_verts={len(m.data.vertices)}  armpit_zone={len(zone)}")
    results = []
    for v in zone:
        w = {vgs[g.group]: round(g.weight,4) for g in v.groups if g.weight > 0.005}
        arm   = sum(val for k,val in w.items() if any(kw in k for kw in ARM_KW))
        torso = sum(val for k,val in w.items() if any(kw in k for kw in TORSO_KW))
        results.append({"co":(round(v.co.x,3),round(v.co.y,3),round(v.co.z,3)),
                        "arm":arm,"torso":torso,"w":w})
    results.sort(key=lambda r: r["arm"], reverse=True)
    print("  Top 15 by arm weight:")
    for r in results[:15]:
        print(f"    co={r['co']}  arm={r['arm']:.3f}  torso={r['torso']:.3f}  {r['w']}")
    if results:
        avg_arm   = sum(r["arm"]   for r in results) / len(results)
        avg_torso = sum(r["torso"] for r in results) / len(results)
        zero_torso = sum(1 for r in results if r["torso"] < 0.01)
        print(f"\n  Average: arm={avg_arm:.3f}  torso={avg_torso:.3f}")
        print(f"  Zero-torso verts: {zero_torso} / {len(results)}")
