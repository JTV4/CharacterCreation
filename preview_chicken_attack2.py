"""Still frames of Chicken.glb attack2 (squat / eggs / recover)."""
import math
import os

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "viewer/public/buildings/Chicken.glb")
OUT_DIR = os.path.join(ROOT, "chicken_attack2_frames")
os.makedirs(OUT_DIR, exist_ok=True)

FRAMES = [
    ("chicken_attack2_00_rest.png", 1),
    ("chicken_attack2_06_crouch.png", 6),
    ("chicken_attack2_14_jump180.png", 14),
    ("chicken_attack2_20_landed.png", 20),
    ("chicken_attack2_22_egg1.png", 22),
    ("chicken_attack2_28_eggs.png", 28),
    ("chicken_attack2_32_impact.png", 32),
    ("chicken_attack2_36_burst.png", 36),
    ("chicken_attack2_42_jumpback.png", 42),
    ("chicken_attack2_48_rest.png", 48),
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
    direction = Vector((1.65, -1.35, 0.55)).normalized()
    loc = center + direction * (radius * 1.15)
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

    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    act = next(a for a in bpy.data.actions if a.name.startswith("attack2"))
    arm.animation_data_create()
    arm.animation_data.action = act
    bpy.context.scene.render.fps = 24

    bpy.context.scene.frame_set(24)
    mn, mx = mesh_bounds()
    center = (mn + mx) * 0.5
    radius = (mx - mn).length * 0.95
    camera_at(center, radius)

    clips = sorted({a.name for a in bpy.data.actions})
    print("actions", clips)
    print("meshes", [o.name for o in bpy.data.objects if o.type == "MESH"])

    for name, frame in FRAMES:
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = os.path.join(OUT_DIR, name)
        bpy.ops.render.render(write_still=True)
        print("wrote", name, "frame", frame)


if __name__ == "__main__":
    main()
