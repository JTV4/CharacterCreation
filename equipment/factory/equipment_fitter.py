"""Equipment Fitter — fits raw GLB meshes to equipment slots on the character rig.

Takes an unrigged GLB (e.g. from Meshy AI), scales/positions it to match a slot's
bounding volume, optionally shrinkwraps to the body surface, auto-skins with Blender
weights, and exports a rigged GLB ready for the viewer.

Usage (headless):
    blender --background --python equipment/factory/equipment_fitter.py -- \
        --rig-blend rig/output/rig.blend \
        --mesh path/to/raw_helmet.glb \
        --slot-type head \
        --slot-id "mystic_helmet" \
        --slot-name "Mystic Helmet" \
        --equip-spec equipment/spec/equipment_spec.json \
        --dimensions equipment/spec/slot_dimensions.json \
        --body-mesh viewer/public/equipment/base_female.glb \
        --out equipment/output/ \
        --game-out equipment/output/game/ \
        --update-spec
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any

import bpy
from mathutils import Vector, Matrix


# ---------------------------------------------------------------------------
# Slot type configuration
# ---------------------------------------------------------------------------

SLOT_TYPE_CONFIG: dict[str, dict[str, Any]] = {
    "head": {
        "shrinkwrap": False,
        "shrinkwrap_offset": 0.0,
        "bilateral": False,
        "category": "equipment",
        "default_color": "#c084fc",
        "hides_body_regions": ["head"],
        "mesh_type": "dome",
        "bones": [
            {"name": "mixamorigHead", "weight": 1.0},
            {"name": "mixamorigNeck", "weight": 0.25},
        ],
    },
    "amulet": {
        "shrinkwrap": False,
        "shrinkwrap_offset": 0.0,
        "bilateral": False,
        "category": "equipment",
        "default_color": "#fbbf24",
        "hides_body_regions": [],
        "mesh_type": "pendant",
        "bones": [
            {"name": "mixamorigSpine2", "weight": 0.7},
            {"name": "mixamorigNeck", "weight": 1.0},
        ],
    },
    "upper_body": {
        "shrinkwrap": True,
        "shrinkwrap_offset": 0.003,
        "bilateral": False,
        "category": "equipment",
        "default_color": "#4a9eff",
        "hides_body_regions": ["torso", "neck", "arms"],
        "mesh_type": "torso",
        "bones": [
            {"name": "mixamorigHips", "weight": 0.6},
            {"name": "mixamorigSpine", "weight": 1.0},
            {"name": "mixamorigSpine1", "weight": 1.0},
            {"name": "mixamorigSpine2", "weight": 1.0},
            {"name": "mixamorigLeftShoulder", "weight": 0.8},
            {"name": "mixamorigRightShoulder", "weight": 0.8},
            {"name": "mixamorigLeftArm", "weight": 1.0},
            {"name": "mixamorigRightArm", "weight": 1.0},
            {"name": "mixamorigLeftForeArm", "weight": 1.0},
            {"name": "mixamorigRightForeArm", "weight": 1.0},
            {"name": "mixamorigLeftHand", "weight": 0.1},
            {"name": "mixamorigRightHand", "weight": 0.1},
            {"name": "mixamorigNeck", "weight": 0.1},
        ],
    },
    "gloves": {
        "shrinkwrap": True,
        "shrinkwrap_offset": 0.002,
        "bilateral": True,
        "category": "equipment",
        "default_color": "#4adb7a",
        "hides_body_regions": ["hands"],
        "mesh_type": "glove",
        "bones": [
            {"name": "mixamorigLeftHand", "weight": 1.0},
            {"name": "mixamorigLeftHandThumb1", "weight": 1.0},
            {"name": "mixamorigLeftHandThumb2", "weight": 1.0},
            {"name": "mixamorigLeftHandThumb3", "weight": 1.0},
            {"name": "mixamorigLeftHandIndex1", "weight": 1.0},
            {"name": "mixamorigLeftHandIndex2", "weight": 1.0},
            {"name": "mixamorigLeftHandIndex3", "weight": 1.0},
            {"name": "mixamorigLeftHandMiddle1", "weight": 1.0},
            {"name": "mixamorigLeftHandMiddle2", "weight": 1.0},
            {"name": "mixamorigLeftHandMiddle3", "weight": 1.0},
            {"name": "mixamorigLeftHandRing1", "weight": 1.0},
            {"name": "mixamorigLeftHandRing2", "weight": 1.0},
            {"name": "mixamorigLeftHandRing3", "weight": 1.0},
            {"name": "mixamorigLeftHandPinky1", "weight": 1.0},
            {"name": "mixamorigLeftHandPinky2", "weight": 1.0},
            {"name": "mixamorigLeftHandPinky3", "weight": 1.0},
            {"name": "mixamorigRightHand", "weight": 1.0},
            {"name": "mixamorigRightHandThumb1", "weight": 1.0},
            {"name": "mixamorigRightHandThumb2", "weight": 1.0},
            {"name": "mixamorigRightHandThumb3", "weight": 1.0},
            {"name": "mixamorigRightHandIndex1", "weight": 1.0},
            {"name": "mixamorigRightHandIndex2", "weight": 1.0},
            {"name": "mixamorigRightHandIndex3", "weight": 1.0},
            {"name": "mixamorigRightHandMiddle1", "weight": 1.0},
            {"name": "mixamorigRightHandMiddle2", "weight": 1.0},
            {"name": "mixamorigRightHandMiddle3", "weight": 1.0},
            {"name": "mixamorigRightHandRing1", "weight": 1.0},
            {"name": "mixamorigRightHandRing2", "weight": 1.0},
            {"name": "mixamorigRightHandRing3", "weight": 1.0},
            {"name": "mixamorigRightHandPinky1", "weight": 1.0},
            {"name": "mixamorigRightHandPinky2", "weight": 1.0},
            {"name": "mixamorigRightHandPinky3", "weight": 1.0},
        ],
    },
    "ring": {
        "shrinkwrap": False,
        "shrinkwrap_offset": 0.0,
        "bilateral": False,
        "category": "equipment",
        "default_color": "#ffd93d",
        "hides_body_regions": [],
        "mesh_type": "torus",
        "bones": [
            {"name": "mixamorigLeftHandRing1", "weight": 1.0},
            {"name": "mixamorigLeftHandRing2", "weight": 0.4},
        ],
    },
    "lower_body": {
        "shrinkwrap": True,
        "shrinkwrap_offset": 0.003,
        "bilateral": True,
        "category": "equipment",
        "default_color": "#ff6b6b",
        "hides_body_regions": ["torso", "legs"],
        "mesh_type": "pants",
        "bones": [
            {"name": "mixamorigHips", "weight": 1.0},
            {"name": "mixamorigLeftUpLeg", "weight": 1.0},
            {"name": "mixamorigRightUpLeg", "weight": 1.0},
            {"name": "mixamorigLeftLeg", "weight": 0.8},
            {"name": "mixamorigRightLeg", "weight": 0.8},
        ],
    },
    "boots": {
        "shrinkwrap": True,
        "shrinkwrap_offset": 0.002,
        "bilateral": True,
        "category": "equipment",
        "default_color": "#f97316",
        "hides_body_regions": ["feet", "legs"],
        "mesh_type": "boot",
        "bones": [
            {"name": "mixamorigLeftLeg", "weight": 0.6},
            {"name": "mixamorigRightLeg", "weight": 0.6},
            {"name": "mixamorigLeftFoot", "weight": 1.0},
            {"name": "mixamorigRightFoot", "weight": 1.0},
            {"name": "mixamorigLeftToeBase", "weight": 1.0},
            {"name": "mixamorigRightToeBase", "weight": 1.0},
        ],
    },
}


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def load_json(path: str) -> dict[str, Any]:
    with open(os.path.abspath(path), "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(os.path.abspath(path), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Mesh import / cleanup (shared with skin_base_meshes.py pattern)
# ---------------------------------------------------------------------------

def import_glb(filepath: str) -> list[bpy.types.Object]:
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(filepath))
    return list(bpy.context.selected_objects)


def collect_mesh_objects(imported_objects: list) -> list[bpy.types.Object]:
    meshes: list[bpy.types.Object] = []
    armatures: list[bpy.types.Object] = []

    def walk(obj: bpy.types.Object) -> None:
        if obj.type == "MESH":
            meshes.append(obj)
        elif obj.type == "ARMATURE":
            armatures.append(obj)
        for child in obj.children:
            walk(child)

    for obj in imported_objects:
        walk(obj)

    for arm in armatures:
        bpy.data.objects.remove(arm, do_unlink=True)

    return meshes


def clear_mesh_rigging(mesh_obj: bpy.types.Object) -> None:
    for mod in list(mesh_obj.modifiers):
        if mod.type == "ARMATURE":
            mesh_obj.modifiers.remove(mod)
    for vg in list(mesh_obj.vertex_groups):
        mesh_obj.vertex_groups.remove(vg)


def join_meshes(mesh_objs: list[bpy.types.Object], name: str) -> bpy.types.Object:
    if len(mesh_objs) == 1:
        mesh_objs[0].name = name
        return mesh_objs[0]

    bpy.ops.object.select_all(action="DESELECT")
    for obj in mesh_objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objs[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = name
    return result


# ---------------------------------------------------------------------------
# Bounding box / fitting
# ---------------------------------------------------------------------------

def get_mesh_bbox(mesh_obj: bpy.types.Object) -> dict[str, Vector]:
    """Get world-space bounding box of a mesh object."""
    mat = mesh_obj.matrix_world
    verts = [mat @ v.co for v in mesh_obj.data.vertices]
    if not verts:
        return {"min": Vector(), "max": Vector(), "center": Vector(), "size": Vector()}
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    mn = Vector((min(xs), min(ys), min(zs)))
    mx = Vector((max(xs), max(ys), max(zs)))
    return {
        "min": mn,
        "max": mx,
        "center": (mn + mx) / 2.0,
        "size": mx - mn,
    }


def scale_to_fit(
    mesh_obj: bpy.types.Object,
    target_bbox: dict[str, Any],
    target_center: list[float],
) -> None:
    """Scale and position mesh to fit within a target bounding volume."""
    current = get_mesh_bbox(mesh_obj)
    cur_size = current["size"]

    max_cur = max(cur_size.x, cur_size.y, cur_size.z)
    if max_cur < 0.0001:
        print("  Warning: mesh has near-zero size, skipping scale")
        return

    target_size = target_bbox["size"]
    max_target = max(target_size)
    if max_target < 0.0001:
        print("  Warning: target slot has near-zero size, skipping scale")
        return

    scale_factor = max_target / max_cur

    mesh_obj.scale = (scale_factor, scale_factor, scale_factor)

    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.transform_apply(scale=True)

    new_bbox = get_mesh_bbox(mesh_obj)
    offset = Vector(target_center) - new_bbox["center"]
    mesh_obj.location += offset

    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.transform_apply(location=True)

    print(f"  Scaled by {scale_factor:.4f}, centered at {target_center}")


# ---------------------------------------------------------------------------
# Shrinkwrap
# ---------------------------------------------------------------------------

def apply_shrinkwrap(
    mesh_obj: bpy.types.Object,
    body_obj: bpy.types.Object,
    offset: float = 0.003,
) -> None:
    """Add and apply a Shrinkwrap modifier to conform mesh to body surface."""
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj

    mod = mesh_obj.modifiers.new(name="Shrinkwrap", type="SHRINKWRAP")
    mod.target = body_obj
    mod.wrap_method = "NEAREST_SURFACEPOINT"
    mod.offset = offset
    mod.wrap_mode = "OUTSIDE_SURFACE"

    bpy.ops.object.modifier_apply(modifier=mod.name)
    print(f"  Applied Shrinkwrap (offset={offset:.4f}m)")


# ---------------------------------------------------------------------------
# Auto-skinning
# ---------------------------------------------------------------------------

def _clear_skinning(mesh_obj: bpy.types.Object) -> None:
    """Remove all armature modifiers and vertex groups from mesh."""
    for mod in list(mesh_obj.modifiers):
        if mod.type == "ARMATURE":
            mesh_obj.modifiers.remove(mod)
    for vg in list(mesh_obj.vertex_groups):
        mesh_obj.vertex_groups.remove(vg)


def _has_nonzero_weights(mesh_obj: bpy.types.Object) -> bool:
    """Check if any vertex has a weight > 0.001."""
    if not mesh_obj.vertex_groups:
        return False
    for v in mesh_obj.data.vertices:
        for g in v.groups:
            if g.weight > 0.001:
                return True
    return False


def parent_with_automatic_weights(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
) -> bool:
    """Try Blender's bone-heat automatic weights. Returns True on success."""
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError:
        return False
    return _has_nonzero_weights(mesh_obj)


def parent_with_envelope_weights(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
) -> bool:
    """Fallback: parent with envelope-based weights. Returns True on success."""
    bpy.ops.object.mode_set(mode="OBJECT")

    # Clear previous parent keeping world transform
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    _clear_skinning(mesh_obj)

    # Create empty vertex groups for each deform bone
    for bone in armature_obj.data.bones:
        if bone.use_deform:
            mesh_obj.vertex_groups.new(name=bone.name)

    # Parent to armature (adds armature modifier automatically)
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.parent_set(type="ARMATURE")

    # Weight paint from bones
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    try:
        bpy.ops.paint.weight_from_bones(type="AUTOMATIC")
    except Exception:
        try:
            bpy.ops.paint.weight_from_bones(type="ENVELOPES")
        except Exception:
            pass
    bpy.ops.object.mode_set(mode="OBJECT")

    return _has_nonzero_weights(mesh_obj)


SLOT_BONE_FILTERS: dict[str, set[str]] = {
    "upper_body": {
        "Hips", "Spine", "Spine1", "Spine2", "Neck",
        "LeftShoulder", "RightShoulder", "LeftArm", "RightArm",
        "LeftForeArm", "RightForeArm",
    },
    "lower_body": {
        "Hips", "Spine",
        "LeftUpLeg", "RightUpLeg", "LeftLeg", "RightLeg",
        "LeftFoot", "RightFoot",
    },
    "helmet": {"Head", "HeadTop_End", "Neck"},
    "boots": {"LeftFoot", "RightFoot", "LeftToeBase", "RightToeBase", "LeftLeg", "RightLeg"},
    "gloves": {
        "LeftHand", "RightHand", "LeftForeArm", "RightForeArm",
        "LeftHandThumb1", "LeftHandThumb2", "LeftHandThumb3",
        "LeftHandIndex1", "LeftHandIndex2", "LeftHandIndex3",
        "LeftHandMiddle1", "LeftHandMiddle2", "LeftHandMiddle3",
        "LeftHandRing1", "LeftHandRing2", "LeftHandRing3",
        "LeftHandPinky1", "LeftHandPinky2", "LeftHandPinky3",
        "RightHandThumb1", "RightHandThumb2", "RightHandThumb3",
        "RightHandIndex1", "RightHandIndex2", "RightHandIndex3",
        "RightHandMiddle1", "RightHandMiddle2", "RightHandMiddle3",
        "RightHandRing1", "RightHandRing2", "RightHandRing3",
        "RightHandPinky1", "RightHandPinky2", "RightHandPinky3",
    },
}


def _bone_matches_filter(bone_name: str, allowed_suffixes: set[str]) -> bool:
    """Check if a bone name ends with one of the allowed suffixes (ignoring rig prefix)."""
    for suffix in allowed_suffixes:
        if bone_name.endswith(suffix):
            return True
    return False


def assign_proximity_weights(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
    weight_radius: float = 0.35,
    slot_type: str | None = None,
) -> None:
    """Last-resort fallback: assign vertex weights based on distance to bone centers.

    Uses a moderate power falloff with optional bone filtering by slot type to
    prevent irrelevant bones (e.g., fingers for upper_body) from stealing weight.
    """
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    _clear_skinning(mesh_obj)

    armature_obj.data.pose_position = "REST"
    bpy.context.view_layer.update()

    allowed = SLOT_BONE_FILTERS.get(slot_type) if slot_type else None

    # Build bone head positions (head_local is reliable; tail_local/length may be
    # in cm due to a Blender GLB importer quirk with scaled parent nodes).
    bone_heads: dict[str, Vector] = {}
    for bone in armature_obj.data.bones:
        bone_heads[bone.name] = armature_obj.matrix_world @ bone.head_local

    bone_vgs: list[tuple[bpy.types.VertexGroup, Vector, float]] = []
    for bone in armature_obj.data.bones:
        if not bone.use_deform:
            continue
        if allowed and not _bone_matches_filter(bone.name, allowed):
            continue
        head_world = bone_heads[bone.name]
        # Estimate true bone length from distance to child bone heads
        child_dists = []
        for child in bone.children:
            child_head = bone_heads.get(child.name)
            if child_head:
                child_dists.append((head_world - child_head).length)
        true_len = min(child_dists) if child_dists else 0.05
        vg = mesh_obj.vertex_groups.new(name=bone.name)
        bone_vgs.append((vg, head_world, true_len))

    if not bone_vgs:
        armature_obj.data.pose_position = "POSE"
        bpy.context.view_layer.update()
        return

    print(f"  Proximity weighting with {len(bone_vgs)} bones"
          f" (slot_type={slot_type}, filter={'yes' if allowed else 'no'})")

    mat = mesh_obj.matrix_world
    for v in mesh_obj.data.vertices:
        v_world = mat @ v.co
        influences: list[tuple[bpy.types.VertexGroup, float]] = []
        for vg, bone_center, bone_len in bone_vgs:
            dist = (v_world - bone_center).length
            effective_r = max(weight_radius, bone_len * 0.6)
            if dist < effective_r:
                falloff = max(0.0, 1.0 - dist / effective_r)
                w = falloff ** 4
                if w > 0.001:
                    influences.append((vg, w))

        influences.sort(key=lambda x: -x[1])
        top = influences[:4]
        total = sum(w for _, w in top)
        if total > 0:
            for vg, w in top:
                vg.add([v.index], w / total, "REPLACE")
        else:
            nearest_vg = min(bone_vgs, key=lambda bd: (v_world - bd[1]).length)[0]
            nearest_vg.add([v.index], 1.0, "REPLACE")

    # Set up parent + armature modifier
    mesh_obj.parent = armature_obj
    mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = armature_obj

    armature_obj.data.pose_position = "POSE"
    bpy.context.view_layer.update()
    print(f"  Assigned proximity weights (radius={weight_radius:.3f}m)")


# ---------------------------------------------------------------------------
# GLB export
# ---------------------------------------------------------------------------

def export_skinned_glb(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
    filepath: str,
    yup: bool = False,
) -> str:
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(filepath),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=yup,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=False,
        export_animations=False,
        export_materials="EXPORT",
    )
    return filepath


# ---------------------------------------------------------------------------
# Spec update
# ---------------------------------------------------------------------------

def build_spec_entry(
    slot_id: str,
    slot_name: str,
    slot_type: str,
    url: str | None,
    color: str | None,
    gender: str | None,
    equip_spec: dict[str, Any],
) -> dict[str, Any]:
    """Build a new equipment_spec.json entry for the fitted equipment."""
    config = SLOT_TYPE_CONFIG[slot_type]

    # Use bounds from the reference slot of the same type in the spec
    ref_slot = None
    for s in equip_spec["slots"]:
        if s["id"] == slot_type:
            ref_slot = s
            break

    bounds = ref_slot["bounds"] if ref_slot else {"z_min": 0, "z_max": 1.9, "radius": 0.25, "weight_radius": 0.35}

    entry: dict[str, Any] = {
        "id": slot_id,
        "name": slot_name,
        "bilateral": config["bilateral"],
        "color": color or config["default_color"],
        "bones": config["bones"],
        "bounds": bounds,
        "rules": {},
        "hides_body_regions": config["hides_body_regions"],
        "mesh_type": config["mesh_type"],
        "mesh_params": {},
    }

    if gender:
        entry["gender"] = gender
    if url:
        entry["url"] = url

    return entry


def update_equip_spec(
    spec_path: str,
    entry: dict[str, Any],
) -> None:
    """Add or update an entry in equipment_spec.json."""
    spec = load_json(spec_path)
    existing_idx = None
    for i, s in enumerate(spec["slots"]):
        if s["id"] == entry["id"]:
            existing_idx = i
            break

    if existing_idx is not None:
        spec["slots"][existing_idx] = entry
        print(f"  Updated existing slot '{entry['id']}' in spec")
    else:
        spec["slots"].append(entry)
        print(f"  Added new slot '{entry['id']}' to spec")

    save_json(spec, spec_path)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def _load_rig_from_glb(glb_path: str) -> bpy.types.Object | None:
    """Import a character GLB and extract its armature for rigging equipment.

    After import, all parent transforms (including the 0.01 cm→m scale node
    common in Mixamo GLBs) are applied so the armature bones sit at their
    actual world-space meter positions. This keeps the equipment mesh at
    the same scale as the slot dimensions and the viewer's coordinate system.
    """
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = import_glb(glb_path)

    armature_obj = None
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            armature_obj = obj
            break

    if not armature_obj:
        return None

    # Apply all transforms on the armature's parent chain so bones end up
    # at their world-space positions (meters).  This flattens any scale
    # nodes (e.g. the 0.01 root added by FBX→GLB conversion).
    bpy.ops.object.select_all(action="DESELECT")
    parent = armature_obj.parent
    while parent:
        parent.select_set(True)
        bpy.context.view_layer.objects.active = parent
        parent = parent.parent

    if bpy.context.selected_objects:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Remove character meshes (we only need the armature)
    meshes_to_remove = [o for o in bpy.data.objects if o.type == "MESH"]
    for m in meshes_to_remove:
        try:
            bpy.data.objects.remove(m, do_unlink=True)
        except ReferenceError:
            pass

    print(f"  Armature bone sample positions (world):")
    for bone in list(armature_obj.data.bones)[:3]:
        print(f"    {bone.name}: head={bone.head_local[:]}")

    return armature_obj


def fit_equipment(
    rig_blend: str | None,
    rig_glb: str | None,
    mesh_path: str,
    slot_type: str,
    slot_id: str,
    slot_name: str,
    equip_spec_path: str,
    dimensions_path: str | None,
    body_mesh_path: str | None,
    output_dir: str,
    game_dir: str | None,
    shrinkwrap_offset: float | None,
    no_shrinkwrap: bool,
    url: str | None,
    color: str | None,
    gender: str | None,
    update_spec: bool,
    scale: float,
    fix_facing: bool,
) -> str | None:
    """Run the full fitting pipeline."""
    config = SLOT_TYPE_CONFIG[slot_type]

    print(f"=== Equipment Fitter ===")
    print(f"  Slot type: {slot_type}")
    print(f"  Slot ID:   {slot_id}")
    print(f"  Mesh:      {mesh_path}")

    # Load rig from GLB (preferred) or .blend file
    armature_obj = None
    if rig_glb:
        print(f"  Loading rig from GLB: {rig_glb}")
        armature_obj = _load_rig_from_glb(rig_glb)
        if not armature_obj:
            print("ERROR: No armature found in the GLB file.")
            return None
    elif rig_blend:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(rig_blend))
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE":
                armature_obj = obj
                break
        if not armature_obj:
            print("ERROR: No armature found in the .blend file.")
            return None
    else:
        print("ERROR: No rig source provided (--rig-blend or --rig-glb required).")
        return None

    bpy.context.view_layer.objects.active = armature_obj
    print(f"  Armature: {armature_obj.name}")
    print(f"  Armature bones: {len(armature_obj.data.bones)}")

    # Import the equipment mesh
    imported = import_glb(mesh_path)
    mesh_objs = collect_mesh_objects(imported)

    if not mesh_objs:
        print(f"  ERROR: No mesh found in {mesh_path}")
        return None

    for m in mesh_objs:
        clear_mesh_rigging(m)

    combined = join_meshes(mesh_objs, f"equip_{slot_id}")
    print(f"  Mesh vertices: {len(combined.data.vertices)}")

    # Fix facing if needed (Y-up GLBs from Meshy AI)
    if fix_facing:
        combined.rotation_euler.x = math.pi / 2
        bpy.ops.object.select_all(action="DESELECT")
        combined.select_set(True)
        bpy.context.view_layer.objects.active = combined
        bpy.ops.object.transform_apply(rotation=True)
        print("  Applied Y-up to Z-up rotation")

    # Apply user-specified scale
    if scale != 1.0:
        combined.scale = (scale, scale, scale)
        bpy.ops.object.select_all(action="DESELECT")
        combined.select_set(True)
        bpy.context.view_layer.objects.active = combined
        bpy.ops.object.transform_apply(scale=True)
        print(f"  Applied scale: {scale}")

    # Scale and position to slot dimensions
    if dimensions_path and os.path.isfile(dimensions_path):
        dims = load_json(dimensions_path)
        slot_dims = dims.get("slots", {}).get(slot_type)
        if slot_dims:
            bbox = slot_dims.get("bones_bounding_box", slot_dims.get("mesh_bounding_box"))
            center = bbox.get("center", [0, 0, 1.0])
            scale_to_fit(combined, bbox, center)
        else:
            print(f"  Warning: no dimensions for slot type '{slot_type}', skipping auto-scale")
    else:
        equip_spec = load_json(equip_spec_path)
        ref_slot = None
        for s in equip_spec["slots"]:
            if s["id"] == slot_type:
                ref_slot = s
                break
        if ref_slot:
            bounds = ref_slot["bounds"]
            z_center = (bounds["z_min"] + bounds["z_max"]) / 2.0
            center = [0.0, 0.0, z_center]
            size = [
                bounds["radius"] * 2,
                bounds["radius"] * 2,
                bounds["z_max"] - bounds["z_min"],
            ]
            scale_to_fit(combined, {"size": size}, center)

    # Shrinkwrap to body mesh
    use_shrinkwrap = config["shrinkwrap"] and not no_shrinkwrap
    if use_shrinkwrap and body_mesh_path and os.path.isfile(body_mesh_path):
        body_imported = import_glb(body_mesh_path)
        body_meshes = [o for o in body_imported if o.type == "MESH"]
        if body_meshes:
            body_obj = body_meshes[0]
            offset = shrinkwrap_offset if shrinkwrap_offset is not None else config["shrinkwrap_offset"]
            apply_shrinkwrap(combined, body_obj, offset)
            bpy.data.objects.remove(body_obj, do_unlink=True)
        else:
            print("  Warning: no mesh in body GLB, skipping shrinkwrap")
    elif use_shrinkwrap:
        print("  Warning: shrinkwrap requested but no body mesh provided, skipping")

    # Auto-skin (3-tier fallback: heat → envelope → proximity)
    print("  Skinning with automatic weights...")
    skinned = parent_with_automatic_weights(combined, armature_obj)
    if skinned:
        print("  Bone-heat weights applied successfully")
    else:
        _clear_skinning(combined)
        print("  Bone-heat failed, trying envelope weights...")
        skinned = parent_with_envelope_weights(combined, armature_obj)
        if skinned:
            print("  Envelope weights applied successfully")
        else:
            print("  Envelope weights failed, using proximity-based weights...")
            assign_proximity_weights(combined, armature_obj, weight_radius=0.35, slot_type=slot_type)

    # Export Y-up (standard glTF convention — viewer applies its own Z-up correction)
    out_path = os.path.join(output_dir, f"{slot_id}.glb")
    export_skinned_glb(combined, armature_obj, out_path, yup=True)
    print(f"  Exported (Y-up): {out_path}")

    # Export Y-up (for game engines)
    if game_dir:
        game_path = os.path.join(game_dir, f"{slot_id}.glb")
        export_skinned_glb(combined, armature_obj, game_path, yup=True)
        print(f"  Exported (Y-up): {game_path}")

    # Update equipment spec
    if update_spec:
        equip_spec = load_json(equip_spec_path)
        entry = build_spec_entry(
            slot_id, slot_name, slot_type, url, color, gender, equip_spec,
        )
        update_equip_spec(equip_spec_path, entry)

    bpy.data.objects.remove(combined, do_unlink=True)

    print(f"=== Done ===")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Equipment Fitter")
    rig_group = parser.add_mutually_exclusive_group(required=True)
    rig_group.add_argument("--rig-blend", default=None, help="Path to the rig .blend file")
    rig_group.add_argument("--rig-glb", default=None, help="Path to character GLB (preferred — matches viewer bone inverses)")
    parser.add_argument("--mesh", required=True, help="Path to raw equipment GLB")
    parser.add_argument(
        "--slot-type", required=True,
        choices=list(SLOT_TYPE_CONFIG.keys()),
        help="Equipment slot type",
    )
    parser.add_argument("--slot-id", required=True, help="Unique ID for this equipment piece")
    parser.add_argument("--slot-name", default=None, help="Display name (defaults to slot-id)")
    parser.add_argument("--equip-spec", required=True, help="Path to equipment_spec.json")
    parser.add_argument("--dimensions", default=None, help="Path to slot_dimensions.json")
    parser.add_argument("--body-mesh", default=None, help="Path to body GLB for shrinkwrap")
    parser.add_argument("--out", required=True, help="Output directory for Z-up GLBs")
    parser.add_argument("--game-out", default=None, help="Output directory for Y-up GLBs")
    parser.add_argument(
        "--shrinkwrap-offset", type=float, default=None,
        help="Override shrinkwrap offset (meters)",
    )
    parser.add_argument("--no-shrinkwrap", action="store_true", help="Skip shrinkwrap even if slot type defaults to it")
    parser.add_argument("--url", default=None, help="URL for the equipment mesh (stored in spec)")
    parser.add_argument("--color", default=None, help="Hex color for spec entry (e.g. #ff0000)")
    parser.add_argument("--gender", default=None, choices=["male", "female"], help="Gender restriction")
    parser.add_argument("--update-spec", action="store_true", help="Add/update entry in equipment_spec.json")
    parser.add_argument("--scale", type=float, default=1.0, help="Uniform scale factor before fitting")
    parser.add_argument("--no-fix-facing", action="store_true", help="Skip Y-up to Z-up rotation")

    args = parser.parse_args(argv)
    if not args.slot_name:
        args.slot_name = args.slot_id.replace("_", " ").title()
    return args


def main() -> None:
    args = parse_args()

    fit_equipment(
        rig_blend=args.rig_blend,
        rig_glb=args.rig_glb,
        mesh_path=args.mesh,
        slot_type=args.slot_type,
        slot_id=args.slot_id,
        slot_name=args.slot_name,
        equip_spec_path=args.equip_spec,
        dimensions_path=args.dimensions,
        body_mesh_path=args.body_mesh,
        output_dir=args.out,
        game_dir=args.game_out,
        shrinkwrap_offset=args.shrinkwrap_offset,
        no_shrinkwrap=args.no_shrinkwrap,
        url=args.url,
        color=args.color,
        gender=args.gender,
        update_spec=args.update_spec,
        scale=args.scale,
        fix_facing=not args.no_fix_facing,
    )


if __name__ == "__main__":
    main()
