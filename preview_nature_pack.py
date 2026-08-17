"""
preview_nature_pack.py
======================
Quality-verification render for the optimized Nature pack GLBs.
Renders a 6-asset grid so you can eyeball whether the aggressive
1024-cap WebP texture optimization damaged the visual quality vs the
untouched source.

Picks a representative sample:
  - BirchTree_3   (big tree, uses the 22 MB bark normal map)
  - MapleTree_1   (uses the 22 MB maple bark normal map)
  - DeadTree_5    (bare geometry, tests mesh only)
  - Bush_Flowers  (alpha-blended leaves, tests transparency)
  - Flower_1      (small, tests fine leaves)
  - Grass_Large   (billboard-y grass mesh)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python preview_nature_pack.py
"""

import math
import os

import bpy
from mathutils import Vector

NATURE_DIR = "/Users/stephenvillavaso/Desktop/Decorations/Nature"

SAMPLES = [
    ("BirchTree_3.glb",  (-4.0, 0.0)),
    ("MapleTree_1.glb",  (-1.5, 0.0)),
    ("DeadTree_5.glb",   ( 1.0, 0.0)),
    ("Bush_Flowers.glb", ( 3.0, 0.0)),
    ("Flower_1.glb",     ( 3.8, 0.0)),
    ("Grass_Large.glb",  ( 4.6, 0.0)),
]

OUT_PATH = os.path.abspath("nature_pack_preview.png")


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


def _add_ground():
    bpy.ops.mesh.primitive_plane_add(size=25.0, location=(0, 0, -0.001))
    plane = bpy.context.object
    plane.name = "GroundPlane"
    mat = bpy.data.materials.new("Ground")
    mat.use_nodes = True
    p = mat.node_tree.nodes.get("Principled BSDF")
    if p:
        p.inputs["Base Color"].default_value = (0.35, 0.42, 0.28, 1.0)  # grassy
        if "Roughness" in p.inputs:
            p.inputs["Roughness"].default_value = 1.0
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


def _fit_camera(objs, camera_dir: Vector, width: int, height: int, margin=1.10):
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
    right = forward.cross(world_up); right.normalize()
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


def _import_at(glb_name: str, x: float, y: float):
    """Import GLB and move root objects to (x, y, 0)."""
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(NATURE_DIR, glb_name))
    new_objs = [o for o in bpy.context.scene.objects if o not in before]

    # Move all root nodes to target position.  We only shift the roots
    # (objects with no parent) so children keep their local offsets.
    for obj in new_objs:
        if obj.parent is None:
            obj.location.x += x
            obj.location.y += y
    return [o for o in new_objs if o.type == "MESH"]


def main():
    print(f"Rendering nature pack preview → {OUT_PATH}")
    _reset()
    _add_lights()
    _add_ground()

    all_meshes = []
    for glb_name, (x, y) in SAMPLES:
        try:
            meshes = _import_at(glb_name, x, y)
            all_meshes.extend(meshes)
            print(f"  loaded: {glb_name}  ({len(meshes)} meshes)")
        except Exception as e:
            print(f"  FAILED: {glb_name}  — {e}")

    # Wide letterbox — the assets line up along +X (small on the
    # right, big trees on the left) so an eye-level 3/4 works well.
    _setup_render(1800, 700)
    _fit_camera(all_meshes, Vector((0.10, -1.0, 0.20)).normalized(),
                1800, 700, margin=1.15)
    bpy.context.scene.render.filepath = OUT_PATH
    bpy.ops.render.render(write_still=True)
    print(f"WROTE: {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes)")


if __name__ == "__main__":
    main()
