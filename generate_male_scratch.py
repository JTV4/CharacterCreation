"""
generate_male_scratch.py
========================
Designs a brand-new stylized male character mesh from scratch for GrindScape.

No existing character assets are imported. Solid body parts are modeled with
male proportions, boolean-unioned into one continuous mesh, remeshed to a
game poly budget, then skinned to a Mixamo T-pose armature.

Outputs:
  viewer/public/models/GrindMale.glb
  rig/CharacterMesh/GrindMale.glb
  grind_male_preview_{3q,front,side}.png

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_male_scratch.py
"""

from __future__ import annotations

import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

OUT_VIEWER = os.path.abspath("viewer/public/models/GrindMale.glb")
OUT_RIG = os.path.abspath("rig/CharacterMesh/GrindMale.glb")
PREVIEW_DIR = os.path.abspath(".")
HEIGHT = 1.85
TARGET_VOXEL = 0.028  # remesh voxel → ~3–5k tris (GrindScape budget)


def _link(obj: bpy.types.Object) -> bpy.types.Object:
    bpy.context.collection.objects.link(obj)
    return obj


def _new_mesh_obj(name: str, bm: bmesh.types.BMesh) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    _link(obj)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return obj


def loft_solid(
    name: str,
    centers: list[Vector],
    radii_xy: list[tuple[float, float]],
    segs: int = 16,
) -> bpy.types.Object:
    bm = bmesh.new()
    rings: list[list[bmesh.types.BMVert]] = []
    for i, (c, (rx, ry)) in enumerate(zip(centers, radii_xy)):
        if i == 0:
            direction = (centers[1] - centers[0]).normalized()
        elif i == len(centers) - 1:
            direction = (centers[-1] - centers[-2]).normalized()
        else:
            direction = (centers[i + 1] - centers[i - 1]).normalized()

        if abs(direction.dot(Vector((0, 0, 1)))) > 0.9:
            side, up = Vector((1, 0, 0)), Vector((0, 1, 0))
        else:
            side = direction.cross(Vector((0, 0, 1)))
            if side.length < 1e-6:
                side = direction.cross(Vector((1, 0, 0)))
            side.normalize()
            up = side.cross(direction).normalized()

        row = []
        for si in range(segs):
            a = 2 * math.pi * si / segs
            row.append(bm.verts.new(c + side * (math.cos(a) * rx) + up * (math.sin(a) * ry)))
        rings.append(row)

    for ri in range(len(rings) - 1):
        for si in range(segs):
            sj = (si + 1) % segs
            bm.faces.new([rings[ri][si], rings[ri][sj], rings[ri + 1][sj], rings[ri + 1][si]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _new_mesh_obj(name, bm)


def ellipsoid(name: str, center: Vector, rx: float, ry: float, rz: float,
              segs: int = 20, rings: int = 14) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segs, ring_count=rings, radius=1.0, location=center,
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (rx, ry, rz)
    bpy.ops.object.transform_apply(scale=True)
    return obj


def boolean_union(objects: list[bpy.types.Object], name: str = "GrindMale") -> bpy.types.Object:
    """Union all meshes into one continuous body."""
    base = objects[0]
    bpy.context.view_layer.objects.active = base
    for other in objects[1:]:
        mod = base.modifiers.new(name=f"union_{other.name}", type="BOOLEAN")
        mod.operation = "UNION"
        mod.solver = "EXACT"
        mod.object = other
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(other, do_unlink=True)
    base.name = name
    base.data.name = name
    return base


def remesh_game(obj: bpy.types.Object, voxel: float = TARGET_VOXEL) -> bpy.types.Object:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

    mod = obj.modifiers.new(name="Remesh", type="REMESH")
    mod.mode = "VOXEL"
    mod.voxel_size = voxel
    mod.adaptivity = 0.0
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Smooth + light polish
    mod = obj.modifiers.new(name="Smooth", type="SMOOTH")
    mod.factor = 0.5
    mod.iterations = 8
    bpy.ops.object.modifier_apply(modifier=mod.name)

    bpy.ops.object.shade_smooth()

    # Correct normals / cleanup
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.remove_doubles(threshold=0.001)
    bpy.ops.object.mode_set(mode="OBJECT")

    # Triangulate for game export
    mod = obj.modifiers.new(name="Tri", type="TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=mod.name)

    # Final validation pass
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0015)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Drop zero-area faces
    dead = [f for f in bm.faces if f.calc_area() < 1e-10]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(mesh)
    bm.free()
    mesh.validate(verbose=False)
    mesh.update()

    print(f"Remeshed: {len(obj.data.vertices)} verts, {len(obj.data.polygons)} tris")
    return obj


def sculpt_male_shape(obj: bpy.types.Object) -> None:
    """Push vertices into clearer male proportions after remesh."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    for v in bm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z

        # Broaden shoulders / upper chest
        if 1.40 <= z <= 1.56:
            t = 1.0 - abs(z - 1.48) / 0.10
            v.co.x *= 1.0 + 0.12 * max(0.0, t)

        # Flatten front pecs
        if 1.30 <= z <= 1.52 and y > 0.02:
            lat = max(0.0, 1.0 - abs(x) / 0.22)
            max_y = 0.055 + 0.02 * (1.0 - lat)
            if y > max_y:
                v.co.y = max_y + (y - max_y) * 0.25

        # Thicken waist (kill hourglass)
        if 1.08 <= z <= 1.22:
            v.co.x *= 1.08
            if y < 0:
                v.co.y *= 1.06

        # Narrow hips
        if 0.92 <= z <= 1.05:
            v.co.x *= 0.90

        # Thicken neck / traps
        if 1.52 <= z <= 1.64:
            v.co.x *= 1.10
            if y < 0:
                v.co.y *= 1.12

        # Male jaw
        if 1.64 <= z <= 1.74 and abs(x) > 0.03:
            v.co.x *= 1.08
            if y > 0:
                v.co.y += 0.008

        # Thicken upper arms
        if abs(x) > 0.25 and 1.40 <= z <= 1.55:
            # radial thicken around arm axis roughly
            cy = y
            cz = z - 1.48
            # mild inflate in YZ around arm
            v.co.y = cy * 1.08
            v.co.z = 1.48 + cz * 1.05

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def build_male_parts() -> list[bpy.types.Object]:
    parts: list[bpy.types.Object] = []

    # Torso — male V
    torso = loft_solid(
        "torso",
        [
            Vector((0, 0, 0.94)),
            Vector((0, 0, 1.02)),
            Vector((0, 0, 1.14)),
            Vector((0, 0, 1.28)),
            Vector((0, 0, 1.40)),
            Vector((0, 0, 1.50)),
            Vector((0, 0, 1.56)),
        ],
        [
            (0.12, 0.095),
            (0.130, 0.100),
            (0.150, 0.108),
            (0.175, 0.112),
            (0.200, 0.105),
            (0.215, 0.095),
            (0.160, 0.085),
        ],
        segs=18,
    )
    parts.append(torso)

    # Neck
    parts.append(loft_solid(
        "neck",
        [Vector((0, 0.01, 1.54)), Vector((0, 0.015, 1.62)), Vector((0, 0.02, 1.68))],
        [(0.075, 0.070), (0.062, 0.058), (0.060, 0.058)],
        segs=14,
    ))

    # Head
    head = ellipsoid("head", Vector((0, 0.03, 1.76)), 0.11, 0.12, 0.125, segs=20, rings=14)
    parts.append(head)

    # Arms
    for sign, label in ((1.0, "L"), (-1.0, "R")):
        arm = loft_solid(
            f"arm_{label}",
            [
                Vector((0.14 * sign, 0.0, 1.52)),
                Vector((0.28 * sign, 0.01, 1.50)),
                Vector((0.48 * sign, 0.02, 1.48)),
                Vector((0.62 * sign, 0.02, 1.47)),
                Vector((0.82 * sign, 0.01, 1.465)),
                Vector((0.98 * sign, 0.0, 1.46)),
                Vector((1.10 * sign, 0.0, 1.46)),
            ],
            [
                (0.065, 0.060),
                (0.058, 0.055),
                (0.052, 0.050),
                (0.044, 0.042),
                (0.040, 0.038),
                (0.045, 0.018),
                (0.038, 0.014),
            ],
            segs=14,
        )
        parts.append(arm)

        # Hand bulb
        hand = ellipsoid(
            f"hand_{label}",
            Vector((1.08 * sign, 0.0, 1.46)),
            0.045, 0.030, 0.025,
            segs=12, rings=8,
        )
        parts.append(hand)

    # Legs
    for sign, label in ((1.0, "L"), (-1.0, "R")):
        leg = loft_solid(
            f"leg_{label}",
            [
                Vector((0.08 * sign, 0.0, 1.00)),
                Vector((0.095 * sign, 0.015, 0.78)),
                Vector((0.10 * sign, 0.02, 0.58)),
                Vector((0.095 * sign, 0.015, 0.50)),
                Vector((0.09 * sign, 0.01, 0.28)),
                Vector((0.085 * sign, 0.0, 0.10)),
                Vector((0.08 * sign, 0.06, 0.04)),
                Vector((0.08 * sign, 0.14, 0.03)),
            ],
            [
                (0.090, 0.085),
                (0.078, 0.075),
                (0.065, 0.062),
                (0.055, 0.052),
                (0.048, 0.046),
                (0.040, 0.038),
                (0.045, 0.032),
                (0.035, 0.020),
            ],
            segs=14,
        )
        parts.append(leg)

    return parts


def build_mixamo_armature() -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.active_object
    arm_obj.name = "Armature"
    arm = arm_obj.data
    arm.name = "Armature"
    eb = arm.edit_bones
    for b in list(eb):
        eb.remove(b)

    def bone(name: str, head: Vector, tail: Vector, parent: str | None = None):
        b = eb.new(name)
        b.head, b.tail = head, tail
        b.use_deform = True
        if parent:
            b.parent = eb[parent]
            b.use_connect = (b.head - eb[parent].tail).length < 1e-4
        return b

    bone("mixamorig:Hips",   Vector((0, 0, 1.00)), Vector((0, 0, 1.10)))
    bone("mixamorig:Spine",  Vector((0, 0, 1.10)), Vector((0, 0, 1.24)), "mixamorig:Hips")
    bone("mixamorig:Spine1", Vector((0, 0, 1.24)), Vector((0, 0, 1.38)), "mixamorig:Spine")
    bone("mixamorig:Spine2", Vector((0, 0, 1.38)), Vector((0, 0, 1.52)), "mixamorig:Spine1")
    bone("mixamorig:Neck",   Vector((0, 0, 1.52)), Vector((0, 0, 1.64)), "mixamorig:Spine2")
    bone("mixamorig:Head",   Vector((0, 0, 1.64)), Vector((0, 0, 1.85)), "mixamorig:Neck")

    for side, s in (("Left", 1.0), ("Right", -1.0)):
        bone(f"mixamorig:{side}Shoulder", Vector((0.05 * s, 0, 1.52)), Vector((0.18 * s, 0, 1.52)), "mixamorig:Spine2")
        bone(f"mixamorig:{side}Arm", Vector((0.18 * s, 0, 1.52)), Vector((0.62 * s, 0.02, 1.47)), f"mixamorig:{side}Shoulder")
        bone(f"mixamorig:{side}ForeArm", Vector((0.62 * s, 0.02, 1.47)), Vector((0.98 * s, 0, 1.46)), f"mixamorig:{side}Arm")
        bone(f"mixamorig:{side}Hand", Vector((0.98 * s, 0, 1.46)), Vector((1.12 * s, 0, 1.46)), f"mixamorig:{side}ForeArm")

    for side, s in (("Left", 1.0), ("Right", -1.0)):
        bone(f"mixamorig:{side}UpLeg", Vector((0.09 * s, 0, 1.00)), Vector((0.10 * s, 0.02, 0.50)), "mixamorig:Hips")
        bone(f"mixamorig:{side}Leg", Vector((0.10 * s, 0.02, 0.50)), Vector((0.09 * s, 0, 0.08)), f"mixamorig:{side}UpLeg")
        bone(f"mixamorig:{side}Foot", Vector((0.09 * s, 0, 0.08)), Vector((0.09 * s, 0.10, 0.025)), f"mixamorig:{side}Leg")
        bone(f"mixamorig:{side}ToeBase", Vector((0.09 * s, 0.10, 0.025)), Vector((0.09 * s, 0.16, 0.02)), f"mixamorig:{side}Foot")

    bpy.ops.object.mode_set(mode="OBJECT")
    print(f"Armature: {len(arm_obj.data.bones)} bones")
    return arm_obj


def bind_mesh(mesh_obj: bpy.types.Object, arm_obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    print(f"Vertex groups: {len(mesh_obj.vertex_groups)}")


def apply_material(obj: bpy.types.Object) -> None:
    mat = bpy.data.materials.new("GrindMaleSkin")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.74, 0.56, 0.43, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.55
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def export_glb(path: str, mesh_obj: bpy.types.Object, arm_obj: bpy.types.Object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
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
    )
    print(f"Exported → {path}")


def render_previews() -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1280
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.eevee.taa_render_samples = 64

    bpy.ops.mesh.primitive_plane_add(size=3.5, location=(0, 0, 0))
    ground = bpy.context.active_object
    gmat = bpy.data.materials.new("Ground")
    gmat.use_nodes = True
    gmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.12, 0.14, 1)
    ground.data.materials.append(gmat)

    bpy.ops.object.light_add(type="AREA", location=(1.6, -2.0, 2.4))
    bpy.context.active_object.data.energy = 100
    bpy.context.active_object.data.size = 2.5

    bpy.ops.object.light_add(type="AREA", location=(-2.0, -0.5, 1.8))
    fill = bpy.context.active_object
    fill.data.energy = 40
    fill.data.color = (0.75, 0.85, 1.0)

    bpy.ops.object.light_add(type="AREA", location=(0.2, 2.0, 2.2))
    bpy.context.active_object.data.energy = 55

    look = Vector((0, 0, HEIGHT * 0.52))
    views = {
        "3q": Vector((1.45, -2.0, 0.45)),
        "front": Vector((0.0, -2.6, 0.35)),
        "side": Vector((2.6, 0.0, 0.35)),
    }
    for name, offset in views.items():
        for obj in list(bpy.data.objects):
            if obj.type == "CAMERA":
                bpy.data.objects.remove(obj, do_unlink=True)
        bpy.ops.object.camera_add(location=look + offset)
        cam = bpy.context.active_object
        cam.rotation_euler = (look - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = 50
        scene.camera = cam
        out = os.path.join(PREVIEW_DIR, f"grind_male_preview_{name}.png")
        scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print(f"Wrote {out}")


def main() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    print("=" * 60)
    print("GrindMale — from-scratch design (boolean-union body)")
    print("=" * 60)

    parts = build_male_parts()
    print(f"Built {len(parts)} solid parts")
    body = boolean_union(parts, "GrindMale")
    remesh_game(body, voxel=TARGET_VOXEL)
    sculpt_male_shape(body)
    apply_material(body)

    # Report
    xs = [v.co.x for v in body.data.vertices]
    zs = [v.co.z for v in body.data.vertices]
    chest = [v.co.y for v in body.data.vertices if 1.35 <= v.co.z <= 1.50 and v.co.y > 0 and abs(v.co.x) < 0.12]
    print(f"  Height: {min(zs):.3f} .. {max(zs):.3f}")
    print(f"  Span X: {min(xs):.3f} .. {max(xs):.3f}")
    if chest:
        print(f"  Chest front Y max: {max(chest):.4f}")
    print(f"  Final: {len(body.data.vertices)} verts, {len(body.data.polygons)} tris")

    arm = build_mixamo_armature()
    bind_mesh(body, arm)
    export_glb(OUT_VIEWER, body, arm)
    export_glb(OUT_RIG, body, arm)
    render_previews()

    print("=" * 60)
    print("Done → viewer/public/models/GrindMale.glb")
    print("Viewer button: GrindMale")
    print("=" * 60)


if __name__ == "__main__":
    main()
