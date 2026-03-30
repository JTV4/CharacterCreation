"""
fix_shell_upperbody_armpit.py
=============================
Fixes armpit clipping on shell_upper_body.glb (viewer/public/equipment/).

Diagnosis: inner armpit crease vertices at |X|≈0.27, Z≈1.36-1.47 are
100% arm-bone weighted (upperarm + clavicle) with zero torso (spine_03).
When the arm adducts to idle/walk, these vertices follow the arm into the body.

Strategy — weight redistribution only (no geometry push):
  Transfer a fraction of upperarm bone weight to spine_03 at the crease,
  using a Gaussian centred on the problem zone.  clavicle weight is
  intentionally kept so the shoulder seam still looks correct.

Conservative settings chosen to fix clipping without changing T-pose look:
  - TRANSFER_FRAC 0.35 (35%) keeps the sleeve arm-driven while anchoring crease
  - Tight sigma 0.065 so only the concave fold is affected

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_shell_upperbody_armpit.py
"""

import bpy
import math

BASE    = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN  = f"{BASE}/viewer/public/equipment/shell_upper_body.glb"
GLB_OUT = GLB_IN

# ── Armpit crease centres (Blender Z-up after GLB import) ─────────────────
# Diagnosis shows zero-torso vertices at |X|≈0.27, Z≈1.36-1.47.
# Centre the Gaussian on the deepest fold (inner edge of that cluster).
ARMPIT_CENTRES = [
    ( 0.22,  0.01, 1.41),   # left  armpit inner crease
    (-0.22,  0.01, 1.41),   # right armpit inner crease
]

# Only reduce upperarm weight — leave clavicle alone so shoulder seam is unaffected
ARM_BONES   = ["upperarm_L", "upperarm_R"]
ANCHOR_BONE = "spine_03"

TRANSFER_FRAC = 0.35   # 35 % of upperarm weight → spine_03 at Gaussian peak
SIGMA         = 0.065  # 6.5 cm half-width
CUTOFF_MULT   = 3.0    # hard cutoff at 3σ ≈ 19.5 cm


def gauss(px, py, pz, cx, cy, cz, sig):
    d2 = (px-cx)**2 + (py-cy)**2 + (pz-cz)**2
    return math.exp(-d2 / (2.0 * sig**2))


# ── 1. Load ───────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and len(o.vertex_groups) > 0]
armatures  = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"[shell_armpit] Loaded meshes: {[o.name for o in mesh_objs]}")
print(f"[shell_armpit] Armatures:     {[o.name for o in armatures]}")

cutoff_dist = SIGMA * CUTOFF_MULT

for obj in mesh_objs:
    bpy.context.view_layer.objects.active = obj
    vg_index = {vg.name: vg.index for vg in obj.vertex_groups}

    if ANCHOR_BONE not in vg_index:
        obj.vertex_groups.new(name=ANCHOR_BONE)
        vg_index = {vg.name: vg.index for vg in obj.vertex_groups}
        print(f"  Created vertex group '{ANCHOR_BONE}'")

    arm_idxs   = {vg_index[b] for b in ARM_BONES if b in vg_index}
    anchor_idx = vg_index[ANCHOR_BONE]

    modified = 0
    for v in obj.data.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z

        best_g = 0.0
        for (cx, cy, cz) in ARMPIT_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < cutoff_dist:
                g = gauss(x, y, z, cx, cy, cz, SIGMA)
                best_g = max(best_g, g)

        if best_g < 0.01:
            continue

        w = {g.group: g.weight for g in v.groups}
        total_arm = sum(w.get(i, 0.0) for i in arm_idxs)
        if total_arm < 0.05:
            continue

        transfer = total_arm * TRANSFER_FRAC * best_g

        for i in arm_idxs:
            if i in w and w[i] > 0:
                frac = w[i] / total_arm
                w[i] = max(0.0, w[i] - transfer * frac)

        w[anchor_idx] = w.get(anchor_idx, 0.0) + transfer

        total = sum(w.values())
        if total > 1e-6:
            for k in w:
                w[k] /= total

        for g in v.groups:
            if g.group in w:
                g.weight = w[g.group]
        obj.vertex_groups[anchor_idx].add([v.index], w.get(anchor_idx, 0.0), 'REPLACE')
        modified += 1

    print(f"  [{obj.name}] Weight redistribution: {modified} vertices modified "
          f"(transfer={TRANSFER_FRAC*100:.0f}%, sigma={SIGMA*100:.1f}cm)")

# ── 2. Export ──────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objs + armatures:
    obj.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[shell_armpit] Exporting → {GLB_OUT}")
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
print("[shell_armpit] Done ✓")
