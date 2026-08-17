#!/usr/bin/env python3
"""
generate_female_bucket_pour.py
==============================

Looping 2.0 s bucket-dump clip. Starts and ends on FemaleIdle. The hold
is the authored arm / forearm / hand pose that tips the bucket so water
falls out the mouth onto the ground in front of the character.

Storyboard
----------
t=0.00–0.16  FemaleIdle hold.
t=0.34  Carry — bucket swings forward.
t=0.58  Dump — authored arm pose, water falls out.
t=0.58–1.48
        Small dump pulses (wrist / forearm / spine).
t=1.58  Still inverted.
t=1.84–2.00  FemaleIdle hold.

Run:
    python3 generate_female_bucket_pour.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

Quat = Tuple[float, float, float, float]
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


def rx(deg: float) -> Quat:
    return quat_axis_angle((1.0, 0.0, 0.0), math.radians(deg))


def ry(deg: float) -> Quat:
    return quat_axis_angle((0.0, 1.0, 0.0), math.radians(deg))


def rz(deg: float) -> Quat:
    return quat_axis_angle((0.0, 0.0, 1.0), math.radians(deg))


def compose(*parts: Quat) -> Quat:
    q = IDENT
    for p in parts:
        q = quat_norm(quat_mul(q, p))
    return q


def quat_euler_xyz(x_deg: float, y_deg: float, z_deg: float) -> Quat:
    """Match THREE.Euler('XYZ') / the pose editor."""
    x = math.radians(x_deg) * 0.5
    y = math.radians(y_deg) * 0.5
    z = math.radians(z_deg) * 0.5
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    return quat_norm((
        sx * cy * cz + cx * sy * sz,
        cx * sy * cz - sx * cy * sz,
        cx * cy * sz + sx * sy * cz,
        cx * cy * cz - sx * sy * sz,
    ))


# FemaleIdle bookend.
REST_RIGHT_ARM: Quat = (0.60838, 0.02168, -0.01819, 0.79314)
REST_LEFT_ARM: Quat = (0.60838, -0.02168, 0.01819, 0.79314)
REST_RIGHT_FOREARM: Quat = (0.0, 0.0, 0.17365, 0.98481)
REST_LEFT_FOREARM: Quat = (0.0, 0.0, -0.17365, 0.98481)
REST_SHOULDER: Quat = (-0.02618, 0.0, 0.0, 0.99966)

# Authored dump pose (pose-editor deltas from bind rest).
DUMP_RIGHT_ARM = quat_euler_xyz(75.447, -0.191, -85.0)
DUMP_RIGHT_FOREARM = quat_euler_xyz(0.0, 0.0, -79.0)
DUMP_RIGHT_HAND = quat_euler_xyz(0.0, 0.0, -42.0)
DUMP_SPINE = quat_euler_xyz(16.0, 0.0, 0.0)
DUMP_SPINE1 = quat_euler_xyz(6.0, 0.0, 0.0)

# Carry = halfway from idle into the dump.
CARRY_SPINE = slerp(IDENT, DUMP_SPINE, 0.5)
CARRY_SPINE1 = slerp(IDENT, DUMP_SPINE1, 0.5)
CARRY_RIGHT_ARM = slerp(REST_RIGHT_ARM, DUMP_RIGHT_ARM, 0.5)
CARRY_RIGHT_FOREARM = slerp(REST_RIGHT_FOREARM, DUMP_RIGHT_FOREARM, 0.5)
CARRY_RIGHT_HAND = slerp(IDENT, DUMP_RIGHT_HAND, 0.5)

SHAKE_RIGHT_ARM = compose(DUMP_RIGHT_ARM, rx(2.0), rz(-2.0))
SHAKE_RIGHT_FOREARM = compose(DUMP_RIGHT_FOREARM, rz(-5.0))
SHAKE_RIGHT_HAND = compose(DUMP_RIGHT_HAND, rz(-6.0))
SHAKE_SPINE = compose(DUMP_SPINE, rx(2.5))
SHAKE_SPINE1 = compose(DUMP_SPINE1, rx(1.5))

HOLD_LEFT_ARM = compose(REST_LEFT_ARM, rx(-10.0), rz(10.0))
HOLD_LEFT_FOREARM = compose(REST_LEFT_FOREARM, rz(12.0))
LEAN_SPINE2 = rx(3.0)
LEAN_NECK = rx(7.0)
LEAN_HEAD = compose(rx(6.0), ry(4.0))
DUMP_SPINE2 = rx(5.0)
DUMP_NECK = rx(10.0)
DUMP_HEAD = compose(rx(9.0), ry(5.0))

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

BUCKET_GRIP: Dict[str, Quat] = {
    "Thumb1": (0.13003, -0.08641, -0.01138, 0.98767),
    "Thumb2": (0.17365, 0.0, 0.0, 0.98481),
    "Thumb3": (0.13053, 0.0, 0.0, 0.99144),
    "Index1": (0.34202, 0.0, 0.0, 0.93969),
    "Index2": (0.50000, 0.0, 0.0, 0.86603),
    "Index3": (0.30071, 0.0, 0.0, 0.95372),
    "Middle1": (0.38268, 0.0, 0.0, 0.92388),
    "Middle2": (0.53730, 0.0, 0.0, 0.84339),
    "Middle3": (0.34202, 0.0, 0.0, 0.93969),
    "Ring1": (0.38268, 0.0, 0.0, 0.92388),
    "Ring2": (0.53730, 0.0, 0.0, 0.84339),
    "Ring3": (0.34202, 0.0, 0.0, 0.93969),
    "Pinky1": (0.34202, 0.0, 0.0, 0.93969),
    "Pinky2": (0.47716, 0.0, 0.0, 0.87882),
    "Pinky3": (0.30071, 0.0, 0.0, 0.95372),
}

FPS = 30
DURATION = 2.0
OUT_DIR = Path(__file__).resolve().parent / "viewer/public/animations"


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


def build_bucket_pour() -> Dict:
    duration = DURATION
    t_idle = 0.16
    t_carry = 0.34
    t_dump = 0.58
    t_hold = 1.42
    t_still = 1.55
    t_home = 1.84

    pulses = [
        (0.74, False),
        (0.90, True),
        (1.06, False),
        (1.22, True),
        (1.36, False),
        (t_hold, False),
    ]

    def dump_or_shake(shake: bool) -> Tuple[Quat, Quat, Quat, Quat, Quat]:
        if shake:
            return SHAKE_RIGHT_ARM, SHAKE_RIGHT_FOREARM, SHAKE_RIGHT_HAND, SHAKE_SPINE, SHAKE_SPINE1
        return DUMP_RIGHT_ARM, DUMP_RIGHT_FOREARM, DUMP_RIGHT_HAND, DUMP_SPINE, DUMP_SPINE1

    def bookend(idle: Quat, mid: List[Tuple[float, Quat]]) -> List[Tuple[float, Quat]]:
        return [(0.0, idle), (t_idle, idle), *mid, (t_home, idle), (duration, idle)]

    right_arm_ks: List[Tuple[float, Quat]] = [
        (t_carry, CARRY_RIGHT_ARM),
        (t_dump, DUMP_RIGHT_ARM),
    ]
    right_fore_ks: List[Tuple[float, Quat]] = [
        (t_carry, CARRY_RIGHT_FOREARM),
        (t_dump, DUMP_RIGHT_FOREARM),
    ]
    right_hand_ks: List[Tuple[float, Quat]] = [
        (t_carry, CARRY_RIGHT_HAND),
        (t_dump, DUMP_RIGHT_HAND),
    ]
    spine_ks: List[Tuple[float, Quat]] = [
        (t_carry, CARRY_SPINE),
        (t_dump, DUMP_SPINE),
    ]
    spine1_ks: List[Tuple[float, Quat]] = [
        (t_carry, CARRY_SPINE1),
        (t_dump, DUMP_SPINE1),
    ]
    for t, shake in pulses:
        arm, fore, hand, spine, spine1 = dump_or_shake(shake)
        right_arm_ks.append((t, arm))
        right_fore_ks.append((t, fore))
        right_hand_ks.append((t, hand))
        spine_ks.append((t, spine))
        spine1_ks.append((t, spine1))
    right_arm_ks.append((t_still, DUMP_RIGHT_ARM))
    right_fore_ks.append((t_still, DUMP_RIGHT_FOREARM))
    right_hand_ks.append((t_still, DUMP_RIGHT_HAND))
    spine_ks.append((t_still, DUMP_SPINE))
    spine1_ks.append((t_still, DUMP_SPINE1))

    tracks: List[Dict] = [
        rotation_track("mixamorigHips", [(0.0, IDENT), (duration, IDENT)]),
        rotation_track("mixamorigSpine", bookend(IDENT, spine_ks)),
        rotation_track("mixamorigSpine1", bookend(IDENT, spine1_ks)),
        rotation_track(
            "mixamorigSpine2",
            bookend(IDENT, [(t_carry, LEAN_SPINE2), (t_dump, DUMP_SPINE2), (t_still, DUMP_SPINE2)]),
        ),
        rotation_track(
            "mixamorigNeck",
            bookend(IDENT, [(t_carry, LEAN_NECK), (t_dump, DUMP_NECK), (t_still, DUMP_NECK)]),
        ),
        rotation_track(
            "mixamorigHead",
            bookend(IDENT, [(t_carry, LEAN_HEAD), (t_dump, DUMP_HEAD), (t_still, DUMP_HEAD)]),
        ),
        rotation_track("mixamorigLeftShoulder", [(0.0, REST_SHOULDER), (duration, REST_SHOULDER)]),
        rotation_track("mixamorigRightShoulder", [(0.0, REST_SHOULDER), (duration, REST_SHOULDER)]),
        rotation_track("mixamorigRightArm", bookend(REST_RIGHT_ARM, right_arm_ks)),
        rotation_track("mixamorigRightForeArm", bookend(REST_RIGHT_FOREARM, right_fore_ks)),
        rotation_track("mixamorigRightHand", bookend(IDENT, right_hand_ks)),
        rotation_track("mixamorigLeftHand", [(0.0, IDENT), (duration, IDENT)]),
        rotation_track(
            "mixamorigLeftArm",
            bookend(REST_LEFT_ARM, [(t_carry, HOLD_LEFT_ARM), (t_still, HOLD_LEFT_ARM)]),
        ),
        rotation_track(
            "mixamorigLeftForeArm",
            bookend(REST_LEFT_FOREARM, [(t_carry, HOLD_LEFT_FOREARM), (t_still, HOLD_LEFT_FOREARM)]),
        ),
    ]

    for finger, idle_q in IDLE_FINGERS.items():
        grip = BUCKET_GRIP[finger]
        tracks.append(
            rotation_track(
                f"mixamorigRightHand{finger}",
                bookend(idle_q, [(t_carry, grip), (t_still, grip)]),
            )
        )
        tracks.append(
            rotation_track(
                f"mixamorigLeftHand{finger}",
                [(0.0, idle_q), (duration, idle_q)],
            )
        )

    return {
        "meta": {
            "name": "FemaleBucketPour",
            "id": "FemaleBucketPour",
            "duration": duration,
            "fps": FPS,
            "loop": True,
        },
        "tracks": tracks,
    }


def main() -> None:
    write_spec(build_bucket_pour(), "FemaleBucketPour.anim.json")
    print("Done. Play: FemaleBucketPour with Water Bucket equipped.")


if __name__ == "__main__":
    main()
