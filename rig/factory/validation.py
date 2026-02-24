"""Rig spec validation — checks structural integrity of rig_spec.json."""

from __future__ import annotations

from typing import Any

REQUIRED_BONES: set[str] = {
    "root", "pelvis",
    "spine_01", "spine_02", "spine_03",
    "neck_01", "head",
    "jaw", "eye_L", "eye_R",
    "clavicle_L", "upperarm_L", "lowerarm_L", "hand_L",
    "clavicle_R", "upperarm_R", "lowerarm_R", "hand_R",
    "thigh_L", "shin_L", "foot_L", "toe_L",
    "thigh_R", "shin_R", "foot_R", "toe_R",
}

FINGER_NAMES: list[str] = ["thumb", "index", "middle", "ring", "pinky"]
FINGER_JOINTS: list[str] = ["01", "02", "03"]
VALID_SIDES: set[str] = {"C", "L", "R"}
VALID_CATEGORIES: set[str] = {"spine", "arm", "leg", "finger", "face", "other"}

MIRROR_TOLERANCE: float = 0.001


class RigSpecError(Exception):
    """Raised when rig spec validation fails."""


def _collect_finger_bones(side: str) -> set[str]:
    """Return the expected set of finger bone names for one side."""
    return {
        f"{finger}_{joint}_{side}"
        for finger in FINGER_NAMES
        for joint in FINGER_JOINTS
    }


def _check_unique_names(bones: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for bone in bones:
        name = bone["name"]
        if name in seen:
            raise RigSpecError(f"Duplicate bone name: '{name}'")
        seen.add(name)


def _check_parents_exist(bones: list[dict[str, Any]]) -> None:
    names = {b["name"] for b in bones}
    for bone in bones:
        parent = bone.get("parent")
        if parent is not None and parent not in names:
            raise RigSpecError(
                f"Bone '{bone['name']}' references non-existent parent '{parent}'"
            )


def _check_no_cycles(bones: list[dict[str, Any]]) -> None:
    parent_map: dict[str, str | None] = {b["name"]: b.get("parent") for b in bones}

    for name in parent_map:
        visited: set[str] = set()
        current: str | None = name
        while current is not None:
            if current in visited:
                raise RigSpecError(f"Cycle detected in bone hierarchy at '{current}'")
            visited.add(current)
            current = parent_map.get(current)


def _check_required_bones(bones: list[dict[str, Any]]) -> None:
    names = {b["name"] for b in bones}
    missing = REQUIRED_BONES - names
    if missing:
        raise RigSpecError(f"Missing required bones: {sorted(missing)}")


def _check_finger_bones(bones: list[dict[str, Any]]) -> None:
    names = {b["name"] for b in bones}

    for side in ("L", "R"):
        expected = _collect_finger_bones(side)
        missing = expected - names
        if missing:
            raise RigSpecError(
                f"Missing finger bones on side {side}: {sorted(missing)}"
            )
        present = expected & names
        if len(present) != 15:
            raise RigSpecError(
                f"Expected 15 finger bones on side {side}, found {len(present)}"
            )


def _check_sides(bones: list[dict[str, Any]]) -> None:
    for bone in bones:
        side = bone.get("side")
        if side not in VALID_SIDES:
            raise RigSpecError(
                f"Bone '{bone['name']}' has invalid side '{side}' "
                f"(must be one of {VALID_SIDES})"
            )


def _check_categories(bones: list[dict[str, Any]]) -> None:
    for bone in bones:
        cat = bone.get("category")
        if cat not in VALID_CATEGORIES:
            raise RigSpecError(
                f"Bone '{bone['name']}' has invalid category '{cat}' "
                f"(must be one of {VALID_CATEGORIES})"
            )


def _check_mirror_pairs(
    bones: list[dict[str, Any]], mirror_pairs: list[list[str]]
) -> None:
    bone_map: dict[str, dict[str, Any]] = {b["name"]: b for b in bones}
    names = set(bone_map.keys())

    l_bones = {n for n in names if n.endswith("_L")}
    r_bones = {n for n in names if n.endswith("_R")}

    pair_l_names = {p[0] for p in mirror_pairs}
    pair_r_names = {p[1] for p in mirror_pairs}

    unlisted_l = l_bones - pair_l_names
    if unlisted_l:
        raise RigSpecError(
            f"L-side bones not in mirror_pairs: {sorted(unlisted_l)}"
        )
    unlisted_r = r_bones - pair_r_names
    if unlisted_r:
        raise RigSpecError(
            f"R-side bones not in mirror_pairs: {sorted(unlisted_r)}"
        )

    for left_name, right_name in mirror_pairs:
        if left_name not in names:
            raise RigSpecError(
                f"Mirror pair references non-existent bone '{left_name}'"
            )
        if right_name not in names:
            raise RigSpecError(
                f"Mirror pair references non-existent bone '{right_name}'"
            )

        left = bone_map[left_name]
        right = bone_map[right_name]

        for attr in ("head", "tail"):
            lx, ly, lz = left[attr]
            rx, ry, rz = right[attr]

            if abs(lx + rx) > MIRROR_TOLERANCE:
                raise RigSpecError(
                    f"Mirror pair ({left_name}, {right_name}) X not mirrored "
                    f"for {attr}: L={lx}, R={rx} (expected R={-lx})"
                )
            if abs(ly - ry) > MIRROR_TOLERANCE:
                raise RigSpecError(
                    f"Mirror pair ({left_name}, {right_name}) Y mismatch "
                    f"for {attr}: L={ly}, R={ry}"
                )
            if abs(lz - rz) > MIRROR_TOLERANCE:
                raise RigSpecError(
                    f"Mirror pair ({left_name}, {right_name}) Z mismatch "
                    f"for {attr}: L={lz}, R={rz}"
                )


def _check_bone_fields(bones: list[dict[str, Any]]) -> None:
    required_fields = {"name", "parent", "side", "head", "tail", "roll", "deform", "category"}
    for bone in bones:
        missing = required_fields - set(bone.keys())
        if missing:
            raise RigSpecError(
                f"Bone '{bone.get('name', '???')}' is missing fields: {sorted(missing)}"
            )
        head = bone["head"]
        tail = bone["tail"]
        if not (isinstance(head, list) and len(head) == 3):
            raise RigSpecError(f"Bone '{bone['name']}' head must be [x, y, z]")
        if not (isinstance(tail, list) and len(tail) == 3):
            raise RigSpecError(f"Bone '{bone['name']}' tail must be [x, y, z]")
        if not isinstance(bone["roll"], (int, float)):
            raise RigSpecError(f"Bone '{bone['name']}' roll must be a number")
        if not isinstance(bone["deform"], bool):
            raise RigSpecError(f"Bone '{bone['name']}' deform must be a boolean")


def validate_rig_spec(spec: dict[str, Any]) -> None:
    """Validate the rig specification. Raises RigSpecError on any issue."""
    if "meta" not in spec:
        raise RigSpecError("Missing 'meta' section in rig spec")
    if "bones" not in spec:
        raise RigSpecError("Missing 'bones' section in rig spec")
    if "mirror_pairs" not in spec:
        raise RigSpecError("Missing 'mirror_pairs' section in rig spec")

    bones: list[dict[str, Any]] = spec["bones"]
    mirror_pairs: list[list[str]] = spec["mirror_pairs"]

    _check_bone_fields(bones)
    _check_unique_names(bones)
    _check_parents_exist(bones)
    _check_no_cycles(bones)
    _check_required_bones(bones)
    _check_finger_bones(bones)
    _check_sides(bones)
    _check_categories(bones)
    _check_mirror_pairs(bones, mirror_pairs)

    print(f"  Rig spec validated: {len(bones)} bones, {len(mirror_pairs)} mirror pairs.")
