"""Texture Baker — Transfer textures from a source model onto a body shell.

Uses Blender's Cycles "Selected to Active" bake to project a source model's
texture (e.g. from Meshy AI) onto a body shell's UV layout, producing a new
GLB with the texture embedded.

Usage
-----
    blender --background --python equipment/factory/texture_baker.py -- \\
        --source  viewer/public/equipment/Female/Upperbody/CrimsonUpperbodyF.glb \\
        --shell   viewer/public/equipment/shell_upper_body.glb \\
        --out     viewer/public/equipment/shell_upper_body_crimson.glb \\
        --resolution 2048

The output GLB contains the shell mesh + armature + baked texture, ready for
the viewer to load with the embedded material intact.
"""

import bpy
import bmesh
import sys
import os
import argparse
from mathutils import Vector


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Texture Baker")
    parser.add_argument(
        "--source", required=True,
        help="Path to source GLB with textures (e.g. Meshy export)",
    )
    parser.add_argument(
        "--shell", required=True,
        help="Path to target body shell GLB",
    )
    parser.add_argument(
        "--out", required=True,
        help="Output path for textured shell GLB",
    )
    parser.add_argument(
        "--texture-out", default=None,
        help="Optional: also save the baked texture as a standalone PNG",
    )
    parser.add_argument(
        "--resolution", type=int, default=2048,
        help="Baked texture resolution in pixels (default 2048)",
    )
    parser.add_argument(
        "--cage-extrusion", type=float, default=0.15,
        help="Ray distance for bake projection in meters (default 0.15)",
    )
    parser.add_argument(
        "--samples", type=int, default=4,
        help="Cycles bake samples (default 4, higher = smoother but slower)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def import_glb(filepath: str) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(filepath))
    after = set(bpy.data.objects)
    return list(after - before)


def collect_meshes(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    meshes: list[bpy.types.Object] = []
    visited = set()
    for obj in objects:
        for candidate in [obj] + list(obj.children_recursive):
            if candidate.type == "MESH" and candidate.name not in visited:
                meshes.append(candidate)
                visited.add(candidate.name)
    return meshes


def find_armature(objects: list[bpy.types.Object]) -> bpy.types.Object | None:
    for obj in objects:
        if obj.type == "ARMATURE":
            return obj
        for child in obj.children_recursive:
            if child.type == "ARMATURE":
                return child
    return None


def get_world_bounds(meshes: list[bpy.types.Object]) -> tuple[Vector, Vector, Vector]:
    """Return (min_corner, max_corner, center) in world space across all meshes."""
    all_min = Vector((float("inf"),) * 3)
    all_max = Vector((float("-inf"),) * 3)
    for mesh in meshes:
        for v in mesh.bound_box:
            world_v = mesh.matrix_world @ Vector(v)
            for i in range(3):
                all_min[i] = min(all_min[i], world_v[i])
                all_max[i] = max(all_max[i], world_v[i])
    center = (all_min + all_max) / 2
    return all_min, all_max, center


def align_source_to_target(
    source_meshes: list[bpy.types.Object],
    target_meshes: list[bpy.types.Object],
) -> None:
    """Scale and translate source meshes to overlap the target's bounding box."""
    src_min, src_max, src_center = get_world_bounds(source_meshes)
    tgt_min, tgt_max, tgt_center = get_world_bounds(target_meshes)

    src_size = src_max - src_min
    tgt_size = tgt_max - tgt_min

    src_largest = max(src_size.x, src_size.y, src_size.z)
    tgt_largest = max(tgt_size.x, tgt_size.y, tgt_size.z)

    if src_largest < 1e-6:
        print("  WARNING: Source mesh has zero size, skipping alignment")
        return

    scale_factor = tgt_largest / src_largest
    print(f"  Auto-align: scale {scale_factor:.4f}x, "
          f"source size {src_largest:.4f} → target size {tgt_largest:.4f}")

    for mesh in source_meshes:
        mesh.scale *= scale_factor

    bpy.context.view_layer.update()

    _, _, new_src_center = get_world_bounds(source_meshes)
    offset = tgt_center - new_src_center
    for mesh in source_meshes:
        mesh.location += offset

    bpy.context.view_layer.update()


def ensure_uv_layer(mesh_obj: bpy.types.Object) -> bool:
    """Ensure the mesh has at least one UV layer. Returns True if one was created."""
    if mesh_obj.data.uv_layers:
        return False

    print("  Shell has no UVs — adding Smart UV Project...")
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    return True


# ---------------------------------------------------------------------------
# Bake pipeline
# ---------------------------------------------------------------------------

def bake_texture(
    source_path: str,
    shell_path: str,
    output_path: str,
    texture_out: str | None,
    resolution: int,
    cage_extrusion: float,
    samples: int,
) -> str | None:
    """Run the full bake pipeline. Returns the output GLB path or None on failure."""
    print("=== Texture Baker ===")
    print(f"  Source:     {source_path}")
    print(f"  Shell:      {shell_path}")
    print(f"  Output:     {output_path}")
    print(f"  Resolution: {resolution}x{resolution}")
    print(f"  Cage:       {cage_extrusion}m")
    print(f"  Samples:    {samples}")

    # ---- Clean scene ----
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # ---- Import shell (target) ----
    print("\n--- Importing shell ---")
    shell_objects = import_glb(shell_path)
    shell_meshes = collect_meshes(shell_objects)
    shell_armature = find_armature(shell_objects)

    if not shell_meshes:
        print("ERROR: No meshes found in shell GLB")
        return None

    # Filter out debug/placeholder meshes (e.g. Icospheres)
    real_meshes = [m for m in shell_meshes if len(m.data.vertices) > 100]
    if not real_meshes:
        real_meshes = shell_meshes
    shell_mesh = max(real_meshes, key=lambda m: len(m.data.polygons))
    print(f"  Shell mesh: {shell_mesh.name} "
          f"({len(shell_mesh.data.vertices)} verts, "
          f"{len(shell_mesh.data.polygons)} faces)")

    ensure_uv_layer(shell_mesh)
    print(f"  UV layers: {len(shell_mesh.data.uv_layers)}")

    # ---- Import source (Meshy model) ----
    print("\n--- Importing source ---")
    source_objects = import_glb(source_path)
    source_meshes = collect_meshes(source_objects)

    if not source_meshes:
        print("ERROR: No meshes found in source GLB")
        return None

    total_src_verts = sum(len(m.data.vertices) for m in source_meshes)
    print(f"  Source meshes: {len(source_meshes)} "
          f"({total_src_verts} total verts)")

    has_materials = any(
        m.data.materials and any(
            mat and mat.use_nodes and
            any(n.type == "TEX_IMAGE" for n in mat.node_tree.nodes)
            for mat in m.data.materials
        )
        for m in source_meshes
    )
    if not has_materials:
        print("  WARNING: Source model has no image textures — "
              "bake will capture vertex/material colors only")

    # ---- Auto-align source to shell ----
    print("\n--- Aligning source to shell ---")
    align_source_to_target(source_meshes, shell_meshes)

    # ---- Prepare bake target material on shell ----
    print("\n--- Preparing bake target ---")
    bake_img = bpy.data.images.new(
        "bake_result", width=resolution, height=resolution, alpha=True,
    )
    bake_img.colorspace_settings.name = "sRGB"

    bake_mat = bpy.data.materials.new("baked_material")
    bake_mat.use_nodes = True
    nodes = bake_mat.node_tree.nodes
    links = bake_mat.node_tree.links

    nodes.clear()

    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    output_node = nodes.new("ShaderNodeOutputMaterial")
    output_node.location = (300, 0)
    links.new(bsdf.outputs["BSDF"], output_node.inputs["Surface"])

    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.image = bake_img
    tex_node.location = (-300, 0)
    links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

    nodes.active = tex_node

    shell_mesh.data.materials.clear()
    shell_mesh.data.materials.append(bake_mat)

    # ---- Configure Cycles bake ----
    print("\n--- Configuring Cycles ---")
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.device = "CPU"
    bpy.context.scene.cycles.samples = samples

    bpy.context.scene.render.bake.use_pass_direct = False
    bpy.context.scene.render.bake.use_pass_indirect = False
    bpy.context.scene.render.bake.use_pass_color = True
    bpy.context.scene.render.bake.use_selected_to_active = True
    bpy.context.scene.render.bake.cage_extrusion = cage_extrusion
    bpy.context.scene.render.bake.max_ray_distance = 0

    # ---- Select source → active shell and bake ----
    print("\n--- Baking ---")

    # Ensure all objects are visible and renderable
    for obj in bpy.data.objects:
        obj.hide_set(False)
        obj.hide_render = False
        obj.hide_viewport = False

    bpy.ops.object.select_all(action="DESELECT")
    for mesh in source_meshes:
        mesh.select_set(True)
    shell_mesh.select_set(True)
    bpy.context.view_layer.objects.active = shell_mesh

    bpy.ops.object.bake(type="DIFFUSE")
    print(f"  Bake complete ({resolution}x{resolution})")

    # ---- Save texture ----
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)

    tex_save_path = texture_out or os.path.join(
        out_dir, os.path.splitext(os.path.basename(output_path))[0] + "_diffuse.png",
    )
    tex_save_path = os.path.abspath(tex_save_path)
    os.makedirs(os.path.dirname(tex_save_path), exist_ok=True)

    bake_img.filepath_raw = tex_save_path
    bake_img.file_format = "PNG"
    bake_img.save()
    print(f"  Saved texture: {tex_save_path}")

    bake_img.pack()

    # ---- Clean up source objects ----
    print("\n--- Cleaning up ---")
    for obj in source_objects:
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

    for img in list(bpy.data.images):
        if img != bake_img and img.users == 0:
            bpy.data.images.remove(img)

    # ---- Export textured shell ----
    print("\n--- Exporting ---")
    bpy.ops.object.select_all(action="DESELECT")
    shell_mesh.select_set(True)
    if shell_armature:
        shell_armature.select_set(True)
        bpy.context.view_layer.objects.active = shell_armature
    else:
        bpy.context.view_layer.objects.active = shell_mesh

    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

    export_kwargs = dict(
        filepath=os.path.abspath(output_path),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_materials="EXPORT",
        export_animations=False,
        export_image_format="AUTO",
    )
    if shell_armature:
        export_kwargs["export_skins"] = True
        export_kwargs["export_all_influences"] = True
        export_kwargs["export_def_bones"] = True

    bpy.ops.export_scene.gltf(**export_kwargs)

    print(f"\n=== Done — {output_path} ===")
    return output_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    bake_texture(
        source_path=args.source,
        shell_path=args.shell,
        output_path=args.out,
        texture_out=args.texture_out,
        resolution=args.resolution,
        cage_extrusion=args.cage_extrusion,
        samples=args.samples,
    )


if __name__ == "__main__":
    main()
