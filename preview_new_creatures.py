"""
preview_new_creatures.py
========================
3/4 + front + side stills for FrostGiant, Bear, RiftStalker, Pig
posed mid-walk, plus a walk filmstrip each.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python preview_new_creatures.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
OUT_DIR = os.path.join(ROOT, "new_creature_previews")
os.makedirs(OUT_DIR, exist_ok=True)

WIDTH, HEIGHT = 900, 720
FRAME_MARGIN = 1.28
STRIP_COUNT = 8

CREATURES = ("FrostGiant", "Bear", "RiftStalker", "Pig")

VIEWS = [
    ("3q", Vector((1.15, -1.35, 0.55)).normalized()),
    ("front", Vector((0.08, -1.00, 0.12)).normalized()),
    ("side", Vector((1.00, -0.12, 0.08)).normalized()),
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
        scene.eevee.taa_render_samples = 24

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.14, 0.16, 0.18, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world


def _add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(6, -7, 9))
    key = bpy.context.object
    key.rotation_euler = (math.radians(50), math.radians(18), math.radians(40))
    key.data.energy = 3.8

    bpy.ops.object.light_add(type="SUN", location=(-5, 3, 5))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(55), math.radians(-22), math.radians(-35))
    fill.data.energy = 1.2

    bpy.ops.object.light_add(type="SUN", location=(2, 5, 6))
    rim = bpy.context.object
    rim.rotation_euler = (math.radians(-25), math.radians(10), math.radians(170))
    rim.data.energy = 1.5


def _world_bbox(objs, frames=None):
    bpy.context.view_layer.update()
    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    scene = bpy.context.scene
    sample = frames or [scene.frame_current]
    for frame in sample:
        scene.frame_set(frame)
        deps = bpy.context.evaluated_depsgraph_get()
        for obj in objs:
            if obj.type != "MESH":
                continue
            evaluated = obj.evaluated_get(deps)
            mesh = evaluated.to_mesh()
            mw = obj.matrix_world
            for v in mesh.vertices:
                wv = mw @ v.co
                mn = Vector((min(mn[i], wv[i]) for i in range(3)))
                mx = Vector((max(mx[i], wv[i]) for i in range(3)))
            evaluated.to_mesh_clear()
    return mn, mx


def _fit_camera(objs, camera_dir: Vector, frames=None, margin: float = FRAME_MARGIN):
    mn, mx = _world_bbox(objs, frames=frames)
    centre = (mn + mx) * 0.5
    corners = [
        Vector((x, y, z))
        for x in (mn.x, mx.x)
        for y in (mn.y, mx.y)
        for z in (mn.z, mx.z)
    ]

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
    extents_up = max(abs((c - centre).dot(up)) for c in corners)
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


def _play_action(name: str):
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    action = next(
        (a for a in bpy.data.actions if a.name == name or a.name.startswith(name)),
        None,
    )
    if arm is None or action is None:
        return 1, 24
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    start = int(action.frame_range[0])
    end = int(action.frame_range[1])
    scene = bpy.context.scene
    scene.frame_start = start
    scene.frame_end = end
    return start, end


def _clear_cameras() -> None:
    for obj in list(bpy.context.scene.objects):
        if obj.type == "CAMERA" or obj.name.startswith("PreviewTarget"):
            bpy.data.objects.remove(obj, do_unlink=True)


def _strip_frames(start: int, end: int, count: int) -> list[int]:
    span = max(end - start, 1)
    return [start + round(i * span / count) for i in range(count)]


def preview_one(stem: str) -> None:
    glb = os.path.join(VIEWER_DIR, f"{stem}.glb")
    if not os.path.isfile(glb):
        raise FileNotFoundError(glb)
    print(f"\n=== {stem} ===")
    _reset()
    _setup_render()
    _add_lights()
    bpy.ops.import_scene.gltf(filepath=glb)
    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not mesh_objs:
        raise RuntimeError(f"No mesh in {stem}.glb")

    start, end = _play_action("walk")
    strip_frames = _strip_frames(start, end, STRIP_COUNT)
    bbox_frames = _strip_frames(start, end, 8)
    still_frame = strip_frames[len(strip_frames) // 4]
    print(f"  walk {start}-{end} | stills at frame {still_frame}")

    bpy.context.scene.frame_set(still_frame)
    for view_name, camera_dir in VIEWS:
        _clear_cameras()
        _fit_camera(mesh_objs, camera_dir, frames=bbox_frames)
        bpy.context.scene.frame_set(still_frame)
        out_path = os.path.join(OUT_DIR, f"{stem}_{view_name}.png")
        bpy.context.scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        print(f"WROTE: {out_path}")

    walk_dir = os.path.join(OUT_DIR, stem, "walk")
    os.makedirs(walk_dir, exist_ok=True)
    _clear_cameras()
    _fit_camera(
        mesh_objs,
        Vector((1.15, -1.35, 0.40)).normalized(),
        frames=bbox_frames,
        margin=1.32,
    )
    for i, frame in enumerate(strip_frames):
        bpy.context.scene.frame_set(frame)
        out_path = os.path.join(walk_dir, f"walk_{i:02d}_f{frame:03d}.png")
        bpy.context.scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        print(f"WROTE: {out_path} (frame {frame})")


def main() -> None:
    for stem in CREATURES:
        preview_one(stem)
    print("DONE")


if __name__ == "__main__":
    main()
