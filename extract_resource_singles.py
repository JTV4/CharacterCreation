"""
extract_resource_singles.py
===========================
Import Exodus-SDK7 single ore chunks and raw fish GLBs, pack any textures,
and write self-contained GLBs into the viewer buildings folder.

Sources:
  ~/Documents/GitHub/Exodus-SDK7/assets/models/Mining/ore/
  ~/Documents/GitHub/Exodus-SDK7/assets/models/Fishing/fish/

Outputs:
  viewer/public/buildings/{Iron,Coal,Gold,Titanium,Tungsten}Ore.glb
  viewer/public/buildings/Raw{Catfish,Bass,Trout,Gar,Walleye}.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python extract_resource_singles.py
"""

from __future__ import annotations

import os

import bpy

ROOT = os.path.dirname(os.path.abspath(__file__))
ORE_DIR = os.path.expanduser(
    "~/Documents/GitHub/Exodus-SDK7/assets/models/Mining/ore"
)
FISH_DIR = os.path.expanduser(
    "~/Documents/GitHub/Exodus-SDK7/assets/models/Fishing/fish"
)
OUT_DIR = os.path.join(ROOT, "viewer/public/buildings")

os.makedirs(OUT_DIR, exist_ok=True)

# Coal uses steel_ore.glb (no coal_ore in the source folder).
ORE_VARIANTS = [
    ("iron_ore.glb", "IronOre"),
    ("steel_ore.glb", "CoalOre"),
    ("gold_ore.glb", "GoldOre"),
    ("tiantium_ore.glb", "TitaniumOre"),
    ("tungsten_ore.glb", "TungstenOre"),
]

FISH_VARIANTS = [
    ("raw_catfish.glb", "RawCatfish"),
    ("raw_bass.glb", "RawBass"),
    ("raw_trout.glb", "RawTrout"),
    ("raw_gar.glb", "RawGar"),
    ("raw_walleye.glb", "RawWalleye"),
]


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def pack_images() -> None:
    for img in bpy.data.images:
        if img.packed_file is None and img.filepath:
            try:
                img.pack()
            except Exception as exc:
                print(f"  warn: could not pack {img.name}: {exc}")


def export_scene(path: str) -> None:
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


def extract_one(src_dir: str, src_name: str, out_stem: str) -> None:
    src = os.path.join(src_dir, src_name)
    if not os.path.isfile(src):
        raise FileNotFoundError(src)

    print(f"\n=== {out_stem} ({src_name}) ===")
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh in {src}")

    pack_images()
    print(f"  meshes={[m.name for m in meshes]}")
    print(f"  images={[img.name for img in bpy.data.images]}")

    out_path = os.path.join(OUT_DIR, f"{out_stem}.glb")
    export_scene(out_path)
    print(f"  -> {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")


def main() -> None:
    print(f"Ore source:  {ORE_DIR}")
    print(f"Fish source: {FISH_DIR}")
    print(f"Output:      {OUT_DIR}")

    for src, stem in ORE_VARIANTS:
        extract_one(ORE_DIR, src, stem)
    for src, stem in FISH_VARIANTS:
        extract_one(FISH_DIR, src, stem)

    print("\nDONE — 5 ores + 5 raw fish exported.")


if __name__ == "__main__":
    main()
