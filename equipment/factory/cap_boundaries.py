"""Cap open boundary edges on a GLB mesh.

After bisect-cutting a solidified shell in Blender, the cut exposes
open edges.  This script closes all boundary holes using BMesh direct
face creation for reliable capping of non-planar curved boundaries.

Usage (headless Blender):
    blender --background --python equipment/factory/cap_boundaries.py -- \
        --input  viewer/public/equipment/female/Boots/Boots.glb \
        --output viewer/public/equipment/female/Boots/Boots_capped.glb
"""

from __future__ import annotations

import argparse
import sys

import bpy
import bmesh


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        description="Cap open boundary edges on a GLB mesh",
    )
    parser.add_argument("--input", required=True, help="Input GLB path")
    parser.add_argument("--output", required=True,
                        help="Output GLB path (can be same as input)")
    return parser.parse_args(argv)


def find_boundary_loops(bm: bmesh.types.BMesh) -> list[list[bmesh.types.BMVert]]:
    """Walk boundary edges to build ordered vertex loops."""
    visited: set[int] = set()
    loops: list[list[bmesh.types.BMVert]] = []

    for seed in bm.edges:
        if not seed.is_boundary or seed.index in visited:
            continue

        verts: list[bmesh.types.BMVert] = []
        cur_edge = seed
        cur_vert = seed.verts[0]

        while True:
            visited.add(cur_edge.index)
            verts.append(cur_vert)
            other = cur_edge.other_vert(cur_vert)

            nxt = None
            for e in other.link_edges:
                if e.is_boundary and e.index not in visited:
                    nxt = e
                    break

            if nxt is None:
                break
            cur_vert = other
            cur_edge = nxt

        if len(verts) >= 3:
            loops.append(verts)

    return loops


def cap_mesh(obj: bpy.types.Object) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    bm = bmesh.from_edit_mesh(obj.data)

    # Step 1: merge duplicates
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    bmesh.update_edit_mesh(obj.data)

    bm = bmesh.from_edit_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    initial = sum(1 for e in bm.edges if e.is_boundary)
    print(f"  {obj.name}: {initial} boundary edges after merge")

    if initial == 0:
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.select_set(False)
        return

    # Step 2: find and fill all boundary loops directly via BMesh
    max_rounds = 5
    for rnd in range(max_rounds):
        bm = bmesh.from_edit_mesh(obj.data)
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()

        loops = find_boundary_loops(bm)
        if not loops:
            break

        before = sum(1 for e in bm.edges if e.is_boundary)
        sizes = sorted([len(l) for l in loops], reverse=True)
        print(f"    Round {rnd + 1}: {len(loops)} loops "
              f"(sizes: {sizes}), {before} boundary edges")

        filled = 0
        for loop_verts in loops:
            try:
                bm.faces.new(loop_verts)
                filled += 1
            except ValueError:
                pass

        bmesh.update_edit_mesh(obj.data)
        bm = bmesh.from_edit_mesh(obj.data)
        after = sum(1 for e in bm.edges if e.is_boundary)
        print(f"    Round {rnd + 1}: filled {filled}/{len(loops)} → "
              f"{after} boundary edges")

        if after == 0 or after >= before:
            break

    # Step 3: operator-based cleanup for any remaining boundaries
    bm = bmesh.from_edit_mesh(obj.data)
    remaining = sum(1 for e in bm.edges if e.is_boundary)
    if remaining > 0:
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.fill_holes(sides=1024)
        bm = bmesh.from_edit_mesh(obj.data)
        after_cleanup = sum(1 for e in bm.edges if e.is_boundary)
        print(f"  fill_holes cleanup: {remaining} → {after_cleanup}")

    # Step 4: triangulate any n-gons we created (for clean export)
    bm = bmesh.from_edit_mesh(obj.data)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons)
        print(f"  Triangulated {len(ngons)} n-gons")
    bmesh.update_edit_mesh(obj.data)

    # Step 5: fix normals
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)

    bm = bmesh.from_edit_mesh(obj.data)
    final = sum(1 for e in bm.edges if e.is_boundary)
    print(f"  {obj.name}: {initial} → {final} boundary edges (done)")

    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)


def main() -> None:
    args = parse_args()

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=args.input)

    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not mesh_objs:
        print("ERROR: No mesh objects found in GLB")
        sys.exit(1)

    print(f"  Found {len(mesh_objs)} mesh object(s): "
          f"{[o.name for o in mesh_objs]}")

    for obj in mesh_objs:
        cap_mesh(obj)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=args.output,
        export_format="GLB",
        use_selection=True,
        export_yup=True,
    )
    print(f"\n  Exported: {args.output}")


if __name__ == "__main__":
    main()
