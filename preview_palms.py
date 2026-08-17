"""Quick side-by-side preview of PalmTree + PalmTreeLeaning."""
import math
import os

import bpy
from mathutils import Vector

VIEWER = os.path.abspath("viewer/public/buildings")
OUT = os.path.abspath("palm_trees_preview.png")


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = 1400
    sc.render.resolution_y = 900
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.eevee.taa_render_samples = 48
    world = bpy.data.worlds.new("W")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.52, 0.72, 0.88, 1.0)
    bg.inputs[1].default_value = 1.0
    sc.world = world

    bpy.ops.object.light_add(type="SUN", location=(6, -8, 10))
    sun = bpy.context.object
    sun.rotation_euler = (math.radians(48), math.radians(18), math.radians(30))
    sun.data.energy = 3.8

    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -0.001))
    ground = bpy.context.object
    mat = bpy.data.materials.new("sand")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (
        0.72, 0.64, 0.48, 1.0,
    )
    ground.data.materials.append(mat)


def import_glb(path, loc):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    root = new[0]
    for o in new:
        o.location = Vector(loc)
    return root


def main():
    reset()
    setup()
    import_glb(os.path.join(VIEWER, "PalmTree.glb"), (-6.0, 0, 0))
    import_glb(os.path.join(VIEWER, "PalmTreeLeaning.glb"), (5.0, 0, 0))

    # Frame both full trees (trunk + frond crown)
    bpy.ops.object.camera_add(location=(1.5, -28.0, 9.5))
    cam = bpy.context.object
    cam.rotation_euler = (math.radians(72), 0, math.radians(4))
    cam.data.lens = 35
    bpy.context.scene.camera = cam

    bpy.context.scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
