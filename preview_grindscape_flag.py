"""
preview_grindscape_flag.py
==========================
Still previews of GrindScapeFlag.glb: 3/4, front (flag face), and side,
all posed mid-wave so the billow reads.

Also renders a filmstrip of frames spread evenly across the wind loop
into `flag_wave_frames/` — a single still can't show whether the ripple
actually travels, which is the whole point of the clip.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python preview_grindscape_flag.py
"""

import math
import os

import bpy
from mathutils import Vector

GLB_PATH = os.path.abspath("viewer/public/buildings/GrindScapeFlag.glb")

WIDTH, HEIGHT = 1000, 900
VIEWS = [
    ("grindscape_flag_preview_3q.png", Vector((1.25, -1.45, 0.48)).normalized()),
    ("grindscape_flag_preview_front.png", Vector((0.22, -1.00, 0.10)).normalized()),
    ("grindscape_flag_preview_side.png", Vector((1.00, 0.22, 0.08)).normalized()),
]
FRAME_MARGIN = 1.18

# Filmstrip across the wind loop, rendered from the 3/4 angle.  Framed on
# the cloth alone — including the pedestal shrinks the flag to a thumbnail
# and the ripple becomes impossible to read.
STRIP_DIR = "flag_wave_frames"
STRIP_COUNT = 8
STRIP_DIR_VEC = Vector((1.25, -1.45, 0.30)).normalized()
STRIP_MARGIN = 1.30


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
    bg.inputs[0].default_value = (0.14, 0.15, 0.18, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world


def _add_lights():
    bpy.ops.object.light_add(type="SUN", location=(6, -7, 9))
    key = bpy.context.object
    key.rotation_euler = (math.radians(50), math.radians(18), math.radians(40))
    key.data.energy = 3.8

    bpy.ops.object.light_add(type="SUN", location=(-5, 3, 5))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(55), math.radians(-22), math.radians(-35))
    fill.data.energy = 1.15

    bpy.ops.object.light_add(type="SUN", location=(2, 5, 6))
    rim = bpy.context.object
    rim.rotation_euler = (math.radians(-25), math.radians(10), math.radians(170))
    rim.data.energy = 1.6


def _world_bbox(objs, frames=None):
    """Union of evaluated (posed) bounds over `frames`.

    Rest-pose bounds would frame the cloth too tightly — the billow
    swings well past where the unposed mesh sits, so the fly edge would
    clip out of shot on part of the loop.
    """
    scene = bpy.context.scene
    restore = scene.frame_current
    frames = list(frames) if frames else [restore]

    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    for frame in frames:
        scene.frame_set(frame)
        deps = bpy.context.evaluated_depsgraph_get()
        for obj in objs:
            if obj.type != "MESH" or obj.data is None:
                continue
            evaluated = obj.evaluated_get(deps)
            mesh = evaluated.to_mesh()
            mw = obj.matrix_world
            for v in mesh.vertices:
                wv = mw @ v.co
                mn = Vector(min(mn[i], wv[i]) for i in range(3))
                mx = Vector(max(mx[i], wv[i]) for i in range(3))
            evaluated.to_mesh_clear()

    scene.frame_set(restore)
    return mn, mx


def _fit_camera(objs, camera_dir: Vector, frames=None, margin=None, bias=0.58):
    margin = FRAME_MARGIN if margin is None else margin
    mn, mx = _world_bbox(objs, frames=frames)
    centre = (mn + mx) * 0.5
    # Bias the framing toward the upper half so the flag (not just the
    # brick plinth) sits in the shot.
    centre = Vector((centre.x, centre.y, mn.z + (mx.z - mn.z) * bias))
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


def _clip_range():
    scene = bpy.context.scene
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    action = arm.animation_data.action if arm and arm.animation_data else None
    if action:
        start = int(action.frame_range[0])
        end = int(action.frame_range[1])
    else:
        start, end = 1, 96
    scene.frame_start = start
    scene.frame_end = end
    return start, end


def _clear_cameras():
    for obj in list(bpy.context.scene.objects):
        if obj.type == "CAMERA" or obj.name.startswith("PreviewTarget"):
            bpy.data.objects.remove(obj, do_unlink=True)


def _strip_frames(start: int, end: int, count: int):
    # Last frame duplicates the first (loop wrap), so stop short of it.
    span = max(end - start, 1)
    return [start + round(i * span / count) for i in range(count)]


def main():
    print(f"Loading: {GLB_PATH}")
    _reset()
    _setup_render()
    _add_lights()

    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not mesh_objs:
        raise RuntimeError("No mesh found in imported GLB")

    start, end = _clip_range()
    strip_frames = _strip_frames(start, end, STRIP_COUNT)
    # Frame every shot against the full swing of the loop.
    bbox_frames = _strip_frames(start, end, 12)
    still_frame = strip_frames[len(strip_frames) // 4]
    print(f"  clip {start}-{end} | stills at frame {still_frame}")

    bpy.context.scene.frame_set(still_frame)
    for out_name, camera_dir in VIEWS:
        _clear_cameras()
        _fit_camera(mesh_objs, camera_dir, frames=bbox_frames)
        bpy.context.scene.frame_set(still_frame)
        out_path = os.path.abspath(out_name)
        bpy.context.scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        print(f"WROTE: {out_path} ({os.path.getsize(out_path)} bytes)")

    # Filmstrip: one fixed camera on the cloth, frames spread across the loop.
    strip_dir = os.path.abspath(STRIP_DIR)
    os.makedirs(strip_dir, exist_ok=True)
    cloth = [o for o in mesh_objs if "cloth" in o.name.lower()] or mesh_objs
    _clear_cameras()
    _fit_camera(
        cloth,
        STRIP_DIR_VEC,
        frames=bbox_frames,
        margin=STRIP_MARGIN,
        bias=0.5,
    )
    for i, frame in enumerate(strip_frames):
        bpy.context.scene.frame_set(frame)
        out_path = os.path.join(strip_dir, f"wave_{i:02d}_f{frame:03d}.png")
        bpy.context.scene.render.filepath = out_path
        bpy.ops.render.render(write_still=True)
        print(f"WROTE: {out_path} (frame {frame})")


if __name__ == "__main__":
    main()
