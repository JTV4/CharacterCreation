"""
generate_castle_keep_kit.py
===========================
Textured modular castle: outer curtain pieces + inner 2-storey keep.

Each piece is its own GLB (Desktop + viewer). Shared 4 m grid.

Curtain:
  CastleCurtainWall, CastleCurtainEntrance, CastleCurtainDoubleDoor,
  CastleTowerPillar, CastleTowerCone, CastleCourtyardFloor,
  CastleCurtainParapet

Keep (fits inside courtyard):
  CastleKeepWall, CastleKeepDoorWall, CastleKeepDoor,
  CastleKeepFloorL1, CastleKeepFloorL2, CastleKeepStairs, CastleKeepRoof,
  CastleKeepAssembled (preview)

Doors: hinge origin on outer edge; rotate local +Z to open.
Gate doors share arch dimensions with CastleCurtainEntrance.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_castle_keep_kit.py
  # optional filter: -- curtain | keep | wall | door | ...
"""

from __future__ import annotations

import math
import os
import sys

import bmesh
import bpy


ROOT = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(ROOT, "castle_keep_textures")
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath(os.path.join(ROOT, "viewer/public/buildings"))
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

# ── Grid ──────────────────────────────────────────────────────────────────
MODULE = 4.0
WALL_T = 0.50
STOREY_H = 3.5
PLINTH_H = 0.15
COPING_H = 0.12
MERLON_H = 0.40

TOWER_R = 0.60
TOWER_H = STOREY_H
CONE_H = 1.80

# Gate opening (shared with double door)
GATE_W = 2.40
GATE_SPRING_Z = 2.40
GATE_R = GATE_W / 2.0
GATE_PEAK_Z = GATE_SPRING_Z + GATE_R
ARCH_SEGS = 14
DOOR_T = 0.08
DOOR_GAP = 0.02

ENTRANCE_W = 5.0
ENTRANCE_D = 1.2

KEEP_SIZE = 8.0
KEEP_DOOR_W = 1.60
KEEP_DOOR_SPRING = 2.10
KEEP_DOOR_R = KEEP_DOOR_W / 2.0
KEEP_DOOR_PEAK = KEEP_DOOR_SPRING + KEEP_DOOR_R

FLOOR_T = 0.18
STAIR_W = 1.40
STAIR_RUN = 3.60


# ── Materials ─────────────────────────────────────────────────────────────

def load_image(name: str) -> bpy.types.Image:
    path = os.path.join(TEX_DIR, name)
    img = bpy.data.images.load(path, check_existing=True)
    img.pack()
    return img


def make_tex_mat(
    name: str, filename: str, *, roughness: float = 0.88, metallic: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = load_image(filename)
    tex.interpolation = "Linear"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


def mats() -> dict[str, bpy.types.Material]:
    return {
        "castle_stone": make_tex_mat("castle_stone", "Stone_BaseColor.png", roughness=0.92),
        "castle_stone_dark": make_tex_mat("castle_stone_dark", "StoneDark_BaseColor.png", roughness=0.90),
        "castle_wood": make_tex_mat("castle_wood", "Wood_BaseColor.png", roughness=0.80),
        "castle_iron": make_tex_mat(
            "castle_iron", "Iron_BaseColor.png", roughness=0.45, metallic=0.8,
        ),
        "castle_roof_tiles": make_tex_mat("castle_roof_tiles", "RoofTiles_BaseColor.png", roughness=0.78),
        "castle_plaster": make_tex_mat("castle_plaster", "Plaster_BaseColor.png", roughness=0.88),
    }


# ── Helpers ───────────────────────────────────────────────────────────────

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def apply_scale_rot(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


def apply_all(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def set_origin(obj, world_point):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.scene.cursor.location = world_point
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def uv_smart(obj, scale=0.35):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    if obj.data.uv_layers:
        for loop in obj.data.uv_layers.active.data:
            loop.uv *= scale


def box(name, center, size, mat) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = size
    apply_scale_rot(obj)
    assign(obj, mat)
    return obj


def cyl(name, center, radius, height, mat, segs=14) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=segs, radius=radius, depth=height, location=center,
    )
    obj = bpy.context.active_object
    obj.name = name
    apply_scale_rot(obj)
    assign(obj, mat)
    return obj


def cone(name, center, radius1, radius2, height, mat, segs=16) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(
        vertices=segs, radius1=radius1, radius2=radius2, depth=height, location=center,
    )
    obj = bpy.context.active_object
    obj.name = name
    apply_scale_rot(obj)
    assign(obj, mat)
    return obj


def join(objects: list, name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    return obj


def report(obj, label):
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    print(f"  [{label}] tris={tris} verts={len(obj.data.vertices)}")
    return tris


def export_single(obj, path):
    apply_all(obj)
    uv_smart(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True,
        export_apply=True, export_materials="EXPORT",
        export_texcoords=True, export_normals=True,
    )


def export_multi(objs, path, *, apply=False):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        o.hide_set(False)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=path, export_format="GLB", use_selection=True,
        export_apply=apply, export_materials="EXPORT",
        export_texcoords=True, export_normals=True,
    )


def dual(filename, export_fn):
    for d in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(d, filename)
        export_fn(path)
        print(f"  -> {path} ({os.path.getsize(path)/1024:.1f} KB)")


# ── Arch helpers ──────────────────────────────────────────────────────────

def arch_spandrel(is_left: bool, y0: float, y1: float, mat, prefix: str,
                  opening_half: float, spring_z: float, peak_z: float,
                  header_z: float, segs: int = ARCH_SEGS):
    """Fill stone above quarter-arch (left or right half)."""
    bm = bmesh.new()
    sign = -1.0 if is_left else 1.0
    # Outline CCW in XZ: outer top of header → peak → along arc down → outer spring → up outer
    pts = []
    # outer top corner at header
    outer_x = sign * opening_half
    pts.append((outer_x, 0.0, header_z))
    pts.append((0.0 if not is_left else 0.0, 0.0, header_z))  # center top — fix below
    # Better outline for left half: x from -R to 0
    r = opening_half
    cx = 0.0
    outline = []
    if is_left:
        outline.append((-r, header_z))
        outline.append((0.0, header_z))
        outline.append((0.0, peak_z))
        for i in range(1, segs):
            th = (math.pi / 2) * i / segs
            # from peak (th=0 at top) sweeping left
            ax = -r * math.sin(th)
            az = spring_z + r * math.cos(th)
            outline.append((ax, az))
        outline.append((-r, spring_z))
    else:
        outline.append((0.0, header_z))
        outline.append((r, header_z))
        outline.append((r, spring_z))
        for i in range(segs - 1, 0, -1):
            th = (math.pi / 2) * i / segs
            ax = r * math.sin(th)
            az = spring_z + r * math.cos(th)
            outline.append((ax, az))
        outline.append((0.0, peak_z))

    front = [bm.verts.new((x, y0, z)) for x, z in outline]
    back = [bm.verts.new((x, y1, z)) for x, z in outline]
    n = len(outline)
    if n >= 3:
        bm.faces.new(front)
        bm.faces.new(list(reversed(back)))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([front[i], front[j], back[j], back[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(f"{prefix}_spandrel_{'L' if is_left else 'R'}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"{prefix}_spandrel_{'L' if is_left else 'R'}", mesh)
    bpy.context.collection.objects.link(obj)
    assign(obj, mat)
    return obj


def door_panel_mesh(outer_x, inner_x, z0, spring_z, peak_z, thickness, mat, name, segs=ARCH_SEGS):
    bm = bmesh.new()
    outline = []
    outline.append((outer_x, z0))
    outline.append((inner_x, z0))
    outline.append((inner_x, peak_z))
    radius = abs(outer_x - inner_x)
    sign = -1.0 if outer_x < inner_x else 1.0
    for i in range(1, segs):
        th = (math.pi / 2) * i / segs
        ax = inner_x + sign * radius * math.sin(th)
        az = spring_z + radius * math.cos(th)
        outline.append((ax, az))
    outline.append((outer_x, spring_z))

    front = [bm.verts.new((x, 0.0, z)) for x, z in outline]
    back = [bm.verts.new((x, thickness, z)) for x, z in outline]
    n = len(outline)
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([front[i], front[j], back[j], back[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    assign(obj, mat)
    return obj


# ── Curtain pieces ────────────────────────────────────────────────────────

def build_curtain_wall(m: dict) -> bpy.types.Object:
    parts = []
    stone, dark = m["castle_stone"], m["castle_stone_dark"]
    hw, ht = MODULE / 2, WALL_T / 2
    body_h = STOREY_H - PLINTH_H - COPING_H - MERLON_H
    # plinth
    parts.append(box("plinth", (0, 0, PLINTH_H / 2), (MODULE + 0.1, WALL_T + 0.1, PLINTH_H), dark))
    # body
    parts.append(box(
        "body", (0, 0, PLINTH_H + body_h / 2), (MODULE, WALL_T, body_h), stone,
    ))
    # coping
    cz = PLINTH_H + body_h + COPING_H / 2
    parts.append(box("coping", (0, 0, cz), (MODULE + 0.08, WALL_T + 0.1, COPING_H), dark))
    # merlons
    mz = PLINTH_H + body_h + COPING_H + MERLON_H / 2
    for i, x in enumerate((-1.5, -0.5, 0.5, 1.5)):
        parts.append(box(f"merlon_{i}", (x, 0, mz), (0.45, WALL_T + 0.08, MERLON_H), dark))
    # arrow slits
    for i, x in enumerate((-1.0, 1.0)):
        parts.append(box(
            f"slit_{i}", (x, -ht + 0.01, PLINTH_H + body_h * 0.55),
            (0.08, 0.04, 0.55), dark,
        ))
    return join(parts, "CastleCurtainWall")


def build_curtain_entrance(m: dict) -> bpy.types.Object:
    parts = []
    stone, dark = m["castle_stone"], m["castle_stone_dark"]
    half_w, half_d = ENTRANCE_W / 2, ENTRANCE_D / 2
    oh = GATE_W / 2
    body_top = STOREY_H - MERLON_H - COPING_H
    # plinth L/R
    for side, x0, x1 in (("L", -half_w, -oh), ("R", oh, half_w)):
        cx = (x0 + x1) / 2
        parts.append(box(
            f"plinth_{side}", (cx, 0, PLINTH_H / 2),
            (x1 - x0, ENTRANCE_D + 0.1, PLINTH_H), dark,
        ))
        parts.append(box(
            f"pier_{side}", (cx, 0, (PLINTH_H + body_top) / 2),
            (x1 - x0, ENTRANCE_D, body_top - PLINTH_H), stone,
        ))
    # header above peak
    if body_top > GATE_PEAK_Z:
        parts.append(box(
            "header", (0, 0, (GATE_PEAK_Z + body_top) / 2),
            (ENTRANCE_W, ENTRANCE_D, body_top - GATE_PEAK_Z), stone,
        ))
    parts.append(arch_spandrel(
        True, -half_d, half_d, stone, "gate", oh, GATE_SPRING_Z, GATE_PEAK_Z, GATE_PEAK_Z + 0.02,
    ))
    parts.append(arch_spandrel(
        False, -half_d, half_d, stone, "gate", oh, GATE_SPRING_Z, GATE_PEAK_Z, GATE_PEAK_Z + 0.02,
    ))
    # coping + merlons
    cz = body_top + COPING_H / 2
    parts.append(box("coping", (0, 0, cz), (ENTRANCE_W + 0.1, ENTRANCE_D + 0.1, COPING_H), dark))
    mz = body_top + COPING_H + MERLON_H / 2
    for i, x in enumerate((-2.0, -1.0, 0.0, 1.0, 2.0)):
        parts.append(box(f"merlon_{i}", (x, 0, mz), (0.4, ENTRANCE_D + 0.08, MERLON_H), dark))
    return join(parts, "CastleCurtainEntrance")


def _build_one_gate_leaf(m: dict, side: str) -> bpy.types.Object:
    wood, iron = m["castle_wood"], m["castle_iron"]
    oh = GATE_W / 2 - DOOR_GAP
    hinge_x = -oh if side == "L" else oh
    inner_x = 0.0
    outer_x = hinge_x
    y0 = -DOOR_T / 2
    parts = []
    panel = door_panel_mesh(
        outer_x, inner_x, DOOR_GAP, GATE_SPRING_Z, GATE_PEAK_Z - 0.02,
        DOOR_T, wood, f"panel_{side}",
    )
    # move panel so front is near y=0
    panel.location.y = y0
    apply_all(panel)
    parts.append(panel)
    # bands
    for i, z in enumerate((0.45, 1.25, 2.05)):
        parts.append(box(
            f"band_{side}_{i}",
            ((outer_x + inner_x) / 2, DOOR_T * 0.55, z),
            (abs(outer_x - inner_x) - 0.1, 0.02, 0.07),
            iron,
        ))
    # hinges
    for i, z in enumerate((0.5, 1.3, 2.1)):
        parts.append(box(
            f"strap_{side}_{i}",
            (outer_x + (0.2 if side == "L" else -0.2), DOOR_T * 0.6, z),
            (0.40, 0.025, 0.09),
            iron,
        ))
        parts.append(cyl(
            f"knuckle_{side}_{i}",
            (outer_x + (0.02 if side == "L" else -0.02), DOOR_T * 0.5, z),
            0.03, 0.11, iron, segs=8,
        ))
    # handle
    hx = 0.25 if side == "L" else -0.25
    parts.append(box(f"plate_{side}", (hx, DOOR_T * 0.65, 1.2), (0.14, 0.02, 0.20), iron))
    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.08, minor_radius=0.015, major_segments=12, minor_segments=6,
        location=(hx, DOOR_T * 0.85, 1.12), rotation=(math.pi / 2, 0, 0),
    )
    ring = bpy.context.active_object
    apply_scale_rot(ring)
    assign(ring, iron)
    parts.append(ring)
    leaf = join(parts, f"CastleCurtainDoor_{side}")
    uv_smart(leaf, 0.4)
    set_origin(leaf, (outer_x, 0.0, 0.0))
    return leaf


def build_curtain_doors(m: dict) -> list[bpy.types.Object]:
    return [_build_one_gate_leaf(m, "L"), _build_one_gate_leaf(m, "R")]


def build_tower_pillar(m: dict) -> bpy.types.Object:
    stone, dark = m["castle_stone"], m["castle_stone_dark"]
    parts = []
    parts.append(cyl("plinth", (0, 0, PLINTH_H / 2), TOWER_R + 0.08, PLINTH_H, dark, 16))
    parts.append(cyl(
        "shaft", (0, 0, PLINTH_H + (TOWER_H - PLINTH_H) / 2),
        TOWER_R, TOWER_H - PLINTH_H, stone, 16,
    ))
    # capital ring
    parts.append(cyl(
        "capital", (0, 0, TOWER_H - 0.08), TOWER_R + 0.06, 0.16, dark, 16,
    ))
    return join(parts, "CastleTowerPillar")


def build_tower_cone(m: dict) -> bpy.types.Object:
    """Cone roof that seats on tower top — origin at base centre (pillar top)."""
    tiles, wood = m["castle_roof_tiles"], m["castle_wood"]
    parts = []
    # Cone sits with base at z=0 (place at pillar top)
    parts.append(cone(
        "cone", (0, 0, CONE_H / 2), TOWER_R + 0.12, 0.04, CONE_H, tiles, 18,
    ))
    parts.append(cyl("finial", (0, 0, CONE_H + 0.08), 0.05, 0.20, wood, 8))
    # wood ring under eaves
    parts.append(cyl("eave_ring", (0, 0, 0.04), TOWER_R + 0.14, 0.08, wood, 16))
    obj = join(parts, "CastleTowerCone")
    set_origin(obj, (0, 0, 0))
    return obj


def build_courtyard_floor(m: dict) -> bpy.types.Object:
    stone = m["castle_stone"]
    parts = [box("slab", (0, 0, -FLOOR_T / 2), (MODULE, MODULE, FLOOR_T), stone)]
    # inset border
    parts.append(box(
        "border", (0, 0, 0.01), (MODULE - 0.15, MODULE - 0.15, 0.03), m["castle_stone_dark"],
    ))
    return join(parts, "CastleCourtyardFloor")


def build_curtain_parapet(m: dict) -> bpy.types.Object:
    """Short crenellated rail for top of curtain walkway — place at z=STOREY_H."""
    stone, dark = m["castle_stone"], m["castle_stone_dark"]
    parts = []
    h = 1.15
    parts.append(box("rail", (0, 0, h / 2), (MODULE, 0.28, h * 0.55), stone))
    for i, x in enumerate((-1.4, -0.45, 0.45, 1.4)):
        parts.append(box(f"merlon_{i}", (x, 0, h * 0.75), (0.4, 0.32, h * 0.5), dark))
    return join(parts, "CastleCurtainParapet")


# ── Keep pieces ───────────────────────────────────────────────────────────

def build_keep_wall(m: dict) -> bpy.types.Object:
    """4 m keep exterior wall with two windows — one storey."""
    stone, dark, plaster, wood = (
        m["castle_stone"], m["castle_stone_dark"], m["castle_plaster"], m["castle_wood"],
    )
    parts = []
    hw, ht = MODULE / 2, WALL_T / 2
    parts.append(box("plinth", (0, 0, PLINTH_H / 2), (MODULE + 0.06, WALL_T + 0.06, PLINTH_H), dark))
    # wall with window openings as segments
    win_w, win_h, win_z0 = 1.0, 1.2, 1.3
    # full sides
    for i, (x0, x1) in enumerate([(-hw, -1.2), (-0.2, 0.2), (1.2, hw)]):
        if x1 - x0 < 0.05:
            continue
        parts.append(box(
            f"seg_{i}", ((x0 + x1) / 2, 0, (PLINTH_H + STOREY_H) / 2),
            (x1 - x0, WALL_T, STOREY_H - PLINTH_H), stone,
        ))
    # below/above windows
    for side, cx in (("L", -0.7), ("R", 0.7)):
        parts.append(box(
            f"below_{side}", (cx, 0, (PLINTH_H + win_z0) / 2),
            (win_w, WALL_T, win_z0 - PLINTH_H), stone,
        ))
        parts.append(box(
            f"above_{side}", (cx, 0, (win_z0 + win_h + STOREY_H) / 2),
            (win_w, WALL_T, STOREY_H - (win_z0 + win_h)), stone,
        ))
        # frame + glass substitute (plaster pane)
        parts.append(box(
            f"frame_{side}", (cx, ht * 0.3, win_z0 + win_h / 2),
            (win_w + 0.1, 0.08, win_h + 0.1), wood,
        ))
        parts.append(box(
            f"pane_{side}", (cx, ht * 0.5, win_z0 + win_h / 2),
            (win_w - 0.15, 0.03, win_h - 0.15), plaster,
        ))
    # top plate
    parts.append(box(
        "plate", (0, 0, STOREY_H - 0.08), (MODULE, WALL_T + 0.04, 0.14), dark,
    ))
    return join(parts, "CastleKeepWall")


def build_keep_door_wall(m: dict) -> bpy.types.Object:
    stone, dark = m["castle_stone"], m["castle_stone_dark"]
    parts = []
    hw = MODULE / 2
    oh = KEEP_DOOR_W / 2
    parts.append(box("plinth_L", ((-hw - oh) / 2, 0, PLINTH_H / 2), (hw - oh, WALL_T + 0.06, PLINTH_H), dark))
    parts.append(box("plinth_R", ((hw + oh) / 2, 0, PLINTH_H / 2), (hw - oh, WALL_T + 0.06, PLINTH_H), dark))
    body_top = STOREY_H
    for side, x0, x1 in (("L", -hw, -oh), ("R", oh, hw)):
        cx = (x0 + x1) / 2
        parts.append(box(
            f"pier_{side}", (cx, 0, (PLINTH_H + body_top) / 2),
            (x1 - x0, WALL_T, body_top - PLINTH_H), stone,
        ))
    if body_top > KEEP_DOOR_PEAK:
        parts.append(box(
            "header", (0, 0, (KEEP_DOOR_PEAK + body_top) / 2),
            (MODULE, WALL_T, body_top - KEEP_DOOR_PEAK), stone,
        ))
    ht = WALL_T / 2
    parts.append(arch_spandrel(
        True, -ht, ht, stone, "keep", oh, KEEP_DOOR_SPRING, KEEP_DOOR_PEAK, KEEP_DOOR_PEAK + 0.02,
    ))
    parts.append(arch_spandrel(
        False, -ht, ht, stone, "keep", oh, KEEP_DOOR_SPRING, KEEP_DOOR_PEAK, KEEP_DOOR_PEAK + 0.02,
    ))
    return join(parts, "CastleKeepDoorWall")


def build_keep_door(m: dict) -> bpy.types.Object:
    """Double leaf keep door fitting keep doorway."""
    wood, iron = m["castle_wood"], m["castle_iron"]
    leaves = []
    for side in ("L", "R"):
        oh = KEEP_DOOR_W / 2 - DOOR_GAP
        outer_x = -oh if side == "L" else oh
        inner_x = 0.0
        parts = []
        panel = door_panel_mesh(
            outer_x, inner_x, DOOR_GAP, KEEP_DOOR_SPRING, KEEP_DOOR_PEAK - 0.02,
            DOOR_T, wood, f"keep_panel_{side}", segs=12,
        )
        panel.location.y = -DOOR_T / 2
        apply_all(panel)
        parts.append(panel)
        for i, z in enumerate((0.4, 1.1, 1.8)):
            parts.append(box(
                f"kb_{side}_{i}",
                ((outer_x + inner_x) / 2, DOOR_T * 0.55, z),
                (abs(outer_x) - 0.08, 0.02, 0.06),
                iron,
            ))
            parts.append(box(
                f"kh_{side}_{i}",
                (outer_x + (0.15 if side == "L" else -0.15), DOOR_T * 0.6, z),
                (0.30, 0.02, 0.08),
                iron,
            ))
        hx = 0.22 if side == "L" else -0.22
        parts.append(box(f"kp_{side}", (hx, DOOR_T * 0.65, 1.15), (0.12, 0.02, 0.18), iron))
        leaf = join(parts, f"CastleKeepDoor_{side}")
        uv_smart(leaf, 0.4)
        set_origin(leaf, (outer_x, 0.0, 0.0))
        leaves.append(leaf)
    return leaves


def build_keep_floor_l1(m: dict) -> bpy.types.Object:
    stone = m["castle_stone"]
    parts = [box("slab", (0, 0, -FLOOR_T / 2), (KEEP_SIZE, KEEP_SIZE, FLOOR_T), stone)]
    # light grid lines
    for x in (-2.0, 0.0, 2.0):
        parts.append(box(f"gx_{x}", (x, 0, 0.01), (0.04, KEEP_SIZE - 0.2, 0.02), m["castle_stone_dark"]))
        parts.append(box(f"gy_{x}", (0, x, 0.01), (KEEP_SIZE - 0.2, 0.04, 0.02), m["castle_stone_dark"]))
    return join(parts, "CastleKeepFloorL1")


def build_keep_floor_l2(m: dict) -> bpy.types.Object:
    """2nd floor with stair cutout near +Y edge."""
    stone, dark = m["castle_stone"], m["castle_stone_dark"]
    parts = []
    # Main slabs around cutout: cutout size STAIR_W x STAIR_RUN at (+0, +2-ish)
    cut_w, cut_d = STAIR_W + 0.15, STAIR_RUN * 0.55
    cut_cy = KEEP_SIZE / 2 - cut_d / 2 - 0.3
    # Build as 3 boxes: left, right, back of cutout
    half = KEEP_SIZE / 2
    # Full depth strips left/right of cutout
    cut_x0, cut_x1 = -cut_w / 2, cut_w / 2
    parts.append(box(
        "L", ((-half + cut_x0) / 2, 0, STOREY_H - FLOOR_T / 2),
        (half + cut_x0, KEEP_SIZE, FLOOR_T), stone,
    ))
    parts.append(box(
        "R", ((half + cut_x1) / 2, 0, STOREY_H - FLOOR_T / 2),
        (half - cut_x1, KEEP_SIZE, FLOOR_T), stone,
    ))
    # Front strip (toward -Y) full width between left/right already covered —
    # middle strip south of cutout
    south_y1 = cut_cy - cut_d / 2
    south_h = south_y1 - (-half)
    if south_h > 0.1:
        parts.append(box(
            "S", (0, (-half + south_y1) / 2, STOREY_H - FLOOR_T / 2),
            (cut_w, south_h, FLOOR_T), stone,
        ))
    # North strip (small)
    north_y0 = cut_cy + cut_d / 2
    north_h = half - north_y0
    if north_h > 0.05:
        parts.append(box(
            "N", (0, (north_y0 + half) / 2, STOREY_H - FLOOR_T / 2),
            (cut_w, north_h, FLOOR_T), stone,
        ))
    # Edge trim around cutout
    parts.append(box(
        "cut_trim", (0, cut_cy, STOREY_H + 0.02),
        (cut_w + 0.1, cut_d + 0.1, 0.04), dark,
    ))
    return join(parts, "CastleKeepFloorL2")


def build_keep_stairs(m: dict) -> bpy.types.Object:
    stone, wood = m["castle_stone"], m["castle_wood"]
    parts = []
    n_steps = 14
    rise = STOREY_H / n_steps
    run = STAIR_RUN / n_steps
    # Stairs climb in -Y direction from y=+start
    y_start = KEEP_SIZE / 2 - 0.4
    for i in range(n_steps):
        z = rise * (i + 0.5)
        y = y_start - run * (i + 0.5)
        parts.append(box(
            f"step_{i}", (0, y, z), (STAIR_W, run * 0.95, rise * 0.9), stone,
        ))
    # Side stringers
    for sx in (-STAIR_W / 2 - 0.06, STAIR_W / 2 + 0.06):
        parts.append(box(
            f"string_{sx}",
            (sx, y_start - STAIR_RUN / 2, STOREY_H / 2),
            (0.10, STAIR_RUN, STOREY_H),
            wood,
        ))
    # Simple rail
    parts.append(box(
        "rail", (STAIR_W / 2 + 0.06, y_start - STAIR_RUN / 2, STOREY_H * 0.55),
        (0.06, STAIR_RUN, 0.08), wood,
    ))
    return join(parts, "CastleKeepStairs")


def build_keep_roof(m: dict) -> bpy.types.Object:
    """Hip/gable tiled roof for 8×8 keep — origin at keep centre, base at z=0
    (place at z = 2*STOREY_H)."""
    tiles, wood, stone = m["castle_roof_tiles"], m["castle_wood"], m["castle_stone"]
    parts = []
    eaves = KEEP_SIZE + 0.8
    ridge_h = 2.4
    # Two main slopes along Y
    for name, y_sign in (("F", 1), ("B", -1)):
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        obj = bpy.context.active_object
        obj.name = f"slope_{name}"
        length = math.hypot(eaves / 2, ridge_h)
        ang = math.atan2(ridge_h, eaves / 2)
        obj.scale = (eaves, length, 0.14)
        obj.location = (0, y_sign * eaves / 4, ridge_h / 2)
        obj.rotation_euler = (y_sign * ang, 0, 0)
        apply_all(obj)
        assign(obj, tiles)
        parts.append(obj)
    parts.append(box("ridge", (0, 0, ridge_h - 0.05), (eaves + 0.1, 0.18, 0.14), wood))
    # gable fills
    for sx in (-1, 1):
        for i in range(5):
            t = (i + 0.5) / 5
            z = ridge_h * (1 - t)
            d = eaves * t
            parts.append(box(
                f"gable_{sx}_{i}", (sx * (KEEP_SIZE / 2 - WALL_T / 2), 0, z / 2 + 0.05),
                (WALL_T * 0.9, d, max(z, 0.1)), stone,
            ))
    return join(parts, "CastleKeepRoof")


def build_keep_assembled(m: dict) -> bpy.types.Object:
    """Preview: keep walls + floors + stairs + roof at correct offsets."""
    parts = []
    # Floors
    f1 = build_keep_floor_l1(m)
    parts.append(f1)
    f2 = build_keep_floor_l2(m)
    parts.append(f2)
    stairs = build_keep_stairs(m)
    parts.append(stairs)
    # Four walls around perimeter (centre of each edge)
    half = KEEP_SIZE / 2 - WALL_T / 2
    for i, (yaw, x, y) in enumerate([
        (0, 0, half),
        (math.pi, 0, -half),
        (math.pi / 2, half, 0),
        (-math.pi / 2, -half, 0),
    ]):
        # two storeys
        for storey in (0, 1):
            if i == 0 and storey == 0:
                w = build_keep_door_wall(m)
            else:
                w = build_keep_wall(m)
            w.location = (x, y, storey * STOREY_H)
            w.rotation_euler = (0, 0, yaw)
            apply_all(w)
            w.name = f"wall_{i}_{storey}"
            parts.append(w)
    # Keep doors closed at door wall
    for leaf in build_keep_door(m):
        leaf.location = (leaf.location.x, half, 0)
        # don't bake location — keep hinge; manually offset by moving data
        # Apply only rot/scale; then translate mesh
        bpy.ops.object.select_all(action="DESELECT")
        leaf.select_set(True)
        bpy.context.view_layer.objects.active = leaf
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        # shift verts by (0, half, 0) and reset origin offset
        for v in leaf.data.vertices:
            v.co.y += half
        set_origin(leaf, (leaf.location.x, half, 0))
        # Actually location still has hinge x — set location for export
        parts.append(leaf)
    roof = build_keep_roof(m)
    for v in roof.data.vertices:
        v.co.z += 2 * STOREY_H
    parts.append(roof)
    # Join everything except hinged doors for a single preview mesh…
    # Keep doors as separate objects in multi export instead.
    solid = [p for p in parts if not p.name.startswith("CastleKeepDoor")]
    doors = [p for p in parts if p.name.startswith("CastleKeepDoor")]
    body = join(solid, "CastleKeepAssembled_body")
    return [body] + doors


# ── Export orchestration ──────────────────────────────────────────────────

PIECES = [
    "curtain_wall", "curtain_entrance", "curtain_doors",
    "tower_pillar", "tower_cone", "courtyard_floor", "curtain_parapet",
    "keep_wall", "keep_door_wall", "keep_door",
    "keep_floor_l1", "keep_floor_l2", "keep_stairs", "keep_roof",
    "keep_assembled",
]


def _filter_arg() -> str | None:
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            return sys.argv[idx + 1].lower()
    return None


def want(name: str, filt: str | None) -> bool:
    if not filt:
        return True
    if filt == "curtain":
        return (
            name.startswith("curtain")
            or name.startswith("tower")
            or name.startswith("courtyard")
        )
    if filt == "keep":
        return name.startswith("keep")
    return filt in name


def main():
    filt = _filter_arg()
    print("\n=== Castle Keep Kit (textured curtain + keep) ===")
    if filt:
        print(f"  filter: {filt}")

    results = []

    def run_piece(key, filename, builder, multi=False):
        if not want(key, filt):
            return
        clear_scene()
        m = mats()
        print(f"\n-- {filename} --")
        if multi:
            objs = builder(m)
            for o in objs:
                if o.name.endswith("_body") or "Wall" in o.name or "Floor" in o.name or "Stairs" in o.name or "Roof" in o.name or "Entrance" in o.name or "Parapet" in o.name or "Pillar" in o.name or "Cone" in o.name or "Courtyard" in o.name:
                    uv_smart(o)
                report(o if hasattr(o, "data") else objs[0], o.name)
            dual(filename, lambda p: export_multi(objs, p, apply=False))
            results.append(filename)
        else:
            obj = builder(m)
            uv_smart(obj)
            report(obj, key)
            dual(filename, lambda p: export_single(obj, p))
            results.append(filename)

    run_piece("curtain_wall", "CastleCurtainWall.glb", build_curtain_wall)
    run_piece("curtain_entrance", "CastleCurtainEntrance.glb", build_curtain_entrance)
    run_piece("curtain_doors", "CastleCurtainDoubleDoor.glb", build_curtain_doors, multi=True)
    run_piece("tower_pillar", "CastleTowerPillar.glb", build_tower_pillar)
    run_piece("tower_cone", "CastleTowerCone.glb", build_tower_cone)
    run_piece("courtyard_floor", "CastleCourtyardFloor.glb", build_courtyard_floor)
    run_piece("curtain_parapet", "CastleCurtainParapet.glb", build_curtain_parapet)

    run_piece("keep_wall", "CastleKeepWall.glb", build_keep_wall)
    run_piece("keep_door_wall", "CastleKeepDoorWall.glb", build_keep_door_wall)
    run_piece("keep_door", "CastleKeepDoor.glb", build_keep_door, multi=True)
    run_piece("keep_floor_l1", "CastleKeepFloorL1.glb", build_keep_floor_l1)
    run_piece("keep_floor_l2", "CastleKeepFloorL2.glb", build_keep_floor_l2)
    run_piece("keep_stairs", "CastleKeepStairs.glb", build_keep_stairs)
    run_piece("keep_roof", "CastleKeepRoof.glb", build_keep_roof)
    run_piece("keep_assembled", "CastleKeepAssembled.glb", build_keep_assembled, multi=True)

    print("\nDONE — exported:")
    for r in results:
        print(f"  {r}")


if __name__ == "__main__":
    main()
