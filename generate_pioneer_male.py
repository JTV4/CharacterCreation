"""
generate_pioneer_male.py
========================
Authored GrindScape pioneer *male* — not a copy of Female V3.

Uses the Male V2 Mixamo T-pose (five-finger hands, 65 bones) as the
rig, then replaces the head and remaps the body to male proportions
before clothing. Face, jaw, chest, and hips are generated / sculpted
as male. Clips: idle, walk, attack1, die.

Outputs:
  viewer/public/models/PioneerMale.glb
  viewer/public/buildings/PioneerMale.glb
  ~/Desktop/Models/Characters/PioneerMale.glb

Run:
  python3 generate_pioneer_male_textures.py
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
    --python generate_pioneer_male.py
"""

from __future__ import annotations

import math
import os
import subprocess

import bmesh
import bpy
from mathutils import Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(ROOT, "pioneer_male_textures")
SRC_GLB = os.path.join(ROOT, "viewer/public/models/BaseMaleV2.glb")
VIEWER_MODELS = os.path.join(ROOT, "viewer/public/models")
VIEWER_BUILDINGS = os.path.join(ROOT, "viewer/public/buildings")
DESKTOP = os.path.expanduser("~/Desktop/Models/Characters")
os.makedirs(VIEWER_MODELS, exist_ok=True)
os.makedirs(VIEWER_BUILDINGS, exist_ok=True)
os.makedirs(DESKTOP, exist_ok=True)

FPS = 24
CLIP_IDLE = 72
CLIP_WALK = 32
CLIP_ATTACK = 28
CLIP_DIE = 36

# Imported Male V2: face / chest sit on −Y.
FRONT_SIGN = -1.0

BODY_REGIONS = (
    "base_body_head",
    "base_body_upper_torso",
    "base_body_lower_torso",
    "base_body_arm_upper",
    "base_body_arm_lower",
    "base_body_hands",
    "base_body_leg_upper",
    "base_body_leg_thigh",
    "base_body_leg_knee",
    "base_body_leg_shin",
    "base_body_leg_ankle",
    "base_body_foot",
)

# Do not remap the T-pose hands — they already have five fingers.
# Head uses its own jaw/brow sculpt, not the chest flatten.
SKIP_MASCULINIZE = {"base_body_hands", "base_body_arm_lower", "base_body_foot", "base_body_head"}


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ensure_textures() -> None:
    needed = [
        "Pioneer_Skin_BaseColor.png",
        "Pioneer_Hair_BaseColor.png",
        "Pioneer_Linen_BaseColor.png",
        "Pioneer_Wool_BaseColor.png",
        "Pioneer_Leather_BaseColor.png",
        "Pioneer_Metal_BaseColor.png",
        "Pioneer_Eye_BaseColor.png",
    ]
    if all(os.path.isfile(os.path.join(TEX_DIR, n)) for n in needed):
        return
    subprocess.check_call(["python3", os.path.join(ROOT, "generate_pioneer_male_textures.py")])


def load_image(filename: str) -> bpy.types.Image:
    path = os.path.join(TEX_DIR, filename)
    img = bpy.data.images.load(path, check_existing=True)
    img.pack()
    return img


def make_tex_mat(
    name: str,
    filename: str,
    *,
    roughness: float = 0.85,
    metallic: float = 0.0,
    uv_scale: float = 1.0,
    tint: tuple[float, float, float] | None = None,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = load_image(filename)
    tex.interpolation = "Linear"
    tex.extension = "REPEAT"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (uv_scale, uv_scale, uv_scale)
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    color_out = tex.outputs["Color"]
    if tint:
        mix = nt.nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs["Fac"].default_value = 1.0
        mix.inputs["Color2"].default_value = (*tint, 1.0)
        nt.links.new(tex.outputs["Color"], mix.inputs["Color1"])
        color_out = mix.outputs["Color"]
    nt.links.new(color_out, bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


def make_solid_mat(name: str, color: tuple[float, float, float], roughness: float = 0.5) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def box_uv(obj: bpy.types.Object, scale: float) -> None:
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active
    for poly in me.polygons:
        n = poly.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if az >= ax and az >= ay:
                u, v = co.x, co.y
            elif ax >= ay:
                u, v = co.y, co.z
            else:
                u, v = co.x, co.z
            uv.data[li].uv = (u * scale, v * scale)


def assign_mat(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def shade_smooth(obj: bpy.types.Object) -> None:
    for poly in obj.data.polygons:
        poly.use_smooth = True


def apply_trs(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def body_meshes() -> dict[str, bpy.types.Object]:
    return {o.name: o for o in bpy.data.objects if o.type == "MESH" and o.name in BODY_REGIONS}


def duplicate_mesh(src: bpy.types.Object, name: str) -> bpy.types.Object:
    obj = src.copy()
    obj.data = src.data.copy()
    obj.name = name
    obj.data.name = name
    bpy.context.collection.objects.link(obj)
    return obj


def inflate(obj: bpy.types.Object, thickness: float) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    for v in bm.verts:
        if v.normal.length > 1e-6:
            v.co += v.normal.normalized() * thickness
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    shade_smooth(obj)


def delete_world_verts(obj: bpy.types.Object, pred) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    kill = [v for v in bm.verts if pred(obj.matrix_world @ v.co)]
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def bind_to_arm(obj: bpy.types.Object, arm: bpy.types.Object) -> None:
    mw = obj.matrix_world.copy()
    obj.parent = arm
    obj.matrix_world = mw
    mods = [m for m in obj.modifiers if m.type == "ARMATURE"]
    if mods:
        mods[0].object = arm
        mods[0].use_vertex_groups = True
    else:
        mod = obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = arm
        mod.use_vertex_groups = True


def adopt_bind_space(obj: bpy.types.Object, template: bpy.types.Object) -> None:
    """Rewrite world-authored verts into a skinned mesh's bind/object space."""
    src_world = obj.matrix_world.copy()
    dest_inv = template.matrix_world.inverted()
    for v in obj.data.vertices:
        v.co = dest_inv @ (src_world @ v.co)
    obj.data.update()
    obj.parent = template.parent
    obj.parent_type = template.parent_type
    obj.matrix_parent_inverse = template.matrix_parent_inverse.copy()
    obj.location = template.location.copy()
    obj.rotation_mode = template.rotation_mode
    obj.rotation_euler = template.rotation_euler.copy()
    obj.rotation_quaternion = template.rotation_quaternion.copy()
    obj.scale = template.scale.copy()


def skin_to_bone(obj: bpy.types.Object, arm: bpy.types.Object, bone: str) -> None:
    for b in arm.data.bones:
        if b.name not in obj.vertex_groups:
            obj.vertex_groups.new(name=b.name)
    obj.vertex_groups[bone].add([v.index for v in obj.data.vertices], 1.0, "REPLACE")
    bind_to_arm(obj, arm)


def loft_solid(
    name: str,
    centers: list[Vector],
    radii_xy: list[tuple[float, float]],
    mat: bpy.types.Material,
    *,
    segs: int = 12,
    uv_scale: float = 1.4,
    cap_start: bool = True,
    cap_end: bool = True,
) -> bpy.types.Object:
    bm = bmesh.new()
    rings: list[list[bmesh.types.BMVert]] = []
    for i, (c, (rx, ry)) in enumerate(zip(centers, radii_xy)):
        if i == 0:
            direction = (centers[1] - centers[0]).normalized()
        elif i == len(centers) - 1:
            direction = (centers[-1] - centers[-2]).normalized()
        else:
            direction = (centers[i + 1] - centers[i - 1]).normalized()
        if abs(direction.dot(Vector((0, 0, 1)))) > 0.9:
            side, up = Vector((1, 0, 0)), Vector((0, 1, 0))
        else:
            side = direction.cross(Vector((0, 0, 1)))
            if side.length < 1e-6:
                side = direction.cross(Vector((1, 0, 0)))
            side.normalize()
            up = side.cross(direction).normalized()
        row = []
        for si in range(segs):
            a = 2 * math.pi * si / segs
            row.append(bm.verts.new(c + side * (math.cos(a) * rx) + up * (math.sin(a) * ry)))
        rings.append(row)
    for ri in range(len(rings) - 1):
        for si in range(segs):
            sj = (si + 1) % segs
            bm.faces.new([rings[ri][si], rings[ri][sj], rings[ri + 1][sj], rings[ri + 1][si]])
    if cap_start:
        bm.faces.new(list(reversed(rings[0])))
    if cap_end:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    assign_mat(obj, mat)
    box_uv(obj, uv_scale)
    shade_smooth(obj)
    return obj


def sphere(
    name: str,
    center: tuple[float, float, float],
    radius: float,
    mat: bpy.types.Material,
    *,
    segs: int = 16,
    rings: int = 10,
    scale: tuple[float, float, float] | None = None,
    uv_scale: float = 1.6,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings, radius=radius, location=center)
    obj = bpy.context.active_object
    obj.name = name
    if scale:
        obj.scale = scale
    apply_trs(obj)
    assign_mat(obj, mat)
    box_uv(obj, uv_scale)
    shade_smooth(obj)
    return obj


def masculinize_point(wp: Vector) -> Vector:
    """Cap breast volume and shift toward a male V. Never invert the mesh."""
    x, y, z = wp.x, wp.y, wp.z
    front = y * FRONT_SIGN

    if 1.26 <= z <= 1.55 and abs(x) < 0.22:
        cap = 0.020
        if front > cap:
            y = FRONT_SIGN * cap

    if 1.44 <= z <= 1.56:
        x *= 1.10

    if 1.16 <= z <= 1.32:
        x *= 1.12

    if 0.90 <= z <= 1.14:
        x *= 0.86

    return Vector((x, y, z))


def masculinize_head_point(wp: Vector) -> Vector:
    """Square the jaw, push the brow, keep the skull in the original volume."""
    x, y, z = wp.x, wp.y, wp.z
    front = y * FRONT_SIGN

    if 1.575 <= z <= 1.670:
        t = max(0.0, 1.0 - abs(z - 1.620) / 0.055)
        x *= 1.0 + 0.20 * t
        if front > 0.015:
            y = FRONT_SIGN * (front + 0.014 * t)

    if 1.705 <= z <= 1.775 and front > 0.035 and abs(x) < 0.08:
        t = max(0.0, 1.0 - abs(z - 1.740) / 0.040)
        y = FRONT_SIGN * (front + 0.011 * t)

    if 1.650 <= z <= 1.740 and abs(x) > 0.035:
        x *= 1.05

    if z > 1.780:
        x *= 0.96
        y *= 0.97

    return Vector((x, y, z))


def flatten_chest_shell(obj: bpy.types.Object, cap: float = 0.040) -> None:
    """Kill breast volume on an already-skinned clothing copy."""
    mat = obj.matrix_world.copy()
    inv = mat.inverted()
    for v in obj.data.vertices:
        wp = mat @ v.co
        if 1.26 <= wp.z <= 1.55 and abs(wp.x) < 0.22:
            front = wp.y * FRONT_SIGN
            if front > cap:
                wp.y = FRONT_SIGN * cap
                v.co = inv @ wp
    obj.data.update()
    shade_smooth(obj)


def masculinize_mesh(obj: bpy.types.Object) -> None:
    """Edit rest verts in world space. Does not apply object transforms."""
    mat = obj.matrix_world.copy()
    inv = mat.inverted()
    for v in obj.data.vertices:
        v.co = inv @ masculinize_point(mat @ v.co)
    obj.data.update()
    shade_smooth(obj)


def finish_head_part(
    obj: bpy.types.Object,
    arm: bpy.types.Object,
    template: bpy.types.Object,
    bone: str = "mixamorig:Head",
) -> bpy.types.Object:
    adopt_bind_space(obj, template)
    skin_to_bone(obj, arm, bone)
    return obj


def skin_by_height(obj: bpy.types.Object, arm: bpy.types.Object, bands: list[tuple[float, str]]) -> None:
    """Assign each vert to the first band whose z-min it clears (bands high → low)."""
    for b in arm.data.bones:
        if b.name not in obj.vertex_groups:
            obj.vertex_groups.new(name=b.name)
    mat = obj.matrix_world
    buckets: dict[str, list[int]] = {name: [] for _, name in bands}
    for v in obj.data.vertices:
        z = (mat @ v.co).z
        chosen = bands[-1][1]
        for zmin, name in bands:
            if z >= zmin:
                chosen = name
                break
        buckets[chosen].append(v.index)
    for name, idxs in buckets.items():
        if idxs:
            obj.vertex_groups[name].add(idxs, 1.0, "REPLACE")
    bind_to_arm(obj, arm)


def build_male_head(
    arm: bpy.types.Object,
    mats: dict[str, bpy.types.Material],
    head: bpy.types.Object,
) -> list[bpy.types.Object]:
    """Sculpt the existing Mixamo head into a male settler. Hair/beard are copies."""
    mat = head.matrix_world.copy()
    inv = mat.inverted()
    for v in head.data.vertices:
        v.co = inv @ masculinize_head_point(mat @ v.co)
    head.data.update()
    shade_smooth(head)
    assign_mat(head, mats["skin"])
    head.name = "male_head"
    head.data.name = "male_head"
    bind_to_arm(head, arm)

    parts: list[bpy.types.Object] = [head]

    hair = duplicate_mesh(head, "male_hair")
    delete_world_verts(
        hair,
        lambda p: p.z < 1.705 or (p.y * FRONT_SIGN > 0.018 and p.z < 1.768),
    )
    inflate(hair, 0.014)
    assign_mat(hair, mats["hair"])
    box_uv(hair, 2.2)
    bind_to_arm(hair, arm)
    parts.append(hair)

    beard = duplicate_mesh(head, "male_beard")
    delete_world_verts(
        beard,
        lambda p: p.z > 1.648 or p.z < 1.555 or p.y * FRONT_SIGN < 0.008 or abs(p.x) > 0.095,
    )
    inflate(beard, 0.016)
    assign_mat(beard, mats["hair"])
    box_uv(beard, 2.4)
    bind_to_arm(beard, arm)
    parts.append(beard)
    return parts


def finish_cloth(obj: bpy.types.Object, mat: bpy.types.Material, uv_scale: float, arm: bpy.types.Object) -> None:
    assign_mat(obj, mat)
    box_uv(obj, uv_scale)
    shade_smooth(obj)
    bind_to_arm(obj, arm)


def add_buckle(
    arm: bpy.types.Object,
    mat: bpy.types.Material,
    z: float,
    y: float,
    template: bpy.types.Object,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, y, z))
    obj = bpy.context.active_object
    obj.name = "pioneer_buckle"
    obj.scale = (0.028, 0.010, 0.022)
    apply_trs(obj)
    adopt_bind_space(obj, template)
    skin_to_bone(obj, arm, "mixamorig:Hips")
    assign_mat(obj, mat)
    box_uv(obj, 4.0)
    return obj


def dress(meshes: dict[str, bpy.types.Object], arm: bpy.types.Object, materials: dict[str, bpy.types.Material]) -> list[bpy.types.Object]:
    extras: list[bpy.types.Object] = []

    def shell(src_name: str, dst_name: str, thick: float, mat, uv: float, crop=None):
        obj = duplicate_mesh(meshes[src_name], dst_name)
        inflate(obj, thick)
        if crop:
            delete_world_verts(obj, crop)
        finish_cloth(obj, mat, uv, arm)
        extras.append(obj)
        return obj

    shell("base_body_arm_upper", "pioneer_tunic_sleeves", 0.012, materials["linen"], 2.6)
    shell("base_body_arm_lower", "pioneer_tunic_forearm", 0.010, materials["linen"], 2.6)
    tunic = shell(
        "base_body_upper_torso",
        "pioneer_tunic",
        0.016,
        materials["leather"],
        1.8,
        crop=lambda p: p.z > 1.545,
    )
    flatten_chest_shell(tunic, cap=0.038)
    flatten_chest_shell(meshes["base_body_upper_torso"], cap=0.022)
    shell("base_body_lower_torso", "pioneer_tunic_waist", 0.016, materials["leather"], 1.8)
    shell("base_body_leg_upper", "pioneer_hose_hip", 0.012, materials["wool"], 2.4)

    for region, name in (
        ("base_body_leg_thigh", "pioneer_hose_thigh"),
        ("base_body_leg_knee", "pioneer_hose_knee"),
        ("base_body_leg_shin", "pioneer_hose_shin"),
    ):
        shell(region, name, 0.010, materials["wool"], 2.8)

    shell("base_body_leg_ankle", "pioneer_boot_ankle", 0.016, materials["leather"], 1.7)
    shell("base_body_foot", "pioneer_boot_foot", 0.016, materials["leather"], 1.7)

    waist = meshes["base_body_lower_torso"]
    zs = [(waist.matrix_world @ v.co).z for v in waist.data.vertices]
    z0, z1 = min(zs), max(zs)
    belt_lo = z0 + (z1 - z0) * 0.18
    belt_hi = z0 + (z1 - z0) * 0.48
    shell(
        "base_body_lower_torso",
        "pioneer_belt",
        0.026,
        materials["leather"],
        2.0,
        crop=lambda p: p.z < belt_lo or p.z > belt_hi,
    )
    ys = [(waist.matrix_world @ v.co).y for v in waist.data.vertices]
    front_y = min(ys) if FRONT_SIGN < 0 else max(ys)
    buckle = duplicate_mesh(waist, "pioneer_buckle")
    delete_world_verts(
        buckle,
        lambda p: abs(p.x) > 0.04
        or p.z < (belt_lo + belt_hi) * 0.5 - 0.018
        or p.z > (belt_lo + belt_hi) * 0.5 + 0.018
        or p.y * FRONT_SIGN < (front_y * FRONT_SIGN) - 0.01,
    )
    inflate(buckle, 0.010)
    assign_mat(buckle, materials["metal"])
    box_uv(buckle, 4.0)
    bind_to_arm(buckle, arm)
    extras.append(buckle)
    return extras


def mats() -> dict[str, bpy.types.Material]:
    return {
        "skin": make_tex_mat(
            "pioneer_skin",
            "Pioneer_Skin_BaseColor.png",
            roughness=0.62,
            uv_scale=3.5,
            tint=(0.92, 0.78, 0.62),
        ),
        "linen": make_tex_mat(
            "pioneer_linen",
            "Pioneer_Linen_BaseColor.png",
            roughness=0.88,
            tint=(0.88, 0.80, 0.58),
        ),
        "wool": make_tex_mat(
            "pioneer_wool",
            "Pioneer_Leather_BaseColor.png",
            roughness=0.90,
            tint=(0.16, 0.13, 0.10),
        ),
        "leather": make_tex_mat("pioneer_leather", "Pioneer_Leather_BaseColor.png", roughness=0.78),
        "metal": make_tex_mat("pioneer_metal", "Pioneer_Metal_BaseColor.png", roughness=0.42, metallic=0.65),
        "hair": make_tex_mat("pioneer_hair", "Pioneer_Hair_BaseColor.png", roughness=0.72),
        "eye": make_tex_mat("pioneer_eye", "Pioneer_Eye_BaseColor.png", roughness=0.22),
        "iris": make_solid_mat("pioneer_iris", (0.28, 0.38, 0.32), 0.28),
        "pupil": make_solid_mat("pioneer_pupil", (0.04, 0.04, 0.05), 0.35),
        "lip": make_solid_mat("pioneer_lip", (0.42, 0.24, 0.20), 0.55),
    }


def paint_skin(meshes: dict[str, bpy.types.Object], skin: bpy.types.Material) -> None:
    for obj in meshes.values():
        assign_mat(obj, skin)
        shade_smooth(obj)


def select_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _bone(arm: bpy.types.Object, short: str) -> bpy.types.PoseBone:
    return arm.pose.bones[f"mixamorig:{short}"]


def _reset_pose(arm: bpy.types.Object) -> None:
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _smooth_action(action: bpy.types.Action) -> None:
    for fcu in action.fcurves:
        for kp in fcu.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"


def _set_action(arm: bpy.types.Object, action: bpy.types.Action) -> None:
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action


def key_euler(pb: bpy.types.PoseBone, frame: int, deg: tuple[float, float, float]) -> None:
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (math.radians(deg[0]), math.radians(deg[1]), math.radians(deg[2]))
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def key_loc(pb: bpy.types.PoseBone, frame: int, loc: tuple[float, float, float]) -> None:
    pb.location = loc
    pb.keyframe_insert(data_path="location", frame=frame)


def _gait_frames(n_frames: int):
    yield from range(1, n_frames + 1)
    yield n_frames + 1


def _begin_action(arm: bpy.types.Object, name: str, n_frames: int) -> bpy.types.Action:
    select_active(arm)
    bpy.ops.object.mode_set(mode="POSE")
    _reset_pose(arm)
    action = bpy.data.actions.new(name=name)
    action.use_fake_user = True
    _set_action(arm, action)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = n_frames
    scene.frame_current = 1
    return action


def _commit_nla(arm: bpy.types.Object, action: bpy.types.Action) -> None:
    _smooth_action(action)
    bpy.ops.object.mode_set(mode="OBJECT")
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = None
    track = arm.animation_data.nla_tracks.new()
    track.name = action.name
    strip = track.strips.new(action.name, 1, action)
    strip.action = action
    strip.frame_start = 1
    strip.frame_end = int(round(action.frame_range[1]))
    strip.extrapolation = "NOTHING"
    strip.blend_type = "REPLACE"


def _key_fingers(arm: bpy.types.Object, side: str, frame: int, curl: float = 0.25) -> None:
    curls = {
        "Thumb": (6.0, 10.0, 8.0, 6.0),
        "Index": (8.0, 12.0, 14.0, 10.0),
        "Middle": (9.0, 13.0, 15.0, 11.0),
        "Ring": (10.0, 14.0, 16.0, 11.0),
        "Pinky": (11.0, 15.0, 16.0, 10.0),
    }
    sign = 1.0 if side == "Left" else -1.0
    for finger, ph in curls.items():
        for i, deg in enumerate(ph, 1):
            name = f"{side}Hand{finger}{i}"
            if f"mixamorig:{name}" not in arm.pose.bones:
                continue
            key_euler(_bone(arm, name), frame, (0.0, 0.0, deg * curl * sign))


def _key_arm(arm: bpy.types.Object, side: str, frame: int, swing: float, bend: float = 0.0, drop: float = 0.45) -> None:
    sign = 1.0 if side == "Left" else -1.0
    key_euler(_bone(arm, f"{side}Shoulder"), frame, (0.0, 0.0, 8.0 * sign * drop))
    key_euler(_bone(arm, f"{side}Arm"), frame, (6.0 * swing, -48.0 * drop * sign, 22.0 * swing))
    key_euler(_bone(arm, f"{side}ForeArm"), frame, (0.0, 0.0, 34.0 * bend * sign))
    key_euler(_bone(arm, f"{side}Hand"), frame, (0.0, 0.0, 6.0 * sign))
    _key_fingers(arm, side, frame, curl=0.18 + 0.08 * bend)


def _key_leg(arm: bpy.types.Object, side: str, frame: int, swing: float, plant: float) -> None:
    lift = 1.0 - plant
    key_euler(_bone(arm, f"{side}UpLeg"), frame, (26.0 * swing, 0.0, 0.0))
    key_euler(_bone(arm, f"{side}Leg"), frame, (38.0 * lift, 0.0, 0.0))
    key_euler(_bone(arm, f"{side}Foot"), frame, (-10.0 * lift - 6.0 * swing, 0.0, 0.0))
    key_euler(_bone(arm, f"{side}ToeBase"), frame, (5.0 * lift, 0.0, 0.0))


def animate_idle(arm: bpy.types.Object) -> bpy.types.Action:
    action = _begin_action(arm, "idle", CLIP_IDLE)
    two_pi = 2.0 * math.pi
    for frame in _gait_frames(CLIP_IDLE):
        t = (frame - 1) / CLIP_IDLE
        breathe = math.sin(two_pi * t)
        look = 0.35 * math.sin(two_pi * t)
        key_euler(_bone(arm, "Hips"), frame, (0.0, 0.0, 0.0))
        key_loc(_bone(arm, "Hips"), frame, (0.0, 0.0, 0.004 * breathe))
        key_euler(_bone(arm, "Spine"), frame, (2.4 * breathe, 0.0, 1.2 * look))
        key_euler(_bone(arm, "Spine1"), frame, (2.8 * breathe, 0.0, 1.4 * look))
        key_euler(_bone(arm, "Spine2"), frame, (2.0 * breathe, 0.0, 1.0 * look))
        key_euler(_bone(arm, "Neck"), frame, (-1.6 * breathe, 0.0, 4.0 * look))
        key_euler(_bone(arm, "Head"), frame, (-2.0 * breathe, 0.0, 6.0 * look))
        _key_arm(arm, "Left", frame, swing=0.08 + 0.04 * breathe, bend=0.20, drop=0.55)
        _key_arm(arm, "Right", frame, swing=-0.08 - 0.04 * breathe, bend=0.20, drop=0.55)
        _key_leg(arm, "Left", frame, 0.0, 1.0)
        _key_leg(arm, "Right", frame, 0.0, 1.0)
    _commit_nla(arm, action)
    return action


def animate_walk(arm: bpy.types.Object) -> bpy.types.Action:
    action = _begin_action(arm, "walk", CLIP_WALK)
    two_pi = 2.0 * math.pi
    for frame in _gait_frames(CLIP_WALK):
        t = (frame - 1) / CLIP_WALK
        left = math.sin(two_pi * t)
        right = math.sin(two_pi * t + math.pi)
        left_plant = 0.5 + 0.5 * math.cos(two_pi * t)
        right_plant = 0.5 + 0.5 * math.cos(two_pi * t + math.pi)
        bob = math.sin(two_pi * 2.0 * t)
        key_euler(_bone(arm, "Hips"), frame, (-2.0 + 1.5 * abs(left), 0.0, 5.0 * left))
        key_loc(_bone(arm, "Hips"), frame, (0.0, 0.0, 0.012 * abs(bob)))
        key_euler(_bone(arm, "Spine"), frame, (1.8 * bob, 0.0, 2.5 * left))
        key_euler(_bone(arm, "Spine1"), frame, (2.0 * bob, 0.0, 2.0 * left))
        key_euler(_bone(arm, "Spine2"), frame, (1.2 * bob, 0.0, -1.6 * left))
        key_euler(_bone(arm, "Neck"), frame, (-1.5 * bob, 0.0, -1.8 * left))
        key_euler(_bone(arm, "Head"), frame, (2.0 * bob, 0.0, 1.2 * left))
        _key_arm(arm, "Left", frame, swing=-left, bend=0.40 * max(0.0, -left), drop=0.62)
        _key_arm(arm, "Right", frame, swing=-right, bend=0.40 * max(0.0, -right), drop=0.62)
        _key_leg(arm, "Left", frame, left, left_plant)
        _key_leg(arm, "Right", frame, right, right_plant)
    _commit_nla(arm, action)
    return action


def animate_attack(arm: bpy.types.Object) -> bpy.types.Action:
    action = _begin_action(arm, "attack1", CLIP_ATTACK)
    keys = (
        (1, 0.05, -0.15, 0.10),
        (8, -0.55, 0.20, 0.35),
        (16, 0.85, -0.25, 0.05),
        (CLIP_ATTACK + 1, 0.05, -0.15, 0.10),
    )
    for frame, r_swing, l_swing, twist in keys:
        key_euler(_bone(arm, "Hips"), frame, (4.0 * twist, 0.0, -8.0 * r_swing))
        key_euler(_bone(arm, "Spine"), frame, (6.0 * twist, 0.0, -10.0 * r_swing))
        key_euler(_bone(arm, "Spine1"), frame, (8.0 * twist, 0.0, -8.0 * r_swing))
        key_euler(_bone(arm, "Spine2"), frame, (6.0 * twist, 0.0, -6.0 * r_swing))
        key_euler(_bone(arm, "Neck"), frame, (-4.0 * twist, 0.0, 6.0 * r_swing))
        key_euler(_bone(arm, "Head"), frame, (-2.0, 0.0, 8.0 * r_swing))
        _key_arm(arm, "Right", frame, swing=r_swing, bend=0.55 if r_swing < 0 else 0.10, drop=0.35)
        _key_arm(arm, "Left", frame, swing=l_swing, bend=0.20, drop=0.50)
        _key_leg(arm, "Left", frame, 0.08, 1.0)
        _key_leg(arm, "Right", frame, -0.06, 1.0)
    _commit_nla(arm, action)
    return action


def animate_die(arm: bpy.types.Object) -> bpy.types.Action:
    action = _begin_action(arm, "die", CLIP_DIE)
    hold = CLIP_DIE + 1
    poses = (
        (1, 0.0, 0.0, 0.0, 0.10, -0.10, 0.0),
        (10, 8.0, 12.0, 0.0, 0.25, -0.20, 0.15),
        (22, 28.0, 38.0, -0.10, 0.55, 0.15, 0.70),
        (hold, 42.0, 52.0, -0.18, 0.70, 0.20, 0.85),
    )
    for frame, hip_x, spine_x, hip_z, r_swing, l_swing, crumple in poses:
        key_euler(_bone(arm, "Hips"), frame, (hip_x, 0.0, 0.0))
        key_loc(_bone(arm, "Hips"), frame, (0.0, 0.12 * crumple, hip_z))
        key_euler(_bone(arm, "Spine"), frame, (spine_x, 0.0, 0.0))
        key_euler(_bone(arm, "Spine1"), frame, (spine_x * 0.85, 0.0, 0.0))
        key_euler(_bone(arm, "Spine2"), frame, (spine_x * 0.55, 0.0, 0.0))
        key_euler(_bone(arm, "Neck"), frame, (18.0 * crumple, 0.0, 0.0))
        key_euler(_bone(arm, "Head"), frame, (22.0 * crumple, 0.0, 0.0))
        _key_arm(arm, "Right", frame, swing=r_swing, bend=0.40 * crumple, drop=0.70)
        _key_arm(arm, "Left", frame, swing=l_swing, bend=0.40 * crumple, drop=0.70)
        key_euler(_bone(arm, "LeftUpLeg"), frame, (-18.0 * crumple, 0.0, 8.0 * crumple))
        key_euler(_bone(arm, "RightUpLeg"), frame, (-12.0 * crumple, 0.0, -8.0 * crumple))
        key_euler(_bone(arm, "LeftLeg"), frame, (55.0 * crumple, 0.0, 0.0))
        key_euler(_bone(arm, "RightLeg"), frame, (48.0 * crumple, 0.0, 0.0))
        key_euler(_bone(arm, "LeftFoot"), frame, (10.0 * crumple, 0.0, 0.0))
        key_euler(_bone(arm, "RightFoot"), frame, (8.0 * crumple, 0.0, 0.0))
    _commit_nla(arm, action)
    return action


def export_glb(path: str, arm: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    arm.hide_set(False)
    arm.select_set(True)
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            obj.hide_set(False)
            obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_skins=True,
        export_all_influences=True,
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
        export_force_sampling=True,
        export_nla_strips=True,
        export_anim_single_armature=True,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def report(arm: bpy.types.Object, actions: list[bpy.types.Action]) -> None:
    verts = tris = 0
    names = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        names.append(o.name)
        verts += len(o.data.vertices)
        tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
    print(f"  meshes={names}")
    print(f"  verts={verts} tris={tris} bones={len(arm.data.bones)}")
    hands = [b.name for b in arm.data.bones if "Hand" in b.name]
    print(f"  hand bones ({len(hands)})")
    for action in actions:
        n = int(round(action.frame_range[1] - action.frame_range[0]))
        print(f"  clip '{action.name}' ~{n}f @ {FPS}fps ({n / FPS:.2f}s)")


def main() -> None:
    ensure_textures()
    if not os.path.isfile(SRC_GLB):
        raise FileNotFoundError(SRC_GLB)
    clear_scene()
    print("\n=== PioneerMale — authored male head + male body, T-pose hands ===")
    bpy.ops.import_scene.gltf(filepath=SRC_GLB)
    bpy.context.view_layer.update()

    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name not in BODY_REGIONS:
            bpy.data.objects.remove(o, do_unlink=True)

    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = body_meshes()
    missing = [n for n in BODY_REGIONS if n not in meshes]
    if missing:
        raise RuntimeError(f"Missing body regions: {missing}")

    materials = mats()
    paint_skin(meshes, materials["skin"])

    for name, obj in meshes.items():
        if name in SKIP_MASCULINIZE:
            continue
        masculinize_mesh(obj)
        print(f"  masculinized {name}")

    head = meshes["base_body_head"]
    head_parts = build_male_head(arm, materials, head)
    print(f"  male head parts: {[o.name for o in head_parts]}")

    extras = dress(meshes, arm, materials)
    print(f"  clothing: {[o.name for o in extras]}")

    covered = (
        "base_body_lower_torso",
        "base_body_arm_upper",
        "base_body_arm_lower",
        "base_body_leg_upper",
        "base_body_leg_thigh",
        "base_body_leg_knee",
        "base_body_leg_shin",
        "base_body_leg_ankle",
        "base_body_foot",
    )
    for name in covered:
        obj = meshes.get(name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)

    actions = [animate_idle(arm), animate_walk(arm), animate_attack(arm), animate_die(arm)]
    report(arm, actions)
    for d in (VIEWER_MODELS, VIEWER_BUILDINGS, DESKTOP):
        export_glb(os.path.join(d, "PioneerMale.glb"), arm)
    print("DONE — PioneerMale exported.")


if __name__ == "__main__":
    main()
