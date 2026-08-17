"""
generate_grindscape_flag.py
===========================
Build a game-ready GrindScape banner: grey-brick pedestal, tall wooden pole,
gold spear finial, and a cloth flag carrying the circular GS logo.

The cloth is skinned to two hem bone chains and exported with a looping
"wave" clip: a travelling ripple with gusts, so it flows in the wind
in-engine rather than swinging like a paddle.

Handoff contract (matches fence / dock / castle pieces):
  - Origin at world (0, 0, 0), ground plane at z = 0.
  - +X = flag flies out from the pole
  - +Y = through the flag (billow axis)
  - +Z = up
  - Brick base centred on the origin footprint.

Outputs:
  ~/Desktop/Models/Buildings/GrindScapeFlag.glb
  viewer/public/buildings/GrindScapeFlag.glb
  flag_textures/FlagAlbedo.png   (composited cloth + logo)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_grindscape_flag.py
"""

from __future__ import annotations

import math
import os

import bmesh
import bpy


ROOT = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(ROOT, "flag_textures")
BRICK_DIR = os.path.join(ROOT, "wall_plaster_textures")
WOOD_DIR = os.path.join(ROOT, "castle_keep_textures")
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
LOGO_PATH = os.path.join(TEX_DIR, "GrindScapeLogo.png")
ALBEDO_PATH = os.path.join(TEX_DIR, "FlagAlbedo.png")
GREY_BRICK_PATH = os.path.join(TEX_DIR, "GreyBrick_BaseColor.png")
OUT_NAME = "GrindScapeFlag.glb"

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)
os.makedirs(TEX_DIR, exist_ok=True)


# ── Dimensions (metres, Z-up) ─────────────────────────────────────────────

# Brick pedestal
PLINTH_XY = 0.92
PLINTH_H = 0.14
BODY_XY = 0.70
BODY_H = 0.50
CAP_XY = 0.78
CAP_H = 0.10
SOCKET_XY = 0.22
SOCKET_H = 0.06
BASE_TOP = PLINTH_H + BODY_H + CAP_H          # 0.74

# Pole
POLE_R_BOT = 0.048
POLE_R_TOP = 0.036
POLE_Z0 = BASE_TOP - 0.04                     # seats into the cap
POLE_Z1 = 4.35
POLE_H = POLE_Z1 - POLE_Z0
POLE_SEGS = 12

# Finial
COLLAR_H = 0.055
COLLAR_R = 0.052
BALL_R = 0.070
SPIKE_H = 0.22
SPIKE_R = 0.028
FINIAL_BALL_Z = POLE_Z1 + COLLAR_H + BALL_R
SPIKE_TIP_Z = FINIAL_BALL_Z + BALL_R * 0.35 + SPIKE_H

# Flag cloth — hangs off the pole near the top, flying +X
FLAG_W = 1.72
FLAG_H = 1.08
FLAG_X0 = POLE_R_TOP + 0.012
FLAG_Z1 = POLE_Z1 - 0.04                      # top edge just under the collar
FLAG_Z0 = FLAG_Z1 - FLAG_H
FLAG_NX = 26                                  # subdivisions along fly
FLAG_NZ = 14                                  # subdivisions along hoist

# Rig: two bone chains (top + bottom hem).  Skinning blends bilinearly
# between them, so the two chains running out of phase twist the cloth
# diagonally instead of swinging it like a flat paddle.
BONE_COLS = 9                                 # segments along the fly
BONE_ROWS = 2                                 # 0 = top hem, 1 = bottom hem
REST_CURL = 0.06                              # metres of rest billow at the fly
REST_SAG = 0.11                               # metres the free corner droops
REST_SAG_BOTTOM = 0.55                        # extra droop weighting at the hem

# Wind clip — 4 s loop.  Every frequency below is a whole number of
# cycles across the clip so the last frame lands exactly on the first
# and the loop has no visible hitch.
FPS = 24
CLIP_FRAMES = 96
SWAY_CYCLES = 2                               # slow whole-cloth swing (0.5 Hz)
WAVE_CYCLES = 4                               # primary ripple (1.0 Hz)
WAVE_CYCLES_2 = 7                             # off-harmonic — breaks the metronome
FLUTTER_CYCLES = 11                           # fast chatter at the fly edge
GUST_CYCLES = 1                               # slow breathing of the whole cloth

# A travelling wave alone barely moves the silhouette: consecutive
# segments rotate against each other, so the chain cancels itself out
# into a shimmer.  Real banners read as a slow coherent swing (low lag,
# large amplitude) with ripples running out along it, so the sway and
# ripple terms are layered rather than tuned as one wave.
SWAY_LAG = 0.16                               # near-coherent → whole cloth swings
WAVE_LAG = 0.80                               # phase lag per segment → travelling wave
ROW_LAG = 0.62                                # bottom hem trails the top hem
SWAY_AMP = 0.22                               # slow swing at the fly end (rad)
BILLOW_AMP = 0.30                             # primary ripple
BILLOW_AMP_2 = 0.13
FLAP_AMP = 0.20                               # vertical undulation
TWIST_AMP = 0.24                              # roll about the fly axis
FLUTTER_AMP = 0.05
GUST_DEPTH = 0.32                             # 0 = steady wind, 1 = full lull
JITTER = 0.12                                 # per-segment amplitude variation


# ── Scene helpers ─────────────────────────────────────────────────────────

def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = CLIP_FRAMES + 1
    scene.frame_current = 1


def select_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_scale_rot(obj: bpy.types.Object) -> None:
    select_active(obj)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


def join_group(objects: list[bpy.types.Object], name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    if joined.data:
        joined.data.name = name
    return joined


def set_origin(obj: bpy.types.Object, world_point: tuple[float, float, float]) -> None:
    select_active(obj)
    bpy.context.scene.cursor.location = world_point
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")


def uv_cube(obj: bpy.types.Object, cube_size: float = 0.50) -> None:
    select_active(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=cube_size, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def uv_cylinder(obj: bpy.types.Object) -> None:
    select_active(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cylinder_project(
        direction="ALIGN_TO_OBJECT",
        align="POLAR_ZX",
        radius=1.0,
        correct_aspect=True,
        scale_to_bounds=True,
    )
    bpy.ops.object.mode_set(mode="OBJECT")


def load_image(path: str) -> bpy.types.Image:
    img = bpy.data.images.load(path, check_existing=True)
    img.pack()
    return img


def make_tex_mat(
    name: str,
    albedo_path: str,
    *,
    roughness: float = 0.88,
    metallic: float = 0.0,
    roughness_path: str | None = None,
    normal_path: str | None = None,
    double_sided: bool = True,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = not double_sided
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = load_image(albedo_path)
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if roughness_path and os.path.isfile(roughness_path):
        rtex = nt.nodes.new("ShaderNodeTexImage")
        rtex.image = load_image(roughness_path)
        rtex.image.colorspace_settings.name = "Non-Color"
        rtex.interpolation = "Linear"
        nt.links.new(rtex.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = roughness
    if normal_path and os.path.isfile(normal_path):
        ntex = nt.nodes.new("ShaderNodeTexImage")
        ntex.image = load_image(normal_path)
        ntex.image.colorspace_settings.name = "Non-Color"
        ntex.interpolation = "Linear"
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nmap.inputs["Strength"].default_value = 0.85
        nt.links.new(ntex.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def make_color_mat(
    name: str,
    color: tuple[float, float, float],
    *,
    roughness: float = 0.5,
    metallic: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
    return mat


def add_box(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    mat: bpy.types.Material,
    cube_size: float = 0.50,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    apply_scale_rot(obj)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    uv_cube(obj, cube_size=cube_size)
    return obj


def add_cylinder(
    name: str,
    center: tuple[float, float, float],
    radius: float,
    height: float,
    mat: bpy.types.Material,
    *,
    segments: int = POLE_SEGS,
    axis: str = "Z",
) -> bpy.types.Object:
    rotation = (0.0, 0.0, 0.0)
    if axis == "X":
        rotation = (0.0, math.pi / 2.0, 0.0)
    elif axis == "Y":
        rotation = (math.pi / 2.0, 0.0, 0.0)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=segments,
        radius=radius,
        depth=height,
        location=center,
        rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = name
    apply_scale_rot(obj)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    uv_cylinder(obj)
    return obj


def add_cone(
    name: str,
    center: tuple[float, float, float],
    radius1: float,
    depth: float,
    mat: bpy.types.Material,
    *,
    segments: int = 10,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments,
        radius1=radius1,
        radius2=0.0,
        depth=depth,
        location=center,
    )
    obj = bpy.context.active_object
    obj.name = name
    apply_scale_rot(obj)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def add_uv_sphere(
    name: str,
    center: tuple[float, float, float],
    radius: float,
    mat: bpy.types.Material,
    *,
    segments: int = 12,
    rings: int = 8,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=center,
    )
    obj = bpy.context.active_object
    obj.name = name
    apply_scale_rot(obj)
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def taper_cylinder(obj: bpy.types.Object, radius_bot: float, radius_top: float) -> None:
    """Scale verts in XY by height so a Z-up cylinder tapers."""
    zs = [v.co.z for v in obj.data.vertices]
    z0, z1 = min(zs), max(zs)
    span = max(z1 - z0, 1e-6)
    mesh = obj.data
    for v in mesh.vertices:
        t = (v.co.z - z0) / span
        r = radius_bot + (radius_top - radius_bot) * t
        # original cylinder radius is radius_bot (we built it that way)
        scale = r / radius_bot
        v.co.x *= scale
        v.co.y *= scale
    mesh.update()


# ── Flag albedo (dark cloth + centred circular logo) ──────────────────────

def composite_flag_albedo(
    logo_path: str,
    out_path: str,
    tex_w: int = 1024,
    tex_h: int = 640,
) -> bpy.types.Image:
    """Stamp the circular GS logo onto a dark rectangular cloth texture."""
    if not os.path.isfile(logo_path):
        raise FileNotFoundError(f"Logo not found: {logo_path}")

    logo = bpy.data.images.load(logo_path, check_existing=True)
    lw, lh = logo.size
    # Force a pixel read; Blender stores bottom-left origin, RGBA floats.
    lp = list(logo.pixels)
    nch = 4

    cloth_r, cloth_g, cloth_b = 0.045, 0.038, 0.036
    pixels = [0.0] * (tex_w * tex_h * nch)

    # Subtle horizontal weave so the cloth doesn't read as a flat fill.
    for y in range(tex_h):
        weave = 0.012 * math.sin(y * 0.35)
        for x in range(tex_w):
            grain = 0.010 * math.sin(x * 0.21 + y * 0.13)
            i = (y * tex_w + x) * nch
            pixels[i] = min(1.0, max(0.0, cloth_r + weave + grain))
            pixels[i + 1] = min(1.0, max(0.0, cloth_g + weave * 0.8 + grain))
            pixels[i + 2] = min(1.0, max(0.0, cloth_b + weave * 0.6 + grain))
            pixels[i + 3] = 1.0

    # Thin ember-gold hem matching the logo ring.
    hem = max(8, tex_h // 48)
    gold = (0.72, 0.38, 0.08)
    for y in range(tex_h):
        for x in range(tex_w):
            edge = min(x, y, tex_w - 1 - x, tex_h - 1 - y)
            if edge < hem:
                t = 1.0 - edge / hem
                t = t * t
                i = (y * tex_w + x) * nch
                pixels[i] = pixels[i] * (1.0 - t) + gold[0] * t
                pixels[i + 1] = pixels[i + 1] * (1.0 - t) + gold[1] * t
                pixels[i + 2] = pixels[i + 2] * (1.0 - t) + gold[2] * t

    # Logo: square, centred, ~86% of flag height so the fire ring has margin.
    dst_h = int(tex_h * 0.86)
    dst_w = dst_h
    ox = (tex_w - dst_w) // 2
    oy = (tex_h - dst_h) // 2

    for dy in range(dst_h):
        sy = min(lh - 1, int(dy * lh / dst_h))
        for dx in range(dst_w):
            sx = min(lw - 1, int(dx * lw / dst_w))
            si = (sy * lw + sx) * nch
            r, g, b, a = lp[si], lp[si + 1], lp[si + 2], lp[si + 3]
            px = ox + dx
            py = oy + dy
            di = (py * tex_w + px) * nch
            ia = 1.0 - a
            pixels[di] = r * a + pixels[di] * ia
            pixels[di + 1] = g * a + pixels[di + 1] * ia
            pixels[di + 2] = b * a + pixels[di + 2] * ia
            pixels[di + 3] = 1.0

    img = bpy.data.images.new("FlagAlbedo", tex_w, tex_h, alpha=True)
    img.pixels = pixels
    img.filepath_raw = out_path
    img.file_format = "PNG"
    img.save()
    img.pack()
    print(f"  flag albedo -> {out_path} ({os.path.getsize(out_path) / 1024.0:.1f} KB)")
    return img


def make_grey_brick_albedo(src: str, dst: str) -> None:
    """Recast the painterly red brick to cool slate grey.

    Keeps mortar, chips, and the matching normal / roughness maps; only
    the hue changes so the pedestal still reads as the same masonry.
    """
    src_img = bpy.data.images.load(src, check_existing=True)
    w, h = src_img.size
    lp = list(src_img.pixels)
    nch = 4
    out = [0.0] * (w * h * nch)
    for i in range(0, len(lp), nch):
        r, g, b, a = lp[i], lp[i + 1], lp[i + 2], lp[i + 3]
        luma = (0.30 * r + 0.50 * g + 0.20 * b) ** 0.92
        grey = 0.26 + 0.64 * luma
        out[i] = min(1.0, grey * 0.96)
        out[i + 1] = min(1.0, grey * 0.99)
        out[i + 2] = min(1.0, grey * 1.05)
        out[i + 3] = a
    img = bpy.data.images.new("GreyBrick", w, h, alpha=True)
    img.pixels = out
    img.filepath_raw = dst
    img.file_format = "PNG"
    img.save()
    img.pack()
    print(f"  grey brick -> {dst} ({os.path.getsize(dst) / 1024.0:.1f} KB)")


# ── Geometry ──────────────────────────────────────────────────────────────

def materials() -> dict[str, bpy.types.Material]:
    brick_src = os.path.join(BRICK_DIR, "WP_Brick_BaseColor.png")
    make_grey_brick_albedo(brick_src, GREY_BRICK_PATH)
    brick_rough = os.path.join(BRICK_DIR, "WP_Brick_Roughness.png")
    brick_norm = os.path.join(BRICK_DIR, "WP_Brick_Normal.png")
    wood_albedo = os.path.join(WOOD_DIR, "Wood_BaseColor.png")
    iron_albedo = os.path.join(WOOD_DIR, "Iron_BaseColor.png")

    mats = {
        "brick": make_tex_mat(
            "flag_brick",
            GREY_BRICK_PATH,
            roughness=0.92,
            roughness_path=brick_rough if os.path.isfile(brick_rough) else None,
            normal_path=brick_norm if os.path.isfile(brick_norm) else None,
        ),
        "wood": make_tex_mat("flag_wood", wood_albedo, roughness=0.78)
        if os.path.isfile(wood_albedo)
        else make_color_mat("flag_wood", (0.28, 0.17, 0.09), roughness=0.78),
        "iron": make_tex_mat("flag_iron", iron_albedo, roughness=0.45, metallic=0.75)
        if os.path.isfile(iron_albedo)
        else make_color_mat("flag_iron", (0.18, 0.17, 0.16), roughness=0.45, metallic=0.7),
        "gold": make_color_mat(
            "flag_gold", (0.83, 0.55, 0.16), roughness=0.28, metallic=0.85
        ),
        "cloth": make_tex_mat(
            "flag_cloth", ALBEDO_PATH, roughness=0.82, double_sided=True
        ),
    }
    return mats


def build_pedestal(mats: dict) -> list[bpy.types.Object]:
    parts: list[bpy.types.Object] = []
    brick = mats["brick"]
    parts.append(add_box(
        "base_plinth",
        (0.0, 0.0, PLINTH_H / 2.0),
        (PLINTH_XY, PLINTH_XY, PLINTH_H),
        brick,
        cube_size=0.42,
    ))
    parts.append(add_box(
        "base_body",
        (0.0, 0.0, PLINTH_H + BODY_H / 2.0),
        (BODY_XY, BODY_XY, BODY_H),
        brick,
        cube_size=0.42,
    ))
    parts.append(add_box(
        "base_cap",
        (0.0, 0.0, PLINTH_H + BODY_H + CAP_H / 2.0),
        (CAP_XY, CAP_XY, CAP_H),
        brick,
        cube_size=0.42,
    ))
    # Raised socket collar where the pole seats.
    parts.append(add_box(
        "base_socket",
        (0.0, 0.0, BASE_TOP + SOCKET_H / 2.0),
        (SOCKET_XY, SOCKET_XY, SOCKET_H),
        brick,
        cube_size=0.28,
    ))
    return parts


def pole_radius_at(z: float) -> float:
    t = min(max((z - POLE_Z0) / max(POLE_H, 1e-6), 0.0), 1.0)
    return POLE_R_BOT + (POLE_R_TOP - POLE_R_BOT) * t


def build_pole(mats: dict) -> list[bpy.types.Object]:
    parts: list[bpy.types.Object] = []
    z_mid = (POLE_Z0 + POLE_Z1) / 2.0
    pole = add_cylinder(
        "pole",
        (0.0, 0.0, z_mid),
        POLE_R_BOT,
        POLE_H,
        mats["wood"],
        segments=POLE_SEGS,
        axis="Z",
    )
    taper_cylinder(pole, POLE_R_BOT, POLE_R_TOP)
    parts.append(pole)

    # Three iron bands up the shaft.
    band_zs = (
        POLE_Z0 + 0.18,
        POLE_Z0 + POLE_H * 0.45,
        POLE_Z1 - 0.22,
    )
    for i, z in enumerate(band_zs):
        r = pole_radius_at(z)
        parts.append(add_cylinder(
            f"pole_band_{i}",
            (0.0, 0.0, z),
            r + 0.008,
            0.045,
            mats["iron"],
            segments=POLE_SEGS,
            axis="Z",
        ))
    return parts


def build_pole_sections(mats: dict) -> list[list[bpy.types.Object]]:
    """Three stacked tapered shaft segments, each with its iron band.

    Used by the modular construction animation so the pole grows in
    thirds instead of bisecting one mesh.
    """
    z_cuts = (
        POLE_Z0,
        POLE_Z0 + POLE_H / 3.0,
        POLE_Z0 + 2.0 * POLE_H / 3.0,
        POLE_Z1,
    )
    band_zs = (
        POLE_Z0 + 0.18,
        POLE_Z0 + POLE_H * 0.45,
        POLE_Z1 - 0.22,
    )
    sections: list[list[bpy.types.Object]] = []
    for i in range(3):
        z0, z1 = z_cuts[i], z_cuts[i + 1]
        h = z1 - z0
        z_mid = 0.5 * (z0 + z1)
        r0 = pole_radius_at(z0)
        r1 = pole_radius_at(z1)
        seg = add_cylinder(
            f"pole_seg_{i}",
            (0.0, 0.0, z_mid),
            r0,
            h,
            mats["wood"],
            segments=POLE_SEGS,
            axis="Z",
        )
        taper_cylinder(seg, r0, r1)
        parts = [seg]
        bz = band_zs[i]
        if z0 - 0.01 <= bz <= z1 + 0.01:
            r = pole_radius_at(bz)
            parts.append(add_cylinder(
                f"pole_band_{i}",
                (0.0, 0.0, bz),
                r + 0.008,
                0.045,
                mats["iron"],
                segments=POLE_SEGS,
                axis="Z",
            ))
        sections.append(parts)
    return sections


def build_finial(mats: dict) -> list[bpy.types.Object]:
    parts: list[bpy.types.Object] = []
    collar_z = POLE_Z1 + COLLAR_H / 2.0
    parts.append(add_cylinder(
        "finial_collar",
        (0.0, 0.0, collar_z),
        COLLAR_R,
        COLLAR_H,
        mats["iron"],
        segments=12,
        axis="Z",
    ))
    parts.append(add_uv_sphere(
        "finial_ball",
        (0.0, 0.0, FINIAL_BALL_Z),
        BALL_R,
        mats["gold"],
    ))
    spike_z = FINIAL_BALL_Z + BALL_R * 0.35 + SPIKE_H / 2.0
    parts.append(add_cone(
        "finial_spike",
        (0.0, 0.0, spike_z),
        SPIKE_R,
        SPIKE_H,
        mats["gold"],
        segments=10,
    ))
    # Small gold orb at the spear tip.
    parts.append(add_uv_sphere(
        "finial_tip",
        (0.0, 0.0, SPIKE_TIP_Z - 0.012),
        0.016,
        mats["gold"],
        segments=10,
        rings=6,
    ))
    return parts


def rest_offset(u: float, v: float) -> tuple[float, float]:
    """Rest-pose (y, dz) at fly fraction `u`, hoist fraction `v`.

    Gives the unposed cloth a J-curl plus gravity droop toward the free
    corner, so a still frame never reads as a flat board.  The armature
    reuses this so bones sit inside the surface they drive.
    """
    y = REST_CURL * (u * u)
    dz = -REST_SAG * (u * u) * (1.0 + REST_SAG_BOTTOM * (1.0 - v))
    return y, dz


def build_flag_mesh(mats: dict) -> bpy.types.Object:
    bm = bmesh.new()
    nx, nz = FLAG_NX, FLAG_NZ
    verts: list[bmesh.types.BMVert] = []
    for iz in range(nz + 1):
        for ix in range(nx + 1):
            u = ix / nx
            v = iz / nz
            y, dz = rest_offset(u, v)
            x = FLAG_X0 + u * FLAG_W
            z = FLAG_Z0 + v * FLAG_H + dz
            verts.append(bm.verts.new((x, y, z)))
    bm.verts.ensure_lookup_table()

    # UVs come from the grid indices, not from world position — the sag
    # offset would otherwise squash the logo toward the free corner.
    grid_uv = {
        verts[iz * (nx + 1) + ix]: (ix / nx, iz / nz)
        for iz in range(nz + 1)
        for ix in range(nx + 1)
    }

    uv_layer = bm.loops.layers.uv.new("UVMap")
    for iz in range(nz):
        for ix in range(nx):
            v00 = verts[iz * (nx + 1) + ix]
            v10 = verts[iz * (nx + 1) + ix + 1]
            v01 = verts[(iz + 1) * (nx + 1) + ix]
            v11 = verts[(iz + 1) * (nx + 1) + ix + 1]
            face = bm.faces.new((v00, v10, v11, v01))
            for loop in face.loops:
                loop[uv_layer].uv = grid_uv[loop.vert]

    mesh = bpy.data.meshes.new("flag_cloth")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("flag_cloth", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.clear()
    obj.data.materials.append(mats["cloth"])
    select_active(obj)
    bpy.ops.object.shade_smooth()
    return obj


def bone_name(row: int, col: int) -> str:
    return f"flag_{'top' if row == 0 else 'btm'}_{col}"


def row_v(row: int) -> float:
    """Hoist fraction of a bone row: top hem = 1.0, bottom hem = 0.0."""
    return 1.0 if row == 0 else 0.0


def build_armature() -> bpy.types.Object:
    """Two parallel chains running out the fly, one per hem.

    Both chains are pinned at the hoist, so rotating a bone pivots the
    cloth downstream of it and the pole-side edge never drifts.
    """
    arm_data = bpy.data.armatures.new("FlagArmatureData")
    arm = bpy.data.objects.new("FlagArmature", arm_data)
    bpy.context.collection.objects.link(arm)
    select_active(arm)
    bpy.ops.object.mode_set(mode="EDIT")

    for row in range(BONE_ROWS):
        v = row_v(row)
        prev = None
        for col in range(BONE_COLS):
            u0 = col / BONE_COLS
            u1 = (col + 1) / BONE_COLS
            y0, dz0 = rest_offset(u0, v)
            y1, dz1 = rest_offset(u1, v)
            bone = arm_data.edit_bones.new(bone_name(row, col))
            bone.head = (FLAG_X0 + u0 * FLAG_W, y0, FLAG_Z0 + v * FLAG_H + dz0)
            bone.tail = (FLAG_X0 + u1 * FLAG_W, y1, FLAG_Z0 + v * FLAG_H + dz1)
            # Roll 0 on a +X bone gives local Z ≈ world up, so local Z
            # billows the cloth in ±Y, local X flaps it vertically, and
            # local Y (the bone axis) rolls it.
            bone.roll = 0.0
            if prev is not None:
                bone.parent = prev
                bone.use_connect = True
            prev = bone

    bpy.ops.object.mode_set(mode="OBJECT")
    arm.display_type = "WIRE"
    arm.show_in_front = True
    return arm


def skin_flag(flag: bpy.types.Object, arm: bpy.types.Object) -> None:
    """Bilinear weights: 2 fly segments × 2 hems = 4 joints per vertex,
    exactly the glTF per-vertex joint budget."""
    for row in range(BONE_ROWS):
        for col in range(BONE_COLS):
            flag.vertex_groups.new(name=bone_name(row, col))

    n = BONE_COLS
    for vert in flag.data.vertices:
        u = min(max((vert.co.x - FLAG_X0) / FLAG_W, 0.0), 1.0)
        # Hoist fraction from the grid row, undoing the rest sag.
        f = min(max(u * n, 0.0), float(n) - 1e-6)
        c0 = min(int(f), n - 1)
        c1 = min(c0 + 1, n - 1)
        wc1 = (f - c0) if c1 != c0 else 0.0
        wc0 = 1.0 - wc1

        _, dz_top = rest_offset(u, 1.0)
        _, dz_btm = rest_offset(u, 0.0)
        z_top = FLAG_Z1 + dz_top
        z_btm = FLAG_Z0 + dz_btm
        v = min(max((vert.co.z - z_btm) / max(z_top - z_btm, 1e-6), 0.0), 1.0)

        cols = [(c0, wc0)]
        if c1 != c0:
            cols.append((c1, wc1))

        for row, w_row in ((0, v), (1, 1.0 - v)):
            if w_row <= 0.0:
                continue
            for col, w_col in cols:
                if w_col <= 0.0:
                    continue
                group = flag.vertex_groups[bone_name(row, col)]
                group.add([vert.index], w_row * w_col, "REPLACE")

    flag.parent = arm
    mod = flag.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    mod.use_vertex_groups = True
    mod.use_bone_envelopes = False


def animate_wave(arm: bpy.types.Object) -> bpy.types.Action:
    """Bake a looping wind clip onto both hem chains.

    Realism comes from four things rather than one big swing:
      • a travelling wave — each segment lags the one before it
        (WAVE_LAG), so ripples run out toward the fly instead of the
        whole cloth swinging as a unit;
      • two ripple frequencies that don't share a harmonic, which keeps
        the motion from reading as a metronome;
      • the bottom hem trailing the top hem (ROW_LAG), which twists the
        surface diagonally the way real fabric rolls;
      • a slow gust envelope plus fast flutter concentrated at the free
        edge, so the cloth breathes and the corner chatters.
    """
    select_active(arm)
    bpy.ops.object.mode_set(mode="POSE")

    action = bpy.data.actions.new(name="wave")
    arm.animation_data_create()
    arm.animation_data.action = action

    two_pi = 2.0 * math.pi
    n = BONE_COLS
    # Key one extra frame holding the t=0 pose so the loop wraps exactly.
    frames = range(1, CLIP_FRAMES + 2)

    for row in range(BONE_ROWS):
        row_phase = ROW_LAG * row
        for col in range(n):
            pb = arm.pose.bones[bone_name(row, col)]
            pb.rotation_mode = "XYZ"

            # Pinned at the hoist, loosest at the fly.
            span = (col + 0.5) / n
            # Uneven segment stiffness — a perfectly uniform ramp reads as
            # a mechanism. Golden-angle stride keeps it deterministic.
            jitter = 1.0 + JITTER * math.sin(2.399 * (col + 1) + 1.7 * row)
            ramp = (span ** 1.35) * jitter
            edge = span ** 3.0
            sway_lag = SWAY_LAG * col + row_phase * 0.4
            lag = WAVE_LAG * col + row_phase

            for frame in frames:
                t = (frame - 1) / CLIP_FRAMES
                gust = (1.0 - GUST_DEPTH) + GUST_DEPTH * (
                    0.5 + 0.5 * math.sin(two_pi * GUST_CYCLES * t)
                )
                sway = math.sin(two_pi * SWAY_CYCLES * t - sway_lag)
                w1 = math.sin(two_pi * WAVE_CYCLES * t - lag)
                w2 = math.sin(two_pi * WAVE_CYCLES_2 * t - lag * 1.6 + 1.1)
                flutter = math.sin(two_pi * FLUTTER_CYCLES * t - lag * 2.2)

                billow = ramp * gust * (
                    SWAY_AMP * sway + BILLOW_AMP * w1 + BILLOW_AMP_2 * w2
                )
                billow += FLUTTER_AMP * edge * flutter
                # Flap and twist trail the billow by a quarter cycle so the
                # cloth lifts as it rolls over, rather than in lockstep.
                flap = ramp * gust * FLAP_AMP * math.sin(
                    two_pi * WAVE_CYCLES * t - lag - 1.35
                )
                twist = ramp * gust * TWIST_AMP * math.sin(
                    two_pi * WAVE_CYCLES * t - lag - 0.55
                )

                pb.rotation_euler = (flap, twist, billow)
                pb.keyframe_insert(data_path="rotation_euler", frame=frame)

    for fcu in action.fcurves:
        for kp in fcu.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"

    bpy.ops.object.mode_set(mode="OBJECT")
    return action


def report(obj: bpy.types.Object, label: str) -> None:
    if obj.type != "MESH" or obj.data is None:
        print(f"  [{label}] type={obj.type}")
        return
    n_verts = len(obj.data.vertices)
    n_tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    mats = [m.name if m else "<none>" for m in obj.data.materials]
    mw = obj.matrix_world
    verts = [mw @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    print(
        f"  [{label}] verts={n_verts} tris={n_tris} mats={mats}"
    )
    print(
        f"  [{label}] bounds X[{min(xs):+.3f},{max(xs):+.3f}]  "
        f"Y[{min(ys):+.3f},{max(ys):+.3f}]  Z[{min(zs):+.3f},{max(zs):+.3f}]"
    )


def report_motion(flag: bpy.types.Object, rows: int = 8) -> None:
    """Sample the deformed cloth across the clip.

    Reports every frame for the global travel, and prints a short table
    covering one primary ripple period — sampling on a coarser stride
    aliases against the wave frequency and makes a moving flag look
    frozen.  `hem_gap` is the top-to-bottom distance at the fly edge:
    linear blend skinning pinches that gap if the two hem chains diverge
    too far, so it's the number to watch when retuning amplitudes.
    """
    scene = bpy.context.scene
    period = max(1, CLIP_FRAMES // WAVE_CYCLES)
    stride = max(1, period // rows)

    # Pick the fly-edge column from rest positions: armature deform keeps
    # vertex order, and a posed cloth curls back under an x threshold.
    fly_idx = [
        v.index
        for v in flag.data.vertices
        if v.co.x > FLAG_X0 + FLAG_W * 0.92
    ]

    y_min = z_min = float("inf")
    y_max = z_max = float("-inf")
    gap_min, gap_max = float("inf"), float("-inf")
    table: list[str] = []

    for frame in range(1, CLIP_FRAMES + 2):
        scene.frame_set(frame)
        deps = bpy.context.evaluated_depsgraph_get()
        evaluated = flag.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        fly = [mesh.vertices[i].co for i in fly_idx]
        ys = [c.y for c in fly]
        zs = [c.z for c in fly]
        gap = max(zs) - min(zs)
        y_min, y_max = min(y_min, min(ys)), max(y_max, max(ys))
        z_min, z_max = min(z_min, min(zs)), max(z_max, max(zs))
        gap_min, gap_max = min(gap_min, gap), max(gap_max, gap)
        if frame <= period and (frame - 1) % stride == 0:
            table.append(
                f"    {frame:4d}: Y[{min(ys):+.3f},{max(ys):+.3f}]  "
                f"Z[{min(zs):+.3f},{max(zs):+.3f}]  gap={gap:.3f}"
            )
        evaluated.to_mesh_clear()

    print(
        f"  fly-edge travel over clip: Y {y_max - y_min:.3f} m "
        f"[{y_min:+.3f},{y_max:+.3f}]  Z {z_max - z_min:.3f} m "
        f"[{z_min:+.3f},{z_max:+.3f}]"
    )
    print(
        f"  hem gap {gap_min:.3f}–{gap_max:.3f} m "
        f"({gap_min / FLAG_H * 100.0:.0f}–{gap_max / FLAG_H * 100.0:.0f}% "
        f"of {FLAG_H:.2f} m — under ~90% means skinning pinch)"
    )
    print(f"  one ripple period ({period} frames):")
    for line in table:
        print(line)
    scene.frame_set(1)


def export_glb(path: str, objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.select_set(True)
        if obj.type == "ARMATURE":
            for child in obj.children:
                child.hide_set(False)
                child.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_skins=True,
        export_animations=True,
        export_animation_mode="ACTIONS",
        export_force_sampling=True,
        export_nla_strips=False,
        export_anim_single_armature=True,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
    )


def main() -> None:
    print("=== GrindScape Flag ===")
    print(f"  logo: {LOGO_PATH}")
    print(f"  pole tip z={SPIKE_TIP_Z:.2f} m | flag {FLAG_W:.2f}×{FLAG_H:.2f} m")

    clear_scene()
    composite_flag_albedo(LOGO_PATH, ALBEDO_PATH)
    mats = materials()

    pedestal = build_pedestal(mats)
    pole = build_pole(mats)
    finial = build_finial(mats)
    base = join_group(pedestal, "flagpole_base")
    set_origin(base, (0.0, 0.0, 0.0))
    select_active(base)
    bpy.ops.object.shade_flat()
    report(base, "flagpole_base")

    shaft = join_group(pole + finial, "flagpole_shaft")
    set_origin(shaft, (0.0, 0.0, 0.0))
    select_active(shaft)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40.0))
    report(shaft, "flagpole_shaft")

    flag = build_flag_mesh(mats)
    arm = build_armature()
    skin_flag(flag, arm)
    action = animate_wave(arm)
    report(flag, "flag_cloth")
    print(
        f"  action '{action.name}'  {CLIP_FRAMES} frames @ {FPS} fps "
        f"({CLIP_FRAMES / FPS:.2f} s loop)  "
        f"bones={BONE_ROWS}×{BONE_COLS}  fcurves={len(action.fcurves)}"
    )
    report_motion(flag)

    export_objs = [base, shaft, flag, arm]
    print("  scene objects:")
    for obj in bpy.data.objects:
        print(f"    {obj.name:24s} {obj.type}")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, OUT_NAME)
        export_glb(path, export_objs)
        print(f"  -> {path} ({os.path.getsize(path) / 1024.0:.1f} KB)")

    # Keep a blend next to Desktop output for pose tweaks.
    blend_path = os.path.join(SOURCE_DIR, "GrindScapeFlag.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print(f"  -> {blend_path}")
    print("DONE")


if __name__ == "__main__":
    main()
