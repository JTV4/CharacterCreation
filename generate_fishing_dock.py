"""
generate_fishing_dock.py
========================
Build a single, game-optimized, UNTEXTURED fishing dock GLB from Blender
primitives.  Follows the same "clean handoff" contract as every other
asset in this repo:

  - Origin at world (0, 0, 0)
  - Root scale = (1, 1, 1) with all transforms baked into vertex data
  - Single joined mesh, so the whole dock is one draw call in-engine
  - MULTIPLE named material slots on that mesh (planks / stringers /
    joists / pilings / ladder / cleats) so the user can slot a texture
    onto each part-type independently later without re-splitting geo.
  - Low, human-readable poly count (~380 verts / ~550 tris).  Cylinders
    use 8 sides on purpose — the silhouette still reads as "round post"
    at typical camera distances but the vert count stays trivial.

Coordinate convention
---------------------
  +X = right (perpendicular to dock length)
  +Y = OUT from shore (dock extends in +Y)
  +Z = up
  Origin is on the SHORE end of the dock, centred on X.
  This makes it trivial to drop into a scene: put the origin on the
  waterline where the dock meets land, rotate about Z to face the pier,
  done.  The pilings extend slightly below z=0 so they visually "sink"
  into whatever surface (water plane, terrain) the game engine places
  underneath.

Vertical stack (all heights are +Z)
-----------------------------------
   z  = -0.20  ── piling bottoms (sunk under ground/water)
   z  =  0.00  ── ground / waterline
   z  =  1.09  ── top of pilings meets underside of stringers
   z  =  1.19  ── top of stringers, underside of joists
   z  =  1.30  ── top of joists, underside of planks
   z  =  1.34  ── top of deck (walkable surface)
   z  =  1.42  ── top of cleats  (small "T" bollards on the deck edge)

Outputs (mirrors the buildings convention — asset library + viewer):
  ~/Desktop/Models/Buildings/FishingDock.glb
  viewer/public/buildings/FishingDock.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_fishing_dock.py
"""

import math
import os

import bpy


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

OUT_NAME = "FishingDock.glb"


# ── Overall dimensions ────────────────────────────────────────────────────
# Kept as module-level constants so tweaking the pier length / width or
# vertical stack is a one-line change and every downstream part-count
# calculation stays consistent.

DOCK_LENGTH = 6.00     # metres, +Y extent (shore at y=0 → far end at y=6.0)
DOCK_HALF_WIDTH = 0.97 # deck spans x ∈ [−0.97, +0.97]  → ~1.94 m wide

# Piling geometry
PILING_ROWS_Y = (0.35, 1.75, 3.15, 4.55, 5.65)  # y-positions of each pair
PILING_X = 0.90                                  # ±X — inboard of deck edge
PILING_RADIUS = 0.11
PILING_Z_BOTTOM = -0.20   # sunk under the surface for visual seating
PILING_Z_TOP    =  1.30   # extends up through the joist layer

# Longitudinal stringers (2 beams running the full pier length under deck)
STRINGER_X = PILING_X
STRINGER_WIDTH  = 0.14
STRINGER_HEIGHT = 0.10
STRINGER_Z_BOTTOM = 1.09
STRINGER_Z_TOP    = STRINGER_Z_BOTTOM + STRINGER_HEIGHT   # 1.19

# Cross joists resting on top of stringers
JOIST_LENGTH = 2.00      # spans a bit past the deck edges (x ∈ [-1.0, +1.0])
JOIST_WIDTH  = 0.11      # thickness along Y
JOIST_HEIGHT = 0.11
JOIST_Z_BOTTOM = STRINGER_Z_TOP           # 1.19
JOIST_Z_TOP    = JOIST_Z_BOTTOM + JOIST_HEIGHT  # 1.30
JOIST_Y_POSITIONS = PILING_ROWS_Y         # 1 joist above each piling pair

# Deck planks on top of joists
PLANK_COUNT     = 13
PLANK_LENGTH    = DOCK_LENGTH             # planks run the full pier length
PLANK_WIDTH     = 0.13                    # along X
PLANK_THICKNESS = 0.04                    # along Z
PLANK_GAP       = 0.01                    # visible gap between planks
PLANK_Z_BOTTOM  = JOIST_Z_TOP             # 1.30
PLANK_Z_TOP     = PLANK_Z_BOTTOM + PLANK_THICKNESS   # 1.34

# Mooring cleats (small "T" bollards near the far end)
CLEAT_Y = 5.40
CLEAT_X = 0.80
CLEAT_POST_SIZE   = (0.07, 0.07, 0.08)    # (sx, sy, sz) — base pedestal
CLEAT_BAR_SIZE    = (0.06, 0.24, 0.05)    # (sx, sy, sz) — horizontal T bar
CLEAT_POST_Z0     = PLANK_Z_TOP            # sits on top of the deck
CLEAT_BAR_Z0      = CLEAT_POST_Z0 + CLEAT_POST_SIZE[2]  # bar on top of post

# Ladder hanging off the +Y (far) end, into the water/ground
LADDER_Y = DOCK_LENGTH + 0.04              # a hair outside the deck edge
LADDER_RAIL_HALF_SPAN = 0.30               # rails at x = ±0.30
LADDER_RAIL_SIZE = (0.05, 0.05)            # (sx, sy) — square cross-section
LADDER_RAIL_Z_BOTTOM = 0.05
LADDER_RAIL_Z_TOP    = 1.28
LADDER_RUNG_ZS = (0.20, 0.55, 0.90, 1.20)  # rung Z positions
LADDER_RUNG_SIZE = (0.03, 0.03)            # (sy, sz) — rung cross-section


# ── Material helpers ──────────────────────────────────────────────────────
# Named slots ONLY.  Colours are intentionally neutral placeholders — the
# user will assign real textures per material slot later.  Roughness is
# left at Principled's default 0.5 for the same reason: whatever the
# texture set ships with will be authoritative.

MATERIAL_COLORS = {
    "dock_planks":    (0.72, 0.66, 0.55),   # warm mid-grey plank placeholder
    "dock_stringers": (0.60, 0.55, 0.47),   # slightly darker beam placeholder
    "dock_joists":    (0.62, 0.57, 0.48),
    "dock_pilings":   (0.48, 0.42, 0.36),   # darker post placeholder
    "dock_ladder":    (0.58, 0.52, 0.44),
    "dock_cleats":    (0.28, 0.28, 0.30),   # dark neutral, hints at metal
}


def make_material(name: str) -> bpy.types.Material:
    """Get-or-create a Principled BSDF material with a neutral placeholder
    colour.  Real textures will be assigned later — this just guarantees
    the slot exists so a Blender / Unity / Three.js material picker can
    address each part-type by name after import."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
        mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        color = MATERIAL_COLORS.get(name, (0.5, 0.5, 0.5))
        principled.inputs["Base Color"].default_value = (*color, 1.0)
    return mat


# ── Primitive helpers ─────────────────────────────────────────────────────

def add_box(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    material_name: str,
    obj_name: str,
) -> bpy.types.Object:
    """Add a unit cube, scale it into a box, bake the scale into vertex
    data, then assign the named material slot.  Baking the scale here
    (rather than at export time) keeps subsequent bounding-box maths
    honest as the script builds up the dock piece by piece."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
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
    depth: float,
    material_name: str,
    obj_name: str,
    sides: int = 8,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """Add a low-poly cylinder oriented along +Z by default.  8 sides is
    the game-asset default here — silhouette still reads as round from a
    normal gameplay camera and the vert count stays trivial."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=sides,
        radius=radius,
        depth=depth,
        location=center,
        rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = obj_name
    obj.data.materials.clear()
    obj.data.materials.append(make_material(material_name))
    return obj


# ── Build helpers (one per part-type) ─────────────────────────────────────

def build_pilings(created: list) -> None:
    """5 pairs of vertical wooden posts along the pier length."""
    depth = PILING_Z_TOP - PILING_Z_BOTTOM
    z_center = (PILING_Z_TOP + PILING_Z_BOTTOM) / 2.0
    for iy, y in enumerate(PILING_ROWS_Y):
        for sx in (-1, +1):
            created.append(add_cylinder(
                center=(sx * PILING_X, y, z_center),
                radius=PILING_RADIUS,
                depth=depth,
                material_name="dock_pilings",
                obj_name=f"piling_{iy}_{'L' if sx < 0 else 'R'}",
            ))


def build_stringers(created: list) -> None:
    """Two longitudinal beams running the full pier length, resting on top
    of the pilings and supporting the cross joists."""
    z_center = (STRINGER_Z_TOP + STRINGER_Z_BOTTOM) / 2.0
    for sx in (-1, +1):
        created.append(add_box(
            center=(sx * STRINGER_X, DOCK_LENGTH / 2.0, z_center),
            size=(STRINGER_WIDTH, DOCK_LENGTH, STRINGER_HEIGHT),
            material_name="dock_stringers",
            obj_name=f"stringer_{'L' if sx < 0 else 'R'}",
        ))


def build_joists(created: list) -> None:
    """Cross joists resting on top of the stringers, one above each
    piling pair.  Slightly longer than the deck width so they poke out
    a touch under the plank edges — reads correctly as "the joist ends
    are visible from the side of the pier"."""
    z_center = (JOIST_Z_TOP + JOIST_Z_BOTTOM) / 2.0
    for iy, y in enumerate(JOIST_Y_POSITIONS):
        created.append(add_box(
            center=(0.0, y, z_center),
            size=(JOIST_LENGTH, JOIST_WIDTH, JOIST_HEIGHT),
            material_name="dock_joists",
            obj_name=f"joist_{iy}",
        ))


def build_planks(created: list) -> None:
    """Individual deck planks running the full pier length, with a small
    visible gap between them.  Modelled as SEPARATE boxes (rather than a
    single quad slab) so the plank seams read even on a completely
    untextured render — that visual "planked deck" language is what
    turns this from a generic platform into a fishing pier."""
    z_center = (PLANK_Z_TOP + PLANK_Z_BOTTOM) / 2.0
    pitch = PLANK_WIDTH + PLANK_GAP
    # Centre the plank set on x=0 regardless of PLANK_COUNT parity.
    x0 = -pitch * (PLANK_COUNT - 1) / 2.0
    for i in range(PLANK_COUNT):
        x_center = x0 + i * pitch
        created.append(add_box(
            center=(x_center, DOCK_LENGTH / 2.0, z_center),
            size=(PLANK_WIDTH, PLANK_LENGTH, PLANK_THICKNESS),
            material_name="dock_planks",
            obj_name=f"plank_{i:02d}",
        ))


def build_cleats(created: list) -> None:
    """Two mooring cleats near the far end of the dock — small T-shaped
    bollards a boat rope could tie off to.  Two boxes each: a stubby
    pedestal on top of the deck and a horizontal bar on top of the
    pedestal."""
    for sx in (-1, +1):
        # Pedestal
        created.append(add_box(
            center=(sx * CLEAT_X, CLEAT_Y, CLEAT_POST_Z0 + CLEAT_POST_SIZE[2] / 2.0),
            size=CLEAT_POST_SIZE,
            material_name="dock_cleats",
            obj_name=f"cleat_post_{'L' if sx < 0 else 'R'}",
        ))
        # Horizontal T bar
        created.append(add_box(
            center=(sx * CLEAT_X, CLEAT_Y, CLEAT_BAR_Z0 + CLEAT_BAR_SIZE[2] / 2.0),
            size=CLEAT_BAR_SIZE,
            material_name="dock_cleats",
            obj_name=f"cleat_bar_{'L' if sx < 0 else 'R'}",
        ))


def build_ladder(created: list) -> None:
    """Simple plank ladder hanging off the +Y (far) end of the pier.
    2 vertical rails + 4 horizontal rungs.  Attached to the outside
    face of the last joist so it hangs cleanly off the pier edge."""
    rail_depth = LADDER_RAIL_Z_TOP - LADDER_RAIL_Z_BOTTOM
    rail_z_center = (LADDER_RAIL_Z_TOP + LADDER_RAIL_Z_BOTTOM) / 2.0
    rail_sx, rail_sy = LADDER_RAIL_SIZE

    for sx in (-1, +1):
        created.append(add_box(
            center=(sx * LADDER_RAIL_HALF_SPAN, LADDER_Y, rail_z_center),
            size=(rail_sx, rail_sy, rail_depth),
            material_name="dock_ladder",
            obj_name=f"ladder_rail_{'L' if sx < 0 else 'R'}",
        ))

    rung_sy, rung_sz = LADDER_RUNG_SIZE
    rung_span = 2 * LADDER_RAIL_HALF_SPAN + rail_sx   # slight overhang past rails
    for i, z in enumerate(LADDER_RUNG_ZS):
        created.append(add_box(
            center=(0.0, LADDER_Y, z),
            size=(rung_span, rung_sy, rung_sz),
            material_name="dock_ladder",
            obj_name=f"ladder_rung_{i}",
        ))


# ── Join + export ─────────────────────────────────────────────────────────

def join_all(created: list, final_name: str) -> bpy.types.Object:
    """Merge every piece into a single mesh so the whole dock is one draw
    call in-engine.  Blender's join keeps each object's assigned material
    on its own slot, so the resulting mesh ends up with the full set of
    named slots (dock_planks / dock_pilings / …) — which is exactly the
    handoff shape a texture-artist workflow expects."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    if len(created) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = final_name
    return obj


def normalize_transform(obj: bpy.types.Object) -> None:
    """Bake root loc/rot/scale into vertex data so the exported GLB has
    scale=(1,1,1) and origin at world (0,0,0)."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def export_glb(obj: bpy.types.Object, out_path: str) -> None:
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


def compute_bounds(obj: bpy.types.Object):
    mw = obj.matrix_world
    verts = [mw @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
    return ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs)))


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Source output: {os.path.join(SOURCE_DIR, OUT_NAME)}")
    print(f"Viewer output: {os.path.join(VIEWER_DIR, OUT_NAME)}")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    created: list = []
    build_pilings(created)
    build_stringers(created)
    build_joists(created)
    build_planks(created)
    build_cleats(created)
    build_ladder(created)

    print(f"Pieces built: {len(created)}")
    dock = join_all(created, final_name="fishing_dock")

    n_verts = len(dock.data.vertices)
    n_faces = len(dock.data.polygons)
    n_tris  = sum(len(p.vertices) - 2 for p in dock.data.polygons)
    n_slots = len(dock.data.materials)
    slot_names = ", ".join(m.name if m else "<none>" for m in dock.data.materials)

    (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(dock)
    print(f"Final mesh: verts={n_verts}, faces={n_faces}, tris={n_tris}")
    print(f"Material slots ({n_slots}): {slot_names}")
    print(f"Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  "
          f"Z[{z_min:+.3f}, {z_max:+.3f}]")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, OUT_NAME)
        export_glb(dock, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0 if os.path.exists(out_path) else 0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    print("\nDONE — fishing dock exported.")


if __name__ == "__main__":
    main()
