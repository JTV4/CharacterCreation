#!/usr/bin/env python3
"""
generate_female_hammering.py
============================

Generates a 3-clip Age-of-Empires-style building hammer set for the
BaseFemale / BaseFemaleV2 Mixamo rig:

  1. FemaleHammerKneel  — stand → one-knee kneel (one-shot)
  2. FemaleHammering    — kneeling hammer loop, 0.5 s per swing (loop)
  3. FemaleHammerStand  — kneel → stand back to idle (one-shot)

Storyboard
----------
Kneel (0.50 s):
    t=0.00  Standing idle / rest pose.
    t=0.20  Weight shifts; right knee starts folding; hips drop.
    t=0.50  Settled on right knee, left foot planted, hammer raised.

Hammer loop (0.50 s):
    t=0.00  Hammer raised (wind-up).
    t=0.18  Mid-swing.
    t=0.25  Impact — strike + torso pulse.
    t=0.38  Rebound.
    t=0.50  Back to raised (seamless loop).

Stand (0.50 s):
    Reverse of kneel; ends on standing rest / idle.

Run:
    python3 generate_female_hammering.py
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

# ----------------------------------------------------------------------
# Quaternion helpers (JSON order is [x, y, z, w])
# ----------------------------------------------------------------------

Quat = Tuple[float, float, float, float]
Vec3 = Tuple[float, float, float]

IDENT: Quat = (0.0, 0.0, 0.0, 1.0)


def quat_axis_angle(axis: Tuple[float, float, float], angle_rad: float) -> Quat:
    ax, ay, az = axis
    length = math.sqrt(ax * ax + ay * ay + az * az)
    if length == 0:
        return IDENT
    ax, ay, az = ax / length, ay / length, az / length
    s = math.sin(angle_rad * 0.5)
    c = math.cos(angle_rad * 0.5)
    return (ax * s, ay * s, az * s, c)


def quat_mul(a: Quat, b: Quat) -> Quat:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def quat_norm(q: Quat) -> Quat:
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0:
        return IDENT
    return (x / n, y / n, z / n, w / n)


def rx(deg: float) -> Quat:
    return quat_axis_angle((1.0, 0.0, 0.0), math.radians(deg))


def ry(deg: float) -> Quat:
    return quat_axis_angle((0.0, 1.0, 0.0), math.radians(deg))


def rz(deg: float) -> Quat:
    return quat_axis_angle((0.0, 0.0, 1.0), math.radians(deg))


def slerp(q0: Quat, q1: Quat, t: float) -> Quat:
    dot = sum(a * b for a, b in zip(q0, q1))
    if dot < 0.0:
        q1 = tuple(-v for v in q1)  # type: ignore[assignment]
        dot = -dot
    if dot > 0.9995:
        lerped = tuple(a * (1.0 - t) + b * t for a, b in zip(q0, q1))  # type: ignore[assignment]
        return quat_norm(lerped)  # type: ignore[arg-type]
    dot = max(-1.0, min(1.0, dot))
    theta_0 = math.acos(dot)
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * t
    sin_theta = math.sin(theta)
    s0 = math.cos(theta) - dot * sin_theta / sin_theta_0
    s1 = sin_theta / sin_theta_0
    return tuple(s0 * a + s1 * b for a, b in zip(q0, q1))  # type: ignore[return-value]


def ease_in_out(t: float) -> float:
    """Smoothstep easing for stand↔kneel transitions."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# ----------------------------------------------------------------------
# Rest pose (shared with other Female clips)
# ----------------------------------------------------------------------

REST_SHOULDER: Quat = (-0.02618, 0.0, 0.0, 0.99966)
REST_RIGHT_ARM: Quat = (0.60838, 0.02168, -0.01819, 0.79314)
REST_LEFT_ARM: Quat = (0.60838, -0.02168, 0.01819, 0.79314)
REST_RIGHT_FOREARM: Quat = (0.0, 0.0, 0.17365, 0.98481)
REST_LEFT_FOREARM: Quat = (0.0, 0.0, -0.17365, 0.98481)

# Hammer grip (tighter than idle curl — from FemaleForging).
HAMMER_FINGERS: Dict[str, Quat] = {
    "Thumb1": (0.13003, -0.08641, -0.01138, 0.98767),
    "Thumb2": (0.17365, 0.0, 0.0, 0.98481),
    "Thumb3": (0.13053, 0.0, 0.0, 0.99144),
    "Index1": (0.38268, 0.0, 0.0, 0.92388),
    "Index2": (0.57358, 0.0, 0.0, 0.81915),
    "Index3": (0.34202, 0.0, 0.0, 0.93969),
    "Middle1": (0.42262, 0.0, 0.0, 0.90631),
    "Middle2": (0.60876, 0.0, 0.0, 0.79335),
    "Middle3": (0.38268, 0.0, 0.0, 0.92388),
    "Ring1": (0.42262, 0.0, 0.0, 0.90631),
    "Ring2": (0.60876, 0.0, 0.0, 0.79335),
    "Ring3": (0.38268, 0.0, 0.0, 0.92388),
    "Pinky1": (0.38268, 0.0, 0.0, 0.92388),
    "Pinky2": (0.53730, 0.0, 0.0, 0.84339),
    "Pinky3": (0.34202, 0.0, 0.0, 0.93969),
}

# Idle finger curl (for stand end pose).
IDLE_FINGERS: Dict[str, Quat] = {
    "Thumb1": (0.08716, 0.0, 0.0, 0.99619),
    "Thumb2": (0.13053, 0.0, 0.0, 0.99144),
    "Thumb3": (0.08716, 0.0, 0.0, 0.99619),
    "Index1": (0.15643, 0.0, 0.0, 0.98769),
    "Index2": (0.24192, 0.0, 0.0, 0.97030),
    "Index3": (0.15643, 0.0, 0.0, 0.98769),
    "Middle1": (0.17365, 0.0, 0.0, 0.98481),
    "Middle2": (0.25882, 0.0, 0.0, 0.96593),
    "Middle3": (0.17365, 0.0, 0.0, 0.98481),
    "Ring1": (0.19081, 0.0, 0.0, 0.98163),
    "Ring2": (0.28402, 0.0, 0.0, 0.95882),
    "Ring3": (0.19081, 0.0, 0.0, 0.98163),
    "Pinky1": (0.21644, 0.0, 0.0, 0.97630),
    "Pinky2": (0.30071, 0.0, 0.0, 0.95372),
    "Pinky3": (0.21644, 0.0, 0.0, 0.97630),
}


# ----------------------------------------------------------------------
# Shared kneel pose (right knee down, left foot planted)
#
# Convention (matches FemaleKick / FemaleDeath / FemaleFarming):
#   Spine / UpLeg / Hips / Head / Foot: +X = forward bend
#   Leg (shin):                         -X = knee folds
# ----------------------------------------------------------------------

# User-authored kneel pose (Pose Editor Euler XYZ degrees → delta quats).
# Right knee down, left foot planted forward.
KNEEL_HIPS_POS: Vec3 = (0.0, 0.0, 34.0)
KNEEL_HIPS_X = -7.0
KNEEL_SPINE_X = 18.0
KNEEL_SPINE1_X = 12.0
KNEEL_SPINE2_X = 6.0
KNEEL_NECK_X = 8.0
KNEEL_HEAD_X = 4.0

# Right knee down.
KNEEL_RIGHT_UPLEG = ry(-6.0)          # [0, -6, 0]
KNEEL_RIGHT_LEG = rx(-90.0)           # [-90, 0, 0]
KNEEL_RIGHT_FOOT = rx(5.0)            # [5, 0, 0]
KNEEL_RIGHT_TOE = rx(68.0)            # [68, 0, 0]

# Left foot planted forward.
KNEEL_LEFT_UPLEG = quat_mul(rx(69.0), ry(8.0))  # [69, 8, 0]
KNEEL_LEFT_LEG = rx(-79.0)            # [-79, 0, 0]
KNEEL_LEFT_FOOT = rx(2.0)             # [2, 0, 0]
KNEEL_LEFT_TOE = IDENT                # [0, 0, 0]

# Thigh/shin fold before the hip drop.
KNEEL_LEG_BONES: Tuple[Tuple[str, Quat], ...] = (
    ("mixamorigRightUpLeg", KNEEL_RIGHT_UPLEG),
    ("mixamorigRightLeg", KNEEL_RIGHT_LEG),
    ("mixamorigLeftUpLeg", KNEEL_LEFT_UPLEG),
    ("mixamorigLeftLeg", KNEEL_LEFT_LEG),
)

# Foot/toe settle with the hip drop so soles aren't driven through Z=0
# while the character is still at standing height.
KNEEL_FOOT_BONES: Tuple[Tuple[str, Quat], ...] = (
    ("mixamorigRightFoot", KNEEL_RIGHT_FOOT),
    ("mixamorigRightToeBase", KNEEL_RIGHT_TOE),
    ("mixamorigLeftFoot", KNEEL_LEFT_FOOT),
    ("mixamorigLeftToeBase", KNEEL_LEFT_TOE),
)

# Left arm braces near the work / ground (mirrors FireStarting kneel reach).
KNEEL_LEFT_ARM = (0.46321, -0.39502, 0.50709, 0.61013)
KNEEL_LEFT_FOREARM = REST_LEFT_FOREARM
KNEEL_LEFT_HAND = IDENT

# Right arm: raised hammer wind-up (from FemaleForging peak).
HAMMER_RAISED_ARM = (0.42637, 0.43452, -0.57327, 0.54842)
HAMMER_RAISED_FOREARM = (-0.11985, 0.11379, -0.67993, 0.71441)
HAMMER_RAISED_HAND = IDENT

# Right arm: impact / strike (adapted from FemaleForging strike + more reach).
HAMMER_STRIKE_ARM = (0.52698, 0.30478, -0.40586, 0.68167)
HAMMER_STRIKE_FOREARM = (-0.00861, 0.16504, -0.00144, 0.98625)
HAMMER_STRIKE_HAND = (-0.03698, -0.22931, 0.38303, 0.89406)

# Extra torso pulse on impact (added on top of kneel spine).
IMPACT_SPINE_EXTRA_X = 14.0
IMPACT_SPINE1_EXTRA_X = 6.0

FPS = 30
OUT_DIR = Path(__file__).resolve().parent / "viewer/public/animations"


# ----------------------------------------------------------------------
# Track builders
# ----------------------------------------------------------------------

def _rounded(q: Quat, digits: int = 5) -> List[float]:
    return [round(v, digits) for v in q]


def make_keyframe(time_s: float, value: Quat) -> Dict:
    return {"time": round(time_s, 5), "value": _rounded(value)}


def rotation_track(bone: str, kfs: Sequence[Tuple[float, Quat]]) -> Dict:
    return {
        "bone": bone,
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": [make_keyframe(t, quat_norm(q)) for t, q in kfs],
    }


def position_track(bone: str, kfs: Sequence[Tuple[float, Vec3]]) -> Dict:
    return {
        "bone": bone,
        "property": "position",
        "interpolation": "linear",
        "keyframes": [
            {"time": round(t, 5), "value": [round(v, 5) for v in xyz]}
            for t, xyz in kfs
        ],
    }


def const_rot(bone: str, q: Quat, t0: float, t1: float) -> Dict:
    return rotation_track(bone, [(t0, q), (t1, q)])


def finger_tracks(side: str, pose: Dict[str, Quat], t0: float, t1: float) -> List[Dict]:
    return [
        const_rot(f"mixamorig{side}Hand{finger}", q, t0, t1)
        for finger, q in pose.items()
    ]


def finger_lerp_tracks(
    side: str,
    start: Dict[str, Quat],
    end: Dict[str, Quat],
    times: Sequence[float],
    progress: Sequence[float],
) -> List[Dict]:
    tracks: List[Dict] = []
    for finger in start:
        kfs = [
            (t, slerp(start[finger], end[finger], p))
            for t, p in zip(times, progress)
        ]
        tracks.append(rotation_track(f"mixamorig{side}Hand{finger}", kfs))
    return tracks


def _validate(spec: Dict) -> None:
    meta = spec["meta"]
    dur = meta["duration"]
    seen: set = set()
    for i, track in enumerate(spec["tracks"]):
        bone = track["bone"]
        prop = track["property"]
        key = (bone, prop)
        assert key not in seen, f"duplicate track {key}"
        seen.add(key)

        expected_len = 4 if prop == "rotation" else 3
        prev_t = -1.0
        for j, kf in enumerate(track["keyframes"]):
            t = kf["time"]
            v = kf["value"]
            assert -0.001 <= t <= dur + 0.001, f"track {i}/{bone}: time {t} out of [0,{dur}]"
            assert t >= prev_t - 0.001, f"track {i}/{bone}: non-monotonic time at kf {j}"
            prev_t = t
            assert len(v) == expected_len, f"track {i}/{bone}: bad value length {len(v)}"
            if prop == "rotation":
                norm = math.sqrt(sum(x * x for x in v))
                assert abs(norm - 1.0) < 0.01, (
                    f"track {i}/{bone} kf {j}: quaternion norm {norm:.5f} != 1.0"
                )


def write_spec(spec: Dict, filename: str) -> Path:
    _validate(spec)
    out_path = OUT_DIR / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(spec, indent=2) + "\n")
    print(
        f"Wrote {out_path.name}: "
        f"{len(spec['tracks'])} tracks, "
        f"{spec['meta']['duration']:.2f}s, "
        f"loop={spec['meta']['loop']}"
    )
    return out_path


# ----------------------------------------------------------------------
# Clip 1 — Kneel down
# ----------------------------------------------------------------------

def build_kneel() -> Dict:
    duration = 0.50
    # Dense keys so the drop stays floor-safe mid-transition.
    times = [i * 0.05 for i in range(0, 11)]  # 0.00 .. 0.50
    # Fold into the kneel leg pose first, THEN drop the hips. Dropping while
    # the legs are still straight drives feet through the floor.
    leg_p = [ease_in_out(min(1.0, t / 0.28)) for t in times]
    hip_p = [
        0.0 if t <= 0.18 else ease_in_out((t - 0.18) / (duration - 0.18))
        for t in times
    ]
    arm_p = [ease_in_out(max(0.0, (t - 0.10) / (duration - 0.10))) for t in times]

    tracks: List[Dict] = []

    # Hips drop.
    tracks.append(
        position_track(
            "mixamorigHips",
            [
                (t, (0.0, 0.0, KNEEL_HIPS_POS[2] * p))
                for t, p in zip(times, hip_p)
            ],
        )
    )

    # Torso.
    for bone, end_deg in (
        ("mixamorigHips", KNEEL_HIPS_X),
        ("mixamorigSpine", KNEEL_SPINE_X),
        ("mixamorigSpine1", KNEEL_SPINE1_X),
        ("mixamorigSpine2", KNEEL_SPINE2_X),
        ("mixamorigNeck", KNEEL_NECK_X),
        ("mixamorigHead", KNEEL_HEAD_X),
    ):
        tracks.append(
            rotation_track(bone, [(t, rx(end_deg * p)) for t, p in zip(times, hip_p)])
        )

    # Thigh/shin fold first; feet/toes settle with the hip drop.
    for bone, end_q in KNEEL_LEG_BONES:
        tracks.append(
            rotation_track(bone, [(t, slerp(IDENT, end_q, p)) for t, p in zip(times, leg_p)])
        )
    for bone, end_q in KNEEL_FOOT_BONES:
        tracks.append(
            rotation_track(bone, [(t, slerp(IDENT, end_q, p)) for t, p in zip(times, hip_p)])
        )

    # Shoulders stay near rest.
    tracks.append(const_rot("mixamorigLeftShoulder", REST_SHOULDER, 0.0, duration))
    tracks.append(const_rot("mixamorigRightShoulder", REST_SHOULDER, 0.0, duration))

    # Arms: left braces, right raises hammer.
    tracks.append(
        rotation_track(
            "mixamorigLeftArm",
            [(t, slerp(REST_LEFT_ARM, KNEEL_LEFT_ARM, p)) for t, p in zip(times, arm_p)],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigRightArm",
            [(t, slerp(REST_RIGHT_ARM, HAMMER_RAISED_ARM, p)) for t, p in zip(times, arm_p)],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigLeftForeArm",
            [(t, slerp(REST_LEFT_FOREARM, KNEEL_LEFT_FOREARM, p)) for t, p in zip(times, arm_p)],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigRightForeArm",
            [
                (t, slerp(REST_RIGHT_FOREARM, HAMMER_RAISED_FOREARM, p))
                for t, p in zip(times, arm_p)
            ],
        )
    )
    tracks.append(const_rot("mixamorigLeftHand", KNEEL_LEFT_HAND, 0.0, duration))
    tracks.append(
        rotation_track(
            "mixamorigRightHand",
            [(t, slerp(IDENT, HAMMER_RAISED_HAND, p)) for t, p in zip(times, arm_p)],
        )
    )

    # Fingers: idle → hammer grip on right; left keeps idle curl.
    tracks.extend(
        finger_lerp_tracks("Right", IDLE_FINGERS, HAMMER_FINGERS, times, arm_p)
    )
    tracks.extend(finger_tracks("Left", IDLE_FINGERS, 0.0, duration))

    return {
        "meta": {
            "name": "FemaleHammerKneel",
            "id": "FemaleHammerKneel",
            "duration": duration,
            "fps": FPS,
            "loop": False,
        },
        "tracks": tracks,
    }


# ----------------------------------------------------------------------
# Clip 2 — Hammering loop (0.5 s)
# ----------------------------------------------------------------------

def build_hammering() -> Dict:
    duration = 0.50
    # Raised → mid → impact → rebound → raised
    t_raise = 0.00
    t_mid = 0.18
    t_hit = 0.25
    t_reb = 0.38
    t_end = 0.50

    tracks: List[Dict] = []

    # Hold kneel body (constant) — only upper body swings.
    tracks.append(
        position_track(
            "mixamorigHips",
            [(t_raise, KNEEL_HIPS_POS), (t_end, KNEEL_HIPS_POS)],
        )
    )
    tracks.append(const_rot("mixamorigHips", rx(KNEEL_HIPS_X), t_raise, t_end))

    # Spine pulse on impact.
    spine_base = rx(KNEEL_SPINE_X)
    spine_hit = rx(KNEEL_SPINE_X + IMPACT_SPINE_EXTRA_X)
    tracks.append(
        rotation_track(
            "mixamorigSpine",
            [
                (t_raise, spine_base),
                (t_mid, spine_base),
                (t_hit, spine_hit),
                (t_reb, spine_base),
                (t_end, spine_base),
            ],
        )
    )
    spine1_base = rx(KNEEL_SPINE1_X)
    spine1_hit = rx(KNEEL_SPINE1_X + IMPACT_SPINE1_EXTRA_X)
    tracks.append(
        rotation_track(
            "mixamorigSpine1",
            [
                (t_raise, spine1_base),
                (t_mid, spine1_base),
                (t_hit, spine1_hit),
                (t_reb, spine1_base),
                (t_end, spine1_base),
            ],
        )
    )
    tracks.append(const_rot("mixamorigSpine2", rx(KNEEL_SPINE2_X), t_raise, t_end))
    tracks.append(const_rot("mixamorigNeck", rx(KNEEL_NECK_X), t_raise, t_end))
    # Slight head nod on impact.
    tracks.append(
        rotation_track(
            "mixamorigHead",
            [
                (t_raise, rx(KNEEL_HEAD_X)),
                (t_hit, rx(KNEEL_HEAD_X + 4.0)),
                (t_end, rx(KNEEL_HEAD_X)),
            ],
        )
    )

    # Legs locked in kneel.
    for bone, q in (*KNEEL_LEG_BONES, *KNEEL_FOOT_BONES):
        tracks.append(const_rot(bone, q, t_raise, t_end))

    tracks.append(const_rot("mixamorigLeftShoulder", REST_SHOULDER, t_raise, t_end))
    tracks.append(const_rot("mixamorigRightShoulder", REST_SHOULDER, t_raise, t_end))

    # Left arm braced near the work.
    tracks.append(const_rot("mixamorigLeftArm", KNEEL_LEFT_ARM, t_raise, t_end))
    tracks.append(const_rot("mixamorigLeftForeArm", KNEEL_LEFT_FOREARM, t_raise, t_end))
    tracks.append(const_rot("mixamorigLeftHand", KNEEL_LEFT_HAND, t_raise, t_end))

    # Right arm hammer swing.
    mid_arm = slerp(HAMMER_RAISED_ARM, HAMMER_STRIKE_ARM, 0.55)
    mid_fore = slerp(HAMMER_RAISED_FOREARM, HAMMER_STRIKE_FOREARM, 0.55)
    mid_hand = slerp(HAMMER_RAISED_HAND, HAMMER_STRIKE_HAND, 0.55)
    reb_arm = slerp(HAMMER_STRIKE_ARM, HAMMER_RAISED_ARM, 0.45)
    reb_fore = slerp(HAMMER_STRIKE_FOREARM, HAMMER_RAISED_FOREARM, 0.45)
    reb_hand = slerp(HAMMER_STRIKE_HAND, HAMMER_RAISED_HAND, 0.45)

    tracks.append(
        rotation_track(
            "mixamorigRightArm",
            [
                (t_raise, HAMMER_RAISED_ARM),
                (t_mid, mid_arm),
                (t_hit, HAMMER_STRIKE_ARM),
                (t_reb, reb_arm),
                (t_end, HAMMER_RAISED_ARM),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigRightForeArm",
            [
                (t_raise, HAMMER_RAISED_FOREARM),
                (t_mid, mid_fore),
                (t_hit, HAMMER_STRIKE_FOREARM),
                (t_reb, reb_fore),
                (t_end, HAMMER_RAISED_FOREARM),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigRightHand",
            [
                (t_raise, HAMMER_RAISED_HAND),
                (t_mid, mid_hand),
                (t_hit, HAMMER_STRIKE_HAND),
                (t_reb, reb_hand),
                (t_end, HAMMER_RAISED_HAND),
            ],
        )
    )

    tracks.extend(finger_tracks("Right", HAMMER_FINGERS, t_raise, t_end))
    tracks.extend(finger_tracks("Left", IDLE_FINGERS, t_raise, t_end))

    return {
        "meta": {
            "name": "FemaleHammering",
            "id": "FemaleHammering",
            "duration": duration,
            "fps": FPS,
            "loop": True,
        },
        "tracks": tracks,
    }


# ----------------------------------------------------------------------
# Clip 3 — Stand up
# ----------------------------------------------------------------------

def build_stand() -> Dict:
    duration = 0.50
    times = [i * 0.05 for i in range(0, 11)]  # 0.00 .. 0.50
    # Rise the hips first (feet leave the floor cleanly), THEN straighten the
    # legs. Straightening while still low drives soles through the floor.
    hip_p = [ease_in_out(min(1.0, t / 0.30)) for t in times]
    leg_p = [
        0.0 if t <= 0.18 else ease_in_out((t - 0.18) / (duration - 0.18))
        for t in times
    ]
    # Arms drop a touch earlier so they clear as the body rises.
    arm_p = [ease_in_out(min(1.0, t / 0.40)) for t in times]

    tracks: List[Dict] = []

    tracks.append(
        position_track(
            "mixamorigHips",
            [
                (t, (0.0, 0.0, KNEEL_HIPS_POS[2] * (1.0 - p)))
                for t, p in zip(times, hip_p)
            ],
        )
    )

    for bone, start_deg in (
        ("mixamorigHips", KNEEL_HIPS_X),
        ("mixamorigSpine", KNEEL_SPINE_X),
        ("mixamorigSpine1", KNEEL_SPINE1_X),
        ("mixamorigSpine2", KNEEL_SPINE2_X),
        ("mixamorigNeck", KNEEL_NECK_X),
        ("mixamorigHead", KNEEL_HEAD_X),
    ):
        tracks.append(
            rotation_track(
                bone,
                [(t, rx(start_deg * (1.0 - p))) for t, p in zip(times, hip_p)],
            )
        )

    for bone, start_q in KNEEL_LEG_BONES:
        tracks.append(
            rotation_track(
                bone,
                [(t, slerp(start_q, IDENT, p)) for t, p in zip(times, leg_p)],
            )
        )
    # Feet/toes uncurl with the hip rise so they don't dig on the way up.
    for bone, start_q in KNEEL_FOOT_BONES:
        tracks.append(
            rotation_track(
                bone,
                [(t, slerp(start_q, IDENT, p)) for t, p in zip(times, hip_p)],
            )
        )

    tracks.append(const_rot("mixamorigLeftShoulder", REST_SHOULDER, 0.0, duration))
    tracks.append(const_rot("mixamorigRightShoulder", REST_SHOULDER, 0.0, duration))

    tracks.append(
        rotation_track(
            "mixamorigLeftArm",
            [(t, slerp(KNEEL_LEFT_ARM, REST_LEFT_ARM, p)) for t, p in zip(times, arm_p)],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigRightArm",
            [(t, slerp(HAMMER_RAISED_ARM, REST_RIGHT_ARM, p)) for t, p in zip(times, arm_p)],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigLeftForeArm",
            [
                (t, slerp(KNEEL_LEFT_FOREARM, REST_LEFT_FOREARM, p))
                for t, p in zip(times, arm_p)
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigRightForeArm",
            [
                (t, slerp(HAMMER_RAISED_FOREARM, REST_RIGHT_FOREARM, p))
                for t, p in zip(times, arm_p)
            ],
        )
    )
    tracks.append(const_rot("mixamorigLeftHand", IDENT, 0.0, duration))
    tracks.append(
        rotation_track(
            "mixamorigRightHand",
            [(t, slerp(HAMMER_RAISED_HAND, IDENT, p)) for t, p in zip(times, arm_p)],
        )
    )

    tracks.extend(
        finger_lerp_tracks("Right", HAMMER_FINGERS, IDLE_FINGERS, times, arm_p)
    )
    tracks.extend(finger_tracks("Left", IDLE_FINGERS, 0.0, duration))

    return {
        "meta": {
            "name": "FemaleHammerStand",
            "id": "FemaleHammerStand",
            "duration": duration,
            "fps": FPS,
            "loop": False,
        },
        "tracks": tracks,
    }


# ----------------------------------------------------------------------

def main() -> None:
    write_spec(build_kneel(), "FemaleHammerKneel.anim.json")
    write_spec(build_hammering(), "FemaleHammering.anim.json")
    write_spec(build_stand(), "FemaleHammerStand.anim.json")

    # Bake a Z>=0 floor constraint into the hip tracks (uses BaseFemale.glb).
    bake = Path(__file__).resolve().parent / "viewer" / "bake_hammer_floor.mjs"
    if bake.exists():
        print("Baking floor constraint…")
        subprocess.run(["node", str(bake)], check=True, cwd=str(bake.parent))

    print("Done. Play order: FemaleHammerKneel → FemaleHammering (loop) → FemaleHammerStand → FemaleIdle")


if __name__ == "__main__":
    main()
