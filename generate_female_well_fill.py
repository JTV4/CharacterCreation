#!/usr/bin/env python3
"""
generate_female_well_fill.py
============================

Standing "busy arms/hands" loop for filling a vial at a well — same
interaction style as FemaleCarving / Manufacturing (legs stay idle;
only arms, forearms, hands, and fingers animate).

Clip:
  FemaleWellFill — 2.0 s seamless loop

Storyboard
----------
t=0.00  Rest / idle arms.
t=0.25  Settled at the well: left hand holds the vial at rim height,
        right hand reaches the well mouth (ready to dip / guide water).
t=0.25–1.75
        Busy dip cycle (×2): right arm/forearm dips into the well,
        lifts, and tips toward the vial while the left hand steadies it.
        Small finger flex on the vial grip so the hands read as active.
t=1.75  Still in work pose.
t=2.00  Back to rest (seamless loop bookend).

Run:
    python3 generate_female_well_fill.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

# ----------------------------------------------------------------------
# Quaternion helpers (JSON order is [x, y, z, w])
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Rest pose (shared with FemaleIdle / Carving / Forging)
# ----------------------------------------------------------------------

REST_RIGHT_ARM: Quat = (0.60838, 0.02168, -0.01819, 0.79314)
REST_LEFT_ARM: Quat = (0.60838, -0.02168, 0.01819, 0.79314)
REST_RIGHT_FOREARM: Quat = (0.0, 0.0, 0.17365, 0.98481)
REST_LEFT_FOREARM: Quat = (0.0, 0.0, -0.17365, 0.98481)

# Idle finger curl.
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

# Tighter vial / dip grip.
VIAL_FINGERS: Dict[str, Quat] = {
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

# Slightly tighter squeeze mid-dip (reads as adjusting the vial).
VIAL_SQUEEZE: Dict[str, Quat] = {
    "Thumb1": (0.15643, -0.10000, -0.01500, 0.98250),
    "Thumb2": (0.21644, 0.0, 0.0, 0.97630),
    "Thumb3": (0.17365, 0.0, 0.0, 0.98481),
    "Index1": (0.42262, 0.0, 0.0, 0.90631),
    "Index2": (0.57358, 0.0, 0.0, 0.81915),
    "Index3": (0.38268, 0.0, 0.0, 0.92388),
    "Middle1": (0.45399, 0.0, 0.0, 0.89101),
    "Middle2": (0.60876, 0.0, 0.0, 0.79335),
    "Middle3": (0.42262, 0.0, 0.0, 0.90631),
    "Ring1": (0.45399, 0.0, 0.0, 0.89101),
    "Ring2": (0.60876, 0.0, 0.0, 0.79335),
    "Ring3": (0.42262, 0.0, 0.0, 0.90631),
    "Pinky1": (0.38268, 0.0, 0.0, 0.92388),
    "Pinky2": (0.53730, 0.0, 0.0, 0.84339),
    "Pinky3": (0.34202, 0.0, 0.0, 0.93969),
}


# ----------------------------------------------------------------------
# Work poses — hands close together in front; soft body/head follow
# ----------------------------------------------------------------------

# Left: vial held near centerline, mid-chest / well-rim height.
HOLD_LEFT_ARM = quat_norm(
    quat_mul(REST_LEFT_ARM, quat_mul(rx(-28.0), quat_mul(ry(-6.0), rz(18.0))))
)
HOLD_LEFT_FOREARM = quat_norm(quat_mul(REST_LEFT_FOREARM, rz(72.0)))
HOLD_LEFT_HAND = quat_norm(quat_mul(ry(6.0), rx(10.0)))

# Right: tucked in beside the vial (hands nearly meet in front).
READY_RIGHT_ARM = quat_norm(
    quat_mul(REST_RIGHT_ARM, quat_mul(rx(-24.0), quat_mul(ry(8.0), rz(-16.0))))
)
READY_RIGHT_FOREARM = quat_norm(quat_mul(REST_RIGHT_FOREARM, rz(-78.0)))
READY_RIGHT_HAND = quat_norm(ry(-10.0))

# Right: short dip toward the well mouth (still centered, not wide).
DIP_RIGHT_ARM = quat_norm(
    quat_mul(REST_RIGHT_ARM, quat_mul(rx(-6.0), quat_mul(ry(12.0), rz(-20.0))))
)
DIP_RIGHT_FOREARM = quat_norm(quat_mul(REST_RIGHT_FOREARM, rz(-102.0)))
DIP_RIGHT_HAND = quat_norm(quat_mul(ry(-14.0), rx(12.0)))

# Right: lift + tip into the vial (hands stay close).
LIFT_RIGHT_ARM = quat_norm(
    quat_mul(REST_RIGHT_ARM, quat_mul(rx(-34.0), quat_mul(ry(4.0), rz(-12.0))))
)
LIFT_RIGHT_FOREARM = quat_norm(quat_mul(REST_RIGHT_FOREARM, rz(-58.0)))
LIFT_RIGHT_HAND = quat_norm(quat_mul(ry(-6.0), rx(-12.0)))

# Left: tiny receive bob (stays close to right hand).
BOB_LEFT_ARM = quat_norm(quat_mul(HOLD_LEFT_ARM, rx(5.0)))
BOB_LEFT_FOREARM = quat_norm(quat_mul(HOLD_LEFT_FOREARM, rz(5.0)))

# Body / head — IDENT at rest; deltas are Mixamo +X = forward lean.
# Work lean: slight bow over the well.
LEAN_SPINE = rx(10.0)
LEAN_SPINE1 = rx(7.0)
LEAN_SPINE2 = rx(4.0)
LEAN_NECK = rx(6.0)
LEAN_HEAD = rx(4.0)

# Dip: deeper bow, glance into the well.
DIP_SPINE = rx(16.0)
DIP_SPINE1 = rx(11.0)
DIP_SPINE2 = rx(7.0)
DIP_NECK = rx(12.0)
DIP_HEAD = quat_mul(rx(10.0), ry(-4.0))

# Lift / tip: open up a touch, glance at the vial.
LIFT_SPINE = rx(7.0)
LIFT_SPINE1 = rx(5.0)
LIFT_SPINE2 = rx(3.0)
LIFT_NECK = rx(2.0)
LIFT_HEAD = quat_mul(rx(2.0), ry(5.0))

FPS = 30
DURATION = 2.0
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


def const_rot(bone: str, q: Quat, t0: float, t1: float) -> Dict:
    return rotation_track(bone, [(t0, q), (t1, q)])


def finger_tracks(side: str, pose: Dict[str, Quat], t0: float, t1: float) -> List[Dict]:
    return [
        const_rot(f"mixamorig{side}Hand{finger}", q, t0, t1)
        for finger, q in pose.items()
    ]


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
# Clip
# ----------------------------------------------------------------------

def build_well_fill() -> Dict:
    """Standing busy-hands vial fill at a well (Manufacturing-style)."""
    duration = DURATION
    t_in = 0.25
    t_out = 1.75

    # Two dip cycles across the busy window.
    # Each cycle: ready → dip → lift → ready
    cycle = (t_out - t_in) / 2.0
    busy_times: List[float] = []
    right_arm: List[Quat] = []
    right_fore: List[Quat] = []
    right_hand: List[Quat] = []
    left_arm: List[Quat] = []
    left_fore: List[Quat] = []
    finger_prog: List[Tuple[float, float]] = []
    spine_ks: List[Quat] = []
    spine1_ks: List[Quat] = []
    spine2_ks: List[Quat] = []
    neck_ks: List[Quat] = []
    head_ks: List[Quat] = []

    for i in range(2):
        base = t_in + i * cycle
        keys = [
            (
                base,
                READY_RIGHT_ARM,
                READY_RIGHT_FOREARM,
                READY_RIGHT_HAND,
                HOLD_LEFT_ARM,
                HOLD_LEFT_FOREARM,
                0.0,
                LEAN_SPINE,
                LEAN_SPINE1,
                LEAN_SPINE2,
                LEAN_NECK,
                LEAN_HEAD,
            ),
            (
                base + cycle * 0.28,
                DIP_RIGHT_ARM,
                DIP_RIGHT_FOREARM,
                DIP_RIGHT_HAND,
                BOB_LEFT_ARM,
                BOB_LEFT_FOREARM,
                1.0,
                DIP_SPINE,
                DIP_SPINE1,
                DIP_SPINE2,
                DIP_NECK,
                DIP_HEAD,
            ),
            (
                base + cycle * 0.55,
                LIFT_RIGHT_ARM,
                LIFT_RIGHT_FOREARM,
                LIFT_RIGHT_HAND,
                HOLD_LEFT_ARM,
                HOLD_LEFT_FOREARM,
                0.35,
                LIFT_SPINE,
                LIFT_SPINE1,
                LIFT_SPINE2,
                LIFT_NECK,
                LIFT_HEAD,
            ),
            (
                base + cycle * 0.82,
                READY_RIGHT_ARM,
                READY_RIGHT_FOREARM,
                READY_RIGHT_HAND,
                HOLD_LEFT_ARM,
                HOLD_LEFT_FOREARM,
                0.0,
                LEAN_SPINE,
                LEAN_SPINE1,
                LEAN_SPINE2,
                LEAN_NECK,
                LEAN_HEAD,
            ),
        ]
        # Avoid duplicating the shared boundary between cycles.
        start = 0 if i == 0 else 1
        for t, ra, rf, rh, la, lf, fp, sp, sp1, sp2, nk, hd in keys[start:]:
            busy_times.append(t)
            right_arm.append(ra)
            right_fore.append(rf)
            right_hand.append(rh)
            left_arm.append(la)
            left_fore.append(lf)
            finger_prog.append((t, fp))
            spine_ks.append(sp)
            spine1_ks.append(sp1)
            spine2_ks.append(sp2)
            neck_ks.append(nk)
            head_ks.append(hd)

    # Ensure we end the busy window on the ready/hold pose.
    if abs(busy_times[-1] - t_out) > 1e-4:
        busy_times.append(t_out)
        right_arm.append(READY_RIGHT_ARM)
        right_fore.append(READY_RIGHT_FOREARM)
        right_hand.append(READY_RIGHT_HAND)
        left_arm.append(HOLD_LEFT_ARM)
        left_fore.append(HOLD_LEFT_FOREARM)
        finger_prog.append((t_out, 0.0))
        spine_ks.append(LEAN_SPINE)
        spine1_ks.append(LEAN_SPINE1)
        spine2_ks.append(LEAN_SPINE2)
        neck_ks.append(LEAN_NECK)
        head_ks.append(LEAN_HEAD)

    # Drop the opening ready key — we already key t_in separately.
    if busy_times and abs(busy_times[0] - t_in) < 1e-6:
        busy_times = busy_times[1:]
        right_arm = right_arm[1:]
        right_fore = right_fore[1:]
        right_hand = right_hand[1:]
        left_arm = left_arm[1:]
        left_fore = left_fore[1:]
        finger_prog = finger_prog[1:]
        spine_ks = spine_ks[1:]
        spine1_ks = spine1_ks[1:]
        spine2_ks = spine2_ks[1:]
        neck_ks = neck_ks[1:]
        head_ks = head_ks[1:]

    tracks: List[Dict] = []

    # Soft torso / head follow so the fill reads flowy, not stiff-armed.
    tracks.append(
        rotation_track(
            "mixamorigSpine",
            [
                (0.0, IDENT),
                (t_in, LEAN_SPINE),
                *[(t, q) for t, q in zip(busy_times, spine_ks)],
                (duration, IDENT),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigSpine1",
            [
                (0.0, IDENT),
                (t_in, LEAN_SPINE1),
                *[(t, q) for t, q in zip(busy_times, spine1_ks)],
                (duration, IDENT),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigSpine2",
            [
                (0.0, IDENT),
                (t_in, LEAN_SPINE2),
                *[(t, q) for t, q in zip(busy_times, spine2_ks)],
                (duration, IDENT),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigNeck",
            [
                (0.0, IDENT),
                (t_in, LEAN_NECK),
                *[(t, q) for t, q in zip(busy_times, neck_ks)],
                (duration, IDENT),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigHead",
            [
                (0.0, IDENT),
                (t_in, LEAN_HEAD),
                *[(t, q) for t, q in zip(busy_times, head_ks)],
                (duration, IDENT),
            ],
        )
    )

    # Left arm — settle to vial hold, gentle bob during dips, return to rest.
    tracks.append(
        rotation_track(
            "mixamorigLeftArm",
            [
                (0.0, REST_LEFT_ARM),
                (t_in, HOLD_LEFT_ARM),
                *[(t, q) for t, q in zip(busy_times, left_arm)],
                (duration, REST_LEFT_ARM),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigLeftForeArm",
            [
                (0.0, REST_LEFT_FOREARM),
                (t_in, HOLD_LEFT_FOREARM),
                *[(t, q) for t, q in zip(busy_times, left_fore)],
                (duration, REST_LEFT_FOREARM),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigLeftHand",
            [
                (0.0, IDENT),
                (t_in, HOLD_LEFT_HAND),
                (t_out, HOLD_LEFT_HAND),
                (duration, IDENT),
            ],
        )
    )

    # Right arm — busy dip / lift / tip toward the vial.
    tracks.append(
        rotation_track(
            "mixamorigRightArm",
            [
                (0.0, REST_RIGHT_ARM),
                (t_in, READY_RIGHT_ARM),
                *[(t, q) for t, q in zip(busy_times, right_arm)],
                (duration, REST_RIGHT_ARM),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigRightForeArm",
            [
                (0.0, REST_RIGHT_FOREARM),
                (t_in, READY_RIGHT_FOREARM),
                *[(t, q) for t, q in zip(busy_times, right_fore)],
                (duration, REST_RIGHT_FOREARM),
            ],
        )
    )
    tracks.append(
        rotation_track(
            "mixamorigRightHand",
            [
                (0.0, IDENT),
                (t_in, READY_RIGHT_HAND),
                *[(t, q) for t, q in zip(busy_times, right_hand)],
                (duration, IDENT),
            ],
        )
    )

    # Left fingers: idle → vial grip while working → idle.
    for finger, idle_q in IDLE_FINGERS.items():
        vial_q = VIAL_FINGERS[finger]
        tracks.append(
            rotation_track(
                f"mixamorigLeftHand{finger}",
                [
                    (0.0, idle_q),
                    (t_in, vial_q),
                    (t_out, vial_q),
                    (duration, idle_q),
                ],
            )
        )

    # Right fingers: vial grip with squeeze pulses on each dip.
    for finger, idle_q in IDLE_FINGERS.items():
        grip = VIAL_FINGERS[finger]
        squeeze = VIAL_SQUEEZE[finger]
        kfs: List[Tuple[float, Quat]] = [
            (0.0, idle_q),
            (t_in, grip),
        ]
        for t, p in finger_prog:
            kfs.append((t, slerp(grip, squeeze, p)))
        kfs.append((duration, idle_q))
        tracks.append(rotation_track(f"mixamorigRightHand{finger}", kfs))

    return {
        "meta": {
            "name": "FemaleWellFill",
            "id": "FemaleWellFill",
            "duration": duration,
            "fps": FPS,
            "loop": True,
        },
        "tracks": tracks,
    }


def main() -> None:
    write_spec(build_well_fill(), "FemaleWellFill.anim.json")
    print("Done. Play: FemaleWellFill (loop) while interacting with a well.")


if __name__ == "__main__":
    main()
