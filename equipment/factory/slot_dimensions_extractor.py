"""Slot Dimensions Extractor — analyzes BaseFemale mesh to extract per-slot body measurements.

Loads the base body GLB and rig spec, slices the mesh at bone-relative Z heights,
and computes cross-section circumferences, radii, and bounding volumes per equipment slot.
The output is used to (a) guide Meshy AI prompts for better-fitting generated meshes
and (b) provide scaling targets for the equipment_fitter pipeline.

Usage (headless):
    blender --background --python equipment/factory/slot_dimensions_extractor.py -- \
        --rig-spec rig/spec/rig_spec.json \
        --mesh-glb viewer/public/equipment/base_female.glb \
        --equip-spec equipment/spec/equipment_spec.json \
        --out equipment/spec/slot_dimensions.json

Usage (without Blender — rig-spec-only mode, bone data only):
    python equipment/factory/slot_dimensions_extractor.py \
        --rig-spec viewer/public/rig_spec.json \
        --equip-spec equipment/spec/equipment_spec.json \
        --out equipment/spec/slot_dimensions.json \
        --rig-only
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any

# Blender imports are optional — rig-only mode works without them
try:
    import bpy
    import bmesh
    from mathutils import Vector
    HAS_BLENDER = True
except ImportError:
    HAS_BLENDER = False


def load_json(path: str) -> dict[str, Any]:
    with open(os.path.abspath(path), "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(os.path.abspath(path), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved: {path}")


# ---------------------------------------------------------------------------
# Bone-data helpers (work with rig_spec.json, no Blender needed)
# ---------------------------------------------------------------------------

SLOT_BONE_MAP: dict[str, list[str]] = {
    "head": ["head", "neck_01"],
    "amulet": ["spine_03", "neck_01"],
    "upper_body": [
        "pelvis", "spine_01", "spine_02", "spine_03",
        "clavicle_L", "clavicle_R", "upperarm_L", "upperarm_R",
        "lowerarm_L", "lowerarm_R", "hand_L", "hand_R", "neck_01",
    ],
    "gloves": [
        "hand_L", "hand_R",
        "thumb_01_L", "thumb_02_L", "thumb_03_L",
        "index_01_L", "index_02_L", "index_03_L",
        "middle_01_L", "middle_02_L", "middle_03_L",
        "ring_01_L", "ring_02_L", "ring_03_L",
        "pinky_01_L", "pinky_02_L", "pinky_03_L",
        "thumb_01_R", "thumb_02_R", "thumb_03_R",
        "index_01_R", "index_02_R", "index_03_R",
        "middle_01_R", "middle_02_R", "middle_03_R",
        "ring_01_R", "ring_02_R", "ring_03_R",
        "pinky_01_R", "pinky_02_R", "pinky_03_R",
    ],
    "ring": ["ring_01_L", "ring_02_L"],
    "lower_body": [
        "pelvis", "thigh_L", "thigh_R", "shin_L", "shin_R",
    ],
    "boots": [
        "shin_L", "shin_R", "foot_L", "foot_R", "toe_L", "toe_R",
    ],
}

SLOT_DEFAULTS: dict[str, dict[str, Any]] = {
    "head": {"shrinkwrap": False, "shrinkwrap_offset": 0.0},
    "amulet": {"shrinkwrap": False, "shrinkwrap_offset": 0.0},
    "upper_body": {"shrinkwrap": True, "shrinkwrap_offset": 0.003},
    "gloves": {"shrinkwrap": True, "shrinkwrap_offset": 0.002},
    "ring": {"shrinkwrap": False, "shrinkwrap_offset": 0.0},
    "lower_body": {"shrinkwrap": True, "shrinkwrap_offset": 0.003},
    "boots": {"shrinkwrap": True, "shrinkwrap_offset": 0.002},
}


def bone_lookup(rig_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {b["name"]: b for b in rig_spec["bones"]}


def bone_midpoint(bone: dict[str, Any]) -> list[float]:
    h, t = bone["head"], bone["tail"]
    return [(h[i] + t[i]) / 2.0 for i in range(3)]


def bone_length(bone: dict[str, Any]) -> float:
    h, t = bone["head"], bone["tail"]
    return math.sqrt(sum((t[i] - h[i]) ** 2 for i in range(3)))


def bones_bounding_box(bones: list[dict[str, Any]]) -> dict[str, list[float]]:
    all_pts = []
    for b in bones:
        all_pts.append(b["head"])
        all_pts.append(b["tail"])
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    zs = [p[2] for p in all_pts]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
        "center": [
            (min(xs) + max(xs)) / 2.0,
            (min(ys) + max(ys)) / 2.0,
            (min(zs) + max(zs)) / 2.0,
        ],
        "size": [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)],
    }


def extract_bone_dimensions(
    slot_id: str,
    equip_slot: dict[str, Any],
    bone_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Extract bone-based dimensions for one slot (no mesh analysis)."""
    rig_bone_names = SLOT_BONE_MAP.get(slot_id, [])
    bones = [bone_map[n] for n in rig_bone_names if n in bone_map]

    if not bones:
        return {"slot_id": slot_id, "error": "no matching bones in rig_spec"}

    bbox = bones_bounding_box(bones)
    result: dict[str, Any] = {
        "slot_id": slot_id,
        "slot_name": equip_slot.get("name", slot_id),
        "bones_bounding_box": bbox,
        "z_range": [equip_slot["bounds"]["z_min"], equip_slot["bounds"]["z_max"]],
        "spec_radius": equip_slot["bounds"]["radius"],
        "fitting_defaults": SLOT_DEFAULTS.get(slot_id, {}),
        "bone_positions": {},
    }

    for bn in rig_bone_names:
        if bn in bone_map:
            b = bone_map[bn]
            result["bone_positions"][bn] = {
                "head": b["head"],
                "tail": b["tail"],
                "midpoint": bone_midpoint(b),
                "length": round(bone_length(b), 5),
            }

    return result


# ---------------------------------------------------------------------------
# Mesh-based cross-section analysis (requires Blender)
# ---------------------------------------------------------------------------

def import_body_glb(filepath: str) -> list:
    """Import a GLB and return all mesh objects."""
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(filepath))
    meshes = [obj for obj in bpy.context.selected_objects if obj.type == "MESH"]
    return meshes


def get_world_vertices(mesh_obj) -> list[list[float]]:
    """Get all vertex positions in world space."""
    mesh_obj.data.calc_loop_triangles()
    mat = mesh_obj.matrix_world
    verts = []
    for v in mesh_obj.data.vertices:
        co = mat @ v.co
        verts.append([co.x, co.y, co.z])
    return verts


def slice_vertices_at_z(
    verts: list[list[float]], z: float, tolerance: float = 0.015,
) -> list[list[float]]:
    """Get vertices within a Z slice."""
    return [v for v in verts if abs(v[2] - z) <= tolerance]


def compute_circumference_at_z(
    verts: list[list[float]], z: float, tolerance: float = 0.015,
) -> dict[str, float]:
    """Compute approximate circumference of the body at a given Z height."""
    ring = slice_vertices_at_z(verts, z, tolerance)
    if len(ring) < 3:
        return {"z": z, "circumference": 0.0, "radius_avg": 0.0, "vertex_count": len(ring)}

    cx = sum(v[0] for v in ring) / len(ring)
    cy = sum(v[1] for v in ring) / len(ring)
    radii = [math.sqrt((v[0] - cx) ** 2 + (v[1] - cy) ** 2) for v in ring]
    avg_r = sum(radii) / len(radii)
    max_r = max(radii)
    min_r = min(radii)

    angles = [math.atan2(v[1] - cy, v[0] - cx) for v in ring]
    sorted_pairs = sorted(zip(angles, ring))

    perimeter = 0.0
    for i in range(len(sorted_pairs)):
        j = (i + 1) % len(sorted_pairs)
        dx = sorted_pairs[j][1][0] - sorted_pairs[i][1][0]
        dy = sorted_pairs[j][1][1] - sorted_pairs[i][1][1]
        perimeter += math.sqrt(dx * dx + dy * dy)

    return {
        "z": round(z, 4),
        "circumference": round(perimeter, 5),
        "radius_avg": round(avg_r, 5),
        "radius_max": round(max_r, 5),
        "radius_min": round(min_r, 5),
        "center": [round(cx, 5), round(cy, 5)],
        "vertex_count": len(ring),
    }


def compute_mesh_bounding_box(
    verts: list[list[float]], z_min: float, z_max: float,
) -> dict[str, Any]:
    """Compute bounding box for vertices within a Z range."""
    filtered = [v for v in verts if z_min <= v[2] <= z_max]
    if not filtered:
        return {"min": [0, 0, 0], "max": [0, 0, 0], "center": [0, 0, 0], "size": [0, 0, 0]}

    xs = [v[0] for v in filtered]
    ys = [v[1] for v in filtered]
    zs = [v[2] for v in filtered]
    return {
        "min": [round(min(xs), 5), round(min(ys), 5), round(min(zs), 5)],
        "max": [round(max(xs), 5), round(max(ys), 5), round(max(zs), 5)],
        "center": [
            round((min(xs) + max(xs)) / 2.0, 5),
            round((min(ys) + max(ys)) / 2.0, 5),
            round((min(zs) + max(zs)) / 2.0, 5),
        ],
        "size": [
            round(max(xs) - min(xs), 5),
            round(max(ys) - min(ys), 5),
            round(max(zs) - min(zs), 5),
        ],
        "vertex_count": len(filtered),
    }


def extract_mesh_dimensions(
    slot_data: dict[str, Any],
    all_verts: list[list[float]],
    bone_map: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Add mesh-based measurements to existing bone-based slot data."""
    z_min = slot_data["z_range"][0]
    z_max = slot_data["z_range"][1]

    slot_data["mesh_bounding_box"] = compute_mesh_bounding_box(all_verts, z_min, z_max)

    num_slices = 5
    z_range = z_max - z_min
    if z_range < 0.01:
        num_slices = 1

    cross_sections = []
    for i in range(num_slices):
        t = i / max(num_slices - 1, 1)
        z = z_min + t * z_range
        cs = compute_circumference_at_z(all_verts, z)
        if cs["vertex_count"] > 0:
            cross_sections.append(cs)
    slot_data["cross_sections"] = cross_sections

    slot_id = slot_data["slot_id"]

    if slot_id == "head":
        head_bone = bone_map.get("head")
        if head_bone:
            head_z = (head_bone["head"][2] + head_bone["tail"][2]) / 2.0
            brow_cs = compute_circumference_at_z(all_verts, head_z - 0.05)
            crown_cs = compute_circumference_at_z(all_verts, head_z + 0.05)
            slot_data["head_measurements"] = {
                "brow_line": brow_cs,
                "crown": crown_cs,
                "head_center_z": round(head_z, 4),
            }

    elif slot_id == "amulet":
        neck = bone_map.get("neck_01")
        if neck:
            neck_z = neck["head"][2]
            neck_cs = compute_circumference_at_z(all_verts, neck_z)
            slot_data["amulet_measurements"] = {
                "neck_base": neck_cs,
                "neck_z": round(neck_z, 4),
            }

    elif slot_id == "upper_body":
        measurements = {}
        spine_z_vals = {
            "pelvis": bone_map.get("pelvis", {}).get("head", [0, 0, 0.95])[2],
            "waist": bone_map.get("spine_01", {}).get("tail", [0, 0, 1.12])[2],
            "chest": bone_map.get("spine_02", {}).get("tail", [0, 0, 1.25])[2],
            "shoulders": bone_map.get("spine_03", {}).get("tail", [0, 0, 1.40])[2],
        }
        for label, z in spine_z_vals.items():
            measurements[label] = compute_circumference_at_z(all_verts, z)

        clav_l = bone_map.get("clavicle_L")
        clav_r = bone_map.get("clavicle_R")
        if clav_l and clav_r:
            shoulder_width = abs(clav_l["tail"][0]) + abs(clav_r["tail"][0])
            measurements["shoulder_width"] = round(shoulder_width, 4)

        hand_l = bone_map.get("hand_L")
        clav_l = bone_map.get("clavicle_L")
        if hand_l and clav_l:
            arm_len = math.sqrt(sum(
                (hand_l["tail"][i] - clav_l["head"][i]) ** 2 for i in range(3)
            ))
            measurements["arm_length_approx"] = round(arm_len, 4)

        slot_data["upper_body_measurements"] = measurements

    elif slot_id == "lower_body":
        measurements = {}
        hip_z = bone_map.get("pelvis", {}).get("head", [0, 0, 0.95])[2]
        measurements["hip"] = compute_circumference_at_z(all_verts, hip_z)

        thigh_l = bone_map.get("thigh_L")
        if thigh_l:
            thigh_mid_z = (thigh_l["head"][2] + thigh_l["tail"][2]) / 2.0
            measurements["thigh_mid"] = compute_circumference_at_z(all_verts, thigh_mid_z)
            knee_z = thigh_l["tail"][2]
            measurements["knee"] = compute_circumference_at_z(all_verts, knee_z)
            inseam = thigh_l["head"][2] - bone_map.get("shin_L", thigh_l)["tail"][2]
            measurements["inseam_length"] = round(abs(inseam), 4)

        slot_data["lower_body_measurements"] = measurements

    elif slot_id == "boots":
        measurements = {}
        shin_l = bone_map.get("shin_L")
        foot_l = bone_map.get("foot_L")
        if shin_l:
            calf_z = (shin_l["head"][2] + shin_l["tail"][2]) / 2.0
            measurements["calf_mid"] = compute_circumference_at_z(all_verts, calf_z)
            ankle_z = shin_l["tail"][2]
            measurements["ankle"] = compute_circumference_at_z(all_verts, ankle_z)
        if foot_l:
            toe = bone_map.get("toe_L")
            if toe:
                foot_length = math.sqrt(sum(
                    (toe["tail"][i] - foot_l["head"][i]) ** 2 for i in range(3)
                ))
                measurements["foot_length"] = round(foot_length, 4)

        slot_data["boots_measurements"] = measurements

    elif slot_id == "gloves":
        measurements = {}
        hand_l = bone_map.get("hand_L")
        if hand_l:
            wrist_z = hand_l["head"][2]
            wrist_verts = [
                v for v in all_verts
                if abs(v[2] - wrist_z) < 0.02 and v[0] < -0.5
            ]
            if wrist_verts:
                ys = [v[1] for v in wrist_verts]
                zs = [v[2] for v in wrist_verts]
                measurements["wrist_width"] = round(max(ys) - min(ys), 4)
                measurements["wrist_height"] = round(max(zs) - min(zs), 4)

        finger_names = ["index", "middle", "ring", "pinky", "thumb"]
        finger_lengths = {}
        for fname in finger_names:
            bone_1 = bone_map.get(f"{fname}_01_L")
            bone_3 = bone_map.get(f"{fname}_03_L")
            if bone_1 and bone_3:
                length = math.sqrt(sum(
                    (bone_3["tail"][i] - bone_1["head"][i]) ** 2 for i in range(3)
                ))
                finger_lengths[fname] = round(length, 4)
        measurements["finger_lengths"] = finger_lengths

        slot_data["gloves_measurements"] = measurements

    elif slot_id == "ring":
        measurements = {}
        ring_bone = bone_map.get("ring_01_L")
        if ring_bone:
            measurements["ring_finger_bone_length"] = round(bone_length(ring_bone), 4)
            mid = bone_midpoint(ring_bone)
            ring_verts = [
                v for v in all_verts
                if math.sqrt(sum((v[i] - mid[i]) ** 2 for i in range(3))) < 0.03
            ]
            if ring_verts:
                dists = [
                    math.sqrt((v[0] - mid[0]) ** 2 + (v[1] - mid[1]) ** 2)
                    for v in ring_verts
                ]
                measurements["finger_radius_at_ring"] = round(sum(dists) / len(dists), 5)

        slot_data["ring_measurements"] = measurements

    return slot_data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

EQUIPMENT_SLOT_IDS = ["head", "amulet", "upper_body", "gloves", "ring", "lower_body", "boots"]


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = argv[1:]

    parser = argparse.ArgumentParser(description="Slot Dimensions Extractor")
    parser.add_argument("--rig-spec", required=True, help="Path to rig_spec.json")
    parser.add_argument("--equip-spec", required=True, help="Path to equipment_spec.json")
    parser.add_argument("--mesh-glb", default=None, help="Path to base body GLB (e.g. base_female.glb)")
    parser.add_argument("--out", required=True, help="Output path for slot_dimensions.json")
    parser.add_argument(
        "--rig-only", action="store_true",
        help="Skip mesh analysis; extract bone-based dimensions only (no Blender needed)",
    )
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    print("=== Slot Dimensions Extractor ===")

    rig_spec = load_json(args.rig_spec)
    equip_spec = load_json(args.equip_spec)
    bone_map = bone_lookup(rig_spec)

    equip_slot_map = {s["id"]: s for s in equip_spec["slots"]}

    all_verts: list[list[float]] | None = None

    if not args.rig_only and args.mesh_glb:
        if not HAS_BLENDER:
            print("  Warning: Blender not available, falling back to rig-only mode")
        else:
            print(f"  Loading mesh: {args.mesh_glb}")
            bpy.ops.wm.read_homefile(use_empty=True)
            mesh_objs = import_body_glb(args.mesh_glb)
            all_verts = []
            for obj in mesh_objs:
                all_verts.extend(get_world_vertices(obj))
            print(f"  Loaded {len(all_verts)} vertices from {len(mesh_objs)} mesh(es)")

    output: dict[str, Any] = {
        "meta": {
            "version": "1.0.0",
            "description": "Per-slot body dimensions extracted from BaseFemale mesh and rig spec.",
            "coordinate_system": rig_spec["meta"],
            "source_mesh": args.mesh_glb or "none (rig-only)",
            "has_mesh_data": all_verts is not None,
        },
        "slots": {},
    }

    for slot_id in EQUIPMENT_SLOT_IDS:
        equip_slot = equip_slot_map.get(slot_id)
        if not equip_slot:
            print(f"  Warning: slot '{slot_id}' not in equipment_spec, skipping")
            continue

        print(f"  Extracting: {slot_id}")
        slot_data = extract_bone_dimensions(slot_id, equip_slot, bone_map)

        if all_verts is not None:
            slot_data = extract_mesh_dimensions(slot_data, all_verts, bone_map)

        output["slots"][slot_id] = slot_data

    save_json(output, args.out)
    print(f"=== Done — {len(output['slots'])} slots extracted ===")


if __name__ == "__main__":
    main()
