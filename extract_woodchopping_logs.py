"""
extract_woodchopping_logs.py
============================
Import Exodus-SDK7 woodchopping log GLBs (external bark textures), pack
textures into self-contained GLBs, and write them into the viewer tools folder.

Sources:
  ~/Documents/GitHub/Exodus-SDK7/assets/models/Woodchopping/logs/*.glb

Outputs:
  viewer/public/buildings/{Sycamore,Poplar,Pine,Acacia,Wisteria}Log.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python extract_woodchopping_logs.py
"""

from __future__ import annotations

import os

import bpy

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.expanduser(
    "~/Documents/GitHub/Exodus-SDK7/assets/models/Woodchopping/logs"
)
OUT_DIR = os.path.join(ROOT, "viewer/public/buildings")

os.makedirs(OUT_DIR, exist_ok=True)

# (source filename, export stem) — bark textures are referenced by URI on disk
LOG_VARIANTS = [
    ("Sycamore_Log.glb", "SycamoreLog"),
    ("Poplar_Log.glb", "PoplarLog"),
    ("Pine_Log.glb", "PineLog"),
    ("weeiping_willow.glb", "AcaciaLog"),  # embeds Acacia_Bark
    ("BlueWillowLog.glb", "WisteriaLog"),  # embeds Wisteria_Bark
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


def export_selection(path: str) -> None:
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


def extract_one(src_name: str, out_stem: str) -> None:
    src = os.path.join(LOG_DIR, src_name)
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
    image_names = [img.name for img in bpy.data.images]
    print(f"  meshes={[m.name for m in meshes]}")
    print(f"  images={image_names}")

    out_path = os.path.join(OUT_DIR, f"{out_stem}.glb")
    export_selection(out_path)
    print(f"  -> {out_path} ({os.path.getsize(out_path) / 1024:.1f} KB)")


def main() -> None:
    print(f"Log source: {LOG_DIR}")
    print(f"Output:     {OUT_DIR}")
    for src, stem in LOG_VARIANTS:
        extract_one(src, stem)
    print("\nDONE — 5 logs exported with embedded textures.")


if __name__ == "__main__":
    main()
