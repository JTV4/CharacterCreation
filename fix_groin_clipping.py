"""
fix_groin_clipping.py
=====================
Fixes inner-groin clipping on shell_lower_body.glb using targeted Laplacian
smoothing — NOT per-vertex normal inflation.

Per-vertex normal inflation in a concave area (the crotch hollow) creates
visible polygon ridges because each vertex's normal points in a different
direction.  Laplacian smoothing instead averages each vertex toward its
neighbours, which naturally pushes the concave surface outward as a smooth
bowl — no visible seams.

The smooth weight uses a Gaussian falloff so only the inner groin is affected.

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_groin_clipping.py
"""

import bpy, bmesh, math

GLB_IN  = (
    "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
    "/viewer/public/equipment/shell_lower_body.glb"
)
GLB_OUT = GLB_IN

# Groin centre confirmed from mesh diagnostic (Z≈0.64-0.94, |X|<0.12)
GROIN_CENTRE   = (0.0, 0.02, 0.76)
FALLOFF_RADIUS = 0.13    # 1-sigma; covers the full inner groin region
CUTOFF_MULT    = 2.5
SMOOTH_ITERS   = 40      # Laplacian passes — enough to fill the concavity
MAX_WEIGHT     = 0.85    # max blend toward Laplacian average at centre

# ── 1. Clear + import ─────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and o.name != 'Icosphere']
print(f"[fix_groin] Meshes: {[o.name for o in mesh_objs]}")

cx, cy, cz = GROIN_CENTRE
cutoff = FALLOFF_RADIUS * CUTOFF_MULT

for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()

    # Pre-compute per-vertex Gaussian weight
    weights = {}
    for v in bm.verts:
        dx, dy, dz = v.co.x - cx, v.co.y - cy, v.co.z - cz
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist < cutoff:
            w = math.exp(-(dist**2) / (2.0 * FALLOFF_RADIUS**2))
            weights[v.index] = min(w, MAX_WEIGHT)

    active = set(weights.keys())
    print(f"  [{obj.name}] {len(active)} verts in groin region, "
          f"running {SMOOTH_ITERS} Laplacian passes …")

    # Laplacian smoothing: each iteration blends each active vertex toward
    # the average of its connected neighbours, weighted by the Gaussian mask.
    for _ in range(SMOOTH_ITERS):
        new_positions = {}
        for v in bm.verts:
            if v.index not in active:
                continue
            w = weights[v.index]
            neighbours = [e.other_vert(v) for e in v.link_edges]
            if not neighbours:
                continue
            avg_x = sum(n.co.x for n in neighbours) / len(neighbours)
            avg_y = sum(n.co.y for n in neighbours) / len(neighbours)
            avg_z = sum(n.co.z for n in neighbours) / len(neighbours)
            new_positions[v.index] = (
                v.co.x + (avg_x - v.co.x) * w,
                v.co.y + (avg_y - v.co.y) * w,
                v.co.z + (avg_z - v.co.z) * w,
            )
        for v in bm.verts:
            if v.index in new_positions:
                nx, ny, nz = new_positions[v.index]
                v.co.x, v.co.y, v.co.z = nx, ny, nz

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"  [{obj.name}] Groin smooth complete.")

# ── 2. Export ─────────────────────────────────────────────────────────────────
print(f"[fix_groin] Exporting to {GLB_OUT} …")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format='GLB',
    export_apply=False,
    export_animations=True,
    export_skins=True,
    use_selection=False,
)
print("[fix_groin] Done ✓")
