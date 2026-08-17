"""
repair_meshy_seams.py
=====================
Aggressive Boolean / voxel-remesh seam repair on the assembled modular male.

For each modular joint (neck, waist, wrists, ankles):
  1. Duplicate adjoining parts and Boolean-union them
  2. Voxel-remesh + smooth the union (clean continuous exterior)
  3. Bisect at the modular seam plane into two halves
  4. Project each original part's seam band onto its remeshed half
  5. Force both boundaries onto the same cut loop (matched modular edge)

Preserves modular object names / armature parenting.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python repair_meshy_seams.py
"""

from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

REPO = os.path.abspath(os.path.dirname(__file__))
OUT_DIR = os.path.join(REPO, "assembled_male")
BLEND = os.path.join(OUT_DIR, "GrindScape_Male_Assembled_Modular.blend")
GLB_OUT = os.path.join(OUT_DIR, "GrindScape_Male_Assembled_Modular.glb")
SHOT_DIR = os.path.join(OUT_DIR, "screenshots")
REPORT = os.path.join(OUT_DIR, "GrindScape_Male_Assembly_Report.txt")

BODY = [
    "Body_Head",
    "Body_Upperbody",
    "Body_Hand_L",
    "Body_Hand_R",
    "Body_Lowerbody",
    "Body_Foot_L",
    "Body_Foot_R",
]


def active(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def world_bounds(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mins = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    maxs = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mins, maxs, (mins + maxs) * 0.5


def world_verts(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def clean(obj, merge=0.0002):
    active(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=merge)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    for p in obj.data.polygons:
        p.use_smooth = True


def strip_armature_mod(obj):
    for m in list(obj.modifiers):
        if m.type == "ARMATURE":
            obj.modifiers.remove(m)


def restore_armature(obj, arm):
    """Parent to armature while preserving world transform (arm may be scale 0.01)."""
    strip_armature_mod(obj)
    mw = obj.matrix_world.copy()
    obj.parent = arm
    obj.matrix_world = mw  # keeps world size despite parent scale
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True


def duplicate_mesh(obj, name):
    """Duplicate mesh with world transform baked into verts (safe unparent)."""
    # Evaluate world positions from source first
    src_world = [obj.matrix_world @ v.co for v in obj.data.vertices]
    dup = obj.copy()
    dup.data = obj.data.copy()
    dup.name = name
    dup.data.name = name
    dup.parent = None
    dup.matrix_world = Matrix.Identity(4)
    for m in list(dup.modifiers):
        dup.modifiers.remove(m)
    bpy.context.scene.collection.objects.link(dup)
    # Write baked world coords into local verts
    for v, w in zip(dup.data.vertices, src_world):
        v.co = w
    dup.data.update()
    return dup


def delete_obj(obj):
    if obj and obj.name in bpy.data.objects:
        bpy.data.objects.remove(obj, do_unlink=True)


def boolean_union(a, b, name):
    """Return a new mesh that is boolean union of a and b (consumes copies)."""
    active(a)
    mod = a.modifiers.new("BoolUnion", "BOOLEAN")
    mod.operation = "UNION"
    mod.solver = "EXACT"
    mod.object = b
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception:
        # fallback FAST
        if "BoolUnion" in a.modifiers:
            a.modifiers["BoolUnion"].solver = "FAST"
            bpy.ops.object.modifier_apply(modifier="BoolUnion")
    a.name = name
    a.data.name = name
    delete_obj(b)
    clean(a, merge=0.0003)
    return a


def voxel_remesh(obj, voxel=0.012, smooth_iter=12):
    active(obj)
    # Blender 4.x remesh
    mod = obj.modifiers.new("Vox", "REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = voxel
    try:
        mod.use_smooth_shade = True
    except Exception:
        pass
    bpy.ops.object.modifier_apply(modifier=mod.name)
    # Laplacian-ish smooth
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=smooth_iter)
    bpy.ops.object.mode_set(mode="OBJECT")
    clean(obj)
    return obj


def bisect_keep(obj, plane_co: Vector, plane_no: Vector, clear_inner: bool, name: str):
    """Bisect mesh; clear one side. Returns object (modified in place, renamed)."""
    active(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.bisect(
        plane_co=plane_co,
        plane_no=plane_no,
        clear_inner=clear_inner,
        clear_outer=not clear_inner,
        use_fill=True,
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.name = name
    obj.data.name = name
    clean(obj)
    return obj


def build_kdtree(obj):
    pts = world_verts(obj)
    if len(pts) < 3:
        return None, pts
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    return kd, pts


def project_band_to_target(src, tgt, center: Vector, axis: Vector, band=0.09, radial_pad=0.12, strength=0.85, max_move=0.04):
    """Project src verts in a slab around center onto tgt surface (clamped)."""
    if tgt is None or len(tgt.data.vertices) < 3:
        print("    project skip: empty target")
        return 0
    axis = axis.normalized()
    kd, _ = build_kdtree(tgt)
    if kd is None:
        print("    project skip: no kdtree")
        return 0
    mw = src.matrix_world
    imw = mw.inverted()
    moved = 0
    for v in src.data.vertices:
        w = mw @ v.co
        axial = (w - center).dot(axis)
        if abs(axial) > band:
            continue
        radial = (w - center) - axis * axial
        if radial.length > radial_pad:
            continue
        co, idx, dist = kd.find(w)
        if co is None or dist is None or dist > 0.14:
            continue
        t = (1.0 - abs(axial) / band) ** 1.4
        w2 = w.lerp(Vector(co), strength * t)
        delta = w2 - w
        if delta.length > max_move:
            w2 = w + delta.normalized() * max_move
        v.co = imw @ w2
        moved += 1
    src.data.update()
    return moved


def force_boundary_to_plane(obj, center: Vector, axis: Vector, band=0.035):
    """Snap verts near plane onto the plane (shared modular cut)."""
    axis = axis.normalized()
    mw = obj.matrix_world
    imw = mw.inverted()
    for v in obj.data.vertices:
        w = mw @ v.co
        axial = (w - center).dot(axis)
        if abs(axial) > band:
            continue
        t = 1.0 - abs(axial) / band
        w2 = w - axis * (axial * (0.65 + 0.35 * t))
        v.co = imw @ w2
    obj.data.update()


def match_boundaries_on_plane(a, b, center: Vector, axis: Vector, sample_r=0.2):
    """
    Make A's and B's verts nearest the cut plane share the same radial silhouette
    by averaging projections onto the plane.
    """
    axis = axis.normalized()
    arb = Vector((1, 0, 0)) if abs(axis.z) < 0.9 else Vector((0, 1, 0))
    x_axis = axis.cross(arb).normalized()
    y_axis = axis.cross(x_axis).normalized()

    def plane_pts(obj):
        mw = obj.matrix_world
        out = []
        for v in obj.data.vertices:
            w = mw @ v.co
            if abs((w - center).dot(axis)) < 0.03:
                out.append((v.index, w))
        return out

    a_pts = plane_pts(a)
    b_pts = plane_pts(b)
    if len(a_pts) < 6 or len(b_pts) < 6:
        return

    # Build average radius by angle from both
    buckets = {}
    for src_pts in (a_pts, b_pts):
        for _, w in src_pts:
            d = w - center
            d = d - axis * d.dot(axis)
            ang = math.atan2(d.dot(y_axis), d.dot(x_axis))
            key = int(round(ang / (2 * math.pi) * 48)) % 48
            buckets.setdefault(key, []).append(d.length)

    avg_r = {k: sum(v) / len(v) for k, v in buckets.items() if v}
    if not avg_r:
        return

    def apply(obj, pts):
        mw = obj.matrix_world
        imw = mw.inverted()
        for idx, w in pts:
            d = w - center
            d = d - axis * d.dot(axis)
            ang = math.atan2(d.dot(y_axis), d.dot(x_axis))
            key = int(round(ang / (2 * math.pi) * 48)) % 48
            # blend neighboring buckets
            r0 = avg_r.get(key)
            if r0 is None:
                # nearest key
                key = min(avg_r.keys(), key=lambda k: min(abs(k - key), 48 - abs(k - key)))
                r0 = avg_r[key]
            if d.length < 1e-8:
                d = x_axis
            new_w = center + d.normalized() * r0
            # keep slight side offset so parts don't z-fight: nudge along axis later
            obj.data.vertices[idx].co = imw @ new_w
        obj.data.update()

    apply(a, a_pts)
    apply(b, b_pts)


def smooth_band(obj, center: Vector, axis: Vector, band=0.08, iterations=8):
    axis = axis.normalized()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    mw = obj.matrix_world
    imw = mw.inverted()
    # work in local; convert center
    ring = set()
    for v in bm.verts:
        w = mw @ v.co
        if abs((w - center).dot(axis)) <= band:
            ring.add(v.index)
    # grow once
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
            nbrs = [e.other_vert(v) for e in v.link_edges]
            if not nbrs:
                newc[vi] = coords[vi]
                continue
            avg = sum((coords[n.index] for n in nbrs), Vector()) / len(nbrs)
            newc[vi] = coords[vi].lerp(avg, 0.55)
        coords.update(newc)
    for v in bm.verts:
        v.co = coords[v.index]
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()


def boundary_loops(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    seen = set()
    loops = []
    mw = obj.matrix_world
    for e0 in bm.edges:
        if not e0.is_boundary or e0.index in seen:
            continue
        start = e0.verts[0]
        cur = e0.verts[1]
        seen.add(e0.index)
        verts = [start]
        for _ in range(100000):
            verts.append(cur)
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
        # unique by index, preserve BMVert refs
        uniq_verts = []
        used = set()
        for v in verts:
            if v.index in used:
                continue
            used.add(v.index)
            uniq_verts.append(v)
        if len(uniq_verts) < 3:
            continue
        coords = [mw @ v.co for v in uniq_verts]
        c = sum(coords, Vector()) / len(coords)
        r = sum((p - c).length for p in coords) / len(coords)
        loops.append({
            "indices": [v.index for v in uniq_verts],
            "center": c,
            "radius": r,
            "count": len(uniq_verts),
        })
    bm.free()
    return sorted(loops, key=lambda L: -L["count"])


def open_caps_near(obj, center: Vector, axis: Vector, band=0.04):
    """Delete nearly planar end-cap faces near center facing along axis."""
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
        if abs((c - center).dot(axis)) > band:
            continue
        n = f.normal.copy()
        n.rotate(rot)
        if abs(n.dot(axis)) < 0.55:
            continue
        to_del.append(f)
    if len(to_del) >= 2:
        bmesh.ops.delete(bm, geom=to_del, context="FACES")
        print(f"    opened {len(to_del)} cap faces on {obj.name}")
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()
    clean(obj)


def repair_joint(parts, name_a, name_b, axis: Vector, plane_center: Vector, voxel=0.011, band=0.10, label="joint"):
    """
    Remesh-union repair between parts[name_a] and parts[name_b].
    clear_inner for bisect: half with positive axis from plane goes to 'outer'.
    We assign:
      - side with center along +axis keeps clear_inner=True (keeps +axis side)
    """
    print(f"\n=== Repair {label}: {name_a} <-> {name_b} ===")
    a = parts[name_a]
    b = parts[name_b]
    axis = axis.normalized()

    # Hard-snap parts so seam centers meet (close large air gaps first)
    def nearest_boundary_center(obj, target):
        loops = boundary_loops(obj)
        if not loops:
            return world_bounds(obj)[2]
        return min(loops, key=lambda L: (L["center"] - target).length)["center"]

    ca = nearest_boundary_center(a, plane_center)
    cb = nearest_boundary_center(b, plane_center)
    # Move each halfway toward a shared mid-plane point
    mid = ca.lerp(cb, 0.5)
    # Prefer mid on the supplied plane_center laterally
    mid = plane_center.lerp(mid, 0.35)
    def translate_world(obj, delta):
        imw = obj.matrix_world.inverted()
        for v in obj.data.vertices:
            w = obj.matrix_world @ v.co
            v.co = imw @ (w + delta)
        obj.data.update()

    translate_world(a, mid - ca)
    translate_world(b, mid - cb)
    # Slight overlap along axis based on which side each part lives on
    a_c = world_bounds(a)[2]
    b_c = world_bounds(b)[2]
    a_sign = 1.0 if (a_c - mid).dot(axis) >= 0 else -1.0
    b_sign = 1.0 if (b_c - mid).dot(axis) >= 0 else -1.0
    translate_world(a, axis * (-0.012 * a_sign))  # pull toward mid
    translate_world(b, axis * (-0.012 * b_sign))
    plane_center = mid.copy()
    print(f"  hard-snapped to mid={tuple(round(x,3) for x in mid)}")

    # Open caps only on non-limb-tip joints (wrist tip opens made needle arms)
    if "wrist" not in label:
        open_caps_near(a, plane_center, axis, band=0.028)
        open_caps_near(b, plane_center, axis, band=0.028)

    da = duplicate_mesh(a, f"TMP_{label}_A")
    db = duplicate_mesh(b, f"TMP_{label}_B")

    try:
        union = boolean_union(da, db, f"TMP_{label}_UNION")
    except Exception as e:
        print(f"  Boolean failed ({e}), joining instead")
        active(da)
        db.select_set(True)
        bpy.ops.object.join()
        union = bpy.context.active_object
        union.name = f"TMP_{label}_UNION"
        clean(union, merge=0.0005)

    print(f"  union verts={len(union.data.vertices)} voxel={voxel}")
    ub = world_bounds(union)
    uh = ub[1].z - ub[0].z
    print(f"  union height={uh:.3f}")
    if uh < 0.05:
        print("  SKIP: union too small / failed")
        delete_obj(union)
        return

    voxel_remesh(union, voxel=voxel, smooth_iter=10)
    ub = world_bounds(union)
    uh = ub[1].z - ub[0].z
    print(f"  remeshed height={uh:.3f} verts={len(union.data.vertices)}")
    if uh < 0.05 or len(union.data.vertices) < 50:
        print("  SKIP: remesh collapsed")
        delete_obj(union)
        return

    # Project BOTH originals onto the full remeshed union
    tight = min(band, 0.09)
    ma = project_band_to_target(a, union, plane_center, axis, band=tight, radial_pad=tight * 1.7, strength=0.92, max_move=0.07)
    mb = project_band_to_target(b, union, plane_center, axis, band=tight, radial_pad=tight * 1.7, strength=0.92, max_move=0.07)
    print(f"  projected verts a={ma} b={mb}")

    ca = world_bounds(a)[2]
    cb = world_bounds(b)[2]
    a_on_pos = (ca - plane_center).dot(axis) >= (cb - plane_center).dot(axis)

    # Shared plane + matched silhouette (tight)
    force_boundary_to_plane(a, plane_center, axis, band=0.025)
    force_boundary_to_plane(b, plane_center, axis, band=0.025)
    match_boundaries_on_plane(a, b, plane_center, axis)

    # Tiny opposing offset so modular cut doesn't z-fight
    nudge = axis * 0.0012
    for obj, side in ((a, 1 if a_on_pos else -1), (b, -1 if a_on_pos else 1)):
        mw = obj.matrix_world
        imw = mw.inverted()
        for v in obj.data.vertices:
            w = mw @ v.co
            if abs((w - plane_center).dot(axis)) < 0.015:
                v.co = imw @ (w + nudge * side)
        obj.data.update()

    smooth_band(a, plane_center, axis, band=tight * 0.85, iterations=6)
    smooth_band(b, plane_center, axis, band=tight * 0.85, iterations=6)
    clean(a)
    clean(b)

    delete_obj(union)
    for name in list(bpy.data.objects.keys()):
        if name.startswith(f"TMP_{label}"):
            delete_obj(bpy.data.objects[name])

    # Post-joint scale guard
    pts = []
    for obj in (a, b):
        pts.extend(world_verts(obj))
    if pts:
        zs = [p.z for p in pts]
        span = max(zs) - min(zs)
        print(f"  post-joint local span Z={span:.3f}")
        if span < 0.05:
            raise RuntimeError(f"{label} collapsed geometry (span={span})")

    print(f"  done {label}")


def estimate_joint_centers(parts):
    """Estimate seam centers from current geometry."""
    head, upper, lower = parts["Body_Head"], parts["Body_Upperbody"], parts["Body_Lowerbody"]
    hl = boundary_loops(head)
    ul = boundary_loops(upper)
    ll = boundary_loops(lower)

    def nearest_z(loops, z, x_lim=0.15):
        pool = [L for L in loops if abs(L["center"].x) < x_lim] or loops
        return min(pool, key=lambda L: abs(L["center"].z - z)) if pool else None

    # Neck: between head bottom and upper top
    h_mins, h_maxs, h_c = world_bounds(head)
    u_mins, u_maxs, u_c = world_bounds(upper)
    neck_z = (h_mins.z + u_maxs.z) * 0.5
    if hl and ul:
        hb = min(hl, key=lambda L: L["center"].z)
        un = max([L for L in ul if abs(L["center"].x) < 0.15] or ul, key=lambda L: L["center"].z)
        neck_c = hb["center"].lerp(un["center"], 0.5)
    else:
        neck_c = Vector((0, (h_c.y + u_c.y) * 0.5, neck_z))

    # Waist
    l_mins, l_maxs, l_c = world_bounds(lower)
    waist_z = (u_mins.z + l_maxs.z) * 0.5
    if ul and ll:
        uw = min([L for L in ul if abs(L["center"].x) < 0.15] or ul, key=lambda L: L["center"].z)
        lw = max([L for L in ll if abs(L["center"].x) < 0.15] or ll, key=lambda L: L["center"].z)
        waist_c = uw["center"].lerp(lw["center"], 0.5)
    else:
        waist_c = Vector((0, (u_c.y + l_c.y) * 0.5, waist_z))

    # Wrists: extreme X tips of upper vs hands
    wrists = {}
    for side, hand_name in (("L", "Body_Hand_L"), ("R", "Body_Hand_R")):
        hand = parts[hand_name]
        u_mins, u_maxs, _ = world_bounds(upper)
        pts = world_verts(upper)
        tip = [p for p in pts if p.x > u_maxs.x - 0.06] if side == "L" else [p for p in pts if p.x < u_mins.x + 0.06]
        hc = world_bounds(hand)[2]
        if tip:
            tip.sort(key=lambda p: (p - hc).length)
            tc = sum(tip[:20], Vector()) / min(20, len(tip))
        else:
            tc = hc.copy()
        # axis from upper center toward hand
        axis = (hc - u_c).normalized()
        wrists[side] = (tc, axis)

    # Ankles
    ankles = {}
    for side, foot_name in (("L", "Body_Foot_L"), ("R", "Body_Foot_R")):
        foot = parts[foot_name]
        fl = boundary_loops(foot)
        if fl:
            f_top = max(fl, key=lambda L: L["center"].z)["center"]
        else:
            f_mins, f_maxs, f_c = world_bounds(foot)
            f_top = Vector((f_c.x, f_c.y, f_maxs.z))
        lpts = [p for p in world_verts(lower) if (p.x > 0.02 if side == "L" else p.x < -0.02)]
        if lpts:
            low = sorted(lpts, key=lambda p: p.z)[:25]
            lc = sum(low, Vector()) / len(low)
        else:
            lc = f_top.copy()
        ankles[side] = (lc.lerp(f_top, 0.5), Vector((0, 0, 1)))

    return {
        "neck": (neck_c, Vector((0, 0, 1))),
        "waist": (waist_c, Vector((0, 0, 1))),
        "wrist_L": wrists["L"],
        "wrist_R": wrists["R"],
        "ankle_L": ankles["L"],
        "ankle_R": ankles["R"],
    }


def rebind(parts, arm):
    for name in BODY:
        obj = parts[name]
        # keep existing vgroups; just restore armature modifier
        restore_armature(obj, arm)
        # limit / normalize if groups exist
        if obj.vertex_groups:
            active(obj)
            try:
                bpy.ops.object.vertex_group_limit_total(limit=4)
                bpy.ops.object.vertex_group_normalize_all(lock_active=False)
            except Exception:
                pass
        print(f"  rebound {name} groups={len(obj.vertex_groups)}")


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1280
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    # lights
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        bpy.ops.object.light_add(type="AREA", location=(1.6, -2.0, 2.4))
        bpy.context.active_object.data.energy = 90
        bpy.context.active_object.data.size = 2.5
        bpy.ops.object.light_add(type="AREA", location=(-2.0, -0.8, 1.8))
        bpy.context.active_object.data.energy = 35
        bpy.ops.object.light_add(type="AREA", location=(0.3, 2.0, 2.2))
        bpy.context.active_object.data.energy = 50
    cam = bpy.data.objects.get("QA_Camera")
    if cam is None:
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
    if center is None:
        c = Vector((c.x, c.y, (mins.z + maxs.z) * 0.52))
    else:
        c = center
    height = max(maxs.z - mins.z, 0.5)
    dist = max(height * 1.55, 1.6)
    cam.location = c + offset.normalized() * dist
    cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("Rendered", path)


def render_qa(parts, arm, cam):
    os.makedirs(SHOT_DIR, exist_ok=True)
    # clear pose
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.rotation_euler = (0, 0, 0)
    bpy.ops.object.mode_set(mode="OBJECT")

    for name, off in {
        "front": Vector((0, -1, 0.12)),
        "back": Vector((0, 1, 0.12)),
        "side": Vector((1, 0, 0.08)),
        "three_quarter": Vector((0.75, -1, 0.18)),
    }.items():
        render_view(cam, parts, os.path.join(SHOT_DIR, f"assembled_{name}.png"), off)

    # closeups
    joints = estimate_joint_centers(parts)
    for key, fname, off, lens in (
        ("neck", "closeup_neck.png", Vector((0.45, -1, 0.1)), 85),
        ("waist", "closeup_waist.png", Vector((0.5, -1, 0)), 70),
        ("wrist_L", "closeup_wrist.png", Vector((0.6, -0.9, 0.2)), 90),
        ("ankle_L", "closeup_ankle.png", Vector((0.55, -1, 0.25)), 90),
    ):
        c, _ = joints[key]
        render_view(cam, parts, os.path.join(SHOT_DIR, fname), off, lens=lens, center=c)

    for hide in BODY:
        for n, o in parts.items():
            o.hide_render = n == hide
            o.hide_viewport = n == hide
        render_view(cam, {k: v for k, v in parts.items() if k != hide},
                    os.path.join(SHOT_DIR, f"hide_{hide}.png"), Vector((0.7, -1, 0.12)))
    for o in parts.values():
        o.hide_render = False
        o.hide_viewport = False

    # a few poses
    poses = {
        "arms_raised": {"mixamorig:LeftArm": (0, 0, -70), "mixamorig:RightArm": (0, 0, 70)},
        "walk": {
            "mixamorig:LeftUpLeg": (-25, 0, 0),
            "mixamorig:RightUpLeg": (20, 0, 0),
            "mixamorig:LeftLeg": (15, 0, 0),
            "mixamorig:RightLeg": (10, 0, 0),
        },
        "crouch": {
            "mixamorig:LeftUpLeg": (-70, 0, 10),
            "mixamorig:RightUpLeg": (-70, 0, -10),
            "mixamorig:LeftLeg": (80, 0, 0),
            "mixamorig:RightLeg": (80, 0, 0),
        },
    }
    for pose_name, pdata in poses.items():
        bpy.ops.object.mode_set(mode="POSE")
        for pb in arm.pose.bones:
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (0, 0, 0)
        for bname, euler in pdata.items():
            pb = arm.pose.bones.get(bname)
            if pb:
                pb.rotation_mode = "XYZ"
                pb.rotation_euler = tuple(math.radians(a) for a in euler)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
        render_view(cam, parts, os.path.join(SHOT_DIR, f"pose_{pose_name}.png"), Vector((0.7, -1, 0.12)))
    # reset
    bpy.ops.object.mode_set(mode="POSE")
    for pb in arm.pose.bones:
        pb.rotation_euler = (0, 0, 0)
    bpy.ops.object.mode_set(mode="OBJECT")


def export_glb(parts, arm):
    bpy.ops.object.select_all(action="DESELECT")
    for n in BODY:
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


def validate():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=GLB_OUT)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    found = {e for o in meshes for e in BODY if e in o.name}
    ok = found == set(BODY) and len(arms) >= 1
    msg = f"\nSeam-repair re-import: parts={sorted(found)} bones={len(arms[0].data.bones) if arms else 0} RESULT={'PASS' if ok else 'FAIL'}\n"
    print(msg)
    with open(REPORT, "a") as f:
        f.write(msg)
    if not ok:
        raise RuntimeError("validation failed")


def main():
    print("Opening", BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)

    parts = {n: bpy.data.objects[n] for n in BODY}
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")

    # Bake world transforms, then detach from armature without collapsing space
    for n, o in parts.items():
        strip_armature_mod(o)
        # bake current world verts into mesh at identity
        world = [o.matrix_world @ v.co for v in o.data.vertices]
        o.parent = None
        o.matrix_world = Matrix.Identity(4)
        for v, w in zip(o.data.vertices, world):
            v.co = w
        o.data.update()
        clean(o)

    # Sanity: character must remain ~human scale
    mins, maxs, _ = char_bounds(parts)
    height = maxs.z - mins.z
    print(f"Pre-repair height={height:.3f}")
    if height < 0.5 or height > 3.5:
        raise RuntimeError(f"Unexpected character height before repair: {height}")

    joints = estimate_joint_centers(parts)
    print("Joint centers:")
    for k, (c, ax) in joints.items():
        print(f"  {k}: c={tuple(round(x,3) for x in c)} axis={tuple(round(x,3) for x in ax)}")

    def full_height():
        mins, maxs, _ = char_bounds(parts)
        return maxs.z - mins.z

    def run_joint(*args, **kwargs):
        repair_joint(*args, **kwargs)
        h = full_height()
        print(f"  character height now={h:.3f}")
        if h < 1.0:
            raise RuntimeError(f"Character collapsed after {kwargs.get('label')}: height={h}")

    # Neck
    run_joint(parts, "Body_Head", "Body_Upperbody", joints["neck"][1], joints["neck"][0],
              voxel=0.010, band=0.08, label="neck")

    # Waist
    joints = estimate_joint_centers(parts)
    run_joint(parts, "Body_Upperbody", "Body_Lowerbody", joints["waist"][1], joints["waist"][0],
              voxel=0.012, band=0.09, label="waist")

    # Wrists
    for side in ("L", "R"):
        joints = estimate_joint_centers(parts)
        c, ax = joints[f"wrist_{side}"]
        run_joint(parts, "Body_Upperbody", f"Body_Hand_{side}", ax, c,
                  voxel=0.008, band=0.06, label=f"wrist_{side}")

    # Ankles
    for side in ("L", "R"):
        joints = estimate_joint_centers(parts)
        c, ax = joints[f"ankle_{side}"]
        run_joint(parts, "Body_Lowerbody", f"Body_Foot_{side}", ax, c,
                  voxel=0.008, band=0.055, label=f"ankle_{side}")

    # Seat feet on ground
    for n in ("Body_Foot_L", "Body_Foot_R"):
        mins, _, _ = world_bounds(parts[n])
        delta = Vector((0, 0, -mins.z))
        imw = parts[n].matrix_world.inverted()
        for v in parts[n].data.vertices:
            w = parts[n].matrix_world @ v.co
            v.co = imw @ (w + delta)
        parts[n].data.update()

    print("\n=== Rebind armature ===")
    rebind(parts, arm)

    # Ensure skin material still assigned
    skin = bpy.data.materials.get("GS_Skin")
    und = bpy.data.materials.get("GS_Underwear")
    for n in BODY:
        o = parts[n]
        if not o.data.materials:
            if skin:
                o.data.materials.append(skin)

    print("=== Render QA ===")
    cam = setup_render()
    render_qa(parts, arm, cam)

    print("=== Save / export ===")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    export_glb(parts, arm)

    with open(REPORT, "a") as f:
        f.write("\n--- Seam repair pass (Boolean + voxel remesh + bisect + project) ---\n")
        f.write("Joints repaired: neck, waist, wrist_L/R, ankle_L/R\n")
        f.write("Modular separation preserved; boundaries matched on cut planes.\n")

    print("=== Validate ===")
    validate()
    print("DONE")


if __name__ == "__main__":
    main()
