"""
weight_ranged_set.py
====================
Generic return-trip script for Ranged Armor sets (Green / Purple / Black /
Red / Blue).  Processes Meshy-textured GLB pieces and produces
*Weighted.glb  outputs ready to drop into  viewer/public/equipment/Female/.

Piece types supported:
  - "hat"       → 48-combo axis calibration + 100% head-bone weighting
  - "upperbody" → 48-combo axis calibration + KD weight transfer
  - "lowerbody" → 48-combo axis calibration + KD weight transfer
  - "boots"     → 48-combo axis calibration + KD weight transfer

Gloves use the separate bilateral pipeline (`weight_meshy_gloves.py`).

Non-destructive:  Inputs are read from `<Piece>.glb` and outputs are written
to `<Piece>Weighted.glb`.  The Meshy source file is never overwritten.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_ranged_set.py
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_ranged_set.py -- --only=green_ranged_hat
"""

import os
import sys
import math
import json
import struct
import itertools
import bpy
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree


def _to_path_list(spec):
    """Normalise a string-or-list `spec` into a list of paths.  Used by the
    multi-shell return-trip configs (e.g. the metal Platebody was textured
    from a joined upload of `shell_v1_lower_torso + shell_v1_upper_torso +
    shell_v1_arm_upper`, so its `scale_reference`, `surface_conform`, and
    `weight_source` are all 3-element lists)."""
    if spec is None:
        return []
    if isinstance(spec, str):
        return [spec]
    if isinstance(spec, (list, tuple)):
        return list(spec)
    return []


def read_glb_position_bbox(path_or_paths):
    """Read POSITION-accessor bboxes across one or more GLBs and return the
    UNION (min, max) as 3-tuples in the GLB's native units (typically metres).
    Returns (None, None) on failure.

    Accepts either a single string path or a list of string paths so a
    multi-shell upload (e.g. lower_torso + upper_torso + arm_upper joined in
    Blender before Meshy texturing) can be referenced as one logical
    `scale_reference`.

    Goes straight to the GLB header — no Blender import, no armature / bone
    / helper objects polluting the bbox.  Iterates EVERY mesh primitive in
    each file (older versions only checked the first primitive, which could
    miss verts in multi-primitive meshes).
    """
    paths = _to_path_list(path_or_paths)
    if not paths:
        return None, None

    u_min = [float("inf"), float("inf"), float("inf")]
    u_max = [float("-inf"), float("-inf"), float("-inf")]
    found_any = False
    for path in paths:
        try:
            with open(path, "rb") as f:
                data = f.read()
            if data[:4] != b"glTF":
                continue
            json_len = struct.unpack("<I", data[12:16])[0]
            j = json.loads(data[20:20 + json_len].decode("utf-8"))
            for m in j.get("meshes", []):
                for p in m.get("primitives", []):
                    pos_idx = p.get("attributes", {}).get("POSITION")
                    if pos_idx is None:
                        continue
                    acc = j["accessors"][pos_idx]
                    if "min" not in acc or "max" not in acc:
                        continue
                    for k in range(3):
                        u_min[k] = min(u_min[k], acc["min"][k])
                        u_max[k] = max(u_max[k], acc["max"][k])
                    found_any = True
        except (OSError, ValueError, KeyError):
            continue
    if not found_any:
        return None, None
    return tuple(u_min), tuple(u_max)

sys.stdout.reconfigure(line_buffering=True)

BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")

EQUIP_DIR = os.path.abspath("viewer/public/equipment/Female")


def _piece(color_id: str, color_name: str, piece_type: str, subfolder: str, file_base: str, regions):
    """Build a piece dict.
    color_id   e.g. 'green', used in slot id:  <color>_ranged_<piece_type>
    file_base  e.g. 'GreenRangedHat'  → source  .glb, output  Weighted.glb.
    """
    src = os.path.join(EQUIP_DIR, subfolder, f"{file_base}.glb")
    out = os.path.join(EQUIP_DIR, subfolder, f"{file_base}Weighted.glb")
    return {
        "name":       f"{color_id}_ranged_{piece_type}",
        "display":    f"{color_name} Ranged: {piece_type.capitalize()}",
        "piece_type": piece_type,
        "src":        src,
        "out":        out,
        "regions":    regions,
    }


REGIONS = {
    "hat":       ["base_body_head"],
    "upperbody": [
        "base_body_upper_torso",
        "base_body_lower_torso",
        "base_body_arm_upper",
        "base_body_arm_lower",
    ],
    "lowerbody": [
        "base_body_leg_upper",
        "base_body_leg_thigh",
        "base_body_leg_knee",
        "base_body_leg_shin",
        "base_body_leg_ankle",
    ],
    "boots": [
        "base_body_foot",
        "base_body_leg_ankle",
    ],
}


def _set(color_id: str, color_name: str):
    """Return the 4 pieces (hat/upper/lower/boots) for one colour."""
    return [
        _piece(color_id, color_name, "hat",       "Hats",      f"{color_name}RangedHat",       REGIONS["hat"]),
        _piece(color_id, color_name, "upperbody", "Upperbody", f"{color_name}RangedUpperbody", REGIONS["upperbody"]),
        _piece(color_id, color_name, "lowerbody", "Lowerbody", f"{color_name}RangedLowerbody", REGIONS["lowerbody"]),
        _piece(color_id, color_name, "boots",     "Boots",     f"{color_name}RangedBoots",     REGIONS["boots"]),
    ]


PIECES = []
PIECES += _set("green",   "Green")
PIECES += _set("leather", "Leather")
PIECES += _set("red",     "Red")
PIECES += _set("purple",  "Purple")
PIECES += _set("black",   "Black")
PIECES += _set("blue",    "Blue")

# One-off Meshy-textured robe.  Lives in the Robes subfolder, but follows
# the same lowerbody pipeline as ranged-armor lowerbody pieces (48-combo
# axis calibration + KD weight transfer from the full leg region stack).
#
# `post_rotation_deg`:  optional Euler XYZ degrees applied AFTER the 48-combo
# calibration, around the mesh's own center, to correct cases where the
# auto-axis-fit picks an upside-down or yawed orientation (a robe's
# "narrow-at-top, wide-at-bottom" shape is the opposite of the body's
# "wide-at-hip, narrow-at-ankle" silhouette, so the fitter sometimes
# inverts vertical axis to score a closer bbox match).
PIECES.append({
    "name":              "robe_test",
    "display":           "Robe Test",
    "piece_type":        "lowerbody",
    "src":               os.path.join(EQUIP_DIR, "Robes", "RobeTest.glb"),
    "out":               os.path.join(EQUIP_DIR, "Robes", "RobeTestWeighted.glb"),
    "regions":           REGIONS["lowerbody"],
    "post_rotation_deg": [180.0, 90.0, 0.0],   # flip upside-down (X=pitch) + yaw 90° (Y=vertical in body frame)
    # After rotation, refit per-axis (no axis swap) to this reference GLB's
    # bbox so the textured robe ends up at the EXACT same dimensions as the
    # original shell that was uploaded to Meshy.
    "scale_reference":   os.path.join(EQUIP_DIR, "Robes", "robe_v2.glb"),
    # Copy weights directly from the well-weighted procedural shell instead
    # of re-deriving them from body skin.  robe_v2's weights were tuned for
    # cloth-style deformation (waist→Hips, mid→symmetric-leg-blend, hem→feet),
    # and since the textured mesh has the same shape as that shell, a
    # nearest-vertex transfer yields identical animation behaviour even
    # though robe_test has ~2× the vertex count from Meshy's UV seams.
    "weight_source":     os.path.join(EQUIP_DIR, "Robes", "robe_v2.glb"),
})

# ----------------------------------------------------------------------
# Magic Armor "robes" — lowerbody piece is a robe bottom, textured in
# Meshy starting from the same `robe_v2.glb` shell as `robe_test` above.
# Identical return-trip pipeline:  post_rotation to undo the auto-fit's
# upside-down pick, scale_reference + weight_source both pointed at the
# procedural robe_v2 so the textured mesh inherits exact shape and the
# tuned cloth weight map.  Add one entry per colour as new files arrive.
#
# Robe weight-post-boost (shared across all colours):  robe_v2's hem weights
# are biased toward Hips/UpLeg, so the robe's lower portion under-follows
# the shin during stride animations and the body's shin geometry pokes
# through the front of the skirt.  Boost the shin bones (LeftLeg /
# RightLeg) on verts below the knee (y < 65 cm) so each robe half tracks
# its own shin when that leg swings forward.  NOTE: vertex-group names in
# the source weight_source (robe_v2.glb) carry Blender's bone-name colon
# prefix (`mixamorig:LeftLeg`), not the stripped form used elsewhere in
# the viewer (`mixamorigLeftLeg`).  side_split=True keeps each side
# asymmetric — left robe verts follow only LeftLeg, right verts follow
# only RightLeg — which gives the cleanest left-leg behaviour at the cost
# of a known residual right-side clip at the front-centre hem.  User has
# chosen to live with the residual right-side clip rather than the
# symmetric clipping that side_split=False produces.
_MAGE_ROBE_WEIGHT_POST_BOOST = {
    "y_below": 65.0,
    "boost": {
        "mixamorig:LeftLeg":  10.0,
        "mixamorig:RightLeg": 10.0,
    },
    "suppress": {
        "mixamorig:Hips":         0.1,
        "mixamorig:LeftUpLeg":    0.2,
        "mixamorig:RightUpLeg":   0.2,
    },
    "side_split": True,
}

PIECES.append({
    "name":              "leather_magic_armor_lowerbody",
    "display":           "Leather Magic: Lowerbody",
    "piece_type":        "lowerbody",
    "src":               os.path.join(EQUIP_DIR, "Robes", "LeatherMageLowerbody.glb"),
    "out":               os.path.join(EQUIP_DIR, "Robes", "LeatherMageLowerbodyWeighted.glb"),
    "regions":           REGIONS["lowerbody"],
    # Leather needs an EXTRA 90° yaw vs the 5 colour Mage robes because
    # the 48-combo fitter picks a different axis mapping for leather's
    # slightly non-cubic source bbox (1.67 × 2.00 × 1.50) than for the
    # cubic colour robes (1.70 × 2.00 × 1.70):
    #   colour: body[XYZ] ← meshy[XZY]  (meshy +Y → body +Z, body's front)
    #   leather: body[XYZ] ← meshy[YZX]  (meshy +Y → body +X, body's side)
    # X=180 flips the auto-fitter's upside-down pick (shared with all
    # robes); Y=90 swings leather's front panel from body +X back to
    # body's actual front, matching the colour robes' final orientation.
    "post_rotation_deg": [180.0, 90.0, 0.0],
    "scale_reference":   os.path.join(EQUIP_DIR, "Robes", "robe_v2.glb"),
    "surface_conform":   os.path.join(EQUIP_DIR, "Robes", "robe_v2.glb"),
    "weight_source":     os.path.join(EQUIP_DIR, "Robes", "robe_v2.glb"),
    "weight_post_boost": _MAGE_ROBE_WEIGHT_POST_BOOST,
})


# Per-colour Mage robe lowerbody.  Sources live in viewer/Robes/ named
# `<Color>MageLowerbody.glb` (Blender naming convention used when the
# Meshy outputs were copied in from the desktop staging folder).  Same
# robe_v2 reference and weight_post_boost as the leather entry above,
# PLUS a `surface_conform` step.
#
# Why surface_conform here but not on leather:
#   The 5 colour Mage Bottoms were uploaded to Meshy after a different
#   normalisation pass than the leather one — their source bboxes are
#   perfectly square in XZ (1.70 × 2.00 × 1.70), whereas leather's is
#   1.67 × 2.00 × 1.50, which already matches `robe_v2.glb`'s
#   0.66 × 0.79 × 0.59 proportions to within a fraction of a percent.
#   Bbox-fitting the cubic colour sources to robe_v2's flatter
#   proportions therefore applies a non-uniform per-axis scale (≈12 %
#   tighter on Z than on X), and the waist ring of the colour robes
#   ends up slightly wider than the upperbody waist — visible as a
#   misalignment at the Top↔Bottom seam.  BVH-snapping to robe_v2's
#   surface erases that warp, the same trick used for the metal
#   Plateskirts where their Meshy outputs share skirt_v2's shape but
#   need a clean per-vertex projection rather than a per-axis stretch.
def _mage_lowerbody(color_id: str, color_name: str):
    src = os.path.join(EQUIP_DIR, "Robes", f"{color_name}MageLowerbody.glb")
    out = os.path.join(EQUIP_DIR, "Robes", f"{color_name}MageLowerbodyWeighted.glb")
    robe_v2 = os.path.join(EQUIP_DIR, "Robes", "robe_v2.glb")
    return {
        "name":              f"{color_id}_magic_armor_lowerbody",
        "display":           f"{color_name} Magic: Lowerbody",
        "piece_type":        "lowerbody",
        "src":               src,
        "out":               out,
        "regions":           REGIONS["lowerbody"],
        "post_rotation_deg": [180.0, 0.0, 0.0],  # see leather_magic_armor_lowerbody comment
        "scale_reference":   robe_v2,
        "surface_conform":   robe_v2,
        "weight_source":     robe_v2,
        "weight_post_boost": _MAGE_ROBE_WEIGHT_POST_BOOST,
    }


PIECES.append(_mage_lowerbody("green",  "Green"))
PIECES.append(_mage_lowerbody("blue",   "Blue"))
PIECES.append(_mage_lowerbody("red",    "Red"))
PIECES.append(_mage_lowerbody("black",  "Black"))
PIECES.append(_mage_lowerbody("purple", "Purple"))


# ----------------------------------------------------------------------
# Magic Armor hats / tops / boots — same Meshy return-trip pipeline as
# the Ranged equivalents (48-combo axis calibration + KD weight transfer
# from the body region stack).  Source filenames use the "Mage" Blender
# convention (`<Color>MageHat`, `<Color>MageTop`, `<Color>MageBoots`)
# rather than the Ranged "<Color>Ranged*" convention, so we can't reuse
# the `_set` helper above.
def _mage_hat(color_id: str, color_name: str):
    src = os.path.join(EQUIP_DIR, "Hats",      f"{color_name}MageHat.glb")
    out = os.path.join(EQUIP_DIR, "Hats",      f"{color_name}MageHatWeighted.glb")
    return {
        "name":       f"{color_id}_magic_armor_hat",
        "display":    f"{color_name} Magic: Hat",
        "piece_type": "hat",
        "src":        src,
        "out":        out,
        "regions":    REGIONS["hat"],
    }


def _mage_upperbody(color_id: str, color_name: str):
    src = os.path.join(EQUIP_DIR, "Upperbody", f"{color_name}MageTop.glb")
    out = os.path.join(EQUIP_DIR, "Upperbody", f"{color_name}MageTopWeighted.glb")
    return {
        "name":       f"{color_id}_magic_armor_upperbody",
        "display":    f"{color_name} Magic: Top",
        "piece_type": "upperbody",
        "src":        src,
        "out":        out,
        "regions":    REGIONS["upperbody"],
    }


def _mage_boots(color_id: str, color_name: str):
    src = os.path.join(EQUIP_DIR, "Boots",     f"{color_name}MageBoots.glb")
    out = os.path.join(EQUIP_DIR, "Boots",     f"{color_name}MageBootsWeighted.glb")
    return {
        "name":       f"{color_id}_magic_armor_boots",
        "display":    f"{color_name} Magic: Boots",
        "piece_type": "boots",
        "src":        src,
        "out":        out,
        "regions":    REGIONS["boots"],
    }


_MAGE_NAMES = [
    ("leather", "Leather"),
    ("green",   "Green"),
    ("blue",    "Blue"),
    ("red",     "Red"),
    ("black",   "Black"),
    ("purple",  "Purple"),
]

for _cid, _cname in _MAGE_NAMES:
    PIECES.append(_mage_hat(_cid, _cname))
    PIECES.append(_mage_upperbody(_cid, _cname))
    PIECES.append(_mage_boots(_cid, _cname))


# ----------------------------------------------------------------------
# Metal Armor Plateskirts (Iron / Steel / Gold / Titanium / Tungsten /
# Luminous).  Same return-trip workflow as the robe: Meshy was given the
# procedural skirt_v2.glb shell to texture, then handed back GLBs that share
# the shell's exact shape but lack rigging, scaling, and the skirt_v2
# weight map.  We rebuild all three from skirt_v2 itself — same trick as
# `robe_test` above — by using it as both `scale_reference` and
# `weight_source`.  The `post_rotation_deg [180, 0, 0]` correction
# (X=pitch flip; no yaw) handles the auto-fitter's upside-down pick
# while leaving the source's natural front-facing direction intact —
# adding a Y yaw would swing the front panel onto the body's side.
def _plateskirt(metal_id: str, metal_name: str, file_base: str):
    src = os.path.join(EQUIP_DIR, "Lowerbody", f"{file_base}.glb")
    out = os.path.join(EQUIP_DIR, "Lowerbody", f"{file_base}Weighted.glb")
    skirt_v2 = os.path.join(EQUIP_DIR, "Skirts", "skirt_v2.glb")
    return {
        "name":              f"{metal_id}_armor_lowerbody",
        "display":           f"{metal_name} Plateskirt",
        "piece_type":        "lowerbody",
        "src":               src,
        "out":               out,
        "regions":           REGIONS["lowerbody"],
        "post_rotation_deg": [180.0, 0.0, 0.0],
        "scale_reference":   skirt_v2,
        # Surface conform fixes the waist-line cross-section.  The bbox refit
        # locks the top and bottom AABB rings to skirt_v2's dimensions, but the
        # per-axis scaling subtly warps everything in between (anatomical X/Z
        # ratio drifts toward circular and centroid wanders), making the waist
        # appear wider than skirt_v2's.  BVH snap to skirt_v2's surface erases
        # that distortion and gives an exact silhouette match.
        "surface_conform":   skirt_v2,
        "weight_source":     skirt_v2,
    }


PIECES.append(_plateskirt("iron",      "Iron",      "IronPlateskirt"))
PIECES.append(_plateskirt("steel",     "Steel",     "SteelPlateskirt"))
PIECES.append(_plateskirt("gold",      "Gold",      "GoldPlateskirt"))
PIECES.append(_plateskirt("titanium",  "Titanium",  "TitaniumPlateskirt"))
PIECES.append(_plateskirt("tungsten",  "Tungsten",  "TungstenPlateskirt"))
PIECES.append(_plateskirt("luminous",  "Luminous",  "LuminousPlateskirt"))


# Metal armor upperbody (Platebody) + boots.
#
# Platebody: the user uploaded a JOINED shell to Meshy made from
#   shell_v1_lower_torso + shell_v1_upper_torso + shell_v1_arm_upper
# (joined in Blender).  Same return-trip trick as `robe_test` and the
# plateskirts:  treat the joined shell as the canonical ground truth via
# scale_reference + surface_conform + weight_source, all pointing at the
# 3-file list.  read_glb_position_bbox / assign_kd_weights_from_glb /
# conform_to_glb_surface all accept list inputs and union the data, so the
# textured Platebody ends up at the EXACT shape and weighting of the joined
# shell — no per-axis bbox distortion across the arm/torso boundaries.
#
# Boots: no scale_reference needed; the metal boots share their shell with
# the existing Ranged boots (same vertex topology, identical bbox), so the
# default 48-combo + body-region KD weight transfer fits cleanly.
_PLATEBODY_SHELL_PARTS = [
    os.path.join(EQUIP_DIR, "ShellV1", "shell_v1_lower_torso.glb"),
    os.path.join(EQUIP_DIR, "ShellV1", "shell_v1_upper_torso.glb"),
    os.path.join(EQUIP_DIR, "ShellV1", "shell_v1_arm_upper.glb"),
]


def _metal_platebody(metal_id: str, metal_name: str):
    src = os.path.join(EQUIP_DIR, "Upperbody", f"{metal_name}Platebody.glb")
    out = os.path.join(EQUIP_DIR, "Upperbody", f"{metal_name}PlatebodyWeighted.glb")
    return {
        "name":            f"{metal_id}_armor_upperbody",
        "display":         f"{metal_name} Platebody",
        "piece_type":      "upperbody",
        "src":             src,
        "out":             out,
        "regions":         REGIONS["upperbody"],
        "scale_reference": _PLATEBODY_SHELL_PARTS,
        "surface_conform": _PLATEBODY_SHELL_PARTS,
        "weight_source":   _PLATEBODY_SHELL_PARTS,
    }


def _metal_boots(metal_id: str, metal_name: str):
    src = os.path.join(EQUIP_DIR, "Boots", f"{metal_name}Boots.glb")
    out = os.path.join(EQUIP_DIR, "Boots", f"{metal_name}BootsWeighted.glb")
    return {
        "name":       f"{metal_id}_armor_boots",
        "display":    f"{metal_name} Plate Boots",
        "piece_type": "boots",
        "src":        src,
        "out":        out,
        "regions":    REGIONS["boots"],
    }


# NOTE: Metal Gauntlets (Iron/Steel/Gold/Titanium/Tungsten/Luminous Gloves)
# are processed by `weight_meshy_gloves.py` — same pipeline as every Ranged
# colour, with an `axis_override` that forces the same axis mapping the
# auto-fitter discovers for Ranged.  We tried routing them through this
# script's scale_reference + surface_conform path but it required collapsing
# the gauntlet geometry into the hand-only shell bbox, which lost the sleeve
# shape and visibly distorted the textures.
_METAL_NAMES = [
    ("iron",     "Iron"),
    ("steel",    "Steel"),
    ("gold",     "Gold"),
    ("titanium", "Titanium"),
    ("tungsten", "Tungsten"),
    ("luminous", "Luminous"),
]

# ----------------------------------------------------------------------
# Metal Armor Helmets — Meshy-textured head pieces.  Sources were
# uploaded to Meshy starting from the procedural `shell_v1_head.glb`,
# so they share that shell's exact shape (only the texture differs).
# Same return-trip pipeline as the metal Platebody: feed shell_v1_head
# in as `scale_reference` + `surface_conform` + `weight_source` so the
# textured helmet ends up at the EXACT shape, scale and weighting of
# the original head shell — no per-axis bbox distortion or 48-combo
# calibration drift.
_HELMET_SHELL = os.path.join(EQUIP_DIR, "ShellV1", "shell_v1_head.glb")


def _metal_helmet(metal_id: str, metal_name: str):
    src = os.path.join(EQUIP_DIR, "Hats", f"{metal_name}Helmet.glb")
    out = os.path.join(EQUIP_DIR, "Hats", f"{metal_name}HelmetWeighted.glb")
    return {
        "name":            f"{metal_id}_armor_head",
        "display":         f"{metal_name} Helmet",
        "piece_type":      "hat",
        "src":             src,
        "out":             out,
        "regions":         REGIONS["hat"],
        # Presence of `scale_reference` automatically routes the helmet
        # through the 48-combo + bbox-aware path instead of the
        # wizard-hat-shape `place_hat_on_head` algorithm (which assumes
        # a narrow crown + wide brim).  After 48-combo aligns the helmet
        # to the head region's bbox, the `scale_reference` refit and
        # `surface_conform` snap give it shell_v1_head's exact shape and
        # weights.
        "scale_reference": _HELMET_SHELL,
        "surface_conform": _HELMET_SHELL,
        "weight_source":   _HELMET_SHELL,
    }


for _mid, _mname in _METAL_NAMES:
    PIECES.append(_metal_helmet(_mid, _mname))
    PIECES.append(_metal_platebody(_mid, _mname))
    PIECES.append(_metal_boots(_mid, _mname))


# ----------------------------------------------------------------------
# Default Armor — a starter outfit textured in Meshy on the same shells
# as the production sets, so each piece can be routed through the exact
# same return-trip pipeline as its sibling:
#
#   - DefaultBootsFemale.glb     uses the same shell as the metal boots
#                                (Iron / Steel / Gold / ...): no
#                                scale_reference needed, the default
#                                48-combo + body-region KD weight
#                                transfer fits the topology cleanly.
#
#   - DefaultLowerbodyFemale.glb uses the same shell as the coloured
#                                Ranged lowerbody pieces (Green / Blue /
#                                Red / ...): again no scale_reference;
#                                the default pipeline handles it.
#
#   - DefaultUpperbodyFemale.glb uses the SAME joined shell as the metal
#                                Platebody (lower_torso + upper_torso +
#                                arm_upper, joined in Blender before
#                                Meshy texturing), so it gets the
#                                _PLATEBODY_SHELL_PARTS list as
#                                scale_reference + surface_conform +
#                                weight_source.
#
# Source filenames don't match the metal/ranged conventions, so these
# are declared inline rather than via the _metal_* / _piece helpers.
PIECES.append({
    "name":       "default_armor_boots",
    "display":    "Default Boots",
    "piece_type": "boots",
    "src":        os.path.join(EQUIP_DIR, "Boots", "DefaultBootsFemale.glb"),
    "out":        os.path.join(EQUIP_DIR, "Boots", "DefaultBootsFemaleWeighted.glb"),
    "regions":    REGIONS["boots"],
})

PIECES.append({
    "name":       "default_armor_lowerbody",
    "display":    "Default Lowerbody",
    "piece_type": "lowerbody",
    "src":        os.path.join(EQUIP_DIR, "Lowerbody", "DefaultLowerbodyFemale.glb"),
    "out":        os.path.join(EQUIP_DIR, "Lowerbody", "DefaultLowerbodyFemaleWeighted.glb"),
    "regions":    REGIONS["lowerbody"],
})

PIECES.append({
    "name":            "default_armor_upperbody",
    "display":         "Default Upperbody",
    "piece_type":      "upperbody",
    "src":             os.path.join(EQUIP_DIR, "Upperbody", "DefaultUpperbodyFemale.glb"),
    "out":             os.path.join(EQUIP_DIR, "Upperbody", "DefaultUpperbodyFemaleWeighted.glb"),
    "regions":         REGIONS["upperbody"],
    "scale_reference": _PLATEBODY_SHELL_PARTS,
    "surface_conform": _PLATEBODY_SHELL_PARTS,
    "weight_source":   _PLATEBODY_SHELL_PARTS,
})


WEIGHT_NEIGHBORS = 12
WEIGHT_POWER = 1.5
MAX_INFLUENCES = 4


# ----------------------------------------------------------------------
# Low-level utilities (lifted verbatim from weight_green_ranged_armor.py)
# ----------------------------------------------------------------------

def suppress():
    dn = open(os.devnull, "w")
    s = os.dup(1)
    os.dup2(dn.fileno(), 1)
    return s, dn


def restore(s, dn):
    os.dup2(s, 1)
    os.close(s)
    dn.close()


def local_bounds(obj):
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def normalize_mesh(mesh_obj):
    verts = mesh_obj.data.vertices
    if len(verts) == 0:
        return
    xs = [v.co.x for v in verts]
    ys = [v.co.y for v in verts]
    zs = [v.co.z for v in verts]
    center = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    half_ext = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)) / 2
    if half_ext < 1e-6:
        return
    for v in verts:
        v.co = (v.co - center) / half_ext
    mesh_obj.data.update()


def remap_meshy_to_body(meshy_mesh, body_objs):
    mverts = meshy_mesh.data.vertices
    if len(mverts) == 0:
        return False

    m_xs = [v.co.x for v in mverts]
    m_ys = [v.co.y for v in mverts]
    m_zs = [v.co.z for v in mverts]
    m_min = Vector((min(m_xs), min(m_ys), min(m_zs)))
    m_max = Vector((max(m_xs), max(m_ys), max(m_zs)))
    m_range = m_max - m_min

    max_extent = max(m_range.x, m_range.y, m_range.z)
    if max_extent > 5.0:
        print(f"  Mesh in body scale (max extent: {max_extent:.1f}), normalizing first...")
        normalize_mesh(meshy_mesh)
        mverts = meshy_mesh.data.vertices
        m_xs = [v.co.x for v in mverts]
        m_ys = [v.co.y for v in mverts]
        m_zs = [v.co.z for v in mverts]
        m_min = Vector((min(m_xs), min(m_ys), min(m_zs)))
        m_max = Vector((max(m_xs), max(m_ys), max(m_zs)))
        m_range = m_max - m_min

    b_xs, b_ys, b_zs = [], [], []
    for obj in body_objs:
        for v in obj.data.vertices:
            b_xs.append(v.co.x)
            b_ys.append(v.co.y)
            b_zs.append(v.co.z)
    if not b_xs:
        return False

    b_min = Vector((min(b_xs), min(b_ys), min(b_zs)))
    b_max = Vector((max(b_xs), max(b_ys), max(b_zs)))
    b_range = b_max - b_min
    b_center = (b_min + b_max) / 2
    m_center = (m_min + m_max) / 2

    print(f"  Body bounds:  X=[{b_min.x:.1f},{b_max.x:.1f}] "
          f"Y=[{b_min.y:.1f},{b_max.y:.1f}] Z=[{b_min.z:.1f},{b_max.z:.1f}]")
    print(f"  Meshy bounds: X=[{m_min.x:.4f},{m_max.x:.4f}] "
          f"Y=[{m_min.y:.4f},{m_max.y:.4f}] Z=[{m_min.z:.4f},{m_max.z:.4f}]")
    sys.stdout.flush()

    body_verts_list = []
    for obj in body_objs:
        for v in obj.data.vertices:
            body_verts_list.append(v.co.copy())

    body_kd = KDTree(len(body_verts_list))
    for i, co in enumerate(body_verts_list):
        body_kd.insert(co, i)
    body_kd.balance()

    n_verts = len(mverts)
    step = max(1, n_verts // 200)
    sample_verts = [mverts[i].co.copy() for i in range(0, n_verts, step)]

    body_sizes = [b_range.x, b_range.y, b_range.z]
    meshy_sizes = [m_range.x, m_range.y, m_range.z]

    best_score = float("inf")
    best_perm = (0, 1, 2)
    best_signs = (1, 1, 1)

    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((-1, 1), repeat=3):
            scales = [0.0, 0.0, 0.0]
            for body_ax in range(3):
                meshy_ax = perm[body_ax]
                br = body_sizes[body_ax]
                mr = meshy_sizes[meshy_ax]
                scales[body_ax] = br / mr if mr > 0.001 else 1.0

            total_dist = 0.0
            for sv in sample_verts:
                new_co = Vector((0, 0, 0))
                for body_ax in range(3):
                    meshy_ax = perm[body_ax]
                    val = (sv[meshy_ax] - m_center[meshy_ax]) * signs[body_ax]
                    new_co[body_ax] = val * scales[body_ax] + b_center[body_ax]
                _, _, dist = body_kd.find(new_co)
                total_dist += dist

            if total_dist < best_score:
                best_score = total_dist
                best_perm = perm
                best_signs = signs

    scales = [0.0, 0.0, 0.0]
    for body_ax in range(3):
        meshy_ax = best_perm[body_ax]
        br = body_sizes[body_ax]
        mr = meshy_sizes[meshy_ax]
        scales[body_ax] = br / mr if mr > 0.001 else 1.0

    axis_names = ["X", "Y", "Z"]
    perm_str = "".join(axis_names[i] for i in best_perm)
    sign_str = "".join("+" if s > 0 else "-" for s in best_signs)
    avg_dist = best_score / len(sample_verts) if sample_verts else 0
    print(f"  Best axis mapping: body[XYZ] ← meshy[{perm_str}], signs: {sign_str}")
    print(f"  Per-axis scales: [{scales[0]:.2f}, {scales[1]:.2f}, {scales[2]:.2f}]")
    print(f"  Avg sample distance to nearest body vert: {avg_dist:.4f}")
    sys.stdout.flush()

    for v in mverts:
        old = v.co.copy()
        new_co = Vector((0, 0, 0))
        for body_ax in range(3):
            meshy_ax = best_perm[body_ax]
            val = (old[meshy_ax] - m_center[meshy_ax]) * best_signs[body_ax]
            new_co[body_ax] = val * scales[body_ax] + b_center[body_ax]
        v.co = new_co
    meshy_mesh.data.update()

    mbx, mby, mbz = local_bounds(meshy_mesh)
    print(f"  Remapped bounds: X=[{mbx[0]:.1f},{mbx[1]:.1f}] "
          f"Y=[{mby[0]:.1f},{mby[1]:.1f}] Z=[{mbz[0]:.1f},{mbz[1]:.1f}]")
    sys.stdout.flush()
    return True


def find_head_bone(arm):
    """Return the name of the head bone in the armature, or None."""
    for pb in arm.pose.bones:
        if pb.name.lower() in ("head", "mixamorighead"):
            return pb.name
    for pb in arm.pose.bones:
        if "head" in pb.name.lower() and "fore" not in pb.name.lower():
            return pb.name
    return None


def place_hat_on_head(hat_mesh, head_regions):
    """
    Deterministic uniform-scale placement for hats.  Designed so that every
    Meshy hat variant (Green / Red / Purple / Black / Blue / Leather) bakes
    to the SAME canonical baseline in body space — i.e. same size, same
    horizontal centring, brim sitting at the same body-Y — regardless of
    per-mesh quirks like vertex count, feather/leaf decorations on the
    crown, or slight Meshy-export proportion differences.  This lets a
    single `default_transform` in the equipment spec apply uniformly to
    every hat in the set.

    Algorithm:
      1. Always normalize the mesh first (max extent = 2, center at origin).
         This makes the input size canonical so `scale` becomes a constant
         derived only from the head's X-width.
      2. Detect axes from extents:
         - shortest extent  = CROWN (vertical on head)
         - longest extent   = brim WIDTH (body X)
         - middle extent    = brim DEPTH (body Z)
      3. Detect crown sign by RADIAL SPREAD (avg distance from crown axis
         in the brim plane).  The brim is a wide ring → high radial spread;
         the crown apex is narrow → low radial spread.  We trim out the
         outer 10% of vertices along the crown axis (which removes
         feather/leaf tips that would otherwise inflate the crown-end
         spread on decorated hats).
      4. Apply uniform scale:  scale = (head_x * 1.5) / 2.0  (constant
         across all hats once normalised).
      5. Translate so the brim sits at  head_top_y - 1.5  and the hat is
         centred horizontally on the head.
    """
    verts = hat_mesh.data.vertices
    if len(verts) == 0:
        return False

    normalize_mesh(hat_mesh)
    verts = hat_mesh.data.vertices

    m_xs = [v.co.x for v in verts]
    m_ys = [v.co.y for v in verts]
    m_zs = [v.co.z for v in verts]
    m_min = Vector((min(m_xs), min(m_ys), min(m_zs)))
    m_max = Vector((max(m_xs), max(m_ys), max(m_zs)))
    m_center = (m_min + m_max) / 2
    m_range = m_max - m_min

    axes_by_ext = sorted([(0, m_range.x), (1, m_range.y), (2, m_range.z)],
                         key=lambda a: a[1])
    crown_ax      = axes_by_ext[0][0]
    brim_short_ax = axes_by_ext[1][0]
    brim_long_ax  = axes_by_ext[2][0]

    h_xs, h_ys, h_zs = [], [], []
    for obj in head_regions:
        for v in obj.data.vertices:
            h_xs.append(v.co.x); h_ys.append(v.co.y); h_zs.append(v.co.z)
    if not h_xs:
        print("  Hat: ERROR no head region verts")
        return False
    h_min = Vector((min(h_xs), min(h_ys), min(h_zs)))
    h_max = Vector((max(h_xs), max(h_ys), max(h_zs)))
    h_range = h_max - h_min
    h_center_x = (h_min.x + h_max.x) / 2
    h_center_z = (h_min.z + h_max.z) / 2

    scale = (h_range.x * 1.5) / m_range[brim_long_ax]

    c_vals = [v.co[crown_ax] for v in verts]
    c_min, c_max = min(c_vals), max(c_vals)
    c_extent = c_max - c_min
    trim = c_extent * 0.10
    c_low_cutoff  = c_min + trim
    c_high_cutoff = c_max - trim
    c_mid = (c_min + c_max) / 2
    low_sum, low_n = 0.0, 0
    high_sum, high_n = 0.0, 0
    for v in verts:
        c_val = v.co[crown_ax]
        if c_val < c_low_cutoff or c_val > c_high_cutoff:
            continue
        dx = v.co[brim_long_ax]  - m_center[brim_long_ax]
        dz = v.co[brim_short_ax] - m_center[brim_short_ax]
        r = (dx * dx + dz * dz) ** 0.5
        if c_val < c_mid:
            low_sum += r; low_n += 1
        else:
            high_sum += r; high_n += 1
    avg_low  = low_sum  / max(1, low_n)
    avg_high = high_sum / max(1, high_n)
    crown_sign = 1 if avg_low > avg_high else -1

    if crown_sign > 0:
        brim_end_val = c_min
    else:
        brim_end_val = c_max

    overlap = 1.5
    brim_target_body_y = h_max.y - overlap
    y_offset = brim_target_body_y - (brim_end_val - m_center[crown_ax]) * crown_sign * scale

    for v in verts:
        o = v.co.copy()
        new_x = (o[brim_long_ax]  - m_center[brim_long_ax])  * scale + h_center_x
        new_y = (o[crown_ax]      - m_center[crown_ax])      * crown_sign * scale + y_offset
        new_z = (o[brim_short_ax] - m_center[brim_short_ax]) * scale + h_center_z
        v.co = Vector((new_x, new_y, new_z))
    hat_mesh.data.update()

    ax_names = "XYZ"
    bx, by, bz = local_bounds(hat_mesh)
    print(f"  Hat axes: crown=meshy[{ax_names[crown_ax]}] (sign {crown_sign:+d}),  "
          f"brim_wide=meshy[{ax_names[brim_long_ax]}],  brim_depth=meshy[{ax_names[brim_short_ax]}]")
    print(f"  Radial spread (trimmed 10%) low/high: {avg_low:.3f} / {avg_high:.3f}  "
          f"→ brim placed at {'low' if crown_sign > 0 else 'high'} end (bottom)")
    print(f"  Uniform scale: {scale:.3f}  (brim ≈ 1.5× head width, "
          f"canonical via normalize)")
    print(f"  Hat placed:  X=[{bx[0]:.1f},{bx[1]:.1f}]  "
          f"Y=[{by[0]:.1f},{by[1]:.1f}]  Z=[{bz[0]:.1f},{bz[1]:.1f}]")
    print(f"  (Head top at Y={h_max.y:.1f}, hat brim at Y={by[0]:.1f})")
    sys.stdout.flush()
    return True


def assign_hat_weights(meshy_mesh, arm):
    """Assign 100% weight on the head bone to every vertex of the hat mesh."""
    head_bone_name = find_head_bone(arm)
    if not head_bone_name:
        raise RuntimeError("Could not find head bone in rig for hat weighting")
    vg = meshy_mesh.vertex_groups.new(name=head_bone_name)
    idx_list = [v.index for v in meshy_mesh.data.vertices]
    vg.add(idx_list, 1.0, "REPLACE")
    print(f"  Hat: assigned 100% weight to '{head_bone_name}' "
          f"({len(idx_list)} verts)")
    sys.stdout.flush()


def assign_kd_weights_from_glb(meshy_mesh, source_glb_path_or_paths):
    """Transfer weights from one or more reference GLB skinned meshes via
    KD-tree.  Accepts either a single path or a list of paths; for a list,
    positions and weights are pooled from every mesh in every file before
    building the KD-tree.

    Used when a piece is *based on* an existing well-weighted shell (e.g. the
    Meshy-textured robe shares shape with `robe_v2.glb`; the metal Platebody
    shares shape with the joined upload of `shell_v1_lower_torso +
    shell_v1_upper_torso + shell_v1_arm_upper`).  This gives the textured
    piece identical animation behaviour to the source(s) — better than
    re-deriving weights from the body skin, because the source weights were
    already tuned for that exact shape.

    The imported source meshes are expected to be in the same body-frame
    coordinates as `meshy_mesh` (Blender auto-converts metres → cm on GLB
    import for both, and the meshy mesh has been refit to the source's
    union bbox by an earlier `scale_reference` step).
    """
    paths = _to_path_list(source_glb_path_or_paths)
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        print(f"  ERROR: weight_source not found")
        return False

    pre_import = {o.name for o in bpy.data.objects}
    s_, dn_ = suppress()
    for p in paths:
        bpy.ops.import_scene.gltf(filepath=p)
    bpy.context.view_layer.update()
    restore(s_, dn_)

    new_objs    = [o for o in bpy.data.objects if o.name not in pre_import]
    new_meshes  = [o for o in new_objs if o.type == "MESH"
                   and "Icosphere" not in o.name]

    if not new_meshes:
        print(f"  ERROR: weight_source GLB(s) have no meshes")
        return False

    # Pool positions + weights from EVERY new mesh.  For single-file usage,
    # this is identical to the old behaviour (largest mesh wins because
    # stray helpers don't appear in well-formed shells); for multi-file
    # usage, each shell contributes its own region of (position, weights).
    src_positions = []
    src_weights   = []
    per_mesh = []
    all_group_names = set()
    for m in new_meshes:
        vg_names = {vg.index: vg.name for vg in m.vertex_groups}
        verts_added = 0
        for v in m.data.vertices:
            groups = {}
            for g in v.groups:
                gname = vg_names.get(g.group)
                if gname and g.weight > 0.0001:
                    groups[gname] = g.weight
                    all_group_names.add(gname)
            src_positions.append(v.co.copy())
            src_weights.append(groups)
            verts_added += 1
        per_mesh.append((m.name, verts_added, len(m.vertex_groups)))

    src_summary = ", ".join(os.path.basename(p) for p in paths)
    print(f"  Weight source: {src_summary}")
    for nm, vc, gc in per_mesh:
        print(f"    Mesh: {nm} ({vc} verts, {gc} groups)")
    print(f"    Combined: {len(src_positions)} verts, "
          f"{len(all_group_names)} unique groups")
    if src_positions:
        s0 = src_positions[0]
        print(f"    Sample src.co: ({s0.x:.2f}, {s0.y:.2f}, {s0.z:.2f})")
    sys.stdout.flush()

    kd = KDTree(len(src_positions))
    for i, pos in enumerate(src_positions):
        kd.insert(pos, i)
    kd.balance()

    for vg in list(meshy_mesh.vertex_groups):
        meshy_mesh.vertex_groups.remove(vg)

    # Pure nearest-vertex copy.  When the meshy mesh is the same shape as
    # the source (as with a Meshy-textured robe vs its source shell), each
    # textured vert lives almost exactly on top of one source vert — so
    # copying that single vert's weights gives identical animation behaviour.
    # Using a wider blend (K=12) instead pulls in source verts spread across
    # ~2× the spatial radius (because the textured mesh has higher density
    # than the source), which dilutes leg-bone weights toward Hips and makes
    # the textured mesh follow the legs less than the source does.
    transferred = 0
    for rv_idx, rv in enumerate(meshy_mesh.data.vertices):
        _, src_idx, _ = kd.find(rv.co)
        if src_idx is None:
            continue
        groups = src_weights[src_idx]
        if not groups:
            continue

        top = sorted(groups.items(), key=lambda x: x[1], reverse=True)[:MAX_INFLUENCES]
        wtotal = sum(w for _, w in top)
        if wtotal <= 0:
            continue

        for name, w in top:
            nw = w / wtotal
            if nw > 0.0001:
                if name not in [vg.name for vg in meshy_mesh.vertex_groups]:
                    meshy_mesh.vertex_groups.new(name=name)
                meshy_mesh.vertex_groups[name].add([rv_idx], nw, "REPLACE")
                transferred += 1

    print(f"    Transferred {transferred} weight entries "
          f"(K=1 nearest-vertex copy, max {MAX_INFLUENCES} per vert)")
    print(f"    Groups: {len(meshy_mesh.vertex_groups)}")
    sys.stdout.flush()

    # Drop everything imported from the weight_source GLB (mesh + armature +
    # any helpers) so the rest of the pipeline only sees meshy_mesh + base_arm.
    bpy.ops.object.select_all(action="DESELECT")
    for o in new_objs:
        try:
            o.select_set(True)
        except (RuntimeError, ReferenceError):
            pass
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    return True


def apply_weight_post_boost(meshy_mesh, cfg):
    """Multiply specific bone weights by a per-bone factor on the subset of
    vertices that pass the spatial filters in `cfg`, then renormalise each
    affected vert's weights to sum to 1 (preserving the original 4-influence
    cap by keeping only the top 4 bones).

    Used to bias the post-transfer weight map so specific portions of the
    mesh follow specific bones more strongly — e.g. boosting the shin bones
    (LeftLeg / RightLeg) on a robe's lower portion so the cloth tracks the
    leg during stride animations instead of leaving body shin geometry to
    poke through.

    Config schema (`weight_post_boost`):
      {
        "y_below":    <float>,   # body-cm upper bound; only verts with co.y < this are affected
        "y_above":    <float, optional>,  # body-cm lower bound; only verts with co.y >= this are
                                          # affected.  Combined with y_below this defines a
                                          # vertical band (useful for zoning the robe so the
                                          # thigh band gets UpLeg-ensure and the shin band
                                          # gets Leg-ensure without one zone overwriting the
                                          # other).
        "boost": {
            "<bone_name>": <factor>,   # multiply this bone's existing weight (>1 amplifies).
                                       # No-op when the vert has zero weight on this bone.
            ...
        },
        "suppress": {
            "<bone_name>": <factor>,   # multiply this bone's weight (0..1 to reduce).
                                       # NOT side-split — applied to every affected vert.
            ...
        },
        "ensure": {
            "<bone_name>": <min_weight>,  # raise this bone's pre-normalised weight to at
                                          # LEAST min_weight, adding the bone to the vert
                                          # if it wasn't present.  Useful when the source
                                          # weight map left some bones missing entirely
                                          # (e.g. front-centre robe verts that have zero
                                          # RightLeg weight — multiplicative boost can't
                                          # fix that, but ensure can).
            ...
        },
        "side_split":  <bool, default True>,
            # When True, only apply LEFT boost/ensure bones (name contains 'Left') to verts
            # with x < 0, and RIGHT to verts with x > 0.  Suppress entries are
            # never side-split.  Keeps the two leg sides asymmetric so each robe
            # half follows its own leg during stride motion — but set False for a
            # robe to allow both shins to influence the centre-front cloth so it
            # tracks the swinging leg that crosses the centreline.
      }
    """
    y_below = float(cfg.get("y_below", 0.0))
    y_above = float(cfg.get("y_above", -1e9))
    boost_map = cfg.get("boost", {}) or {}
    suppress_map = cfg.get("suppress", {}) or {}
    ensure_map = cfg.get("ensure", {}) or {}
    side_split = bool(cfg.get("side_split", True))
    if not boost_map and not suppress_map and not ensure_map:
        return

    vg_by_name = {vg.name: vg for vg in meshy_mesh.vertex_groups}

    # Diagnostic: print the actual co.y range + vertex group names so it's
    # easy to spot threshold or bone-name mismatches.
    ys = [v.co.y for v in meshy_mesh.data.vertices]
    print(f"  weight_post_boost: mesh-local Y range = "
          f"[{min(ys):.2f}, {max(ys):.2f}] (cfg y_below={y_below:.2f})")
    print(f"  weight_post_boost: existing vgroups = {sorted(vg_by_name.keys())}")
    print(f"  weight_post_boost: configured bones = {sorted(boost_map.keys())}")
    sys.stdout.flush()
    n_boosted_verts = 0
    n_boosted_entries = 0

    for v in meshy_mesh.data.vertices:
        if v.co.y >= y_below:
            continue
        if v.co.y < y_above:
            continue

        # Side-split applies to BOOST and ENSURE entries.  Suppress entries
        # always apply to every vert below the threshold (they reduce the
        # symmetric "centre" bones like Hips that compete with both legs).
        def _side_split_skip(bone_name):
            if not side_split:
                return False
            if "Left" in bone_name and v.co.x >= 0.0:
                return True
            if "Right" in bone_name and v.co.x <= 0.0:
                return True
            return False

        boost_applicable = {n: float(f) for n, f in boost_map.items()
                            if n in vg_by_name and not _side_split_skip(n)}
        suppress_applicable = {n: float(f) for n, f in suppress_map.items()
                               if n in vg_by_name}
        ensure_applicable = {n: float(f) for n, f in ensure_map.items()
                             if not _side_split_skip(n)}
        if not boost_applicable and not suppress_applicable and not ensure_applicable:
            continue

        current = {}
        for g in v.groups:
            name = meshy_mesh.vertex_groups[g.group].name
            if g.weight > 0.0001:
                current[name] = g.weight

        # Boost: multiply existing weight by factor (skip if bone not present;
        # we don't fabricate bone weight on verts the source decided not to bind).
        for name, factor in boost_applicable.items():
            if name in current:
                current[name] = current[name] * factor
        # Suppress: multiply existing weight by factor (typically < 1 to reduce).
        for name, factor in suppress_applicable.items():
            if name in current:
                current[name] = current[name] * factor

        # Drop anything we suppressed below the floor BEFORE ensure, so an
        # ensure floor isn't immediately cleared away.
        for name in list(current.keys()):
            if current[name] <= 0.0001:
                current.pop(name, None)

        # Ensure: raise specified bones to AT LEAST min_weight, adding the
        # bone to the vert if it wasn't present.  Pre-normalisation values —
        # the final sum-to-1 renormalise happens below.
        for name, min_w in ensure_applicable.items():
            existing = current.get(name, 0.0)
            if existing < min_w:
                current[name] = min_w

        top = sorted(current.items(), key=lambda kv: kv[1], reverse=True)[:MAX_INFLUENCES]
        wtotal = sum(w for _, w in top)
        if wtotal <= 0:
            continue

        for vg in meshy_mesh.vertex_groups:
            vg.remove([v.index])

        for name, w in top:
            nw = w / wtotal
            if nw <= 0.0001:
                continue
            if name not in vg_by_name:
                vg_by_name[name] = meshy_mesh.vertex_groups.new(name=name)
            vg_by_name[name].add([v.index], nw, "REPLACE")
            n_boosted_entries += 1
        n_boosted_verts += 1

    y_range_str = (f"y<{y_below:.1f}" if y_above <= -1e8
                   else f"{y_above:.1f}≤y<{y_below:.1f}")
    print(f"  weight_post_boost: {y_range_str}  "
          f"side_split={side_split}  "
          f"boost={list(boost_map.keys())}  "
          f"suppress={list(suppress_map.keys())}  "
          f"ensure={list(ensure_map.keys())}  "
          f"→ adjusted {n_boosted_verts} verts ({n_boosted_entries} entries)")
    sys.stdout.flush()


def assign_kd_weights(meshy_mesh, regions, region_meshes):
    """Transfer weights from the listed body regions via KD-tree nearest-N."""
    all_positions = []
    all_weights = []

    for rname in regions:
        src = region_meshes.get(rname)
        if not src:
            print(f"  WARNING: Region '{rname}' not found")
            continue
        vg_names = {vg.index: vg.name for vg in src.vertex_groups}
        for v in src.data.vertices:
            groups = {}
            for g in v.groups:
                gname = vg_names.get(g.group)
                if gname and g.weight > 0.0001:
                    groups[gname] = g.weight
            all_positions.append(v.co.copy())
            all_weights.append(groups)

    print(f"  Body reference: {len(all_positions)} verts from {len(regions)} regions")
    sys.stdout.flush()

    if not all_positions:
        print(f"  ERROR: No body verts")
        return

    kd = KDTree(len(all_positions))
    for i, pos in enumerate(all_positions):
        kd.insert(pos, i)
    kd.balance()

    transferred = 0
    for rv_idx, rv in enumerate(meshy_mesh.data.vertices):
        neighbors = kd.find_n(rv.co, WEIGHT_NEIGHBORS)

        inv_weights = []
        for co, idx, dist in neighbors:
            w = 1.0 / (dist ** WEIGHT_POWER + 1e-8)
            inv_weights.append((idx, w))

        total_inv = sum(w for _, w in inv_weights)

        blended = {}
        for body_idx, inv_w in inv_weights:
            factor = inv_w / total_inv
            for gname, bw in all_weights[body_idx].items():
                blended[gname] = blended.get(gname, 0.0) + bw * factor

        top = sorted(blended.items(), key=lambda x: x[1], reverse=True)[:MAX_INFLUENCES]
        wtotal = sum(w for _, w in top)
        if wtotal > 0:
            for name, w in top:
                nw = w / wtotal
                if nw > 0.0001:
                    if name not in [vg.name for vg in meshy_mesh.vertex_groups]:
                        meshy_mesh.vertex_groups.new(name=name)
                    meshy_mesh.vertex_groups[name].add([rv_idx], nw, "REPLACE")
                    transferred += 1

    print(f"  Transferred {transferred} weight entries (max {MAX_INFLUENCES} per vert)")
    print(f"  Groups: {len(meshy_mesh.vertex_groups)}")
    sys.stdout.flush()


def conform_to_glb_surface(meshy_mesh, source_glb_path_or_paths):
    """Snap every vert of `meshy_mesh` to the closest point on the source
    surface (BVH-tree nearest-face projection).  The source can be a single
    GLB OR a list of GLBs whose polygons are unioned into one BVH — used
    when Meshy was given a multi-shell upload (e.g. the metal Platebody was
    textured from a joined upload of `shell_v1_lower_torso +
    shell_v1_upper_torso + shell_v1_arm_upper`).

    Why this is needed:  the 48-combo body-region calibration + post-rotation
    + bbox refit aligns the AABB of the textured Meshy mesh with the source
    shell's AABB, but each step is per-axis and centered on different origins,
    so the cross-section between the top and bottom rings ends up subtly
    distorted (X/Z ratio drifts toward 1:1 and the centroid wanders sideways).
    Visually that shows up as a "wider waist" — the body's anatomical
    front-to-back compression at the waist gets washed out.

    Since the textured mesh and the source share the same underlying shape
    (Meshy textured the same shell), snapping every vert to the source's
    nearest surface point gives the textured piece an EXACT silhouette match
    while preserving its UV layout, materials, and vertex topology (only
    positions change).  Seam-pair verts (Meshy adds them at UV boundaries)
    collapse to the same surface point, which is the correct behaviour — in
    3D they're meant to be coincident.

    Called AFTER `scale_reference` refit, so the textured mesh is already
    inside the source's AABB and BVH-nearest gives sub-cm displacements.
    """
    paths = _to_path_list(source_glb_path_or_paths)
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        print(f"  ERROR: surface_conform source not found")
        return False

    pre_import = {o.name for o in bpy.data.objects}
    s_, dn_ = suppress()
    for p in paths:
        bpy.ops.import_scene.gltf(filepath=p)
    bpy.context.view_layer.update()
    restore(s_, dn_)

    new_objs   = [o for o in bpy.data.objects if o.name not in pre_import]
    new_meshes = [o for o in new_objs if o.type == "MESH"
                  and "Icosphere" not in o.name]
    if not new_meshes:
        print(f"  ERROR: surface_conform sources have no meshes")
        return False

    # Combine polygons from ALL imported meshes into a single BVH.  Polygon
    # vertex indices are local to each mesh, so we offset them by the running
    # total of verts as we accumulate them into the global vertex list.
    src_verts = []
    src_polys = []
    per_mesh = []
    for m in new_meshes:
        base = len(src_verts)
        for v in m.data.vertices:
            src_verts.append(v.co.copy())
        polys_added = 0
        for p in m.data.polygons:
            src_polys.append(tuple(base + i for i in p.vertices))
            polys_added += 1
        per_mesh.append((m.name, len(m.data.vertices), polys_added))

    if not src_polys:
        print(f"  ERROR: surface_conform sources have no polygons → BVH disabled")
        bpy.ops.object.select_all(action="DESELECT")
        for o in new_objs:
            try: o.select_set(True)
            except (RuntimeError, ReferenceError): pass
        if bpy.context.selected_objects:
            bpy.ops.object.delete(use_global=False)
        return False

    bvh = BVHTree.FromPolygons(src_verts, src_polys)

    snapped = 0
    total_dist = 0.0
    max_dist = 0.0
    for v in meshy_mesh.data.vertices:
        loc, _, _, dist = bvh.find_nearest(v.co)
        if loc is None:
            continue
        snapped += 1
        total_dist += dist
        if dist > max_dist:
            max_dist = dist
        v.co = loc
    meshy_mesh.data.update()

    avg_dist = total_dist / max(1, snapped)
    src_summary = ", ".join(os.path.basename(p) for p in paths)
    print(f"  Surface conform to {src_summary}")
    for nm, vc, pc in per_mesh:
        print(f"    Source mesh: {nm} ({vc} verts, {pc} polys)")
    print(f"    Combined: {len(src_verts)} verts, {len(src_polys)} polys")
    print(f"    Snapped {snapped}/{len(meshy_mesh.data.vertices)} verts  "
          f"avg displacement {avg_dist:.3f} cm  max {max_dist:.3f} cm")
    sys.stdout.flush()

    bpy.ops.object.select_all(action="DESELECT")
    for o in new_objs:
        try: o.select_set(True)
        except (RuntimeError, ReferenceError): pass
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    return True


def process_piece(piece):
    piece_name = piece["name"]
    piece_type = piece["piece_type"]
    src_path = piece["src"]
    out_path = piece["out"]
    regions = piece["regions"]

    print(f"\n{'='*60}")
    print(f"Processing: {piece_name}  ({piece_type})")
    sys.stdout.flush()

    if not os.path.exists(src_path):
        print(f"  SKIP: source not found → {src_path}")
        return

    bpy.ops.wm.read_factory_settings(use_empty=True)

    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
    bpy.context.view_layer.update()
    restore(s, dn)

    base_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if base_arm is None:
        print(f"  ERROR: No armature in BaseFemaleV2")
        return
    region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

    pre_import = {o.name for o in bpy.data.objects}
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=src_path)
    bpy.context.view_layer.update()
    restore(s, dn)

    new_objects = [o for o in bpy.data.objects if o.name not in pre_import]
    imported_meshes = [o for o in new_objects if o.type == "MESH"
                       and "Icosphere" not in o.name]

    if not imported_meshes:
        print(f"  ERROR: No mesh found")
        return

    if len(imported_meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for m in imported_meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = imported_meshes[0]
        bpy.ops.object.join()
    meshy_mesh = imported_meshes[0]

    print(f"  Mesh: {meshy_mesh.name} ({len(meshy_mesh.data.vertices)} verts)")
    sys.stdout.flush()

    body_objs = [region_meshes[r] for r in regions if r in region_meshes]
    if not body_objs:
        print(f"  ERROR: None of the required regions found: {regions}")
        return

    # `place_hat_on_head` is wizard-hat-shape-aware — it detects the
    # crown by SHORTEST extent and the brim by LONGEST extent, then
    # uniform-scales to a constant fraction of the head's X width.  That
    # works for tall narrow-tip hats but it produces nonsense on a
    # near-cubic helmet (no clear crown axis to detect).  When a piece
    # provides its own `scale_reference` (e.g. metal helmets pointing at
    # `shell_v1_head.glb`), route it through the 48-combo path instead so
    # the bbox-aware axis calibration runs and the subsequent
    # `scale_reference` + `surface_conform` steps can fine-tune the fit.
    use_hat_placer = (piece_type == "hat" and not piece.get("scale_reference"))
    if use_hat_placer:
        placed = place_hat_on_head(meshy_mesh, body_objs)
        if not placed:
            print("  ERROR: Hat placement failed")
            return
    else:
        remapped = remap_meshy_to_body(meshy_mesh, body_objs)
        if not remapped:
            print("  WARNING: Mesh was not remapped — may already be in body scale")

    # Optional post-calibration Euler rotation around the mesh's own center.
    # Applied AFTER bbox calibration, so the rotated mesh stays inside the
    # body's leg-region bbox.  Used by the robe pipeline because a robe's
    # silhouette is inverted relative to the body's leg silhouette and the
    # 48-combo fitter sometimes scores an upside-down mapping as best.
    post_rot = piece.get("post_rotation_deg")
    if post_rot:
        verts = meshy_mesh.data.vertices
        xs = [v.co.x for v in verts]
        ys = [v.co.y for v in verts]
        zs = [v.co.z for v in verts]
        center = Vector((
            (min(xs) + max(xs)) / 2,
            (min(ys) + max(ys)) / 2,
            (min(zs) + max(zs)) / 2,
        ))
        rx = math.radians(post_rot[0])
        ry = math.radians(post_rot[1])
        rz = math.radians(post_rot[2])
        R = (
            Matrix.Rotation(rz, 4, "Z")
            @ Matrix.Rotation(ry, 4, "Y")
            @ Matrix.Rotation(rx, 4, "X")
        )
        for v in verts:
            v.co = R @ (v.co - center) + center
        meshy_mesh.data.update()
        print(f"  Post-calibration rotation: Euler XYZ = {post_rot} deg, "
              f"around center ({center.x:.1f}, {center.y:.1f}, {center.z:.1f})")
        sys.stdout.flush()

    # Optional refit to a reference GLB's bbox (axis-aligned, no axis swap).
    # The earlier 48-combo calibration scaled the mesh to fit the body's leg
    # bbox — but that bbox is taller and narrower than the actual robe, and a
    # post-rotation around Y also swaps which mesh axis fills which body axis.
    # Refitting to a reference robe's bbox gives the textured robe the EXACT
    # dimensions (and vertical placement) of the original shell that the user
    # uploaded to Meshy.  Per-axis scale + translate only — orientation is
    # preserved from the post-rotation step.
    #
    # We read the reference bbox straight from the GLB POSITION accessor so
    # nothing else (armature visualisations, sibling meshes, helper objects)
    # can pollute the bbox the way a full Blender import would.
    scale_ref = piece.get("scale_reference")
    scale_ref_paths = [p for p in _to_path_list(scale_ref) if os.path.exists(p)]
    if scale_ref_paths:
        ref_min, ref_max = read_glb_position_bbox(scale_ref_paths)
        if ref_min is None:
            print(f"  WARNING: couldn't read POSITION bbox from {scale_ref_paths}")
        else:
            r_min = Vector(ref_min)
            r_max = Vector(ref_max)

            # Body region meshes in this scene live in centimetres (range
            # 10..107 cm vertically).  GLBs commonly export in metres
            # (range 0.28..1.07 m).  If the reference bbox is < 5 units in
            # max extent, treat as metres and convert to cm so the scaling
            # math lines up with the meshy_mesh's cm-scale coordinates.
            ref_extent = max((r_max - r_min).x, (r_max - r_min).y, (r_max - r_min).z)
            if ref_extent < 5.0:
                r_min = r_min * 100.0
                r_max = r_max * 100.0
                print(f"  scale_reference appears to be in metres → converted to cm")

            r_center = (r_min + r_max) / 2
            r_size   = r_max - r_min

            verts = meshy_mesh.data.vertices
            mxs = [v.co.x for v in verts]
            mys = [v.co.y for v in verts]
            mzs = [v.co.z for v in verts]
            m_min = Vector((min(mxs), min(mys), min(mzs)))
            m_max = Vector((max(mxs), max(mys), max(mzs)))
            m_center = (m_min + m_max) / 2
            m_size   = m_max - m_min

            sx = r_size.x / max(0.001, m_size.x)
            sy = r_size.y / max(0.001, m_size.y)
            sz = r_size.z / max(0.001, m_size.z)

            for v in verts:
                o = v.co - m_center
                v.co = Vector((
                    o.x * sx + r_center.x,
                    o.y * sy + r_center.y,
                    o.z * sz + r_center.z,
                ))
            meshy_mesh.data.update()

            ref_label = ", ".join(os.path.basename(p) for p in scale_ref_paths)
            print(f"  Refit to scale_reference: {ref_label}")
            print(f"    Ref bbox:  X=[{r_min.x:.1f},{r_max.x:.1f}] "
                  f"Y=[{r_min.y:.1f},{r_max.y:.1f}] Z=[{r_min.z:.1f},{r_max.z:.1f}]")
            print(f"    Per-axis scale: [{sx:.3f}, {sy:.3f}, {sz:.3f}]")
            sys.stdout.flush()

    # Optional surface conform — snap every vert onto the source GLB's surface.
    # Used by the metal-armor plateskirt pipeline (and any similar return-trip
    # piece) to erase the small per-axis distortion that the bbox refit leaves
    # in the cross-section.  See `conform_to_glb_surface` doc for full context.
    surf_ref = piece.get("surface_conform")
    surf_ref_paths = [p for p in _to_path_list(surf_ref) if os.path.exists(p)]
    if surf_ref_paths:
        conform_to_glb_surface(meshy_mesh, surf_ref_paths)

    meshy_mesh.vertex_groups.clear()
    for mod in list(meshy_mesh.modifiers):
        if mod.type == "ARMATURE":
            meshy_mesh.modifiers.remove(mod)

    if piece_type == "hat":
        assign_hat_weights(meshy_mesh, base_arm)
    else:
        weight_src = piece.get("weight_source")
        weight_src_paths = [p for p in _to_path_list(weight_src) if os.path.exists(p)]
        used_glb_source = False
        if weight_src_paths:
            used_glb_source = assign_kd_weights_from_glb(meshy_mesh, weight_src_paths)
            if not used_glb_source:
                print(f"  Falling back to body-region weight transfer")
        if not used_glb_source:
            assign_kd_weights(meshy_mesh, regions, region_meshes)

    # Optional per-region bone-weight boost.  Used to bias which bones drive
    # specific portions of the mesh after the bulk weight transfer has run.
    # Common case:  robe/skirt hems whose nearest source vertex happens to
    # carry mostly UpLeg/Hips weight (because the source weight transfer
    # blended K-nearest neighbours), so the lower mesh under-follows the
    # shin bones during stride animations and the body leg pokes through.
    # See `weight_post_boost` config docs in PIECES definitions.
    # `weight_post_boost` may be either a single dict (one zone) or a list of
    # dicts (multiple Y-zones applied in order, e.g. a thigh band + shin band
    # with different ensure bones).
    boost_cfg = piece.get("weight_post_boost")
    if boost_cfg:
        zones = boost_cfg if isinstance(boost_cfg, list) else [boost_cfg]
        for zone in zones:
            apply_weight_post_boost(meshy_mesh, zone)

    mod = meshy_mesh.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = base_arm

    if meshy_mesh.parent:
        bpy.ops.object.select_all(action="DESELECT")
        meshy_mesh.select_set(True)
        bpy.context.view_layer.objects.active = meshy_mesh
        bpy.ops.object.parent_clear(type="CLEAR")

    meshy_mesh.parent = base_arm
    meshy_mesh.matrix_parent_inverse = Matrix.Identity(4)
    meshy_mesh.matrix_basis = Matrix.Identity(4)

    bpy.context.view_layer.update()

    keep = {meshy_mesh.name, base_arm.name}
    bpy.ops.object.select_all(action="DESELECT")
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    bpy.ops.object.select_all(action="DESELECT")
    meshy_mesh.select_set(True)
    base_arm.select_set(True)
    bpy.context.view_layer.objects.active = base_arm

    s, dn = suppress()
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=False,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_image_format="AUTO",
    )
    restore(s, dn)
    print(f"  Exported → {out_path}")
    sys.stdout.flush()


print("Starting weight_ranged_set.py ...")
sys.stdout.flush()

only = None
for arg in sys.argv:
    if arg.startswith("--only="):
        raw = arg.split("=", 1)[1]
        only = {p.strip() for p in raw.split(",") if p.strip()}

for piece in PIECES:
    if only and piece["name"] not in only:
        continue
    process_piece(piece)

print(f"\n{'='*60}")
print("All pieces processed!")
print(f"{'='*60}")
sys.stdout.flush()
