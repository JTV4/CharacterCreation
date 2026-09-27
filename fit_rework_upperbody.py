"""
Fit CharacterRework/Upperbody.glb onto BaseMaleRework.

Aligns the authored mesh to the Rework male neck/wrists, copies Mixamo
weights from the body, exports the existing rework shirt slot.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python fit_rework_upperbody.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
BODY_GLB = os.path.join(ROOT, "viewer/public/models/BaseMaleRework.glb")
SRC_GLB = os.path.expanduser(
    "~/Desktop/Models/Characters/CharacterRework/Upperbody.glb"
)
OUT_GLB = os.path.join(ROOT, "viewer/public/equipment/Rework/Male/shirt.glb")
PREVIEW_DIR = os.path.join(ROOT, "rework_previews")


def world_bbox(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def apply_mesh_transform(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def setup_preview() -> None:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 960
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.15, 0.16, 0.18, 1.0)
    scene.world = world
    bpy.ops.object.light_add(type="SUN", location=(5, -6, 8))
    bpy.context.object.rotation_euler = (math.radians(50), math.radians(16), math.radians(30))
    bpy.context.object.data.energy = 3.4
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    def look_from(offset: Vector, distance: float, center: Vector) -> None:
        cam.location = center + offset.normalized() * distance
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

    def render_to(name: str) -> None:
        path = os.path.join(PREVIEW_DIR, name)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("  preview", path)

    return look_from, render_to


def adopt_body_space(shirt: bpy.types.Object, body: bpy.types.Object) -> None:
    inv = body.matrix_world.inverted()
    shirt.data.transform(inv)
    shirt.data.update()
    shirt.parent = body.parent
    shirt.matrix_parent_inverse = body.matrix_parent_inverse.copy()
    shirt.location = body.location.copy()
    shirt.rotation_euler = body.rotation_euler.copy()
    shirt.scale = body.scale.copy()


def transfer_weights(body: bpy.types.Object, shirt: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Copy Mixamo weights from the body surface, then attach an armature modifier."""
    for vg in list(shirt.vertex_groups):
        shirt.vertex_groups.remove(vg)
    for vg in body.vertex_groups:
        shirt.vertex_groups.new(name=vg.name)
    bpy.ops.object.select_all(action="DESELECT")
    shirt.select_set(True)
    bpy.context.view_layer.objects.active = shirt
    for mod in list(shirt.modifiers):
        shirt.modifiers.remove(mod)
    mod = shirt.modifiers.new("WeightTransfer", "DATA_TRANSFER")
    mod.object = body
    mod.use_vert_data = True
    mod.data_types_verts = {"VGROUP_WEIGHTS"}
    mod.vert_mapping = "POLYINTERP_NEAREST"
    bpy.ops.object.datalayout_transfer(modifier="WeightTransfer")
    bpy.ops.object.modifier_apply(modifier="WeightTransfer")
    amod = shirt.modifiers.new("Armature", "ARMATURE")
    amod.object = arm
    weighted = 0
    for v in shirt.data.vertices:
        if any(g.weight > 0.001 for g in v.groups):
            weighted += 1
    if weighted == 0:
        raise RuntimeError("Weight transfer left every vertex unweighted")
    print(f"  weights groups={len(shirt.vertex_groups)} weighted={weighted}/{len(shirt.data.vertices)}")


def align_to_body(shirt: bpy.types.Object, body: bpy.types.Object, arm: bpy.types.Object) -> dict:
    """Place collar on the neck, cuffs at the wrists, chest outside the pecs."""
    bones = {normalize_bone_name(pb.name): pb for pb in arm.pose.bones}
    amw = arm.matrix_world
    neck = amw @ bones["Neck"].head
    hips = amw @ bones["Hips"].head
    l_hand = amw @ bones["LeftHand"].head
    bpts = [body.matrix_world @ v.co for v in body.data.vertices]
    torso = [p for p in bpts if 0.30 <= p.z <= 0.52 and abs(p.x) <= 0.20]
    body_front = max(p.y for p in torso)
    body_back = min(p.y for p in torso)
    body_cy = 0.02
    hem_z = hips.z - 0.02
    collar_z = neck.z + 0.008
    wrist_x = abs(l_hand.x) - 0.02

    spts = [shirt.matrix_world @ v.co for v in shirt.data.vertices]
    collar_src = [p for p in spts if math.hypot(p.x, p.y) < 0.08]
    src_collar_z = max(p.z for p in collar_src) if collar_src else max(p.z for p in spts)
    hem_src = [p for p in spts if abs(p.x) < 0.16]
    src_hem_z = min(p.z for p in hem_src) if hem_src else min(p.z for p in spts)
    src_h = src_collar_z - src_hem_z
    src_cuff = max(abs(p.x) for p in spts)
    src_front = max(p.y for p in spts)
    src_back = min(p.y for p in spts)

    z_scale = (collar_z - hem_z) / max(src_h, 1e-4)
    shirt.scale *= z_scale
    bpy.context.view_layer.update()
    spts = [shirt.matrix_world @ v.co for v in shirt.data.vertices]
    collar_now = max(p.z for p in spts if math.hypot(p.x, p.y) < 0.10)
    shirt.location.z += collar_z - collar_now
    lo, hi = world_bbox(shirt)
    shirt.location.x += -0.5 * (lo.x + hi.x)
    shirt.location.y += body_cy - 0.5 * (lo.y + hi.y)
    bpy.context.view_layer.update()
    apply_mesh_transform(shirt)

    lo, hi = world_bbox(shirt)
    x_scale = wrist_x / max(max(abs(lo.x), abs(hi.x)), 1e-4)
    y_need_front = (body_front + 0.014) / max(hi.y - body_cy, 1e-4)
    y_need_back = (abs(body_back) + 0.014) / max(body_cy - lo.y, 1e-4)
    y_scale = max(1.0, y_need_front, y_need_back)
    mid = Vector((0.5 * (lo.x + hi.x), 0.5 * (lo.y + hi.y), 0.5 * (lo.z + hi.z)))
    for v in shirt.data.vertices:
        p = Vector(v.co)
        p.x = mid.x + (p.x - mid.x) * x_scale
        p.y = mid.y + (p.y - mid.y) * y_scale
        v.co = p
    shirt.data.update()
    lo2, hi2 = world_bbox(shirt)
    stats = {
        "srcHemCollar": [round(src_hem_z, 4), round(src_collar_z, 4)],
        "srcCuff": round(src_cuff, 4),
        "zScale": round(z_scale, 4),
        "xScale": round(x_scale, 4),
        "yScale": round(y_scale, 4),
        "targetCollar": round(collar_z, 4),
        "targetWrist": round(wrist_x, 4),
        "fit": {
            "x": [round(lo2.x, 4), round(hi2.x, 4)],
            "y": [round(lo2.y, 4), round(hi2.y, 4)],
            "z": [round(lo2.z, 4), round(hi2.z, 4)],
        },
    }
    print("  align", stats)
    return stats


def normalize_bone_name(name: str) -> str:
    if name.startswith("mixamorig:"):
        return name[len("mixamorig:") :]
    if name.startswith("mixamorig"):
        return name[len("mixamorig") :]
    return name


def main() -> None:
    if not os.path.isfile(SRC_GLB):
        raise FileNotFoundError(SRC_GLB)
    os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
    print("=== fit_rework_upperbody ===")
    print("  src", SRC_GLB)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=BODY_GLB)
    bpy.context.view_layer.update()
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("BaseMale"))
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SRC_GLB)
    imported = [o for o in set(bpy.data.objects) - before if o.type == "MESH"]
    if not imported:
        raise RuntimeError("No mesh in Upperbody.glb")
    shirt = max(imported, key=lambda o: len(o.data.vertices))
    shirt.name = "ReworkMaleShirt"
    bpy.ops.object.select_all(action="DESELECT")
    shirt.select_set(True)
    bpy.context.view_layer.objects.active = shirt
    if shirt.parent:
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    apply_mesh_transform(shirt)
    print(f"  shirt verts={len(shirt.data.vertices)} faces={len(shirt.data.polygons)}")

    look_from, render_to = setup_preview()
    center = Vector((0.0, 0.0, 0.35))
    body.hide_render = True
    look_from(Vector((1.2, -1.6, 0.55)), 3.2, center)
    render_to("upperbody_src_3q.png")
    look_from(Vector((0.0, -1.0, 0.08)), 3.15, center)
    render_to("upperbody_src_front.png")
    body.hide_render = False

    align_to_body(shirt, body, arm)
    adopt_body_space(shirt, body)
    transfer_weights(body, shirt, arm)
    bpy.context.view_layer.update()

    look_from(Vector((1.2, -1.6, 0.55)), 3.2, center)
    render_to("upperbody_fit_3q.png")
    look_from(Vector((0.0, -1.0, 0.08)), 3.15, center)
    render_to("upperbody_fit_front.png")
    look_from(Vector((2.4, 0.0, 0.08)), 3.15, center)
    render_to("upperbody_fit_side.png")

    body.hide_set(True)
    bpy.ops.object.select_all(action="DESELECT")
    shirt.hide_set(False)
    arm.hide_set(False)
    shirt.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_skins=True,
        export_all_influences=True,
        export_animations=False,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    print(f"  -> {OUT_GLB} ({os.path.getsize(OUT_GLB) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
