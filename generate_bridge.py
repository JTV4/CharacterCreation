"""
generate_bridge.py
==================
Build a single, game-optimized, UNTEXTURED arched wooden bridge GLB from
Blender primitives.  Same clean-handoff contract as the fishing dock:

  - Origin at world (0, 0, 0), one end of the bridge on the shore-side.
  - Root scale = (1, 1, 1) with all transforms baked into vertex data.
  - Single joined mesh — one draw call in-engine.
  - Multiple named material slots (planks / posts / rails / stringers)
    so texture assignment later is per-part-type without re-splitting.

Arch geometry (see also `_arch_point()` below)
----------------------------------------------
The deck follows a CIRCULAR ARC.  User spec: 15 m horizontal span, 2 m
wide, "about 30° upward at the ends" — the natural reading is that the
deck's TANGENT at each endpoint makes a 30° angle with horizontal, so
the slope you experience stepping onto the bridge is 30°.

For a circular arc of chord C with tangent-angle θ at the endpoints:
    R = C / (2·sin θ)
    rise = R · (1 − cos θ)      # sagitta (peak height above the chord)

Plugging in C = 15 m, θ = 30°:
    R    = 15 / (2 · 0.5)             = 15.00 m
    rise = 15 · (1 − √3/2)            ≈ 2.01 m
    arc  = R · 2θ = 15 · (π/3)        ≈ 15.71 m   (walkable distance)

The circle's centre sits at y = 7.5 (mid-span), z = −√(R² − 7.5²) ≈
−12.99 m — i.e. WAY below the ground, directly under the peak.  Every
point on the deck is at (0, 7.5 + R·sin φ, z_c + R·cos φ) for the
signed sweep angle φ ∈ [−30°, +30°], and the outward normal at that
point is (0, sin φ, cos φ) — used for placing planks perpendicular to
the arc surface.

Coordinate convention
---------------------
  +X = perpendicular to bridge length (deck width)
  +Y = along the bridge (bridge extends from y=0 to y=15)
  +Z = up
  Origin sits on the ground at the shore-side end (y=0, x=0, z=0).
  The mid-line peak of the arch sits at (0, 7.5, ~2.01).

Parts (with a joined-mesh material slot each)
---------------------------------------------
  30 crosswise deck planks    -> material "bridge_planks"
  16 vertical railing posts   -> material "bridge_posts"    (8 per side)
  14 top-rail segments        -> material "bridge_rails"    (7 per side)
  14 stringer segments        -> material "bridge_stringers" (7 per side,
                                                              under deck)

Poly budget (final mesh, after join): ~900 tris.

Outputs (mirrors buildings/dock convention):
  ~/Desktop/Models/Buildings/Bridge.glb
  viewer/public/buildings/Bridge.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_bridge.py
"""

import math
import os

import bpy


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)

OUT_NAME = "Bridge.glb"


# ── Arch geometry (see module docstring for derivation) ───────────────────

BRIDGE_LENGTH     = 15.00   # horizontal chord along +Y
BRIDGE_HALF_WIDTH = 1.00    # deck spans x ∈ [−1.0, +1.0]
TANGENT_ANGLE_DEG = 30.00   # slope at the endpoints (user spec)

_TANGENT = math.radians(TANGENT_ANGLE_DEG)
ARCH_RADIUS     = BRIDGE_LENGTH / (2.0 * math.sin(_TANGENT))   # 15.00
ARCH_MID_Y      = BRIDGE_LENGTH / 2.0                          # 7.50
ARCH_CENTER_Z   = -math.sqrt(ARCH_RADIUS ** 2 - ARCH_MID_Y ** 2)  # ≈ -12.99
ARCH_RISE       = ARCH_RADIUS - math.sqrt(ARCH_RADIUS ** 2 - ARCH_MID_Y ** 2)
ARCH_PHI_MIN    = -_TANGENT
ARCH_PHI_MAX    = +_TANGENT


# ── Part dimensions ───────────────────────────────────────────────────────

# Deck planks: individual crosswise boards tilted along the arc.  30
# planks × ~0.524 m arc-per-plank ≈ 15.71 m of arc, so this exactly
# covers the arc.  Local plank length is a hair less than the arc slice
# so a small V-groove reads between adjacent planks and the seams look
# right even before any texture is added.
PLANK_COUNT     = 30
PLANK_WIDTH     = 2.0 * BRIDGE_HALF_WIDTH   # 2.0 m — matches deck width
PLANK_ARC_SLICE = (ARCH_PHI_MAX - ARCH_PHI_MIN) * ARCH_RADIUS / PLANK_COUNT  # ≈ 0.524
PLANK_LENGTH    = PLANK_ARC_SLICE * 0.94    # ~6% shorter → visible seam
PLANK_THICKNESS = 0.05

# Railing posts (vertical, world +Z) spaced evenly along the arc.
POST_COUNT_PER_SIDE = 8
POST_HEIGHT   = 1.00
POST_XSIZE    = 0.06
POST_YSIZE    = 0.06
POST_INSET    = 0.03    # post OUTER face flush with deck edge (x=±1.0)

# Top handrail — piecewise-straight segments between adjacent post tops.
RAIL_XSIZE = 0.06
RAIL_ZSIZE = 0.06

# Under-deck longitudinal stringers — piecewise-straight, mirror of the
# handrail geometry offset below the deck instead of above.
STRINGER_XSIZE  = 0.10
STRINGER_ZSIZE  = 0.12
STRINGER_INSET  = 0.05    # slightly inboard of the deck edge


# ── Materials ─────────────────────────────────────────────────────────────
# Neutral placeholder colours only — the whole point of the untextured
# export is that texture artists replace the base-colour input later.
# Colours here are picked to match the fishing dock palette so the two
# assets read as "same wood tradition" side-by-side in the viewer.

MATERIAL_COLORS = {
    "bridge_planks":    (0.72, 0.66, 0.55),
    "bridge_posts":     (0.60, 0.55, 0.47),
    "bridge_rails":     (0.62, 0.57, 0.48),
    "bridge_stringers": (0.48, 0.42, 0.36),
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


# ── Primitive helpers ─────────────────────────────────────────────────────

def add_box(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    material_name: str,
    obj_name: str,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """Add a cube, scale it into a box, rotate, then bake the transform
    into vertex data so downstream bounding-box maths stay honest."""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = obj_name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(make_material(material_name))
    return obj


# ── Arch math helpers ─────────────────────────────────────────────────────

def arch_point(phi: float) -> tuple[float, float, float]:
    """(x=0, y, z) of the point on the mathematical arch curve at signed
    sweep angle `phi` (radians).  This is the CENTRE-LINE of the deck —
    plank centres sit here, stringer tops sit here.  Convert to plank
    top / stringer bottom by offsetting along the outward normal
    (`arch_normal`)."""
    return (
        0.0,
        ARCH_MID_Y + ARCH_RADIUS * math.sin(phi),
        ARCH_CENTER_Z + ARCH_RADIUS * math.cos(phi),
    )


def arch_normal(phi: float) -> tuple[float, float, float]:
    """Unit outward normal at the arch point for angle `phi`.  Points
    UP-and-outward — used to displace planks / stringers above / below
    the mathematical arch surface."""
    return (0.0, math.sin(phi), math.cos(phi))


def sample_arc_phis(count: int) -> list[float]:
    """Evenly-spaced phi values including both endpoints — used for
    posts, top-rail joints, and stringer joints."""
    if count == 1:
        return [0.0]
    return [
        ARCH_PHI_MIN + (ARCH_PHI_MAX - ARCH_PHI_MIN) * i / (count - 1)
        for i in range(count)
    ]


# ── Build helpers (one per part-type) ─────────────────────────────────────

def build_planks(created: list) -> None:
    """Crosswise deck planks — each tilted so its top face is tangent to
    the arch at that point.  Placed at plank-CENTRE phi values (half a
    slice in from the endpoints), so the deck exactly fills the arc."""
    slice_phi = (ARCH_PHI_MAX - ARCH_PHI_MIN) / PLANK_COUNT
    for i in range(PLANK_COUNT):
        phi = ARCH_PHI_MIN + slice_phi * (i + 0.5)
        # Plank centre sits +PLANK_THICKNESS/2 above the arch centre-line
        # so its BOTTOM face touches the mathematical arch (== top of
        # any stringer we place at the same phi below).
        p = arch_point(phi)
        n = arch_normal(phi)
        offset = PLANK_THICKNESS / 2.0
        centre = (
            p[0] + n[0] * offset,
            p[1] + n[1] * offset,
            p[2] + n[2] * offset,
        )
        # Rotate around X so the plank's local +Y aligns with the arc
        # tangent (which drops in +Z as phi increases past 0) — that's
        # rot_x = -phi.  See docstring maths.
        created.append(add_box(
            center=centre,
            size=(PLANK_WIDTH, PLANK_LENGTH, PLANK_THICKNESS),
            material_name="bridge_planks",
            obj_name=f"plank_{i:02d}",
            rotation=(-phi, 0.0, 0.0),
        ))


def build_posts(created: list) -> None:
    """Vertical railing posts.  Kept world-vertical (not tilted with the
    arch) because that's how real bridge posts read — they carry the
    handrail load straight into the deck below.  Base sits on the deck
    TOP surface at the post's phi."""
    for side_x in (-1.0, +1.0):
        for i, phi in enumerate(sample_arc_phis(POST_COUNT_PER_SIDE)):
            p = arch_point(phi)
            deck_top_z = p[2] + PLANK_THICKNESS  # top of the plank at this phi
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
    """Add a box that stretches from p1 to p2 in the YZ plane (both
    points share the same X).  `cross_section = (x_size, z_local_size)`.
    Rotation is chosen so the box's local +Y axis aligns with (p2 − p1)."""
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
    # Segment lives in YZ plane (assumed dx ≈ 0).  Rotate around X:
    # local +Y should point along (dy, dz), so rot_x = atan2(dz, dy).
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
    """Top handrail: piecewise-straight segments between the tops of
    adjacent posts on each side.  Piecewise-linear rather than a
    single curved beam so the geometry stays trivial and the segments
    match the post positions exactly."""
    phis = sample_arc_phis(POST_COUNT_PER_SIDE)
    for side_x in (-1.0, +1.0):
        x = side_x * (BRIDGE_HALF_WIDTH - POST_INSET)
        # Compute all post-top positions on this side first, then walk
        # adjacent pairs to build rail segments between them.
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


def build_stringers(created: list) -> None:
    """Longitudinal stringers under the deck edges — piecewise-straight
    box segments approximating the arch curve from below.  Provide the
    "visible structure beneath the planks" language that reads as
    "engineered wooden bridge" rather than "floating deck"."""
    phis = sample_arc_phis(POST_COUNT_PER_SIDE)
    for side_x in (-1.0, +1.0):
        x = side_x * (BRIDGE_HALF_WIDTH - STRINGER_INSET)
        # Stringer TOP sits at the mathematical arch centre-line (== the
        # plank BOTTOM), so centre = arch_point − (STRINGER_ZSIZE/2)
        # along the outward normal.
        bottoms = []
        for phi in phis:
            p = arch_point(phi)
            n = arch_normal(phi)
            offset = STRINGER_ZSIZE / 2.0
            bottoms.append((
                x,
                p[1] - n[1] * offset,
                p[2] - n[2] * offset,
            ))
        for i in range(len(bottoms) - 1):
            _connect_with_box(
                p1=bottoms[i],
                p2=bottoms[i + 1],
                cross_section=(STRINGER_XSIZE, STRINGER_ZSIZE),
                material_name="bridge_stringers",
                obj_name=f"stringer_{'L' if side_x < 0 else 'R'}{i}",
                created=created,
            )


# ── Join + export (identical to fishing dock — same handoff contract) ────

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
    print(f"Arch derived:  R={ARCH_RADIUS:.3f} m, "
          f"rise={ARCH_RISE:.3f} m, arc={ARCH_RADIUS * 2 * _TANGENT:.3f} m")

    bpy.ops.wm.read_factory_settings(use_empty=True)

    created: list = []
    build_planks(created)
    build_posts(created)
    build_rails(created)
    build_stringers(created)

    print(f"Pieces built: {len(created)}")
    bridge = join_all(created, final_name="arched_bridge")

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

    print("\nDONE — arched bridge exported.")


if __name__ == "__main__":
    main()
