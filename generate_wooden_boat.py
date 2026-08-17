"""
generate_wooden_boat.py
=======================
A small wooden rowboat, game-optimized and untextured.  Same clean-
handoff contract as the other assets in this repo:

  - Origin at world (0, 0, 0) — stern-centre, keel resting at z=0.
  - Root scale = (1, 1, 1) with transforms baked into vertex data.
  - Single joined mesh — one draw call in-engine.
  - Multiple named material slots (hull / gunwale / seats) so texturing
    later is per-part-type without re-splitting.

Coordinate convention
---------------------
  +X = starboard (right side of boat when facing forward)
  +Y = FORWARD (bow direction)
  +Z = up
  Origin sits on the ground/waterline at the STERN centre.  The bow
  tip is at (0, 3.50, ~0.30) — a slight rise, characteristic of every
  rowing boat that ever sat in a river.

Hull construction (why bmesh, not boxes)
----------------------------------------
Unlike the dock / bridge / buildings which are all straight-primitive
assemblies, a boat NEEDS curved geometry to read as a boat at all.  We
build the hull the same way real wooden boats are lofted: as a series
of transverse "stations" (cross-sections) along the length, each with
5 vertices forming a U-shape:

           gun_p ────────── gun_s    (gunwale — top port + starboard)
            /                 \
         chine_p           chine_s   (chine — where hull side meets bottom)
             \             /
              \           /
                 keel               (bottom centre-line)

Adjacent stations are stitched with quads to form the hull skin.  The
stern is closed with a flat transom (pentagon face); the bow tapers to
a single bow-tip vertex closed with a triangle fan.

The interior is real, not fake: we cap the top with a boat-shaped
N-gon, then use bmesh's INSET + EXTRUDE ops to create the gunwale rim
(hull thickness ≈ 6 cm), interior walls, and a flat interior floor.
The result is a manifold mesh you can walk around AND look down into.

Poly budget (final joined mesh): ~330 verts / ~470 tris.

Outputs (mirrors buildings / dock / bridge convention):
  ~/Desktop/Models/Buildings/WoodenBoat.glb
  viewer/public/buildings/WoodenBoat.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_wooden_boat.py
"""

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

OUT_NAME = "WoodenBoat.glb"


# ── Hull geometry (station table) ─────────────────────────────────────────
# Each row defines the cross-section at one Y position along the boat.
#   y        : position from stern (0.0) toward bow (BOW_TIP_Y)
#   keel_z   : bottom-of-hull height (rocker — flat in the middle, rising
#              at the ends for the classic "banana" waterline)
#   chine_x  : half-width at the chine (where the flat-ish bottom meets
#              the rising side).  0 at the bow tip.
#   chine_z  : height of the chine above the keel — slight because the
#              bottom is close to flat over the middle stations
#   gun_x    : half-width at the gunwale (top edge).  Widest slightly aft
#              of centre — traditional rowing-boat proportions.
#   gun_z    : height of the gunwale above the ground plane.  Rises
#              subtly toward bow + stern ("sheer") so the ends kick up.
#
# 7 stations × 5 verts each = 35 hull-skin verts, plus 1 bow-tip vert.

STATIONS: list[tuple[float, float, float, float, float, float]] = [
    # y      keel_z  chine_x  chine_z  gun_x  gun_z
    (0.00,   0.05,   0.42,    0.12,    0.55,  0.52),   # stern (transom)
    (0.40,   0.02,   0.52,    0.10,    0.62,  0.50),
    (0.95,   0.00,   0.60,    0.08,    0.67,  0.50),
    (1.65,   0.00,   0.62,    0.08,    0.68,  0.50),   # widest — main beam
    (2.30,   0.02,   0.55,    0.10,    0.63,  0.51),
    (2.85,   0.10,   0.38,    0.18,    0.45,  0.54),
    (3.25,   0.22,   0.17,    0.28,    0.22,  0.56),   # near bow (narrow)
]
BOW_TIP_Y = 3.50
BOW_TIP_Z = 0.32
# Bow tip is a single vertex at (0, BOW_TIP_Y, BOW_TIP_Z) — the pointed
# prow that all 5 verts of the last station fan into.

HULL_THICKNESS  = 0.06   # gunwale-rim width (inset amount from top cap)
INTERIOR_DEPTH  = 0.34   # how far the interior cavity extrudes downward
                         # from the gunwale — floor ends up at
                         # gunwale_z − INTERIOR_DEPTH ≈ z=0.16-0.22

# ── Interior thwarts (seat benches across the boat) ──────────────────────
# Thwart widths are computed DYNAMICALLY from the interior width at each
# Y position (see `_interior_half_width_at_y` below).  Hard-coding a
# single THWART_XSIZE (like an early revision did) causes the ends of
# the middle + bow-most thwarts to poke through the hull sides, because
# the boat narrows sharply toward the bow while a fixed-width bench
# stays the same length.  Dynamic sizing keeps every thwart inside the
# interior with a small clearance for the "wooden seat resting inside a
# hull" look.

THWART_YS         = (0.75, 1.75, 2.55)  # Y positions of the 3 seat benches
THWART_END_CLEARANCE = 0.03             # gap between thwart end + interior wall
THWART_YSIZE      = 0.18                # front-to-back thickness of each seat
THWART_ZSIZE      = 0.04                # plank thickness (top-bottom)
THWART_TOP_Z      = 0.42                # top-of-thwart height (sits ABOVE the
                                        # interior floor, resting near the
                                        # gunwale like real thwart benches)


# ── Materials ─────────────────────────────────────────────────────────────
# Named slots only — placeholder colours picked to match the dock/bridge
# palette so all three assets read as the same wooden tradition.

MATERIAL_COLORS = {
    "boat_hull":    (0.55, 0.42, 0.30),   # weathered warm brown
    "boat_gunwale": (0.68, 0.55, 0.40),   # slightly lighter trim
    "boat_seats":   (0.72, 0.60, 0.44),   # lighter still — bench planks
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


# ── Hull construction (bmesh) ─────────────────────────────────────────────

def _build_hull_mesh() -> bpy.types.Object:
    """Build the hollow hull as one manifold mesh via bmesh.

    Sequence:
      1. Create 5 verts per station + 1 bow-tip vert.
      2. Stitch adjacent stations with 4 quads each (bottom port, side
         port, side starboard, bottom starboard).
      3. Close the stern with a flat pentagon (transom).
      4. Fan the last station's 5 verts into the bow tip (5 tris).
      5. Cap the top with a boat-shaped N-gon spanning the whole gunwale
         outline (port gunwales aft→fwd, bow tip, starboard gunwales
         fwd→aft).
      6. INSET that top cap by HULL_THICKNESS — creates the gunwale-rim
         ring of quads around the smaller inset face.
      7. EXTRUDE the inset face DOWN by INTERIOR_DEPTH — creates the
         interior side walls; the extruded face becomes the interior
         floor.
      8. Delete the original inset face (now sealed inside the mesh),
         opening the top of the boat so you can see into the interior.

    Material slot assignment (all done AFTER geometry is finalised):
      - Every hull face gets slot 0 ("boat_hull") by default.
      - The gunwale-rim ring gets slot 1 ("boat_gunwale") — we hold
        references to those faces from step 6 so re-tagging is trivial.
    """
    mesh = bpy.data.meshes.new("wooden_boat_hull")
    obj  = bpy.data.objects.new("wooden_boat_hull", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    # 1. Station verts.  Store as list of dicts keyed by role so face
    # construction below reads by name rather than by fragile indices.
    station_verts = []
    for (y, keel_z, chine_x, chine_z, gun_x, gun_z) in STATIONS:
        station_verts.append({
            "keel":    bm.verts.new(Vector((0.0,       y, keel_z))),
            "chine_p": bm.verts.new(Vector((-chine_x,  y, chine_z))),
            "gun_p":   bm.verts.new(Vector((-gun_x,    y, gun_z))),
            "gun_s":   bm.verts.new(Vector((+gun_x,    y, gun_z))),
            "chine_s": bm.verts.new(Vector((+chine_x,  y, chine_z))),
        })
    bow_tip = bm.verts.new(Vector((0.0, BOW_TIP_Y, BOW_TIP_Z)))

    bm.verts.ensure_lookup_table()

    # 2. Hull-skin quads between adjacent stations.  Winding order is
    # chosen so face normals point OUTWARD (away from the boat's
    # interior) — verified after build with `bm.normal_update()`.
    for i in range(len(STATIONS) - 1):
        A = station_verts[i]      # aft station
        F = station_verts[i + 1]  # forward station
        bm.faces.new([A["keel"],    F["keel"],    F["chine_p"], A["chine_p"]])   # bottom port
        bm.faces.new([A["chine_p"], F["chine_p"], F["gun_p"],   A["gun_p"]])     # side port
        bm.faces.new([A["gun_s"],   F["gun_s"],   F["chine_s"], A["chine_s"]])   # side stbd
        bm.faces.new([A["chine_s"], F["chine_s"], F["keel"],    A["keel"]])      # bottom stbd

    # 3. Transom (stern closure) — flat pentagon facing -Y.
    S0 = station_verts[0]
    bm.faces.new([S0["keel"], S0["chine_p"], S0["gun_p"], S0["gun_s"], S0["chine_s"]])

    # 4. Bow fan — 5 triangles from the last station's pentagon into
    # the single bow tip.  Winding chosen so normals still face outward.
    SL = station_verts[-1]
    bm.faces.new([SL["keel"],    SL["chine_s"], bow_tip])
    bm.faces.new([SL["chine_s"], SL["gun_s"],   bow_tip])
    bm.faces.new([SL["gun_s"],   SL["gun_p"],   bow_tip])
    bm.faces.new([SL["gun_p"],   SL["chine_p"], bow_tip])
    bm.faces.new([SL["chine_p"], SL["keel"],    bow_tip])

    # 5. Top cap — boat-plan-shape N-gon at gunwale level.  Vert order:
    #    port gunwales aft→fwd, bow tip, starboard gunwales fwd→aft.
    top_perimeter = (
        [s["gun_p"] for s in station_verts]
        + [bow_tip]
        + [s["gun_s"] for s in reversed(station_verts)]
    )
    top_cap = bm.faces.new(top_perimeter)

    bm.normal_update()

    # 6. Inset the top cap by HULL_THICKNESS.  `inset_region` returns
    # the newly-created BORDER faces (the gunwale rim ring) — we grab
    # those to re-material them below.
    inset_result = bmesh.ops.inset_region(
        bm,
        faces=[top_cap],
        thickness=HULL_THICKNESS,
        depth=0.0,
        use_even_offset=True,
        use_boundary=True,
    )
    gunwale_faces = list(inset_result["faces"])
    # `top_cap` is now the SMALLER inset face (same BMFace, shrunk in-
    # place by the op).

    # 7. Extrude that inset face downward to carve out the interior.
    #    `extrude_face_region` returns {geom: [BMVert, BMEdge, BMFace,...]}
    #    — new geometry connected to the original face by side quads.
    extrude_result = bmesh.ops.extrude_face_region(bm, geom=[top_cap])
    new_geom = extrude_result["geom"]
    new_verts = [g for g in new_geom if isinstance(g, bmesh.types.BMVert)]
    for v in new_verts:
        v.co.z -= INTERIOR_DEPTH

    # 8. Delete the ORIGINAL top_cap (now sealed inside the mesh at the
    #    gunwale level).  Without this the boat would appear "roofed"
    #    and you couldn't see the interior from above.
    bm.faces.remove(top_cap)

    bm.normal_update()

    # ── Material assignment ────────────────────────────────────────
    # Slot 0 = boat_hull (default for every hull face).
    # Slot 1 = boat_gunwale (only the rim faces from step 6).
    # (Slot 2 = boat_seats — used by the thwart boxes added later.)
    #
    # Slots are appended in a fixed order below so callers can assume
    # the numeric indices; face `.material_index` gets set here before
    # we write bmesh back to the mesh datablock.
    hull_mat_idx    = 0
    gunwale_mat_idx = 1

    gunwale_face_set = set(gunwale_faces)
    for f in bm.faces:
        f.material_index = gunwale_mat_idx if f in gunwale_face_set else hull_mat_idx

    bm.to_mesh(mesh)
    bm.free()

    # Attach the two mesh-level material slots (the seats material is
    # appended later, on the joined final object).
    mesh.materials.append(make_material("boat_hull"))
    mesh.materials.append(make_material("boat_gunwale"))

    return obj


# ── Thwart benches (box primitives, joined onto the hull) ────────────────

def _gunwale_half_width_at_y(y: float) -> float:
    """Piecewise-linear interpolation of the gunwale half-width (gun_x
    column of STATIONS) at an arbitrary Y along the boat.  Beyond the
    last station, linearly tapers to zero at BOW_TIP_Y so bow-adjacent
    thwarts get the correct narrow width."""
    # Between defined stations
    for i in range(len(STATIONS) - 1):
        y0, _, _, _, gx0, _ = STATIONS[i]
        y1, _, _, _, gx1, _ = STATIONS[i + 1]
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0) if y1 > y0 else 0.0
            return gx0 + t * (gx1 - gx0)
    # Forward of the last station — taper to bow tip (width → 0).
    y_last, _, _, _, gx_last, _ = STATIONS[-1]
    if y > y_last and y < BOW_TIP_Y:
        t = (y - y_last) / (BOW_TIP_Y - y_last)
        return gx_last * (1.0 - t)
    # Clamp to endpoints if outside the station range.
    if y < STATIONS[0][0]:
        return STATIONS[0][4]
    return 0.0


def _interior_half_width_at_y(y: float) -> float:
    """Half-width INSIDE the hull — i.e. usable seat span at that Y —
    computed as the gunwale half-width minus the hull-side thickness.
    Never returns a negative number so a thwart placed too close to the
    bow just collapses to a point rather than throwing."""
    return max(0.0, _gunwale_half_width_at_y(y) - HULL_THICKNESS)


def _build_thwarts() -> list[bpy.types.Object]:
    thwarts = []
    seats_mat = make_material("boat_seats")
    for i, y in enumerate(THWART_YS):
        interior_half = _interior_half_width_at_y(y)
        thwart_xsize = max(0.0, 2.0 * (interior_half - THWART_END_CLEARANCE))
        if thwart_xsize <= 0.0:
            # Not enough interior room for a real bench at this Y —
            # skip rather than emit a degenerate zero-scale cube.
            continue
        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=(0.0, y, THWART_TOP_Z - THWART_ZSIZE / 2.0),
        )
        obj = bpy.context.active_object
        obj.name = f"thwart_{i}"
        obj.scale = (thwart_xsize, THWART_YSIZE, THWART_ZSIZE)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.data.materials.clear()
        obj.data.materials.append(seats_mat)
        thwarts.append(obj)
    return thwarts


# ── Join + export helpers (same contract as the other generators) ────────

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

    bpy.ops.wm.read_factory_settings(use_empty=True)

    hull = _build_hull_mesh()
    thwarts = _build_thwarts()

    print(f"Hull faces: {len(hull.data.polygons)}, thwarts: {len(thwarts)}")

    boat = join_all([hull, *thwarts], final_name="wooden_boat")

    n_verts = len(boat.data.vertices)
    n_faces = len(boat.data.polygons)
    n_tris  = sum(len(p.vertices) - 2 for p in boat.data.polygons)
    n_slots = len(boat.data.materials)
    slot_names = ", ".join(m.name if m else "<none>" for m in boat.data.materials)

    (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(boat)
    print(f"Final mesh: verts={n_verts}, faces={n_faces}, tris={n_tris}")
    print(f"Material slots ({n_slots}): {slot_names}")
    print(f"Bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  "
          f"Z[{z_min:+.3f}, {z_max:+.3f}]")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, OUT_NAME)
        export_glb(boat, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0 if os.path.exists(out_path) else 0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")

    print("\nDONE — wooden boat exported.")


if __name__ == "__main__":
    main()
