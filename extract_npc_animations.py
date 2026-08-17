"""
extract_npc_animations.py
=========================
Generates the NPC animation pack for the viewer:

  viewer/public/animations/NPCIdle.anim.json   (shared, delta mode)
  viewer/public/animations/NPCWalk.anim.json   (shared, delta mode)

Both clips are SHARED across every Meshy-rig NPC.  This works because the
clips are emitted in delta mode (`meta.absolute = false`), where each
keyframe value is a rotation/translation OFFSET from the bone's rest pose.
The player composes `character_rest * delta` at runtime, so the same delta
plays correctly on every character with the same skeleton convention,
regardless of small per-character variations in rest pose.

Source of truth:
  HopperWhiteFemale.glb's embedded "Walking" animation.  Every NPC in
  the roster (8 names x 4 variants = 32 characters) shares the same
  24-joint Meshy skeleton, so a single clip authored against Hopper's
  skeleton generalises to all of them in delta mode.

Walk authoring decisions (driven by user feedback "walk drags top of
character down" and "walk is a bit funky"):
  - Hips Y bob is recentered: source has the bob's MEAN sitting ~3 cm
    below rest height (character spends most of the cycle squatting).
    We subtract the mean so the bob oscillates around rest instead.
  - Hips Y bob amplitude scaled to HIPS_BOB_AMPLITUDE_SCALE of source.
  - Every rotation delta's angle scaled by WALK_ROT_AMPLITUDE_SCALE.
    The source authoring has stiff/exaggerated spine and arm swings;
    softening the angle around the same axis tames that without
    changing motion direction.
  - Timeline stretched by WALK_DURATION_SCALE.  Source pace (1.0s for a
    full 2-step cycle) is right at the upper edge of natural walking;
    a slight stretch gives a more deliberate stride.
  - Hips X/Z deltas are zeroed so the cycle plays in place.
  - Non-Hips position tracks are dropped — bone offsets are skeleton
    geometry, not animation.
  - Per-bone overrides (`WALK_BONE_OVERRIDES`) clamp specific bones to
    a fixed pose for the whole cycle.  Driven by user pose values: the
    spine + hips collapse to rest (no twist or bob), and the upper
    arms hold a static "close to the side" pose so the legs do all
    the visible work of the walk.  Override values are interpreted as
    Blender pose-mode Euler XYZ deltas, matching the N-panel display.

Idle authoring decisions (driven by user feedback "still looks too
still"):
  - Arm-bone constant deltas pulled from Hopper's walk-frame-0 (rotates
    arms from T-pose to the side).
  - 6-second breath/sway loop layering two rhythms:
      * Breath:  Spine/Spine01/Spine02/neck rock forward on exhale,
                 Hips Y drops ~0.8 cm.
      * Sway:    Hips rotate ±2° around Y (with a hint of Z lateral
                 drop) to suggest weight shifting between feet, while
                 Head adds five-keyframe yaw glance + slight nod.
    The sway is what reads at distance; the breath fills in the
    in-between beats so the rig is never purely static.

Run:
  python3 extract_npc_animations.py
"""

import json
import math
import os
import struct
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
ANIM_DIR  = os.path.join(REPO_ROOT, "viewer/public/animations")
NPC_DIR   = os.path.join(REPO_ROOT, "viewer/public/NPCs")

WALK_SOURCE_GLB  = os.path.join(NPC_DIR, "WhiteFemale", "HopperWhiteFemale.glb")
WALK_SOURCE_NAME = "Walking"

OUT_IDLE = os.path.join(ANIM_DIR, "NPCIdle.anim.json")
OUT_WALK = os.path.join(ANIM_DIR, "NPCWalk.anim.json")

# Bones whose rest pose has the limb in a near-T-pose orientation.  The
# Idle clip emits a constant rotation delta on these so the arms drop to
# the sides; everything else gets only the breathing motion.
ARM_BONES = {
    "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
    "RightShoulder", "RightArm", "RightForeArm", "RightHand",
}

# ---- Walk shaping knobs ----
# Source authored amplitude is heavy and slightly stiff; pulling the
# whole cycle back gives a more natural saunter that reads better on
# both Finn and Hopper.
HIPS_BOB_AMPLITUDE_SCALE = 0.4   # 1.0 = source amplitude
WALK_ROT_AMPLITUDE_SCALE = 0.75  # scale every rotation delta's angle
WALK_DURATION_SCALE      = 1.4   # 1.0 = source timing (1.0s); >1 = slower

# ---- Walk per-bone overrides ----
# Each entry is applied AFTER the source-derived delta tracks are built.
#   - "rotation_deg":  Blender-style intrinsic Euler XYZ in degrees,
#                      interpreted as a delta from rest (matches what
#                      pose-mode shows in the N-panel).  [0,0,0] drops
#                      the rotation track entirely (delta = identity =
#                      rest pose at runtime).  Anything else replaces
#                      the track with a constant 2-keyframe track that
#                      pins the bone to that pose for the whole cycle.
#   - "position":      Same idea for translation deltas.
#
# LeftArm Y/Z are sign-flipped from RightArm to produce the mirror
# pose; the user-specified X is 44 vs 40.  If the rig's bone frame is
# already mirrored (so identical numbers give a symmetric pose), flip
# the Y/Z signs back to match RightArm exactly.
WALK_BONE_OVERRIDES = {
    "Hips":     {"rotation_deg": [ 0.0,    0.0,     0.0   ],
                 "position":     [ 0.0,    0.0,     0.0   ]},
    "Spine01":  {"rotation_deg": [ 0.0,    0.0,     0.0   ]},
    "Spine02":  {"rotation_deg": [ 0.0,    0.0,     0.0   ]},
    "RightArm": {"rotation_deg": [40.0,  -17.266, -14.882]},
    "LeftArm":  {"rotation_deg": [44.0,  +17.266, +14.882]},
}

# ---- Idle shaping knobs ----
IDLE_DURATION = 6.0  # seconds for one full breath loop


# ---------------------------------------------------------------------------
# GLB I/O
# ---------------------------------------------------------------------------

def parse_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"glTF":
        raise ValueError(f"{path} is not a glTF binary")
    json_len = struct.unpack("<I", data[12:16])[0]
    json_chunk = json.loads(data[20:20 + json_len].decode("utf-8"))
    bin_chunk_offset = 20 + json_len + 8
    return json_chunk, data[bin_chunk_offset:]


def read_accessor(j, b, idx):
    acc = j["accessors"][idx]
    bv = j["bufferViews"][acc["bufferView"]]
    offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    count = acc["count"]
    type_count = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[acc["type"]]
    if acc["componentType"] != 5126:
        raise ValueError(f"unsupported componentType {acc['componentType']}")
    n = count * type_count
    raw = b[offset:offset + n * 4]
    vals = struct.unpack(f"<{n}f", raw)
    return [list(vals[i:i + type_count]) for i in range(0, n, type_count)]


def get_bone_rest(j, name, kind):
    default = [0, 0, 0, 1] if kind == "rotation" else [0, 0, 0]
    for n in j["nodes"]:
        if n.get("name") == name:
            return list(n.get(kind, default))
    return default


# ---------------------------------------------------------------------------
# Quaternion math (unit quaternions, [x, y, z, w])
# ---------------------------------------------------------------------------

def quat_conjugate(q):
    return [-q[0], -q[1], -q[2], q[3]]


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    ]


def quat_normalize(q):
    n = math.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + q[3] ** 2)
    if n < 1e-12:
        return [0.0, 0.0, 0.0, 1.0]
    return [q[0] / n, q[1] / n, q[2] / n, q[3] / n]


def quat_from_axis_angle_deg(axis, deg):
    half = math.radians(deg) * 0.5
    s = math.sin(half)
    return [axis[0] * s, axis[1] * s, axis[2] * s, math.cos(half)]


def quat_from_euler_xyz_deg(deg_xyz):
    """Blender / Three.js intrinsic XYZ Euler to quaternion.
    Equivalent to qX * qY * qZ.  Input is degrees."""
    rx, ry, rz = (math.radians(d) for d in deg_xyz)
    c1, s1 = math.cos(rx * 0.5), math.sin(rx * 0.5)
    c2, s2 = math.cos(ry * 0.5), math.sin(ry * 0.5)
    c3, s3 = math.cos(rz * 0.5), math.sin(rz * 0.5)
    return [
        s1 * c2 * c3 + c1 * s2 * s3,  # x
        c1 * s2 * c3 - s1 * c2 * s3,  # y
        c1 * c2 * s3 + s1 * s2 * c3,  # z
        c1 * c2 * c3 - s1 * s2 * s3,  # w
    ]


def quat_delta_from_to(rest_q, target_q):
    """Return the delta `d` such that rest_q * d = target_q.
    i.e. d = rest_q^-1 * target_q (works on unit quaternions)."""
    return quat_normalize(quat_mul(quat_conjugate(rest_q), target_q))


def quat_scale_angle(q, factor):
    """Return a quaternion that rotates around the same axis as `q`
    but by `factor * angle(q)`.  Used to soften walk pose deltas:
    factor=1.0 leaves q unchanged, factor=0.0 returns identity."""
    x, y, z, w = quat_normalize(q)
    # Pick the shorter rotation arc (handles q with w<0).
    if w < 0.0:
        x, y, z, w = -x, -y, -z, -w
    if w >= 1.0 - 1e-9:
        return [0.0, 0.0, 0.0, 1.0]
    angle = 2.0 * math.acos(max(-1.0, min(1.0, w)))
    s = math.sin(angle * 0.5)
    if s < 1e-9:
        return [0.0, 0.0, 0.0, 1.0]
    ax, ay, az = x / s, y / s, z / s
    new_half = (angle * factor) * 0.5
    ns = math.sin(new_half)
    return [ax * ns, ay * ns, az * ns, math.cos(new_half)]


# ---------------------------------------------------------------------------
# Animation extraction
# ---------------------------------------------------------------------------

def extract_walking_tracks(j, b, anim_name):
    nodes = j["nodes"]
    node_name = {i: n.get("name", f"node{i}") for i, n in enumerate(nodes)}
    skin_joints = set(j["skins"][0]["joints"]) if j.get("skins") else None

    anim = next((a for a in j.get("animations", []) if a.get("name") == anim_name), None)
    if anim is None:
        raise ValueError(f"animation {anim_name!r} not found in source GLB")

    tracks = []
    duration = 0.0
    for ch in anim["channels"]:
        node_idx = ch["target"]["node"]
        path = ch["target"]["path"]
        if path not in ("rotation", "translation"):
            continue
        if skin_joints is not None and node_idx not in skin_joints:
            continue

        samp = anim["samplers"][ch["sampler"]]
        times  = read_accessor(j, b, samp["input"])
        values = read_accessor(j, b, samp["output"])
        interp = "linear" if samp.get("interpolation", "LINEAR") != "STEP" else "step"

        keyframes = [{"time": t[0], "value": list(v)} for t, v in zip(times, values)]
        if keyframes:
            duration = max(duration, keyframes[-1]["time"])

        tracks.append({
            "bone": node_name[node_idx],
            "property": "rotation" if path == "rotation" else "position",
            "interpolation": interp,
            "keyframes": keyframes,
        })

    return tracks, duration


# ---------------------------------------------------------------------------
# Walk: convert source absolute walking animation to character-agnostic deltas
# ---------------------------------------------------------------------------

def build_walk_delta_tracks(walk_tracks, src_json):
    """Convert source absolute walk into character-agnostic delta tracks.

    Three shaping passes are applied on top of the rest-relative delta
    conversion:
      - Time stretch (`WALK_DURATION_SCALE`): multiplies every keyframe
        time so the cycle plays slower than the heavy 1Hz source pace.
      - Rotation softening (`WALK_ROT_AMPLITUDE_SCALE`): scales every
        delta rotation's *angle* around its own axis, taming aggressive
        spine/arm swings without changing motion direction.
      - Hips Y bob recentering + amplitude scaling (see header).
    """
    delta_tracks = []
    rotations_kept = 0
    rotations_dropped = 0

    for t in walk_tracks:
        bone = t["bone"]
        prop = t["property"]
        kfs = t["keyframes"]
        if not kfs:
            continue

        if prop == "rotation":
            rest = get_bone_rest(src_json, bone, "rotation")
            new_kfs = []
            varies = False
            for kf in kfs:
                d = quat_delta_from_to(rest, kf["value"])
                d = quat_scale_angle(d, WALK_ROT_AMPLITUDE_SCALE)
                new_kfs.append({"time": kf["time"] * WALK_DURATION_SCALE,
                                "value": d})
                if (abs(d[0]) > 1e-4 or abs(d[1]) > 1e-4
                        or abs(d[2]) > 1e-4 or abs(d[3] - 1.0) > 1e-4):
                    varies = True
            if not varies:
                rotations_dropped += 1
                continue
            rotations_kept += 1
            delta_tracks.append({
                "bone": bone,
                "property": "rotation",
                "interpolation": t["interpolation"],
                "keyframes": new_kfs,
            })

        elif prop == "position":
            if bone != "Hips":
                continue  # bone geometry, not animation
            rest_pos = get_bone_rest(src_json, bone, "translation")
            ys_raw = [kf["value"][1] - rest_pos[1] for kf in kfs]
            mean_y = sum(ys_raw) / len(ys_raw)

            new_kfs = []
            for kf, y_raw in zip(kfs, ys_raw):
                # Recenter the bob around rest_y, then dampen the amplitude.
                y_centered = y_raw - mean_y
                y_final = y_centered * HIPS_BOB_AMPLITUDE_SCALE
                new_kfs.append({"time": kf["time"] * WALK_DURATION_SCALE,
                                "value": [0.0, y_final, 0.0]})
            delta_tracks.append({
                "bone": bone,
                "property": "position",
                "interpolation": t["interpolation"],
                "keyframes": new_kfs,
            })

    print(f"  walk rotation tracks: {rotations_kept} kept, "
          f"{rotations_dropped} dropped (rest-equivalent); "
          f"angle scale x{WALK_ROT_AMPLITUDE_SCALE}, "
          f"time stretch x{WALK_DURATION_SCALE}")
    return delta_tracks


def apply_walk_bone_overrides(delta_tracks, duration):
    """Replace specific bones' tracks with user-specified overrides.

    Behaviour per (bone, property):
      - Override value is rest (rotation_deg [0,0,0] or position [0,0,0]):
        the existing track is dropped.  In delta mode, an absent track
        is identity, which means the bone sits at each character's own
        rest pose.
      - Override value is non-rest:
        the existing track is replaced with a constant 2-keyframe track
        pinning the bone to that delta for the whole cycle.

    Bones not listed in `WALK_BONE_OVERRIDES` are left untouched.
    """
    drop_rotation = set()
    drop_position = set()
    constant_rotations = {}
    constant_positions = {}

    EPS = 1e-9

    def _is_zero(v):
        return all(abs(c) < EPS for c in v)

    for bone, spec in WALK_BONE_OVERRIDES.items():
        if "rotation_deg" in spec:
            rd = spec["rotation_deg"]
            if _is_zero(rd):
                drop_rotation.add(bone)
            else:
                constant_rotations[bone] = quat_from_euler_xyz_deg(rd)
        if "position" in spec:
            p = spec["position"]
            if _is_zero(p):
                drop_position.add(bone)
            else:
                constant_positions[bone] = list(p)

    out = []
    for t in delta_tracks:
        bone, prop = t["bone"], t["property"]
        if prop == "rotation" and (bone in drop_rotation
                                   or bone in constant_rotations):
            continue
        if prop == "position" and (bone in drop_position
                                   or bone in constant_positions):
            continue
        out.append(t)

    for bone, q in constant_rotations.items():
        out.append({
            "bone": bone,
            "property": "rotation",
            "interpolation": "linear",
            "keyframes": [
                {"time": 0.0,      "value": q},
                {"time": duration, "value": list(q)},
            ],
        })

    for bone, p in constant_positions.items():
        out.append({
            "bone": bone,
            "property": "position",
            "interpolation": "linear",
            "keyframes": [
                {"time": 0.0,      "value": p},
                {"time": duration, "value": list(p)},
            ],
        })

    pinned = sorted(set(constant_rotations) | set(constant_positions))
    cleared = sorted(drop_rotation | drop_position)
    if pinned:
        print(f"  walk override pinned: {', '.join(pinned)}")
    if cleared:
        print(f"  walk override cleared: {', '.join(cleared)}")
    return out


# ---------------------------------------------------------------------------
# Idle: arm overrides + subtle breathing (all delta mode)
# ---------------------------------------------------------------------------

def build_idle_delta_tracks(walk_tracks, src_json):
    """Idle = constant arm-down deltas + multi-bone breathing/sway loop.

    Authored as a single 6-second cycle with two interleaved rhythms:

      - Breath  (0..6s):   spine rocks slightly forward at exhale,
                           shoulders rise on inhale, hips bob vertically.
                           Period = full cycle, so the breath repeats
                           once per loop.
      - Sway    (0..6s):   hips rotate gently around Y to suggest weight
                           shifting between feet, head glances side-to-
                           side at half-frequency offset.  This is the
                           motion the user actually sees from across the
                           room — much more legible than breath alone.

    Magnitudes are still small enough to read as "alive", not as a
    deliberate pose, but ~2x what the previous pass used so motion is
    unmistakable on a static camera.
    """
    walk0_rotations = {}
    for t in walk_tracks:
        if t["property"] == "rotation" and t["keyframes"]:
            walk0_rotations[t["bone"]] = list(t["keyframes"][0]["value"])

    idle_tracks = []
    duration = IDLE_DURATION

    # ---- Constant arm-down rotation deltas, repeated at start and end so
    #      the player's loop machinery has well-formed track bookends.
    for bone in sorted(ARM_BONES):
        target = walk0_rotations.get(bone)
        if target is None:
            print(f"  WARNING: arm bone {bone!r} not in source walk animation")
            continue
        rest = get_bone_rest(src_json, bone, "rotation")
        d = quat_delta_from_to(rest, target)
        idle_tracks.append({
            "bone": bone,
            "property": "rotation",
            "interpolation": "linear",
            "keyframes": [
                {"time": 0.0,      "value": d},
                {"time": duration, "value": list(d)},
            ],
        })

    AX_X = [1.0, 0.0, 0.0]
    AX_Y = [0.0, 1.0, 0.0]
    AX_Z = [0.0, 0.0, 1.0]
    IDENTITY = [0.0, 0.0, 0.0, 1.0]

    def ease(spec):
        return [{"time": kf[0], "value": kf[1]} for kf in spec]

    half = duration * 0.5  # 3.0s = mid-cycle keyframe
    q1   = duration * 0.25
    q3   = duration * 0.75

    # Spine: forward/back breath rock.  Larger forward swell on exhale,
    # smaller backward recovery on inhale.
    idle_tracks.append({
        "bone": "Spine",
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": ease([
            (0.0,      IDENTITY),
            (q1,       quat_from_axis_angle_deg(AX_X, +2.5)),
            (half,     IDENTITY),
            (q3,       quat_from_axis_angle_deg(AX_X, -1.2)),
            (duration, IDENTITY),
        ]),
    })

    # Spine01: follow-through, half the spine amplitude.
    idle_tracks.append({
        "bone": "Spine01",
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": ease([
            (0.0,      IDENTITY),
            (q1,       quat_from_axis_angle_deg(AX_X, +1.4)),
            (half,     IDENTITY),
            (q3,       quat_from_axis_angle_deg(AX_X, -0.6)),
            (duration, IDENTITY),
        ]),
    })

    # Spine02 (chest): tiny chest expansion on inhale (slight backward
    # tilt of upper torso), eases into a forward slump on exhale.
    idle_tracks.append({
        "bone": "Spine02",
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": ease([
            (0.0,      IDENTITY),
            (q1,       quat_from_axis_angle_deg(AX_X, +0.8)),
            (half,     IDENTITY),
            (q3,       quat_from_axis_angle_deg(AX_X, -0.4)),
            (duration, IDENTITY),
        ]),
    })

    # Neck: counter-rotates spine so head stays mostly level during breath.
    idle_tracks.append({
        "bone": "neck",
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": ease([
            (0.0,      IDENTITY),
            (q1,       quat_from_axis_angle_deg(AX_X, -1.5)),
            (half,     IDENTITY),
            (q3,       quat_from_axis_angle_deg(AX_X, +0.8)),
            (duration, IDENTITY),
        ]),
    })

    # Head: combined yaw glance + tiny nod.  Five keyframes so the eye
    # tracks something different at each beat of the loop.
    head_yaw_l   = quat_from_axis_angle_deg(AX_Y, +3.0)
    head_yaw_r   = quat_from_axis_angle_deg(AX_Y, -2.5)
    head_nod     = quat_from_axis_angle_deg(AX_X, +1.2)
    idle_tracks.append({
        "bone": "Head",
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": ease([
            (0.0,                   IDENTITY),
            (duration * 0.20,       head_yaw_l),
            (duration * 0.40,       head_nod),
            (duration * 0.60,       IDENTITY),
            (duration * 0.80,       head_yaw_r),
            (duration,              IDENTITY),
        ]),
    })

    # Hips rotation: weight-shift sway around Y.  This is the largest
    # readable motion — eye-catching from a distance even on a static
    # camera.  Uses Z too for a hint of lateral hip drop on each side.
    idle_tracks.append({
        "bone": "Hips",
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": ease([
            (0.0,      IDENTITY),
            (q1,       quat_normalize(quat_mul(
                            quat_from_axis_angle_deg(AX_Y, +2.0),
                            quat_from_axis_angle_deg(AX_Z, -1.0)))),
            (half,     IDENTITY),
            (q3,       quat_normalize(quat_mul(
                            quat_from_axis_angle_deg(AX_Y, -2.0),
                            quat_from_axis_angle_deg(AX_Z, +1.0)))),
            (duration, IDENTITY),
        ]),
    })

    # Hips position: vertical breath bob, ~0.8 cm peak-to-peak.  Drops
    # on exhale, lifts very slightly on inhale.
    idle_tracks.append({
        "bone": "Hips",
        "property": "position",
        "interpolation": "linear",
        "keyframes": ease([
            (0.0,      [0.0,  0.00, 0.0]),
            (q1,       [0.0, -0.80, 0.0]),
            (half,     [0.0,  0.00, 0.0]),
            (q3,       [0.0, +0.40, 0.0]),
            (duration, [0.0,  0.00, 0.0]),
        ]),
    })

    return idle_tracks, duration


# ---------------------------------------------------------------------------
# Spec writer
# ---------------------------------------------------------------------------

def round_floats(obj, digits=6):
    if isinstance(obj, float):
        return round(obj, digits)
    if isinstance(obj, list):
        return [round_floats(x, digits) for x in obj]
    if isinstance(obj, dict):
        return {k: round_floats(v, digits) for k, v in obj.items()}
    return obj


def write_spec(path, name, duration, tracks, comment):
    spec = {
        "meta": {
            "name": name,
            "id": name,
            "duration": duration,
            "fps": 30,
            "loop": True,
            "absolute": False,
            "_comment": comment,
        },
        "tracks": tracks,
    }
    with open(path, "w") as f:
        json.dump(round_floats(spec), f, indent=2)
        f.write("\n")
    print(f"  wrote {os.path.relpath(path, REPO_ROOT)}  "
          f"({len(tracks)} tracks, {duration:.2f}s)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"source: {os.path.relpath(WALK_SOURCE_GLB, REPO_ROOT)}::{WALK_SOURCE_NAME}")
    src_json, src_bin = parse_glb(WALK_SOURCE_GLB)
    walk_abs_tracks, walk_duration = extract_walking_tracks(src_json, src_bin, WALK_SOURCE_NAME)
    print(f"  extracted {len(walk_abs_tracks)} absolute tracks "
          f"({walk_duration:.2f}s) from source")

    walk_delta_tracks = build_walk_delta_tracks(walk_abs_tracks, src_json)
    walk_out_duration = walk_duration * WALK_DURATION_SCALE
    walk_delta_tracks = apply_walk_bone_overrides(walk_delta_tracks,
                                                  walk_out_duration)
    write_spec(
        OUT_WALK,
        "NPCWalk",
        walk_out_duration,
        walk_delta_tracks,
        "Walk cycle for Meshy-rig NPCs.  Delta mode: each value is an "
        "offset from the active character's own rest pose, so this single "
        "clip drives every NPC in the roster.  Source: HopperWhiteFemale's "
        "embedded 'Walking' animation, converted to deltas.  Shaping "
        "passes on top of the source: (1) Hips Y bob recentered around "
        "rest height and dampened to "
        f"{int(HIPS_BOB_AMPLITUDE_SCALE * 100)}% amplitude; (2) every "
        f"rotation delta's angle scaled to {int(WALK_ROT_AMPLITUDE_SCALE * 100)}% "
        "to soften aggressive spine/arm swings inherited from the source; "
        f"(3) timeline stretched x{WALK_DURATION_SCALE} for a more natural "
        "walking pace; (4) per-bone overrides clamp Hips/Spine01/Spine02 "
        "to rest and pin LeftArm/RightArm to a static side-pose so the "
        "upper body doesn't fight the leg cycle.  X/Z translation zeroed; "
        "non-Hips position tracks dropped (skeleton geometry, not "
        "animation).",
    )

    idle_delta_tracks, idle_duration = build_idle_delta_tracks(walk_abs_tracks, src_json)
    write_spec(
        OUT_IDLE,
        "NPCIdle",
        idle_duration,
        idle_delta_tracks,
        "Idle for Meshy-rig NPCs.  Delta mode.  Constant arm-bone "
        "rotation deltas drop the arms from the rest T-pose to the side.  "
        f"{IDLE_DURATION:.0f}-second breath/sway loop layers two rhythms: "
        "Spine/Spine01/Spine02/neck breathing rock + Hips Y bob (~0.8 cm "
        "peak-to-peak) for the breath; Hips Y/Z rotation weight-shift "
        "sway + multi-beat Head yaw/nod for the readable side-to-side "
        "motion the eye actually tracks.  Tracks omitted for legs, feet, "
        "toes, hands, and forearms — those sit at each character's own "
        "rest pose.",
    )

    print("done")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
