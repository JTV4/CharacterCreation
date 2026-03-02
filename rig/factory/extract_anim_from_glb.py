"""Extract animation data from a GLB file and write it as .anim.json spec format.

Usage:
    blender --background --python rig/factory/extract_anim_from_glb.py -- \
        --glb viewer/public/animations/Walk.glb \
        --out animations/specs/walk.anim.json \
        --id walk --name Walk --loop
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

import bpy


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Extract animation from GLB to .anim.json")
    parser.add_argument("--glb", required=True, help="Path to input GLB file")
    parser.add_argument("--out", required=True, help="Output .anim.json path")
    parser.add_argument("--id", required=True, help="Animation id")
    parser.add_argument("--name", required=True, help="Animation display name")
    parser.add_argument("--loop", action="store_true", help="Mark animation as looping")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for action in bpy.data.actions:
        bpy.data.actions.remove(action)

    glb_path = os.path.abspath(args.glb)
    bpy.ops.import_scene.gltf(filepath=glb_path)

    actions = list(bpy.data.actions)
    if not actions:
        print(f"ERROR: No actions found in {glb_path}")
        sys.exit(1)

    action = actions[0]
    print(f"  Extracting action '{action.name}' from {os.path.basename(glb_path)}")

    fps = bpy.context.scene.render.fps
    frame_start, frame_end = action.frame_range
    duration = round((frame_end - frame_start) / fps, 4)

    bone_tracks: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    for fc in action.fcurves:
        dp = fc.data_path
        if 'pose.bones["' not in dp:
            continue

        bone_name = dp.split('pose.bones["')[1].split('"]')[0]

        if dp.endswith(".rotation_quaternion"):
            prop = "rotation"
        elif dp.endswith(".location"):
            prop = "position"
        else:
            continue

        ch_idx = fc.array_index
        key = f"{bone_name}|{prop}"

        for kp in fc.keyframe_points:
            frame, value = kp.co
            time = round((frame - frame_start) / fps, 4)
            bone_tracks[key].setdefault("keyframes_raw", defaultdict(dict))
            bone_tracks[key]["keyframes_raw"][time][ch_idx] = value
            bone_tracks[key]["bone"] = bone_name
            bone_tracks[key]["prop"] = prop
            bone_tracks[key]["interp"] = "linear" if kp.interpolation == "LINEAR" else "step"

    tracks = []
    for key, data in bone_tracks.items():
        bone_name = data["bone"]
        prop = data["prop"]
        interp = data.get("interp", "linear")
        raw_kfs = data.get("keyframes_raw", {})

        keyframes = []
        for time in sorted(raw_kfs.keys()):
            channels = raw_kfs[time]
            if prop == "rotation":
                w = round(channels.get(0, 1.0), 6)
                x = round(channels.get(1, 0.0), 6)
                y = round(channels.get(2, 0.0), 6)
                z = round(channels.get(3, 0.0), 6)
                keyframes.append({"time": time, "value": [x, y, z, w]})
            elif prop == "position":
                x = round(channels.get(0, 0.0), 6)
                y = round(channels.get(1, 0.0), 6)
                z = round(channels.get(2, 0.0), 6)
                keyframes.append({"time": time, "value": [x, y, z]})

        if keyframes:
            tracks.append({
                "bone": bone_name,
                "property": prop,
                "interpolation": interp,
                "keyframes": keyframes,
            })

    spec = {
        "meta": {
            "name": args.name,
            "id": args.id,
            "duration": duration,
            "fps": fps,
            "loop": args.loop,
        },
        "tracks": tracks,
    }

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)

    print(f"  Wrote {len(tracks)} tracks to {out_path}")


if __name__ == "__main__":
    main()
