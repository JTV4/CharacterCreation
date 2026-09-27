"""
preview_pioneer_male.py
=======================
3/4, front, and side stills of PioneerMale.glb posed on idle.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python preview_pioneer_male.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
GLB_PATH = os.path.join(ROOT, "viewer/public/models/PioneerMale.glb")
OUT_DIR = os.path.join(ROOT, "pioneer_male_previews")
os.makedirs(OUT_DIR, exist_ok=True)

WIDTH, HEIGHT = 720, 960
FRAME_MARGIN = 1.22

VIEWS = [
    ("3q", Vector((1.15, -1.45, 0.42)).normalized()),
    ("front", Vector((0.04, -1.00, 0.10)).normalized()),
    ("side", Vector((1.00, -0.08, 0.08)).normalized()),
    ("face", Vector((0.15, -1.00, 0.18)).normalized()),
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
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 32
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.15, 0.16, 0.18, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world


def _add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(5, -6, 8))
    key = bpy.context.object
    key.rotation_euler = (math.radians(50), math.radians(16), math.radians(30))
    key.data.energy = 3.4
    bpy.ops.object.light_add(type="SUN", location=(-5, 3, 4))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(55), math.radians(-20), math.radians(-35))
    fill.data.energy = 1.1


def _add_ground() -> None:
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    mat = bpy.data.materials.new("Ground")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.20, 0.18, 0.15, 1.0)
    ground.data.materials.append(mat)


def _world_bbox(objs):
    bpy.context.view_layer.update()
    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in objs:
        if obj.type != "MESH":
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
    if zoom < 1.0:
        center = Vector((center.x, center.y, mx.z - 0.18))
    size = (mx - mn).length
    cam = bpy.context.scene.camera
    cam.location = center + camera_dir.normalized() * (size * FRAME_MARGIN * 1.25 * zoom)
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50


def _pose_clip(name: str, frame: int) -> None:
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        return
    arm = arms[0]
    action = bpy.data.actions.get(name)
    if action is None:
        for act in bpy.data.actions:
            if act.name.lower().startswith(name):
                action = act
                break
    if action is None:
        print(f"  WARN: no {name} action")
        return
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()


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
        zoom = 0.42 if name == "face" else 1.0
        _fit_camera(meshes, direction, zoom=zoom)
        path = os.path.join(OUT_DIR, f"pioneer_male_{name}.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("wrote", path)
    _pose_clip("idle", 1)
    _fit_camera(meshes, VIEWS[0][1], zoom=1.0)
    idle_path = os.path.join(OUT_DIR, "pioneer_male_idle.png")
    bpy.context.scene.render.filepath = idle_path
    bpy.ops.render.render(write_still=True)
    print("wrote", idle_path)
    _pose_clip("walk", 9)
    _fit_camera(meshes, VIEWS[0][1], zoom=1.0)
    walk_path = os.path.join(OUT_DIR, "pioneer_male_walk.png")
    bpy.context.scene.render.filepath = walk_path
    bpy.ops.render.render(write_still=True)
    print("wrote", walk_path)

    # Left-hand close-up in T-pose bind (same view as the Avatar inspector).
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if arms and arms[0].animation_data:
        arms[0].animation_data.action = None
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    hand_pts = []
    deps = bpy.context.evaluated_depsgraph_get()
    hand_meshes = [o for o in meshes if "hand" in o.name.lower()] or meshes
    for obj in hand_meshes:
        ev = obj.evaluated_get(deps)
        for v in ev.data.vertices:
            w = ev.matrix_world @ v.co
            if w.x > 0.70:
                hand_pts.append(w)
    if hand_pts:
        hand_center = sum(hand_pts, Vector()) / len(hand_pts)
    else:
        hand_center = Vector((0.30, 0.02, 0.80))
    cam = bpy.context.scene.camera
    cam.location = hand_center + Vector((0.06, -0.28, 0.08))
    cam.rotation_euler = (hand_center - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 60
    hand_path = os.path.join(OUT_DIR, "pioneer_male_hand.png")
    bpy.context.scene.render.filepath = hand_path
    bpy.ops.render.render(write_still=True)
    print("wrote", hand_path)
    print("DONE")


if __name__ == "__main__":
    main()
