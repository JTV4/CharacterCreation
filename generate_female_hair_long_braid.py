"""
generate_female_hair_long_braid.py
==================================
Stylized LONG BRAID hair molded to BaseFemaleV3 head (Mixamo cm bind space).

Matches the reference card silhouette:
  - Scalp volume with soft center part
  - Face-framing clumps to mid-cheek; ears left open
  - Back weave feeding a long 3-strand braid down the spine
  - Hair-tie + tip tuft

Skinned 100% to mixamorig:Head. UV-unwrapped for Meshy texturing.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_female_hair_long_braid.py
"""

from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
BODY_GLB = os.path.join(ROOT, "viewer/public/models/BaseFemaleV3.glb")
OUT_DIR = os.path.join(ROOT, "viewer/public/equipment/Female/Hair")
OUT_GLB = os.path.join(OUT_DIR, "HairLongBraidV1.glb")

# Head local cm landmarks (BaseFemaleV3)
CROWN = Vector((-0.18, 175.0, -2.34))
NAPE = Vector((0.0, 152.0, -10.5))
EAR_L_X, EAR_R_X = -9.53, 9.53
FACE_Z_CUT = 3.0
OFFSET_CM = 0.85

# Braid path (bind Y-up, face = +Z, back = −Z)
# Upper torso back surface reaches ~z=-13.5 at mid-back — keep braid
# fully behind it (center + radius clearance).
# Braid starts high on the occipital so it merges into the scalp (no floating gap).
BRAID_START = Vector((0.0, 158.5, -12.8))
BRAID_END = Vector((0.0, 136.0, -18.5))  # shorter; hangs clear of upper back
BRAID_RADIUS = 2.0
BRAID_SEGMENTS = 10
BRAID_RADIAL = 10


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
    """BVH tree in local mesh space for nearest-surface queries."""
    import mathutils.bvhtree

    bm = bmesh.new()
    bm.from_mesh(head_obj.data)
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    bvh = mathutils.bvhtree.BVHTree.FromBMesh(bm, epsilon=0.0)
    # Keep a copy of face normals via a temp mesh for later
    bm.free()
    return bvh, head_obj.data


def _nearest_on_head(bvh, me, point: Vector):
    """Return (location, normal) of nearest head surface point."""
    loc, normal, idx, dist = bvh.find_nearest(point)
    if loc is None:
        return None, None, None
    # Prefer face normal from mesh if available
    if idx is not None and 0 <= idx < len(me.polygons):
        normal = me.polygons[idx].normal.copy()
    if normal is None or normal.length < 1e-8:
        normal = Vector((0, 1, 0))
    else:
        normal = normal.normalized()
    return Vector(loc), normal, dist


def _hairline_z(y: float, x: float) -> float:
    """
    Continuous hairline in +Z (face). Higher = more forehead coverage.
    Head face max z ≈ 11 — keep fringe near that on the upper brow.
    """
    temple = abs(x) / 9.5
    # Aggressive forward hairline (was ~8.6 — still too much bare brow)
    forehead = 10.4 - 1.5 * temple  # center ~10.4, temples ~8.9
    # Start covering from mid-forehead upward
    t = max(0.0, min(1.0, (y - 160.0) / 10.0))
    return -0.5 + t * (forehead + 0.5)


def build_scalp_from_head(head_obj) -> bmesh.types.BMesh:
    """
    Continuous scalp shell: parametric grid projected onto the head surface
    (+ offset). No face-deletion holes — that was the crack source.
    Ears stay visible by tucking sides back, not punching gaps.
    """
    bvh, me = _build_head_bvh(head_obj)

    # Bias seed ellipsoid slightly forward so forehead gets denser coverage
    cx, cy, cz = 0.0, 162.0, 1.5
    rx, ry, rz = 10.2, 14.0, 12.5

    nu, nv = 36, 20  # azimuth × polar — dense enough to look solid
    # polar: 0 = crown, v_max covers down toward nape (not full sphere)
    v_max = 0.58

    bm = bmesh.new()
    grid = []  # grid[iv][iu] -> BMVert | None

    for iv in range(nv + 1):
        v = (iv / nv) * v_max
        row = []
        for iu in range(nu):
            u = iu / nu
            theta = u * math.tau
            phi = v * math.pi
            # Seed on ellipsoid around head
            seed = Vector(
                (
                    cx + rx * math.sin(phi) * math.cos(theta),
                    cy + ry * math.cos(phi),
                    cz + rz * math.sin(phi) * math.sin(theta),
                )
            )
            loc, normal, dist = _nearest_on_head(bvh, me, seed)
            if loc is None:
                row.append(None)
                continue

            # Reject face region — keep continuous hairline instead of holes
            hl_z = _hairline_z(loc.y, loc.x)
            if loc.z > hl_z + 0.35:
                # Still keep a vertex but pull it back to hairline so the
                # grid stays watertight (no deleted cells → no cracks).
                pull = loc.z - hl_z
                loc = Vector((loc.x, loc.y, hl_z))
                # Prefer back-facing normal
                normal = Vector((normal.x, normal.y, min(normal.z, 0.0)))
                if normal.length < 1e-6:
                    normal = Vector((0, 0, -1))
                else:
                    normal = normal.normalized()

            # Tuck behind ears (no holes): push inward/back around ear band
            if abs(loc.x) > 6.5 and 157.0 < loc.y < 168.0 and -7.0 < loc.z < 3.0:
                loc = Vector(
                    (
                        math.copysign(min(abs(loc.x), 7.2), loc.x),
                        loc.y,
                        min(loc.z, -2.5),
                    )
                )

            # Stylized offset + crown loft + soft center part
            face_amt = max(0.0, min(1.0, (loc.z + 2.0) / 8.0))
            off = OFFSET_CM * (1.0 - 0.35 * face_amt)
            crown = max(0.0, (loc.y - 165.0) / 10.0)
            loft = 2.0 * crown * crown
            part = 0.0
            if loc.y > 168.0 and abs(loc.x) < 3.5:
                part = -0.45 * (1.0 - abs(loc.x) / 3.5)

            p = loc + normal * (off + loft) + Vector((0.0, part * 0.25, part * 0.15))

            # Mild side volume behind ears
            if abs(p.x) > 5.0 and p.z < -1.0 and p.y > 158.0:
                p.x += math.copysign(0.5, p.x)
                p.z -= 0.35

            row.append(bm.verts.new(p))
        grid.append(row)

    bm.verts.ensure_lookup_table()

    # Build continuous quads — skip only if a corner is missing
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

    # Crown cap fan
    top_seed = Vector((cx, cy + ry + 1.0, cz))
    loc, normal, _ = _nearest_on_head(bvh, me, top_seed)
    if loc is None:
        loc = CROWN.copy()
        normal = Vector((0, 1, 0))
    top = bm.verts.new(loc + normal * (OFFSET_CM + 2.2))
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

    # One Laplacian smooth pass to erase any projection noise (keeps continuity)
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
        v.co = coords[v].lerp(acc / n, 0.45)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    print(f"  Scalp faces={faces} verts={len(bm.verts)} (continuous shell)")
    return bm


def add_face_frame_clumps(bm: bmesh.types.BMesh):
    """Two stylized cheek-length strands — roots buried in scalp, both ends capped."""
    for side in (-1.0, 1.0):
        pts = [
            # Start inside the scalp volume (not poking above crown)
            Vector((side * 3.2, 170.5, 7.5)),
            Vector((side * 4.8, 168.0, 8.2)),
            Vector((side * 5.5, 163.5, 6.5)),
            Vector((side * 5.0, 159.0, 5.0)),
        ]
        _add_tube_along(
            bm, pts, radius=1.2, radial=7, tip_scale=0.5, root_scale=0.15, cap_root=True
        )


def add_side_locks(bm: bmesh.types.BMesh):
    """Short side locks tucked near ears — capped, roots buried."""
    for side in (-1.0, 1.0):
        pts = [
            Vector((side * 6.8, 166.5, -2.5)),
            Vector((side * 7.5, 163.0, -3.5)),
            Vector((side * 7.0, 159.0, -5.0)),
            Vector((side * 5.8, 155.5, -6.0)),
        ]
        _add_tube_along(
            bm, pts, radius=0.95, radial=6, tip_scale=0.45, root_scale=0.2, cap_root=True
        )


def add_back_weave(bm: bmesh.types.BMesh):
    """V-shaped back clumps feeding into the braid — merge toward nape."""
    tiers = [
        (168.0, -10.0, 5.0, 1.35),
        (163.5, -11.0, 4.0, 1.4),
        (159.5, -12.0, 2.8, 1.5),
    ]
    for y, zb, hw, r in tiers:
        for side in (-1.0, 1.0):
            pts = [
                Vector((side * hw, y + 1.5, zb + 1.0)),
                Vector((side * hw * 0.45, y - 0.5, zb - 0.3)),
                # Converge into braid root
                Vector((side * 0.6, 158.0, -12.2)),
            ]
            _add_tube_along(
                bm, pts, radius=r, radial=6, tip_scale=0.85, root_scale=0.35, cap_root=True
            )


def add_nape_gather(bm: bmesh.types.BMesh):
    """Thick gather that seals scalp → braid (closes the floating gap)."""
    pts = [
        Vector((0.0, 164.0, -10.0)),   # on occipital scalp
        Vector((0.0, 161.0, -11.5)),
        Vector((0.0, 158.5, -12.8)),   # braid start
        Vector((0.0, 156.0, -13.8)),   # overlaps first braid segments
    ]
    _add_tube_along(
        bm, pts, radius=3.2, radial=12, tip_scale=0.75, root_scale=0.9, cap_root=True
    )
    # Extra fill shell slightly larger
    _add_tube_along(
        bm,
        [
            Vector((0.0, 162.5, -9.5)),
            Vector((0.0, 159.0, -12.0)),
            Vector((0.0, 156.5, -13.5)),
        ],
        radius=2.6,
        radial=10,
        tip_scale=0.8,
        root_scale=0.7,
        cap_root=True,
    )


def _bezier_quad(p0, p1, p2, t):
    u = 1.0 - t
    return u * u * p0 + 2 * u * t * p1 + t * t * p2


def _add_tube_along(
    bm,
    pts,
    radius=1.0,
    radial=8,
    tip_scale=0.4,
    root_scale=0.35,
    cap_root=True,
):
    """Tapered tube along a polyline. Both ends capped so no hollow openings."""
    if len(pts) < 2:
        return
    path = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        steps = 4
        for s in range(steps):
            path.append(a.lerp(b, s / steps))
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
        # Taper root → mid → tip
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

    # Cap tip
    tip_dir = (path[-1] - path[-2]).normalized()
    tip = bm.verts.new(path[-1] + tip_dir * (radius * tip_scale * 0.5))
    for k in range(radial):
        k2 = (k + 1) % radial
        try:
            bm.faces.new((rings[-1][k], rings[-1][k2], tip))
        except ValueError:
            pass

    # Cap root (fixes hollow cylinders poking out of the scalp)
    if cap_root:
        root_dir = (path[0] - path[1]).normalized()
        root = bm.verts.new(path[0] + root_dir * (radius * root_scale * 0.4))
        for k in range(radial):
            k2 = (k + 1) % radial
            try:
                bm.faces.new((rings[0][k2], rings[0][k], root))
            except ValueError:
                pass


def add_long_braid(bm: bmesh.types.BMesh):
    """
    Stylized 3-strand braid: overlapping bulbous segments along a curve,
    then a hair-tie ring and tip tuft (matches reference back view).
    """
    start = BRAID_START
    end = BRAID_END
    # Curve braid away from the back (more −Z) so it never clips the torso
    mid = Vector((0.1, (start.y + end.y) * 0.5, min(start.z, end.z) - 1.5))

    centers = []
    for i in range(BRAID_SEGMENTS + 1):
        t = i / BRAID_SEGMENTS
        c = _bezier_quad(start, mid, end, t)
        centers.append(c)

    # Three intertwining strand offsets
    strand_phase = [0.0, math.tau / 3, 2 * math.tau / 3]
    strand_r = BRAID_RADIUS * 0.55
    bulb_r = BRAID_RADIUS * 0.72

    for si, phase in enumerate(strand_phase):
        pts = []
        for i, c in enumerate(centers):
            t = i / BRAID_SEGMENTS
            tang = (centers[min(i + 1, len(centers) - 1)] - centers[max(i - 1, 0)]).normalized()
            up = Vector((0, 0, 1))
            if abs(tang.dot(up)) > 0.85:
                up = Vector((1, 0, 0))
            side = tang.cross(up).normalized()
            norm = side.cross(tang).normalized()
            ang = phase + t * math.tau * 2.2
            offset = (math.cos(ang) * side + math.sin(ang) * norm) * strand_r
            bulge = 1.0 + 0.18 * math.sin(t * math.pi * BRAID_SEGMENTS)
            pts.append(c + offset * bulge)
        _add_tube_along(
            bm,
            pts,
            radius=bulb_r * 0.85,
            radial=BRAID_RADIAL,
            tip_scale=0.65,
            root_scale=0.55,
            cap_root=True,
        )

    # Outer braid envelope
    env_pts = list(centers)
    _add_tube_along(
        bm,
        env_pts,
        radius=BRAID_RADIUS * 0.95,
        radial=12,
        tip_scale=0.55,
        root_scale=0.7,
        cap_root=True,
    )

    # Hair tie near tip
    tie_t = 0.88
    tie_c = _bezier_quad(start, mid, end, tie_t)
    tang = (end - start).normalized()
    _add_torus(bm, tie_c, tang, major=BRAID_RADIUS * 0.95, minor=0.55, major_seg=12, minor_seg=6)

    # Tip tuft below tie
    tip_start = _bezier_quad(start, mid, end, 0.92)
    tip_end = end + Vector((0.1, -3.5, -0.5))
    _add_tube_along(
        bm,
        [tip_start, tip_start.lerp(tip_end, 0.5), tip_end],
        radius=1.6,
        radial=8,
        tip_scale=0.2,
        root_scale=0.7,
        cap_root=True,
    )


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
        # Local frame for tube
        radial_dir = (ring_c - center).normalized()
        tang = axis  # approximate
        ring = []
        for j in range(minor_seg):
            b = j / minor_seg * math.tau
            # Circle in plane of radial_dir × axis
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


def merge_and_finish(bm: bmesh.types.BMesh) -> bpy.types.Object:
    # Remove doubles / cleanup
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.02)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # Light smooth pass
    bm.normal_update()
    for v in list(bm.verts):
        if not v.link_edges:
            continue
        acc = Vector(v.co)
        n = 1
        for e in v.link_edges:
            acc += e.other_vert(v).co
            n += 1
        # Keep braid clumps sharper than scalp
        mix = 0.25 if v.co.y < 152.0 else 0.4
        v.co = v.co.lerp(acc / n, mix * 0.35)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new("HairLongBraidV1")
    bm.to_mesh(me)
    bm.free()

    obj = bpy.data.objects.new("HairLongBraidV1", me)
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

    mat = bpy.data.materials.new("HairLongBraidV1_Placeholder")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        # Medium brown like reference
        bsdf.inputs["Base Color"].default_value = (0.42, 0.28, 0.18, 1.0)
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
    print("generate_female_hair_long_braid.py")
    print("=" * 60)
    clear_scene()
    arm, head_bone, head = load_body()
    print(f"[1/4] Head + armature ({head_bone})")

    bm = build_scalp_from_head(head)
    print("[2/4] Building braid style clumps…")
    add_face_frame_clumps(bm)
    add_side_locks(bm)
    add_back_weave(bm)
    add_nape_gather(bm)
    add_long_braid(bm)

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
