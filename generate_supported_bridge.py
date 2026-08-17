"""
generate_supported_bridge.py
============================
Sibling of `generate_bridge.py`.  Same arch profile (15 m span, 30°
tangent at the endpoints) but TWICE THE WIDTH (4 m instead of 2 m),
raised off the ground and carried on 3 pairs of vertical support
piers — one pair at each end, one pair in the middle under the arch
peak — with a horizontal cap beam capping each pair.

The doubled width is a single-constant change (`BRIDGE_HALF_WIDTH`
below).  Every dependent dimension — plank length, pier X positions,
cap beam length, stringer inset — is derived from that constant so
scaling the deck width doesn't require touching any other part of the
build.

The design intent is "arched wooden bridge over a chasm / river / dry
gulch": something that clearly HOVERS above a lower plane and needs
visible legs to stand there.  If the deck endpoints stayed at z=0 (as
in the plain `Bridge.glb`) the end-piers would be zero-height stubs
buried under the deck, which is why the whole arch is shifted up by
`DECK_Z_OFFSET` here.

The plain `Bridge.glb` is NOT touched — this exports a separate
`SupportedBridge.glb` alongside it so both are selectable in the viewer.

Arch geometry
-------------
Identical to `generate_bridge.py` (see that file's docstring for the
derivation of R = 15 m, rise = 2.01 m, arc = 15.71 m at 30° tangent).
The ONLY change is that every deck / post / rail / stringer z-value is
shifted by +DECK_Z_OFFSET so the whole arch sits above the ground plane.

Vertical stack (all heights are +Z, with DECK_Z_OFFSET = 1.50)
--------------------------------------------------------------
   z =  0.00   ── ground plane (bottom of every support pier)
   z ≈  1.32   ── top of end-piers = bottom of end cap beam
   z ≈  1.50   ── top of end cap beam = deck underside at y=0 & y=15
   z ≈  3.33   ── top of mid-piers = bottom of mid cap beam
   z ≈  3.51   ── top of mid cap beam = deck underside at y=7.5 (peak)
   z ≈  3.56   ── deck top at y=7.5 (peak walkable surface)
   z ≈  4.56   ── mid rail top (post_height above the mid deck)

Parts added on top of the plain-bridge geometry
-----------------------------------------------
    6 vertical support piers (2 per position × 3 positions)
    3 horizontal cap beams (one per pier pair)
   -> new material slot "bridge_supports"

Outputs:
  ~/Desktop/Models/Buildings/SupportedBridge.glb
  viewer/public/buildings/SupportedBridge.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_supported_bridge.py
"""

import math
import os

import bpy


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

OUT_NAME = "SupportedBridge.glb"


# ── Arch geometry (mirror of generate_bridge.py, shifted up by Z_OFFSET) ──
# Keeping the constants in-file (rather than importing from
# `generate_bridge`) so this script stays runnable standalone and the
# plain bridge script never has to know about DECK_Z_OFFSET.  If you
# tune arch parameters, update both files.

BRIDGE_LENGTH     = 15.00
BRIDGE_HALF_WIDTH = 2.00     # doubled from plain bridge's 1.00 → 4 m deck
TANGENT_ANGLE_DEG = 30.00

_TANGENT = math.radians(TANGENT_ANGLE_DEG)
ARCH_RADIUS   = BRIDGE_LENGTH / (2.0 * math.sin(_TANGENT))
ARCH_MID_Y    = BRIDGE_LENGTH / 2.0
ARCH_RISE     = ARCH_RADIUS - math.sqrt(ARCH_RADIUS ** 2 - ARCH_MID_Y ** 2)

# How high off the ground plane the arched deck sits.  1.5 m is a
# comfortable "elevated bridge over a chasm/river" clearance — tall
# enough that the end-piers are clearly visible, short enough that
# 3.5 m of total structure (deck peak + rails) fits in most game
# camera frames without being cartoonishly tall.
DECK_Z_OFFSET = 1.50

# Circle centre z is shifted by DECK_Z_OFFSET, so every arch_point()
# result comes out already elevated with no per-function offset needed.
ARCH_CENTER_Z = -math.sqrt(ARCH_RADIUS ** 2 - ARCH_MID_Y ** 2) + DECK_Z_OFFSET

ARCH_PHI_MIN = -_TANGENT
ARCH_PHI_MAX = +_TANGENT


# ── Part dimensions (same as generate_bridge.py) ─────────────────────────

PLANK_COUNT     = 30
PLANK_WIDTH     = 2.0 * BRIDGE_HALF_WIDTH
PLANK_ARC_SLICE = (ARCH_PHI_MAX - ARCH_PHI_MIN) * ARCH_RADIUS / PLANK_COUNT
PLANK_LENGTH    = PLANK_ARC_SLICE * 0.94
PLANK_THICKNESS = 0.05

POST_COUNT_PER_SIDE = 8
POST_HEIGHT   = 1.00
# Posts thickened for a sturdier railing — 4× cross-section of the plain
# bridge's 0.06 × 0.06 uprights.  POST_INSET stays derived from
# POST_XSIZE / 2 so the post's OUTER face remains flush with the deck
# edge no matter how thick the posts get.
POST_XSIZE    = 0.12
POST_YSIZE    = 0.12
POST_INSET    = POST_XSIZE / 2.0

# Top handrail: chunky board-like cross-section — 0.10 wide × 0.15 tall,
# reading as a "2×4 on edge" plank rather than the slim square rod on
# the plain bridge (0.06 × 0.06).
RAIL_XSIZE = 0.10
RAIL_ZSIZE = 0.15

# Mid-rail: a second horizontal board halfway up the posts.  Two-rail
# railings are the standard sturdy-bridge idiom (bottom rail keeps
# people/carts from slipping through, top rail is the handhold), and
# adding one here is the single biggest visual "engineered wooden
# railing" upgrade available without changing the palette.  Kept
# slightly slimmer than the top rail (0.08 × 0.14) so the visual
# hierarchy still reads top-rail-as-primary.
MID_RAIL_XSIZE       = 0.08
MID_RAIL_ZSIZE       = 0.14
MID_RAIL_HEIGHT_FRAC = 0.50   # fraction of POST_HEIGHT above the deck top

STRINGER_XSIZE  = 0.10
STRINGER_ZSIZE  = 0.12
STRINGER_INSET  = 0.05


# ── Support piers (NEW — the whole point of this asset) ──────────────────
# 3 pairs of vertical piers at y = 0, 7.5, 15.  Each pair carries a
# horizontal cap beam that meets the deck's underside.  Cross-section
# is larger than the railing posts (0.22 vs 0.06) so the piers read as
# structural load-bearers, not decorative uprights.

SUPPORT_Y_POSITIONS = (0.0, ARCH_MID_Y, BRIDGE_LENGTH)  # (0, 7.5, 15)

PIER_XSIZE  = 0.22
PIER_YSIZE  = 0.22
PIER_INSET  = 0.10                # piers at x = ±(BRIDGE_HALF_WIDTH - PIER_INSET)
PIER_X      = BRIDGE_HALF_WIDTH - PIER_INSET   # 0.90

CAP_XSIZE   = 2.0 * BRIDGE_HALF_WIDTH + 0.20   # 2.20 — slight overhang past deck edge
CAP_YSIZE   = 0.28
CAP_ZSIZE   = 0.18


# ── Materials ─────────────────────────────────────────────────────────────
# Same palette as generate_bridge.py, plus one new slot for the
# support structure so texture assignment stays per-part-type.

MATERIAL_COLORS = {
    "bridge_planks":    (0.72, 0.66, 0.55),
    "bridge_posts":     (0.60, 0.55, 0.47),
    "bridge_rails":     (0.62, 0.57, 0.48),
    "bridge_stringers": (0.48, 0.42, 0.36),
    "bridge_supports":  (0.42, 0.36, 0.30),  # darker structural wood
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
    return mat


# ── Primitive + arch helpers (identical to generate_bridge.py) ───────────

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


def arch_point(phi: float) -> tuple[float, float, float]:
    """(x=0, y, z) of the deck centre-line at signed sweep angle `phi`.
    Uses the DECK_Z_OFFSET-shifted ARCH_CENTER_Z, so every returned z
    is already elevated."""
    return (
        0.0,
        ARCH_MID_Y + ARCH_RADIUS * math.sin(phi),
        ARCH_CENTER_Z + ARCH_RADIUS * math.cos(phi),
    )


def arch_normal(phi: float) -> tuple[float, float, float]:
    return (0.0, math.sin(phi), math.cos(phi))


def sample_arc_phis(count: int) -> list[float]:
    if count == 1:
        return [0.0]
    return [
        ARCH_PHI_MIN + (ARCH_PHI_MAX - ARCH_PHI_MIN) * i / (count - 1)
        for i in range(count)
    ]


def phi_at_y(y: float) -> float:
    """Inverse of `arch_point`: given a target y, return the phi that
    puts the deck centre-line at that y.  Used to compute the deck-
    underside height directly above each support pier."""
    ratio = (y - ARCH_MID_Y) / ARCH_RADIUS
    # Clamp to valid asin domain, defensively — Y positions passed in
    # are always inside [0, 15] so this branch is protective only.
    ratio = max(-1.0, min(1.0, ratio))
    return math.asin(ratio)


# ── Build helpers (deck / rails / stringers — same as plain bridge) ──────
# NOTE: these are byte-for-byte the same as generate_bridge.py's
# `build_planks` / `build_posts` / `build_rails` / `build_stringers`.
# All the elevation change is baked into `arch_point()` via
# `ARCH_CENTER_Z += DECK_Z_OFFSET` above, so no per-function edits.

def build_planks(created: list) -> None:
    slice_phi = (ARCH_PHI_MAX - ARCH_PHI_MIN) / PLANK_COUNT
    for i in range(PLANK_COUNT):
        phi = ARCH_PHI_MIN + slice_phi * (i + 0.5)
        p = arch_point(phi)
        n = arch_normal(phi)
        offset = PLANK_THICKNESS / 2.0
        centre = (p[0] + n[0] * offset, p[1] + n[1] * offset, p[2] + n[2] * offset)
        created.append(add_box(
            center=centre,
            size=(PLANK_WIDTH, PLANK_LENGTH, PLANK_THICKNESS),
            material_name="bridge_planks",
            obj_name=f"plank_{i:02d}",
            rotation=(-phi, 0.0, 0.0),
        ))


def build_posts(created: list) -> None:
    for side_x in (-1.0, +1.0):
        for i, phi in enumerate(sample_arc_phis(POST_COUNT_PER_SIDE)):
            p = arch_point(phi)
            deck_top_z = p[2] + PLANK_THICKNESS
            x = side_x * (BRIDGE_HALF_WIDTH - POST_INSET)
            centre = (x, p[1], deck_top_z + POST_HEIGHT / 2.0)
            created.append(add_box(
                center=centre,
                size=(POST_XSIZE, POST_YSIZE, POST_HEIGHT),
                material_name="bridge_posts",
                obj_name=f"post_{'L' if side_x < 0 else 'R'}{i}",
            ))


def _connect_with_box(
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
    cross_section: tuple[float, float],
    material_name: str,
    obj_name: str,
    created: list,
) -> None:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dz = p2[2] - p1[2]
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return
    centre = (
        (p1[0] + p2[0]) / 2.0,
        (p1[1] + p2[1]) / 2.0,
        (p1[2] + p2[2]) / 2.0,
    )
    rot_x = math.atan2(dz, dy)
    cs_x, cs_z = cross_section
    created.append(add_box(
        center=centre,
        size=(cs_x, length, cs_z),
        material_name=material_name,
        obj_name=obj_name,
        rotation=(rot_x, 0.0, 0.0),
    ))


def build_rails(created: list) -> None:
    phis = sample_arc_phis(POST_COUNT_PER_SIDE)
    for side_x in (-1.0, +1.0):
        x = side_x * (BRIDGE_HALF_WIDTH - POST_INSET)
        tops = []
        for phi in phis:
            p = arch_point(phi)
            tops.append((x, p[1], p[2] + PLANK_THICKNESS + POST_HEIGHT))
        for i in range(len(tops) - 1):
            _connect_with_box(
                p1=tops[i],
                p2=tops[i + 1],
                cross_section=(RAIL_XSIZE, RAIL_ZSIZE),
                material_name="bridge_rails",
                obj_name=f"rail_{'L' if side_x < 0 else 'R'}{i}",
                created=created,
            )


def build_mid_rails(created: list) -> None:
    """Second horizontal board halfway up the posts on each side.
    Same piecewise-straight construction as `build_rails`, just placed
    at MID_RAIL_HEIGHT_FRAC × POST_HEIGHT above the deck top instead of
    at the post tops.  Shares the `bridge_rails` material slot so this
    doesn't inflate the material count for texture assignment."""
    phis = sample_arc_phis(POST_COUNT_PER_SIDE)
    for side_x in (-1.0, +1.0):
        x = side_x * (BRIDGE_HALF_WIDTH - POST_INSET)
        mids = []
        for phi in phis:
            p = arch_point(phi)
            mids.append((
                x,
                p[1],
                p[2] + PLANK_THICKNESS + POST_HEIGHT * MID_RAIL_HEIGHT_FRAC,
            ))
        for i in range(len(mids) - 1):
            _connect_with_box(
                p1=mids[i],
                p2=mids[i + 1],
                cross_section=(MID_RAIL_XSIZE, MID_RAIL_ZSIZE),
                material_name="bridge_rails",
                obj_name=f"midrail_{'L' if side_x < 0 else 'R'}{i}",
                created=created,
            )


def build_stringers(created: list) -> None:
    phis = sample_arc_phis(POST_COUNT_PER_SIDE)
    for side_x in (-1.0, +1.0):
        x = side_x * (BRIDGE_HALF_WIDTH - STRINGER_INSET)
        bottoms = []
        for phi in phis:
            p = arch_point(phi)
            n = arch_normal(phi)
            offset = STRINGER_ZSIZE / 2.0
            bottoms.append((x, p[1] - n[1] * offset, p[2] - n[2] * offset))
        for i in range(len(bottoms) - 1):
            _connect_with_box(
                p1=bottoms[i],
                p2=bottoms[i + 1],
                cross_section=(STRINGER_XSIZE, STRINGER_ZSIZE),
                material_name="bridge_stringers",
                obj_name=f"stringer_{'L' if side_x < 0 else 'R'}{i}",
                created=created,
            )


# ── Build helpers (NEW — support piers + cap beams) ──────────────────────

def build_supports(created: list) -> None:
    """One pair of vertical piers + a horizontal cap beam at each of
    the y positions in SUPPORT_Y_POSITIONS.  Cap beam sits so its TOP
    face just touches the deck's underside at that y — computed via
    `phi_at_y` so the geometry follows the arch exactly rather than
    approximating.

    Layout at each SUPPORT_Y:
        pier_left            pier_right         (from z=0 upward)
             |                     |
             +----[ cap beam ]-----+            (deck underside on top)
             |                     |
    """
    for y in SUPPORT_Y_POSITIONS:
        # Where the deck's underside sits at this y (== arch centre-
        # line at the corresponding phi, since planks are centred on
        # the arch centre-line).
        phi = phi_at_y(y)
        deck_bottom_z = arch_point(phi)[2]

        cap_z_top    = deck_bottom_z
        cap_z_bottom = cap_z_top - CAP_ZSIZE
        cap_centre_z = (cap_z_top + cap_z_bottom) / 2.0

        pier_z_top    = cap_z_bottom
        pier_z_bottom = 0.0
        pier_height   = pier_z_top - pier_z_bottom
        pier_centre_z = pier_height / 2.0

        # Two piers, one per side.
        for side_x in (-1.0, +1.0):
            x = side_x * PIER_X
            created.append(add_box(
                center=(x, y, pier_centre_z),
                size=(PIER_XSIZE, PIER_YSIZE, pier_height),
                material_name="bridge_supports",
                obj_name=f"pier_{'L' if side_x < 0 else 'R'}_y{int(round(y))}",
            ))

        # Cap beam spanning between the two piers, with slight overhang
        # past the deck edges.
        created.append(add_box(
            center=(0.0, y, cap_centre_z),
            size=(CAP_XSIZE, CAP_YSIZE, CAP_ZSIZE),
            material_name="bridge_supports",
            obj_name=f"cap_y{int(round(y))}",
        ))


# ── Join + export (identical to fishing dock / plain bridge) ─────────────

def join_all(created: list, final_name: str) -> bpy.types.Object:
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
    print(f"Arch derived:  R={ARCH_RADIUS:.3f} m, rise={ARCH_RISE:.3f} m, "
          f"arc={ARCH_RADIUS * 2 * _TANGENT:.3f} m, "
          f"deck z-offset={DECK_Z_OFFSET:.3f} m")
    print(f"Support piers at y = {SUPPORT_Y_POSITIONS} "
          f"(deck-bottom z at those y: "
          f"{[round(arch_point(phi_at_y(y))[2], 3) for y in SUPPORT_Y_POSITIONS]})")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    created: list = []
    build_planks(created)
    build_posts(created)
    build_rails(created)
    build_mid_rails(created)
    build_stringers(created)
    build_supports(created)

    print(f"Pieces built: {len(created)}")
    bridge = join_all(created, final_name="supported_arched_bridge")

    n_verts = len(bridge.data.vertices)
    n_faces = len(bridge.data.polygons)
    n_tris  = sum(len(p.vertices) - 2 for p in bridge.data.polygons)
    n_slots = len(bridge.data.materials)
    slot_names = ", ".join(m.name if m else "<none>" for m in bridge.data.materials)

    (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(bridge)
    print(f"Final mesh: verts={n_verts}, faces={n_faces}, tris={n_tris}")
    print(f"Material slots ({n_slots}): {slot_names}")
    print(f"Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  "
          f"Z[{z_min:+.3f}, {z_max:+.3f}]")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, OUT_NAME)
        export_glb(bridge, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0 if os.path.exists(out_path) else 0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    print("\nDONE — supported arched bridge exported.")


if __name__ == "__main__":
    main()
