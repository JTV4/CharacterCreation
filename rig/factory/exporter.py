"""Export utilities for saving Blender armatures to various formats."""

from __future__ import annotations

import os
from pathlib import Path

import bpy


def _ensure_directory(filepath: str) -> None:
    """Create parent directories if they don't exist."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)


def export_blend(filepath: str) -> None:
    """Save the current scene as a .blend file."""
    _ensure_directory(filepath)
    abspath = os.path.abspath(filepath)
    bpy.ops.wm.save_as_mainfile(filepath=abspath)
    print(f"  Saved .blend: {abspath}")


def export_glb(filepath: str, include_anims: bool = True) -> None:
    """Export the current scene as a GLB (binary glTF) file.

    Applies the following settings for game-engine compatibility:
    - Y-up coordinate system (glTF standard)
    - Armatures exported with bone data
    - All baked actions exported as separate animations
    """
    _ensure_directory(filepath)
    abspath = os.path.abspath(filepath)

    bpy.ops.export_scene.gltf(
        filepath=abspath,
        export_format="GLB",
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=False,
        export_def_bones=False,
        export_animations=include_anims,
        export_nla_strips=False,
        export_animation_mode="ACTIONS" if include_anims else "NLA_TRACKS",
    )
    print(f"  Exported GLB: {abspath} (animations={'yes' if include_anims else 'no'})")


def export_glb_per_animation(
    armature_obj: bpy.types.Object,
    output_dir: str,
) -> list[str]:
    """Export one GLB per animation action, each named [ActionName].glb.

    Each GLB contains the full rig skeleton plus a single animation.
    Returns a list of exported file paths.
    """
    _ensure_directory(os.path.join(output_dir, "_placeholder"))

    if not armature_obj.animation_data:
        print("  No animation data on armature, skipping per-animation export.")
        return []

    all_actions = [a for a in bpy.data.actions if a.users > 0 or a.use_fake_user]
    if not all_actions:
        print("  No actions found, skipping per-animation export.")
        return []

    original_action = armature_obj.animation_data.action
    exported: list[str] = []

    for action in all_actions:
        armature_obj.animation_data.action = action
        filename = f"{action.name}.glb"
        filepath = os.path.join(os.path.abspath(output_dir), filename)

        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format="GLB",
            export_apply=False,
            export_yup=True,
            export_skins=True,
            export_all_influences=False,
            export_def_bones=False,
            export_animations=True,
            export_nla_strips=False,
            export_animation_mode="ACTIVE_ACTIONS",
        )
        exported.append(filepath)
        print(f"    Exported: {filename}")

    armature_obj.animation_data.action = original_action
    return exported


def export_fbx(filepath: str) -> None:
    """Export the current scene as an FBX file.

    Applies axis conversion: Z-up source -> Y-up target (standard for
    Unreal/Unity import). Only armature data is exported.
    """
    _ensure_directory(filepath)
    abspath = os.path.abspath(filepath)

    has_actions = len(bpy.data.actions) > 0
    bpy.ops.export_scene.fbx(
        filepath=abspath,
        use_selection=False,
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        object_types={"ARMATURE"},
        use_armature_deform_only=False,
        add_leaf_bones=False,
        bake_anim=has_actions,
        bake_anim_use_all_actions=has_actions,
    )
    print(f"  Exported FBX: {abspath} (animations={'yes' if has_actions else 'no'})")
