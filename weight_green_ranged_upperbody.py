"""
weight_green_ranged_upperbody.py
================================
Dedicated script to weight & scale the Green Ranged Upperbody mesh to the
BaseFemaleV2 character.

Uses a hard-coded axis mapping (XZY with signs +-+) determined by geometric
analysis and user feedback, rather than the brute-force search which picks
wrong orientations for T-pose shapes.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_green_ranged_upperbody.py
"""

import os
import sys
import bpy
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

sys.stdout.reconfigure(line_buffering=True)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
SRC_GLB    = os.path.abspath("viewer/public/equipment/Female/Upperbody/TexturedGreenRangedUpperBody.glb")
OUT_GLB    = os.path.abspath("viewer/public/equipment/Female/Upperbody/TexturedGreenRangedUpperBody.glb")

BODY_REGIONS = [
    "base_body_upper_torso",
    "base_body_lower_torso",
    "base_body_arm_upper",
    "base_body_arm_lower",
]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER     = 1.5
MAX_INFLUENCES   = 4

# Original brute-force best mapping: XZY with signs ++-
AXIS_PERM  = (0, 2, 1)   # body[XYZ] ← meshy[X,Z,Y]
AXIS_SIGNS = (1, 1, -1)  # signs: +, +, -


def suppress():
    dn = open(os.devnull, "w")
    s = os.dup(1)
    os.dup2(dn.fileno(), 1)
    return s, dn


def restore(s, dn):
    os.dup2(s, 1)
    os.close(s)
    dn.close()


def bbox(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def combined_bbox(objs):
    all_min = Vector((1e9, 1e9, 1e9))
    all_max = Vector((-1e9, -1e9, -1e9))
    for obj in objs:
        lo, hi = bbox(obj)
        for i in range(3):
            all_min[i] = min(all_min[i], lo[i])
            all_max[i] = max(all_max[i], hi[i])
    return all_min, all_max


def normalize_mesh(mesh_obj):
    """Normalize mesh vertices to [-1, 1] on the longest axis, centered at origin.
    This undoes any previous remapping so we start from a canonical form."""
    verts = mesh_obj.data.vertices
    if len(verts) == 0:
        return

    lo, hi = bbox(mesh_obj)
    center = (lo + hi) / 2
    extent = hi - lo
    max_extent = max(extent)

    if max_extent < 0.001:
        return

    scale = 2.0 / max_extent
    for v in verts:
        v.co = (v.co - center) * scale
    mesh_obj.data.update()


def remap_to_body(mesh_obj, body_objs):
    """Map the normalized [-1,1] mesh to body-region coordinates using
    the hard-coded axis mapping."""
    verts = mesh_obj.data.vertices
    if len(verts) == 0:
        return

    m_lo, m_hi = bbox(mesh_obj)
    m_center = (m_lo + m_hi) / 2
    m_range = m_hi - m_lo

    b_lo, b_hi = combined_bbox(body_objs)
    b_center = (b_lo + b_hi) / 2
    b_range = b_hi - b_lo

    meshy_sizes = [m_range.x, m_range.y, m_range.z]
    body_sizes  = [b_range.x, b_range.y, b_range.z]

    scales = [0.0, 0.0, 0.0]
    for body_ax in range(3):
        meshy_ax = AXIS_PERM[body_ax]
        br = body_sizes[body_ax]
        mr = meshy_sizes[meshy_ax]
        scales[body_ax] = br / mr if mr > 0.001 else 1.0

    axis_names = ["X", "Y", "Z"]
    perm_str = "".join(axis_names[AXIS_PERM[i]] for i in range(3))
    sign_str = "".join("+" if s > 0 else "-" for s in AXIS_SIGNS)
    print(f"  Axis mapping: body[XYZ] <- meshy[{perm_str}] signs={sign_str}")
    print(f"  Per-axis scales: [{scales[0]:.2f}, {scales[1]:.2f}, {scales[2]:.2f}]")
    print(f"  Meshy center: ({m_center.x:.4f}, {m_center.y:.4f}, {m_center.z:.4f})")
    print(f"  Body center:  ({b_center.x:.4f}, {b_center.y:.4f}, {b_center.z:.4f})")
    sys.stdout.flush()

    for v in verts:
        old = v.co.copy()
        new_co = Vector((0, 0, 0))
        for body_ax in range(3):
            meshy_ax = AXIS_PERM[body_ax]
            val = (old[meshy_ax] - m_center[meshy_ax]) * AXIS_SIGNS[body_ax]
            new_co[body_ax] = val * scales[body_ax] + b_center[body_ax]
        v.co = new_co
    mesh_obj.data.update()

    new_lo, new_hi = bbox(mesh_obj)
    print(f"  Remapped bounds: min=({new_lo.x:.4f},{new_lo.y:.4f},{new_lo.z:.4f}) "
          f"max=({new_hi.x:.4f},{new_hi.y:.4f},{new_hi.z:.4f})")


def transfer_weights(meshy_mesh, region_meshes, regions):
    meshy_mesh.vertex_groups.clear()
    for mod in list(meshy_mesh.modifiers):
        if mod.type == "ARMATURE":
            meshy_mesh.modifiers.remove(mod)

    all_positions = []
    all_weights = []
    for rname in regions:
        src = region_meshes.get(rname)
        if not src:
            print(f"  WARNING: Region '{rname}' not found in base model")
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
    if not all_positions:
        print("  ERROR: No body reference verts!")
        return False

    kd = KDTree(len(all_positions))
    for i, pos in enumerate(all_positions):
        kd.insert(pos, i)
    kd.balance()

    transferred = 0
    max_dist = 0.0
    total_dist = 0.0
    for rv_idx, rv in enumerate(meshy_mesh.data.vertices):
        neighbors = kd.find_n(rv.co, WEIGHT_NEIGHBORS)
        nearest_dist = neighbors[0][2] if neighbors else 0
        max_dist = max(max_dist, nearest_dist)
        total_dist += nearest_dist

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

    n_verts = len(meshy_mesh.data.vertices)
    avg_dist = total_dist / n_verts if n_verts > 0 else 0
    print(f"  Weight transfer: {transferred} entries across {n_verts} verts")
    print(f"  Vertex groups created: {len(meshy_mesh.vertex_groups)}")
    print(f"  Nearest-neighbor distances: avg={avg_dist:.6f}, max={max_dist:.6f}")
    vg_names_list = sorted([vg.name for vg in meshy_mesh.vertex_groups])
    print(f"  Groups: {vg_names_list}")
    sys.stdout.flush()
    return True


# ── Main ─────────────────────────────────────────────────────────────────────
print("=" * 60)
print("Weight Green Ranged Upperbody → BaseFemaleV2")
print("=" * 60)
print(f"Base model: {BASE_MODEL}")
print(f"Source:     {SRC_GLB}")
print(f"Output:     {OUT_GLB}")
sys.stdout.flush()

bpy.ops.wm.read_factory_settings(use_empty=True)

# Import base model
print("\n[1/6] Loading BaseFemaleV2...")
sys.stdout.flush()
s, dn = suppress()
bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
bpy.context.view_layer.update()
restore(s, dn)

base_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
print(f"  Armature: {base_arm.name if base_arm else 'NONE'}")

available_regions = [r for r in BODY_REGIONS if r in region_meshes]
missing_regions = [r for r in BODY_REGIONS if r not in region_meshes]
if missing_regions:
    print(f"  WARNING: Missing regions: {missing_regions}")
print(f"  Using regions: {available_regions}")
sys.stdout.flush()

body_objs = [region_meshes[r] for r in available_regions]

b_lo, b_hi = combined_bbox(body_objs)
b_range = b_hi - b_lo
print(f"  Body bounds: min=({b_lo.x:.1f},{b_lo.y:.1f},{b_lo.z:.1f}) "
      f"max=({b_hi.x:.1f},{b_hi.y:.1f},{b_hi.z:.1f})")
print(f"  Body range:  ({b_range.x:.1f},{b_range.y:.1f},{b_range.z:.1f})")

# Import Meshy piece
print("\n[2/6] Loading Green Ranged Upperbody mesh...")
sys.stdout.flush()
pre_import = {o.name for o in bpy.data.objects}
s, dn = suppress()
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
bpy.context.view_layer.update()
restore(s, dn)

new_objects = [o for o in bpy.data.objects if o.name not in pre_import]
imported_meshes = [o for o in new_objects if o.type == "MESH" and "Icosphere" not in o.name]
imported_armatures = [o for o in new_objects if o.type == "ARMATURE"]

if not imported_meshes:
    print("  ERROR: No mesh found in the GLB!")
    sys.exit(1)

if len(imported_meshes) > 1:
    print(f"  Joining {len(imported_meshes)} meshes...")
    bpy.ops.object.select_all(action="DESELECT")
    for m in imported_meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = imported_meshes[0]
    bpy.ops.object.join()
meshy_mesh = imported_meshes[0]

m_lo, m_hi = bbox(meshy_mesh)
print(f"  Mesh: '{meshy_mesh.name}' with {len(meshy_mesh.data.vertices)} verts")
print(f"  Raw bounds: min=({m_lo.x:.4f},{m_lo.y:.4f},{m_lo.z:.4f}) "
      f"max=({m_hi.x:.4f},{m_hi.y:.4f},{m_hi.z:.4f})")

# Normalize to [-1, 1] (undoes any previous remap)
print("\n[3/6] Normalizing mesh to canonical [-1,1] range...")
sys.stdout.flush()
normalize_mesh(meshy_mesh)
m_lo, m_hi = bbox(meshy_mesh)
m_range = m_hi - m_lo
print(f"  Normalized bounds: min=({m_lo.x:.4f},{m_lo.y:.4f},{m_lo.z:.4f}) "
      f"max=({m_hi.x:.4f},{m_hi.y:.4f},{m_hi.z:.4f})")
print(f"  Normalized range:  ({m_range.x:.4f},{m_range.y:.4f},{m_range.z:.4f})")

# Remap to body coordinates
print("\n[4/6] Remapping to body coordinates (hard-coded signs +-+)...")
sys.stdout.flush()
remap_to_body(meshy_mesh, body_objs)

# Transfer weights
print("\n[5/6] Transferring bone weights...")
sys.stdout.flush()
ok = transfer_weights(meshy_mesh, region_meshes, available_regions)
if not ok:
    print("  Weight transfer failed!")
    sys.exit(1)

# Parent to armature
print("\n[6/6] Parenting to armature and exporting...")
sys.stdout.flush()
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
    filepath=OUT_GLB,
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

print(f"\n  Exported → {OUT_GLB}")
print(f"\n{'='*60}")
print("Done! Green Ranged Upperbody weighted and exported.")
print(f"{'='*60}")
sys.stdout.flush()
