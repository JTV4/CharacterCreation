"""
repair_and_weight.py
====================
Takes a Meshy-textured mesh (which has holes from remeshing), repairs the
holes by filling boundary edge loops, transfers bone weights, and exports.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python repair_and_weight.py

Configure the paths and body regions below.
"""

import os
import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_MODEL     = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
MESHY_GLB      = os.path.abspath("viewer/public/equipment/Female/Upperbody/upperbodyTest3.glb")
OUT_PATH       = os.path.abspath("viewer/public/equipment/Female/Upperbody/upperbody_weighted.glb")

BODY_REGIONS = [
    "base_body_arm_upper",
    "base_body_upper_torso",
    "base_body_lower_torso",
]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER     = 1.5

# ── 1. Load BaseFemaleV2 ─────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
print(f"Loaded base model: {len(region_meshes)} body regions")

# ── 2. Load Meshy export ─────────────────────────────────────────────────────
pre_import = {o.name for o in bpy.data.objects}
bpy.ops.import_scene.gltf(filepath=MESHY_GLB)
bpy.context.view_layer.update()

meshy_mesh = None
for obj in bpy.data.objects:
    if obj.type == "MESH" and obj.name not in pre_import:
        if len(obj.data.vertices) > 100:
            meshy_mesh = obj
            break

if not meshy_mesh:
    raise RuntimeError("Could not find Meshy mesh after import")

print(f"Meshy mesh: {meshy_mesh.name} ({len(meshy_mesh.data.vertices)} verts, {len(meshy_mesh.data.polygons)} faces)")

# ── 3. Scale Meshy mesh to match body ────────────────────────────────────────
body_verts = []
for rname in BODY_REGIONS:
    src = region_meshes.get(rname)
    if src:
        body_verts.extend([src.matrix_world @ v.co for v in src.data.vertices])

body_min = Vector((min(v.x for v in body_verts), min(v.y for v in body_verts), min(v.z for v in body_verts)))
body_max = Vector((max(v.x for v in body_verts), max(v.y for v in body_verts), max(v.z for v in body_verts)))
body_size = body_max - body_min
body_center = (body_min + body_max) / 2

bpy.ops.object.select_all(action="DESELECT")
meshy_mesh.select_set(True)
bpy.context.view_layer.objects.active = meshy_mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

m_verts = [v.co.copy() for v in meshy_mesh.data.vertices]
m_min = Vector((min(v.x for v in m_verts), min(v.y for v in m_verts), min(v.z for v in m_verts)))
m_max = Vector((max(v.x for v in m_verts), max(v.y for v in m_verts), max(v.z for v in m_verts)))
m_size = m_max - m_min
m_center = (m_min + m_max) / 2

scale = body_size.z / m_size.z if m_size.z > 0.001 else 1.0
offset = body_center - m_center * scale

for v in meshy_mesh.data.vertices:
    v.co = v.co * scale + offset

meshy_mesh.data.update()
print(f"Scaled by {scale:.6f}, repositioned to overlap body regions")

# ── 4. Repair holes ──────────────────────────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
meshy_mesh.select_set(True)
bpy.context.view_layer.objects.active = meshy_mesh
bpy.ops.object.mode_set(mode="EDIT")

bm = bmesh.from_edit_mesh(meshy_mesh.data)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
bm.faces.ensure_lookup_table()

boundary_edges = [e for e in bm.edges if e.is_boundary]
print(f"Boundary edges (hole edges): {len(boundary_edges)}")

if boundary_edges:
    # Find boundary edge loops (each loop = one hole)
    visited = set()
    loops = []

    for start_edge in boundary_edges:
        if start_edge.index in visited:
            continue

        loop = []
        edge = start_edge
        vert = edge.verts[0]

        while True:
            visited.add(edge.index)
            loop.append(vert)

            other_vert = edge.other_vert(vert)
            next_edge = None
            for e in other_vert.link_edges:
                if e.is_boundary and e.index not in visited:
                    next_edge = e
                    break

            if next_edge is None:
                break

            vert = other_vert
            edge = next_edge

        if len(loop) >= 3:
            loops.append(loop)

    print(f"Found {len(loops)} boundary loops (holes)")

    filled_count = 0
    for i, loop_verts in enumerate(loops):
        print(f"  Hole {i}: {len(loop_verts)} vertices")

        if len(loop_verts) < 3:
            continue

        # Fill the hole with a triangle fan from centroid
        center_co = Vector((0, 0, 0))
        for v in loop_verts:
            center_co += v.co
        center_co /= len(loop_verts)

        center_vert = bm.verts.new(center_co)
        bm.verts.ensure_lookup_table()

        for j in range(len(loop_verts)):
            v1 = loop_verts[j]
            v2 = loop_verts[(j + 1) % len(loop_verts)]
            try:
                new_face = bm.faces.new([center_vert, v1, v2])
                new_face.smooth = True
                filled_count += 1
            except ValueError:
                pass

    bm.normal_update()
    print(f"Filled {filled_count} triangles across all holes")

    # Smooth the filled vertices slightly
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Assign UVs for filled faces from nearest existing face
    if meshy_mesh.data.uv_layers:
        uv_layer = bm.loops.layers.uv.active
        if uv_layer:
            for f in bm.faces:
                if not f.is_valid:
                    continue
                has_uv = any(l[uv_layer].uv.length > 0.001 for l in f.loops)
                if not has_uv:
                    center = f.calc_center_median()
                    # Find nearest face with valid UVs and copy average UV
                    best_dist = float("inf")
                    best_uv = Vector((0.5, 0.5))
                    for of in bm.faces:
                        if of == f or not of.is_valid:
                            continue
                        d = (of.calc_center_median() - center).length
                        if d < best_dist:
                            any_uv = any(l[uv_layer].uv.length > 0.001 for l in of.loops)
                            if any_uv:
                                best_dist = d
                                avg = Vector((0, 0))
                                for l in of.loops:
                                    avg += l[uv_layer].uv
                                avg /= len(of.loops)
                                best_uv = avg
                    for l in f.loops:
                        l[uv_layer].uv = best_uv

bmesh.update_edit_mesh(meshy_mesh.data)
bpy.ops.object.mode_set(mode="OBJECT")

print(f"Repaired mesh: {len(meshy_mesh.data.vertices)} verts, {len(meshy_mesh.data.polygons)} faces")

# Verify no remaining holes
bm_check = bmesh.new()
bm_check.from_mesh(meshy_mesh.data)
remaining_boundary = [e for e in bm_check.edges if e.is_boundary]
print(f"Remaining boundary edges after repair: {len(remaining_boundary)}")
bm_check.free()

# ── 5. Create body reference for weight transfer ─────────────────────────────
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
print(f"Body reference: {len(body_ref.data.vertices)} verts")

# ── 6. Duplicate body_ref for armature binding, replace with Meshy geometry ──
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.duplicate(linked=False)
final_obj = bpy.context.active_object
final_obj.name = "upperbody_v1"
final_obj.data.name = "upperbody_v1"

mat_inv = final_obj.matrix_world.inverted()
meshy_mat = meshy_mesh.matrix_world

bpy.ops.object.select_all(action="DESELECT")
final_obj.select_set(True)
bpy.context.view_layer.objects.active = final_obj
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(final_obj.data)
bmesh.ops.delete(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], context="VERTS")

vert_map = {}
for i, v in enumerate(meshy_mesh.data.vertices):
    world_pos = meshy_mat @ v.co
    local_pos = mat_inv @ world_pos
    new_v = bm.verts.new(local_pos)
    vert_map[i] = new_v

bm.verts.ensure_lookup_table()

for poly in meshy_mesh.data.polygons:
    face_verts = [vert_map[vi] for vi in poly.vertices]
    try:
        bm.faces.new(face_verts)
    except ValueError:
        pass

bm.normal_update()
for f in bm.faces:
    f.smooth = True

bmesh.update_edit_mesh(final_obj.data)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()

# Transfer materials from Meshy mesh
final_obj.data.materials.clear()
for mat in meshy_mesh.data.materials:
    final_obj.data.materials.append(mat)

# Transfer UVs
if meshy_mesh.data.uv_layers:
    src_uv = meshy_mesh.data.uv_layers.active
    if not final_obj.data.uv_layers:
        final_obj.data.uv_layers.new(name="UVMap")
    dst_uv = final_obj.data.uv_layers.active

    for poly_idx, poly in enumerate(meshy_mesh.data.polygons):
        if poly_idx < len(final_obj.data.polygons):
            dst_poly = final_obj.data.polygons[poly_idx]
            for i, loop_idx in enumerate(poly.loop_indices):
                if i < len(dst_poly.loop_indices):
                    dst_uv.data[dst_poly.loop_indices[i]].uv = src_uv.data[loop_idx].uv

print(f"Final mesh: {len(final_obj.data.vertices)} verts, {len(final_obj.data.polygons)} faces")

# ── 7. Weight transfer ───────────────────────────────────────────────────────
kd = KDTree(len(body_ref.data.vertices))
for i, v in enumerate(body_ref.data.vertices):
    kd.insert(v.co, i)
kd.balance()

transferred = 0
for rv_idx, rv in enumerate(final_obj.data.vertices):
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
                if name not in [vg.name for vg in final_obj.vertex_groups]:
                    final_obj.vertex_groups.new(name=name)
                final_obj.vertex_groups[name].add([rv_idx], nw, "REPLACE")
                transferred += 1

print(f"Transferred {transferred} blended weight entries")

# ── 8. Clean up ──────────────────────────────────────────────────────────────
for obj in [body_ref, meshy_mesh]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.delete(use_global=False)

# ── 9. Export ────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
final_obj.select_set(True)
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

print(f"\nExported: {OUT_PATH}")
print(f"  Vertices: {len(final_obj.data.vertices)}")
print(f"  Faces:    {len(final_obj.data.polygons)}")
