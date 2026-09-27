"""
preview_storehouse.py
=====================
3/4, front, and side stills of Storehouse.glb.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python preview_storehouse.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
GLB_PATH = os.path.join(ROOT, "viewer/public/buildings/Storehouse.glb")
OUT_DIR = os.path.join(ROOT, "storehouse_previews")
os.makedirs(OUT_DIR, exist_ok=True)

WIDTH, HEIGHT = 960, 720
FRAME_MARGIN = 1.22

# Door / half-timber facade faces +Y, so cameras sit on +Y looking back at origin.
VIEWS = [
    ("3q", Vector((1.20, 1.40, 0.62)).normalized()),
    ("front", Vector((0.06, 1.00, 0.16)).normalized()),
    ("side", Vector((1.00, 0.14, 0.10)).normalized()),
    ("close", Vector((0.45, 1.18, 0.24)).normalized()),
]


def _reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _setup_render() -> None:
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = WIDTH
    scene.render.resolution_y = HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 32

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.15, 0.16, 0.18, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world


def _add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(6, -7, 9))
    key = bpy.context.object
    key.rotation_euler = (math.radians(50), math.radians(16), math.radians(36))
    key.data.energy = 3.6

    bpy.ops.object.light_add(type="SUN", location=(-5, 3, 5))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(55), math.radians(-20), math.radians(-35))
    fill.data.energy = 1.15

    bpy.ops.object.light_add(type="SUN", location=(2, 5, 6))
    rim = bpy.context.object
    rim.rotation_euler = (math.radians(-22), math.radians(8), math.radians(170))
    rim.data.energy = 1.35


def _add_ground() -> None:
    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.object
    ground.name = "Ground"
    mat = bpy.data.materials.new("GroundDirt")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.22, 0.20, 0.16, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.94
    ground.data.materials.append(mat)


def _world_bbox(objs) -> tuple[Vector, Vector]:
    bpy.context.view_layer.update()
    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in objs:
        if obj.type != "MESH" or obj.data is None:
            continue
        ev = obj.evaluated_get(deps)
        for v in ev.data.vertices:
            wv = ev.matrix_world @ v.co
            mn = Vector(min(mn[i], wv[i]) for i in range(3))
            mx = Vector(max(mx[i], wv[i]) for i in range(3))
    return mn, mx


def _fit_camera(objs, camera_dir: Vector, zoom: float = 1.0) -> None:
    mn, mx = _world_bbox(objs)
    center = (mn + mx) * 0.5
    size = (mx - mn).length
    cam = bpy.context.scene.camera
    cam.location = center + camera_dir.normalized() * (size * FRAME_MARGIN * 1.32 * zoom)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50


def main() -> None:
    if not os.path.isfile(GLB_PATH):
        raise FileNotFoundError(GLB_PATH)
    _reset()
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    _setup_render()
    _add_lights()
    _add_ground()
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name != "Ground"]
    for name, direction in VIEWS:
        zoom = 0.62 if name == "close" else 1.0
        _fit_camera(meshes, direction, zoom=zoom)
        path = os.path.join(OUT_DIR, f"storehouse_{name}.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("wrote", path)
    print("DONE — storehouse previews")


if __name__ == "__main__":
    main()
