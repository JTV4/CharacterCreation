"""
generate_female_hair_ponytail.py
================================
Stylized PONYTAIL hair molded to BaseFemaleV3 head (Mixamo cm bind space).

Reference card silhouette:
  - Swept-back hairline, open forehead (no fringe curtain)
  - High crown volume with chunky ridges
  - Short temple lock in front of each ear
  - Radial back clumps into a high-back ponytail tie
  - S-curve ponytail with jagged layered tip

Skinned 100% to mixamorig:Head. UV-unwrapped for Meshy texturing.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_female_hair_ponytail.py
"""

from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
BODY_GLB = os.path.join(ROOT, "viewer/public/models/BaseFemaleV3.glb")
OUT_DIR = os.path.join(ROOT, "viewer/public/equipment/Female/Hair")
OUT_GLB = os.path.join(OUT_DIR, "HairPonytailV1.glb")

CROWN = Vector((-0.18, 175.0, -2.34))
OFFSET_CM = 0.95

# High-back ponytail base (crown/occipital) — flush with scalp, not floating.
PONY_BASE = Vector((0.0, 169.5, -11.8))
PONY_MID = Vector((0.3, 161.0, -18.0))   # S-curve out, clear of torso
PONY_END = Vector((0.0, 147.0, -17.0))
PONY_RADIUS = 2.4


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_body():
    bpy.ops.import_scene.gltf(filepath=BODY_GLB)
    bpy.context.view_layer.update()
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    head = next(
        o for o in bpy.data.objects if o.type == "MESH" and "head" in o.name.lower()
    )
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o is not head:
            bpy.data.objects.remove(o, do_unlink=True)
    head_bone = next(
        b.name
        for b in arm.data.bones
        if b.name in ("mixamorig:Head", "mixamorigHead", "Head", "head")
    )
    return arm, head_bone, head


def skin_to_head(mesh_obj, arm, head_name):
    mesh_obj.vertex_groups.clear()
    idxs = list(range(len(mesh_obj.data.vertices)))
    for bone_name in [b.name for b in arm.data.bones]:
        vg = mesh_obj.vertex_groups.new(name=bone_name)
        vg.add(idxs, 1.0 if bone_name == head_name else 0.0, "REPLACE")
    mesh_obj.parent = arm
    for m in list(mesh_obj.modifiers):
        mesh_obj.modifiers.remove(m)
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm


def export_glb(meshes, arm, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
    )
    print(f"  → {path}")


def _build_head_bvh(head_obj):
    import mathutils.bvhtree

    bm = bmesh.new()
    bm.from_mesh(head_obj.data)
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    bvh = mathutils.bvhtree.BVHTree.FromBMesh(bm, epsilon=0.0)
    bm.free()
    return bvh, head_obj.data


def _nearest_on_head(bvh, me, point: Vector):
    loc, normal, idx, dist = bvh.find_nearest(point)
    if loc is None:
        return None, None, None
    if idx is not None and 0 <= idx < len(me.polygons):
        normal = me.polygons[idx].normal.copy()
    if normal is None or normal.length < 1e-8:
        normal = Vector((0, 1, 0))
    else:
        normal = normal.normalized()
    return Vector(loc), normal, dist


def _hairline_z(y: float, x: float) -> float:
    """
    Forward hairline that covers the forehead (above brow).
    Swept style — no hanging fringe curtain — but not parked at the crown.
    """
    temple = abs(x) / 9.5
    # Aggressive forward coverage (head face max z ≈ 11)
    forehead = 10.2 - 1.2 * temple  # center ~10.2, temples ~9.0
    t = max(0.0, min(1.0, (y - 161.0) / 11.0))
    return -0.5 + t * (forehead + 0.5)


def build_scalp_from_head(head_obj) -> bmesh.types.BMesh:
    """Continuous scalp shell with forward hairline + high crown volume."""
    bvh, me = _build_head_bvh(head_obj)

    # Bias seed forward so forehead/temples get hits
    cx, cy, cz = 0.0, 163.0, 2.0
    rx, ry, rz = 10.4, 14.5, 13.0
    nu, nv = 36, 20
    v_max = 0.55

    bm = bmesh.new()
    grid = []

    for iv in range(nv + 1):
        v = (iv / nv) * v_max
        row = []
        for iu in range(nu):
            u = iu / nu
            theta = u * math.tau
            phi = v * math.pi
            seed = Vector(
                (
                    cx + rx * math.sin(phi) * math.cos(theta),
                    cy + ry * math.cos(phi),
                    cz + rz * math.sin(phi) * math.sin(theta),
                )
            )
            loc, normal, _ = _nearest_on_head(bvh, me, seed)
            if loc is None:
                row.append(None)
                continue

            hl_z = _hairline_z(loc.y, loc.x)

            # Skull surface on the brow is only ~z 6–8. Push the hairline
            # FORWARD onto the forehead so it isn't stuck at the crown.
            if loc.y > 164.0 and loc.z < hl_z:
                push = hl_z - loc.z
                loc = Vector(
                    (
                        loc.x,
                        loc.y - 0.12 * push,  # slight drop toward brow
                        hl_z,
                    )
                )
                # Prefer a face-outward normal once we've left the skull
                normal = Vector((normal.x * 0.4, normal.y * 0.3, 0.85)).normalized()
            elif loc.z > hl_z + 0.4:
                # Past hairline into face — pull back to the line
                loc = Vector((loc.x, loc.y, hl_z))
                normal = Vector((normal.x, normal.y, min(normal.z, 0.15)))
                if normal.length < 1e-6:
                    normal = Vector((0, 0, 1))
                else:
                    normal = normal.normalized()

            # Soft ear open: only pull the ear bowl itself, NOT the temple/front
            if (
                abs(loc.x) > 7.5
                and 159.0 < loc.y < 166.0
                and -6.0 < loc.z < -1.0
            ):
                loc = Vector((loc.x, loc.y, min(loc.z, -2.0)))

            # High crown loft
            face_amt = max(0.0, min(1.0, (loc.z + 2.0) / 10.0))
            off = OFFSET_CM * (1.0 - 0.25 * face_amt)
            crown = max(0.0, (loc.y - 164.0) / 11.0)
            loft = 3.0 * crown * crown
            ridge = 0.35 * math.sin(u * math.tau * 4.0) * crown

            # Crown-only back bias — never drag the hairline rearward
            back_bias = Vector((0.0, 0.08 * crown, -0.15 * crown * (1.0 - face_amt)))

            p = loc + normal * (off + loft + ridge) + back_bias

            if abs(p.x) > 5.5 and p.z < -2.0 and p.y > 158.0:
                p.x += math.copysign(0.35, p.x)

            row.append(bm.verts.new(p))
        grid.append(row)

    bm.verts.ensure_lookup_table()
    faces = 0
    for iv in range(nv):
        for iu in range(nu):
            iu2 = (iu + 1) % nu
            v00, v10 = grid[iv][iu], grid[iv][iu2]
            v01, v11 = grid[iv + 1][iu], grid[iv + 1][iu2]
            if None in (v00, v10, v01, v11):
                continue
            try:
                bm.faces.new((v00, v10, v11, v01))
                faces += 1
            except ValueError:
                pass

    top_seed = Vector((cx, cy + ry + 1.0, cz - 1.0))
    loc, normal, _ = _nearest_on_head(bvh, me, top_seed)
    if loc is None:
        loc, normal = CROWN.copy(), Vector((0, 1, 0))
    top = bm.verts.new(loc + normal * (OFFSET_CM + 3.4) + Vector((0, 0.2, -0.8)))
    for iu in range(nu):
        iu2 = (iu + 1) % nu
        a, b = grid[0][iu], grid[0][iu2]
        if a is None or b is None:
            continue
        try:
            bm.faces.new((top, a, b))
            faces += 1
        except ValueError:
            pass

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    coords = {v: v.co.copy() for v in bm.verts}
    for v in bm.verts:
        if not v.link_edges:
            continue
        acc = coords[v].copy()
        n = 1
        for e in v.link_edges:
            acc += coords[e.other_vert(v)]
            n += 1
        v.co = coords[v].lerp(acc / n, 0.4)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    print(f"  Scalp faces={faces} verts={len(bm.verts)} (continuous shell)")
    return bm


def _add_tube_along(
    bm,
    pts,
    radius=1.0,
    radial=8,
    tip_scale=0.4,
    root_scale=0.35,
    cap_root=True,
):
    if len(pts) < 2:
        return
    path = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        for s in range(4):
            path.append(a.lerp(b, s / 4))
    path.append(pts[-1])

    rings = []
    for i, p in enumerate(path):
        t = i / max(1, len(path) - 1)
        if i == 0:
            tang = (path[1] - path[0]).normalized()
        elif i == len(path) - 1:
            tang = (path[-1] - path[-2]).normalized()
        else:
            tang = (path[i + 1] - path[i - 1]).normalized()
        up = Vector((0, 1, 0))
        if abs(tang.dot(up)) > 0.9:
            up = Vector((1, 0, 0))
        binorm = tang.cross(up).normalized()
        norm = binorm.cross(tang).normalized()
        if t < 0.35:
            r = radius * (root_scale + (1.0 - root_scale) * (t / 0.35))
        else:
            tt = (t - 0.35) / 0.65
            r = radius * (1.0 - (1.0 - tip_scale) * (tt ** 1.15))
        ring = []
        for k in range(radial):
            ang = k / radial * math.tau
            offset = (math.cos(ang) * binorm + math.sin(ang) * norm) * r
            ring.append(bm.verts.new(p + offset))
        rings.append(ring)

    bm.verts.ensure_lookup_table()
    for i in range(len(rings) - 1):
        for k in range(radial):
            k2 = (k + 1) % radial
            try:
                bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
            except ValueError:
                pass

    tip_dir = (path[-1] - path[-2]).normalized()
    tip = bm.verts.new(path[-1] + tip_dir * (radius * tip_scale * 0.5))
    for k in range(radial):
        k2 = (k + 1) % radial
        try:
            bm.faces.new((rings[-1][k], rings[-1][k2], tip))
        except ValueError:
            pass

    if cap_root:
        root_dir = (path[0] - path[1]).normalized()
        root = bm.verts.new(path[0] + root_dir * (radius * root_scale * 0.4))
        for k in range(radial):
            k2 = (k + 1) % radial
            try:
                bm.faces.new((rings[0][k2], rings[0][k], root))
            except ValueError:
                pass


def _add_torus(bm, center, axis, major, minor, major_seg=12, minor_seg=6):
    axis = axis.normalized()
    up = Vector((0, 1, 0))
    if abs(axis.dot(up)) > 0.9:
        up = Vector((1, 0, 0))
    binorm = axis.cross(up).normalized()
    norm = binorm.cross(axis).normalized()

    rings = []
    for i in range(major_seg):
        a = i / major_seg * math.tau
        ring_c = center + (math.cos(a) * binorm + math.sin(a) * norm) * major
        radial_dir = (ring_c - center).normalized()
        ring = []
        for j in range(minor_seg):
            b = j / minor_seg * math.tau
            offset = (math.cos(b) * radial_dir + math.sin(b) * axis) * minor
            ring.append(bm.verts.new(ring_c + offset))
        rings.append(ring)

    bm.verts.ensure_lookup_table()
    for i in range(major_seg):
        i2 = (i + 1) % major_seg
        for j in range(minor_seg):
            j2 = (j + 1) % minor_seg
            try:
                bm.faces.new((rings[i][j], rings[i][j2], rings[i2][j2], rings[i2][j]))
            except ValueError:
                pass


def _bezier_quad(p0, p1, p2, t):
    u = 1.0 - t
    return u * u * p0 + 2 * u * t * p1 + t * t * p2


def add_temple_locks(bm: bmesh.types.BMesh):
    """Short pointed lock in front of each ear — roots on forward hairline."""
    for side in (-1.0, 1.0):
        pts = [
            Vector((side * 4.5, 171.0, 7.5)),
            Vector((side * 5.8, 168.0, 5.5)),
            Vector((side * 6.8, 165.0, 2.0)),
            Vector((side * 7.0, 162.5, -0.5)),
        ]
        _add_tube_along(
            bm, pts, radius=1.1, radial=7, tip_scale=0.25, root_scale=0.2, cap_root=True
        )


def add_radial_to_pony(bm: bmesh.types.BMesh):
    """Sunburst clumps on back of head feeding into pony base."""
    n = 8
    for i in range(n):
        t = i / (n - 1)
        ang = -0.95 + 1.9 * t  # fan across back
        start = Vector(
            (
                math.sin(ang) * 6.5,
                172.0 + 1.5 * math.cos(ang * 0.5),
                -6.0 - 3.5 * abs(math.cos(ang)),
            )
        )
        mid = Vector(
            (
                math.sin(ang) * 3.0,
                170.5,
                -9.5,
            )
        )
        end = PONY_BASE + Vector((math.sin(ang) * 0.4, 0.2, 0.3))
        _add_tube_along(
            bm,
            [start, mid, end],
            radius=1.25,
            radial=6,
            tip_scale=0.7,
            root_scale=0.4,
            cap_root=True,
        )


def add_ponytail(bm: bmesh.types.BMesh):
    """Thick S-curve ponytail with layered jagged tip + hair tie."""
    # Gather shell at base so pony is flush with scalp
    _add_tube_along(
        bm,
        [
            PONY_BASE + Vector((0, 1.5, 1.5)),
            PONY_BASE,
            PONY_BASE + Vector((0, -1.2, -1.0)),
        ],
        radius=3.4,
        radial=12,
        tip_scale=0.85,
        root_scale=0.75,
        cap_root=True,
    )

    # Main pony body (S-curve)
    segs = 12
    centers = []
    for i in range(segs + 1):
        t = i / segs
        centers.append(_bezier_quad(PONY_BASE, PONY_MID, PONY_END, t))

    # Layered strands for chunky look
    for phase, r_mul, tip in (
        (0.0, 1.0, 0.45),
        (2.1, 0.78, 0.3),
        (-2.1, 0.78, 0.3),
    ):
        pts = []
        for i, c in enumerate(centers):
            t = i / segs
            tang = (
                centers[min(i + 1, len(centers) - 1)] - centers[max(i - 1, 0)]
            ).normalized()
            up = Vector((1, 0, 0))
            side = tang.cross(up).normalized()
            if side.length < 1e-6:
                side = Vector((1, 0, 0))
            norm = side.cross(tang).normalized()
            wobble = (math.cos(phase + t * 3.0) * side + math.sin(phase + t * 2.0) * norm) * (
                0.55 * r_mul
            )
            pts.append(c + wobble)
        _add_tube_along(
            bm,
            pts,
            radius=PONY_RADIUS * r_mul,
            radial=10,
            tip_scale=tip,
            root_scale=0.65,
            cap_root=True,
        )

    # Outer silhouette envelope
    _add_tube_along(
        bm,
        centers,
        radius=PONY_RADIUS * 1.05,
        radial=12,
        tip_scale=0.4,
        root_scale=0.8,
        cap_root=True,
    )

    # Hair tie at base
    tie_c = PONY_BASE + Vector((0.0, -0.4, -0.6))
    tang = (PONY_MID - PONY_BASE).normalized()
    _add_torus(bm, tie_c, tang, major=2.5, minor=0.55, major_seg=14, minor_seg=6)

    # Jagged tip tufts (V-shaped layered points from ref)
    tip_base = _bezier_quad(PONY_BASE, PONY_MID, PONY_END, 0.82)
    for dx, dz, drop in (
        (0.0, 0.0, 0.0),
        (-1.4, 0.4, 1.2),
        (1.4, 0.4, 1.2),
        (-0.7, -0.3, 2.2),
        (0.7, -0.3, 2.2),
        (0.0, 0.5, 3.0),
    ):
        tip = tip_base + Vector((dx, -4.5 - drop, dz - 0.5))
        _add_tube_along(
            bm,
            [tip_base + Vector((dx * 0.3, -0.5, dz * 0.2)), tip],
            radius=1.1,
            radial=6,
            tip_scale=0.12,
            root_scale=0.55,
            cap_root=True,
        )

    # Keep hanging pony clear of torso back (~z=-13.5)
    for v in bm.verts:
        if v.co.y < 165.0 and v.co.z > -14.8:
            v.co.z = -14.8 - 0.3 * max(0.0, (165.0 - v.co.y) / 20.0)


def merge_and_finish(bm: bmesh.types.BMesh) -> bpy.types.Object:
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.02)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    bm.normal_update()
    for v in list(bm.verts):
        if not v.link_edges:
            continue
        acc = Vector(v.co)
        n = 1
        for e in v.link_edges:
            acc += e.other_vert(v).co
            n += 1
        mix = 0.2 if v.co.y < 160.0 else 0.35
        v.co = v.co.lerp(acc / n, mix * 0.35)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new("HairPonytailV1")
    bm.to_mesh(me)
    bm.free()

    obj = bpy.data.objects.new("HairPonytailV1", me)
    bpy.context.collection.objects.link(obj)
    for poly in me.polygons:
        poly.use_smooth = True

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    mat = bpy.data.materials.new("HairPonytailV1_Placeholder")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.40, 0.26, 0.16, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
    me.materials.append(mat)
    return obj


def fit_report(hair, head):
    def aabb(obj):
        coords = [v.co for v in obj.data.vertices]
        return (
            min(c.x for c in coords),
            max(c.x for c in coords),
            min(c.y for c in coords),
            max(c.y for c in coords),
            min(c.z for c in coords),
            max(c.z for c in coords),
            len(coords),
        )

    h = aabb(hair)
    d = aabb(head)
    print(
        f"  Hair cm: x=[{h[0]:.1f},{h[1]:.1f}] y=[{h[2]:.1f},{h[3]:.1f}] "
        f"z=[{h[4]:.1f},{h[5]:.1f}] v={h[6]}"
    )
    print(
        f"  Head cm: x=[{d[0]:.1f},{d[1]:.1f}] y=[{d[2]:.1f},{d[3]:.1f}] "
        f"z=[{d[4]:.1f},{d[5]:.1f}] v={d[6]}"
    )


def main():
    print("=" * 60)
    print("generate_female_hair_ponytail.py")
    print("=" * 60)
    clear_scene()
    arm, head_bone, head = load_body()
    print(f"[1/4] Head + armature ({head_bone})")

    bm = build_scalp_from_head(head)
    print("[2/4] Building ponytail style…")
    add_temple_locks(bm)
    add_radial_to_pony(bm)
    add_ponytail(bm)

    hair = merge_and_finish(bm)
    print("[3/4] Mesh finished")
    fit_report(hair, head)

    bpy.data.objects.remove(head, do_unlink=True)
    skin_to_head(hair, arm, head_bone)
    export_glb([hair], arm, OUT_GLB)
    print("[4/4] Exported")
    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
