"""
compare_armpit_weights.py
=========================
Compares armpit vertex weights between base_female.glb and shell_upper_body.glb.

The base_female uses Mixamo bone names; the shell uses generic rig names.
This script remaps them to the same names so weights can be compared directly.

Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python compare_armpit_weights.py
"""
import bpy
import math

BASE_DIR = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
BODY_GLB  = f"{BASE_DIR}/viewer/public/equipment/base_female.glb"
SHELL_GLB = f"{BASE_DIR}/viewer/public/equipment/shell_upper_body.glb"

# Mixamo → generic remap (body uses Mixamo, shell uses generic)
MIXAMO_TO_GENERIC = {
    "mixamorig:LeftArm":      "upperarm_L",
    "mixamorig:RightArm":     "upperarm_R",
    "mixamorig:LeftShoulder": "clavicle_L",
    "mixamorig:RightShoulder":"clavicle_R",
    "mixamorig:Spine2":       "spine_03",
    "mixamorig:Spine1":       "spine_02",
    "mixamorig:Spine":        "spine_01",
    "mixamorig:Hips":         "pelvis",
    "mixamorig:Neck":         "neck_01",
    "mixamorig:Head":         "head",
    "mixamorig:LeftForeArm":  "lowerarm_L",
    "mixamorig:RightForeArm": "lowerarm_R",
    "mixamorig:LeftHand":     "hand_L",
    "mixamorig:RightHand":    "hand_R",
}
# Also try without namespace prefix
for k in list(MIXAMO_TO_GENERIC.keys()):
    MIXAMO_TO_GENERIC[k.replace("mixamorig:", "")] = MIXAMO_TO_GENERIC[k]

ARM_BONES   = {"upperarm_L", "upperarm_R", "clavicle_L", "clavicle_R"}
TORSO_BONES = {"spine_01", "spine_02", "spine_03", "pelvis"}

def load_armpit_weights(glb_path, remap=None):
    """Load a GLB and return {co: {generic_bone: weight}} for armpit zone."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=glb_path)

    m = next((o for o in bpy.data.objects
               if o.type == 'MESH' and len(o.vertex_groups) > 0), None)
    if not m:
        print(f"  No mesh with vertex groups in {glb_path}")
        return []

    vgs = {vg.index: vg.name for vg in m.vertex_groups}
    print(f"  {glb_path.split('/')[-1]}: {len(m.data.vertices)} verts, vgroups={list(vgs.values())[:6]}...")

    results = []
    for v in m.data.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z
        if not (0.04 < abs(x) < 0.30 and 1.20 < z < 1.50):
            continue

        w_raw = {vgs[g.group]: g.weight for g in v.groups if g.weight > 0.005}
        if remap:
            w = {}
            for name, weight in w_raw.items():
                generic = remap.get(name, name)
                w[generic] = w.get(generic, 0.0) + weight
        else:
            w = w_raw

        arm   = sum(v for k,v in w.items() if k in ARM_BONES)
        torso = sum(v for k,v in w.items() if k in TORSO_BONES)
        results.append({
            "co": (round(x,3), round(y,3), round(z,3)),
            "arm": round(arm,3), "torso": round(torso,3),
            "w": {k: round(v,3) for k,v in w.items()}
        })

    return results

print("=== BASE FEMALE armpit weights ===")
body_results = load_armpit_weights(BODY_GLB, remap=MIXAMO_TO_GENERIC)
body_results.sort(key=lambda r: r["arm"], reverse=True)
print(f"  Inner zone vertices: {len(body_results)}")
print("  Top 15 by arm weight:")
for r in body_results[:15]:
    print(f"    co={r['co']}  arm={r['arm']:.3f}  torso={r['torso']:.3f}  {r['w']}")
if body_results:
    avg_arm   = sum(r["arm"]   for r in body_results) / len(body_results)
    avg_torso = sum(r["torso"] for r in body_results) / len(body_results)
    zero_torso = sum(1 for r in body_results if r["torso"] < 0.01)
    print(f"\n  Average: arm={avg_arm:.3f}  torso={avg_torso:.3f}")
    print(f"  Zero-torso verts: {zero_torso}")

print("\n=== SHELL UPPER BODY armpit weights ===")
shell_results = load_armpit_weights(SHELL_GLB)
shell_results.sort(key=lambda r: r["arm"], reverse=True)
print(f"  Inner zone vertices: {len(shell_results)}")
print("  Top 15 by arm weight:")
for r in shell_results[:15]:
    print(f"    co={r['co']}  arm={r['arm']:.3f}  torso={r['torso']:.3f}  {r['w']}")
if shell_results:
    avg_arm   = sum(r["arm"]   for r in shell_results) / len(shell_results)
    avg_torso = sum(r["torso"] for r in shell_results) / len(shell_results)
    zero_torso = sum(1 for r in shell_results if r["torso"] < 0.01)
    print(f"\n  Average: arm={avg_arm:.3f}  torso={avg_torso:.3f}")
    print(f"  Zero-torso verts: {zero_torso}")
