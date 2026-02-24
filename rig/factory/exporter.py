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
