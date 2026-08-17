"""
weight_skin_textures_white.py
=============================
Fit & rig Meshy-textured Equipment Shell V1 pieces (White skin) for Female V2.

Inputs (Meshy-normalized, unskinned):
  /Users/.../Desktop/Shells/SkinnedShells/Female/White/shell_v1_*.glb

Outputs (sized + Mixamo-skinned, Shell V1 format):
  viewer/public/equipment/Female/SkinTextures/White/shell_v1_*.glb

Body pieces use the same remap + KD weight transfer as
weight_green_ranged_armor.py, targeting each Shell V1 reference mesh.

Hands use the MeshyInputHands return-trip from weight_meshy_gloves.py:
  calibrate to MeshyInputHands → split L/R → snap to shell_v1_hands
  centroids → KD weight transfer from base_body_hands.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python weight_skin_textures_white.py
"""

from __future__ import annotations

import itertools
import os
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

sys.stdout.reconfigure(line_buffering=True)

BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
SHELL_DIR = os.path.abspath("viewer/public/equipment/Female/ShellV1")
SRC_DIR = os.path.abspath(
    "/Users/stephenvillavaso/Desktop/Shells/SkinnedShells/Female/White"
)
OUT_DIR = os.path.abspath("viewer/public/equipment/Female/SkinTextures/White")
MESHY_INPUT_HANDS = os.path.abspath(
    "viewer/public/equipment/Female/Gloves/MeshyInputHands.glb"
)

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER = 1.5
MAX_INFLUENCES = 4

# Non-hand shell pieces → body region(s) used for weight transfer.
# Remap target is always the matching Shell V1 mesh (same shape family).
BODY_PIECES = [
    {
        "file": "shell_v1_head.glb",
        "regions": ["base_body_head"],
    },
    {
        "file": "shell_v1_upper_torso.glb",
        "regions": ["base_body_upper_torso"],
    },
    {
        "file": "shell_v1_lower_torso.glb",
        "regions": ["base_body_lower_torso"],
    },
    {
        "file": "shell_v1_arm_upper.glb",
        "regions": ["base_body_arm_upper"],
    },
    {
        "file": "shell_v1_arm_lower.glb",
        "regions": ["base_body_arm_lower"],
    },
    {
        "file": "shell_v1_leg_upper.glb",
        "regions": ["base_body_leg_upper"],
    },
    {
        "file": "shell_v1_leg_thigh.glb",
        "regions": ["base_body_leg_thigh"],
    },
    {
        "file": "shell_v1_leg_knee.glb",
        "regions": ["base_body_leg_knee"],
    },
    {
        "file": "shell_v1_leg_shin.glb",
        "regions": ["base_body_leg_shin"],
    },
    {
        "file": "shell_v1_leg_ankle.glb",
        "regions": ["base_body_leg_ankle"],
    },
    {
        "file": "shell_v1_foot.glb",
        "regions": ["base_body_foot"],
    },
]


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


def bounds_and_centroid(verts):
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    mn = Vector((min(xs), min(ys), min(zs)))
    mx = Vector((max(xs), max(ys), max(zs)))
    return mn, mx, (mn + mx) / 2


def load_verts_from_glb(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    restore(s, dn)
    mesh_obj = None
    for o in bpy.data.objects:
        if o.type == "MESH" and "Icosphere" not in o.name:
            mesh_obj = o
            break
    if mesh_obj is None:
        raise RuntimeError(f"No mesh in {path}")
    return [v.co.copy() for v in mesh_obj.data.vertices]


def normalize_mesh(mesh_obj):
    verts = mesh_obj.data.vertices
    if len(verts) == 0:
        return
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    center = Vector(
        ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    )
    half_ext = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) / 2
    if half_ext < 1e-6:
        return
    for v in verts:
        v.co = (v.co - center) / half_ext
    mesh_obj.data.update()


def remap_meshy_to_target(meshy_mesh, target_objs):
    """48-combo axis remap so Meshy mesh matches target geometry bounds."""
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

    t_xs, t_ys, t_zs = [], [], []
    for obj in target_objs:
        for v in obj.data.vertices:
            t_xs.append(v.co.x)
            t_ys.append(v.co.y)
            t_zs.append(v.co.z)
    if not t_xs:
        return False

    t_min = Vector((min(t_xs), min(t_ys), min(t_zs)))
    t_max = Vector((max(t_xs), max(t_ys), max(t_zs)))
    t_range = t_max - t_min
    t_center = (t_min + t_max) / 2
    m_center = (m_min + m_max) / 2

    print(
        f"  Target bounds: X=[{t_min.x:.3f},{t_max.x:.3f}] "
        f"Y=[{t_min.y:.3f},{t_max.y:.3f}] Z=[{t_min.z:.3f},{t_max.z:.3f}]"
    )
    print(
        f"  Meshy bounds:  X=[{m_min.x:.4f},{m_max.x:.4f}] "
        f"Y=[{m_min.y:.4f},{m_max.y:.4f}] Z=[{m_min.z:.4f},{m_max.z:.4f}]"
    )

    target_verts = []
    for obj in target_objs:
        for v in obj.data.vertices:
            target_verts.append(v.co.copy())
    kd = KDTree(len(target_verts))
    for i, co in enumerate(target_verts):
        kd.insert(co, i)
    kd.balance()

    n_verts = len(mverts)
    step = max(1, n_verts // 200)
    sample_verts = [mverts[i].co.copy() for i in range(0, n_verts, step)]

    body_sizes = [t_range.x, t_range.y, t_range.z]
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
                    new_co[body_ax] = val * scales[body_ax] + t_center[body_ax]
                _, _, dist = kd.find(new_co)
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
    print(f"  Best axis mapping: body[XYZ] ← meshy[{perm_str}], signs: {sign_str}")
    print(f"  Per-axis scales: [{scales[0]:.3f}, {scales[1]:.3f}, {scales[2]:.3f}]")
    print(f"  Avg sample distance to target: {avg_dist:.4f}")

    for v in mverts:
        old = v.co.copy()
        new_co = Vector((0, 0, 0))
        for body_ax in range(3):
            meshy_ax = best_perm[body_ax]
            val = (old[meshy_ax] - m_center[meshy_ax]) * best_signs[body_ax]
            new_co[body_ax] = val * scales[body_ax] + t_center[body_ax]
        v.co = new_co
    meshy_mesh.data.update()

    mbx, mby, mbz = local_bounds(meshy_mesh)
    print(
        f"  Remapped bounds: X=[{mbx[0]:.3f},{mbx[1]:.3f}] "
        f"Y=[{mby[0]:.3f},{mby[1]:.3f}] Z=[{mbz[0]:.3f},{mbz[1]:.3f}]"
    )
    return True


def transfer_weights(dst_mesh, src_objs):
    all_positions = []
    all_weights = []
    for src in src_objs:
        vg_names = {vg.index: vg.name for vg in src.vertex_groups}
        for v in src.data.vertices:
            groups = {}
            for g in v.groups:
                gname = vg_names.get(g.group)
                if gname and g.weight > 0.0001:
                    groups[gname] = g.weight
            all_positions.append(v.co.copy())
            all_weights.append(groups)

    if not all_positions:
        raise RuntimeError("No weight-source vertices")

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
        f"  Transferred {transferred} weight entries, "
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
    print(f"  Exported → {out_path}")


def import_joined_mesh(path):
    pre = {o.name for o in bpy.data.objects}
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    restore(s, dn)
    new_objs = [o for o in bpy.data.objects if o.name not in pre]
    meshes = [
        o for o in new_objs if o.type == "MESH" and "Icosphere" not in o.name
    ]
    if not meshes:
        return None
    if len(meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for m in meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.join()
    return meshes[0]


def process_body_piece(piece):
    fname = piece["file"]
    src = os.path.join(SRC_DIR, fname)
    shell_ref = os.path.join(SHELL_DIR, fname)
    out = os.path.join(OUT_DIR, fname)
    regions = piece["regions"]

    print(f"\n{'=' * 60}")
    print(f"Body piece: {fname}")
    print(f"{'=' * 60}")
    sys.stdout.flush()

    if not os.path.exists(src):
        print(f"  SKIP: missing {src}")
        return False
    if not os.path.exists(shell_ref):
        print(f"  SKIP: missing shell ref {shell_ref}")
        return False

    bpy.ops.wm.read_factory_settings(use_empty=True)

    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
    bpy.context.view_layer.update()
    restore(s, dn)

    base_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    if not base_arm:
        raise RuntimeError("No armature in BaseFemaleV2")

    # Import Shell V1 reference as remap + weight source (preferred),
    # falling back to body regions for weights if shell has no groups.
    shell_mesh = import_joined_mesh(shell_ref)
    if shell_mesh is None:
        raise RuntimeError(f"No mesh in shell ref {shell_ref}")
    print(f"  Shell ref: {shell_mesh.name} ({len(shell_mesh.data.vertices)} verts)")

    meshy_mesh = import_joined_mesh(src)
    if meshy_mesh is None:
        print(f"  SKIP: no mesh in {src}")
        return False
    print(f"  Meshy mesh: {meshy_mesh.name} ({len(meshy_mesh.data.vertices)} verts)")

    remap_meshy_to_target(meshy_mesh, [shell_mesh])

    weight_srcs = [shell_mesh] if shell_mesh.vertex_groups else []
    if not weight_srcs:
        weight_srcs = [region_meshes[r] for r in regions if r in region_meshes]
    if not weight_srcs:
        # Prefer body regions alongside shell if shell groups empty after import
        weight_srcs = [region_meshes[r] for r in regions if r in region_meshes]
        if shell_mesh.vertex_groups:
            weight_srcs = [shell_mesh]
    if not weight_srcs:
        body = [region_meshes[r] for r in regions if r in region_meshes]
        weight_srcs = body if body else [shell_mesh]

    # Always prefer shell vertex groups when present; else body regions.
    if shell_mesh.vertex_groups:
        weight_srcs = [shell_mesh]
    else:
        weight_srcs = [region_meshes[r] for r in regions if r in region_meshes]
        print(f"  Using body regions for weights: {[o.name for o in weight_srcs]}")

    transfer_weights(meshy_mesh, weight_srcs)
    parent_and_export(meshy_mesh, base_arm, out)
    return True


def build_hand_refs():
    shell_verts = load_verts_from_glb(os.path.join(SHELL_DIR, "shell_v1_hands.glb"))
    shell_left = [v for v in shell_verts if v.x < 0.0]
    shell_right = [v for v in shell_verts if v.x > 0.0]
    left_ctr = sum(shell_left, Vector()) / len(shell_left)
    right_ctr = sum(shell_right, Vector()) / len(shell_right)
    print(
        f"  shell_v1_hands centroids: "
        f"L=({left_ctr.x:.2f},{left_ctr.y:.2f},{left_ctr.z:.2f})  "
        f"R=({right_ctr.x:.2f},{right_ctr.y:.2f},{right_ctr.z:.2f})"
    )

    mih_verts = load_verts_from_glb(MESHY_INPUT_HANDS)
    mih_min, mih_max, mih_ctr = bounds_and_centroid(mih_verts)
    mih_centered = [v - mih_ctr for v in mih_verts]
    print(
        f"  MeshyInputHands: {len(mih_verts)}v  "
        f"X=[{mih_min.x:.3f},{mih_max.x:.3f}]  "
        f"Y=[{mih_min.y:.3f},{mih_max.y:.3f}]  "
        f"Z=[{mih_min.z:.3f},{mih_max.z:.3f}]"
    )

    mih_kd = KDTree(len(mih_centered))
    for i, co in enumerate(mih_centered):
        mih_kd.insert(co, i)
    mih_kd.balance()

    return {
        "left_ctr": left_ctr,
        "right_ctr": right_ctr,
        "mih_kd": mih_kd,
        "mih_X_ext": mih_max.x - mih_min.x,
        "mih_Y_ext": mih_max.y - mih_min.y,
        "mih_Z_ext": mih_max.z - mih_min.z,
    }


def process_hands(refs=None):
    """Fit White hands via MeshyInputHands orientation + per-hand size match.

    Source is the close-together MIH layout (hands nearly fill X with a small
    gap).  Meshy remesh changes aspect ratio, so a single uniform scale leaves
    hands oversized and opens a wrist gap after centroid snap.

    Pipeline:
      1. Calibrate axis mapping against MeshyInputHands (same as gloves).
      2. Apply mapping with a provisional uniform scale.
      3. Split L/R; uniformly rescale EACH hand so its X-span matches the
         corresponding shell_v1_hands hand (locks wrist position).
      4. Snap each hand centroid to shell_v1_hands.
      5. KD weight transfer from shell_v1_hands / base_body_hands.
    """
    fname = "shell_v1_hands.glb"
    src = os.path.join(SRC_DIR, fname)
    shell_ref = os.path.join(SHELL_DIR, fname)
    out = os.path.join(OUT_DIR, fname)

    print(f"\n{'=' * 60}")
    print("Hands (MIH orient + per-hand X-span match to shell)")
    print(f"{'=' * 60}")
    sys.stdout.flush()

    if not os.path.exists(src):
        print(f"  SKIP: missing {src}")
        return False

    # ---- shell + MIH references --------------------------------------
    shell_verts = load_verts_from_glb(shell_ref)
    shell_left = [v for v in shell_verts if v.x < 0.0]
    shell_right = [v for v in shell_verts if v.x > 0.0]
    left_ctr = sum(shell_left, Vector()) / len(shell_left)
    right_ctr = sum(shell_right, Vector()) / len(shell_right)

    def _span_x(vs):
        xs = [v.x for v in vs]
        return max(xs) - min(xs)

    shell_left_x = _span_x(shell_left)
    shell_right_x = _span_x(shell_right)
    print(
        f"  shell hands: L_xspan={shell_left_x:.2f} R_xspan={shell_right_x:.2f}  "
        f"L_ctr=({left_ctr.x:.2f},{left_ctr.y:.2f},{left_ctr.z:.2f})  "
        f"R_ctr=({right_ctr.x:.2f},{right_ctr.y:.2f},{right_ctr.z:.2f})"
    )

    mih_verts = load_verts_from_glb(MESHY_INPUT_HANDS)
    mih_min, mih_max, mih_ctr = bounds_and_centroid(mih_verts)
    mih_centered = [v - mih_ctr for v in mih_verts]
    mih_X_ext = mih_max.x - mih_min.x
    mih_Y_ext = mih_max.y - mih_min.y
    mih_Z_ext = mih_max.z - mih_min.z
    print(
        f"  MeshyInputHands: Xspan={mih_X_ext:.2f} Yspan={mih_Y_ext:.2f} "
        f"Zspan={mih_Z_ext:.2f}"
    )

    mih_kd = KDTree(len(mih_centered))
    for i, co in enumerate(mih_centered):
        mih_kd.insert(co, i)
    mih_kd.balance()

    # ---- base + meshy -----------------------------------------------
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
    bpy.context.view_layer.update()
    restore(s, dn)

    base_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    if not base_arm:
        raise RuntimeError("No armature in BaseFemaleV2")

    glove = import_joined_mesh(src)
    if glove is None:
        print(f"  SKIP: no mesh in {src}")
        return False
    print(f"  Meshy mesh: {glove.name} ({len(glove.data.vertices)} verts)")

    mv_local = [v.co.copy() for v in glove.data.vertices]
    meshy_min, meshy_max, meshy_ctr = bounds_and_centroid(mv_local)
    print(
        f"  Meshy bounds: X=[{meshy_min.x:.3f},{meshy_max.x:.3f}]  "
        f"Y=[{meshy_min.y:.3f},{meshy_max.y:.3f}]  "
        f"Z=[{meshy_min.z:.3f},{meshy_max.z:.3f}]"
    )

    mv_centered = [v - meshy_ctr for v in mv_local]
    meshy_ext = meshy_max - meshy_min
    meshy_sizes = [meshy_ext.x, meshy_ext.y, meshy_ext.z]

    n_verts = len(mv_centered)
    step = max(1, n_verts // 300)
    sample = mv_centered[::step]

    # Forced XZY mapping used by all MIH-derived glove sets.
    best_perm = (0, 2, 1)
    best_signs = (+1, +1, -1)
    # Provisional scale from MIH bilateral X (gets us into the right ballpark
    # before per-hand correction).
    best_scale = mih_X_ext / meshy_sizes[0]

    total = 0.0
    for mv in sample:
        new_co = Vector((0.0, 0.0, 0.0))
        for body_ax in range(3):
            ma = best_perm[body_ax]
            new_co[body_ax] = mv[ma] * best_signs[body_ax] * best_scale
        _, _, dist = mih_kd.find(new_co)
        total += dist
    avg_dist = total / len(sample)
    print(
        f"  Axis mapping (FORCED): body[XYZ] <- meshy[XZY], signs: ++-, "
        f"provisional_scale={best_scale:.4f}"
    )
    print(f"  Avg sample distance to MeshyInputHands: {avg_dist:.4f}")

    for v in glove.data.vertices:
        old = v.co - meshy_ctr
        new_co = Vector((0.0, 0.0, 0.0))
        for body_ax in range(3):
            ma = best_perm[body_ax]
            new_co[body_ax] = old[ma] * best_signs[body_ax] * best_scale
        v.co = new_co
    glove.data.update()

    left_idx = [i for i, v in enumerate(glove.data.vertices) if v.co.x < 0.0]
    right_idx = [i for i, v in enumerate(glove.data.vertices) if v.co.x > 0.0]
    print(f"  Split: left={len(left_idx)}  right={len(right_idx)}")
    if not left_idx or not right_idx:
        raise RuntimeError("Hands split failed — one side empty")

    def _hand_spans(indices):
        xs = [glove.data.vertices[i].co.x for i in indices]
        ys = [glove.data.vertices[i].co.y for i in indices]
        zs = [glove.data.vertices[i].co.z for i in indices]
        return (
            max(xs) - min(xs),
            max(ys) - min(ys),
            max(zs) - min(zs),
            Vector((
                (min(xs) + max(xs)) / 2,
                (min(ys) + max(ys)) / 2,
                (min(zs) + max(zs)) / 2,
            )),
        )

    def _shell_hand_spans(verts):
        xs = [v.x for v in verts]
        ys = [v.y for v in verts]
        zs = [v.z for v in verts]
        return (
            max(xs) - min(xs),
            max(ys) - min(ys),
            max(zs) - min(zs),
        )

    shell_l_spans = _shell_hand_spans(shell_left)
    shell_r_spans = _shell_hand_spans(shell_right)

    def _aabb_center(verts):
        xs = [v.x for v in verts]
        ys = [v.y for v in verts]
        zs = [v.z for v in verts]
        return Vector((
            (min(xs) + max(xs)) / 2,
            (min(ys) + max(ys)) / 2,
            (min(zs) + max(zs)) / 2,
        ))

    shell_l_aabb_ctr = _aabb_center(shell_left)
    shell_r_aabb_ctr = _aabb_center(shell_right)

    for indices, target_spans, target_aabb_ctr, side in [
        (left_idx, shell_l_spans, shell_l_aabb_ctr, "L"),
        (right_idx, shell_r_spans, shell_r_aabb_ctr, "R"),
    ]:
        sx, sy, sz, ctr = _hand_spans(indices)
        tx, ty, tz = target_spans
        if min(sx, sy, sz) < 1e-6:
            raise RuntimeError(f"{side} hand has zero span")
        scale = Vector((tx / sx, ty / sy, tz / sz))
        print(
            f"  {side}: spans ({sx:.2f},{sy:.2f},{sz:.2f}) -> "
            f"({tx:.2f},{ty:.2f},{tz:.2f})  "
            f"scale=({scale.x:.3f},{scale.y:.3f},{scale.z:.3f})"
        )
        for i in indices:
            co = glove.data.vertices[i].co
            d = co - ctr
            glove.data.vertices[i].co = Vector((
                ctr.x + d.x * scale.x,
                ctr.y + d.y * scale.y,
                ctr.z + d.z * scale.z,
            ))

        # Spans match — snap AABB center so bounds coincide with shell hand
        _, _, _, aabb_ctr = _hand_spans(indices)
        offset = target_aabb_ctr - aabb_ctr
        for i in indices:
            glove.data.vertices[i].co = glove.data.vertices[i].co + offset
        print(
            f"  {side}: AABB snap "
            f"({offset.x:.2f},{offset.y:.2f},{offset.z:.2f})  "
            f"-> ({target_aabb_ctr.x:.2f},{target_aabb_ctr.y:.2f},{target_aabb_ctr.z:.2f})"
        )
    glove.data.update()

    f_min, f_max, _ = bounds_and_centroid(
        [v.co.copy() for v in glove.data.vertices]
    )
    shell_min, shell_max, _ = bounds_and_centroid(shell_verts)
    print(
        f"  Final bounds: X=[{f_min.x:.2f},{f_max.x:.2f}]  "
        f"Y=[{f_min.y:.2f},{f_max.y:.2f}]  Z=[{f_min.z:.2f},{f_max.z:.2f}]"
    )
    print(
        f"  Shell  bounds: X=[{shell_min.x:.2f},{shell_max.x:.2f}]  "
        f"Y=[{shell_min.y:.2f},{shell_max.y:.2f}]  Z=[{shell_min.z:.2f},{shell_max.z:.2f}]"
    )

    # Weight transfer from shell (preferred) or body hands
    shell_mesh = None
    pre = {o.name for o in bpy.data.objects}
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=shell_ref)
    bpy.context.view_layer.update()
    restore(s, dn)
    for o in bpy.data.objects:
        if o.name not in pre and o.type == "MESH" and "Icosphere" not in o.name:
            shell_mesh = o
            break

    if shell_mesh and shell_mesh.vertex_groups:
        print("  Weight source: shell_v1_hands")
        transfer_weights(glove, [shell_mesh])
    else:
        print("  Weight source: base_body_hands")
        transfer_weights(glove, [region_meshes["base_body_hands"]])

    parent_and_export(glove, base_arm, out)
    return True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    only = None
    for arg in sys.argv:
        if arg.startswith("--only="):
            only = arg.split("=", 1)[1]

    print("weight_skin_textures_white.py")
    print(f"  SRC: {SRC_DIR}")
    print(f"  OUT: {OUT_DIR}")
    if only:
        print(f"  ONLY: {only}")
    sys.stdout.flush()

    ok = 0
    total = 0

    if only in (None, "body"):
        for piece in BODY_PIECES:
            total += 1
            if process_body_piece(piece):
                ok += 1

    if only in (None, "hands"):
        total += 1
        if process_hands():
            ok += 1

    print(f"\n{'=' * 60}")
    print(f"Finished: {ok}/{total} pieces")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
