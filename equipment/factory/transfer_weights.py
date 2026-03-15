"""
Transfer vertex weights from a source shell GLB to a target (edited) GLB.
Uses the source shell's armature to produce output matching the shell format
(Y-up, legacy bone names, identity-scale ibm).

Usage:
    blender --background --python transfer_weights.py -- \
        --source <shell.glb> --target <edited.glb> --output <output.glb>
        [--method surface|bone]
"""

import bpy
import sys
import os
from mathutils import Vector


def get_args():
    argv = sys.argv
    if "--" not in argv:
        raise RuntimeError("Expected -- separator in command line args")
    argv = argv[argv.index("--") + 1:]

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True,
                        help="Source shell GLB with correct weights + armature")
    parser.add_argument("--target", required=True,
                        help="Target GLB (user-edited mesh)")
    parser.add_argument("--output", required=True, help="Output GLB path")
    parser.add_argument("--method", choices=["surface", "bone", "auto"], default="auto",
                        help="Weight transfer method: 'auto' uses Blender's automatic "
                             "weights / bone heat diffusion (recommended for imported meshes), "
                             "'surface' uses Data Transfer modifier (best for similar geometry), "
                             "'bone' uses bone proximity. Default: auto")
    parser.add_argument("--fit", type=float, default=0.85,
                        help="Scale multiplier applied after auto-alignment. "
                             "Lower = tighter fit. Default: 0.85")
    parser.add_argument("--no-align", action="store_true",
                        help="Skip auto-alignment. Use when the target mesh is "
                             "already in the correct coordinate space.")
    parser.add_argument("--reference", default=None,
                        help="Reference GLB with correct position/scale (e.g. the "
                             "original custom mesh before Meshy texturing). The target "
                             "is aligned to this instead of the source shell.")
    return parser.parse_args(argv)


def find_mesh_objects(objects):
    return [o for o in objects if o.type == "MESH"]


def find_armature(objects):
    for o in objects:
        if o.type == "ARMATURE":
            return o
    return None


def import_glb(filepath):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(filepath))
    after = set(bpy.data.objects)
    return list(after - before)


def pick_largest_mesh(objects, label=""):
    meshes = find_mesh_objects(objects)
    if not meshes:
        raise RuntimeError(f"No mesh found in {label}")
    for m in meshes:
        print(f"  [{label}] mesh: {m.name}, "
              f"{len(m.data.vertices)} verts, "
              f"{len(m.data.polygons)} faces, "
              f"{len(m.vertex_groups)} vgroups")
    meshes.sort(key=lambda m: len(m.data.vertices), reverse=True)
    chosen = meshes[0]
    print(f"  -> Using: {chosen.name} ({len(chosen.data.vertices)} verts)")
    return chosen


def get_world_bounds(mesh_obj):
    verts = [mesh_obj.matrix_world @ Vector(v) for v in mesh_obj.bound_box]
    mins = Vector((min(v[i] for v in verts) for i in range(3)))
    maxs = Vector((max(v[i] for v in verts) for i in range(3)))
    center = (mins + maxs) / 2
    size = maxs - mins
    return mins, maxs, center, size


def point_to_segment_dist(point, seg_a, seg_b):
    """Shortest distance from a point to a line segment."""
    ab = seg_b - seg_a
    ap = point - seg_a
    t = ap.dot(ab) / max(ab.dot(ab), 1e-12)
    t = max(0.0, min(1.0, t))
    closest = seg_a + ab * t
    return (point - closest).length


def get_significant_bones(source_mesh, threshold=0.1):
    """Return the set of bone names that carry significant weight in the source mesh.

    Sums total vertex weight per group across all vertices. Only bones
    with total weight above threshold (relative to max) are returned.
    """
    totals = {}
    for vg in source_mesh.vertex_groups:
        totals[vg.name] = 0.0
    for vert in source_mesh.data.vertices:
        for g in vert.groups:
            vg = source_mesh.vertex_groups[g.group]
            totals[vg.name] = totals.get(vg.name, 0.0) + g.weight
    if not totals:
        return set()
    max_total = max(totals.values()) if totals else 1.0
    significant = {name for name, total in totals.items()
                   if total > max_total * threshold}
    print(f"  Significant bones ({len(significant)}/{len(totals)}): "
          f"{sorted(significant)}")
    return significant


def assign_bone_proximity_weights(target_mesh, armature, max_influences=4, falloff=2.0,
                                  bone_filter=None):
    """Assign vertex weights based on distance to bone segments.

    For each vertex, computes distances to every deform bone and assigns
    weights to the closest ones using inverse-distance weighting. This
    produces smooth, natural gradients regardless of source mesh topology.

    bone_filter: optional set of bone names to include. If provided, only
    these bones participate in the proximity calculation (excludes fingers,
    toes, face, etc.).
    """
    arm_matrix = armature.matrix_world
    mesh_matrix = target_mesh.matrix_world

    bone_data = []
    for bone in armature.data.bones:
        if bone_filter and bone.name not in bone_filter:
            continue
        head_world = arm_matrix @ bone.head_local
        tail_world = arm_matrix @ bone.tail_local
        bone_data.append((bone.name, head_world, tail_world))

    if not bone_data:
        print("  WARNING: No bones found in armature after filtering")
        return

    for vg in target_mesh.vertex_groups:
        target_mesh.vertex_groups.remove(vg)

    groups = {}
    for bname, _, _ in bone_data:
        groups[bname] = target_mesh.vertex_groups.new(name=bname)

    mesh = target_mesh.data
    vert_count = len(mesh.vertices)

    for i, vert in enumerate(mesh.vertices):
        v_world = mesh_matrix @ vert.co

        dists = []
        for bname, head, tail in bone_data:
            d = point_to_segment_dist(v_world, head, tail)
            dists.append((d, bname))
        dists.sort(key=lambda x: x[0])

        top = dists[:max_influences]
        inv_dists = []
        for d, bname in top:
            inv_dists.append((1.0 / max(d, 1e-6) ** falloff, bname))

        total = sum(w for w, _ in inv_dists)
        if total < 1e-12:
            groups[top[0][1]].add([i], 1.0, "REPLACE")
            continue

        assigned = []
        for w, bname in inv_dists:
            nw = w / total
            if nw > 0.01:
                groups[bname].add([i], nw, "REPLACE")
                assigned.append((bname, round(nw, 4)))

    print(f"  Bone-proximity weights assigned: {len(bone_data)} bones, "
          f"{vert_count} verts, max {max_influences} influences, falloff {falloff}")


def align_to_reference(target_mesh, ref_mesh):
    """Align target to a reference mesh with identical geometry but different position/scale.

    Used when Meshy (or similar) re-exports the same geometry at a new origin.
    Matches the bounding box exactly since the shapes are the same.
    """
    r_min, r_max, r_center, r_size = get_world_bounds(ref_mesh)
    t_min, t_max, t_center, t_size = get_world_bounds(target_mesh)

    r_largest = max(r_size.x, r_size.y, r_size.z)
    t_largest = max(t_size.x, t_size.y, t_size.z)

    if t_largest < 1e-6:
        print("  WARNING: Target has zero size, skipping alignment")
        return

    scale_factor = r_largest / t_largest
    print(f"  Reference align: scale {scale_factor:.4f}x")
    target_mesh.scale *= scale_factor
    bpy.context.view_layer.update()

    _, _, new_t_center, _ = get_world_bounds(target_mesh)
    offset = r_center - new_t_center
    target_mesh.location += offset
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action="DESELECT")
    target_mesh.select_set(True)
    bpy.context.view_layer.objects.active = target_mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print(f"  Aligned to reference (applied transforms)")


def align_target_to_source(target_mesh, source_mesh, fit=0.85):
    """Scale and translate target to overlap source's bounding box.

    Aligns the TOP of the bounding boxes (shoulder line) instead of centers,
    so meshes with extra lower geometry (skirts) hang naturally below.
    The fit parameter (0-1) shrinks the result for a tighter fit.
    """
    s_min, s_max, s_center, s_size = get_world_bounds(source_mesh)
    t_min, t_max, t_center, t_size = get_world_bounds(target_mesh)

    s_largest = max(s_size.x, s_size.y, s_size.z)
    t_largest = max(t_size.x, t_size.y, t_size.z)

    if t_largest < 1e-6:
        print("  WARNING: Target has zero size, skipping alignment")
        return

    scale_factor = (s_largest / t_largest) * fit
    print(f"  Align: scale {scale_factor:.4f}x (fit={fit})")
    target_mesh.scale *= scale_factor
    bpy.context.view_layer.update()

    _, new_t_max, _, _ = get_world_bounds(target_mesh)
    offset = Vector((
        s_center.x - ((get_world_bounds(target_mesh)[0].x + new_t_max.x) / 2),
        s_center.y - ((get_world_bounds(target_mesh)[0].y + new_t_max.y) / 2),
        s_max.z - new_t_max.z,
    ))
    target_mesh.location += offset
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action="DESELECT")
    target_mesh.select_set(True)
    bpy.context.view_layer.objects.active = target_mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    print(f"  Aligned target to source (top-aligned, applied transforms)")


def main():
    args = get_args()

    bpy.ops.wm.read_factory_settings(use_empty=True)

    # --- Import source shell (Y-up GLB with correct armature + weights) ---
    print(f"Importing source: {args.source}")
    source_objects = import_glb(args.source)
    source_mesh = pick_largest_mesh(source_objects, "source")
    source_armature = find_armature(source_objects)
    if not source_armature:
        raise RuntimeError("No armature in source")
    print(f"  Source armature: {source_armature.name}, "
          f"{len(source_armature.data.bones)} bones")

    # --- Import target (user-edited Y-up GLB) ---
    print(f"Importing target: {args.target}")
    target_objects = import_glb(args.target)
    target_mesh = pick_largest_mesh(target_objects, "target")

    # --- Align target mesh ---
    if args.no_align:
        print("  Skipping alignment (--no-align)")
    elif args.reference:
        print(f"Importing reference: {args.reference}")
        ref_objects = import_glb(args.reference)
        ref_mesh = pick_largest_mesh(ref_objects, "reference")
        print("  Aligning target to reference mesh (original positioned mesh)")
        align_to_reference(target_mesh, ref_mesh)
    else:
        s_min, s_max, s_center, s_size = get_world_bounds(source_mesh)
        t_min, t_max, t_center, t_size = get_world_bounds(target_mesh)
        dist = (s_center - t_center).length
        s_largest = max(s_size.x, s_size.y, s_size.z)
        if dist > s_largest * 0.3:
            print(f"  Target center offset from source by {dist:.4f} — aligning")
            align_target_to_source(target_mesh, source_mesh, fit=args.fit)
        else:
            print(f"  Target already aligned (offset {dist:.4f})")

    # --- Transfer weights from source to target ---
    vg_before = len(target_mesh.vertex_groups)

    if args.method == "auto":
        print("  Using automatic weights (bone heat diffusion)")
        # Clean mesh geometry for better heat diffusion results
        bpy.ops.object.select_all(action="DESELECT")
        target_mesh.select_set(True)
        bpy.context.view_layer.objects.active = target_mesh
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.0001)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.mesh.delete_loose()
        bpy.ops.object.mode_set(mode="OBJECT")
        print(f"  Cleaned mesh: {len(target_mesh.data.vertices)} verts, "
              f"{len(target_mesh.data.polygons)} faces")

        # Clear any existing parent/armature
        bpy.ops.object.select_all(action="DESELECT")
        target_mesh.select_set(True)
        bpy.context.view_layer.objects.active = target_mesh
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        for mod in list(target_mesh.modifiers):
            if mod.type == "ARMATURE":
                target_mesh.modifiers.remove(mod)
        for vg in list(target_mesh.vertex_groups):
            target_mesh.vertex_groups.remove(vg)

        # Parent with automatic weights — Blender's heat diffusion
        bpy.ops.object.select_all(action="DESELECT")
        target_mesh.select_set(True)
        source_armature.select_set(True)
        bpy.context.view_layer.objects.active = source_armature
        result = bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        print(f"  parent_set result: {result}")

        # Check if heat diffusion actually assigned weights
        has_weights = False
        for v in target_mesh.data.vertices[:100]:
            if any(g.weight > 0.01 for g in v.groups):
                has_weights = True
                break

        if not has_weights:
            print("  WARNING: Heat diffusion failed — falling back to filtered bone proximity")
            # Clear the empty vertex groups from failed auto
            for vg in list(target_mesh.vertex_groups):
                target_mesh.vertex_groups.remove(vg)
            # Remove the armature modifier/parent added by parent_set
            bpy.ops.object.select_all(action="DESELECT")
            target_mesh.select_set(True)
            bpy.context.view_layer.objects.active = target_mesh
            bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
            for mod in list(target_mesh.modifiers):
                if mod.type == "ARMATURE":
                    target_mesh.modifiers.remove(mod)
            sig_bones = get_significant_bones(source_mesh)
            assign_bone_proximity_weights(target_mesh, source_armature,
                                          max_influences=6, falloff=1.5,
                                          bone_filter=sig_bones if sig_bones else None)
            # Reparent manually
            target_mesh.parent = source_armature
            target_mesh.parent_type = "OBJECT"
            target_mesh.matrix_parent_inverse = source_armature.matrix_world.inverted()
            arm_mod = target_mesh.modifiers.new("Armature", type="ARMATURE")
            arm_mod.object = source_armature
            arm_mod.use_vertex_groups = True

    elif args.method == "surface":
        print("  Using surface (Data Transfer) weight mapping")
        # Clean mesh first
        bpy.ops.object.select_all(action="DESELECT")
        target_mesh.select_set(True)
        bpy.context.view_layer.objects.active = target_mesh
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.0001)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.mesh.delete_loose()
        bpy.ops.object.mode_set(mode="OBJECT")
        print(f"  Cleaned mesh: {len(target_mesh.data.vertices)} verts, "
              f"{len(target_mesh.data.polygons)} faces")

        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = target_mesh
        target_mesh.select_set(True)

        dt_mod = target_mesh.modifiers.new("WeightTransfer", type="DATA_TRANSFER")
        dt_mod.object = source_mesh
        dt_mod.use_vert_data = True
        dt_mod.data_types_verts = {"VGROUP_WEIGHTS"}
        dt_mod.vert_mapping = "POLYINTERP_NEAREST"

        bpy.ops.object.datalayout_transfer(modifier=dt_mod.name)
        bpy.ops.object.modifier_apply(modifier=dt_mod.name)

        bpy.ops.object.select_all(action="DESELECT")
        target_mesh.select_set(True)
        bpy.context.view_layer.objects.active = target_mesh
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        for mod in list(target_mesh.modifiers):
            if mod.type == "ARMATURE":
                target_mesh.modifiers.remove(mod)
        target_mesh.parent = source_armature
        target_mesh.parent_type = "OBJECT"
        target_mesh.matrix_parent_inverse = source_armature.matrix_world.inverted()
        arm_mod = target_mesh.modifiers.new("Armature", type="ARMATURE")
        arm_mod.object = source_armature
        arm_mod.use_vertex_groups = True
    else:
        print("  Using bone-proximity weight mapping")
        sig_bones = get_significant_bones(source_mesh)
        assign_bone_proximity_weights(target_mesh, source_armature,
                                      bone_filter=sig_bones if sig_bones else None)

        bpy.ops.object.select_all(action="DESELECT")
        target_mesh.select_set(True)
        bpy.context.view_layer.objects.active = target_mesh
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
        for mod in list(target_mesh.modifiers):
            if mod.type == "ARMATURE":
                target_mesh.modifiers.remove(mod)
        target_mesh.parent = source_armature
        target_mesh.parent_type = "OBJECT"
        target_mesh.matrix_parent_inverse = source_armature.matrix_world.inverted()
        arm_mod = target_mesh.modifiers.new("Armature", type="ARMATURE")
        arm_mod.object = source_armature
        arm_mod.use_vertex_groups = True

    vg_after = len(target_mesh.vertex_groups)
    print(f"  Vertex groups: {vg_before} -> {vg_after}")
    print(f"  Parented to armature: {source_armature.name}")

    # --- Hide everything except source armature + target mesh ---
    for obj in bpy.data.objects:
        obj.select_set(False)
        obj.hide_set(True)
        obj.hide_render = True

    source_armature.hide_set(False)
    source_armature.select_set(True)
    target_mesh.hide_set(False)
    target_mesh.select_set(True)
    bpy.context.view_layer.objects.active = source_armature

    # Export with Y-up to match shell format (body_shell_extractor uses yup=True)
    print(f"Exporting to: {args.output}")
    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(args.output),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
    )

    print("Done!")


if __name__ == "__main__":
    main()
