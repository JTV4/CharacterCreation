"""
fix_shell_weights.py
====================
Corrects bone weights on shell_lower_body.glb in the inner groin / crotch
transition zone to prevent clipping during leg-raise animations.

WHY THIS WORKS
--------------
The shell has the same bone weights as the body mesh.  When the thigh rotates
~73° the inner groin shell vertex (offset 20 mm from the body) traces a
slightly larger arc than the body vertex → shell gets pulled inward past the
body surface.

Fixing this doesn't require more thickness; it requires that the inner groin
vertices follow the PELVIS (torso anchor) more than the THIGHS.  By
transferring a fraction of thigh_L / thigh_R weight to pelvis in that zone the
groin shell stays close to the torso and can't be dragged inward by the leg.

The transfer uses a Gaussian spatial falloff so the correction is invisible in
T-pose and blends smoothly into the surrounding weight map.

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_shell_weights.py
"""

import bpy
import bmesh
import math

# ── Config ────────────────────────────────────────────────────────────────────
GLB_PATH = (
    "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
    "/viewer/public/equipment/shell_lower_body.glb"
)

# Spatial region (confirmed from mesh diagnostic)
GROIN_CENTRE   = (0.0, 0.02, 0.76)   # world-space centre of inner crotch
FALLOFF_RADIUS = 0.11                 # 1-sigma Gaussian radius (metres)
CUTOFF_MULT    = 2.5                  # only process verts within this * sigma

# Weight transfer
PULLING_BONES  = ["thigh_L", "thigh_R"]   # bones that drag the shell inward
ANCHOR_BONE    = "pelvis"                  # bone that keeps the shell on the torso
TRANSFER_FRAC  = 0.45   # at the Gaussian peak, move this fraction of combined
                        # thigh weight to pelvis.  0.45 = 45% transfer.

# ── 1. Import ─────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
print(f"[fix_shell_weights] Importing {GLB_PATH}")
bpy.ops.import_scene.gltf(filepath=GLB_PATH)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and o.name != 'Icosphere']
print(f"[fix_shell_weights] Meshes: {[o.name for o in mesh_objs]}")

cx, cy, cz = GROIN_CENTRE
cutoff = FALLOFF_RADIUS * CUTOFF_MULT

for obj in mesh_objs:
    # Build vertex-group name → index lookup
    vg_index = {vg.name: vg.index for vg in obj.vertex_groups}

    anchor_idx  = vg_index.get(ANCHOR_BONE)
    pulling_idx = [vg_index[b] for b in PULLING_BONES if b in vg_index]

    if anchor_idx is None:
        print(f"  [{obj.name}] WARNING: anchor bone '{ANCHOR_BONE}' not found — skipping")
        continue
    if not pulling_idx:
        print(f"  [{obj.name}] WARNING: none of {PULLING_BONES} found — skipping")
        continue

    anchor_vg  = obj.vertex_groups[anchor_idx]
    pulling_vg = [obj.vertex_groups[i] for i in pulling_idx]

    corrected = 0
    for v in obj.data.vertices:
        dx = v.co.x - cx
        dy = v.co.y - cy
        dz = v.co.z - cz
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist >= cutoff:
            continue

        gauss = math.exp(-(dist**2) / (2.0 * FALLOFF_RADIUS**2))
        effective_transfer = TRANSFER_FRAC * gauss

        # Read current weights for all groups on this vertex
        weights = {}
        for g in v.groups:
            weights[g.group] = g.weight

        # Sum up current thigh weights
        total_thigh = sum(weights.get(i, 0.0) for i in pulling_idx)
        if total_thigh < 1e-6:
            continue   # no thigh influence here — nothing to transfer

        # Amount moving from thighs to pelvis
        transfer_amount = total_thigh * effective_transfer

        # Reduce each thigh proportionally
        for i in pulling_idx:
            old_w = weights.get(i, 0.0)
            if old_w > 0:
                share = old_w / total_thigh
                weights[i] = old_w - transfer_amount * share

        # Increase pelvis
        weights[anchor_idx] = weights.get(anchor_idx, 0.0) + transfer_amount

        # Renormalise to sum = 1.0
        total = sum(weights.values())
        if total > 1e-6:
            weights = {k: v / total for k, v in weights.items()}

        # Write back to vertex groups
        for vg in obj.vertex_groups:
            new_w = weights.get(vg.index, 0.0)
            if new_w > 1e-5:
                vg.add([v.index], new_w, 'REPLACE')
            else:
                try:
                    vg.remove([v.index])
                except RuntimeError:
                    pass

        corrected += 1

    print(f"  [{obj.name}] Corrected weights on {corrected} groin vertices "
          f"(transfer={TRANSFER_FRAC*100:.0f}% thigh→pelvis at peak)")

# ── 2. Export ─────────────────────────────────────────────────────────────────
print(f"\n[fix_shell_weights] Exporting to {GLB_PATH} …")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=GLB_PATH,
    export_format='GLB',
    export_apply=False,
    export_animations=True,
    export_skins=True,
    use_selection=False,
)
print("[fix_shell_weights] Done ✓")
