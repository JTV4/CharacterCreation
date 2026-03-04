"""Equipment Mesh Factory — generates weighted placeholder geometry per equipment slot.

Reads equipment_spec.json and rig_spec.json, creates placeholder meshes for each
slot, weights them to the armature bones, and exports individual GLB files.

Usage (headless):
    blender --background --python equipment/factory/mesh_factory.py -- \
        --rig-spec rig/spec/rig_spec.json \
        --equip-spec equipment/spec/equipment_spec.json \
        --rig-blend rig/output/rig.blend \
        --out equipment/output/
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any

import bpy
import bmesh
from mathutils import Vector, Matrix


def load_json(path: str) -> dict[str, Any]:
    abspath = os.path.abspath(path)
    with open(abspath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_bone_data(rig_spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build a lookup of bone name -> bone data from the rig spec."""
    return {b["name"]: b for b in rig_spec["bones"]}


# ---------------------------------------------------------------------------
# Geometry generators
# ---------------------------------------------------------------------------

def _create_dome(slot: dict, bone_map: dict) -> bpy.types.Object:
    """Helmet dome sitting on the head bone."""
    head_bone = bone_map["head"]
    center_z = (head_bone["head"][2] + head_bone["tail"][2]) / 2.0
    params = slot["mesh_params"]
    segments = params.get("segments", 16)
    rings = params.get("rings", 8)
    radius = slot["bounds"]["radius"]

    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=(0, 0, center_z + params.get("offset_z", 0)),
    )
    obj = bpy.context.active_object
    obj.name = f"equip_{slot['id']}"

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.bisect_plane(
        bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=(0, 0, center_z - 0.02),
        plane_no=(0, 0, -1),
        clear_inner=True,
    )
    bm.to_mesh(obj.data)
    bm.free()

    return obj


def _create_pendant(slot: dict, bone_map: dict) -> bpy.types.Object:
    """Necklace chain around the neck with a pendant hanging at the front."""
    params = slot["mesh_params"]
    neck_r = params.get("neck_radius", 0.065)
    chain_r = params.get("chain_radius", 0.003)
    chain_z = params.get("chain_z", 1.43)
    chain_segs = params.get("chain_segments", 32)
    chain_tube_segs = params.get("chain_tube_segments", 6)
    pendant_r = params.get("pendant_radius", 0.018)
    pendant_thick = params.get("pendant_thickness", 0.004)
    bail_r = params.get("bail_radius", 0.005)
    bail_tube_r = params.get("bail_tube_radius", 0.002)
    bail_segs = params.get("bail_segments", 12)
    bail_tube_segs = params.get("bail_tube_segments", 6)

    mesh = bpy.data.meshes.new(f"equip_{slot['id']}")
    obj = bpy.data.objects.new(f"equip_{slot['id']}", mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()

    def add_torus(center, major_r, minor_r, maj_segs, min_segs, axis="Z"):
        """Add a torus to the bmesh at the given center."""
        rings = []
        for i in range(maj_segs):
            angle = 2 * math.pi * i / maj_segs
            if axis == "Z":
                ring_center = Vector((
                    center[0] + major_r * math.cos(angle),
                    center[1] + major_r * math.sin(angle),
                    center[2],
                ))
                tangent = Vector((-math.sin(angle), math.cos(angle), 0)).normalized()
                radial = Vector((math.cos(angle), math.sin(angle), 0)).normalized()
                up = Vector((0, 0, 1))
            else:
                ring_center = Vector((
                    center[0],
                    center[1] + major_r * math.sin(angle),
                    center[2] + major_r * math.cos(angle),
                ))
                tangent = Vector((0, math.cos(angle), -math.sin(angle))).normalized()
                radial = Vector((0, math.sin(angle), math.cos(angle))).normalized()
                up = Vector((1, 0, 0))

            ring_verts = []
            for j in range(min_segs):
                t_angle = 2 * math.pi * j / min_segs
                offset = radial * math.cos(t_angle) * minor_r + up * math.sin(t_angle) * minor_r
                v = bm.verts.new(ring_center + offset)
                ring_verts.append(v)
            rings.append(ring_verts)

        for i in range(maj_segs):
            i_next = (i + 1) % maj_segs
            for j in range(min_segs):
                j_next = (j + 1) % min_segs
                v1 = rings[i][j]
                v2 = rings[i][j_next]
                v3 = rings[i_next][j_next]
                v4 = rings[i_next][j]
                try:
                    bm.faces.new([v1, v2, v3, v4])
                except ValueError:
                    pass

    chain_center = (0, 0, chain_z)
    add_torus(chain_center, neck_r, chain_r, chain_segs, chain_tube_segs, axis="Z")

    front_y = neck_r
    pendant_hang_z = chain_z - bail_r * 2 - pendant_r * 0.5

    bail_center = (0, front_y, chain_z - bail_r)
    add_torus(bail_center, bail_r, bail_tube_r, bail_segs, bail_tube_segs, axis="X")

    disc_z = pendant_hang_z - pendant_r * 0.3
    disc_rings = []
    disc_steps = 12
    for ri in range(2):
        z_off = -pendant_thick / 2 + ri * pendant_thick
        row = []
        for si in range(disc_steps):
            angle = 2 * math.pi * si / disc_steps
            x = math.cos(angle) * pendant_r
            y_pos = front_y + math.sin(angle) * pendant_r
            v = bm.verts.new((x, y_pos, disc_z + z_off))
            row.append(v)
        disc_rings.append(row)

    for si in range(disc_steps):
        si_next = (si + 1) % disc_steps
        v1 = disc_rings[0][si]
        v2 = disc_rings[0][si_next]
        v3 = disc_rings[1][si_next]
        v4 = disc_rings[1][si]
        try:
            bm.faces.new([v1, v2, v3, v4])
        except ValueError:
            pass

    cap_center_bot = bm.verts.new((0, front_y, disc_z - pendant_thick / 2))
    cap_center_top = bm.verts.new((0, front_y, disc_z + pendant_thick / 2))
    for si in range(disc_steps):
        si_next = (si + 1) % disc_steps
        try:
            bm.faces.new([cap_center_bot, disc_rings[0][si_next], disc_rings[0][si]])
        except ValueError:
            pass
        try:
            bm.faces.new([cap_center_top, disc_rings[1][si], disc_rings[1][si_next]])
        except ValueError:
            pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


def _create_tube_along_bone(bone_data: dict, radius: float, segments: int = 8) -> tuple[list, list]:
    """Return verts and faces for a tube segment along a bone axis."""
    head = Vector(bone_data["head"])
    tail = Vector(bone_data["tail"])
    direction = tail - head
    length = direction.length
    if length < 0.001:
        return [], []

    direction.normalize()
    up = Vector((0, 0, 1))
    if abs(direction.dot(up)) > 0.99:
        up = Vector((1, 0, 0))
    side = direction.cross(up).normalized()
    up = side.cross(direction).normalized()

    verts = []
    for t in [0.0, 1.0]:
        center = head + direction * length * t
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            offset = side * math.cos(angle) * radius + up * math.sin(angle) * radius
            verts.append(center + offset)

    faces = []
    for i in range(segments):
        i_next = (i + 1) % segments
        faces.append((i, i_next, segments + i_next, segments + i))

    return verts, faces


def _create_glove_mesh(slot: dict, bone_map: dict, side: str) -> bpy.types.Object:
    """Tube mesh wrapping hand and finger bones for one side (wrist to fingertips)."""
    params = slot["mesh_params"]
    tube_r = params.get("tube_radius", 0.015)
    wrist_r = params.get("wrist_radius", 0.022)
    segs = params.get("segments", 8)

    mesh = bpy.data.meshes.new(f"equip_glove_{side}")
    obj = bpy.data.objects.new(f"equip_glove_{side}", mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()

    suffix = f"_{side}"
    relevant_bones = [
        b for b in slot["bones"]
        if b["name"].endswith(suffix) and b["name"] in bone_map
    ]

    for bone_ref in relevant_bones:
        bname = bone_ref["name"]
        bd = bone_map[bname]
        if "hand" in bname:
            r = wrist_r
        elif "thumb" in bname or "pinky" in bname:
            r = tube_r * 0.6
        else:
            r = tube_r * 0.7
        verts, faces = _create_tube_along_bone(bd, r, segs)
        if not verts:
            continue

        bm_verts = [bm.verts.new(v) for v in verts]
        bm.verts.ensure_lookup_table()
        for f in faces:
            try:
                bm.faces.new([bm_verts[idx] for idx in f])
            except ValueError:
                pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


def _create_gloves(slot: dict, bone_map: dict) -> bpy.types.Object:
    """Create glove meshes for both hands, joined into one object."""
    left = _create_glove_mesh(slot, bone_map, "L")
    right = _create_glove_mesh(slot, bone_map, "R")

    bpy.context.view_layer.objects.active = left
    left.select_set(True)
    right.select_set(True)
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = f"equip_{slot['id']}"
    return joined


def _create_torus_ring(slot: dict, bone_map: dict) -> bpy.types.Object:
    """Torus ring around the left middle finger."""
    params = slot["mesh_params"]
    anchor = params.get("bone_anchor", "middle_01_L")
    bone = bone_map[anchor]
    t = params.get("position_along_bone", 0.35)
    head = Vector(bone["head"])
    tail = Vector(bone["tail"])
    pos = head.lerp(tail, t)

    major_r = params.get("major_radius", 0.009)
    minor_r = params.get("minor_radius", 0.002)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_r,
        minor_radius=minor_r,
        major_segments=params.get("major_segments", 24),
        minor_segments=params.get("minor_segments", 8),
        location=pos,
    )
    obj = bpy.context.active_object
    obj.name = f"equip_{slot['id']}"

    bone_dir = (tail - head).normalized()
    up = Vector((0, 0, 1))
    if abs(bone_dir.dot(up)) > 0.99:
        up = Vector((0, 1, 0))

    rot_quat = bone_dir.to_track_quat('Z', 'Y')
    obj.rotation_euler = rot_quat.to_euler()

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def _create_torso(slot: dict, bone_map: dict) -> bpy.types.Object:
    """Torso tube from waist to shoulders, with sleeves to the wrist."""
    params = slot["mesh_params"]
    segs = params.get("segments", 16)
    rings = params.get("rings", 6)
    sleeve_segs = params.get("sleeve_segments", 10)
    sleeve_r = params.get("sleeve_radius", 0.04)
    wrist_r = params.get("wrist_radius", 0.025)

    pelvis = bone_map["pelvis"]
    spine_bones = ["spine_01", "spine_02", "spine_03"]
    z_positions = [pelvis["head"][2]]
    for sname in spine_bones:
        b = bone_map[sname]
        z_positions.append(b["head"][2])
    z_positions.append(bone_map["spine_03"]["tail"][2])

    pelvis_r_val = params.get("pelvis_radius", 0.13)
    waist_r_val = params.get("waist_radius", 0.14)
    chest_r_val = params.get("chest_radius", 0.17)
    shoulder_r_val = params.get("shoulder_radius", 0.20)

    z_min = z_positions[0]
    z_max = z_positions[-1]
    z_range = z_max - z_min

    mesh = bpy.data.meshes.new(f"equip_{slot['id']}")
    obj = bpy.data.objects.new(f"equip_{slot['id']}", mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()

    ring_verts = []
    for ring_i in range(rings + 1):
        t = ring_i / rings
        z = z_min + t * z_range

        # Radial profile: pelvis -> waist -> chest -> shoulder
        # pelvis region is roughly the first ~15% of the range
        pelvis_frac = (z_positions[1] - z_min) / z_range if z_range > 0 else 0.15
        if t < pelvis_frac:
            frac = t / pelvis_frac if pelvis_frac > 0 else 0
            r = pelvis_r_val + (waist_r_val - pelvis_r_val) * frac
        elif t < 0.5:
            frac = (t - pelvis_frac) / (0.5 - pelvis_frac) if (0.5 - pelvis_frac) > 0 else 0
            r = waist_r_val + (chest_r_val - waist_r_val) * frac
        else:
            r = chest_r_val + (shoulder_r_val - chest_r_val) * ((t - 0.5) / 0.5)

        row = []
        for seg_i in range(segs):
            angle = 2 * math.pi * seg_i / segs
            x = math.cos(angle) * r
            y = math.sin(angle) * r
            v = bm.verts.new((x, y, z))
            row.append(v)
        ring_verts.append(row)

    for ri in range(rings):
        for si in range(segs):
            si_next = (si + 1) % segs
            v1 = ring_verts[ri][si]
            v2 = ring_verts[ri][si_next]
            v3 = ring_verts[ri + 1][si_next]
            v4 = ring_verts[ri + 1][si]
            bm.faces.new([v1, v2, v3, v4])

    for side_name in ["L", "R"]:
        arm_bones = [
            bone_map.get(f"clavicle_{side_name}"),
            bone_map.get(f"upperarm_{side_name}"),
            bone_map.get(f"lowerarm_{side_name}"),
        ]
        arm_bones = [b for b in arm_bones if b is not None]
        if not arm_bones:
            continue

        points = []
        for ab in arm_bones:
            points.append(Vector(ab["head"]))
        points.append(Vector(arm_bones[-1]["tail"]))

        seg_lengths = [
            (points[i + 1] - points[i]).length for i in range(len(points) - 1)
        ]
        total_len = sum(seg_lengths)

        def sample_path(t_global: float):
            """Return (position, local_tangent) at parametric t along the arm."""
            target_dist = t_global * total_len
            accum = 0.0
            for seg_i in range(len(points) - 1):
                sl = seg_lengths[seg_i]
                if accum + sl >= target_dist or seg_i == len(points) - 2:
                    frac = (target_dist - accum) / sl if sl > 0 else 0
                    frac = max(0.0, min(1.0, frac))
                    pos = points[seg_i].lerp(points[seg_i + 1], frac)
                    tangent = (points[seg_i + 1] - points[seg_i]).normalized()
                    return pos, tangent
                accum += sl
            return points[-1], (points[-1] - points[-2]).normalized()

        arm_rings = []
        steps = max(6, len(points) * 4)
        for step_i in range(steps + 1):
            t = step_i / steps
            pos, tangent = sample_path(t)

            r = shoulder_r_val * 0.35 + (sleeve_r - shoulder_r_val * 0.35) * min(t * 2, 1.0)
            if t > 0.5:
                r = sleeve_r + (wrist_r - sleeve_r) * ((t - 0.5) / 0.5)

            up = Vector((0, 0, 1))
            if abs(tangent.dot(up)) > 0.99:
                up = Vector((0, 1, 0))
            side_vec = tangent.cross(up).normalized()
            up_vec = side_vec.cross(tangent).normalized()

            row = []
            for seg_i in range(sleeve_segs):
                angle = 2 * math.pi * seg_i / sleeve_segs
                offset = side_vec * math.cos(angle) * r + up_vec * math.sin(angle) * r
                v = bm.verts.new(pos + offset)
                row.append(v)
            arm_rings.append(row)

        for ri in range(len(arm_rings) - 1):
            for si in range(sleeve_segs):
                si_next = (si + 1) % sleeve_segs
                v1 = arm_rings[ri][si]
                v2 = arm_rings[ri][si_next]
                v3 = arm_rings[ri + 1][si_next]
                v4 = arm_rings[ri + 1][si]
                try:
                    bm.faces.new([v1, v2, v3, v4])
                except ValueError:
                    pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


def _create_pants(slot: dict, bone_map: dict) -> bpy.types.Object:
    """Pants covering pelvis, thighs, and upper shin (down to boot tops)."""
    params = slot["mesh_params"]
    segs = params.get("segments", 12)
    hip_r = params.get("hip_radius", 0.15)
    thigh_r = params.get("thigh_radius", 0.08)
    knee_r = params.get("knee_radius", 0.06)
    calf_r = params.get("calf_radius", 0.055)

    mesh = bpy.data.meshes.new(f"equip_{slot['id']}")
    obj = bpy.data.objects.new(f"equip_{slot['id']}", mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()

    pelvis = bone_map["pelvis"]
    hip_z = pelvis["head"][2]

    for side_name, sign in [("L", -1), ("R", 1)]:
        thigh = bone_map[f"thigh_{side_name}"]
        shin = bone_map[f"shin_{side_name}"]
        thigh_head_z = thigh["head"][2]
        thigh_tail_z = thigh["tail"][2]
        thigh_x = thigh["head"][0]
        shin_mid_z = (shin["head"][2] + shin["tail"][2]) / 2.0

        leg_rings = []
        z_values = [
            hip_z,
            thigh_head_z,
            (thigh_head_z + thigh_tail_z) / 2.0,
            thigh_tail_z,
            shin_mid_z,
        ]
        r_values = [hip_r, hip_r * 0.7, thigh_r, knee_r, calf_r]

        for z, r in zip(z_values, r_values):
            x_off = 0 if z >= thigh_head_z else thigh_x
            row = []
            for si in range(segs):
                angle = 2 * math.pi * si / segs
                x = x_off + math.cos(angle) * r
                y = math.sin(angle) * r
                v = bm.verts.new((x, y, z))
                row.append(v)
            leg_rings.append(row)

        for ri in range(len(leg_rings) - 1):
            for si in range(segs):
                si_next = (si + 1) % segs
                v1 = leg_rings[ri][si]
                v2 = leg_rings[ri][si_next]
                v3 = leg_rings[ri + 1][si_next]
                v4 = leg_rings[ri + 1][si]
                try:
                    bm.faces.new([v1, v2, v3, v4])
                except ValueError:
                    pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


def _create_boot(slot: dict, bone_map: dict) -> bpy.types.Object:
    """Boot mesh with a calf shaft and a proper foot shape with flat sole."""
    params = slot["mesh_params"]
    segs = params.get("segments", 12)
    calf_r = params.get("calf_radius", 0.055)
    ankle_r = params.get("ankle_radius", 0.04)
    sole_thick = params.get("sole_thickness", 0.02)

    mesh = bpy.data.meshes.new(f"equip_{slot['id']}")
    obj = bpy.data.objects.new(f"equip_{slot['id']}", mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()

    for side_name in ["L", "R"]:
        shin = bone_map[f"shin_{side_name}"]
        foot = bone_map[f"foot_{side_name}"]
        toe = bone_map[f"toe_{side_name}"]
        x_c = shin["head"][0]

        shin_top_z = (shin["head"][2] + shin["tail"][2]) / 2.0
        ankle_z = shin["tail"][2]
        foot_tail = Vector(foot["tail"])
        toe_tail = Vector(toe["tail"])
        ground_z = -sole_thick

        shaft_count = 6
        shaft_rings = []
        for i in range(shaft_count + 1):
            t = i / shaft_count
            z = shin_top_z + (ankle_z - shin_top_z) * t
            r = calf_r + (ankle_r - calf_r) * (t ** 0.7)
            row = []
            for si in range(segs):
                angle = 2 * math.pi * si / segs
                x = x_c + math.cos(angle) * r
                y = math.sin(angle) * r
                v = bm.verts.new((x, y, z))
                row.append(v)
            shaft_rings.append(row)

        for ri in range(len(shaft_rings) - 1):
            for si in range(segs):
                si_next = (si + 1) % segs
                try:
                    bm.faces.new([
                        shaft_rings[ri][si], shaft_rings[ri][si_next],
                        shaft_rings[ri + 1][si_next], shaft_rings[ri + 1][si],
                    ])
                except ValueError:
                    pass

        foot_stations = [
            (-0.02, ankle_z * 0.85, ankle_r * 1.05),
            (0.0,   ankle_z * 0.7,  ankle_r * 1.0),
            (0.03,  ankle_z * 0.55, ankle_r * 1.0),
            (0.06,  ankle_z * 0.42, ankle_r * 0.95),
            (foot_tail.y, 0.035,    ankle_r * 0.9),
            (toe_tail.y - 0.04, 0.028, ankle_r * 0.78),
            (toe_tail.y - 0.01, 0.02,  ankle_r * 0.55),
            (toe_tail.y + 0.005, 0.014, ankle_r * 0.25),
        ]

        foot_rings = []
        for y_pos, z_top, w in foot_stations:
            row = []
            for si in range(segs):
                angle = 2 * math.pi * si / segs
                x = x_c + math.cos(angle) * w
                sin_a = math.sin(angle)
                if sin_a >= 0:
                    z = ground_z + (z_top - ground_z) * sin_a
                else:
                    z = ground_z
                v = bm.verts.new((x, y_pos, z))
                row.append(v)
            foot_rings.append(row)

        for ri in range(len(foot_rings) - 1):
            for si in range(segs):
                si_next = (si + 1) % segs
                try:
                    bm.faces.new([
                        foot_rings[ri][si], foot_rings[ri][si_next],
                        foot_rings[ri + 1][si_next], foot_rings[ri + 1][si],
                    ])
                except ValueError:
                    pass

        last_ring = foot_rings[-1]
        z_avg = sum(v.co.z for v in last_ring) / len(last_ring)
        toe_cap = bm.verts.new((x_c, toe_tail.y + 0.008, z_avg))
        for si in range(segs):
            si_next = (si + 1) % segs
            try:
                bm.faces.new([toe_cap, last_ring[si_next], last_ring[si]])
            except ValueError:
                pass

        first_ring = foot_rings[0]
        z_avg = sum(v.co.z for v in first_ring) / len(first_ring)
        heel_cap = bm.verts.new((x_c, -0.025, z_avg))
        for si in range(segs):
            si_next = (si + 1) % segs
            try:
                bm.faces.new([heel_cap, first_ring[si], first_ring[si_next]])
            except ValueError:
                pass

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


def _create_base_body(slot: dict, bone_map: dict) -> list[bpy.types.Object]:
    """Low-poly base character body (OSRS-style, ≤5k triangles).

    Builds head, neck, torso, arms, hands, legs, and feet from procedural
    tubes and spheres, skinned to the rig. Returns separate mesh objects per
    body region so equipment can hide regions when equipped.
    """
    params = slot["mesh_params"]
    max_tris = params.get("max_triangles", 5000)

    head_segs = params.get("head_segments", 20)
    head_rings = params.get("head_rings", 10)
    neck_segs = params.get("neck_segments", 12)
    torso_segs = params.get("torso_segments", 20)
    torso_rings = params.get("torso_rings", 10)
    arm_segs = params.get("arm_segments", 12)
    arm_joint_inset = params.get("arm_joint_inset", 0.06)
    leg_segs = params.get("leg_segments", 16)
    hand_segs = params.get("hand_segments", 10)
    finger_segs = params.get("finger_segments", 8)
    finger_r = params.get("finger_radius", 0.009)
    joint_inset = params.get("finger_joint_inset", 0.08)
    foot_segs = params.get("foot_segments", 12)

    region_objs: list[bpy.types.Object] = []

    def add_tube_rings(bm_inner: bmesh.types.BMesh, points: list, radii: list,
                       segs: int, axis: str = "Z") -> None:
        """Add tube geometry along a path. Cross-section perpendicular to axis.
        axis: 'Z' for vertical bones (neck, torso), 'path' for path-aligned (arms, legs, fingers).
        """
        if len(points) < 2 or len(radii) != len(points):
            return
        pts = [Vector(p) for p in points]
        verts_by_ring = []
        for i, (pos, r) in enumerate(zip(pts, radii)):
            center = pos
            if axis == "path":
                if i == 0:
                    direction = (pts[1] - pts[0]).normalized()
                elif i == len(pts) - 1:
                    direction = (pts[-1] - pts[-2]).normalized()
                else:
                    direction = (pts[i + 1] - pts[i - 1]).normalized()
                up_ref = Vector((0, 0, 1))
                if abs(direction.dot(up_ref)) > 0.99:
                    up_ref = Vector((1, 0, 0))
                side = direction.cross(up_ref).normalized()
                up = side.cross(direction).normalized()
            row = []
            for si in range(segs):
                angle = 2 * math.pi * si / segs
                if axis == "Z":
                    x = center.x + math.cos(angle) * r
                    y = center.y + math.sin(angle) * r
                    z = center.z
                    row.append(bm_inner.verts.new((x, y, z)))
                else:
                    offset = side * math.cos(angle) * r + up * math.sin(angle) * r
                    row.append(bm_inner.verts.new(center + offset))
            verts_by_ring.append(row)

        for ri in range(len(verts_by_ring) - 1):
            for si in range(segs):
                si_next = (si + 1) % segs
                try:
                    bm_inner.faces.new([
                        verts_by_ring[ri][si], verts_by_ring[ri][si_next],
                        verts_by_ring[ri + 1][si_next], verts_by_ring[ri + 1][si],
                    ])
                except ValueError:
                    pass

    def make_region_mesh(region_name: str, bm_src: bmesh.types.BMesh) -> bpy.types.Object:
        """Create a mesh object from a bmesh and add to scene."""
        mesh = bpy.data.meshes.new(f"equip_base_body_{region_name}")
        obj = bpy.data.objects.new(f"equip_base_body_{region_name}", mesh)
        bpy.context.scene.collection.objects.link(obj)
        bm_src.to_mesh(mesh)
        bm_src.free()
        mesh.update()
        return obj

    # --- Head (full sphere ellipsoid) ---
    head_bone = bone_map["head"]
    head_center_z = (head_bone["head"][2] + head_bone["tail"][2]) / 2.0
    head_r = 0.12
    scale_x = 1.1
    scale_y = 1.05
    scale_z = 1.1

    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=head_segs,
        ring_count=head_rings,
        radius=head_r,
        location=(0, 0, head_center_z),
    )
    head_obj = bpy.context.active_object
    head_obj.scale = (scale_x, scale_y, scale_z)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bm_head = bmesh.new()
    bm_head.from_mesh(head_obj.data)
    region_objs.append(make_region_mesh("head", bm_head))
    bpy.data.objects.remove(head_obj, do_unlink=True)

    # --- Neck ---
    bm_neck = bmesh.new()
    neck_bone = bone_map["neck_01"]
    head = Vector(neck_bone["head"])
    tail = Vector(neck_bone["tail"])
    neck_r = 0.055
    pts = [head, tail]
    rads = [neck_r * 1.1, neck_r]
    add_tube_rings(bm_neck, pts, rads, neck_segs)
    region_objs.append(make_region_mesh("neck", bm_neck))

    # --- Torso (pelvis to shoulders) ---
    bm_torso = bmesh.new()
    pelvis = bone_map["pelvis"]
    spine_bones = ["spine_01", "spine_02", "spine_03"]
    z_vals = [pelvis["head"][2]]
    for sname in spine_bones:
        z_vals.append(bone_map[sname]["head"][2])
    z_vals.append(bone_map["spine_03"]["tail"][2])
    z_min, z_max = min(z_vals), max(z_vals)
    z_range = z_max - z_min

    pelvis_r, waist_r, chest_r, shoulder_r = 0.12, 0.13, 0.15, 0.16
    torso_ring_verts = []
    for ri in range(torso_rings + 1):
        t = ri / torso_rings
        z = z_min + t * z_range
        if t < 0.2:
            r = pelvis_r + (waist_r - pelvis_r) * (t / 0.2)
        elif t < 0.5:
            r = waist_r + (chest_r - waist_r) * ((t - 0.2) / 0.3)
        else:
            r = chest_r + (shoulder_r - chest_r) * ((t - 0.5) / 0.5)
        row = []
        for si in range(torso_segs):
            angle = 2 * math.pi * si / torso_segs
            row.append(bm_torso.verts.new((math.cos(angle) * r, math.sin(angle) * r, z)))
        torso_ring_verts.append(row)

    for ri in range(torso_rings):
        for si in range(torso_segs):
            si_next = (si + 1) % torso_segs
            try:
                bm_torso.faces.new([
                    torso_ring_verts[ri][si], torso_ring_verts[ri][si_next],
                    torso_ring_verts[ri + 1][si_next], torso_ring_verts[ri + 1][si],
                ])
            except ValueError:
                pass
    region_objs.append(make_region_mesh("torso", bm_torso))

    # --- Arms (muscular, individual cylinders per bone with joint gaps) ---
    bm_arms = bmesh.new()
    arm_bone_names = ["clavicle", "upperarm", "lowerarm", "hand"]
    for side_name in ["L", "R"]:
        for i, bname_base in enumerate(arm_bone_names):
            bname = f"{bname_base}_{side_name}"
            if bname not in bone_map:
                continue
            bd = bone_map[bname]
            head = Vector(bd["head"])
            tail = Vector(bd["tail"])
            direction = tail - head
            length = direction.length
            if length < 0.001:
                continue
            direction.normalize()
            inset_dist = min(length * arm_joint_inset, 0.012)
            start_pt = head + direction * inset_dist
            end_pt = tail - direction * inset_dist
            effective_len = (end_pt - start_pt).length

            # Muscular radius profiles: thicker in middle (bicep/forearm bulge)
            if bname_base == "clavicle":
                t_vals = [0.0, 0.5, 1.0]
                r_vals = [0.042, 0.048, 0.044]
            elif bname_base == "upperarm":
                t_vals = [0.0, 0.25, 0.5, 0.75, 1.0]
                r_vals = [0.042, 0.048, 0.055, 0.050, 0.044]
            elif bname_base == "lowerarm":
                t_vals = [0.0, 0.25, 0.5, 0.75, 1.0]
                r_vals = [0.042, 0.048, 0.052, 0.048, 0.038]
            else:
                t_vals = [0.0, 0.5, 1.0]
                r_vals = [0.032, 0.030, 0.028]

            pts = []
            rads = []
            for t, r in zip(t_vals, r_vals):
                pts.append(start_pt + direction * (effective_len * t))
                rads.append(r)
            add_tube_rings(bm_arms, pts, rads, arm_segs, axis="path")
    region_objs.append(make_region_mesh("arms", bm_arms))

    # --- Legs (thigh -> shin) ---
    bm_legs = bmesh.new()
    for side_name in ["L", "R"]:
        thigh = bone_map[f"thigh_{side_name}"]
        shin = bone_map[f"shin_{side_name}"]
        foot = bone_map[f"foot_{side_name}"]
        pts = [
            Vector(thigh["head"]),
            Vector(thigh["tail"]),
            Vector(shin["head"]),
            Vector(shin["tail"]),
            Vector(foot["tail"]),
        ]
        rads = [0.075, 0.07, 0.06, 0.05, 0.04]
        add_tube_rings(bm_legs, pts, rads, leg_segs, axis="path")
    region_objs.append(make_region_mesh("legs", bm_legs))

    # --- Feet ---
    bm_feet = bmesh.new()
    for side_name in ["L", "R"]:
        foot = bone_map[f"foot_{side_name}"]
        toe = bone_map[f"toe_{side_name}"]
        foot_head = Vector(foot["head"])
        foot_tail = Vector(foot["tail"])
        toe_tail = Vector(toe["tail"])
        foot_pts = [foot_head, foot_tail, toe_tail]
        foot_rads = [0.04, 0.035, 0.02]
        add_tube_rings(bm_feet, foot_pts, foot_rads, foot_segs, axis="path")
    region_objs.append(make_region_mesh("feet", bm_feet))

    # --- Hands (individual fingers) ---
    bm_hands = bmesh.new()
    finger_bones = [
        "thumb_01", "thumb_02", "thumb_03",
        "index_01", "index_02", "index_03",
        "middle_01", "middle_02", "middle_03",
        "ring_01", "ring_02", "ring_03",
        "pinky_01", "pinky_02", "pinky_03",
    ]
    for side_name in ["L", "R"]:
        for fname in finger_bones:
            bname = f"{fname}_{side_name}"
            if bname not in bone_map:
                continue
            bd = bone_map[bname]
            head = Vector(bd["head"])
            tail = Vector(bd["tail"])
            direction = tail - head
            length = direction.length
            if length < 0.001:
                continue
            direction.normalize()
            inset_dist = min(length * joint_inset, 0.008)
            start_pt = head + direction * inset_dist
            end_pt = tail - direction * inset_dist
            pts = [start_pt, end_pt]
            if "thumb" in fname or "pinky" in fname:
                r = finger_r * 0.65
            else:
                r = finger_r * 0.85
            rads = [r, r]
            add_tube_rings(bm_hands, pts, rads, finger_segs, axis="path")
    region_objs.append(make_region_mesh("hands", bm_hands))

    tri_count = sum(len(o.data.polygons) for o in region_objs)
    if tri_count > max_tris:
        print(f"  Warning: base_body has {tri_count} tris (max {max_tris})")
    else:
        print(f"  base_body: {tri_count} triangles ({len(region_objs)} regions)")

    return region_objs


GENERATORS = {
    "base_body": _create_base_body,
    "dome": _create_dome,
    "pendant": _create_pendant,
    "glove": _create_gloves,
    "torus": _create_torus_ring,
    "torso": _create_torso,
    "pants": _create_pants,
    "boot": _create_boot,
}


# ---------------------------------------------------------------------------
# Vertex weighting
# ---------------------------------------------------------------------------

def assign_weights(
    mesh_obj: bpy.types.Object,
    slot: dict[str, Any],
    bone_map: dict[str, dict[str, Any]],
) -> None:
    """Assign vertex weights based on distance to each bone's axis.

    Uses a tight influence radius so that arm/leg vertices are dominated by
    their nearest bones rather than being diluted by distant trunk bones.
    Only the top 4 influences are kept per vertex (GPU skinning limit).
    """
    MAX_INFLUENCES = 4
    max_dist = slot["bounds"].get("weight_radius", 0.25)

    for bone_ref in slot["bones"]:
        bname = bone_ref["name"]
        if bname not in bone_map:
            continue
        vg = mesh_obj.vertex_groups.new(name=bname)

    mesh = mesh_obj.data
    for v in mesh.vertices:
        vpos = Vector(v.co)
        weights: list[tuple[str, float]] = []

        for bone_ref in slot["bones"]:
            bname = bone_ref["name"]
            if bname not in bone_map:
                continue
            bd = bone_map[bname]
            head = Vector(bd["head"])
            tail = Vector(bd["tail"])
            bone_dir = tail - head
            bone_len = bone_dir.length
            if bone_len < 0.001:
                dist = (vpos - head).length
            else:
                bone_dir_n = bone_dir.normalized()
                proj = (vpos - head).dot(bone_dir_n)
                proj = max(0, min(bone_len, proj))
                closest = head + bone_dir_n * proj
                dist = (vpos - closest).length

            if dist > max_dist:
                continue
            falloff = max(0.0, 1.0 - (dist / max_dist))
            w = (falloff ** 3) * bone_ref["weight"]
            if w > 0.001:
                weights.append((bname, w))

        weights.sort(key=lambda x: x[1], reverse=True)
        weights = weights[:MAX_INFLUENCES]

        total_weight = sum(w for _, w in weights)
        if total_weight > 0:
            for bname, w in weights:
                vg = mesh_obj.vertex_groups.get(bname)
                if vg:
                    vg.add([v.index], w / total_weight, "REPLACE")


def hex_to_linear(hex_color: str) -> tuple[float, float, float]:
    """Convert a hex color string (#RRGGBB) to linear-space RGB floats."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    # sRGB to linear conversion
    def srgb_to_linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b))


def assign_material(mesh_obj: bpy.types.Object, slot: dict[str, Any]) -> None:
    """Create and assign a PBR material with the slot's color."""
    color_hex = slot.get("color", "#94a3b8")
    lr, lg, lb = hex_to_linear(color_hex)

    mat_name = f"mat_{slot['id']}"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (lr, lg, lb, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.6
        bsdf.inputs["Metallic"].default_value = 0.0

    mesh_obj.data.materials.clear()
    mesh_obj.data.materials.append(mat)


def parent_to_armature(mesh_obj: bpy.types.Object, armature_obj: bpy.types.Object) -> None:
    """Parent mesh to armature with Armature modifier."""
    mesh_obj.parent = armature_obj
    mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = armature_obj
    mod.use_vertex_groups = True


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_slot_glb(mesh_obj: bpy.types.Object | list[bpy.types.Object],
                    armature_obj: bpy.types.Object,
                    slot_id: str, output_dir: str, yup: bool = False) -> str:
    """Export a single slot mesh (or multiple meshes) + armature as GLB.

    Args:
        mesh_obj: Single mesh object or list of mesh objects (e.g. base_body regions).
        yup: When True, convert to Y-up (glTF standard) for game engine import.
             When False, keep Blender's Z-up (used by the viewer).
    """
    filepath = os.path.join(output_dir, f"{slot_id}.glb")
    os.makedirs(output_dir, exist_ok=True)

    mesh_objs = mesh_obj if isinstance(mesh_obj, list) else [mesh_obj]

    bpy.ops.object.select_all(action="DESELECT")
    armature_obj.select_set(True)
    for m in mesh_objs:
        m.select_set(True)
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
    print(f"    Exported: {filepath}")
    return filepath


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_all_equipment(
    rig_spec: dict[str, Any],
    equip_spec: dict[str, Any],
    armature_obj: bpy.types.Object,
    output_dir: str,
    game_dir: str | None = None,
) -> list[bpy.types.Object]:
    """Generate, weight, parent, and export all equipment slot meshes.

    Args:
        game_dir: If provided, also export Y-up GLBs (glTF-standard) here
                  for direct import into game engines.
    """
    bone_map = get_bone_data(rig_spec)
    slot_objs: list[bpy.types.Object] = []

    for slot in equip_spec["slots"]:
        if slot.get("url"):
            print(f"  Skipping slot: {slot['id']} (loads from URL)")
            continue

        mesh_type = slot["mesh_type"]
        gen = GENERATORS.get(mesh_type)
        if not gen:
            print(f"  Warning: no generator for mesh_type '{mesh_type}', skipping {slot['id']}")
            continue

        print(f"  Generating slot: {slot['id']} (type={mesh_type})")
        gen_result = gen(slot, bone_map)

        mesh_objs = gen_result if isinstance(gen_result, list) else [gen_result]
        for m in mesh_objs:
            assign_material(m, slot)
            assign_weights(m, slot, bone_map)
            parent_to_armature(m, armature_obj)

        export_meshes = mesh_objs[0] if len(mesh_objs) == 1 else mesh_objs
        export_slot_glb(export_meshes, armature_obj, slot["id"], output_dir, yup=False)

        if game_dir:
            export_slot_glb(export_meshes, armature_obj, slot["id"], game_dir, yup=True)

        slot_objs.extend(mesh_objs)

    return slot_objs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="Equipment Mesh Factory")
    parser.add_argument("--rig-spec", required=True, help="Path to rig_spec.json")
    parser.add_argument("--equip-spec", required=True, help="Path to equipment_spec.json")
    parser.add_argument("--rig-blend", required=True, help="Path to the rig .blend file")
    parser.add_argument("--out", required=True, help="Output directory for GLB files (Z-up, for viewer)")
    parser.add_argument("--game-out", default=None,
                        help="Output directory for game-ready GLBs (Y-up, glTF standard)")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()

    print("=== Equipment Mesh Factory ===")

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(args.rig_blend))

    armature_obj = None
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            armature_obj = obj
            break

    if not armature_obj:
        print("ERROR: No armature found in the .blend file.")
        sys.exit(1)

    bpy.context.view_layer.objects.active = armature_obj
    print(f"  Using armature: {armature_obj.name}")

    rig_spec = load_json(args.rig_spec)
    equip_spec = load_json(args.equip_spec)

    slot_objs = build_all_equipment(
        rig_spec, equip_spec, armature_obj, args.out,
        game_dir=args.game_out,
    )

    blend_out = os.path.join(args.out, "equipment.blend")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(blend_out))
    print(f"  Saved combined: {blend_out}")

    print(f"=== Done — {len(slot_objs)} slot meshes generated ===")


if __name__ == "__main__":
    main()
