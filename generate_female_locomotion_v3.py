#!/usr/bin/env python3
"""
generate_female_locomotion_v3.py
================================

Builds FemaleWalkV3 / FemaleRunV3 from the V2 clips (contralateral arms,
authored elbow fold, walk knee tweaks) with a more relaxed pace:

  WalkV3 — slower stroll, shorter stride, smaller arm swing, softer bounce
  RunV3  — easy run / jog, same timing feel as V2 but less punchy

Run:
    python3 generate_female_locomotion_v3.py
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

ANIM_DIR = Path(__file__).resolve().parent / "viewer/public/animations"

Quat = List[float]
IDENT: Quat = [0.0, 0.0, 0.0, 1.0]
ARM_HANG: Quat = [0.58779, 0.0, 0.0, 0.80902]

FOREARMS = {"mixamorigLeftForeArm", "mixamorigRightForeArm"}
KNEES = {"mixamorigLeftLeg", "mixamorigRightLeg"}
STRIDE_BONES = {"mixamorigLeftUpLeg", "mixamorigRightUpLeg"}
FOOT_BONES = {
    "mixamorigLeftFoot",
    "mixamorigRightFoot",
    "mixamorigLeftToeBase",
    "mixamorigRightToeBase",
}
TORSO_BONES = {
    "mixamorigHips",
    "mixamorigSpine",
    "mixamorigSpine1",
    "mixamorigSpine2",
    "mixamorigNeck",
    "mixamorigHead",
}
ARM_BONES = {"mixamorigLeftArm", "mixamorigRightArm"}

WALK_KNEE_START_X_DEG = 4.0


def quat_norm(q: Sequence[float]) -> Quat:
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0:
        return list(IDENT)
    return [x / n, y / n, z / n, w / n]


def slerp(q0: Sequence[float], q1: Sequence[float], t: float) -> Quat:
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


def rx(deg: float) -> Quat:
    half = math.radians(deg) * 0.5
    return [math.sin(half), 0.0, 0.0, math.cos(half)]


def rz(deg: float) -> Quat:
    half = math.radians(deg) * 0.5
    return [0.0, 0.0, math.sin(half), math.cos(half)]


def rounded(q: Sequence[float], digits: int = 5) -> List[float]:
    return [round(v, digits) for v in q]


def time_scale_track(track: Dict[str, Any], scale: float) -> Dict[str, Any]:
    out = copy.deepcopy(track)
    for kf in out["keyframes"]:
        kf["time"] = round(float(kf["time"]) * scale, 5)
    return out


def dampen_rotations(track: Dict[str, Any], amount: float, toward: Sequence[float]) -> Dict[str, Any]:
    """Slerp every key `amount` of the way toward `toward` (0 = unchanged)."""
    if amount <= 0:
        return track
    out = copy.deepcopy(track)
    for kf in out["keyframes"]:
        kf["value"] = rounded(slerp(kf["value"], toward, amount))
    return out


def scale_positions(track: Dict[str, Any], amount: float) -> Dict[str, Any]:
    out = copy.deepcopy(track)
    for kf in out["keyframes"]:
        kf["value"] = [round(v * amount, 5) for v in kf["value"]]
    return out


def scale_rx_angles(track: Dict[str, Any], scale: float) -> Dict[str, Any]:
    out = copy.deepcopy(track)
    for kf in out["keyframes"]:
        x, y, z, w = kf["value"]
        angle = 2.0 * math.atan2(x, w)
        half = 0.5 * angle * scale
        kf["value"] = rounded([math.sin(half), y, z, math.cos(half)])
    return out


def set_key_at(track: Dict[str, Any], time: float, value: List[float]) -> None:
    t = round(time, 5)
    for kf in track["keyframes"]:
        if abs(float(kf["time"]) - t) < 1e-4:
            kf["time"] = t
            kf["value"] = rounded(value)
            return
    track["keyframes"].append({"time": t, "value": rounded(value)})
    track["keyframes"].sort(key=lambda kf: float(kf["time"]))


def forearm_track(bone: str, duration: float, times: List[float], fwd_deg: float, sign: float) -> Dict[str, Any]:
    keyframes = []
    for t in times:
        p = (t / duration) % 1.0 if duration else 0.0
        if bone.endswith("LeftForeArm"):
            deg = fwd_deg * 0.5 * (1.0 + math.cos(2.0 * math.pi * p))
        else:
            deg = fwd_deg * 0.5 * (1.0 - math.cos(2.0 * math.pi * p))
        keyframes.append({"time": round(t, 5), "value": rounded(rz(sign * deg))})
    return {
        "bone": bone,
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": keyframes,
    }


def make_relaxed(
    src_id: str,
    dst_id: str,
    *,
    time_scale: float,
    hip_bob: float,
    torso: float,
    stride: float,
    arm_swing: float,
    knee: float,
    elbow_fwd: float,
    keep_start_knee: bool,
    comment: str,
) -> Path:
    src = json.loads((ANIM_DIR / f"{src_id}.anim.json").read_text())
    src_dur = float(src["meta"]["duration"])
    duration = round(src_dur * time_scale, 5)

    dst = copy.deepcopy(src)
    dst["meta"]["name"] = dst_id
    dst["meta"]["id"] = dst_id
    dst["meta"]["duration"] = duration
    dst["meta"]["_comment"] = comment

    tracks: List[Dict[str, Any]] = []
    arm_times: List[float] | None = None
    for track in src["tracks"]:
        bone = track.get("bone")
        prop = track.get("property")
        if bone in FOREARMS and prop == "rotation":
            continue

        out = time_scale_track(track, time_scale)

        if prop == "position" and bone == "mixamorigHips":
            out = scale_positions(out, hip_bob)
        elif prop == "position":
            out = scale_positions(out, 0.5 + 0.5 * hip_bob)
        elif prop == "rotation" and bone in TORSO_BONES:
            out = dampen_rotations(out, torso, IDENT)
        elif prop == "rotation" and bone in STRIDE_BONES:
            out = dampen_rotations(out, stride, IDENT)
        elif prop == "rotation" and bone in FOOT_BONES:
            out = dampen_rotations(out, stride * 0.7, IDENT)
        elif prop == "rotation" and bone in ARM_BONES:
            out = dampen_rotations(out, arm_swing, ARM_HANG)
            arm_times = [float(kf["time"]) for kf in out["keyframes"]]
        elif prop == "rotation" and bone in KNEES:
            out = scale_rx_angles(out, knee)

        tracks.append(out)

    if not arm_times:
        n = max(8, int(round(duration * 30 / 4)))
        arm_times = [duration * i / n for i in range(n + 1)]

    tracks.append(forearm_track("mixamorigLeftForeArm", duration, arm_times, elbow_fwd, 1.0))
    tracks.append(forearm_track("mixamorigRightForeArm", duration, arm_times, elbow_fwd, -1.0))

    if keep_start_knee:
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

    dst["tracks"] = tracks
    out_path = ANIM_DIR / f"{dst_id}.anim.json"
    out_path.write_text(json.dumps(dst, indent=2) + "\n")
    print(
        f"Wrote {out_path.name} from {src_id} "
        f"({src_dur:.2f}s → {duration:.2f}s)"
    )
    return out_path


def main() -> None:
    make_relaxed(
        "FemaleWalkV2",
        "FemaleWalkV3",
        time_scale=1.35,
        hip_bob=0.55,
        torso=0.28,
        stride=0.22,
        arm_swing=0.30,
        knee=0.82,
        elbow_fwd=28.0,
        keep_start_knee=True,
        comment=(
            "Relaxed stroll based on FemaleWalkV2. Slower cycle, shorter stride, "
            "softer bounce, smaller arm swing. Same contralateral limb phase "
            "and authored start-knee pose."
        ),
    )
    make_relaxed(
        "FemaleRunV2",
        "FemaleRunV3",
        time_scale=1.22,
        hip_bob=0.75,
        torso=0.18,
        stride=0.12,
        arm_swing=0.18,
        knee=0.90,
        elbow_fwd=32.0,
        keep_start_knee=False,
        comment=(
            "Easy run / jog based on FemaleRunV2. Slightly slower and less "
            "punchy, same contralateral limb phase and forward elbow fold."
        ),
    )


if __name__ == "__main__":
    main()
