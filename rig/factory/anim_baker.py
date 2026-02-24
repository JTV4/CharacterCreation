"""Animation Baker — loads .anim.json files and creates Blender Actions.

Reads the animation spec format (quaternion deltas in XYZW order) and converts
them into Blender Actions with proper FCurves keyed on pose bones.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any

import bpy
from mathutils import Quaternion


def load_anim_spec(path: str) -> dict[str, Any]:
    """Load a single .anim.json file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def discover_anims(anim_dir: str) -> list[str]:
    """Find all .anim.json files in a directory."""
    pattern = os.path.join(os.path.abspath(anim_dir), "*.anim.json")
    return sorted(glob.glob(pattern))


def bake_action(
    armature_obj: bpy.types.Object,
    anim_spec: dict[str, Any],
) -> bpy.types.Action | None:
    """Create a Blender Action from an animation spec and assign it.

    Rotation keyframes are stored as delta quaternions (XYZW) where identity
    [0,0,0,1] means rest pose. In Blender pose mode, bone rotation_quaternion
    is already relative to the edit-bone rest orientation, so the deltas map
    directly (after XYZW -> WXYZ conversion).

    Position keyframes are deltas from the bone's rest location.

    Returns the created Action, or None if the spec has no usable tracks.
    """
    meta = anim_spec["meta"]
    tracks = anim_spec.get("tracks", [])
    if not tracks:
        return None

    fps = meta.get("fps", 30)
    action_name = meta.get("name", meta.get("id", "Untitled"))
    action = bpy.data.actions.new(name=action_name)
    action.use_fake_user = True

    pose_bones = armature_obj.pose.bones
    valid_bone_names = {pb.name for pb in pose_bones}

    for track in tracks:
        bone_name = track["bone"]
        if bone_name not in valid_bone_names:
            print(f"    Warning: bone '{bone_name}' not found, skipping track")
            continue

        prop = track.get("property", "rotation")
        keyframes = track.get("keyframes", [])
        if not keyframes:
            continue

        interp_type = "LINEAR" if track.get("interpolation", "linear") == "linear" else "CONSTANT"
        data_path_prefix = f'pose.bones["{bone_name}"]'

        if prop == "rotation":
            data_path = f"{data_path_prefix}.rotation_quaternion"
            for ch_idx in range(4):
                fc = action.fcurves.new(data_path=data_path, index=ch_idx)
                for kf in keyframes:
                    x, y, z, w = kf["value"]
                    blender_quat = (w, x, y, z)  # XYZW -> WXYZ
                    frame = kf["time"] * fps
                    kp = fc.keyframe_points.insert(frame, blender_quat[ch_idx])
                    kp.interpolation = interp_type

        elif prop == "position":
            data_path = f"{data_path_prefix}.location"
            for ch_idx in range(3):
                fc = action.fcurves.new(data_path=data_path, index=ch_idx)
                for kf in keyframes:
                    val = kf["value"]
                    frame = kf["time"] * fps
                    kp = fc.keyframe_points.insert(frame, val[ch_idx])
                    kp.interpolation = interp_type

    if action.fcurves:
        frame_end = meta.get("duration", 1.0) * fps
        action.frame_range = (0, frame_end)

    print(f"    Baked action '{action_name}' ({len(action.fcurves)} fcurves)")
    return action


def bake_all_anims(
    armature_obj: bpy.types.Object,
    anim_dir: str,
) -> list[bpy.types.Action]:
    """Discover and bake all animations from a directory.

    The first baked action is set as the armature's active action so it appears
    in the Action Editor. All actions get fake_user=True so they persist in the
    .blend even when not actively assigned.
    """
    paths = discover_anims(anim_dir)
    if not paths:
        print(f"  No .anim.json files found in: {anim_dir}")
        return []

    print(f"  Found {len(paths)} animation file(s) in: {anim_dir}")

    for pb in armature_obj.pose.bones:
        pb.rotation_mode = "QUATERNION"

    actions: list[bpy.types.Action] = []
    for path in paths:
        spec = load_anim_spec(path)
        action = bake_action(armature_obj, spec)
        if action:
            actions.append(action)

    if actions:
        if not armature_obj.animation_data:
            armature_obj.animation_data_create()
        armature_obj.animation_data.action = actions[0]

    return actions
