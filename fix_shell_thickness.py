"""
fix_shell_thickness.py
======================
Uniformly inflates shell_upper_body.glb outward along vertex normals.

The female base mesh was clipping through the shell in several areas
(upper back, shoulder blades, near armpits).  The shell is a closed mesh
so there are no open holes to patch — the fix is to add uniform thickness
via a shrink/fatten displacement along normals.

Current shell offset: ~12 mm.  We add INFLATE_AMOUNT on top of that.

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background --python fix_shell_thickness.py
"""

import bpy
import bmesh
import shutil

# ── Config ────────────────────────────────────────────────────────────────────
GLB_IN  = (
    "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
    "/viewer/public/equipment/shell_upper_body_backup.glb"   # clean pre-fix backup
)
GLB_OUT = (
    "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
    "/viewer/public/equipment/shell_upper_body.glb"
)

INFLATE_AMOUNT = 0.006   # metres (6 mm extra clearance on top of the existing ~12 mm offset)

# ── 1. Clear scene ────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# ── 2. Import from clean backup ───────────────────────────────────────────────
print(f"[fix_shell_thickness] Reading from {GLB_IN}")
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != 'Icosphere']
print(f"[fix_shell_thickness] Meshes: {[o.name for o in mesh_objs]}")

# ── 3. Inflate each mesh along vertex normals ─────────────────────────────────
for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.normal_update()
    bm.verts.ensure_lookup_table()

    for v in bm.verts:
        n = v.normal
        v.co.x += n.x * INFLATE_AMOUNT
        v.co.y += n.y * INFLATE_AMOUNT
        v.co.z += n.z * INFLATE_AMOUNT

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"  [{obj.name}] Inflated {len(mesh.vertices)} vertices by {INFLATE_AMOUNT*1000:.1f} mm")

# ── 4. Export ─────────────────────────────────────────────────────────────────
print(f"\n[fix_shell_thickness] Exporting to {GLB_OUT} …")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format='GLB',
    export_apply=False,
    export_animations=True,
    export_skins=True,
    use_selection=False,
)
print("[fix_shell_thickness] Done ✓")
