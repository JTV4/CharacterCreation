"""
texture_grindmoore_castle.py
============================
Import GrindMooreCastleKeep.glb (solid-color materials + existing UVs),
wire procedural textures onto the 6 material slots, and export textured GLB.

Source (default):
  ~/Downloads/GrindMooreCastleKeep.glb

Textures:
  grindmoore_castle_textures/GM_*.png

Outputs:
  ~/Desktop/Models/Buildings/GrindMooreCastleKeep.glb
  viewer/public/buildings/GrindMooreCastleKeep.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python texture_grindmoore_castle.py
"""

from __future__ import annotations

import os
import sys

import bpy


ROOT = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(ROOT, "grindmoore_castle_textures")
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath(os.path.join(ROOT, "viewer/public/buildings"))
DEFAULT_SRC = os.path.expanduser("~/Downloads/GrindMooreCastleKeep.glb")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

# Map Blender import material names → (export material name, texture file, opts)
MATERIAL_MAP = {
    "Material_0": ("castle_stone_dark", "GM_StoneDark.png", {"roughness": 0.92}),
    "Material_1": ("castle_stone", "GM_StoneMain.png", {"roughness": 0.90}),
    "Material_2": ("castle_roof_tiles", "GM_RoofTiles.png", {"roughness": 0.78}),
    "Material_3": ("castle_wood", "GM_DoorWood.png", {"roughness": 0.82}),
    "Material_4": ("castle_stone_light", "GM_StoneLight.png", {"roughness": 0.72}),
    "Material_5": (
        "castle_glass",
        "GM_WindowGlass.png",
        {"roughness": 0.12, "alpha_blend": True, "alpha": 0.35},
    ),
}


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_image(filename: str) -> bpy.types.Image:
    path = os.path.join(TEX_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=False)
    img.pack()
    return img


def wire_texture(
    mat: bpy.types.Material,
    img: bpy.types.Image,
    *,
    roughness: float = 0.85,
    metallic: float = 0.02,
    alpha_blend: bool = False,
    alpha: float | None = None,
):
    mat.use_nodes = True
    mat.use_backface_culling = False
    if alpha_blend:
        mat.blend_method = "BLEND"
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = "NONE"
    else:
        mat.blend_method = "OPAQUE"

    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    # Slight UV scale so block patterns read at castle scale
    mp.inputs["Scale"].default_value = (2.0, 2.0, 2.0)

    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha_blend:
        if alpha is not None:
            bsdf.inputs["Alpha"].default_value = alpha
        elif "Alpha" in tex.outputs:
            nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic


def export_glb(path: str):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=False,
        export_apply=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
    )


def main():
    src = DEFAULT_SRC
    if "--" in sys.argv:
        i = sys.argv.index("--")
        if i + 1 < len(sys.argv):
            src = os.path.expanduser(sys.argv[i + 1])

    if not os.path.isfile(src):
        raise FileNotFoundError(src)

    print(f"\n=== Texture GrindMooreCastleKeep ===")
    print(f"  source: {src}")
    print(f"  textures: {TEX_DIR}")

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()

    # Apply textures to each known material
    renamed = 0
    for mat in list(bpy.data.materials):
        key = mat.name
        # glTF import sometimes suffixes .001
        base = key.split(".")[0]
        if base not in MATERIAL_MAP and key not in MATERIAL_MAP:
            print(f"  skip unknown material: {key}")
            continue
        entry = MATERIAL_MAP.get(key) or MATERIAL_MAP[base]
        new_name, tex_file, opts = entry
        img = load_image(tex_file)
        wire_texture(mat, img, **opts)
        mat.name = new_name
        renamed += 1
        print(f"  {key} → {new_name} ({tex_file})")

    print(f"  textured materials: {renamed}")

    for d in (SOURCE_DIR, VIEWER_DIR):
        out = os.path.join(d, "GrindMooreCastleKeep.glb")
        export_glb(out)
        print(f"  -> {out} ({os.path.getsize(out)/1024:.1f} KB)")

    print("DONE")


if __name__ == "__main__":
    main()
