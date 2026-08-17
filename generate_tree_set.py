"""
generate_tree_set.py
====================
Fortnite-style landmark trees for browser MMORPG use:

  Tall bare trunk → branches + leaf canopy clustered near the TOP.

Seven species, each its own GLB with unique generated atlases:

  1. SycamoreTree.glb     — broad rounded crown
  2. PoplarTree.glb       — tall columnar crown
  3. EvergreenTree.glb    — conical layered needle canopy
  4. OakTree.glb          — wide stout crown
  5. WeepingWillowTree.glb — high crown with hanging cascades
  6. LumenbarkTree.glb    — original fun design (teal/magenta orbs)
  7. PalmTree.glb         — tall ringed trunk, radiating arched fronds
  8. PalmTreeLeaning.glb  — beach palm that hangs over (crown ~70° lean)

Clean-handoff (same as other building assets):
  - Origin at (0,0,0) on ground, trunk centre
  - Single joined mesh, transforms baked
  - Materials: tree_bark (opaque) + tree_leaves (MASK, double-sided)
  - ~900–1,400 tris each

Textures live in tree_textures/ (Gen* atlases, 256²).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_tree_set.py
"""

from __future__ import annotations

import math
import os
import random

import bpy
import bmesh
from mathutils import Vector


SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")
TEX_DIR = os.path.abspath("tree_textures")
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)


# ── Per-species configs ───────────────────────────────────────────────────
# Fortnite silhouette: trunk_height is most of the tree; canopy_z sits
# near the top; branches only spawn in the upper fraction of the trunk.

TREE_DEFS: list[dict] = [
    {
        "id": "sycamore",
        "display": "Sycamore",
        "out_name": "SycamoreTree.glb",
        "bark": "BarkDeciduous.png",
        "leaves": "LeavesSycamore.png",
        "seed": 11,
        "trunk_h": 9.0,
        "r_base": 0.42,
        "r_top": 0.12,
        "sides": 10,
        "rings": 12,
        "tip_extra": 0.35,
        # Branches: (yaw, pitch_from_horiz, length, r_base, r_tip, z_frac)
        "branches": [
            (15, 28, 2.4, 0.11, 0.035, 0.72),
            (70, 32, 2.2, 0.10, 0.032, 0.76),
            (125, 26, 2.5, 0.11, 0.034, 0.74),
            (180, 34, 2.1, 0.095, 0.030, 0.78),
            (235, 30, 2.3, 0.10, 0.032, 0.75),
            (290, 36, 2.0, 0.09, 0.028, 0.80),
            (340, 24, 2.2, 0.095, 0.030, 0.77),
        ],
        "canopy_c": (0.1, 0.05, 10.6),
        "canopy_r": (3.2, 3.0, 1.7),
        "leaf_cards": 70,
        "leaf_hw": (0.85, 1.35),
        "leaf_hh": (0.70, 1.15),
        "droop": 0.0,
        "style": "round",
    },
    {
        "id": "poplar",
        "display": "Poplar",
        "out_name": "PoplarTree.glb",
        "bark": "BarkDeciduous.png",
        "leaves": "LeavesPoplar.png",
        "seed": 22,
        "trunk_h": 11.5,
        "r_base": 0.28,
        "r_top": 0.08,
        "sides": 9,
        "rings": 14,
        "tip_extra": 0.40,
        "branches": [
            (10, 55, 1.6, 0.07, 0.022, 0.70),
            (55, 58, 1.5, 0.065, 0.020, 0.74),
            (100, 52, 1.7, 0.07, 0.022, 0.72),
            (150, 60, 1.4, 0.06, 0.018, 0.78),
            (200, 54, 1.6, 0.065, 0.020, 0.76),
            (250, 57, 1.5, 0.06, 0.018, 0.80),
            (300, 50, 1.55, 0.065, 0.020, 0.75),
            (340, 56, 1.45, 0.06, 0.018, 0.82),
        ],
        "canopy_c": (0.05, 0.0, 12.4),
        # Wider/taller leaf volume — trunk/branches unchanged
        "canopy_r": (1.90, 1.85, 3.35),
        "leaf_cards": 118,
        "leaf_hw": (0.72, 1.20),
        "leaf_hh": (0.95, 1.55),
        "leaf_cross": 0.62,             # extra overlapping cards for fluff
        "droop": 0.0,
        "style": "column",
    },
    {
        "id": "evergreen",
        "display": "Evergreen",
        "out_name": "EvergreenTree.glb",
        "bark": "BarkEvergreen.png",
        "leaves": "LeavesEvergreen.png",
        "seed": 33,
        "trunk_h": 11.0,
        "r_base": 0.34,
        "r_top": 0.06,
        "sides": 9,
        "rings": 14,
        "tip_extra": 0.50,
        # Whorl-style laterals — mostly horizontal
        "branches": [
            (0, 12, 2.8, 0.08, 0.025, 0.55),
            (60, 10, 2.6, 0.075, 0.022, 0.55),
            (120, 14, 2.7, 0.08, 0.024, 0.55),
            (180, 11, 2.5, 0.07, 0.022, 0.55),
            (240, 13, 2.6, 0.075, 0.022, 0.55),
            (300, 10, 2.5, 0.07, 0.020, 0.55),
            (30, 14, 2.2, 0.065, 0.020, 0.68),
            (90, 12, 2.1, 0.06, 0.018, 0.68),
            (150, 15, 2.2, 0.065, 0.020, 0.68),
            (210, 11, 2.0, 0.06, 0.018, 0.68),
            (270, 13, 2.1, 0.06, 0.018, 0.68),
            (330, 12, 2.0, 0.055, 0.016, 0.68),
            (45, 16, 1.5, 0.05, 0.015, 0.82),
            (135, 14, 1.4, 0.048, 0.014, 0.82),
            (225, 15, 1.5, 0.05, 0.015, 0.82),
            (315, 13, 1.4, 0.048, 0.014, 0.82),
        ],
        "canopy_c": (0.0, 0.0, 8.5),
        "canopy_r": (2.6, 2.6, 3.8),
        "leaf_cards": 80,
        "leaf_hw": (0.70, 1.20),
        "leaf_hh": (0.55, 0.95),
        "droop": 0.0,
        "style": "cone",
    },
    {
        "id": "oak",
        "display": "Oak",
        "out_name": "OakTree.glb",
        "bark": "BarkDeciduous.png",
        "leaves": "LeavesOak.png",
        "seed": 44,
        "trunk_h": 8.0,
        "r_base": 0.55,
        "r_top": 0.16,
        "sides": 11,
        "rings": 11,
        "tip_extra": 0.30,
        "branches": [
            (20, 22, 2.8, 0.14, 0.040, 0.68),
            (80, 26, 2.5, 0.13, 0.038, 0.72),
            (140, 20, 2.9, 0.14, 0.040, 0.70),
            (200, 28, 2.4, 0.12, 0.035, 0.74),
            (260, 24, 2.7, 0.13, 0.038, 0.71),
            (320, 18, 2.6, 0.12, 0.036, 0.73),
        ],
        "canopy_c": (0.15, 0.1, 9.6),
        "canopy_r": (3.6, 3.4, 1.9),
        "leaf_cards": 74,
        "leaf_hw": (0.90, 1.45),
        "leaf_hh": (0.75, 1.20),
        "droop": 0.0,
        "style": "round",
    },
    {
        # Reference weeping willow (Fortnite-style):
        #   sturdy trunk splits into upward branches → dense rounded
        #   volume of bright hanging willow-leaf curtains (no lichen).
        "id": "willow",
        "display": "Weeping Willow",
        "out_name": "WeepingWillowTree.glb",
        "bark": "BarkDeciduous.png",
        "leaves": "LeavesWillow.png",
        "seed": 84,
        "trunk_h": 9.5,
        "r_base": 0.42,
        "r_top": 0.13,
        "sides": 10,
        "rings": 14,
        "tip_extra": 0.55,
        # Upward primaries that open into a high scaffold
        "branches": [
            (10, 42, 3.2, 0.11, 0.030, 0.72),
            (55, 38, 3.0, 0.10, 0.028, 0.76),
            (100, 45, 3.4, 0.11, 0.030, 0.70),
            (145, 36, 2.9, 0.10, 0.026, 0.78),
            (190, 44, 3.3, 0.11, 0.030, 0.73),
            (235, 34, 2.8, 0.095, 0.026, 0.80),
            (280, 40, 3.1, 0.10, 0.028, 0.74),
            (325, 42, 3.2, 0.11, 0.030, 0.72),
        ],
        # Rounded drooping canopy volume (filled with hanging strands)
        "canopy_c": (0.0, 0.0, 10.2),
        "canopy_r": (3.6, 3.6, 2.4),
        # Sparse top clumps only — volume comes from hang curtains
        "leaf_cards": 36,
        "leaf_hw": (0.55, 0.90),
        "leaf_hh": (0.45, 0.75),
        "droop": 0.55,
        "style": "weep",
        # Dense layered hanging willow strands (the silhouette)
        "strand_count": 180,
        "strand_hw": (0.18, 0.38),
        "strand_hh": (1.80, 3.40),
        "strand_hang": (0.4, 1.8),
        "strand_min_anchor_z": 7.2,
        "strand_floor_frac": 0.38,   # curtains reach mid-trunk; base clear
        "lichen_count": 0,
    },
    {
        # Original fun design — tall pale trunk, teal/magenta orb canopy.
        "id": "lumenbark",
        "display": "Lumenbark",
        "out_name": "LumenbarkTree.glb",
        "bark": "BarkLumenbark.png",
        "leaves": "LeavesLumenbark.png",
        "seed": 66,
        "trunk_h": 10.5,
        "r_base": 0.36,
        "r_top": 0.10,
        "sides": 10,
        "rings": 13,
        "tip_extra": 0.45,
        "branches": [
            (0, 30, 2.0, 0.09, 0.028, 0.70),
            (72, 34, 1.9, 0.085, 0.026, 0.74),
            (144, 28, 2.1, 0.09, 0.028, 0.72),
            (216, 36, 1.8, 0.08, 0.024, 0.78),
            (288, 32, 2.0, 0.085, 0.026, 0.76),
        ],
        "canopy_c": (0.0, 0.0, 11.8),
        "canopy_r": (2.8, 2.8, 1.8),
        "leaf_cards": 68,
        "leaf_hw": (0.75, 1.25),
        "leaf_hh": (0.75, 1.25),
        "droop": 0.0,
        "style": "orbs",   # spiral tiered clusters
    },
    {
        # Tropical palm: ringed columnar trunk, crownshaft swell,
        # multi-segment fronds that arch out and droop.
        "id": "palm",
        "display": "Palm",
        "out_name": "PalmTree.glb",
        "bark": "BarkPalm.png",
        "leaves": "LeavesPalm.png",
        "seed": 77,
        "trunk_h": 10.5,
        "r_base": 0.34,
        "r_top": 0.20,          # palms stay relatively thick at the crown
        "sides": 12,
        "rings": 22,
        "tip_extra": 0.45,
        "lean_deg": 8.0,            # gentle natural lean
        "lean_yaw": 25.0,
        "lean_power": 1.35,
        # Short upward stubs just under the frond crown
        "branches": [
            (0, 68, 0.70, 0.07, 0.032, 0.93),
            (55, 62, 0.65, 0.065, 0.030, 0.94),
            (110, 70, 0.72, 0.07, 0.032, 0.92),
            (165, 60, 0.62, 0.06, 0.028, 0.95),
            (220, 66, 0.68, 0.065, 0.030, 0.93),
            (275, 64, 0.66, 0.06, 0.028, 0.94),
            (330, 68, 0.70, 0.065, 0.030, 0.93),
        ],
        "canopy_c": (0.0, 0.0, 11.0),
        "canopy_r": (4.6, 4.6, 1.8),
        "leaf_cards": 42,           # used as frond count
        "leaf_hw": (0.68, 1.12),    # frond width
        "leaf_hh": (2.9, 4.4),      # frond length
        "droop": 0.95,
        "style": "palm",
        "frond_cols": 6,            # atlas columns in LeavesPalm.png
        "frond_segs": 5,            # quads per frond along the arch
        "coconut_count": 5,
    },
    {
        # Beach / cliff palm — trunk rises then hangs over hard so the
        # crown leans ~70° from vertical (in the 45–90° range).
        "id": "palm_leaning",
        "display": "Leaning Palm",
        "out_name": "PalmTreeLeaning.glb",
        "bark": "BarkPalm.png",
        "leaves": "LeavesPalm.png",
        "seed": 91,
        "trunk_h": 11.5,
        "r_base": 0.36,
        "r_top": 0.19,
        "sides": 12,
        "rings": 28,
        "tip_extra": 0.40,
        "lean_deg": 80.0,           # crown tip ~80° from upright (in 45–90°)
        "lean_yaw": 0.0,            # hangs over +X
        "lean_power": 1.55,         # upright base, smooth hang-over up top
        "branches": [
            (0, 55, 0.60, 0.065, 0.028, 0.94),
            (60, 48, 0.55, 0.06, 0.026, 0.95),
            (120, 58, 0.62, 0.065, 0.028, 0.93),
            (180, 45, 0.52, 0.055, 0.024, 0.96),
            (240, 52, 0.58, 0.06, 0.026, 0.94),
            (300, 50, 0.56, 0.055, 0.024, 0.95),
        ],
        "canopy_c": (6.5, 0.0, 7.2),
        "canopy_r": (4.0, 4.0, 2.2),
        "leaf_cards": 40,
        "leaf_hw": (0.65, 1.08),
        "leaf_hh": (2.8, 4.2),
        "droop": 1.15,
        "style": "palm",
        "frond_cols": 6,
        "frond_segs": 5,
        "coconut_count": 4,
        "gravity_bias": 0.65,       # pull frond tips toward world -Z
    },
]


# ── Materials ─────────────────────────────────────────────────────────────

def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_image(filename: str) -> bpy.types.Image:
    path = os.path.join(TEX_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    # Unique datablock name per load so species don't share images
    img = bpy.data.images.load(path, check_existing=False)
    img.name = os.path.splitext(filename)[0]
    img.pack()
    return img


def make_bark_material(name: str, img: bpy.types.Image) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.92
    return mat


def make_leaf_material(
    name: str,
    img: bpy.types.Image,
    *,
    alpha_threshold: float = 0.15,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "CLIP"
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "CLIP"
    # Lower threshold keeps soft feathered alpha fringes (lichen).
    mat.alpha_threshold = alpha_threshold
    mat.use_backface_culling = False
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.78
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.12
    return mat


# ── Geometry ──────────────────────────────────────────────────────────────

def _trunk_radius_at(t: float, r_base: float, r_top: float, style: str = "round") -> float:
    if style == "palm":
        # Columnar palm: base flare, leaf-scar rings, crownshaft swell
        flare = 1.0 + 0.70 * max(0.0, 1.0 - t / 0.14) ** 2
        taper = r_base * (1.0 - t * 0.55) + r_top * (t * 0.55)
        # Periodic leaf-scar ridges (reads as ringed bark even at low poly)
        rings = 1.0 + 0.08 * (0.55 + 0.45 * math.sin(t * math.pi * 20)) ** 2
        # Soft crownshaft swell — keep gentle so bent trunks don't notch
        boot = 1.0
        if t > 0.88:
            boot = 1.0 + 0.22 * ((t - 0.88) / 0.12) ** 1.1
        return taper * flare * rings * boot

    flare = 1.0 + 0.95 * max(0.0, 1.0 - t / 0.18) ** 2
    belly = 1.0 + 0.06 * math.sin(math.pi * t)
    return (r_base * (1.0 - t) + r_top * t) * flare * belly


def _project_cylinder_uv(obj: bpy.types.Object, u_tile: float = 2.0, v_tile: float = 4.0) -> None:
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    zs = [v.co.z for v in me.vertices]
    z0, z1 = min(zs), max(zs)
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            ang = math.atan2(co.y, co.x)
            u = (ang + math.pi) / (2 * math.pi) * u_tile
            v = (co.z - z0) / max(z1 - z0, 1e-6) * v_tile
            uv[li].uv = (u, v)


def _trunk_centerline(cfg: dict, rings: int) -> list[tuple[Vector, Vector]]:
    """Sample (position, tangent) along the trunk path.

    `lean_deg` is total tip lean from vertical (0 = upright). Values in
    the 45–90° range produce a beach palm that hangs over.
    """
    h = cfg["trunk_h"]
    lean_deg = float(cfg.get("lean_deg", 0.0))
    lean_yaw = math.radians(float(cfg.get("lean_yaw", 0.0)))
    power = float(cfg.get("lean_power", 1.6))

    if lean_deg < 1.0:
        # Mild organic offset (legacy upright trees)
        sway = 0.18 if cfg["id"] == "lumenbark" else 0.10
        samples: list[tuple[Vector, Vector]] = []
        for ri in range(rings + 1):
            t = ri / rings
            pos = Vector((
                sway * t + 0.02 * math.sin(t * 7),
                0.015 * math.sin(t * 5),
                t * h,
            ))
            samples.append((pos, Vector((0, 0, 1))))
        # Fix tangents from finite differences
        for i in range(rings + 1):
            if i == 0:
                tan = (samples[1][0] - samples[0][0]).normalized()
            elif i == rings:
                tan = (samples[i][0] - samples[i - 1][0]).normalized()
            else:
                tan = (samples[i + 1][0] - samples[i - 1][0]).normalized()
            samples[i] = (samples[i][0], tan)
        return samples

    # Integrate a bent centerline. Ease keeps the base upright then
    # smoothly hangs the crown over (no sharp kink at mid-trunk).
    sub = max(rings * 12, 96)
    pos = Vector((0.0, 0.0, 0.0))
    dense: list[tuple[float, Vector, Vector]] = []
    for i in range(sub + 1):
        t = i / sub
        # Smoothstep-ish: t^power blended with a softer mid curve
        ease = t ** power
        ease = ease * ease * (3.0 - 2.0 * ease)  # smoothstep on the eased t
        # Re-apply a touch of power so lower trunk stays more vertical
        ease = ease ** 0.85
        theta = math.radians(lean_deg * ease)
        tan = Vector((
            math.sin(theta) * math.cos(lean_yaw),
            math.sin(theta) * math.sin(lean_yaw),
            math.cos(theta),
        )).normalized()
        dense.append((t, pos.copy(), tan))
        if i < sub:
            pos = pos + tan * (h / sub)

    samples = []
    for ri in range(rings + 1):
        t = ri / rings
        f = t * sub
        i0 = min(int(math.floor(f)), sub - 1)
        i1 = i0 + 1
        a = f - i0
        _, p0, tan0 = dense[i0]
        _, p1, tan1 = dense[i1]
        p = p0.lerp(p1, a)
        tan = (tan0.lerp(tan1, a)).normalized()
        samples.append((p, tan))
    return samples


def _parallel_frames(centerline: list[tuple[Vector, Vector]]):
    """Smooth (x, y) axes along a curve — avoids ring kinks on bends."""
    frames: list[tuple[Vector, Vector]] = []
    t0 = centerline[0][1]
    arb = Vector((0, 0, 1)) if abs(t0.z) < 0.92 else Vector((1, 0, 0))
    x = t0.cross(arb).normalized()
    y = t0.cross(x).normalized()
    frames.append((x, y))
    for i in range(1, len(centerline)):
        t_curr = centerline[i][1]
        x_new = x - t_curr * x.dot(t_curr)
        if x_new.length < 1e-4:
            x_new = y - t_curr * y.dot(t_curr)
        x_new.normalize()
        y_new = t_curr.cross(x_new).normalized()
        frames.append((x_new, y_new))
        x, y = x_new, y_new
    return frames


def build_trunk(cfg: dict, bark_mat):
    """Build trunk mesh. Returns (obj, centerline samples)."""
    sides, rings = cfg["sides"], cfg["rings"]
    r_base, r_top = cfg["r_base"], cfg["r_top"]
    style = cfg.get("style", "round")
    centerline = _trunk_centerline(cfg, rings)
    frames = _parallel_frames(centerline)
    bm = bmesh.new()
    rings_v = []
    ring_uv_v: list[float] = []

    for ri, ((center, tangent), (x_axis, y_axis)) in enumerate(zip(centerline, frames)):
        t = ri / rings
        r = _trunk_radius_at(t, r_base, r_top, style=style if style == "palm" else "round")
        ring = []
        for si in range(sides):
            ang = (2 * math.pi * si) / sides
            wobble = 1.0 + (0.035 if style == "palm" else 0.06) * math.sin(si * 2.4 + t * 4)
            rr = r * wobble
            offset = (x_axis * math.cos(ang) + y_axis * math.sin(ang)) * rr
            ring.append(bm.verts.new(center + offset))
        rings_v.append(ring)
        ring_uv_v.append(t)

    for ri in range(rings):
        for si in range(sides):
            sj = (si + 1) % sides
            bm.faces.new([rings_v[ri][si], rings_v[ri][sj], rings_v[ri + 1][sj], rings_v[ri + 1][si]])

    tip_tan = centerline[-1][1]
    if style == "palm":
        # Blunt crownshaft — short tapered stub, not a needle point
        mid = centerline[-1][0] + tip_tan * (cfg["tip_extra"] * 0.45)
        tip_pos = centerline[-1][0] + tip_tan * cfg["tip_extra"]
        arb = Vector((0, 0, 1)) if abs(tip_tan.z) < 0.9 else Vector((1, 0, 0))
        x_axis = tip_tan.cross(arb).normalized()
        y_axis = tip_tan.cross(x_axis).normalized()
        mid_r = r_top * 0.72
        mid_ring = []
        for si in range(sides):
            ang = (2 * math.pi * si) / sides
            mid_ring.append(bm.verts.new(
                mid + (x_axis * math.cos(ang) + y_axis * math.sin(ang)) * mid_r
            ))
        for si in range(sides):
            sj = (si + 1) % sides
            bm.faces.new([rings_v[-1][si], rings_v[-1][sj], mid_ring[sj], mid_ring[si]])
        tip = bm.verts.new(tip_pos)
        for si in range(sides):
            bm.faces.new([mid_ring[si], mid_ring[(si + 1) % sides], tip])
        ring_uv_v.append(ring_uv_v[-1] + 0.04)
    else:
        # Pointed tip along final tangent
        tip_pos = centerline[-1][0] + tip_tan * cfg["tip_extra"]
        tip = bm.verts.new(tip_pos)
        for si in range(sides):
            bm.faces.new([rings_v[-1][si], rings_v[-1][(si + 1) % sides], tip])

    mesh = bpy.data.meshes.new(f"{cfg['id']}_trunk_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"{cfg['id']}_trunk", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(bark_mat)

    # UVs from construction topology (works for bent trunks)
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    u_tile = 2.0
    v_tile = 6.0 if style == "palm" else 5.0
    face_i = 0
    for ri in range(rings):
        for si in range(sides):
            poly = me.polygons[face_i]
            face_i += 1
            u0 = si / sides * u_tile
            u1 = (si + 1) / sides * u_tile
            v0 = ring_uv_v[ri] * v_tile
            v1 = ring_uv_v[ri + 1] * v_tile
            coords = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
            for i, li in enumerate(poly.loop_indices):
                uv[li].uv = coords[i % 4]
    # Cap / tip faces — simple continuation UVs
    while face_i < len(me.polygons):
        poly = me.polygons[face_i]
        face_i += 1
        si = (face_i - rings * sides - 1) % sides
        u0 = si / sides * u_tile
        u1 = (si + 1) / sides * u_tile
        v0 = ring_uv_v[-1] * v_tile
        v1 = (ring_uv_v[-1] + 0.08) * v_tile
        if len(poly.loop_indices) == 4:
            coords = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        else:
            coords = [(u0, v0), (u1, v0), ((u0 + u1) * 0.5, v1)]
        for i, li in enumerate(poly.loop_indices):
            uv[li].uv = coords[i % len(coords)]

    # Extend centerline with tip for branch/frond anchoring
    centerline = list(centerline) + [(tip_pos, tip_tan)]
    return obj, centerline


def _branch_centerline(start: Vector, direction: Vector, length: float, segs: int):
    direction = direction.normalized()
    up = Vector((0, 0, 1))
    samples = []
    for i in range(segs + 1):
        t = i / segs
        pos = start + direction * (length * t) + up * (0.18 * length * t * t)
        tangent = (direction * length + up * (0.36 * length * t)).normalized()
        samples.append((pos, tangent))
    return samples


def build_branch(
    start: Vector, direction: Vector, length: float,
    r_base: float, r_tip: float, bark_mat, name: str,
    sides: int = 6, segs: int = 4,
):
    bm = bmesh.new()
    samples = _branch_centerline(start, direction, length, segs)
    rings = []
    for i, (pos, tangent) in enumerate(samples):
        t = i / segs
        flare = 1.0 + 0.50 * max(0.0, 1.0 - t / 0.22) ** 2
        r = (r_base * (1 - t) + r_tip * t) * flare
        arb = Vector((1, 0, 0)) if abs(tangent.x) < 0.9 else Vector((0, 1, 0))
        x_axis = tangent.cross(arb).normalized()
        y_axis = tangent.cross(x_axis).normalized()
        ring = [
            bm.verts.new(pos + (x_axis * math.cos(a) + y_axis * math.sin(a)) * r)
            for a in ((2 * math.pi * s) / sides for s in range(sides))
        ]
        rings.append(ring)
    for i in range(segs):
        for s in range(sides):
            sj = (s + 1) % sides
            bm.faces.new([rings[i][s], rings[i][sj], rings[i + 1][sj], rings[i + 1][s]])

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(bark_mat)
    _project_cylinder_uv(obj, u_tile=1.5, v_tile=2.5)
    return obj, samples


def build_branches(cfg: dict, bark_mat, rng: random.Random, centerline=None):
    objs, tips = [], []
    h = cfg["trunk_h"]
    style = cfg.get("style", "round")
    tip_pos = centerline[-1][0] if centerline else Vector((0, 0, h))
    tip_tan = centerline[-1][1] if centerline else Vector((0, 0, 1))

    for i, (yaw_d, pitch_d, length, rb, rt, z_frac) in enumerate(cfg["branches"]):
        yaw, pitch = math.radians(yaw_d), math.radians(pitch_d)
        r_at = _trunk_radius_at(
            z_frac, cfg["r_base"], cfg["r_top"],
            style=style if style == "palm" else "round",
        )

        if style == "palm" and centerline:
            # Crown stubs radiate from tip, relative to tip tangent frame
            arb = Vector((0, 0, 1)) if abs(tip_tan.z) < 0.92 else Vector((1, 0, 0))
            x_axis = tip_tan.cross(arb).normalized()
            y_axis = tip_tan.cross(x_axis).normalized()
            # pitch_d here = angle from tip tangent toward outward
            out = (x_axis * math.cos(yaw) + y_axis * math.sin(yaw)).normalized()
            direction = (
                tip_tan * math.sin(pitch) + out * math.cos(pitch)
            ).normalized()
            start = tip_pos - tip_tan * (length * 0.15) + out * (r_at * 0.25)
            buried = r_at * 0.55
        else:
            direction = Vector((
                math.cos(yaw) * math.cos(pitch),
                math.sin(yaw) * math.cos(pitch),
                math.sin(pitch),
            ))
            start = Vector((
                math.cos(yaw) * r_at * 0.15,
                math.sin(yaw) * r_at * 0.15,
                h * z_frac,
            ))
            buried = r_at * 0.85

        obj, samples = build_branch(
            start, direction, length + buried, rb, rt, bark_mat,
            f"{cfg['id']}_branch_{i}",
        )
        objs.append(obj)
        tips.append(samples[-1][0])

        # One secondary per primary (willow gets drooping secondaries).
        # Palms skip secondaries — crown is all fronds.
        if style == "palm":
            continue
        if i < len(cfg["branches"]):
            fork_idx = max(1, int(round((len(samples) - 1) * 0.50)))
            fork_pos, fork_tan = samples[fork_idx]
            syaw = yaw + math.radians(rng.choice([-36, -26, 26, 36]))
            if style == "weep":
                # Rise then gently droop — scaffold for hanging curtains
                spitch = math.radians(rng.uniform(-18, 12))
            else:
                spitch = min(pitch + math.radians(rng.uniform(6, 14)), math.radians(48))
            sdir = Vector((
                math.cos(syaw) * math.cos(spitch),
                math.sin(syaw) * math.cos(spitch),
                math.sin(spitch),
            )).normalized()
            sec_rb = rb * 0.55
            sstart = fork_pos - sdir * (sec_rb * 1.8) - fork_tan * (rb * 0.35)
            sec_len = length * (0.72 if style == "weep" else 0.55)
            sobj, ssamples = build_branch(
                sstart, sdir, sec_len + sec_rb * 1.8, sec_rb, rt * 0.7,
                bark_mat, f"{cfg['id']}_branch_{i}_sec", sides=5, segs=3,
            )
            objs.append(sobj)
            tips.append(ssamples[-1][0])
    return objs, tips


def _sample_canopy(cfg: dict, rng: random.Random) -> Vector:
    style = cfg["style"]
    cx, cy, cz = cfg["canopy_c"]
    rx, ry, rz = cfg["canopy_r"]

    if style == "cone":
        # Conical shell: radius shrinks with height
        t = rng.uniform(0.05, 0.98)  # 0 at bottom of cone, 1 at tip
        z = cz - rz + 2 * rz * t
        rad_scale = 1.0 - t * 0.92
        ang = rng.uniform(0, 2 * math.pi)
        r = rad_scale * rx * rng.uniform(0.35, 1.0)
        return Vector((cx + r * math.cos(ang), cy + r * math.sin(ang), z))

    if style == "orbs":
        # Spiral of 4 orb centres up the crown
        orb_i = rng.randint(0, 3)
        ang0 = orb_i * (math.pi / 2) + 0.4
        orb_c = Vector((
            cx + math.cos(ang0) * rx * 0.45,
            cy + math.sin(ang0) * ry * 0.45,
            cz - rz * 0.6 + orb_i * (rz * 0.45),
        ))
        # Point inside small sphere around orb
        while True:
            x, y, z = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)
            if x * x + y * y + z * z <= 1.0:
                break
        return orb_c + Vector((x * 0.85, y * 0.85, z * 0.70))

    # round / column / weep — ellipsoid
    while True:
        x, y, z = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)
        if x * x + y * y + z * z <= 1.0:
            break
    if style == "column":
        z = abs(z)  # fill upward
    else:
        z = abs(z) * 0.5 + z * 0.5
    return Vector((cx + x * rx, cy + y * ry, cz + z * rz))


def _card_axes(rng: random.Random, droop: float = 0.0):
    yaw = rng.uniform(0, 2 * math.pi)
    if droop > 0.5:
        # Prefer hanging / vertical cards for willow
        tilt = rng.uniform(0.9, 1.35)  # near vertical
    else:
        tilt = rng.uniform(-0.55, 0.55)
    right = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    up = Vector((
        math.sin(tilt) * -math.sin(yaw),
        math.sin(tilt) * math.cos(yaw),
        math.cos(tilt),
    )).normalized()
    return right, up


def _finish_card_mesh(
    bm: bmesh.types.BMesh,
    face_uv_rot: list[int],
    material,
    name: str,
    rng: random.Random,
    lock_uv_upright: bool = False,
    uv_rects: list[tuple[float, float, float, float]] | None = None,
):
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)

    me = obj.data
    me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    for pi, poly in enumerate(me.polygons):
        if uv_rects and pi < len(uv_rects):
            u0, v0, u1, v1 = uv_rects[pi]
            base = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        else:
            base = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        rot = 0 if lock_uv_upright else (face_uv_rot[pi] if pi < len(face_uv_rot) else 0)
        uvs = base[rot:] + base[:rot]
        if (not lock_uv_upright) and rng.random() < 0.5:
            uvs = [(u0 + u1 - u, v) for u, v in uvs] if uv_rects and pi < len(uv_rects) else [
                (1.0 - u, v) for u, v in uvs
            ]
        for i, li in enumerate(poly.loop_indices):
            uv[li].uv = uvs[i % 4]
    return obj


def _add_quad(bm, face_uv_rot, center, right, up, hw, hh, uv_rot: int = 0):
    r, u = right.normalized() * hw, up.normalized() * hh
    v0 = bm.verts.new(center - r - u)
    v1 = bm.verts.new(center + r - u)
    v2 = bm.verts.new(center + r + u)
    v3 = bm.verts.new(center - r + u)
    bm.faces.new([v0, v1, v2, v3])
    face_uv_rot.append(uv_rot)


def _strand_uv_rect(
    rng: random.Random,
    n_cols: int = 11,
    *,
    prefer_thin: bool = False,
) -> tuple[float, float, float, float]:
    """UV one vertical strand column from a foliage/lichen atlas."""
    # Prefer thinner right-side columns for cascade cards when available
    if prefer_thin:
        col = rng.randint(max(0, n_cols // 3), n_cols - 1)
    else:
        col = rng.randint(0, n_cols - 1)
    pad_u = 0.01
    u0 = col / n_cols + pad_u
    u1 = (col + 1) / n_cols - pad_u
    v0 = rng.uniform(0.00, 0.06)
    v1 = rng.uniform(0.92, 1.00)
    if rng.random() < 0.5:
        u0, u1 = u1, u0
    return (u0, v0, u1, v1)


def build_foliage(cfg: dict, tips: list[Vector], leaf_mat, rng: random.Random):
    bm = bmesh.new()
    face_uv_rot: list[int] = []
    hw_lo, hw_hi = cfg["leaf_hw"]
    hh_lo, hh_hi = cfg["leaf_hh"]
    droop = cfg["droop"]
    count = cfg["leaf_cards"]

    placements: list[Vector] = []
    for tip in tips:
        p = tip + Vector((
            rng.uniform(-0.25, 0.25),
            rng.uniform(-0.25, 0.25),
            rng.uniform(0.05, 0.40),
        ))
        if droop > 0:
            p = p + Vector((0, 0, -rng.uniform(0.2, droop)))
        placements.append(p)
    while len(placements) < count:
        p = _sample_canopy(cfg, rng)
        if droop > 0 and rng.random() < 0.65:
            p = p + Vector((0, 0, -rng.uniform(0.3, droop)))
        if p.z < cfg["trunk_h"] * 0.45:
            continue
        placements.append(p)

    cross_rate = cfg.get("leaf_cross", 0.40)
    for center in placements:
        hw = rng.uniform(hw_lo, hw_hi)
        hh = rng.uniform(hh_lo, hh_hi)
        right, up = _card_axes(rng, droop)
        _add_quad(bm, face_uv_rot, center, right, up, hw, hh, rng.randint(0, 3))
        if rng.random() < cross_rate:
            cross = up.cross(right)
            if cross.length > 0.1:
                right2 = cross.normalized()
                up2 = right.cross(right2).normalized()
                _add_quad(bm, face_uv_rot, center, right2, up2, hw * 0.9, hh * 0.9, rng.randint(0, 3))

    return _finish_card_mesh(
        bm, face_uv_rot, leaf_mat, f"{cfg['id']}_leaves", rng, lock_uv_upright=False,
    )


def _frond_uv_rect(col: int, n_cols: int, v0: float, v1: float, flip: bool):
    pad = 0.01
    u0 = col / n_cols + pad
    u1 = (col + 1) / n_cols - pad
    if flip:
        u0, u1 = u1, u0
    return (u0, v0, u1, v1)


def _add_arched_frond(
    bm,
    face_uv_rot: list[int],
    uv_rects: list[tuple[float, float, float, float]],
    origin: Vector,
    azimuth: float,
    elev_start: float,
    elev_end: float,
    length: float,
    hw: float,
    n_segs: int,
    n_cols: int,
    rng: random.Random,
    gravity_bias: float = 0.0,
    cross: bool = False,
):
    """Multi-segment frond card chain along an arching curve."""
    dir_h = Vector((math.cos(azimuth), math.sin(azimuth), 0.0))
    if dir_h.length < 1e-6:
        dir_h = Vector((1, 0, 0))
    dir_h.normalize()

    positions = [origin.copy()]
    tangents: list[Vector] = []
    pos = origin.copy()
    for i in range(n_segs):
        t = (i + 0.5) / n_segs
        elev = elev_start * (1.0 - t) + elev_end * t
        tan = (dir_h * math.cos(elev) + Vector((0, 0, 1)) * math.sin(elev))
        if gravity_bias > 0:
            tan = (tan + Vector((0, 0, -gravity_bias * t))).normalized()
        else:
            tan = tan.normalized()
        tangents.append(tan)
        pos = pos + tan * (length / n_segs)
        positions.append(pos.copy())

    col = rng.randint(0, n_cols - 1)
    flip = rng.random() < 0.5
    twist0 = rng.uniform(-0.40, 0.40)

    for i in range(n_segs):
        p0, p1 = positions[i], positions[i + 1]
        center = (p0 + p1) * 0.5
        up_axis = tangents[i]
        right = up_axis.cross(Vector((0, 0, 1)))
        if right.length < 0.12:
            right = up_axis.cross(Vector((1, 0, 0)))
        right.normalize()
        twist = twist0 + rng.uniform(-0.08, 0.08)
        right = (
            right * math.cos(twist) + up_axis.cross(right) * math.sin(twist)
        ).normalized()

        # Width & UV taper toward tip; slight segment overlap hides seams
        wt = 1.0 - 0.42 * ((i + 0.5) / n_segs)
        seg_hh = (p1 - p0).length * 0.58
        _add_quad(bm, face_uv_rot, center, right, up_axis, hw * wt, seg_hh, 0)
        v0 = i / n_segs
        v1 = (i + 1) / n_segs
        # Texture stem is at top of atlas → map frond base→tip as v=1→0
        uv_rects.append(_frond_uv_rect(col, n_cols, 1.0 - v1, 1.0 - v0, flip))

        if cross and i < n_segs - 1 and rng.random() < 0.55:
            right2 = up_axis.cross(right).normalized()
            _add_quad(
                bm, face_uv_rot,
                center + right2 * rng.uniform(-0.06, 0.06),
                right2, up_axis,
                hw * wt * 0.72, seg_hh * 0.90, 0,
            )
            uv_rects.append(_frond_uv_rect(
                rng.randint(0, n_cols - 1), n_cols, 1.0 - v1, 1.0 - v0, flip,
            ))


def build_palm_coconuts(
    cfg: dict,
    origin: Vector,
    tip_tan: Vector,
    bark_mat,
    rng: random.Random,
):
    """Small fruit cluster hanging under the crown (bark-colored)."""
    count = int(cfg.get("coconut_count", 0))
    if count <= 0:
        return []
    objs = []
    # Hang slightly below / behind the crown tip
    base = origin - tip_tan * 0.35 + Vector((0, 0, -0.15))
    for i in range(count):
        ang = (2 * math.pi * i) / count + rng.uniform(-0.2, 0.2)
        radial = Vector((math.cos(ang), math.sin(ang), 0.0)) * rng.uniform(0.12, 0.28)
        loc = base + radial + Vector((0, 0, rng.uniform(-0.22, 0.05)))
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=1, radius=rng.uniform(0.10, 0.15), location=loc,
        )
        obj = bpy.context.active_object
        obj.name = f"{cfg['id']}_coconut_{i}"
        # Slight squash
        obj.scale = (1.0, 1.0, rng.uniform(0.85, 0.95))
        bpy.ops.object.transform_apply(scale=True)
        obj.data.materials.append(bark_mat)
        objs.append(obj)
    return objs


def build_palm_foliage(
    cfg: dict,
    tips: list[Vector],
    leaf_mat,
    rng: random.Random,
    crown_origin: Vector | None = None,
    tip_tan: Vector | None = None,
):
    """Radiating multi-segment palm fronds that arch out and droop."""
    bm = bmesh.new()
    face_uv_rot: list[int] = []
    uv_rects: list[tuple[float, float, float, float]] = []
    hw_lo, hw_hi = cfg["leaf_hw"]
    hh_lo, hh_hi = cfg["leaf_hh"]
    n_fronds = cfg["leaf_cards"]
    n_cols = cfg.get("frond_cols", 6)
    n_segs = int(cfg.get("frond_segs", 4))
    gravity_bias = float(cfg.get("gravity_bias", 0.25))
    cx, cy, cz = cfg["canopy_c"]

    if crown_origin is not None:
        origin = crown_origin.copy()
    elif tips:
        avg = sum(tips, Vector((0, 0, 0))) / len(tips)
        origin = Vector((avg.x * 0.45, avg.y * 0.45, max(t.z for t in tips) + 0.12))
    else:
        origin = Vector((cx, cy, cz))

    # Lean-aware: bias more fronds toward the hang-over side
    lean_yaw = math.radians(float(cfg.get("lean_yaw", 0.0)))
    lean_deg = float(cfg.get("lean_deg", 0.0))

    for i in range(n_fronds):
        # Layered whorls: outer droopers + mid + a few high ones
        layer = i / max(n_fronds - 1, 1)
        ang = (2 * math.pi * i) / n_fronds + rng.uniform(-0.10, 0.10)
        if lean_deg > 40:
            # Prefer fronds spilling over the lean direction
            ang = ang * 0.55 + lean_yaw + rng.uniform(-0.55, 0.55)

        if layer < 0.55:
            # Outer skirt — start near horizontal, droop hard
            elev0 = rng.uniform(-0.15, 0.35)
            elev1 = elev0 - rng.uniform(0.85, 1.35)
            length = rng.uniform(hh_lo * 1.05, hh_hi)
            hw = rng.uniform(hw_lo * 1.05, hw_hi)
        elif layer < 0.82:
            elev0 = rng.uniform(0.15, 0.55)
            elev1 = elev0 - rng.uniform(0.55, 0.95)
            length = rng.uniform(hh_lo, hh_hi * 0.92)
            hw = rng.uniform(hw_lo, hw_hi * 0.95)
        else:
            elev0 = rng.uniform(0.45, 0.95)
            elev1 = elev0 - rng.uniform(0.25, 0.55)
            length = rng.uniform(hh_lo * 0.75, hh_lo * 1.05)
            hw = rng.uniform(hw_lo * 0.75, hw_hi * 0.85)

        _add_arched_frond(
            bm, face_uv_rot, uv_rects,
            origin, ang, elev0, elev1, length, hw, n_segs, n_cols, rng,
            gravity_bias=gravity_bias,
            cross=True,
        )

    # Crown heart — short upright / tip-aligned fronds
    heart_n = 8
    for j in range(heart_n):
        ang = (2 * math.pi * j) / heart_n + rng.uniform(-0.15, 0.15)
        elev0 = rng.uniform(0.70, 1.25)
        elev1 = elev0 - rng.uniform(0.15, 0.40)
        length = rng.uniform(hh_lo * 0.40, hh_lo * 0.70)
        hw = rng.uniform(hw_lo * 0.65, hw_hi * 0.80)
        # Offset heart slightly along tip tangent so it reads as a tuft
        heart_origin = origin + (tip_tan * 0.18 if tip_tan else Vector((0, 0, 0.18)))
        _add_arched_frond(
            bm, face_uv_rot, uv_rects,
            heart_origin, ang, elev0, elev1, length, hw,
            max(2, n_segs - 1), n_cols, rng,
            gravity_bias=gravity_bias * 0.4,
            cross=False,
        )

    return _finish_card_mesh(
        bm, face_uv_rot, leaf_mat, f"{cfg['id']}_fronds", rng,
        lock_uv_upright=True,
        uv_rects=uv_rects,
    )


def build_willow_foliage(
    cfg: dict,
    tips: list[Vector],
    leaf_mat,
    lichen_mat,
    rng: random.Random,
) -> list:
    """Reference weeping willow silhouette:

      Sturdy upward branch scaffold + dense rounded volume of bright
      hanging willow-leaf curtains (layered vertical cards).  No lichen.
    """
    parts: list = []

    # Sparse top clumps so the dome reads solid from above
    parts.append(build_foliage(cfg, tips, leaf_mat, rng))

    min_z = cfg.get("strand_min_anchor_z", cfg["trunk_h"] * 0.75)
    cx, cy, cz = cfg["canopy_c"]
    rx, ry, rz = cfg["canopy_r"]
    floor_z = cfg["trunk_h"] * cfg.get("strand_floor_frac", 0.38)

    def _volume_anchors(n: int) -> list[Vector]:
        """Fill a rounded canopy ellipsoid — not just the outer rim."""
        out: list[Vector] = []
        for tip in tips:
            for _ in range(4):
                out.append(tip + Vector((
                    rng.uniform(-0.55, 0.55),
                    rng.uniform(-0.55, 0.55),
                    rng.uniform(-0.25, 0.55),
                )))
        # Dense sample throughout the canopy volume
        tries = 0
        while len(out) < n * 2 and tries < n * 8:
            tries += 1
            x, y, z = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)
            # Prefer upper hemisphere so hang starts high
            if x * x + y * y + z * z > 1.0:
                continue
            if z < -0.35:
                continue
            p = Vector((cx + x * rx, cy + y * ry, cz + z * rz))
            if p.z < min_z:
                continue
            out.append(p)
        rng.shuffle(out)
        return out

    bm = bmesh.new()
    face_uv_rot: list[int] = []
    uv_rects: list[tuple[float, float, float, float]] = []
    hw_lo, hw_hi = cfg["strand_hw"]
    hh_lo, hh_hi = cfg["strand_hh"]
    hang_lo, hang_hi = cfg["strand_hang"]
    count = cfg["strand_count"]

    placed = 0
    for anchor in _volume_anchors(count):
        if placed >= count:
            break
        # Longer strands toward the outer rim for the rounded skirt
        dist_xy = math.hypot(anchor.x - cx, anchor.y - cy)
        rim = min(1.0, dist_xy / max(rx, 0.01))
        hang = rng.uniform(hang_lo, hang_hi) * (0.75 + 0.45 * rim)
        hh = rng.uniform(hh_lo, hh_hi) * (0.85 + 0.35 * rim)
        hw = rng.uniform(hw_lo, hw_hi)
        # Mix thin strands + thicker clusters (left atlas cols are bushier)
        prefer_thin = rng.random() < 0.55
        if not prefer_thin:
            hw *= rng.uniform(1.15, 1.55)

        top_z = anchor.z - hang * 0.10
        center_z = top_z - hh * 0.5
        bottom = center_z - hh * 0.5
        if bottom < floor_z:
            hh = max(0.9, top_z - floor_z)
            center_z = top_z - hh * 0.5
            if hh < 0.9:
                continue

        center = Vector((
            anchor.x + rng.uniform(-0.12, 0.12),
            anchor.y + rng.uniform(-0.12, 0.12),
            center_z,
        ))
        yaw = rng.uniform(0, 2 * math.pi)
        right = Vector((math.cos(yaw), math.sin(yaw), 0.0))
        # Nearly vertical hang — slight outward flare like reference curtains
        flare = rng.uniform(0.02, 0.14)
        out_dir = Vector((anchor.x - cx, anchor.y - cy, 0.0))
        if out_dir.length > 0.05:
            out_dir.normalize()
        else:
            out_dir = Vector((math.cos(yaw), math.sin(yaw), 0.0))
        up_axis = (Vector((0, 0, -1)) + out_dir * flare).normalized()
        _add_quad(bm, face_uv_rot, center, right, up_axis, hw, hh, 0)
        uv_rects.append(_strand_uv_rect(rng, 11, prefer_thin=prefer_thin))

        # Cross card for volume — higher rate so curtains read dense
        if rng.random() < 0.48:
            right2 = Vector((-right.y, right.x, 0.0))
            _add_quad(
                bm, face_uv_rot,
                center + right2 * rng.uniform(-0.05, 0.05),
                right2, up_axis,
                hw * rng.uniform(0.70, 0.92),
                hh * rng.uniform(0.80, 0.98),
                0,
            )
            uv_rects.append(_strand_uv_rect(rng, 11, prefer_thin=prefer_thin))
        placed += 1

    if face_uv_rot:
        parts.append(_finish_card_mesh(
            bm, face_uv_rot, leaf_mat, f"{cfg['id']}_cascade", rng,
            lock_uv_upright=True,
            uv_rects=uv_rects,
        ))
    else:
        bm.free()

    return parts


# ── Export helpers ────────────────────────────────────────────────────────

def join_group(objects: list, name: str):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    return obj


def normalize_transform(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")


def export_glb(obj, out_path: str):
    normalize_transform(obj)
    for mat in obj.data.materials:
        if mat and ("leaf" in mat.name or "lichen" in mat.name):
            mat.use_backface_culling = False
            mat.blend_method = "CLIP"
            # Keep lichen fringe soft; leaves stay a bit crisper
            mat.alpha_threshold = 0.06 if "lichen" in mat.name else 0.15
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
    )


def report(obj, label: str):
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    mats = [m.name if m else "?" for m in obj.data.materials]
    xs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    print(f"  [{label}] verts={len(obj.data.vertices)} tris={tris} mats={mats}")
    print(
        f"  [{label}] bounds Z[{min(v.z for v in xs):+.2f}, {max(v.z for v in xs):+.2f}]  "
        f"footprint≈{max(abs(v.x) for v in xs) + max(abs(v.y) for v in xs):.1f}m"
    )
    return tris


def build_one(cfg: dict) -> int:
    clear_scene()
    rng = random.Random(cfg["seed"])
    print(f"\n=== {cfg['display']} ({cfg['id']}) ===")
    print(f"  Fortnite silhouette: trunk {cfg['trunk_h']:.1f}m, canopy style={cfg['style']}")

    bark_img = load_image(cfg["bark"])
    leaf_img = load_image(cfg["leaves"])
    bark_mat = make_bark_material(f"tree_bark_{cfg['id']}", bark_img)
    leaf_mat = make_leaf_material(f"tree_leaves_{cfg['id']}", leaf_img)
    # Export-facing names (shared logical slots)
    bark_mat.name = "tree_bark"
    leaf_mat.name = "tree_leaves"

    trunk, centerline = build_trunk(cfg, bark_mat)
    parts = [trunk]
    branches, tips = build_branches(cfg, bark_mat, rng, centerline=centerline)
    parts.extend(branches)

    if cfg["style"] == "weep":
        lichen_mat = None
        if cfg.get("lichen") and cfg.get("lichen_count", 0) > 0:
            lichen_img = load_image(cfg["lichen"])
            lichen_mat = make_leaf_material(
                f"tree_lichen_{cfg['id']}", lichen_img, alpha_threshold=0.06,
            )
            lichen_mat.name = "tree_lichen"
        parts.extend(build_willow_foliage(cfg, tips, leaf_mat, lichen_mat, rng))
        floor = cfg["trunk_h"] * cfg.get("strand_floor_frac", 0.38)
        print(
            f"  willow (ref): {cfg['leaf_cards']} crown clumps + "
            f"{cfg['strand_count']} hanging curtains, floor≥{floor:.1f}m"
        )
    elif cfg["style"] == "palm":
        tip_pos, tip_tan = centerline[-1]
        # Crown sits just past the trunk tip along the lean
        crown = tip_pos + tip_tan * 0.08
        parts.append(build_palm_foliage(
            cfg, tips, leaf_mat, rng,
            crown_origin=crown, tip_tan=tip_tan,
        ))
        parts.extend(build_palm_coconuts(cfg, crown, tip_tan, bark_mat, rng))
        lean = float(cfg.get("lean_deg", 0.0))
        print(
            f"  palm: {cfg['leaf_cards']} arched fronds + crown heart"
            + (f", lean={lean:.0f}°" if lean else "")
        )
    else:
        parts.append(build_foliage(cfg, tips, leaf_mat, rng))

    tree = join_group(parts, f"tree_{cfg['id']}")
    tris = report(tree, cfg["id"])

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, cfg["out_name"])
        export_glb(tree, path)
        print(f"  -> {path} ({os.path.getsize(path)/1024:.1f} KB)")
    return tris


def main():
    import sys
    only = {a.lower() for a in sys.argv[1:] if not a.startswith("-")}
    defs = [c for c in TREE_DEFS if (not only) or c["id"] in only or c["display"].lower().replace(" ", "") in only]
    if only and not defs:
        print(f"No matching trees for {only}. Known ids: {[c['id'] for c in TREE_DEFS]}")
        return

    print(f"Source: {SOURCE_DIR}")
    print(f"Viewer: {VIEWER_DIR}")
    print(f"Textures: {TEX_DIR}")
    print(f"Building {len(defs)} Fortnite-style trees…")
    results = []
    for cfg in defs:
        tris = build_one(cfg)
        results.append((cfg["out_name"], cfg["display"], tris))
    print("\nDONE — tree set exported:")
    for name, disp, tris in results:
        print(f"  {disp:18s}  {name:28s}  {tris} tris")


if __name__ == "__main__":
    main()
