"""
weight_red_ranged_gloves.py
===========================
Single-piece variant of weight_green_ranged_armor.py for the Red Ranged
gloves. The source GLB is a Meshy text-to-texture output of the Shell V1
hands with the two gloves manually moved closer together before upload,
so the mesh bounds no longer span shoulder-to-shoulder.

Pipeline (identical to weight_green_ranged_armor.py, scoped to one piece):
  1. Normalise to [-1, 1] on the longest axis (if Meshy hasn't).
  2. Try all 48 axis-permutation x sign combos, pick the one that
     minimises nearest-neighbour distance to the base_body_hands region.
  3. Per-axis scale + translate so the mesh matches base_body_hands bounds
     -- this stretches the two gloves back out to shoulder-width.
  4. KD-tree weight transfer from base_body_hands verts; each vertex
     independently inherits weights from its 12 nearest body verts via
     inverse-distance blending. Left-side gloves pick up LeftHand bones;
     right-side gloves pick up RightHand bones -- bilateral handling is
     automatic.
  5. Parent to the base armature and export, overwriting the input.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_red_ranged_gloves.py
"""

import os
import sys
import itertools
import bpy
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

sys.stdout.reconfigure(line_buffering=True)

BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")

PIECE = {
    "name": "red_ranged_gloves",
    "src": os.path.abspath("viewer/public/equipment/Female/Gloves/RedRangedGloves.glb"),
    "out": os.path.abspath("viewer/public/equipment/Female/Gloves/RedRangedGloves.glb"),
    "regions": ["base_body_hands"],
}

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


def local_bounds(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def normalize_mesh(mesh_obj):
    verts = mesh_obj.data.vertices
    if len(verts) == 0:
        return
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    center = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    half_ext = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)) / 2
    if half_ext < 1e-6:
        return
    for v in verts:
        v.co = (v.co - center) / half_ext
    mesh_obj.data.update()
    bx, by, bz = local_bounds(mesh_obj)
    print(f"  Normalized bounds: X=[{bx[0]:.3f},{bx[1]:.3f}] "
          f"Y=[{by[0]:.3f},{by[1]:.3f}] Z=[{bz[0]:.3f},{bz[1]:.3f}]")
    sys.stdout.flush()


def remap_meshy_to_body(meshy_mesh, body_objs):
    mverts = meshy_mesh.data.vertices
    if len(mverts) == 0:
        return False

    m_xs = [v.co.x for v in mverts]
    m_ys = [v.co.y for v in mverts]
    m_zs = [v.co.z for v in mverts]
    m_min = Vector((min(m_xs), min(m_ys), min(m_zs)))
    m_max = Vector((max(m_xs), max(m_ys), max(m_zs)))
    m_range = m_max - m_min

    max_extent = max(m_range.x, m_range.y, m_range.z)
    if max_extent > 5.0:
        print(f"  Mesh in body scale (max extent: {max_extent:.1f}), normalizing first...")
        normalize_mesh(meshy_mesh)
        mverts = meshy_mesh.data.vertices
        m_xs = [v.co.x for v in mverts]
        m_ys = [v.co.y for v in mverts]
        m_zs = [v.co.z for v in mverts]
        m_min = Vector((min(m_xs), min(m_ys), min(m_zs)))
        m_max = Vector((max(m_xs), max(m_ys), max(m_zs)))
        m_range = m_max - m_min

    b_xs, b_ys, b_zs = [], [], []
    for obj in body_objs:
        for v in obj.data.vertices:
            b_xs.append(v.co.x)
            b_ys.append(v.co.y)
            b_zs.append(v.co.z)
    if not b_xs:
        return False

    b_min = Vector((min(b_xs), min(b_ys), min(b_zs)))
    b_max = Vector((max(b_xs), max(b_ys), max(b_zs)))
    b_range = b_max - b_min
    b_center = (b_min + b_max) / 2
    m_center = (m_min + m_max) / 2

    print(f"  Body bounds:  X=[{b_min.x:.3f},{b_max.x:.3f}] "
          f"Y=[{b_min.y:.3f},{b_max.y:.3f}] Z=[{b_min.z:.3f},{b_max.z:.3f}]")
    print(f"  Meshy bounds: X=[{m_min.x:.4f},{m_max.x:.4f}] "
          f"Y=[{m_min.y:.4f},{m_max.y:.4f}] Z=[{m_min.z:.4f},{m_max.z:.4f}]")
    sys.stdout.flush()

    body_verts_list = []
    for obj in body_objs:
        for v in obj.data.vertices:
            body_verts_list.append(v.co.copy())
    body_kd = KDTree(len(body_verts_list))
    for i, co in enumerate(body_verts_list):
        body_kd.insert(co, i)
    body_kd.balance()

    n_verts = len(mverts)
    step = max(1, n_verts // 200)
    sample_verts = [mverts[i].co.copy() for i in range(0, n_verts, step)]

    body_sizes = [b_range.x, b_range.y, b_range.z]
    meshy_sizes = [m_range.x, m_range.y, m_range.z]

    best_score = float("inf")
    best_perm = (0, 1, 2)
    best_signs = (1, 1, 1)

    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            scales = [0.0, 0.0, 0.0]
            for body_ax in range(3):
                meshy_ax = perm[body_ax]
                br = body_sizes[body_ax]
                mr = meshy_sizes[meshy_ax]
                scales[body_ax] = br / mr if mr > 0.001 else 1.0

            total_dist = 0.0
            for sv in sample_verts:
                new_co = Vector((0, 0, 0))
                for body_ax in range(3):
                    meshy_ax = perm[body_ax]
                    val = (sv[meshy_ax] - m_center[meshy_ax]) * signs[body_ax]
                    new_co[body_ax] = val * scales[body_ax] + b_center[body_ax]
                _, _, dist = body_kd.find(new_co)
                total_dist += dist

            if total_dist < best_score:
                best_score = total_dist
                best_perm = perm
                best_signs = signs

    scales = [0.0, 0.0, 0.0]
    for body_ax in range(3):
        meshy_ax = best_perm[body_ax]
        br = body_sizes[body_ax]
        mr = meshy_sizes[meshy_ax]
        scales[body_ax] = br / mr if mr > 0.001 else 1.0

    axis_names = ["X", "Y", "Z"]
    perm_str = "".join(axis_names[i] for i in best_perm)
    sign_str = "".join("+" if s > 0 else "-" for s in best_signs)
    avg_dist = best_score / len(sample_verts) if sample_verts else 0
    print(f"  Best axis mapping: body[XYZ] <- meshy[{perm_str}], signs: {sign_str}")
    print(f"  Per-axis scales: [{scales[0]:.2f}, {scales[1]:.2f}, {scales[2]:.2f}]")
    print(f"  Avg sample distance to nearest body vert: {avg_dist:.4f}")
    sys.stdout.flush()

    for v in mverts:
        old = v.co.copy()
        new_co = Vector((0, 0, 0))
        for body_ax in range(3):
            meshy_ax = best_perm[body_ax]
            val = (old[meshy_ax] - m_center[meshy_ax]) * best_signs[body_ax]
            new_co[body_ax] = val * scales[body_ax] + b_center[body_ax]
        v.co = new_co
    meshy_mesh.data.update()

    mbx, mby, mbz = local_bounds(meshy_mesh)
    print(f"  Remapped bounds: X=[{mbx[0]:.3f},{mbx[1]:.3f}] "
          f"Y=[{mby[0]:.3f},{mby[1]:.3f}] Z=[{mbz[0]:.3f},{mbz[1]:.3f}]")
    sys.stdout.flush()
    return True


def process_piece(piece):
    piece_name = piece["name"]
    src_path = piece["src"]
    out_path = piece["out"]
    regions = piece["regions"]

    print(f"\n{'='*60}")
    print(f"Processing: {piece_name}")
    sys.stdout.flush()

    bpy.ops.wm.read_factory_settings(use_empty=True)

    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
    bpy.context.view_layer.update()
    restore(s, dn)

    base_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

    pre_import = {o.name for o in bpy.data.objects}
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=src_path)
    bpy.context.view_layer.update()
    restore(s, dn)

    new_objects = [o for o in bpy.data.objects if o.name not in pre_import]
    imported_meshes = [o for o in new_objects if o.type == "MESH"
                       and "Icosphere" not in o.name]

    if not imported_meshes:
        print("  ERROR: No mesh found")
        return

    if len(imported_meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for m in imported_meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = imported_meshes[0]
        bpy.ops.object.join()
    meshy_mesh = imported_meshes[0]

    print(f"  Mesh: {meshy_mesh.name} ({len(meshy_mesh.data.vertices)} verts)")
    sys.stdout.flush()

    body_objs = [region_meshes[r] for r in regions if r in region_meshes]
    if not body_objs:
        print(f"  ERROR: None of {regions} found in base model")
        return
    remap_meshy_to_body(meshy_mesh, body_objs)

    meshy_mesh.vertex_groups.clear()
    for mod in list(meshy_mesh.modifiers):
        if mod.type == "ARMATURE":
            meshy_mesh.modifiers.remove(mod)

    all_positions = []
    all_weights = []
    for rname in regions:
        src = region_meshes.get(rname)
        if not src:
            continue
        vg_names = {vg.index: vg.name for vg in src.vertex_groups}
        for v in src.data.vertices:
            groups = {}
            for g in v.groups:
                gname = vg_names.get(g.group)
                if gname and g.weight > 0.0001:
                    groups[gname] = g.weight
            all_positions.append(v.co.copy())
            all_weights.append(groups)

    print(f"  Body reference: {len(all_positions)} verts from {len(regions)} regions")
    sys.stdout.flush()

    if not all_positions:
        print("  ERROR: No body verts")
        return

    kd = KDTree(len(all_positions))
    for i, pos in enumerate(all_positions):
        kd.insert(pos, i)
    kd.balance()

    transferred = 0
    for rv_idx, rv in enumerate(meshy_mesh.data.vertices):
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
                    if name not in [vg.name for vg in meshy_mesh.vertex_groups]:
                        meshy_mesh.vertex_groups.new(name=name)
                    meshy_mesh.vertex_groups[name].add([rv_idx], nw, "REPLACE")
                    transferred += 1

    print(f"  Transferred {transferred} weight entries (max {MAX_INFLUENCES} per vert)")
    print(f"  Groups: {len(meshy_mesh.vertex_groups)}")
    sys.stdout.flush()

    target_arm = base_arm
    mod = meshy_mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = target_arm

    if meshy_mesh.parent:
        bpy.ops.object.select_all(action="DESELECT")
        meshy_mesh.select_set(True)
        bpy.context.view_layer.objects.active = meshy_mesh
        bpy.ops.object.parent_clear(type="CLEAR")

    meshy_mesh.parent = target_arm
    meshy_mesh.matrix_parent_inverse = Matrix.Identity(4)
    meshy_mesh.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()

    keep = {meshy_mesh.name}
    if target_arm:
        keep.add(target_arm.name)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    bpy.ops.object.select_all(action="DESELECT")
    meshy_mesh.select_set(True)
    if target_arm:
        target_arm.select_set(True)
        bpy.context.view_layer.objects.active = target_arm

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
    print(f"  Exported -> {out_path}")
    sys.stdout.flush()


print("Starting weight_red_ranged_gloves.py ...")
sys.stdout.flush()
process_piece(PIECE)
print("Done.")
sys.stdout.flush()
