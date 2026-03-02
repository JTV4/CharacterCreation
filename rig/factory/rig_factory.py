"""Rig Factory — builds a Blender armature from a rig_spec.json file.

Usage (headless):
    blender --background --python rig/factory/rig_factory.py -- \
        --spec rig/spec/rig_spec.json \
        --out rig/output/rig.blend \
        --export-glb rig/output/rig.glb

Usage (inside Blender's scripting tab):
    Run this script with sys.argv overrides or call build_armature() directly.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any

import bpy
from mathutils import Vector

CONNECT_TOLERANCE: float = 0.0001


def load_spec(path: str) -> dict[str, Any]:
    """Load and return the rig specification from a JSON file."""
    abspath = os.path.abspath(path)
    with open(abspath, "r", encoding="utf-8") as f:
        spec: dict[str, Any] = json.load(f)
    print(f"  Loaded rig spec from: {abspath}")
    return spec


def _topological_sort(bones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort bones so that every parent appears before its children."""
    bone_map = {b["name"]: b for b in bones}
    sorted_list: list[dict[str, Any]] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        bone = bone_map[name]
        parent = bone.get("parent")
        if parent is not None:
            visit(parent)
        visited.add(name)
        sorted_list.append(bone)

    for bone in bones:
        visit(bone["name"])

    return sorted_list


def build_armature(spec: dict[str, Any], name: str = "Rig") -> bpy.types.Object:
    """Create a Blender armature from the rig specification.

    Returns the armature Object (already linked to the active scene).
    """
    armature_data = bpy.data.armatures.new(name)
    armature_obj = bpy.data.objects.new(name, armature_data)

    scene = bpy.context.scene
    scene.collection.objects.link(armature_obj)
    bpy.context.view_layer.objects.active = armature_obj
    armature_obj.select_set(True)

    bpy.ops.object.mode_set(mode="EDIT")

    sorted_bones = _topological_sort(spec["bones"])
    edit_bones = armature_data.edit_bones

    bone_refs: dict[str, bpy.types.EditBone] = {}

    for bone_data in sorted_bones:
        bone_name: str = bone_data["name"]
        eb = edit_bones.new(bone_name)

        head = bone_data["head"]
        tail = bone_data["tail"]
        eb.head = Vector((head[0], head[1], head[2]))
        eb.tail = Vector((tail[0], tail[1], tail[2]))
        eb.roll = float(bone_data["roll"])
        eb.use_deform = bool(bone_data["deform"])

        parent_name = bone_data.get("parent")
        if parent_name and parent_name in bone_refs:
            parent_eb = bone_refs[parent_name]
            eb.parent = parent_eb

            dist = (eb.head - parent_eb.tail).length
            eb.use_connect = dist < CONNECT_TOLERANCE

        bone_refs[bone_name] = eb

    bpy.ops.object.mode_set(mode="OBJECT")

    _apply_bone_groups(armature_obj, spec["bones"])

    print(f"  Built armature '{name}' with {len(sorted_bones)} bones.")
    return armature_obj


CATEGORY_COLORS: dict[str, tuple[float, float, float]] = {
    "spine":  (0.290, 0.620, 1.000),   # #4a9eff
    "arm":    (0.290, 0.859, 0.478),   # #4adb7a
    "leg":    (1.000, 0.420, 0.420),   # #ff6b6b
    "finger": (1.000, 0.851, 0.239),   # #ffd93d
    "face":   (0.753, 0.518, 0.988),   # #c084fc
    "other":  (0.580, 0.639, 0.722),   # #94a3b8
}


def _apply_bone_groups(
    armature_obj: bpy.types.Object, bones: list[dict[str, Any]]
) -> None:
    """Assign category metadata and per-bone colors (Blender 4.x).

    Sets custom color on each bone via the armature data (edit bones persist
    color even outside pose mode) and stores category/side as custom props.
    """
    bpy.ops.object.mode_set(mode="EDIT")
    for bone_data in bones:
        bone_name = bone_data["name"]
        eb = armature_obj.data.edit_bones.get(bone_name)
        if eb:
            cat = bone_data.get("category", "other")
            rgb = CATEGORY_COLORS.get(cat, CATEGORY_COLORS["other"])
            eb.color.palette = "CUSTOM"
            eb.color.custom.normal = rgb
            eb.color.custom.select = tuple(min(c + 0.2, 1.0) for c in rgb)
            eb.color.custom.active = tuple(min(c + 0.35, 1.0) for c in rgb)
    bpy.ops.object.mode_set(mode="OBJECT")

    for bone_data in bones:
        bone_name = bone_data["name"]
        pose_bone = armature_obj.pose.bones.get(bone_name)
        if pose_bone:
            pose_bone["category"] = bone_data["category"]
            pose_bone["side"] = bone_data["side"]
            cat = bone_data.get("category", "other")
            rgb = CATEGORY_COLORS.get(cat, CATEGORY_COLORS["other"])
            pose_bone.color.palette = "CUSTOM"
            pose_bone.color.custom.normal = rgb
            pose_bone.color.custom.select = tuple(min(c + 0.2, 1.0) for c in rgb)
            pose_bone.color.custom.active = tuple(min(c + 0.35, 1.0) for c in rgb)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments (handles Blender's '--' separator)."""
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        description="Rig Factory — generate a canonical humanoid skeleton."
    )
    parser.add_argument(
        "--spec",
        required=True,
        help="Path to rig_spec.json",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output path for .blend file",
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
    parser.add_argument(
        "--anims",
        default=None,
        help="Directory containing .anim.json files to bake into the rig",
    )
    parser.add_argument(
        "--name",
        default="Rig",
        help="Name for the armature object (default: 'Rig')",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Entry point for CLI execution."""
    args = parse_args()

    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)

    print("=== Rig Factory ===")
    spec = load_spec(args.spec)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from validation import validate_rig_spec

    validate_rig_spec(spec)

    armature_obj = build_armature(spec, name=args.name)

    if args.anims:
        from anim_baker import bake_all_anims

        actions = bake_all_anims(armature_obj, args.anims)
        print(f"  Baked {len(actions)} animation(s) into armature.")

    from exporter import export_blend, export_glb, export_fbx, export_glb_per_animation

    export_blend(args.out)

    if args.export_glb:
        export_glb(args.export_glb)

        if args.anims:
            glb_dir = os.path.dirname(os.path.abspath(args.export_glb))
            anim_glb_dir = os.path.join(glb_dir, "animations")
            print(f"  Exporting per-animation GLBs to: {anim_glb_dir}")
            export_glb_per_animation(armature_obj, anim_glb_dir, args.anims)

    if args.export_fbx:
        export_fbx(args.export_fbx)

    print("=== Done ===")


if __name__ == "__main__":
    main()
