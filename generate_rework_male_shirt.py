"""
generate_rework_male_shirt.py
=============================
Loft a shirt cage from the measured torso hull plus garment ease.
Collision only pushes verts that go inside the body.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
    --python generate_rework_male_shirt.py

Output:
  viewer/public/equipment/Rework/Male/shirt.glb
"""

from __future__ import annotations

import json
import math
import os

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_GLB = os.path.join(ROOT, "viewer/public/models/BaseMaleRework.glb")
OUT_DIR = os.path.join(ROOT, "viewer/public/equipment/Rework/Male")
OUT_GLB = os.path.join(OUT_DIR, "shirt.glb")

# Shirt sits just outside the measured BaseMaleRework hull. Not skin-tight, not a puffy ellipse.
EASE = 0.012
HEM_EASE = 0.016
NECK_EASE = 0.008
FRONT_PEC_EASE = 0.008
SLEEVE_R = 0.054
SLEEVE_ROOT_EXTRA = 0.006
DOCK = 0.010
COLLISION_CLEARANCE = 0.012
SLEEVE_CLEARANCE = 0.012
THICKNESS = 0.004
HEM_BELOW_HIPS = 0.032
COLLAR_ABOVE_NECK = 0.012
CUFF_BEFORE_WRIST = 0.016
TORSO_SEGS = 24
SLEEVE_SEGS = 12
TORSO_RINGS = 14
SLEEVE_RINGS = 6
LINEN = (0.72, 0.64, 0.52)
VIEWER_HEIGHT_SCALE = 1.9 / 1.75


def normalize_bone_name(name: str) -> str:
    if name.startswith("mixamorig:"):
        return name[len("mixamorig:") :]
    if name.startswith("mixamorig"):
        return name[len("mixamorig") :]
    return name


def bone_key_map(arm: bpy.types.Object) -> dict[str, bpy.types.PoseBone]:
    return {normalize_bone_name(pb.name): pb for pb in arm.pose.bones}


def bone_world(arm: bpy.types.Object, pb: bpy.types.PoseBone) -> tuple[Vector, Vector]:
    mw = arm.matrix_world
    return mw @ pb.head, mw @ pb.tail


def world_points(mesh: bpy.types.Object) -> list[Vector]:
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    mw = ev.matrix_world
    return [mw @ v.co.copy() for v in ev.data.vertices]


def lerp(a: Vector, b: Vector, t: float) -> Vector:
    return a.lerp(b, t)


def _torso_max_ax(t: float) -> float:
    if t < 0.92:
        return 0.22
    return 0.09


def _torso_ease(t: float) -> float:
    if t < 0.16:
        return HEM_EASE
    if t > 0.92:
        return NECK_EASE
    return EASE


def _front_pec_extra(t: float, ang: float) -> float:
    """Front pec / deltoid chords undershoot a linear loft. Extra ease there only."""
    if not (0.48 <= t <= 0.92):
        return 0.0
    front = math.sin(ang)
    if front < 0.12:
        return 0.0
    return FRONT_PEC_EASE * min(1.0, (front - 0.12) / 0.55)


def measure_hull_radii(
    pts: list[Vector],
    z: float,
    dz: float,
    segs: int,
    max_ax: float,
    cy: float = 0.02,
) -> list[float]:
    radii = [0.0] * segs
    for p in pts:
        if abs(p.z - z) > dz or abs(p.x) > max_ax:
            continue
        dx = p.x
        dy = p.y - cy
        r = math.hypot(dx, dy)
        i = int((math.atan2(dy, dx) + math.pi) / (2.0 * math.pi) * segs) % segs
        for j in (i, (i - 1) % segs, (i + 1) % segs):
            if r > radii[j]:
                radii[j] = r
    for i in range(segs):
        if radii[i] > 1e-4:
            continue
        filled = 0.0
        for span in range(1, segs // 2 + 1):
            a = radii[(i - span) % segs]
            b = radii[(i + span) % segs]
            if a > 0 and b > 0:
                filled = 0.5 * (a + b)
                break
            if a > 0:
                filled = a
                break
            if b > 0:
                filled = b
                break
        radii[i] = filled if filled > 1e-4 else 0.12
    return radii


def hull_ring_pts(
    z: float,
    radii: list[float],
    ease: float,
    t: float,
    cy: float = 0.02,
) -> list[Vector]:
    segs = len(radii)
    pts = []
    for i in range(segs):
        ang = -math.pi + 2.0 * math.pi * i / segs
        r = radii[i] + ease + _front_pec_extra(t, ang)
        pts.append(Vector((math.cos(ang) * r, cy + math.sin(ang) * r, z)))
    return pts


def _ring(center: Vector, axis: Vector, rx: float, ry: float, segs: int) -> list[Vector]:
    axis = axis.normalized()
    up = Vector((0.0, 0.0, 1.0))
    if abs(axis.dot(up)) > 0.85:
        up = Vector((0.0, 1.0, 0.0))
    side = axis.cross(up).normalized()
    up = side.cross(axis).normalized()
    return [
        center
        + side * (rx * math.cos(2.0 * math.pi * i / segs))
        + up * (ry * math.sin(2.0 * math.pi * i / segs))
        for i in range(segs)
    ]


def _add_ring(bm: bmesh.types.BMesh, pts: list[Vector]) -> list[bmesh.types.BMVert]:
    return [bm.verts.new(p) for p in pts]


def _loft(bm: bmesh.types.BMesh, rows: list[list[bmesh.types.BMVert]], skip_side: bool = False, shoulder_z: float = 0.0) -> int:
    skipped = 0
    segs = len(rows[0])
    for ri in range(len(rows) - 1):
        midz = 0.5 * (rows[ri][0].co.z + rows[ri + 1][0].co.z)
        near_sh = skip_side and abs(midz - shoulder_z) < 0.055
        for si in range(segs):
            sj = (si + 1) % segs
            vs = [rows[ri][si], rows[ri][sj], rows[ri + 1][sj], rows[ri + 1][si]]
            if near_sh:
                cx = sum(v.co.x for v in vs) * 0.25
                cy = sum(v.co.y for v in vs) * 0.25
                if abs(cx) > 0.09 and abs(cy) < 0.09:
                    skipped += 1
                    continue
            try:
                bm.faces.new(vs)
            except ValueError:
                pass
    return skipped


def _bridge(bm: bmesh.types.BMesh, a: list[bmesh.types.BMVert], b: list[bmesh.types.BMVert]) -> None:
    na, nb = len(a), len(b)
    if na < 3 or nb < 3:
        return
    steps = max(na, nb)
    for i in range(steps):
        ia0 = int(i * na / steps) % na
        ia1 = int((i + 1) * na / steps) % na
        ib0 = int(i * nb / steps) % nb
        ib1 = int((i + 1) * nb / steps) % nb
        try:
            if ia0 == ia1:
                bm.faces.new([a[ia0], b[ib0], b[ib1]])
            elif ib0 == ib1:
                bm.faces.new([a[ia0], a[ia1], b[ib0]])
            else:
                bm.faces.new([a[ia0], a[ia1], b[ib1], b[ib0]])
        except ValueError:
            pass


def _align(loop: list[bmesh.types.BMVert], target: list[bmesh.types.BMVert]) -> list[bmesh.types.BMVert]:
    if len(loop) < 3 or not target:
        return loop
    best_i, best_d = 0, 1e9
    for i, v in enumerate(loop):
        d = (v.co - target[0].co).length
        if d < best_d:
            best_i, best_d = i, d
    rot = loop[best_i:] + loop[:best_i]
    if len(rot) > 2 and (rot[1].co - target[min(1, len(target) - 1)].co).length > (
        rot[-1].co - target[min(1, len(target) - 1)].co
    ).length:
        rot = [rot[0]] + list(reversed(rot[1:]))
    return rot


def _punch_armholes(bm: bmesh.types.BMesh, sh_z: float, collar_z: float) -> int:
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        if abs(c.x) < 0.11 or abs(c.y) > 0.07 or c.z > collar_z - 0.058:
            continue
        target = Vector((math.copysign(0.175, c.x), 0.02, sh_z - 0.018))
        if (c - target).length < 0.072:
            kill.append(f)
    n = len(kill)
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    return n


def _order_loop(verts: list[bmesh.types.BMVert], axis: Vector) -> list[bmesh.types.BMVert]:
    if len(verts) < 3:
        return verts
    mid = sum((v.co.copy() for v in verts), Vector((0, 0, 0))) / len(verts)
    axis = axis.normalized()
    ref = Vector((0.0, 0.0, 1.0))
    if abs(axis.dot(ref)) > 0.9:
        ref = Vector((0.0, 1.0, 0.0))
    x_axis = axis.cross(ref).normalized()
    y_axis = axis.cross(x_axis).normalized()
    return sorted(verts, key=lambda v: math.atan2((v.co - mid).dot(y_axis), (v.co - mid).dot(x_axis)))


def _boundary_loop(bm: bmesh.types.BMesh, sign: float, z: float) -> list[bmesh.types.BMVert]:
    used: set[bmesh.types.BMEdge] = set()
    best: list[bmesh.types.BMVert] = []
    best_score = 1e9
    for e0 in bm.edges:
        if len(e0.link_faces) != 1 or e0 in used:
            continue
        verts = [e0.verts[0]]
        e = e0
        v = e0.verts[1]
        used.add(e0)
        for _ in range(48):
            verts.append(v)
            nxt = next((ne for ne in v.link_edges if ne is not e and len(ne.link_faces) == 1 and ne not in used), None)
            if nxt is None:
                break
            used.add(nxt)
            e = nxt
            v = nxt.other_vert(v)
            if v == verts[0]:
                break
        if len(verts) < 4:
            continue
        mid = sum((p.co for p in verts), Vector((0, 0, 0))) / len(verts)
        if mid.x * sign <= 0.04:
            continue
        score = abs(mid.z - z) + abs(abs(mid.x) - 0.16)
        if score < best_score:
            best_score = score
            best = verts
    return best


def build_shirt_cage(
    hem_z: float,
    collar_z: float,
    body_pts: list[Vector],
    l_sh: Vector,
    l_elb: Vector,
    l_wrist: Vector,
    r_sh: Vector,
    r_elb: Vector,
    r_wrist: Vector,
) -> tuple[bpy.types.Object, dict]:
    """Loft a shirt from measured torso hull rings plus garment ease."""
    bm = bmesh.new()
    topo: dict = {"method": "hull+ease", "rings": []}

    torso_rows: list[list[bmesh.types.BMVert]] = []
    for i in range(TORSO_RINGS):
        t = i / (TORSO_RINGS - 1)
        z = hem_z + (collar_z - hem_z) * t
        ease = _torso_ease(t)
        radii = measure_hull_radii(body_pts, z, 0.020, TORSO_SEGS, _torso_max_ax(t))
        torso_rows.append(_add_ring(bm, hull_ring_pts(z, radii, ease, t)))
        topo["rings"].append({
            "t": round(t, 2),
            "z": round(z, 3),
            "ease": round(ease, 4),
            "rMin": round(min(radii), 4),
            "rMax": round(max(radii), 4),
        })
    skipped = _loft(bm, torso_rows, skip_side=False, shoulder_z=l_sh.z)
    topo["skippedArmholeFaces"] = skipped
    topo["punchedArmholeFaces"] = _punch_armholes(bm, l_sh.z, collar_z)
    left_hole = _order_loop(_boundary_loop(bm, 1.0, l_sh.z), Vector((1.0, 0.0, 0.0)))
    right_hole = _order_loop(_boundary_loop(bm, -1.0, r_sh.z), Vector((-1.0, 0.0, 0.0)))
    topo["hole_1"] = len(left_hole)
    topo["hole_-1"] = len(right_hole)

    def add_sleeve(hole: list[bmesh.types.BMVert], elb: Vector, wrist: Vector, sign: float) -> None:
        if len(hole) < 4:
            return
        cuff = wrist - (wrist - elb).normalized() * CUFF_BEFORE_WRIST
        start = sum((v.co.copy() for v in hole), Vector((0, 0, 0))) / len(hole)
        dock: list[bmesh.types.BMVert] = []
        for v in hole:
            p = v.co.copy()
            away = Vector((sign, 0.12 if p.y < 0.04 else 0.20, 0.0))
            dock.append(bm.verts.new(p + away.normalized() * DOCK))
        _loft(bm, [hole, dock])
        path = [start + Vector((sign * 0.012, 0.0, 0.0)), lerp(start, elb, 0.50), elb, cuff]
        segs = len(path) - 1
        n = len(hole)
        rows: list[list[bmesh.types.BMVert]] = [dock]
        for i in range(1, SLEEVE_RINGS):
            t = i / (SLEEVE_RINGS - 1)
            f = t * segs
            idx = min(segs - 1, int(f))
            origin = lerp(path[idx], path[idx + 1], f - idx)
            direction = (path[idx + 1] - path[idx]).normalized()
            t_ease = max(0.0, 1.0 - t / 0.45)
            rad = SLEEVE_R + SLEEVE_ROOT_EXTRA * t_ease
            rows.append(_add_ring(bm, _ring(origin, direction, rad, rad, n)))
        rows[0] = _align(dock, rows[1])
        _loft(bm, rows)
        cuff_axis = (wrist - elb).normalized()
        cuff_ring = _add_ring(bm, _ring(cuff, cuff_axis, SLEEVE_R, SLEEVE_R, 16))
        _bridge(bm, rows[-1], cuff_ring)
        mid = start
        topo[f"holeMid_{int(sign)}"] = [round(mid.x, 3), round(mid.y, 3), round(mid.z, 3)]
        topo[f"cuffN_{int(sign)}"] = len(cuff_ring)

    add_sleeve(left_hole, l_elb, l_wrist, 1.0)
    add_sleeve(right_hole, r_elb, r_wrist, -1.0)
    fill_edges = []
    for e in bm.edges:
        if len(e.link_faces) != 1:
            continue
        mid = (e.verts[0].co + e.verts[1].co) * 0.5
        if abs(mid.x) > 0.30:
            continue
        fill_edges.append(e)
    bmesh.ops.holes_fill(bm, edges=fill_edges, sides=6)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.004)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mesh = bpy.data.meshes.new("ReworkMaleShirt")
    obj = bpy.data.objects.new("ReworkMaleShirt", mesh)
    bpy.context.collection.objects.link(obj)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj, topo


def apply_collision(mesh_obj: bpy.types.Object, body_obj: bpy.types.Object, clearance: float) -> dict:
    """Push only verts that penetrate the body. Cage shape is kept if already outside."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = body_obj.evaluated_get(deps)
    bvh = BVHTree.FromObject(ev, deps)
    mw = ev.matrix_world
    mwi = mw.inverted()
    rot = mw.to_3x3()
    smw = mesh_obj.matrix_world
    smwi = smw.inverted()
    pushed = 0
    kept = 0
    for v in mesh_obj.data.vertices:
        world = smw @ v.co
        hit, normal, *_ = bvh.find_nearest(mwi @ world)
        if hit is None:
            kept += 1
            continue
        world_hit = mw @ hit
        world_n = (rot @ normal).normalized()
        if world_n.length < 0.2:
            kept += 1
            continue
        if abs(world.x) > 0.20:
            need = SLEEVE_CLEARANCE
        else:
            need = clearance
        side = (world - world_hit).dot(world_n)
        if side < need:
            v.co = smwi @ (world_hit + world_n * need)
            pushed += 1
        else:
            kept += 1
    mesh_obj.data.update()
    print(f"  Collision +{clearance*1000:.0f}mm: pushed {pushed} kept {kept}")
    return {"pushed": pushed, "kept": kept}



def ensure_outward(obj: bpy.types.Object) -> None:
    mesh = obj.data
    if not mesh.polygons:
        return
    center = sum((v.co.copy() for v in mesh.vertices), Vector((0, 0, 0))) / len(mesh.vertices)
    score = 0.0
    for poly in mesh.polygons:
        score += poly.normal.dot(poly.center - center)
    if score >= 0:
        return
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.flip_normals()
    bpy.ops.object.mode_set(mode="OBJECT")


def assign_linen(obj: bpy.types.Object) -> None:
    mat = bpy.data.materials.new(f"{obj.name}_linen")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*LINEN, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.72
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True


def solidify(obj: bpy.types.Object, thickness: float) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new("ClothThickness", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_quality_normals = True
    bpy.ops.object.modifier_apply(modifier="ClothThickness")


def adopt_body_space(shirt: bpy.types.Object, body: bpy.types.Object) -> None:
    inv = body.matrix_world.inverted()
    shirt.data.transform(inv)
    shirt.data.update()
    shirt.parent = body.parent
    shirt.matrix_parent_inverse = body.matrix_parent_inverse.copy()
    shirt.location = body.location.copy()
    shirt.rotation_euler = body.rotation_euler.copy()
    shirt.scale = body.scale.copy()


def circularize_cuffs(mesh_obj: bpy.types.Object, radius: float) -> dict:
    """Force both evaluated cuff rings to a circle. Write a small rest delta."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(deps)
    ev_mw = ev.matrix_world
    smwi = mesh_obj.matrix_world.inverted()
    moved = {"left": 0, "right": 0}
    n = min(len(mesh_obj.data.vertices), len(ev.data.vertices))
    ev_pts = [ev_mw @ ev.data.vertices[i].co for i in range(n)]
    for sign, name in ((1.0, "left"), (-1.0, "right")):
        idxs = [i for i, p in enumerate(ev_pts) if p.x * sign > 0.46]
        if len(idxs) < 5:
            continue
        idxs.sort(key=lambda i: -abs(ev_pts[i].x))
        ring = idxs[:16]
        mid = sum((ev_pts[i] for i in ring), Vector((0, 0, 0))) / len(ring)
        axis = Vector((sign, 0.0, 0.0))
        for i in ring:
            p = ev_pts[i]
            rel = p - mid
            rel = rel - axis * rel.dot(axis)
            if rel.length < 1e-4:
                continue
            desired = mid + rel.normalized() * radius
            delta = desired - p
            if delta.length > 0.04:
                delta = delta.normalized() * 0.04
            base = mesh_obj.matrix_world @ mesh_obj.data.vertices[i].co
            mesh_obj.data.vertices[i].co = smwi @ (base + delta)
            moved[name] += 1
    mesh_obj.data.update()
    print(f"  circularize cuffs {moved}")
    return moved


def transfer_weights(body: bpy.types.Object, shirt: bpy.types.Object, arm: bpy.types.Object) -> None:
    for vg in body.vertex_groups:
        if vg.name not in shirt.vertex_groups:
            shirt.vertex_groups.new(name=vg.name)
    bpy.ops.object.select_all(action="DESELECT")
    shirt.select_set(True)
    bpy.context.view_layer.objects.active = shirt
    mod = shirt.modifiers.new("WeightTransfer", "DATA_TRANSFER")
    mod.object = body
    mod.use_vert_data = True
    mod.data_types_verts = {"VGROUP_WEIGHTS"}
    mod.vert_mapping = "POLYINTERP_NEAREST"
    bpy.ops.object.datalayout_transfer(modifier="WeightTransfer")
    bpy.ops.object.modifier_apply(modifier="WeightTransfer")
    if not any(m.type == "ARMATURE" for m in shirt.modifiers):
        amod = shirt.modifiers.new("Armature", "ARMATURE")
        amod.object = arm


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=== generate_rework_male_shirt (hull + ease) ===")
    print(
        f"  spec: ease {EASE*1000:.0f}mm sleeve {SLEEVE_R*1000:.0f} "
        f"collide +{COLLISION_CLEARANCE*1000:.0f}mm thick {THICKNESS*1000:.0f}mm"
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=SRC_GLB)
    bpy.context.view_layer.update()

    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    body = next(o for o in bpy.data.objects if o.type == "MESH")
    bones = bone_key_map(arm)
    for required in ("Hips", "Neck", "LeftArm", "LeftForeArm", "LeftHand", "RightArm", "RightForeArm", "RightHand"):
        if required not in bones:
            raise RuntimeError(f"Missing bone {required}: {list(bones)}")

    hips_h, _ = bone_world(arm, bones["Hips"])
    neck_h, _ = bone_world(arm, bones["Neck"])
    l_arm_h, _ = bone_world(arm, bones["LeftArm"])
    l_fa_h, _ = bone_world(arm, bones["LeftForeArm"])
    l_hand_h, _ = bone_world(arm, bones["LeftHand"])
    r_arm_h, _ = bone_world(arm, bones["RightArm"])
    r_fa_h, _ = bone_world(arm, bones["RightForeArm"])
    r_hand_h, _ = bone_world(arm, bones["RightHand"])

    hem_z = hips_h.z - HEM_BELOW_HIPS
    collar_z = neck_h.z + COLLAR_ABOVE_NECK
    body_pts = world_points(body)
    print(f"  hips_z={hips_h.z:.3f} neck_z={neck_h.z:.3f} hem={hem_z:.3f} collar={collar_z:.3f}")

    shirt, shirt_topo = build_shirt_cage(
        hem_z, collar_z, body_pts, l_arm_h, l_fa_h, l_hand_h, r_arm_h, r_fa_h, r_hand_h,
    )
    print("  cage", json.dumps(shirt_topo))
    apply_collision(shirt, body, COLLISION_CLEARANCE)
    ensure_outward(shirt)
    solidify(shirt, THICKNESS)
    assign_linen(shirt)
    adopt_body_space(shirt, body)
    transfer_weights(body, shirt, arm)
    circularize_cuffs(shirt, SLEEVE_R)
    bpy.context.view_layer.update()

    wpts = world_points(body)
    raw = [v.co.copy() for v in shirt.data.vertices]
    print(
        f"  shirt verts={len(shirt.data.vertices)} groups={len(shirt.vertex_groups)} "
        f"raw_bbox x={min(v.x for v in raw):.3f}..{max(v.x for v in raw):.3f} "
        f"z={min(v.z for v in raw):.3f}..{max(v.z for v in raw):.3f}"
    )
    deps = bpy.context.evaluated_depsgraph_get()
    ev = shirt.evaluated_get(deps)
    ev_pts = [ev.matrix_world @ v.co for v in ev.data.vertices]
    print(
        f"  eval_bbox x={min(p.x for p in ev_pts):.3f}..{max(p.x for p in ev_pts):.3f} "
        f"y={min(p.y for p in ev_pts):.3f}..{max(p.y for p in ev_pts):.3f} "
        f"z={min(p.z for p in ev_pts):.3f}..{max(p.z for p in ev_pts):.3f}"
    )
    body_z = [p.z for p in wpts]
    viewer_lift = -0.0001 - min(body_z) * VIEWER_HEIGHT_SCALE
    print(f"  body_z={min(body_z):.3f}..{max(body_z):.3f} viewer_z_lift={viewer_lift:.4f}")
    evb = body.evaluated_get(deps)
    bvh = BVHTree.FromObject(evb, deps)
    bmw = evb.matrix_world
    bmwi = bmw.inverted()
    brot = bmw.to_3x3()
    regions = {
        "pecFront": {"pred": lambda p: 0.36 <= p.z <= 0.52 and p.y > 0.06 and abs(p.x) <= 0.20},
        "shoulder": {"pred": lambda p: 0.48 <= p.z <= 0.58 and p.y > 0.03 and 0.10 <= abs(p.x) <= 0.24},
        "side": {"pred": lambda p: 0.28 <= p.z <= 0.50 and 0.12 <= abs(p.x) <= 0.22 and abs(p.y) <= 0.08},
        "arm": {"pred": lambda p: abs(p.x) >= 0.24 and 0.42 <= p.z <= 0.56},
    }
    for name, spec in regions.items():
        min_s, inside, n, worst = 99.0, 0, 0, None
        for p in ev_pts:
            if not spec["pred"](p):
                continue
            n += 1
            hit, normal, *_ = bvh.find_nearest(bmwi @ p)
            if hit is None:
                continue
            wn = (brot @ normal).normalized()
            if wn.length < 0.2:
                continue
            side = (p - (bmw @ hit)).dot(wn)
            if side < min_s:
                min_s = side
                worst = [round(p.x, 3), round(p.y, 3), round(p.z, 3), round(side, 4)]
            if side < 0.002:
                inside += 1
        print(f"  clear {name} n={n} inside={inside} min={None if min_s == 99 else round(min_s, 4)} worst={worst}")

    body.hide_set(True)
    bpy.ops.object.select_all(action="DESELECT")
    shirt.hide_set(False)
    arm.hide_set(False)
    shirt.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_skins=True,
        export_all_influences=True,
        export_animations=False,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    print(f"  -> {OUT_GLB} ({os.path.getsize(OUT_GLB) / 1024:.1f} KB)")

    body.hide_set(False)
    body.hide_render = False
    if body.data.materials:
        bsdf = body.data.materials[0].node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (0.82, 0.68, 0.56, 1.0)
    preview_dir = os.path.join(ROOT, "rework_previews")
    os.makedirs(preview_dir, exist_ok=True)
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 960
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.15, 0.16, 0.18, 1.0)
    scene.world = world
    bpy.ops.object.light_add(type="SUN", location=(5, -6, 8))
    bpy.context.object.rotation_euler = (math.radians(50), math.radians(16), math.radians(30))
    bpy.context.object.data.energy = 3.4
    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    center = Vector((0.0, 0.0, 0.15))

    def look_from(offset: Vector, distance: float) -> None:
        cam.location = center + offset.normalized() * distance
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

    def render_to(name: str) -> None:
        path = os.path.join(preview_dir, name)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("  preview", path)

    look_from(Vector((1.2, -1.6, 0.55)), 3.2)
    render_to("male_shirt.png")
    look_from(Vector((0.0, -1.0, 0.08)), 3.15)
    render_to("male_shirt_front.png")

    body.hide_render = True
    body.hide_set(True)
    look_from(Vector((1.2, -1.6, 0.55)), 3.2)
    render_to("male_shirt_only.png")
    look_from(Vector((0.0, -1.0, 0.08)), 3.15)
    render_to("male_shirt_only_front.png")

    body.hide_render = False
    body.hide_set(False)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        key = normalize_bone_name(pb.name)
        pb.rotation_mode = "XYZ"
        if key == "LeftArm":
            pb.rotation_euler = (0.0, 0.0, math.radians(-55))
        elif key == "RightArm":
            pb.rotation_euler = (0.0, 0.0, math.radians(55))
        elif key == "Hips":
            pb.rotation_euler = (0.0, math.radians(10), 0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    look_from(Vector((1.2, -1.6, 0.55)), 3.2)
    render_to("male_shirt_armraise.png")
    look_from(Vector((0.0, -1.0, 0.08)), 3.15)
    render_to("male_shirt_armraise_front.png")
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.matrix_basis.identity()
    bpy.ops.object.mode_set(mode="OBJECT")


if __name__ == "__main__":
    main()
