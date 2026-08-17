"""
generate_grind_coin.py
======================
3D GrindCoin GLB from ~/Desktop/GrindCoin(G).png.

Clean-handoff contract (same as other props):
  - Origin at world (0, 0, 0) = coin centre, bottom on the ground
  - Coin lies flat in XY, bottom face at z = 0
  - Root scale (1,1,1), transforms baked
  - Single joined mesh
  - Two material slots:
      grind_coin_face — cleaned PNG on the recessed face beds
      grind_coin_rim  — solid smooth gold on rim + side wall

The source PNG has a soft anti-aliased alpha fringe. Mapping that fringe
onto the geometric rim produced the jagged/noisy edge ring. We fix it by:
  1. Compositing the art onto opaque gold and upscaling (no alpha fringe)
  2. UV-mapping ONLY the face beds to the art (inset so we skip the fringe)
  3. Assigning a solid-gold material to the rim / side (no texture sample)

Outputs:
  ~/Desktop/Models/Buildings/GrindCoin.glb
  viewer/public/buildings/GrindCoin.glb
  viewer/public/buildings/textures/GrindCoin.png

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_grind_coin.py
"""

from __future__ import annotations

import math
import os
import subprocess
import sys

import bmesh
import bpy

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
TEX_DIR = os.path.join(VIEWER_DIR, "textures")
REF_PNG = os.path.expanduser("~/Desktop/GrindCoin(G).png")
TEX_PNG = os.path.join(TEX_DIR, "GrindCoin.png")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)
os.makedirs(TEX_DIR, exist_ok=True)

OUT_NAME = "GrindCoin.glb"

# Metres — sized like a single mining ore chunk (~1 m across).
RADIUS = 0.50
THICKNESS = 0.070
RIM_WIDTH = 0.070
RIM_RAISE = 0.020
FACE_RECESS = 0.009
SEGMENTS = 256
BEVEL_WIDTH = 0.008
BEVEL_SEGS = 5

# Face UV uses this fraction of the texture radius so soft fringe is skipped.
FACE_UV_INSET = 0.90

GOLD_RGB = (0.90, 0.66, 0.14)
TEX_SIZE = 1024


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def shutil_which_python() -> str:
    import shutil
    for candidate in ("python3", "/usr/bin/python3", "/opt/homebrew/bin/python3", sys.executable):
        path = shutil.which(candidate) if not candidate.startswith("/") else candidate
        if path and os.path.isfile(path):
            return path
    return sys.executable


def prepare_texture() -> str:
    """Composite PNG onto opaque gold, harden the circle, upscale.

    Runs in a subprocess so Blender's bundled Python doesn't need Pillow.
    """
    if not os.path.isfile(REF_PNG):
        raise FileNotFoundError(REF_PNG)

    helper = r"""
import sys
from PIL import Image, ImageFilter
import numpy as np

src, dst, size = sys.argv[1], sys.argv[2], int(sys.argv[3])
img = Image.open(src).convert("RGBA")
# Upscale with LANCZOS for a sharper G at coin scale
img = img.resize((size, size), Image.Resampling.LANCZOS)
arr = np.array(img).astype(np.float32)
rgb = arr[:, :, :3]
a = arr[:, :, 3:4] / 255.0

# Gold fill behind any transparency (kills fringe rainbow / black bleed)
gold = np.array([230.0, 168.0, 36.0], dtype=np.float32)
comp = rgb * a + gold * (1.0 - a)

# Harden alpha: anything mostly opaque stays; fringe snapped to gold fill
# (already composited). Output is fully opaque.
out = np.zeros((size, size, 4), dtype=np.uint8)
out[:, :, :3] = np.clip(comp, 0, 255).astype(np.uint8)
out[:, :, 3] = 255

# Very light bilateral-ish smooth only on the outer 2%% ring to kill
# leftover jag from the original anti-alias (optional box blur on mask).
yy, xx = np.mgrid[0:size, 0:size]
cx = cy = (size - 1) / 2.0
rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
R = size * 0.5
outer = (rr > 0.96 * R).astype(np.float32)
# Mild blur of outer ring only
blurred = Image.fromarray(out[:, :, :3]).filter(ImageFilter.GaussianBlur(radius=0.8))
blurred_arr = np.array(blurred)
mix = outer[:, :, None]
out[:, :, :3] = (
    out[:, :, :3].astype(np.float32) * (1.0 - mix * 0.65)
    + blurred_arr.astype(np.float32) * (mix * 0.65)
).astype(np.uint8)

Image.fromarray(out, mode="RGBA").save(dst, optimize=True)
print(f"wrote {dst} {size}x{size}")
"""
    # Use system Python (Pillow); Blender's bundled interpreter often lacks it.
    py = shutil_which_python()
    proc = subprocess.run(
        [py, "-c", helper, REF_PNG, TEX_PNG, str(TEX_SIZE)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        # Fallback: plain copy via Blender if Pillow path fails
        print("  texture prep warning:", proc.stderr.strip() or proc.stdout.strip())
        import shutil
        shutil.copy2(REF_PNG, TEX_PNG)
    else:
        print(f"  {proc.stdout.strip()}")
    return TEX_PNG


def make_face_material(tex_path: str) -> bpy.types.Material:
    mat = bpy.data.materials.new(name="grind_coin_face")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (400, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)

    tex = nodes.new("ShaderNodeTexImage")
    tex.location = (-220, 40)
    img = bpy.data.images.load(tex_path)
    img.alpha_mode = "NONE"
    tex.image = img
    tex.interpolation = "Linear"
    tex.extension = "EXTEND"

    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.82
    bsdf.inputs["Roughness"].default_value = 0.28
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.5
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.5

    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_rim_material() -> bpy.types.Material:
    mat = bpy.data.materials.new(name="grind_coin_rim")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.inputs["Base Color"].default_value = (*GOLD_RGB, 1.0)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.22
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.55
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.55
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def build_coin_body() -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=SEGMENTS,
        radius=RADIUS,
        depth=THICKNESS,
        location=(0.0, 0.0, THICKNESS * 0.5),
    )
    coin = bpy.context.active_object
    coin.name = "GrindCoin"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bm = bmesh.new()
    bm.from_mesh(coin.data)
    bm.faces.ensure_lookup_table()

    top = max(
        (f for f in bm.faces if f.normal.z > 0.9),
        key=lambda f: f.calc_center_median().z,
    )
    ret = bmesh.ops.inset_individual(
        bm, faces=[top], thickness=RIM_WIDTH, depth=0.0, use_even_offset=True,
    )
    inner_faces = ret["faces"]

    face_z = THICKNESS - FACE_RECESS
    for f in inner_faces:
        for v in f.verts:
            v.co.z = face_z

    for v in bm.verts:
        r = math.hypot(v.co.x, v.co.y)
        if v.co.z > THICKNESS - 1e-4 and r > RADIUS - RIM_WIDTH * 0.95:
            v.co.z = THICKNESS + RIM_RAISE

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(coin.data)
    bm.free()
    coin.data.update()
    return coin


def assign_uvs_and_materials(
    coin: bpy.types.Object,
    face_mat: bpy.types.Material,
    rim_mat: bpy.types.Material,
) -> None:
    """Face beds → textured material + inset planar UVs.
    Everything else → solid rim gold (no texture fringe)."""
    coin.data.materials.clear()
    coin.data.materials.append(face_mat)  # slot 0
    coin.data.materials.append(rim_mat)   # slot 1

    bm = bmesh.new()
    bm.from_mesh(coin.data)
    while bm.loops.layers.uv:
        bm.loops.layers.uv.remove(bm.loops.layers.uv[0])
    uv_layer = bm.loops.layers.uv.new("UVMap")

    face_r_max = RADIUS - RIM_WIDTH * 0.85
    face_z_top = THICKNESS - FACE_RECESS
    face_z_bot = 0.0

    for face in bm.faces:
        n = face.normal
        center = face.calc_center_median()
        r = math.hypot(center.x, center.y)

        is_face_bed = (
            abs(n.z) > 0.85
            and r < face_r_max
            and (
                abs(center.z - face_z_top) < FACE_RECESS * 2.5
                or abs(center.z - face_z_bot) < FACE_RECESS * 2.5
                or center.z < THICKNESS * 0.35  # bottom after sit_on_ground later
            )
        )

        # Before sit_on_ground: top face bed near face_z, bottom near 0.
        # After bevel, z values shift slightly — use normal + radius primarily.
        is_face_bed = abs(n.z) > 0.85 and r <= (RADIUS - RIM_WIDTH * 0.55)

        if is_face_bed:
            face.material_index = 0
            for loop in face.loops:
                co = loop.vert.co
                # Map face bed across FACE_UV_INSET of the texture so the
                # soft outer fringe of the art is never sampled.
                u = 0.5 + (co.x / RADIUS) * 0.5 * FACE_UV_INSET
                v = 0.5 + (co.y / RADIUS) * 0.5 * FACE_UV_INSET
                if n.z < 0:
                    u = 1.0 - u
                loop[uv_layer].uv = (u, v)
        else:
            face.material_index = 1
            for loop in face.loops:
                # Dummy UVs — rim material has no texture
                loop[uv_layer].uv = (0.0, 0.0)

    bm.to_mesh(coin.data)
    bm.free()
    coin.data.update()


def bevel_coin(coin: bpy.types.Object) -> None:
    mod = coin.modifiers.new(name="bevel", type="BEVEL")
    mod.width = BEVEL_WIDTH
    mod.segments = BEVEL_SEGS
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30)
    mod.miter_outer = "MITER_ARC"
    bpy.context.view_layer.objects.active = coin
    bpy.ops.object.modifier_apply(modifier=mod.name)


def sit_on_ground(coin: bpy.types.Object) -> None:
    zs = [v.co.z for v in coin.data.vertices]
    zmin = min(zs)
    for v in coin.data.vertices:
        v.co.z -= zmin
    coin.data.update()
    coin.location = (0.0, 0.0, 0.0)


def shade_smooth_clean(coin: bpy.types.Object) -> None:
    """Smooth the cylindrical silhouette; keep rim/face transitions sharp."""
    bpy.ops.object.select_all(action="DESELECT")
    coin.select_set(True)
    bpy.context.view_layer.objects.active = coin
    bpy.ops.object.shade_smooth()

    # Auto-smooth / sharp edges by angle (Blender 4.1 uses modifier or mesh flag)
    try:
        coin.data.use_auto_smooth = True
        coin.data.auto_smooth_angle = math.radians(35)
    except Exception:
        # Blender 4.1+ may have removed use_auto_smooth — use EdgeSplit
        mod = coin.modifiers.new(name="EdgeSplit", type="EDGE_SPLIT")
        mod.split_angle = math.radians(35)
        mod.use_edge_angle = True
        mod.use_edge_sharp = True
        bpy.ops.object.modifier_apply(modifier=mod.name)


def export_glb(obj: bpy.types.Object, path: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
    )


def main() -> None:
    clear_scene()
    print("=== GrindCoin (clean rim) ===")
    tex_path = prepare_texture()

    coin = build_coin_body()
    bevel_coin(coin)

    face_mat = make_face_material(tex_path)
    rim_mat = make_rim_material()
    assign_uvs_and_materials(coin, face_mat, rim_mat)

    sit_on_ground(coin)
    # Re-tag materials after z-shift (bottom face z changed)
    assign_uvs_and_materials(coin, face_mat, rim_mat)
    shade_smooth_clean(coin)

    n_face = sum(1 for p in coin.data.polygons if p.material_index == 0)
    n_rim = sum(1 for p in coin.data.polygons if p.material_index == 1)
    print(f"  verts={len(coin.data.vertices)} faces={len(coin.data.polygons)}")
    print(f"  face polys={n_face}  rim polys={n_rim}")
    print(f"  size Ø={RADIUS * 200:.1f} cm  thick≈{(THICKNESS + RIM_RAISE) * 1000:.1f} mm")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, OUT_NAME)
        export_glb(coin, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")

    print("DONE")


if __name__ == "__main__":
    main()
