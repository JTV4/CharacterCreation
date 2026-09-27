"""
generate_giant_rat.py
=====================
Import the unrigged Giant Rat, sit it on the ground facing −Y (glTF +Z),
skin it to a quadruped armature, and bake looping ``idle``, ``walk``, and ``attack1``.

Source (do not overwrite):
  ~/Desktop/Models/Creatures/GiantRat.glb

Output:
  viewer/public/buildings/GiantRat.glb

Handoff contract (matches cows / sheep / chickens):
  - Origin at world (0, 0, 0) = ground between the feet
  - Blender: −Y = forward (snout), +Z = up, +X = creature left
  - glTF Y-up export: visual snout = +Z, no root motion
  - Clips (exact lowercase names):
      ``idle``  loop — breath, look, ear flicks, tail sway; feet planted
      ``walk``  loop, in-place diagonal trot
      ``attack1`` loop — in-place bite / lunge (no root motion)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_giant_rat.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_GLB = os.path.expanduser("~/Desktop/Models/Creatures/GiantRat.glb")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
os.makedirs(VIEWER_DIR, exist_ok=True)

FPS = 24
CLIP_IDLE = 72  # 3.000 s
CLIP_WALK = 32  # 1.333 s
CLIP_ATTACK = 36  # 1.500 s


# ── Scene helpers ─────────────────────────────────────────────────────────

def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def select_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _mean(pts: list[Vector]) -> Vector:
    n = max(len(pts), 1)
    return Vector((
        sum(p.x for p in pts) / n,
        sum(p.y for p in pts) / n,
        sum(p.z for p in pts) / n,
    ))


def world_coords(mesh: bpy.types.Object) -> list[Vector]:
    mw = mesh.matrix_world
    return [mw @ v.co for v in mesh.data.vertices]


# ── Import + orient ───────────────────────────────────────────────────────

def import_authored_mesh(src_path: str, name: str) -> bpy.types.Object:
    if not os.path.isfile(src_path):
        raise FileNotFoundError(src_path)

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=src_path)
    new_objs = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new_objs if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh in {src_path}")

    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    if len(meshes) > 1:
        bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    mesh.name = name
    mesh.data.name = name

    select_active(mesh)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Author file already faces −Y after Blender's Y-up → Z-up import.
    # That is glTF +Z after export_yup (same as Cow / Sheep). Do not yaw 180.

    coords = [v.co.copy() for v in mesh.data.vertices]
    zmin = min(c.z for c in coords)
    zs = sorted(c.z for c in coords)
    z_cut = zs[max(int(len(zs) * 0.04), 1)]
    feet = [c for c in coords if c.z <= z_cut]
    origin = _mean(feet) if feet else Vector((0.0, 0.0, zmin))
    mesh.location = (-origin.x, -origin.y, -zmin)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    for obj in list(new_objs):
        if obj == mesh:
            continue
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)

    for img in bpy.data.images:
        if img.source == "FILE" and img.filepath:
            try:
                img.pack()
            except Exception:
                pass

    return mesh


# ── Landmarks ─────────────────────────────────────────────────────────────

def _cluster_paws(feet: list[Vector]) -> dict[str, Vector]:
    """Four paws. Creature faces −Y: left = +X, right = −X, front = −Y, hind = +Y."""
    ys = sorted(c.y for c in feet)
    mid_y = ys[len(ys) // 2]
    front = [c for c in feet if c.y < mid_y] or feet
    hind = [c for c in feet if c.y >= mid_y] or feet

    def split_lr(pts: list[Vector]) -> tuple[Vector, Vector]:
        left = [c for c in pts if c.x >= 0.0] or pts
        right = [c for c in pts if c.x < 0.0] or pts
        return _mean(left), _mean(right)

    fl, fr = split_lr(front)
    hl, hr = split_lr(hind)
    return {"fl": fl, "fr": fr, "hl": hl, "hr": hr}


def _band_mean(
    coords: list[Vector],
    *,
    y0: float | None = None,
    y1: float | None = None,
    z0: float | None = None,
    z1: float | None = None,
    x0: float | None = None,
    x1: float | None = None,
    fallback: Vector | None = None,
) -> Vector:
    pts = []
    for c in coords:
        if y0 is not None and c.y < y0:
            continue
        if y1 is not None and c.y >= y1:
            continue
        if z0 is not None and c.z < z0:
            continue
        if z1 is not None and c.z >= z1:
            continue
        if x0 is not None and c.x < x0:
            continue
        if x1 is not None and c.x >= x1:
            continue
        pts.append(c)
    if pts:
        return _mean(pts)
    if fallback is not None:
        return fallback
    return _mean(coords)


def _sample_tail_from_mesh(coords: list[Vector], rump: Vector, n: int, height: float) -> list[Vector]:
    """Bind bones to the authored tail volume so weights stick to the real mesh."""
    rear = [c for c in coords if c.y > rump.y - 0.02 * height and c.z > 0.05 * height]
    if not rear:
        rear = [c for c in coords if c.y > rump.y]
    tip = max(rear, key=lambda c: c.y)
    span = max(tip.y - rump.y, 1e-3)
    points: list[Vector] = []
    for i in range(n):
        t = (i + 1) / n
        y = rump.y + t * span
        half = max(0.045 * span, 0.025)
        band = [c for c in rear if abs(c.y - y) <= half and c.z > 0.04 * height]
        if not band:
            band = [c for c in rear if abs(c.y - y) <= half * 2.0]
        points.append(_mean(band) if band else rump.lerp(tip, t))
    return points


def landmarks_from_mesh(mesh: bpy.types.Object) -> dict[str, Vector]:
    coords = world_coords(mesh)
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    zmin, zmax = min(zs), max(zs)
    height = max(zmax - zmin, 1e-4)
    length = max(ymax - ymin, 1e-4)
    width = max(xmax - xmin, 1e-4)

    zs_sorted = sorted(zs)
    z_cut = zs_sorted[max(int(len(zs_sorted) * 0.04), 1)]
    feet = [c for c in coords if c.z <= z_cut]
    paws = _cluster_paws(feet if feet else coords)

    # Snout = most-forward (−Y) verts in the front third.
    front_pts = [c for c in coords if c.y < ymin + 0.28 * length]
    snout = min(front_pts, key=lambda c: c.y) if front_pts else Vector((0.0, ymin, 0.35 * height))
    skull_pts = [
        c for c in front_pts
        if c.z > 0.28 * height and abs(c.x) < 0.22 * width
    ] or front_pts
    skull = _mean(skull_pts) if skull_pts else Vector((0.0, ymin + 0.12 * length, 0.42 * height))

    ear_l_pts = [c for c in front_pts if c.x > 0.03 and c.z > 0.38 * height]
    ear_r_pts = [c for c in front_pts if c.x < -0.03 and c.z > 0.38 * height]
    ear_l = _mean(ear_l_pts) if ear_l_pts else Vector((0.10 * width, skull.y, 0.55 * height))
    ear_r = _mean(ear_r_pts) if ear_r_pts else Vector((-0.10 * width, skull.y, 0.55 * height))

    # Torso mass: mid height, not the tail, not the snout.
    torso = [
        c for c in coords
        if 0.28 * height < c.z < 0.92 * height
        and (ymin + 0.22 * length) < c.y < (ymax - 0.28 * length)
    ]
    body = _mean(torso) if torso else Vector((0.0, 0.0, 0.50 * height))

    chest = _band_mean(
        coords,
        y0=ymin + 0.18 * length,
        y1=body.y + 0.02 * length,
        z0=0.35 * height,
        z1=0.95 * height,
        fallback=Vector((0.0, (snout.y + body.y) * 0.5, 0.55 * height)),
    )
    pelvis = _band_mean(
        coords,
        y0=body.y,
        y1=ymax - 0.22 * length,
        z0=0.30 * height,
        z1=0.90 * height,
        fallback=Vector((0.0, (paws["hl"].y + paws["hr"].y) * 0.5, 0.48 * height)),
    )
    spine = Vector((
        0.0,
        chest.y * 0.45 + pelvis.y * 0.55,
        max(chest.z, pelvis.z) * 0.55 + 0.45 * zmax,
    ))
    # Keep the spine on the arch.
    arch_pts = [
        c for c in coords
        if abs(c.y - spine.y) < 0.08 * length and c.z > 0.55 * height and abs(c.x) < 0.12 * width
    ]
    if arch_pts:
        spine = Vector((0.0, spine.y, _mean(arch_pts).z))

    neck = Vector((
        0.0,
        skull.y * 0.45 + chest.y * 0.55,
        skull.z * 0.40 + chest.z * 0.60,
    ))
    head = Vector((0.0, skull.y * 0.65 + snout.y * 0.35, skull.z))
    snout_pt = Vector((0.0, snout.y, min(snout.z + 0.02 * height, head.z)))

    # Front paws sit under the neck, so do not climb the paw-cloud to the skull.
    # Place shoulders on the chest, then drop elbow / wrist toward each paw.
    shoulder_l = Vector((
        max(abs(paws["fl"].x) * 0.62, 0.055 * width),
        chest.y + 0.02 * length,
        chest.z * 0.78,
    ))
    shoulder_r = Vector((
        -max(abs(paws["fr"].x) * 0.62, 0.055 * width),
        chest.y + 0.02 * length,
        chest.z * 0.78,
    ))
    elbow_l = Vector((
        paws["fl"].x * 0.88,
        paws["fl"].y * 0.62 + shoulder_l.y * 0.38,
        0.20 * height,
    ))
    elbow_r = Vector((
        paws["fr"].x * 0.88,
        paws["fr"].y * 0.62 + shoulder_r.y * 0.38,
        0.20 * height,
    ))
    wrist_l = Vector((paws["fl"].x, paws["fl"].y + 0.012 * length, 0.075 * height))
    wrist_r = Vector((paws["fr"].x, paws["fr"].y + 0.012 * length, 0.075 * height))
    paw_l = Vector((paws["fl"].x, paws["fl"].y - 0.028 * length, max(paws["fl"].z, 0.012)))
    paw_r = Vector((paws["fr"].x, paws["fr"].y - 0.028 * length, max(paws["fr"].z, 0.012)))

    # Mild digitigrade, not a Y-zigzag: keep hock nearly above the paw.
    hip_l = Vector((paws["hl"].x * 0.62, pelvis.y, max(0.46 * height, pelvis.z * 0.86)))
    hip_r = Vector((paws["hr"].x * 0.62, pelvis.y, max(0.46 * height, pelvis.z * 0.86)))
    knee_l = Vector((paws["hl"].x * 0.78, hip_l.y - 0.022 * length, 0.28 * height))
    knee_r = Vector((paws["hr"].x * 0.78, hip_r.y - 0.022 * length, 0.28 * height))
    hock_l = Vector((paws["hl"].x * 0.92, paws["hl"].y + 0.012 * length, 0.11 * height))
    hock_r = Vector((paws["hr"].x * 0.92, paws["hr"].y + 0.012 * length, 0.11 * height))
    foot_l = Vector((paws["hl"].x, paws["hl"].y - 0.018 * length, max(paws["hl"].z, 0.012)))
    foot_r = Vector((paws["hr"].x, paws["hr"].y - 0.018 * length, max(paws["hr"].z, 0.012)))

    rump = Vector((0.0, pelvis.y + 0.06 * length, pelvis.z * 0.85))
    tail_pts = _sample_tail_from_mesh(coords, rump, 5, height)

    return {
        "height": Vector((height, length, width)),
        "pelvis": Vector((0.0, pelvis.y, pelvis.z)),
        "spine": Vector((0.0, spine.y, spine.z)),
        "chest": Vector((0.0, chest.y, chest.z)),
        "neck": Vector((0.0, neck.y, neck.z)),
        "head": Vector((0.0, head.y, head.z)),
        "snout": snout_pt,
        "ear_l": ear_l,
        "ear_r": ear_r,
        "shoulder_l": shoulder_l,
        "shoulder_r": shoulder_r,
        "elbow_l": elbow_l,
        "elbow_r": elbow_r,
        "wrist_l": wrist_l,
        "wrist_r": wrist_r,
        "paw_l": paw_l,
        "paw_r": paw_r,
        "hip_l": hip_l,
        "hip_r": hip_r,
        "knee_l": knee_l,
        "knee_r": knee_r,
        "hock_l": hock_l,
        "hock_r": hock_r,
        "foot_l": foot_l,
        "foot_r": foot_r,
        "rump": rump,
        "tail1": tail_pts[0],
        "tail2": tail_pts[1],
        "tail3": tail_pts[2],
        "tail4": tail_pts[3],
        "tail5": tail_pts[4],
        "paw_fl": paws["fl"],
        "paw_fr": paws["fr"],
        "paw_hl": paws["hl"],
        "paw_hr": paws["hr"],
    }


def print_landmarks(j: dict[str, Vector]) -> None:
    h, length, width = j["height"].x, j["height"].y, j["height"].z
    print(f"  size  height={h:.3f} length={length:.3f} width={width:.3f}")
    for key in (
        "pelvis", "spine", "chest", "neck", "head", "snout",
        "shoulder_l", "elbow_l", "wrist_l", "paw_l",
        "hip_l", "knee_l", "hock_l", "foot_l",
        "rump", "tail1", "tail3", "tail5",
        "ear_l", "ear_r",
    ):
        v = j[key]
        print(f"    {key:12s}  ({v.x:+.3f}, {v.y:+.3f}, {v.z:+.3f})")


# ── Armature ──────────────────────────────────────────────────────────────

def add_edit_bone(
    arm_data: bpy.types.Armature,
    name: str,
    head: Vector,
    tail: Vector,
    parent: str | None = None,
    *,
    connect: bool = False,
    align: Vector | None = None,
    deform: bool = True,
) -> bpy.types.EditBone:
    bone = arm_data.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    if (tail - head).length < 0.010:
        bone.tail = head + Vector((0.0, -0.014, 0.0))
    bone.use_deform = deform
    if parent:
        bone.parent = arm_data.edit_bones[parent]
        bone.use_connect = connect
    if align is not None:
        bone.align_roll(align)
    return bone


def build_armature(j: dict[str, Vector]) -> bpy.types.Object:
    arm_data = bpy.data.armatures.new("GiantRatArmatureData")
    arm = bpy.data.objects.new("GiantRatArmature", arm_data)
    bpy.context.collection.objects.link(arm)
    select_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")

    up = Vector((0.0, 0.0, 1.0))
    fwd = Vector((0.0, -1.0, 0.0))
    height = j["height"].x
    ear_len = max(0.045 * height, 0.028)

    add_edit_bone(arm_data, "Root", Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.04 * height)), align=fwd, deform=False)
    add_edit_bone(arm_data, "Pelvis", j["pelvis"], j["spine"], "Root", align=up)
    add_edit_bone(arm_data, "Spine", j["spine"], j["chest"], "Pelvis", connect=True, align=up)
    add_edit_bone(arm_data, "Chest", j["chest"], j["neck"], "Spine", connect=True, align=up)
    add_edit_bone(arm_data, "Neck", j["neck"], j["head"], "Chest", connect=True, align=up)
    add_edit_bone(arm_data, "Head", j["head"], j["snout"], "Neck", connect=True, align=up)

    add_edit_bone(arm_data, "Ear_L", j["ear_l"], j["ear_l"] + Vector((0.02, 0.0, ear_len)), "Head", align=fwd)
    add_edit_bone(arm_data, "Ear_R", j["ear_r"], j["ear_r"] + Vector((-0.02, 0.0, ear_len)), "Head", align=fwd)

    add_edit_bone(arm_data, "Shoulder_L", j["shoulder_l"], j["elbow_l"], "Chest", align=fwd)
    add_edit_bone(arm_data, "Elbow_L", j["elbow_l"], j["wrist_l"], "Shoulder_L", connect=True, align=fwd)
    add_edit_bone(arm_data, "Wrist_L", j["wrist_l"], j["paw_l"], "Elbow_L", connect=True, align=up)
    add_edit_bone(arm_data, "Paw_L", j["paw_l"], j["paw_l"] + Vector((0.0, -0.03, 0.0)), "Wrist_L", connect=True, align=up)
    add_edit_bone(arm_data, "Shoulder_R", j["shoulder_r"], j["elbow_r"], "Chest", align=fwd)
    add_edit_bone(arm_data, "Elbow_R", j["elbow_r"], j["wrist_r"], "Shoulder_R", connect=True, align=fwd)
    add_edit_bone(arm_data, "Wrist_R", j["wrist_r"], j["paw_r"], "Elbow_R", connect=True, align=up)
    add_edit_bone(arm_data, "Paw_R", j["paw_r"], j["paw_r"] + Vector((0.0, -0.03, 0.0)), "Wrist_R", connect=True, align=up)

    add_edit_bone(arm_data, "Hip_L", j["hip_l"], j["knee_l"], "Pelvis", align=fwd)
    add_edit_bone(arm_data, "Knee_L", j["knee_l"], j["hock_l"], "Hip_L", connect=True, align=fwd)
    add_edit_bone(arm_data, "Hock_L", j["hock_l"], j["foot_l"], "Knee_L", connect=True, align=up)
    add_edit_bone(arm_data, "Foot_L", j["foot_l"], j["foot_l"] + Vector((0.0, -0.032, 0.0)), "Hock_L", connect=True, align=up)
    add_edit_bone(arm_data, "Hip_R", j["hip_r"], j["knee_r"], "Pelvis", align=fwd)
    add_edit_bone(arm_data, "Knee_R", j["knee_r"], j["hock_r"], "Hip_R", connect=True, align=fwd)
    add_edit_bone(arm_data, "Hock_R", j["hock_r"], j["foot_r"], "Knee_R", connect=True, align=up)
    add_edit_bone(arm_data, "Foot_R", j["foot_r"], j["foot_r"] + Vector((0.0, -0.032, 0.0)), "Hock_R", connect=True, align=up)

    add_edit_bone(arm_data, "Tail1", j["rump"], j["tail1"], "Pelvis", align=up)
    add_edit_bone(arm_data, "Tail2", j["tail1"], j["tail2"], "Tail1", connect=True, align=up)
    add_edit_bone(arm_data, "Tail3", j["tail2"], j["tail3"], "Tail2", connect=True, align=up)
    add_edit_bone(arm_data, "Tail4", j["tail3"], j["tail4"], "Tail3", connect=True, align=up)
    add_edit_bone(arm_data, "Tail5", j["tail4"], j["tail5"], "Tail4", connect=True, align=up)

    bpy.ops.object.mode_set(mode="OBJECT")
    arm.display_type = "WIRE"
    arm.show_in_front = True
    arm.data.display_type = "OCTAHEDRAL"
    return arm


def _dist_to_segment(p: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    length_sq = ab.length_squared
    if length_sq < 1e-10:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / length_sq))
    return (p - (a + ab * t)).length


def skin(mesh: bpy.types.Object, arm: bpy.types.Object, j: dict[str, Vector]) -> None:
    """Proximity weights with region masks. Heat weighting fails on thin paws / tail / whiskers."""
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE")
    mod = next((m for m in mesh.modifiers if m.type == "ARMATURE"), None)
    if mod is None:
        mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False

    while mesh.vertex_groups:
        mesh.vertex_groups.remove(mesh.vertex_groups[0])
    groups = {b.name: mesh.vertex_groups.new(name=b.name) for b in arm.data.bones if b.use_deform}

    height = j["height"].x
    length = j["height"].y
    segments = {
        b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local)
        for b in arm.data.bones if b.use_deform
    }
    falloff = {
        "Pelvis": 0.20 * height,
        "Spine": 0.18 * height,
        "Chest": 0.20 * height,
        "Neck": 0.11 * height,
        "Head": 0.16 * height,
        "Ear_L": 0.09 * height,
        "Ear_R": 0.09 * height,
        "Shoulder_L": 0.13 * height,
        "Elbow_L": 0.09 * height,
        "Wrist_L": 0.07 * height,
        "Paw_L": 0.09 * height,
        "Shoulder_R": 0.13 * height,
        "Elbow_R": 0.09 * height,
        "Wrist_R": 0.07 * height,
        "Paw_R": 0.09 * height,
        "Hip_L": 0.16 * height,
        "Knee_L": 0.11 * height,
        "Hock_L": 0.09 * height,
        "Foot_L": 0.10 * height,
        "Hip_R": 0.16 * height,
        "Knee_R": 0.11 * height,
        "Hock_R": 0.09 * height,
        "Foot_R": 0.10 * height,
        "Tail1": 0.16 * height,
        "Tail2": 0.14 * height,
        "Tail3": 0.13 * height,
        "Tail4": 0.12 * height,
        "Tail5": 0.11 * height,
    }

    front_leg = {
        "L": ("Shoulder_L", "Elbow_L", "Wrist_L", "Paw_L"),
        "R": ("Shoulder_R", "Elbow_R", "Wrist_R", "Paw_R"),
    }
    hind_leg = {
        "L": ("Hip_L", "Knee_L", "Hock_L", "Foot_L"),
        "R": ("Hip_R", "Knee_R", "Hock_R", "Foot_R"),
    }
    tail_names = ("Tail1", "Tail2", "Tail3", "Tail4", "Tail5")
    ear_names = ("Ear_L", "Ear_R")

    chest_y = j["chest"].y
    pelvis_y = j["pelvis"].y
    head_y = j["head"].y
    rump_y = j["rump"].y
    counts = {name: 0 for name in groups}

    def chain_dist(names: tuple[str, ...], co: Vector) -> float:
        return min(_dist_to_segment(co, *segments[n]) for n in names)

    for vert in mesh.data.vertices:
        co = mesh.matrix_world @ vert.co
        weights: dict[str, float] = {}
        for name, (a, b) in segments.items():
            d = _dist_to_segment(co, a, b)
            radius = falloff[name]
            w = max(0.0, 1.0 - d / radius)
            if w > 0.0:
                weights[name] = w * w

        d_fl = chain_dist(front_leg["L"], co)
        d_fr = chain_dist(front_leg["R"], co)
        d_hl = chain_dist(hind_leg["L"], co)
        d_hr = chain_dist(hind_leg["R"], co)
        d_head = _dist_to_segment(co, *segments["Head"])
        d_neck = _dist_to_segment(co, *segments["Neck"])
        d_tail = min(chain_dist(tail_names, co), _dist_to_segment(co, *segments["Tail5"]))
        d_ear_l = _dist_to_segment(co, *segments["Ear_L"])
        d_ear_r = _dist_to_segment(co, *segments["Ear_R"])

        d_paw = min(
            (co - j["paw_fl"]).length,
            (co - j["paw_fr"]).length,
            (co - j["paw_hl"]).length,
            (co - j["paw_hr"]).length,
        )
        near_foot = co.z < 0.09 * height and d_paw < 0.12 * length

        behind_hips = co.y > rump_y + 0.05 * length
        in_tail = behind_hips and co.z > 0.055 * height
        in_front_leg = (
            not in_tail
            and min(d_fl, d_fr) < 0.12 * height
            and co.y < chest_y + 0.08 * length
            and co.z < 0.60 * height
        )
        in_hind_leg = (
            not in_tail
            and min(d_hl, d_hr) < 0.16 * height
            and co.y > pelvis_y - 0.12 * length
            and co.z < 0.68 * height
        )
        in_head = (
            not in_front_leg
            and d_head < 0.18 * height
            and co.y < head_y + 0.10 * length
            and co.z > 0.22 * height
        )
        in_neck = d_neck < 0.10 * height and not in_head and not in_front_leg
        in_ear = min(d_ear_l, d_ear_r) < 0.08 * height and in_head

        if in_ear:
            side = "L" if d_ear_l <= d_ear_r else "R"
            keep = {f"Ear_{side}", "Head"}
            weights = {k: (v * (2.4 if k.startswith("Ear") else 0.5)) for k, v in weights.items() if k in keep} or {
                f"Ear_{side}": 1.0
            }
        elif in_head:
            keep = {"Head", "Neck", "Ear_L", "Ear_R"}
            weights = {k: (v * (2.2 if k == "Head" else 0.6)) for k, v in weights.items() if k in keep} or {
                "Head": 1.0
            }
        elif in_neck:
            keep = {"Neck", "Head", "Chest"}
            weights = {k: (v * (2.0 if k == "Neck" else 0.55)) for k, v in weights.items() if k in keep} or {
                "Neck": 1.0
            }
        elif in_tail:
            keep = set(tail_names)
            weights = {k: v for k, v in weights.items() if k in keep}
            if not weights:
                closest = min(tail_names, key=lambda n: _dist_to_segment(co, *segments[n]))
                weights = {closest: 1.0}
        elif in_front_leg or (near_foot and co.y < chest_y):
            side = "L" if d_fl <= d_fr else "R"
            keep = set(front_leg[side])
            weights = {k: v for k, v in weights.items() if k in keep} or {
                f"Paw_{side}" if near_foot else f"Elbow_{side}": 1.0
            }
        elif in_hind_leg or (near_foot and co.y >= chest_y):
            side = "L" if d_hl <= d_hr else "R"
            keep = set(hind_leg[side])
            weights = {k: v for k, v in weights.items() if k in keep} or {
                f"Foot_{side}" if near_foot else f"Knee_{side}": 1.0
            }
        else:
            for k in list(weights):
                if k in ear_names:
                    weights[k] *= 0.15
                if k.startswith(("Shoulder", "Elbow", "Wrist", "Paw", "Hip", "Knee", "Hock", "Foot", "Tail")):
                    weights[k] *= 0.10

        total = sum(weights.values())
        if total <= 1e-8:
            if near_foot:
                if co.y < chest_y:
                    side = "L" if d_fl <= d_fr else "R"
                    weights = {f"Paw_{side}": 1.0}
                else:
                    side = "L" if d_hl <= d_hr else "R"
                    weights = {f"Foot_{side}": 1.0}
            elif in_tail:
                weights = {"Tail2": 1.0}
            elif co.y < head_y + 0.05 * length:
                weights = {"Head": 1.0}
            else:
                weights = {"Spine": 1.0}
            total = 1.0

        ranked = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)[:4]
        total = sum(w for _, w in ranked) or 1.0
        for g in groups.values():
            g.add([vert.index], 0.0, "REPLACE")
        for name, w in ranked:
            groups[name].add([vert.index], w / total, "REPLACE")
            counts[name] += 1

    print(f"  weight influence counts: {counts}")


# ── Animation ─────────────────────────────────────────────────────────────

def _set_action(arm: bpy.types.Object, action: bpy.types.Action) -> None:
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action


def _reset_pose(arm: bpy.types.Object) -> None:
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def _smooth_action(action: bpy.types.Action) -> None:
    for fcu in action.fcurves:
        for kp in fcu.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"


def _pulse(t: float, start: float, end: float) -> float:
    if t <= start or t >= end:
        return 0.0
    return math.sin(math.pi * (t - start) / (end - start))


def _begin_action(arm: bpy.types.Object, name: str, n_frames: int) -> bpy.types.Action:
    select_active(arm)
    bpy.ops.object.mode_set(mode="POSE")
    _reset_pose(arm)
    action = bpy.data.actions.new(name=name)
    action.use_fake_user = True
    _set_action(arm, action)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = n_frames
    scene.frame_current = 1
    return action


def _commit_nla(arm: bpy.types.Object, action: bpy.types.Action) -> None:
    _smooth_action(action)
    bpy.ops.object.mode_set(mode="OBJECT")
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = None
    track = arm.animation_data.nla_tracks.new()
    track.name = action.name
    track.strips.new(action.name, 1, action)


def key_euler(pb: bpy.types.PoseBone, frame: int, deg: tuple[float, float, float]) -> None:
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = (math.radians(deg[0]), math.radians(deg[1]), math.radians(deg[2]))
    pb.keyframe_insert(data_path="rotation_euler", frame=frame)


def key_loc(pb: bpy.types.PoseBone, frame: int, loc: tuple[float, float, float]) -> None:
    pb.location = loc
    pb.keyframe_insert(data_path="location", frame=frame)


def _gait_frames(n_frames: int):
    return range(1, n_frames + 2)


def _key_front_leg(
    bones,
    side: str,
    frame: int,
    swing: float,
    plant: float,
    *,
    amp: float = 1.0,
) -> None:
    """Sagittal stride. Rest pose is 0; do not bake a locked crouch into idle."""
    lift = 1.0 - plant
    shoulder = 28.0 * amp * swing
    elbow = 36.0 * amp * lift - 8.0 * amp * swing
    wrist = -8.0 * amp * swing - 12.0 * amp * lift
    paw = -6.0 * amp * lift
    key_euler(bones[f"Shoulder_{side}"], frame, (shoulder, 0.0, 0.0))
    key_euler(bones[f"Elbow_{side}"], frame, (elbow, 0.0, 0.0))
    key_euler(bones[f"Wrist_{side}"], frame, (wrist, 0.0, 0.0))
    key_euler(bones[f"Paw_{side}"], frame, (paw, 0.0, 0.0))


def _key_hind_leg(
    bones,
    side: str,
    frame: int,
    swing: float,
    plant: float,
    *,
    amp: float = 1.0,
) -> None:
    lift = 1.0 - plant
    hip = 30.0 * amp * swing
    knee = 34.0 * amp * lift - 8.0 * amp * swing
    hock = -8.0 * amp * swing - 14.0 * amp * lift
    foot = -7.0 * amp * lift
    key_euler(bones[f"Hip_{side}"], frame, (hip, 0.0, 0.0))
    key_euler(bones[f"Knee_{side}"], frame, (knee, 0.0, 0.0))
    key_euler(bones[f"Hock_{side}"], frame, (hock, 0.0, 0.0))
    key_euler(bones[f"Foot_{side}"], frame, (foot, 0.0, 0.0))


def _key_tail(bones, frame: int, sway: float, pitch: float) -> None:
    key_euler(bones["Tail1"], frame, (pitch * 0.30, 0.0, sway * 0.20))
    key_euler(bones["Tail2"], frame, (pitch * 0.45, 0.0, sway * 0.35))
    key_euler(bones["Tail3"], frame, (pitch * 0.55, 0.0, sway * 0.50))
    key_euler(bones["Tail4"], frame, (pitch * 0.40, 0.0, sway * 0.70))
    key_euler(bones["Tail5"], frame, (pitch * 0.25, 0.0, sway * 0.85))


def _key_ears(bones, frame: int, flick_l: float, flick_r: float, breathe: float) -> None:
    key_euler(bones["Ear_L"], frame, (8.0 * flick_l - 2.0 * breathe, 0.0, -6.0 * flick_l))
    key_euler(bones["Ear_R"], frame, (8.0 * flick_r - 2.0 * breathe, 0.0, 6.0 * flick_r))


def animate_idle(arm: bpy.types.Object, height: float) -> bpy.types.Action:
    action = _begin_action(arm, "idle", CLIP_IDLE)
    bones = arm.pose.bones
    two_pi = 2.0 * math.pi

    for frame in _gait_frames(CLIP_IDLE):
        t = (frame - 1) / CLIP_IDLE
        breathe = math.sin(two_pi * t)
        look = math.sin(two_pi * t)
        sniff = _pulse(t, 0.18, 0.34)
        glance = _pulse(t, 0.58, 0.78)
        flick_l = _pulse(t, 0.12, 0.22) + 0.45 * _pulse(t, 0.70, 0.80)
        flick_r = _pulse(t, 0.42, 0.52) + 0.35 * _pulse(t, 0.88, 0.98)

        key_euler(bones["Pelvis"], frame, (0.0, 0.0, 0.0))
        key_loc(bones["Pelvis"], frame, (0.0, 0.0, 0.0))
        key_euler(bones["Spine"], frame, (3.2 * breathe - 4.0 * sniff, 0.0, 2.0 * look))
        key_euler(bones["Chest"], frame, (4.2 * breathe - 5.0 * sniff, 0.0, 2.8 * look))
        key_euler(bones["Neck"], frame, (-2.5 * breathe - 10.0 * sniff + 5.0 * glance, 0.0, 10.0 * look))
        key_euler(bones["Head"], frame, (
            -4.0 * breathe + 12.0 * sniff - 5.0 * glance,
            0.0,
            16.0 * look + 10.0 * glance,
        ))
        _key_ears(bones, frame, flick_l, flick_r, breathe)
        _key_front_leg(bones, "L", frame, 0.0, 1.0, amp=0.0)
        _key_front_leg(bones, "R", frame, 0.0, 1.0, amp=0.0)
        _key_hind_leg(bones, "L", frame, 0.0, 1.0, amp=0.0)
        _key_hind_leg(bones, "R", frame, 0.0, 1.0, amp=0.0)
        _key_tail(bones, frame, sway=5.0 * look, pitch=-3.0 * breathe)

    _commit_nla(arm, action)
    return action


def animate_walk(arm: bpy.types.Object, height: float) -> bpy.types.Action:
    action = _begin_action(arm, "walk", CLIP_WALK)
    bones = arm.pose.bones
    two_pi = 2.0 * math.pi

    for frame in _gait_frames(CLIP_WALK):
        t = (frame - 1) / CLIP_WALK
        # Diagonal trot: front-left with hind-right.
        fl = math.sin(two_pi * t)
        fr = math.sin(two_pi * t + math.pi)
        fl_plant = 0.5 + 0.5 * math.cos(two_pi * t)
        fr_plant = 0.5 + 0.5 * math.cos(two_pi * t + math.pi)
        bob = math.sin(two_pi * 2.0 * t)
        stride = math.sin(two_pi * t)

        key_euler(bones["Pelvis"], frame, (-2.0 + 2.2 * abs(fl), 0.0, 5.0 * stride))
        key_loc(bones["Pelvis"], frame, (0.0, 0.0, 0.006 * height * abs(bob)))
        key_euler(bones["Spine"], frame, (2.0 * bob, 0.0, 3.0 * stride))
        key_euler(bones["Chest"], frame, (-1.5 + 2.5 * abs(fr), 0.0, -4.0 * stride))
        key_euler(bones["Neck"], frame, (-2.5 * bob, 0.0, -2.5 * stride))
        key_euler(bones["Head"], frame, (3.5 * bob, 0.0, 1.5 * stride))
        _key_ears(bones, frame, 0.15 + 0.10 * fl, 0.15 + 0.10 * fr, 0.3 * bob)
        _key_front_leg(bones, "L", frame, fl, fl_plant)
        _key_front_leg(bones, "R", frame, fr, fr_plant)
        _key_hind_leg(bones, "L", frame, fr, fr_plant)
        _key_hind_leg(bones, "R", frame, fl, fl_plant)
        _key_tail(bones, frame, sway=-6.0 * stride, pitch=-3.0 * bob)

    _commit_nla(arm, action)
    return action


def animate_attack1(arm: bpy.types.Object, height: float) -> bpy.types.Action:
    """In-place bite. Hind feet stay planted; clip loops from rest."""
    action = _begin_action(arm, "attack1", CLIP_ATTACK)
    bones = arm.pose.bones

    for frame in _gait_frames(CLIP_ATTACK):
        t = (frame - 1) / CLIP_ATTACK
        coil = _pulse(t, 0.00, 0.30)
        strike = _pulse(t, 0.16, 0.50)

        key_euler(bones["Pelvis"], frame, (0.0, 0.0, 0.0))
        key_loc(bones["Pelvis"], frame, (0.0, 0.0, 0.0))
        key_euler(bones["Spine"], frame, (8.0 * coil - 12.0 * strike, 0.0, 0.0))
        key_euler(bones["Chest"], frame, (10.0 * coil - 16.0 * strike, 0.0, 0.0))
        key_euler(bones["Neck"], frame, (18.0 * coil - 32.0 * strike, 0.0, 0.0))
        key_euler(bones["Head"], frame, (14.0 * coil - 26.0 * strike, 0.0, 0.0))
        _key_ears(bones, frame, 0.35 * coil, 0.35 * coil, -0.4 * strike)
        _key_front_leg(bones, "L", frame, 0.40 * strike, 1.0 - 0.22 * strike, amp=0.50)
        _key_front_leg(bones, "R", frame, 0.40 * strike, 1.0 - 0.22 * strike, amp=0.50)
        _key_hind_leg(bones, "L", frame, 0.0, 1.0, amp=0.0)
        _key_hind_leg(bones, "R", frame, 0.0, 1.0, amp=0.0)
        _key_tail(bones, frame, sway=8.0 * strike, pitch=10.0 * coil - 8.0 * strike)

    _commit_nla(arm, action)
    return action


# ── Export ────────────────────────────────────────────────────────────────

def report(mesh: bpy.types.Object, arm: bpy.types.Object, actions: list[bpy.types.Action]) -> None:
    n_verts = len(mesh.data.vertices)
    n_tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    mats = [m.name if m else "<none>" for m in mesh.data.materials]
    mw = mesh.matrix_world
    verts = [mw @ v.co for v in mesh.data.vertices]
    xs, ys, zs = [v.x for v in verts], [v.y for v in verts], [v.z for v in verts]
    print(f"  [{mesh.name}] verts={n_verts} tris={n_tris}")
    print(f"  [{mesh.name}] mats={mats}")
    print(
        f"  [{mesh.name}] bounds X[{min(xs):+.3f},{max(xs):+.3f}]  "
        f"Y[{min(ys):+.3f},{max(ys):+.3f}]  Z[{min(zs):+.3f},{max(zs):+.3f}]"
    )
    print(f"  bones: {[b.name for b in arm.data.bones]}")
    for action in actions:
        n_frames = int(round(action.frame_range[1] - action.frame_range[0]))
        print(
            f"  action '{action.name}'  ~{n_frames} frames @ {FPS} fps "
            f"({n_frames / FPS:.3f} s)  fcurves={len(action.fcurves)}"
        )


def export_glb(path: str, arm: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    arm.hide_set(False)
    arm.select_set(True)
    for child in arm.children:
        child.hide_set(False)
        child.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_skins=True,
        export_animations=True,
        export_animation_mode="NLA_TRACKS",
        export_force_sampling=True,
        export_nla_strips=True,
        export_anim_single_armature=True,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )


def main() -> None:
    print("=== Giant Rat (authored mesh → quadruped idle/walk/attack1) ===")
    print(f"  source: {SRC_GLB}")
    clear_scene()
    mesh = import_authored_mesh(SRC_GLB, "GiantRat")
    j = landmarks_from_mesh(mesh)
    print_landmarks(j)
    arm = build_armature(j)
    skin(mesh, arm, j)
    height = j["height"].x
    actions = [
        animate_idle(arm, height),
        animate_walk(arm, height),
        animate_attack1(arm, height),
    ]
    report(mesh, arm, actions)

    keep = {arm, mesh}
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)

    out = os.path.join(VIEWER_DIR, "GiantRat.glb")
    export_glb(out, arm)
    print(f"  -> {out} ({os.path.getsize(out) / 1024.0:.1f} KB)")
    print("DONE")


if __name__ == "__main__":
    main()
