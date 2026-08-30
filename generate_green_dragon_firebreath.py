"""
generate_green_dragon_firebreath.py
===================================
Author locomotion + combat clips on the chromatic dragons and attach
mouth-parented fire meshes for ``attack1``.

Sources (unrigged textured meshes — do not overwrite):
  ~/Desktop/Models/Creatures/Dragons/{Color}Dragon.glb

Rig / weight donor (same armature for every color):
  viewer/public/buildings/GreenDragon_cloudinary.glb

Output: ``viewer/public/buildings/{Color}Dragon.glb``

Shipped clips (exact lowercase names; source Idle / walk1 / walk2 /
attack_melee / attack_fire are stripped and not exported):

  idle       looping breath / tail sway
  walk       looping in-place trot
  run        looping in-place gallop (not a game state; extra clip)
  attack1    2.0 s fire-breath (client loops this as the ranged attack)
  attack2    1.5 s melee bite (rear-up, jaws open, lunge and snap)
  die        1.5 s sprawl — legs out, drop straight down

Run (all five colors by default; pass names after ``--``):
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_green_dragon_firebreath.py -- green blue red black violet
"""

from __future__ import annotations

import math
import os
import shutil
import sys

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree


ROOT = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.expanduser("~/Desktop/Models/Creatures")
MESH_DIR = os.path.join(DESKTOP_DIR, "Dragons")
BUILDINGS_DIR = os.path.join(ROOT, "viewer/public/buildings")
RIG_DONOR = os.path.join(BUILDINGS_DIR, "GreenDragon_cloudinary.glb")

WEIGHT_NEIGHBORS = 8
WEIGHT_POWER = 1.5
MAX_INFLUENCES = 4

DRAGONS = {
    "green": {
        "label": "Green Dragon",
        "src": os.path.join(MESH_DIR, "GreenDragon.glb"),
        "out": os.path.join(BUILDINGS_DIR, "GreenDragon.glb"),
        "desktop": "GreenDragon.glb",
    },
    "blue": {
        "label": "Blue Dragon",
        "src": os.path.join(MESH_DIR, "BlueDragon.glb"),
        "out": os.path.join(BUILDINGS_DIR, "BlueDragon.glb"),
        "desktop": "BlueDragon.glb",
    },
    "red": {
        "label": "Red Dragon",
        "src": os.path.join(MESH_DIR, "RedDragon.glb"),
        "out": os.path.join(BUILDINGS_DIR, "RedDragon.glb"),
        "desktop": "RedDragon.glb",
    },
    "black": {
        "label": "Black Dragon",
        "src": os.path.join(MESH_DIR, "BlackDragon.glb"),
        "out": os.path.join(BUILDINGS_DIR, "BlackDragon.glb"),
        "desktop": "BlackDragon.glb",
    },
    "violet": {
        "label": "Violet Dragon",
        "src": os.path.join(MESH_DIR, "VioletDragon.glb"),
        "out": os.path.join(BUILDINGS_DIR, "VioletDragon.glb"),
        "desktop": "VioletDragon.glb",
    },
}
DEFAULT_DRAGON_KEYS = ("green", "blue", "red", "black", "violet")
FPS = 24

CLIP_IDLE = 72  # 3.000 s loop — breath + tail, first/last pose match
CLIP_ATTACK1 = 48  # 2.000 s fire-breath (client loops this clip)
CLIP_WALK = 32  # 1.333 s loop
CLIP_RUN = 16  # 0.667 s loop
CLIP_ATTACK2 = 36  # 1.500 s melee bite
CLIP_DIE = 36  # 1.500 s play-once

ATTACK1_NAME = "attack1"


def _pulse(t: float, start: float, end: float) -> float:
    if t <= start or t >= end:
        return 0.0
    return math.sin(math.pi * (t - start) / (end - start))


def _smoothstep(t: float, start: float, end: float) -> float:
    if end <= start:
        return 1.0 if t >= end else 0.0
    u = max(0.0, min(1.0, (t - start) / (end - start)))
    return u * u * (3.0 - 2.0 * u)


def _plateau(t: float, rise0: float, rise1: float, fall0: float, fall1: float) -> float:
    if t < rise0:
        return 0.0
    if t < rise1:
        return _smoothstep(t, rise0, rise1)
    if t < fall0:
        return 1.0
    if t < fall1:
        return 1.0 - _smoothstep(t, fall0, fall1)
    return 0.0


def _reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _select_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _emission_material(
    name: str,
    color: tuple[float, float, float],
    strength: float,
    alpha: float,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        return mat
    rgba = (color[0], color[1], color[2], alpha)
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = rgba
    elif "Emission" in bsdf.inputs:
        bsdf.inputs["Emission"].default_value = rgba
    if "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = strength
    bsdf.inputs["Base Color"].default_value = rgba
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = alpha
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = 1.0
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def _ico(loc: tuple[float, float, float], scale: tuple[float, float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=loc)
    obj = bpy.context.view_layer.objects.active
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def _join_named(name: str, objects: list[bpy.types.Object]) -> bpy.types.Object:
    _select_active(objects[0])
    for extra in objects[1:]:
        extra.select_set(True)
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    return joined


def _make_mouth_fire() -> bpy.types.Object:
    """Volume of overlapping wisps that sit inside the open jaws."""
    white = _emission_material("DragonFireMouthHot", (1.0, 0.96, 0.72), 36.0, 0.88)
    gold = _emission_material("DragonFireMouthMid", (1.0, 0.62, 0.16), 24.0, 0.72)
    orange = _emission_material("DragonFireMouthCool", (1.0, 0.28, 0.05), 16.0, 0.55)
    parts = [
        _ico((0.00, 0.04, 0.00), (0.22, 0.28, 0.20), white),
        _ico((0.00, 0.16, 0.02), (0.30, 0.34, 0.26), gold),
        _ico((0.10, 0.10, -0.04), (0.18, 0.22, 0.16), gold),
        _ico((-0.09, 0.12, 0.05), (0.17, 0.22, 0.15), gold),
        _ico((0.00, 0.28, 0.00), (0.26, 0.32, 0.22), orange),
        _ico((0.06, -0.04, 0.03), (0.14, 0.16, 0.12), white),
        _ico((-0.05, -0.02, -0.03), (0.13, 0.15, 0.12), gold),
        _ico((0.00, 0.38, 0.06), (0.16, 0.22, 0.14), orange),
    ]
    return _join_named("DragonFireMouth", parts)


def _make_jet_fire() -> bpy.types.Object:
    """Irregular wisp chain, not a clean cone."""
    hot = _emission_material("DragonFireJetHot", (1.0, 0.90, 0.42), 30.0, 0.70)
    mid = _emission_material("DragonFireJetMid", (1.0, 0.40, 0.06), 20.0, 0.58)
    cool = _emission_material("DragonFireJetCool", (0.95, 0.14, 0.02), 12.0, 0.42)
    parts: list[bpy.types.Object] = []
    # Same reach along +Y; wider X/Z so the stream reads as a round blast.
    wisps = [
        ((0.00, 0.35, 0.00), (0.18, 0.28, 0.18), hot),
        ((0.08, 0.85, 0.04), (0.38, 0.40, 0.34), hot),
        ((-0.12, 1.25, -0.06), (0.48, 0.48, 0.42), mid),
        ((0.16, 1.75, 0.08), (0.55, 0.58, 0.48), mid),
        ((-0.10, 2.20, -0.08), (0.52, 0.62, 0.46), mid),
        ((0.18, 2.70, 0.06), (0.46, 0.70, 0.40), cool),
        ((-0.16, 3.15, -0.08), (0.38, 0.62, 0.34), cool),
        ((0.08, 3.55, 0.04), (0.28, 0.48, 0.24), cool),
        ((-0.04, 3.90, -0.03), (0.16, 0.32, 0.14), cool),
        ((0.32, 1.55, 0.16), (0.24, 0.28, 0.22), mid),
        ((-0.30, 2.05, -0.14), (0.22, 0.30, 0.20), mid),
        ((0.26, 2.95, 0.12), (0.20, 0.34, 0.18), cool),
        ((0.00, 2.40, 0.22), (0.36, 0.40, 0.32), mid),
        ((0.00, 2.40, -0.20), (0.34, 0.40, 0.30), mid),
    ]
    for loc, scale, mat in wisps:
        parts.append(_ico(loc, scale, mat))
    return _join_named("DragonFireBreath", parts)


def _add_fire_bones(arm: bpy.types.Object) -> None:
    _select_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = arm.data.edit_bones
    parent = ebs["Bone.003"]
    upper = ebs["Bone.004"]
    jaw = ebs["Bone.LowerJaw"]
    lips = (upper.tail + jaw.tail) * 0.5
    direction = (upper.tail - upper.head).normalized()
    cavity = lips - direction * 0.34

    if "FireMouth" not in ebs:
        mouth = ebs.new("FireMouth")
        mouth.parent = parent
        mouth.use_deform = False
        mouth.head = cavity
        mouth.tail = cavity + direction * 0.28

    if "FireBreath" not in ebs:
        jet = ebs.new("FireBreath")
        jet.parent = parent
        jet.use_deform = False
        jet.head = lips + direction * 0.02
        jet.tail = lips + direction * 0.68
    bpy.ops.object.mode_set(mode="OBJECT")


def _parent_to_bone(
    obj: bpy.types.Object,
    arm: bpy.types.Object,
    bone: str,
    loc: tuple[float, float, float],
) -> None:
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.location = loc
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)


def _drop_orphan_icospheres() -> None:
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and obj.name.startswith("Icosphere") and obj.parent is None:
            bpy.data.objects.remove(obj, do_unlink=True)


def _world_aabb(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    mw = obj.matrix_world
    pts = [mw @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _align_mesh_to_donor(mesh: bpy.types.Object, donor: bpy.types.Object) -> None:
    """Uniform-scale + translate the origin-centered mesh onto the donor AABB."""
    d_lo, d_hi = _world_aabb(donor)
    n_lo, n_hi = _world_aabb(mesh)
    d_ext = d_hi - d_lo
    n_ext = n_hi - n_lo
    if min(n_ext) < 1e-6:
        raise RuntimeError(f"Authored mesh {mesh.name} has a degenerate AABB")
    scale = d_ext.x / n_ext.x
    mesh.scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    n_lo, n_hi = _world_aabb(mesh)
    mesh.location += ((d_lo + d_hi) * 0.5) - ((n_lo + n_hi) * 0.5)
    bpy.context.view_layer.update()
    _select_active(mesh)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def _transfer_weights(
    mesh: bpy.types.Object,
    donors: list[bpy.types.Object],
) -> None:
    positions: list[Vector] = []
    weights: list[dict[str, float]] = []
    for src in donors:
        vg_names = {vg.index: vg.name for vg in src.vertex_groups}
        mw = src.matrix_world
        for v in src.data.vertices:
            groups = {}
            for g in v.groups:
                name = vg_names.get(g.group)
                if name and g.weight > 1e-4:
                    groups[name] = g.weight
            if not groups:
                continue
            positions.append(mw @ v.co)
            weights.append(groups)
    if not positions:
        raise RuntimeError("Donor meshes have no weighted vertices")

    kd = KDTree(len(positions))
    for i, pos in enumerate(positions):
        kd.insert(pos, i)
    kd.balance()

    for vg in list(mesh.vertex_groups):
        mesh.vertex_groups.remove(vg)
    vg_cache: dict[str, bpy.types.VertexGroup] = {}

    max_dist = 0.0
    total_dist = 0.0
    mw = mesh.matrix_world
    for idx, v in enumerate(mesh.data.vertices):
        world = mw @ v.co
        neighbors = kd.find_n(world, WEIGHT_NEIGHBORS)
        nearest = neighbors[0][2] if neighbors else 0.0
        max_dist = max(max_dist, nearest)
        total_dist += nearest
        inv_w = [(i, 1.0 / (dist ** WEIGHT_POWER + 1e-8)) for _co, i, dist in neighbors]
        denom = sum(w for _i, w in inv_w) or 1.0
        blended: dict[str, float] = {}
        for body_i, w in inv_w:
            factor = w / denom
            for name, bw in weights[body_i].items():
                blended[name] = blended.get(name, 0.0) + bw * factor
        top = sorted(blended.items(), key=lambda x: x[1], reverse=True)[:MAX_INFLUENCES]
        wtotal = sum(w for _n, w in top)
        if wtotal <= 0:
            continue
        for name, w in top:
            nw = w / wtotal
            if nw <= 1e-4:
                continue
            vg = vg_cache.get(name)
            if vg is None:
                vg = mesh.vertex_groups.new(name=name)
                vg_cache[name] = vg
            vg.add([idx], nw, "REPLACE")

    n = max(len(mesh.data.vertices), 1)
    print(
        f"  weights: {len(vg_cache)} groups  "
        f"nn avg={total_dist / n:.4f} max={max_dist:.4f}"
    )
    if max_dist > 0.75:
        raise RuntimeError(f"Weight transfer too far from donor (max {max_dist:.3f} m)")


def _bind_authored_mesh(arm: bpy.types.Object, mesh_path: str) -> bpy.types.Object:
    donors = [
        obj for obj in bpy.data.objects
        if obj.type == "MESH" and obj.vertex_groups and obj.parent == arm
    ]
    if not donors:
        donors = [
            obj for obj in bpy.data.objects
            if obj.type == "MESH" and obj.vertex_groups
        ]
    if not donors:
        raise RuntimeError("No weighted donor meshes on the dragon armature")
    donor_body = max(donors, key=lambda o: len(o.data.vertices))

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=mesh_path)
    newcomers = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    if not newcomers:
        raise RuntimeError(f"No mesh in {mesh_path}")
    mesh = newcomers[0]
    if len(newcomers) > 1:
        _select_active(mesh)
        for extra in newcomers[1:]:
            extra.select_set(True)
        bpy.ops.object.join()
        mesh = bpy.context.view_layer.objects.active

    _align_mesh_to_donor(mesh, donor_body)
    d_lo, d_hi = _world_aabb(donor_body)
    n_lo, n_hi = _world_aabb(mesh)
    print(
        f"  aligned AABB  donor x[{d_lo.x:.2f},{d_hi.x:.2f}] "
        f"y[{d_lo.y:.2f},{d_hi.y:.2f}] z[{d_lo.z:.2f},{d_hi.z:.2f}]"
    )
    print(
        f"             mesh  x[{n_lo.x:.2f},{n_hi.x:.2f}] "
        f"y[{n_lo.y:.2f},{n_hi.y:.2f}] z[{n_lo.z:.2f},{n_hi.z:.2f}]"
    )
    _transfer_weights(mesh, donors)

    mesh.name = "DragonMesh"
    mw = mesh.matrix_world.copy()
    mesh.parent = arm
    mesh.matrix_parent_inverse = arm.matrix_world.inverted()
    mesh.matrix_world = mw
    for mod in list(mesh.modifiers):
        if mod.type == "ARMATURE":
            mesh.modifiers.remove(mod)
    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True

    keep = {arm, mesh}
    for obj in list(bpy.data.objects):
        if obj in keep:
            continue
        if obj.type in {"MESH", "ARMATURE", "EMPTY"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    return mesh


def _key_euler(pb: bpy.types.PoseBone, frame: int, deg: tuple[float, float, float]) -> None:
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (
        math.radians(deg[0]),
        math.radians(deg[1]),
        math.radians(deg[2]),
    )
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def _key_loc(pb: bpy.types.PoseBone, frame: int, loc: tuple[float, float, float]) -> None:
    pb.location = loc
    pb.keyframe_insert(data_path="location", frame=frame)


def _key_scale(pb: bpy.types.PoseBone, frame: int, scale: tuple[float, float, float]) -> None:
    pb.scale = scale
    pb.keyframe_insert(data_path="scale", frame=frame)


def _smooth_action(action: bpy.types.Action) -> None:
    for fcu in action.fcurves:
        for kp in fcu.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"


def _reset_pose(arm: bpy.types.Object) -> None:
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
        if pb.name in ("FireBreath", "FireMouth"):
            pb.scale = (0.001, 0.001, 0.001)


def _remove_nla_track(arm: bpy.types.Object, name: str) -> None:
    if arm.animation_data is None:
        return
    for track in list(arm.animation_data.nla_tracks):
        if track.name == name:
            arm.animation_data.nla_tracks.remove(track)


def _strip_imported_animations() -> None:
    """Drop every imported action / NLA strip so only authored clips export."""
    for obj in bpy.data.objects:
        ad = obj.animation_data
        if ad is None:
            continue
        for track in list(ad.nla_tracks):
            ad.nla_tracks.remove(track)
        ad.action = None
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)


def _begin_action(arm: bpy.types.Object, name: str, n_frames: int) -> bpy.types.Action:
    _select_active(arm)
    bpy.ops.object.mode_set(mode="POSE")
    _reset_pose(arm)
    # Drop a previous authoring of this clip so re-runs stay clean.
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    action = bpy.data.actions.new(name=name)
    action.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
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
    _remove_nla_track(arm, action.name)
    track = arm.animation_data.nla_tracks.new()
    track.name = action.name
    track.strips.new(action.name, 1, action)


def _hide_fire(bones, frame: int) -> None:
    for name in ("FireBreath", "FireMouth"):
        if name in bones:
            _key_scale(bones[name], frame, (0.001, 0.001, 0.001))


def _key_front_leg(
    bones: bpy.types.bpy_prop_collection,
    side: str,
    frame: int,
    *,
    swing: float,
    lift: float,
    fold: float,
) -> None:
    """side 'L' uses +Y forward; 'R' uses -Y forward (mirrored bone)."""
    sign = 1.0 if side == "L" else -1.0
    sh = bones[f"Bone_{side}"]
    el = bones[f"Bone_{side}.001"]
    wr = bones[f"Bone_{side}.002"]
    _key_euler(sh, frame, (18.0 * lift, sign * 22.0 * swing, sign * 4.0 * swing))
    _key_euler(el, frame, (28.0 * fold, sign * 4.0 * swing, 0.0))
    _key_euler(wr, frame, (-8.0 * fold - 4.0 * swing, sign * -6.0 * swing, 0.0))


def _key_hind_leg(
    bones: bpy.types.bpy_prop_collection,
    side: str,
    frame: int,
    *,
    swing: float,
    lift: float,
    fold: float,
) -> None:
    sign = 1.0 if side == "L" else -1.0
    hip = bones[f"Bone.006_{side}"]
    knee = bones[f"Bone.006_{side}.001"]
    ankle = bones[f"Bone.006_{side}.002"]
    _key_euler(hip, frame, (6.0 * lift, sign * 20.0 * swing, sign * 3.0 * swing))
    _key_euler(knee, frame, (32.0 * fold, sign * 3.0 * swing, 0.0))
    _key_euler(ankle, frame, (-6.0 * fold, sign * -5.0 * swing, 0.0))


def _key_front_leg_walk(
    bones: bpy.types.bpy_prop_collection,
    side: str,
    frame: int,
    swing: float,
) -> None:
    """Sagittal-only stride. Local X/Z abduct and cross; keep Y only."""
    sign = 1.0 if side == "L" else -1.0
    _key_euler(bones[f"Bone_{side}"], frame, (0.0, sign * 28.0 * swing, 0.0))
    _key_euler(bones[f"Bone_{side}.001"], frame, (0.0, sign * 6.0 * swing, 0.0))
    _key_euler(bones[f"Bone_{side}.002"], frame, (0.0, sign * -10.0 * swing, 0.0))


def _key_hind_leg_walk(
    bones: bpy.types.bpy_prop_collection,
    side: str,
    frame: int,
    swing: float,
) -> None:
    sign = 1.0 if side == "L" else -1.0
    _key_euler(bones[f"Bone.006_{side}"], frame, (0.0, sign * 24.0 * swing, 0.0))
    _key_euler(bones[f"Bone.006_{side}.001"], frame, (0.0, sign * 7.0 * swing, 0.0))
    _key_euler(bones[f"Bone.006_{side}.002"], frame, (0.0, sign * -8.0 * swing, 0.0))


IK_LEG_CHAINS = (
    ("Bone_L.002", ("Bone_L", "Bone_L.001", "Bone_L.002")),
    ("Bone_R.002", ("Bone_R", "Bone_R.001", "Bone_R.002")),
    ("Bone.006_L.002", ("Bone.006_L", "Bone.006_L.001", "Bone.006_L.002")),
    ("Bone.006_R.002", ("Bone.006_R", "Bone.006_R.001", "Bone.006_R.002")),
)
FOOT_BONES = (
    "Bone_L.003",
    "Bone_R.003",
    "Bone.006_L.003",
    "Bone.006_R.003",
)


def _setup_foot_iks(arm: bpy.types.Object, targets: dict):
    bones = arm.pose.bones
    for ik_bone, _chain in IK_LEG_CHAINS:
        pb = bones[ik_bone]
        for c in list(pb.constraints):
            if c.name == "plantIK":
                pb.constraints.remove(c)
        c = pb.constraints.new("IK")
        c.name = "plantIK"
        c.target = targets[ik_bone]
        c.chain_count = 3
        c.use_tail = True
        c.iterations = 120
        c.weight = 1.0


def _clear_foot_iks(arm: bpy.types.Object, targets: dict) -> None:
    bones = arm.pose.bones
    for ik_bone, _chain in IK_LEG_CHAINS:
        pb = bones.get(ik_bone)
        if pb is None:
            continue
        for c in list(pb.constraints):
            if c.name == "plantIK":
                pb.constraints.remove(c)
    for obj in targets.values():
        bpy.data.objects.remove(obj, do_unlink=True)


def _bake_ik_legs(arm: bpy.types.Object, frame: int) -> None:
    """Reset legs to rest, let IK reach the plant empties, key the result."""
    bones = arm.pose.bones
    names = [n for _ik, chain in IK_LEG_CHAINS for n in chain]
    for ik_bone, _chain in IK_LEG_CHAINS:
        for c in bones[ik_bone].constraints:
            if c.name == "plantIK":
                c.mute = False
    for name in names:
        pb = bones[name]
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()
    mats = {name: bones[name].matrix.copy() for name in names}
    for ik_bone, _chain in IK_LEG_CHAINS:
        for c in bones[ik_bone].constraints:
            if c.name == "plantIK":
                c.mute = True
    for _ik, chain in IK_LEG_CHAINS:
        for name in chain:
            pb = bones[name]
            pb.rotation_mode = "XYZ"
            pb.matrix = mats[name]
            pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def _lock_feet_idle(arm: bpy.types.Object, rest_foot_mats: dict, frame: int) -> None:
    """Keep pads at idle world rotation so they stay flat, not IK-tilted."""
    from mathutils import Matrix
    bones = arm.pose.bones
    bpy.context.view_layer.update()
    for name in FOOT_BONES:
        pb = bones[name]
        pb.rotation_mode = "XYZ"
        loc = pb.matrix.to_translation()
        rest_rot = rest_foot_mats[name].to_quaternion()
        scl = pb.matrix.to_scale()
        pb.matrix = Matrix.LocRotScale(loc, rest_rot, scl)
        pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def _key_wings(
    bones: bpy.types.bpy_prop_collection,
    frame: int,
    *,
    raise_deg: float,
    flare: float,
    fold: float,
) -> None:
    _key_euler(bones["Bone_L.016"], frame, (raise_deg - 4.0 * fold, 6.0 * fold, flare))
    _key_euler(bones["Bone_R.016"], frame, (raise_deg - 4.0 * fold, -6.0 * fold, -flare))
    _key_euler(bones["Bone_L.018"], frame, (8.0 * raise_deg * 0.15, 0.0, 10.0 * flare * 0.2))
    _key_euler(bones["Bone_R.018"], frame, (8.0 * raise_deg * 0.15, 0.0, -10.0 * flare * 0.2))


def _key_wings_up(bones, frame: int, raise_deg: float) -> None:
    """Lift wings on local +X only. Local Z folds them forward across the chest."""
    _key_euler(bones["Bone_L.016"], frame, (raise_deg, 0.0, 0.0))
    _key_euler(bones["Bone_R.016"], frame, (raise_deg, 0.0, 0.0))
    _key_euler(bones["Bone_L.018"], frame, (raise_deg * 0.42, 0.0, 0.0))
    _key_euler(bones["Bone_R.018"], frame, (raise_deg * 0.42, 0.0, 0.0))


def _key_wings_melee(bones, frame: int, open_amt: float) -> None:
    """Spread wings back and out for the claw swipe.

    ``_key_wings`` flare is local Z and folds both membranes across the
    chest/neck. The sampled bird-open pose keeps tips ~±4 X, behind the neck.
    """
    x = 2.0 * open_amt
    y = 18.0 * open_amt
    z = -32.0 * open_amt
    _key_euler(bones["Bone_L.016"], frame, (x, y, z))
    _key_euler(bones["Bone_R.016"], frame, (x, -y, -z))
    x18 = 28.0 * open_amt
    _key_euler(bones["Bone_L.018"], frame, (x18, 0.0, 0.0))
    _key_euler(bones["Bone_R.018"], frame, (x18, 0.0, 0.0))


def _key_wings_breath(bones, frame: int, open_amt: float, down_amt: float) -> None:
    """Bird-open on rear-up, then fold for the blast with tips kept above ground.

    Full old down pose put the tip at ~Z -0.4 (through the floor). This down
    pose is shallower so membrane verts stay above Z 0.
    """
    # Left 016: open (2, 18, -32), down (-5, 10, -8) — spread, not into dirt.
    x = 2.0 * open_amt - 5.0 * down_amt
    y = 18.0 * open_amt + 10.0 * down_amt
    z = -32.0 * open_amt - 8.0 * down_amt
    _key_euler(bones["Bone_L.016"], frame, (x, y, z))
    _key_euler(bones["Bone_R.016"], frame, (x, -y, -z))
    # Outer wing: open lifts (+32 X); shallow fold instead of -28 X into the floor.
    x18 = 32.0 * open_amt - 10.0 * down_amt
    z18 = 6.0 * down_amt
    _key_euler(bones["Bone_L.018"], frame, (x18, 0.0, z18))
    _key_euler(bones["Bone_R.018"], frame, (x18, 0.0, -z18))


def _key_tail(
    bones: bpy.types.bpy_prop_collection,
    frame: int,
    *,
    sway: float,
    pitch: float,
) -> None:
    _key_euler(bones["Bone.006"], frame, (pitch, 0.0, sway))
    _key_euler(bones["Bone.007"], frame, (pitch * 0.7, 0.0, sway * 1.15))
    _key_euler(bones["Bone.008"], frame, (pitch * 0.5, 0.0, sway * 1.25))
    if "Bone.009" in bones:
        _key_euler(bones["Bone.009"], frame, (pitch * 0.3, 0.0, sway * 1.1))


def _gait_frames(n_frames: int):
    """Inclusive 1..n_frames+1 so first and last poses match for looping."""
    return range(1, n_frames + 2)


# ── Clips ─────────────────────────────────────────────────────────────────

def animate_idle(arm: bpy.types.Object) -> bpy.types.Action:
    """Looping rest: chest breath, slow head look, wing lift, tail sway."""
    action = _begin_action(arm, "idle", CLIP_IDLE)
    bones = arm.pose.bones
    two_pi = 2.0 * math.pi

    for frame in _gait_frames(CLIP_IDLE):
        t = (frame - 1) / CLIP_IDLE
        breath = 0.5 + 0.5 * math.sin(two_pi * t)
        look = math.sin(two_pi * t)

        # Do not pitch Waist — that drags planted feet through the floor.
        _key_euler(bones["Bone"], frame, (4.0 * breath, 0.0, 0.0))
        _key_euler(bones["Bone.001"], frame, (2.5 * breath, 0.0, 3.0 * look))
        if "Bone.002" in bones:
            _key_euler(bones["Bone.002"], frame, (1.5 * breath, 0.0, 0.0))
        _key_euler(bones["Bone.003"], frame, (2.0 * breath, 0.0, 2.0 * look))
        _key_euler(bones["Bone.004"], frame, (1.5 * breath, 0.0, 0.0))
        _key_euler(bones["Bone.LowerJaw"], frame, (-3.0 * breath, 0.0, 0.0))
        _key_wings_up(bones, frame, 2.0 + 3.0 * breath)
        _key_tail(bones, frame, sway=5.0 * look, pitch=-2.5 * breath)
        _hide_fire(bones, frame)

    _commit_nla(arm, action)
    return action


def animate_walk(arm: bpy.types.Object) -> bpy.types.Action:
    action = _begin_action(arm, "walk", CLIP_WALK)
    bones = arm.pose.bones
    two_pi = 2.0 * math.pi

    for frame in _gait_frames(CLIP_WALK):
        t = (frame - 1) / CLIP_WALK
        # Trot: front-left with hind-right. Y-only so feet stay on rails.
        fl = math.sin(two_pi * t)
        fr = math.sin(two_pi * t + math.pi)
        stride = math.sin(two_pi * t)

        _key_euler(bones["Bone"], frame, (-2.0 + 2.5 * abs(fl), 0.0, 0.0))
        _key_euler(bones["Bone.001"], frame, (-3.0 * stride, 0.0, 0.0))
        _key_euler(bones["Bone.003"], frame, (2.0 * stride, 0.0, 0.0))
        _key_front_leg_walk(bones, "L", frame, fl)
        _key_front_leg_walk(bones, "R", frame, fr)
        _key_hind_leg_walk(bones, "L", frame, fr)
        _key_hind_leg_walk(bones, "R", frame, fl)
        # One slow wing pulse per stride — not |sin(4πt)|.
        flap = math.sin(two_pi * t)
        _key_wings(bones, frame, raise_deg=3.0 + 2.0 * flap, flare=2.5, fold=0.04)
        _key_tail(bones, frame, sway=3.0 * stride, pitch=-2.0 * math.sin(two_pi * 2.0 * t))
        _hide_fire(bones, frame)

    _commit_nla(arm, action)
    return action


def animate_run(arm: bpy.types.Object) -> bpy.types.Action:
    action = _begin_action(arm, "run", CLIP_RUN)
    bones = arm.pose.bones
    two_pi = 2.0 * math.pi

    for frame in _gait_frames(CLIP_RUN):
        t = (frame - 1) / CLIP_RUN
        # Same diagonal trot as walk — longer, faster stride.
        fl = math.sin(two_pi * t)
        fr = math.sin(two_pi * t + math.pi)
        stride = math.sin(two_pi * t)

        _key_euler(bones["Bone"], frame, (-3.0 + 4.0 * abs(fl), 0.0, 0.0))
        _key_euler(bones["Bone.001"], frame, (-5.0 * stride, 0.0, 0.0))
        _key_euler(bones["Bone.003"], frame, (3.0 * stride, 0.0, 0.0))
        _key_front_leg_walk(bones, "L", frame, fl * 1.4)
        _key_front_leg_walk(bones, "R", frame, fr * 1.4)
        _key_hind_leg_walk(bones, "L", frame, fr * 1.4)
        _key_hind_leg_walk(bones, "R", frame, fl * 1.4)
        _key_wings_up(bones, frame, 5.0 + 3.5 * math.sin(two_pi * t))
        _key_tail(bones, frame, sway=4.0 * stride, pitch=-5.0 * math.sin(two_pi * 2.0 * t))
        _hide_fire(bones, frame)

    _commit_nla(arm, action)
    return action


def animate_attack2(arm: bpy.types.Object) -> bpy.types.Action:
    """Melee bite: rear up with jaws open, then lunge forward and snap shut. No fire."""
    action = _begin_action(arm, "attack2", CLIP_ATTACK2)
    bones = arm.pose.bones
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()

    rest_pos = {
        "Bone_L.002": arm.matrix_world @ bones["Bone_L.002"].tail,
        "Bone_R.002": arm.matrix_world @ bones["Bone_R.002"].tail,
        "Bone.006_L.002": arm.matrix_world @ bones["Bone.006_L.002"].tail,
        "Bone.006_R.002": arm.matrix_world @ bones["Bone.006_R.002"].tail,
    }
    rest_foot_mats = {name: bones[name].matrix.copy() for name in FOOT_BONES}
    ik_targets = {}
    for name, loc in rest_pos.items():
        empty = bpy.data.objects.new(f"Plant_{name}", None)
        bpy.context.collection.objects.link(empty)
        empty.empty_display_size = 0.06
        empty.location = loc
        ik_targets[name] = empty
    _setup_foot_iks(arm, ik_targets)

    for frame in range(1, CLIP_ATTACK2 + 1):
        t = (frame - 1) / max(CLIP_ATTACK2 - 1, 1)
        rear = _pulse(t, 0.00, 0.40)
        lunge = _plateau(t, 0.22, 0.34, 0.52, 0.78)
        gape = _plateau(t, 0.02, 0.12, 0.26, 0.40)
        snap = _pulse(t, 0.28, 0.55)
        recover = _smoothstep(t, 0.72, 1.00)
        scene.frame_set(frame)

        # Chest -X leans the bite forward and down. Neck +X extends the snout
        # along that lean (all-negative neck curled the head in place).
        _key_euler(bones["Bone"], frame, (
            18.0 * rear - 38.0 * lunge - 2.0 * recover,
            0.0,
            0.0,
        ))
        _key_euler(bones["Bone.001"], frame, (
            14.0 * rear - 14.0 * lunge,
            0.0,
            0.0,
        ))
        if "Bone.002" in bones:
            _key_euler(bones["Bone.002"], frame, (6.0 * rear + 8.0 * lunge, 0.0, 0.0))
        _key_euler(bones["Bone.003"], frame, (
            8.0 * rear + 20.0 * lunge,
            0.0,
            0.0,
        ))
        _key_euler(bones["Bone.004"], frame, (
            4.0 * rear + 14.0 * lunge,
            0.0,
            0.0,
        ))
        # Open on the rear-up, slam shut on the lunge (snap overrides leftover gape).
        _key_euler(bones["Bone.LowerJaw"], frame, (
            -52.0 * gape * (1.0 - snap) + 10.0 * snap,
            0.0,
            0.0,
        ))

        if "Bone.005" in bones:
            # Sink the hips on the lunge so IK folds the knees instead of
            # leaving a near-rest crouch.
            _key_euler(bones["Bone.005"], frame, (8.0 * rear - 16.0 * lunge, 0.0, 0.0))
        _key_wings_melee(bones, frame, 0.58 + 0.32 * rear)
        _key_tail(
            bones, frame,
            sway=4.0 * math.sin(t * math.pi * 2.0) * lunge,
            pitch=8.0 * rear - 6.0 * lunge,
        )
        _hide_fire(bones, frame)

        # IK plants the ankles; feet are then locked to idle world rotation.
        _bake_ik_legs(arm, frame)
        _lock_feet_idle(arm, rest_foot_mats, frame)

    _clear_foot_iks(arm, ik_targets)

    _commit_nla(arm, action)
    return action


def animate_die(arm: bpy.types.Object) -> bpy.types.Action:
    """Sprawl all four legs out and drop straight down. No side roll."""
    action = _begin_action(arm, "die", CLIP_DIE)
    bones = arm.pose.bones

    for frame in range(1, CLIP_DIE + 1):
        t = (frame - 1) / max(CLIP_DIE - 1, 1)
        flinch = _pulse(t, 0.00, 0.16)
        sprawl = _smoothstep(t, 0.04, 0.20)
        fall_s = _smoothstep(t, 0.10, 0.58)
        settle = _smoothstep(t, 0.58, 1.00)

        # Sagittal collapse only — Waist Y was the old side roll.
        _key_euler(bones["Waist"], frame, (
            4.0 * flinch + 58.0 * fall_s + 8.0 * settle,
            0.0,
            0.0,
        ))
        # Lower the body so the collapse is a drop, not a see-saw (hips up).
        _key_loc(bones["Waist"], frame, (0.0, 0.0, -1.4 * fall_s))
        _key_euler(bones["Bone"], frame, (
            -6.0 * flinch - 8.0 * fall_s,
            0.0,
            0.0,
        ))
        if "Bone.002" in bones:
            _key_euler(bones["Bone.002"], frame, (4.0 * fall_s, 0.0, 0.0))
        _key_euler(bones["Bone.001"], frame, (6.0 * fall_s + 4.0 * settle, 0.0, 0.0))
        _key_euler(bones["Bone.003"], frame, (8.0 * fall_s + 4.0 * settle, 0.0, 0.0))
        _key_euler(bones["Bone.004"], frame, (10.0 * fall_s, 0.0, 0.0))
        _key_euler(bones["Bone.LowerJaw"], frame, (
            -8.0 * flinch - 26.0 * fall_s - 10.0 * settle,
            0.0,
            0.0,
        ))

        # Local X abducts. Same sign on L and R spreads both sides.
        for side, sign in (("L", 1.0), ("R", -1.0)):
            _key_euler(bones[f"Bone_{side}"], frame, (
                52.0 * sprawl,
                sign * (-6.0 * fall_s),
                0.0,
            ))
            _key_euler(bones[f"Bone_{side}.001"], frame, (22.0 * sprawl, 0.0, 0.0))
            _key_euler(bones[f"Bone_{side}.002"], frame, (-8.0 * sprawl, 0.0, 0.0))
            _key_euler(bones[f"Bone_{side}.003"], frame, (0.0, 0.0, 0.0))
            _key_euler(bones[f"Bone.006_{side}"], frame, (
                -48.0 * sprawl,
                sign * (8.0 * fall_s),
                0.0,
            ))
            _key_euler(bones[f"Bone.006_{side}.001"], frame, (26.0 * sprawl, 0.0, 0.0))
            _key_euler(bones[f"Bone.006_{side}.002"], frame, (-10.0 * sprawl, 0.0, 0.0))
            if f"Bone.006_{side}.003" in bones:
                _key_euler(bones[f"Bone.006_{side}.003"], frame, (0.0, 0.0, 0.0))

        if "Bone.005" in bones:
            _key_euler(bones["Bone.005"], frame, (6.0 * fall_s, 0.0, 0.0))
        _key_wings_melee(bones, frame, 0.22 + 0.38 * sprawl * (1.0 - 0.4 * settle))
        _key_tail(
            bones, frame,
            sway=0.0,
            pitch=-14.0 * fall_s - 8.0 * settle,
        )
        _hide_fire(bones, frame)

    _commit_nla(arm, action)
    return action


def animate_attack1(arm: bpy.types.Object) -> bpy.types.Action:
    action = _begin_action(arm, ATTACK1_NAME, CLIP_ATTACK1)
    bones = arm.pose.bones

    for frame in range(1, CLIP_ATTACK1 + 1):
        t = (frame - 1) / max(CLIP_ATTACK1 - 1, 1)
        # Pulse rear-up then immediately drive forward into the blast — no hold.
        rear = _pulse(t, 0.00, 0.38)
        blast = _plateau(t, 0.14, 0.26, 0.64, 0.88)
        roar = _plateau(t, 0.16, 0.28, 0.66, 0.90)
        mouth = _plateau(t, 0.16, 0.26, 0.68, 0.90)
        stream = _plateau(t, 0.24, 0.34, 0.62, 0.86)
        recover = _smoothstep(t, 0.78, 1.00)
        flicker = 0.82 + 0.18 * math.sin(t * math.pi * 22.0) if (mouth + stream) > 0.05 else 1.0

        # Chest +X lifts the snout on the rear-up. During the blast, drop
        # that lift and pitch the head forward so the jet stays level —
        # not skyward, not into the floor.
        _key_euler(bones["Waist"], frame, (-14.0 * rear - 4.0 * blast, 0.0, 0.0))
        _key_euler(bones["Bone"], frame, (
            22.0 * rear - 4.0 * blast - 4.0 * recover,
            0.0,
            0.0,
        ))
        _key_euler(bones["Bone.001"], frame, (
            18.0 * rear - 4.0 * blast,
            0.0,
            2.0 * math.sin(t * math.pi * 2.0) * stream,
        ))
        _key_euler(bones["Bone.002"], frame, (
            8.0 * rear - 2.0 * blast,
            0.0,
            0.0,
        ))
        _key_euler(bones["Bone.003"], frame, (
            6.0 * rear - 4.0 * roar,
            0.0,
            0.0,
        ))
        _key_euler(bones["Bone.004"], frame, (
            8.0 * rear - 12.0 * roar,
            0.0,
            0.0,
        ))
        _key_euler(bones["Bone.LowerJaw"], frame, (
            -10.0 * rear - 42.0 * roar,
            0.0,
            0.0,
        ))

        _key_front_leg_walk(bones, "L", frame, -0.35 * rear + 0.2 * blast)
        _key_front_leg_walk(bones, "R", frame, -0.35 * rear + 0.2 * blast)
        _key_hind_leg_walk(bones, "L", frame, 0.25 * rear)
        _key_hind_leg_walk(bones, "R", frame, 0.25 * rear)

        _key_euler(bones["Bone.005"], frame, (
            12.0 * rear + 4.0 * blast,
            0.0,
            0.0,
        ))
        _key_tail(
            bones, frame,
            sway=6.0 * math.sin(t * math.pi * 2.0) * stream,
            pitch=10.0 * rear - 4.0 * blast,
        )

        _key_wings_breath(bones, frame, open_amt=rear, down_amt=blast)

        if "FireMouth" in bones:
            s = max(0.001, mouth * flicker * 1.25)
            _key_scale(bones["FireMouth"], frame, (s * 1.15, s * 1.05, s * 1.10))
        if "FireBreath" in bones:
            sx = max(0.001, (0.25 * mouth + 0.95 * stream) * flicker)
            sy = max(0.001, (0.15 * mouth + 1.35 * stream) * flicker)
            _key_scale(bones["FireBreath"], frame, (sx * 1.65, sy, sx * 1.65))

    _commit_nla(arm, action)
    return action


def _hide_fire_on_other_clips(arm: bpy.types.Object) -> None:
    """Idle / walk / melee / new clips must keep mouth fire scaled away."""
    names = [n for n in ("FireBreath", "FireMouth") if n in arm.pose.bones]
    if not names or arm.animation_data is None:
        return
    bpy.ops.object.mode_set(mode="POSE")
    for track in arm.animation_data.nla_tracks:
        if track.name == ATTACK1_NAME:
            continue
        for strip in track.strips:
            act = strip.action
            if act is None:
                continue
            arm.animation_data.action = act
            start = int(round(act.frame_range[0])) or 1
            end = int(round(act.frame_range[1]))
            for name in names:
                pb = arm.pose.bones[name]
                pb.scale = (0.001, 0.001, 0.001)
                pb.keyframe_insert(data_path="scale", frame=start)
                if end != start:
                    pb.keyframe_insert(data_path="scale", frame=end)
    arm.animation_data.action = None
    bpy.ops.object.mode_set(mode="OBJECT")


def export_glb(path: str, arm: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    arm.hide_set(False)
    arm.select_set(True)
    for child in arm.children_recursive:
        child.hide_set(False)
        child.select_set(True)
    fx = bpy.data.objects.get("Armature.002")
    if fx is not None:
        bpy.data.objects.remove(fx, do_unlink=True)
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and obj.name.startswith("Icosphere") and obj.parent is None:
            bpy.data.objects.remove(obj, do_unlink=True)
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


def _parse_keys() -> list[str]:
    argv = sys.argv
    extra = argv[argv.index("--") + 1 :] if "--" in argv else []
    keys = [k.strip().lower() for k in extra if k.strip()]
    if not keys:
        return list(DEFAULT_DRAGON_KEYS)
    unknown = [k for k in keys if k not in DRAGONS]
    if unknown:
        raise ValueError(f"Unknown dragon(s) {unknown}. Known: {sorted(DRAGONS)}")
    return keys


def process_dragon(spec: dict) -> None:
    src = spec["src"]
    out = spec["out"]
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    if not os.path.isfile(RIG_DONOR):
        raise FileNotFoundError(RIG_DONOR)

    print(f"=== {spec['label']} clips + fire-breath ===")
    print(f"  mesh: {src}")
    print(f"  rig:  {RIG_DONOR}")
    _reset()
    bpy.ops.import_scene.gltf(filepath=RIG_DONOR)
    arm = bpy.data.objects.get("Armature")
    if arm is None:
        raise RuntimeError(f"Armature not found in {RIG_DONOR}")

    _bind_authored_mesh(arm, src)
    _add_fire_bones(arm)
    mouth = _make_mouth_fire()
    jet = _make_jet_fire()
    _parent_to_bone(mouth, arm, "FireMouth", (0.0, 0.02, 0.0))
    _parent_to_bone(jet, arm, "FireBreath", (0.0, 0.08, 0.0))
    _drop_orphan_icospheres()

    _strip_imported_animations()
    actions = [
        animate_idle(arm),
        animate_walk(arm),
        animate_run(arm),
        animate_attack1(arm),
        animate_attack2(arm),
        animate_die(arm),
    ]
    _hide_fire_on_other_clips(arm)

    for action in actions:
        n_frames = int(round(action.frame_range[1] - action.frame_range[0]))
        print(
            f"  action '{action.name}'  {n_frames} frames @ {FPS} fps "
            f"({n_frames / FPS:.3f} s)  fcurves={len(action.fcurves)}"
        )

    # Cows / sheep / farm birds face +Z in Y-up glTF (Grindscape rest pose).
    # Blender +Y forward exports as −Z; keep a 180° Z yaw on the armature
    # node (do not apply — apply drops armature yaw).
    arm.rotation_mode = "XYZ"
    arm.rotation_euler[2] += math.pi

    os.makedirs(os.path.dirname(out), exist_ok=True)
    export_glb(out, arm)
    print(f"  -> {out} ({os.path.getsize(out) / 1024.0:.1f} KB)")

    os.makedirs(DESKTOP_DIR, exist_ok=True)
    desktop_path = os.path.join(DESKTOP_DIR, spec["desktop"])
    shutil.copy2(out, desktop_path)
    print(f"  -> {desktop_path}")


def main() -> None:
    keys = _parse_keys()
    for key in keys:
        process_dragon(DRAGONS[key])
    print("DONE")


if __name__ == "__main__":
    main()
