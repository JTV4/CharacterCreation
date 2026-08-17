"""
generate_farm_chickens.py
=========================
Import authored hen + rooster meshes, sit them on the ground facing +Y,
skin them to a bird armature, and add a looping in-place ``walk`` clip.

Source meshes (unrigged):
  ~/Desktop/Models/Creatures/FarmCreatures/Chicken.glb
  ~/Desktop/Models/Creatures/FarmCreatures/Rooster.glb

Handoff contract (matches dock / boat / flag):
  - Origin at world (0, 0, 0) = ground between the feet
  - +Y = forward, +Z = up, +X = right
  - Root scale (1, 1, 1), transforms baked into rest pose
  - Clips (in-place; the game translates the entity):
      ``idle``    loop
      ``walk``    loop
      ``attack1`` one-shot peck / lunge (canonical; ``attack`` is an engine alias)
      ``die``     one-shot collapse, holds the last pose

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_farm_chickens.py
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import bpy
from mathutils import Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
AUTHOR_DIR = os.path.expanduser("~/Desktop/Models/Creatures/FarmCreatures")
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

FPS = 24
CLIP_WALK = 20
CLIP_IDLE = 48
CLIP_ATTACK = 18
CLIP_DIE = 28
CLIP_FRAMES = CLIP_WALK


@dataclass(frozen=True)
class BirdJob:
    filename: str
    label: str
    is_rooster: bool


HEN = BirdJob("Chicken.glb", "Chicken", False)
ROOSTER = BirdJob("Rooster.glb", "Rooster", True)


# ── Scene helpers ─────────────────────────────────────────────────────────

def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def select_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _mean(pts: list[Vector]) -> Vector:
    n = max(len(pts), 1)
    return Vector((
        sum(p.x for p in pts) / n,
        sum(p.y for p in pts) / n,
        sum(p.z for p in pts) / n,
    ))


def world_coords(mesh: bpy.types.Object) -> list[Vector]:
    mw = mesh.matrix_world
    return [mw @ v.co for v in mesh.data.vertices]


# ── Import + orient ───────────────────────────────────────────────────────

def import_authored_mesh(src_path: str, name: str) -> bpy.types.Object:
    if not os.path.isfile(src_path):
        raise FileNotFoundError(src_path)

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=src_path)
    new_objs = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new_objs if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh in {src_path}")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    if len(meshes) > 1:
        bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    mesh.name = name
    mesh.data.name = name

    select_active(mesh)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Author files face -Y after Blender's Y-up → Z-up import. Pipeline is +Y forward.
    mesh.rotation_euler = (0.0, 0.0, math.pi)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    coords = [v.co.copy() for v in mesh.data.vertices]
    zmin = min(c.z for c in coords)
    zs = sorted(c.z for c in coords)
    z_cut = zs[max(int(len(zs) * 0.03), 1)]
    feet = [c for c in coords if c.z <= z_cut]
    origin = _mean(feet) if feet else Vector((0.0, 0.0, zmin))
    mesh.location = (-origin.x, -origin.y, -zmin)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    for obj in list(new_objs):
        if obj == mesh:
            continue
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

    for img in bpy.data.images:
        if img.source == "FILE" and img.filepath:
            try:
                img.pack()
            except Exception:
                pass

    return mesh


# ── Landmarks ─────────────────────────────────────────────────────────────

def landmarks_from_mesh(mesh: bpy.types.Object) -> dict[str, Vector]:
    coords = world_coords(mesh)
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    zmin, zmax = min(zs), max(zs)
    height = max(zmax - zmin, 1e-4)
    length = max(ymax - ymin, 1e-4)

    zs_sorted = sorted(zs)
    z_cut = zs_sorted[max(int(len(zs_sorted) * 0.03), 1)]
    feet = [c for c in coords if c.z <= z_cut]
    foot_l_pts = [c for c in feet if c.x < 0.0] or feet
    foot_r_pts = [c for c in feet if c.x >= 0.0] or feet
    foot_l = _mean(foot_l_pts)
    foot_r = _mean(foot_r_pts)

    # Head = highest verts in the front half. Beak = most-forward verts up on the skull.
    front = [c for c in coords if c.y > 0.18 * length and c.z > 0.45 * height]
    if not front:
        front = [c for c in coords if c.y > 0.0]
    comb = max(front, key=lambda c: c.z)
    beak_tip = max(front, key=lambda c: c.y)
    tail_pts = [c for c in coords if c.y < ymin + 0.14 * length and c.z > 0.28 * height]
    tail = _mean(tail_pts) if tail_pts else Vector((0.0, ymin, 0.55 * height))

    torso = [
        c for c in coords
        if 0.30 * height < c.z < 0.72 * height
        and (ymin + 0.12 * length) < c.y < (beak_tip.y - 0.18 * length)
    ]
    body = _mean(torso) if torso else Vector((0.0, 0.05 * length, 0.52 * height))

    hip_z = 0.32 * height
    hip_y = body.y * 0.35 + 0.65 * (foot_l.y + foot_r.y) * 0.5
    hip_l = Vector((foot_l.x * 0.82, hip_y, hip_z))
    hip_r = Vector((foot_r.x * 0.82, hip_y, hip_z))

    knee_z = 0.155 * height
    knee_y = (foot_l.y + foot_r.y) * 0.5 - 0.045 * height
    knee_l = Vector((foot_l.x * 0.92, knee_y, knee_z))
    knee_r = Vector((foot_r.x * 0.92, knee_y, knee_z))

    ankle_z = max(0.028 * height, 0.018)
    ankle_l = Vector((foot_l.x, foot_l.y + 0.008 * height, ankle_z))
    ankle_r = Vector((foot_r.x, foot_r.y + 0.008 * height, ankle_z))
    toe_l = Vector((foot_l.x, foot_l.y + 0.085 * height, 0.010))
    toe_r = Vector((foot_r.x, foot_r.y + 0.085 * height, 0.010))

    skull_y = min(comb.y * 0.75 + beak_tip.y * 0.25, beak_tip.y - 0.05 * length)
    head = Vector((0.0, skull_y, comb.z * 0.62 + beak_tip.z * 0.38))
    beak = Vector((0.0, beak_tip.y, min(beak_tip.z, head.z - 0.02 * height)))
    nape = Vector((0.0, head.y * 0.40 + body.y * 0.60, head.z * 0.42 + body.z * 0.58))
    neck_top = nape
    neck_base = Vector((0.0, body.y * 0.70 + nape.y * 0.30, body.z * 0.88 + nape.z * 0.12))
    # Head bone spans the skull (nape → beak) so the comb/wattles follow the nod.
    head = Vector((0.0, nape.y * 0.45 + head.y * 0.55, nape.z * 0.30 + head.z * 0.70))

    wing_l_pts = [c for c in coords if c.x < xmin * 0.55 and 0.22 * height < c.z < 0.62 * height]
    wing_r_pts = [c for c in coords if c.x > xmax * 0.55 and 0.22 * height < c.z < 0.62 * height]
    wing_l = _mean(wing_l_pts) if wing_l_pts else Vector((xmin * 0.7, body.y, body.z))
    wing_r = _mean(wing_r_pts) if wing_r_pts else Vector((xmax * 0.7, body.y, body.z))
    shoulder_l = Vector((wing_l.x * 0.55, body.y + 0.02 * length, body.z + 0.02 * height))
    shoulder_r = Vector((wing_r.x * 0.55, body.y + 0.02 * length, body.z + 0.02 * height))
    wing_mid_l = Vector((wing_l.x * 0.85, wing_l.y * 0.5 + body.y * 0.5 - 0.04 * length, wing_l.z))
    wing_mid_r = Vector((wing_r.x * 0.85, wing_r.y * 0.5 + body.y * 0.5 - 0.04 * length, wing_r.z))
    wing_tip_l = Vector((wing_l.x, min(wing_l.y, body.y) - 0.06 * length, wing_l.z - 0.02 * height))
    wing_tip_r = Vector((wing_r.x, min(wing_r.y, body.y) - 0.06 * length, wing_r.z - 0.02 * height))

    tail_base = Vector((0.0, body.y - 0.18 * length, body.z + 0.04 * height))
    tail_end = Vector((0.0, tail.y, max(tail.z, tail_base.z + 0.04 * height)))

    return {
        "height": Vector((height, length, 0.0)),
        "body": body,
        "neck_base": neck_base,
        "neck_top": neck_top,
        "head": head,
        "beak": Vector((0.0, beak.y, beak.z)),
        "shoulder_l": shoulder_l,
        "shoulder_r": shoulder_r,
        "wing_mid_l": wing_mid_l,
        "wing_mid_r": wing_mid_r,
        "wing_tip_l": wing_tip_l,
        "wing_tip_r": wing_tip_r,
        "tail_base": tail_base,
        "tail_end": tail_end,
        "hip_l": hip_l,
        "hip_r": hip_r,
        "knee_l": knee_l,
        "knee_r": knee_r,
        "ankle_l": ankle_l,
        "ankle_r": ankle_r,
        "toe_l": toe_l,
        "toe_r": toe_r,
        "foot_l": foot_l,
        "foot_r": foot_r,
    }


def print_landmarks(label: str, j: dict[str, Vector]) -> None:
    print(f"  [{label}] height={j['height'].x:.3f} length={j['height'].y:.3f}")
    for key in (
        "body", "neck_base", "head", "beak", "tail_end",
        "hip_l", "knee_l", "ankle_l", "foot_l",
    ):
        v = j[key]
        print(f"    {key:10s}  ({v.x:+.3f}, {v.y:+.3f}, {v.z:+.3f})")


# ── Armature ──────────────────────────────────────────────────────────────

def add_edit_bone(
    arm_data: bpy.types.Armature,
    name: str,
    head: Vector,
    tail: Vector,
    parent: str | None = None,
    *,
    connect: bool = False,
    align: Vector | None = None,
) -> bpy.types.EditBone:
    bone = arm_data.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    if (tail - head).length < 0.008:
        bone.tail = head + Vector((0.0, 0.012, 0.0))
    if parent:
        bone.parent = arm_data.edit_bones[parent]
        bone.use_connect = connect
    if align is not None:
        bone.align_roll(align)
    return bone


def build_armature(label: str, j: dict[str, Vector]) -> bpy.types.Object:
    arm_data = bpy.data.armatures.new(f"{label}ArmatureData")
    arm = bpy.data.objects.new(f"{label}Armature", arm_data)
    bpy.context.collection.objects.link(arm)
    select_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")

    up = Vector((0.0, 0.0, 1.0))
    fwd = Vector((0.0, 1.0, 0.0))
    height = j["height"].x
    body_len = max(0.10 * j["height"].y, 0.08)

    add_edit_bone(arm_data, "Root", Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.04 * height)), align=fwd)
    add_edit_bone(
        arm_data, "Body",
        j["body"],
        j["body"] + Vector((0.0, body_len, 0.0)),
        "Root", align=up,
    )
    add_edit_bone(arm_data, "Neck", j["neck_base"], j["neck_top"], "Body", align=up)
    add_edit_bone(arm_data, "Head", j["head"], j["beak"], "Neck", align=up)
    add_edit_bone(arm_data, "Wing_L", j["shoulder_l"], j["wing_mid_l"], "Body", align=up)
    add_edit_bone(arm_data, "WingTip_L", j["wing_mid_l"], j["wing_tip_l"], "Wing_L", connect=True, align=up)
    add_edit_bone(arm_data, "Wing_R", j["shoulder_r"], j["wing_mid_r"], "Body", align=up)
    add_edit_bone(arm_data, "WingTip_R", j["wing_mid_r"], j["wing_tip_r"], "Wing_R", connect=True, align=up)
    add_edit_bone(arm_data, "Tail", j["tail_base"], j["tail_end"], "Body", align=up)
    add_edit_bone(arm_data, "Thigh_L", j["hip_l"], j["knee_l"], "Body", align=fwd)
    add_edit_bone(arm_data, "Shin_L", j["knee_l"], j["ankle_l"], "Thigh_L", connect=True, align=fwd)
    add_edit_bone(arm_data, "Foot_L", j["ankle_l"], j["toe_l"], "Shin_L", connect=True, align=up)
    add_edit_bone(arm_data, "Thigh_R", j["hip_r"], j["knee_r"], "Body", align=fwd)
    add_edit_bone(arm_data, "Shin_R", j["knee_r"], j["ankle_r"], "Thigh_R", connect=True, align=fwd)
    add_edit_bone(arm_data, "Foot_R", j["ankle_r"], j["toe_r"], "Shin_R", connect=True, align=up)

    bpy.ops.object.mode_set(mode="OBJECT")
    arm.display_type = "WIRE"
    arm.show_in_front = True
    arm.data.display_type = "OCTAHEDRAL"
    return arm


def _dist_to_segment(p: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    length_sq = ab.length_squared
    if length_sq < 1e-10:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / length_sq))
    return (p - (a + ab * t)).length


def skin(mesh: bpy.types.Object, arm: bpy.types.Object, j: dict[str, Vector]) -> None:
    """Proximity weights. Heat weighting fails on these thin-legged authored meshes."""
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE")
    mod = next((m for m in mesh.modifiers if m.type == "ARMATURE"), None)
    if mod is None:
        mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False

    while mesh.vertex_groups:
        mesh.vertex_groups.remove(mesh.vertex_groups[0])
    groups = {b.name: mesh.vertex_groups.new(name=b.name) for b in arm.data.bones}

    height = j["height"].x
    segments = {
        b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local)
        for b in arm.data.bones
    }
    falloff = {
        "Root": 0.05 * height,
        "Body": 0.24 * height,
        "Neck": 0.11 * height,
        "Head": 0.13 * height,
        "Wing_L": 0.11 * height,
        "WingTip_L": 0.09 * height,
        "Wing_R": 0.11 * height,
        "WingTip_R": 0.09 * height,
        "Tail": 0.18 * height,
        "Thigh_L": 0.11 * height,
        "Shin_L": 0.07 * height,
        "Foot_L": 0.16 * height,
        "Thigh_R": 0.11 * height,
        "Shin_R": 0.07 * height,
        "Foot_R": 0.16 * height,
    }

    hip_z = 0.5 * (j["hip_l"].z + j["hip_r"].z)
    head_y = j["head"].y
    tail_y = j["tail_base"].y
    counts = {name: 0 for name in groups}

    for vert in mesh.data.vertices:
        co = mesh.matrix_world @ vert.co
        weights: dict[str, float] = {}
        for name, (a, b) in segments.items():
            d = _dist_to_segment(co, a, b)
            radius = falloff[name]
            w = max(0.0, 1.0 - d / radius)
            if w > 0.0:
                weights[name] = w * w

        d_l = min(_dist_to_segment(co, *segments[n]) for n in ("Thigh_L", "Shin_L", "Foot_L"))
        d_r = min(_dist_to_segment(co, *segments[n]) for n in ("Thigh_R", "Shin_R", "Foot_R"))
        side = "L" if d_l <= d_r else "R"
        leg_names = (f"Thigh_{side}", f"Shin_{side}", f"Foot_{side}")
        d_leg = d_l if side == "L" else d_r
        d_head = _dist_to_segment(co, *segments["Head"])
        d_neck = _dist_to_segment(co, *segments["Neck"])
        d_tail = _dist_to_segment(co, *segments["Tail"])

        d_foot = min((co - j["foot_l"]).length, (co - j["foot_r"]).length)
        d_body = _dist_to_segment(co, *segments["Body"])
        # Only the actual feet/toes — not the hanging breast (z can be < hip).
        near_foot = co.z < 0.10 and d_foot < 0.18
        in_leg = near_foot or (
            d_leg < 0.09 * height
            and co.z < hip_z + 0.04 * height
            and d_leg + 0.02 < d_body
        )
        in_head = (
            d_head < 0.13 * height
            and co.z > 0.70 * height
            and co.y > head_y - 0.10 * height
        )
        in_neck = d_neck < 0.10 * height and not in_head
        in_tail = d_tail < 0.14 * height and co.y < tail_y + 0.04 * height

        if in_leg:
            keep = set(leg_names)
            weights = {k: v for k, v in weights.items() if k in keep} or {
                f"Foot_{side}" if near_foot else f"Shin_{side}": 1.0
            }
        elif in_head:
            keep = {"Head", "Neck"}
            weights = {k: (v * (2.2 if k == "Head" else 0.7)) for k, v in weights.items() if k in keep} or {
                "Head": 1.0
            }
        elif in_neck:
            keep = {"Neck", "Head", "Body"}
            weights = {k: (v * (2.0 if k == "Neck" else 0.6)) for k, v in weights.items() if k in keep} or {
                "Neck": 1.0
            }
        elif in_tail:
            for k in list(weights):
                if k.startswith("Thigh") or k.startswith("Shin") or k.startswith("Foot"):
                    weights.pop(k, None)
            weights["Tail"] = weights.get("Tail", 0.0) + 1.2
            weights["Body"] = weights.get("Body", 0.0) + 0.35
        else:
            weights.pop("Root", None)
            for k in ("Thigh_L", "Shin_L", "Foot_L", "Thigh_R", "Shin_R", "Foot_R"):
                if k in weights:
                    weights[k] *= 0.12

        total = sum(weights.values())
        if total <= 1e-8:
            if near_foot:
                weights = {f"Foot_{side}": 1.0}
            else:
                weights = {"Body": 1.0}
            total = 1.0

        for g in groups.values():
            g.add([vert.index], 0.0, "REPLACE")
        for name, w in weights.items():
            groups[name].add([vert.index], w / total, "REPLACE")
            counts[name] += 1

    print(f"  weight influence counts: {counts}")


# ── Animation ─────────────────────────────────────────────────────────────

def _set_action(arm: bpy.types.Object, action: bpy.types.Action) -> None:
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action


def _reset_pose(arm: bpy.types.Object) -> None:
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _smooth_action(action: bpy.types.Action) -> None:
    for fcu in action.fcurves:
        for kp in fcu.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"


def _pulse(t: float, start: float, end: float) -> float:
    if t <= start or t >= end:
        return 0.0
    return math.sin(math.pi * (t - start) / (end - start))


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
    track.strips.new(action.name, 1, action)


def key_euler(pb: bpy.types.PoseBone, frame: int, deg: tuple[float, float, float]) -> None:
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (math.radians(deg[0]), math.radians(deg[1]), math.radians(deg[2]))
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def key_loc(pb: bpy.types.PoseBone, frame: int, loc: tuple[float, float, float]) -> None:
    pb.location = loc
    pb.keyframe_insert(data_path="location", frame=frame)


def _key_bird(
    bones: dict,
    frame: int,
    *,
    body_e: tuple[float, float, float] = (0.0, 0.0, 0.0),
    body_l: tuple[float, float, float] = (0.0, 0.0, 0.0),
    neck_e: tuple[float, float, float] = (0.0, 0.0, 0.0),
    head_e: tuple[float, float, float] = (0.0, 0.0, 0.0),
    thigh_l: float = 0.0,
    shin_l: float = 0.0,
    foot_l: float = 0.0,
    thigh_r: float = 0.0,
    shin_r: float = 0.0,
    foot_r: float = 0.0,
    wing_l: tuple[float, float, float] = (0.0, 0.0, -4.0),
    wing_r: tuple[float, float, float] = (0.0, 0.0, 4.0),
    tip_l: tuple[float, float, float] = (0.0, 0.0, 0.0),
    tip_r: tuple[float, float, float] = (0.0, 0.0, 0.0),
    tail_e: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> None:
    key_euler(bones["Body"], frame, body_e)
    key_loc(bones["Body"], frame, body_l)
    key_euler(bones["Neck"], frame, neck_e)
    key_euler(bones["Head"], frame, head_e)
    key_euler(bones["Thigh_L"], frame, (thigh_l, 0.0, 0.0))
    key_euler(bones["Shin_L"], frame, (shin_l, 0.0, 0.0))
    key_euler(bones["Foot_L"], frame, (foot_l, 0.0, 0.0))
    key_euler(bones["Thigh_R"], frame, (thigh_r, 0.0, 0.0))
    key_euler(bones["Shin_R"], frame, (shin_r, 0.0, 0.0))
    key_euler(bones["Foot_R"], frame, (foot_r, 0.0, 0.0))
    key_euler(bones["Wing_L"], frame, wing_l)
    key_euler(bones["WingTip_L"], frame, tip_l)
    key_euler(bones["Wing_R"], frame, wing_r)
    key_euler(bones["WingTip_R"], frame, tip_r)
    key_euler(bones["Tail"], frame, tail_e)


def animate_walk(arm: bpy.types.Object, is_rooster: bool, height: float) -> bpy.types.Action:
    action = _begin_action(arm, "walk", CLIP_WALK)
    bones = arm.pose.bones
    scale = height / 0.45
    strut = 1.15 if is_rooster else 1.0
    step_amp = 38.0 * strut
    lift_fold = 55.0 * strut
    bob_amp = 14.0
    bounce = (0.016 if is_rooster else 0.013) * scale
    yaw_amp = 7.0 * strut
    wing_amp = 9.0
    tail_amp = 10.0 if is_rooster else 7.0
    sway = 0.008 * scale
    two_pi = 2.0 * math.pi

    for frame in range(1, CLIP_WALK + 2):
        t = (frame - 1) / CLIP_WALK
        l_swing = math.sin(two_pi * t)
        r_swing = math.sin(two_pi * t + math.pi)
        l_plant = 0.5 + 0.5 * math.cos(two_pi * t)
        r_plant = 0.5 + 0.5 * math.cos(two_pi * t + math.pi)
        bob = math.sin(two_pi * 2.0 * t)
        body_pitch = -4.0 + 3.0 * abs(math.sin(two_pi * t))
        body_yaw = yaw_amp * math.sin(two_pi * t + math.pi)

        def leg(swing: float, plant: float) -> tuple[float, float, float]:
            thigh = -8.0 + step_amp * swing
            shin = 12.0 + lift_fold * (1.0 - plant)
            foot = -thigh * 0.25 - shin * 0.15 + 4.0 * plant
            return thigh, shin, foot

        lt, ls, lf = leg(l_swing, l_plant)
        rt, rs, rf = leg(r_swing, r_plant)
        _key_bird(
            bones, frame,
            body_e=(body_pitch, 0.0, body_yaw),
            body_l=(sway * math.sin(two_pi * t + math.pi), 0.004 * scale * bob, bounce * (0.35 + 0.65 * abs(math.sin(two_pi * t)))),
            neck_e=(-body_pitch * 0.7 - bob_amp * 0.35 * bob, 0.0, -body_yaw * 0.4),
            head_e=(bob_amp * 0.55 * bob, 0.0, 0.0),
            thigh_l=lt, shin_l=ls, foot_l=lf,
            thigh_r=rt, shin_r=rs, foot_r=rf,
            wing_l=(wing_amp * (1.0 - l_plant), 0.0, -4.0),
            tip_l=(4.0 * (1.0 - l_plant), 0.0, 0.0),
            wing_r=(wing_amp * (1.0 - r_plant), 0.0, 4.0),
            tip_r=(4.0 * (1.0 - r_plant), 0.0, 0.0),
            tail_e=(-tail_amp * bob, 0.0, -body_yaw * 0.6),
        )

    _commit_nla(arm, action)
    return action


def animate_idle(arm: bpy.types.Object, is_rooster: bool, height: float) -> bpy.types.Action:
    action = _begin_action(arm, "idle", CLIP_IDLE)
    bones = arm.pose.bones
    scale = height / 0.45
    two_pi = 2.0 * math.pi
    look_amp = 16.0 if is_rooster else 11.0
    breathe_z = (0.010 if is_rooster else 0.008) * scale

    for frame in range(1, CLIP_IDLE + 2):
        t = (frame - 1) / CLIP_IDLE
        breathe = math.sin(two_pi * t)
        look = math.sin(two_pi * t)
        peck = _pulse(t, 0.36, 0.58) * (0.85 if is_rooster else 1.15)
        dart = _pulse(t, 0.10, 0.22) * (1.0 if is_rooster else 0.25)
        shift = math.sin(two_pi * t)
        _key_bird(
            bones, frame,
            body_e=(-2.0 + 1.6 * breathe - 6.0 * peck, 0.0, 3.0 * shift),
            body_l=(0.004 * scale * shift, -0.006 * scale * peck, breathe_z * (0.5 + 0.5 * breathe)),
            neck_e=(-8.0 * peck - 4.0 * dart + 2.0 * breathe, 0.0, look_amp * look * 0.35),
            head_e=(18.0 * peck + 10.0 * dart - 3.0 * breathe, 0.0, look_amp * look),
            thigh_l=-3.0 * shift, shin_l=4.0 + 3.0 * max(shift, 0.0), foot_l=2.0,
            thigh_r=3.0 * shift, shin_r=4.0 + 3.0 * max(-shift, 0.0), foot_r=2.0,
            wing_l=(3.0 + 2.0 * breathe, 0.0, -5.0),
            wing_r=(3.0 + 2.0 * breathe, 0.0, 5.0),
            tail_e=(-4.0 * breathe, 0.0, -5.0 * look),
        )

    _commit_nla(arm, action)
    return action


def animate_attack(arm: bpy.types.Object, is_rooster: bool, height: float) -> bpy.types.Action:
    action = _begin_action(arm, "attack1", CLIP_ATTACK)
    bones = arm.pose.bones
    scale = height / 0.45
    amp = 1.2 if is_rooster else 1.0

    for frame in range(1, CLIP_ATTACK + 1):
        t = (frame - 1) / max(CLIP_ATTACK - 1, 1)
        coil = _pulse(t, 0.00, 0.32)
        strike = _pulse(t, 0.18, 0.55)
        recover = _pulse(t, 0.48, 1.00)
        _key_bird(
            bones, frame,
            body_e=(
                -6.0 * coil + 22.0 * amp * strike - 4.0 * recover,
                0.0,
                4.0 * strike * amp,
            ),
            body_l=(
                0.012 * scale * amp * strike,
                (0.070 * strike - 0.018 * coil) * scale * amp,
                (-0.024 * coil + 0.036 * strike) * scale * amp,
            ),
            neck_e=(-12.0 * coil + 38.0 * amp * strike, 0.0, 0.0),
            head_e=(8.0 * coil + 28.0 * amp * strike, 0.0, 0.0),
            thigh_l=-18.0 * coil - 8.0 * strike,
            shin_l=22.0 * coil + 10.0 * strike,
            foot_l=-6.0 * coil,
            thigh_r=10.0 * coil - 14.0 * strike,
            shin_r=8.0 + 16.0 * strike,
            foot_r=4.0 * strike,
            wing_l=(-8.0 + 32.0 * amp * strike, 0.0, -8.0 - 28.0 * amp * strike),
            tip_l=(18.0 * strike, 0.0, -10.0 * strike),
            wing_r=(-8.0 + 32.0 * amp * strike, 0.0, 8.0 + 28.0 * amp * strike),
            tip_r=(18.0 * strike, 0.0, 10.0 * strike),
            tail_e=(12.0 * coil - 16.0 * strike, 0.0, 8.0 * strike),
        )

    _commit_nla(arm, action)
    return action


def animate_die(arm: bpy.types.Object, is_rooster: bool, height: float) -> bpy.types.Action:
    action = _begin_action(arm, "die", CLIP_DIE)
    bones = arm.pose.bones
    scale = height / 0.45
    side = 1.0

    for frame in range(1, CLIP_DIE + 1):
        t = (frame - 1) / max(CLIP_DIE - 1, 1)
        flinch = _pulse(t, 0.00, 0.22)
        fall = 0.0 if t < 0.12 else min(1.0, (t - 0.12) / 0.50)
        fall_s = fall * fall * (3.0 - 2.0 * fall)
        kick = _pulse(t, 0.28, 0.62)
        settle = 0.0 if t < 0.55 else min(1.0, (t - 0.55) / 0.45)

        _key_bird(
            bones, frame,
            body_e=(
                -8.0 * flinch + 18.0 * fall_s + 8.0 * settle,
                82.0 * side * fall_s,
                6.0 * flinch - 10.0 * fall_s,
            ),
            body_l=(
                0.10 * scale * side * fall_s,
                0.02 * scale * flinch - 0.04 * scale * fall_s,
                (0.02 * flinch - 0.14 * height * fall_s) + 0.01 * scale * kick,
            ),
            neck_e=(25.0 * fall_s + 10.0 * settle, 18.0 * side * fall_s, -8.0 * flinch),
            head_e=(20.0 * fall_s + 16.0 * settle, 12.0 * side * fall_s, 0.0),
            thigh_l=-10.0 * fall_s + 28.0 * kick,
            shin_l=18.0 * fall_s + 30.0 * kick,
            foot_l=-8.0 * fall_s,
            thigh_r=8.0 * fall_s - 16.0 * kick,
            shin_r=12.0 * fall_s + 8.0 * kick,
            foot_r=6.0 * fall_s,
            wing_l=(20.0 * flinch - 10.0 * fall_s, 0.0, -16.0 - 22.0 * fall_s),
            tip_l=(8.0 * fall_s, 0.0, -12.0 * fall_s),
            wing_r=(8.0 * flinch + 35.0 * fall_s, 0.0, 12.0 + 40.0 * fall_s),
            tip_r=(14.0 * fall_s, 0.0, 16.0 * fall_s),
            tail_e=(-18.0 * fall_s, 0.0, -12.0 * side * fall_s),
        )

    _commit_nla(arm, action)
    return action


# ── Export / report ───────────────────────────────────────────────────────

def report(mesh: bpy.types.Object, arm: bpy.types.Object, actions: list[bpy.types.Action]) -> None:
    n_verts = len(mesh.data.vertices)
    n_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    mats = [m.name if m else "<none>" for m in mesh.data.materials]
    mw = mesh.matrix_world
    verts = [mw @ v.co for v in mesh.data.vertices]
    xs, ys, zs = [v.x for v in verts], [v.y for v in verts], [v.z for v in verts]
    groups = [g.name for g in mesh.vertex_groups]
    print(f"  [{mesh.name}] verts={n_verts} tris={n_tris}")
    print(f"  [{mesh.name}] mats={mats}")
    print(
        f"  [{mesh.name}] bounds X[{min(xs):+.3f},{max(xs):+.3f}]  "
        f"Y[{min(ys):+.3f},{max(ys):+.3f}]  Z[{min(zs):+.3f},{max(zs):+.3f}]"
    )
    print(f"  bones: {[b.name for b in arm.data.bones]}")
    print(f"  vertex groups: {groups}")
    for action in actions:
        n_frames = int(round(action.frame_range[1] - action.frame_range[0]))
        print(
            f"  action '{action.name}'  ~{n_frames} frames @ {FPS} fps "
            f"({n_frames / FPS:.3f} s)  fcurves={len(action.fcurves)}"
        )


def export_glb(path: str, arm: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    arm.hide_set(False)
    arm.select_set(True)
    for child in arm.children:
        child.hide_set(False)
        child.select_set(True)
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


def build_one(job: BirdJob) -> None:
    print(f"=== {job.label} ===")
    clear_scene()
    src = os.path.join(AUTHOR_DIR, job.filename)
    mesh = import_authored_mesh(src, job.label)
    j = landmarks_from_mesh(mesh)
    print_landmarks(job.label, j)
    arm = build_armature(job.label, j)
    skin(mesh, arm, j)
    height = j["height"].x
    actions = [
        animate_idle(arm, job.is_rooster, height),
        animate_walk(arm, job.is_rooster, height),
        animate_attack(arm, job.is_rooster, height),
        animate_die(arm, job.is_rooster, height),
    ]
    report(mesh, arm, actions)

    keep = {arm, mesh}
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, job.filename)
        export_glb(path, arm)
        print(f"  -> {path} ({os.path.getsize(path) / 1024.0:.1f} KB)")

    blend_path = os.path.join(SOURCE_DIR, job.filename.replace(".glb", ".blend"))
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"  -> {blend_path}")


def main() -> None:
    print("=== Farm chickens (authored FarmCreatures meshes) ===")
    print(f"  author dir: {AUTHOR_DIR}")
    for job in (HEN, ROOSTER):
        build_one(job)
    print("DONE")


if __name__ == "__main__":
    main()
