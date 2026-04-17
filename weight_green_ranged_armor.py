"""
weight_green_ranged_armor.py
============================
Takes each Green Ranged Armor piece (downloaded from Meshy AI), auto-detects
the coordinate transform Meshy applied (normalization, axis swap, centering),
remaps vertices to match the BaseFemaleV2 body regions, transfers bone weights
via KD-tree, and exports weighted GLBs in the same format as Shell V1.

Meshy AI typically:
  - Re-meshes the model (different vertex count)
  - Normalises to [-1, 1] on the longest axis
  - Swaps Y and Z axes (internal Z-up exported as Y-up without conversion)
  - Centers the mesh at the origin

The script tries all 48 axis-permutation × sign combinations and picks the
one that best matches the body-region geometry via nearest-vertex distance.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_green_ranged_armor.py
"""

import os
import sys
import itertools
import bpy
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

sys.stdout.reconfigure(line_buffering=True)

BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")

PIECES = [
    {
        "name": "green_ranged_upperbody",
        "src": os.path.abspath("viewer/public/equipment/Female/Upperbody/TexturedGreenRangedUpperBody.glb"),
        "out": os.path.abspath("viewer/public/equipment/Female/Upperbody/TexturedGreenRangedUpperBody.glb"),
        "regions": [
            "base_body_upper_torso",
            "base_body_lower_torso",
            "base_body_arm_upper",
            "base_body_arm_lower",
        ],
    },
    {
        "name": "green_ranged_gloves",
        "src": os.path.abspath("viewer/public/equipment/Female/Gloves/TexturedGreenRangedGloves.glb"),
        "out": os.path.abspath("viewer/public/equipment/Female/Gloves/TexturedGreenRangedGloves.glb"),
        "regions": [
            "base_body_hands",
        ],
    },
    {
        "name": "green_ranged_lowerbody",
        "src": os.path.abspath("viewer/public/equipment/Female/Lowerbody/TexturedGreenRangedLowerBody.glb"),
        "out": os.path.abspath("viewer/public/equipment/Female/Lowerbody/TexturedGreenRangedLowerBody.glb"),
        "regions": [
            "base_body_leg_upper",
            "base_body_leg_thigh",
            "base_body_leg_knee",
            "base_body_leg_shin",
            "base_body_leg_ankle",
        ],
    },
    {
        "name": "green_ranged_boots",
        "src": os.path.abspath("viewer/public/equipment/Female/Boots/TexturedGreenRangedBoots.glb"),
        "out": os.path.abspath("viewer/public/equipment/Female/Boots/TexturedGreenRangedBoots.glb"),
        "regions": [
            "base_body_foot",
            "base_body_leg_ankle",
        ],
    },
]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER = 1.5


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
    """Center and scale mesh vertices to [-1, 1] on the longest axis."""
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
    """
    Transform Meshy's normalised/axis-swapped mesh to match body-region
    coordinates.  Always normalizes first for idempotent re-processing.
    Returns True if a remap was applied, False on error.
    """
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

    # Combined body-region bounds
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

    print(f"  Body bounds:  X=[{b_min.x:.1f},{b_max.x:.1f}] "
          f"Y=[{b_min.y:.1f},{b_max.y:.1f}] Z=[{b_min.z:.1f},{b_max.z:.1f}]")
    print(f"  Meshy bounds: X=[{m_min.x:.4f},{m_max.x:.4f}] "
          f"Y=[{m_min.y:.4f},{m_max.y:.4f}] Z=[{m_min.z:.4f},{m_max.z:.4f}]")
    sys.stdout.flush()

    # Build KD-tree from body vertices for scoring
    body_verts_list = []
    for obj in body_objs:
        for v in obj.data.vertices:
            body_verts_list.append(v.co.copy())

    body_kd = KDTree(len(body_verts_list))
    for i, co in enumerate(body_verts_list):
        body_kd.insert(co, i)
    body_kd.balance()

    # Sample meshy vertices for fast evaluation
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

    # Compute final per-axis scales
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
    print(f"  Per-axis scales: [{scales[0]:.2f}, {scales[1]:.2f}, {scales[2]:.2f}]")
    print(f"  Avg sample distance to nearest body vert: {avg_dist:.4f}")
    sys.stdout.flush()

    # Apply the transformation to ALL vertices
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
    print(f"  Remapped bounds: X=[{mbx[0]:.1f},{mbx[1]:.1f}] "
          f"Y=[{mby[0]:.1f},{mby[1]:.1f}] Z=[{mbz[0]:.1f},{mbz[1]:.1f}]")
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

    # Import base model
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
    bpy.context.view_layer.update()
    restore(s, dn)

    base_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

    # Import Meshy piece
    pre_import = {o.name for o in bpy.data.objects}
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=src_path)
    bpy.context.view_layer.update()
    restore(s, dn)

    new_objects = [o for o in bpy.data.objects if o.name not in pre_import]
    imported_meshes = [o for o in new_objects if o.type == "MESH"
                       and "Icosphere" not in o.name]
    imported_armatures = [o for o in new_objects if o.type == "ARMATURE"]

    if not imported_meshes:
        print(f"  ERROR: No mesh found")
        return

    # Join if multiple meshes
    if len(imported_meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for m in imported_meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = imported_meshes[0]
        bpy.ops.object.join()
    meshy_mesh = imported_meshes[0]

    print(f"  Mesh: {meshy_mesh.name} ({len(meshy_mesh.data.vertices)} verts)")
    sys.stdout.flush()

    # ------------------------------------------------------------------
    # Remap Meshy vertices to match body region coordinates.
    # Meshy normalises, re-centres, and may swap axes.
    # ------------------------------------------------------------------
    body_objs = [region_meshes[r] for r in regions if r in region_meshes]
    remapped = remap_meshy_to_body(meshy_mesh, body_objs)
    if not remapped:
        print("  WARNING: Mesh was not remapped — may already be in body scale")

    # ------------------------------------------------------------------
    # Clear existing vertex groups & armature modifiers
    # ------------------------------------------------------------------
    meshy_mesh.vertex_groups.clear()
    for mod in list(meshy_mesh.modifiers):
        if mod.type == "ARMATURE":
            meshy_mesh.modifiers.remove(mod)

    # ------------------------------------------------------------------
    # Build KD-tree from body regions for weight transfer
    # ------------------------------------------------------------------
    all_positions = []
    all_weights = []

    for rname in regions:
        src = region_meshes.get(rname)
        if not src:
            print(f"  WARNING: Region '{rname}' not found")
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
        print(f"  ERROR: No body verts")
        return

    kd = KDTree(len(all_positions))
    for i, pos in enumerate(all_positions):
        kd.insert(pos, i)
    kd.balance()

    # ------------------------------------------------------------------
    # Transfer weights using local-space nearest-neighbour
    # ------------------------------------------------------------------
    MAX_INFLUENCES = 4

    transferred = 0
    for rv_idx, rv in enumerate(meshy_mesh.data.vertices):
        neighbors = kd.find_n(rv.co, WEIGHT_NEIGHBORS)

        inv_weights = []
        for co, idx, dist in neighbors:
            w = 1.0 / (dist ** WEIGHT_POWER + 1e-8)
            inv_weights.append((idx, w))

        total_inv = sum(w for _, w in inv_weights)

        blended = {}
        for body_idx, inv_w in inv_weights:
            factor = inv_w / total_inv
            for gname, bw in all_weights[body_idx].items():
                blended[gname] = blended.get(gname, 0.0) + bw * factor

        # Keep only top MAX_INFLUENCES bones per vertex and re-normalise
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

    # ------------------------------------------------------------------
    # Parent to armature with identity-relative transform so the exported
    # GLB matches the Shell V1 format (mesh node = identity under armature).
    # ------------------------------------------------------------------
    target_arm = base_arm

    mod = meshy_mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = target_arm

    # Clear any existing parent
    if meshy_mesh.parent:
        bpy.ops.object.select_all(action="DESELECT")
        meshy_mesh.select_set(True)
        bpy.context.view_layer.objects.active = meshy_mesh
        bpy.ops.object.parent_clear(type="CLEAR")

    meshy_mesh.parent = target_arm
    meshy_mesh.matrix_parent_inverse = Matrix.Identity(4)
    meshy_mesh.matrix_basis = Matrix.Identity(4)

    bpy.context.view_layer.update()

    # ------------------------------------------------------------------
    # Clean scene: keep only meshy mesh + armature
    # ------------------------------------------------------------------
    keep = {meshy_mesh.name}
    if target_arm:
        keep.add(target_arm.name)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
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
    print(f"  Exported → {out_path}")
    sys.stdout.flush()


print("Starting weight_green_ranged_armor.py ...")
sys.stdout.flush()

only = None
for arg in sys.argv:
    if arg.startswith("--only="):
        only = arg.split("=", 1)[1]

for piece in PIECES:
    if only and piece["name"] != only:
        continue
    process_piece(piece)

print(f"\n{'='*60}")
print("All pieces processed!")
print(f"{'='*60}")
sys.stdout.flush()
