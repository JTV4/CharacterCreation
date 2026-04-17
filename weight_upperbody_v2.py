"""
weight_upperbody_v2.py
======================
Takes the original base shell mesh (correct geometry, no holes) and applies:
  1. The texture/material from the Meshy-processed weighted mesh
  2. UV transfer via nearest-surface projection
  3. Bone weights via N-nearest KD-tree blending
  4. Proper armature parenting

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_upperbody_v2.py
"""

import os
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
BASE_MESH_GLB = os.path.abspath("viewer/public/equipment/Female/Upperbody/Upperbody.glb 2")
TEXTURED_GLB = os.path.abspath("viewer/public/equipment/Female/Upperbody/upperbody_weighted.glb")
OUT_PATH = os.path.abspath("viewer/public/equipment/Female/Upperbody/upperbody_weighted.glb")

BODY_REGIONS = [
    "base_body_arm_upper",
    "base_body_upper_torso",
    "base_body_lower_torso",
]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER     = 1.5

# ── 1. Load BaseFemaleV2 (for armature + weight reference) ───────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
print(f"Loaded {len(region_meshes)} body region meshes")

# ── 2. Load the clean base mesh ──────────────────────────────────────────────
bpy.ops.import_scene.gltf(filepath=BASE_MESH_GLB)
bpy.context.view_layer.update()

base_mesh = None
for obj in bpy.data.objects:
    if obj.type == "MESH" and obj.name not in region_meshes:
        if len(obj.data.vertices) > 100:
            base_mesh = obj
            break

print(f"Base mesh: {base_mesh.name} ({len(base_mesh.data.vertices)} verts, {len(base_mesh.data.polygons)} faces)")

# ── 3. Load the textured mesh (for material + UV source) ─────────────────────
bpy.ops.import_scene.gltf(filepath=TEXTURED_GLB)
bpy.context.view_layer.update()

tex_mesh = None
for obj in bpy.data.objects:
    if obj.type == "MESH" and obj.name not in region_meshes and obj != base_mesh:
        if len(obj.data.vertices) > 100:
            tex_mesh = obj
            break

print(f"Textured mesh: {tex_mesh.name} ({len(tex_mesh.data.vertices)} verts, {len(tex_mesh.data.polygons)} faces)")
print(f"  Materials: {[m.name for m in tex_mesh.data.materials]}")

# ── 4. Create joined body reference for weight transfer ──────────────────────
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

# ── 5. Duplicate body_ref to inherit armature binding ────────────────────────
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.duplicate(linked=False)
upperbody = bpy.context.active_object
upperbody.name = "upperbody_v1"
upperbody.data.name = "upperbody_v1"

mat_inv = upperbody.matrix_world.inverted()

# ── 6. Replace geometry with the base mesh geometry ──────────────────────────
bpy.ops.object.select_all(action="DESELECT")
upperbody.select_set(True)
bpy.context.view_layer.objects.active = upperbody
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(upperbody.data)
bmesh.ops.delete(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], context="VERTS")

# The base mesh is already at the correct scale/position (same as body regions)
# Transform from base mesh world space to upperbody local space
base_mat = base_mesh.matrix_world
vert_map = {}
for i, v in enumerate(base_mesh.data.vertices):
    world_pos = base_mat @ v.co
    local_pos = mat_inv @ world_pos
    new_v = bm.verts.new(local_pos)
    vert_map[i] = new_v

bm.verts.ensure_lookup_table()

for poly in base_mesh.data.polygons:
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

# ── 7. Transfer material from textured mesh ──────────────────────────────────
upperbody.data.materials.clear()
for mat in tex_mesh.data.materials:
    upperbody.data.materials.append(mat)
print(f"Materials transferred: {[m.name for m in upperbody.data.materials]}")

# ── 8. Transfer UVs from textured mesh via nearest-surface projection ────────
# Build KD-tree from textured mesh vertices (world space)
tex_kd = KDTree(len(tex_mesh.data.vertices))
tex_world_cos = []
for i, v in enumerate(tex_mesh.data.vertices):
    wco = tex_mesh.matrix_world @ v.co
    tex_kd.insert(wco, i)
    tex_world_cos.append(wco)
tex_kd.balance()

# Build a mapping: for each base mesh vertex, find nearest textured mesh vertex
base_to_tex = {}
for i, v in enumerate(base_mesh.data.vertices):
    wco = base_mat @ v.co
    _, tex_idx, _ = tex_kd.find(wco)
    base_to_tex[i] = tex_idx

# Get UV data from textured mesh
tex_uv = tex_mesh.data.uv_layers.active
if not tex_uv:
    print("WARNING: No UV layer on textured mesh!")
else:
    # Build per-vertex UV from textured mesh (average of all loop UVs for each vert)
    tex_vert_uvs = {}
    for poly in tex_mesh.data.polygons:
        for vi, loop_idx in zip(poly.vertices, poly.loop_indices):
            uv = tex_uv.data[loop_idx].uv
            if vi not in tex_vert_uvs:
                tex_vert_uvs[vi] = [uv.copy(), 1]
            else:
                tex_vert_uvs[vi][0] += uv
                tex_vert_uvs[vi][1] += 1

    for vi in tex_vert_uvs:
        tex_vert_uvs[vi] = tex_vert_uvs[vi][0] / tex_vert_uvs[vi][1]

    # Apply UVs to upperbody
    if not upperbody.data.uv_layers:
        upperbody.data.uv_layers.new(name="UVMap")
    dst_uv = upperbody.data.uv_layers.active

    for poly in upperbody.data.polygons:
        for vi, loop_idx in zip(poly.vertices, poly.loop_indices):
            tex_vi = base_to_tex.get(vi, 0)
            if tex_vi in tex_vert_uvs:
                dst_uv.data[loop_idx].uv = tex_vert_uvs[tex_vi]
            else:
                dst_uv.data[loop_idx].uv = (0.0, 0.0)

    print(f"UV coordinates transferred via nearest-vertex projection")

# ── 9. Smooth weight transfer ────────────────────────────────────────────────
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

# ── 10. Clean up ─────────────────────────────────────────────────────────────
for obj in [body_ref, base_mesh, tex_mesh]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.delete(use_global=False)

# Delete any stray objects from imports
for obj in list(bpy.data.objects):
    if obj.type == "MESH" and obj != upperbody and obj.name not in region_meshes:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.delete(use_global=False)
    elif obj.type == "ARMATURE" and obj != armature:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.delete(use_global=False)

# ── 11. Export ───────────────────────────────────────────────────────────────
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
