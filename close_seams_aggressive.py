"""
close_seams_aggressive.py
=========================
Direct AABB / tip-based gap closing + radial flaring for modular seams.
Preserves modular objects and armature parenting (keep_transform).

Run after assemble / repair:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python close_seams_aggressive.py
"""

from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

REPO = os.path.abspath(os.path.dirname(__file__))
OUT = os.path.join(REPO, "assembled_male")
BLEND = os.path.join(OUT, "GrindScape_Male_Assembled_Modular.blend")
GLB = os.path.join(OUT, "GrindScape_Male_Assembled_Modular.glb")
SHOT = os.path.join(OUT, "screenshots")
BODY = [
    "Body_Head", "Body_Upperbody", "Body_Hand_L", "Body_Hand_R",
    "Body_Lowerbody", "Body_Foot_L", "Body_Foot_R",
]


def world_bounds(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    mins = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    maxs = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mins, maxs, (mins + maxs) * 0.5


def translate(obj, delta: Vector):
    imw = obj.matrix_world.inverted()
    for v in obj.data.vertices:
        v.co = imw @ (obj.matrix_world @ v.co + delta)
    obj.data.update()


def scale_about(obj, center: Vector, s: float):
    imw = obj.matrix_world.inverted()
    for v in obj.data.vertices:
        w = obj.matrix_world @ v.co
        v.co = imw @ (center + (w - center) * s)
    obj.data.update()


def flare_band(obj, center: Vector, axis: Vector, target_r: float, band=0.08, strength=0.85):
    """Radially scale verts in a band toward target radius about axis through center."""
    axis = axis.normalized()
    imw = obj.matrix_world.inverted()
    mw = obj.matrix_world
    for v in obj.data.vertices:
        w = mw @ v.co
        axial = (w - center).dot(axis)
        if abs(axial) > band:
            continue
        radial = (w - center) - axis * axial
        if radial.length < 1e-8:
            continue
        t = (1.0 - abs(axial) / band) ** 1.2
        new_r = radial.length * (1 - strength * t) + target_r * (strength * t)
        w2 = center + axis * axial + radial.normalized() * new_r
        v.co = imw @ w2
    obj.data.update()


def smooth_band(obj, center: Vector, axis: Vector, band=0.07, iterations=8):
    axis = axis.normalized()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    mw = obj.matrix_world
    ring = set()
    for v in bm.verts:
        w = mw @ v.co
        if abs((w - center).dot(axis)) <= band:
            ring.add(v.index)
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
            avg = sum((coords[n.index] for n in nbrs), Vector()) / max(len(nbrs), 1)
            newc[vi] = coords[vi].lerp(avg, 0.55)
        coords.update(newc)
    for v in bm.verts:
        v.co = coords[v.index]
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()


def tip_cluster(obj, side: str):
    mins, maxs, _ = world_bounds(obj)
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if side == "L":
        tip = [p for p in pts if p.x > maxs.x - 0.06]
    else:
        tip = [p for p in pts if p.x < mins.x + 0.06]
    tip.sort(key=lambda p: p.z)
    tip = tip[: max(16, len(tip) // 3)]
    c = sum(tip, Vector()) / len(tip)
    r = sum(math.hypot(p.x - c.x, p.y - c.y) for p in tip) / len(tip)
    return c, r


def ankle_cluster(obj, side: str):
    mins, maxs, _ = world_bounds(obj)
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if side == "L":
        pts = [p for p in pts if p.x > 0.02]
    else:
        pts = [p for p in pts if p.x < -0.02]
    pts = sorted(pts, key=lambda p: p.z)[:30]
    c = sum(pts, Vector()) / len(pts)
    r = sum(math.hypot(p.x - c.x, p.y - c.y) for p in pts) / len(pts)
    return c, r


def foot_top(obj):
    mins, maxs, c = world_bounds(obj)
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices if (obj.matrix_world @ v.co).z > maxs.z - 0.04]
    tc = sum(pts, Vector()) / len(pts)
    r = sum(math.hypot(p.x - tc.x, p.y - tc.y) for p in pts) / len(pts)
    return tc, r


def detach_bake(obj):
    """Bake world verts, clear parent, identity matrix — keep meter-space verts."""
    world = [obj.matrix_world @ v.co for v in obj.data.vertices]
    # IMPORTANT: if parent has scale, matrix_world shrinks — compensate using raw if needed
    # Detect: if world height << raw height, use raw (already meter space)
    raw_zs = [v.co.z for v in obj.data.vertices]
    world_zs = [w.z for w in world]
    raw_h = max(raw_zs) - min(raw_zs)
    world_h = max(world_zs) - min(world_zs)
    obj.parent = None
    for m in list(obj.modifiers):
        if m.type == "ARMATURE":
            obj.modifiers.remove(m)
    obj.matrix_world = Matrix.Identity(4)
    if world_h < raw_h * 0.5:
        # already in meter local space; leave verts
        pass
    else:
        for v, w in zip(obj.data.vertices, world):
            v.co = w
    obj.data.update()


def reparent_keep(obj, arm):
    mw = obj.matrix_world.copy()
    obj.parent = arm
    obj.matrix_world = mw
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True


def boolean_remesh_project(a, b, center, axis, voxel=0.011, band=0.08):
    """Optional polish: remesh union and project band with clamp."""
    def dup(obj, name):
        d = obj.copy()
        d.data = obj.data.copy()
        d.name = name
        d.parent = None
        d.matrix_world = Matrix.Identity(4)
        for m in list(d.modifiers):
            d.modifiers.remove(m)
        bpy.context.scene.collection.objects.link(d)
        # verts already world-baked
        return d

    da, db = dup(a, "TMP_A"), dup(b, "TMP_B")
    bpy.ops.object.select_all(action="DESELECT")
    da.select_set(True)
    bpy.context.view_layer.objects.active = da
    mod = da.modifiers.new("B", "BOOLEAN")
    mod.operation = "UNION"
    mod.solver = "EXACT"
    mod.object = db
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception:
        if "B" in da.modifiers:
            da.modifiers["B"].solver = "FAST"
            bpy.ops.object.modifier_apply(modifier="B")
    bpy.data.objects.remove(db, do_unlink=True)
    # remesh
    rm = da.modifiers.new("R", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = voxel
    bpy.ops.object.modifier_apply(modifier=rm.name)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=8)
    bpy.ops.object.mode_set(mode="OBJECT")

    pts = [da.matrix_world @ v.co for v in da.data.vertices]
    if len(pts) < 30:
        bpy.data.objects.remove(da, do_unlink=True)
        return
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    axis = axis.normalized()
    for obj in (a, b):
        imw = obj.matrix_world.inverted()
        for v in obj.data.vertices:
            w = obj.matrix_world @ v.co
            if abs((w - center).dot(axis)) > band:
                continue
            co, idx, dist = kd.find(w)
            if co is None or dist > 0.12:
                continue
            t = (1.0 - abs((w - center).dot(axis)) / band) ** 1.2
            w2 = w.lerp(Vector(co), 0.9 * t)
            delta = w2 - w
            if delta.length > 0.06:
                w2 = w + delta.normalized() * 0.06
            v.co = imw @ w2
        obj.data.update()
    bpy.data.objects.remove(da, do_unlink=True)


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    parts = {n: bpy.data.objects[n] for n in BODY}
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")

    for o in parts.values():
        detach_bake(o)

    head, upper, lower = parts["Body_Head"], parts["Body_Upperbody"], parts["Body_Lowerbody"]

    # ── NECK ──
    hmin, hmax, hc = world_bounds(head)
    umin, umax, uc = world_bounds(upper)
    # Neck opening radius on upper (top verts near center)
    top = [upper.matrix_world @ v.co for v in upper.data.vertices
           if (upper.matrix_world @ v.co).z > umax.z - 0.05 and abs((upper.matrix_world @ v.co).x) < 0.12]
    unc = sum(top, Vector()) / len(top)
    unr = sum(math.hypot(p.x - unc.x, p.y - unc.y) for p in top) / len(top)
    # Head neck bottom
    bot = [head.matrix_world @ v.co for v in head.data.vertices
           if (head.matrix_world @ v.co).z < hmin.z + 0.05]
    hnc = sum(bot, Vector()) / len(bot)
    hnr = sum(math.hypot(p.x - hnc.x, p.y - hnc.y) for p in bot) / len(bot)
    print(f"NECK upper r={unr:.3f} head r={hnr:.3f}")
    # Flare head neck to nearly upper opening
    flare_band(head, hnc, Vector((0, 0, 1)), unr * 0.95, band=0.10, strength=0.9)
    # Pull head down to seat into collar with overlap
    hmin, hmax, _ = world_bounds(head)
    umin, umax, _ = world_bounds(upper)
    # Seat: head bottom slightly below upper top
    target_bottom = umax.z - 0.025
    translate(head, Vector((unc.x - hnc.x, unc.y - hnc.y, target_bottom - hmin.z)))
    hmin, _, _ = world_bounds(head)
    bot = [head.matrix_world @ v.co for v in head.data.vertices if (head.matrix_world @ v.co).z < hmin.z + 0.04]
    hnc = sum(bot, Vector()) / len(bot)
    flare_band(upper, unc, Vector((0, 0, 1)), unr * 0.92, band=0.07, strength=0.7)
    flare_band(head, hnc, Vector((0, 0, 1)), unr * 0.92, band=0.08, strength=0.85)
    smooth_band(head, hnc, Vector((0, 0, 1)), band=0.09, iterations=10)
    smooth_band(upper, unc, Vector((0, 0, 1)), band=0.08, iterations=10)
    boolean_remesh_project(head, upper, Vector((0, (hnc.y + unc.y) * 0.5, (hmin.z + umax.z) * 0.5)),
                           Vector((0, 0, 1)), voxel=0.010, band=0.08)
    print("NECK done", world_bounds(head)[0].z, world_bounds(upper)[1].z)

    # ── WAIST ──
    umin, umax, uc = world_bounds(upper)
    lmin, lmax, lc = world_bounds(lower)
    ubot = [upper.matrix_world @ v.co for v in upper.data.vertices
            if (upper.matrix_world @ v.co).z < umin.z + 0.05 and abs((upper.matrix_world @ v.co).x) < 0.18]
    uwc = sum(ubot, Vector()) / len(ubot)
    uwr = sum(math.hypot(p.x - uwc.x, p.y - uwc.y) for p in ubot) / len(ubot)
    ltop = [lower.matrix_world @ v.co for v in lower.data.vertices
            if (lower.matrix_world @ v.co).z > lmax.z - 0.05 and abs((lower.matrix_world @ v.co).x) < 0.18]
    lwc = sum(ltop, Vector()) / len(ltop)
    lwr = sum(math.hypot(p.x - lwc.x, p.y - lwc.y) for p in ltop) / len(ltop)
    mid_r = (uwr + lwr) * 0.5
    print(f"WAIST upper r={uwr:.3f} lower r={lwr:.3f}")
    # Pull lower UP so top overlaps upper bottom
    translate(lower, Vector((uwc.x - lwc.x, uwc.y - lwc.y, (umin.z + 0.03) - lmax.z)))
    # recenter X
    lmin, lmax, lc = world_bounds(lower)
    translate(lower, Vector((-lc.x, 0, 0)))
    umin, umax, _ = world_bounds(upper)
    lmin, lmax, _ = world_bounds(lower)
    uwc = Vector((0, uwc.y, umin.z))
    lwc = Vector((0, lwc.y, lmax.z))
    flare_band(upper, uwc, Vector((0, 0, 1)), mid_r, band=0.08, strength=0.85)
    flare_band(lower, Vector((0, lwc.y, lmax.z)), Vector((0, 0, 1)), mid_r, band=0.08, strength=0.85)
    smooth_band(upper, uwc, Vector((0, 0, 1)), band=0.08, iterations=8)
    smooth_band(lower, Vector((0, 0, lmax.z)), Vector((0, 0, 1)), band=0.08, iterations=8)
    boolean_remesh_project(upper, lower, Vector((0, 0, (umin.z + lmax.z) * 0.5)),
                           Vector((0, 0, 1)), voxel=0.012, band=0.09)
    print("WAIST done", world_bounds(upper)[0].z, world_bounds(lower)[1].z)

    # ── WRISTS ──
    for side, hand_name in (("L", "Body_Hand_L"), ("R", "Body_Hand_R")):
        hand = parts[hand_name]
        tip_c, tip_r = tip_cluster(upper, side)
        # Hand wrist = verts nearest tip
        hpts = [hand.matrix_world @ v.co for v in hand.data.vertices]
        hpts.sort(key=lambda p: (p - tip_c).length)
        wrist_pts = hpts[:40]
        wc = sum(wrist_pts, Vector()) / len(wrist_pts)
        wr = sum((p - wc).length for p in wrist_pts) / len(wrist_pts)
        target_r = max(wr, tip_r, 0.032) * 1.05
        print(f"WRIST_{side} tip_r={tip_r:.3f} hand_r={wr:.3f} -> {target_r:.3f}")
        # Flare arm tip OUT so it's not a needle
        flare_band(upper, tip_c, Vector((1 if side == "L" else -1, 0, 0)), target_r, band=0.09, strength=0.95)
        tip_c, tip_r = tip_cluster(upper, side)
        # Move hand so wrist meets tip
        translate(hand, tip_c - wc)
        # Flare hand wrist
        hpts = [hand.matrix_world @ v.co for v in hand.data.vertices]
        hpts.sort(key=lambda p: (p - tip_c).length)
        wc = sum(hpts[:40], Vector()) / 40
        flare_band(hand, tip_c, (tip_c - world_bounds(hand)[2]).normalized() if (tip_c - world_bounds(hand)[2]).length > 1e-6 else Vector((0, 0, 1)),
                   target_r, band=0.06, strength=0.85)
        smooth_band(upper, tip_c, Vector((1 if side == "L" else -1, 0, 0)), band=0.08, iterations=8)
        smooth_band(hand, tip_c, Vector((0, 0, 1)), band=0.06, iterations=8)
        boolean_remesh_project(upper, hand, tip_c, Vector((1 if side == "L" else -1, 0, 0)),
                               voxel=0.008, band=0.07)

    # ── ANKLES ──
    for side, foot_name in (("L", "Body_Foot_L"), ("R", "Body_Foot_R")):
        foot = parts[foot_name]
        ac, ar = ankle_cluster(lower, side)
        fc, fr = foot_top(foot)
        target_r = max(ar, fr, 0.035)
        print(f"ANKLE_{side} leg_r={ar:.3f} foot_r={fr:.3f}")
        mid = ac.lerp(fc, 0.5)
        translate(foot, Vector((mid.x - fc.x, mid.y - fc.y, mid.z - fc.z)))
        # keep sole on ground
        fmin, _, _ = world_bounds(foot)
        translate(foot, Vector((0, 0, -fmin.z)))
        fc, fr = foot_top(foot)
        flare_band(lower, ac, Vector((0, 0, 1)), target_r, band=0.07, strength=0.9)
        flare_band(foot, fc, Vector((0, 0, 1)), target_r, band=0.06, strength=0.9)
        # pull lower ankle down slightly toward foot top
        ac2, _ = ankle_cluster(lower, side)
        if ac2.z > fc.z + 0.01:
            # move only ankle-band verts down
            imw = lower.matrix_world.inverted()
            for v in lower.data.vertices:
                w = lower.matrix_world @ v.co
                if side == "L" and w.x < 0.02:
                    continue
                if side == "R" and w.x > -0.02:
                    continue
                if w.z > ac2.z + 0.08:
                    continue
                t = max(0.0, 1.0 - abs(w.z - ac2.z) / 0.08)
                w.z = w.z * (1 - 0.7 * t) + fc.z * (0.7 * t)
                v.co = imw @ w
            lower.data.update()
        smooth_band(lower, fc, Vector((0, 0, 1)), band=0.07, iterations=8)
        smooth_band(foot, fc, Vector((0, 0, 1)), band=0.06, iterations=8)
        boolean_remesh_project(lower, foot, fc, Vector((0, 0, 1)), voxel=0.008, band=0.06)

    # Ground feet again
    for n in ("Body_Foot_L", "Body_Foot_R"):
        fmin, _, _ = world_bounds(parts[n])
        translate(parts[n], Vector((0, 0, -fmin.z)))

    for p in parts.values():
        for poly in p.data.polygons:
            poly.use_smooth = True

    # Rebind
    for o in parts.values():
        reparent_keep(o, arm)

    mins = Vector((1e9,) * 3)
    maxs = Vector((-1e9,) * 3)
    for o in parts.values():
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            mins = Vector(tuple(min(a, b) for a, b in zip(mins, w)))
            maxs = Vector(tuple(max(a, b) for a, b in zip(maxs, w)))
    print(f"FINAL H={maxs.z - mins.z:.3f} Z={mins.z:.3f}..{maxs.z:.3f}")
    if maxs.z - mins.z < 1.0:
        raise RuntimeError("collapsed")

    # Render QA
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1280
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    if not any(o.type == "LIGHT" for o in bpy.data.objects):
        bpy.ops.object.light_add(type="AREA", location=(1.6, -2, 2.4))
        bpy.context.active_object.data.energy = 90
    cam = bpy.data.objects.get("QA_Camera")
    if not cam:
        cd = bpy.data.cameras.new("QA_Camera")
        cam = bpy.data.objects.new("QA_Camera", cd)
        scene.collection.objects.link(cam)
    scene.camera = cam
    c = Vector((0, (mins.y + maxs.y) * 0.5, (mins.z + maxs.z) * 0.52))
    h = maxs.z - mins.z
    for name, off in {
        "front": Vector((0, -1, 0.12)),
        "back": Vector((0, 1, 0.12)),
        "side": Vector((1, 0, 0.08)),
        "three_quarter": Vector((0.75, -1, 0.18)),
    }.items():
        cam.location = c + off.normalized() * max(h * 1.55, 1.6)
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = 50
        scene.render.filepath = os.path.join(SHOT, f"assembled_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("Rendered", name)
    for name, cc, off in (
        ("neck", Vector((0, c.y, world_bounds(head)[0].z)), Vector((0.5, -1, 0.1))),
        ("waist", Vector((0, c.y, world_bounds(upper)[0].z)), Vector((0.5, -1, 0))),
        ("wrist", tip_cluster(upper, "L")[0], Vector((0.7, -0.9, 0.2))),
        ("ankle", foot_top(parts["Body_Foot_L"])[0], Vector((0.6, -1, 0.3))),
    ):
        cam.location = cc + off.normalized() * 0.5
        cam.rotation_euler = (cc - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = 85
        scene.render.filepath = os.path.join(SHOT, f"closeup_{name}.png")
        bpy.ops.render.render(write_still=True)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.object.select_all(action="DESELECT")
    for n in BODY:
        parts[n].select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=GLB, export_format="GLB", use_selection=True, export_apply=False,
        export_yup=True, export_skins=True, export_all_influences=True,
        export_def_bones=True, export_animations=False, export_materials="EXPORT",
    )
    print("DONE")


if __name__ == "__main__":
    main()
