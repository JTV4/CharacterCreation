"""
preview_rock_path.py
====================
Three-view preview for the rock walk path:
  - Top-down (sells the arc / spacing pattern)
  - Hero 3/4 (perspective view a level designer would recognise)
  - Walking POV (eye-level camera at the start of the path, looking
    down its length — validates the stones actually feel walkable)

Adds a 1.8 m human-silhouette placeholder next to the first stone in
the top-down / 3q shots so you can eyeball scale.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python preview_rock_path.py
"""

import math
import os

import bpy
from mathutils import Vector

GLB_PATH = os.path.abspath("viewer/public/buildings/RockPath.glb")

# Path bounds: X ≈ [-0.5, +1.6], Y ≈ [0, 5.2]
# Top-down and hero want wide letterboxes; POV is portrait.
WIDTH_WIDE,   HEIGHT_WIDE   = 1600, 800
WIDTH_HERO,   HEIGHT_HERO   = 1600, 900
WIDTH_POV,    HEIGHT_POV    = 900,  1300

FRAME_MARGIN = 1.10
HUMAN_SIZE   = (0.40, 0.30, 1.80)   # stubby stand-in figure
POV_HEIGHT   = 1.65                 # eye-level camera height above ground


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
    bg.inputs[0].default_value = (0.55, 0.72, 0.85, 1.0)  # soft sky blue
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


def _add_ground():
    # Grass-green ground — makes the stones pop and hints at a garden
    # context (which is the natural use case for a stepping-stone path).
    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(2.5, 2.5, -0.001))
    plane = bpy.context.object
    plane.name = "GroundPlane"
    mat = bpy.data.materials.new("Grass")
    mat.use_nodes = True
    p = mat.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value = (0.35, 0.48, 0.25, 1.0)
        if "Roughness" in p.inputs:
            p.inputs["Roughness"].default_value = 1.0
    plane.data.materials.append(mat)


def _add_human_silhouette(x: float, y: float) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, HUMAN_SIZE[2] / 2))
    obj = bpy.context.object
    obj.name = "HumanScale"
    obj.scale = HUMAN_SIZE
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mat = bpy.data.materials.new("HumanRef")
    mat.use_nodes = True
    p = mat.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value = (0.20, 0.55, 0.75, 1.0)
    obj.data.materials.append(mat)
    return obj


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


def _fit_camera(objs, camera_dir: Vector, width: int, height: int,
                margin: float = FRAME_MARGIN):
    mn, mx = _world_bbox(objs)
    centre = (mn + mx) * 0.5
    corners = [Vector((x, y, z))
               for x in (mn.x, mx.x)
               for y in (mn.y, mx.y)
               for z in (mn.z, mx.z)]

    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = 50.0
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
    distance = (half_extent * margin) / math.tan(fov_v * 0.5)
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


def _add_pov_camera(width: int, height: int):
    """Eye-level camera at the start of the path (y ≈ -0.6), looking
    down the +Y direction toward the far end.  A stubby wide lens
    (35 mm) suits the "person about to step" feel."""
    bpy.ops.object.camera_add(location=(0.0, -0.6, POV_HEIGHT))
    cam = bpy.context.object
    cam.data.lens = 35.0
    cam.data.sensor_width = 36.0

    # Look toward the far end of the path (y ≈ 5, ground level)
    target = bpy.data.objects.new("POVTarget", None)
    target.location = Vector((0.4, 5.0, 0.1))
    bpy.context.collection.objects.link(target)
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    bpy.context.scene.camera = cam


def main():
    print(f"Loading: {GLB_PATH}")

    # ── View 1: Top-down with human silhouette for scale ──────────────
    _reset()
    _add_lights()
    _add_ground()
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    _add_human_silhouette(-0.7, 0.0)
    all_meshes = [o for o in bpy.context.scene.objects
                  if o.type == "MESH" and o.name != "GroundPlane"]
    _setup_render(WIDTH_WIDE, HEIGHT_WIDE)
    _fit_camera(all_meshes, Vector((0.02, 0.02, 1.0)).normalized(),
                WIDTH_WIDE, HEIGHT_WIDE)
    out = os.path.abspath("rock_path_preview_top.png")
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print(f"WROTE: {out} ({os.path.getsize(out)} bytes)")

    # ── View 2: Hero 3/4 with human silhouette ────────────────────────
    _reset()
    _add_lights()
    _add_ground()
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    _add_human_silhouette(-0.7, 0.0)
    all_meshes = [o for o in bpy.context.scene.objects
                  if o.type == "MESH" and o.name != "GroundPlane"]
    _setup_render(WIDTH_HERO, HEIGHT_HERO)
    _fit_camera(all_meshes, Vector((0.55, -0.90, 0.45)).normalized(),
                WIDTH_HERO, HEIGHT_HERO)
    out = os.path.abspath("rock_path_preview_3q.png")
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print(f"WROTE: {out} ({os.path.getsize(out)} bytes)")

    # ── View 3: Eye-level walking POV (no human silhouette) ───────────
    _reset()
    _add_lights()
    _add_ground()
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    _setup_render(WIDTH_POV, HEIGHT_POV)
    _add_pov_camera(WIDTH_POV, HEIGHT_POV)
    out = os.path.abspath("rock_path_preview_pov.png")
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print(f"WROTE: {out} ({os.path.getsize(out)} bytes)")


if __name__ == "__main__":
    main()
