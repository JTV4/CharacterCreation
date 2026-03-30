"""
fix_armpits_v3.py
=================
Fixes armpit clipping on shell_upper_body.glb by inflating the armpit hollow
outward along vertex normals using a Gaussian falloff.

The shell_upper_body is a fully-closed mesh (no armhole boundary edges), so
the flange-ring approach in fix_armpits.py does not apply.  Instead we push
the concave armpit vertices outward so the body mesh can no longer poke through.

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python fix_armpits_v3.py
"""

import bpy
import bmesh
import shutil
import math

# ── Config ────────────────────────────────────────────────────────────────────
GLB_IN   = (
    "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
    "/viewer/public/equipment/shell_upper_body_backup.glb"   # read from pre-fix backup
)
GLB_OUT  = (
    "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
    "/viewer/public/equipment/shell_upper_body.glb"
)

# Armpit centres (world space, Blender Z-up / Y-forward)
# Confirmed from mesh diagnostic: armpit region is Z≈1.25-1.44, |X|≈0.04-0.22
ARMPIT_CENTRES = [
    ( 0.145,  0.005, 1.330),   # right armpit
    (-0.145,  0.005, 1.330),   # left  armpit
]

INFLATE_AMOUNT = 0.014   # metres along normal at the Gaussian peak
FALLOFF_RADIUS = 0.075   # metres – 1-sigma Gaussian radius
CUTOFF_MULT    = 3.0     # only process verts within CUTOFF_MULT * FALLOFF_RADIUS

# ── 1. Clear scene ────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# ── 2. Import ─────────────────────────────────────────────────────────────────
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != 'Icosphere']
print(f"[fix_armpits_v3] Meshes to process: {[o.name for o in mesh_objs]}")

for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    total_moved = 0
    for v in bm.verts:
        max_weight = 0.0
        max_inflate = 0.0
        for (cx, cy, cz) in ARMPIT_CENTRES:
            dx = v.co.x - cx
            dy = v.co.y - cy
            dz = v.co.z - cz
            dist = math.sqrt(dx*dx + dy*dy + dz*dz)
            if dist < FALLOFF_RADIUS * CUTOFF_MULT:
                w = math.exp(-(dist**2) / (2.0 * FALLOFF_RADIUS**2))
                if w > max_weight:
                    max_weight = w
                    max_inflate = INFLATE_AMOUNT * w

        if max_weight > 0.001:
            n = v.normal
            v.co.x += n.x * max_inflate
            v.co.y += n.y * max_inflate
            v.co.z += n.z * max_inflate
            total_moved += 1

    print(f"  [{obj.name}] Inflated {total_moved} vertices")
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

# ── 3. Export ─────────────────────────────────────────────────────────────────
print(f"\n[fix_armpits_v3] Exporting to {GLB_OUT} …")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format='GLB',
    export_apply=False,
    export_animations=True,
    export_skins=True,
    use_selection=False,
)
print("[fix_armpits_v3] Done ✓")
