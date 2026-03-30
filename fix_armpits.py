"""
fix_armpits.py  (v2 – UV-seam-safe)
Run with:  /Applications/Blender.app/Contents/MacOS/Blender --background --python fix_armpits.py

Strategy
--------
GLB meshes split vertices at every UV seam, which makes the naive boundary-edge
search find hundreds of 3-vertex "micro-loops" that aren't real holes.

Fix: after importing, merge-by-distance (weld) all vertices within 0.0001 m of
each other.  This closes UV-seam splits while leaving true open holes (armholes,
neckline, waistband) as the only genuine boundary edges.

Then for each surviving boundary loop we extrude a flange ring inward so the
body mesh can never poke through the opening.

Finally, re-export with the armature so skinning is preserved.
"""

import bpy
import bmesh
import shutil

# ── Config ────────────────────────────────────────────────────────────────────
GLB_PATH    = (
    "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
    "/viewer/public/equipment/shell_upper_body.glb"
)
BACKUP_PATH = GLB_PATH.replace(".glb", "_backup.glb")

FOLD_DEPTH  = 0.022   # metres – how far the new flange ring moves inward in XY
FOLD_Z      = 0.008   # metres – how far it sinks back toward the body in Z
WELD_DIST   = 0.0001  # metres – threshold for merging UV-seam duplicate verts
MIN_LOOP    = 5       # ignore loops with fewer edges than this (safety net)
# Sleeve cuffs sit at |cx| ≈ 0.64 m.  Armholes sit at |cx| ≈ 0.15–0.30 m.
# Body openings (neckline, waistband) sit at |cx| < 0.15 m.
# Raise threshold to 0.35 so armhole loops are included but cuffs are still skipped.
MAX_LOOP_CX = 0.35    # metres – skip any loop whose |centre_x| exceeds this

# ── 1. Clear scene ────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# ── 2. Backup + Import ────────────────────────────────────────────────────────
shutil.copy2(GLB_PATH, BACKUP_PATH)
print(f"[fix_armpits] Backed up to {BACKUP_PATH}")

bpy.ops.import_scene.gltf(filepath=GLB_PATH)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
print(f"[fix_armpits] Meshes: {[o.name for o in mesh_objs]}")

# ── 3. Process each mesh ──────────────────────────────────────────────────────
for obj in mesh_objs:
    print(f"\n[fix_armpits] ── {obj.name} ──")
    bpy.context.view_layer.objects.active = obj

    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)

    # ── 3a. Weld UV-seam duplicate vertices ───────────────────────────────────
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=WELD_DIST)
    after  = len(bm.verts)
    print(f"  Welded {before - after} duplicate verts ({before} → {after})")

    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()

    boundary_edges = [e for e in bm.edges if e.is_boundary]
    print(f"  Boundary edges after weld: {len(boundary_edges)}")

    if not boundary_edges:
        print("  Mesh is fully closed – no flanges needed.")
        bm.free()
        continue

    # ── 3b. Group boundary edges into connected loops ─────────────────────────
    visited = set()
    loops   = []

    for start in boundary_edges:
        if id(start) in visited:
            continue
        loop_edges = []
        loop_verts = set()
        stack = [start]
        while stack:
            e = stack.pop()
            if id(e) in visited:
                continue
            visited.add(id(e))
            loop_edges.append(e)
            for v in e.verts:
                loop_verts.add(v)
                for oe in v.link_edges:
                    if oe.is_boundary and id(oe) not in visited:
                        stack.append(oe)
        cx_loop = sum(v.co.x for v in loop_verts) / max(len(loop_verts), 1)
        if len(loop_edges) < MIN_LOOP:
            print(f"  Skipping tiny loop with {len(loop_edges)} edges (artefact)")
        elif abs(cx_loop) > MAX_LOOP_CX:
            print(f"  Skipping sleeve-cuff loop with {len(loop_edges)} edges  cx={cx_loop:.3f} (not a body opening)")
        else:
            loops.append((loop_edges, loop_verts))

    print(f"  Real boundary loops: {len(loops)}")
    for i, (edges, verts) in enumerate(loops):
        cx = sum(v.co.x for v in verts) / len(verts)
        cy = sum(v.co.y for v in verts) / len(verts)
        cz = sum(v.co.z for v in verts) / len(verts)
        print(f"    Loop {i}: {len(edges)} edges  centre=({cx:.3f}, {cy:.3f}, {cz:.3f})")

    # ── 3c. Extrude a flange ring for each real loop ──────────────────────────
    # We need a mapping: bmesh vert index → original mesh vert index.
    # After remove_doubles the indices shifted, so we record them now.
    orig_boundary_vert_indices = {}   # bm.vert.index → will be mesh vert idx

    new_vert_to_orig = {}   # new_vert_bm_index → orig_vert_bm_index

    for loop_edges, loop_verts in loops:
        cx = sum(v.co.x for v in loop_verts) / len(loop_verts)
        cy = sum(v.co.y for v in loop_verts) / len(loop_verts)

        # Remember original vert indices before extrusion
        orig_indices_map = {v.index: v for v in loop_verts}

        # Extrude – new verts start at same position as originals
        result    = bmesh.ops.extrude_edge_only(bm, edges=loop_edges)
        new_verts = [g for g in result['geom'] if isinstance(g, bmesh.types.BMVert)]

        print(f"    Extruded {len(new_verts)} flange verts")

        for nv in new_verts:
            # Map to nearest original boundary vert (same position at time of extrude)
            best_dist = float('inf')
            best_orig_idx = None
            for ov in loop_verts:
                d = (nv.co - ov.co).length
                if d < best_dist:
                    best_dist = d
                    best_orig_idx = ov.index

            # Move inward in XY toward loop centre
            dx = cx - nv.co.x
            dy = cy - nv.co.y
            dist_xy = (dx*dx + dy*dy) ** 0.5
            if dist_xy > 0.001:
                nv.co.x += (dx / dist_xy) * FOLD_DEPTH
                nv.co.y += (dy / dist_xy) * FOLD_DEPTH
            nv.co.z -= FOLD_Z

            if best_orig_idx is not None:
                new_vert_to_orig[nv.index] = best_orig_idx

    # ── 3d. Write bmesh back to mesh ──────────────────────────────────────────
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    # ── 3e. Copy vertex-group weights to new flange verts ────────────────────
    if new_vert_to_orig and obj.vertex_groups:
        # Build a lookup: new mesh vert index → original mesh vert index.
        # After remove_doubles the bmesh indices no longer match the original
        # mesh indices, so we copy by position proximity using the current mesh.
        vcount = len(mesh.vertices)
        print(f"  Copying weights for {len(new_vert_to_orig)} new verts …")

        # For each new vert, find the nearest OLD vert by position in the mesh
        import mathutils
        kd = mathutils.kdtree.KDTree(vcount - len(new_vert_to_orig))
        kd.balance()   # we'll fall back to brute-force below since KDTree needs rebuild

        # Brute-force nearest: iterate over all vertex groups
        # We use bmesh new_vert_to_orig which maps bm indices.
        # After bm.to_mesh, the bm indices correspond to mesh vertex indices.
        for vg in obj.vertex_groups:
            for new_idx, orig_bm_idx in new_vert_to_orig.items():
                # new_idx and orig_bm_idx are bmesh indices which equal mesh indices
                # after bm.to_mesh when no vertices were removed since to_mesh.
                try:
                    w = vg.weight(orig_bm_idx)
                    if w > 0.0:
                        vg.add([new_idx], w, 'REPLACE')
                except RuntimeError:
                    pass

    print(f"  [{obj.name}] Flanges complete.")

# ── 4. Export ─────────────────────────────────────────────────────────────────
print(f"\n[fix_armpits] Exporting to {GLB_PATH} …")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=GLB_PATH,
    export_format='GLB',
    export_apply=False,
    export_animations=True,
    export_skins=True,
    use_selection=False,
)
print("[fix_armpits] Done ✓")
