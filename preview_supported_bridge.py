"""
preview_supported_bridge.py
===========================
Two-view preview render for the supported (piered + elevated) arched
bridge — sibling of `preview_bridge.py`.  Pure side profile shows off
the 3 pier pairs + arch silhouette; 3/4 view shows the deck depth.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python preview_supported_bridge.py
"""

import math
import os

import bpy
from mathutils import Vector

GLB_PATH = os.path.abspath("viewer/public/buildings/SupportedBridge.glb")

WIDTH, HEIGHT = 1280, 620   # slightly taller frame — asset now reaches z≈4.6
VIEWS = [
    ("supported_bridge_preview_side.png",
     Vector((1.00, 0.00, 0.08)).normalized()),
    ("supported_bridge_preview_3q.png",
     Vector((0.90, 0.70, 0.55)).normalized()),
]
FRAME_MARGIN = 1.15


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = WIDTH
    scene.render.resolution_y = HEIGHT
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.eevee.taa_render_samples = 32

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.15, 0.17, 0.20, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world


def _add_lights():
    bpy.ops.object.light_add(type="SUN", location=(5, -6, 8))
    key = bpy.context.object
    key.rotation_euler = (math.radians(50), math.radians(20), math.radians(35))
    key.data.energy = 3.5

    bpy.ops.object.light_add(type="SUN", location=(-5, 3, 4))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(60), math.radians(-25), math.radians(-40))
    fill.data.energy = 1.2

    bpy.ops.object.light_add(type="SUN", location=(0, 4, 6))
    rim = bpy.context.object
    rim.rotation_euler = (math.radians(-30), math.radians(0), math.radians(180))
    rim.data.energy = 1.5


def _world_bbox(objs):
    bpy.context.view_layer.update()
    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    for obj in objs:
        if obj.type != "MESH" or obj.data is None:
            continue
        mw = obj.matrix_world
        for v in obj.data.vertices:
            wv = mw @ v.co
            mn = Vector(min(mn[i], wv[i]) for i in range(3))
            mx = Vector(max(mx[i], wv[i]) for i in range(3))
    return mn, mx


def _fit_camera(objs, camera_dir: Vector):
    mn, mx = _world_bbox(objs)
    centre = (mn + mx) * 0.5
    corners = [Vector((x, y, z))
               for x in (mn.x, mx.x)
               for y in (mn.y, mx.y)
               for z in (mn.z, mx.z)]

    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = 50.0
    cam.data.sensor_fit = "AUTO"
    cam.data.sensor_width = 36.0

    forward = -camera_dir
    world_up = Vector((0.0, 0.0, 1.0))
    right = forward.cross(world_up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up = right.cross(forward).normalized()

    aspect = WIDTH / HEIGHT
    extents_right = max(abs((c - centre).dot(right)) for c in corners)
    extents_up    = max(abs((c - centre).dot(up))    for c in corners)
    half_extent = max(extents_right / aspect, extents_up)

    fov_v = 2.0 * math.atan((cam.data.sensor_width * 0.5 / aspect) / cam.data.lens)
    distance = (half_extent * FRAME_MARGIN) / math.tan(fov_v * 0.5)
    cam.location = centre + camera_dir * distance

    target = bpy.data.objects.new("PreviewTarget", None)
    target.location = centre
    bpy.context.collection.objects.link(target)
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    bpy.context.scene.camera = cam
    return cam


def main():
    print(f"Loading: {GLB_PATH}")
    _reset()
    _setup_render()
    _add_lights()

    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not mesh_objs:
        raise RuntimeError("No mesh found in imported GLB")

    for out_name, camera_dir in VIEWS:
        for obj in list(bpy.context.scene.objects):
            if obj.type == "CAMERA" or obj.name.startswith("PreviewTarget"):
                bpy.data.objects.remove(obj, do_unlink=True)

        _fit_camera(mesh_objs, camera_dir)
        out_path = os.path.abspath(out_name)
        bpy.context.scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        print(f"WROTE: {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    main()
