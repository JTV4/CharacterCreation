"""
generate_female_eyes.py
=======================
Designs 5 removable textured eye pairs for BaseFemaleV2.

Each pair is a skinned GLB (100% mixamorig:Head) that can be toggled on/off
in the viewer Equipment panel without hiding the head mesh.

Eye sockets (probed from BaseFemaleV2 head, Z-up meters):
  L ≈ (-0.036, 0.104, 1.640)
  R ≈ ( 0.037, 0.103, 1.641)

Outputs (per type):
  viewer/public/equipment/Female/Eyes/<Name>EyesWeighted.glb
  viewer/public/equipment/Female/Eyes/Textures/<Name>Eyes.png

Types:
  1. Brown   — classic warm brown iris
  2. Blue    — bright sky-blue iris
  3. Green   — forest green iris
  4. Amber   — golden amber with vertical slit pupil
  5. Violet  — mystic violet with luminous ring

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_female_eyes.py
"""

from __future__ import annotations

import math
import os

import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
BODY_GLB = os.path.join(ROOT, "viewer/public/models/BaseFemaleV2.glb")
OUT_DIR = os.path.join(ROOT, "viewer/public/equipment/Female/Eyes")
TEX_DIR = os.path.join(OUT_DIR, "Textures")
os.makedirs(TEX_DIR, exist_ok=True)

# Socket centers in BaseFemaleV2 bind / local mesh space (cm).
# Armature matrix maps: world.x=0.01*lx, world.y=-0.01*lz, world.z=0.01*ly
# Face surface in Blender world is +Y ⇒ negative local Z.
#
# The viewer applies rotX(π/2) to external equipment and a Z-up display
# convention that effectively mirrors the authored forward axis for
# head-weighted overlays (same reason hats ship with yaw≈180°).  Author
# eyes on the BACK of the head in Blender bind space (+local Z) so they
# land on the FACE after that remap.
EYE_L = Vector((-3.45, 164.2, 13.6))
EYE_R = Vector((3.45, 164.2, 13.6))
EYE_RADIUS = 1.35  # cm
SEGMENTS = 24
RINGS = 16

EYE_TYPES = [
    {
        "id": "brown_eyes",
        "name": "Brown",
        "file": "BrownEyesWeighted.glb",
        "tex": "BrownEyes.png",
        "iris": (0.45, 0.28, 0.12),
        "iris_dark": (0.22, 0.12, 0.05),
        "iris_light": (0.70, 0.48, 0.22),
        "pupil_style": "round",
        "glow": 0.0,
        "color": "#8B5E3C",
    },
    {
        "id": "blue_eyes",
        "name": "Blue",
        "file": "BlueEyesWeighted.glb",
        "tex": "BlueEyes.png",
        "iris": (0.25, 0.48, 0.78),
        "iris_dark": (0.10, 0.22, 0.45),
        "iris_light": (0.55, 0.75, 0.95),
        "pupil_style": "round",
        "glow": 0.0,
        "color": "#3B82F6",
    },
    {
        "id": "green_eyes",
        "name": "Green",
        "file": "GreenEyesWeighted.glb",
        "tex": "GreenEyes.png",
        "iris": (0.22, 0.55, 0.28),
        "iris_dark": (0.08, 0.28, 0.12),
        "iris_light": (0.45, 0.78, 0.40),
        "pupil_style": "round",
        "glow": 0.0,
        "color": "#22C55E",
    },
    {
        "id": "amber_eyes",
        "name": "Amber",
        "file": "AmberEyesWeighted.glb",
        "tex": "AmberEyes.png",
        "iris": (0.85, 0.55, 0.15),
        "iris_dark": (0.55, 0.28, 0.05),
        "iris_light": (0.98, 0.78, 0.35),
        "pupil_style": "slit",
        "glow": 0.05,
        "color": "#F59E0B",
    },
    {
        "id": "violet_eyes",
        "name": "Violet",
        "file": "VioletEyesWeighted.glb",
        "tex": "VioletEyes.png",
        "iris": (0.55, 0.25, 0.75),
        "iris_dark": (0.28, 0.08, 0.45),
        "iris_light": (0.78, 0.50, 0.95),
        "pupil_style": "round",
        "glow": 0.35,
        "color": "#A855F7",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
#  Texture generation
# ══════════════════════════════════════════════════════════════════════════════
def make_eye_texture(spec: dict, size: int = 512) -> str:
    """Paint a stylized iris + sclera texture (front-facing UV)."""
    path = os.path.join(TEX_DIR, spec["tex"])
    img = np.zeros((size, size, 4), dtype=np.float32)

    yy, xx = np.mgrid[0:size, 0:size]
    # UV: center of front hemisphere maps near (0.5, 0.5) for our sphere unwrap
    u = (xx + 0.5) / size
    v = (yy + 0.5) / size
    # Remap to centered coords for polar iris
    cx = (u - 0.5) * 2.0
    cy = (v - 0.5) * 2.0
    r = np.sqrt(cx * cx + cy * cy)
    ang = np.arctan2(cy, cx)

    sclera = np.array([0.96, 0.96, 0.97, 1.0], dtype=np.float32)
    iris = np.array([*spec["iris"], 1.0], dtype=np.float32)
    iris_d = np.array([*spec["iris_dark"], 1.0], dtype=np.float32)
    iris_l = np.array([*spec["iris_light"], 1.0], dtype=np.float32)
    pupil = np.array([0.02, 0.02, 0.03, 1.0], dtype=np.float32)
    limbus = np.array([0.05, 0.05, 0.06, 1.0], dtype=np.float32)

    # Base sclera
    img[:, :] = sclera

    iris_r = 0.55
    pupil_r = 0.18
    # Soft iris disk
    iris_mask = np.clip((iris_r - r) / 0.04, 0, 1) * np.clip((r - 0.02) / 0.02 + 1, 0, 1)
    # Radial fibers
    fiber = 0.55 + 0.45 * np.sin(ang * 18.0 + r * 12.0) * np.sin(ang * 7.0)
    fiber = fiber * (0.7 + 0.3 * np.sin(r * 40.0))
    # Color mix dark→base→light by radius
    t = np.clip(r / iris_r, 0, 1)
    iris_col = (
        iris_d[None, None, :] * (1 - t)[:, :, None] ** 1.4
        + iris[None, None, :] * (1 - np.abs(t - 0.45) * 1.5).clip(0, 1)[:, :, None]
        + iris_l[None, None, :] * (t ** 1.6)[:, :, None]
    )
    iris_col = iris_col * (0.75 + 0.25 * fiber[:, :, None])
    iris_col[..., 3] = 1.0

    m = iris_mask[:, :, None]
    img = img * (1 - m) + iris_col * m

    # Limbus ring
    ring = np.exp(-((r - iris_r * 0.92) ** 2) / (2 * 0.012 ** 2))
    img = img * (1 - ring[:, :, None] * 0.7) + limbus * ring[:, :, None] * 0.7

    # Pupil
    if spec["pupil_style"] == "slit":
        # Vertical cat slit
        slit = np.exp(-(cx ** 2) / (2 * 0.06 ** 2)) * np.clip(1.0 - np.abs(cy) / 0.42, 0, 1)
        slit = np.clip(slit * 1.4, 0, 1)
        img = img * (1 - slit[:, :, None]) + pupil * slit[:, :, None]
    else:
        pmask = np.clip((pupil_r - r) / 0.03, 0, 1)
        img = img * (1 - pmask[:, :, None]) + pupil * pmask[:, :, None]

    # Catchlight
    hx, hy = -0.18, -0.15
    hl = np.exp(-((cx - hx) ** 2 + (cy - hy) ** 2) / (2 * 0.06 ** 2))
    img = img * (1 - hl[:, :, None] * 0.85) + np.array([1, 1, 1, 1]) * hl[:, :, None] * 0.85

    # Glow ring for violet
    if spec["glow"] > 0:
        g = np.exp(-((r - 0.38) ** 2) / (2 * 0.04 ** 2)) * spec["glow"]
        glow_col = iris_l
        img = np.clip(img + glow_col * g[:, :, None], 0, 1)
        img[..., 3] = 1.0

    # Soft vignette at sphere edge (back of eye darker)
    edge = np.clip((r - 0.85) / 0.2, 0, 1)
    img = img * (1 - edge[:, :, None] * 0.55)

    # Write via Blender image
    if spec["tex"] in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[spec["tex"]])
    bl_img = bpy.data.images.new(spec["tex"], width=size, height=size, alpha=True)
    # Blender expects flattened RGBA bottom-to-top
    pixels = img[::-1].reshape(-1)
    bl_img.pixels = pixels.tolist()
    bl_img.filepath_raw = path
    bl_img.file_format = "PNG"
    bl_img.save()
    print(f"  Texture → {path}")
    return path


# ══════════════════════════════════════════════════════════════════════════════
#  Geometry
# ══════════════════════════════════════════════════════════════════════════════
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _assign_front_uvs(obj: bpy.types.Object) -> None:
    """Circular UV on the front of the eye (iris faces -local Z → +world Y)."""
    import bmesh
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.active
    if uv_layer is None:
        uv_layer = bm.loops.layers.uv.new("UVMap")

    for face in bm.faces:
        for loop in face.loops:
            co = loop.vert.co
            u = 0.5 + co.x / (EYE_RADIUS * 2.2)
            v = 0.5 + co.y / (EYE_RADIUS * 2.2)
            loop[uv_layer].uv = (u, v)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def make_eye_sphere(name: str, center: Vector, tex_path: str, glow: float) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=SEGMENTS,
        ring_count=RINGS,
        radius=EYE_RADIUS,
        location=(0, 0, 0),
    )
    obj = bpy.context.active_object
    obj.name = name
    # Flatten along local Z (depth toward face / camera after armature remap)
    obj.scale = (1.08, 1.0, 0.70)
    bpy.ops.object.transform_apply(scale=True)

    _assign_front_uvs(obj)

    for v in obj.data.vertices:
        v.co += center
    obj.data.update()

    bpy.ops.object.shade_smooth()

    # Material
    mat = bpy.data.materials.new(name=f"{name}_Mat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(tex_path)
    tex.image = img
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.22
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.55
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.55
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.45
        bsdf.inputs["Coat Roughness"].default_value = 0.05
    elif "Clearcoat" in bsdf.inputs:
        bsdf.inputs["Clearcoat"].default_value = 0.45
        bsdf.inputs["Clearcoat Roughness"].default_value = 0.05
    if glow > 0:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (0.55, 0.3, 0.85, 1.0)
            bsdf.inputs["Emission Strength"].default_value = glow * 0.9
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (0.55, 0.3, 0.85, 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = glow * 0.9

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def load_body_armature():
    bpy.ops.import_scene.gltf(filepath=BODY_GLB)
    bpy.context.view_layer.update()
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    # Remove body meshes + bone-shape helpers — keep only armature
    for o in list(bpy.data.objects):
        if o.type == "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    print(f"Armature: {arm.name}  bones={len(arm.data.bones)}  scale={tuple(arm.scale)}")
    head_name = None
    for b in arm.data.bones:
        if b.name in ("mixamorig:Head", "mixamorigHead", "Head", "head"):
            head_name = b.name
            break
    if not head_name:
        raise RuntimeError("No Head bone found on BaseFemaleV2 armature")
    print(f"  Head bone: {head_name}")
    return arm, head_name


def skin_to_head(mesh_obj: bpy.types.Object, arm: bpy.types.Object, head_name: str) -> None:
    """100% Head weights; create empty groups for every bone (hat convention)."""
    mesh_obj.vertex_groups.clear()
    idxs = list(range(len(mesh_obj.data.vertices)))
    bone_names = [b.name for b in arm.data.bones]
    for bone_name in bone_names:
        vg = mesh_obj.vertex_groups.new(name=bone_name)
        vg.add(idxs, 1.0 if bone_name == head_name else 0.0, "REPLACE")

    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True
    print(f"  Skinned 100% → {head_name}  ({len(bone_names)} groups)")


def export_eyes(mesh_objs: list[bpy.types.Object], arm: bpy.types.Object, path: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for m in mesh_objs:
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
    print(f"  Exported → {path}")


def build_one(spec: dict) -> str:
    print(f"\n=== {spec['name']} Eyes ===")
    clear_scene()
    tex_path = make_eye_texture(spec)
    arm, head_name = load_body_armature()

    left = make_eye_sphere(f"{spec['name']}Eye_L", EYE_L, tex_path, spec["glow"])
    right = make_eye_sphere(f"{spec['name']}Eye_R", EYE_R, tex_path, spec["glow"])

    # Join into one mesh for a single equipment slot
    bpy.ops.object.select_all(action="DESELECT")
    left.select_set(True)
    right.select_set(True)
    bpy.context.view_layer.objects.active = left
    bpy.ops.object.join()
    eyes = left
    eyes.name = f"{spec['name']}Eyes"
    eyes.data.name = f"{spec['name']}Eyes"

    skin_to_head(eyes, arm, head_name)

    out = os.path.join(OUT_DIR, spec["file"])
    export_eyes([eyes], arm, out)
    print(f"  verts={len(eyes.data.vertices)}  tris={len(eyes.data.polygons)}")
    return out


def write_spec_snippet():
    """Print JSON slots for convenience (actual merge done separately)."""
    ids = [s["id"] for s in EYE_TYPES]
    print("\n--- equipment_spec slots ---")
    for spec in EYE_TYPES:
        others = [i for i in ids if i != spec["id"]]
        print(f"  {spec['id']}: hides peers {others}")


def main():
    print("=" * 60)
    print("Generating 5 removable textured eye types for BaseFemaleV2")
    print("=" * 60)
    for spec in EYE_TYPES:
        build_one(spec)
    write_spec_snippet()
    print("\nDone. Eyes in", OUT_DIR)


if __name__ == "__main__":
    main()
