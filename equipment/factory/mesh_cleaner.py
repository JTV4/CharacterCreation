"""Mesh Cleaner — fixes rogue vertices, duplicate verts, and degenerate faces.

Loads a skinned GLB, cleans the mesh geometry while preserving armature and
skin weights, then re-exports.  Designed for shell equipment meshes that may
have displaced vertex chains or disconnected micro-islands from the extraction
or solidify pipeline.

Cleaning steps:
    1. Merge by distance (eliminates duplicate/overlapping vertices)
    2. Remove degenerate faces (zero-area triangles)
    3. Remove loose vertices (unconnected geometry)
    4. Delete small disconnected mesh islands (< min_island_verts)
    5. Multi-pass outlier smoothing (snaps spike chains to neighbor averages)
    6. Recalculate normals for a clean result

Usage (headless Blender):
    blender --background --python equipment/factory/mesh_cleaner.py -- \\
        --input  viewer/public/equipment/shell_gloves.glb \\
        --output viewer/public/equipment/shell_gloves.glb \\
        [--merge-distance 0.0001] \\
        [--outlier-threshold 0.05] \\
        [--outlier-passes 6] \\
        [--min-island-verts 20]
"""

import bpy
import bmesh
import sys
import os


def get_args():
    argv = sys.argv
    if "--" not in argv:
        raise RuntimeError("Expected -- separator in command line args")
    argv = argv[argv.index("--") + 1:]

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Input GLB path")
    parser.add_argument("--output", required=True, help="Output GLB path")
    parser.add_argument("--merge-distance", type=float, default=0.0001,
                        help="Merge-by-distance threshold (meters). Default: 0.0001")
    parser.add_argument("--outlier-threshold", type=float, default=0.05,
                        help="Outlier smoothing threshold. Default: 0.05")
    parser.add_argument("--outlier-passes", type=int, default=6,
                        help="Max outlier smoothing passes. Default: 6")
    parser.add_argument("--min-island-verts", type=int, default=20,
                        help="Delete mesh islands smaller than this. Default: 20")
    parser.add_argument("--inflate", type=float, default=0.0,
                        help="Push vertices outward along normals (meters). "
                             "Matches viewer's INFLATE_AMOUNT. Default: 0.0 (off)")
    parser.add_argument("--inflate-skip-finger-inward", action="store_true",
                        help="Skip inward-facing normals in finger region (|X|>0.75). "
                             "Matches viewer's inflateGeometry behaviour for gloves.")
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for coll in bpy.data.collections:
        bpy.data.collections.remove(coll)


def find_mesh_objects():
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def smooth_outlier_vertices(obj, threshold, max_passes):
    """Multi-pass outlier smoothing in edit mode using bmesh."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)

    total_fixed = 0
    for pass_num in range(max_passes):
        bm.verts.ensure_lookup_table()
        pass_fixed = 0

        for v in bm.verts:
            if len(v.link_edges) < 2:
                continue
            neighbors = [e.other_vert(v) for e in v.link_edges]
            avg = sum((n.co for n in neighbors), type(v.co)()) / len(neighbors)
            dist = (v.co - avg).length
            if dist > threshold:
                v.co = avg
                pass_fixed += 1

        total_fixed += pass_fixed
        print(f"  Pass {pass_num + 1}: smoothed {pass_fixed} outlier vertices")
        if pass_fixed == 0:
            break

    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')
    return total_fixed


def delete_small_islands(obj, min_verts):
    """Delete disconnected mesh islands smaller than min_verts."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')

    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    visited = set()
    islands = []

    for v in bm.verts:
        if v.index in visited:
            continue
        island = set()
        stack = [v]
        while stack:
            curr = stack.pop()
            if curr.index in visited:
                continue
            visited.add(curr.index)
            island.add(curr.index)
            for e in curr.link_edges:
                nb = e.other_vert(curr)
                if nb.index not in visited:
                    stack.append(nb)
        islands.append(island)

    islands.sort(key=len, reverse=True)
    deleted_count = 0

    for island in islands:
        if len(island) >= min_verts:
            continue
        bm.verts.ensure_lookup_table()
        for vi in island:
            if vi < len(bm.verts):
                bm.verts[vi].select_set(True)
        deleted_count += len(island)

    if deleted_count > 0:
        bpy.ops.mesh.select_all(action='DESELECT')
        bm.verts.ensure_lookup_table()
        for island in islands:
            if len(island) >= min_verts:
                continue
            for vi in island:
                if vi < len(bm.verts):
                    bm.verts[vi].select_set(True)

        bmesh.update_edit_mesh(obj.data)
        bpy.ops.mesh.delete(type='VERT')

    bpy.ops.object.mode_set(mode='OBJECT')

    island_summary = [len(i) for i in islands]
    print(f"  Found {len(islands)} islands: {island_summary}")
    print(f"  Deleted {deleted_count} vertices from small islands (< {min_verts} verts)")
    return deleted_count


def inflate_mesh(obj, amount, skip_finger_inward):
    """Push vertices outward along their normals."""
    mesh = obj.data
    mesh.update()

    from mathutils import Vector
    import math

    vert_normals = [Vector(v.normal) for v in mesh.vertices]

    moved = 0
    for v in mesh.vertices:
        n = vert_normals[v.index]
        if n.length < 0.001:
            continue

        if skip_finger_inward and abs(v.co.x) > 0.75:
            radial_len = math.sqrt(v.co.x ** 2 + v.co.y ** 2)
            if radial_len > 0.01:
                dot = (v.co.x * n.x + v.co.y * n.y) / radial_len
                if dot < 0:
                    continue

        v.co += n * amount
        moved += 1

    print(f"  Inflate: pushed {moved} vertices by {amount}")
    return moved


def clean_mesh(obj, args):
    """Run all cleaning steps on a mesh object."""
    print(f"\nCleaning mesh: {obj.name}")
    print(f"  Initial: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} faces")

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    before_verts = len(obj.data.vertices)
    bpy.ops.mesh.remove_doubles(threshold=args.merge_distance)
    bpy.ops.object.mode_set(mode='OBJECT')
    after_verts = len(obj.data.vertices)
    print(f"  Merge by distance ({args.merge_distance}): {before_verts} → {after_verts} verts "
          f"({before_verts - after_verts} merged)")

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    before_faces = len(obj.data.polygons)
    bpy.ops.mesh.dissolve_degenerate(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT')
    after_faces = len(obj.data.polygons)
    print(f"  Remove degenerate faces: {before_faces} → {after_faces} "
          f"({before_faces - after_faces} removed)")

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.mesh.select_loose()
    bpy.ops.mesh.delete(type='VERT')
    bpy.ops.object.mode_set(mode='OBJECT')
    loose_removed = after_verts - len(obj.data.vertices)
    print(f"  Remove loose vertices: {loose_removed} removed")

    deleted = delete_small_islands(obj, args.min_island_verts)

    smoothed = smooth_outlier_vertices(obj, args.outlier_threshold, args.outlier_passes)
    print(f"  Outlier smoothing: {smoothed} total vertices smoothed")

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    print("  Recalculated normals")

    if args.inflate > 0:
        inflate_mesh(obj, args.inflate, args.inflate_skip_finger_inward)

    print(f"  Final: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} faces")


def main():
    args = get_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"=== Mesh Cleaner ===")
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")

    clear_scene()

    print(f"\nImporting GLB...")
    bpy.ops.import_scene.gltf(filepath=input_path)

    meshes = find_mesh_objects()
    if not meshes:
        raise RuntimeError("No mesh objects found in GLB")

    print(f"Found {len(meshes)} mesh object(s): {[m.name for m in meshes]}")

    for obj in meshes:
        clean_mesh(obj, args)

    print(f"\nExporting cleaned GLB to: {output_path}")
    bpy.ops.export_scene.gltf(
        filepath=output_path,
        export_format='GLB',
        export_skins=True,
        export_animations=False,
        export_morph=False,
        export_lights=False,
        export_cameras=False,
    )

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
