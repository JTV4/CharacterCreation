"""
generate_stylized_tree.py
=========================
Browser-optimized stylized deciduous tree matching the GrindScape tree
GLB approach (Acacia / Sycamore / Poplar / Pine / Wisteria):

  - Low-poly tapered trunk + primary/secondary branches (bark atlas)
  - Canopy of LARGE overlapping double-sided ALPHA-CUTOUT cards
    using dense leaf-cluster + branch-with-leaves atlases
  - ~900–1,300 tris, ~150–200 KB with packed 256² textures

This replaces the earlier "icosphere blob" / tiny star-card attempts
that read as sparse and toy-like.  The visual weight comes from the
atlases (same idea as GrindScape), not from solid geometry.

Textures (checked into tree_textures/ — freshly generated, not
reused from GrindScape):
  GenBark.png    — warm furrowed bark tile
  GenLeaves.png  — dense lime leaf-cluster atlas (RGBA alpha)
  GenBranch.png  — branch + leaves atlas (RGBA alpha)

Clean-handoff:
  - Origin at (0,0,0), ground at z=0
  - Single joined mesh, transforms baked
  - Materials: tree_bark, tree_leaves (MASK), tree_branch (MASK)

Outputs:
  ~/Desktop/Models/Buildings/StylizedTree.glb
  viewer/public/buildings/StylizedTree.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_stylized_tree.py
"""

from __future__ import annotations

import math
import os
import random

import bpy
import bmesh
from mathutils import Vector


SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.abspath("viewer/public/buildings")
TEX_DIR = os.path.abspath("tree_textures")
os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)
OUT_NAME = "StylizedTree.glb"

RNG = random.Random(7)


# ── Dimensions ────────────────────────────────────────────────────────────

# Trunk continues ABOVE the highest branch attach so looking up into
# the canopy never shows a flat "stump top" with a limb sitting on it.
TRUNK_HEIGHT = 4.60
TRUNK_R_BASE = 0.36
TRUNK_R_TOP = 0.08
TRUNK_SIDES = 10
TRUNK_RINGS = 10

BRANCH_DEFS = [
    # yaw, pitch (from horizontal), length, r_base, r_tip, z_frac
    # All pitches kept moderate so limbs grow OUT of the trunk sides —
    # a near-vertical "leader" sitting on the trunk top was the main
    # cause of the disconnected upward limb look.
    (20,  34, 1.95, 0.100, 0.032, 0.52),
    (75,  40, 1.70, 0.090, 0.028, 0.58),
    (130, 36, 1.90, 0.095, 0.030, 0.54),
    (185, 42, 1.60, 0.085, 0.026, 0.62),
    (240, 38, 1.80, 0.092, 0.030, 0.56),
    (300, 44, 1.55, 0.080, 0.025, 0.64),
    (340, 32, 1.45, 0.075, 0.024, 0.70),
]

# Large overlapping leaf cards — this is what makes GrindScape trees
# read as a solid crown at a fraction of the tris.
LEAF_CARD_COUNT = 62
LEAF_HALF_W = (0.70, 1.15)      # random range (m)
LEAF_HALF_H = (0.60, 1.00)
# Branch cards are NO LONGER scattered randomly in the canopy (that
# made woody limbs look like they floated / faced the wrong way).
# They are placed only along real geometric branch segments and
# oriented to match each limb's axis.
BRANCH_CARD_HALF_W = (0.35, 0.55)
BRANCH_CARD_HALF_H = (0.55, 0.85)
BRANCH_CARDS_PER_LIMB = 2       # along each primary / secondary

CANOPY_CENTER = Vector((0.10, 0.05, 4.80))
CANOPY_RX, CANOPY_RY, CANOPY_RZ = 2.35, 2.20, 1.55


# ── Materials / textures ──────────────────────────────────────────────────

def load_image(filename: str) -> bpy.types.Image:
    path = os.path.join(TEX_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Missing tree texture: {path}")
    img = bpy.data.images.load(path)
    img.pack()
    return img


def make_bark_material(img: bpy.types.Image) -> bpy.types.Material:
    mat = bpy.data.materials.new("tree_bark")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.92
    return mat


def make_alpha_material(name: str, img: bpy.types.Image) -> bpy.types.Material:
    """Double-sided alpha-clip card material.  Source atlases already
    carry a proper RGBA alpha channel — wire it straight through.
    Cutoff is intentionally low (~0.15) so soft leaf edges from the
    photographic atlases survive (a 0.45 cutoff was eating most of
    the foliage and leaving white clipped shards)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "CLIP"
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "CLIP"
    mat.alpha_threshold = 0.15
    mat.use_backface_culling = False

    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.78
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.12
    return mat


# ── Trunk / branches ──────────────────────────────────────────────────────

def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _trunk_radius_at(t: float) -> float:
    flare = 1.0 + 1.05 * max(0.0, 1.0 - t / 0.20) ** 2
    belly = 1.0 + 0.07 * math.sin(math.pi * t)
    r = TRUNK_R_BASE * (1.0 - t) + TRUNK_R_TOP * t
    return r * flare * belly


def _project_cylinder_uv(obj: bpy.types.Object, u_tile: float = 2.0, v_tile: float = 3.0) -> None:
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    zs = [v.co.z for v in me.vertices]
    z0, z1 = min(zs), max(zs)
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            ang = math.atan2(co.y, co.x)
            u = (ang + math.pi) / (2 * math.pi) * u_tile
            v = (co.z - z0) / max(z1 - z0, 1e-6) * v_tile
            uv[li].uv = (u, v)


def build_trunk(bark_mat: bpy.types.Material) -> bpy.types.Object:
    bm = bmesh.new()
    rings = []
    for ri in range(TRUNK_RINGS + 1):
        t = ri / TRUNK_RINGS
        z = t * TRUNK_HEIGHT
        r = _trunk_radius_at(t)
        cx = 0.10 * t + 0.025 * math.sin(t * 8)
        cy = 0.02 * math.sin(t * 5)
        ring = []
        for si in range(TRUNK_SIDES):
            ang = (2 * math.pi * si) / TRUNK_SIDES
            rr = r * (1.0 + 0.07 * math.sin(si * 2.3 + t * 5))
            ring.append(bm.verts.new((
                cx + rr * math.cos(ang),
                cy + rr * math.sin(ang),
                z,
            )))
        rings.append(ring)

    for ri in range(TRUNK_RINGS):
        for si in range(TRUNK_SIDES):
            sj = (si + 1) % TRUNK_SIDES
            bm.faces.new([
                rings[ri][si], rings[ri][sj],
                rings[ri + 1][sj], rings[ri + 1][si],
            ])

    # Pointed tip — closes the trunk without a flat downward-facing
    # disk (which looked like a cut stump / disconnected upward limb
    # when viewed from below into the canopy).
    tip_z = TRUNK_HEIGHT + 0.28
    cx = sum(v.co.x for v in rings[-1]) / TRUNK_SIDES
    cy = sum(v.co.y for v in rings[-1]) / TRUNK_SIDES
    tip = bm.verts.new((cx, cy, tip_z))
    for si in range(TRUNK_SIDES):
        sj = (si + 1) % TRUNK_SIDES
        bm.faces.new([rings[-1][si], rings[-1][sj], tip])

    mesh = bpy.data.meshes.new("tree_trunk_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("tree_trunk", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(bark_mat)
    _project_cylinder_uv(obj)
    return obj


def _branch_centerline(
    start: Vector,
    direction: Vector,
    length: float,
    segs: int,
) -> list[tuple[Vector, Vector]]:
    """Sample (position, tangent) along a gently upward-curving branch.
    Secondaries and foliage cards MUST use these same points so nothing
    floats off the limb."""
    direction = direction.normalized()
    up = Vector((0, 0, 1))
    samples: list[tuple[Vector, Vector]] = []
    for i in range(segs + 1):
        t = i / segs
        # Quadratic lift — matches the loft used in build_branch.
        pos = start + direction * (length * t) + up * (0.22 * length * t * t)
        # d/dt of the centerline (then normalize).
        tangent = (direction * length + up * (0.44 * length * t)).normalized()
        samples.append((pos, tangent))
    return samples


def build_branch(
    start: Vector, direction: Vector, length: float,
    r_base: float, r_tip: float, bark_mat: bpy.types.Material,
    name: str, sides: int = 6, segs: int = 4,
) -> tuple[bpy.types.Object, list[tuple[Vector, Vector]]]:
    """Loft a tapered branch.  Returns (mesh_object, centerline samples).
    The first sample is at the attachment point (buried into the parent
    so the joint reads as connected)."""
    bm = bmesh.new()
    direction = direction.normalized()
    samples = _branch_centerline(start, direction, length, segs)
    rings = []
    for i, (pos, tangent) in enumerate(samples):
        t = i / segs
        # Extra flare in the first ~20% so the limb thickens at the
        # trunk joint (reads as a natural crotch, not a stuck-on tube).
        flare = 1.0 + 0.55 * max(0.0, 1.0 - t / 0.22) ** 2
        r = (r_base * (1 - t) + r_tip * t) * flare
        arb = Vector((1, 0, 0)) if abs(tangent.x) < 0.9 else Vector((0, 1, 0))
        x_axis = tangent.cross(arb).normalized()
        y_axis = tangent.cross(x_axis).normalized()
        ring = []
        for s in range(sides):
            ang = (2 * math.pi * s) / sides
            ring.append(bm.verts.new(
                pos + (x_axis * math.cos(ang) + y_axis * math.sin(ang)) * r
            ))
        rings.append(ring)

    for i in range(segs):
        for s in range(sides):
            sj = (s + 1) % sides
            bm.faces.new([rings[i][s], rings[i][sj], rings[i + 1][sj], rings[i + 1][s]])
    # No end caps.  Base is buried inside the trunk / parent limb.
    # Tip is left open too — a flat tip disk reads as a "cut limb"
    # when it peeks through the canopy (especially on upward leaders).
    # Leaf cards cover the open tip ring in normal views.

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(bark_mat)
    _project_cylinder_uv(obj, u_tile=1.5, v_tile=2.0)
    return obj, samples


def build_branches(
    bark_mat: bpy.types.Material,
) -> tuple[list, list[Vector], list[tuple[Vector, Vector]]]:
    """Build primary + secondary limbs that actually connect.

    - Primary starts slightly INSIDE the trunk surface so the joint
      is buried (no floating stump end).
    - Secondary forks from a mid-point ON the primary's curved
      centerline (not the straight chord), so it never detaches.
    Returns (objects, tip_positions, all_limb_centerlines).
    """
    objs: list = []
    tips: list[Vector] = []
    limbs: list[tuple[Vector, Vector]] = []  # flattened (pos, tangent) samples

    for i, (yaw_d, pitch_d, length, rb, rt, z_frac) in enumerate(BRANCH_DEFS):
        yaw, pitch = math.radians(yaw_d), math.radians(pitch_d)
        direction = Vector((
            math.cos(yaw) * math.cos(pitch),
            math.sin(yaw) * math.cos(pitch),
            math.sin(pitch),
        ))
        r_at = _trunk_radius_at(z_frac)
        # Bury the thick end deep into the trunk core so the open
        # cylinder base / end-ring is never visible from outside.
        # 0.15× local radius puts the start near the trunk axis.
        start = Vector((
            math.cos(yaw) * r_at * 0.15,
            math.sin(yaw) * r_at * 0.15,
            TRUNK_HEIGHT * z_frac,
        ))
        # Lengthen slightly so the visible protruding length stays
        # similar after the deeper bury.
        buried = r_at * 0.85
        obj, samples = build_branch(
            start, direction, length + buried, rb, rt, bark_mat, f"branch_{i}",
        )
        objs.append(obj)
        tips.append(samples[-1][0])
        limbs.extend(samples)

        # Secondary fork — attach to the actual curved primary path.
        if i < 6:
            # Pick a sample ~40–55% along the primary.
            fork_idx = max(1, int(round((len(samples) - 1) * 0.48)))
            fork_pos, fork_tangent = samples[fork_idx]
            # Angle the secondary away from the primary (yaw offset in
            # the horizontal plane + a bit more upward pitch).
            syaw = yaw + math.radians(RNG.choice([-38, -28, 28, 38]))
            # Keep secondaries spreading outward — don't let them tip
            # past ~50° or they read as a second vertical trunk.
            spitch = min(pitch + math.radians(RNG.uniform(6, 14)), math.radians(48))
            sdir = Vector((
                math.cos(syaw) * math.cos(spitch),
                math.sin(syaw) * math.cos(spitch),
                math.sin(spitch),
            )).normalized()
            # Seat the secondary deep into the primary's volume —
            # pull back along BOTH the secondary direction and the
            # primary tangent so the joint is fully occluded.
            sec_rb = rb * 0.55
            sstart = (
                fork_pos
                - sdir * (sec_rb * 1.8)
                - fork_tangent * (rb * 0.4)
            )
            sobj, ssamples = build_branch(
                sstart, sdir, length * 0.55 + sec_rb * 1.8, sec_rb, rt * 0.7,
                bark_mat, f"branch_{i}_sec", sides=5, segs=3,
            )
            objs.append(sobj)
            tips.append(ssamples[-1][0])
            limbs.extend(ssamples)

    return objs, tips, limbs


# ── Foliage cards ─────────────────────────────────────────────────────────

def _sample_canopy_point(prefer_outer: bool = False) -> Vector:
    while True:
        x, y, z = RNG.uniform(-1, 1), RNG.uniform(-1, 1), RNG.uniform(-1, 1)
        if x * x + y * y + z * z > 1.0:
            continue
        # Bias upper hemisphere for a full rounded crown
        z = abs(z) * 0.55 + z * 0.45
        if prefer_outer:
            # Push toward shell
            n = math.sqrt(x * x + y * y + z * z) or 1.0
            x, y, z = x / n * RNG.uniform(0.65, 1.0), y / n * RNG.uniform(0.65, 1.0), z / n * RNG.uniform(0.55, 1.0)
        p = CANOPY_CENTER + Vector((x * CANOPY_RX, y * CANOPY_RY, z * CANOPY_RZ))
        if p.z < TRUNK_HEIGHT * 0.65:
            continue
        return p


def _card_axes() -> tuple[Vector, Vector]:
    """Mostly upright card with random yaw + mild tilt (reads as foliage
    volume, not flat ground stamps)."""
    yaw = RNG.uniform(0, 2 * math.pi)
    tilt = RNG.uniform(-0.55, 0.55)
    right = Vector((math.cos(yaw), math.sin(yaw), 0.0))
    up = Vector((
        math.sin(tilt) * -math.sin(yaw),
        math.sin(tilt) * math.cos(yaw),
        math.cos(tilt),
    )).normalized()
    return right, up


def build_card_mesh(
    placements: list[tuple[Vector, Vector | None, Vector | None]],
    half_w_range: tuple[float, float],
    half_h_range: tuple[float, float],
    material: bpy.types.Material,
    name: str,
    crossed_frac: float = 0.35,
    lock_uv: bool = False,
) -> bpy.types.Object:
    """Build foliage / branch cards.

    Each placement is (center, right_or_None, up_or_None).  When right/up
    are provided the card is oriented to that frame (used for branch
    cards that must follow a limb).  Otherwise a random upright frame
    is generated (leaf cards).
    """
    bm = bmesh.new()
    face_uv_rot: list[int] = []

    def add_quad(center: Vector, right: Vector, up: Vector, hw: float, hh: float) -> None:
        r, u = right.normalized() * hw, up.normalized() * hh
        v0 = bm.verts.new(center - r - u)
        v1 = bm.verts.new(center + r - u)
        v2 = bm.verts.new(center + r + u)
        v3 = bm.verts.new(center - r + u)
        bm.faces.new([v0, v1, v2, v3])
        # Branch atlases have a preferred "wood runs along V" layout —
        # keep UV upright when lock_uv so the painted branch aligns with
        # the geometric limb (up axis of the card).
        face_uv_rot.append(0 if lock_uv else RNG.randint(0, 3))

    for center, right_opt, up_opt in placements:
        hw = RNG.uniform(*half_w_range)
        hh = RNG.uniform(*half_h_range)
        if right_opt is not None and up_opt is not None:
            right, up = right_opt, up_opt
        else:
            right, up = _card_axes()
        add_quad(center, right, up, hw, hh)
        if RNG.random() < crossed_frac:
            cross = up.cross(right)
            if cross.length > 0.1:
                right2 = cross.normalized()
                up2 = right.cross(right2).normalized()
                add_quad(center, right2, up2, hw * 0.9, hh * 0.9)

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)

    me = obj.data
    me.uv_layers.new(name="UVMap")
    uv = me.uv_layers.active.data
    base = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    for pi, poly in enumerate(me.polygons):
        rot = face_uv_rot[pi] if pi < len(face_uv_rot) else 0
        uvs = base[rot:] + base[:rot]
        if (not lock_uv) and RNG.random() < 0.5:
            uvs = [(1.0 - u, v) for u, v in uvs]
        for i, li in enumerate(poly.loop_indices):
            uv[li].uv = uvs[i % 4]
    return obj


def _frame_along_tangent(tangent: Vector) -> tuple[Vector, Vector]:
    """Card frame where the card's long axis (`up`) follows the limb
    so the painted wood in GenBranch runs along the geometric branch,
    and `right` is a horizontal-ish side vector."""
    t = tangent.normalized()
    world_up = Vector((0, 0, 1))
    right = t.cross(world_up)
    if right.length < 0.15:
        right = t.cross(Vector((1, 0, 0)))
    right.normalize()
    return right, t


def build_foliage(
    tips: list[Vector],
    limbs: list[tuple[Vector, Vector]],
    leaf_mat,
    branch_mat=None,
) -> list[bpy.types.Object]:
    """Leaf cards only.  Woody branch-atlas cards were removed — even
    when snapped to limb samples they read as floating cut limbs
    (painted wood on a flat card) and caused the attachment bug the
    user flagged.  Real bark geometry carries all the limb structure.
    `limbs` / `branch_mat` kept in the signature for call-site clarity.
    """
    del limbs, branch_mat  # foliage no longer uses these
    leaf_placements: list[tuple[Vector, Vector | None, Vector | None]] = []

    # Leaf cards clustered around real tips first so canopy volume
    # follows the actual skeleton.
    for tip in tips:
        leaf_placements.append((
            tip + Vector((
                RNG.uniform(-0.30, 0.30),
                RNG.uniform(-0.30, 0.30),
                RNG.uniform(0.05, 0.45),
            )),
            None, None,
        ))

    while len(leaf_placements) < LEAF_CARD_COUNT:
        leaf_placements.append((_sample_canopy_point(prefer_outer=RNG.random() < 0.55), None, None))

    return [
        build_card_mesh(
            leaf_placements, LEAF_HALF_W, LEAF_HALF_H, leaf_mat,
            "tree_leaves", crossed_frac=0.40, lock_uv=False,
        ),
    ]


# ── Join / export ─────────────────────────────────────────────────────────

def join_group(objects: list, name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = name
    return obj


def normalize_transform(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")


def export_glb(obj: bpy.types.Object, out_path: str) -> None:
    normalize_transform(obj)
    # Force double-sided + clip on foliage mats before export
    for mat in obj.data.materials:
        if mat and mat.name != "tree_bark":
            mat.use_backface_culling = False
            mat.blend_method = "CLIP"
            mat.alpha_threshold = 0.15
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
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


def report_mesh(obj: bpy.types.Object) -> None:
    n_tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    mats = [m.name if m else "?" for m in obj.data.materials]
    xs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    print(f"  verts={len(obj.data.vertices)}, tris={n_tris}, materials={mats}")
    print(
        f"  bounds: X[{min(v.x for v in xs):+.3f}, {max(v.x for v in xs):+.3f}]  "
        f"Y[{min(v.y for v in xs):+.3f}, {max(v.y for v in xs):+.3f}]  "
        f"Z[{min(v.z for v in xs):+.3f}, {max(v.z for v in xs):+.3f}]"
    )


def main() -> None:
    print(f"Source: {os.path.join(SOURCE_DIR, OUT_NAME)}")
    print(f"Viewer: {os.path.join(VIEWER_DIR, OUT_NAME)}")
    print(f"Textures: {TEX_DIR}")
    print("Approach: GrindScape-style large alpha leaf/branch cards")

    clear_scene()

    bark_img = load_image("GenBark.png")
    leaf_img = load_image("GenLeaves.png")

    bark_mat = make_bark_material(bark_img)
    leaf_mat = make_alpha_material("tree_leaves", leaf_img)

    parts = [build_trunk(bark_mat)]
    branches, tips, limbs = build_branches(bark_mat)
    parts.extend(branches)
    parts.extend(build_foliage(tips, limbs, leaf_mat))

    print(f"  parts={len(parts)}, branch_tips={len(tips)}, limb_samples={len(limbs)}")
    tree = join_group(parts, "stylized_tree")
    report_mesh(tree)

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        path = os.path.join(out_dir, OUT_NAME)
        export_glb(tree, path)
        print(f"  -> {path} ({os.path.getsize(path)/1024:.1f} KB)")

    print("\nDONE — GrindScape-style stylized tree exported.")


if __name__ == "__main__":
    main()
