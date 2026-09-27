"""
generate_frost_giant.py
=======================
Keep the authored Mixamo rig on FrostGiant.glb, drop the leftover
icosphere, put FrostGiantWeapon in the right hand, and bake looping
``idle``, ``walk``, and ``attack1``.

Source (do not overwrite):
  ~/Desktop/Models/Creatures/FrostGiant.glb
  ~/Desktop/Models/Creatures/FrostGiantWeapon.glb

Output:
  viewer/public/buildings/FrostGiant.glb

Handoff:
  - Origin at world (0, 0, 0) = ground between the feet
  - Blender: −Y = forward, +Z = up, +X = creature left
  - glTF Y-up export: visual snout = +Z, no root motion
  - Clips: ``idle`` loop (planted feet), ``walk`` loop (in-place), ``attack1`` loop

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_frost_giant.py
"""

from __future__ import annotations

import json
import math
import os
import struct

import bpy
from mathutils import Matrix, Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_GIANT = os.path.expanduser("~/Desktop/Models/Creatures/FrostGiant.glb")
SRC_WEAPON = os.path.expanduser("~/Desktop/Models/Creatures/FrostGiantWeapon.glb")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
os.makedirs(VIEWER_DIR, exist_ok=True)

FPS = 24
CLIP_IDLE = 72
CLIP_WALK = 32
CLIP_ATTACK = 40

# Viewer gizmo, local to RightHand (glTF / Three.js). The exporter always
# writes Rx90 on bone children, so these TRS values are patched onto the
# weapon node after export.
WEAPON_LOCAL_POS = (0.1641, 0.2026, -0.0171)
WEAPON_LOCAL_QUAT_XYZW = (0.0325, 0.1967, 0.1116, 0.9736)


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


def _pack_images() -> None:
    for img in bpy.data.images:
        if img.source == "FILE" and img.filepath:
            try:
                img.pack()
            except Exception:
                pass


def import_gltf_objects(path: str) -> list[bpy.types.Object]:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


def import_giant() -> tuple[bpy.types.Object, bpy.types.Object]:
    new_objs = import_gltf_objects(SRC_GIANT)
    arm = next((o for o in new_objs if o.type == "ARMATURE"), None)
    meshes = [o for o in new_objs if o.type == "MESH"]
    if arm is None or not meshes:
        raise RuntimeError("FrostGiant.glb needs an armature + mesh")

    body = max(meshes, key=lambda o: len(o.data.vertices))
    body.name = "FrostGiant"
    body.data.name = "FrostGiant"
    for extra in meshes:
        if extra != body:
            bpy.data.objects.remove(extra, do_unlink=True)

    arm.name = "FrostGiantArmature"
    select_active(arm)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    select_active(body)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    mw = body.matrix_world
    coords = [mw @ v.co for v in body.data.vertices]
    zmin = min(c.z for c in coords)
    zs = sorted(c.z for c in coords)
    z_cut = zs[max(int(len(zs) * 0.04), 1)]
    feet = [c for c in coords if c.z <= z_cut]
    origin = _mean(feet) if feet else Vector((0.0, 0.0, zmin))
    delta = Vector((-origin.x, -origin.y, -zmin))
    arm.location += delta
    bpy.context.view_layer.update()
    select_active(arm)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)

    _shorten_hand_bones(arm)
    _pack_images()
    return body, arm


def _shorten_hand_bones(arm: bpy.types.Object) -> None:
    """Mixamo hand / head_end tails are huge; keep a short grip bone for the club."""
    select_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, length in (("LeftHand", 0.12), ("RightHand", 0.12), ("headfront", 0.08)):
        eb = arm.data.edit_bones.get(name)
        if eb is None:
            continue
        direction = (eb.tail - eb.head)
        if direction.length < 1e-6:
            continue
        eb.tail = eb.head + direction.normalized() * length
    bpy.ops.object.mode_set(mode="OBJECT")


def import_weapon() -> bpy.types.Object:
    new_objs = import_gltf_objects(SRC_WEAPON)
    meshes = [o for o in new_objs if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("FrostGiantWeapon.glb has no mesh")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    if len(meshes) > 1:
        bpy.ops.object.join()
    weapon = bpy.context.view_layer.objects.active
    weapon.name = "FrostGiantWeapon"
    weapon.data.name = "FrostGiantWeapon"
    select_active(weapon)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    _pack_images()
    return weapon


def attach_weapon(weapon: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Parent the club to RightHand. Mesh yaw puts the shaft across the palm;
    viewer-local TRS is applied after export (see patch_weapon_node)."""
    select_active(arm)
    bpy.ops.object.mode_set(mode="POSE")
    pb = arm.pose.bones["RightHand"]
    bone_len = (pb.tail - pb.head).length
    bpy.ops.object.mode_set(mode="OBJECT")

    weapon.parent = arm
    weapon.parent_type = "BONE"
    weapon.parent_bone = "RightHand"
    # Exporter always writes Rx90 on bone children: mesh X stays bone X,
    # mesh Z → bone Y. Authored shaft is +Z; Ry(+90) bakes it onto mesh X
    # so a fist can wrap around it (thumb→pinky) instead of the club
    # continuing the forearm.
    weapon.data.transform(Matrix.Rotation(math.pi / 2.0, 4, "Y"))
    weapon.data.update()
    weapon.location = (0.0, -bone_len, 0.0)
    weapon.rotation_euler = (0.0, 0.0, 0.0)
    weapon.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    print(f"  weapon parented to RightHand  bone_len={bone_len:.3f}")


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


def _gait_frames(n_frames: int):
    yield from range(1, n_frames + 1)
    yield n_frames + 1


def key_euler(pb: bpy.types.PoseBone, frame: int, deg: tuple[float, float, float]) -> None:
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (
        math.radians(deg[0]),
        math.radians(deg[1]),
        math.radians(deg[2]),
    )
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def key_loc(pb: bpy.types.PoseBone, frame: int, loc: tuple[float, float, float]) -> None:
    pb.location = loc
    pb.keyframe_insert(data_path="location", frame=frame)


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


def _arm_hang(side: str, drop: float, swing: float) -> tuple[tuple[float, float, float], ...]:
    """Mixamo T-pose: local Y along the arm, local X drops both arms the same way.

    Opposite Z signs send one arm forward and the other back. Extra ``drop``
    on the right arm keeps the club-carrying hand a bit lower.
    """
    sign = 1.0 if side == "Left" else -1.0
    shoulder = (4.0 * drop, 0.0, 6.0 * sign)
    arm = (
        48.0 + 12.0 * drop,
        12.0 * sign + 5.0 * swing,
        10.0 * sign + 20.0 * swing,
    )
    forearm = (6.0 * drop, 0.0, (16.0 + 10.0 * drop) * sign)
    hand = (0.0, 0.0, 8.0 * sign)
    return shoulder, arm, forearm, hand


def _key_arm(bones, side: str, frame: int, drop: float, swing: float) -> None:
    sh, arm, fore, hand = _arm_hang(side, drop, swing)
    key_euler(bones[f"{side}Shoulder"], frame, sh)
    key_euler(bones[f"{side}Arm"], frame, arm)
    key_euler(bones[f"{side}ForeArm"], frame, fore)
    key_euler(bones[f"{side}Hand"], frame, hand)


def _key_leg(bones, side: str, frame: int, swing: float, plant: float) -> None:
    lift = 1.0 - plant
    key_euler(bones[f"{side}UpLeg"], frame, (28.0 * swing, 0.0, 0.0))
    key_euler(bones[f"{side}Leg"], frame, (42.0 * lift, 0.0, 0.0))
    key_euler(bones[f"{side}Foot"], frame, (-10.0 * lift - 8.0 * swing, 0.0, 0.0))
    key_euler(bones[f"{side}ToeBase"], frame, (6.0 * lift, 0.0, 0.0))


def animate_idle(arm: bpy.types.Object, height: float) -> bpy.types.Action:
    action = _begin_action(arm, "idle", CLIP_IDLE)
    bones = arm.pose.bones
    two_pi = 2.0 * math.pi

    for frame in _gait_frames(CLIP_IDLE):
        t = (frame - 1) / CLIP_IDLE
        breathe = math.sin(two_pi * t)
        look = math.sin(two_pi * t)
        glance = _pulse(t, 0.55, 0.78)

        key_euler(bones["Hips"], frame, (0.0, 0.0, 0.0))
        key_loc(bones["Hips"], frame, (0.0, 0.0, 0.0))
        key_euler(bones["Spine"], frame, (3.0 * breathe, 0.0, 1.5 * look))
        key_euler(bones["Spine01"], frame, (3.5 * breathe, 0.0, 2.0 * look))
        key_euler(bones["Spine02"], frame, (2.5 * breathe, 0.0, 1.6 * look))
        key_euler(bones["neck"], frame, (-2.0 * breathe + 4.0 * glance, 0.0, 8.0 * look))
        key_euler(bones["Head"], frame, (-3.0 * breathe - 4.0 * glance, 0.0, 12.0 * look + 8.0 * glance))
        _key_arm(bones, "Left", frame, drop=0.15 + 0.08 * breathe, swing=0.12)
        _key_arm(bones, "Right", frame, drop=0.22 + 0.06 * breathe, swing=-0.08)
        _key_leg(bones, "Left", frame, 0.0, 1.0)
        _key_leg(bones, "Right", frame, 0.0, 1.0)

    _commit_nla(arm, action)
    return action


def animate_walk(arm: bpy.types.Object, height: float) -> bpy.types.Action:
    action = _begin_action(arm, "walk", CLIP_WALK)
    bones = arm.pose.bones
    two_pi = 2.0 * math.pi

    for frame in _gait_frames(CLIP_WALK):
        t = (frame - 1) / CLIP_WALK
        left = math.sin(two_pi * t)
        right = math.sin(two_pi * t + math.pi)
        left_plant = 0.5 + 0.5 * math.cos(two_pi * t)
        right_plant = 0.5 + 0.5 * math.cos(two_pi * t + math.pi)
        bob = math.sin(two_pi * 2.0 * t)

        key_euler(bones["Hips"], frame, (-3.0 + 2.0 * abs(left), 0.0, 6.0 * left))
        key_loc(bones["Hips"], frame, (0.0, 0.0, 0.010 * height * abs(bob)))
        key_euler(bones["Spine"], frame, (2.0 * bob, 0.0, 3.0 * left))
        key_euler(bones["Spine01"], frame, (2.5 * bob, 0.0, 2.5 * left))
        key_euler(bones["Spine02"], frame, (1.5 * bob, 0.0, -2.0 * left))
        key_euler(bones["neck"], frame, (-2.0 * bob, 0.0, -2.0 * left))
        key_euler(bones["Head"], frame, (3.0 * bob, 0.0, 1.5 * left))
        _key_arm(bones, "Left", frame, drop=0.10, swing=-left)
        _key_arm(bones, "Right", frame, drop=0.18, swing=-right)
        _key_leg(bones, "Left", frame, left, left_plant)
        _key_leg(bones, "Right", frame, right, right_plant)

    _commit_nla(arm, action)
    return action


def animate_attack1(arm: bpy.types.Object, height: float) -> bpy.types.Action:
    """Overhead club smash. Starts and ends at the idle hang so the clip can loop."""
    action = _begin_action(arm, "attack1", CLIP_ATTACK)
    bones = arm.pose.bones

    for frame in _gait_frames(CLIP_ATTACK):
        t = (frame - 1) / CLIP_ATTACK
        coil = _pulse(t, 0.00, 0.32)
        strike = _pulse(t, 0.20, 0.55)
        follow = _pulse(t, 0.48, 0.82)

        key_euler(bones["Hips"], frame, (0.0, 0.0, 0.0))
        key_loc(bones["Hips"], frame, (0.0, 0.0, 0.0))
        key_euler(bones["Spine"], frame, (-10.0 * coil + 16.0 * strike, 0.0, 8.0 * strike))
        key_euler(bones["Spine01"], frame, (-8.0 * coil + 20.0 * strike, 0.0, 10.0 * strike))
        key_euler(bones["Spine02"], frame, (-6.0 * coil + 14.0 * strike, 0.0, 8.0 * strike))
        key_euler(bones["neck"], frame, (8.0 * coil - 12.0 * strike, 0.0, 4.0 * strike))
        key_euler(bones["Head"], frame, (10.0 * coil - 8.0 * strike, 0.0, 6.0 * strike))
        _key_arm(
            bones,
            "Left",
            frame,
            drop=0.15 + 0.12 * strike,
            swing=0.12 - 0.28 * strike,
        )
        _key_arm(
            bones,
            "Right",
            frame,
            drop=0.22 - 3.4 * coil + 1.8 * strike + 0.35 * follow,
            swing=-0.08 - 0.60 * coil + 1.40 * strike,
        )
        _key_leg(bones, "Left", frame, 0.0, 1.0)
        _key_leg(bones, "Right", frame, 0.0, 1.0)

    _commit_nla(arm, action)
    return action


def report(mesh: bpy.types.Object, arm: bpy.types.Object, actions: list[bpy.types.Action]) -> None:
    n_verts = len(mesh.data.vertices)
    n_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    mw = mesh.matrix_world
    verts = [mw @ v.co for v in mesh.data.vertices]
    xs, ys, zs = [v.x for v in verts], [v.y for v in verts], [v.z for v in verts]
    print(f"  [{mesh.name}] verts={n_verts} tris={n_tris}")
    print(
        f"  [{mesh.name}] bounds X[{min(xs):+.3f},{max(xs):+.3f}]  "
        f"Y[{min(ys):+.3f},{max(ys):+.3f}]  Z[{min(zs):+.3f},{max(zs):+.3f}]"
    )
    print(f"  bones: {[b.name for b in arm.data.bones]}")
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
        for grandchild in child.children:
            grandchild.hide_set(False)
            grandchild.select_set(True)
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


def _glb_pad4(n: int) -> int:
    return (4 - (n % 4)) % 4


def patch_weapon_node(path: str) -> None:
    """Write the viewer-authored RightHand-local TRS onto FrostGiantWeapon."""
    with open(path, "rb") as fh:
        blob = fh.read()
    magic, version, _length = struct.unpack_from("<4sII", blob, 0)
    if magic != b"glTF":
        raise RuntimeError(f"not a GLB: {path}")
    json_len, json_type = struct.unpack_from("<I4s", blob, 12)
    if json_type != b"JSON":
        raise RuntimeError("GLB missing JSON chunk")
    json_start = 20
    json_end = json_start + json_len
    doc = json.loads(blob[json_start:json_end])
    node = next((n for n in doc.get("nodes", []) if n.get("name") == "FrostGiantWeapon"), None)
    if node is None:
        raise RuntimeError("FrostGiantWeapon node missing from GLB")
    node["translation"] = [float(x) for x in WEAPON_LOCAL_POS]
    node["rotation"] = [float(x) for x in WEAPON_LOCAL_QUAT_XYZW]
    node["scale"] = [1.0, 1.0, 1.0]
    new_json = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    new_json += b" " * _glb_pad4(len(new_json))
    rest = blob[json_end:]
    out = bytearray()
    out += struct.pack("<4sII", b"glTF", version, 12 + 8 + len(new_json) + len(rest))
    out += struct.pack("<I4s", len(new_json), b"JSON")
    out += new_json
    out += rest
    with open(path, "wb") as fh:
        fh.write(out)
    print(
        f"  patched weapon TRS  pos={WEAPON_LOCAL_POS}  "
        f"quat={WEAPON_LOCAL_QUAT_XYZW}"
    )


def main() -> None:
    print("=== Frost Giant (Mixamo rig + right-hand weapon, idle/walk/attack1) ===")
    print(f"  source: {SRC_GIANT}")
    print(f"  weapon: {SRC_WEAPON}")
    clear_scene()
    mesh, arm = import_giant()
    weapon = import_weapon()
    attach_weapon(weapon, arm)
    mw = mesh.matrix_world
    zs = [(mw @ v.co).z for v in mesh.data.vertices]
    height = max(zs) - min(zs)
    actions = [
        animate_idle(arm, height),
        animate_walk(arm, height),
        animate_attack1(arm, height),
    ]
    report(mesh, arm, actions)
    keep = {arm, mesh, weapon}
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    out = os.path.join(VIEWER_DIR, "FrostGiant.glb")
    export_glb(out, arm)
    patch_weapon_node(out)
    print(f"  -> {out} ({os.path.getsize(out) / 1024.0:.1f} KB)")
    print("DONE")


if __name__ == "__main__":
    main()
