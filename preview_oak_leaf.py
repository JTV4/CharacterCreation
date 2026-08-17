"""
preview_oak_leaf.py
===================
Three-view preview for the large oak leaf.  Top-down shows the
silhouette (the main "is this shape actually reading as an oak
leaf?" test), the underside view proves the two-material split works
end-to-end (paler green underside vs deep green top), and a 3/4 shows
it as a scene prop from a normal camera angle.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python preview_oak_leaf.py
"""

import math
import os

import bpy
from mathutils import Vector

GLB_PATH = os.path.abspath("viewer/public/buildings/OakLeaf.glb")

# Leaf is long-and-narrow (32 cm × 15 cm); portrait frames suit it.
WIDTH_TALL, HEIGHT_TALL = 700, 1100
WIDTH_SQ,   HEIGHT_SQ   = 900, 900

VIEWS = [
    # Straight top-down: pure silhouette, shows the lobe pattern.
    ("oak_leaf_preview_top.png",
     Vector((0.02, 0.02, 1.00)).normalized(), WIDTH_TALL, HEIGHT_TALL),
    # Straight underside: same silhouette, paler colour proves the
    # two-material split.  Camera looks UP through Z axis.
    ("oak_leaf_preview_underside.png",
     Vector((0.02, 0.02, -1.00)).normalized(), WIDTH_TALL, HEIGHT_TALL),
    # 3/4 low camera: "as-a-prop" view.
    ("oak_leaf_preview_3q.png",
     Vector((0.55, -0.75, 0.40)).normalized(), WIDTH_SQ, HEIGHT_SQ),
]
FRAME_MARGIN = 1.15


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _setup_render(width: int, height: int):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
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

    # Extra fill from BELOW for the underside view so the shaded face
    # actually gets lit — otherwise it renders nearly black.
    bpy.ops.object.light_add(type="SUN", location=(0, 0, -3))
    below = bpy.context.object
    below.rotation_euler = (math.radians(180), 0, 0)
    below.data.energy = 2.5


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


def _fit_camera(objs, camera_dir: Vector, width: int, height: int):
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

    aspect = width / height
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
    _add_lights()

    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not mesh_objs:
        raise RuntimeError("No mesh found in imported GLB")

    for out_name, camera_dir, w, h in VIEWS:
        for obj in list(bpy.context.scene.objects):
            if obj.type == "CAMERA" or obj.name.startswith("PreviewTarget"):
                bpy.data.objects.remove(obj, do_unlink=True)

        _setup_render(w, h)
        _fit_camera(mesh_objs, camera_dir, w, h)
        out_path = os.path.abspath(out_name)
        bpy.context.scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        print(f"WROTE: {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    main()
