"""Body Shell Extractor — generates conforming equipment meshes from a character.

Extracts per-slot submeshes from a Mixamo-rigged body mesh, offsets them
outward with Blender's Solidify modifier, and exports rigged GLBs that
perfectly match the character's topology.  The resulting shells serve as
base geometry for AI texturing (e.g. Meshy) — because they are derived from
the character mesh itself, there is zero clipping or gap.

Pipeline:
    1. Import base mesh, rename vertex groups (Mixamo → rig names)
    2. Dominant-slot face assignment (each face → highest-scoring slot)
    3. Neighbor-majority smoothing (eliminates jagged boundaries)
    4. Overlap expansion (lets specified slot pairs share shin/waist regions)
    5. Per-slot extraction, Solidify, spike removal, export as skinned GLB

Configuration (top of file):
    SLOT_BONES               — rig bones per equipment slot
    SHELL_THICKNESS          — outward offset in meters per slot
    OVERLAP_PAIRS            — slot pairs allowed to share faces
    OVERLAP_WEIGHT_THRESHOLD — min bone weight for overlap expansion

Usage (headless Blender):
    blender --background --python equipment/factory/body_shell_extractor.py -- \\
        --rig-blend rig/output/rig.blend \\
        --body-glb  rig/CharacterMesh/BaseFemale.glb \\
        --out       equipment/output/shells/ \\
        --thickness 0          # 0 = use per-slot SHELL_THICKNESS defaults \\
        --slots upper_body,lower_body,boots,gloves,head

After extraction, copy shells to the viewer:
    cp equipment/output/shells/shell_*.glb viewer/public/equipment/
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from typing import Any

import bpy
import bmesh


# ---------------------------------------------------------------------------
# Slot bone configuration — maps each equipment slot to the rig bone names
# it covers. These match the bone names in rig.blend / rig_spec.json.
# ---------------------------------------------------------------------------

SLOT_BONES: dict[str, list[str]] = {
    "head": [
        "head",
        "neck_01",
        "spine_03",
        "jaw",
        "eye_L",
        "eye_R",
    ],
    "upper_body": [
        "pelvis",
        "spine_01",
        "spine_02",
        "spine_03",
        "clavicle_L",
        "clavicle_R",
        "upperarm_L",
        "upperarm_R",
        "lowerarm_L",
        "lowerarm_R",
    ],
    "gloves": [
        "lowerarm_L",
        "lowerarm_R",
        "hand_L",
        "thumb_01_L", "thumb_02_L", "thumb_03_L",
        "index_01_L", "index_02_L", "index_03_L",
        "middle_01_L", "middle_02_L", "middle_03_L",
        "ring_01_L", "ring_02_L", "ring_03_L",
        "pinky_01_L", "pinky_02_L", "pinky_03_L",
        "hand_R",
        "thumb_01_R", "thumb_02_R", "thumb_03_R",
        "index_01_R", "index_02_R", "index_03_R",
        "middle_01_R", "middle_02_R", "middle_03_R",
        "ring_01_R", "ring_02_R", "ring_03_R",
        "pinky_01_R", "pinky_02_R", "pinky_03_R",
    ],
    "lower_body": [
        "pelvis",
        "thigh_L",
        "thigh_R",
        "shin_L",
        "shin_R",
        "foot_L",
        "foot_R",
        "toe_L",
        "toe_R",
    ],
    "boots": [
        "shin_L",
        "shin_R",
        "foot_L",
        "foot_R",
        "toe_L",
        "toe_R",
    ],
}

# Per-slot outward offset (meters).  Larger values make the equipment
# visually bulkier.  Set to 0 to skip Solidify for a slot (flat shell).
SHELL_THICKNESS: dict[str, float] = {
    "head": 0.005,
    "upper_body": 0.005,
    "lower_body": 0.005,
    "gloves": 0.03,
    "boots": 0.06,
}

# Slot pairs that share faces in their overlap region.  Each member
# expands into the other's territory wherever it has bone weight above
# OVERLAP_WEIGHT_THRESHOLD.  Use this for pants/boots or shirt/pants
# where the outer piece (higher thickness) should sit on top.
OVERLAP_PAIRS: list[tuple[str, str]] = [
    ("lower_body", "boots"),
    ("upper_body", "lower_body"),
]

# Lower = more overlap (faces claimed further from slot's bone centers).
OVERLAP_WEIGHT_THRESHOLD: float = 0.01

ALL_SLOT_TYPES = list(SLOT_BONES.keys())


# ---------------------------------------------------------------------------
# Mixamo → rig bone name mapping.
# Maps Mixamo vertex group names (with "mixamorig:" prefix) to the
# generic bone names used in rig.blend / rig_spec.json.
# ---------------------------------------------------------------------------

MIXAMO_TO_RIG: dict[str, str] = {
    "mixamorig:Hips": "pelvis",
    "mixamorig:Spine": "spine_01",
    "mixamorig:Spine1": "spine_02",
    "mixamorig:Spine2": "spine_03",
    "mixamorig:Neck": "neck_01",
    "mixamorig:Head": "head",
    "mixamorig:LeftShoulder": "clavicle_L",
    "mixamorig:RightShoulder": "clavicle_R",
    "mixamorig:LeftArm": "upperarm_L",
    "mixamorig:RightArm": "upperarm_R",
    "mixamorig:LeftForeArm": "lowerarm_L",
    "mixamorig:RightForeArm": "lowerarm_R",
    "mixamorig:LeftHand": "hand_L",
    "mixamorig:RightHand": "hand_R",
    "mixamorig:LeftUpLeg": "thigh_L",
    "mixamorig:RightUpLeg": "thigh_R",
    "mixamorig:LeftLeg": "shin_L",
    "mixamorig:RightLeg": "shin_R",
    "mixamorig:LeftFoot": "foot_L",
    "mixamorig:RightFoot": "foot_R",
    "mixamorig:LeftToeBase": "toe_L",
    "mixamorig:RightToeBase": "toe_R",
    "mixamorig:LeftHandThumb1": "thumb_01_L",
    "mixamorig:LeftHandThumb2": "thumb_02_L",
    "mixamorig:LeftHandThumb3": "thumb_03_L",
    "mixamorig:LeftHandIndex1": "index_01_L",
    "mixamorig:LeftHandIndex2": "index_02_L",
    "mixamorig:LeftHandIndex3": "index_03_L",
    "mixamorig:LeftHandMiddle1": "middle_01_L",
    "mixamorig:LeftHandMiddle2": "middle_02_L",
    "mixamorig:LeftHandMiddle3": "middle_03_L",
    "mixamorig:LeftHandRing1": "ring_01_L",
    "mixamorig:LeftHandRing2": "ring_02_L",
    "mixamorig:LeftHandRing3": "ring_03_L",
    "mixamorig:LeftHandPinky1": "pinky_01_L",
    "mixamorig:LeftHandPinky2": "pinky_02_L",
    "mixamorig:LeftHandPinky3": "pinky_03_L",
    "mixamorig:RightHandThumb1": "thumb_01_R",
    "mixamorig:RightHandThumb2": "thumb_02_R",
    "mixamorig:RightHandThumb3": "thumb_03_R",
    "mixamorig:RightHandIndex1": "index_01_R",
    "mixamorig:RightHandIndex2": "index_02_R",
    "mixamorig:RightHandIndex3": "index_03_R",
    "mixamorig:RightHandMiddle1": "middle_01_R",
    "mixamorig:RightHandMiddle2": "middle_02_R",
    "mixamorig:RightHandMiddle3": "middle_03_R",
    "mixamorig:RightHandRing1": "ring_01_R",
    "mixamorig:RightHandRing2": "ring_02_R",
    "mixamorig:RightHandRing3": "ring_03_R",
    "mixamorig:RightHandPinky1": "pinky_01_R",
    "mixamorig:RightHandPinky2": "pinky_02_R",
    "mixamorig:RightHandPinky3": "pinky_03_R",
    "mixamorig:Jaw": "jaw",
    "mixamorig:LeftEye": "eye_L",
    "mixamorig:RightEye": "eye_R",
    "mixamorig:HeadTop_End": "head",
}


# ---------------------------------------------------------------------------
# Import / mesh helpers
# ---------------------------------------------------------------------------

def import_glb(filepath: str) -> list[bpy.types.Object]:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(filepath))
    after = set(bpy.data.objects)
    return list(after - before)


def find_armature_in(objects: list[bpy.types.Object]) -> bpy.types.Object | None:
    for obj in objects:
        if obj.type == "ARMATURE":
            return obj
        for child in obj.children_recursive:
            if child.type == "ARMATURE":
                return child
    return None


def collect_meshes(objects: list[bpy.types.Object]) -> list[bpy.types.Object]:
    meshes: list[bpy.types.Object] = []
    for obj in objects:
        if obj.type == "MESH":
            meshes.append(obj)
        for child in obj.children_recursive:
            if child.type == "MESH" and child not in meshes:
                meshes.append(child)
    return meshes


def rename_vertex_groups(
    mesh_obj: bpy.types.Object,
    name_map: dict[str, str],
) -> int:
    """Rename vertex groups using a name mapping. Returns count of renamed groups."""
    renamed = 0
    for vg in mesh_obj.vertex_groups:
        new_name = name_map.get(vg.name)
        if new_name and new_name != vg.name:
            vg.name = new_name
            renamed += 1
    return renamed


# ---------------------------------------------------------------------------
# Face selection by bone weights
# ---------------------------------------------------------------------------

def get_slot_vgroup_indices(mesh_obj: bpy.types.Object, slot_type: str) -> set[int]:
    bone_names = set(SLOT_BONES[slot_type])
    indices: set[int] = set()
    for vg in mesh_obj.vertex_groups:
        if vg.name in bone_names:
            indices.add(vg.index)
    return indices


def assign_faces_to_slots(
    mesh_obj: bpy.types.Object,
    slot_types: list[str],
    weight_threshold: float = 0.1,
) -> dict[int, str]:
    """Assign each face to exactly one slot based on dominant bone weight.

    For every face, the total bone weight per slot is summed across the face's
    vertices.  The face is assigned to whichever slot scores highest.  This
    guarantees non-overlapping, seamless coverage between adjacent slots.
    """
    all_slot_vg: dict[str, set[int]] = {}
    for slot_type in slot_types:
        all_slot_vg[slot_type] = get_slot_vgroup_indices(mesh_obj, slot_type)

    mesh_data = mesh_obj.data

    vert_slot_weights: dict[int, dict[str, float]] = {}
    for v in mesh_data.vertices:
        sw: dict[str, float] = {}
        for slot_type in slot_types:
            total = 0.0
            for g in v.groups:
                if g.group in all_slot_vg[slot_type]:
                    total += g.weight
            if total > weight_threshold:
                sw[slot_type] = total
        vert_slot_weights[v.index] = sw

    face_assignments: dict[int, str] = {}
    for face in mesh_data.polygons:
        slot_scores: dict[str, float] = {}
        for slot_type in slot_types:
            score = sum(
                vert_slot_weights[vi].get(slot_type, 0.0)
                for vi in face.vertices
            )
            if score > 0:
                slot_scores[slot_type] = score
        if slot_scores:
            face_assignments[face.index] = max(slot_scores, key=slot_scores.get)

    counts: dict[str, int] = {}
    for slot in face_assignments.values():
        counts[slot] = counts.get(slot, 0) + 1
    unassigned = len(mesh_data.polygons) - len(face_assignments)
    print(f"  Face assignments (raw): {counts}, unassigned: {unassigned}")

    return face_assignments


def smooth_face_assignments(
    mesh_obj: bpy.types.Object,
    assignments: dict[int, str],
    iterations: int = 5,
) -> dict[int, str]:
    """Remove jagged boundary spikes by flipping outlier faces to neighbor majority.

    Builds a face adjacency graph (faces sharing an edge are neighbors), then
    iteratively reassigns any face whose slot differs from ≥60 % of its
    neighbors.  This produces smooth, clean boundary lines between all slots.
    """
    mesh_data = mesh_obj.data

    edge_to_faces: dict[tuple[int, int], list[int]] = {}
    for face in mesh_data.polygons:
        for ek in face.edge_keys:
            edge_to_faces.setdefault(ek, []).append(face.index)

    face_neighbors: dict[int, set[int]] = {}
    for face in mesh_data.polygons:
        neighbors: set[int] = set()
        for ek in face.edge_keys:
            for fi in edge_to_faces[ek]:
                if fi != face.index:
                    neighbors.add(fi)
        face_neighbors[face.index] = neighbors

    result = dict(assignments)
    total_flipped = 0
    for iteration in range(iterations):
        changes = 0
        new_result = dict(result)
        for fi, slot in result.items():
            neighbors = face_neighbors.get(fi, set())
            if not neighbors:
                continue
            slot_counts: dict[str, int] = {}
            for ni in neighbors:
                ns = result.get(ni)
                if ns:
                    slot_counts[ns] = slot_counts.get(ns, 0) + 1
            if not slot_counts:
                continue
            majority = max(slot_counts, key=slot_counts.get)
            total_n = sum(slot_counts.values())
            if majority != slot and slot_counts[majority] >= total_n * 0.6:
                new_result[fi] = majority
                changes += 1
        result = new_result
        total_flipped += changes
        if changes == 0:
            break

    if total_flipped > 0:
        counts: dict[str, int] = {}
        for slot in result.values():
            counts[slot] = counts.get(slot, 0) + 1
        print(f"  Face assignments (smoothed, {total_flipped} flipped): {counts}")

    return result


def select_slot_faces(
    mesh_obj: bpy.types.Object,
    slot_type: str,
    weight_threshold: float = 0.1,
    face_assignments: dict[int, str] | None = None,
) -> int:
    """Select faces belonging to a slot.

    When *face_assignments* is provided (from ``assign_faces_to_slots``),
    selects only the pre-assigned faces for clean, non-overlapping boundaries.
    Falls back to the per-vertex weight approach otherwise.
    """
    mesh_data = mesh_obj.data

    bpy.ops.object.mode_set(mode="OBJECT")
    for face in mesh_data.polygons:
        face.select = False
    for edge in mesh_data.edges:
        edge.select = False
    for vert in mesh_data.vertices:
        vert.select = False

    if face_assignments is not None:
        selected_count = 0
        for face in mesh_data.polygons:
            if face_assignments.get(face.index) == slot_type:
                face.select = True
                selected_count += 1
        return selected_count

    slot_vg_indices = get_slot_vgroup_indices(mesh_obj, slot_type)
    if not slot_vg_indices:
        print(f"  Warning: no matching vertex groups for slot '{slot_type}'")
        return 0

    vert_weights: dict[int, float] = {}
    for v in mesh_data.vertices:
        total = 0.0
        for g in v.groups:
            if g.group in slot_vg_indices:
                total += g.weight
        vert_weights[v.index] = total

    selected_count = 0
    for face in mesh_data.polygons:
        include = any(
            vert_weights.get(vi, 0.0) > weight_threshold
            for vi in face.vertices
        )
        face.select = include
        if include:
            selected_count += 1

    return selected_count


# ---------------------------------------------------------------------------
# Mesh extraction and solidify
# ---------------------------------------------------------------------------

def _ensure_object_mode(obj: bpy.types.Object) -> None:
    if bpy.context.active_object and bpy.context.active_object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _remove_spike_vertices(
    mesh_obj: bpy.types.Object,
    max_edge_ratio: float = 3.0,
) -> int:
    """Remove vertices connected to abnormally long edges (post-solidify spikes).

    Computes the median edge length, then deletes any vertex that has an edge
    longer than median * max_edge_ratio.  Returns count of removed vertices.
    """
    import bmesh as _bm

    _ensure_object_mode(mesh_obj)
    bm = _bm.new()
    bm.from_mesh(mesh_obj.data)
    bm.edges.ensure_lookup_table()

    if not bm.edges:
        bm.free()
        return 0

    lengths = sorted(e.calc_length() for e in bm.edges)
    median_len = lengths[len(lengths) // 2]
    threshold = median_len * max_edge_ratio

    spike_verts: set = set()
    for e in bm.edges:
        if e.calc_length() > threshold:
            for v in e.verts:
                spike_verts.add(v)

    if spike_verts:
        _bm.ops.delete(bm, geom=list(spike_verts), context="VERTS")
        bm.to_mesh(mesh_obj.data)
        mesh_obj.data.update()
        print(f"  Removed {len(spike_verts)} spike vertices "
              f"(threshold={threshold:.5f}m, median={median_len:.5f}m)")

    bm.free()
    return len(spike_verts)


def extract_slot_shell(
    body_mesh: bpy.types.Object,
    slot_type: str,
    thickness: float,
    weight_threshold: float,
    face_assignments: dict[int, str] | None = None,
) -> bpy.types.Object | None:
    """Extract a slot region from the body mesh and apply solidify."""
    _ensure_object_mode(body_mesh)

    bpy.ops.object.duplicate()
    shell = bpy.context.active_object
    shell.name = f"shell_{slot_type}"

    if shell.parent:
        world_mat = shell.matrix_world.copy()
        shell.parent = None
        shell.matrix_world = world_mat
    for mod in list(shell.modifiers):
        if mod.type == "ARMATURE":
            shell.modifiers.remove(mod)

    selected = select_slot_faces(
        shell, slot_type, weight_threshold,
        face_assignments=face_assignments,
    )
    if selected == 0:
        print(f"  No faces selected for slot '{slot_type}', skipping")
        bpy.data.objects.remove(shell, do_unlink=True)
        return None

    total_faces = len(shell.data.polygons)
    print(f"  Selected {selected}/{total_faces} faces for {slot_type}")

    _ensure_object_mode(shell)
    bpy.ops.object.mode_set(mode="EDIT")

    bpy.ops.mesh.select_all(action="INVERT")
    bpy.ops.mesh.delete(type="FACE")

    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.delete_loose(use_verts=True, use_edges=True, use_faces=False)

    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0001)

    bpy.ops.mesh.normals_make_consistent(inside=False)

    bpy.ops.object.mode_set(mode="OBJECT")

    remaining = len(shell.data.polygons)
    print(f"  Shell mesh: {remaining} faces, {len(shell.data.vertices)} vertices")

    if thickness > 0:
        _ensure_object_mode(shell)

        mod = shell.modifiers.new("Solidify", type="SOLIDIFY")
        mod.thickness = thickness
        mod.offset = -1.0
        mod.use_even_offset = True
        mod.use_quality_normals = True
        mod.thickness_clamp = 2.0

        bpy.ops.object.modifier_apply(modifier=mod.name)

        _ensure_object_mode(shell)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.0002)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")

        _remove_spike_vertices(shell, max_edge_ratio=6.0)

        final_faces = len(shell.data.polygons)
        final_verts = len(shell.data.vertices)
        print(f"  After Solidify: {final_faces} faces, {final_verts} vertices "
              f"(thickness={thickness:.4f}m)")

    return shell


# ---------------------------------------------------------------------------
# Armature parenting and export
# ---------------------------------------------------------------------------

def parent_to_armature(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
) -> None:
    mesh_obj.parent = armature_obj
    has_armature_mod = any(m.type == "ARMATURE" for m in mesh_obj.modifiers)
    if not has_armature_mod:
        mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = armature_obj


def export_skinned_glb(
    mesh_obj: bpy.types.Object,
    armature_obj: bpy.types.Object,
    filepath: str,
    yup: bool = False,
) -> str:
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    # Purge orphan mesh data blocks to prevent stray geometry in exports
    for mesh_data in list(bpy.data.meshes):
        if mesh_data.users == 0:
            bpy.data.meshes.remove(mesh_data)

    # Hide all non-export objects to prevent inclusion
    for obj in bpy.data.objects:
        if obj not in (mesh_obj, armature_obj):
            obj.hide_set(True)
            obj.hide_render = True

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
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
    )

    # Unhide objects for subsequent operations
    for obj in bpy.data.objects:
        obj.hide_set(False)
        obj.hide_render = False

    return filepath


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def extract_shells(
    rig_blend: str,
    body_glb: str,
    output_dir: str,
    slot_types: list[str],
    thickness: float,
    weight_threshold: float,
    game_dir: str | None,
) -> list[str]:
    """Run the full shell extraction pipeline."""
    print("=== Body Shell Extractor ===")
    print(f"  Rig:       {rig_blend}")
    print(f"  Body:      {body_glb}")
    print(f"  Output:    {output_dir}")
    print(f"  Slots:     {', '.join(slot_types)}")
    print(f"  Thickness: {thickness}m (0 = per-slot defaults)")
    print(f"  Threshold: {weight_threshold}")

    # ---- Step 1: Import body GLB into a clean scene ----
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = import_glb(body_glb)

    imported_armature = find_armature_in(imported)
    meshes = collect_meshes(imported)

    # Filter out debug/placeholder meshes (like Icospheres)
    body_meshes = [m for m in meshes if len(m.data.vertices) > 100]
    if not body_meshes:
        body_meshes = meshes

    if not body_meshes:
        print("ERROR: No mesh found in body GLB.")
        return []

    # Unparent from any imported armature
    for m in body_meshes:
        if m.parent:
            world_mat = m.matrix_world.copy()
            m.parent = None
            m.matrix_world = world_mat
        for mod in list(m.modifiers):
            if mod.type == "ARMATURE":
                m.modifiers.remove(mod)

    # Join into single mesh
    if len(body_meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in body_meshes:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = body_meshes[0]
        bpy.ops.object.join()
        body_mesh = bpy.context.active_object
    else:
        body_mesh = body_meshes[0]
    body_mesh.name = "body_for_extraction"

    # Apply transforms
    bpy.ops.object.select_all(action="DESELECT")
    body_mesh.select_set(True)
    bpy.context.view_layer.objects.active = body_mesh
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    vg_names = [vg.name for vg in body_mesh.vertex_groups]
    print(f"  Body mesh: {len(body_mesh.data.vertices)} verts, "
          f"{len(body_mesh.data.polygons)} faces, "
          f"{len(vg_names)} vertex groups")

    if not vg_names:
        print("  ERROR: Body mesh has no vertex groups. "
              "Use a skinned GLB (e.g. rig/CharacterMesh/BaseFemale.glb).")
        return []

    # ---- Step 2: Rename vertex groups from Mixamo to rig names ----
    is_mixamo = any("mixamorig" in vg for vg in vg_names)
    if is_mixamo:
        renamed = rename_vertex_groups(body_mesh, MIXAMO_TO_RIG)
        vg_names = [vg.name for vg in body_mesh.vertex_groups]
        print(f"  Renamed {renamed} vertex groups (Mixamo → rig names)")
    print(f"  Vertex groups: {', '.join(vg_names[:10])}"
          f"{'...' if len(vg_names) > 10 else ''}")

    # Weight diagnostic
    nonzero = sum(
        1 for v in body_mesh.data.vertices
        if any(g.weight > 0.001 for g in v.groups)
    )
    print(f"  Vertices with weights: {nonzero}/{len(body_mesh.data.vertices)}")

    # ---- Step 3: Load rig armature from .blend ----
    # Delete everything except the body mesh (imported armatures, Empties, etc.)
    objs_to_remove = [
        o for o in bpy.data.objects
        if o != body_mesh
    ]
    for obj in objs_to_remove:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except ReferenceError:
            pass

    # Append armature from rig.blend
    with bpy.data.libraries.load(os.path.abspath(rig_blend)) as (data_from, data_to):
        data_to.objects = list(data_from.objects)

    armature_obj = None
    for obj in data_to.objects:
        if obj is None:
            continue
        bpy.context.collection.objects.link(obj)
        if obj.type == "ARMATURE" and armature_obj is None:
            armature_obj = obj
        elif obj.type == "MESH":
            # Remove stray meshes appended from .blend (e.g. debug Icospheres)
            bpy.data.objects.remove(obj, do_unlink=True)

    if not armature_obj:
        print("ERROR: No armature found in rig .blend file.")
        return []

    print(f"  Armature: {armature_obj.name} ({len(armature_obj.data.bones)} bones)")

    # ---- Step 4: Parent mesh to rig armature ----
    parent_to_armature(body_mesh, armature_obj)
    print("  Parented body mesh to rig armature")

    # Final cleanup: remove any stray objects (e.g. Icosphere from source GLB)
    stray = [o for o in bpy.data.objects if o not in (body_mesh, armature_obj)]
    for obj in stray:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except ReferenceError:
            pass
    if stray:
        print(f"  Cleaned up {len(stray)} stray object(s)")

    # Aggressively remove orphan data blocks — especially stray mesh data from
    # the source GLB (e.g. Icosphere debug mesh).
    keep_meshes = {body_mesh.data.name}
    for mesh_data in list(bpy.data.meshes):
        if mesh_data.name not in keep_meshes:
            bpy.data.meshes.remove(mesh_data, do_unlink=True)
    for _ in range(3):
        bpy.ops.outliner.orphans_purge(
            do_local_ids=True, do_linked_ids=True, do_recursive=True
        )

    os.makedirs(output_dir, exist_ok=True)
    if game_dir:
        os.makedirs(game_dir, exist_ok=True)

    # ---- Step 5: Pre-compute dominant-slot face assignments ----
    valid_slots = [s for s in slot_types if s in SLOT_BONES]
    print(f"\n  Computing dominant-slot face assignments for {len(valid_slots)} slots...")
    face_assignments = assign_faces_to_slots(body_mesh, valid_slots, weight_threshold)
    face_assignments = smooth_face_assignments(body_mesh, face_assignments)

    # ---- Step 5b: Expand overlap pairs ----
    # Overlap pairs (e.g. lower_body + boots) share faces in their overlap
    # region so both meshes cover the area (boots sit on top via thickness).
    # Each slot is expanded into its partner's territory wherever it still has
    # meaningful bone weight, keeping dominant boundaries clean elsewhere.
    slot_face_views: dict[str, dict[int, str]] = {s: face_assignments for s in valid_slots}

    for s1, s2 in OVERLAP_PAIRS:
        if s1 not in valid_slots or s2 not in valid_slots:
            continue
        s1_vg = get_slot_vgroup_indices(body_mesh, s1)
        s2_vg = get_slot_vgroup_indices(body_mesh, s2)
        s1_view = dict(face_assignments)
        s2_view = dict(face_assignments)
        s1_gained = 0
        s2_gained = 0

        for face in body_mesh.data.polygons:
            assigned = face_assignments.get(face.index)
            if assigned == s2:
                w = sum(
                    g.weight for vi in face.vertices
                    for g in body_mesh.data.vertices[vi].groups
                    if g.group in s1_vg
                )
                if w > OVERLAP_WEIGHT_THRESHOLD:
                    s1_view[face.index] = s1
                    s1_gained += 1
            elif assigned == s1:
                w = sum(
                    g.weight for vi in face.vertices
                    for g in body_mesh.data.vertices[vi].groups
                    if g.group in s2_vg
                )
                if w > OVERLAP_WEIGHT_THRESHOLD:
                    s2_view[face.index] = s2
                    s2_gained += 1

        slot_face_views[s1] = s1_view
        slot_face_views[s2] = s2_view
        print(f"  Overlap expansion: {s1} gained {s1_gained} faces from {s2}, "
              f"{s2} gained {s2_gained} faces from {s1}")

    # ---- Step 6: Extract shells per slot ----
    exported: list[str] = []

    for slot_type in valid_slots:
        print(f"\n--- Extracting: {slot_type} ---")

        slot_thickness = (SHELL_THICKNESS.get(slot_type, 0.005)
                          if thickness <= 0 else thickness)

        shell = extract_slot_shell(body_mesh, slot_type, slot_thickness,
                                   weight_threshold,
                                   face_assignments=slot_face_views[slot_type])
        if not shell:
            continue

        parent_to_armature(shell, armature_obj)

        out_path = os.path.join(output_dir, f"shell_{slot_type}.glb")
        export_skinned_glb(shell, armature_obj, out_path, yup=True)
        print(f"  Exported: {out_path}")
        exported.append(out_path)

        if game_dir:
            game_path = os.path.join(game_dir, f"shell_{slot_type}.glb")
            export_skinned_glb(shell, armature_obj, game_path, yup=True)
            print(f"  Exported (Y-up): {game_path}")

        bpy.data.objects.remove(shell, do_unlink=True)

    bpy.data.objects.remove(body_mesh, do_unlink=True)

    print(f"\n=== Done — {len(exported)} shells exported ===")
    return exported


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Body Shell Extractor")
    parser.add_argument(
        "--rig-blend", required=True,
        help="Path to the rig .blend file",
    )
    parser.add_argument(
        "--body-glb", required=True,
        help="Path to body GLB (e.g. rig/CharacterMesh/BaseFemale.glb)",
    )
    parser.add_argument(
        "--out", required=True,
        help="Output directory for shell GLBs",
    )
    parser.add_argument(
        "--thickness", type=float, default=0.005,
        help="Shell thickness in meters (default 0.005 = 5mm). "
             "Set 0 to use per-slot defaults.",
    )
    parser.add_argument(
        "--slots", default=None,
        help=f"Comma-separated slot types (default: all). "
             f"Options: {','.join(ALL_SLOT_TYPES)}",
    )
    parser.add_argument(
        "--weight-threshold", type=float, default=0.1,
        help="Min total bone weight to include a vertex in a slot (default 0.1)",
    )
    parser.add_argument(
        "--game-out", default=None,
        help="Optional Y-up export directory for game engines",
    )

    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    slot_types = ALL_SLOT_TYPES
    if args.slots:
        slot_types = [s.strip() for s in args.slots.split(",")]

    extract_shells(
        rig_blend=args.rig_blend,
        body_glb=args.body_glb,
        output_dir=args.out,
        slot_types=slot_types,
        thickness=args.thickness,
        weight_threshold=args.weight_threshold,
        game_dir=args.game_out,
    )


if __name__ == "__main__":
    main()
