"""
weight_test_upperbody.py
========================
Weights a Meshy-generated upper body GLB to the BaseFemaleV2 armature.
Auto-aligns the Meshy mesh to the body via bounding-box matching, then
creates a properly parented mesh object (duplicated from body_ref to
inherit armature transform) and transfers bone weights via KD-tree.

Covers: upper_torso, lower_torso, arm_upper, arm_lower

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_test_upperbody.py
"""

import os
import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
EQUIPMENT_GLB = os.path.abspath(
    "viewer/public/equipment/Female/Upperbody/TestUpperBody.glb"
)
OUT_PATH = os.path.abspath(
    "viewer/public/equipment/Female/Upperbody/test_upperbody_weighted.glb"
)

BODY_REGIONS = [
    "base_body_arm_upper",
    "base_body_arm_lower",
    "base_body_upper_torso",
    "base_body_lower_torso",
]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER = 1.5


def world_bbox(obj):
    """Return (min_vec, max_vec) bounding box in world space."""
    verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


# ── 1. Load BaseFemaleV2 (armature + weight reference) ──────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
print(f"Loaded {len(region_meshes)} body region meshes from BaseFemaleV2")

# ── 2. Load the Meshy equipment GLB ─────────────────────────────────────────
bpy.ops.import_scene.gltf(filepath=EQUIPMENT_GLB)
bpy.context.view_layer.update()

imported_armatures = [
    o for o in bpy.data.objects if o.type == "ARMATURE" and o != armature
]
equip_meshes = [
    o
    for o in bpy.data.objects
    if o.type == "MESH" and o.name not in region_meshes and len(o.data.vertices) > 10
]

print(f"Equipment meshes found: {len(equip_meshes)}")
for m in equip_meshes:
    print(f"  {m.name}: {len(m.data.vertices)} verts, {len(m.data.polygons)} faces")

if len(equip_meshes) > 1:
    bpy.ops.object.select_all(action="DESELECT")
    for m in equip_meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = equip_meshes[0]
    bpy.ops.object.join()
    equip_src = bpy.context.active_object
    print(f"Joined into single mesh: {len(equip_src.data.vertices)} verts")
else:
    equip_src = equip_meshes[0]

print(
    f"Equipment source: {equip_src.name} "
    f"({len(equip_src.data.vertices)} verts, "
    f"{len(equip_src.data.polygons)} faces)"
)
print(f"  Materials: {[m.name for m in equip_src.data.materials]}")

for arm in imported_armatures:
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.delete(use_global=False)

# ── 3. Build joined body reference for weight transfer ──────────────────────
copies = []
for rname in BODY_REGIONS:
    src = region_meshes.get(rname)
    if not src:
        print(f"  WARNING: {rname} not found, skipping")
        continue
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    bpy.ops.object.duplicate(linked=False)
    copies.append(bpy.context.active_object)

bpy.ops.object.select_all(action="DESELECT")
for c in copies:
    c.select_set(True)
bpy.context.view_layer.objects.active = copies[0]
bpy.ops.object.join()
body_ref = bpy.context.active_object
body_ref.name = "body_ref_temp"
print(
    f"Body reference: {len(body_ref.data.vertices)} verts, "
    f"{len(body_ref.vertex_groups)} vertex groups"
)

# ── 4. Compute alignment transform (Meshy world → body world) ──────────────
body_min, body_max = world_bbox(body_ref)
equip_min, equip_max = world_bbox(equip_src)

body_size = body_max - body_min
equip_size = equip_max - equip_min
body_center = (body_min + body_max) / 2.0
equip_center = (equip_min + equip_max) / 2.0

scale_x = body_size.x / equip_size.x if equip_size.x > 1e-6 else 1.0
uniform_scale = scale_x
print(f"\nBody  bbox: size=({body_size.x:.4f}, {body_size.y:.4f}, {body_size.z:.4f})")
print(f"Equip bbox: size=({equip_size.x:.4f}, {equip_size.y:.4f}, {equip_size.z:.4f})")
print(f"Uniform scale: {uniform_scale:.4f}")

# ── 5. Duplicate body_ref to inherit armature binding ───────────────────────
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.duplicate(linked=False)
upperbody = bpy.context.active_object
upperbody.name = "test_upperbody"
upperbody.data.name = "test_upperbody"

dst_mat_inv = upperbody.matrix_world.inverted()

# ── 6. Replace geometry with aligned Meshy mesh ────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
upperbody.select_set(True)
bpy.context.view_layer.objects.active = upperbody
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(upperbody.data)
bmesh.ops.delete(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], context="VERTS")

equip_mat = equip_src.matrix_world
vert_map = {}
for i, v in enumerate(equip_src.data.vertices):
    world_co = equip_mat @ v.co
    aligned_world = (world_co - equip_center) * uniform_scale + body_center
    local_co = dst_mat_inv @ aligned_world
    new_v = bm.verts.new(local_co)
    vert_map[i] = new_v

bm.verts.ensure_lookup_table()

for poly in equip_src.data.polygons:
    face_verts = [vert_map[vi] for vi in poly.vertices]
    try:
        bm.faces.new(face_verts)
    except ValueError:
        pass

bm.normal_update()
for f in bm.faces:
    f.smooth = True

bmesh.update_edit_mesh(upperbody.data)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()

print(f"Upperbody mesh: {len(upperbody.data.vertices)} verts, "
      f"{len(upperbody.data.polygons)} faces")

# ── 7. Transfer material from Meshy mesh ────────────────────────────────────
upperbody.data.materials.clear()
for mat in equip_src.data.materials:
    upperbody.data.materials.append(mat)
print(f"Materials transferred: {[m.name for m in upperbody.data.materials]}")

# ── 8. Transfer UVs from Meshy mesh via vertex mapping ──────────────────────
src_uv = equip_src.data.uv_layers.active
if src_uv:
    src_vert_uvs = {}
    for poly in equip_src.data.polygons:
        for vi, loop_idx in zip(poly.vertices, poly.loop_indices):
            uv = src_uv.data[loop_idx].uv
            if vi not in src_vert_uvs:
                src_vert_uvs[vi] = [uv.copy(), 1]
            else:
                src_vert_uvs[vi][0] += uv
                src_vert_uvs[vi][1] += 1
    for vi in src_vert_uvs:
        src_vert_uvs[vi] = src_vert_uvs[vi][0] / src_vert_uvs[vi][1]

    if not upperbody.data.uv_layers:
        upperbody.data.uv_layers.new(name="UVMap")
    dst_uv = upperbody.data.uv_layers.active

    for poly in upperbody.data.polygons:
        for vi, loop_idx in zip(poly.vertices, poly.loop_indices):
            if vi in src_vert_uvs:
                dst_uv.data[loop_idx].uv = src_vert_uvs[vi]
            else:
                dst_uv.data[loop_idx].uv = (0.0, 0.0)
    print("UV coordinates transferred")
else:
    print("WARNING: No UV layer on source mesh")

# ── 9. Transfer weights via KD-tree ─────────────────────────────────────────
for vg in upperbody.vertex_groups:
    vg.remove(range(len(upperbody.data.vertices)))

kd = KDTree(len(body_ref.data.vertices))
for i, v in enumerate(body_ref.data.vertices):
    kd.insert(v.co, i)
kd.balance()

transferred = 0
for rv_idx, rv in enumerate(upperbody.data.vertices):
    neighbors = kd.find_n(rv.co, WEIGHT_NEIGHBORS)

    inv_weights = []
    for co, idx, dist in neighbors:
        w = 1.0 / (dist**WEIGHT_POWER + 1e-8)
        inv_weights.append((idx, w))

    total_inv = sum(w for _, w in inv_weights)

    blended = {}
    for body_idx, inv_w in inv_weights:
        factor = inv_w / total_inv
        bv = body_ref.data.vertices[body_idx]
        for g in bv.groups:
            bw = g.weight
            if bw > 0.0001:
                vg_name = body_ref.vertex_groups[g.group].name
                blended[vg_name] = blended.get(vg_name, 0.0) + bw * factor

    wtotal = sum(blended.values())
    if wtotal > 0:
        for name, w in blended.items():
            nw = w / wtotal
            if nw > 0.0001:
                upperbody.vertex_groups[name].add([rv_idx], nw, "REPLACE")
                transferred += 1

print(f"Transferred {transferred} blended weight entries")

# ── 10. Clean up ────────────────────────────────────────────────────────────
for obj in [body_ref, equip_src]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.delete(use_global=False)

for obj in list(bpy.data.objects):
    if obj == upperbody or obj == armature:
        continue
    if obj.name in region_meshes:
        continue
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.delete(use_global=False)

# ── 11. Export ──────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
upperbody.select_set(True)
if armature:
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

bpy.ops.export_scene.gltf(
    filepath=OUT_PATH,
    export_format="GLB",
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_skins=True,
    export_all_influences=True,
    export_def_bones=True,
    export_animations=False,
    export_materials="EXPORT",
    export_texcoords=True,
    export_image_format="AUTO",
)

print(f"\nWeighted equipment exported: {OUT_PATH}")
print(f"  Vertices: {len(upperbody.data.vertices)}")
print(f"  Faces:    {len(upperbody.data.polygons)}")
