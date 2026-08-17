"""
generate_female_hair_v1.py
==========================
Hair fitted tightly to BaseFemaleV3 head by cloning the scalp surface.

Author in Mixamo bind space (cm), same as SoftEyebrows / eyes.
Skinned 100% to mixamorig:Head. UV-unwrapped for texturing.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_female_hair_v1.py
"""

from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
BODY_GLB = os.path.join(ROOT, "viewer/public/models/BaseFemaleV3.glb")
OUT_DIR = os.path.join(ROOT, "viewer/public/equipment/Female/Hair")
OUT_GLB = os.path.join(OUT_DIR, "HairMediumV1.glb")

# Scalp selection in head LOCAL cm space.
# Face ≈ +Z (eyes authored at z≈13.6). Keep hair off the face.
Y_MIN_SCALP = 156.0          # above jaw / neck
Y_CROWN = 175.0
FACE_Z_CUT = 3.0             # delete scalp faces more forward than this
FRINGE_Z_MAX = 5.5           # thin fringe may reach slightly farther at hairline
OFFSET_CM = 0.75             # sit just outside skull
LENGTH_RINGS = 7
TIP_Y = 145.0                # ends near shoulders
SIDE_FLARE_CM = 0.8          # keep close to head width


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_body():
    bpy.ops.import_scene.gltf(filepath=BODY_GLB)
    bpy.context.view_layer.update()
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    head = next(
        o for o in bpy.data.objects if o.type == "MESH" and "head" in o.name.lower()
    )
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o is not head:
            bpy.data.objects.remove(o, do_unlink=True)
    head_bone = next(
        b.name
        for b in arm.data.bones
        if b.name in ("mixamorig:Head", "mixamorigHead", "Head", "head")
    )
    return arm, head_bone, head


def skin_to_head(mesh_obj, arm, head_name):
    mesh_obj.vertex_groups.clear()
    idxs = list(range(len(mesh_obj.data.vertices)))
    for bone_name in [b.name for b in arm.data.bones]:
        vg = mesh_obj.vertex_groups.new(name=bone_name)
        vg.add(idxs, 1.0 if bone_name == head_name else 0.0, "REPLACE")
    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm


def export_glb(meshes, arm, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )
    print(f"  → {path}")


def _face_centroid(f):
    co = Vector((0, 0, 0))
    for v in f.verts:
        co += v.co
    return co / len(f.verts)


def build_hair_from_head(head_obj: bpy.types.Object) -> bpy.types.Object:
    """
    1. Clone head
    2. Keep scalp faces only (cut face + neck)
    3. Offset along normals (tight fit)
    4. Extrude lower rim downward for length (back/sides only)
    """
    bm = bmesh.new()
    bm.from_mesh(head_obj.data)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.normal_update()

    # --- Delete non-scalp faces ---
    to_delete = []
    for f in bm.faces:
        c = _face_centroid(f)
        # Neck / lower head
        if c.y < Y_MIN_SCALP:
            to_delete.append(f)
            continue
        # Face: strong +Z
        if c.z > FACE_Z_CUT:
            # Allow a thin forehead fringe band near the hairline
            near_hairline = c.y > 168.0 and c.z < FRINGE_Z_MAX
            if not near_hairline:
                to_delete.append(f)
                continue
        # Ear / cheek sides that poke forward
        if c.z > 2.0 and c.y < 162.0 and abs(c.x) > 6.0:
            to_delete.append(f)
            continue

    bmesh.ops.delete(bm, geom=to_delete, context="FACES")
    # Drop loose verts
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")

    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    print(f"  Scalp faces kept: {len(bm.faces)}  verts: {len(bm.verts)}")

    # --- Offset along normals (sit on top of skull) ---
    for v in bm.verts:
        if v.normal.length > 0:
            # Slightly less offset on the fringe (+Z) so it hugs the forehead
            face_amt = max(0.0, min(1.0, v.co.z / FRINGE_Z_MAX)) if v.co.z > 0 else 0.0
            off = OFFSET_CM * (1.0 - 0.35 * face_amt)
            v.co += v.normal.normalized() * off

    # Soft side-part: nudge crown volume a touch toward +X
    for v in bm.verts:
        if v.co.y > 168.0:
            v.co.x += 0.4 * math.sin(max(-1.0, min(1.0, v.co.x / 8.0)) * math.pi)

    bm.normal_update()

    # --- Find lower boundary edges (rim) for length extrusion ---
    # ONLY extrude the neck / side / back rim — never the forehead face-cut,
    # or length grows forward over the face.
    boundary = [e for e in bm.edges if e.is_boundary]
    rim_verts = set()
    for e in boundary:
        for v in e.verts:
            # Forehead / face opening — do not grow length from here
            if v.co.z > 1.5 and v.co.y > 164.0:
                continue
            # Keep lower back & side rim
            if v.co.y < 166.0 or v.co.z < 1.0:
                rim_verts.add(v)

    rim_verts = list(rim_verts)
    print(f"  Length rim verts: {len(rim_verts)}")

    current_rim = set(rim_verts)
    for ring in range(1, LENGTH_RINGS + 1):
        t = ring / LENGTH_RINGS
        rim_edges = [
            e
            for e in bm.edges
            if e.is_boundary
            and e.verts[0] in current_rim
            and e.verts[1] in current_rim
        ]
        if not rim_edges:
            break

        ret = bmesh.ops.extrude_edge_only(bm, edges=rim_edges)
        extruded = [v for v in ret["geom"] if isinstance(v, bmesh.types.BMVert)]
        new_rim = set()
        for v in extruded:
            front = max(0.0, v.co.z)
            radial = Vector((v.co.x, 0.0, v.co.z))
            if radial.length > 1e-4:
                radial.normalize()
            else:
                radial = Vector((0.0, 0.0, -1.0))

            # Even steps toward shoulder tip; less on anything still forward
            drop = (TIP_Y - v.co.y) * (1.0 / (LENGTH_RINGS - ring + 1))
            if front > 2.0:
                drop *= 0.35
            v.co.y += drop

            flare = SIDE_FLARE_CM * math.sin(t * math.pi) * (0.25 if front > 2.0 else 1.0)
            v.co.x += radial.x * flare * 0.30
            v.co.z += radial.z * flare * 0.40
            v.co.x += 0.2 * math.sin(v.co.x * 0.25 + t) * t
            new_rim.add(v)

        current_rim = new_rim
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

    # Clean / normals
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Mild smooth: average with neighbors once
    bm.normal_update()
    for v in list(bm.verts):
        if not v.link_edges:
            continue
        acc = Vector(v.co)
        n = 1
        for e in v.link_edges:
            other = e.other_vert(v)
            acc += other.co
            n += 1
        avg = acc / n
        # Keep fringe / hairline sharper
        mix = 0.35 if v.co.z > 3.0 else 0.55
        v.co = v.co.lerp(avg, mix * 0.4)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new("HairMediumV1")
    bm.to_mesh(me)
    bm.free()

    obj = bpy.data.objects.new("HairMediumV1", me)
    bpy.context.collection.objects.link(obj)

    for poly in me.polygons:
        poly.use_smooth = True
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    mat = bpy.data.materials.new("HairMediumV1_Placeholder")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.45, 0.32, 0.22, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
    me.materials.append(mat)

    return obj


def fit_report(hair, head):
    def aabb(obj, local=True):
        coords = [v.co for v in obj.data.vertices] if local else [
            obj.matrix_world @ v.co for v in obj.data.vertices
        ]
        xs = [c.x for c in coords]
        ys = [c.y for c in coords]
        zs = [c.z for c in coords]
        return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs), len(coords)

    h = aabb(hair)
    d = aabb(head)
    print(
        f"  Hair cm: x=[{h[0]:.2f},{h[1]:.2f}] y=[{h[2]:.2f},{h[3]:.2f}] "
        f"z=[{h[4]:.2f},{h[5]:.2f}] v={h[6]}"
    )
    print(
        f"  Head cm: x=[{d[0]:.2f},{d[1]:.2f}] y=[{d[2]:.2f},{d[3]:.2f}] "
        f"z=[{d[4]:.2f},{d[5]:.2f}] v={d[6]}"
    )


def main():
    print("=" * 60)
    print("generate_female_hair_v1.py  (scalp-fit)")
    print("=" * 60)
    clear_scene()
    arm, head_bone, head = load_body()
    print(f"[1/3] Head + armature ({head_bone})")

    hair = build_hair_from_head(head)
    print("[2/3] Hair built from scalp")
    fit_report(hair, head)

    # Remove head from export
    bpy.data.objects.remove(head, do_unlink=True)

    skin_to_head(hair, arm, head_bone)
    export_glb([hair], arm, OUT_GLB)
    print("[3/3] Exported")
    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
