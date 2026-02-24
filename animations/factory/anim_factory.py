"""Animation Factory — imports animation JSON specs into Blender as Actions.

Usage (headless):
    blender --background --python animations/factory/anim_factory.py -- \
        --rig rig/output/rig.blend \
        --anims animations/specs/ \
        --out rig/output/rig_animated.blend \
        --export-glb rig/output/rig_animated.glb
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path
from typing import Any

import bpy


def load_json(path: str) -> dict[str, Any]:
    """Load a JSON file and return its contents."""
    abspath = os.path.abspath(path)
    with open(abspath, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_armature() -> bpy.types.Object:
    """Find the first armature object in the scene."""
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            return obj
    raise RuntimeError("No armature found in the .blend file")


def _blender_interp(interp_name: str) -> str:
    """Map our interpolation names to Blender keyframe interpolation types."""
    return {
        "linear": "LINEAR",
        "step": "CONSTANT",
    }.get(interp_name, "LINEAR")


def import_animation(
    armature_obj: bpy.types.Object,
    anim_spec: dict[str, Any],
) -> bpy.types.Action:
    """Create a Blender Action from an animation spec.

    Returns the created Action.
    """
    meta = anim_spec["meta"]
    tracks = anim_spec["tracks"]
    fps = meta["fps"]

    action = bpy.data.actions.new(name=meta["name"])
    action.use_fake_user = True

    armature_obj.rotation_mode = "QUATERNION"
    for pb in armature_obj.pose.bones:
        pb.rotation_mode = "QUATERNION"

    for track in tracks:
        bone_name: str = track["bone"]
        prop: str = track["property"]
        interp: str = track["interpolation"]
        keyframes: list[dict[str, Any]] = track["keyframes"]

        pose_bone = armature_obj.pose.bones.get(bone_name)
        if pose_bone is None:
            print(f"  Warning: bone '{bone_name}' not found in armature, skipping track")
            continue

        if prop == "rotation":
            data_path = f'pose.bones["{bone_name}"].rotation_quaternion'
            num_channels = 4
            channel_order = [3, 0, 1, 2]
        elif prop == "position":
            data_path = f'pose.bones["{bone_name}"].location'
            num_channels = 3
            channel_order = [0, 1, 2]
        else:
            continue

        fcurves: list[bpy.types.FCurve] = []
        for ch_idx in range(num_channels):
            fc = action.fcurves.new(data_path=data_path, index=ch_idx)
            fcurves.append(fc)

        for kf in keyframes:
            time_seconds: float = kf["time"]
            value: list[float] = kf["value"]
            frame = time_seconds * fps + 1.0

            for ch_idx in range(num_channels):
                src_idx = channel_order[ch_idx]
                point = fcurves[ch_idx].keyframe_points.insert(
                    frame, value[src_idx]
                )
                point.interpolation = _blender_interp(interp)

    action_name = meta["name"]
    print(f"  Created action '{action_name}': {len(tracks)} tracks")
    return action


def export_blend(filepath: str) -> None:
    """Save the scene as a .blend file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(filepath))
    print(f"  Saved .blend: {os.path.abspath(filepath)}")


def export_glb(filepath: str) -> None:
    """Export as GLB with animations."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(filepath),
        export_format="GLB",
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_animations=True,
        export_nla_strips=True,
    )
    print(f"  Exported GLB: {os.path.abspath(filepath)}")


def export_fbx(filepath: str) -> None:
    """Export as FBX with animations."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=os.path.abspath(filepath),
        use_selection=False,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        object_types={"ARMATURE"},
        use_armature_deform_only=False,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
    )
    print(f"  Exported FBX: {os.path.abspath(filepath)}")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments (handles Blender's '--' separator)."""
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        description="Animation Factory — import animation specs into Blender."
    )
    parser.add_argument(
        "--rig",
        required=True,
        help="Path to the rig .blend file",
    )
    parser.add_argument(
        "--anims",
        required=True,
        help="Path to animation specs directory or a single .anim.json file",
    )
    parser.add_argument(
        "--rig-spec",
        default=None,
        help="Path to rig_spec.json for validation (optional)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output .blend file path",
    )
    parser.add_argument(
        "--export-glb",
        default=None,
        help="Optional: also export as GLB to this path",
    )
    parser.add_argument(
        "--export-fbx",
        default=None,
        help="Optional: also export as FBX to this path",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Entry point for CLI execution."""
    args = parse_args()

    print("=== Animation Factory ===")

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.rig))
    armature_obj = _find_armature()
    print(f"  Loaded rig: {args.rig}")

    rig_spec: dict[str, Any] | None = None
    if args.rig_spec:
        rig_spec = load_json(args.rig_spec)

    anim_files: list[str] = []
    anims_path = args.anims
    if os.path.isdir(anims_path):
        anim_files = sorted(glob.glob(os.path.join(anims_path, "*.anim.json")))
    elif os.path.isfile(anims_path):
        anim_files = [anims_path]
    else:
        print(f"  Error: '{anims_path}' is not a file or directory")
        sys.exit(1)

    if not anim_files:
        print("  No animation files found.")
        sys.exit(0)

    if rig_spec:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from anim_validation import validate_anim_spec

    for anim_file in anim_files:
        anim_spec = load_json(anim_file)
        print(f"\n  Processing: {os.path.basename(anim_file)}")

        if rig_spec:
            validate_anim_spec(anim_spec, rig_spec)

        if len(anim_spec.get("tracks", [])) == 0:
            print(f"    Skipping '{anim_spec['meta']['name']}': no tracks defined")
            continue

        action = import_animation(armature_obj, anim_spec)

        track = armature_obj.animation_data_create().nla_tracks.new()
        track.name = anim_spec["meta"]["name"]
        fps = anim_spec["meta"]["fps"]
        duration_frames = anim_spec["meta"]["duration"] * fps
        track.strips.new(action.name, int(1), action)

    export_blend(args.out)

    if args.export_glb:
        export_glb(args.export_glb)

    if args.export_fbx:
        export_fbx(args.export_fbx)

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
