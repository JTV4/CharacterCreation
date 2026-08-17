#!/usr/bin/env python3
"""
generate_female_death.py
========================

Generates `viewer/public/animations/FemaleDeath.anim.json` — a one-shot
"forward collapse to knees" death animation for the BaseFemaleV2 (Mixamo-
rigged) character.

Storyboard (purely rotational — no world-space translation guesses):

    t=0.00 (frame  0):  Standing rest pose.
    t=0.10 (frame  3):  Brief hit-reaction. Body recoils slightly, head jerks.
    t=0.30 (frame  9):  Knees soften, head bows, arms go slack.
    t=0.65 (frame 20):  Stagger — torso tipping forward, knees folding,
                        hips beginning to tilt.
    t=1.00 (frame 30):  Deep slump — torso bent ~60°, knees ~90°.
    t=1.30 (frame 39):  Heels meet ground; final kneeling slump with body
                        bowed over the legs.
    t=1.50 (frame 45):  Tiny breath-out settle on the final pose.

The arms/forearms/head end on the exact Blender-Euler targets supplied
by the user (see TARGET_* constants), interpolated from rest via slerp.

Run:
    python3 generate_female_death.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

# ----------------------------------------------------------------------
# Quaternion helpers (JSON order is [x, y, z, w])
# ----------------------------------------------------------------------

Quat = Tuple[float, float, float, float]


def quat_axis_angle(axis: Tuple[float, float, float], angle_rad: float) -> Quat:
    ax, ay, az = axis
    length = math.sqrt(ax * ax + ay * ay + az * az)
    if length == 0:
        return (0.0, 0.0, 0.0, 1.0)
    ax, ay, az = ax / length, ay / length, az / length
    s = math.sin(angle_rad * 0.5)
    c = math.cos(angle_rad * 0.5)
    return (ax * s, ay * s, az * s, c)


def quat_mul(a: Quat, b: Quat) -> Quat:
    """Hamilton product: result = a * b."""
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
        return (0.0, 0.0, 0.0, 1.0)
    return (x / n, y / n, z / n, w / n)


def rx(deg: float) -> Quat:
    return quat_axis_angle((1.0, 0.0, 0.0), math.radians(deg))


def ry(deg: float) -> Quat:
    return quat_axis_angle((0.0, 1.0, 0.0), math.radians(deg))


def rz(deg: float) -> Quat:
    return quat_axis_angle((0.0, 0.0, 1.0), math.radians(deg))


def euler_xyz_deg(x_deg: float, y_deg: float, z_deg: float) -> Quat:
    """Convert Blender pose-bone Euler 'XYZ' (degrees) to quaternion.

    Matches Blender's `mathutils.Euler((x, y, z), 'XYZ').to_quaternion()`:
    q = qx * qy * qz   (intrinsic XYZ Hamilton product).
    """
    qx = quat_axis_angle((1.0, 0.0, 0.0), math.radians(x_deg))
    qy = quat_axis_angle((0.0, 1.0, 0.0), math.radians(y_deg))
    qz = quat_axis_angle((0.0, 0.0, 1.0), math.radians(z_deg))
    return quat_mul(quat_mul(qx, qy), qz)


def slerp(q0: Quat, q1: Quat, t: float) -> Quat:
    """Spherical linear interpolation between two unit quaternions."""
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


IDENT: Quat = (0.0, 0.0, 0.0, 1.0)


# ----------------------------------------------------------------------
# Rest-pose constants (copied verbatim from the other Female animations
# in this project — these offsets put the T-pose-authored mesh into the
# canonical "arms down, slight finger curl" idle pose).
# ----------------------------------------------------------------------

REST_SHOULDER: Quat = (-0.02618, 0.0, 0.0, 0.99966)        # both sides
REST_RIGHT_ARM: Quat = (0.60838,  0.02168, -0.01819, 0.79314)
REST_LEFT_ARM:  Quat = (0.60838, -0.02168,  0.01819, 0.79314)
REST_RIGHT_FOREARM: Quat = (0.0, 0.0,  0.17365, 0.98481)
REST_LEFT_FOREARM:  Quat = (0.0, 0.0, -0.17365, 0.98481)

# Finger curls (identical on left and right; from FemaleKick).
FINGER_REST: Dict[str, Quat] = {
    "Thumb1":  (0.08716, 0.0, 0.0, 0.99619),
    "Thumb2":  (0.13053, 0.0, 0.0, 0.99144),
    "Thumb3":  (0.08716, 0.0, 0.0, 0.99619),
    "Index1":  (0.15643, 0.0, 0.0, 0.98769),
    "Index2":  (0.24192, 0.0, 0.0, 0.97030),
    "Index3":  (0.15643, 0.0, 0.0, 0.98769),
    "Middle1": (0.17365, 0.0, 0.0, 0.98481),
    "Middle2": (0.25882, 0.0, 0.0, 0.96593),
    "Middle3": (0.17365, 0.0, 0.0, 0.98481),
    "Ring1":   (0.19081, 0.0, 0.0, 0.98163),
    "Ring2":   (0.28402, 0.0, 0.0, 0.95882),
    "Ring3":   (0.19081, 0.0, 0.0, 0.98163),
    "Pinky1":  (0.21644, 0.0, 0.0, 0.97630),
    "Pinky2":  (0.30071, 0.0, 0.0, 0.95372),
    "Pinky3":  (0.21644, 0.0, 0.0, 0.97630),
}


# ----------------------------------------------------------------------
# Final-pose targets for arms / forearms / head, supplied by the user
# as Blender pose-bone Euler 'XYZ' rotations (degrees).
# These are the *absolute* local-pose values the bones should hold at
# the end of the animation; we slerp from rest into each of them.
# ----------------------------------------------------------------------

TARGET_RIGHT_ARM:     Quat = euler_xyz_deg(-107.0,  87.0, 0.0)
TARGET_LEFT_ARM:      Quat = euler_xyz_deg(-107.0, -87.0, 0.0)
TARGET_RIGHT_FOREARM: Quat = euler_xyz_deg(  -5.0,   0.0, 0.0)
TARGET_LEFT_FOREARM:  Quat = euler_xyz_deg(   5.0,   0.0, 0.0)
TARGET_HEAD:          Quat = euler_xyz_deg(   6.0,   0.0, 0.0)

# Hips final pose (Blender pose-bone N-panel values from the user).
# Rotation is pure-X, so we still drive it through HIPS_X below.
# Position is a delta from the bone's rest position, applied by the
# viewer as `restPos + value`. Existing animations use the same units
# (FemaleFireStarting / FemaleFarming reach ~45-50 on this axis).
TARGET_HIPS_POS: Tuple[float, float, float] = (0.0, 0.0, 55.0)
TARGET_HIPS_X_DEG: float = 57.0


# ----------------------------------------------------------------------
# Storyboard keyframe times (seconds)
#
# Times scaled by 1/2.5 from the previous 0.75 s pacing.  Total
# duration is now 0.30 s (9 frames at 30 fps) — a near-instant
# collapse.
# ----------------------------------------------------------------------

T0   = 0.000  # standing
T1   = 0.020  # hit reaction
T2   = 0.060  # body starts to slump / arms start to swing
T3   = 0.130  # stagger forward
T4   = 0.200  # deep slump
T5   = 0.260  # final pose almost reached
T6   = 0.300  # settle on the user-supplied end pose

DURATION = T6
FPS = 30


# ----------------------------------------------------------------------
# Bend angles (degrees) at each storyboard time.
#
# Convention (matches FemaleKick's data):
#   Spine / UpLeg / Hips / Head:  +X rotation = forward bend / forward kick
#   Leg (shin):                   -X rotation = knee folds backward
# ----------------------------------------------------------------------

# Spine chain: total forward bend distributed over Hips + Spine + Spine1 + Spine2.
# Neck and Head bow the head forward separately.
#
# At T5 the cumulative forward bend should be ~110° so the torso lies
# along the thighs (face roughly above the knees).
#
# Format: angle_deg per bone at each (T1..T6) keyframe.

# Hips forward bend ends at the user-supplied 57° target.  Intermediate
# values are scaled to that end, with a small back-recoil at T1.
HIPS_X = {T0: 0.0, T1: -3.0, T2:  6.0, T3: 20.0, T4: 40.0, T5: 54.0, T6: TARGET_HIPS_X_DEG}
SPINE_X = {T0: 0.0, T1: -5.0, T2:  3.0, T3: 12.0, T4: 22.0, T5: 28.0, T6: 28.0}
SPINE1_X = {T0: 0.0, T1: -2.0, T2:  4.0, T3: 12.0, T4: 22.0, T5: 28.0, T6: 28.0}
SPINE2_X = {T0: 0.0, T1:  0.0, T2:  3.0, T3:  8.0, T4: 14.0, T5: 18.0, T6: 18.0}
NECK_X = {T0: 0.0, T1: -8.0, T2:  6.0, T3: 14.0, T4: 22.0, T5: 28.0, T6: 28.0}
# Head ends at the user-supplied target of +6° X (Euler), so the head
# stays mostly in line with the slumped spine rather than chin-tucking.
# A small back-jerk at T1 keeps the impact reaction.
HEAD_X = {T0: 0.0, T1: -8.0, T2: -2.0, T3:  1.0, T4:  3.5, T5:  5.5, T6:  6.0}

# Legs (kneeling collapse).
UPLEG_X = {T0: 0.0, T1: 0.0, T2:  8.0, T3: 25.0, T4: 45.0, T5: 55.0, T6: 55.0}
LEG_X   = {T0: 0.0, T1: 0.0, T2: -12.0, T3: -45.0, T4: -90.0, T5: -110.0, T6: -110.0}
# Feet: as the shin folds back, foot rotates so toes stay near the ground.
FOOT_X  = {T0: 0.0, T1: 0.0, T2:  5.0, T3: 20.0, T4: 40.0, T5: 50.0, T6: 50.0}


# ----------------------------------------------------------------------
# Track builders
# ----------------------------------------------------------------------

def _rounded(q: Quat, digits: int = 5) -> List[float]:
    return [round(v, digits) for v in q]


def make_keyframe(time_s: float, value: Quat) -> Dict:
    return {"time": round(time_s, 5), "value": _rounded(value)}


def rotation_track(bone: str, kfs: List[Tuple[float, Quat]]) -> Dict:
    return {
        "bone": bone,
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": [make_keyframe(t, quat_norm(q)) for t, q in kfs],
    }


def position_track(bone: str, kfs: List[Tuple[float, Tuple[float, float, float]]]) -> Dict:
    return {
        "bone": bone,
        "property": "position",
        "interpolation": "linear",
        "keyframes": [
            {"time": round(t, 5), "value": [round(v, 5) for v in xyz]}
            for t, xyz in kfs
        ],
    }


def _x_curve_track(bone: str, angle_map: Dict[float, float]) -> Dict:
    times = sorted(angle_map.keys())
    return rotation_track(bone, [(t, rx(angle_map[t])) for t in times])


def _const_track(bone: str, q: Quat) -> Dict:
    return rotation_track(bone, [(T0, q), (DURATION, q)])


# Arm relaxation: shoulders droop slightly forward as the body collapses.
# We do this by post-composing a small +X rotation on top of the rest pose.
def _shoulder_track(bone: str) -> Dict:
    kfs: List[Tuple[float, Quat]] = []
    droop_map = {T0: 0.0, T1: -2.0, T2: 3.0, T3: 6.0, T4: 9.0, T5: 11.0, T6: 11.0}
    for t in sorted(droop_map.keys()):
        kfs.append((t, quat_mul(REST_SHOULDER, rx(droop_map[t]))))
    return rotation_track(bone, kfs)


# Per-keyframe progress (0 = full rest, 1 = full target) shared by arms,
# forearms, and any other "slerp from rest to user target" tracks. Arms
# stay close to rest during the hit reaction (T0/T1) so the recoil reads,
# then ease into the target pose as the body slumps.
SLERP_PROGRESS: Dict[float, float] = {
    T0: 0.00,
    T1: 0.00,
    T2: 0.10,
    T3: 0.35,
    T4: 0.70,
    T5: 0.95,
    T6: 1.00,
}


def _slerp_track(bone: str, rest_q: Quat, target_q: Quat) -> Dict:
    """Build a rotation track that slerps from rest_q to target_q along
    the SLERP_PROGRESS curve, so the bone ends exactly on the target."""
    kfs: List[Tuple[float, Quat]] = []
    for t in sorted(SLERP_PROGRESS.keys()):
        kfs.append((t, slerp(rest_q, target_q, SLERP_PROGRESS[t])))
    return rotation_track(bone, kfs)


def _eased_position_track(
    bone: str,
    start: Tuple[float, float, float],
    end: Tuple[float, float, float],
) -> Dict:
    """Linear position track that eases from `start` to `end` along the
    same SLERP_PROGRESS curve used by the arms.  This keeps every "final
    pose" element arriving on T6 together, so the hips drop in sync with
    the arm swing and torso slump."""
    kfs: List[Tuple[float, Tuple[float, float, float]]] = []
    for t in sorted(SLERP_PROGRESS.keys()):
        p = SLERP_PROGRESS[t]
        pos = (
            start[0] + (end[0] - start[0]) * p,
            start[1] + (end[1] - start[1]) * p,
            start[2] + (end[2] - start[2]) * p,
        )
        kfs.append((t, pos))
    return position_track(bone, kfs)


def _finger_tracks(side: str) -> List[Dict]:
    tracks: List[Dict] = []
    for finger, rest_q in FINGER_REST.items():
        bone = f"mixamorig{side}Hand{finger}"
        tracks.append(_const_track(bone, rest_q))
    return tracks


# ----------------------------------------------------------------------
# Assemble the full spec
# ----------------------------------------------------------------------

def build_spec() -> Dict:
    tracks: List[Dict] = []

    # Hips position eases from rest into the user-supplied [0, 0, 55]
    # final pose, which is what grounds the character at the end of the
    # collapse (without this the body bends but the hips stay at full
    # standing height and the character looks like it's floating).
    tracks.append(_eased_position_track("mixamorigHips", (0.0, 0.0, 0.0), TARGET_HIPS_POS))

    # Spine chain forward bend.
    tracks.append(_x_curve_track("mixamorigHips", HIPS_X))
    tracks.append(_x_curve_track("mixamorigSpine", SPINE_X))
    tracks.append(_x_curve_track("mixamorigSpine1", SPINE1_X))
    tracks.append(_x_curve_track("mixamorigSpine2", SPINE2_X))
    tracks.append(_x_curve_track("mixamorigNeck", NECK_X))
    tracks.append(_x_curve_track("mixamorigHead", HEAD_X))

    # Legs: both sides collapse together.
    for side in ("Left", "Right"):
        tracks.append(_x_curve_track(f"mixamorig{side}UpLeg", UPLEG_X))
        tracks.append(_x_curve_track(f"mixamorig{side}Leg", LEG_X))
        tracks.append(_x_curve_track(f"mixamorig{side}Foot", FOOT_X))

    # Shoulders keep their rest offsets, with a slight slump.
    tracks.append(_shoulder_track("mixamorigLeftShoulder"))
    tracks.append(_shoulder_track("mixamorigRightShoulder"))

    # Arms and forearms slerp from rest into the user-supplied final pose.
    tracks.append(_slerp_track("mixamorigLeftArm",      REST_LEFT_ARM,      TARGET_LEFT_ARM))
    tracks.append(_slerp_track("mixamorigRightArm",     REST_RIGHT_ARM,     TARGET_RIGHT_ARM))
    tracks.append(_slerp_track("mixamorigLeftForeArm",  REST_LEFT_FOREARM,  TARGET_LEFT_FOREARM))
    tracks.append(_slerp_track("mixamorigRightForeArm", REST_RIGHT_FOREARM, TARGET_RIGHT_FOREARM))

    # Hands at neutral; fingers preserve their resting curl values throughout.
    tracks.append(_const_track("mixamorigLeftHand", IDENT))
    tracks.append(_const_track("mixamorigRightHand", IDENT))
    tracks.extend(_finger_tracks("Left"))
    tracks.extend(_finger_tracks("Right"))

    return {
        "meta": {
            "name": "FemaleDeath",
            "id": "FemaleDeath",
            "duration": DURATION,
            "fps": FPS,
            "loop": False,
        },
        "tracks": tracks,
    }


# ----------------------------------------------------------------------
# Sanity validation (mirrors animations/factory/anim_validation.py)
# ----------------------------------------------------------------------

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


def main() -> None:
    spec = build_spec()
    _validate(spec)

    out_path = Path(__file__).resolve().parent / "viewer/public/animations/FemaleDeath.anim.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(spec, indent=2))

    print(f"Wrote {out_path}")
    print(f"  tracks: {len(spec['tracks'])}")
    print(f"  duration: {DURATION:.2f}s @ {FPS} fps -> {int(DURATION * FPS)} frames")
    print(f"  loop: {spec['meta']['loop']}")


if __name__ == "__main__":
    main()
