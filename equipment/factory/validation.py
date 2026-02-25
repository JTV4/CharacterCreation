"""Validates equipment_spec.json against rig_spec.json.

Checks:
  1. Every bone referenced in a slot exists in the rig spec.
  2. Bone Z-ranges don't cross slot boundaries.
  3. No bone appears at full weight (1.0) in two overlapping slots.
  4. hidden_by rules reference valid slot IDs.
  5. Bilateral slots reference both L and R bones.

Can be run standalone:
    python equipment/factory/validation.py \
        --rig-spec rig/spec/rig_spec.json \
        --equip-spec equipment/spec/equipment_spec.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    with open(os.path.abspath(path), "r", encoding="utf-8") as f:
        return json.load(f)


def validate_equipment_spec(
    equip_spec: dict[str, Any],
    rig_spec: dict[str, Any],
) -> list[str]:
    """Return a list of error strings. Empty list means valid."""
    errors: list[str] = []

    bone_map = {b["name"]: b for b in rig_spec["bones"]}
    slot_ids = {s["id"] for s in equip_spec["slots"]}

    full_weight_bones: dict[str, list[str]] = {}

    for slot in equip_spec["slots"]:
        sid = slot["id"]

        # 1. Check bone existence
        for bone_ref in slot["bones"]:
            bname = bone_ref["name"]
            if bname not in bone_map:
                errors.append(f"[{sid}] Bone '{bname}' not found in rig spec.")

        # 2. Check Z-boundary overlap
        z_min = slot["bounds"]["z_min"]
        z_max = slot["bounds"]["z_max"]
        for bone_ref in slot["bones"]:
            bname = bone_ref["name"]
            if bname not in bone_map:
                continue
            bd = bone_map[bname]
            bone_z_min = min(bd["head"][2], bd["tail"][2])
            bone_z_max = max(bd["head"][2], bd["tail"][2])
            if bone_z_max < z_min - 0.1 or bone_z_min > z_max + 0.1:
                errors.append(
                    f"[{sid}] Bone '{bname}' (Z {bone_z_min:.3f}-{bone_z_max:.3f}) "
                    f"is outside slot bounds (Z {z_min:.3f}-{z_max:.3f})."
                )

        # 3. Track full-weight bones for overlap detection
        for bone_ref in slot["bones"]:
            bname = bone_ref["name"]
            if bone_ref["weight"] >= 1.0:
                full_weight_bones.setdefault(bname, []).append(sid)

        # 4. hidden_by references valid slot IDs
        hidden_by = slot.get("rules", {}).get("hidden_by", [])
        for ref_id in hidden_by:
            if ref_id not in slot_ids:
                errors.append(f"[{sid}] hidden_by references unknown slot '{ref_id}'.")

        # 5. Bilateral slots must reference both L and R
        if slot.get("bilateral", False):
            l_bones = [b["name"] for b in slot["bones"] if b["name"].endswith("_L")]
            r_bones = [b["name"] for b in slot["bones"] if b["name"].endswith("_R")]
            l_bases = {n.rsplit("_L", 1)[0] for n in l_bones}
            r_bases = {n.rsplit("_R", 1)[0] for n in r_bones}
            missing_r = l_bases - r_bases
            missing_l = r_bases - l_bases
            if missing_r:
                errors.append(
                    f"[{sid}] Bilateral slot missing R-side bones for: "
                    f"{', '.join(sorted(missing_r))}"
                )
            if missing_l:
                errors.append(
                    f"[{sid}] Bilateral slot missing L-side bones for: "
                    f"{', '.join(sorted(missing_l))}"
                )

    # 3b. Check for full-weight bone overlaps between slots.
    # Exempt pairs where one slot is hidden_by the other (mutually exclusive).
    slot_lookup = {s["id"]: s for s in equip_spec["slots"]}
    for bname, sids in full_weight_bones.items():
        if len(sids) > 1:
            for i in range(len(sids)):
                for j in range(i + 1, len(sids)):
                    s1, s2 = sids[i], sids[j]
                    hidden_by_1 = slot_lookup[s1].get("rules", {}).get("hidden_by", [])
                    hidden_by_2 = slot_lookup[s2].get("rules", {}).get("hidden_by", [])
                    if s2 in hidden_by_1 or s1 in hidden_by_2:
                        continue
                    b1 = slot_lookup[s1]["bounds"]
                    b2 = slot_lookup[s2]["bounds"]
                    if b1["z_min"] < b2["z_max"] and b2["z_min"] < b1["z_max"]:
                        errors.append(
                            f"Bone '{bname}' has weight=1.0 in overlapping slots: "
                            f"{s1}, {s2}"
                        )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate equipment spec")
    parser.add_argument("--rig-spec", required=True)
    parser.add_argument("--equip-spec", required=True)
    args = parser.parse_args()

    rig_spec = load_json(args.rig_spec)
    equip_spec = load_json(args.equip_spec)

    errors = validate_equipment_spec(equip_spec, rig_spec)
    if errors:
        print(f"Validation FAILED with {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        slot_count = len(equip_spec["slots"])
        bone_count = sum(len(s["bones"]) for s in equip_spec["slots"])
        print(f"Validation PASSED: {slot_count} slots, {bone_count} bone references.")


if __name__ == "__main__":
    main()
