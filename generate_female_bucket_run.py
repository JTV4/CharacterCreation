#!/usr/bin/env python3
"""
generate_female_bucket_run.py
=============================

Looping run-with-bucket clip. Legs / hips / torso come from FemaleRunV3.
The right arm stays on the FemaleIdle hang so the bucket handle stays in
the palm (no arm-pump). Left arm still runs. Right-hand fingers use the
same grip as FemaleBucketPour.

Delta-from-rest, same as the other Mixamo clips.

Run:
    python3 generate_female_bucket_run.py
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ANIM_DIR = Path(__file__).resolve().parent / "viewer/public/animations"
SRC = ANIM_DIR / "FemaleRunV3.anim.json"
OUT = ANIM_DIR / "FemaleBucketRun.anim.json"
MANIFEST = ANIM_DIR / "manifest.json"

Quat = Tuple[float, float, float, float]
IDENT: Quat = (0.0, 0.0, 0.0, 1.0)

# FemaleIdle bookend (same values as generate_female_bucket_pour.py).
REST_RIGHT_ARM: Quat = (0.60838, 0.02168, -0.01819, 0.79314)
REST_RIGHT_FOREARM: Quat = (0.0, 0.0, 0.17365, 0.98481)
REST_RIGHT_SHOULDER: Quat = (-0.02618, 0.0, 0.0, 0.99966)

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

RIGHT_HOLD = {
    "mixamorigRightArm": REST_RIGHT_ARM,
    "mixamorigRightForeArm": REST_RIGHT_FOREARM,
    "mixamorigRightHand": IDENT,
    "mixamorigRightShoulder": REST_RIGHT_SHOULDER,
}

RIGHT_FINGER_PREFIX = "mixamorigRightHand"


def quat_norm(q: Sequence[float]) -> List[float]:
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n == 0:
        return [0.0, 0.0, 0.0, 1.0]
    return [x / n, y / n, z / n, w / n]


def rounded(q: Sequence[float], digits: int = 5) -> List[float]:
    return [round(v, digits) for v in quat_norm(q)]


def constant_rotation(bone: str, duration: float, q: Sequence[float]) -> Dict:
    value = rounded(q)
    return {
        "bone": bone,
        "property": "rotation",
        "interpolation": "linear",
        "keyframes": [
            {"time": 0.0, "value": value},
            {"time": round(duration, 5), "value": list(value)},
        ],
    }


def replace_or_add(tracks: List[Dict], replacement: Dict) -> None:
    bone = replacement["bone"]
    prop = replacement["property"]
    for i, track in enumerate(tracks):
        if track.get("bone") == bone and track.get("property") == prop:
            tracks[i] = replacement
            return
    tracks.append(replacement)


def build() -> Dict:
    src = json.loads(SRC.read_text())
    duration = float(src["meta"]["duration"])
    dst = copy.deepcopy(src)
    dst["meta"]["name"] = "FemaleBucketRun"
    dst["meta"]["id"] = "FemaleBucketRun"
    dst["meta"]["_comment"] = (
        "FemaleRunV3 legs / hips / left arm, right arm pinned to FemaleIdle "
        "hang so a bucket (or any right-hand vessel) stays in the palm. "
        "Right fingers use the FemaleBucketPour grip. Delta mode."
    )

    tracks: List[Dict] = list(dst["tracks"])
    for bone, quat in RIGHT_HOLD.items():
        replace_or_add(tracks, constant_rotation(bone, duration, quat))

    for short, quat in BUCKET_GRIP.items():
        replace_or_add(
            tracks,
            constant_rotation(f"{RIGHT_FINGER_PREFIX}{short}", duration, quat),
        )

    dst["tracks"] = tracks
    return dst


def upsert_manifest() -> None:
    data = json.loads(MANIFEST.read_text())
    entry = {"id": "FemaleBucketRun", "file": "FemaleBucketRun.anim.json", "loop": True}
    anims = data["animations"]
    for i, row in enumerate(anims):
        if row.get("id") == "FemaleBucketRun":
            anims[i] = entry
            break
    else:
        insert_at = next(
            (i for i, row in enumerate(anims) if row.get("id") == "FemaleBucketPour"),
            len(anims),
        )
        anims.insert(insert_at + 1, entry)
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Updated {MANIFEST.name}")


def main() -> None:
    spec = build()
    OUT.write_text(json.dumps(spec, indent=2) + "\n")
    print(
        f"Wrote {OUT.name}: {len(spec['tracks'])} tracks, "
        f"{spec['meta']['duration']:.3f}s, loop={spec['meta']['loop']}"
    )
    upsert_manifest()


if __name__ == "__main__":
    main()
