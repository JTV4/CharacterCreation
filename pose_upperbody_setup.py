"""
pose_upperbody_setup.py
=======================

Build a single .blend file containing all 18 weighted upperbody pieces
(6 metal Platebodies + 6 colour Mage Tops + 6 colour Ranged Upperbodies)
with each piece's arm bones rotated downward so the sleeves drop to the
character's sides for thumbnail screenshots.

Each piece lives in its own Collection so the user can solo one at a
time from the Outliner's eye-icon toggle.  All pieces are placed at the
world origin so the camera doesn't need repositioning between pieces.

Run headless:
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python pose_upperbody_setup.py
"""

import math
import os
import sys

import bpy
from mathutils import Euler

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
UPPERBODY_DIR = os.path.join(
    REPO_ROOT, "viewer", "public", "equipment", "Female", "Upperbody"
)
OUTPUT_BLEND = os.path.join(REPO_ROOT, "pose_upperbodies.blend")

# (display_label, weighted_glb_filename)
PIECES = [
    ("Iron Platebody",       "IronPlatebodyWeighted.glb"),
    ("Steel Platebody",      "SteelPlatebodyWeighted.glb"),
    ("Gold Platebody",       "GoldPlatebodyWeighted.glb"),
    ("Titanium Platebody",   "TitaniumPlatebodyWeighted.glb"),
    ("Tungsten Platebody",   "TungstenPlatebodyWeighted.glb"),
    ("Luminous Platebody",   "LuminousPlatebodyWeighted.glb"),

    ("Leather Mage Top",     "LeatherMageTopWeighted.glb"),
    ("Green Mage Top",       "GreenMageTopWeighted.glb"),
    ("Blue Mage Top",        "BlueMageTopWeighted.glb"),
    ("Red Mage Top",         "RedMageTopWeighted.glb"),
    ("Black Mage Top",       "BlackMageTopWeighted.glb"),
    ("Purple Mage Top",      "PurpleMageTopWeighted.glb"),

    ("Leather Ranged Upperbody", "LeatherRangedUpperbodyWeighted.glb"),
    ("Green Ranged Upperbody",   "GreenRangedUpperbodyWeighted.glb"),
    ("Blue Ranged Upperbody",    "BlueRangedUpperbodyWeighted.glb"),
    ("Red Ranged Upperbody",     "RedRangedUpperbodyWeighted.glb"),
    ("Black Ranged Upperbody",   "BlackRangedUpperbodyWeighted.glb"),
    ("Purple Ranged Upperbody",  "PurpleRangedUpperbodyWeighted.glb"),
]

# Arm rotation in degrees.  Mixamo arms are in T-pose; we need to drop
# them ~75 degrees toward the character's side.  The axis (X/Y/Z) and
# sign depend on each bone's rest orientation, so we apply rotations on
# all three Euler components -- only the correct one will actually swing
# the bone; the others stay at 0 by definition of the rest pose.
# 75deg is a "natural" A-pose drop; tweak this constant if you want the
# arms tighter to the body or further out.
ARM_DOWN_DEG = 75.0

# Bone name candidates (with and without the Mixamo "mixamorig:" prefix
# colon -- glTF importers vary).  Order matters; we use the first match.
LEFT_ARM_CANDIDATES = [
    "mixamorig:LeftArm",
    "mixamorigLeftArm",
]
RIGHT_ARM_CANDIDATES = [
    "mixamorig:RightArm",
    "mixamorigRightArm",
]


def _safe_collection_name(label: str) -> str:
    """Outliner-friendly name (Blender collection names must be <= 63 chars)."""
    name = label.strip().replace("/", "_")
    return name[:63]


def _set_active_collection(coll: bpy.types.Collection) -> None:
    """Make `coll` the active collection so subsequent imports land in it."""
    def _find(layer_coll):
        if layer_coll.collection == coll:
            return layer_coll
        for child in layer_coll.children:
            hit = _find(child)
            if hit:
                return hit
        return None

    root = bpy.context.view_layer.layer_collection
    target = _find(root)
    if target is not None:
        bpy.context.view_layer.active_layer_collection = target


def _import_glb_into_collection(glb_path: str, coll: bpy.types.Collection):
    """Import the GLB so its objects go into `coll`.

    Blender's glTF importer drops everything into the *active* layer
    collection, so we first set our target as active.  Returns the list
    of objects created by this import.
    """
    _set_active_collection(coll)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    after = set(bpy.data.objects)
    return list(after - before)


def _pose_arms_down(armature: bpy.types.Object, degrees: float) -> tuple[bool, bool]:
    """Rotate the LeftArm/RightArm bones to the character's sides.

    Returns (left_ok, right_ok) so the caller can warn on missing bones.
    """
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")

    def _resolve(candidates):
        for n in candidates:
            pb = armature.pose.bones.get(n)
            if pb is not None:
                return pb
        return None

    left = _resolve(LEFT_ARM_CANDIDATES)
    right = _resolve(RIGHT_ARM_CANDIDATES)

    # Apply rotation on the bone's local X axis.  Mixamo arm bones have
    # local Y running along the arm (shoulder->elbow) and local Z
    # pointing roughly upward in T-pose, so rotating around local Z
    # swings the arm forward/back like a zombie.  Local X is the
    # horizontal axis perpendicular to both, so rotating around it
    # swings the arm in the vertical plane -- i.e. drops it to the
    # character's side.  Sign convention: BOTH arms use the same +X
    # rotation; Mixamo's LeftArm and RightArm bones share a common
    # local-X orientation (they're not mirror-rolled), so using
    # opposite signs sends one arm down and the other up.
    rad = math.radians(degrees)
    for pb in (left, right):
        if pb is None:
            continue
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = Euler((rad, 0.0, 0.0), "XYZ")

    bpy.ops.object.mode_set(mode="OBJECT")
    return (left is not None, right is not None)


def main() -> None:
    # 1. Start from a clean factory scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 2. Set scene units to metric meters (matches the GLBs)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    summary = []

    for i, (label, fname) in enumerate(PIECES):
        glb_path = os.path.join(UPPERBODY_DIR, fname)
        if not os.path.exists(glb_path):
            summary.append(f"  MISSING: {fname}")
            continue

        coll_name = _safe_collection_name(label)
        # If a same-named collection was somehow created already, append
        # an index to avoid silent name-collision merge into one bucket.
        existing = bpy.data.collections.get(coll_name)
        if existing is not None:
            coll_name = f"{coll_name}.{i:02d}"
        coll = bpy.data.collections.new(coll_name)
        scene.collection.children.link(coll)

        new_objs = _import_glb_into_collection(glb_path, coll)

        armature = next((o for o in new_objs if o.type == "ARMATURE"), None)
        if armature is None:
            summary.append(
                f"  no armature in {fname} -- piece imported but not posed"
            )
            # hide all but the first piece
            view_coll = bpy.context.view_layer.layer_collection.children[coll_name]
            view_coll.hide_viewport = i > 0
            continue

        left_ok, right_ok = _pose_arms_down(armature, ARM_DOWN_DEG)
        bones_msg = ""
        if not left_ok:
            bones_msg += " [missing LeftArm]"
        if not right_ok:
            bones_msg += " [missing RightArm]"

        # Only the first piece is visible; rest start hidden so the
        # Outliner is uncluttered.  User clicks the eye icon to solo.
        view_coll = bpy.context.view_layer.layer_collection.children[coll_name]
        view_coll.hide_viewport = i > 0

        summary.append(f"  OK  {label}{bones_msg}")

    # 3. Frame view default-ish: position the 3D cursor at the bind-pose
    # head height (~1.7m up in glTF Y-up which becomes Z-up in Blender,
    # so ~1.7 on Blender's Z).
    scene.cursor.location = (0.0, 0.0, 1.5)

    # 4. Save
    bpy.ops.wm.save_as_mainfile(filepath=OUTPUT_BLEND)

    print("\n=== Posed upperbody setup ===")
    print(f"Pieces processed: {len(PIECES)}")
    for line in summary:
        print(line)
    print(f"\nSaved -> {OUTPUT_BLEND}")
    print("Open this .blend in Blender and solo each Collection via the")
    print("Outliner's eye icon to view one piece at a time at the origin.")


if __name__ == "__main__":
    main()
