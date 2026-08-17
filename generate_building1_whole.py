"""
generate_building1_whole.py
===========================
Medieval shop/cottage inspired by Building1Whole reference layout:

  Modular pieces (kept as separate objects in one GLB):
    Building1_Walls  — plaster shell, rock base, timber, windows, floor
    Building1_Door   — hinged wood door (origin on hinge; rotate local +Z)
    Building1_Roof   — removable round-tile roof + wood fascia

  Footprint ≈ reference: 12.4 m (X) × 6.4 m (Y) × ~7.5 m (Z-up).

  Custom textures in building1_textures/ (not the reference atlases).

Outputs (Desktop + viewer):
  Building1Whole.glb
  Building1Whole_NoRoof.glb
  Building1Whole_DoorOpen.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_building1_whole.py
"""

from __future__ import annotations

import math
import os
import sys

import bpy


# ── Paths ─────────────────────────────────────────────────────────────────

ROOT = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(ROOT, "building1_textures")
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath(os.path.join(ROOT, "viewer/public/buildings"))

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)


# ── Dimensions (metres, Z-up) ─────────────────────────────────────────────

BUILD_W = 12.40          # full width along X
BUILD_D = 6.40           # full depth along Y
HALF_W = BUILD_W * 0.5
HALF_D = BUILD_D * 0.5

WALL_T = 0.28            # wall thickness
FLOOR_Z = 0.08
ROCK_H = 0.55            # stone base height
EAVE_Z = 3.20            # top of plaster walls / plate
RIDGE_Z = 7.40           # roof ridge height
OVERHANG = 0.45

# Front door (+Y face)
DOOR_W = 1.20
DOOR_H = 2.35
DOOR_T = 0.08
DOOR_CX = -0.35          # slight offset like reference
DOOR_ARCH_R = 0.55       # rounded top radius
DOOR_GAP = 0.02

# Front windows
WIN_H = 1.35
WIN_Z0 = 1.15
WIN_DEPTH = 0.08


# ── Scene helpers ─────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def join_group(objects: list, name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        if o is not None:
            o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    return obj


def apply_trs(obj: bpy.types.Object):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def set_origin_to_point(obj: bpy.types.Object, world_point: tuple[float, float, float]):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.scene.cursor.location = world_point
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")


def box(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    mat: bpy.types.Material,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (size[0], size[1], size[2])
    apply_trs(obj)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj


def report(obj: bpy.types.Object, label: str):
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    mats = [m.name if m else "?" for m in obj.data.materials]
    xs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    print(
        f"  [{label}] verts={len(obj.data.vertices)} tris={tris} mats={mats}"
    )
    print(
        f"  [{label}] X[{min(v.x for v in xs):+.2f},{max(v.x for v in xs):+.2f}] "
        f"Y[{min(v.y for v in xs):+.2f},{max(v.y for v in xs):+.2f}] "
        f"Z[{min(v.z for v in xs):+.2f},{max(v.z for v in xs):+.2f}]"
    )
    return tris


# ── Materials / textures ──────────────────────────────────────────────────

def load_image(filename: str) -> bpy.types.Image:
    path = os.path.join(TEX_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    img = bpy.data.images.load(path, check_existing=True)
    img.pack()
    return img


def make_textured_material(
    name: str,
    img: bpy.types.Image,
    *,
    roughness: float = 0.85,
    metallic: float = 0.0,
    alpha_blend: bool = False,
    alpha_value: float | None = None,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    if alpha_blend:
        mat.blend_method = "BLEND"
        if hasattr(mat, "shadow_method"):
            mat.shadow_method = "NONE"
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    mapping = nt.nodes.new("ShaderNodeMapping")
    texcoord = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha_blend:
        if alpha_value is not None:
            bsdf.inputs["Alpha"].default_value = alpha_value
        elif "Alpha" in tex.outputs:
            nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


def make_materials() -> dict[str, bpy.types.Material]:
    return {
        "building_plaster": make_textured_material(
            "building_plaster", load_image("Plaster_BaseColor.png"), roughness=0.92,
        ),
        "building_wood_trim": make_textured_material(
            "building_wood_trim", load_image("WoodTrim_BaseColor.png"), roughness=0.80,
        ),
        "building_round_tiles": make_textured_material(
            "building_round_tiles", load_image("RoundTiles_BaseColor.png"), roughness=0.78,
        ),
        "building_rock_trim": make_textured_material(
            "building_rock_trim", load_image("RockTrim_BaseColor.png"), roughness=0.90,
        ),
        "building_door_wood": make_textured_material(
            "building_door_wood", load_image("DoorWood_BaseColor.png"), roughness=0.82,
        ),
        "building_metal": make_textured_material(
            "building_metal", load_image("Metal_BaseColor.png"),
            roughness=0.45, metallic=0.75,
        ),
        "building_glass": make_textured_material(
            "building_glass", load_image("Glass_BaseColor.png"),
            roughness=0.08, alpha_blend=True, alpha_value=0.18,
        ),
    }


def ensure_uv(obj: bpy.types.Object, scale: float = 0.35):
    """Smart-project UVs so textures tile on modular parts."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    # Scale UVs
    me = obj.data
    if me.uv_layers:
        uv = me.uv_layers.active.data
        for loop in uv:
            loop.uv *= scale


def assign_mat(obj: bpy.types.Object, mat: bpy.types.Material):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ── Wall shell (with door / window openings) ──────────────────────────────

def build_walls(mats: dict) -> bpy.types.Object:
    """Construct hollow building shell with openings for door + windows."""
    parts: list[bpy.types.Object] = []
    plaster = mats["building_plaster"]
    wood = mats["building_wood_trim"]
    rock = mats["building_rock_trim"]
    glass = mats["building_glass"]

    xin = HALF_W - WALL_T
    yin = HALF_D - WALL_T

    # Floor slab
    floor = box(
        "floor",
        (0, 0, FLOOR_Z * 0.5),
        (BUILD_W - 0.05, BUILD_D - 0.05, FLOOR_Z),
        wood,
    )
    parts.append(floor)

    # Rock base — four sides
    rock_specs = [
        # front (+Y)
        (0, HALF_D - WALL_T * 0.5, ROCK_H * 0.5, BUILD_W, WALL_T, ROCK_H),
        # back (−Y)
        (0, -HALF_D + WALL_T * 0.5, ROCK_H * 0.5, BUILD_W, WALL_T, ROCK_H),
        # left (−X)
        (-HALF_W + WALL_T * 0.5, 0, ROCK_H * 0.5, WALL_T, BUILD_D - 2 * WALL_T, ROCK_H),
        # right (+X)
        (HALF_W - WALL_T * 0.5, 0, ROCK_H * 0.5, WALL_T, BUILD_D - 2 * WALL_T, ROCK_H),
    ]
    for i, (cx, cy, cz, sx, sy, sz) in enumerate(rock_specs):
        parts.append(box(f"rock_{i}", (cx, cy, cz), (sx, sy, sz), rock))

    # Plaster walls above rock, with segmented front for door + windows
    z0 = ROCK_H
    z1 = EAVE_Z
    mid_z = (z0 + z1) * 0.5
    h = z1 - z0

    # Back wall (solid)
    parts.append(box(
        "wall_back",
        (0, -HALF_D + WALL_T * 0.5, mid_z),
        (BUILD_W, WALL_T, h),
        plaster,
    ))
    # Left / right walls (solid)
    parts.append(box(
        "wall_left",
        (-HALF_W + WALL_T * 0.5, 0, mid_z),
        (WALL_T, BUILD_D - 2 * WALL_T, h),
        plaster,
    ))
    parts.append(box(
        "wall_right",
        (HALF_W - WALL_T * 0.5, 0, mid_z),
        (WALL_T, BUILD_D - 2 * WALL_T, h),
        plaster,
    ))

    # Front wall segments around door + two wide windows
    # Layout along X (left → right): wall | winL | wall | door | wall | winR | wall
    win_w = 2.40
    gap = 0.35
    door_left = DOOR_CX - DOOR_W * 0.5
    door_right = DOOR_CX + DOOR_W * 0.5
    win_l_cx = -3.60
    win_r_cx = 3.40
    win_l0, win_l1 = win_l_cx - win_w * 0.5, win_l_cx + win_w * 0.5
    win_r0, win_r1 = win_r_cx - win_w * 0.5, win_r_cx + win_w * 0.5

    # Horizontal bands: below windows, between sill-lintel gaps handled per col
    front_y = HALF_D - WALL_T * 0.5

    def front_panel(name, x0, x1, za, zb):
        if x1 - x0 < 0.05 or zb - za < 0.05:
            return
        cx = (x0 + x1) * 0.5
        cz = (za + zb) * 0.5
        parts.append(box(
            name, (cx, front_y, cz), (x1 - x0, WALL_T, zb - za), plaster,
        ))

    # Full-height end walls on front
    x_edges = [
        (-HALF_W, win_l0),
        (win_l1, door_left),
        (door_right, win_r0),
        (win_r1, HALF_W),
    ]
    for i, (a, b) in enumerate(x_edges):
        front_panel(f"front_full_{i}", a, b, z0, z1)

    # Below / above windows
    for side, a, b in (("L", win_l0, win_l1), ("R", win_r0, win_r1)):
        front_panel(f"front_below_{side}", a, b, z0, WIN_Z0)
        front_panel(f"front_above_{side}", a, b, WIN_Z0 + WIN_H, z1)

    # Door sides already covered; below door (threshold rock already) + arch fill above
    front_panel("front_above_door", door_left, door_right, DOOR_H + 0.02, z1)

    # Timber framing (beams)
    beam_t = 0.14
    # Corner posts
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(box(
                f"post_{sx}_{sy}",
                (sx * (HALF_W - WALL_T * 0.5), sy * (HALF_D - WALL_T * 0.5), (z0 + z1) * 0.5),
                (beam_t, beam_t, h + 0.05),
                wood,
            ))
    # Extra vertical studs on front facade
    for x in (-5.2, -2.0, 1.5, 5.0):
        parts.append(box(
            f"stud_f_{x}",
            (x, HALF_D - WALL_T * 0.5, mid_z),
            (beam_t * 0.85, beam_t * 0.7, h),
            wood,
        ))
    # Diagonal braces on front corners
    for sx, name in ((-1, "brace_L"), (1, "brace_R")):
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        br = bpy.context.active_object
        br.name = name
        br.scale = (0.10, 0.08, 1.55)
        br.location = (sx * 5.5, HALF_D - WALL_T * 0.45, ROCK_H + 1.1)
        br.rotation_euler = (0, 0, sx * math.radians(28))
        apply_trs(br)
        assign_mat(br, wood)
        parts.append(br)
    # Horizontal plate at eave
    parts.append(box(
        "plate_front",
        (0, HALF_D - WALL_T * 0.5, EAVE_Z - 0.07),
        (BUILD_W, beam_t, 0.14),
        wood,
    ))
    parts.append(box(
        "plate_back",
        (0, -HALF_D + WALL_T * 0.5, EAVE_Z - 0.07),
        (BUILD_W, beam_t, 0.14),
        wood,
    ))
    parts.append(box(
        "plate_left",
        (-HALF_W + WALL_T * 0.5, 0, EAVE_Z - 0.07),
        (beam_t, BUILD_D, 0.14),
        wood,
    ))
    parts.append(box(
        "plate_right",
        (HALF_W - WALL_T * 0.5, 0, EAVE_Z - 0.07),
        (beam_t, BUILD_D, 0.14),
        wood,
    ))
    # Mid timber belt
    parts.append(box(
        "belt_front",
        (0, HALF_D - WALL_T * 0.5, ROCK_H + 0.08),
        (BUILD_W, beam_t * 0.9, 0.12),
        wood,
    ))
    parts.append(box(
        "belt_back",
        (0, -HALF_D + WALL_T * 0.5, ROCK_H + 1.55),
        (BUILD_W, beam_t * 0.9, 0.12),
        wood,
    ))
    parts.append(box(
        "belt_left",
        (-HALF_W + WALL_T * 0.5, 0, ROCK_H + 1.55),
        (beam_t * 0.9, BUILD_D - 2 * WALL_T, 0.12),
        wood,
    ))
    parts.append(box(
        "belt_right",
        (HALF_W - WALL_T * 0.5, 0, ROCK_H + 1.55),
        (beam_t * 0.9, BUILD_D - 2 * WALL_T, 0.12),
        wood,
    ))
    # Window sills
    for name, cx, w in (("sillL", win_l_cx, win_w), ("sillR", win_r_cx, win_w)):
        parts.append(box(
            name,
            (cx, front_y + 0.06, WIN_Z0 - 0.06),
            (w + 0.20, 0.16, 0.08),
            wood,
        ))

    # Windows (frames + glass) — front
    for name, cx, w in (("winL", win_l_cx, win_w), ("winR", win_r_cx, win_w)):
        parts.extend(_make_window(name, cx, front_y, w, WIN_H, WIN_Z0, wood, glass))

    # Side windows (one each side)
    for name, sx in (("winSideL", -1), ("winSideR", 1)):
        cy = 0.2
        wx, wy = WALL_T, 1.60
        cx = sx * (HALF_W - WALL_T * 0.5)
        # frame as thin box in wall plane
        parts.extend(_make_side_window(name, cx, cy, sx, wy, WIN_H, WIN_Z0, wood, glass))

    # Interior ceiling joist hint (visible when roof removed)
    for i, x in enumerate((-3.5, -1.2, 1.2, 3.5)):
        parts.append(box(
            f"joist_{i}",
            (x, 0, EAVE_Z - 0.12),
            (0.12, BUILD_D - 0.6, 0.16),
            wood,
        ))

    walls = join_group(parts, "Building1_Walls")
    ensure_uv(walls, scale=0.28)
    return walls


def _make_window(name, cx, cy, w, h, z0, wood, glass) -> list:
    objs = []
    frame_t = 0.08
    cz = z0 + h * 0.5
    # Outer frame
    objs.append(box(
        f"{name}_frame",
        (cx, cy + 0.02, cz),
        (w + 0.08, frame_t, h + 0.08),
        wood,
    ))
    # Mullion / muntin cross
    objs.append(box(
        f"{name}_mull_v",
        (cx, cy + 0.04, cz),
        (0.06, 0.04, h - 0.06),
        wood,
    ))
    objs.append(box(
        f"{name}_mull_h",
        (cx, cy + 0.04, cz),
        (w - 0.1, 0.04, 0.06),
        wood,
    ))
    # Glass panes (4)
    pw, ph = (w - 0.16) * 0.5, (h - 0.16) * 0.5
    for ix, ox in ((-1, -pw * 0.5 - 0.03), (1, pw * 0.5 + 0.03)):
        for iz, oz in ((-1, -ph * 0.5 - 0.03), (1, ph * 0.5 + 0.03)):
            objs.append(box(
                f"{name}_glass_{ix}_{iz}",
                (cx + ox, cy + 0.05, cz + oz),
                (pw, 0.02, ph),
                glass,
            ))
    return objs


def _make_side_window(name, cx, cy, sx, w, h, z0, wood, glass) -> list:
    objs = []
    cz = z0 + h * 0.5
    objs.append(box(
        f"{name}_frame",
        (cx, cy, cz),
        (WALL_T + 0.04, w + 0.08, h + 0.08),
        wood,
    ))
    objs.append(box(
        f"{name}_glass",
        (cx + sx * 0.02, cy, cz),
        (0.03, w - 0.12, h - 0.12),
        glass,
    ))
    return objs


# ── Door (hinged) ─────────────────────────────────────────────────────────

def build_door(mats: dict) -> bpy.types.Object:
    wood = mats["building_door_wood"]
    metal = mats["building_metal"]
    parts: list[bpy.types.Object] = []

    # Door sits in the front opening; hinge on the LEFT (smaller X)
    hinge_x = DOOR_CX - DOOR_W * 0.5 + DOOR_GAP
    front_y = HALF_D - WALL_T * 0.5 + DOOR_T * 0.5 + 0.01

    # Main panel (rounded top approximated with extra blocks + cylinder slice)
    straight_h = DOOR_H - DOOR_ARCH_R
    panel = box(
        "door_panel",
        (DOOR_CX, front_y, straight_h * 0.5 + 0.02),
        (DOOR_W - 2 * DOOR_GAP, DOOR_T, straight_h),
        wood,
    )
    parts.append(panel)

    # Arch top — semicylinder
    bpy.ops.mesh.primitive_cylinder_add(
        radius=DOOR_ARCH_R - DOOR_GAP * 0.5,
        depth=DOOR_T,
        vertices=16,
        location=(DOOR_CX, front_y, straight_h),
        rotation=(math.pi * 0.5, 0, 0),
    )
    arch = bpy.context.active_object
    arch.name = "door_arch"
    apply_trs(arch)
    # Keep only upper half by bisect
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.bisect(
        plane_co=(DOOR_CX, front_y, straight_h),
        plane_no=(0, 0, -1),
        clear_inner=True,
        clear_outer=False,
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    assign_mat(arch, wood)
    parts.append(arch)

    # Iron bands
    for i, z in enumerate((0.35, 1.05, 1.75)):
        parts.append(box(
            f"door_band_{i}",
            (DOOR_CX, front_y + DOOR_T * 0.55, z),
            (DOOR_W - 0.12, 0.02, 0.08),
            metal,
        ))

    # Hinge straps (3)
    for i, z in enumerate((0.40, 1.10, 1.80)):
        parts.append(box(
            f"hinge_strap_{i}",
            (hinge_x + 0.18, front_y + DOOR_T * 0.6, z),
            (0.36, 0.025, 0.10),
            metal,
        ))
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.035,
            depth=0.12,
            vertices=8,
            location=(hinge_x + 0.02, front_y + DOOR_T * 0.55, z),
        )
        knuckle = bpy.context.active_object
        knuckle.name = f"hinge_knuckle_{i}"
        apply_trs(knuckle)
        assign_mat(knuckle, metal)
        parts.append(knuckle)

    # Ring pull
    parts.append(box(
        "pull_plate",
        (DOOR_CX + DOOR_W * 0.28, front_y + DOOR_T * 0.65, 1.15),
        (0.16, 0.02, 0.22),
        metal,
    ))
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.09,
        minor_radius=0.018,
        major_segments=12,
        minor_segments=6,
        location=(DOOR_CX + DOOR_W * 0.28, front_y + DOOR_T * 0.85, 1.05),
        rotation=(math.pi * 0.5, 0, 0),
    )
    ring = bpy.context.active_object
    ring.name = "pull_ring"
    apply_trs(ring)
    assign_mat(ring, metal)
    parts.append(ring)

    # Studs
    for xi in (-0.35, -0.15, 0.15, 0.35):
        for z in (0.55, 1.25, 1.95):
            bpy.ops.mesh.primitive_uv_sphere_add(
                radius=0.03, segments=8, ring_count=4,
                location=(DOOR_CX + xi, front_y + DOOR_T * 0.7, z),
            )
            stud = bpy.context.active_object
            apply_trs(stud)
            assign_mat(stud, metal)
            parts.append(stud)

    door = join_group(parts, "Building1_Door")
    ensure_uv(door, scale=0.45)

    # Origin on hinge line at ground
    hinge_world = (hinge_x, front_y, 0.0)
    set_origin_to_point(door, hinge_world)
    return door


# ── Roof (removable) ──────────────────────────────────────────────────────

def build_roof(mats: dict) -> bpy.types.Object:
    tiles = mats["building_round_tiles"]
    wood = mats["building_wood_trim"]
    plaster = mats["building_plaster"]
    parts: list[bpy.types.Object] = []

    # Gable roof: two slopes along Y (ridge parallel to X)
    # Front slope (+Y) and back slope (−Y)
    ridge_y = 0.0
    eave_y_f = HALF_D + OVERHANG
    eave_y_b = -HALF_D - OVERHANG
    eave_z = EAVE_Z - 0.05
    roof_x = BUILD_W + 2 * OVERHANG

    def slope_panel(name, y0, y1, z0, z1, mat):
        """Create a thin roof slab between two Y edges via a rotated cube."""
        cy = (y0 + y1) * 0.5
        cz = (z0 + z1) * 0.5
        dy = y1 - y0
        dz = z1 - z0
        length = math.hypot(dy, dz)
        angle = math.atan2(dz, dy)  # rotate around X
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, cy, cz))
        obj = bpy.context.active_object
        obj.name = name
        obj.scale = (roof_x, length, 0.12)
        obj.rotation_euler = (angle, 0, 0)
        apply_trs(obj)
        assign_mat(obj, mat)
        return obj

    parts.append(slope_panel(
        "roof_front", eave_y_f, ridge_y, eave_z, RIDGE_Z, tiles,
    ))
    parts.append(slope_panel(
        "roof_back", ridge_y, eave_y_b, RIDGE_Z, eave_z, tiles,
    ))

    # Layered tile rows for silhouette depth (front slope)
    rows = 10
    for i in range(rows):
        t = (i + 0.5) / rows
        y = eave_y_f + (ridge_y - eave_y_f) * t
        z = eave_z + (RIDGE_Z - eave_z) * t + 0.06
        # stagger rows slightly
        x_off = 0.08 if i % 2 else 0.0
        parts.append(box(
            f"tile_row_f_{i}",
            (x_off, y, z),
            (roof_x - 0.3, 0.42, 0.05),
            tiles,
        ))
    for i in range(rows):
        t = (i + 0.5) / rows
        y = ridge_y + (eave_y_b - ridge_y) * t
        z = RIDGE_Z + (eave_z - RIDGE_Z) * t + 0.06
        x_off = 0.08 if i % 2 else 0.0
        parts.append(box(
            f"tile_row_b_{i}",
            (x_off, y, z),
            (roof_x - 0.3, 0.42, 0.05),
            tiles,
        ))

    # Ridge beam
    parts.append(box(
        "ridge_beam",
        (0, 0, RIDGE_Z - 0.05),
        (roof_x + 0.1, 0.16, 0.14),
        wood,
    ))

    # Gable end triangles (plaster) — left and right
    for sx, name in ((-1, "gable_L"), (1, "gable_R")):
        gable = _make_gable(
            name,
            x=sx * (HALF_W - WALL_T * 0.5),
            mat_plaster=plaster,
            mat_wood=wood,
        )
        parts.append(gable)

    # Fascia boards
    parts.append(box(
        "fascia_front",
        (0, eave_y_f - 0.02, eave_z - 0.05),
        (roof_x, 0.08, 0.16),
        wood,
    ))
    parts.append(box(
        "fascia_back",
        (0, eave_y_b + 0.02, eave_z - 0.05),
        (roof_x, 0.08, 0.16),
        wood,
    ))

    # Soffit strips under eaves
    parts.append(box(
        "soffit_front",
        (0, HALF_D + OVERHANG * 0.45, EAVE_Z - 0.18),
        (roof_x - 0.2, OVERHANG * 0.85, 0.04),
        plaster,
    ))
    parts.append(box(
        "soffit_back",
        (0, -HALF_D - OVERHANG * 0.45, EAVE_Z - 0.18),
        (roof_x - 0.2, OVERHANG * 0.85, 0.04),
        plaster,
    ))

    # Chimney on back-left roof
    parts.append(box(
        "chimney",
        (-3.2, -1.1, RIDGE_Z + 0.35),
        (0.70, 0.70, 1.40),
        mats["building_rock_trim"],
    ))
    parts.append(box(
        "chimney_cap",
        (-3.2, -1.1, RIDGE_Z + 1.10),
        (0.85, 0.85, 0.12),
        mats["building_rock_trim"],
    ))

    roof = join_group(parts, "Building1_Roof")
    ensure_uv(roof, scale=0.22)
    return roof


def _make_gable(name, x, mat_plaster, mat_wood) -> bpy.types.Object:
    """Triangular gable fill under the roof peaks at ±X ends."""
    # Approximate with a tall thin wedge using a cube scaled/rotated + bisect
    # Simpler: stacked plaster blocks forming a triangle silhouette
    parts = []
    steps = 6
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        z0 = EAVE_Z + (RIDGE_Z - EAVE_Z) * t0
        z1 = EAVE_Z + (RIDGE_Z - EAVE_Z) * t1
        # half-depth of roof at this height
        # at eave: HALF_D+OVERHANG, at ridge: 0
        depth0 = (HALF_D + OVERHANG) * (1.0 - t0)
        depth1 = (HALF_D + OVERHANG) * (1.0 - t1)
        depth = (depth0 + depth1) * 0.5
        cz = (z0 + z1) * 0.5
        h = max(z1 - z0, 0.05)
        parts.append(box(
            f"{name}_step_{i}",
            (x, 0, cz),
            (WALL_T * 0.9, depth * 2, h),
            mat_plaster,
        ))
    # Timber bargeboard edges
    length = math.hypot(HALF_D + OVERHANG, RIDGE_Z - EAVE_Z)
    ang = math.atan2(RIDGE_Z - EAVE_Z, HALF_D + OVERHANG)
    for sy in (1, -1):
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        obj = bpy.context.active_object
        obj.name = f"{name}_barge_{sy}"
        obj.scale = (0.10, length, 0.12)
        # place along slope
        cy = sy * (HALF_D + OVERHANG) * 0.5
        cz = (EAVE_Z + RIDGE_Z) * 0.5
        obj.location = (x, cy, cz)
        obj.rotation_euler = (sy * ang, 0, 0)
        apply_trs(obj)
        assign_mat(obj, mat_wood)
        parts.append(obj)
    return join_group(parts, name)


# ── Export ────────────────────────────────────────────────────────────────

def export_multi(objs: list[bpy.types.Object], out_path: str, *, apply: bool):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        o.hide_set(False)
        o.hide_render = False
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=apply,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
    )


def dual_write(filename: str, objs: list, *, apply: bool):
    for d in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(d, filename)
        export_multi(objs, path, apply=apply)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


# ── Main ──────────────────────────────────────────────────────────────────

def build_all():
    clear_scene()
    print("\n=== Building1Whole — medieval modular cottage ===")
    mats = make_materials()

    walls = build_walls(mats)
    door = build_door(mats)
    roof = build_roof(mats)

    # Bake walls + roof TRS; door keeps hinge origin (location ≠ 0)
    apply_trs(walls)
    apply_trs(roof)
    # Door already has custom origin — do NOT apply location (would break hinge)
    bpy.ops.object.select_all(action="DESELECT")
    door.select_set(True)
    bpy.context.view_layer.objects.active = door
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    total = 0
    total += report(walls, "walls")
    total += report(door, "door")
    total += report(roof, "roof")
    print(f"  TOTAL tris≈{total}")

    # 1) Complete
    print("\nExport Complete…")
    dual_write("Building1Whole.glb", [walls, door, roof], apply=False)

    # 2) Roof removed
    print("\nExport NoRoof…")
    dual_write("Building1Whole_NoRoof.glb", [walls, door], apply=False)

    # 3) Door open (~95° around local Z)
    print("\nExport DoorOpen…")
    door.rotation_euler = (0, 0, math.radians(95))
    bpy.context.view_layer.update()
    dual_write("Building1Whole_DoorOpen.glb", [walls, door, roof], apply=False)
    door.rotation_euler = (0, 0, 0)

    print("\nDONE — Building1Whole variants exported.")
    return total


if __name__ == "__main__":
    # Allow `blender --python this.py --` with no extra args
    build_all()
