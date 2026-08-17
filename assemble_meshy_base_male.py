"""
assemble_meshy_base_male.py
===========================
Assemble Meshy BaseMale parts into a modular GrindScape character.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python assemble_meshy_base_male.py
"""

from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

REPO = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = "/Users/stephenvillavaso/Desktop/Shells/BaseMale"
REF_GLB = os.path.join(REPO, "viewer/public/models/BaseMaleV2.glb")
OUT_DIR = os.path.join(REPO, "assembled_male")
SHOT_DIR = os.path.join(OUT_DIR, "screenshots")
BLEND_OUT = os.path.join(OUT_DIR, "GrindScape_Male_Assembled_Modular.blend")
GLB_OUT = os.path.join(OUT_DIR, "GrindScape_Male_Assembled_Modular.glb")
REPORT_OUT = os.path.join(OUT_DIR, "GrindScape_Male_Assembly_Report.txt")

PART_FILES = {
    "HEAD": "Meshy_AI_Blue_Eyed_Avatar_0730030520_texture.glb",
    "UPPER": "Meshy_AI_Headless_Muscular_Tor_0730030512_texture.glb",
    "HANDS": "Meshy_AI_Disembodied_Hands_0730030501_texture.glb",
    "LOWER": "Meshy_AI_Gray_Boxer_Briefs_on__0730030506_texture.glb",
    "FEET": "Meshy_AI_Two_feet_on_stumps_0730030456_texture.glb",
}

BODY_NAMES = [
    "Body_Head",
    "Body_Upperbody",
    "Body_Hand_L",
    "Body_Hand_R",
    "Body_Lowerbody",
    "Body_Foot_L",
    "Body_Foot_R",
]

SKIN = (0.72, 0.52, 0.40, 1.0)
UNDERWEAR = (0.22, 0.23, 0.25, 1.0)
EYE_W = (0.95, 0.95, 0.96, 1.0)
EYE_I = (0.18, 0.42, 0.78, 1.0)


# ── Scene helpers ────────────────────────────────────────────────────────────
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ensure_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link_only(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    if obj.name not in col.objects:
        col.objects.link(obj)


def active(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_tf(obj):
    active(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def clean_mesh(obj, merge=0.00015):
    active(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=merge)
    bpy.ops.mesh.delete_loose()
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in obj.data.polygons:
        p.use_smooth = True


def world_bounds(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mins = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    maxs = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mins, maxs, (mins + maxs) * 0.5


def world_verts(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def set_world_verts(obj, new_world_coords):
    imw = obj.matrix_world.inverted()
    for v, w in zip(obj.data.vertices, new_world_coords):
        v.co = imw @ w
    obj.data.update()


def transform_world(obj, fn):
    """Apply fn(world_vector) -> world_vector to every vertex."""
    set_world_verts(obj, [fn(p) for p in world_verts(obj)])


def translate_obj(obj, delta: Vector):
    transform_world(obj, lambda p: p + delta)


def scale_about(obj, center: Vector, sx, sy=None, sz=None):
    sy = sx if sy is None else sy
    sz = sx if sz is None else sz

    def fn(p):
        d = p - center
        return center + Vector((d.x * sx, d.y * sy, d.z * sz))

    transform_world(obj, fn)


def rotate_about(obj, center: Vector, quat: Quaternion):
    def fn(p):
        return center + quat @ (p - center)

    transform_world(obj, fn)


def duplicate(obj, name, col):
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = name
    dup.data.name = name
    col.objects.link(dup)
    return dup


def join_objects(objects, name):
    objects = [o for o in objects if o and o.name in bpy.data.objects]
    active(objects[0])
    for o in objects[1:]:
        o.select_set(True)
    if len(objects) > 1:
        bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    joined.data.name = name
    return joined


def separate_loose(obj):
    active(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    return [o for o in bpy.context.selected_objects if o.type == "MESH"]


def delete_objs(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        if o and o.name in bpy.data.objects:
            o.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete()


# ── Boundary loops ───────────────────────────────────────────────────────────
def pick_loop(loops, mode, obj_center=None):
    """Pick a semantic boundary loop from a mesh."""
    if not loops:
        return None
    if mode == "waist":
        # lowest Z among loops near centerline (not wrists)
        central = [L for L in loops if abs(L["center"].x) < 0.12]
        pool = central or loops
        return min(pool, key=lambda L: L["center"].z)
    if mode == "neck":
        central = [L for L in loops if abs(L["center"].x) < 0.12]
        pool = central or loops
        return max(pool, key=lambda L: L["center"].z)
    if mode == "wrist_l":
        return max(loops, key=lambda L: L["center"].x)
    if mode == "wrist_r":
        return min(loops, key=lambda L: L["center"].x)
    if mode == "ankle_l":
        rightish = [L for L in loops if L["center"].x > 0]
        return min(rightish or loops, key=lambda L: L["center"].z)
    if mode == "ankle_r":
        leftish = [L for L in loops if L["center"].x < 0]
        return min(leftish or loops, key=lambda L: L["center"].z)
    if mode == "top":
        return max(loops, key=lambda L: L["center"].z)
    if mode == "bottom":
        return min(loops, key=lambda L: L["center"].z)
    return loops[0]


def boundary_loops(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    seen = set()
    loops = []
    mw = obj.matrix_world
    for e0 in bm.edges:
        if not e0.is_boundary or e0.index in seen:
            continue
        start = e0.verts[0]
        cur = e0.verts[1]
        seen.add(e0.index)
        idxs = [start.index]
        for _ in range(100000):
            idxs.append(cur.index)
            nxt = None
            for e in cur.link_edges:
                if e.is_boundary and e.index not in seen:
                    nxt = e
                    break
            if not nxt:
                break
            seen.add(nxt.index)
            cur = nxt.other_vert(cur)
            if cur == start:
                break
        uniq = list(dict.fromkeys(idxs))
        if len(uniq) < 3:
            continue
        coords = [mw @ bm.verts[i].co for i in uniq]
        c = sum(coords, Vector()) / len(coords)
        nx = ny = nz = 0.0
        for i in range(len(coords)):
            a, b = coords[i], coords[(i + 1) % len(coords)]
            nx += (a.y - b.y) * (a.z + b.z)
            ny += (a.z - b.z) * (a.x + b.x)
            nz += (a.x - b.x) * (a.y + b.y)
        n = Vector((nx, ny, nz))
        n = n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))
        r = 0.0
        for p in coords:
            d = p - c
            d = d - n * d.dot(n)
            r += d.length
        r /= len(coords)
        loops.append({"indices": uniq, "center": c, "radius": r, "normal": n, "count": len(uniq)})
    bm.free()
    return sorted(loops, key=lambda L: -L["count"])


def delete_horizontal_caps(obj, z_world, band=0.03, facing_up=None):
    """Delete nearly-horizontal faces near a world Z plane (end caps / lids)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mw = obj.matrix_world
    rot = mw.to_3x3()
    to_del = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        if abs(c.z - z_world) > band:
            continue
        n = f.normal.copy()
        n.rotate(rot)
        if abs(n.z) < 0.7:
            continue
        if facing_up is True and n.z < 0:
            continue
        if facing_up is False and n.z > 0:
            continue
        to_del.append(f)
    if to_del:
        bmesh.ops.delete(bm, geom=to_del, context="FACES")
        print(f"  deleted {len(to_del)} cap faces near z={z_world:.3f} on {obj.name}")
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    clean_mesh(obj)


def delete_outward_disk_caps(obj, center: Vector, axis: Vector, band=0.04):
    """Delete faces near center whose normals align with axis (wrist/ankle lids)."""
    axis = axis.normalized()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    mw = obj.matrix_world
    rot = mw.to_3x3()
    to_del = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        if (c - center).length > band * 2.5:
            continue
        # must be near the plane of the opening
        if abs((c - center).dot(axis)) > band:
            continue
        n = f.normal.copy()
        n.rotate(rot)
        if abs(n.dot(axis)) < 0.65:
            continue
        to_del.append(f)
    if len(to_del) >= 3:
        bmesh.ops.delete(bm, geom=to_del, context="FACES")
        print(f"  deleted {len(to_del)} disk caps on {obj.name}")
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    clean_mesh(obj)


def fit_boundary_radius(obj, loop, target_center: Vector, target_radius: float, influence=0.05):
    """Move boundary verts onto a circle; blend neighbors radially. Keeps modular split."""
    mw = obj.matrix_world
    imw = mw.inverted()
    normal = loop["normal"]
    if normal.dot(Vector((0, 0, 1))) < 0 and abs(normal.z) > 0.5:
        normal = -normal
    idxs = set(loop["indices"])

    # orthonormal basis
    arb = Vector((1, 0, 0)) if abs(normal.z) < 0.9 else Vector((0, 1, 0))
    x_axis = normal.cross(arb).normalized()
    y_axis = normal.cross(x_axis).normalized()

    mesh = obj.data
    # place boundary verts on target circle, preserving angle
    for i in loop["indices"]:
        w = mw @ mesh.vertices[i].co
        d = w - target_center
        d = d - normal * d.dot(normal)
        if d.length < 1e-8:
            d = x_axis * target_radius
        else:
            d = d.normalized() * target_radius
        mesh.vertices[i].co = imw @ (target_center + d)

    # soft radial blend for nearby verts
    for v in mesh.vertices:
        if v.index in idxs:
            continue
        w = mw @ v.co
        # distance to plane center along plane
        d = w - target_center
        axial = d.dot(normal)
        radial = d - normal * axial
        # distance to boundary ring
        dist = math.hypot(abs(radial.length - target_radius), abs(axial))
        if dist > influence:
            continue
        t = (1.0 - dist / influence) ** 2
        if radial.length > 1e-8:
            new_r = radial.length * (1 - 0.5 * t) + target_radius * (0.5 * t)
            # also pull slightly toward plane
            new_axial = axial * (1 - 0.35 * t)
            new_w = target_center + normal * new_axial + radial.normalized() * new_r
            v.co = imw @ w.lerp(new_w, t)
    mesh.update()


def smooth_near_boundary(obj, iterations=5):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    border = {v.index for v in bm.verts if v.is_boundary}
    ring = set(border)
    for _ in range(4):
        grow = set()
        for vi in ring:
            for e in bm.verts[vi].link_edges:
                grow.add(e.other_vert(bm.verts[vi]).index)
        ring |= grow
    coords = {v.index: v.co.copy() for v in bm.verts}
    for _ in range(iterations):
        newc = {}
        for vi in ring:
            v = bm.verts[vi]
            if v.is_boundary:
                newc[vi] = coords[vi]
                continue
            nbrs = [e.other_vert(v) for e in v.link_edges]
            avg = sum((coords[n.index] for n in nbrs), Vector()) / max(len(nbrs), 1)
            newc[vi] = coords[vi].lerp(avg, 0.5)
        coords.update(newc)
    for v in bm.verts:
        v.co = coords[v.index]
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()


# ── Import / prepare ─────────────────────────────────────────────────────────
def import_sources(source_col):
    imported = {}
    for key, fname in PART_FILES.items():
        path = os.path.join(SRC_DIR, fname)
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=path)
        new_objs = [o for o in bpy.data.objects if o not in before]
        meshes = []
        for o in new_objs:
            if o.type == "MESH":
                meshes.append(o)
            else:
                bpy.data.objects.remove(o, do_unlink=True)
        if not meshes:
            raise RuntimeError(f"No mesh in {fname}")
        obj = join_objects(meshes, f"SRC_{key}") if len(meshes) > 1 else meshes[0]
        obj.name = f"SRC_{key}"
        obj.data.name = f"SRC_{key}"
        link_only(obj, source_col)
        clean_mesh(obj)
        apply_tf(obj)
        imported[key] = obj
        print(f"Imported {key}: v={len(obj.data.vertices)}")
    source_col.hide_viewport = True
    source_col.hide_render = True
    return imported


def prepare_parts(sources, work_col):
    parts = {}

    # Head + eyes
    head = duplicate(sources["HEAD"], "WRK_HEAD", work_col)
    separate_loose(head)
    pieces = [o for o in bpy.data.objects if o.name.startswith("WRK_HEAD") and o.type == "MESH"]
    pieces.sort(key=lambda o: len(o.data.vertices), reverse=True)
    keep = [pieces[0]] + [p for p in pieces[1:] if len(p.data.vertices) >= 15]
    trash = [p for p in pieces if p not in keep]
    delete_objs(trash)
    parts["Body_Head"] = join_objects(keep, "Body_Head")
    link_only(parts["Body_Head"], work_col)
    clean_mesh(parts["Body_Head"])

    parts["Body_Upperbody"] = duplicate(sources["UPPER"], "Body_Upperbody", work_col)
    clean_mesh(parts["Body_Upperbody"])

    hands = duplicate(sources["HANDS"], "WRK_HANDS", work_col)
    separate_loose(hands)
    hpieces = [o for o in bpy.data.objects if o.name.startswith("WRK_HANDS") and o.type == "MESH"]
    hpieces.sort(key=lambda o: world_bounds(o)[2].x)
    # Mixamo: Left = +X, Right = -X. File -X then +X after sort.
    hpieces[0].name = "Body_Hand_R"
    hpieces[0].data.name = "Body_Hand_R"
    hpieces[1].name = "Body_Hand_L"
    hpieces[1].data.name = "Body_Hand_L"
    parts["Body_Hand_R"] = hpieces[0]
    parts["Body_Hand_L"] = hpieces[1]
    for n in ("Body_Hand_L", "Body_Hand_R"):
        link_only(parts[n], work_col)
        clean_mesh(parts[n])

    lower = duplicate(sources["LOWER"], "WRK_LOWER", work_col)
    separate_loose(lower)
    lpieces = [o for o in bpy.data.objects if o.name.startswith("WRK_LOWER") and o.type == "MESH"]
    parts["Body_Lowerbody"] = join_objects(lpieces, "Body_Lowerbody")
    link_only(parts["Body_Lowerbody"], work_col)
    # Weld hip/leg junctions from Meshy's separate islands
    clean_mesh(parts["Body_Lowerbody"], merge=0.0015)

    feet = duplicate(sources["FEET"], "WRK_FEET", work_col)
    separate_loose(feet)
    fpieces = [o for o in bpy.data.objects if o.name.startswith("WRK_FEET") and o.type == "MESH"]
    fpieces.sort(key=lambda o: world_bounds(o)[2].x)
    fpieces[0].name = "Body_Foot_R"
    fpieces[0].data.name = "Body_Foot_R"
    fpieces[1].name = "Body_Foot_L"
    fpieces[1].data.name = "Body_Foot_L"
    parts["Body_Foot_R"] = fpieces[0]
    parts["Body_Foot_L"] = fpieces[1]
    for n in ("Body_Foot_L", "Body_Foot_R"):
        link_only(parts[n], work_col)
        clean_mesh(parts[n])

    return parts


def load_armature(arm_col):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=REF_GLB)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    for o in new:
        if o.type != "ARMATURE":
            bpy.data.objects.remove(o, do_unlink=True)
    arm.name = "Armature"
    if arm.animation_data:
        arm.animation_data_clear()
    link_only(arm, arm_col)
    return arm


def bone(arm, name):
    b = arm.data.bones[name]
    return arm.matrix_world @ b.head_local


# ── Alignment ────────────────────────────────────────────────────────────────
def align_parts(parts, arm):
    hips = bone(arm, "mixamorig:Hips")
    neck = bone(arm, "mixamorig:Neck")
    head_b = bone(arm, "mixamorig:Head")
    l_hand = bone(arm, "mixamorig:LeftHand")
    r_hand = bone(arm, "mixamorig:RightHand")
    l_fore = bone(arm, "mixamorig:LeftForeArm")
    r_fore = bone(arm, "mixamorig:RightForeArm")
    l_foot = bone(arm, "mixamorig:LeftFoot")
    r_foot = bone(arm, "mixamorig:RightFoot")
    l_arm = bone(arm, "mixamorig:LeftArm")
    r_arm = bone(arm, "mixamorig:RightArm")

    # Targets
    waist_z = hips.z + 0.04          # ~1.07
    neck_z = neck.z - 0.01           # ~1.47
    ankle_z = (l_foot.z + r_foot.z) * 0.5 + 0.015  # ~0.11
    head_top_z = head_b.z + 0.24     # ~1.78

    # ── UPPER ──
    # Uniform scale only (arms hang near waist Z — non-uniform Z crush destroys them).
    # Only open neck/waist lids; never strip wrist/arm geometry.
    upper = parts["Body_Upperbody"]
    mins, maxs, cen = world_bounds(upper)
    delete_horizontal_caps(upper, maxs.z, band=0.028, facing_up=True)
    delete_horizontal_caps(upper, maxs.z, band=0.028, facing_up=False)
    delete_horizontal_caps(upper, mins.z, band=0.028, facing_up=True)
    delete_horizontal_caps(upper, mins.z, band=0.028, facing_up=False)

    mins, maxs, cen = world_bounds(upper)
    # Neck opening is near top; waist opening near bottom — but arms may extend
    # slightly below waist. Scale so shoulder width fits Mixamo.
    src_w = maxs.x - mins.x
    tgt_w = abs(l_arm.x - r_arm.x) * 2.55
    s = tgt_w / max(src_w, 1e-6)
    print(f"UPPER scale {s:.3f}")
    scale_about(upper, cen, s)

    # Place: X centered, waist opening → waist_z.
    loops = boundary_loops(upper)
    waist_loop = pick_loop(loops, "waist")
    mins, maxs, cen = world_bounds(upper)
    if waist_loop:
        target_waist = Vector((0.0, hips.y + 0.01, waist_z))
        translate_obj(upper, target_waist - waist_loop["center"])
    else:
        translate_obj(upper, Vector((-cen.x, hips.y - cen.y + 0.01, waist_z - mins.z)))
    mins, maxs, cen = world_bounds(upper)
    translate_obj(upper, Vector((-cen.x, 0, 0)))
    print("UPPER", world_bounds(upper)[0], world_bounds(upper)[1])
    print("  upper loops:", [(round(L["center"].x, 3), round(L["center"].z, 3), round(L["radius"], 3)) for L in boundary_loops(upper)[:6]])

    # ── LOWER ──
    # Uniform scale from waist radius + place so waist meets upper; ankles near feet.
    lower = parts["Body_Lowerbody"]
    mins, maxs, cen = world_bounds(lower)
    delete_horizontal_caps(lower, maxs.z, band=0.028)
    delete_horizontal_caps(lower, mins.z, band=0.028)

    u_mins, u_maxs, u_cen = world_bounds(upper)
    u_loops = boundary_loops(upper)
    u_waist = pick_loop(u_loops, "waist")
    if u_waist:
        u_waist_r = u_waist["radius"]
        u_waist_c = u_waist["center"]
    else:
        # fallback: verts near torso bottom but near X=0
        u_waist_pts = [p for p in world_verts(upper) if p.z < u_mins.z + 0.06 and abs(p.x) < 0.15]
        if not u_waist_pts:
            u_waist_pts = [p for p in world_verts(upper) if p.z < u_mins.z + 0.04]
        u_waist_c = sum(u_waist_pts, Vector()) / len(u_waist_pts)
        u_waist_r = sum(math.hypot(p.x - u_waist_c.x, p.y - u_waist_c.y) for p in u_waist_pts) / len(u_waist_pts)

    mins, maxs, cen = world_bounds(lower)
    l_loops = boundary_loops(lower)
    l_waist = pick_loop(l_loops, "top")
    # Prefer top central loop
    top_central = [L for L in l_loops if abs(L["center"].x) < 0.12]
    if top_central:
        l_waist = max(top_central, key=lambda L: L["center"].z)
    if l_waist:
        l_waist_r = l_waist["radius"]
        l_waist_c = l_waist["center"]
    else:
        l_waist_pts = [p for p in world_verts(lower) if p.z > maxs.z - 0.04]
        l_waist_c = sum(l_waist_pts, Vector()) / len(l_waist_pts)
        l_waist_r = sum(math.hypot(p.x - l_waist_c.x, p.y - l_waist_c.y) for p in l_waist_pts) / len(l_waist_pts)

    s = u_waist_r / max(l_waist_r, 1e-6)
    s = max(0.85, min(1.25, s))
    print(f"LOWER scale {s:.3f} (u_waist r={u_waist_r:.3f} @ x={u_waist_c.x:.3f} z={u_waist_c.z:.3f})")
    scale_about(lower, cen, s)

    # Snap waist centers together (slight overlap so underwear hides the cut)
    l_loops = boundary_loops(lower)
    top_central = [L for L in l_loops if abs(L["center"].x) < 0.15]
    l_waist = max(top_central, key=lambda L: L["center"].z) if top_central else pick_loop(l_loops, "top")
    u_loops = boundary_loops(upper)
    u_waist = pick_loop(u_loops, "waist")
    if l_waist and u_waist:
        print(f"  snap lower waist {tuple(round(c,3) for c in l_waist['center'])} -> {tuple(round(c,3) for c in u_waist['center'])}")
        translate_obj(lower, u_waist["center"] - l_waist["center"] + Vector((0, 0, 0.004)))
    else:
        mins, maxs, cen = world_bounds(lower)
        u_mins, u_maxs, u_cen = world_bounds(upper)
        translate_obj(lower, Vector((-cen.x, u_cen.y - cen.y, u_waist_c.z - maxs.z + 0.004)))

    # Force center X of lower to 0
    mins, maxs, cen = world_bounds(lower)
    translate_obj(lower, Vector((-cen.x, 0, 0)))

    # If ankles are far from target ankle_z, uniform re-scale about waist
    mins, maxs, cen = world_bounds(lower)
    cur_ankle = mins.z
    if abs(cur_ankle - ankle_z) > 0.08:
        l_loops = boundary_loops(lower)
        top_central = [L for L in l_loops if abs(L["center"].x) < 0.15]
        l_waist = max(top_central, key=lambda L: L["center"].z) if top_central else pick_loop(l_loops, "top")
        pivot = l_waist["center"].copy() if l_waist else Vector((0, 0, maxs.z))
        s2 = (pivot.z - ankle_z) / max(pivot.z - cur_ankle, 1e-6)
        s2 = max(0.85, min(1.2, s2))
        print(f"LOWER ankle fit scale {s2:.3f}")
        scale_about(lower, pivot, s2)
        # re-snap waist + recenter
        l_loops = boundary_loops(lower)
        top_central = [L for L in l_loops if abs(L["center"].x) < 0.15]
        l_waist = max(top_central, key=lambda L: L["center"].z) if top_central else pick_loop(l_loops, "top")
        u_loops = boundary_loops(upper)
        u_waist = pick_loop(u_loops, "waist")
        if l_waist and u_waist:
            translate_obj(lower, u_waist["center"] - l_waist["center"] + Vector((0, 0, 0.004)))
        mins, maxs, cen = world_bounds(lower)
        translate_obj(lower, Vector((-cen.x, 0, 0)))
    print("LOWER", world_bounds(lower)[0], world_bounds(lower)[1])

    # ── HEAD ──
    head = parts["Body_Head"]
    mins, maxs, cen = world_bounds(head)
    # scale so head height fits neck→top
    src_h = maxs.z - mins.z
    tgt_h = head_top_z - neck_z
    s = tgt_h / max(src_h, 1e-6)
    # also keep head width reasonable (~0.22)
    s_w = 0.22 / max(maxs.x - mins.x, 1e-6)
    s = (s * 0.65 + s_w * 0.35)
    s = max(0.25, min(0.45, s))
    print(f"HEAD scale {s:.3f}")
    scale_about(head, cen, s)
    mins, maxs, cen = world_bounds(head)
    # neck is bottom of head
    u_mins, u_maxs, u_cen = world_bounds(upper)
    # upper neck opening center
    u_neck_pts = [p for p in world_verts(upper) if p.z > u_maxs.z - 0.04]
    if u_neck_pts:
        unc = sum(u_neck_pts, Vector()) / len(u_neck_pts)
    else:
        unc = Vector((0, u_cen.y, u_maxs.z))
    translate_obj(head, Vector((unc.x - cen.x, unc.y - cen.y, unc.z - mins.z + 0.002)))
    print("HEAD", world_bounds(head)[0], world_bounds(head)[1])

    # ── HANDS ──
    # Upper-arm wrists are the extreme-X tips (arms hang near waist height).
    def upper_wrist_target(side):
        u_mins, u_maxs, _ = world_bounds(upper)
        pts = world_verts(upper)
        if side == "L":
            tip = [p for p in pts if p.x > u_maxs.x - 0.05]
        else:
            tip = [p for p in pts if p.x < u_mins.x + 0.05]
        if not tip:
            return l_hand if side == "L" else r_hand
        # Prefer the lowest tip verts (wrist hangs down)
        tip.sort(key=lambda p: p.z)
        tip = tip[: max(12, len(tip) // 3)]
        return sum(tip, Vector()) / len(tip)

    for side, hand, hbone, fbone in (
        ("L", parts["Body_Hand_L"], l_hand, l_fore),
        ("R", parts["Body_Hand_R"], r_hand, r_fore),
    ):
        mins, maxs, cen = world_bounds(hand)
        delete_horizontal_caps(hand, maxs.z, band=0.045, facing_up=True)
        delete_horizontal_caps(hand, maxs.z, band=0.045, facing_up=False)

        mins, maxs, cen = world_bounds(hand)
        longest = max(maxs.x - mins.x, maxs.y - mins.y, maxs.z - mins.z)
        s = 0.17 / max(longest, 1e-6)
        s = max(0.28, min(0.5, s))
        print(f"HAND_{side} scale {s:.3f}")
        scale_about(hand, cen, s)

        target = upper_wrist_target(side)
        # Wrist opening should face toward shoulder (inward / up-arm)
        shoulder = l_arm if side == "L" else r_arm
        desired = (shoulder - target).normalized()

        loops = boundary_loops(hand)
        if loops:
            wloop = max(loops, key=lambda L: L["count"])
            current = wloop["normal"]
            if current.dot(desired) < 0:
                current = -current
            quat = current.rotation_difference(desired)
            rotate_about(hand, wloop["center"], quat)

        loops = boundary_loops(hand)
        wloop = max(loops, key=lambda L: L["count"]) if loops else None
        if wloop:
            translate_obj(hand, target - wloop["center"])
        else:
            translate_obj(hand, target - world_bounds(hand)[2])
        print(f"HAND_{side}", world_bounds(hand)[0], world_bounds(hand)[1])

    # ── FEET ──
    for side, foot, fbone in (
        ("L", parts["Body_Foot_L"], l_foot),
        ("R", parts["Body_Foot_R"], r_foot),
    ):
        mins, maxs, cen = world_bounds(foot)
        delete_horizontal_caps(foot, maxs.z, band=0.06)
        # Scale: foot length ~0.26, height ~0.11
        mins, maxs, cen = world_bounds(foot)
        foot_len = max(maxs.y - mins.y, maxs.x - mins.x)
        s = 0.26 / max(foot_len, 1e-6)
        s = max(0.2, min(0.45, s))
        print(f"FOOT_{side} scale {s:.3f}")
        scale_about(foot, cen, s)

        # Orient ankle normal up
        loops = boundary_loops(foot)
        if loops:
            aloop = max(loops, key=lambda L: L["center"].z)
            current = aloop["normal"]
            desired = Vector((0, 0, 1))
            if current.dot(desired) < 0:
                current = -current
            quat = current.rotation_difference(desired)
            rotate_about(foot, aloop["center"], quat)

        # Place sole on ground, ankle under leg ankle
        mins, maxs, cen = world_bounds(foot)
        translate_obj(foot, Vector((0, 0, -mins.z)))

        l_pts = world_verts(lower)
        if side == "L":
            ank = [p for p in l_pts if p.x > 0 and p.z < world_bounds(lower)[0].z + 0.06]
        else:
            ank = [p for p in l_pts if p.x < 0 and p.z < world_bounds(lower)[0].z + 0.06]
        if ank:
            ac = sum(ank, Vector()) / len(ank)
        else:
            ac = fbone.copy()
        loops = boundary_loops(foot)
        if loops:
            aloop = max(loops, key=lambda L: L["center"].z)
            translate_obj(foot, Vector((ac.x - aloop["center"].x, ac.y - aloop["center"].y, 0)))
        # Keep sole on ground
        mins, maxs, _ = world_bounds(foot)
        translate_obj(foot, Vector((0, 0, -mins.z)))
        print(f"FOOT_{side}", world_bounds(foot)[0], world_bounds(foot)[1])

    # Nudge lower ankles down to meet feet if gap/overlap in Z
    for side, foot in (("L", parts["Body_Foot_L"]), ("R", parts["Body_Foot_R"])):
        f_loops = boundary_loops(foot)
        if not f_loops:
            continue
        f_a = max(f_loops, key=lambda L: L["center"].z)
        # pull lower ankle verts toward foot ankle z (soft)
        lower = parts["Body_Lowerbody"]
        mw = lower.matrix_world
        imw = mw.inverted()
        for v in lower.data.vertices:
            w = mw @ v.co
            if side == "L" and w.x <= 0:
                continue
            if side == "R" and w.x >= 0:
                continue
            if w.z > f_a["center"].z + 0.08:
                continue
            if w.z < f_a["center"].z - 0.05:
                continue
            # blend z toward foot ankle
            t = 1.0 - abs(w.z - f_a["center"].z) / 0.08
            w.z = w.z * (1 - 0.6 * t) + f_a["center"].z * (0.6 * t)
            # mild xy toward foot ankle
            w.x = w.x * (1 - 0.3 * t) + f_a["center"].x * (0.3 * t)
            w.y = w.y * (1 - 0.3 * t) + f_a["center"].y * (0.3 * t)
            v.co = imw @ w
        lower.data.update()


def shrinkwrap_seam(src, tgt, center: Vector, radius: float, band_z=0.07):
    """Project src verts near a connection band onto tgt surface (nearest)."""
    # Build KD tree of target world verts
    tw = world_verts(tgt)
    if not tw:
        return
    kd = None
    try:
        from mathutils.kdtree import KDTree
        kd = KDTree(len(tw))
        for i, p in enumerate(tw):
            kd.insert(p, i)
        kd.balance()
    except Exception:
        return
    mw = src.matrix_world
    imw = mw.inverted()
    for v in src.data.vertices:
        w = mw @ v.co
        if abs(w.z - center.z) > band_z:
            continue
        if math.hypot(w.x - center.x, w.y - center.y) > radius * 2.2:
            continue
        co, idx, dist = kd.find(w)
        if dist > 0.08:
            continue
        # stronger pull near the seam plane
        t = 1.0 - min(abs(w.z - center.z) / band_z, 1.0)
        t = t * t
        v.co = imw @ w.lerp(Vector(co), 0.55 * t + 0.25)
    src.data.update()


def close_modular_gaps(parts):
    """Final hard snaps so modular openings occupy the same world positions."""
    upper = parts["Body_Upperbody"]
    head = parts["Body_Head"]
    lower = parts["Body_Lowerbody"]

    # Trim upper neck collar lips (duplicate rim loops)
    u_loops = boundary_loops(upper)
    neck_loops = sorted([L for L in u_loops if abs(L["center"].x) < 0.12], key=lambda L: -L["center"].z)
    if len(neck_loops) >= 2 and abs(neck_loops[0]["center"].z - neck_loops[1]["center"].z) < 0.03:
        # delete faces near the higher tiny lip
        delete_horizontal_caps(upper, neck_loops[0]["center"].z, band=0.02)

    # Neck: put head neck loop on upper neck loop
    h_loops = boundary_loops(head)
    u_loops = boundary_loops(upper)
    if h_loops and u_loops:
        h_neck = pick_loop(h_loops, "bottom")
        u_neck = pick_loop(u_loops, "neck")
        # Meet in the middle vertically; head overlaps into collar
        mid_z = (h_neck["center"].z + u_neck["center"].z) * 0.5
        translate_obj(head, Vector((u_neck["center"].x - h_neck["center"].x,
                                    u_neck["center"].y - h_neck["center"].y,
                                    mid_z - h_neck["center"].z - 0.01)))
        # Widen head neck AND shrink upper collar toward shared radius
        h_loops = boundary_loops(head)
        h_neck = pick_loop(h_loops, "bottom")
        u_loops = boundary_loops(upper)
        u_neck = pick_loop(u_loops, "neck")
        mid_r = (h_neck["radius"] * 0.35 + u_neck["radius"] * 0.65)
        mid_c = Vector((0.0, (h_neck["center"].y + u_neck["center"].y) * 0.5, (h_neck["center"].z + u_neck["center"].z) * 0.5))
        fit_boundary_radius(head, h_neck, mid_c, mid_r, influence=0.08)
        fit_boundary_radius(upper, u_neck, mid_c, mid_r, influence=0.07)
        shrinkwrap_seam(head, upper, mid_c, mid_r, band_z=0.08)
        shrinkwrap_seam(upper, head, mid_c, mid_r, band_z=0.06)

    # Waist: pull lower UP so underwear overlaps torso cut
    u_loops = boundary_loops(upper)
    l_loops = boundary_loops(lower)
    if u_loops and l_loops:
        u_w = pick_loop(u_loops, "waist")
        top_central = [L for L in l_loops if abs(L["center"].x) < 0.15]
        l_w = max(top_central, key=lambda L: L["center"].z) if top_central else pick_loop(l_loops, "top")
        translate_obj(lower, u_w["center"] - l_w["center"] + Vector((0, 0, 0.028)))
        mins, maxs, cen = world_bounds(lower)
        translate_obj(lower, Vector((-cen.x, 0, 0)))
        # Match waist radii
        l_loops = boundary_loops(lower)
        top_central = [L for L in l_loops if abs(L["center"].x) < 0.15]
        l_w = max(top_central, key=lambda L: L["center"].z) if top_central else pick_loop(l_loops, "top")
        u_loops = boundary_loops(upper)
        u_w = pick_loop(u_loops, "waist")
        mid_r = (u_w["radius"] + l_w["radius"]) * 0.5
        mid_c = Vector((0.0, (u_w["center"].y + l_w["center"].y) * 0.5, (u_w["center"].z + l_w["center"].z) * 0.5))
        fit_boundary_radius(upper, u_w, mid_c, mid_r, influence=0.05)
        fit_boundary_radius(lower, l_w, mid_c, mid_r, influence=0.05)
        shrinkwrap_seam(upper, lower, mid_c, mid_r, band_z=0.06)
        shrinkwrap_seam(lower, upper, mid_c, mid_r, band_z=0.06)

    # Wrists — flare thin Meshy arm tips to hand wrist radius, then seat hands
    for side, hand in (("L", parts["Body_Hand_L"]), ("R", parts["Body_Hand_R"])):
        h_loops = boundary_loops(hand)
        if not h_loops:
            continue
        h_w = max(h_loops, key=lambda L: L["count"])
        u_loops = boundary_loops(upper)
        u_w = pick_loop(u_loops, "wrist_l" if side == "L" else "wrist_r")
        u_mins, u_maxs, _ = world_bounds(upper)
        pts = world_verts(upper)
        tip = [p for p in pts if p.x > u_maxs.x - 0.05] if side == "L" else [p for p in pts if p.x < u_mins.x + 0.05]
        if tip:
            tip.sort(key=lambda p: p.z)
            tip = tip[: max(16, len(tip) // 3)]
            tc = sum(tip, Vector()) / len(tip)
        elif u_w:
            tc = u_w["center"]
        else:
            continue
        mid_r = max(h_w["radius"], (u_w["radius"] if u_w else 0.02)) * 0.95
        mid_r = max(mid_r, 0.028)
        if u_w:
            fit_boundary_radius(upper, u_w, tc, mid_r, influence=0.055)
        translate_obj(hand, tc - h_w["center"])
        h_loops = boundary_loops(hand)
        h_w = max(h_loops, key=lambda L: L["count"])
        fit_boundary_radius(hand, h_w, tc, mid_r, influence=0.04)

    # Ankles: move foot ankle loop to lower ankle loop; keep sole on ground via Z scale about ankle
    for side, foot in (("L", parts["Body_Foot_L"]), ("R", parts["Body_Foot_R"])):
        f_loops = boundary_loops(foot)
        l_loops = boundary_loops(lower)
        if not f_loops or not l_loops:
            continue
        f_a = max(f_loops, key=lambda L: L["center"].z)
        cand = [L for L in l_loops if (L["center"].x > 0.02 if side == "L" else L["center"].x < -0.02)] or l_loops
        # prefer lowest among side candidates
        l_a = min(cand, key=lambda L: L["center"].z)
        # match XY at ankle, then scale foot in Z so sole hits ground while ankle stays
        translate_obj(foot, Vector((l_a["center"].x - f_a["center"].x, l_a["center"].y - f_a["center"].y, l_a["center"].z - f_a["center"].z)))
        f_loops = boundary_loops(foot)
        f_a = max(f_loops, key=lambda L: L["center"].z)
        mins, maxs, _ = world_bounds(foot)
        if mins.z < -0.001 or mins.z > 0.01:
            # scale about ankle so sole → 0
            if abs(f_a["center"].z - mins.z) > 1e-6:
                s = f_a["center"].z / max(f_a["center"].z - mins.z, 1e-6)
                # actually: new_sole = ankle + (sole-ankle)*s = 0
                # s = -ankle/(sole-ankle) = ankle/(ankle-sole)
                s = f_a["center"].z / max(f_a["center"].z - mins.z, 1e-6)
                scale_about(foot, f_a["center"], 1.0, 1.0, s)
                mins, _, _ = world_bounds(foot)
                translate_obj(foot, Vector((0, 0, -mins.z)))


def blend_seams(parts):
    """Conservative seam matching — match radii at shared planes, no heavy warping."""
    close_modular_gaps(parts)

    upper = parts["Body_Upperbody"]
    head = parts["Body_Head"]
    lower = parts["Body_Lowerbody"]

    # Neck
    h_loops = boundary_loops(head)
    u_loops = boundary_loops(upper)
    if h_loops and u_loops:
        h_neck = pick_loop(h_loops, "bottom")
        u_neck = pick_loop(u_loops, "neck")
        mid_c = h_neck["center"].lerp(u_neck["center"], 0.5)
        mid_r = (h_neck["radius"] + u_neck["radius"]) * 0.5
        translate_obj(head, mid_c - h_neck["center"])
        h_loops = boundary_loops(head)
        h_neck = pick_loop(h_loops, "bottom")
        fit_boundary_radius(head, h_neck, mid_c, mid_r, influence=0.03)
        fit_boundary_radius(upper, u_neck, mid_c, mid_r, influence=0.03)

    # Waist — translate to meet, mild radius match (underwear hides cut)
    u_loops = boundary_loops(upper)
    l_loops = boundary_loops(lower)
    if u_loops and l_loops:
        u_w = pick_loop(u_loops, "waist")
        top_central = [L for L in l_loops if abs(L["center"].x) < 0.15]
        l_w = max(top_central, key=lambda L: L["center"].z) if top_central else pick_loop(l_loops, "top")
        mid_c = u_w["center"].lerp(l_w["center"], 0.5)
        mid_r = (u_w["radius"] + l_w["radius"]) * 0.5
        translate_obj(lower, mid_c - l_w["center"] + Vector((0, 0, 0.002)))
        mins, maxs, cen = world_bounds(lower)
        translate_obj(lower, Vector((-cen.x, 0, 0)))
        l_loops = boundary_loops(lower)
        top_central = [L for L in l_loops if abs(L["center"].x) < 0.15]
        l_w = max(top_central, key=lambda L: L["center"].z) if top_central else pick_loop(l_loops, "top")
        u_loops = boundary_loops(upper)
        u_w = pick_loop(u_loops, "waist")
        mid_c = Vector((0.0, (u_w["center"].y + l_w["center"].y) * 0.5, (u_w["center"].z + l_w["center"].z) * 0.5))
        fit_boundary_radius(upper, u_w, mid_c, mid_r, influence=0.03)
        fit_boundary_radius(lower, l_w, mid_c, mid_r, influence=0.03)

    # Wrists — fit hand opening only (do not reshape shredded upper tips)
    for side, hand in (("L", parts["Body_Hand_L"]), ("R", parts["Body_Hand_R"])):
        h_loops = boundary_loops(hand)
        if not h_loops:
            continue
        h_w = max(h_loops, key=lambda L: L["count"])
        u_mins, u_maxs, _ = world_bounds(upper)
        pts = world_verts(upper)
        tip = [p for p in pts if (p.x > u_maxs.x - 0.05) ] if side == "L" else [p for p in pts if p.x < u_mins.x + 0.05]
        if tip:
            tip.sort(key=lambda p: p.z)
            tip = tip[: max(12, len(tip) // 3)]
            tc = sum(tip, Vector()) / len(tip)
            tr = sum(math.hypot(p.x - tc.x, p.y - tc.y) for p in tip) / len(tip)
            mid_r = (h_w["radius"] + max(tr, 0.02)) * 0.5
            translate_obj(hand, tc - h_w["center"])
            h_loops = boundary_loops(hand)
            h_w = max(h_loops, key=lambda L: L["count"])
            fit_boundary_radius(hand, h_w, tc, mid_r, influence=0.025)

    # Ankles
    for side, foot in (("L", parts["Body_Foot_L"]), ("R", parts["Body_Foot_R"])):
        f_loops = boundary_loops(foot)
        l_loops = boundary_loops(lower)
        if not f_loops or not l_loops:
            continue
        f_a = max(f_loops, key=lambda L: L["center"].z)
        cand = [L for L in l_loops if (L["center"].x > 0 if side == "L" else L["center"].x < 0)] or l_loops
        l_a = min(cand, key=lambda L: L["center"].z)
        mid_c = f_a["center"].lerp(l_a["center"], 0.5)
        mid_r = (f_a["radius"] + l_a["radius"]) * 0.5
        translate_obj(foot, Vector((mid_c.x - f_a["center"].x, mid_c.y - f_a["center"].y, 0)))
        # keep sole on ground
        mins, _, _ = world_bounds(foot)
        translate_obj(foot, Vector((0, 0, -mins.z)))
        f_loops = boundary_loops(foot)
        f_a = max(f_loops, key=lambda L: L["center"].z)
        fit_boundary_radius(foot, f_a, Vector((mid_c.x, mid_c.y, f_a["center"].z)), mid_r, influence=0.03)
        fit_boundary_radius(lower, l_a, Vector((mid_c.x, mid_c.y, l_a["center"].z)), mid_r, influence=0.03)

    close_modular_gaps(parts)

    for name in BODY_NAMES:
        smooth_near_boundary(parts[name], iterations=3)
        clean_mesh(parts[name], merge=0.00012)

    # Normalize overall height to ~1.82m standing male (feet on ground)
    mins, maxs, cen = None, None, None
    all_pts = []
    for n in BODY_NAMES:
        all_pts.extend(world_verts(parts[n]))
    gmin = Vector((min(p.x for p in all_pts), min(p.y for p in all_pts), min(p.z for p in all_pts)))
    gmax = Vector((max(p.x for p in all_pts), max(p.y for p in all_pts), max(p.z for p in all_pts)))
    height = gmax.z - gmin.z
    if height > 1e-6:
        s = 1.82 / height
        print(f"Global height normalize {height:.3f} -> 1.82 (s={s:.3f})")
        pivot = Vector((0, 0, 0))
        for n in BODY_NAMES:
            scale_about(parts[n], pivot, s)
        # re-seat soles
        for n in ("Body_Foot_L", "Body_Foot_R"):
            mins, _, _ = world_bounds(parts[n])
            translate_obj(parts[n], Vector((0, 0, -mins.z)))
        close_modular_gaps(parts)


# ── Materials / rig / render / export ────────────────────────────────────────
def make_mat(name, color, rough=0.52, spec=0.35):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = spec
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def assign_materials(parts):
    skin = make_mat("GS_Skin", SKIN)
    und = make_mat("GS_Underwear", UNDERWEAR, rough=0.7, spec=0.2)
    ew = make_mat("GS_EyeWhite", EYE_W, rough=0.25)
    ei = make_mat("GS_EyeIris", EYE_I, rough=0.2)
    for name in BODY_NAMES:
        obj = parts[name]
        obj.data.materials.clear()
        obj.data.materials.append(skin)
        if name == "Body_Lowerbody":
            obj.data.materials.append(und)
            mins, maxs, _ = world_bounds(obj)
            cut = maxs.z - (maxs.z - mins.z) * 0.18
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            for f in bm.faces:
                cz = sum((obj.matrix_world @ v.co).z for v in f.verts) / len(f.verts)
                f.material_index = 1 if cz >= cut else 0
            bm.to_mesh(obj.data)
            bm.free()
        if name == "Body_Head":
            # Keep unified skin on head. Eye islands (if still separate face slots)
            # stay skin-colored for game consistency; no crude face masks.
            _ = (ew, ei)  # materials available if needed later
    for mat in list(bpy.data.materials):
        if not mat.name.startswith("GS_") and mat.users == 0:
            bpy.data.materials.remove(mat)


def bind_parts(parts, arm):
    for name in BODY_NAMES:
        obj = parts[name]
        obj.parent = None
        for m in list(obj.modifiers):
            obj.modifiers.remove(m)
        obj.vertex_groups.clear()
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.vertex_group_limit_total(limit=4)
        bpy.ops.object.vertex_group_normalize_all(lock_active=False)
        # fix unweighted
        bad = [v.index for v in obj.data.vertices if sum(g.weight for g in v.groups) < 1e-4]
        if bad:
            hips = obj.vertex_groups.get("mixamorig:Hips") or obj.vertex_groups.new(name="mixamorig:Hips")
            hips.add(bad, 1.0, "REPLACE")
        print(f"Bound {name}")


POSES = {
    "neutral": {},
    "arms_raised": {"mixamorig:LeftArm": (0, 0, -70), "mixamorig:RightArm": (0, 0, 70)},
    "walk": {
        "mixamorig:LeftUpLeg": (-25, 0, 0),
        "mixamorig:RightUpLeg": (20, 0, 0),
        "mixamorig:LeftLeg": (15, 0, 0),
        "mixamorig:RightLeg": (10, 0, 0),
        "mixamorig:LeftArm": (0, 0, -15),
        "mixamorig:RightArm": (0, 0, 15),
    },
    "crouch": {
        "mixamorig:LeftUpLeg": (-70, 0, 10),
        "mixamorig:RightUpLeg": (-70, 0, -10),
        "mixamorig:LeftLeg": (80, 0, 0),
        "mixamorig:RightLeg": (80, 0, 0),
        "mixamorig:Spine": (20, 0, 0),
    },
    "weapon_hold": {
        "mixamorig:LeftArm": (0, 0, -35),
        "mixamorig:RightArm": (0, 0, 40),
        "mixamorig:LeftForeArm": (0, -50, 0),
        "mixamorig:RightForeArm": (0, 55, 0),
    },
    "torso_twist": {"mixamorig:Spine": (0, 0, 25), "mixamorig:Spine1": (0, 0, 20)},
}


def apply_pose(arm, pose_dict):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)
    for bname, euler_deg in pose_dict.items():
        pb = arm.pose.bones.get(bname)
        if pb:
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = tuple(math.radians(a) for a in euler_deg)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1280
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    try:
        scene.eevee.taa_render_samples = 48
    except Exception:
        pass
    bpy.ops.object.light_add(type="AREA", location=(1.6, -2.0, 2.4))
    bpy.context.active_object.data.energy = 90
    bpy.context.active_object.data.size = 2.5
    bpy.ops.object.light_add(type="AREA", location=(-2.0, -0.8, 1.8))
    bpy.context.active_object.data.energy = 35
    bpy.ops.object.light_add(type="AREA", location=(0.3, 2.0, 2.2))
    bpy.context.active_object.data.energy = 50
    cam_data = bpy.data.cameras.new("QA_Camera")
    cam = bpy.data.objects.new("QA_Camera", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def char_bounds(parts):
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    deps = bpy.context.evaluated_depsgraph_get()
    for obj in parts.values():
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        try:
            for v in mesh.vertices:
                w = ev.matrix_world @ v.co
                mins = Vector(tuple(min(a, b) for a, b in zip(mins, w)))
                maxs = Vector(tuple(max(a, b) for a, b in zip(maxs, w)))
        finally:
            ev.to_mesh_clear()
    return mins, maxs, (mins + maxs) * 0.5


def render_view(cam, parts, path, offset, lens=50, center=None):
    mins, maxs, c = char_bounds(parts)
    if center is not None:
        c = center
    else:
        # Frame full body: bias center slightly up from AABB center
        c = Vector((c.x, c.y, (mins.z + maxs.z) * 0.52))
    height = max(maxs.z - mins.z, 0.5)
    dist = max(height * 1.55, (maxs - mins).length * 0.75, 1.6)
    cam.location = c + offset.normalized() * dist
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("Rendered", path)


def render_qa(parts, arm, cam):
    os.makedirs(SHOT_DIR, exist_ok=True)
    apply_pose(arm, {})
    for name, off in {
        "front": Vector((0, -1, 0.12)),
        "back": Vector((0, 1, 0.12)),
        "side": Vector((1, 0, 0.08)),
        "three_quarter": Vector((0.75, -1, 0.18)),
    }.items():
        render_view(cam, parts, os.path.join(SHOT_DIR, f"assembled_{name}.png"), off)

    # closeups
    def loop_center(obj, pick):
        loops = boundary_loops(obj)
        return pick(loops)["center"] if loops else world_bounds(obj)[2]

    close = {
        "neck": (loop_center(parts["Body_Head"], lambda L: min(L, key=lambda x: x["center"].z)), Vector((0.45, -1, 0.1)), 85),
        "waist": (loop_center(parts["Body_Upperbody"], lambda L: min(L, key=lambda x: x["center"].z)), Vector((0.5, -1, 0)), 70),
        "wrist": (loop_center(parts["Body_Hand_L"], lambda L: max(L, key=lambda x: x["count"])), Vector((0.6, -0.9, 0.2)), 90),
        "ankle": (loop_center(parts["Body_Foot_L"], lambda L: max(L, key=lambda x: x["center"].z)), Vector((0.55, -1, 0.25)), 90),
    }
    for name, (c, off, lens) in close.items():
        render_view(cam, parts, os.path.join(SHOT_DIR, f"closeup_{name}.png"), off, lens=lens, center=c)

    for hide in BODY_NAMES:
        for n, o in parts.items():
            o.hide_render = n == hide
            o.hide_viewport = n == hide
        render_view(cam, {k: v for k, v in parts.items() if k != hide},
                    os.path.join(SHOT_DIR, f"hide_{hide}.png"), Vector((0.7, -1, 0.12)))
    for o in parts.values():
        o.hide_render = False
        o.hide_viewport = False

    for pose_name, pdata in POSES.items():
        if pose_name == "neutral":
            continue
        apply_pose(arm, pdata)
        render_view(cam, parts, os.path.join(SHOT_DIR, f"pose_{pose_name}.png"), Vector((0.7, -1, 0.12)))
    apply_pose(arm, {})


def export_glb(parts, arm):
    bpy.ops.object.select_all(action="DESELECT")
    for n in BODY_NAMES:
        parts[n].select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=GLB_OUT,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
    )
    print("Exported", GLB_OUT)


def write_report(parts, arm):
    total_v = sum(len(parts[n].data.vertices) for n in BODY_NAMES)
    tris = 0
    for n in BODY_NAMES:
        parts[n].data.calc_loop_triangles()
        tris += len(parts[n].data.loop_triangles)
    mats = sorted({s.material.name for n in BODY_NAMES for s in parts[n].material_slots if s.material})
    mins, maxs, _ = char_bounds(parts)
    lines = [
        "GrindScape Male Assembled Modular — Assembly Report",
        "=" * 60,
        f"Source folder: {SRC_DIR}",
        f"Reference armature: {REF_GLB}",
        "",
        "BODY_MODULAR:",
    ]
    for n in BODY_NAMES:
        o = parts[n]
        lines.append(f"  - {n}: {len(o.data.vertices)} verts, {len(o.data.polygons)} faces")
    lines += [
        "",
        f"Vertices: {total_v}",
        f"Triangles: {tris}",
        f"Materials ({len(mats)}): {', '.join(mats)}",
        f"Bones: {len(arm.data.bones)}",
        f"Bounds X {mins.x:.3f}..{maxs.x:.3f}  Y {mins.y:.3f}..{maxs.y:.3f}  Z {mins.z:.3f}..{maxs.z:.3f}",
        f"Height: {maxs.z - mins.z:.3f} m",
        "",
        "Modular hide: Head / Upperbody / Hand_L / Hand_R / Lowerbody / Foot_L / Foot_R",
        "Rig: shared Mixamo armature, automatic weights, ≤4 influences.",
        "Seams: caps opened, boundary radii matched, neighborhood smoothed.",
        "Materials: unified GS_Skin + GS_Underwear (+ eye mats).",
        "",
        f"Blend: {BLEND_OUT}",
        f"GLB:   {GLB_OUT}",
        f"Shots: {SHOT_DIR}",
    ]
    text = "\n".join(lines) + "\n"
    with open(REPORT_OUT, "w") as f:
        f.write(text)
    print(text)


def validate_reimport():
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=GLB_OUT)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    found = set()
    for o in meshes:
        for e in BODY_NAMES:
            if e in o.name:
                found.add(e)
    skinned = sum(1 for o in meshes if o.vertex_groups or (o.parent and o.parent.type == "ARMATURE"))
    ok = found == set(BODY_NAMES) and len(arms) >= 1 and skinned >= 7
    # sanity bounds
    mins = Vector((1e9, 1e9, 1e9))
    maxs = Vector((-1e9, -1e9, -1e9))
    for o in meshes:
        if "Icosphere" in o.name:
            continue
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            mins = Vector(tuple(min(a, b) for a, b in zip(mins, w)))
            maxs = Vector(tuple(max(a, b) for a, b in zip(maxs, w)))
    height = maxs.z - mins.z
    centered = abs((mins.x + maxs.x) * 0.5) < 0.15
    height_ok = 1.5 < height < 2.1
    ok = ok and centered and height_ok
    msg = (
        f"\nRe-import validation:\n"
        f"  parts={sorted(found)}\n"
        f"  bones={len(arms[0].data.bones) if arms else 0}\n"
        f"  height={height:.3f} centered={centered}\n"
        f"  RESULT={'PASS' if ok else 'FAIL'}\n"
    )
    print(msg)
    with open(REPORT_OUT, "a") as f:
        f.write(msg)
    if not ok:
        raise RuntimeError("Validation failed")
    return ok


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SHOT_DIR, exist_ok=True)
    clear_scene()

    root = ensure_collection("GRINDSCAPE_CHARACTER")
    source_col = ensure_collection("SOURCE_MESHES", root)
    work_col = ensure_collection("CHARACTER_WORKING", root)
    body_col = ensure_collection("BODY_MODULAR", root)
    arm_col = ensure_collection("ARMATURE", root)
    ensure_collection("MATERIALS", root)
    ensure_collection("TEST_POSES", root)
    ensure_collection("EXPORT", root)

    print("=== Import ===")
    sources = import_sources(source_col)
    print("=== Prepare ===")
    parts = prepare_parts(sources, work_col)
    print("=== Armature ===")
    arm = load_armature(arm_col)
    print("=== Align ===")
    align_parts(parts, arm)
    print("=== Blend seams ===")
    blend_seams(parts)
    print("=== Materials ===")
    assign_materials(parts)
    print("=== Rig ===")
    bind_parts(parts, arm)
    for n in BODY_NAMES:
        link_only(parts[n], body_col)
    work_col.hide_viewport = True
    work_col.hide_render = True

    print("=== Render QA ===")
    cam = setup_render()
    render_qa(parts, arm, cam)

    print("=== Save / export ===")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
    write_report(parts, arm)
    export_glb(parts, arm)
    print("=== Validate ===")
    validate_reimport()
    print("DONE")


if __name__ == "__main__":
    main()
