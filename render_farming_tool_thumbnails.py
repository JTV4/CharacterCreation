#!/usr/bin/env python3
"""
Render 64×64 (supersampled) transparent PNG thumbnails for farming vessels.

Empty items are the raw GLB. Full items add a simple fill mesh so water /
milk / compost / sand read at icon size.

Run:
    /Applications/Blender.app/Contents/MacOS/Blender --background \\
        --python render_farming_tool_thumbnails.py
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parent
FARM = REPO / "viewer/public/tools/farming"
OUT = FARM / "thumbs"
THUMB_SIZE = 64
SUPERSAMPLE = 4
CAMERA_OFFSET_DIRECTION = Vector((0.55, -0.85, 0.35)).normalized()
FRAME_MARGIN = 1.18

BUCKET = FARM / "EmptyBucket.glb"
CAN = FARM / "EmptyTinWateringCan.glb"
SIFTER = FARM / "SandSifter.glb"

# glTF Y-up → Blender Z-up: model (x, y, z) becomes (x, -z, y)
def gltf_to_blender(x: float, y: float, z: float) -> Vector:
    return Vector((x, -z, y))


ITEMS = [
    {"id": "EmptyBucket", "glb": BUCKET, "fill": None},
    {"id": "WaterBucket", "glb": BUCKET, "fill": "water"},
    {"id": "MilkBucket", "glb": BUCKET, "fill": "milk"},
    {"id": "CompostBucket", "glb": BUCKET, "fill": "compost"},
    {"id": "SandBucket", "glb": BUCKET, "fill": "sand"},
    {"id": "EmptyTinWateringCan", "glb": CAN, "fill": None},
    {"id": "WaterTinWateringCan", "glb": CAN, "fill": "can_water"},
    {"id": "SandSifter", "glb": SIFTER, "fill": None},
]

FILL_COLOR = {
    "water": (0.18, 0.62, 0.88, 0.88),
    "milk": (0.95, 0.90, 0.78, 0.96),
    "compost": (0.16, 0.10, 0.05, 1.0),
    "sand": (0.78, 0.64, 0.42, 1.0),
    "can_water": (0.18, 0.62, 0.88, 0.88),
}

# Offsets in Blender space on top of the bucket fill cylinder (Z up).
COMPOST_CLODS = [
    ((0.0, 0.0, 0.058), 0.072, (0.16, 0.10, 0.05, 1.0)),
    ((0.022, 0.016, 0.078), 0.028, (0.28, 0.17, 0.08, 1.0)),
    ((-0.024, 0.018, 0.074), 0.026, (0.20, 0.24, 0.09, 1.0)),
    ((0.01, -0.026, 0.076), 0.03, (0.12, 0.07, 0.03, 1.0)),
    ((-0.018, -0.014, 0.082), 0.02, (0.36, 0.26, 0.10, 1.0)),
    ((0.03, -0.01, 0.07), 0.022, (0.32, 0.20, 0.09, 1.0)),
    ((-0.032, -0.008, 0.072), 0.024, (0.22, 0.26, 0.10, 1.0)),
    ((0.012, 0.03, 0.084), 0.018, (0.42, 0.30, 0.12, 1.0)),
    ((-0.006, 0.004, 0.094), 0.016, (0.24, 0.14, 0.06, 1.0)),
    ((0.02, -0.02, 0.088), 0.017, (0.18, 0.22, 0.08, 1.0)),
]

SAND_CLODS = [
    ((0.0, 0.0, 0.058), 0.072, (0.78, 0.64, 0.42, 1.0)),
    ((0.022, 0.016, 0.078), 0.028, (0.86, 0.72, 0.48, 1.0)),
    ((-0.024, 0.018, 0.074), 0.026, (0.70, 0.56, 0.34, 1.0)),
    ((0.01, -0.026, 0.076), 0.03, (0.82, 0.68, 0.44, 1.0)),
    ((-0.018, -0.014, 0.082), 0.02, (0.90, 0.78, 0.55, 1.0)),
    ((0.03, -0.01, 0.07), 0.022, (0.74, 0.58, 0.36, 1.0)),
    ((-0.032, -0.008, 0.072), 0.024, (0.80, 0.66, 0.40, 1.0)),
    ((0.012, 0.03, 0.084), 0.018, (0.88, 0.74, 0.50, 1.0)),
    ((-0.006, 0.004, 0.094), 0.016, (0.68, 0.52, 0.32, 1.0)),
    ((0.02, -0.02, 0.088), 0.017, (0.84, 0.70, 0.46, 1.0)),
]


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = THUMB_SIZE * SUPERSAMPLE
    scene.render.resolution_y = THUMB_SIZE * SUPERSAMPLE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.eevee.taa_render_samples = 32

    world = bpy.data.worlds.new("ThumbWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
    bg.inputs[1].default_value = 0.6
    scene.world = world

    bpy.ops.object.light_add(type="SUN", location=(2, -3, 3))
    key = bpy.context.object
    key.rotation_euler = (math.radians(45), math.radians(15), math.radians(20))
    key.data.energy = 3.5
    bpy.ops.object.light_add(type="SUN", location=(-3, -1, 2))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(60), math.radians(-20), math.radians(-30))
    fill.data.energy = 1.2


def make_fill_mat(name: str, rgba: tuple, compost: bool = False) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    r, g, b, a = rgba
    bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0 if compost else (0.35 if a < 1 else 0.92)
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.04 if compost else 0.5
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.04 if compost else 0.5
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    if a < 1 and not compost:
        mat.blend_method = "BLEND"
        if "Alpha" in bsdf.inputs:
            bsdf.inputs["Alpha"].default_value = a
        if "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = 0.35
        elif "Transmission Weight" in bsdf.inputs:
            bsdf.inputs["Transmission Weight"].default_value = 0.35
    return mat


def shade_flat(obj: bpy.types.Object) -> None:
    for poly in obj.data.polygons:
        poly.use_smooth = False


def add_fill(kind: str) -> None:
    compost = kind in ("compost", "sand")
    mat = make_fill_mat(f"fill_{kind}", FILL_COLOR[kind], compost=compost)
    if kind in ("water", "milk", "compost", "sand"):
        # Bucket interior: body (0, -0.178, 0) glTF, radius 0.078, depth 0.118
        loc = gltf_to_blender(0.0, -0.178, 0.0)
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=24,
            radius=0.072,
            depth=0.11,
            location=loc,
        )
        cyl = bpy.context.object
        # Cylinder default axis is Blender Z; bucket depth is along glTF −Y = Blender −Z
        cyl.rotation_euler = (0.0, 0.0, 0.0)
        cyl.data.materials.append(mat)
        if compost:
            scene = bpy.context.scene
            scene.view_settings.view_transform = "Standard"
            scene.view_settings.look = "None"
            for obj in scene.objects:
                if obj.type == "LIGHT":
                    obj.data.energy *= 0.70 if kind == "sand" else 0.55
            shade_flat(cyl)
            clods = SAND_CLODS if kind == "sand" else COMPOST_CLODS
            for i, (offset, radius, rgba) in enumerate(clods):
                clod_mat = make_fill_mat(f"clod_{i}", rgba, compost=True)
                bpy.ops.mesh.primitive_ico_sphere_add(
                    subdivisions=1,
                    radius=radius,
                    location=loc + Vector(offset),
                )
                clod = bpy.context.object
                clod.rotation_euler = (
                    math.radians(25 * (i + 1)),
                    math.radians(40 * i),
                    math.radians(15 * i),
                )
                clod.data.materials.append(clod_mat)
                clod.scale = (
                    1.0,
                    0.72 + (i % 3) * 0.12,
                    0.8 + (i % 2) * 0.15,
                )
                shade_flat(clod)
    else:
        loc = gltf_to_blender(-0.095, 0.055, 0.0)
        bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=0.058, depth=0.10, location=loc)
        cyl = bpy.context.object
        cyl.rotation_euler = (math.radians(90), 0.0, 0.0)
        cyl.data.materials.append(mat)


def world_bbox(objs):
    bpy.context.view_layer.update()
    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    for obj in objs:
        if obj.type != "MESH" or not obj.data or not obj.data.vertices:
            continue
        mw = obj.matrix_world
        for v in obj.data.vertices:
            wv = mw @ v.co
            mn = Vector(min(mn[i], wv[i]) for i in range(3))
            mx = Vector(max(mx[i], wv[i]) for i in range(3))
    return mn, mx


def fit_camera(objs) -> None:
    mn, mx = world_bbox(objs)
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
    forward = -CAMERA_OFFSET_DIRECTION
    world_up = Vector((0.0, 0.0, 1.0))
    right = forward.cross(world_up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up = right.cross(forward).normalized()
    half_extent = max(
        max(abs((c - centre).dot(right)) for c in corners),
        max(abs((c - centre).dot(up)) for c in corners),
        1e-3,
    )
    fov = 2.0 * math.atan((cam.data.sensor_width * 0.5) / cam.data.lens)
    distance = (half_extent * FRAME_MARGIN) / math.tan(fov * 0.5)
    cam.location = centre + CAMERA_OFFSET_DIRECTION * distance
    target = bpy.data.objects.new("ThumbTarget", None)
    target.location = centre
    bpy.context.collection.objects.link(target)
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    bpy.context.scene.camera = cam


def render_one(item: dict) -> bool:
    out_path = OUT / f"{item['id']}_thumb.png"
    print(f"\n=== {item['id']} → {out_path} ===")
    reset_scene()
    bpy.ops.import_scene.gltf(filepath=str(item["glb"]))
    if item["fill"]:
        add_fill(item["fill"])
    mesh_objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not mesh_objs:
        print("  WARN: no meshes")
        return False
    fit_camera(mesh_objs)
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(out_path)
    bpy.ops.render.render(write_still=True)
    ok = out_path.exists()
    print(f"  {'OK' if ok else 'FAIL'} {out_path.stat().st_size if ok else 0} bytes")
    return ok


def cli_ids() -> set[str]:
    if "--" not in sys.argv:
        return set()
    return {a for a in sys.argv[sys.argv.index("--") + 1 :] if a and not a.startswith("-")}


def main() -> None:
    wanted = cli_ids()
    ok = 0
    total = 0
    for item in ITEMS:
        if wanted and item["id"] not in wanted:
            continue
        total += 1
        try:
            if render_one(item):
                ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {item['id']}: {exc}")
    print(f"\nDone: {ok}/{total}")


if __name__ == "__main__":
    main()
