"""
generate_storehouse.py
======================
Simple medieval pioneering storehouse — from-scratch geometry with
tileable BaseColor maps (storehouse_textures/).

  Modular pieces in one GLB:
    Storehouse_Walls  — stone plinth, plaster + half-timber, windows, floor
    Storehouse_Door   — hinged oak door (origin on hinge; rotate local +Z)
    Storehouse_Roof   — removable terracotta gable + chimney

  Footprint 5.20 m (X) × 4.00 m (Y) × ~4.55 m (Z-up).

Outputs (Desktop + viewer):
  Storehouse.glb
  Storehouse_NoRoof.glb
  Storehouse_DoorOpen.glb

Run:
  python3 generate_storehouse_textures.py
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_storehouse.py
"""

from __future__ import annotations

import math
import os
import subprocess

import bpy


ROOT = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(ROOT, "storehouse_textures")
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath(os.path.join(ROOT, "viewer/public/buildings"))

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

BUILD_W = 5.20
BUILD_D = 4.00
HALF_W = BUILD_W * 0.5
HALF_D = BUILD_D * 0.5

WALL_T = 0.22
FLOOR_Z = 0.08
ROCK_H = 0.46
EAVE_Z = 2.72
RIDGE_Z = 4.50
OVERHANG = 0.32

DOOR_W = 1.08
DOOR_H = 2.00
DOOR_T = 0.07
DOOR_CX = -0.72
DOOR_GAP = 0.02
DOOR_Z0 = 0.44
DOOR_TOP = DOOR_Z0 + DOOR_H

WIN_W = 0.92
WIN_H = 1.00
WIN_Z0 = 1.18
WIN_CX = 1.28


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def ensure_textures() -> None:
    needed = [
        "Storehouse_Plaster_BaseColor.png",
        "Storehouse_Wood_BaseColor.png",
        "Storehouse_Stone_BaseColor.png",
        "Storehouse_Tiles_BaseColor.png",
        "Storehouse_DoorWood_BaseColor.png",
        "Storehouse_Metal_BaseColor.png",
        "Storehouse_Glass_BaseColor.png",
    ]
    if all(os.path.isfile(os.path.join(TEX_DIR, n)) for n in needed):
        return
    gen = os.path.join(ROOT, "generate_storehouse_textures.py")
    print("  generating storehouse textures…")
    subprocess.check_call(["python3", gen])


def apply_trs(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def set_origin_to_point(obj: bpy.types.Object, world_point: tuple[float, float, float]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.scene.cursor.location = world_point
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")


def assign_mat(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def box_uv(obj: bpy.types.Object, scale: float) -> None:
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active
    for poly in me.polygons:
        n = poly.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if az >= ax and az >= ay:
                u, v = co.x, co.y
            elif ax >= ay:
                u, v = co.y, co.z
            else:
                u, v = co.x, co.z
            uv.data[li].uv = (u * scale, v * scale)


def wood_uv(obj: bpy.types.Object, scale: float = 0.95) -> None:
    me = obj.data
    xs = [v.co.x for v in me.vertices]
    ys = [v.co.y for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    dims = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    grain = dims.index(max(dims))
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            v = (co.x, co.y, co.z)[grain]
            if grain == 2:
                u = co.x if abs(n.y) >= abs(n.x) else co.y
            elif grain == 0:
                u = co.z if abs(n.y) >= abs(n.z) else co.y
            else:
                u = co.z if abs(n.x) >= abs(n.z) else co.x
            uv.data[li].uv = (u * scale * 2.4, v * scale)


def roof_uv(obj: bpy.types.Object, u_scale: float = 0.52, v_scale: float = 0.52) -> None:
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active
    eave_y = HALF_D + OVERHANG
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            along = math.hypot(abs(co.y) - 0.0, max(0.0, co.z - (EAVE_Z - 0.1)))
            # fall back: distance from front eave along the roof plane
            along = math.hypot(eave_y - abs(co.y), max(0.0, co.z - (EAVE_Z - 0.08)))
            uv.data[li].uv = (co.x * u_scale, along * v_scale)


def box(
    name: str,
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    mat: bpy.types.Material,
    *,
    uv: str = "box",
    uv_scale: float = 0.55,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    apply_trs(obj)
    assign_mat(obj, mat)
    if uv == "wood":
        wood_uv(obj, uv_scale)
    elif uv == "roof":
        roof_uv(obj, uv_scale, uv_scale)
    else:
        box_uv(obj, uv_scale)
    return obj


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


def report(obj: bpy.types.Object, label: str) -> int:
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    mats = [m.name if m else "?" for m in obj.data.materials]
    xs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    print(f"  [{label}] verts={len(obj.data.vertices)} tris={tris} mats={mats}")
    print(
        f"  [{label}] X[{min(v.x for v in xs):+.2f},{max(v.x for v in xs):+.2f}] "
        f"Y[{min(v.y for v in xs):+.2f},{max(v.y for v in xs):+.2f}] "
        f"Z[{min(v.z for v in xs):+.2f},{max(v.z for v in xs):+.2f}]"
    )
    return tris


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
    tex.extension = "REPEAT"
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
        "plaster": make_textured_material(
            "storehouse_plaster", load_image("Storehouse_Plaster_BaseColor.png"), roughness=0.92
        ),
        "wood": make_textured_material(
            "storehouse_wood", load_image("Storehouse_Wood_BaseColor.png"), roughness=0.80
        ),
        "stone": make_textured_material(
            "storehouse_stone", load_image("Storehouse_Stone_BaseColor.png"), roughness=0.90
        ),
        "tiles": make_textured_material(
            "storehouse_tiles", load_image("Storehouse_Tiles_BaseColor.png"), roughness=0.78
        ),
        "door": make_textured_material(
            "storehouse_door", load_image("Storehouse_DoorWood_BaseColor.png"), roughness=0.82
        ),
        "metal": make_textured_material(
            "storehouse_metal",
            load_image("Storehouse_Metal_BaseColor.png"),
            roughness=0.48,
            metallic=0.70,
        ),
        "glass": make_textured_material(
            "storehouse_glass",
            load_image("Storehouse_Glass_BaseColor.png"),
            roughness=0.10,
            alpha_blend=True,
            alpha_value=0.20,
        ),
    }


BEAM = 0.14
TIMBER_PROUD = 0.055  # timber sits on the exterior face, not inside the plaster
SIDE_WIN_W = 1.10
SIDE_WIN_H = 0.95
SIDE_WIN_CY = 0.10


def _front_window(name: str, cx: float, y_face: float, w: float, h: float, z0: float, wood, glass) -> list:
    objs = []
    cz = z0 + h * 0.5
    ft = 0.06
    objs.append(box(f"{name}_top", (cx, y_face, z0 + h + 0.02), (w + 0.12, ft, 0.08), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_bot", (cx, y_face, z0 - 0.02), (w + 0.16, ft + 0.04, 0.07), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_L", (cx - w * 0.5, y_face, cz), (0.07, ft, h + 0.04), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_R", (cx + w * 0.5, y_face, cz), (0.07, ft, h + 0.04), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_mull_v", (cx, y_face + 0.01, cz), (0.045, 0.04, h - 0.06), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_mull_h", (cx, y_face + 0.01, cz), (w - 0.10, 0.04, 0.045), wood, uv="wood", uv_scale=0.9))
    pw, ph = (w - 0.14) * 0.5, (h - 0.14) * 0.5
    for ox in (-pw * 0.5 - 0.025, pw * 0.5 + 0.025):
        for oz in (-ph * 0.5 - 0.025, ph * 0.5 + 0.025):
            objs.append(
                box(
                    f"{name}_g_{ox:.2f}_{oz:.2f}",
                    (cx + ox, y_face + 0.02, cz + oz),
                    (pw, 0.016, ph),
                    glass,
                    uv_scale=0.7,
                )
            )
    return objs


def _side_window(name: str, sx: float, cy: float, w: float, h: float, z0: float, wood, glass) -> list:
    objs = []
    x_face = sx * (HALF_W + TIMBER_PROUD - 0.02)
    cz = z0 + h * 0.5
    ft = 0.06
    objs.append(box(f"{name}_top", (x_face, cy, z0 + h + 0.02), (ft, w + 0.12, 0.08), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_bot", (x_face, cy, z0 - 0.02), (ft + 0.03, w + 0.16, 0.07), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_N", (x_face, cy - w * 0.5, cz), (ft, 0.07, h + 0.04), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_S", (x_face, cy + w * 0.5, cz), (ft, 0.07, h + 0.04), wood, uv="wood", uv_scale=0.9))
    objs.append(box(f"{name}_mull", (x_face + sx * 0.01, cy, cz), (0.04, 0.045, h - 0.08), wood, uv="wood", uv_scale=0.9))
    objs.append(
        box(
            f"{name}_glass",
            (x_face + sx * 0.02, cy, cz),
            (0.016, w - 0.16, h - 0.16),
            glass,
            uv_scale=0.7,
        )
    )
    return objs


def build_walls(mats: dict) -> bpy.types.Object:
    parts: list[bpy.types.Object] = []
    plaster, wood, stone, glass = mats["plaster"], mats["wood"], mats["stone"], mats["glass"]

    parts.append(
        box("floor", (0, 0, FLOOR_Z * 0.5), (BUILD_W - 0.08, BUILD_D - 0.08, FLOOR_Z), wood, uv="wood", uv_scale=0.7)
    )

    # Front rock is split so the door sits on a low stone threshold, not through the plinth.
    rock_front_y = HALF_D - WALL_T * 0.5
    door_l = DOOR_CX - DOOR_W * 0.5
    door_r = DOOR_CX + DOOR_W * 0.5
    rock_specs = [
        ((-HALF_W + door_l) * 0.5, rock_front_y, ROCK_H * 0.5, door_l - (-HALF_W) + 0.04, WALL_T + 0.04, ROCK_H),
        ((door_r + HALF_W) * 0.5, rock_front_y, ROCK_H * 0.5, HALF_W - door_r + 0.04, WALL_T + 0.04, ROCK_H),
        (DOOR_CX, rock_front_y, DOOR_Z0 * 0.5, DOOR_W + 0.04, WALL_T + 0.04, DOOR_Z0),
        (0, -HALF_D + WALL_T * 0.5, ROCK_H * 0.5, BUILD_W + 0.04, WALL_T + 0.04, ROCK_H),
        (-HALF_W + WALL_T * 0.5, 0, ROCK_H * 0.5, WALL_T + 0.04, BUILD_D - 2 * WALL_T, ROCK_H),
        (HALF_W - WALL_T * 0.5, 0, ROCK_H * 0.5, WALL_T + 0.04, BUILD_D - 2 * WALL_T, ROCK_H),
    ]
    for i, (cx, cy, cz, sx, sy, sz) in enumerate(rock_specs):
        parts.append(box(f"rock_{i}", (cx, cy, cz), (sx, sy, sz), stone, uv_scale=0.62))

    qw, qh = 0.30, 0.82
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(
                box(
                    f"quoin_{sx}_{sy}",
                    (sx * (HALF_W - 0.04), sy * (HALF_D - 0.04), qh * 0.5),
                    (qw, qw, qh),
                    stone,
                    uv_scale=0.62,
                )
            )

    z0, z1 = ROCK_H, EAVE_Z
    mid_z = (z0 + z1) * 0.5
    h = z1 - z0
    plaster_t = WALL_T - 0.04
    fy_plaster = HALF_D - plaster_t * 0.5 - 0.03
    by_plaster = -HALF_D + plaster_t * 0.5 + 0.03
    y_face = HALF_D + TIMBER_PROUD
    y_back = -HALF_D - TIMBER_PROUD
    x_left = -HALF_W - TIMBER_PROUD
    x_right = HALF_W + TIMBER_PROUD

    win_l, win_r = WIN_CX - WIN_W * 0.5, WIN_CX + WIN_W * 0.5
    side_a, side_b = SIDE_WIN_CY - SIDE_WIN_W * 0.5, SIDE_WIN_CY + SIDE_WIN_W * 0.5

    def plaster_panel(name: str, cx: float, cy: float, cz: float, sx: float, sy: float, sz: float) -> None:
        if sx < 0.05 or sy < 0.05 or sz < 0.05:
            return
        parts.append(box(name, (cx, cy, cz), (sx, sy, sz), plaster, uv_scale=0.42))

    # Front plaster around door + window
    for i, (a, b) in enumerate(((-HALF_W, door_l), (door_r, win_l), (win_r, HALF_W))):
        plaster_panel(f"front_full_{i}", (a + b) * 0.5, fy_plaster, mid_z, b - a, plaster_t, h)
    plaster_panel("front_below_win", WIN_CX, fy_plaster, (z0 + WIN_Z0) * 0.5, WIN_W, plaster_t, WIN_Z0 - z0)
    plaster_panel("front_above_win", WIN_CX, fy_plaster, (WIN_Z0 + WIN_H + z1) * 0.5, WIN_W, plaster_t, z1 - (WIN_Z0 + WIN_H))
    plaster_panel("front_above_door", DOOR_CX, fy_plaster, (DOOR_TOP + 0.04 + z1) * 0.5, DOOR_W, plaster_t, z1 - (DOOR_TOP + 0.04))

    # Back plaster (solid)
    plaster_panel("wall_back", 0, by_plaster, mid_z, BUILD_W, plaster_t, h)

    # Side plaster around windows
    for side, x_pl in (("L", -HALF_W + plaster_t * 0.5 + 0.03), ("R", HALF_W - plaster_t * 0.5 - 0.03)):
        for i, (a, b) in enumerate(((-HALF_D + WALL_T, side_a), (side_b, HALF_D - WALL_T))):
            plaster_panel(f"side_{side}_full_{i}", x_pl, (a + b) * 0.5, mid_z, plaster_t, b - a, h)
        plaster_panel(
            f"side_{side}_below",
            x_pl,
            SIDE_WIN_CY,
            (z0 + WIN_Z0) * 0.5,
            plaster_t,
            SIDE_WIN_W,
            WIN_Z0 - z0,
        )
        plaster_panel(
            f"side_{side}_above",
            x_pl,
            SIDE_WIN_CY,
            (WIN_Z0 + SIDE_WIN_H + z1) * 0.5,
            plaster_t,
            SIDE_WIN_W,
            z1 - (WIN_Z0 + SIDE_WIN_H),
        )

    # Corner posts — proud on the exterior corner
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(
                box(
                    f"post_{sx}_{sy}",
                    (sx * (HALF_W + TIMBER_PROUD * 0.2), sy * (HALF_D + TIMBER_PROUD * 0.2), mid_z),
                    (BEAM, BEAM, h + 0.06),
                    wood,
                    uv="wood",
                    uv_scale=0.9,
                )
            )

    # Front / back studs + plates + belts + braces
    for x in (-1.85, 0.20, 1.85):
        parts.append(box(f"stud_f_{x}", (x, y_face, mid_z), (BEAM * 0.85, 0.08, h), wood, uv="wood", uv_scale=0.9))
        parts.append(box(f"stud_b_{x}", (x, y_back, mid_z), (BEAM * 0.85, 0.08, h), wood, uv="wood", uv_scale=0.9))

    for y, name in ((y_face, "f"), (y_back, "b")):
        parts.append(box(f"plate_{name}", (0, y, EAVE_Z - 0.06), (BUILD_W + 0.08, 0.08, 0.13), wood, uv="wood", uv_scale=0.85))
        parts.append(box(f"belt_{name}", (0, y, ROCK_H + 0.08), (BUILD_W + 0.08, 0.08, 0.11), wood, uv="wood", uv_scale=0.85))
        parts.append(box(f"mid_{name}", (0, y, ROCK_H + h * 0.52), (BUILD_W - 0.3, 0.07, 0.10), wood, uv="wood", uv_scale=0.85))

    for sx, name in ((-1, "brace_fL"), (1, "brace_fR")):
        parts.append(
            box(
                name,
                (sx * 2.05, y_face, ROCK_H + 0.95),
                (0.09, 0.07, 1.35),
                wood,
                uv="wood",
                uv_scale=0.9,
                rotation=(0.0, sx * math.radians(-34), 0.0),
            )
        )
    for sx, name in ((-1, "brace_bL"), (1, "brace_bR")):
        parts.append(
            box(
                name,
                (sx * 2.05, y_back, ROCK_H + 0.95),
                (0.09, 0.07, 1.35),
                wood,
                uv="wood",
                uv_scale=0.9,
                rotation=(0.0, sx * math.radians(34), 0.0),
            )
        )

    for x, name in ((x_left, "L"), (x_right, "R")):
        parts.append(box(f"plate_{name}", (x, 0, EAVE_Z - 0.06), (0.08, BUILD_D + 0.08, 0.13), wood, uv="wood", uv_scale=0.85))
        parts.append(box(f"belt_{name}", (x, 0, ROCK_H + 0.08), (0.08, BUILD_D + 0.08, 0.11), wood, uv="wood", uv_scale=0.85))
        parts.append(box(f"mid_{name}", (x, 0, ROCK_H + h * 0.52), (0.07, BUILD_D - 0.35, 0.10), wood, uv="wood", uv_scale=0.85))
        parts.append(box(f"stud_{name}", (x, -1.15, mid_z), (0.08, BEAM * 0.85, h), wood, uv="wood", uv_scale=0.9))

    parts.append(
        box("lintel", (DOOR_CX, y_face, DOOR_TOP + 0.06), (DOOR_W + 0.20, 0.10, 0.10), wood, uv="wood", uv_scale=0.9)
    )
    parts.append(box("step", (DOOR_CX, HALF_D + 0.12, 0.06), (DOOR_W + 0.30, 0.30, 0.12), stone, uv_scale=0.7))

    parts.extend(_front_window("winF", WIN_CX, y_face, WIN_W, WIN_H, WIN_Z0, wood, glass))
    parts.extend(_side_window("winL", -1, SIDE_WIN_CY, SIDE_WIN_W, SIDE_WIN_H, WIN_Z0, wood, glass))
    parts.extend(_side_window("winR", 1, SIDE_WIN_CY, SIDE_WIN_W, SIDE_WIN_H, WIN_Z0, wood, glass))

    for i, x in enumerate((-1.4, 0.0, 1.4)):
        parts.append(
            box(f"joist_{i}", (x, 0, EAVE_Z - 0.12), (0.11, BUILD_D - 0.5, 0.14), wood, uv="wood", uv_scale=0.85)
        )

    return join_group(parts, "Storehouse_Walls")


def build_door(mats: dict) -> bpy.types.Object:
    wood, metal = mats["door"], mats["metal"]
    parts: list[bpy.types.Object] = []
    hinge_x = DOOR_CX - DOOR_W * 0.5 + DOOR_GAP
    front_y = HALF_D + TIMBER_PROUD + DOOR_T * 0.5

    parts.append(
        box(
            "door_panel",
            (DOOR_CX, front_y, DOOR_Z0 + DOOR_H * 0.5),
            (DOOR_W - 2 * DOOR_GAP, DOOR_T, DOOR_H - 0.04),
            wood,
            uv="wood",
            uv_scale=0.55,
        )
    )
    for i, z in enumerate((DOOR_Z0 + 0.32, DOOR_Z0 + 0.95, DOOR_Z0 + 1.55)):
        parts.append(
            box(
                f"door_band_{i}",
                (DOOR_CX, front_y + DOOR_T * 0.55, z),
                (DOOR_W - 0.14, 0.018, 0.07),
                metal,
                uv_scale=1.1,
            )
        )
        parts.append(
            box(
                f"hinge_strap_{i}",
                (hinge_x + 0.16, front_y + DOOR_T * 0.62, z),
                (0.32, 0.022, 0.09),
                metal,
                uv_scale=1.1,
            )
        )
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.03,
            depth=0.10,
            vertices=8,
            location=(hinge_x + 0.02, front_y + DOOR_T * 0.5, z),
        )
        knuckle = bpy.context.active_object
        knuckle.name = f"hinge_knuckle_{i}"
        apply_trs(knuckle)
        assign_mat(knuckle, metal)
        box_uv(knuckle, 1.1)
        parts.append(knuckle)

    parts.append(
        box(
            "pull_plate",
            (DOOR_CX + DOOR_W * 0.28, front_y + DOOR_T * 0.65, DOOR_Z0 + 0.94),
            (0.14, 0.018, 0.20),
            metal,
            uv_scale=1.2,
        )
    )
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.08,
        minor_radius=0.016,
        major_segments=12,
        minor_segments=6,
        location=(DOOR_CX + DOOR_W * 0.28, front_y + DOOR_T * 0.82, DOOR_Z0 + 0.84),
        rotation=(math.pi * 0.5, 0, 0),
    )
    ring = bpy.context.active_object
    ring.name = "pull_ring"
    apply_trs(ring)
    assign_mat(ring, metal)
    box_uv(ring, 1.2)
    parts.append(ring)

    door = join_group(parts, "Storehouse_Door")
    set_origin_to_point(door, (hinge_x, front_y, 0.0))
    return door


def _make_gable(name: str, x: float, plaster, wood) -> bpy.types.Object:
    """Stepped plaster gable kept *under* the roof, plus a proud timber frame."""
    parts = []
    steps = 5
    for i in range(steps):
        t0 = i / steps
        t1 = (i + 1) / steps
        z0 = EAVE_Z + (RIDGE_Z - EAVE_Z) * t0
        z1 = EAVE_Z + (RIDGE_Z - EAVE_Z) * t1
        depth = (HALF_D + OVERHANG * 0.15) * (1.0 - (t0 + t1) * 0.5) * 0.90
        parts.append(
            box(
                f"{name}_step_{i}",
                (x, 0, (z0 + z1) * 0.5),
                (WALL_T * 0.85, max(depth * 2, 0.12), max(z1 - z0, 0.05)),
                plaster,
                uv_scale=0.42,
            )
        )
    # Proud timber on the gable face (no bargeboards — those pierced the roof)
    x_face = x + (0.07 if x > 0 else -0.07)
    gable_h = RIDGE_Z - EAVE_Z
    parts.append(
        box(f"{name}_post", (x_face, 0, EAVE_Z + gable_h * 0.5), (0.08, 0.12, gable_h), wood, uv="wood", uv_scale=0.9)
    )
    parts.append(
        box(
            f"{name}_collar",
            (x_face, 0, EAVE_Z + gable_h * 0.42),
            (0.07, (HALF_D + 0.05) * 1.15, 0.10),
            wood,
            uv="wood",
            uv_scale=0.85,
        )
    )
    return join_group(parts, name)


def build_roof(mats: dict) -> bpy.types.Object:
    tiles, wood, plaster, stone = mats["tiles"], mats["wood"], mats["plaster"], mats["stone"]
    parts: list[bpy.types.Object] = []
    eave_y_f = HALF_D + OVERHANG
    eave_y_b = -HALF_D - OVERHANG
    eave_z = EAVE_Z - 0.04
    roof_x = BUILD_W + 2 * OVERHANG

    def slope_panel(name: str, y0: float, y1: float, z0: float, z1: float) -> bpy.types.Object:
        cy = (y0 + y1) * 0.5
        cz = (z0 + z1) * 0.5
        dy, dz = y1 - y0, z1 - z0
        length = math.hypot(dy, dz)
        angle = math.atan2(dz, dy)
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, cy, cz))
        obj = bpy.context.active_object
        obj.name = name
        obj.scale = (roof_x, length, 0.11)
        obj.rotation_euler = (angle, 0, 0)
        apply_trs(obj)
        assign_mat(obj, tiles)
        roof_uv(obj)
        return obj

    parts.append(slope_panel("roof_front", eave_y_f, 0.0, eave_z, RIDGE_Z))
    parts.append(slope_panel("roof_back", 0.0, eave_y_b, RIDGE_Z, eave_z))

    parts.append(box("ridge_beam", (0, 0, RIDGE_Z - 0.04), (roof_x + 0.08, 0.14, 0.12), wood, uv="wood", uv_scale=0.85))
    parts.append(_make_gable("gable_L", -(HALF_W - WALL_T * 0.5), plaster, wood))
    parts.append(_make_gable("gable_R", +(HALF_W - WALL_T * 0.5), plaster, wood))
    parts.append(box("fascia_f", (0, eave_y_f - 0.02, eave_z - 0.04), (roof_x, 0.07, 0.14), wood, uv="wood", uv_scale=0.85))
    parts.append(box("fascia_b", (0, eave_y_b + 0.02, eave_z - 0.04), (roof_x, 0.07, 0.14), wood, uv="wood", uv_scale=0.85))

    parts.append(box("chimney", (1.55, -0.85, RIDGE_Z + 0.28), (0.52, 0.52, 1.15), stone, uv_scale=0.7))
    parts.append(box("chimney_cap", (1.55, -0.85, RIDGE_Z + 0.90), (0.64, 0.64, 0.10), stone, uv_scale=0.7))

    return join_group(parts, "Storehouse_Roof")


def export_multi(objs: list[bpy.types.Object], out_path: str, *, apply: bool) -> None:
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


def dual_write(filename: str, objs: list, *, apply: bool) -> None:
    for d in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(d, filename)
        export_multi(objs, path, apply=apply)
        print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def build_all() -> int:
    ensure_textures()
    clear_scene()
    print("\n=== Storehouse — pioneering medieval hut ===")
    mats = make_materials()
    walls = build_walls(mats)
    door = build_door(mats)
    roof = build_roof(mats)

    apply_trs(walls)
    apply_trs(roof)
    bpy.ops.object.select_all(action="DESELECT")
    door.select_set(True)
    bpy.context.view_layer.objects.active = door
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    total = report(walls, "walls") + report(door, "door") + report(roof, "roof")
    print(f"  TOTAL tris≈{total}")

    print("\nExport Complete…")
    dual_write("Storehouse.glb", [walls, door, roof], apply=False)
    print("\nExport NoRoof…")
    dual_write("Storehouse_NoRoof.glb", [walls, door], apply=False)
    print("\nExport DoorOpen…")
    door.rotation_euler = (0, 0, math.radians(95))
    bpy.context.view_layer.update()
    dual_write("Storehouse_DoorOpen.glb", [walls, door, roof], apply=False)
    door.rotation_euler = (0, 0, 0)
    print("\nDONE — Storehouse variants exported.")
    return total


if __name__ == "__main__":
    build_all()
