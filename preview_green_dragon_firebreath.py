"""Still frames of GreenDragon.glb attack1 (windup / breath / recover)."""
import math
import os

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "viewer/public/buildings/GreenDragon.glb")
OUT_DIR = os.path.join(ROOT, "dragon_firebreath_frames")
os.makedirs(OUT_DIR, exist_ok=True)

FRAMES = [
    ("dragon_attack1_00_rest.png", 1),
    ("dragon_attack1_12_coil.png", 12),
    ("dragon_attack1_28_open.png", 28),
    ("dragon_attack1_40_stream.png", 40),
    ("dragon_attack1_52_hold.png", 52),
    ("dragon_attack1_68_recover.png", 68),
]


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_render() -> None:
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1100
    scene.render.resolution_y = 800
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 24
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.10, 0.11, 0.13, 1.0)
    scene.world = world


def add_lights() -> None:
    bpy.ops.object.light_add(type="SUN", location=(4, -3, 8))
    sun = bpy.context.object
    sun.data.energy = 3.5
    bpy.ops.object.light_add(type="AREA", location=(-3, 4, 5))
    area = bpy.context.object
    area.data.energy = 250
    area.data.size = 4


def camera_at(center: Vector, radius: float) -> None:
    direction = Vector((1.55, 0.95, 0.35)).normalized()
    loc = center + direction * radius
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    look = center - loc
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()


def mesh_bounds() -> tuple[Vector, Vector]:
    pts: list[Vector] = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        mw = obj.matrix_world
        pts.extend(mw @ v.co for v in obj.data.vertices)
    xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
    mn = Vector((min(xs), min(ys), min(zs)))
    mx = Vector((max(xs), max(ys), max(zs)))
    return mn, mx


def main() -> None:
    reset()
    bpy.ops.import_scene.gltf(filepath=SRC)
    setup_render()
    add_lights()

    arm = bpy.data.objects["Armature"]
    act = next(a for a in bpy.data.actions if a.name.startswith("attack1"))
    arm.animation_data_create()
    arm.animation_data.action = act
    bpy.context.scene.render.fps = 24

    bpy.context.scene.frame_set(40)
    mn, mx = mesh_bounds()
    center = (mn + mx) * 0.5
    radius = (mx - mn).length * 0.85
    camera_at(center, radius)

    for name, frame in FRAMES:
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = os.path.join(OUT_DIR, name)
        bpy.ops.render.render(write_still=True)
        print("wrote", name, "frame", frame)

    print("DONE", OUT_DIR)


if __name__ == "__main__":
    main()
