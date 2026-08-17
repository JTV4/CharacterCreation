"""
weight_textured_hair.py
=======================
Takes Meshy-textured hair (unit-normalized, unskinned) and remaps it into
the matching authored hair bind space (cm), skins 100% to mixamorig:Head,
exports GLB with baked texture preserved.

Set PIECE below, then run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python weight_textured_hair.py
"""

from __future__ import annotations

import os

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))

# Which textured piece to weight. Options: "medium", "long_braid_blonde"
PIECE = "long_braid_blonde"

PIECES = {
    "medium": {
        "meshy": "~/Desktop/Shells/Hair/Female Hair/female_textured_hair.glb",
        "ref": "viewer/public/equipment/Female/Hair/HairMediumV1.glb",
        "out": "viewer/public/equipment/Female/Hair/HairMediumV1_Textured.glb",
        "name": "HairMediumV1_Textured",
    },
    "long_braid_blonde": {
        "meshy": "~/Desktop/Shells/Hair/Female Hair/textured_blonde_hair.glb",
        "ref": "viewer/public/equipment/Female/Hair/HairLongBraidV1.glb",
        "out": "viewer/public/equipment/Female/Hair/HairLongBraidV1_TexturedBlonde.glb",
        "name": "HairLongBraidV1_TexturedBlonde",
    },
}

BODY_GLB = os.path.join(ROOT, "viewer/public/models/BaseFemaleV3.glb")
_cfg = PIECES[PIECE]
MESHY_GLB = os.path.expanduser(_cfg["meshy"])
REF_GLB = os.path.join(ROOT, _cfg["ref"])
OUT_GLB = os.path.join(ROOT, _cfg["out"])
MESH_NAME = _cfg["name"]


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def aabb(obj):
    coords = [v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (
        Vector((min(xs), min(ys), min(zs))),
        Vector((max(xs), max(ys), max(zs))),
    )


def remap_bbox(src, src_min, src_max, dst_min, dst_max):
    """Affine map src AABB → dst AABB (per-axis)."""
    src_size = src_max - src_min
    dst_size = dst_max - dst_min
    for v in src.data.vertices:
        p = v.co
        t = Vector(
            (
                0.0 if abs(src_size.x) < 1e-9 else (p.x - src_min.x) / src_size.x,
                0.0 if abs(src_size.y) < 1e-9 else (p.y - src_min.y) / src_size.y,
                0.0 if abs(src_size.z) < 1e-9 else (p.z - src_min.z) / src_size.z,
            )
        )
        v.co = Vector(
            (
                dst_min.x + t.x * dst_size.x,
                dst_min.y + t.y * dst_size.y,
                dst_min.z + t.z * dst_size.z,
            )
        )


def _unit01(p: Vector, mn: Vector, size: Vector) -> Vector:
    return Vector(
        (
            0.0 if abs(size.x) < 1e-9 else (p.x - mn.x) / size.x,
            0.0 if abs(size.y) < 1e-9 else (p.y - mn.y) / size.y,
            0.0 if abs(size.z) < 1e-9 else (p.z - mn.z) / size.z,
        )
    )


def _face_centroid(me, fi: int) -> Vector:
    f = me.polygons[fi]
    c = Vector((0, 0, 0))
    for vi in f.vertices:
        c += me.vertices[vi].co
    return c / max(1, len(f.vertices))


def detect_axis_remap(src, ref):
    """
    Meshy often reorients meshes in its unit cube. Find the axis remapping
    that best aligns face centroids with the authored reference.

    Returns (name, fn) where fn maps unit src (x,y,z) → unit ref (x,y,z).
    """
    src_min, src_max = aabb(src)
    ref_min, ref_max = aabb(ref)
    src_size = src_max - src_min
    ref_size = ref_max - ref_min

    candidates = {
        "identity": lambda u: u,
        "yflip": lambda u: Vector((u.x, 1.0 - u.y, u.z)),
        "zflip": lambda u: Vector((u.x, u.y, 1.0 - u.z)),
        "yzflip": lambda u: Vector((u.x, 1.0 - u.y, 1.0 - u.z)),
        # Meshy braid case: (x,y,z)_ref ↔ (x, 1-z, y)_meshy  ⇒  meshy→ref = (x, z, 1-y)
        "x_z_1minusY": lambda u: Vector((u.x, u.z, 1.0 - u.y)),
        "x_1minusZ_y": lambda u: Vector((u.x, 1.0 - u.z, u.y)),
        "x_y_from_z_z_from_y": lambda u: Vector((u.x, u.z, u.y)),
        "x_1minusY_from_z_z_from_y": lambda u: Vector((u.x, 1.0 - u.z, 1.0 - u.y)),
    }

    n_faces = min(len(src.data.polygons), len(ref.data.polygons))
    sample = list(range(0, n_faces, max(1, n_faces // 140)))
    scores = {}
    for name, fn in candidates.items():
        total = 0.0
        for fi in sample:
            su = _unit01(_face_centroid(src.data, fi), src_min, src_size)
            ru = _unit01(_face_centroid(ref.data, fi), ref_min, ref_size)
            total += (fn(su) - ru).length
        scores[name] = total / max(1, len(sample))

    best = min(scores, key=scores.get)
    print(f"  Axis remap scores: { {k: round(v, 4) for k, v in scores.items()} }")
    print(f"  Chosen axis remap: {best}")
    return best, candidates[best]


def remap_with_axis(src, src_min, src_max, dst_min, dst_max, axis_fn):
    """Normalize src → apply axis_fn in unit space → scale into dst AABB."""
    src_size = src_max - src_min
    dst_size = dst_max - dst_min
    for v in src.data.vertices:
        u = axis_fn(_unit01(v.co, src_min, src_size))
        v.co = Vector(
            (
                dst_min.x + u.x * dst_size.x,
                dst_min.y + u.y * dst_size.y,
                dst_min.z + u.z * dst_size.z,
            )
        )


def feature_polarity(obj):
    """Crown should be high-Y mid-Z; braid tip low-Y back-Z."""
    coords = [v.co.copy() for v in obj.data.vertices]
    order = sorted(range(len(coords)), key=lambda i: coords[i].y)
    top = [coords[i] for i in order[-100:]]
    bot = [coords[i] for i in order[:100]]
    return {
        "top100_mean_z": sum(p.z for p in top) / len(top),
        "bot100_mean_z": sum(p.z for p in bot) / len(bot),
        "top100_mean_y": sum(p.y for p in top) / len(top),
        "bot100_mean_y": sum(p.y for p in bot) / len(bot),
    }


def skin_to_head(mesh_obj, arm, head_name):
    mesh_obj.vertex_groups.clear()
    idxs = list(range(len(mesh_obj.data.vertices)))
    for bone_name in [b.name for b in arm.data.bones]:
        vg = mesh_obj.vertex_groups.new(name=bone_name)
        vg.add(idxs, 1.0 if bone_name == head_name else 0.0, "REPLACE")
    mesh_obj.parent = arm
    for m in list(mesh_obj.modifiers):
        mesh_obj.modifiers.remove(m)
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm


def main():
    print("=" * 60)
    print(f"weight_textured_hair.py  [{PIECE}]")
    print("=" * 60)
    if not os.path.isfile(MESHY_GLB):
        raise SystemExit(f"Missing Meshy GLB: {MESHY_GLB}")

    clear_scene()

    # Keep reference mesh in scene for axis detection, then remove after.
    bpy.ops.import_scene.gltf(filepath=REF_GLB)
    ref = next(o for o in bpy.data.objects if o.type == "MESH" and "Hair" in o.name)
    ref_min, ref_max = aabb(ref)
    print(
        f"[1/4] Ref AABB cm: {tuple(round(x, 2) for x in ref_min)} → "
        f"{tuple(round(x, 2) for x in ref_max)}  v={len(ref.data.vertices)}"
    )

    bpy.ops.import_scene.gltf(filepath=BODY_GLB)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    # Drop body meshes only (keep ref + arm)
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o is not ref:
            bpy.data.objects.remove(o, do_unlink=True)
    head_bone = next(
        b.name
        for b in arm.data.bones
        if b.name in ("mixamorig:Head", "mixamorigHead", "Head", "head")
    )
    print(f"[2/4] Armature ready, head={head_bone}")

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=MESHY_GLB)
    imported = [o for o in bpy.data.objects if o not in before]
    hair = next(o for o in imported if o.type == "MESH")
    for o in imported:
        if o is not hair and o.type != "ARMATURE":
            bpy.data.objects.remove(o, do_unlink=True)

    src_min, src_max = aabb(hair)
    print(
        f"[3/4] Meshy AABB: {tuple(round(x, 4) for x in src_min)} → "
        f"{tuple(round(x, 4) for x in src_max)}  v={len(hair.data.vertices)}"
    )

    axis_name, axis_fn = detect_axis_remap(hair, ref)
    remap_with_axis(hair, src_min, src_max, ref_min, ref_max, axis_fn)
    hair.name = MESH_NAME
    hair.data.name = MESH_NAME

    dst_min, dst_max = aabb(hair)
    tex_polarity = feature_polarity(hair)
    print(
        f"  Remapped ({axis_name}) → {tuple(round(x, 2) for x in dst_min)} → "
        f"{tuple(round(x, 2) for x in dst_max)}"
    )
    print(f"  Polarity topZ={tex_polarity['top100_mean_z']:.2f} botZ={tex_polarity['bot100_mean_z']:.2f}")

    # Done with reference mesh
    bpy.data.objects.remove(ref, do_unlink=True)

    skin_to_head(hair, arm, head_bone)

    os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    hair.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB,
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
        export_texcoords=True,
    )
    print(f"[4/4] → {OUT_GLB}")
    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
