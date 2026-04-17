"""
weight_upperbody_v1.py
======================
Takes an imported upperbody mesh (no bones, no weights, wrong scale)
and fits it onto the Female V2 character by:
  1. Scaling + translating to match the combined body region bounds
  2. Transferring bone weights via N-nearest KD-tree blending
  3. Parenting to the armature (using the body_ref duplication trick)
  4. Re-exporting as a properly skinned GLB

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_upperbody_v1.py
"""

import os
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

BASE_GLB = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
IMPORTED_GLB = os.path.abspath("viewer/public/equipment/Female/Upperbody/upperbodytest2.glb")
OUT_PATH = os.path.abspath("viewer/public/equipment/Female/Upperbody/upperbody_weighted.glb")

BODY_REGIONS = [
    "base_body_arm_upper",
    "base_body_upper_torso",
    "base_body_lower_torso",
]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER     = 1.5

IMPORTED_MESH_NAME = "Mesh_0"

# ── 1. Load BaseFemaleV2 ─────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=BASE_GLB)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

print(f"Loaded {len(region_meshes)} body region meshes")

# ── 2. Compute combined body region bounding box (world space) ────────────────
body_world_verts = []
for rname in BODY_REGIONS:
    obj = region_meshes.get(rname)
    if obj:
        body_world_verts.extend([obj.matrix_world @ v.co for v in obj.data.vertices])

body_min = Vector((
    min(v.x for v in body_world_verts),
    min(v.y for v in body_world_verts),
    min(v.z for v in body_world_verts),
))
body_max = Vector((
    max(v.x for v in body_world_verts),
    max(v.y for v in body_world_verts),
    max(v.z for v in body_world_verts),
))
body_size = body_max - body_min
body_center = (body_min + body_max) / 2

print(f"Body bounds: min={body_min}, max={body_max}")
print(f"Body size: {body_size}, center: {body_center}")

# ── 3. Load imported mesh ─────────────────────────────────────────────────────
bpy.ops.import_scene.gltf(filepath=IMPORTED_GLB)
bpy.context.view_layer.update()

imported = bpy.data.objects.get(IMPORTED_MESH_NAME)
if not imported:
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.name not in region_meshes:
            if len(obj.data.vertices) > 100:
                imported = obj
                break

if not imported:
    raise RuntimeError("Could not find imported mesh!")

print(f"Imported mesh: {imported.name} ({len(imported.data.vertices)} verts, {len(imported.data.polygons)} faces)")
print(f"  Materials: {[m.name for m in imported.data.materials]}")

# Apply any existing transforms
bpy.ops.object.select_all(action="DESELECT")
imported.select_set(True)
bpy.context.view_layer.objects.active = imported
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Compute imported mesh bounding box (now in world space after apply)
imp_verts = [v.co.copy() for v in imported.data.vertices]
imp_min = Vector((min(v.x for v in imp_verts), min(v.y for v in imp_verts), min(v.z for v in imp_verts)))
imp_max = Vector((max(v.x for v in imp_verts), max(v.y for v in imp_verts), max(v.z for v in imp_verts)))
imp_size = imp_max - imp_min
imp_center = (imp_min + imp_max) / 2

print(f"Imported bounds: min={imp_min}, max={imp_max}")
print(f"Imported size: {imp_size}, center: {imp_center}")

# ── 4. Compute uniform scale and offset ───────────────────────────────────────
scale_z = body_size.z / imp_size.z if imp_size.z > 0.001 else 1.0
scale = scale_z
print(f"Uniform scale factor: {scale:.6f}")

# ── 5. Create joined body reference for weight transfer ───────────────────────
copies = []
for rname in BODY_REGIONS:
    src = region_meshes.get(rname)
    if not src:
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

print(f"Body reference: {len(body_ref.data.vertices)} verts, {len([vg.name for vg in body_ref.vertex_groups])} vertex groups")

# ── 6. Duplicate body_ref to inherit correct armature binding ─────────────────
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.duplicate(linked=False)
upperbody = bpy.context.active_object
upperbody.name = "upperbody_v1"
upperbody.data.name = "upperbody_v1"

mat_inv = upperbody.matrix_world.inverted()

# ── 7. Replace geometry with scaled+translated imported mesh ──────────────────
bpy.ops.object.select_all(action="DESELECT")
upperbody.select_set(True)
bpy.context.view_layer.objects.active = upperbody
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(upperbody.data)
bmesh.ops.delete(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], context="VERTS")

# Read imported mesh data and transform vertices:
# world_pos = imported_local * scale + (body_center - imp_center * scale)
offset = body_center - imp_center * scale

imp_mesh = imported.data
vert_map = {}
for i, v in enumerate(imp_mesh.vertices):
    world_pos = v.co * scale + offset
    local_pos = mat_inv @ world_pos
    new_v = bm.verts.new(local_pos)
    vert_map[i] = new_v

bm.verts.ensure_lookup_table()

# Copy faces
for poly in imp_mesh.polygons:
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

print(f"Upperbody mesh: {len(upperbody.data.vertices)} verts, {len(upperbody.data.polygons)} faces")

# ── 8. Transfer material from imported mesh ───────────────────────────────────
upperbody.data.materials.clear()
for mat in imp_mesh.materials:
    upperbody.data.materials.append(mat)
print(f"Materials transferred: {[m.name for m in upperbody.data.materials]}")

# ── 9. Transfer UV coordinates ────────────────────────────────────────────────
if imp_mesh.uv_layers:
    src_uv = imp_mesh.uv_layers.active
    if not upperbody.data.uv_layers:
        upperbody.data.uv_layers.new(name=src_uv.name)
    dst_uv = upperbody.data.uv_layers.active

    for poly_idx, poly in enumerate(imp_mesh.polygons):
        if poly_idx < len(upperbody.data.polygons):
            dst_poly = upperbody.data.polygons[poly_idx]
            for i, loop_idx in enumerate(poly.loop_indices):
                if i < len(dst_poly.loop_indices):
                    dst_loop_idx = dst_poly.loop_indices[i]
                    dst_uv.data[dst_loop_idx].uv = src_uv.data[loop_idx].uv
    print(f"UV coordinates transferred from '{src_uv.name}'")

# ── 10. Smooth weight transfer via N-nearest blending ─────────────────────────
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
        w = 1.0 / (dist ** WEIGHT_POWER + 1e-8)
        inv_weights.append((idx, w))

    total_inv = sum(w for _, w in inv_weights)

    blended = {}
    for body_idx, inv_w in inv_weights:
        factor = inv_w / total_inv
        for vg in body_ref.vertex_groups:
            try:
                bw = vg.weight(body_idx)
            except RuntimeError:
                continue
            if bw > 0.0001:
                blended[vg.name] = blended.get(vg.name, 0.0) + bw * factor

    wtotal = sum(blended.values())
    if wtotal > 0:
        for name, w in blended.items():
            nw = w / wtotal
            if nw > 0.0001:
                upperbody.vertex_groups[name].add([rv_idx], nw, 'REPLACE')
                transferred += 1

print(f"Transferred {transferred} blended weight entries")

# ── 11. Clean up ──────────────────────────────────────────────────────────────
for obj in [body_ref, imported]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.delete(use_global=False)

# Delete stray Icosphere if present
ico = bpy.data.objects.get("Icosphere")
if ico:
    bpy.ops.object.select_all(action="DESELECT")
    ico.select_set(True)
    bpy.context.view_layer.objects.active = ico
    bpy.ops.object.delete(use_global=False)

# ── 12. Export ────────────────────────────────────────────────────────────────
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

print(f"\nUpperbody exported: {OUT_PATH}")
print(f"  Vertices: {len(upperbody.data.vertices)}")
print(f"  Faces:    {len(upperbody.data.polygons)}")
