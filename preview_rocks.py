"""
preview_rocks.py
================
Group-shot preview for the rock family, plus one close-up per rock.

The group shot arranges all 4 rocks in a line along +X (Small on the
left, Huge on the right) with a 2 m human silhouette placeholder next
to Huge for scale.  Individual close-ups isolate each rock at a
consistent camera angle so the difference in point-count / jitter
across sizes is visible.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python preview_rocks.py
"""

import math
import os

import bpy
from mathutils import Vector

ROCK_NAMES = ["SmallRock", "MediumRock", "LargeRock", "HugeRock"]
ROCK_DIR   = os.path.abspath("viewer/public/buildings")

# Human-silhouette placeholder — a 0.4 × 0.3 × 1.8 m capsule-ish box
# just so viewers can eyeball how big "Huge" actually is.
HUMAN_SIZE = (0.40, 0.30, 1.80)


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

    bpy.ops.object.light_add(type="SUN", location=(0, 4, 6))
    rim = bpy.context.object
    rim.rotation_euler = (math.radians(-30), math.radians(0), math.radians(180))
    rim.data.energy = 1.5


def _add_ground():
    bpy.ops.mesh.primitive_plane_add(size=15.0, location=(0, 0, -0.001))
    plane = bpy.context.object
    plane.name = "GroundPlane"
    mat = bpy.data.materials.new("Ground")
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (0.28, 0.28, 0.30, 1.0)
        if "Roughness" in principled.inputs:
            principled.inputs["Roughness"].default_value = 1.0
    plane.data.materials.append(mat)


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
                margin: float = 1.15):
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


def _import_rock(name: str, location: tuple) -> list:
    """Import a rock GLB and return its mesh objects (moved to `location`)."""
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROCK_DIR, f"{name}.glb"))
    new_objs = [o for o in bpy.context.scene.objects if o not in before]
    for obj in new_objs:
        if obj.type == "MESH":
            obj.location = Vector(location) + obj.location
    return [o for o in new_objs if o.type == "MESH"]


def _add_human_silhouette(x: float, y: float):
    """A stubby 1.8 m stand-in figure — cyan tint so it reads as
    reference rather than "another asset"."""
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


# ── Group shot ────────────────────────────────────────────────────────────

def render_group_shot():
    _reset()
    _add_lights()
    _add_ground()

    # Layout: rocks in a row along +X, spaced to avoid overlap.
    # We size the spacing off the biggest rock's width so the row
    # never crowds.
    positions = {
        "SmallRock":   (-3.5, 0.0),
        "MediumRock":  (-2.5, 0.0),
        "LargeRock":   (-0.8, 0.0),
        "HugeRock":    ( 2.3, 0.0),
    }

    all_meshes = []
    for name in ROCK_NAMES:
        x, y = positions[name]
        all_meshes.extend(_import_rock(name, (x, y, 0.0)))

    human = _add_human_silhouette(4.7, 0.0)
    all_meshes.append(human)

    # 3/4 view from front-right, high enough to see all rock tops
    camera_dir = Vector((0.35, -1.0, 0.28)).normalized()
    _setup_render(1800, 700)
    _fit_camera(all_meshes, camera_dir, 1800, 700, margin=1.10)

    out_path = os.path.abspath("rocks_preview_group.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"WROTE: {out_path} ({os.path.getsize(out_path)} bytes)")


# ── Individual close-ups (2×2 style) ──────────────────────────────────────

def render_individual(name: str):
    _reset()
    _add_lights()
    _add_ground()

    meshes = _import_rock(name, (0, 0, 0))
    camera_dir = Vector((0.65, -0.75, 0.35)).normalized()
    _setup_render(700, 700)
    _fit_camera(meshes, camera_dir, 700, 700, margin=1.20)

    out_path = os.path.abspath(f"rock_preview_{name.lower().replace('rock', '')}.png")
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print(f"WROTE: {out_path} ({os.path.getsize(out_path)} bytes)")


def main():
    render_group_shot()
    for name in ROCK_NAMES:
        render_individual(name)


if __name__ == "__main__":
    main()
