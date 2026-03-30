"""
fix_armpit_weights.py
=====================
Redistributes bone weights at the inner armpit crease of shell_upper_body.glb.

Diagnosis showed those vertices are ~90-95% weighted to arm bones
(upperarm_L/R + clavicle_L/R) with only 5-10% torso (spine_02/03).
When the arm goes down the inner crease follows the arm and clips
through the body.

Fix: transfer up to TRANSFER_FRAC of the arm-bone weight to spine_03 at
the inner armpit crease, using a Gaussian falloff so only the deepest
concave zone is affected and the outer arm is unchanged.

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python fix_armpit_weights.py
"""

import bpy
import math

GLB_IN  = ("/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
           "/viewer/public/equipment/shell_upper_body.glb")
GLB_OUT = GLB_IN

# Armpit centre positions (one per side); the Gaussian is applied in 3D.
# Left armpit inner crease is at positive X in Blender/GLB coords.
ARMPIT_CENTRES = [
    ( 0.175,  0.05, 1.42),   # left armpit
    (-0.175,  0.05, 1.42),   # right armpit
]
FALLOFF_SIGMA   = 0.06     # 6 cm sigma — tight, affects only the crease
CUTOFF_MULT     = 2.0      # hard cutoff at 12 cm
TRANSFER_FRAC   = 0.28     # transfer up to 28% of arm weight to torso at peak

ARM_BONES   = ["upperarm_L", "upperarm_R", "clavicle_L", "clavicle_R"]
ANCHOR_BONE = "spine_03"   # torso bone that gains the weight

# ── 1. Import ──────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and len(o.vertex_groups) > 0]
armatures = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"[armpit] Meshes: {[o.name for o in mesh_objs]}")

cutoff = FALLOFF_SIGMA * CUTOFF_MULT

for obj in mesh_objs:
    bpy.context.view_layer.objects.active = obj
    vg_names = {vg.index: vg.name for vg in obj.vertex_groups}
    vg_index = {vg.name: vg.index for vg in obj.vertex_groups}

    # Ensure anchor bone vertex group exists
    if ANCHOR_BONE not in vg_index:
        obj.vertex_groups.new(name=ANCHOR_BONE)
        vg_index = {vg.name: vg.index for vg in obj.vertex_groups}
        vg_names  = {vg.index: vg.name for vg in obj.vertex_groups}
        print(f"  Created vertex group '{ANCHOR_BONE}'")

    arm_indices    = {vg_index[b] for b in ARM_BONES   if b in vg_index}
    anchor_idx     = vg_index[ANCHOR_BONE]

    modified = 0
    for v in obj.data.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z

        # Find closest armpit centre
        best_gauss = 0.0
        for cx, cy, cz in ARMPIT_CENTRES:
            dx, dy, dz = x - cx, y - cy, z - cz
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            if dist < cutoff:
                g = math.exp(-(dist**2) / (2.0 * FALLOFF_SIGMA**2))
                best_gauss = max(best_gauss, g)

        if best_gauss < 0.01:
            continue

        # Current weights as dict
        w = {g.group: g.weight for g in v.groups}

        total_arm_w = sum(w.get(idx, 0.0) for idx in arm_indices)
        if total_arm_w < 0.05:
            continue

        # Amount to transfer from arm bones to anchor
        transfer = total_arm_w * TRANSFER_FRAC * best_gauss

        # Reduce each arm-bone weight proportionally
        for idx in arm_indices:
            if idx in w and w[idx] > 0:
                frac = w[idx] / total_arm_w
                w[idx] = max(0.0, w[idx] - transfer * frac)

        # Increase anchor weight
        w[anchor_idx] = w.get(anchor_idx, 0.0) + transfer

        # Renormalize
        total = sum(w.values())
        if total > 1e-6:
            for k in w:
                w[k] /= total

        # Write back
        for g in v.groups:
            if g.group in w:
                g.weight = w[g.group]
        # Set anchor (may not already be in groups)
        anchor_vg = obj.vertex_groups[anchor_idx]
        anchor_vg.add([v.index], w.get(anchor_idx, 0.0), 'REPLACE')

        modified += 1

    print(f"  [{obj.name}] Redistributed weights on {modified} armpit vertices "
          f"(peak_transfer={TRANSFER_FRAC*100:.0f}%, sigma={FALLOFF_SIGMA*100:.0f}cm)")

# ── 2. Export ──────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objs + armatures:
    obj.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[armpit] Exporting → {GLB_OUT}")
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format='GLB',
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_skins=True,
    export_all_influences=True,
    export_def_bones=True,
    export_animations=False,
    export_materials='EXPORT',
)
print("[armpit] Done ✓")
