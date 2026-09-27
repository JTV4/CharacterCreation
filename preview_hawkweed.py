"""
preview_hawkweed.py
===================
Still previews of Hawkweed.glb at each growth hold, plus a short
Increase3 filmstrip. A 1×1 plot square is drawn at z=0 for scale.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python preview_hawkweed.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
GLB_PATH = os.path.join(ROOT, "viewer/public/buildings/Hawkweed.glb")
STRIP_DIR = os.path.join(ROOT, "hawkweed_frames")
os.makedirs(STRIP_DIR, exist_ok=True)

WIDTH, HEIGHT = 900, 900
FRAME_MARGIN = 1.28
STRIP_COUNT = 8

STAGES = [
    ("idle", 1, "hawkweed_preview_idle.png"),
    ("Increase1", 40, "hawkweed_preview_increase1.png"),
    ("Increase2", 40, "hawkweed_preview_increase2.png"),
    ("Increase3", 40, "hawkweed_preview_increase3.png"),
]


def _reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _setup_render(width: int = WIDTH, height: int = HEIGHT) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 32

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.16, 0.17, 0.19, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world


def _add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(4, -6, 7))
    key = bpy.context.object
    key.rotation_euler = (math.radians(50), math.radians(18), math.radians(30))
    key.data.energy = 3.4

    bpy.ops.object.light_add(type="SUN", location=(-5, 3, 4))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(55), math.radians(-20), math.radians(-40))
    fill.data.energy = 1.15


def _add_plot() -> None:
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, 0.0))
    plot = bpy.context.object
    plot.name = "Plot1x1"
    mat = bpy.data.materials.new("PlotDirt")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.28, 0.20, 0.12, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.92
    plot.data.materials.append(mat)


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


def _fit_camera(objs, camera_dir: Vector) -> None:
    mn, mx = _world_bbox(objs)
    center = (mn + mx) * 0.5
    size = (mx - mn).length
    cam = bpy.context.scene.camera
    cam.location = center + camera_dir.normalized() * (size * FRAME_MARGIN * 1.35)
    direction = center - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 50


def _pose_clip(name: str, frame: int) -> None:
    scene = bpy.context.scene
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        return
    arm = arms[0]
    action = bpy.data.actions.get(name) or bpy.data.actions.get(f"{name}_{arm.name}")
    if action is None:
        for act in bpy.data.actions:
            if act.name.lower().startswith(name.lower()):
                action = act
                break
    if action is None:
        print(f"  WARN: no action for {name}")
        return
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    scene.frame_set(int(frame))
    bpy.context.view_layer.update()


def _load() -> list[bpy.types.Object]:
    _reset()
    bpy.ops.import_scene.gltf(filepath=GLB_PATH)
    _setup_render()
    _add_lights()
    _add_plot()
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return [o for o in bpy.data.objects if o.type == "MESH"]


def main() -> None:
    if not os.path.isfile(GLB_PATH):
        raise FileNotFoundError(GLB_PATH)

    meshes = _load()
    view = Vector((1.15, -1.45, 0.72)).normalized()
    for clip, frame, filename in STAGES:
        _pose_clip(clip, frame)
        _fit_camera(meshes, view)
        path = os.path.join(ROOT, filename)
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("wrote", filename)

    # Increase3 filmstrip (grow from almost-grown to harvestable)
    _pose_clip("Increase3", 1)
    for i in range(STRIP_COUNT):
        fr = 1 + int(round(i * 39 / (STRIP_COUNT - 1)))
        _pose_clip("Increase3", fr)
        _fit_camera(meshes, view)
        path = os.path.join(STRIP_DIR, f"increase3_{i:02d}_f{fr:03d}.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("wrote", path)

    print("DONE — hawkweed previews")


if __name__ == "__main__":
    main()
