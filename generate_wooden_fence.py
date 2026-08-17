"""
generate_wooden_fence.py
========================
Build a game-optimized, UNTEXTURED wooden fence kit from Blender
primitives.  Same clean-handoff contract as the castle wall / bridge
generators:

  - Origin at world (0, 0, 0), ground plane at z = 0.
  - Single joined mesh per piece (except the gate, which keeps its
    hinge origin as object TRS — see below).
  - Baked TRS on static pieces so bounding-box maths stay honest.
  - Named material slots for a later texture pass.

Four pieces, each exported as its own GLB, designed to snap together:

  1. FenceSection   — 3.0 m modular span with TWO horizontal round
                      wooden rails.  No posts (posts are separate).
  2. FenceGate      — matching 3.0 m hinged gate (frame + 2 round
                      rails + diagonal brace + iron hinges).  Object
                      origin sits on the hinge line so a game engine
                      rotates around local +Z to swing it open.
  3. FenceEndPost   — square grey concrete / brick anchor post for
                      the end of a straight run.
  4. FenceCornerPost — square grey concrete / brick anchor post for
                      a 90° corner (slightly larger, with a distinct
                      cap so it reads as the corner piece).

Modular fit
-----------
  SECTION_SPAN = 3.0 m  — distance between post centres along a run.
  Place posts at x = 0 and x = 3, then place a FenceSection (or
  FenceGate) with its origin at x = 1.5 so the rails / gate leaf
  fill the clear gap between the posts.

  Corner posts sit at a bend: rails approach from −X and from −Y
  (or any two perpendicular directions).  The corner piece itself
  is rotationally symmetric so orientation is free.

Coordinate convention
---------------------
  +X = along the fence run
  +Y = through the fence (thin axis)
  +Z = up
  Fence section / gate centred on the span (origin at mid-span for
  the section; gate origin moved to the left hinge after build).
  Posts centred on their footprint.

Outputs:
  ~/Desktop/Models/Buildings/FenceSection.glb
  ~/Desktop/Models/Buildings/FenceGate.glb
  ~/Desktop/Models/Buildings/FenceEndPost.glb
  ~/Desktop/Models/Buildings/FenceCornerPost.glb
  viewer/public/buildings/<same>

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_wooden_fence.py
"""

from __future__ import annotations

import math
import os

import bpy


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)


# ── Shared modular dimensions ─────────────────────────────────────────────

SECTION_SPAN = 3.00             # post-centre → post-centre along +X

# End post (straight-run anchor)
END_POST_SIDE = 0.32
END_POST_HEIGHT = 1.25
END_POST_PLINTH = 0.06          # slightly wider base pad
END_POST_CAP = 0.05             # flat cap height

# Corner post — a touch larger so corners read as structural anchors
CORNER_POST_SIDE = 0.38
CORNER_POST_HEIGHT = 1.35
CORNER_POST_PLINTH = 0.07
CORNER_POST_CAP = 0.07

# Round rails (2 per section / gate)
RAIL_RADIUS = 0.045
RAIL_SEGMENTS = 10              # low-poly cylinder
RAIL_Z_LOW = 0.40
RAIL_Z_HIGH = 0.95
# Clearance: rails stop short of the post faces so they don't clip
# into the concrete when posts sit at ±SECTION_SPAN/2.
RAIL_END_GAP = 0.02

# Gate frame (square stock) + brace + hinges
GATE_FRAME_SIZE = 0.07          # square upright / top-rail stock
GATE_THICKNESS = 0.08           # Y-depth of the leaf
GATE_BRACE_SIZE = 0.055
HINGE_COUNT = 3
HINGE_KNUCKLE_R = 0.018
HINGE_KNUCKLE_H = 0.05
HINGE_STRAP_LEN = 0.18
HINGE_STRAP_W = 0.04
HINGE_STRAP_T = 0.012


# ── Materials ─────────────────────────────────────────────────────────────

MATERIAL_COLORS = {
    "fence_wood_rail":      (0.48, 0.34, 0.18),   # warm oak round rails
    "fence_wood_frame":     (0.42, 0.29, 0.15),   # slightly darker frame
    "fence_concrete":       (0.52, 0.52, 0.54),   # grey brick / concrete
    "fence_concrete_trim":  (0.42, 0.42, 0.45),   # darker cap / plinth
    "fence_iron":           (0.18, 0.17, 0.16),   # hinge hardware
}


def make_material(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        color = MATERIAL_COLORS.get(name, (0.5, 0.5, 0.5))
        principled.inputs["Base Color"].default_value = (*color, 1.0)
        if "wood" in name:
            principled.inputs["Roughness"].default_value = 0.75
        elif "iron" in name:
            principled.inputs["Roughness"].default_value = 0.55
            if "Metallic" in principled.inputs:
                principled.inputs["Metallic"].default_value = 0.6
        else:
            principled.inputs["Roughness"].default_value = 0.90
    return mat


# ── Scene / primitive helpers ─────────────────────────────────────────────

def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def add_box(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    material_name: str,
    obj_name: str,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = obj_name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(make_material(material_name))
    return obj


def add_cylinder(
    center: tuple[float, float, float],
    radius: float,
    height: float,
    material_name: str,
    obj_name: str,
    axis: str = "X",
    segments: int = RAIL_SEGMENTS,
) -> bpy.types.Object:
    """Low-poly cylinder.  Default axis=X so rails run along the fence."""
    if axis == "X":
        rotation = (0.0, math.pi / 2.0, 0.0)
    elif axis == "Y":
        rotation = (math.pi / 2.0, 0.0, 0.0)
    elif axis == "Z":
        rotation = (0.0, 0.0, 0.0)
    else:
        raise ValueError(f"axis must be X/Y/Z, got {axis}")
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=segments,
        radius=radius,
        depth=height,
        location=center,
        rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = obj_name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(make_material(material_name))
    return obj


def join_group(objects: list[bpy.types.Object], name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = name
    return joined


def normalize_transform(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")


def set_origin_to_point(
    obj: bpy.types.Object,
    world_point: tuple[float, float, float],
) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.scene.cursor.location = world_point
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")


def export_glb_single(obj: bpy.types.Object, out_path: str) -> None:
    normalize_transform(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
    )


def export_glb_preserve_transforms(obj: bpy.types.Object, out_path: str) -> None:
    """Keep object TRS (hinge origin) in the glTF node."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_materials="EXPORT",
    )


def report_mesh(obj: bpy.types.Object, label: str) -> None:
    n_verts = len(obj.data.vertices)
    n_faces = len(obj.data.polygons)
    n_tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    mats = [m.name if m else "<none>" for m in obj.data.materials]
    mw = obj.matrix_world
    verts = [mw @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
    print(
        f"  [{label}] verts={n_verts}, faces={n_faces}, tris={n_tris}, "
        f"materials={len(mats)}: {', '.join(mats)}"
    )
    print(
        f"  [{label}] bounds: X[{min(xs):+.3f}, {max(xs):+.3f}]  "
        f"Y[{min(ys):+.3f}, {max(ys):+.3f}]  "
        f"Z[{min(zs):+.3f}, {max(zs):+.3f}]"
    )


# ── Shared geometry ───────────────────────────────────────────────────────

def rail_clear_length(post_side: float = END_POST_SIDE) -> float:
    """Length of a rail that sits in the clear gap between two posts
    whose centres are SECTION_SPAN apart."""
    return SECTION_SPAN - post_side - 2.0 * RAIL_END_GAP


def add_two_rails(
    created: list,
    length: float,
    center_x: float = 0.0,
    center_y: float = 0.0,
    prefix: str = "rail",
) -> None:
    for i, z in enumerate((RAIL_Z_LOW, RAIL_Z_HIGH)):
        created.append(add_cylinder(
            center=(center_x, center_y, z),
            radius=RAIL_RADIUS,
            height=length,
            material_name="fence_wood_rail",
            obj_name=f"{prefix}_{i}",
            axis="X",
        ))


def build_concrete_post(
    side: float,
    height: float,
    plinth_overhang: float,
    cap_height: float,
    prefix: str,
) -> list[bpy.types.Object]:
    """Square concrete post: wider plinth pad → body → slightly
    overhanging flat cap.  Origin will sit at footprint centre."""
    created: list[bpy.types.Object] = []
    plinth_side = side + 2.0 * plinth_overhang
    plinth_h = 0.08
    body_h = height - plinth_h - cap_height
    cap_side = side + 2.0 * 0.02

    created.append(add_box(
        center=(0.0, 0.0, plinth_h / 2.0),
        size=(plinth_side, plinth_side, plinth_h),
        material_name="fence_concrete_trim",
        obj_name=f"{prefix}_plinth",
    ))
    created.append(add_box(
        center=(0.0, 0.0, plinth_h + body_h / 2.0),
        size=(side, side, body_h),
        material_name="fence_concrete",
        obj_name=f"{prefix}_body",
    ))
    created.append(add_box(
        center=(0.0, 0.0, plinth_h + body_h + cap_height / 2.0),
        size=(cap_side, cap_side, cap_height),
        material_name="fence_concrete_trim",
        obj_name=f"{prefix}_cap",
    ))
    return created


# ── Piece 1: Fence Section ────────────────────────────────────────────────

def build_fence_section() -> list[bpy.types.Object]:
    """Two round rails spanning the clear gap of a 3 m modular bay.
    Origin at mid-span; place at the midpoint between two posts."""
    created: list[bpy.types.Object] = []
    length = rail_clear_length(END_POST_SIDE)
    add_two_rails(created, length=length, prefix="section_rail")
    return created


# ── Piece 2: Gate ─────────────────────────────────────────────────────────

def build_fence_gate() -> list[bpy.types.Object]:
    """Hinged gate leaf matching the fence: left/right uprights, top
    and bottom square rails, two round rails at the same heights as
    the fence section, a diagonal brace, and three iron strap hinges
    on the left upright.

    Built centred on the span first; export step moves the origin to
    the left hinge line."""
    created: list[bpy.types.Object] = []

    # Gate leaf fills the same clear gap as the fence rails.
    clear = rail_clear_length(END_POST_SIDE)
    half = clear / 2.0
    # Leaf sits slightly forward (+Y) of the rail centre-line so it
    # can swing past the rails of adjacent sections without z-fighting
    # when closed in a mixed run — but for a pure gate bay it's just
    # the leaf.  Keep it on y=0 for a clean closed pose.
    y = 0.0

    # Vertical uprights at left / right edges of the leaf.
    upright_h = RAIL_Z_HIGH + RAIL_RADIUS + 0.12
    left_x = -half + GATE_FRAME_SIZE / 2.0
    right_x = +half - GATE_FRAME_SIZE / 2.0

    created.append(add_box(
        center=(left_x, y, upright_h / 2.0),
        size=(GATE_FRAME_SIZE, GATE_THICKNESS, upright_h),
        material_name="fence_wood_frame",
        obj_name="gate_upright_left",
    ))
    created.append(add_box(
        center=(right_x, y, upright_h / 2.0),
        size=(GATE_FRAME_SIZE, GATE_THICKNESS, upright_h),
        material_name="fence_wood_frame",
        obj_name="gate_upright_right",
    ))

    # Top + bottom square frame rails spanning between uprights.
    span_inner = clear - 2.0 * GATE_FRAME_SIZE
    for i, z in enumerate((GATE_FRAME_SIZE / 2.0 + 0.02, upright_h - GATE_FRAME_SIZE / 2.0)):
        created.append(add_box(
            center=(0.0, y, z),
            size=(span_inner, GATE_THICKNESS, GATE_FRAME_SIZE),
            material_name="fence_wood_frame",
            obj_name=f"gate_frame_rail_{i}",
        ))

    # Two round rails — same heights / radius as the fence section,
    # shortened to sit between the uprights.
    round_len = span_inner - 0.04
    add_two_rails(
        created,
        length=round_len,
        center_x=0.0,
        center_y=y,
        prefix="gate_rail",
    )

    # Diagonal brace (bottom-left → top-right) for a classic gate look.
    # Box stretched along +X then pitched/yawed to the brace chord.
    brace_z0 = GATE_FRAME_SIZE + 0.05
    brace_z1 = upright_h - GATE_FRAME_SIZE - 0.05
    brace_x0 = left_x + GATE_FRAME_SIZE / 2.0
    brace_x1 = right_x - GATE_FRAME_SIZE / 2.0
    dx = brace_x1 - brace_x0
    dz = brace_z1 - brace_z0
    brace_len = math.sqrt(dx * dx + dz * dz)
    mid = ((brace_x0 + brace_x1) / 2.0, y, (brace_z0 + brace_z1) / 2.0)
    pitch = math.atan2(dz, dx)  # rotate around Y so +X follows the brace
    created.append(add_box(
        center=mid,
        size=(brace_len, GATE_BRACE_SIZE, GATE_BRACE_SIZE),
        material_name="fence_wood_frame",
        obj_name="gate_brace",
        rotation=(0.0, -pitch, 0.0),
    ))

    # Three iron strap hinges on the LEFT upright (hinge side).
    # Knuckle sits on the outer (−X) face; strap reaches onto the leaf.
    hinge_x_knuckle = left_x - GATE_FRAME_SIZE / 2.0 - HINGE_KNUCKLE_R * 0.6
    hinge_zs = [upright_h * t for t in (0.18, 0.50, 0.82)]
    for i, hz in enumerate(hinge_zs):
        created.append(add_cylinder(
            center=(hinge_x_knuckle, y, hz),
            radius=HINGE_KNUCKLE_R,
            height=HINGE_KNUCKLE_H,
            material_name="fence_iron",
            obj_name=f"gate_hinge_knuckle_{i}",
            axis="Z",
            segments=8,
        ))
        strap_cx = left_x + HINGE_STRAP_LEN / 2.0 - GATE_FRAME_SIZE / 4.0
        created.append(add_box(
            center=(strap_cx, y + GATE_THICKNESS / 2.0 + HINGE_STRAP_T / 2.0, hz),
            size=(HINGE_STRAP_LEN, HINGE_STRAP_T, HINGE_STRAP_W),
            material_name="fence_iron",
            obj_name=f"gate_hinge_strap_{i}",
        ))

    return created


# ── Pieces 3 & 4: Posts ───────────────────────────────────────────────────

def build_end_post() -> list[bpy.types.Object]:
    return build_concrete_post(
        side=END_POST_SIDE,
        height=END_POST_HEIGHT,
        plinth_overhang=END_POST_PLINTH,
        cap_height=END_POST_CAP,
        prefix="end_post",
    )


def build_corner_post() -> list[bpy.types.Object]:
    """Larger concrete anchor with a chunkier cap.  Same footprint
    centre convention as the end post so a corner replaces an end
    post without shifting the modular grid."""
    created = build_concrete_post(
        side=CORNER_POST_SIDE,
        height=CORNER_POST_HEIGHT,
        plinth_overhang=CORNER_POST_PLINTH,
        cap_height=CORNER_POST_CAP,
        prefix="corner_post",
    )
    # Small pyramidal-ish top nub (just a smaller box) so the corner
    # reads differently from the end post at a glance.
    nub_side = CORNER_POST_SIDE * 0.45
    nub_h = 0.06
    created.append(add_box(
        center=(0.0, 0.0, CORNER_POST_HEIGHT + nub_h / 2.0),
        size=(nub_side, nub_side, nub_h),
        material_name="fence_concrete_trim",
        obj_name="corner_post_nub",
    ))
    return created


# ── Build + export ────────────────────────────────────────────────────────

def _export_static(created: list, name: str, filename: str) -> None:
    print(f"\n=== {name} ===")
    print(f"  built pieces: {len(created)}")
    joined = join_group(created, name)
    report_mesh(joined, name)
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, filename)
        export_glb_single(joined, path)
        print(f"  -> {path} ({os.path.getsize(path) / 1024.0:.1f} KB)")


def build_and_export_section() -> None:
    clear_scene()
    _export_static(build_fence_section(), "fence_section", "FenceSection.glb")


def build_and_export_gate() -> None:
    print("\n=== Fence Gate ===")
    clear_scene()
    created = build_fence_gate()
    print(f"  built pieces: {len(created)}")
    gate = join_group(created, "fence_gate")

    # Hinge line: outer face of the left upright, at leaf mid-thickness.
    clear = rail_clear_length(END_POST_SIDE)
    half = clear / 2.0
    hinge_x = -half
    hinge_y = 0.0
    # Bake mesh scales/rotations first (but NOT location — we need
    # world verts stable), then move origin to the hinge.
    bpy.ops.object.select_all(action="DESELECT")
    gate.select_set(True)
    bpy.context.view_layer.objects.active = gate
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    set_origin_to_point(gate, world_point=(hinge_x, hinge_y, 0.0))
    report_mesh(gate, "fence_gate")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, "FenceGate.glb")
        export_glb_preserve_transforms(gate, path)
        print(
            f"  -> {path} ({os.path.getsize(path) / 1024.0:.1f} KB)  "
            f"(hinge origin at x={hinge_x:+.3f})"
        )


def build_and_export_end_post() -> None:
    clear_scene()
    _export_static(build_end_post(), "fence_end_post", "FenceEndPost.glb")


def build_and_export_corner_post() -> None:
    clear_scene()
    _export_static(build_corner_post(), "fence_corner_post", "FenceCornerPost.glb")


def main() -> None:
    print(f"Source output dir: {SOURCE_DIR}")
    print(f"Viewer output dir: {VIEWER_DIR}")
    print(
        f"Modular span: {SECTION_SPAN:.2f} m centre-to-centre | "
        f"rails at z={RAIL_Z_LOW:.2f} / {RAIL_Z_HIGH:.2f} m | "
        f"rail clear length={rail_clear_length():.2f} m"
    )

    build_and_export_section()
    build_and_export_gate()
    build_and_export_end_post()
    build_and_export_corner_post()

    print("\nDONE — wooden fence set (4 pieces) exported.")


if __name__ == "__main__":
    main()
