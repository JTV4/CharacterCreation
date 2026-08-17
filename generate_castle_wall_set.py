"""
generate_castle_wall_set.py
===========================
Build a game-optimized, UNTEXTURED castle wall set from Blender primitives.
Same clean-handoff contract as the bridge / fishing dock generators:

  - Origin at world (0, 0, 0), ground plane at z = 0.
  - Single joined mesh per piece (except the double door, which stays as
    two hinged sub-objects — see below).
  - Baked TRS (transform_apply on location/rotation/scale) so downstream
    bounding-box maths stay honest.
  - Multiple named material slots so a texture artist can paint each
    part-type once and have every instance follow.

Six pieces, each exported as its own GLB, designed to snap together:

  1. Castle Pillar          — 1.2 × 1.2 m footprint, 5.0 m tall corner
                              tower with crenellated top and cross-shape
                              arrow slits on all four faces.
  2. Castle Wall Segment    — 4.0 × 0.5 m footprint, 3.5 m tall crenellated
                              wall run with a blind-arch machicolation
                              frieze along the top edge.
  2b. Castle Wall Window    — same wall module with a centered pointed
                              (Gothic) arched window opening + stone sill.
  2c. Castle Wall Window Frame — wood frame + leaded glass + mullions
                              that slides into the Wall Window opening
                              (shared WIN_* arch constants).
  2d. Castle Wall Window Frame Clear — same insert with textured oak
                              frame + see-through tinted glass (no
                              opaque glass map).
  2e. Castle Wall Window Frame Open — same as Clear but without the
                              inner T / cross mullions.
  2f. Castle Wall Window Frame Plain — same as Window Frame (leaded
                              glass) but without the inner T mullions.
  3. Castle Entrance Arch   — 5.0 × 1.2 m footprint, 5.0 m tall gatehouse
                              with two flanking crenellated towers and a
                              2.4-m-wide semicircular arched opening
                              (spring line z=2.5 m, peak z=3.7 m).
  4. Castle Double Door     — Two hinged wooden panels with iron banding,
                              iron studs, ring pulls, and hinge straps.
                              The panels' top edges follow the same
                              quarter-arc as the entrance's opening, so
                              when closed they exactly fill the arch.
                              Left panel origin at (-1.2, 0.04, 0);
                              right panel origin at (+1.2, 0.04, 0) —
                              rotate each around local Z to swing open.
  5. Castle Pillar Cone     — rectangular (square) pillar + conical roof,
                              square plinth, cross arrow slit.
  6. Castle Pillar Round Cone — round cylindrical pillar + conical roof,
                              square plinth, cross arrow slit.

Coordinate convention (matches bridge/fishing_dock)
---------------------------------------------------
  +X = width (along wall length for wall segment, across opening for
       entrance).
  +Y = wall depth (through the wall — outside face at -Y, inside face
       at +Y).
  +Z = up.
  Origin sits at ground level on the wall centre-line, so pillars
  and entrance sit centered on their footprints, and wall segments
  extend +X/-X from origin along the wall length.

Modular fit
-----------
  - Wall segment (Y-length): 4.0 m along +X, thickness 0.5 m in Y.
  - Pillar and entrance both use footprint depth 1.2 m in Y, which is
    wider than the wall thickness of 0.5 m — a real corner tower.
    Place a pillar at (0, 0, 0), then place wall segments with their
    ends at (±0.6, 0, 0) so the pillar visibly protrudes 0.35 m in front
    and behind the wall.
  - The entrance is placed exactly like a pillar: its centre at the
    wall centre-line, opening spanning ±1.2 m in X.
  - The double door's opening dimensions (2.4 m wide, 3.7 m peak,
    1.2 m arch radius) match the entrance's opening dimensions bit-
    for-bit — see OPENING_* constants shared between build_entrance
    and build_double_door.

Poly budgets (final joined mesh per piece):
  - Pillar          ~ 350 tris
  - Wall Segment    ~ 650 tris
  - Entrance        ~ 1200 tris (the arched opening is the expensive
                                  part — 12 arc segments × 2 faces of
                                  quads)
  - Double Door     ~ 800 tris across both panels combined

Outputs (mirrors bridge / dock convention):
  ~/Desktop/Models/Buildings/CastlePillar.glb
  ~/Desktop/Models/Buildings/CastleWallSegment.glb
  ~/Desktop/Models/Buildings/CastleEntrance.glb
  ~/Desktop/Models/Buildings/CastleDoubleDoor.glb
  ~/Desktop/Models/Buildings/CastlePillarCone.glb
  ~/Desktop/Models/Buildings/CastlePillarRoundCone.glb
  ~/Desktop/Models/Buildings/CastleWallWindow.glb
  ~/Desktop/Models/Buildings/CastleWallWindowFrame.glb
  ~/Desktop/Models/Buildings/CastleWallWindowFrameClear.glb
  ~/Desktop/Models/Buildings/CastleWallWindowFrameOpen.glb
  ~/Desktop/Models/Buildings/CastleWallWindowFramePlain.glb
  (+ matching paths under viewer/public/buildings/)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python generate_castle_wall_set.py
  # optional filter: -- cone | round | pillar | wall | window | frame | clear | open | plain | entrance | door
"""

import math
import os
import sys

import bpy
import bmesh


# ── Output paths ──────────────────────────────────────────────────────────

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.expanduser("~/Desktop/Models/Buildings")
VIEWER_DIR = os.path.join(ROOT, "viewer/public/buildings")
TEX_DIR = os.path.join(ROOT, "castle_wall_textures")

os.makedirs(SOURCE_DIR, exist_ok=True)
os.makedirs(VIEWER_DIR, exist_ok=True)


# ── Shared geometry constants ─────────────────────────────────────────────
# The whole castle set snaps together via a small number of shared
# constants.  Tweak here and every affected piece re-derives its shape.

# Base plinth (a small overhang footing common to every stone piece).
PLINTH_HEIGHT = 0.15
PLINTH_OVERHANG = 0.05          # plinth is this much wider than the body

# Wall body vs. wall total heights.  Every "stone" piece stacks:
#   plinth → body → coping → merlons
COPING_HEIGHT = 0.15            # decorative overhang below the merlons
MERLON_HEIGHT = 0.45
MERLON_XZ = 0.35                # merlon square cross-section (X = along wall, Z = up)
MERLON_YEXTRA = 0.05            # merlons extend this much past the wall thickness
                                # on each side so they read like real stone caps

# Wall segment.  Height = plinth + body + coping + merlons.
WALL_LENGTH    = 4.00           # +X extent (4-m tileable module)
WALL_THICKNESS = 0.50           # Y-depth of the wall body
WALL_BODY_HEIGHT = 2.75         # z from top-of-plinth to bottom-of-coping
WALL_TOTAL_HEIGHT = (
    PLINTH_HEIGHT + WALL_BODY_HEIGHT + COPING_HEIGHT + MERLON_HEIGHT
)  # 3.50 m

# Pillar / tower.  Taller than a wall segment so towers punctuate wall runs.
PILLAR_SIDE  = 1.20             # square footprint (X = Y)
PILLAR_BODY_HEIGHT = 4.25       # z from top-of-plinth to bottom-of-coping
PILLAR_TOTAL_HEIGHT = (
    PLINTH_HEIGHT + PILLAR_BODY_HEIGHT + COPING_HEIGHT + MERLON_HEIGHT
)  # 5.00 m

# Cone-top pillars (rectangular + round) — same modular footprint as
# the crenellated pillar so they snap into the same wall slots.
CONE_PILLAR_BODY_H = 3.60       # stone shaft height above plinth
CONE_ROOF_H = 1.85              # conical / pyramidal roof height
CONE_OVERHANG = 0.14            # roof base wider than shaft
CONE_CORNICE_H = 0.12
ROUND_PILLAR_R = PILLAR_SIDE / 2.0   # 0.60 m — matches 1.2 m square width

# Entrance.  Uses the same body/coping/merlon layer heights as the
# pillar for a matched roofline, plus a semicircular arched opening
# on the centre-line.
ENTRANCE_WIDTH  = 5.00          # +X extent (matches roughly 1 wall + pillar-and-a-half)
ENTRANCE_DEPTH  = 1.20          # Y-depth (matches pillar footprint)
ENTRANCE_TOTAL_HEIGHT = PILLAR_TOTAL_HEIGHT  # 5.00 m

# Shared opening dimensions — MUST be identical between entrance and door.
OPENING_WIDTH  = 2.40           # X-extent of the archway hole (± 1.20 m)
OPENING_SPRING_Z = 2.50         # z where the vertical jamb ends and arch begins
OPENING_RADIUS = OPENING_WIDTH / 2.0        # 1.20 m — semicircular arch
OPENING_PEAK_Z = OPENING_SPRING_Z + OPENING_RADIUS  # 3.70 m
# Number of straight-line segments per HALF of the semicircular arch.
# Used everywhere the arch curve is discretised — entrance spandrels
# AND the top of each door panel — so both silhouettes stay in lock-
# step and the door's arched top exactly matches the entrance's arch
# curve when the door is closed.  16 per half (=32 across the full
# opening) gives a visually smooth curve at any browser-viewport zoom
# while keeping tri counts modest.
ARCH_HALF_SEGMENTS = 16

# Door dimensions — the two panels together fill the entrance opening.
DOOR_THICKNESS = 0.08           # panel Y-depth
DOOR_INSET_Z   = 0.03           # panel bottom sits this far above ground so
                                # it doesn't clip the floor / ground grid
DOOR_HINGE_INSET = 0.02         # panels don't quite reach the jamb walls
                                # (small gap for hinge hardware clearance)


# ── Materials ─────────────────────────────────────────────────────────────
# Placeholder colours only — the point of the untextured export is that
# a texture artist replaces the base-colour input later.  Palette
# picked to read as "cool grey castle stone + warm oak-with-iron door"
# so the four pieces look like a set even before any texture pass.

MATERIAL_COLORS = {
    "castle_stone_main":  (0.55, 0.55, 0.58),   # main masonry (light grey)
    "castle_stone_trim":  (0.48, 0.48, 0.51),   # merlons, coping (slightly darker)
    "castle_stone_dark":  (0.22, 0.22, 0.25),   # arrow slits, arch recess
    "castle_door_wood":   (0.42, 0.29, 0.17),   # oak plank base colour
    "castle_door_iron":   (0.16, 0.15, 0.14),   # iron banding, studs, ring pulls
    "castle_window_wood": (0.38, 0.26, 0.15),   # window frame / mullions
    "castle_glass":       (0.35, 0.55, 0.72),   # leaded / opaque-tinted panes
    "castle_glass_clear": (0.45, 0.70, 0.85),   # see-through tinted glass
}

# Textured materials (window frame).  Fall back to flat colour if PNG missing.
# Clear glass intentionally has NO texture so alpha/transmission stay readable.
MATERIAL_TEXTURES = {
    "castle_window_wood": "WindowWood_BaseColor.png",
    "castle_glass": "WindowGlass_BaseColor.png",
}


def load_texture(filename: str) -> bpy.types.Image | None:
    path = os.path.join(TEX_DIR, filename)
    if not os.path.isfile(path):
        return None
    img = bpy.data.images.load(path, check_existing=True)
    img.pack()
    return img


def make_material(name: str) -> bpy.types.Material:
    """Idempotent lookup-or-create.  Window wood/glass use packed textures
    when present; other slots stay flat palette colours for handoff paint."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    color = MATERIAL_COLORS.get(name, (0.5, 0.5, 0.5))
    tex_name = MATERIAL_TEXTURES.get(name)
    img = load_texture(tex_name) if tex_name else None

    if img is not None:
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Linear"
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        # Glass diamonds read better a bit denser; wood grain ~1:1.
        scale = 1.6 if name == "castle_glass" else 1.0
        mp.inputs["Scale"].default_value = (scale, scale, scale)
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        if name == "castle_glass":
            mat.blend_method = "BLEND"
            if hasattr(mat, "shadow_method"):
                mat.shadow_method = "NONE"
            bsdf.inputs["Alpha"].default_value = 0.42
            bsdf.inputs["Roughness"].default_value = 0.14
            if "Transmission Weight" in bsdf.inputs:
                bsdf.inputs["Transmission Weight"].default_value = 0.75
            elif "Transmission" in bsdf.inputs:
                bsdf.inputs["Transmission"].default_value = 0.75
        else:
            bsdf.inputs["Roughness"].default_value = 0.78
        return mat

    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        if name in ("castle_glass", "castle_glass_clear"):
            mat.blend_method = "BLEND"
            if hasattr(mat, "shadow_method"):
                mat.shadow_method = "NONE"
            principled.inputs["Base Color"].default_value = (*color, 1.0)
            # Clear glass: low alpha so the viewer reads true see-through.
            principled.inputs["Alpha"].default_value = (
                0.22 if name == "castle_glass_clear" else 0.35
            )
            principled.inputs["Roughness"].default_value = 0.08
            if "Transmission Weight" in principled.inputs:
                principled.inputs["Transmission Weight"].default_value = 0.95
            elif "Transmission" in principled.inputs:
                principled.inputs["Transmission"].default_value = 0.95
            if "IOR" in principled.inputs:
                principled.inputs["IOR"].default_value = 1.45
        else:
            principled.inputs["Base Color"].default_value = (*color, 1.0)
            if "wood" in name or "iron" in name:
                principled.inputs["Roughness"].default_value = 0.7
            else:
                principled.inputs["Roughness"].default_value = 0.85
    return mat


def ensure_uvs(obj: bpy.types.Object) -> None:
    """Smart-project UVs so textured materials have something to sample."""
    if obj.type != "MESH":
        return
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


# ── Primitive helpers ─────────────────────────────────────────────────────

def add_box(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    material_name: str,
    obj_name: str,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """Add a cube, scale it into a box, rotate, then bake the transform
    into vertex data (matches generate_bridge.py's contract)."""
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
    axis: str = "Z",           # cylinder axis alignment
    segments: int = 12,        # keep low for game-poly budget
) -> bpy.types.Object:
    """Add a low-poly cylinder oriented along the given world axis.
    Used for door hinge knuckles and ring pulls."""
    if axis == "Z":
        rotation = (0.0, 0.0, 0.0)
    elif axis == "X":
        rotation = (0.0, math.pi / 2, 0.0)
    elif axis == "Y":
        rotation = (math.pi / 2, 0.0, 0.0)
    else:
        raise ValueError(f"axis must be one of X/Y/Z, got {axis}")
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


def add_torus(
    center: tuple[float, float, float],
    major_radius: float,
    minor_radius: float,
    material_name: str,
    obj_name: str,
    axis: str = "Y",           # ring plane normal
    major_segments: int = 12,
    minor_segments: int = 6,
) -> bpy.types.Object:
    """Low-poly torus for door ring pulls.  Default axis=Y so the ring
    lies in the XZ plane, presenting flat toward the viewer standing
    in front of the closed door."""
    if axis == "Y":
        rotation = (math.pi / 2, 0.0, 0.0)
    elif axis == "X":
        rotation = (0.0, math.pi / 2, 0.0)
    else:
        rotation = (0.0, 0.0, 0.0)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=major_segments,
        minor_segments=minor_segments,
        location=center,
        rotation=rotation,
    )
    obj = bpy.context.active_object
    obj.name = obj_name
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(make_material(material_name))
    return obj


# ── Detail helpers (shared across pillar / wall / entrance) ───────────────

def add_cross_slit(
    center_face_xyz: tuple[float, float, float],
    face_normal: str,               # "+X", "-X", "+Y", "-Y"
    height: float,
    width: float,
    depth: float,
    material_name: str,
    obj_name: str,
) -> bpy.types.Object:
    """Attach a small cruciform "arrow slit" recess onto a wall face.
    Implemented as a THIN dark-stone box embedded slightly into the
    face — a proper boolean subtraction would look sharper but keep
    the poly budget much higher.  The cross reads as an arrow slit
    from any reasonable game viewing distance.

    center_face_xyz is the point on the wall face where the CENTRE of
    the cross should sit.  face_normal names the outward direction of
    that face so we can offset the slit slightly outward from the wall
    surface and orient the cross geometry the right way."""
    n = face_normal
    outward = {
        "+X": (+1, 0, 0), "-X": (-1, 0, 0),
        "+Y": (0, +1, 0), "-Y": (0, -1, 0),
    }[n]
    # Nudge the recess a hair outward so it sits proud of the wall
    # surface — dark stone against light stone reads as an arrow slit.
    ox, oy, oz = center_face_xyz
    nudge = 0.005
    embed_x = ox + outward[0] * nudge
    embed_y = oy + outward[1] * nudge
    embed_z = oz + outward[2] * nudge

    # Vertical + horizontal arm sizes.  Which world-axis corresponds
    # to the "vertical" and "horizontal" arm of the cross depends on
    # the face normal.  For +X / -X faces the vertical is world +Z
    # and horizontal is world +Y.  For +Y / -Y faces horizontal is +X.
    if n in ("+X", "-X"):
        vertical_size  = (depth, width * 0.5, height)          # tall arm (thin in Y)
        horizontal_size= (depth, width, height * 0.35)          # short arm (thin in Z)
    else:
        vertical_size  = (width * 0.5, depth, height)
        horizontal_size= (width, depth, height * 0.35)

    v = add_box(
        center=(embed_x, embed_y, embed_z),
        size=vertical_size,
        material_name=material_name,
        obj_name=f"{obj_name}_v",
    )
    h = add_box(
        # Cross arm sits a bit above the centre for the classic
        # cruciform arrow-slit proportion (long down, short across
        # near the top-third).
        center=(embed_x, embed_y, embed_z + height * 0.15),
        size=horizontal_size,
        material_name=material_name,
        obj_name=f"{obj_name}_h",
    )
    return [v, h]


def build_merlons(
    x_start: float,
    x_end: float,
    y_center: float,
    y_thickness: float,
    z_base: float,
    count: int,
    material_name: str,
    obj_prefix: str,
    created: list,
) -> None:
    """Evenly space `count` square-cross-section merlons between x_start
    and x_end on top of a wall/coping band.  Merlons sit at both
    endpoints (i.e. one at x_start and one at x_end), matching classic
    Norman crenellations, with even gaps between.  Merlons extend
    MERLON_YEXTRA past the y_thickness on both sides so they read as
    real stone blocks capping the wall."""
    span = x_end - x_start
    if count < 2:
        positions = [x_start + span / 2.0]
    else:
        positions = [x_start + span * i / (count - 1) for i in range(count)]
    z_center = z_base + MERLON_HEIGHT / 2.0
    y_size = y_thickness + 2.0 * MERLON_YEXTRA
    for i, x in enumerate(positions):
        created.append(add_box(
            center=(x, y_center, z_center),
            size=(MERLON_XZ, y_size, MERLON_HEIGHT),
            material_name=material_name,
            obj_name=f"{obj_prefix}_merlon_{i}",
        ))


def build_side_merlons(
    y_start: float,
    y_end: float,
    x_center: float,
    x_thickness: float,
    z_base: float,
    count: int,
    material_name: str,
    obj_prefix: str,
    created: list,
) -> None:
    """Mirror of `build_merlons` for the two Y-facing sides of a square
    tower — used by pillar / entrance flanking towers.  Same evenly-
    spaced layout, MERLON_YEXTRA of overhang on each X side."""
    span = y_end - y_start
    if count < 2:
        positions = [y_start + span / 2.0]
    else:
        positions = [y_start + span * i / (count - 1) for i in range(count)]
    z_center = z_base + MERLON_HEIGHT / 2.0
    x_size = x_thickness + 2.0 * MERLON_YEXTRA
    for i, y in enumerate(positions):
        created.append(add_box(
            center=(x_center, y, z_center),
            size=(x_size, MERLON_XZ, MERLON_HEIGHT),
            material_name=material_name,
            obj_name=f"{obj_prefix}_merlon_{i}",
        ))


# ═══════════════════════════════════════════════════════════════════════════
# Piece 1: Castle Pillar (Tower)
# ═══════════════════════════════════════════════════════════════════════════

def build_pillar() -> list:
    """1.2 × 1.2 × 5.0 m corner tower.  Plinth → body → coping → 4
    merlons per face → arrow-slit crosses on the 4 body faces halfway
    up.  Used both as a stand-alone tower and as a hint of the shape
    that flanks the entrance."""
    created: list = []

    plinth_size = PILLAR_SIDE + 2.0 * PLINTH_OVERHANG
    body_z_min = PLINTH_HEIGHT
    body_z_max = PLINTH_HEIGHT + PILLAR_BODY_HEIGHT
    coping_z_max = body_z_max + COPING_HEIGHT
    coping_size = PILLAR_SIDE + 2.0 * MERLON_YEXTRA

    # Plinth
    created.append(add_box(
        center=(0.0, 0.0, PLINTH_HEIGHT / 2.0),
        size=(plinth_size, plinth_size, PLINTH_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="pillar_plinth",
    ))
    # Main body
    created.append(add_box(
        center=(0.0, 0.0, (body_z_min + body_z_max) / 2.0),
        size=(PILLAR_SIDE, PILLAR_SIDE, PILLAR_BODY_HEIGHT),
        material_name="castle_stone_main",
        obj_name="pillar_body",
    ))
    # Coping (overhang cap under the merlons)
    created.append(add_box(
        center=(0.0, 0.0, (body_z_max + coping_z_max) / 2.0),
        size=(coping_size, coping_size, COPING_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="pillar_coping",
    ))
    # Merlons — 3 per face for a 1.2-m-side tower reads as classic
    # square-crown battlements.  Corner merlons are shared across two
    # faces, so we build a corner merlon at each of the 4 corners plus
    # a mid-face merlon at each of the 4 face midpoints (8 merlons
    # total, ~1/3 gap ratio).
    z_base = coping_z_max
    half = PILLAR_SIDE / 2.0
    half_ov = half + MERLON_YEXTRA
    z_center = z_base + MERLON_HEIGHT / 2.0
    # 4 corner merlons
    for i, (sx, sy) in enumerate([(+1, +1), (-1, +1), (-1, -1), (+1, -1)]):
        created.append(add_box(
            center=(sx * half, sy * half, z_center),
            size=(MERLON_XZ + 2.0 * MERLON_YEXTRA * 0.0,   # keep single-face width
                  MERLON_XZ + 2.0 * MERLON_YEXTRA * 0.0,
                  MERLON_HEIGHT),
            material_name="castle_stone_trim",
            obj_name=f"pillar_merlon_corner_{i}",
        ))
    # 4 mid-face merlons
    for i, (cx, cy) in enumerate([(0.0, +half), (0.0, -half), (+half, 0.0), (-half, 0.0)]):
        # For mid-X-face merlons the merlon is oriented with its long side
        # spanning the face (X for +Y/-Y faces, Y for +X/-X faces).
        if abs(cy) > 0.001:   # merlon on ±Y face
            size = (MERLON_XZ, MERLON_XZ, MERLON_HEIGHT)
        else:
            size = (MERLON_XZ, MERLON_XZ, MERLON_HEIGHT)
        created.append(add_box(
            center=(cx, cy, z_center),
            size=size,
            material_name="castle_stone_trim",
            obj_name=f"pillar_merlon_mid_{i}",
        ))

    # Arrow-slit crosses on the 4 body faces, halfway up.  Recess is
    # 0.02 m deep dark-stone box that sits just proud of the face.
    slit_z = body_z_min + PILLAR_BODY_HEIGHT * 0.55
    slit_h = 0.55
    slit_w = 0.10
    slit_d = 0.02
    for face_normal, cx, cy in [
        ("+X", +half, 0.0), ("-X", -half, 0.0),
        ("+Y", 0.0, +half), ("-Y", 0.0, -half),
    ]:
        created.extend(add_cross_slit(
            center_face_xyz=(cx, cy, slit_z),
            face_normal=face_normal,
            height=slit_h,
            width=slit_w,
            depth=slit_d,
            material_name="castle_stone_dark",
            obj_name=f"pillar_slit_{face_normal.replace('+', 'p').replace('-', 'n')}",
        ))

    return created


def _add_cone_roof(
    created: list,
    *,
    z_base: float,
    radius: float,
    height: float,
    vertices: int,
    obj_prefix: str,
) -> None:
    """Pointy conical roof seated on z_base, slight overhang radius."""
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=radius,
        radius2=0.04,
        depth=height,
        location=(0.0, 0.0, z_base + height / 2.0),
    )
    obj = bpy.context.active_object
    obj.name = f"{obj_prefix}_cone"
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.data.materials.clear()
    obj.data.materials.append(make_material("castle_stone_trim"))
    created.append(obj)
    # Small finial nub
    created.append(add_cylinder(
        center=(0.0, 0.0, z_base + height + 0.06),
        radius=0.05,
        height=0.14,
        material_name="castle_stone_dark",
        obj_name=f"{obj_prefix}_finial",
        segments=8,
    ))


def build_pillar_rect_cone() -> list:
    """Rectangular (square) pillar with conical stone roof — same 1.2 m
    footprint as CastlePillar, for cone-top tower slots."""
    created: list = []
    plinth_size = PILLAR_SIDE + 2.0 * PLINTH_OVERHANG
    body_z0 = PLINTH_HEIGHT
    body_z1 = PLINTH_HEIGHT + CONE_PILLAR_BODY_H
    half = PILLAR_SIDE / 2.0

    created.append(add_box(
        center=(0.0, 0.0, PLINTH_HEIGHT / 2.0),
        size=(plinth_size, plinth_size, PLINTH_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="rect_cone_plinth",
    ))
    created.append(add_box(
        center=(0.0, 0.0, (body_z0 + body_z1) / 2.0),
        size=(PILLAR_SIDE, PILLAR_SIDE, CONE_PILLAR_BODY_H),
        material_name="castle_stone_main",
        obj_name="rect_cone_body",
    ))
    # Cornice ring under the cone
    created.append(add_box(
        center=(0.0, 0.0, body_z1 + CONE_CORNICE_H / 2.0),
        size=(
            PILLAR_SIDE + 2.0 * CONE_OVERHANG * 0.55,
            PILLAR_SIDE + 2.0 * CONE_OVERHANG * 0.55,
            CONE_CORNICE_H,
        ),
        material_name="castle_stone_trim",
        obj_name="rect_cone_cornice",
    ))
    roof_z = body_z1 + CONE_CORNICE_H
    # Circular cone on square shaft (matches reference silhouette)
    _add_cone_roof(
        created,
        z_base=roof_z,
        radius=half + CONE_OVERHANG,
        height=CONE_ROOF_H,
        vertices=16,
        obj_prefix="rect_cone",
    )

    slit_z = body_z0 + CONE_PILLAR_BODY_H * 0.48
    for face_normal, cx, cy in [
        ("+X", +half, 0.0), ("-X", -half, 0.0),
        ("+Y", 0.0, +half), ("-Y", 0.0, -half),
    ]:
        created.extend(add_cross_slit(
            center_face_xyz=(cx, cy, slit_z),
            face_normal=face_normal,
            height=0.55,
            width=0.10,
            depth=0.02,
            material_name="castle_stone_dark",
            obj_name=f"rect_cone_slit_{face_normal.replace('+', 'p').replace('-', 'n')}",
        ))
    return created


def build_pillar_round_cone() -> list:
    """Round cylindrical pillar with conical roof — square plinth matching
    the modular 1.2 m footprint, cross arrow slit on four cardinals."""
    created: list = []
    plinth_size = PILLAR_SIDE + 2.0 * PLINTH_OVERHANG
    body_z0 = PLINTH_HEIGHT
    body_z1 = PLINTH_HEIGHT + CONE_PILLAR_BODY_H
    r = ROUND_PILLAR_R

    created.append(add_box(
        center=(0.0, 0.0, PLINTH_HEIGHT / 2.0),
        size=(plinth_size, plinth_size, PLINTH_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="round_cone_plinth",
    ))
    created.append(add_cylinder(
        center=(0.0, 0.0, (body_z0 + body_z1) / 2.0),
        radius=r,
        height=CONE_PILLAR_BODY_H,
        material_name="castle_stone_main",
        obj_name="round_cone_body",
        segments=16,
    ))
    # Cornice torus-like ring (cylinder collar)
    created.append(add_cylinder(
        center=(0.0, 0.0, body_z1 + CONE_CORNICE_H / 2.0),
        radius=r + CONE_OVERHANG * 0.55,
        height=CONE_CORNICE_H,
        material_name="castle_stone_trim",
        obj_name="round_cone_cornice",
        segments=16,
    ))
    roof_z = body_z1 + CONE_CORNICE_H
    _add_cone_roof(
        created,
        z_base=roof_z,
        radius=r + CONE_OVERHANG,
        height=CONE_ROOF_H,
        vertices=16,
        obj_prefix="round_cone",
    )

    slit_z = body_z0 + CONE_PILLAR_BODY_H * 0.48
    for face_normal, cx, cy in [
        ("+X", +r, 0.0), ("-X", -r, 0.0),
        ("+Y", 0.0, +r), ("-Y", 0.0, -r),
    ]:
        created.extend(add_cross_slit(
            center_face_xyz=(cx, cy, slit_z),
            face_normal=face_normal,
            height=0.55,
            width=0.10,
            depth=0.02,
            material_name="castle_stone_dark",
            obj_name=f"round_cone_slit_{face_normal.replace('+', 'p').replace('-', 'n')}",
        ))
    return created


# ═══════════════════════════════════════════════════════════════════════════
# Piece 2: Castle Wall Segment
# ═══════════════════════════════════════════════════════════════════════════

def build_wall_segment() -> list:
    """4.0 m long × 0.5 m thick × 3.5 m tall crenellated wall.  Plinth
    → body → machicolation-style blind-arch frieze → coping → 5
    merlons across.  Two arrow-slit crosses on the outside face."""
    created: list = []

    plinth_x = WALL_LENGTH + 2.0 * PLINTH_OVERHANG
    plinth_y = WALL_THICKNESS + 2.0 * PLINTH_OVERHANG
    body_z_min = PLINTH_HEIGHT
    body_z_max = PLINTH_HEIGHT + WALL_BODY_HEIGHT
    coping_z_max = body_z_max + COPING_HEIGHT

    # Plinth
    created.append(add_box(
        center=(0.0, 0.0, PLINTH_HEIGHT / 2.0),
        size=(plinth_x, plinth_y, PLINTH_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="wall_plinth",
    ))
    # Body
    created.append(add_box(
        center=(0.0, 0.0, (body_z_min + body_z_max) / 2.0),
        size=(WALL_LENGTH, WALL_THICKNESS, WALL_BODY_HEIGHT),
        material_name="castle_stone_main",
        obj_name="wall_body",
    ))
    # Coping (overhang cap under the merlons, slightly wider than body)
    coping_x = WALL_LENGTH + 2.0 * MERLON_YEXTRA
    coping_y = WALL_THICKNESS + 2.0 * MERLON_YEXTRA
    created.append(add_box(
        center=(0.0, 0.0, (body_z_max + coping_z_max) / 2.0),
        size=(coping_x, coping_y, COPING_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="wall_coping",
    ))

    # Machicolation-style blind arches on the outside (-Y) face, just
    # below the coping.  10 tiny arch corbels evenly spaced along the
    # wall — a decorative frieze that reads at any zoom level.  Each
    # corbel is a small trim-stone box that protrudes very slightly
    # from the face.
    frieze_z = body_z_max - 0.28
    frieze_z_size = 0.20
    frieze_corbel_count = 10
    for i in range(frieze_corbel_count):
        # Corbels sit at evenly-spaced positions with small gaps
        # between them (7 corbels, 6 gaps ≈ 4 m).
        u = (i + 0.5) / frieze_corbel_count
        x = -WALL_LENGTH / 2.0 + u * WALL_LENGTH
        # Corbel juts 0.03 m outward from the wall's -Y face.
        y = -WALL_THICKNESS / 2.0 - 0.015
        created.append(add_box(
            center=(x, y, frieze_z),
            size=(WALL_LENGTH / frieze_corbel_count * 0.6, 0.06, frieze_z_size),
            material_name="castle_stone_trim",
            obj_name=f"wall_corbel_{i:02d}",
        ))

    # Merlons across the top — 5 with a merlon at each end for
    # visual tileability against a pillar / entrance.
    build_merlons(
        x_start=-WALL_LENGTH / 2.0 + MERLON_XZ / 2.0,
        x_end=+WALL_LENGTH / 2.0 - MERLON_XZ / 2.0,
        y_center=0.0,
        y_thickness=WALL_THICKNESS,
        z_base=coping_z_max,
        count=5,
        material_name="castle_stone_trim",
        obj_prefix="wall",
        created=created,
    )

    # Two arrow-slit crosses on the -Y (outside) face at 60% height.
    slit_z = body_z_min + WALL_BODY_HEIGHT * 0.55
    slit_h = 0.55
    slit_w = 0.10
    slit_d = 0.02
    for i, x in enumerate([-WALL_LENGTH / 3.0, +WALL_LENGTH / 3.0]):
        created.extend(add_cross_slit(
            center_face_xyz=(x, -WALL_THICKNESS / 2.0, slit_z),
            face_normal="-Y",
            height=slit_h,
            width=slit_w,
            depth=slit_d,
            material_name="castle_stone_dark",
            obj_name=f"wall_slit_{i}",
        ))

    return created


# Window opening on the windowed wall variant (pointed Gothic / lancet).
# The insert frame (CastleWallWindowFrame) shares these constants so it
# slides into the opening with a small clearance gap.
WIN_W = 0.85
WIN_SILL_Z = 0.75          # top of sill / bottom of opening (lower on wall)
WIN_SPRING_Z = 1.55        # where the pointed arch begins
WIN_PEAK_Z = WIN_SPRING_Z + WIN_W * math.sqrt(3.0) / 2.0  # ~2.29
WIN_ARCH_SEGS = 10
WIN_FRAME_GAP = 0.018      # clearance vs wall opening so the insert slides in
WIN_FRAME_THICK = 0.075    # frame rail thickness in the wall plane
WIN_FRAME_DEPTH = WALL_THICKNESS - 0.06  # slightly thinner than the wall


def _pointed_arch_outline(
    win_w: float,
    sill_z: float,
    spring_z: float,
    peak_z: float,
    segs: int,
) -> list[tuple[float, float]]:
    """XZ outline of a pointed Gothic window (same curve as the wall cut)."""
    half = win_w / 2.0
    outline: list[tuple[float, float]] = []
    outline.append((-half, sill_z))
    outline.append((+half, sill_z))
    outline.append((+half, spring_z))
    cx_r, cz_r = -half, spring_z
    for i in range(1, segs):
        th = (math.pi / 3.0) * (i / segs)
        outline.append((cx_r + win_w * math.cos(th), cz_r + win_w * math.sin(th)))
    outline.append((0.0, peak_z))
    cx_l, cz_l = +half, spring_z
    for i in range(1, segs):
        th = (2.0 * math.pi / 3.0) + (math.pi / 3.0) * (i / segs)
        outline.append((cx_l + win_w * math.cos(th), cz_l + win_w * math.sin(th)))
    outline.append((-half, spring_z))
    return outline


def _pointed_arch_solid(
    *,
    win_w: float,
    sill_z: float,
    spring_z: float,
    peak_z: float,
    y0: float,
    y1: float,
    segs: int,
    material_name: str,
    obj_name: str,
) -> bpy.types.Object:
    """Filled pointed-arch prism (used for frame outer/inner and glass)."""
    outline = _pointed_arch_outline(win_w, sill_z, spring_z, peak_z, segs)
    bm = bmesh.new()
    front = [bm.verts.new((x, y0, z)) for x, z in outline]
    back = [bm.verts.new((x, y1, z)) for x, z in outline]
    n = len(outline)
    f_edges = [bm.edges.new((front[i], front[(i + 1) % n])) for i in range(n)]
    b_edges = [bm.edges.new((back[i], back[(i + 1) % n])) for i in range(n)]
    bmesh.ops.triangle_fill(bm, use_beauty=True, edges=f_edges)
    bmesh.ops.triangle_fill(bm, use_beauty=True, edges=b_edges)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([front[i], front[j], back[j], back[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    mesh = bpy.data.meshes.new(f"{obj_name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(obj_name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.clear()
    obj.data.materials.append(make_material(material_name))
    ensure_uvs(obj)
    return obj


def _pointed_arch_cutter(
    *,
    win_w: float,
    sill_z: float,
    spring_z: float,
    peak_z: float,
    y0: float,
    y1: float,
    segs: int,
    obj_name: str,
) -> bpy.types.Object:
    """Solid cutter: rectangle jambs + pointed Gothic arch top, extruded in Y."""
    return _pointed_arch_solid(
        win_w=win_w,
        sill_z=sill_z,
        spring_z=spring_z,
        peak_z=peak_z,
        y0=y0,
        y1=y1,
        segs=segs,
        material_name="castle_stone_dark",
        obj_name=obj_name,
    )


def build_wall_segment_window() -> list:
    """Same 4.0 × 0.5 × 3.5 m crenellated wall module as the plain
    segment, but with a centered pointed arched window (open void)
    and a protruding stone sill — no side arrow slits."""
    created: list = []

    plinth_x = WALL_LENGTH + 2.0 * PLINTH_OVERHANG
    plinth_y = WALL_THICKNESS + 2.0 * PLINTH_OVERHANG
    body_z_min = PLINTH_HEIGHT
    body_z_max = PLINTH_HEIGHT + WALL_BODY_HEIGHT
    coping_z_max = body_z_max + COPING_HEIGHT

    created.append(add_box(
        center=(0.0, 0.0, PLINTH_HEIGHT / 2.0),
        size=(plinth_x, plinth_y, PLINTH_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="winwall_plinth",
    ))

    # Solid body, then boolean-cut the pointed window
    body = add_box(
        center=(0.0, 0.0, (body_z_min + body_z_max) / 2.0),
        size=(WALL_LENGTH, WALL_THICKNESS, WALL_BODY_HEIGHT),
        material_name="castle_stone_main",
        obj_name="winwall_body",
    )
    cutter = _pointed_arch_cutter(
        win_w=WIN_W,
        sill_z=WIN_SILL_Z,
        spring_z=WIN_SPRING_Z,
        peak_z=WIN_PEAK_Z,
        y0=-WALL_THICKNESS,   # overshoot so boolean is clean
        y1=+WALL_THICKNESS,
        segs=WIN_ARCH_SEGS,
        obj_name="winwall_cutter",
    )
    # Boolean difference
    mod = body.modifiers.new(name="WindowCut", type="BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    created.append(body)

    # Protruding sill on the outside (-Y) face
    created.append(add_box(
        center=(0.0, -WALL_THICKNESS / 2.0 - 0.08, WIN_SILL_Z - 0.06),
        size=(WIN_W + 0.28, 0.18, 0.10),
        material_name="castle_stone_trim",
        obj_name="winwall_sill",
    ))

    coping_x = WALL_LENGTH + 2.0 * MERLON_YEXTRA
    coping_y = WALL_THICKNESS + 2.0 * MERLON_YEXTRA
    created.append(add_box(
        center=(0.0, 0.0, (body_z_max + coping_z_max) / 2.0),
        size=(coping_x, coping_y, COPING_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="winwall_coping",
    ))

    frieze_z = body_z_max - 0.28
    frieze_z_size = 0.20
    frieze_corbel_count = 10
    for i in range(frieze_corbel_count):
        u = (i + 0.5) / frieze_corbel_count
        x = -WALL_LENGTH / 2.0 + u * WALL_LENGTH
        y = -WALL_THICKNESS / 2.0 - 0.015
        created.append(add_box(
            center=(x, y, frieze_z),
            size=(WALL_LENGTH / frieze_corbel_count * 0.6, 0.06, frieze_z_size),
            material_name="castle_stone_trim",
            obj_name=f"winwall_corbel_{i:02d}",
        ))

    build_merlons(
        x_start=-WALL_LENGTH / 2.0 + MERLON_XZ / 2.0,
        x_end=+WALL_LENGTH / 2.0 - MERLON_XZ / 2.0,
        y_center=0.0,
        y_thickness=WALL_THICKNESS,
        z_base=coping_z_max,
        count=5,
        material_name="castle_stone_trim",
        obj_prefix="winwall",
        created=created,
    )

    return created


def build_wall_window_frame(
    *,
    wood_mat: str = "castle_window_wood",
    glass_mat: str = "castle_glass",
    name_prefix: str = "winframe",
    with_mullions: bool = True,
) -> list:
    """Insert frame + glass that seats in CastleWallWindow's opening.

    Shares WIN_* arch constants with the wall cut.  Outer silhouette is
    WIN_W − 2·GAP so the piece slides into the opening with clearance.
    Place at the same origin as the wall segment (0,0,0).

    glass_mat:
      castle_glass       — textured leaded diamonds (existing piece)
      castle_glass_clear — flat tinted alpha glass (see-through)
    with_mullions:
      False omits the inner T / cross bars over the glass.
    """
    created: list = []
    outer_w = WIN_W - 2.0 * WIN_FRAME_GAP
    # Shrink width with clearance; keep Gothic curve family (peak from width).
    outer_sill = WIN_SILL_Z + WIN_FRAME_GAP
    outer_spring = WIN_SPRING_Z
    outer_peak = outer_spring + outer_w * math.sqrt(3.0) / 2.0

    inner_w = outer_w - 2.0 * WIN_FRAME_THICK
    inner_sill = outer_sill + WIN_FRAME_THICK
    inner_spring = outer_spring + WIN_FRAME_THICK * 0.35
    inner_peak = inner_spring + inner_w * math.sqrt(3.0) / 2.0

    y0 = -WIN_FRAME_DEPTH / 2.0
    y1 = +WIN_FRAME_DEPTH / 2.0

    outer = _pointed_arch_solid(
        win_w=outer_w,
        sill_z=outer_sill,
        spring_z=outer_spring,
        peak_z=outer_peak,
        y0=y0,
        y1=y1,
        segs=WIN_ARCH_SEGS,
        material_name=wood_mat,
        obj_name=f"{name_prefix}_outer",
    )
    inner_cut = _pointed_arch_solid(
        win_w=inner_w,
        sill_z=inner_sill,
        spring_z=inner_spring,
        peak_z=inner_peak,
        y0=y0 - 0.02,
        y1=y1 + 0.02,
        segs=WIN_ARCH_SEGS,
        material_name=wood_mat,
        obj_name=f"{name_prefix}_inner_cut",
    )
    mod = outer.modifiers.new(name="FrameHollow", type="BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = inner_cut
    mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = outer
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(inner_cut, do_unlink=True)
    created.append(outer)

    # Glass pane — slightly thinner, sits in the inner opening
    glass = _pointed_arch_solid(
        win_w=inner_w - 0.01,
        sill_z=inner_sill + 0.005,
        spring_z=inner_spring,
        peak_z=inner_peak - 0.01,
        y0=-0.015,
        y1=+0.015,
        segs=WIN_ARCH_SEGS,
        material_name=glass_mat,
        obj_name=f"{name_prefix}_glass",
    )
    created.append(glass)

    if with_mullions:
        # Simple cross / T mullion (wood) in front of the glass
        mid_z = (inner_sill + inner_peak) * 0.5
        mull_v = add_box(
            center=(0.0, 0.0, mid_z),
            size=(0.045, WIN_FRAME_DEPTH * 0.55, inner_peak - inner_sill - 0.04),
            material_name=wood_mat,
            obj_name=f"{name_prefix}_mullion_v",
        )
        ensure_uvs(mull_v)
        created.append(mull_v)
        mull_h = add_box(
            center=(0.0, 0.0, inner_spring * 0.55 + inner_sill * 0.45),
            size=(inner_w - 0.06, WIN_FRAME_DEPTH * 0.55, 0.045),
            material_name=wood_mat,
            obj_name=f"{name_prefix}_mullion_h",
        )
        ensure_uvs(mull_h)
        created.append(mull_h)

    return created


# ═══════════════════════════════════════════════════════════════════════════
# Piece 3: Castle Arched Entrance
# ═══════════════════════════════════════════════════════════════════════════

def _build_arch_spandrel_bmesh(
    is_left_half: bool,
    y_front: float,
    y_back: float,
    arc_segments: int,
    material_name: str,
) -> bpy.types.Object:
    """Build half of the stone that FILLS the spandrel region above the
    arch curve and below the header beam.  Produced as an extruded
    concave polygon so the arch reads as ONE smooth surface instead of
    a fan of individually-visible voussoir blocks.

    Region covered (for is_left_half=True):
      x ∈ [-OPENING_RADIUS, 0],  z ∈ [<arch curve>, OPENING_PEAK_Z].

    2D outline of the region traced CCW-ish (the exact handedness is
    irrelevant because we call `bmesh.ops.recalc_face_normals` at the
    end):
      1. arch base at (±OPENING_RADIUS, OPENING_SPRING_Z)
      2. vertical UP the pier inner edge to (±OPENING_RADIUS, OPENING_PEAK_Z)
      3. horizontal across the top to (0, OPENING_PEAK_Z)  (arch peak)
      4. quarter arc from the peak back down to the arch base

    When extruded from y_front to y_back:
      - The two FILL faces (at y_front and y_back) become the visible
        stone on the entrance's front and back facades — no fanning
        wedge silhouette, just one clean arched cutout.
      - The side quads along the ARC segment of the outline form the
        smooth inner TUNNEL WALL you see when looking through the
        archway.

    `bmesh.ops.triangle_fill(use_beauty=True)` is used for the two
    fill faces because the polygon is concave along the arc — a
    single-face `bm.faces.new(outline)` would refuse it.
    """
    bm = bmesh.new()

    outline_2d: list[tuple[float, float]] = []
    if is_left_half:
        outer_x = -OPENING_RADIUS
        # Corners first, then the arc from peak → left base.
        outline_2d.append((outer_x, OPENING_SPRING_Z))    # left arch base
        outline_2d.append((outer_x, OPENING_PEAK_Z))      # top-left corner
        outline_2d.append((0.0, OPENING_PEAK_Z))          # arch peak
        # Semicircle parametrised so theta=pi/2 is the peak and
        # theta=pi is the left base.  Only add intermediate points —
        # the two endpoints are already in the outline.
        for i in range(1, arc_segments):
            theta = math.pi / 2.0 + (math.pi / 2.0) * i / arc_segments
            ax = OPENING_RADIUS * math.cos(theta)
            az = OPENING_SPRING_Z + OPENING_RADIUS * math.sin(theta)
            outline_2d.append((ax, az))
    else:
        outer_x = +OPENING_RADIUS
        # Mirror of the left half — traversed in the SAME rotational
        # sense so the outline never crosses itself.
        #
        # After v2 (right arch base) we walk along the arc back to v0
        # (arch peak).  The arc must therefore be sampled in the order
        # starting NEAR THE RIGHT BASE and ending NEAR THE PEAK — i.e.
        # theta going 0 → pi/2, NOT pi/2 → 0.  Using the "reverse"
        # parametrisation would land the first sample right next to
        # the peak, making a huge diagonal jump across the spandrel
        # interior that self-intersects the top / right edges.
        outline_2d.append((0.0, OPENING_PEAK_Z))          # arch peak
        outline_2d.append((outer_x, OPENING_PEAK_Z))      # top-right corner
        outline_2d.append((outer_x, OPENING_SPRING_Z))    # right arch base
        # Semicircle parametrised so theta=0 is the right base and
        # theta=pi/2 is the peak.  Only add intermediate points — the
        # two endpoints are already in the outline.
        for i in range(1, arc_segments):
            theta = (math.pi / 2.0) * i / arc_segments
            ax = OPENING_RADIUS * math.cos(theta)
            az = OPENING_SPRING_Z + OPENING_RADIUS * math.sin(theta)
            outline_2d.append((ax, az))

    # Front and back vertex loops.
    front_verts = [bm.verts.new((x, y_front, z)) for (x, z) in outline_2d]
    back_verts  = [bm.verts.new((x, y_back,  z)) for (x, z) in outline_2d]

    n = len(outline_2d)
    # Front-face loop → triangulate.
    front_edges = [bm.edges.new((front_verts[i], front_verts[(i + 1) % n]))
                   for i in range(n)]
    bmesh.ops.triangle_fill(bm, use_beauty=True, edges=front_edges)

    # Back-face loop → triangulate.
    back_edges  = [bm.edges.new((back_verts[i],  back_verts[(i + 1) % n]))
                   for i in range(n)]
    bmesh.ops.triangle_fill(bm, use_beauty=True, edges=back_edges)

    # Side quads connecting front and back around the whole outline.
    # The quads along the arc portion of the outline are what give the
    # opening its smooth tunnel wall.
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([front_verts[i], back_verts[i], back_verts[j], front_verts[j]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    side_label = "left" if is_left_half else "right"
    mesh = bpy.data.meshes.new(f"entrance_arch_spandrel_{side_label}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"entrance_arch_spandrel_{side_label}", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(make_material(material_name))
    return obj


def build_entrance() -> list:
    """5.0 × 1.2 × 5.0 m gatehouse with a 2.4-m arched opening.

    Built from the following straightforward pieces:
      - Left pier   (solid stone tower shape, X < -opening_half)
      - Right pier  (solid stone tower shape, X > +opening_half)
      - Header beam (solid stone above OPENING_PEAK_Z, spanning full width)
      - Two arch spandrels — extruded bmesh polygons that FILL the
                             region above the arch curve and below the
                             header beam, one for each half of the
                             semicircle (split at the arch peak x=0).
                             Their side quads along the curved edge
                             double as the smooth inner TUNNEL WALL of
                             the archway you see when looking through
                             the opening.
    Plus plinth, coping, merlons, and cross slits on the piers.

    Splitting the spandrel into two halves keeps each polygon simple
    and non-self-touching (the arch peak just grazes the header base,
    so a single-polygon spandrel would pinch to zero width there and
    triangle_fill would fail)."""
    created: list = []

    half_w = ENTRANCE_WIDTH / 2.0
    half_d = ENTRANCE_DEPTH / 2.0
    opening_half = OPENING_WIDTH / 2.0
    body_z_min = PLINTH_HEIGHT
    body_z_max = PLINTH_HEIGHT + PILLAR_BODY_HEIGHT   # same as pillar
    coping_z_max = body_z_max + COPING_HEIGHT

    plinth_x = ENTRANCE_WIDTH + 2.0 * PLINTH_OVERHANG
    plinth_y = ENTRANCE_DEPTH + 2.0 * PLINTH_OVERHANG

    # Plinth — full width, with a matching cut-out under the opening
    # so the door swings across a clean floor.  Simplest: two plinth
    # blocks left and right of the opening.
    plinth_z = PLINTH_HEIGHT / 2.0
    # Left plinth block:
    left_plinth_x = -half_w - PLINTH_OVERHANG
    left_plinth_x_end = -opening_half
    left_plinth_center_x = (left_plinth_x + left_plinth_x_end) / 2.0
    left_plinth_size_x = left_plinth_x_end - left_plinth_x
    created.append(add_box(
        center=(left_plinth_center_x, 0.0, plinth_z),
        size=(left_plinth_size_x, plinth_y, PLINTH_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="entrance_plinth_left",
    ))
    # Right plinth block (mirror)
    right_plinth_x_start = +opening_half
    right_plinth_x = +half_w + PLINTH_OVERHANG
    right_plinth_center_x = (right_plinth_x_start + right_plinth_x) / 2.0
    right_plinth_size_x = right_plinth_x - right_plinth_x_start
    created.append(add_box(
        center=(right_plinth_center_x, 0.0, plinth_z),
        size=(right_plinth_size_x, plinth_y, PLINTH_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="entrance_plinth_right",
    ))

    # Left and right piers (solid stone from plinth top to coping top).
    # Each pier spans from the outer edge of the entrance inward to the
    # jamb of the opening.
    pier_z_center = (body_z_min + body_z_max) / 2.0
    pier_size_z = PILLAR_BODY_HEIGHT
    # Left pier
    left_pier_x_start = -half_w
    left_pier_x_end = -opening_half
    left_pier_center_x = (left_pier_x_start + left_pier_x_end) / 2.0
    left_pier_size_x = left_pier_x_end - left_pier_x_start
    created.append(add_box(
        center=(left_pier_center_x, 0.0, pier_z_center),
        size=(left_pier_size_x, ENTRANCE_DEPTH, pier_size_z),
        material_name="castle_stone_main",
        obj_name="entrance_pier_left",
    ))
    # Right pier
    right_pier_x_start = +opening_half
    right_pier_x_end = +half_w
    right_pier_center_x = (right_pier_x_start + right_pier_x_end) / 2.0
    right_pier_size_x = right_pier_x_end - right_pier_x_start
    created.append(add_box(
        center=(right_pier_center_x, 0.0, pier_z_center),
        size=(right_pier_size_x, ENTRANCE_DEPTH, pier_size_z),
        material_name="castle_stone_main",
        obj_name="entrance_pier_right",
    ))

    # Header beam — solid stone above the arch peak, spanning the full
    # entrance width up to the body top.  Only exists between
    # OPENING_PEAK_Z and body_z_max.
    header_z_min = OPENING_PEAK_Z
    header_z_max = body_z_max
    if header_z_max > header_z_min:
        header_size_z = header_z_max - header_z_min
        # Header is full-width but with a thickness that matches the
        # entrance depth (deep enough that it looks structural).
        created.append(add_box(
            center=(0.0, 0.0, (header_z_min + header_z_max) / 2.0),
            size=(ENTRANCE_WIDTH, ENTRANCE_DEPTH, header_size_z),
            material_name="castle_stone_main",
            obj_name="entrance_header",
        ))

    # Fill the two spandrels — the regions above the arch curve and
    # below the header beam.  We use two extruded bmesh polygons
    # (one per half, split at the arch peak x=0 where the arch tops
    # out at the header base).  This gives:
    #   * a smooth, continuous stone surface on the entrance's front
    #     and back facades (no visible fan of voussoir wedges), and
    #   * a smooth inner TUNNEL WALL along the arch curve — provided
    #     naturally by the side quads of each extrusion along the
    #     curved edge of the outline.
    # ARCH_HALF_SEGMENTS per half gives a visually smooth semicircle at
    # any reasonable camera distance while keeping the total triangle
    # budget close to what the old 12-wedge scheme cost.
    spandrel_y_front = -ENTRANCE_DEPTH / 2.0
    spandrel_y_back  = +ENTRANCE_DEPTH / 2.0
    created.append(_build_arch_spandrel_bmesh(
        is_left_half=True,
        y_front=spandrel_y_front,
        y_back=spandrel_y_back,
        arc_segments=ARCH_HALF_SEGMENTS,
        material_name="castle_stone_main",
    ))
    created.append(_build_arch_spandrel_bmesh(
        is_left_half=False,
        y_front=spandrel_y_front,
        y_back=spandrel_y_back,
        arc_segments=ARCH_HALF_SEGMENTS,
        material_name="castle_stone_main",
    ))

    # Coping band — spans the full width of the entrance, sits above
    # the header, below the merlons.  Slightly wider than the body.
    coping_x = ENTRANCE_WIDTH + 2.0 * MERLON_YEXTRA
    coping_y = ENTRANCE_DEPTH + 2.0 * MERLON_YEXTRA
    created.append(add_box(
        center=(0.0, 0.0, (body_z_max + coping_z_max) / 2.0),
        size=(coping_x, coping_y, COPING_HEIGHT),
        material_name="castle_stone_trim",
        obj_name="entrance_coping",
    ))

    # Merlons across the top — 8 spanning the full width, plus the
    # front/back edge merlons.  Simpler: use build_merlons across the
    # full length.
    build_merlons(
        x_start=-ENTRANCE_WIDTH / 2.0 + MERLON_XZ / 2.0,
        x_end=+ENTRANCE_WIDTH / 2.0 - MERLON_XZ / 2.0,
        y_center=0.0,
        y_thickness=ENTRANCE_DEPTH,
        z_base=coping_z_max,
        count=8,
        material_name="castle_stone_trim",
        obj_prefix="entrance",
        created=created,
    )

    # Arrow-slit crosses on the piers (2 total — one on each pier's
    # -Y face).
    slit_z = body_z_min + PILLAR_BODY_HEIGHT * 0.60
    slit_h = 0.55
    slit_w = 0.10
    slit_d = 0.02
    for i, cx in enumerate([left_pier_center_x, right_pier_center_x]):
        created.extend(add_cross_slit(
            center_face_xyz=(cx, -ENTRANCE_DEPTH / 2.0, slit_z),
            face_normal="-Y",
            height=slit_h,
            width=slit_w,
            depth=slit_d,
            material_name="castle_stone_dark",
            obj_name=f"entrance_slit_{i}",
        ))

    return created


# ═══════════════════════════════════════════════════════════════════════════
# Piece 4: Castle Double Door
# ═══════════════════════════════════════════════════════════════════════════

def _door_panel_bmesh(
    outer_x: float,
    inner_x: float,
    z_bottom: float,
    spring_z: float,
    peak_z: float,
    thickness: float,
    arc_segments: int,
    material_name: str,
    obj_name: str,
) -> bpy.types.Object:
    """Build a door PANEL with straight vertical outer and inner edges
    and a QUARTER-ARC top that matches the entrance's arch profile.

    Outline (in the XZ plane at y=0), traced counter-clockwise viewed
    from +Y so the front face's normal points +Y:

              (inner_x, peak_z)  ── arc down and outward ──
                                                            ╲
        (inner_x, z_bottom) ── (outer_x, z_bottom) ── (outer_x, spring_z)

    Then extruded along +Y by `thickness`.  The panel is a single
    convex polygon on each face plus a strip of side quads, ~40 tris
    per panel body.  Panels are LEFT/RIGHT mirrors of each other:
      Left panel:  outer_x = -1.2, inner_x = 0.0  →  arc curves up-right
      Right panel: outer_x = +1.2, inner_x = 0.0  →  arc curves up-left
    """
    bm = bmesh.new()

    # Outline in CCW order (viewed from +Y).  We build the FRONT
    # verts at y=0 and the BACK verts at y=+thickness, then face
    # them in the winding directions that make the normals point
    # outward (front → +Y, back → -Y).
    outline: list[tuple[float, float, float]] = []
    outline.append((outer_x, 0.0, z_bottom))                    # bottom-outer
    outline.append((inner_x, 0.0, z_bottom))                    # bottom-inner
    outline.append((inner_x, 0.0, peak_z))                      # top-inner (arch peak)

    # Arc from theta = 0 (top-inner) sweeping outward to theta = pi/2
    # (top-outer at spring line).  Circle centre at (inner_x, spring_z),
    # radius = |outer_x - inner_x| = OPENING_RADIUS.
    radius = abs(outer_x - inner_x)
    sign = -1.0 if outer_x < inner_x else +1.0
    # Skip the two endpoints (already added / to be added) — just fill
    # the intermediate arc vertices.
    for i in range(1, arc_segments):
        theta = (math.pi / 2.0) * i / arc_segments
        ax = inner_x + sign * radius * math.sin(theta)
        az = spring_z + radius * math.cos(theta)
        outline.append((ax, 0.0, az))
    outline.append((outer_x, 0.0, spring_z))                    # top-outer (arch spring)

    # Create front verts (y=0) and back verts (y=+thickness) in the
    # SAME order as the outline.
    front_verts = [bm.verts.new(v) for v in outline]
    back_verts  = [bm.verts.new((v[0], v[1] + thickness, v[2])) for v in outline]

    bm.verts.ensure_lookup_table()
    # Front face — needs to face -Y (outside of the castle, toward the
    # visitor approaching the door), so we build it in the REVERSE
    # order of our +Y-CCW outline.
    bm.faces.new(list(reversed(front_verts)))
    # Back face — faces +Y (interior of the castle).  Uses the natural
    # outline order.
    bm.faces.new(back_verts)
    # Side quads connecting front-i, back-i to front-i+1, back-i+1.
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        # Winding chosen so side normals point radially outward from
        # the panel body (X-outward for left/right edges, Z-outward
        # for top/bottom edges).
        bm.faces.new([front_verts[i], back_verts[i], back_verts[j], front_verts[j]])

    # Normal recalculation — guarantees consistent outward-facing
    # normals whichever way we wound.
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    mesh = bpy.data.meshes.new(f"{obj_name}_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(obj_name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(make_material(material_name))
    return obj


def _build_one_door_panel(
    side: str,                 # "left" or "right"
    hinge_x: float,            # x of the outer edge (hinge line) in world space
    inner_x: float,            # x of the inner edge (meets the other panel)
) -> list:
    """Build the plank body + all iron hardware for one door panel.

    Everything is built in WORLD coordinates (panel centred between
    hinge_x and inner_x).  The caller is responsible for joining these
    into one object and setting its origin to the hinge line so a
    game engine can rotate the panel around local Z to swing it open.

    Iron hardware layout (matches the reference image):
      - 3 horizontal iron bands across the panel (near top, middle,
        near bottom).
      - ~6 iron studs on each band.
      - 1 ring-pull halfway up, near the inner edge (where the two
        panels meet).
      - 3 iron hinge straps on the outer edge, each with a small
        cylindrical knuckle at the hinge line.
    """
    created: list = []
    panel_thickness = DOOR_THICKNESS
    z_bottom = DOOR_INSET_Z
    front_y = 0.0

    # Panel width & centre for hardware placement.
    outer_x = hinge_x - (DOOR_HINGE_INSET if hinge_x < 0 else -DOOR_HINGE_INSET)
    # Panel body (arched-top bmesh)
    panel = _door_panel_bmesh(
        outer_x=outer_x,
        inner_x=inner_x,
        z_bottom=z_bottom,
        spring_z=OPENING_SPRING_Z,
        peak_z=OPENING_PEAK_Z,
        thickness=panel_thickness,
        arc_segments=ARCH_HALF_SEGMENTS,
        material_name="castle_door_wood",
        obj_name=f"door_panel_{side}",
    )
    created.append(panel)

    # Iron bands — 3 horizontal straps.  Placed at ~15%, ~50%, ~85%
    # of the panel's vertical span (measured up to the spring line;
    # above the spring line the top follows the arch so bands there
    # would need to curve, which we skip for the low-poly budget).
    band_zs = [
        z_bottom + 0.30,
        z_bottom + 1.15,
        z_bottom + 2.05,
    ]
    band_x_center = (outer_x + inner_x) / 2.0
    band_x_size   = abs(outer_x - inner_x) - 0.04    # tiny inset from panel edge
    band_y_size   = panel_thickness + 0.02           # bands sit proud of front / back
    band_z_size   = 0.08
    for bi, bz in enumerate(band_zs):
        created.append(add_box(
            center=(band_x_center, front_y + panel_thickness / 2.0, bz),
            size=(band_x_size, band_y_size, band_z_size),
            material_name="castle_door_iron",
            obj_name=f"door_{side}_band_{bi}",
        ))

    # Iron studs along each band — 5 per band, evenly spaced across
    # the interior width.  Studs are small cylinders sticking out of
    # the front face (-Y direction).
    stud_count_per_band = 5
    stud_radius = 0.03
    stud_depth = 0.03
    stud_y = -stud_depth / 2.0 + 0.005          # protrudes 0.005 m out
    for bi, bz in enumerate(band_zs):
        for si in range(stud_count_per_band):
            u = (si + 0.5) / stud_count_per_band
            sx = outer_x + u * (inner_x - outer_x)
            created.append(add_cylinder(
                center=(sx, stud_y, bz),
                radius=stud_radius,
                height=stud_depth,
                material_name="castle_door_iron",
                obj_name=f"door_{side}_stud_{bi}_{si}",
                axis="Y",
                segments=8,
            ))

    # Ring pull — one per panel, near the inner edge at ~mid-height.
    # The pull is a small mounting plate + a torus ring.
    pull_x = inner_x + (-0.20 if inner_x >= 0.0 else +0.20)
    # Actually the ring should sit at a hand-reachable height (~1.2 m
    # off the ground) and slightly toward the inner edge from centre.
    pull_x = (inner_x + (outer_x - inner_x) * 0.15)
    pull_z = z_bottom + 1.30
    # Backplate — small square iron plate
    created.append(add_box(
        center=(pull_x, front_y + panel_thickness / 2.0, pull_z),
        size=(0.14, panel_thickness + 0.015, 0.14),
        material_name="castle_door_iron",
        obj_name=f"door_{side}_pull_plate",
    ))
    # Ring — torus lying in the XZ plane
    created.append(add_torus(
        center=(pull_x, front_y - 0.02, pull_z - 0.05),
        major_radius=0.06,
        minor_radius=0.012,
        material_name="castle_door_iron",
        obj_name=f"door_{side}_pull_ring",
        axis="Y",
        major_segments=10,
        minor_segments=5,
    ))

    # Hinge straps — 3 iron plates on the outer edge.  Each strap
    # extends from the hinge line INWARD along the panel face.
    # Cylindrical knuckle at the hinge line (rotating on the vertical
    # axis).
    hinge_strap_length = 0.35
    hinge_strap_height = 0.10
    hinge_strap_zs = [z_bottom + 0.20, z_bottom + 1.15, z_bottom + 2.05]
    strap_x_direction = +1.0 if hinge_x < 0.0 else -1.0     # inward from hinge
    for hi, hz in enumerate(hinge_strap_zs):
        # Strap: extends from hinge_x inward.
        strap_center_x = hinge_x + strap_x_direction * hinge_strap_length / 2.0
        # Strap sits on the FRONT face (-Y side of panel).  Y-thickness
        # of the strap is 0.02 m, positioned so its outer surface is
        # 0.005 m off the panel front.
        strap_y = -0.02 / 2.0 - 0.005
        created.append(add_box(
            center=(strap_center_x, strap_y, hz),
            size=(hinge_strap_length, 0.02, hinge_strap_height),
            material_name="castle_door_iron",
            obj_name=f"door_{side}_hinge_strap_{hi}",
        ))
        # Knuckle: small vertical cylinder at the hinge line.
        knuckle_x = hinge_x + strap_x_direction * 0.02      # a hair inboard
        knuckle_r = 0.035
        knuckle_h = 0.14
        created.append(add_cylinder(
            center=(knuckle_x, front_y + panel_thickness / 2.0 - 0.02, hz),
            radius=knuckle_r,
            height=knuckle_h,
            material_name="castle_door_iron",
            obj_name=f"door_{side}_hinge_knuckle_{hi}",
            axis="Z",
            segments=10,
        ))

    return created


def build_double_door() -> list[list]:
    """Build both door panels.  Returns TWO sub-lists — one per panel —
    because unlike the other three pieces we DON'T want to join both
    panels into a single mesh: the game engine needs them separately
    hinged.  Each sub-list is joined into one panel object by the
    caller and gets its origin set to the hinge line.
    """
    left_panel = _build_one_door_panel(
        side="left",
        hinge_x=-OPENING_WIDTH / 2.0,   # -1.2
        inner_x=0.0,
    )
    right_panel = _build_one_door_panel(
        side="right",
        hinge_x=+OPENING_WIDTH / 2.0,   # +1.2
        inner_x=0.0,
    )
    return [left_panel, right_panel]


# ── Join / export helpers (identical to bridge — same handoff) ────────────

def join_group(created: list, final_name: str) -> bpy.types.Object:
    """Join a list of objects into a single mesh, preserve material
    slots.  Returns the joined object with all its transforms already
    baked (per add_box's transform_apply(scale=True) contract)."""
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
    """Bake location / rotation / scale into vertex data so the exported
    object's TRS is identity — matches the bridge / dock convention."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def set_origin_to_point(
    obj: bpy.types.Object,
    world_point: tuple[float, float, float],
) -> None:
    """Move an object's origin to `world_point` without moving its
    vertices in world space.  Used for the two door panels so their
    hinge lines sit at the object origins — a game engine then just
    rotates around local Z to swing the panels open.

    Blender's ORIGIN_CURSOR mode uses the 3D cursor as the new
    origin, and re-expresses every vertex relative to that."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.context.scene.cursor.location = world_point
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")


def export_glb_single(obj: bpy.types.Object, out_path: str) -> None:
    """Export a single object with a fully-baked identity TRS."""
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
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
    )


def export_glb_multi_preserve_transforms(
    objs: list[bpy.types.Object],
    out_path: str,
) -> None:
    """Export multiple objects together, PRESERVING each object's
    location / rotation so origin-at-hinge information survives to
    glTF's node TRS.  Used exclusively for the double-door export."""
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        # export_apply=True would BAKE transforms into geometry — the
        # opposite of what we want.  It's default-False, but be
        # explicit here for future readers.
        export_apply=False,
        export_materials="EXPORT",
    )


def compute_bounds(obj: bpy.types.Object):
    mw = obj.matrix_world
    verts = [mw @ v.co for v in obj.data.vertices]
    xs = [v.x for v in verts]; ys = [v.y for v in verts]; zs = [v.z for v in verts]
    return ((min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs)))


def report_mesh(obj: bpy.types.Object, label: str) -> None:
    n_verts = len(obj.data.vertices)
    n_faces = len(obj.data.polygons)
    n_tris  = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    n_slots = len(obj.data.materials)
    slot_names = ", ".join(m.name if m else "<none>" for m in obj.data.materials)
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = compute_bounds(obj)
    print(f"  [{label}] verts={n_verts}, faces={n_faces}, tris={n_tris}, "
          f"materials={n_slots}: {slot_names}")
    print(f"  [{label}] bounds: X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  "
          f"Z[{z_min:+.3f}, {z_max:+.3f}]")


# ── Main ──────────────────────────────────────────────────────────────────

def _fresh_scene() -> None:
    """Reset Blender to an empty scene before each piece.  A shared
    process would otherwise accumulate materials / objects across
    pieces, and normalize_transform's active-object rules would get
    confused."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def build_and_export_pillar() -> None:
    print("\n=== Castle Pillar ===")
    _fresh_scene()
    created = build_pillar()
    print(f"  built pieces: {len(created)}")
    pillar = join_group(created, "castle_pillar")
    report_mesh(pillar, "pillar")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastlePillar.glb")
        export_glb_single(pillar, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_wall_segment() -> None:
    print("\n=== Castle Wall Segment ===")
    _fresh_scene()
    created = build_wall_segment()
    print(f"  built pieces: {len(created)}")
    wall = join_group(created, "castle_wall_segment")
    report_mesh(wall, "wall_segment")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastleWallSegment.glb")
        export_glb_single(wall, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_wall_segment_window() -> None:
    print("\n=== Castle Wall Window ===")
    _fresh_scene()
    created = build_wall_segment_window()
    print(f"  built pieces: {len(created)}")
    wall = join_group(created, "castle_wall_window")
    report_mesh(wall, "wall_window")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastleWallWindow.glb")
        export_glb_single(wall, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_wall_window_frame() -> None:
    print("\n=== Castle Wall Window Frame ===")
    _fresh_scene()
    created = build_wall_window_frame(
        wood_mat="castle_window_wood",
        glass_mat="castle_glass",
        name_prefix="winframe",
    )
    print(f"  built pieces: {len(created)}")
    frame = join_group(created, "castle_wall_window_frame")
    report_mesh(frame, "wall_window_frame")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastleWallWindowFrame.glb")
        export_glb_single(frame, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_wall_window_frame_clear() -> None:
    print("\n=== Castle Wall Window Frame Clear ===")
    _fresh_scene()
    created = build_wall_window_frame(
        wood_mat="castle_window_wood",
        glass_mat="castle_glass_clear",
        name_prefix="winframe_clear",
        with_mullions=True,
    )
    print(f"  built pieces: {len(created)}")
    frame = join_group(created, "castle_wall_window_frame_clear")
    report_mesh(frame, "wall_window_frame_clear")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastleWallWindowFrameClear.glb")
        export_glb_single(frame, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_wall_window_frame_open() -> None:
    print("\n=== Castle Wall Window Frame Open ===")
    _fresh_scene()
    created = build_wall_window_frame(
        wood_mat="castle_window_wood",
        glass_mat="castle_glass_clear",
        name_prefix="winframe_open",
        with_mullions=False,
    )
    print(f"  built pieces: {len(created)}")
    frame = join_group(created, "castle_wall_window_frame_open")
    report_mesh(frame, "wall_window_frame_open")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastleWallWindowFrameOpen.glb")
        export_glb_single(frame, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_wall_window_frame_plain() -> None:
    print("\n=== Castle Wall Window Frame Plain ===")
    _fresh_scene()
    created = build_wall_window_frame(
        wood_mat="castle_window_wood",
        glass_mat="castle_glass",
        name_prefix="winframe_plain",
        with_mullions=False,
    )
    print(f"  built pieces: {len(created)}")
    frame = join_group(created, "castle_wall_window_frame_plain")
    report_mesh(frame, "wall_window_frame_plain")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastleWallWindowFramePlain.glb")
        export_glb_single(frame, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_entrance() -> None:
    print("\n=== Castle Entrance (Arched) ===")
    _fresh_scene()
    created = build_entrance()
    print(f"  built pieces: {len(created)}")
    entrance = join_group(created, "castle_entrance")
    report_mesh(entrance, "entrance")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastleEntrance.glb")
        export_glb_single(entrance, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_double_door() -> None:
    print("\n=== Castle Double Door ===")
    _fresh_scene()
    left_pieces, right_pieces = build_double_door()
    print(f"  built pieces: left={len(left_pieces)}, right={len(right_pieces)}")

    left_panel  = join_group(left_pieces,  "castle_door_left")
    # Set origin at the LEFT panel's hinge — the outer bottom corner.
    # Note the panel's outer edge is at hinge_x = -OPENING_WIDTH/2 = -1.2.
    # Y = DOOR_THICKNESS / 2 so rotation is around the CENTRE of the
    # panel's thickness (typical hinge axis).
    set_origin_to_point(
        left_panel,
        world_point=(-OPENING_WIDTH / 2.0, DOOR_THICKNESS / 2.0, 0.0),
    )
    report_mesh(left_panel, "door_left")

    right_panel = join_group(right_pieces, "castle_door_right")
    set_origin_to_point(
        right_panel,
        world_point=(+OPENING_WIDTH / 2.0, DOOR_THICKNESS / 2.0, 0.0),
    )
    report_mesh(right_panel, "door_right")

    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastleDoubleDoor.glb")
        export_glb_multi_preserve_transforms([left_panel, right_panel], out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)  (2 hinged sub-objects: "
              f"castle_door_left, castle_door_right)")


def build_and_export_pillar_rect_cone() -> None:
    print("\n=== Castle Pillar Cone (rectangular) ===")
    _fresh_scene()
    created = build_pillar_rect_cone()
    print(f"  built pieces: {len(created)}")
    pillar = join_group(created, "castle_pillar_cone")
    report_mesh(pillar, "pillar_cone")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastlePillarCone.glb")
        export_glb_single(pillar, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def build_and_export_pillar_round_cone() -> None:
    print("\n=== Castle Pillar Round Cone ===")
    _fresh_scene()
    created = build_pillar_round_cone()
    print(f"  built pieces: {len(created)}")
    pillar = join_group(created, "castle_pillar_round_cone")
    report_mesh(pillar, "pillar_round_cone")
    for out_dir in (SOURCE_DIR, VIEWER_DIR):
        out_path = os.path.join(out_dir, "CastlePillarRoundCone.glb")
        export_glb_single(pillar, out_path)
        size_kb = os.path.getsize(out_path) / 1024.0
        print(f"  -> {out_path} ({size_kb:.1f} KB)")


def main() -> None:
    print(f"Source output dir: {SOURCE_DIR}")
    print(f"Viewer output dir: {VIEWER_DIR}")
    print(f"Shared opening:  width={OPENING_WIDTH:.2f} m, "
          f"spring_z={OPENING_SPRING_Z:.2f} m, peak_z={OPENING_PEAK_Z:.2f} m")

    only = {a.lower() for a in sys.argv[1:] if not a.startswith("-")}
    # Allow `blender --python script.py -- cone` style filters
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        only |= {a.lower() for a in sys.argv[idx + 1:] if not a.startswith("-")}

    def want(*keys: str) -> bool:
        if not only:
            return True
        return any(k in only for k in keys)

    if want("pillar"):
        build_and_export_pillar()
    if want("wall"):
        build_and_export_wall_segment()
    if want("window", "wallwindow"):
        build_and_export_wall_segment_window()
    if want("frame", "windowframe"):
        build_and_export_wall_window_frame()
    if want("clear", "frameclear", "windowframeclear"):
        build_and_export_wall_window_frame_clear()
    if want("open", "frameopen", "windowframeopen"):
        build_and_export_wall_window_frame_open()
    if want("plain", "frameplain", "windowframeplain"):
        build_and_export_wall_window_frame_plain()
    if want("entrance"):
        build_and_export_entrance()
    if want("door"):
        build_and_export_double_door()
    if want("cone", "rect", "pillarcone"):
        build_and_export_pillar_rect_cone()
    if want("round", "roundcone", "pillarround"):
        build_and_export_pillar_round_cone()

    print("\nDONE — castle wall set exported.")


if __name__ == "__main__":
    main()
