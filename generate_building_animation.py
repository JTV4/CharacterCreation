"""
generate_building_animation.py
==============================
Split BuildingNWhole GLBs into modular construction pieces (no Z-bisect)
and emit multi-node GLBs + JSON manifests for staggered drop-in playback
in the Building Viewer.

Inspired by Winter Cats' modular Unity assemble approach: pieces animate
individually into place rather than height-sliced meshes.

Default buildings: Cooking(1), Bank(2), Apothecary(3), Merchant(4),
Forge(5), Workshop(6), Manufacturing(7), Sheep Fence(9), Cow Fence(10).
Pass `-- 8` for Chronocrafting, or `-- all`.

Outputs per building N:
  viewer/public/buildings/Construction/Building{N}Animation_Modular.glb
  viewer/public/buildings/Construction/building{N}_animation_manifest.json
  (~/Desktop/Models/Buildings/Construction/ mirrors)

Sheep Fence (9) writes SheepFenceAnimation_Modular.glb + SheepFence_INIT.glb.
Cow Fence (10) writes CowFenceAnimation_Modular.glb + CowFence_INIT.glb.
Forge (5) also writes legacy BuildingAnimation_Modular.glb names used by
the existing "Building Animation" sidebar entry.

Stages (viewer bookmarks, 10 total):
  1 INIT       — resource piles only (no dirt pad / building mesh)
  2 foundation — authored floor first
  3–10         — walls → gable → framing → eaves → roof complete

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_building_animation.py
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_building_animation.py -- 1 2 3
"""

from __future__ import annotations

import json
import math
import os
import re
import sys

import bmesh
import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
VIEWER_OUT = os.path.join(VIEWER_DIR, "Construction")
DESKTOP_OUT = os.path.expanduser("~/Desktop/Models/Buildings/Construction")
DECODED_DIR = os.path.expanduser(
    "~/Desktop/Buildings/NewBuildings/Completed_decoded"
)
COMPLETED_DIR = os.path.expanduser(
    "~/Desktop/Buildings/NewBuildings/Completed"
)

os.makedirs(VIEWER_OUT, exist_ok=True)
os.makedirs(DESKTOP_OUT, exist_ok=True)

DROP_Z = 2.8
OUTWARD = 0.55
# Merge micro debris (common after authored wood-trim atlases) so stages
# don't unlock hundreds of 4-vert shards.
MIN_PIECE_VERTS = 24

# Resource piles for Site Prep INIT (same set as Whole construction INITs).
INIT_PILE_PATHS = {
    "sycamore_logs": os.path.join(VIEWER_DIR, "LogPile_Sycamore.glb"),
    "iron_ore": os.path.join(VIEWER_DIR, "OrePile_Iron.glb"),
    "raw_catfish": os.path.join(VIEWER_DIR, "RawFishPile_Catfish.glb"),
    "cooked_catfish": os.path.join(VIEWER_DIR, "FishPile_Catfish.glb"),
    "clay": os.path.join(VIEWER_DIR, "Clay.glb"),
    "grind_coins": os.path.join(VIEWER_DIR, "CoinPile_Grind.glb"),
}
# (key, name, nx, ny, yaw, uniform_scale) — fractions of half-width/depth
# Compact layout; export_site_prep_init also clamps each pile into footprint.
INIT_PILE_LAYOUT = [
    ("sycamore_logs", "pile_sycamore_logs", -0.32, -0.32, 0.0, 0.28),
    ("iron_ore", "pile_iron_ore", 0.32, -0.30, 0.2, 0.28),
    ("clay", "pile_clay", -0.38, 0.32, 0.1, 0.40),
    ("grind_coins", "pile_grind_coins", 0.00, 0.36, 0.35, 0.38),
    ("raw_catfish", "pile_raw_catfish", 0.26, 0.36, 0.5, 0.38),
    ("cooked_catfish", "pile_cooked_catfish", 0.42, 0.32, -0.4, 0.38),
]

# Default roll-out: Cooking→Manufacturing + Sheep Fence (9) + Cow Fence (10).
# Chronocrafting (8) remains available via `-- 8` / `-- all`.
DEFAULT_IDS = (1, 2, 3, 4, 5, 6, 7, 9, 10)

BUILDING_META: dict[int, dict[str, str]] = {
    1: {"structureName": "Cooking Animation", "slug": "cooking"},
    2: {"structureName": "Bank Animation", "slug": "bank"},
    3: {"structureName": "Apothecary Animation", "slug": "apothecary"},
    4: {"structureName": "Merchant Animation", "slug": "merchant"},
    5: {"structureName": "Building Animation", "slug": "forge"},
    6: {"structureName": "Workshop Animation", "slug": "workshop"},
    7: {"structureName": "Manufacturing Animation", "slug": "manufacturing"},
    8: {"structureName": "Chronocrafting Animation", "slug": "chronocrafting"},
    9: {
        "structureName": "Sheep Fence Animation",
        "slug": "sheep_fence",
        "sourceFile": "SheepFence.glb",
        "outGlb": "SheepFenceAnimation_Modular.glb",
        "outManifest": "sheep_fence_animation_manifest.json",
        "initGlb": "SheepFence_INIT.glb",
    },
    10: {
        "structureName": "Cow Fence Animation",
        "slug": "cow_fence",
        "sourceFile": "CowFence.glb",
        "outGlb": "CowFenceAnimation_Modular.glb",
        "outManifest": "cow_fence_animation_manifest.json",
        "initGlb": "CowFence_INIT.glb",
    },
}

STAGE_ORDER = [
    "foundation",
    "walls_a",
    "walls_b",
    "walls_c",
    "walls_d",
    "gable",
    "framing",
    "eaves",
    "complete",
]


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def world_bounds(obj: bpy.types.Object):
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def find_walkable_floor_z(obj: bpy.types.Object) -> float | None:
    candidates: list[tuple[float, float]] = []
    for f in obj.data.polygons:
        if f.normal.z > 0.85:
            candidates.append((f.center.z, f.area))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    z_min_face = candidates[0][0]
    band = [(z, a) for z, a in candidates if z <= z_min_face + 0.35]
    band.sort(key=lambda t: -t[1])
    return band[0][0]


def bake_trs(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def pack_images() -> None:
    for img in bpy.data.images:
        if img.packed_file is None and img.filepath:
            try:
                img.pack()
            except Exception as exc:
                print(f"  warn pack {img.name}: {exc}")


def classify_material(mat_name: str) -> str:
    n = (mat_name or "").lower()
    if any(k in n for k in ("roundtile", "round_tile", "roof", "shingle")):
        return "Roof"
    if "tile" in n and "floor" not in n and "wall" not in n:
        return "Roof"
    if any(k in n for k in ("forgediron", "forged_iron", "iron")):
        return "Trim"
    if any(k in n for k in ("woodtrim", "wood_trim", "trim", "beam", "timber")):
        return "Trim"
    if any(k in n for k in ("pasturewood", "fence", "rail", "post")):
        return "Wall"
    if "wood" in n and "plaster" not in n:
        return "Trim"
    if any(k in n for k in ("unevenbrick", "brick", "stone", "cobble", "floor")):
        return "Brick"
    if "plaster" in n or "stucco" in n or "wall" in n:
        return "Wall"
    return "Wall"


def upward_face_ratio(obj: bpy.types.Object) -> float:
    up = 0.0
    total = 0.0
    for f in obj.data.polygons:
        total += f.area
        # Object-space normal is fine after bake_trs
        if f.normal.z > 0.7:
            up += f.area
    return (up / total) if total > 1e-8 else 0.0


def looks_like_floor(obj: bpy.types.Object, *, relaxed: bool = False) -> bool:
    """Detect walkable floor slabs by shape (wide, thin, near ground)."""
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(obj)
    height = z1 - z0
    span_x = x1 - x0
    span_y = y1 - y0
    area = span_x * span_y
    zc = 0.5 * (z0 + z1)
    # Degenerate strips / proxy leftovers aren't real floors.
    if span_x < 1.2 or span_y < 1.2:
        return False
    if z0 > (0.9 if relaxed else 0.55):
        return False
    if height > (1.6 if relaxed else 1.15):
        return False
    if area < (1.5 if relaxed else 2.5):
        return False
    up = upward_face_ratio(obj)
    if height <= 0.55 and area >= 3.0 and zc <= 0.7:
        return True
    if up >= (0.35 if relaxed else 0.45) and height <= 1.25 and zc <= 0.85:
        return True
    if relaxed and up >= 0.25 and height <= 1.5 and area >= 4.0 and z0 <= 0.25:
        return True
    return False


def face_is_walkable_floor(
    obj: bpy.types.Object,
    poly: bpy.types.MeshPolygon,
    *,
    z_max: float = 0.45,
    z_min: float = -0.15,
    up_dot: float = 0.65,
) -> bool:
    """True for top/underside faces of the authored ground slab (Z-up)."""
    mw = obj.matrix_world
    c = mw @ poly.center
    n = (mw.to_3x3() @ poly.normal).normalized()
    if c.z > z_max or c.z < z_min:
        return False
    if n.z >= up_dot:
        return True
    # Underside of a thin floor board / slab.
    if n.z <= -up_dot and c.z <= 0.30:
        return True
    return False


def _mat_allows_floor_extract(mat_hint: str) -> bool:
    n = (mat_hint or "").lower()
    if any(k in n for k in ("glass", "metal", "ornament", "window", "roundtile")):
        return False
    if classify_material(mat_hint) == "Roof":
        return False
    # Floors are usually wood / brick / plaster / stone sharing a trim atlas.
    return any(
        k in n
        for k in (
            "wood",
            "brick",
            "floor",
            "plank",
            "stone",
            "plaster",
            "rock",
            "cobble",
            "tile",
        )
    )


def classify_piece(obj: bpy.types.Object, mat_hint: str) -> str:
    name_l = (obj.name or "").lower()
    # Honor true Floor/Door/Roof nodes — not Meshy "Floor_WoodDark" atlases.
    if re.match(r"^door(\.\d+)?$", name_l) or name_l.startswith("door_"):
        return "Wall"  # keep with wall stages but never destroy
    if (
        re.match(r"^floor(\.\d+)?$", name_l)
        or name_l.startswith("floor_extracted")
        or name_l.startswith("floor_slab")
        or name_l.startswith("floor_from")
        or name_l.startswith("floor_authored")
        or name_l.startswith("floor_reclass")
        or name_l.startswith("floor_merged")
        or name_l.startswith("ba_floor")
    ):
        return "Floor"
    if re.match(r"^roof(\.\d+)?$", name_l) or name_l.startswith("roof_"):
        # Avoid Roof_Tiles matching as roof when it's actually a material mesh
        # name — only honor clean Roof / Roof.001 or roof_* module names.
        if not any(
            k in name_l
            for k in ("wood", "trim", "plaster", "brick", "tile_detail")
        ):
            return "Roof"

    (_x), (_y), (z0, z1) = world_bounds(obj)
    zc = 0.5 * (z0 + z1)
    height = z1 - z0
    kind = classify_material(mat_hint)

    # Geometry wins for clear floor slabs (matches Forge BA_Floor_* first).
    if looks_like_floor(obj):
        return "Floor"

    if kind == "Roof":
        if looks_like_floor(obj, relaxed=True):
            return "Floor"
        return "Roof"
    if kind == "Trim":
        if looks_like_floor(obj, relaxed=True):
            return "Floor"
        return "Trim"
    if kind == "Brick":
        if zc < 0.65 and height < 1.3:
            return "Floor"
        return "Wall"
    if zc < 0.4 and height < 0.7:
        return "Floor"
    return "Wall"


def add_proxy_floor(
    pieces: list[tuple[bpy.types.Object, str]],
) -> list[tuple[bpy.types.Object, str]]:
    """Last-resort thin slab — only if authored floor faces cannot be found."""
    if not pieces:
        return pieces
    xs: list[float] = []
    ys: list[float] = []
    for o, _h in pieces:
        (x0, x1), (y0, y1), (_z0, _z1) = world_bounds(o)
        xs.extend([x0, x1])
        ys.extend([y0, y1])
    pad = 0.05
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    sx = max(0.5, (max(xs) - min(xs)) + pad)
    sy = max(0.5, (max(ys) - min(ys)) + pad)
    thick = 0.08

    mat = None
    for o, hint in pieces:
        hl = hint.lower()
        if any(k in hl for k in ("brick", "floor", "wood", "stone", "plaster")):
            if o.data.materials:
                mat = o.data.materials[0]
                break
    if mat is None:
        for o, _h in pieces:
            if o.data.materials:
                mat = o.data.materials[0]
                break

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(cx, cy, thick * 0.5))
    floor = bpy.context.active_object
    floor.name = "BA_Floor_proxy"
    floor.scale = (sx, sy, thick)
    bake_trs(floor)
    if mat is not None:
        floor.data.materials.clear()
        floor.data.materials.append(mat)
    print(f"  WARN proxy floor {sx:.2f}×{sy:.2f}×{thick:.2f} (no authored floor found)")
    return [(floor, mat.name if mat else "proxy_floor")] + list(pieces)


def _floor_footprint_ok(obj: bpy.types.Object) -> bool:
    (x0, x1), (y0, y1), (_z0, _z1) = world_bounds(obj)
    return (x1 - x0) >= 1.5 and (y1 - y0) >= 1.5


def extract_authored_floor_faces(
    pieces: list[tuple[bpy.types.Object, str]],
    *,
    z_max: float = 0.45,
    min_area: float = 2.0,
) -> list[tuple[bpy.types.Object, str]]:
    """Separate walkable ground faces from mixed wood/trim/wall atlases.

    Many Whole buildings paint the floor with the same material as vertical
    trim, so material-only splits leave no Floor piece and we used to invent
    a proxy cube.  Pulling near-ground upward faces keeps the real flooring.
    """
    kept: list[tuple[bpy.types.Object, str]] = []
    extracted: list[tuple[bpy.types.Object, str]] = []

    for o, hint in pieces:
        if len(o.data.polygons) == 0:
            kept.append((o, hint))
            continue

        # Already a clean floor slab — don't peel it further.
        if looks_like_floor(o) and _floor_footprint_ok(o):
            if "floor" not in (o.name or "").lower():
                o.name = f"Floor_slab_{hint[:18]}"
            kept.append((o, hint))
            continue

        if not _mat_allows_floor_extract(hint):
            kept.append((o, hint))
            continue

        floor_area = sum(
            p.area for p in o.data.polygons if face_is_walkable_floor(o, p, z_max=z_max)
        )
        if floor_area < min_area:
            kept.append((o, hint))
            continue

        floor_count = sum(
            1 for p in o.data.polygons if face_is_walkable_floor(o, p, z_max=z_max)
        )
        if floor_count == len(o.data.polygons):
            o.name = f"Floor_from_{hint[:20]}"
            extracted.append((o, hint))
            print(f"  floor extract: whole {o.name} area≈{floor_area:.1f} ({hint})")
            continue

        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        for p in o.data.polygons:
            p.select = face_is_walkable_floor(o, p, z_max=z_max)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.separate(type="SELECTED")
        bpy.ops.object.mode_set(mode="OBJECT")

        new_objs = [
            obj
            for obj in bpy.context.selected_objects
            if obj.type == "MESH" and obj != o
        ]
        if not new_objs:
            kept.append((o, hint))
            continue

        floor_obj = new_objs[0]
        floor_obj.name = f"Floor_extracted_{hint[:16]}"
        if not _floor_footprint_ok(floor_obj):
            # Too small / strip — merge back by joining into original.
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            floor_obj.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.join()
            kept.append((o, hint))
            print(f"  floor extract: rejected thin peel from {hint}")
            continue

        extracted.append((floor_obj, hint))
        print(
            f"  floor extract: {floor_obj.name} area≈{floor_area:.1f} "
            f"verts={len(floor_obj.data.vertices)} ({hint})"
        )
        if len(o.data.vertices) >= 3 and len(o.data.polygons) >= 1:
            kept.append((o, hint))
        else:
            bpy.data.objects.remove(o, do_unlink=True)

    if not extracted:
        return kept

    if len(extracted) == 1:
        return extracted + kept

    hint0 = extracted[0][1]
    joined = join_objects([o for o, _h in extracted], "Floor_authored")
    print(f"  floor extract: joined {len(extracted)} peels → {joined.name}")
    return [(joined, hint0)] + kept


def ensure_floor_pieces(
    pieces: list[tuple[bpy.types.Object, str]],
) -> list[tuple[bpy.types.Object, str]]:
    """Guarantee foundation uses each building's authored floor (no proxy first).

    Destructive horizontal bisects punched holes in walls — we only reclassify
    or peel upward near-ground faces from shared trim/wood atlases.
    """
    pieces = extract_authored_floor_faces(pieces, z_max=0.45, min_area=2.0)

    classified = [(o, h, classify_piece(o, h)) for o, h in pieces]
    floors = [
        (o, h)
        for o, h, c in classified
        if c == "Floor" and _floor_footprint_ok(o)
    ]
    if floors:
        return [(o, h) for o, h, _c in classified]

    # Soft reclassify whole slab-like pieces (no mesh edits).
    out: list[tuple[bpy.types.Object, str]] = []
    found = False
    for o, h, c in classified:
        if (
            not found
            and c != "Roof"
            and looks_like_floor(o, relaxed=True)
            and _floor_footprint_ok(o)
        ):
            print(f"  reclassify {o.name} → Floor (relaxed slab, no cut)")
            if "floor" not in (o.name or "").lower():
                o.name = f"Floor_reclass_{h[:16]}"
            found = True
        out.append((o, h))
    if found:
        return out

    # One more peel with a slightly taller band (thick plank floors).
    print("  floor extract: retry with z_max=0.70")
    out = extract_authored_floor_faces(out, z_max=0.70, min_area=1.5)
    classified = [(o, h, classify_piece(o, h)) for o, h in out]
    floors = [
        (o, h)
        for o, h, c in classified
        if c == "Floor" and _floor_footprint_ok(o)
    ]
    if floors:
        return [(o, h) for o, h, _c in classified]

    # Honor extracted object names even if classify_piece is unsure.
    named = False
    final: list[tuple[bpy.types.Object, str]] = []
    for o, h in out:
        if not named and "floor" in (o.name or "").lower() and _floor_footprint_ok(o):
            named = True
        final.append((o, h))
    if named:
        return final

    print("  no authored floor faces found — proxy fallback")
    return add_proxy_floor(out)


def _is_wallish_mat(mat_name: str) -> bool:
    n = (mat_name or "").lower()
    if any(k in n for k in ("tile", "glass", "metal", "ornament")):
        return False
    return any(
        k in n
        for k in ("brick", "plaster", "stone", "rock", "cobble", "uneven", "stucco")
    )


def _is_eave_wood_mat(mat_name: str) -> bool:
    n = (mat_name or "").lower()
    if "tile" in n:
        return False
    return any(k in n for k in ("wood", "trim", "beam", "timber"))


def seal_under_eave_lintels(
    pieces: list[tuple[bpy.types.Object, str]],
) -> list[tuple[bpy.types.Object, str]]:
    """Fill authored gaps between wall tops / door arches and eaves wood.

    Forge / Manufacturing / similar Whole meshes leave a rectangular void at
    the top-center of each doorway (and sometimes a thin under-eave band on
    each facade).  The modular split preserves that hole 1:1 — this patches
    it with thin stone panels merged into the primary wall piece.
    """
    if not pieces:
        return pieces

    faces: list[tuple[Vector, str]] = []
    for o, hint in pieces:
        mw = o.matrix_world
        for p in o.data.polygons:
            mat = (
                o.data.materials[p.material_index].name
                if o.data.materials
                else hint
            )
            faces.append((mw @ p.center, mat))

    wallish = [(c, m) for c, m in faces if _is_wallish_mat(m)]
    # Eaves fascia only — ignore vertical jambs / floor boards (those pull
    # wood_min down and hide real lintel gaps).
    wood = [
        (c, m)
        for c, m in faces
        if _is_eave_wood_mat(m) and 2.55 <= c.z <= 3.35
    ]
    if not wallish or not wood:
        print("  under-eave seal: skip (no wall/wood faces)")
        return pieces

    host_obj: bpy.types.Object | None = None
    host_mat = None
    best = -1
    for o, hint in pieces:
        if not _is_wallish_mat(hint):
            continue
        score = len(o.data.polygons)
        hl = hint.lower()
        if any(k in hl for k in ("uneven", "brick", "stone", "cobble", "plaster")):
            score += 10_000
        # RockTrim is often a thin ledge — prefer real wall skins as host.
        if "rocktrim" in hl or "rock_trim" in hl:
            score -= 5_000
        if score > best:
            best = score
            host_obj = o
            host_mat = o.data.materials[0] if o.data.materials else None
    if host_obj is None:
        print("  under-eave seal: skip (no wall host)")
        return pieces

    x0 = min(c.x for c, _ in wallish)
    x1 = max(c.x for c, _ in wallish)
    y0 = min(c.y for c, _ in wallish)
    y1 = max(c.y for c, _ in wallish)
    step = 0.12

    def cluster_spans(
        vals: list[float],
        wall_pred,
        wood_pred,
    ) -> list[tuple[float, float, float, float]]:
        cols: list[tuple[float, float, float]] = []
        for t in vals:
            wall_zs = [c.z for c, _ in wallish if wall_pred(c, t)]
            wood_zs = [c.z for c, _ in wood if wood_pred(c, t)]
            if not wall_zs or not wood_zs:
                continue
            wmax = max(wall_zs)
            wmin = min(wood_zs)
            gap = wmin - wmax
            # Thin under-eave / door-lintel voids only (not open timber bays).
            if gap < 0.12 or gap > 0.75 or wmax < 2.20:
                continue
            # Prefer doorway columns (no mid-wall) so we seal lintels, not
            # random facade recesses.
            has_mid = any(
                1.0 < c.z < 2.15 for c, _ in wallish if wall_pred(c, t)
            )
            if has_mid and gap < 0.28:
                continue
            cols.append((t, wmax, wmin))
        if not cols:
            return []
        cols.sort(key=lambda c: c[0])
        groups: list[list[tuple[float, float, float]]] = [[cols[0]]]
        for col in cols[1:]:
            if col[0] - groups[-1][-1][0] <= step * 2.5:
                groups[-1].append(col)
            else:
                groups.append([col])
        spans: list[tuple[float, float, float, float]] = []
        for g in groups:
            t0, t1 = g[0][0], g[-1][0]
            width = (t1 - t0) + step
            if width < step * 0.5 or width > 8.0:
                continue
            # Single-sample hits are common at arch centers — widen to a
            # readable lintel panel so the hole actually closes.
            min_visual = 0.70
            if width < min_visual:
                pad = 0.5 * (min_visual - width)
                t0 -= pad
                t1 += pad
                width = t1 - t0
            z0 = min(c[1] for c in g) - 0.03
            z1 = min(max(c[2] for c in g) + 0.02, z0 + 0.70)
            if z1 - z0 < 0.10:
                continue
            spans.append((t0, t1, z0, z1))
        return spans

    xs = [x0 + i * step for i in range(int((x1 - x0) / step) + 1)]
    ys = [y0 + i * step for i in range(int((y1 - y0) / step) + 1)]
    margin = 0.35
    facade_jobs = [
        (
            "+Y",
            cluster_spans(
                xs,
                lambda c, t: abs(c.x - t) < step and c.y > y1 - margin,
                lambda c, t: abs(c.x - t) < step and c.y > y1 - margin - 0.15,
            ),
            "x",
            y1,
            -1.0,
        ),
        (
            "-Y",
            cluster_spans(
                xs,
                lambda c, t: abs(c.x - t) < step and c.y < y0 + margin,
                lambda c, t: abs(c.x - t) < step and c.y < y0 + margin + 0.15,
            ),
            "x",
            y0,
            1.0,
        ),
        (
            "+X",
            cluster_spans(
                ys,
                lambda c, t: abs(c.y - t) < step and c.x > x1 - margin,
                lambda c, t: abs(c.y - t) < step and c.x > x1 - margin - 0.15,
            ),
            "y",
            x1,
            -1.0,
        ),
        (
            "-X",
            cluster_spans(
                ys,
                lambda c, t: abs(c.y - t) < step and c.x < x0 + margin,
                lambda c, t: abs(c.y - t) < step and c.x < x0 + margin + 0.15,
            ),
            "y",
            x0,
            1.0,
        ),
    ]

    depth = 0.20
    fillers: list[bpy.types.Object] = []
    for name, spans, axis, plane, inward in facade_jobs:
        for t0, t1, z0, z1 in spans:
            width = t1 - t0
            height = z1 - z0
            cz = 0.5 * (z0 + z1)
            ct = 0.5 * (t0 + t1)
            # Sit just inside the outer wall plane so it reads as wall fill.
            c_plane = plane + inward * (depth * 0.45)
            if axis == "x":
                loc = (ct, c_plane, cz)
                scale = (width, depth, height)
            else:
                loc = (c_plane, ct, cz)
                scale = (depth, width, height)
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
            filler = bpy.context.active_object
            filler.name = f"BA_LintelSeal_{name}"
            filler.scale = scale
            bake_trs(filler)
            if host_mat is not None:
                filler.data.materials.clear()
                filler.data.materials.append(host_mat)
            fillers.append(filler)
            print(
                f"  under-eave seal {name}: "
                f"{width:.2f}×{height:.2f} at {axis}=[{t0:.2f},{t1:.2f}] "
                f"z=[{z0:.2f},{z1:.2f}]"
            )

    if not fillers:
        print("  under-eave seal: no gaps detected")
        return pieces

    bpy.ops.object.select_all(action="DESELECT")
    host_obj.select_set(True)
    for f in fillers:
        f.select_set(True)
    bpy.context.view_layer.objects.active = host_obj
    bpy.ops.object.join()
    print(f"  under-eave seal: merged {len(fillers)} panel(s) → {host_obj.name}")
    return pieces


def is_pasture_fence(meta: dict) -> bool:
    return meta.get("slug") in ("sheep_fence", "cow_fence")


def separate_by_material(obj: bpy.types.Object) -> list[bpy.types.Object]:
    if not obj.data.materials or len(obj.data.materials) <= 1:
        return [obj]

    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="MATERIAL")
    bpy.ops.object.mode_set(mode="OBJECT")
    separated = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    return separated if separated else [obj]


def separate_loose(obj: bpy.types.Object) -> list[bpy.types.Object]:
    """Explode a joined fence mesh into disconnected board/post islands."""
    if obj.type != "MESH" or len(obj.data.vertices) < 3:
        return [obj]
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    separated = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    return separated if separated else [obj]


# CowFence.glb stores the full pasture as a few atlas materials whose
# boards are disconnected islands. Cluster them into ~bay-sized sections
# so the modular walk matches Sheep Fence (one panel group per stagger).
FENCE_BAY_SPAN = 4.2


def explode_and_cluster_fence_bays(
    pieces: list[tuple[bpy.types.Object, str]],
    max_span: float = FENCE_BAY_SPAN,
) -> list[tuple[bpy.types.Object, str]]:
    islands: list[tuple[bpy.types.Object, str]] = []
    for o, hint in pieces:
        for part in separate_loose(o):
            if len(part.data.vertices) < 3:
                bpy.data.objects.remove(part, do_unlink=True)
                continue
            bake_trs(part)
            islands.append((part, hint))
    if not islands:
        return pieces
    print(f"  cow fence: {len(islands)} loose islands → clustering bays")

    recs: list[dict] = []
    for o, hint in islands:
        c = piece_centroid(o)
        recs.append({"obj": o, "hint": hint, "cx": c.x, "cy": c.y})
    cx = sum(r["cx"] for r in recs) / len(recs)
    cy = sum(r["cy"] for r in recs) / len(recs)
    recs.sort(key=lambda r: math.atan2(r["cy"] - cy, r["cx"] - cx))

    clusters: list[list[dict]] = [[recs[0]]]
    for r in recs[1:]:
        cur = clusters[-1]
        xs = [p["cx"] for p in cur] + [r["cx"]]
        ys = [p["cy"] for p in cur] + [r["cy"]]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        prev = cur[-1]
        jump = math.hypot(r["cx"] - prev["cx"], r["cy"] - prev["cy"])
        if span > max_span or jump > max_span * 1.35:
            clusters.append([r])
        else:
            cur.append(r)

    if len(clusters) > 1:
        first, last = clusters[0], clusters[-1]
        p0, p1 = first[0], last[-1]
        jump = math.hypot(p0["cx"] - p1["cx"], p0["cy"] - p1["cy"])
        xs = [p["cx"] for p in first + last]
        ys = [p["cy"] for p in first + last]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        if jump < max_span * 1.1 and span <= max_span * 1.15:
            clusters[0] = last + first
            clusters.pop()

    result: list[tuple[bpy.types.Object, str]] = []
    for i, cluster in enumerate(clusters):
        objs = [p["obj"] for p in cluster]
        if len(objs) == 1:
            result.append((objs[0], cluster[0]["hint"]))
            continue
        merged = join_objects(objs, f"FenceBay_{i:02d}")
        bake_trs(merged)
        result.append((merged, "Wall"))
    print(f"  cow fence: {len(result)} bay pieces")
    return result


def cluster_by_xy_quadrant(obj: bpy.types.Object, min_verts: int = 40) -> list[bpy.types.Object]:
    if len(obj.data.vertices) < min_verts:
        return [obj]

    (x0, x1), (y0, y1), (_z0, _z1) = world_bounds(obj)
    cx = 0.5 * (x0 + x1)
    cy = 0.5 * (y0 + y1)
    span = max(x1 - x0, y1 - y0)
    if span < 1.5:
        return [obj]

    me = obj.data
    world = obj.matrix_world.copy()
    mats = list(obj.data.materials)

    counts = [0, 0, 0, 0]
    for v in me.vertices:
        w = world @ v.co
        qi = (0 if w.x < cx else 1) + (0 if w.y < cy else 2)
        counts[qi] += 1
    if sum(1 for c in counts if c > 0) <= 1:
        return [obj]

    results: list[bpy.types.Object] = []
    for qi in range(4):
        if counts[qi] == 0:
            continue
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        to_delete = []
        for v in bm.verts:
            w = world @ v.co
            vqi = (0 if w.x < cx else 1) + (0 if w.y < cy else 2)
            if vqi != qi:
                to_delete.append(v)
        if len(to_delete) == len(bm.verts):
            bm.free()
            continue
        bmesh.ops.delete(bm, geom=to_delete, context="VERTS")
        if len(bm.verts) == 0:
            bm.free()
            continue
        new_me = bpy.data.meshes.new(f"{obj.name}_Q{qi}_mesh")
        bm.to_mesh(new_me)
        bm.free()
        new_obj = bpy.data.objects.new(f"{obj.name}_Q{qi}", new_me)
        bpy.context.collection.objects.link(new_obj)
        new_obj.matrix_world = world
        for mat in mats:
            new_obj.data.materials.append(mat)
        bake_trs(new_obj)
        results.append(new_obj)

    if not results:
        return [obj]
    bpy.data.objects.remove(obj, do_unlink=True)
    return results


def export_pieces(pieces: list[bpy.types.Object], path: str) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for o in pieces:
        o.select_set(True)
        o.hide_set(False)
    bpy.context.view_layer.objects.active = pieces[0]
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
    )


def piece_centroid(obj: bpy.types.Object) -> Vector:
    (x0, x1), (y0, y1), (z0, z1) = world_bounds(obj)
    return Vector((0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1)))


def even_batches(items: list[str], n_batches: int) -> list[list[str]]:
    """Split items into n_batches contiguous chunks (some may be empty)."""
    if n_batches <= 0:
        return []
    if not items:
        return [[] for _ in range(n_batches)]
    out: list[list[str]] = [[] for _ in range(n_batches)]
    for i, item in enumerate(items):
        # Fill early stages first when fewer pieces than batches
        idx = min(i, n_batches - 1) if len(items) <= n_batches else i * n_batches // len(items)
        # Contiguous chunking for len > n_batches
        if len(items) > n_batches:
            idx = min(n_batches - 1, i * n_batches // len(items))
        out[idx].append(item)
    # Contiguous re-chunk (cleaner progression)
    if len(items) > n_batches:
        size = math.ceil(len(items) / n_batches)
        out = [items[i : i + size] for i in range(0, len(items), size)]
        while len(out) < n_batches:
            out.append([])
        out = out[:n_batches]
    return out


def order_sheep_fence_perimeter(
    pieces: list[tuple[str, str, bpy.types.Object]],
) -> list[str]:
    """Walk the pasture fence starting west of the gate, CCW, gate last.

    Layout (approx): rectangular run with the forged-iron gate on the
    south edge.  Build order:
      hinge post → south-west run → west → north → east → south-east run → gate.
    """
    recs: list[dict] = []
    for pid, cat, obj in pieces:
        c = piece_centroid(obj)
        (x0, x1), (y0, y1), (_z0, _z1) = world_bounds(obj)
        mat = (
            obj.data.materials[0].name
            if obj.data.materials
            else ""
        ).lower()
        recs.append(
            {
                "id": pid,
                "cat": cat,
                "cx": c.x,
                "cy": c.y,
                "sx": x1 - x0,
                "sy": y1 - y0,
                "mat": mat,
            }
        )
    if not recs:
        return []

    iron = [r for r in recs if "iron" in r["mat"]]
    if not iron:
        # Fallback: southernmost long piece as gate stand-in.
        iron = [min(recs, key=lambda r: r["cy"])]
    gate_cx = sum(r["cx"] for r in iron) / len(iron)
    gate_cy = sum(r["cy"] for r in iron) / len(iron)

    # Gate leaf: long wood panel on the south edge near the iron.
    gate_leaf = [
        r
        for r in recs
        if r not in iron
        and r["cy"] < gate_cy + 0.8
        and abs(r["cx"] - gate_cx) < 1.2
        and r["sx"] > 2.0
    ]
    gate_ids = {r["id"] for r in iron + gate_leaf}

    # Hinge / start post: small south post just west of the gate opening.
    start_post = None
    candidates = [
        r
        for r in recs
        if r["id"] not in gate_ids
        and r["cy"] < gate_cy + 0.8
        and r["cx"] < gate_cx
        and r["sx"] < 0.6
        and r["sy"] < 0.6
    ]
    if candidates:
        start_post = max(candidates, key=lambda r: r["cx"])  # closest to gate
        gate_ids.add(start_post["id"])  # placed at the very start, not in peri sort

    peri = [r for r in recs if r["id"] not in gate_ids]
    if start_post:
        # start_post is in gate_ids so removed from peri — good
        pass

    ys = [r["cy"] for r in peri]
    xs = [r["cx"] for r in peri]
    y_min, y_max = min(ys), max(ys)
    x_min, x_max = min(xs), max(xs)
    y_span = max(0.5, y_max - y_min)
    x_span = max(0.5, x_max - x_min)
    # Edge bands (~18% of span from each side)
    band_y = 0.18 * y_span
    band_x = 0.18 * x_span

    south = [r for r in peri if r["cy"] <= y_min + band_y]
    north = [r for r in peri if r["cy"] >= y_max - band_y]
    west = [
        r
        for r in peri
        if r["cx"] <= x_min + band_x and r not in south and r not in north
    ]
    east = [
        r
        for r in peri
        if r["cx"] >= x_max - band_x and r not in south and r not in north
    ]
    # Anything missed (corners double-claimed already excluded) — append by angle.
    assigned = {r["id"] for r in south + north + west + east}
    leftover = [r for r in peri if r["id"] not in assigned]

    south_west = sorted(
        [r for r in south if r["cx"] < gate_cx], key=lambda r: -r["cx"]
    )  # nearest-to-gate first, then westward
    south_east = sorted(
        [r for r in south if r["cx"] >= gate_cx], key=lambda r: -r["cx"]
    )  # east corner → back toward gate
    west_run = sorted(west, key=lambda r: r["cy"])  # south → north
    north_run = sorted(north, key=lambda r: r["cx"])  # west → east
    east_run = sorted(east, key=lambda r: -r["cy"])  # north → south

    ordered: list[str] = []
    if start_post:
        ordered.append(start_post["id"])
    for run in (south_west, west_run, north_run, east_run, south_east):
        for r in run:
            if r["id"] not in ordered:
                ordered.append(r["id"])
    # Leftovers: insert by angle continuing the walk
    if leftover:
        cx = sum(r["cx"] for r in recs) / len(recs)
        cy = sum(r["cy"] for r in recs) / len(recs)
        start_ang = math.atan2(
            (start_post or south_west[0])["cy"] - cy,
            (start_post or south_west[0])["cx"] - cx,
        )

        def ang_key(r: dict) -> float:
            return (math.atan2(r["cy"] - cy, r["cx"] - cx) - start_ang) % (
                2 * math.pi
            )

        for r in sorted(leftover, key=ang_key):
            if r["id"] not in ordered:
                ordered.append(r["id"])

    # Gate closes the loop: wood leaf then iron fittings.
    for r in gate_leaf:
        if r["id"] not in ordered:
            ordered.append(r["id"])
    for r in iron:
        if r["id"] not in ordered:
            ordered.append(r["id"])

    # Any remaining (shouldn't happen)
    for r in recs:
        if r["id"] not in ordered:
            ordered.append(r["id"])

    print(
        "  sheep fence path: "
        + " → ".join(ordered[:4])
        + " … "
        + " → ".join(ordered[-3:])
    )
    return ordered


def order_cow_fence_perimeter(
    pieces: list[tuple[str, str, bpy.types.Object]],
) -> list[str]:
    """Walk the cow pasture fence starting at one gate post, CCW, other post last.

    CowFence.glb has no swinging gate (that's a separate Cow Gate structure).
    The west-side opening is the largest Euclidean gap on the angular loop.
    """
    recs: list[dict] = []
    for pid, cat, obj in pieces:
        c = piece_centroid(obj)
        recs.append({"id": pid, "cat": cat, "cx": c.x, "cy": c.y})
    if not recs:
        return []

    cx = sum(r["cx"] for r in recs) / len(recs)
    cy = sum(r["cy"] for r in recs) / len(recs)
    for r in recs:
        r["ang"] = math.atan2(r["cy"] - cy, r["cx"] - cx)
    recs.sort(key=lambda r: r["ang"])

    n = len(recs)
    best_gap = -1.0
    best_i = n - 1
    for i in range(n):
        a = recs[i]
        b = recs[(i + 1) % n]
        gap = math.hypot(b["cx"] - a["cx"], b["cy"] - a["cy"])
        if gap > best_gap:
            best_gap = gap
            best_i = i

    start = (best_i + 1) % n
    ordered = [recs[(start + k) % n]["id"] for k in range(n)]
    print(
        f"  cow fence path: gap={best_gap:.2f}m  "
        + " → ".join(ordered[:4])
        + " … "
        + " → ".join(ordered[-3:])
    )
    return ordered


def build_sheep_fence_manifest(
    pieces: list[tuple[str, str, bpy.types.Object]],
    *,
    source_name: str,
    structure_name: str,
) -> dict:
    """9 assembly stages walk the fence; INIT is separate site-prep."""
    path_ids = order_sheep_fence_perimeter(pieces)
    by_id = {pid: (pid, cat, obj) for pid, cat, obj in pieces}

    piece_defs = []
    stagger = 0
    for pid in path_ids:
        _pid, cat, obj = by_id[pid]
        c = piece_centroid(obj)
        ang = math.atan2(c.y, c.x)
        # Spawn from slightly outside the loop (radial outward).
        outward = Vector((c.x, c.y, 0.0))
        if outward.length > 1e-4:
            outward.normalize()
        else:
            outward = Vector((1.0, 0.0, 0.0))
        piece_defs.append(
            {
                "id": pid,
                "category": cat,
                "staggerIndex": stagger,
                "spawnOffset": [
                    round(outward.x * OUTWARD, 4),
                    round(outward.y * OUTWARD, 4),
                    round(DROP_Z, 4),
                ],
                "spawnYawDeg": round(8.0 * math.sin(ang * 2.0), 2),
                "durationSec": 0.40,
            }
        )
        stagger += 1

    # Stages 2–9 walk the perimeter; stage 10 (complete) hangs the gate.
    gate_tail: list[str] = []
    body = list(path_ids)
    # Gate leaf + iron are appended last by order_sheep_fence_perimeter.
    while body:
        pid = body[-1]
        _p, cat, obj = by_id[pid]
        mat = (
            obj.data.materials[0].name if obj.data.materials else ""
        ).lower()
        if "iron" in mat or cat == "Trim":
            gate_tail.insert(0, body.pop())
            continue
        # Wood gate leaf: final wood piece before iron (already at end).
        if not gate_tail and cat == "Wall":
            # Peek: if this is the long south leaf next to iron, take it.
            c = piece_centroid(obj)
            (x0, x1), (y0, y1), _z = world_bounds(obj)
            if (x1 - x0) > 2.0 and c.y < 0:
                gate_tail.insert(0, body.pop())
                continue
        break
    # If we only grabbed iron, also pull the preceding wood leaf.
    if len(gate_tail) == 1 and body:
        pid = body[-1]
        _p, cat, obj = by_id[pid]
        (x0, x1), (y0, y1), _z = world_bounds(obj)
        c = piece_centroid(obj)
        if cat == "Wall" and (x1 - x0) > 2.0 and c.y < 0:
            gate_tail.insert(0, body.pop())

    n_walk = max(1, len(STAGE_ORDER) - 1)
    # Even split with no trailing empty stage (28 panels → 8 non-empty walks).
    walk_batches: list[list[str]] = [[] for _ in range(n_walk)]
    if body:
        base, rem = divmod(len(body), n_walk)
        idx = 0
        for b in range(n_walk):
            take = base + (1 if b < rem else 0)
            walk_batches[b] = body[idx : idx + take]
            idx += take
    batches = walk_batches + [gate_tail]

    cumulative: list[str] = []
    stages: dict[str, list[str]] = {}
    for key, add in zip(STAGE_ORDER, batches):
        for p in add:
            if p not in cumulative:
                cumulative.append(p)
        stages[key] = list(cumulative)
    stages["complete"] = list(path_ids)

    return {
        "source": source_name,
        "structureName": structure_name,
        "coordinateSystem": "Z-up",
        "buildPath": "gate_west_ccw",
        "pieces": piece_defs,
        "stages": stages,
        "stageOrder": list(STAGE_ORDER),
        "tween": {
            "staggerSec": 0.05,
            "ease": "easeOutCubic",
            "startScale": 0.92,
        },
    }


def build_cow_fence_manifest(
    pieces: list[tuple[str, str, bpy.types.Object]],
    *,
    source_name: str,
    structure_name: str,
) -> dict:
    """9 assembly stages walk the pasture; last stage is the gate opening."""
    path_ids = order_cow_fence_perimeter(pieces)
    by_id = {pid: (pid, cat, obj) for pid, cat, obj in pieces}

    piece_defs = []
    stagger = 0
    for pid in path_ids:
        _pid, cat, obj = by_id[pid]
        c = piece_centroid(obj)
        ang = math.atan2(c.y, c.x)
        outward = Vector((c.x, c.y, 0.0))
        if outward.length > 1e-4:
            outward.normalize()
        else:
            outward = Vector((1.0, 0.0, 0.0))
        piece_defs.append(
            {
                "id": pid,
                "category": cat,
                "staggerIndex": stagger,
                "spawnOffset": [
                    round(outward.x * OUTWARD, 4),
                    round(outward.y * OUTWARD, 4),
                    round(DROP_Z, 4),
                ],
                "spawnYawDeg": round(8.0 * math.sin(ang * 2.0), 2),
                "durationSec": 0.40,
            }
        )
        stagger += 1

    n_tail = max(2, min(4, max(1, len(path_ids) // 9)))
    gate_tail = path_ids[-n_tail:]
    body = path_ids[:-n_tail]

    n_walk = max(1, len(STAGE_ORDER) - 1)
    walk_batches: list[list[str]] = [[] for _ in range(n_walk)]
    if body:
        base, rem = divmod(len(body), n_walk)
        idx = 0
        for b in range(n_walk):
            take = base + (1 if b < rem else 0)
            walk_batches[b] = body[idx : idx + take]
            idx += take
    batches = walk_batches + [gate_tail]

    cumulative: list[str] = []
    stages: dict[str, list[str]] = {}
    for key, add in zip(STAGE_ORDER, batches):
        for p in add:
            if p not in cumulative:
                cumulative.append(p)
        stages[key] = list(cumulative)
    stages["complete"] = list(path_ids)

    return {
        "source": source_name,
        "structureName": structure_name,
        "coordinateSystem": "Z-up",
        "buildPath": "gate_gap_ccw",
        "pieces": piece_defs,
        "stages": stages,
        "stageOrder": list(STAGE_ORDER),
        "tween": {
            "staggerSec": 0.05,
            "ease": "easeOutCubic",
            "startScale": 0.92,
        },
    }


def build_manifest(
    pieces: list[tuple[str, str, bpy.types.Object]],
    *,
    source_name: str,
    structure_name: str,
) -> dict:
    by_cat: dict[str, list[str]] = {
        "Floor": [],
        "Wall": [],
        "Trim": [],
        "Roof": [],
    }
    piece_defs = []

    enriched = []
    for pid, cat, obj in pieces:
        c = piece_centroid(obj)
        ang = math.atan2(c.y, c.x)
        enriched.append((pid, cat, obj, c, ang))

    order_key = {"Floor": 0, "Wall": 1, "Trim": 2, "Roof": 3}
    enriched.sort(key=lambda t: (order_key.get(t[1], 9), t[3].z, t[4]))

    stagger = 0
    ordered_ids: list[str] = []
    for pid, cat, obj, c, ang in enriched:
        by_cat.setdefault(cat, []).append(pid)
        ordered_ids.append(pid)
        outward = Vector((c.x, c.y, 0.0))
        if outward.length > 1e-4:
            outward.normalize()
        else:
            outward = Vector((1.0, 0.0, 0.0))
        spawn = [
            round(outward.x * OUTWARD, 4),
            round(outward.y * OUTWARD, 4),
            round(DROP_Z, 4),
        ]
        piece_defs.append(
            {
                "id": pid,
                "category": cat,
                "staggerIndex": stagger,
                "spawnOffset": spawn,
                "spawnYawDeg": round(12.0 * math.sin(ang * 3.0), 2),
                "durationSec": 0.45,
            }
        )
        stagger += 1

    floors = list(by_cat.get("Floor", []))
    walls = list(by_cat.get("Wall", []))
    trims = list(by_cat.get("Trim", []))
    roofs = list(by_cat.get("Roof", []))

    # Prefer category-aware batches when we have enough structure;
    # otherwise evenly distribute all pieces across the 9 assembly stages.
    use_category = len(floors) + len(walls) + len(trims) + len(roofs) >= 4 and (
        len(walls) >= 2 or len(trims) + len(roofs) >= 1
    )

    if use_category:
        gable_ids: list[str] = []
        wall_body = list(walls)
        if wall_body:
            gable_ids = [wall_body.pop()]
        wall_batches = even_batches(wall_body, 4)
        while len(wall_batches) < 4:
            wall_batches.append([])
        trim_lower = trims[:1]
        trim_upper = trims[1:] if len(trims) > 1 else ([] if trims else [])
        # Floor first, then walls → trim → roof (build from the ground up).
        additions = [
            floors,  # foundation
            wall_batches[0],
            wall_batches[1],
            wall_batches[2],
            wall_batches[3],
            gable_ids,
            trim_lower,
            trim_upper,
            roofs if roofs else [],
        ]
        if not floors and ordered_ids:
            additions[0] = [ordered_ids[0]]
        # Ensure every piece appears at least once
        covered = {p for batch in additions for p in batch}
        missing = [p for p in ordered_ids if p not in covered]
        if missing:
            additions[-1] = additions[-1] + missing
    else:
        # Even with even batches, keep floors in foundation first.
        floor_ids = [pid for pid, cat, _o in pieces if cat == "Floor"]
        rest = [pid for pid in ordered_ids if pid not in floor_ids]
        rest_batches = even_batches(rest, 8)
        additions = [
            floor_ids if floor_ids else ([ordered_ids[0]] if ordered_ids else [])
        ]
        additions.extend(rest_batches)
        while len(additions) < 9:
            additions.append([])
        additions = additions[:9]

    cumulative: list[str] = []
    stages: dict[str, list[str]] = {}
    for key, add in zip(STAGE_ORDER, additions):
        for p in add:
            if p not in cumulative:
                cumulative.append(p)
        # Empty addition → hold previous (still a selectable step)
        stages[key] = list(cumulative)

    # Final stage must include everything
    stages["complete"] = list(ordered_ids)

    return {
        "source": source_name,
        "structureName": structure_name,
        "coordinateSystem": "Z-up",
        "pieces": piece_defs,
        "stages": stages,
        "stageOrder": list(STAGE_ORDER),
        "tween": {
            "staggerSec": 0.07,
            "ease": "easeOutCubic",
            "startScale": 0.92,
        },
    }


def resolve_src(building_id: int) -> str:
    """Prefer Blender-importable decoded Whole GLBs (no meshopt)."""
    meta = BUILDING_META.get(building_id, {})
    name = meta.get("sourceFile") or f"Building{building_id}Whole.glb"
    candidates = [
        os.path.join(DECODED_DIR, name),
        os.path.join(VIEWER_DIR, name),
        os.path.join(COMPLETED_DIR, name),
        os.path.join(ROOT, "viewer/public/buildings", name),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        # Skip meshopt-compressed files — Blender 4.1 can't import them.
        try:
            with open(path, "rb") as f:
                data = f.read(12)
                if data[:4] != b"glTF":
                    continue
                f.seek(12)
                import struct

                chunk_len = struct.unpack("<I", f.read(4))[0]
                chunk_type = f.read(4)
                if chunk_type != b"JSON":
                    return path
                js = f.read(chunk_len)
            if b"EXT_meshopt_compression" in js:
                print(f"  skip meshopt: {path}")
                continue
            return path
        except Exception:
            return path
    raise FileNotFoundError(
        f"No importable {name} in Completed_decoded / viewer / Completed"
    )


def _import_centered_pile(path: str, name: str) -> bpy.types.Object | None:
    bpy.ops.import_scene.gltf(filepath=path)
    pile_objs = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    if not pile_objs:
        return None
    bpy.ops.object.select_all(action="DESELECT")
    for o in pile_objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = pile_objs[0]
    if len(pile_objs) > 1:
        bpy.ops.object.join()
    pile = bpy.context.active_object
    pile.name = name
    bake_trs(pile)
    (ax0, ax1), (ay0, ay1), (az0, _az1) = world_bounds(pile)
    for v in pile.data.vertices:
        v.co.x -= 0.5 * (ax0 + ax1)
        v.co.y -= 0.5 * (ay0 + ay1)
        v.co.z -= az0
    pile.data.update()
    pile.location = (0.0, 0.0, 0.0)
    return pile


def export_site_prep_init(
    cleaned: list[tuple[str, str, bpy.types.Object]],
    init_name: str,
    *,
    layout: list[tuple[str, str, float, float, float, float]] | None = None,
    layout_margin: float = 0.55,
) -> None:
    """Resource piles only for stage-1 Site Prep (no dirt / chalk floor pad)."""
    xs: list[float] = []
    ys: list[float] = []
    for _pid, _cat, o in cleaned:
        (x0, x1), (y0, y1), (_z0, _z1) = world_bounds(o)
        xs.extend([x0, x1])
        ys.extend([y0, y1])
    if not xs:
        return
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    cx = 0.5 * (x_min + x_max)
    cy = 0.5 * (y_min + y_max)
    hx = 0.5 * (x_max - x_min)
    hy = 0.5 * (y_max - y_min)
    if hx < 0.5:
        hx = 0.5
    if hy < 0.5:
        hy = 0.5

    pile_layout = layout if layout is not None else INIT_PILE_LAYOUT

    clear_scene()
    created: list[bpy.types.Object] = []
    for key, name, nx, ny, yaw, scale in pile_layout:
        path = INIT_PILE_PATHS.get(key)
        if not path or not os.path.isfile(path):
            print(f"  warn INIT skip missing pile: {key}")
            continue
        px = cx + max(-layout_margin, min(layout_margin, nx)) * hx
        py = cy + max(-layout_margin, min(layout_margin, ny)) * hy
        pile = _import_centered_pile(path, name)
        if pile is None:
            continue

        used = _place_pile_in_box(
            pile, px, py, 0.0, yaw, scale, x_min, x_max, y_min, y_max
        )
        bake_trs(pile)
        zs = [(pile.matrix_world @ v.co).z for v in pile.data.vertices]
        if zs:
            z0 = min(zs)
            for v in pile.data.vertices:
                v.co.z -= z0
            pile.data.update()
        (wx0, wx1), (wy0, wy1), _ = world_bounds(pile)
        created.append(pile)
        print(
            f"  INIT + {name} @ ({0.5*(wx0+wx1):.2f},{0.5*(wy0+wy1):.2f}) "
            f"scale={used:.2f}"
        )

    if not created:
        print("  warn INIT: no resource piles placed")
        return

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    if len(created) > 1:
        bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = init_name.replace(".glb", "")
    fit_s = _shrink_joined_to_footprint(result, x_min, x_max, y_min, y_max)
    if fit_s < 0.999:
        print(f"  INIT group shrink-to-footprint ×{fit_s:.3f}")

    for out_dir in (VIEWER_OUT, DESKTOP_OUT):
        path = os.path.join(out_dir, init_name)
        bpy.ops.object.select_all(action="DESELECT")
        result.select_set(True)
        bpy.context.view_layer.objects.active = result
        bpy.ops.export_scene.gltf(
            filepath=path,
            export_format="GLB",
            use_selection=True,
            export_apply=True,
            export_materials="EXPORT",
            export_image_format="AUTO",
            export_texcoords=True,
            export_normals=True,
        )
        print(f"  -> {path} (site-prep INIT, resources only)")


def export_sheep_fence_site_prep_init(
    cleaned: list[tuple[str, str, bpy.types.Object]],
    init_name: str,
    *,
    coins: bool = False,
) -> None:
    """Fence site prep: two sycamore log stacks at pasture center (+ coins)."""
    xs: list[float] = []
    ys: list[float] = []
    for _pid, _cat, o in cleaned:
        (x0, x1), (y0, y1), (_z0, _z1) = world_bounds(o)
        xs.extend([x0, x1])
        ys.extend([y0, y1])
    if not xs:
        return
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    cx = 0.5 * (x_min + x_max)
    cy = 0.5 * (y_min + y_max)

    path = INIT_PILE_PATHS.get("sycamore_logs")
    if not path or not os.path.isfile(path):
        print("  warn INIT: missing sycamore_logs pile")
        return

    clear_scene()
    # Probe one stack for half-width so the pair sits side-by-side with a gap.
    probe = _import_centered_pile(path, "pile_sycamore_logs_probe")
    if probe is None:
        return
    scale = 0.28
    probe.scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    (px0, px1), (_py0, _py1), _ = world_bounds(probe)
    half_w = 0.5 * (px1 - px0)
    gap = max(0.15, half_w * 0.25)
    # Remove probe — place two fresh stacks at final positions.
    bpy.data.objects.remove(probe, do_unlink=True)

    created: list[bpy.types.Object] = []
    placements = [
        ("pile_sycamore_logs_a", cx - (half_w + 0.5 * gap), cy, 0.0),
        ("pile_sycamore_logs_b", cx + (half_w + 0.5 * gap), cy, 0.18),
    ]
    print("  pasture fence INIT: two log stacks at pasture center")
    for name, px, py, yaw in placements:
        pile = _import_centered_pile(path, name)
        if pile is None:
            continue
        used = _place_pile_in_box(
            pile, px, py, 0.0, yaw, scale, x_min, x_max, y_min, y_max
        )
        bake_trs(pile)
        zs = [(pile.matrix_world @ v.co).z for v in pile.data.vertices]
        if zs:
            z0 = min(zs)
            for v in pile.data.vertices:
                v.co.z -= z0
            pile.data.update()
        (wx0, wx1), (wy0, wy1), _ = world_bounds(pile)
        created.append(pile)
        print(
            f"  INIT + {name} @ ({0.5*(wx0+wx1):.2f},{0.5*(wy0+wy1):.2f}) "
            f"scale={used:.2f}"
        )

    if coins:
        coin_path = INIT_PILE_PATHS.get("grind_coins")
        if coin_path and os.path.isfile(coin_path):
            pile = _import_centered_pile(coin_path, "pile_grind_coins")
            if pile is not None:
                used = _place_pile_in_box(
                    pile,
                    cx,
                    cy + (half_w + gap),
                    0.0,
                    0.28,
                    0.32,
                    x_min,
                    x_max,
                    y_min,
                    y_max,
                )
                bake_trs(pile)
                zs = [(pile.matrix_world @ v.co).z for v in pile.data.vertices]
                if zs:
                    z0 = min(zs)
                    for v in pile.data.vertices:
                        v.co.z -= z0
                    pile.data.update()
                created.append(pile)
                print(f"  INIT + pile_grind_coins scale={used:.2f}")
        else:
            print("  warn INIT: missing grind_coins pile")

    if not created:
        print("  warn INIT: no log stacks placed")
        return

    bpy.ops.object.select_all(action="DESELECT")
    for o in created:
        o.select_set(True)
    bpy.context.view_layer.objects.active = created[0]
    if len(created) > 1:
        bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = init_name.replace(".glb", "")
    fit_s = _shrink_joined_to_footprint(result, x_min, x_max, y_min, y_max)
    if fit_s < 0.999:
        print(f"  INIT group shrink-to-footprint ×{fit_s:.3f}")

    for out_dir in (VIEWER_OUT, DESKTOP_OUT):
        out_path = os.path.join(out_dir, init_name)
        bpy.ops.object.select_all(action="DESELECT")
        result.select_set(True)
        bpy.context.view_layer.objects.active = result
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
        print(f"  -> {out_path} (pasture fence site-prep INIT)")


def _place_pile_in_box(
    pile: bpy.types.Object,
    px: float,
    py: float,
    z0: float,
    yaw: float,
    scale: float,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    inset: float = 0.10,
) -> float:
    bx0, bx1 = x_min + inset, x_max - inset
    by0, by1 = y_min + inset, y_max - inset
    bw = max(0.05, bx1 - bx0)
    bh = max(0.05, by1 - by0)
    px = max(bx0 + 0.05 * bw, min(bx1 - 0.05 * bw, px))
    py = max(by0 + 0.05 * bh, min(by1 - 0.05 * bh, py))
    pile.location = (px, py, z0)
    pile.rotation_euler = (0.0, 0.0, yaw)
    pile.scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    (ox0, ox1), (oy0, oy1), _ = world_bounds(pile)
    ow = max(1e-6, ox1 - ox0)
    oh = max(1e-6, oy1 - oy0)
    cx_p = 0.5 * (ox0 + ox1)
    cy_p = 0.5 * (oy0 + oy1)
    max_hw = max(0.02, min(cx_p - bx0, bx1 - cx_p))
    max_hh = max(0.02, min(cy_p - by0, by1 - cy_p))
    fit = min(1.0, (2.0 * max_hw) / ow, (2.0 * max_hh) / oh, bw / ow, bh / oh)
    if fit < 0.999:
        scale *= fit
        pile.scale = (scale, scale, scale)
        bpy.context.view_layer.update()
        (ox0, ox1), (oy0, oy1), _ = world_bounds(pile)
    dx = dy = 0.0
    if ox0 < bx0:
        dx = bx0 - ox0
    elif ox1 > bx1:
        dx = bx1 - ox1
    if oy0 < by0:
        dy = by0 - oy0
    elif oy1 > by1:
        dy = by1 - oy1
    if abs(dx) > 1e-6 or abs(dy) > 1e-6:
        pile.location.x += dx
        pile.location.y += dy
        bpy.context.view_layer.update()
    return scale


def _shrink_joined_to_footprint(
    obj: bpy.types.Object,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    inset: float = 0.05,
) -> float:
    bx0, bx1 = x_min + inset, x_max - inset
    by0, by1 = y_min + inset, y_max - inset
    bw = max(0.05, bx1 - bx0)
    bh = max(0.05, by1 - by0)
    (ox0, ox1), (oy0, oy1), _ = world_bounds(obj)
    ow = max(1e-6, ox1 - ox0)
    oh = max(1e-6, oy1 - oy0)
    s = min(1.0, bw / ow, bh / oh)
    if s >= 0.999:
        dx = dy = 0.0
        if ox0 < bx0:
            dx = bx0 - ox0
        elif ox1 > bx1:
            dx = bx1 - ox1
        if oy0 < by0:
            dy = by0 - oy0
        elif oy1 > by1:
            dy = by1 - oy1
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            for v in obj.data.vertices:
                v.co.x += dx
                v.co.y += dy
            obj.data.update()
        return 1.0
    ocx = 0.5 * (ox0 + ox1)
    ocy = 0.5 * (oy0 + oy1)
    tcx = 0.5 * (bx0 + bx1)
    tcy = 0.5 * (by0 + by1)
    for v in obj.data.vertices:
        v.co.x = tcx + (v.co.x - ocx) * s
        v.co.y = tcy + (v.co.y - ocy) * s
    obj.data.update()
    return s


def join_objects(objects: list[bpy.types.Object], name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    return obj


def consolidate_tiny(
    pieces: list[tuple[bpy.types.Object, str]],
) -> list[tuple[bpy.types.Object, str]]:
    """Merge same-material-hint shards under MIN_PIECE_VERTS into one blob."""
    keep: list[tuple[bpy.types.Object, str]] = []
    tiny_by_hint: dict[str, list[bpy.types.Object]] = {}
    for o, hint in pieces:
        name_l = (o.name or "").lower()
        # Preserve true Floor/Door/Roof nodes (Floor, Floor.001) — not
        # Meshy atlas names like Floor_WoodDark / Roof_Tiles_Detail.
        is_authored = bool(
            re.match(r"^(floor|door|roof)(\.\d+)?$", name_l)
        )
        if is_authored:
            keep.append((o, hint))
            continue
        if len(o.data.vertices) < MIN_PIECE_VERTS:
            tiny_by_hint.setdefault(hint, []).append(o)
        else:
            keep.append((o, hint))
    for hint, objs in tiny_by_hint.items():
        if not objs:
            continue
        if len(objs) == 1 and len(objs[0].data.vertices) >= 3:
            keep.append((objs[0], hint))
            continue
        # Floor-ish materials: merge as a Floor candidate, not Trim debris.
        hl = hint.lower()
        merge_name = f"tiny_{hint[:24]}"
        if any(k in hl for k in ("floor", "brick", "wooddark", "plank")):
            merge_name = f"Floor_merged_{hint[:20]}"
        merged = join_objects(objs, merge_name)
        keep.append((merged, hint))
        print(f"  merged {len(objs)} tiny shards → {merged.name} ({hint})")
    return keep


def process_building(building_id: int) -> None:
    meta = BUILDING_META.get(building_id)
    if not meta:
        raise KeyError(f"No BUILDING_META for {building_id}")

    src = resolve_src(building_id)

    print(f"\n######## Building {building_id} — {meta['structureName']} ########")
    print(f"Source: {src} ({os.path.getsize(src)/1024/1024:.2f} MB)")

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()
    pack_images()

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No meshes in {src}")

    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    for m in list(meshes):
        bake_trs(m)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]

    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.duplicate()
    dupes = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    bpy.context.view_layer.objects.active = dupes[0]
    if len(dupes) > 1:
        bpy.ops.object.join()
    joined = bpy.context.active_object
    if is_pasture_fence(meta):
        # Rails aren't a walkable slab — seat the fence on its lowest verts.
        zs = [(joined.matrix_world @ v.co).z for v in joined.data.vertices]
        floor_z = min(zs) if zs else 0.0
    else:
        floor_z = find_walkable_floor_z(joined)
    print(f"  floor_z={floor_z}")
    bpy.data.objects.remove(joined, do_unlink=True)

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if floor_z is not None and abs(floor_z) > 1e-4:
        print(f"  shifting floor {floor_z:.3f} → 0")
        for o in meshes:
            for v in o.data.vertices:
                v.co.z -= floor_z
            o.data.update()

    working: list[tuple[bpy.types.Object, str]] = []
    for o in meshes:
        mat_name = o.data.materials[0].name if o.data.materials else o.name
        for part in separate_by_material(o):
            mat_hint = (
                part.data.materials[0].name if part.data.materials else mat_name
            )
            working.append((part, mat_hint))

    if meta.get("slug") == "cow_fence":
        working = explode_and_cluster_fence_bays(working)
    else:
        working = consolidate_tiny(working)

    # Material splits only — XY quadrant clustering deleted spanning faces
    # and caused missing back walls / roof corners on Complete.
    final_objs: list[tuple[bpy.types.Object, str]] = []
    for o, mat_hint in working:
        if len(o.data.vertices) < 3:
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        final_objs.append((o, mat_hint))

    # Patch authored under-eave / door-lintel voids (source Whole holes).
    if meta.get("slug") != "cow_fence":
        final_objs = seal_under_eave_lintels(final_objs)

    # Sheep / cow fence sit on in-game terrain — never invent a floor pad.
    if is_pasture_fence(meta):
        print(f"  {meta.get('slug')}: skipping floor extract / proxy (terrain is floor)")
    else:
        # Authored floor unlocks first (foundation stage) — extract from source.
        final_objs = ensure_floor_pieces(final_objs)

    cleaned: list[tuple[str, str, bpy.types.Object]] = []
    counters = {"Floor": 0, "Wall": 0, "Trim": 0, "Roof": 0}
    for o, mat_hint in final_objs:
        if len(o.data.vertices) < 3:
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        cat = classify_piece(o, mat_hint)
        name_l = (o.name or "").lower()
        # Only honor peels/proxies we created — not source names like Floor_WoodDark.
        extracted_floor = (
            o.name.startswith("BA_Floor")
            or o.name.startswith("Floor_extracted")
            or o.name.startswith("Floor_slab")
            or o.name.startswith("Floor_from")
            or o.name.startswith("Floor_authored")
            or o.name.startswith("Floor_reclass")
            or o.name.startswith("Floor_merged")
            or o.name.startswith("BA_Floor_proxy")
            or name_l.startswith("floor_extracted")
            or name_l.startswith("floor_slab")
            or name_l.startswith("floor_from")
            or name_l.startswith("floor_authored")
            or name_l.startswith("floor_reclass")
            or name_l.startswith("floor_merged")
        )
        if extracted_floor and "door" not in name_l and "roof" not in name_l:
            cat = "Floor"
        # Drop degenerate / strip "floors" (proxy leftovers, thin brick shards).
        if cat == "Floor" and not _floor_footprint_ok(o):
            print(f"  demote {o.name} Floor→Wall (footprint too small)")
            cat = "Wall"
        counters[cat] = counters.get(cat, 0) + 1
        idx = counters[cat]
        pid = f"BA_{cat}_{idx:02d}"
        o.name = pid
        cleaned.append((pid, cat, o))

    print(
        f"  pieces: {len(cleaned)}  "
        f"(Floor={counters.get('Floor',0)} Wall={counters.get('Wall',0)} "
        f"Trim={counters.get('Trim',0)} Roof={counters.get('Roof',0)})"
    )
    for pid, cat, o in cleaned:
        (x0, x1), (y0, y1), (z0, z1) = world_bounds(o)
        print(
            f"    {pid:16} verts={len(o.data.vertices):4d} "
            f"Z[{z0:.2f},{z1:.2f}] mat={[m.name for m in o.data.materials]}"
        )

    if not cleaned:
        raise RuntimeError(f"No pieces produced for building {building_id}")

    for _pid, _cat, o in cleaned:
        bake_trs(o)
        o.location = (0.0, 0.0, 0.0)
        o.rotation_euler = (0.0, 0.0, 0.0)
        o.scale = (1.0, 1.0, 1.0)

    pack_images()
    objs = [o for _, _, o in cleaned]
    source_name = meta.get("sourceFile") or f"Building{building_id}Whole.glb"
    if meta.get("slug") == "sheep_fence":
        manifest = build_sheep_fence_manifest(
            cleaned,
            source_name=source_name,
            structure_name=meta["structureName"],
        )
    elif meta.get("slug") == "cow_fence":
        manifest = build_cow_fence_manifest(
            cleaned,
            source_name=source_name,
            structure_name=meta["structureName"],
        )
    else:
        manifest = build_manifest(
            cleaned,
            source_name=source_name,
            structure_name=meta["structureName"],
        )

    stem_glb = meta.get("outGlb") or f"Building{building_id}Animation_Modular.glb"
    stem_json = (
        meta.get("outManifest") or f"building{building_id}_animation_manifest.json"
    )
    outputs = [(stem_glb, stem_json)]
    # Keep forge legacy filenames so existing sidebar entry keeps working.
    if building_id == 5:
        outputs.append(
            ("BuildingAnimation_Modular.glb", "building_animation_manifest.json")
        )

    for out_dir in (VIEWER_OUT, DESKTOP_OUT):
        for glb_name, json_name in outputs:
            glb_path = os.path.join(out_dir, glb_name)
            export_pieces(objs, glb_path)
            print(f"  -> {glb_path} ({os.path.getsize(glb_path)/1024:.1f} KB)")
            man_path = os.path.join(out_dir, json_name)
            with open(man_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
                f.write("\n")
            print(f"  -> {man_path}")

    init_glb = meta.get("initGlb")
    if init_glb:
        # Site-prep pad for non-BuildingN sources (e.g. SheepFence / CowFence).
        if meta.get("slug") == "sheep_fence":
            export_sheep_fence_site_prep_init(cleaned, init_glb)
        elif meta.get("slug") == "cow_fence":
            export_sheep_fence_site_prep_init(cleaned, init_glb, coins=True)
        else:
            export_site_prep_init(cleaned, init_glb)


def parse_ids() -> list[int]:
    args: list[str] = []
    if "--" in sys.argv:
        args = sys.argv[sys.argv.index("--") + 1 :]
    if not args:
        return list(DEFAULT_IDS)
    if any(a.lower() == "all" for a in args):
        return sorted(BUILDING_META.keys())
    ids: list[int] = []
    for a in args:
        al = a.lower()
        if al in ("sheep", "fence", "sheep_fence", "sheepfence"):
            ids.append(9)
            continue
        if al in ("cow", "cow_fence", "cowfence", "cow_pasture", "cowpasture"):
            ids.append(10)
            continue
        try:
            ids.append(int(a))
        except ValueError:
            print(f"  skip unknown arg: {a}")
    return ids or list(DEFAULT_IDS)


def main() -> None:
    ids = parse_ids()
    print("=== Building Animation modular split ===")
    print(f"Buildings: {ids}")
    for bid in ids:
        process_building(bid)
    print("\nDONE — modular assembly assets exported.")


if __name__ == "__main__":
    main()
