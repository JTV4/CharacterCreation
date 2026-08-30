"""
1000×1000 idle portraits of the five chromatic dragons.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python render_dragon_portraits.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT, "viewer/public/buildings")
OUT_DIR = os.path.expanduser("~/Desktop/Models/Creatures/Dragons")
SIZE = 1000
IDLE_FRAME = 20
CAMERA_DIR = Vector((1.45, 2.25, 0.62)).normalized()
FRAME_MARGIN = 1.16

DRAGONS = (
    "GreenDragon",
    "BlueDragon",
    "RedDragon",
    "BlackDragon",
    "VioletDragon",
)


def _reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _setup_render() -> None:
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = SIZE
    scene.render.resolution_y = SIZE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.fps = 24
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 64
        if hasattr(scene.eevee, "use_gtao"):
            scene.eevee.use_gtao = True
        if hasattr(scene.eevee, "use_bloom"):
            scene.eevee.use_bloom = False
    if hasattr(scene.view_settings, "view_transform"):
        scene.view_settings.view_transform = "Filmic"
        scene.view_settings.look = "Medium High Contrast"

    world = bpy.data.worlds.new("PortraitWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.14, 0.155, 0.175, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world


def _add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(6, 8, 10))
    key = bpy.context.object
    key.rotation_euler = (math.radians(48), math.radians(-12), math.radians(-28))
    key.data.energy = 4.2
    key.data.angle = math.radians(8)

    bpy.ops.object.light_add(type="AREA", location=(-6, 3, 5))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(70), math.radians(25), math.radians(40))
    fill.data.energy = 420
    fill.data.size = 8
    fill.data.color = (0.72, 0.82, 1.0)

    bpy.ops.object.light_add(type="SUN", location=(-4, -6, 4))
    rim = bpy.context.object
    rim.rotation_euler = (math.radians(55), math.radians(35), math.radians(-150))
    rim.data.energy = 1.8
    rim.data.color = (1.0, 0.92, 0.82)


def _add_ground() -> None:
    bpy.ops.mesh.primitive_plane_add(size=28, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    mat = bpy.data.materials.new("GroundMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.11, 0.12, 0.13, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.78
    ground.data.materials.append(mat)


def _hide_fire() -> None:
    for obj in bpy.data.objects:
        name = obj.name.lower()
        if obj.type != "MESH":
            continue
        if name.startswith("icosphere") or "dragonfire" in name or name.startswith("fire"):
            obj.hide_render = True
            obj.hide_viewport = True
            continue
        mats = obj.data.materials if obj.data else []
        if any(m and "dragonfire" in (m.name or "").lower() for m in mats):
            obj.hide_render = True
            obj.hide_viewport = True


def _pose_idle() -> None:
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if arm is None:
        return
    idle = bpy.data.actions.get("idle")
    if idle is None:
        idle = next((a for a in bpy.data.actions if a.name.lower() == "idle"), None)
    if idle is None:
        return
    if arm.animation_data is None:
        arm.animation_data_create()
    for track in arm.animation_data.nla_tracks:
        track.mute = True
    arm.animation_data.action = idle
    bpy.context.scene.frame_set(IDLE_FRAME)
    bpy.context.view_layer.update()


def _mesh_objs() -> list:
    return [
        o for o in bpy.data.objects
        if o.type == "MESH"
        and o.data
        and not o.hide_render
        and o.name != "Ground"
    ]


def _world_bbox(objs) -> tuple[Vector, Vector]:
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    for obj in objs:
        ev = obj.evaluated_get(deps)
        me = ev.to_mesh()
        mw = obj.matrix_world
        for v in me.vertices:
            wv = mw @ v.co
            mn = Vector(tuple(min(mn[i], wv[i]) for i in range(3)))
            mx = Vector(tuple(max(mx[i], wv[i]) for i in range(3)))
        ev.to_mesh_clear()
    return mn, mx


def _fit_camera(objs) -> None:
    mn, mx = _world_bbox(objs)
    centre = (mn + mx) * 0.5
    # Bias look toward the head/chest so the square frame isn't all tail.
    centre = Vector((centre.x, centre.y + 0.35, centre.z + 0.08))
    corners = [
        Vector((x, y, z))
        for x in (mn.x, mx.x)
        for y in (mn.y, mx.y)
        for z in (mn.z, mx.z)
    ]

    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = 50.0
    cam.data.sensor_fit = "VERTICAL"
    cam.data.sensor_width = 36.0
    cam.data.clip_start = 0.05
    cam.data.clip_end = 80.0

    forward = -CAMERA_DIR
    world_up = Vector((0.0, 0.0, 1.0))
    right = forward.cross(world_up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up = right.cross(forward).normalized()
    half = max(
        max(abs((c - centre).dot(right)) for c in corners),
        max(abs((c - centre).dot(up)) for c in corners),
        1e-3,
    )
    fov = 2.0 * math.atan((cam.data.sensor_width * 0.5) / cam.data.lens)
    distance = (half * FRAME_MARGIN) / math.tan(fov * 0.5)
    cam.location = centre + CAMERA_DIR * distance

    target = bpy.data.objects.new("Look", None)
    target.location = centre
    bpy.context.collection.objects.link(target)
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    bpy.context.scene.camera = cam


def render_one(name: str) -> str:
    src = os.path.join(SRC_DIR, f"{name}.glb")
    out = os.path.join(OUT_DIR, f"{name}.png")
    print(f"=== {name} ===")
    _reset()
    bpy.ops.import_scene.gltf(filepath=src)
    _setup_render()
    _add_lights()
    _add_ground()
    _hide_fire()
    _pose_idle()
    meshes = _mesh_objs()
    if not meshes:
        raise RuntimeError(f"No visible mesh in {src}")
    _fit_camera(meshes)
    bpy.context.scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print(f"  -> {out}")
    return out


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in DRAGONS:
        path = os.path.join(SRC_DIR, f"{name}.glb")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        render_one(name)
    print("DONE", OUT_DIR)


if __name__ == "__main__":
    main()
