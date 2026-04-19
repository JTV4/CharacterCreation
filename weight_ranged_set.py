"""
weight_ranged_set.py
====================
Generic return-trip script for Ranged Armor sets (Green / Purple / Black /
Red / Blue).  Processes Meshy-textured GLB pieces and produces
*Weighted.glb  outputs ready to drop into  viewer/public/equipment/Female/.

Piece types supported:
  - "hat"       → 48-combo axis calibration + 100% head-bone weighting
  - "upperbody" → 48-combo axis calibration + KD weight transfer
  - "lowerbody" → 48-combo axis calibration + KD weight transfer
  - "boots"     → 48-combo axis calibration + KD weight transfer

Gloves use the separate bilateral pipeline (`weight_meshy_gloves.py`).

Non-destructive:  Inputs are read from `<Piece>.glb` and outputs are written
to `<Piece>Weighted.glb`.  The Meshy source file is never overwritten.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_ranged_set.py
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_ranged_set.py -- --only=green_ranged_hat
"""

import os
import sys
import itertools
import bpy
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

sys.stdout.reconfigure(line_buffering=True)

BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")

EQUIP_DIR = os.path.abspath("viewer/public/equipment/Female")


def _piece(color_id: str, color_name: str, piece_type: str, subfolder: str, file_base: str, regions):
    """Build a piece dict.
    color_id   e.g. 'green', used in slot id:  <color>_ranged_<piece_type>
    file_base  e.g. 'GreenRangedHat'  → source  .glb, output  Weighted.glb.
    """
    src = os.path.join(EQUIP_DIR, subfolder, f"{file_base}.glb")
    out = os.path.join(EQUIP_DIR, subfolder, f"{file_base}Weighted.glb")
    return {
        "name":       f"{color_id}_ranged_{piece_type}",
        "display":    f"{color_name} Ranged: {piece_type.capitalize()}",
        "piece_type": piece_type,
        "src":        src,
        "out":        out,
        "regions":    regions,
    }


REGIONS = {
    "hat":       ["base_body_head"],
    "upperbody": [
        "base_body_upper_torso",
        "base_body_lower_torso",
        "base_body_arm_upper",
        "base_body_arm_lower",
    ],
    "lowerbody": [
        "base_body_leg_upper",
        "base_body_leg_thigh",
        "base_body_leg_knee",
        "base_body_leg_shin",
        "base_body_leg_ankle",
    ],
    "boots": [
        "base_body_foot",
        "base_body_leg_ankle",
    ],
}


def _set(color_id: str, color_name: str):
    """Return the 4 pieces (hat/upper/lower/boots) for one colour."""
    return [
        _piece(color_id, color_name, "hat",       "Hats",      f"{color_name}RangedHat",       REGIONS["hat"]),
        _piece(color_id, color_name, "upperbody", "Upperbody", f"{color_name}RangedUpperbody", REGIONS["upperbody"]),
        _piece(color_id, color_name, "lowerbody", "Lowerbody", f"{color_name}RangedLowerbody", REGIONS["lowerbody"]),
        _piece(color_id, color_name, "boots",     "Boots",     f"{color_name}RangedBoots",     REGIONS["boots"]),
    ]


PIECES = []
PIECES += _set("green",  "Green")
# Future: uncomment once the Meshy GLBs are dropped in.
# PIECES += _set("purple", "Purple")
# PIECES += _set("black",  "Black")
# PIECES += _set("red",    "Red")
# PIECES += _set("blue",   "Blue")


WEIGHT_NEIGHBORS = 12
WEIGHT_POWER = 1.5
MAX_INFLUENCES = 4


# ----------------------------------------------------------------------
# Low-level utilities (lifted verbatim from weight_green_ranged_armor.py)
# ----------------------------------------------------------------------

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

    print(f"  Body bounds:  X=[{b_min.x:.1f},{b_max.x:.1f}] "
          f"Y=[{b_min.y:.1f},{b_max.y:.1f}] Z=[{b_min.z:.1f},{b_max.z:.1f}]")
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
    print(f"  Best axis mapping: body[XYZ] ← meshy[{perm_str}], signs: {sign_str}")
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
    print(f"  Remapped bounds: X=[{mbx[0]:.1f},{mbx[1]:.1f}] "
          f"Y=[{mby[0]:.1f},{mby[1]:.1f}] Z=[{mbz[0]:.1f},{mbz[1]:.1f}]")
    sys.stdout.flush()
    return True


def find_head_bone(arm):
    """Return the name of the head bone in the armature, or None."""
    for pb in arm.pose.bones:
        if pb.name.lower() in ("head", "mixamorighead"):
            return pb.name
    for pb in arm.pose.bones:
        if "head" in pb.name.lower() and "fore" not in pb.name.lower():
            return pb.name
    return None


def place_hat_on_head(hat_mesh, head_regions):
    """
    Uniform-scale placement for hats.  Unlike  `remap_meshy_to_body`  (which
    anisotropically stretches a piece into a body-region bbox), a hat has a
    shape that is completely unlike a head (wide brim, short crown), so
    per-axis fitting mangles its proportions and rotates it wrong.

    Heuristic:
      - The shortest Meshy extent is the CROWN axis (vertical on the head).
      - Of the remaining two, the longest is the brim WIDTH (body X).
      - The middle is the brim DEPTH (body Z).
      - Brim end is where vertex radial spread (in the 2 horizontal axes) is
        LARGER than at the opposite end;  it must end up at the BOTTOM
        (lowest body Y) so the hat opens downwards onto the head.

    Scale is uniform, chosen so the brim is ~1.5× the head's X width (typical
    fedora/ball-cap brim sticks out past the head).  The hat is then
    translated so the brim rests on top of the head (small overlap).
    """
    verts = hat_mesh.data.vertices
    if len(verts) == 0:
        return False

    m_xs = [v.co.x for v in verts]
    m_ys = [v.co.y for v in verts]
    m_zs = [v.co.z for v in verts]
    m_range = Vector((max(m_xs) - min(m_xs),
                      max(m_ys) - min(m_ys),
                      max(m_zs) - min(m_zs)))

    if max(m_range) > 5.0:
        print(f"  Hat: mesh in body scale (max {max(m_range):.1f}), normalizing first")
        normalize_mesh(hat_mesh)
        verts = hat_mesh.data.vertices
        m_xs = [v.co.x for v in verts]
        m_ys = [v.co.y for v in verts]
        m_zs = [v.co.z for v in verts]
        m_range = Vector((max(m_xs) - min(m_xs),
                          max(m_ys) - min(m_ys),
                          max(m_zs) - min(m_zs)))

    m_min = Vector((min(m_xs), min(m_ys), min(m_zs)))
    m_max = Vector((max(m_xs), max(m_ys), max(m_zs)))
    m_center = (m_min + m_max) / 2

    axes_by_ext = sorted([(0, m_range.x), (1, m_range.y), (2, m_range.z)],
                         key=lambda a: a[1])
    crown_ax      = axes_by_ext[0][0]
    brim_short_ax = axes_by_ext[1][0]
    brim_long_ax  = axes_by_ext[2][0]

    h_xs, h_ys, h_zs = [], [], []
    for obj in head_regions:
        for v in obj.data.vertices:
            h_xs.append(v.co.x); h_ys.append(v.co.y); h_zs.append(v.co.z)
    if not h_xs:
        print("  Hat: ERROR no head region verts")
        return False
    h_min = Vector((min(h_xs), min(h_ys), min(h_zs)))
    h_max = Vector((max(h_xs), max(h_ys), max(h_zs)))
    h_range = h_max - h_min
    h_center_x = (h_min.x + h_max.x) / 2
    h_center_z = (h_min.z + h_max.z) / 2

    scale = (h_range.x * 1.5) / m_range[brim_long_ax]

    c_vals = [v.co[crown_ax] for v in verts]
    c_min, c_max = min(c_vals), max(c_vals)
    c_mid = (c_min + c_max) / 2
    low_sum, low_n = 0.0, 0
    high_sum, high_n = 0.0, 0
    for v in verts:
        c_val = v.co[crown_ax]
        dx = v.co[brim_long_ax]  - m_center[brim_long_ax]
        dz = v.co[brim_short_ax] - m_center[brim_short_ax]
        r = (dx * dx + dz * dz) ** 0.5
        if c_val < c_mid:
            low_sum += r; low_n += 1
        else:
            high_sum += r; high_n += 1
    avg_low  = low_sum  / max(1, low_n)
    avg_high = high_sum / max(1, high_n)
    crown_sign = 1 if avg_low > avg_high else -1

    if crown_sign > 0:
        brim_end_val = c_min
    else:
        brim_end_val = c_max

    overlap = 1.5
    brim_target_body_y = h_max.y - overlap
    y_offset = brim_target_body_y - (brim_end_val - m_center[crown_ax]) * crown_sign * scale

    for v in verts:
        o = v.co.copy()
        new_x = (o[brim_long_ax]  - m_center[brim_long_ax])  * scale + h_center_x
        new_y = (o[crown_ax]      - m_center[crown_ax])      * crown_sign * scale + y_offset
        new_z = (o[brim_short_ax] - m_center[brim_short_ax]) * scale + h_center_z
        v.co = Vector((new_x, new_y, new_z))
    hat_mesh.data.update()

    ax_names = "XYZ"
    bx, by, bz = local_bounds(hat_mesh)
    print(f"  Hat axes: crown=meshy[{ax_names[crown_ax]}] (sign {crown_sign:+d}),  "
          f"brim_wide=meshy[{ax_names[brim_long_ax]}],  brim_depth=meshy[{ax_names[brim_short_ax]}]")
    print(f"  Radial spread @ crown low/high ends: {avg_low:.3f} / {avg_high:.3f}  "
          f"→ brim placed at {'low' if crown_sign > 0 else 'high'} end (bottom)")
    print(f"  Uniform scale: {scale:.2f}  (brim ≈ 1.5× head width)")
    print(f"  Hat placed:  X=[{bx[0]:.1f},{bx[1]:.1f}]  "
          f"Y=[{by[0]:.1f},{by[1]:.1f}]  Z=[{bz[0]:.1f},{bz[1]:.1f}]")
    print(f"  (Head top at Y={h_max.y:.1f}, hat brim at Y={by[0]:.1f})")
    sys.stdout.flush()
    return True


def assign_hat_weights(meshy_mesh, arm):
    """Assign 100% weight on the head bone to every vertex of the hat mesh."""
    head_bone_name = find_head_bone(arm)
    if not head_bone_name:
        raise RuntimeError("Could not find head bone in rig for hat weighting")
    vg = meshy_mesh.vertex_groups.new(name=head_bone_name)
    idx_list = [v.index for v in meshy_mesh.data.vertices]
    vg.add(idx_list, 1.0, "REPLACE")
    print(f"  Hat: assigned 100% weight to '{head_bone_name}' "
          f"({len(idx_list)} verts)")
    sys.stdout.flush()


def assign_kd_weights(meshy_mesh, regions, region_meshes):
    """Transfer weights from the listed body regions via KD-tree nearest-N."""
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


def process_piece(piece):
    piece_name = piece["name"]
    piece_type = piece["piece_type"]
    src_path = piece["src"]
    out_path = piece["out"]
    regions = piece["regions"]

    print(f"\n{'='*60}")
    print(f"Processing: {piece_name}  ({piece_type})")
    sys.stdout.flush()

    if not os.path.exists(src_path):
        print(f"  SKIP: source not found → {src_path}")
        return

    bpy.ops.wm.read_factory_settings(use_empty=True)

    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
    bpy.context.view_layer.update()
    restore(s, dn)

    base_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if base_arm is None:
        print(f"  ERROR: No armature in BaseFemaleV2")
        return
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
        print(f"  ERROR: No mesh found")
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
        print(f"  ERROR: None of the required regions found: {regions}")
        return

    if piece_type == "hat":
        placed = place_hat_on_head(meshy_mesh, body_objs)
        if not placed:
            print("  ERROR: Hat placement failed")
            return
    else:
        remapped = remap_meshy_to_body(meshy_mesh, body_objs)
        if not remapped:
            print("  WARNING: Mesh was not remapped — may already be in body scale")

    meshy_mesh.vertex_groups.clear()
    for mod in list(meshy_mesh.modifiers):
        if mod.type == "ARMATURE":
            meshy_mesh.modifiers.remove(mod)

    if piece_type == "hat":
        assign_hat_weights(meshy_mesh, base_arm)
    else:
        assign_kd_weights(meshy_mesh, regions, region_meshes)

    mod = meshy_mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = base_arm

    if meshy_mesh.parent:
        bpy.ops.object.select_all(action="DESELECT")
        meshy_mesh.select_set(True)
        bpy.context.view_layer.objects.active = meshy_mesh
        bpy.ops.object.parent_clear(type="CLEAR")

    meshy_mesh.parent = base_arm
    meshy_mesh.matrix_parent_inverse = Matrix.Identity(4)
    meshy_mesh.matrix_basis = Matrix.Identity(4)

    bpy.context.view_layer.update()

    keep = {meshy_mesh.name, base_arm.name}
    bpy.ops.object.select_all(action="DESELECT")
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    bpy.ops.object.select_all(action="DESELECT")
    meshy_mesh.select_set(True)
    base_arm.select_set(True)
    bpy.context.view_layer.objects.active = base_arm

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


print("Starting weight_ranged_set.py ...")
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
