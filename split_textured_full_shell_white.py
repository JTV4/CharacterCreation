"""
split_textured_full_shell_white.py
==================================
Cut a Meshy-textured full-body Shell V1 join back into the 12 Female V2
Shell V1 region pieces.

Inputs:
  Desktop/.../White/full_female_shell_textured.glb   (Meshy Text-to-Texture)
  Desktop/.../White/full_female_shell.glb             (pre-Meshy join, optional
                                                      calibration reference)
  viewer/public/equipment/Female/ShellV1/shell_v1_*.glb

Method:
  1. Remap textured mesh into Shell V1 / body cm space (48-combo fit to the
     joined pre-Meshy full shell, falling back to union of Shell V1 pieces).
  2. Label every textured face by nearest Shell V1 piece face-centroid.
  3. Split into 12 meshes (materials/UVs preserved).
  4. KD-transfer Mixamo weights from the matching Shell V1 piece.
  5. Parent to BaseFemaleV2 armature and export.

Outputs:
  viewer/public/equipment/Female/SkinTextures/White/shell_v1_*.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python split_textured_full_shell_white.py
"""

from __future__ import annotations

import itertools
import os
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

sys.stdout.reconfigure(line_buffering=True)

SRC_DIR = os.path.abspath(
    "/Users/stephenvillavaso/Desktop/Shells/SkinnedShells/Female/White"
)
TEXTURED = os.path.join(SRC_DIR, "full_female_shell_textured.glb")
FULL_REF = os.path.join(SRC_DIR, "full_female_shell.glb")
SHELL_DIR = os.path.abspath("viewer/public/equipment/Female/ShellV1")
BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
OUT_DIR = os.path.abspath("viewer/public/equipment/Female/SkinTextures/White")

SHELL_PIECES = [
    "shell_v1_head.glb",
    "shell_v1_upper_torso.glb",
    "shell_v1_lower_torso.glb",
    "shell_v1_arm_upper.glb",
    "shell_v1_arm_lower.glb",
    "shell_v1_hands.glb",
    "shell_v1_leg_upper.glb",
    "shell_v1_leg_thigh.glb",
    "shell_v1_leg_knee.glb",
    "shell_v1_leg_shin.glb",
    "shell_v1_leg_ankle.glb",
    "shell_v1_foot.glb",
]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER = 1.5
MAX_INFLUENCES = 4


def suppress():
    dn = open(os.devnull, "w")
    s = os.dup(1)
    os.dup2(dn.fileno(), 1)
    return s, dn


def restore(s, dn):
    os.dup2(s, 1)
    os.close(s)
    dn.close()


def import_largest_mesh(path, label=""):
    pre = {o.name for o in bpy.data.objects}
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    restore(s, dn)
    new = [o for o in bpy.data.objects if o.name not in pre]
    meshes = [
        o for o in new
        if o.type == "MESH" and "Icosphere" not in o.name
    ]
    if not meshes:
        raise RuntimeError(f"No mesh in {path}")
    meshes.sort(key=lambda m: len(m.data.vertices), reverse=True)
    chosen = meshes[0]
    print(
        f"  [{label}] {chosen.name}: "
        f"{len(chosen.data.vertices)}v / {len(chosen.data.polygons)}f"
    )
    # Drop extras from this import
    for o in new:
        if o != chosen and o.type == "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    return chosen


def local_bounds(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return (
        Vector((min(xs), min(ys), min(zs))),
        Vector((max(xs), max(ys), max(zs))),
    )


def normalize_mesh(mesh_obj):
    verts = mesh_obj.data.vertices
    if not verts:
        return
    mn, mx = local_bounds(mesh_obj)
    center = (mn + mx) / 2
    half = max((mx - mn).x, (mx - mn).y, (mx - mn).z) / 2
    if half < 1e-6:
        return
    for v in verts:
        v.co = (v.co - center) / half
    mesh_obj.data.update()


def remap_to_target(meshy_mesh, target_verts):
    """48-combo axis remap so meshy matches target vertex cloud."""
    mverts = meshy_mesh.data.vertices
    m_xs = [v.co.x for v in mverts]
    m_ys = [v.co.y for v in mverts]
    m_zs = [v.co.z for v in mverts]
    m_min = Vector((min(m_xs), min(m_ys), min(m_zs)))
    m_max = Vector((max(m_xs), max(m_ys), max(m_zs)))
    m_range = m_max - m_min

    if max(m_range) > 5.0:
        print("  Normalizing textured mesh first (body-scale input)...")
        normalize_mesh(meshy_mesh)
        mverts = meshy_mesh.data.vertices
        m_xs = [v.co.x for v in mverts]
        m_ys = [v.co.y for v in mverts]
        m_zs = [v.co.z for v in mverts]
        m_min = Vector((min(m_xs), min(m_ys), min(m_zs)))
        m_max = Vector((max(m_xs), max(m_ys), max(m_zs)))
        m_range = m_max - m_min

    t_xs = [v.x for v in target_verts]
    t_ys = [v.y for v in target_verts]
    t_zs = [v.z for v in target_verts]
    t_min = Vector((min(t_xs), min(t_ys), min(t_zs)))
    t_max = Vector((max(t_xs), max(t_ys), max(t_zs)))
    t_range = t_max - t_min
    t_center = (t_min + t_max) / 2
    m_center = (m_min + m_max) / 2

    print(
        f"  Target bounds: X=[{t_min.x:.1f},{t_max.x:.1f}] "
        f"Y=[{t_min.y:.1f},{t_max.y:.1f}] Z=[{t_min.z:.1f},{t_max.z:.1f}]"
    )
    print(
        f"  Meshy  bounds: X=[{m_min.x:.3f},{m_max.x:.3f}] "
        f"Y=[{m_min.y:.3f},{m_max.y:.3f}] Z=[{m_min.z:.3f},{m_max.z:.3f}]"
    )

    kd = KDTree(len(target_verts))
    for i, co in enumerate(target_verts):
        kd.insert(co, i)
    kd.balance()

    step = max(1, len(mverts) // 300)
    sample = [mverts[i].co.copy() for i in range(0, len(mverts), step)]
    body_sizes = [t_range.x, t_range.y, t_range.z]
    meshy_sizes = [m_range.x, m_range.y, m_range.z]

    best_score = float("inf")
    best_perm = (0, 1, 2)
    best_signs = (1, 1, 1)

    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            scales = [
                body_sizes[b] / meshy_sizes[perm[b]]
                if meshy_sizes[perm[b]] > 0.001 else 1.0
                for b in range(3)
            ]
            total = 0.0
            for sv in sample:
                new_co = Vector((0, 0, 0))
                for b in range(3):
                    val = (sv[perm[b]] - m_center[perm[b]]) * signs[b]
                    new_co[b] = val * scales[b] + t_center[b]
                _, _, dist = kd.find(new_co)
                total += dist
            if total < best_score:
                best_score = total
                best_perm = perm
                best_signs = signs

    scales = [
        body_sizes[b] / meshy_sizes[best_perm[b]]
        if meshy_sizes[best_perm[b]] > 0.001 else 1.0
        for b in range(3)
    ]
    axis = "XYZ"
    perm_str = "".join(axis[i] for i in best_perm)
    sign_str = "".join("+" if s > 0 else "-" for s in best_signs)
    print(
        f"  Axis map: body[XYZ]<-meshy[{perm_str}] signs:{sign_str} "
        f"scales=[{scales[0]:.2f},{scales[1]:.2f},{scales[2]:.2f}] "
        f"avg_dist={best_score/len(sample):.4f}"
    )

    for v in mverts:
        old = v.co.copy()
        new_co = Vector((0, 0, 0))
        for b in range(3):
            val = (old[best_perm[b]] - m_center[best_perm[b]]) * best_signs[b]
            new_co[b] = val * scales[b] + t_center[b]
        v.co = new_co
    meshy_mesh.data.update()
    mn, mx = local_bounds(meshy_mesh)
    print(
        f"  Remapped: X=[{mn.x:.1f},{mx.x:.1f}] "
        f"Y=[{mn.y:.1f},{mx.y:.1f}] Z=[{mn.z:.1f},{mx.z:.1f}]"
    )


def face_centroids(obj):
    mesh = obj.data
    cents = []
    for poly in mesh.polygons:
        c = Vector((0, 0, 0))
        for vi in poly.vertices:
            c += mesh.vertices[vi].co
        c /= len(poly.vertices)
        cents.append(c)
    return cents


def build_region_face_index():
    """KD of (face_centroid -> region_name) from Shell V1 pieces."""
    region_centroids = []
    region_labels = []
    region_meshes = {}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    for fname in SHELL_PIECES:
        path = os.path.join(SHELL_DIR, fname)
        region = fname.replace(".glb", "")
        mesh = import_largest_mesh(path, label=region)
        region_meshes[region] = mesh
        for c in face_centroids(mesh):
            region_centroids.append(c)
            region_labels.append(region)

    kd = KDTree(len(region_centroids))
    for i, c in enumerate(region_centroids):
        kd.insert(c, i)
    kd.balance()
    print(
        f"  Region face index: {len(region_centroids)} faces across "
        f"{len(SHELL_PIECES)} pieces"
    )
    return kd, region_labels, region_meshes


def assign_faces(textured, kd, region_labels):
    cents = face_centroids(textured)
    labels = []
    dist_sum = 0.0
    for c in cents:
        _, idx, dist = kd.find(c)
        labels.append(region_labels[idx])
        dist_sum += dist
    # counts
    counts = {}
    for lab in labels:
        counts[lab] = counts.get(lab, 0) + 1
    print(f"  Face assignment avg dist to shell face: {dist_sum/len(labels):.4f}")
    for fname in SHELL_PIECES:
        region = fname.replace(".glb", "")
        print(f"    {region}: {counts.get(region, 0)} faces")
    return labels


def split_by_labels(textured, labels):
    """Return dict region -> new mesh object (materials preserved)."""
    src = textured.data
    # Ensure we're in object mode
    bpy.context.view_layer.objects.active = textured
    bpy.ops.object.mode_set(mode="OBJECT")

    # Group polygon indices by region
    by_region = {}
    for pi, lab in enumerate(labels):
        by_region.setdefault(lab, []).append(pi)

    out = {}
    for region, polys in by_region.items():
        # Build new mesh from selected faces via bmesh
        bm = bmesh.new()
        bm.from_mesh(src)
        bm.faces.ensure_lookup_table()
        keep = set(polys)
        # delete faces not in keep
        to_del = [f for f in bm.faces if f.index not in keep]
        bmesh.ops.delete(bm, geom=to_del, context="FACES")
        # remove loose verts
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")

        new_mesh = bpy.data.meshes.new(region)
        bm.to_mesh(new_mesh)
        bm.free()

        # Copy materials
        for mat in src.materials:
            new_mesh.materials.append(mat)

        obj = bpy.data.objects.new(region, new_mesh)
        bpy.context.collection.objects.link(obj)
        print(
            f"  Split {region}: {len(new_mesh.vertices)}v / "
            f"{len(new_mesh.polygons)}f"
        )
        out[region] = obj
    return out


def transfer_weights(dst_mesh, src_mesh):
    all_positions = []
    all_weights = []
    vg_names = {vg.index: vg.name for vg in src_mesh.vertex_groups}
    for v in src_mesh.data.vertices:
        groups = {}
        for g in v.groups:
            gname = vg_names.get(g.group)
            if gname and g.weight > 0.0001:
                groups[gname] = g.weight
        all_positions.append(v.co.copy())
        all_weights.append(groups)

    if not all_positions:
        raise RuntimeError(f"No weights on {src_mesh.name}")

    kd = KDTree(len(all_positions))
    for i, pos in enumerate(all_positions):
        kd.insert(pos, i)
    kd.balance()

    dst_mesh.vertex_groups.clear()
    for mod in list(dst_mesh.modifiers):
        if mod.type == "ARMATURE":
            dst_mesh.modifiers.remove(mod)

    transferred = 0
    for rv_idx, rv in enumerate(dst_mesh.data.vertices):
        neighbors = kd.find_n(rv.co, WEIGHT_NEIGHBORS)
        inv_weights = []
        for _co, idx, dist in neighbors:
            w = 1.0 / (dist ** WEIGHT_POWER + 1e-8)
            inv_weights.append((idx, w))
        total_inv = sum(w for _, w in inv_weights)
        blended = {}
        for body_idx, inv_w in inv_weights:
            factor = inv_w / total_inv
            for gname, bw in all_weights[body_idx].items():
                blended[gname] = blended.get(gname, 0.0) + bw * factor
        top = sorted(blended.items(), key=lambda x: x[1], reverse=True)[:MAX_INFLUENCES]
        wtotal = sum(w for _, w in top)
        if wtotal > 0:
            for name, w in top:
                nw = w / wtotal
                if nw > 0.0001:
                    if name not in [vg.name for vg in dst_mesh.vertex_groups]:
                        dst_mesh.vertex_groups.new(name=name)
                    dst_mesh.vertex_groups[name].add([rv_idx], nw, "REPLACE")
                    transferred += 1
    print(
        f"    weights: {transferred} entries, "
        f"{len(dst_mesh.vertex_groups)} groups"
    )


def parent_and_export(mesh_obj, arm, out_path):
    mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = arm
    if mesh_obj.parent:
        bpy.ops.object.select_all(action="DESELECT")
        mesh_obj.select_set(True)
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.parent_clear(type="CLEAR")
    mesh_obj.parent = arm
    mesh_obj.matrix_parent_inverse = Matrix.Identity(4)
    mesh_obj.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()

    # Isolate for export
    keep = {mesh_obj.name, arm.name}
    bpy.ops.object.select_all(action="DESELECT")
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    s, dn = suppress()
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=False,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_image_format="AUTO",
    )
    restore(s, dn)
    print(f"    Exported → {out_path}")


def main():
    print("=" * 60)
    print("split_textured_full_shell_white.py")
    print("=" * 60)
    if not os.path.exists(TEXTURED):
        raise SystemExit(f"Missing textured GLB: {TEXTURED}")
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---- 1. Load calibration target verts ----------------------------
    print("\n[1/5] Loading calibration reference")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if os.path.exists(FULL_REF):
        ref_mesh = import_largest_mesh(FULL_REF, label="full_ref")
        target_verts = [v.co.copy() for v in ref_mesh.data.vertices]
    else:
        print("  full_female_shell.glb missing — union of Shell V1 pieces")
        target_verts = []
        for fname in SHELL_PIECES:
            m = import_largest_mesh(os.path.join(SHELL_DIR, fname), label=fname)
            target_verts.extend(v.co.copy() for v in m.data.vertices)

    # ---- 2. Load + remap textured ------------------------------------
    print("\n[2/5] Remapping textured full body into Shell V1 space")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    textured = import_largest_mesh(TEXTURED, label="textured")
    # Need target verts again in this scene — reload ref
    if os.path.exists(FULL_REF):
        ref_mesh = import_largest_mesh(FULL_REF, label="full_ref")
        target_verts = [v.co.copy() for v in ref_mesh.data.vertices]
        # hide/remove ref mesh from interfering later — keep verts list
        bpy.data.objects.remove(ref_mesh, do_unlink=True)
    remap_to_target(textured, target_verts)

    # ---- 3. Build region face index from Shell V1 --------------------
    print("\n[3/5] Building Shell V1 region face index")
    # Fresh scene with shells + keep textured by re-importing remapped...
    # Save remapped textured to temp, rebuild scene with shells + textured.
    tmp_path = os.path.join(OUT_DIR, "_tmp_remapped_full.glb")
    bpy.ops.object.select_all(action="DESELECT")
    textured.select_set(True)
    bpy.context.view_layer.objects.active = textured
    s, dn = suppress()
    bpy.ops.export_scene.gltf(
        filepath=tmp_path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_skins=False,
        export_animations=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_image_format="AUTO",
    )
    restore(s, dn)

    kd, region_labels, _ = build_region_face_index()

    # Re-import remapped textured into scene that has shell pieces
    textured = import_largest_mesh(tmp_path, label="remapped")

    # ---- 4. Assign faces + split -------------------------------------
    print("\n[4/5] Assigning faces and splitting")
    labels = assign_faces(textured, kd, region_labels)
    pieces = split_by_labels(textured, labels)

    # Export all unweighted splits to temp files BEFORE wiping the scene
    tmp_pieces = {}
    for fname in SHELL_PIECES:
        region = fname.replace(".glb", "")
        if region not in pieces:
            print(f"  SKIP {region}: no faces assigned")
            continue
        piece_obj = pieces[region]
        tmp_piece = os.path.join(OUT_DIR, f"_tmp_{region}.glb")
        bpy.ops.object.select_all(action="DESELECT")
        piece_obj.select_set(True)
        bpy.context.view_layer.objects.active = piece_obj
        s, dn = suppress()
        bpy.ops.export_scene.gltf(
            filepath=tmp_piece,
            export_format="GLB",
            use_selection=True,
            export_apply=True,
            export_yup=True,
            export_skins=False,
            export_animations=False,
            export_materials="EXPORT",
            export_texcoords=True,
            export_image_format="AUTO",
        )
        restore(s, dn)
        tmp_pieces[region] = tmp_piece

    # ---- 5. Weight each piece + export -------------------------------
    print("\n[5/5] Weight transfer + export")
    for fname in SHELL_PIECES:
        region = fname.replace(".glb", "")
        if region not in tmp_pieces:
            continue

        tmp_piece = tmp_pieces[region]
        shell_path = os.path.join(SHELL_DIR, fname)
        out_path = os.path.join(OUT_DIR, fname)

        bpy.ops.wm.read_factory_settings(use_empty=True)
        s, dn = suppress()
        bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
        bpy.context.view_layer.update()
        restore(s, dn)
        arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
        if not arm:
            raise RuntimeError("No armature in BaseFemaleV2")

        shell_mesh = import_largest_mesh(shell_path, label=f"shell:{region}")
        piece = import_largest_mesh(tmp_piece, label=f"piece:{region}")
        print(f"  {region}:")
        transfer_weights(piece, shell_mesh)
        parent_and_export(piece, arm, out_path)

        try:
            os.remove(tmp_piece)
        except OSError:
            pass

    try:
        os.remove(tmp_path)
    except OSError:
        pass

    print("\n" + "=" * 60)
    print(f"Done. Pieces written to {OUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
