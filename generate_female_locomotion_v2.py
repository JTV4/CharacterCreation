#!/usr/bin/env python3
"""
generate_female_locomotion_v2.py
================================

Copies FemaleWalk / FemaleRun to FemaleWalkV2 / FemaleRunV2, then:

  1. Shifts the upper-arm cycle 180° so the limbs are contralateral
     (right arm forward with left leg, left arm forward with right leg).
  2. Bakes the authored LeftForeArm Euler [0, 0, 36] as the forward
     elbow fold at t=0, straightens it on the backswing, and applies
     the mirrored fold to RightForeArm when that arm comes in front.
  3. Closes the loop (last key = first key).

Run:
    python3 generate_female_locomotion_v2.py
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, List

ANIM_DIR = Path(__file__).resolve().parent / "viewer/public/animations"

UPPER_ARMS = {
    "mixamorigLeftArm",
    "mixamorigRightArm",
}

FOREARMS = {
    "mixamorigLeftForeArm",
    "mixamorigRightForeArm",
}

KNEES = {
    "mixamorigLeftLeg",
    "mixamorigRightLeg",
}

# User-authored forward elbow (viewer bone panel, Euler XYZ degrees).
# Walk: LeftForeArm [0, 0, 36]; right uses mirrored Z.
ELBOW_FWD_DEG = 36.0

# Run V2 elbow poses (viewer bone panel, Euler XYZ).
# t=0: left arm in front [0,-23,65], right arm back [0,0,16].
# Half-cycle uses the mirrored pair so the loop stays even.
RUN_LEFT_ELBOW_FWD = (0.0, -23.0, 65.0)
RUN_RIGHT_ELBOW_FWD = (0.0, 23.0, -65.0)
RUN_RIGHT_ELBOW_BACK = (0.0, 0.0, 16.0)
RUN_LEFT_ELBOW_BACK = (0.0, 0.0, -16.0)

IDENT = [0.0, 0.0, 0.0, 1.0]

# Walk only: scale Mixamo shin (knee flex) angles. 1.0 = original clip.
WALK_KNEE_SCALE = 1.4

# User-authored RightLeg at WalkV2 t=0 (viewer Euler XYZ). Applied to
# LeftLeg at half-cycle so both trailing legs match in the loop.
WALK_KNEE_START_X_DEG = 4.0


def rz(deg: float) -> List[float]:
    half = math.radians(deg) * 0.5
    return [0.0, 0.0, round(math.sin(half), 5), round(math.cos(half), 5)]


def rx(deg: float) -> List[float]:
    half = math.radians(deg) * 0.5
    return [round(math.sin(half), 5), 0.0, 0.0, round(math.cos(half), 5)]


def quat_norm(q: List[float]) -> List[float]:
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0:
        return list(IDENT)
    return [x / n, y / n, z / n, w / n]


def euler_xyz(x_deg: float, y_deg: float, z_deg: float) -> List[float]:
    """Match THREE.Euler('XYZ') / the pose editor."""
    x = math.radians(x_deg) * 0.5
    y = math.radians(y_deg) * 0.5
    z = math.radians(z_deg) * 0.5
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    return quat_norm([
        sx * cy * cz + cx * sy * sz,
        cx * sy * cz - sx * cy * sz,
        cx * cy * sz + sx * sy * cz,
        cx * cy * cz - sx * sy * sz,
    ])


def slerp(q0: List[float], q1: List[float], t: float) -> List[float]:
    a = quat_norm(q0)
    b = quat_norm(q1)
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0.0:
        b = [-v for v in b]
        dot = -dot
    if dot > 0.9995:
        return quat_norm([a[i] * (1.0 - t) + b[i] * t for i in range(4)])
    dot = max(-1.0, min(1.0, dot))
    theta_0 = math.acos(dot)
    sin_0 = math.sin(theta_0)
    theta = theta_0 * t
    s0 = math.cos(theta) - dot * math.sin(theta) / sin_0
    s1 = math.sin(theta) / sin_0
    return quat_norm([s0 * a[i] + s1 * b[i] for i in range(4)])


def lerp(a: List[float], b: List[float], t: float) -> List[float]:
    return [a[i] + (b[i] - a[i]) * t for i in range(len(a))]


def sample_track(track: Dict[str, Any], time: float, duration: float) -> List[float]:
    """Linear sample of a looping track at `time`."""
    kfs = track["keyframes"]
    t = time % duration if duration > 0 else 0.0
    times = [float(kf["time"]) for kf in kfs]
    values = [kf["value"] for kf in kfs]
    if t <= times[0]:
        return copy.deepcopy(values[0])
    for i in range(1, len(times)):
        if t <= times[i]:
            span = times[i] - times[i - 1]
            u = 0.0 if span <= 1e-9 else (t - times[i - 1]) / span
            return lerp(values[i - 1], values[i], u)
    return copy.deepcopy(values[-1])


def shift_looping_track(track: Dict[str, Any], shift: float, duration: float) -> Dict[str, Any]:
    """Advance a looping track by `shift` seconds, keeping keys sorted and closed."""
    out = copy.deepcopy(track)
    wrapped: List[Dict[str, Any]] = []
    seen = set()
    for kf in track["keyframes"]:
        t = float(kf["time"])
        if t >= duration - 1e-6:
            continue
        new_t = round((t + shift) % duration, 5)
        if new_t in seen:
            continue
        seen.add(new_t)
        wrapped.append({"time": new_t, "value": copy.deepcopy(kf["value"])})
    wrapped.sort(key=lambda kf: kf["time"])
    if not wrapped:
        return out
    if wrapped[0]["time"] > 1e-6:
        wrapped.insert(0, {
            "time": 0.0,
            "value": sample_track(track, (0.0 - shift) % duration, duration),
        })
    first = copy.deepcopy(wrapped[0])
    first["time"] = round(duration, 5)
    wrapped.append(first)
    out["keyframes"] = wrapped
    return out


def scale_rx_quat(q: List[float], scale: float) -> List[float]:
    """Scale a (mostly) X-axis rotation quaternion's angle."""
    x, y, z, w = q
    angle = 2.0 * math.atan2(x, w)
    half = 0.5 * angle * scale
    return [
        round(math.sin(half), 5),
        round(y, 5),
        round(z, 5),
        round(math.cos(half), 5),
    ]


def scale_knee_track(track: Dict[str, Any], scale: float) -> Dict[str, Any]:
    out = copy.deepcopy(track)
    out["keyframes"] = [
        {"time": kf["time"], "value": scale_rx_quat(kf["value"], scale)}
        for kf in track["keyframes"]
    ]
    return out


def set_key_at(track: Dict[str, Any], time: float, value: List[float]) -> None:
    t = round(time, 5)
    for kf in track["keyframes"]:
        if abs(float(kf["time"]) - t) < 1e-4:
            kf["time"] = t
            kf["value"] = copy.deepcopy(value)
            return
    track["keyframes"].append({"time": t, "value": copy.deepcopy(value)})
    track["keyframes"].sort(key=lambda kf: float(kf["time"]))


def apply_walk_start_knee(tracks: List[Dict[str, Any]], duration: float) -> None:
    """Bake RightLeg [4,0,0] at t=0 and the same pose on LeftLeg at mid-cycle."""
    pose = rx(WALK_KNEE_START_X_DEG)
    half = duration * 0.5
    for track in tracks:
        if track.get("property") != "rotation":
            continue
        if track.get("bone") == "mixamorigRightLeg":
            set_key_at(track, 0.0, pose)
            set_key_at(track, duration, pose)
        elif track.get("bone") == "mixamorigLeftLeg":
            set_key_at(track, half, pose)


def forearm_track(
    bone: str,
    duration: float,
    times: List[float],
    back_quat: List[float],
    fwd_quat: List[float],
    *,
    left: bool,
) -> Dict[str, Any]:
    """Slerp from `back_quat` (arm behind) to `fwd_quat` (arm in front).

    Left arm is in front at t=0; right arm is in front at half-cycle.
    """
    keyframes = []
    for t in times:
        p = (t / duration) % 1.0 if duration else 0.0
        if left:
            u = 0.5 * (1.0 + math.cos(2.0 * math.pi * p))
        else:
            u = 0.5 * (1.0 - math.cos(2.0 * math.pi * p))
        q = slerp(back_quat, fwd_quat, u)
        keyframes.append({"time": round(t, 5), "value": [round(v, 5) for v in q]})
    return {
        "bone": bone,
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": keyframes,
    }


def make_v2(
    src_name: str,
    dst_id: str,
    knee_scale: float = 1.0,
    walk_start_knee: bool = False,
    left_elbow_euler: tuple[float, float, float] | None = None,
    right_elbow_euler: tuple[float, float, float] | None = None,
    left_elbow_back_euler: tuple[float, float, float] | None = None,
    right_elbow_back_euler: tuple[float, float, float] | None = None,
) -> Path:
    src = json.loads((ANIM_DIR / src_name).read_text())
    duration = float(src["meta"]["duration"])
    shift = duration * 0.5

    dst = copy.deepcopy(src)
    dst["meta"]["name"] = dst_id
    dst["meta"]["id"] = dst_id
    dst["meta"]["_comment"] = (
        f"Copy of {src['meta']['id']} with the arm cycle shifted 180° "
        "(right arm + left leg, left arm + right leg). Elbows use the "
        "authored LeftForeArm [0,0,36] forward fold; the right arm gets "
        "the mirrored fold when it comes in front. Loop starts on that pose."
    )

    tracks: List[Dict[str, Any]] = []
    arm_times: List[float] | None = None
    for track in src["tracks"]:
        bone = track.get("bone")
        prop = track.get("property")
        if bone in FOREARMS and prop == "rotation":
            continue
        if bone in UPPER_ARMS and prop == "rotation":
            shifted = shift_looping_track(track, shift, duration)
            tracks.append(shifted)
            if bone == "mixamorigLeftArm":
                arm_times = [float(kf["time"]) for kf in shifted["keyframes"]]
            continue
        if bone in KNEES and prop == "rotation" and knee_scale != 1.0:
            tracks.append(scale_knee_track(track, knee_scale))
            continue
        tracks.append(copy.deepcopy(track))

    if not arm_times:
        n = int(round(duration * 30))
        arm_times = [duration * i / n for i in range(n + 1)]

    if left_elbow_euler is None:
        left_elbow_euler = (0.0, 0.0, ELBOW_FWD_DEG)
    if right_elbow_euler is None:
        right_elbow_euler = (0.0, 0.0, -ELBOW_FWD_DEG)
    if left_elbow_back_euler is None:
        left_elbow_back_euler = (0.0, 0.0, 0.0)
    if right_elbow_back_euler is None:
        right_elbow_back_euler = (0.0, 0.0, 0.0)
    left_fwd = euler_xyz(*left_elbow_euler)
    right_fwd = euler_xyz(*right_elbow_euler)
    left_back = euler_xyz(*left_elbow_back_euler)
    right_back = euler_xyz(*right_elbow_back_euler)

    tracks.append(forearm_track(
        "mixamorigLeftForeArm", duration, arm_times, left_back, left_fwd, left=True,
    ))
    tracks.append(forearm_track(
        "mixamorigRightForeArm", duration, arm_times, right_back, right_fwd, left=False,
    ))
    if walk_start_knee:
        apply_walk_start_knee(tracks, duration)
    dst["tracks"] = tracks

    out_path = ANIM_DIR / f"{dst_id}.anim.json"
    out_path.write_text(json.dumps(dst, indent=2) + "\n")
    extra = f", knee x{knee_scale:.2f}" if knee_scale != 1.0 else ""
    print(
        f"Wrote {out_path.name} from {src_name} "
        f"(arm phase +{shift:.3f}s, elbow fwd {ELBOW_FWD_DEG:.0f}°{extra})"
    )
    return out_path


def main() -> None:
    make_v2(
        "FemaleWalk.anim.json",
        "FemaleWalkV2",
        knee_scale=WALK_KNEE_SCALE,
        walk_start_knee=True,
    )
    make_v2(
        "FemaleRun.anim.json",
        "FemaleRunV2",
        left_elbow_euler=RUN_LEFT_ELBOW_FWD,
        right_elbow_euler=RUN_RIGHT_ELBOW_FWD,
        left_elbow_back_euler=RUN_LEFT_ELBOW_BACK,
        right_elbow_back_euler=RUN_RIGHT_ELBOW_BACK,
    )


if __name__ == "__main__":
    main()
