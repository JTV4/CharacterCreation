"""
texture_wall_plaster_straight.py
================================
Duplicate Wall_Plaster_Straight_Base.glb with a fresh Warm Clay texture
set (peach plaster, terracotta brick, honey/walnut wood trim).

Source (default):
  ~/Downloads/Wall_Plaster_Straight_Base.glb

Textures:
  wall_plaster_textures/WP_*.png
  (regenerate with generate_wall_plaster_textures.py after extracting
   source maps, or this script will extract + regenerate if missing)

Outputs:
  ~/Desktop/Models/Buildings/WallPlasterStraightClay.glb
  viewer/public/buildings/WallPlasterStraightClay.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python texture_wall_plaster_straight.py
"""

from __future__ import annotations

import os
import subprocess
import sys

import bpy

ROOT = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(ROOT, "wall_plaster_textures")
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
DEFAULT_SRC = os.path.expanduser("~/Downloads/Wall_Plaster_Straight_Base.glb")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)
os.makedirs(TEX_DIR, exist_ok=True)

# Source glTF material base-name → replacement texture set
MATERIAL_TEX = {
    "MI_Plaster": {
        "base": "WP_Plaster_BaseColor.png",
        "orm": "WP_Plaster_ORM.png",
        "normal": "WP_Plaster_Normal.png",
    },
    "MI_Brick": {
        "base": "WP_Brick_BaseColor.png",
        "rough": "WP_Brick_Roughness.png",
        "normal": "WP_Brick_Normal.png",
    },
    "MI_WoodTrim": {
        "base": "WP_WoodTrim_BaseColor.png",
        "rough": "WP_WoodTrim_Roughness.png",
        "normal": "WP_WoodTrim_Normal.png",
    },
}


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ensure_textures(src_glb: str) -> None:
    """Extract source maps + run generate_wall_plaster_textures.py if needed."""
    needed = [
        "WP_Plaster_BaseColor.png",
        "WP_Brick_BaseColor.png",
        "WP_WoodTrim_BaseColor.png",
        "WP_Plaster_Normal.png",
        "WP_Plaster_ORM.png",
        "WP_Brick_Normal.png",
        "WP_Brick_Roughness.png",
        "WP_WoodTrim_Normal.png",
        "WP_WoodTrim_Roughness.png",
    ]
    if all(os.path.isfile(os.path.join(TEX_DIR, n)) for n in needed):
        return

    extract_dir = "/tmp/wall_plaster_src"
    os.makedirs(extract_dir, exist_ok=True)
    # Extract embedded images from the source GLB into a temp Blender session
    # (we are already in Blender — extract now).
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src_glb)
    for img in bpy.data.images:
        if not img.size[0]:
            continue
        path = os.path.join(extract_dir, f"{img.name}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        print(f"  extracted {path}")

    gen = os.path.join(ROOT, "generate_wall_plaster_textures.py")
    env = os.environ.copy()
    env["WALL_PLASTER_SRC"] = extract_dir
    print("  regenerating warm-clay texture set…")
    subprocess.check_call(["python3", gen], env=env)


def load_image(filename: str) -> bpy.types.Image:
    path = os.path.join(TEX_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=False)
    img.pack()
    return img


def mat_key(name: str) -> str | None:
    base = name.split(".")[0]
    for key in MATERIAL_TEX:
        if base == key or base.startswith(key):
            return key
    return None


def _trace_tex_image(socket) -> bpy.types.Node | None:
    """Walk upstream links to find a connected TEX_IMAGE node."""
    if socket is None:
        return None
    for link in socket.links:
        node = link.from_node
        if node.type == "TEX_IMAGE":
            return node
        # Walk through common utility nodes (Normal Map, Separate, Math, …)
        for inp in node.inputs:
            found = _trace_tex_image(inp)
            if found is not None:
                return found
    return None


def replace_images_on_material(mat: bpy.types.Material, texset: dict) -> None:
    """Swap Image Texture node images via Principled BSDF socket tracing."""
    if not mat.use_nodes:
        return
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return

    role_files = {
        "base": texset.get("base"),
        "orm": texset.get("orm") or texset.get("rough"),
        "normal": texset.get("normal"),
    }
    loaded = {k: load_image(v) for k, v in role_files.items() if v}

    assignments = [
        ("Base Color", "base", "sRGB"),
        ("Roughness", "orm", "Non-Color"),
        ("Metallic", "orm", "Non-Color"),
        ("Normal", "normal", "Non-Color"),
    ]
    seen: set[int] = set()
    for socket_name, role, colorspace in assignments:
        sock = bsdf.inputs.get(socket_name)
        tex_node = _trace_tex_image(sock)
        if tex_node is None or role not in loaded:
            continue
        if id(tex_node) in seen and role == "orm":
            continue
        tex_node.image = loaded[role]
        try:
            tex_node.image.colorspace_settings.name = colorspace
        except Exception:
            pass
        seen.add(id(tex_node))
        print(f"    {mat.name}: {socket_name} ← {loaded[role].name}")


def recenter_to_origin() -> None:
    """Source wall was authored ~75 m off on Y.  Snap every mesh so its
    bounding-box sits on Z=0 with X/Y centered on the wall centre-line —
    matches CastleWallSegment / other viewer buildings."""
    import mathutils

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        return

    # World-space bounds across all meshes
    coords: list[mathutils.Vector] = []
    for obj in meshes:
        for v in obj.data.vertices:
            coords.append(obj.matrix_world @ v.co)
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    z0 = min(zs)
    delta = mathutils.Vector((-cx, -cy, -z0))
    print(f"  recenter delta=({delta.x:.3f}, {delta.y:.3f}, {delta.z:.3f})")

    for obj in meshes:
        # Bake current TRS, then shift vertices in object space.
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        # Inverse of world translation applied in local space (now identity TRS)
        for v in obj.data.vertices:
            v.co += delta
        obj.data.update()
        obj.location = (0.0, 0.0, 0.0)


def export_glb(path: str) -> None:
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


def main() -> None:
    src = DEFAULT_SRC
    if "--" in sys.argv:
        i = sys.argv.index("--")
        if i + 1 < len(sys.argv):
            src = os.path.expanduser(sys.argv[i + 1])
    if not os.path.isfile(src):
        raise FileNotFoundError(src)

    print("\n=== Texture Wall Plaster Straight (Warm Clay) ===")
    print(f"  source: {src}")
    ensure_textures(src)

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()
    recenter_to_origin()

    # Rename root mesh for the new asset identity
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            obj.name = "WallPlasterStraightClay"
            if obj.data:
                obj.data.name = "WallPlasterStraightClay"

    for mat in list(bpy.data.materials):
        key = mat_key(mat.name)
        if key is None:
            print(f"  skip unknown material: {mat.name}")
            continue
        replace_images_on_material(mat, MATERIAL_TEX[key])
        # Friendly export names
        new_name = {
            "MI_Plaster": "wall_plaster_clay",
            "MI_Brick": "wall_brick_terracotta",
            "MI_WoodTrim": "wall_wood_walnut",
        }[key]
        mat.name = new_name
        print(f"  textured {key} → {new_name}")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "WallPlasterStraightClay.glb")
        export_glb(out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    # Also write a recentered copy of the ORIGINAL textures (Base variant)
    # so Straight (Base) is visible in the viewer too.
    print("\n=== Recenter Wall Plaster Straight (Base) ===")
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()
    recenter_to_origin()
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            obj.name = "WallPlasterStraightBase"
            if obj.data:
                obj.data.name = "WallPlasterStraightBase"
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "WallPlasterStraightBase.glb")
        export_glb(out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    print("DONE")


if __name__ == "__main__":
    main()
