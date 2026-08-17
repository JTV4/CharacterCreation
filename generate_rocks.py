"""
generate_rocks.py
=================
A family of naturally-shaped stones for scattering into scenes: Small,
Medium, Large, Huge.  Same clean-handoff contract as every other asset
in the repo:

  - Each rock is a single joined mesh with baked transforms.
  - Origin at (0, 0, 0) = footprint centre at ground level, so scenes
    can scatter them with a single translation and never worry about
    them sinking below or hovering above the ground.
  - Single material slot `rock_stone` per rock — the artist will
    typically wire the same tileable stone material into all four,
    which keeps the world looking cohesive without any per-mesh work.
  - Flat-shaded faces (bmesh default) for a chunky, weathered look —
    smooth shading on a low-poly convex hull would round out the
    facets and lose the whole reason we chose this technique.

Geometry approach — convex hull of a jittered point cloud
---------------------------------------------------------
For each rock we:
  1. Sample N uniformly-distributed points on the unit sphere.
  2. Radially perturb each point by ±JITTER (creates bumps and dents).
  3. Scale by the rock's (halfX, halfY, halfZ) ellipsoid extents.
  4. Take the convex hull.
  5. Recentre so the footprint centre is at (X=0, Y=0) and the lowest
     vertex sits on the ground (Z=0).

The convex-hull-of-points idiom is the classic "instant rock" trick:
it produces the flat facets and sharp edges you get from real
weathered stone, without any noise modifier or sculpt work, and the
random seed guarantees each rock is unique but the output is
deterministic (same run → same rock, always).

Outputs (one per rock):
  ~/Desktop/Models/Buildings/{SmallRock,MediumRock,LargeRock,HugeRock}.glb
  viewer/public/buildings/{SmallRock,MediumRock,LargeRock,HugeRock}.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_rocks.py
"""

import math
import os
import random

import bpy
import bmesh
from mathutils import Vector


# ── Output paths ──────────────────────────────────────────────────────────

SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)


# ── Rock specifications ──────────────────────────────────────────────────
# Half-extents in metres (so full size = 2×half in each axis before
# jitter tweaks it).  Point counts scale gently with size — bigger
# rocks get more facets both because they occupy more screen area and
# because their silhouette benefits from finer bumps.  Jitter DECREASES
# with size — a hand-sized rock reads best chunky/angular, but a
# car-sized landmark boulder wants a smoother, more massive silhouette.

ROCKS = [
    # (out_name,     half_extents (X, Y, Z),   num_points, radial_jitter, seed)
    ("SmallRock",    (0.10, 0.10, 0.08),        16,         0.22,          1),
    ("MediumRock",   (0.28, 0.28, 0.22),        24,         0.18,          2),
    ("LargeRock",    (0.65, 0.65, 0.48),        36,         0.15,          3),
    ("HugeRock",     (1.45, 1.45, 1.05),        50,         0.12,          4),
]


# ── Materials ─────────────────────────────────────────────────────────────

MATERIAL_COLORS = {
    "rock_stone": (0.45, 0.42, 0.38),   # neutral warm-grey stone base
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
        # Rocks are matte — kill the default 0.5 specular so previews
        # don't show a gloss spot on every facet.
        if "Specular IOR Level" in principled.inputs:
            principled.inputs["Specular IOR Level"].default_value = 0.15
        elif "Specular" in principled.inputs:
            principled.inputs["Specular"].default_value = 0.15
        if "Roughness" in principled.inputs:
            principled.inputs["Roughness"].default_value = 0.85
    return mat


# ── Point sampling helpers ────────────────────────────────────────────────

def _uniform_point_on_sphere(rng: random.Random) -> tuple[float, float, float]:
    """Uniformly-distributed point on the unit sphere.

    Uses the "uniform z + uniform longitude" method (a straight fallout
    of the fact that a sphere's area element in cylindrical coordinates
    is 2π·dz — no rejection loop, no clustering at the poles).
    """
    z = rng.uniform(-1.0, 1.0)
    phi = rng.uniform(0.0, 2.0 * math.pi)
    r_xy = math.sqrt(max(0.0, 1.0 - z * z))
    return (r_xy * math.cos(phi), r_xy * math.sin(phi), z)


# ── Rock builder ─────────────────────────────────────────────────────────

def build_rock(name: str,
               half: tuple[float, float, float],
               num_points: int,
               jitter: float,
               seed: int) -> bpy.types.Object:
    """Build one rock: sample points → hull → recentre → assign material."""
    rng = random.Random(seed)

    hx, hy, hz = half

    # 1) Sample & jitter points, then squash into the target ellipsoid.
    pts = []
    for _ in range(num_points):
        ux, uy, uz = _uniform_point_on_sphere(rng)
        # Radial perturbation: values >1 push outward (bump), <1 pull
        # inward (dent).  Multiplicative around 1.0 keeps things
        # symmetric — no directional bias.
        r = 1.0 + rng.uniform(-jitter, jitter)
        pts.append(Vector((ux * r * hx, uy * r * hy, uz * r * hz)))

    # 2) Feed the points into a bmesh and take the convex hull.
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    obj  = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    bm.verts.ensure_lookup_table()

    result = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)

    # convex_hull returns any points that ended up strictly interior in
    # result['geom_interior'] / ['geom_unused'] — delete them so the
    # final vert count matches the hull-only count.  The two keys can
    # overlap for the same vert in Blender 4.1+ (interior AND unused
    # points show up in both), so dedupe by identity before feeding to
    # bmesh.ops.delete — it errors on duplicate geom.
    unused_set = set()
    for key in ("geom_interior", "geom_unused"):
        for g in result.get(key, []):
            unused_set.add(g)
    if unused_set:
        bmesh.ops.delete(bm, geom=list(unused_set), context="VERTS")

    # 3) Recentre so origin = (X=0, Y=0, ground level).
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    cx = (min(xs) + max(xs)) / 2.0
    cy = (min(ys) + max(ys)) / 2.0
    min_z = min(zs)
    for v in bm.verts:
        v.co.x -= cx
        v.co.y -= cy
        v.co.z -= min_z

    # 4) Recompute normals from the (recentred) hull geometry.  bmesh's
    # convex_hull produces outward-facing faces by construction, but
    # normal_update makes sure per-vertex normals reflect the flat
    # shading we want.
    for f in bm.faces:
        f.smooth = False
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    obj.data.materials.append(make_material("rock_stone"))
    return obj


# ── Export helpers ───────────────────────────────────────────────────────

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
    print("Generating rock family — SmallRock, MediumRock, LargeRock, HugeRock")
    print()

    for (name, half, num_points, jitter, seed) in ROCKS:
        # Fresh scene per rock so we can export each in isolation with
        # a clean object graph and no interference from previous rocks.
        bpy.ops.wm.read_factory_settings(use_empty=True)

        rock = build_rock(name, half, num_points, jitter, seed)

        n_verts = len(rock.data.vertices)
        n_faces = len(rock.data.polygons)
        n_tris  = sum(len(p.vertices) - 2 for p in rock.data.polygons)
        (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(rock)
        size_x = x_max - x_min
        size_y = y_max - y_min
        size_z = z_max - z_min

        print(f"── {name} (seed={seed}, points={num_points}, jitter={jitter}) ──")
        print(f"   mesh: verts={n_verts}, faces={n_faces}, tris={n_tris}")
        print(f"   size: {size_x:.2f} × {size_y:.2f} × {size_z:.2f} m  "
              f"(X[{x_min:+.2f},{x_max:+.2f}]  "
              f"Y[{y_min:+.2f},{y_max:+.2f}]  "
              f"Z[{z_min:+.2f},{z_max:+.2f}])")

        out_name = f"{name}.glb"
        for out_dir in (SOURCE_DIR, VIEWER_DIR):
            out_path = os.path.join(out_dir, out_name)
            export_glb(rock, out_path)
            size_kb = os.path.getsize(out_path) / 1024.0 if os.path.exists(out_path) else 0
            print(f"   -> {out_path} ({size_kb:.1f} KB)")
        print()

    print("DONE — 4 rocks exported.")


if __name__ == "__main__":
    main()
