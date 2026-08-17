"""
generate_rugs.py
================
Build five game-optimized, UNTEXTURED rug GLBs — each a different
silhouette so interiors can mix shapes without looking cloned.

Same clean-handoff contract as oak leaf / bridge / castle pieces:

  - Origin at world (0, 0, 0), rug rests on the ground plane (z = 0).
  - Single joined mesh per rug, transforms baked into vertex data.
  - Two named material slots: `rug_top` (walkable face) and
    `rug_underside` (bottom + thin side strip) so a texture artist
    can paint pile vs backing separately later.

Six shapes (exported as separate GLBs, registered as stages of one
sidebar entry):

  1. RugRectangle.glb  — classic rectangular area rug
  2. RugSquare.glb     — square area rug
  3. RugCircle.glb     — round rug
  4. RugOval.glb       — elongated ellipse
  5. RugRunner.glb     — long narrow hallway runner
  6. RugHexagon.glb    — regular hexagon

Coordinate convention
---------------------
  +X = rug width
  +Y = rug length (longest axis)
  +Z = up
  Bottom face at z = 0, top face at z = RUG_THICKNESS.
  Origin at the footprint centre so the rug drops in centred on a
  floor tile.

Outputs:
  ~/Desktop/Models/Buildings/RugRectangle.glb
  ~/Desktop/Models/Buildings/RugSquare.glb
  ~/Desktop/Models/Buildings/RugCircle.glb
  ~/Desktop/Models/Buildings/RugOval.glb
  ~/Desktop/Models/Buildings/RugRunner.glb
  ~/Desktop/Models/Buildings/RugHexagon.glb
  viewer/public/buildings/<same>

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_rugs.py
"""

from __future__ import annotations

import math
import os

import bpy
import bmesh
from mathutils import Vector


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

RUG_THICKNESS = 0.015   # 1.5 cm pile — reads as a rug edge-on without
                        # floating above the floor at typical zoom

# Per-shape top colours so the five are easy to tell apart in the
# untextured viewer; all share the same material *names* so a later
# texture pass can swap them uniformly.
RUG_DEFS: list[dict] = [
    {
        "id": "rectangle",
        "out_name": "RugRectangle.glb",
        "mesh_name": "rug_rectangle",
        "top_color": (0.55, 0.18, 0.16),   # deep red
        "outline": "rectangle",
        # 2.0 m wide × 1.4 m deep — classic living-room area rug
        "params": {"half_x": 1.00, "half_y": 0.70},
    },
    {
        "id": "square",
        "out_name": "RugSquare.glb",
        "mesh_name": "rug_square",
        "top_color": (0.55, 0.42, 0.18),   # ochre / mustard
        "outline": "rectangle",
        # 1.6 × 1.6 m square area rug
        "params": {"half_x": 0.80, "half_y": 0.80},
    },
    {
        "id": "circle",
        "out_name": "RugCircle.glb",
        "mesh_name": "rug_circle",
        "top_color": (0.22, 0.32, 0.55),   # slate blue
        "outline": "ellipse",
        # Diameter 1.6 m
        "params": {"rx": 0.80, "ry": 0.80, "segments": 24},
    },
    {
        "id": "oval",
        "out_name": "RugOval.glb",
        "mesh_name": "rug_oval",
        "top_color": (0.20, 0.42, 0.28),   # forest green
        "outline": "ellipse",
        # 2.2 × 1.2 m elongated oval
        "params": {"rx": 1.10, "ry": 0.60, "segments": 28},
    },
    {
        "id": "runner",
        "out_name": "RugRunner.glb",
        "mesh_name": "rug_runner",
        "top_color": (0.50, 0.36, 0.18),   # warm amber
        "outline": "rectangle",
        # 3.0 m long × 0.65 m wide hallway runner
        "params": {"half_x": 0.325, "half_y": 1.50},
    },
    {
        "id": "hexagon",
        "out_name": "RugHexagon.glb",
        "mesh_name": "rug_hexagon",
        "top_color": (0.40, 0.22, 0.45),   # muted purple
        "outline": "regular_polygon",
        # Flat-to-flat width ≈ 1.7 m (apothem = 0.85)
        "params": {"apothem": 0.85, "sides": 6},
    },
]

UNDERSIDE_COLOR = (0.35, 0.30, 0.24)   # drab jute / backing


# ── Materials ─────────────────────────────────────────────────────────────

def make_material(name: str, color: tuple[float, float, float]) -> bpy.types.Material:
    """Lookup-or-create.  Colour is reapplied each call so regenerating
    with a different palette picks up the change."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = (*color, 1.0)
        if "Specular IOR Level" in principled.inputs:
            principled.inputs["Specular IOR Level"].default_value = 0.15
        elif "Specular" in principled.inputs:
            principled.inputs["Specular"].default_value = 0.15
        principled.inputs["Roughness"].default_value = 0.90
    return mat


# ── Outline builders ──────────────────────────────────────────────────────

def outline_rectangle(half_x: float, half_y: float) -> list[tuple[float, float]]:
    """CCW from +Z: SW → SE → NE → NW."""
    return [
        (-half_x, -half_y),
        (+half_x, -half_y),
        (+half_x, +half_y),
        (-half_x, +half_y),
    ]


def outline_ellipse(
    rx: float,
    ry: float,
    segments: int = 24,
) -> list[tuple[float, float]]:
    """CCW ellipse centred on origin."""
    pts: list[tuple[float, float]] = []
    for i in range(segments):
        t = (2.0 * math.pi * i) / segments
        pts.append((rx * math.cos(t), ry * math.sin(t)))
    return pts


def outline_regular_polygon(
    apothem: float,
    sides: int = 6,
) -> list[tuple[float, float]]:
    """Regular N-gon with a flat side facing −Y (so a hexagon reads
    with a horizontal bottom edge).  `apothem` is centre → flat."""
    # Vertex radius from apothem: R = apothem / cos(π/n)
    r = apothem / math.cos(math.pi / sides)
    # Rotate so a flat sits at the bottom (−Y): first vertex offset by
    # π/n from the −Y axis… equivalently start angle = −π/2 − π/n.
    start = -math.pi / 2.0 - math.pi / sides
    pts: list[tuple[float, float]] = []
    for i in range(sides):
        t = start + (2.0 * math.pi * i) / sides
        pts.append((r * math.cos(t), r * math.sin(t)))
    return pts


def build_outline(kind: str, params: dict) -> list[tuple[float, float]]:
    if kind == "rectangle":
        return outline_rectangle(**params)
    if kind == "ellipse":
        return outline_ellipse(**params)
    if kind == "regular_polygon":
        return outline_regular_polygon(**params)
    raise ValueError(f"unknown outline kind: {kind}")


# ── Mesh builder ──────────────────────────────────────────────────────────

def build_rug(
    outline: list[tuple[float, float]],
    mesh_name: str,
    top_color: tuple[float, float, float],
) -> bpy.types.Object:
    """Extruded outline with distinct top vs underside materials.

    Winding (outline CCW from +Z):
      - Top face:    top_verts in outline order        → normal +Z
      - Bottom face: bot_verts REVERSED               → normal −Z
      - Side quads:  [bot[i], bot[j], top[j], top[i]] → outward
    """
    n = len(outline)
    mesh = bpy.data.meshes.new(f"{mesh_name}_mesh")
    obj = bpy.data.objects.new(mesh_name, mesh)
    bpy.context.collection.objects.link(obj)

    # Slot 0 = underside, slot 1 = top (matches oak-leaf convention).
    # Material names are shared across all rugs; colour is per-shape
    # via unique material datablock names so Blender doesn't collapse
    # them.  On export the *slot names* the artist cares about are
    # still `rug_underside` / `rug_top` — we name the materials that
    # way and accept that regenerating one rug after another will
    # overwrite the shared colour.  To keep colours distinct in a
    # multi-export session we suffix the datablock name with the
    # mesh id, but expose the same base name via… actually GLB
    # exports the material *name*.  So if we want unique colours
    # AND shared logical names for texturing, we use the shared
    # names and accept last-write-wins for colour in Blender's
    # session — each GLB is exported alone so each file gets the
    # colour set for that shape.  Perfect.
    obj.data.materials.append(make_material("rug_underside", UNDERSIDE_COLOR))
    obj.data.materials.append(make_material("rug_top", top_color))
    MAT_UNDERSIDE = 0
    MAT_TOP = 1

    bm = bmesh.new()
    z_bot = 0.0
    z_top = RUG_THICKNESS

    bot_verts = [bm.verts.new(Vector((x, y, z_bot))) for (x, y) in outline]
    top_verts = [bm.verts.new(Vector((x, y, z_top))) for (x, y) in outline]

    f_top = bm.faces.new(top_verts)
    f_top.material_index = MAT_TOP

    f_bot = bm.faces.new(list(reversed(bot_verts)))
    f_bot.material_index = MAT_UNDERSIDE

    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new([bot_verts[i], bot_verts[j], top_verts[j], top_verts[i]])
        f.material_index = MAT_UNDERSIDE

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    return obj


# ── Scene / export helpers ────────────────────────────────────────────────

def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials):
        for datablock in list(block):
            block.remove(datablock)


def normalize_transform(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")


def export_glb(obj: bpy.types.Object, out_path: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        use_selection=True,
        export_format="GLB",
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
    )


def mesh_stats(obj: bpy.types.Object) -> tuple[int, int, int, list[str]]:
    mesh = obj.data
    tris = sum(len(p.vertices) - 2 for p in mesh.polygons)
    mats = [slot.material.name for slot in obj.material_slots if slot.material]
    return len(mesh.vertices), len(mesh.polygons), tris, mats


def bounds_str(obj: bpy.types.Object) -> str:
    xs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    if not xs:
        return "(empty)"
    return (
        f"X[{min(v.x for v in xs):+.3f}, {max(v.x for v in xs):+.3f}]  "
        f"Y[{min(v.y for v in xs):+.3f}, {max(v.y for v in xs):+.3f}]  "
        f"Z[{min(v.z for v in xs):+.3f}, {max(v.z for v in xs):+.3f}]"
    )


# ── Main ──────────────────────────────────────────────────────────────────

def build_and_export(defn: dict) -> dict:
    clear_scene()
    outline = build_outline(defn["outline"], defn["params"])
    obj = build_rug(outline, defn["mesh_name"], defn["top_color"])
    normalize_transform(obj)

    verts, faces, tris, mats = mesh_stats(obj)
    print(
        f"  [{defn['id']}] verts={verts}, faces={faces}, tris={tris}, "
        f"materials={len(mats)}: {', '.join(mats)}"
    )
    print(f"  [{defn['id']}] bounds: {bounds_str(obj)}")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, defn["out_name"])
        export_glb(obj, path)
        size_kb = os.path.getsize(path) / 1024.0
        print(f"  -> {path} ({size_kb:.1f} KB)")

    return {
        "id": defn["id"],
        "out_name": defn["out_name"],
        "tris": tris,
        "verts": verts,
    }


def main() -> None:
    print(f"Source output dir: {SOURCE_DIR}")
    print(f"Viewer output dir: {VIEWER_DIR}")
    print(f"Rug thickness: {RUG_THICKNESS * 100:.1f} cm\n")

    results = []
    for defn in RUG_DEFS:
        print(f"=== Rug {defn['id'].title()} ===")
        results.append(build_and_export(defn))
        print()

    print(f"DONE — {len(results)} rugs exported.")
    for r in results:
        print(f"  {r['out_name']}: {r['tris']} tris / {r['verts']} verts")


if __name__ == "__main__":
    main()
