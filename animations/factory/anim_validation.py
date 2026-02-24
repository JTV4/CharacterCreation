"""Animation spec validation — checks keyframe data against the rig spec."""

from __future__ import annotations

import math
from typing import Any


class AnimSpecError(Exception):
    """Raised when animation spec validation fails."""


VALID_PROPERTIES: set[str] = {"rotation", "position"}
VALID_INTERPOLATIONS: set[str] = {"linear", "step"}
QUAT_NORM_TOLERANCE: float = 0.01


def _check_meta(meta: dict[str, Any]) -> None:
    required = {"name", "id", "duration", "fps", "loop"}
    missing = required - set(meta.keys())
    if missing:
        raise AnimSpecError(f"Animation meta missing fields: {sorted(missing)}")
    if not isinstance(meta["duration"], (int, float)) or meta["duration"] <= 0:
        raise AnimSpecError(f"Duration must be a positive number, got {meta['duration']}")
    if not isinstance(meta["fps"], (int, float)) or meta["fps"] <= 0:
        raise AnimSpecError(f"FPS must be a positive number, got {meta['fps']}")
    if not isinstance(meta["loop"], bool):
        raise AnimSpecError(f"Loop must be a boolean, got {meta['loop']}")


def _check_tracks(
    tracks: list[dict[str, Any]],
    rig_bone_names: set[str],
    duration: float,
) -> None:
    seen_pairs: set[tuple[str, str]] = set()

    for i, track in enumerate(tracks):
        bone = track.get("bone")
        prop = track.get("property")
        interp = track.get("interpolation")
        keyframes = track.get("keyframes")

        if not bone or not isinstance(bone, str):
            raise AnimSpecError(f"Track {i}: missing or invalid 'bone' field")
        if bone not in rig_bone_names:
            raise AnimSpecError(
                f"Track {i}: bone '{bone}' does not exist in the rig spec"
            )

        if prop not in VALID_PROPERTIES:
            raise AnimSpecError(
                f"Track {i} ({bone}): property must be one of {VALID_PROPERTIES}, got '{prop}'"
            )

        if prop == "position" and bone != "root":
            raise AnimSpecError(
                f"Track {i} ({bone}): position tracks are only allowed on the 'root' bone"
            )

        if interp not in VALID_INTERPOLATIONS:
            raise AnimSpecError(
                f"Track {i} ({bone}): interpolation must be one of {VALID_INTERPOLATIONS}, got '{interp}'"
            )

        pair = (bone, prop)
        if pair in seen_pairs:
            raise AnimSpecError(
                f"Track {i}: duplicate track for bone '{bone}' property '{prop}'"
            )
        seen_pairs.add(pair)

        if not isinstance(keyframes, list):
            raise AnimSpecError(f"Track {i} ({bone}): keyframes must be a list")

        _check_keyframes(keyframes, bone, prop, duration, i)


def _check_keyframes(
    keyframes: list[dict[str, Any]],
    bone: str,
    prop: str,
    duration: float,
    track_idx: int,
) -> None:
    expected_len = 4 if prop == "rotation" else 3
    prev_time: float = -1.0

    for j, kf in enumerate(keyframes):
        time = kf.get("time")
        value = kf.get("value")

        if not isinstance(time, (int, float)):
            raise AnimSpecError(
                f"Track {track_idx} ({bone}), keyframe {j}: time must be a number"
            )

        if time < -0.001 or time > duration + 0.001:
            raise AnimSpecError(
                f"Track {track_idx} ({bone}), keyframe {j}: "
                f"time {time} outside range [0, {duration}]"
            )

        if time < prev_time - 0.001:
            raise AnimSpecError(
                f"Track {track_idx} ({bone}), keyframe {j}: "
                f"times must be in ascending order (got {time} after {prev_time})"
            )
        prev_time = time

        if not isinstance(value, list) or len(value) != expected_len:
            raise AnimSpecError(
                f"Track {track_idx} ({bone}), keyframe {j}: "
                f"value must be a list of {expected_len} numbers for '{prop}'"
            )

        for k, v in enumerate(value):
            if not isinstance(v, (int, float)):
                raise AnimSpecError(
                    f"Track {track_idx} ({bone}), keyframe {j}: "
                    f"value[{k}] must be a number, got {type(v).__name__}"
                )

        if prop == "rotation":
            norm = math.sqrt(sum(v * v for v in value))
            if abs(norm - 1.0) > QUAT_NORM_TOLERANCE:
                raise AnimSpecError(
                    f"Track {track_idx} ({bone}), keyframe {j}: "
                    f"quaternion is not unit-length (norm={norm:.4f})"
                )


def validate_anim_spec(
    anim_spec: dict[str, Any],
    rig_spec: dict[str, Any],
) -> None:
    """Validate an animation spec against the rig spec.

    Raises AnimSpecError on any issue.
    """
    if "meta" not in anim_spec:
        raise AnimSpecError("Missing 'meta' section in animation spec")
    if "tracks" not in anim_spec:
        raise AnimSpecError("Missing 'tracks' section in animation spec")

    meta = anim_spec["meta"]
    tracks = anim_spec["tracks"]

    _check_meta(meta)

    rig_bone_names = {b["name"] for b in rig_spec["bones"]}
    _check_tracks(tracks, rig_bone_names, meta["duration"])

    print(
        f"  Animation '{meta['name']}' validated: "
        f"{len(tracks)} tracks, {meta['duration']}s, "
        f"{'looping' if meta['loop'] else 'one-shot'}."
    )
