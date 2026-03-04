"""Skin external base body meshes to the canonical rig.

Downloads Base Male and Base Female GLB meshes (or uses local paths), strips any
existing armature, applies our rig with Blender's automatic weights, and exports
skinned GLB files.

Usage (headless):
    blender --background --python equipment/factory/skin_base_meshes.py -- \
        --rig-blend rig/output/rig.blend \
        --out equipment/output/ \
        [--base-male-url URL | --base-male-path PATH] \
        [--base-female-url URL | --base-female-path PATH] \
        [--scale 1.0]

Unskin mode (strip armature from skin texture GLBs):
    blender --background --python equipment/factory/skin_base_meshes.py -- \
        --rig-blend rig/output/rig.blend \
        --out equipment/output/ \
        --unskin
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import urllib.request
from typing import Any

import bpy


def download_glb(url: str, dest_path: str) -> str:
    """Download a GLB file from URL to dest_path. Returns dest_path."""
    print(f"  Downloading: {url}")
    urllib.request.urlretrieve(url, dest_path)
    return dest_path


def get_mesh_path(url: str | None, path: str | None, temp_dir: str, slot_id: str) -> str | None:
    """Resolve mesh path from URL (download) or local path."""
    if path and os.path.isfile(path):
        return os.path.abspath(path)
    if url:
        dest = os.path.join(temp_dir, f"{slot_id}.glb")
        download_glb(url, dest)
        return dest
    return None


def clear_mesh_rigging(mesh_obj: bpy.types.Object) -> None:
    """Remove armature modifier and vertex groups from a mesh."""
    for mod in list(mesh_obj.modifiers):
        if mod.type == "ARMATURE":
            mesh_obj.modifiers.remove(mod)
    for vg in list(mesh_obj.vertex_groups):
        mesh_obj.vertex_groups.remove(vg)


def collect_mesh_objects(imported_objects: list) -> list[bpy.types.Object]:
    """Collect mesh objects from imported hierarchy, excluding armatures."""
    meshes: list[bpy.types.Object] = []
    armatures: list[bpy.types.Object] = []

    def walk(obj: bpy.types.Object) -> None:
        if obj.type == "MESH":
            meshes.append(obj)
        elif obj.type == "ARMATURE":
            armatures.append(obj)
        for child in obj.children:
            walk(child)

    for obj in imported_objects:
        walk(obj)

    # Delete imported armatures (we use our own rig)
    for arm in armatures:
        bpy.data.objects.remove(arm, do_unlink=True)

    return meshes


def import_glb(filepath: str) -> list[bpy.types.Object]:
    """Import a GLB file. Returns list of root objects created."""
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(filepath))
    return list(bpy.context.selected_objects)


def join_meshes(mesh_objs: list[bpy.types.Object], name: str) -> bpy.types.Object:
    """Join multiple mesh objects into one."""
    if len(mesh_objs) == 1:
        mesh_objs[0].name = name
        return mesh_objs[0]

    bpy.ops.object.select_all(action="DESELECT")
    for obj in mesh_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objs[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = name
    return result


def parent_with_automatic_weights(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
) -> bool:
    """Parent mesh to armature using Blender's automatic weight painting.
    Returns True if weights were applied, False if heat failed (try envelope fallback)."""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    # Check if we got valid weights (any vertex has non-zero weight)
    if mesh_obj.vertex_groups:
        for v in mesh_obj.data.vertices:
            for g in v.groups:
                if g.weight > 0.001:
                    return True
    return False


def parent_with_envelope_weights(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
) -> None:
    """Parent mesh using bone envelope weights (fallback when heat algorithm fails)."""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    # Create empty vertex groups for each bone (required for ARMATURE parent)
    for bone in armature_obj.data.bones:
        if bone.use_deform:
            mesh_obj.vertex_groups.new(name=bone.name)
    # Add armature modifier and parent
    mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = armature_obj
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.parent_set(type="ARMATURE")
    # Assign weights (try AUTOMATIC first, fallback to ENVELOPES)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    try:
        bpy.ops.paint.weight_from_bones(type="AUTOMATIC")
    except Exception:
        bpy.ops.paint.weight_from_bones(type="ENVELOPES")
    bpy.ops.object.mode_set(mode="OBJECT")


def export_skinned_glb(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
    filepath: str,
    yup: bool = False,
) -> str:
    """Export mesh + armature as skinned GLB."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(filepath),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=yup,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=False,
        export_animations=False,
        export_materials="EXPORT",
    )
    return filepath


def export_unskinned_glb(mesh_obj: bpy.types.Object, filepath: str, yup: bool = False) -> str:
    """Export mesh only (no armature, no skinning)."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj

    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(filepath),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=yup,
        export_skins=False,
        export_animations=False,
        export_materials="EXPORT",
    )
    return filepath


def flip_mesh(mesh_obj: bpy.types.Object, axis: str) -> None:
    """Mirror/flip mesh geometry on the given axis (X, Y, or Z)."""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj

    scale_map = {"X": (-1, 1, 1), "Y": (1, -1, 1), "Z": (1, 1, -1)}
    s = scale_map.get(axis.upper(), (1, 1, 1))
    mesh_obj.scale.x = s[0]
    mesh_obj.scale.y = s[1]
    mesh_obj.scale.z = s[2]
    bpy.ops.object.transform_apply(scale=True)

    # Recalculate normals (scale -1 can flip them; bone heat needs correct normals)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")


# Slots where bone heat works only if we flip BEFORE rigging (female).
# Male needs flip AFTER rigging; heat fails when flipped before.
FLIP_BEFORE_RIG_SLOTS: frozenset[str] = frozenset({"base_female", "base_female_with_skin_texture"})

# Slots that need 180° X rotation to match rig orientation (e.g. skin texture meshes from CharacterMesh).
ROTATE_X_180_SLOTS: frozenset[str] = frozenset({"base_male_with_skin_texture", "base_female_with_skin_texture"})


def unskin_mesh(mesh_path: str, output_path: str, slot_id: str) -> str | None:
    """Import a skinned GLB, strip armature/vertex groups, export as mesh-only GLB."""
    bpy.ops.wm.read_homefile(use_empty=True)

    imported = import_glb(mesh_path)
    mesh_objs = collect_mesh_objects(imported)

    if not mesh_objs:
        print(f"  Warning: No mesh found in {mesh_path}, skipping {slot_id}")
        return None

    for m in mesh_objs:
        clear_mesh_rigging(m)

    combined = join_meshes(mesh_objs, f"base_{slot_id}")

    export_unskinned_glb(combined, output_path, yup=False)
    print(f"  Exported (unskinned): {output_path}")

    bpy.data.objects.remove(combined, do_unlink=True)
    return output_path


def skin_external_mesh(
    mesh_path: str,
    slot_id: str,
    armature_obj: bpy.types.Object,
    output_dir: str,
    scale: float = 1.0,
    game_dir: str | None = None,
    fix_facing: bool = True,
    flip_axis: str | None = None,
) -> str | None:
    """Import, strip, skin, and export an external mesh to our rig."""
    # Import
    imported = import_glb(mesh_path)
    mesh_objs = collect_mesh_objects(imported)

    if not mesh_objs:
        print(f"  Warning: No mesh found in {mesh_path}, skipping {slot_id}")
        return None

    # Clear existing rigging (unrig)
    for m in mesh_objs:
        clear_mesh_rigging(m)

    # Join if multiple meshes
    combined = join_meshes(mesh_objs, f"base_{slot_id}")

    # Fix facing (align mesh to rig)
    if fix_facing:
        combined.rotation_euler.z = __import__("math").pi
        bpy.ops.object.select_all(action="DESELECT")
        combined.select_set(True)
        bpy.context.view_layer.objects.active = combined
        bpy.ops.object.transform_apply(rotation=True)

    # Extra 180° X for slots that come in upside down (e.g. skin texture meshes from CharacterMesh)
    if slot_id in ROTATE_X_180_SLOTS:
        combined.rotation_euler.x = __import__("math").pi
        bpy.ops.object.select_all(action="DESELECT")
        combined.select_set(True)
        bpy.context.view_layer.objects.active = combined
        bpy.ops.object.transform_apply(rotation=True)
        print(f"  Applied 180° X rotation (upside-down fix)")

    # Flip before rig for slots where heat fails after flip (e.g. base_female)
    if flip_axis and slot_id in FLIP_BEFORE_RIG_SLOTS:
        flip_mesh(combined, flip_axis)
        print(f"  Flipped mesh on {flip_axis} axis (before rig)")

    # Optional scale (e.g. if mesh is in different units)
    if scale != 1.0:
        combined.scale = (scale, scale, scale)
        bpy.ops.object.select_all(action="DESELECT")
        combined.select_set(True)
        bpy.context.view_layer.objects.active = combined
        bpy.ops.object.transform_apply(scale=True)

    # Parent with automatic weights (rig)
    if not parent_with_automatic_weights(combined, armature_obj):
        for mod in list(combined.modifiers):
            if mod.type == "ARMATURE":
                combined.modifiers.remove(mod)
        for vg in list(combined.vertex_groups):
            combined.vertex_groups.remove(vg)
        print(f"  Heat failed, using envelope weights")
        parent_with_envelope_weights(combined, armature_obj)

    # Flip after rig for slots where heat fails when flipped before (e.g. base_male)
    if flip_axis and slot_id not in FLIP_BEFORE_RIG_SLOTS:
        flip_mesh(combined, flip_axis)
        print(f"  Flipped mesh on {flip_axis} axis (after rig)")

    # Export (Z-up for viewer)
    out_path = os.path.join(output_dir, f"{slot_id}.glb")
    export_skinned_glb(combined, armature_obj, out_path, yup=False)
    print(f"  Exported: {out_path}")

    # Optionally export Y-up for game engines
    if game_dir:
        game_path = os.path.join(game_dir, f"{slot_id}.glb")
        export_skinned_glb(combined, armature_obj, game_path, yup=True)
        print(f"  Exported (Y-up): {game_path}")

    # Clean up mesh from scene (so next import starts fresh)
    bpy.data.objects.remove(combined, do_unlink=True)

    return out_path


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(
        description="Skin external base body meshes to the canonical rig"
    )
    parser.add_argument("--rig-blend", required=True, help="Path to the rig .blend file")
    parser.add_argument("--out", required=True, help="Output directory for skinned GLB files")
    parser.add_argument(
        "--base-male-url",
        default="https://res.cloudinary.com/dyd9wffl9/image/upload/v1772581419/BaseMale_vzq458.glb",
        help="URL for Base Male GLB",
    )
    parser.add_argument(
        "--base-female-url",
        default="https://res.cloudinary.com/dyd9wffl9/image/upload/v1772581112/BaseFemale_or1q8f.glb",
        help="URL for Base Female GLB",
    )
    parser.add_argument(
        "--base-male-path",
        default=None,
        help="Local path to Base Male GLB (overrides URL)",
    )
    parser.add_argument(
        "--base-female-path",
        default=None,
        help="Local path to Base Female GLB (overrides URL)",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor for imported meshes (default 1.0)",
    )
    parser.add_argument(
        "--male-only",
        action="store_true",
        help="Only process Base Male",
    )
    parser.add_argument(
        "--female-only",
        action="store_true",
        help="Only process Base Female",
    )
    parser.add_argument(
        "--game-out",
        default=None,
        help="Also export Y-up GLBs here for game engines (glTF standard)",
    )
    parser.add_argument(
        "--no-fix-facing",
        action="store_true",
        help="Skip 180° Z rotation (use if mesh already faces correct direction)",
    )
    parser.add_argument(
        "--flip-axis",
        choices=["X", "Y", "Z"],
        default=None,
        help="Mirror mesh on axis before rigging (X=left-right, Y=front-back, Z=up-down)",
    )
    parser.add_argument(
        "--unskin",
        action="store_true",
        help="Unskin mode: strip armature from BaseMaleWithSkinTexture and BaseFemaleWithSkinTexture GLBs",
    )
    parser.add_argument(
        "--unskin-male-path",
        default=None,
        help="Path to BaseMaleWithSkinTexture.glb (default: rig/CharacterMesh/BaseMaleWithSkinTexture.glb)",
    )
    parser.add_argument(
        "--unskin-female-path",
        default=None,
        help="Path to BaseFemaleWithSkinTexture.glb (default: rig/CharacterMesh/BaseFemaleWithSkinTexture.glb)",
    )
    parser.add_argument(
        "--unskin-out",
        default=None,
        help="Output directory for unskinned GLBs (default: same as --out)",
    )
    parser.add_argument(
        "--skin-texture-variants",
        action="store_true",
        help="Also skin base_male_with_skin_texture and base_female_with_skin_texture from equipment/output/",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    if args.unskin:
        _run_unskin(args)
        return

    print("=== Skin Base Meshes ===")

    # Load rig
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.rig_blend))

    armature_obj = None
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            armature_obj = obj
            break

    if not armature_obj:
        print("ERROR: No armature found in the .blend file.")
        sys.exit(1)

    bpy.context.view_layer.objects.active = armature_obj
    print(f"  Using armature: {armature_obj.name}")

    with tempfile.TemporaryDirectory() as temp_dir:
        tasks: list[tuple[str, str | None, str | None]] = []

        if not args.female_only:
            tasks.append(("base_male", args.base_male_path, args.base_male_url))
        if not args.male_only:
            tasks.append(("base_female", args.base_female_path, args.base_female_url))

        for slot_id, path, url in tasks:
            mesh_path = get_mesh_path(url, path, temp_dir, slot_id)
            if not mesh_path:
                print(f"  Skipping {slot_id}: no URL or valid path")
                continue

            print(f"  Processing {slot_id}...")
            skin_external_mesh(
                mesh_path,
                slot_id,
                armature_obj,
                args.out,
                scale=args.scale,
                game_dir=args.game_out,
                fix_facing=not args.no_fix_facing,
                flip_axis=args.flip_axis,
            )

        if args.skin_texture_variants:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            repo_root = os.path.dirname(os.path.dirname(script_dir))
            male_path = os.path.join(args.out, "base_male_with_skin_texture.glb")
            female_path = os.path.join(args.out, "base_female_with_skin_texture.glb")
            if not os.path.isfile(male_path):
                male_path = os.path.join(repo_root, "rig", "CharacterMesh", "BaseMaleWithSkinTexture.glb")
            if not os.path.isfile(female_path):
                female_path = os.path.join(repo_root, "rig", "CharacterMesh", "BaseFemaleWithSkinTexture.glb")

            for slot_id, mesh_path in [
                ("base_male_with_skin_texture", male_path),
                ("base_female_with_skin_texture", female_path),
            ]:
                if os.path.isfile(mesh_path):
                    print(f"  Processing {slot_id}...")
                    skin_external_mesh(
                        mesh_path,
                        slot_id,
                        armature_obj,
                        args.out,
                        scale=args.scale,
                        game_dir=args.game_out,
                        fix_facing=not args.no_fix_facing,
                        flip_axis=args.flip_axis,
                    )
                else:
                    print(f"  Skipping {slot_id}: {mesh_path} not found")

    print("=== Done ===")


def _run_unskin(args: argparse.Namespace) -> None:
    """Unskin BaseMaleWithSkinTexture and BaseFemaleWithSkinTexture GLBs."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(script_dir))
    default_male = os.path.join(repo_root, "rig", "CharacterMesh", "BaseMaleWithSkinTexture.glb")
    default_female = os.path.join(repo_root, "rig", "CharacterMesh", "BaseFemaleWithSkinTexture.glb")

    out_dir = args.unskin_out or args.out
    os.makedirs(out_dir, exist_ok=True)

    male_path = args.unskin_male_path or default_male
    female_path = args.unskin_female_path or default_female

    print("=== Unskin Base Meshes (Skin Texture) ===")

    if os.path.isfile(male_path):
        print(f"  Processing base_male_with_skin_texture...")
        unskin_mesh(
            male_path,
            os.path.join(out_dir, "base_male_with_skin_texture.glb"),
            "base_male_with_skin_texture",
        )
    else:
        print(f"  Skipping male: {male_path} not found")

    if os.path.isfile(female_path):
        print(f"  Processing base_female_with_skin_texture...")
        unskin_mesh(
            female_path,
            os.path.join(out_dir, "base_female_with_skin_texture.glb"),
            "base_female_with_skin_texture",
        )
    else:
        print(f"  Skipping female: {female_path} not found")

    print("=== Done ===")


if __name__ == "__main__":
    main()
