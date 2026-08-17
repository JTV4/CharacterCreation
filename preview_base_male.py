"""
preview_base_male.py
====================
Renders three preview angles of BaseMaleV2 for visual QA.

Output:
  base_male_preview_3q.png
  base_male_preview_front.png
  base_male_preview_side.png
"""

import bpy
import math
import os
from mathutils import Vector

SRC = os.path.abspath("viewer/public/models/BaseMaleV2.glb")
OUT_DIR = os.path.abspath(".")

VIEWS = {
    "3q":    Vector((1.35, -1.85, 0.55)),
    "front": Vector((0.0, -2.4, 0.45)),
    "side":  Vector((2.4, 0.0, 0.45)),
}


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1280
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.eevee.taa_render_samples = 64

    # Soft ground shadow catcher (optional plane)
    bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    mat = bpy.data.materials.new("GroundMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfDiffuse")
    bsdf.inputs["Color"].default_value = (0.12, 0.12, 0.14, 1)
    mat.node_tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    ground.data.materials.append(mat)

    # Lighting
    bpy.ops.object.light_add(type="AREA", location=(1.5, -1.8, 2.2))
    key = bpy.context.active_object
    key.data.energy = 80
    key.data.size = 2.5
    key.rotation_euler = (math.radians(55), 0, math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(-1.8, -0.5, 1.6))
    fill = bpy.context.active_object
    fill.data.energy = 30
    fill.data.size = 3.0
    fill.data.color = (0.75, 0.85, 1.0)

    bpy.ops.object.light_add(type="AREA", location=(0.2, 1.8, 2.0))
    rim = bpy.context.active_object
    rim.data.energy = 45
    rim.data.size = 2.0
    rim.data.color = (1.0, 0.95, 0.85)


def mesh_bounds():
    """World-space AABB from evaluated vertex positions (ignores rest bind quirks)."""
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.name == "Ground":
            continue
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        try:
            for v in mesh.vertices:
                w = eval_obj.matrix_world @ v.co
                mins.x = min(mins.x, w.x); mins.y = min(mins.y, w.y); mins.z = min(mins.z, w.z)
                maxs.x = max(maxs.x, w.x); maxs.y = max(maxs.y, w.y); maxs.z = max(maxs.z, w.z)
        finally:
            eval_obj.to_mesh_clear()
    center = (mins + maxs) * 0.5
    size = maxs - mins
    return center, size


def tint_skin():
    """Give the character a readable mid-tone skin material for preview."""
    mat = bpy.data.materials.new("PreviewSkin")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.76, 0.58, 0.45, 1)
        bsdf.inputs["Roughness"].default_value = 0.55
        if "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.35
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.name != "Ground":
            obj.data.materials.clear()
            obj.data.materials.append(mat)


def place_camera(cam_pos, look_at):
    bpy.ops.object.camera_add(location=cam_pos)
    cam = bpy.context.active_object
    direction = look_at - cam_pos
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50
    bpy.context.scene.camera = cam
    return cam


def main():
    reset()
    bpy.ops.import_scene.gltf(filepath=SRC)
    bpy.context.view_layer.update()
    setup_scene()
    tint_skin()

    # Armature scale-0.01 AABBs are unreliable; use known male height.
    height = 1.82
    look_at = Vector((0.0, 0.0, height * 0.52))
    print(f"Framing height={height:.3f} look_at_z={look_at.z:.3f}")

    for name, offset in VIEWS.items():
        for obj in list(bpy.data.objects):
            if obj.type == "CAMERA":
                bpy.data.objects.remove(obj, do_unlink=True)

        cam_pos = look_at + offset
        place_camera(cam_pos, look_at)

        out = os.path.join(OUT_DIR, f"base_male_preview_{name}.png")
        bpy.context.scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print(f"Wrote {out}")


if __name__ == "__main__":
    main()
