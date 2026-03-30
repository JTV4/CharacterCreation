"""
fix_upperbody_v1_armpit.py
==========================
Fixes armpit clipping on UpperbodyTestV1.glb.

Diagnosis: all inner-armpit vertices are 100% weighted to upperarm_L/R +
clavicle_L/R with zero torso (spine_03) weight.  When the arm rotates down
to idle/walk/run, the inner crease follows the arm 100% and clips through
the body.

Two-pass fix:
  Pass 1 — Weight redistribution
    Transfer a fraction of arm-bone weight to spine_03 at the inner armpit,
    using a Gaussian falloff so only the concave crease is affected and the
    outer sleeve remains unchanged.

  Pass 2 — Geometry inflation
    Push the inner armpit vertices outward along their normals by a small
    amount.  This adds physical clearance so the surface cannot clip even
    at extreme arm-down deformation.

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_upperbody_v1_armpit.py
"""

import bpy
import bmesh
import shutil
import math

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE   = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN  = f"{BASE}/viewer/public/equipment/Female/Upperbody/UpperbodyTestV1.glb"
GLB_OUT = GLB_IN  # overwrite in place

# ── Armpit geometry centres (Blender Z-up, loaded from GLB) ──────────────────
# Inner crease sits at |X|≈0.12, Y≈0.02, Z≈1.37 based on mesh diagnosis.
# Left side = positive X in this rig's GLB orientation.
ARMPIT_CENTRES = [
    ( 0.13,  0.02, 1.37),   # left  armpit inner crease
    (-0.13,  0.02, 1.37),   # right armpit inner crease
]

# ── Pass 1 — Weight redistribution params ────────────────────────────────────
# Bone groups in UpperbodyTestV1 (generic rig names, confirmed by diagnosis)
ARM_BONES    = ["upperarm_L", "upperarm_R", "clavicle_L", "clavicle_R"]
ANCHOR_BONE  = "spine_03"      # receives transferred weight

# How aggressively to anchor the crease to the torso.
# 0.5 = transfer up to 50% of arm weight to spine_03 at the Gaussian peak.
# This keeps the sleeve arm-driven but stops the inner fold from following.
TRANSFER_FRAC = 0.50

W_SIGMA   = 0.08   # 8 cm — Gaussian half-width for weight redistribution
W_CUTOFF  = 3.0    # hard cutoff at 3 * sigma = 24 cm

# ── Pass 2 — Geometry inflation params ───────────────────────────────────────
INFLATE_AMOUNT = 0.012   # 12 mm outward push at the Gaussian peak
G_SIGMA        = 0.07    # 7 cm — Gaussian half-width for inflation
G_CUTOFF       = 3.0     # hard cutoff at 3 * sigma = 21 cm

# ── 1. Clear scene + import ───────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and len(o.vertex_groups) > 0]
armatures  = [o for o in bpy.data.objects if o.type == 'ARMATURE']

print(f"[armpit_fix] Loaded: {[o.name for o in mesh_objs]}")
print(f"[armpit_fix] Armatures: {[o.name for o in armatures]}")


# ─────────────────────────────────────────────────────────────────────────────
# PASS 1 — Weight redistribution
# ─────────────────────────────────────────────────────────────────────────────
def gaussian(px, py, pz, cx, cy, cz, sigma):
    d2 = (px-cx)**2 + (py-cy)**2 + (pz-cz)**2
    return math.exp(-d2 / (2.0 * sigma**2))


for obj in mesh_objs:
    bpy.context.view_layer.objects.active = obj
    vg_index = {vg.name: vg.index for vg in obj.vertex_groups}
    vg_names  = {vg.index: vg.name for vg in obj.vertex_groups}

    # Create anchor group if missing
    if ANCHOR_BONE not in vg_index:
        obj.vertex_groups.new(name=ANCHOR_BONE)
        vg_index = {vg.name: vg.index for vg in obj.vertex_groups}
        print(f"  Created vertex group '{ANCHOR_BONE}'")

    arm_idxs   = {vg_index[b] for b in ARM_BONES if b in vg_index}
    anchor_idx = vg_index[ANCHOR_BONE]
    w_cutoff_d = W_SIGMA * W_CUTOFF

    modified_w = 0
    for v in obj.data.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z

        # Best Gaussian weight across both armpits
        best_g = 0.0
        for (cx, cy, cz) in ARMPIT_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < w_cutoff_d:
                g = gaussian(x, y, z, cx, cy, cz, W_SIGMA)
                best_g = max(best_g, g)

        if best_g < 0.01:
            continue

        # Current weight map
        w = {g.group: g.weight for g in v.groups}
        total_arm = sum(w.get(i, 0.0) for i in arm_idxs)
        if total_arm < 0.05:
            continue

        transfer = total_arm * TRANSFER_FRAC * best_g

        # Reduce each arm bone proportionally
        for i in arm_idxs:
            if i in w and w[i] > 0:
                frac = w[i] / total_arm
                w[i] = max(0.0, w[i] - transfer * frac)

        # Increase anchor
        w[anchor_idx] = w.get(anchor_idx, 0.0) + transfer

        # Normalise
        total = sum(w.values())
        if total > 1e-6:
            for k in w:
                w[k] /= total

        # Write arm-bone weights back through vertex group API
        for g in v.groups:
            if g.group in w:
                g.weight = w[g.group]
        obj.vertex_groups[anchor_idx].add([v.index], w.get(anchor_idx, 0.0), 'REPLACE')
        modified_w += 1

    print(f"  [Pass 1] {obj.name}: redistributed weights on {modified_w} vertices "
          f"(peak_transfer={TRANSFER_FRAC*100:.0f}%, sigma={W_SIGMA*100:.0f}cm)")


# ─────────────────────────────────────────────────────────────────────────────
# PASS 2 — Geometry inflation
# ─────────────────────────────────────────────────────────────────────────────
for obj in mesh_objs:
    bpy.context.view_layer.objects.active = obj
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    g_cutoff_d = G_SIGMA * G_CUTOFF
    moved = 0

    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z

        best_g = 0.0
        for (cx, cy, cz) in ARMPIT_CENTRES:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < g_cutoff_d:
                g = gaussian(x, y, z, cx, cy, cz, G_SIGMA)
                best_g = max(best_g, g)

        if best_g < 0.01:
            continue

        n = v.normal
        inflate = INFLATE_AMOUNT * best_g
        v.co.x += n.x * inflate
        v.co.y += n.y * inflate
        v.co.z += n.z * inflate
        moved += 1

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    print(f"  [Pass 2] {obj.name}: inflated {moved} armpit vertices "
          f"(peak={INFLATE_AMOUNT*1000:.0f}mm, sigma={G_SIGMA*100:.0f}cm)")


# ── 3. Export ─────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objs + armatures:
    obj.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[armpit_fix] Exporting → {GLB_OUT}")
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
print("[armpit_fix] Done ✓")
