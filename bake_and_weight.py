"""
bake_and_weight.py
==================
Takes an original clean mesh + a Meshy-textured mesh and:
  1. UV-unwraps the clean mesh (Smart UV Project)
  2. Bakes the Meshy texture onto the clean mesh
  3. Transfers bone weights via N-nearest KD-tree blending
  4. Parents to the armature and exports

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python bake_and_weight.py

Configure the paths and body regions below.
"""

import os
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

# ── Configuration ─────────────────────────────────────────────────────────────
BASE_MODEL      = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
CLEAN_MESH_GLB  = os.path.abspath("viewer/public/equipment/Female/Upperbody/Upperbody.glb 2")
MESHY_MESH_GLB  = os.path.abspath("viewer/public/equipment/Female/Upperbody/upperbodytest2.glb")
OUT_PATH        = os.path.abspath("viewer/public/equipment/Female/Upperbody/upperbody_weighted.glb")
BAKE_RES        = 1024

BODY_REGIONS = [
    "base_body_arm_upper",
    "base_body_upper_torso",
    "base_body_lower_torso",
]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER     = 1.5

# ── 1. Load BaseFemaleV2 (armature + weight source) ─────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)

# Need Cycles for baking
bpy.context.scene.render.engine = "CYCLES"
bpy.context.scene.cycles.device = "CPU"
bpy.context.scene.cycles.samples = 1
bpy.context.scene.render.bake.use_selected_to_active = True
bpy.context.scene.render.bake.cage_extrusion = 0.5
bpy.context.scene.render.bake.max_ray_distance = 0.0

bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
print(f"Loaded {len(region_meshes)} body region meshes")

# ── 2. Load the clean base mesh ─────────────────────────────────────────────
bpy.ops.import_scene.gltf(filepath=CLEAN_MESH_GLB)
bpy.context.view_layer.update()

clean_mesh = None
for obj in bpy.data.objects:
    if obj.type == "MESH" and obj.name not in region_meshes:
        if len(obj.data.vertices) > 100:
            clean_mesh = obj
            break

print(f"Clean mesh: {clean_mesh.name} ({len(clean_mesh.data.vertices)} verts, {len(clean_mesh.data.polygons)} faces)")

# ── 3. Load the Meshy-textured mesh ─────────────────────────────────────────
pre_import_meshes = {o.name for o in bpy.data.objects if o.type == "MESH"}
bpy.ops.import_scene.gltf(filepath=MESHY_MESH_GLB)
bpy.context.view_layer.update()

meshy_mesh = None
for obj in bpy.data.objects:
    if obj.type == "MESH" and obj.name not in region_meshes and obj != clean_mesh:
        if obj.name not in pre_import_meshes and len(obj.data.vertices) > 100:
            meshy_mesh = obj
            break

if not meshy_mesh:
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj != clean_mesh and obj.name not in region_meshes:
            if len(obj.data.vertices) > 100:
                meshy_mesh = obj
                break

print(f"Meshy mesh: {meshy_mesh.name} ({len(meshy_mesh.data.vertices)} verts, {len(meshy_mesh.data.polygons)} faces)")
print(f"  Materials: {[m.name for m in meshy_mesh.data.materials]}")

# ── 4. Scale Meshy mesh to match clean mesh ──────────────────────────────────
# The Meshy mesh was exported at a different scale; match it to the clean mesh
clean_verts = [clean_mesh.matrix_world @ v.co for v in clean_mesh.data.vertices]
clean_min = Vector((min(v.x for v in clean_verts), min(v.y for v in clean_verts), min(v.z for v in clean_verts)))
clean_max = Vector((max(v.x for v in clean_verts), max(v.y for v in clean_verts), max(v.z for v in clean_verts)))
clean_size = clean_max - clean_min
clean_center = (clean_min + clean_max) / 2

bpy.ops.object.select_all(action="DESELECT")
meshy_mesh.select_set(True)
bpy.context.view_layer.objects.active = meshy_mesh
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

meshy_verts = [v.co.copy() for v in meshy_mesh.data.vertices]
meshy_min = Vector((min(v.x for v in meshy_verts), min(v.y for v in meshy_verts), min(v.z for v in meshy_verts)))
meshy_max = Vector((max(v.x for v in meshy_verts), max(v.y for v in meshy_verts), max(v.z for v in meshy_verts)))
meshy_size = meshy_max - meshy_min
meshy_center = (meshy_min + meshy_max) / 2

scale = clean_size.z / meshy_size.z if meshy_size.z > 0.001 else 1.0
offset = clean_center - meshy_center * scale

for v in meshy_mesh.data.vertices:
    v.co = v.co * scale + offset

meshy_mesh.data.update()
print(f"Meshy mesh scaled by {scale:.6f} and repositioned to overlap clean mesh")

# ── 5. Smart UV unwrap the clean mesh ────────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
clean_mesh.select_set(True)
bpy.context.view_layer.objects.active = clean_mesh

if not clean_mesh.data.uv_layers:
    clean_mesh.data.uv_layers.new(name="UVMap")

bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02, scale_to_bounds=True)
bpy.ops.object.mode_set(mode="OBJECT")
print("Smart UV Project applied to clean mesh")

# ── 6. Convert Meshy material to Emission (so EMIT bake captures the texture) ─
for mat in meshy_mesh.data.materials:
    if not mat or not mat.use_nodes:
        continue
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Find the texture image node
    tex_img_node = None
    for node in nodes:
        if node.type == "TEX_IMAGE" and node.image:
            tex_img_node = node
            break

    if tex_img_node:
        # Rewire: texture → emission → output
        output_node = None
        for node in nodes:
            if node.type == "OUTPUT_MATERIAL":
                output_node = node
                break
        if not output_node:
            output_node = nodes.new("ShaderNodeOutputMaterial")

        emit_node = nodes.new("ShaderNodeEmission")
        emit_node.inputs["Strength"].default_value = 1.0

        # Clear existing links to output
        for link in list(links):
            if link.to_node == output_node:
                links.remove(link)

        links.new(tex_img_node.outputs["Color"], emit_node.inputs["Color"])
        links.new(emit_node.outputs["Emission"], output_node.inputs["Surface"])
        print(f"  Meshy material '{mat.name}' rewired: texture → emission → output")
    else:
        print(f"  WARNING: No texture image found in material '{mat.name}'")

# ── 7. Set up bake target on clean mesh ──────────────────────────────────────
bake_image = bpy.data.images.new("baked_texture", width=BAKE_RES, height=BAKE_RES, alpha=False)
bake_image.colorspace_settings.name = "sRGB"

bake_mat = bpy.data.materials.new(name="BakedMaterial")
bake_mat.use_nodes = True
bk_nodes = bake_mat.node_tree.nodes
bk_links = bake_mat.node_tree.links
bk_nodes.clear()

bk_emit = bk_nodes.new("ShaderNodeEmission")
bk_output = bk_nodes.new("ShaderNodeOutputMaterial")
bk_tex = bk_nodes.new("ShaderNodeTexImage")
bk_tex.image = bake_image
bk_tex.select = True
bk_nodes.active = bk_tex

bk_links.new(bk_tex.outputs["Color"], bk_emit.inputs["Color"])
bk_links.new(bk_emit.outputs["Emission"], bk_output.inputs["Surface"])

clean_mesh.data.materials.clear()
clean_mesh.data.materials.append(bake_mat)

print("Bake materials set up (Emission pipeline)")

# ── 8. Bake texture from Meshy mesh to clean mesh ───────────────────────────
bpy.ops.object.select_all(action="DESELECT")
meshy_mesh.select_set(True)
clean_mesh.select_set(True)
bpy.context.view_layer.objects.active = clean_mesh

print("Starting EMIT bake (Selected to Active)...")
bpy.ops.object.bake(type="EMIT")
print("Bake complete!")

# Save the baked image
bake_image_path = os.path.join(os.path.dirname(OUT_PATH), "upperbody_baked_texture.png")
bake_image.filepath_raw = bake_image_path
bake_image.file_format = "PNG"
bake_image.save()
print(f"Baked texture saved: {bake_image_path}")

# ── 8. Create body reference for weight transfer ────────────────────────────
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

# ── 9. Duplicate body_ref for armature binding, replace with clean geometry ──
bpy.ops.object.select_all(action="DESELECT")
body_ref.select_set(True)
bpy.context.view_layer.objects.active = body_ref
bpy.ops.object.duplicate(linked=False)
upperbody = bpy.context.active_object
upperbody.name = "upperbody_v1"
upperbody.data.name = "upperbody_v1"

mat_inv = upperbody.matrix_world.inverted()
base_mat = clean_mesh.matrix_world

import bmesh

bpy.ops.object.select_all(action="DESELECT")
upperbody.select_set(True)
bpy.context.view_layer.objects.active = upperbody
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(upperbody.data)
bmesh.ops.delete(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], context="VERTS")

vert_map = {}
for i, v in enumerate(clean_mesh.data.vertices):
    world_pos = base_mat @ v.co
    local_pos = mat_inv @ world_pos
    new_v = bm.verts.new(local_pos)
    vert_map[i] = new_v

bm.verts.ensure_lookup_table()

for poly in clean_mesh.data.polygons:
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

print(f"Upperbody: {len(upperbody.data.vertices)} verts, {len(upperbody.data.polygons)} faces")

# ── 10. Create PBR material with baked texture for GLTF export ───────────────
bake_image.pack()

export_mat = bpy.data.materials.new(name="UpperbodyMaterial")
export_mat.use_nodes = True
ex_nodes = export_mat.node_tree.nodes
ex_links = export_mat.node_tree.links
ex_nodes.clear()

ex_bsdf = ex_nodes.new("ShaderNodeBsdfPrincipled")
ex_bsdf.inputs["Roughness"].default_value = 0.8
ex_bsdf.inputs["Metallic"].default_value = 0.0

ex_output = ex_nodes.new("ShaderNodeOutputMaterial")
ex_tex = ex_nodes.new("ShaderNodeTexImage")
ex_tex.image = bake_image

ex_links.new(ex_tex.outputs["Color"], ex_bsdf.inputs["Base Color"])
ex_links.new(ex_bsdf.outputs["BSDF"], ex_output.inputs["Surface"])

upperbody.data.materials.clear()
upperbody.data.materials.append(export_mat)

if clean_mesh.data.uv_layers:
    src_uv = clean_mesh.data.uv_layers.active
    if not upperbody.data.uv_layers:
        upperbody.data.uv_layers.new(name="UVMap")
    dst_uv = upperbody.data.uv_layers.active

    for poly_idx, poly in enumerate(clean_mesh.data.polygons):
        if poly_idx < len(upperbody.data.polygons):
            dst_poly = upperbody.data.polygons[poly_idx]
            for i, loop_idx in enumerate(poly.loop_indices):
                if i < len(dst_poly.loop_indices):
                    dst_loop_idx = dst_poly.loop_indices[i]
                    dst_uv.data[dst_loop_idx].uv = src_uv.data[loop_idx].uv

print("UVs and baked material applied")

# ── 11. Weight transfer ─────────────────────────────────────────────────────
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

# ── 12. Clean up ─────────────────────────────────────────────────────────────
for obj in [body_ref, clean_mesh, meshy_mesh]:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.delete(use_global=False)

for obj in list(bpy.data.objects):
    if obj == upperbody or obj == armature or obj.name in region_meshes:
        continue
    if obj.type in ("MESH", "ARMATURE", "EMPTY"):
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.delete(use_global=False)

# ── 13. Export ───────────────────────────────────────────────────────────────
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
