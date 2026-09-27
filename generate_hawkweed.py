"""
generate_hawkweed.py
====================
Farm-plot Hawkweed (hawkweed_seed) from the authored Hawkeye herb mesh.

Theme: keen-eye herb for Accuracy potions — not a bird. Mid-tier between
Glowgrass (farming 40) and Aetherleaf (farming 45): farming 42, 12 min grow.

Handoff contract (matches Glowgrass / Aetherleaf):
  - Origin at plot center, stem at z=0 (glTF Y-up after export)
  - Root scale (1, 1, 1), transforms baked into rest pose
  - Modest 1×1 plot footprint — bind pose is the MATURE plant, ~0.52 m,
    so it sits between Glowgrass (~0.39 m) and Aetherleaf (~0.70 m)
    without needing a visualScale (Flax's 5.6× grow is the anti-pattern)
  - Four clips only. Dead is a runtime brown tint, not a fifth clip.

    idle       loop     tiny sprout (planted 0–3 min)
    Increase1   once     sprout → small plant (growing1 3–9 min)
    Increase2   once     small → almost grown (growing2 9–12 min)
    Increase3  once     almost grown → harvestable (mature 12 min+)

Clip names match PlantGrowthVisual.tsx after normalizeClipName
(case-insensitive, strip spaces/_/-).

Source: ~/Desktop/Models/Farming/HawkeyePlant.glb
Outputs:
  ~/Desktop/Models/Farming/Hawkweed.glb
  ~/Desktop/Models/Farming/Animations/Hawkweed.glb
  viewer/public/buildings/Hawkweed.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_hawkweed.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Quaternion, Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Desktop/Models/Farming/HawkeyePlant.glb")
OUT_DIRS = [
    os.path.expanduser("~/Desktop/Models/Farming"),
    os.path.expanduser("~/Desktop/Models/Farming/Animations"),
    os.path.join(ROOT, "viewer/public/buildings"),
]
OUT_NAME = "Hawkweed.glb"

# Mature height in metres — between Glowgrass (~0.39) and Aetherleaf (~0.70).
# Footprint scales with height; source is ~1×1 so 0.52 m stays on a 1×1 plot.
MATURE_HEIGHT = 0.52

FPS = 24
IDLE_FRAMES = 20
GROW_FRAMES = 40

# Bone scale relative to bind pose (mature = 1.0). Same staged grow as Glowgrass.
IDLE_SCALE = 0.08
GROW1_END = 0.30
GROW2_END = 0.62
GROW3_END = 1.00

BONE_NAME = "Stem"


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def select_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_transforms(obj: bpy.types.Object) -> None:
    select_active(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def world_coords(mesh: bpy.types.Object) -> list[Vector]:
    mw = mesh.matrix_world
    return [mw @ v.co for v in mesh.data.vertices]


def import_mesh(src_path: str) -> bpy.types.Object:
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
    mesh.name = "Hawkweed"
    mesh.data.name = "Hawkweed"
    apply_transforms(mesh)

    # glTF import is Z-up in Blender. Lowest Z is ground contact (drooping
    # leaf / stem). Center XZ on the plot origin.
    coords = [v.co.copy() for v in mesh.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    zmin = min(zs)
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    mesh.location = (-cx, -cy, -zmin)
    apply_transforms(mesh)

    height = max(v.co.z for v in mesh.data.vertices) - min(v.co.z for v in mesh.data.vertices)
    if height < 1e-4:
        raise RuntimeError("Hawkweed mesh has zero height")
    mesh.scale = (MATURE_HEIGHT / height,) * 3
    apply_transforms(mesh)

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


def tune_material(mesh: bpy.types.Object) -> None:
    for mat in mesh.data.materials:
        if not mat:
            continue
        mat.name = "Hawkweed"
        if not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type != "BSDF_PRINCIPLED":
                continue
            if "Metallic" in node.inputs:
                node.inputs["Metallic"].default_value = 0.0
            if "Roughness" in node.inputs:
                node.inputs["Roughness"].default_value = 0.58
            spec = node.inputs.get("Specular IOR Level") or node.inputs.get("Specular")
            if spec and not spec.is_linked:
                spec.default_value = 0.22


def build_armature(height: float) -> bpy.types.Object:
    arm_data = bpy.data.armatures.new("HawkweedArmature")
    arm = bpy.data.objects.new("HawkweedArmature", arm_data)
    bpy.context.collection.objects.link(arm)
    select_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    bone = arm_data.edit_bones.new(BONE_NAME)
    bone.head = (0.0, 0.0, 0.0)
    bone.tail = (0.0, 0.0, height)
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def skin(mesh: bpy.types.Object, arm: bpy.types.Object) -> None:
    select_active(mesh)
    if BONE_NAME in mesh.vertex_groups:
        vg = mesh.vertex_groups[BONE_NAME]
    else:
        vg = mesh.vertex_groups.new(name=BONE_NAME)
    vg.add(list(range(len(mesh.data.vertices))), 1.0, "REPLACE")

    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mesh.parent = arm


def _set_action(arm: bpy.types.Object, action: bpy.types.Action) -> None:
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action


def _reset_pose(arm: bpy.types.Object) -> None:
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)


def _smooth_action(action: bpy.types.Action) -> None:
    for fcu in action.fcurves:
        for kp in fcu.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"


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


def _key_bone(pb: bpy.types.PoseBone, frame: int, scale: float, quat: Quaternion) -> None:
    pb.location = (0.0, 0.0, 0.0)
    pb.scale = (scale, scale, scale)
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = quat
    pb.keyframe_insert(data_path="location", frame=frame)
    pb.keyframe_insert(data_path="scale", frame=frame)
    pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def ease_inout(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def animate_idle(arm: bpy.types.Object) -> bpy.types.Action:
    action = _begin_action(arm, "idle", IDLE_FRAMES)
    pb = arm.pose.bones[BONE_NAME]
    for frame in range(1, IDLE_FRAMES + 1):
        t = (frame - 1) / IDLE_FRAMES
        # Tiny sprout, slight breeze — not a second grow clip.
        sway = math.radians(3.2) * math.sin(2.0 * math.pi * t)
        nod = math.radians(1.4) * math.sin(4.0 * math.pi * t)
        quat = (
            Quaternion((0.0, 1.0, 0.0), sway)
            @ Quaternion((1.0, 0.0, 0.0), nod)
        )
        _key_bone(pb, frame, IDLE_SCALE, quat)
    _commit_nla(arm, action)
    return action


def animate_grow(arm: bpy.types.Object, name: str, start: float, end: float) -> bpy.types.Action:
    action = _begin_action(arm, name, GROW_FRAMES)
    pb = arm.pose.bones[BONE_NAME]
    identity = Quaternion((1.0, 0.0, 0.0, 0.0))
    for frame in range(1, GROW_FRAMES + 1):
        t = ease_inout((frame - 1) / (GROW_FRAMES - 1))
        scale = start + (end - start) * t
        _key_bone(pb, frame, scale, identity)
    _commit_nla(arm, action)
    return action


def export_glb(path: str, arm: bpy.types.Object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
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


def report(mesh: bpy.types.Object, arm: bpy.types.Object, actions: list[bpy.types.Action]) -> None:
    n_verts = len(mesh.data.vertices)
    n_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    mats = [m.name if m else "<none>" for m in mesh.data.materials]
    verts = world_coords(mesh)
    xs, ys, zs = [v.x for v in verts], [v.y for v in verts], [v.z for v in verts]
    print(f"  verts={n_verts} tris={n_tris} mats={mats}")
    print(
        f"  bind (mature) X[{min(xs):+.3f},{max(xs):+.3f}] "
        f"Y[{min(ys):+.3f},{max(ys):+.3f}] Z[{min(zs):+.3f},{max(zs):+.3f}] "
        f"h={max(zs)-min(zs):.3f} footprint={max(max(xs)-min(xs), max(ys)-min(ys)):.3f}"
    )
    print(f"  idle height ~ {IDLE_SCALE * (max(zs) - min(zs)):.3f}")
    print(f"  Increase1 end ~ {GROW1_END * (max(zs) - min(zs)):.3f}")
    print(f"  Increase2 end ~ {GROW2_END * (max(zs) - min(zs)):.3f}")
    print(f"  Increase3 end ~ {GROW3_END * (max(zs) - min(zs)):.3f}")
    print(f"  bones: {[b.name for b in arm.data.bones]}")
    for action in actions:
        n_frames = int(round(action.frame_range[1] - action.frame_range[0]))
        print(
            f"  clip '{action.name}'  {n_frames} frames @ {FPS} fps "
            f"({n_frames / FPS:.3f} s)  fcurves={len(action.fcurves)}"
        )


def main() -> None:
    clear_scene()
    mesh = import_mesh(SRC)
    tune_material(mesh)
    height = max(v.co.z for v in mesh.data.vertices)
    arm = build_armature(height)
    skin(mesh, arm)
    actions = [
        animate_idle(arm),
        animate_grow(arm, "Increase1", IDLE_SCALE, GROW1_END),
        animate_grow(arm, "Increase2", GROW1_END, GROW2_END),
        animate_grow(arm, "Increase3", GROW2_END, GROW3_END),
    ]
    report(mesh, arm, actions)

    keep = {arm, mesh}
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)

    for out_dir in OUT_DIRS:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, OUT_NAME)
        export_glb(path, arm)
        kb = os.path.getsize(path) / 1024.0
        print(f"  -> {path} ({kb:.1f} KB)")

    print("\nDONE — Hawkweed farm plant exported.")


if __name__ == "__main__":
    main()
