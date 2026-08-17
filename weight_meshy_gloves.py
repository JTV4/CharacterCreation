"""
weight_meshy_gloves.py
======================
Return trip for the "moved-together" Meshy gloves workflow.

Upstream: make_meshy_input_hands.py produced MeshyInputHands.glb by
taking shell_v1_hands.glb and translating the two hands along +/-X so
they sit 4 cm apart. The user textures that GLB in Meshy and drops the
result into viewer/public/equipment/Female/Gloves/<Variant>Gloves.glb.

This script puts them back on the character WITHOUT the anisotropic
stretching that the bounding-box-fit approach in
weight_green_ranged_armor.py introduces:

  1. Calibrate orientation + a SINGLE uniform scale by matching the
     Meshy mesh to the known pre-Meshy reference (MeshyInputHands.glb).
     Tries all 48 axis-permutation x sign combos; scale is derived from
     the Y-axis ratio (Y was untouched by the inward X translation, so
     it's the clean reference axis).
  2. Split the transformed mesh by X sign into left-hand / right-hand
     components.
  3. Snap each component's centroid to the corresponding per-hand
     centroid from shell_v1_hands.glb. This is a pure rigid translation
     per glove -- no shape distortion, no per-axis stretching.
  4. KD-tree inverse-distance weight transfer from base_body_hands
     inside BaseFemaleV2 (same code path as weight_green_ranged_armor.py).
  5. Parent to the base armature and export to a *Weighted.glb file
     alongside the source (never overwrites the pristine Meshy output).

Add a new variant by appending an entry to PIECES below. Each entry is:
    {"src": "<Meshy output GLB>", "out": "<output weighted GLB>"}
Both paths are relative to the repo root.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python weight_meshy_gloves.py
"""

import os
import sys
import itertools
import bpy
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree

sys.stdout.reconfigure(line_buffering=True)

BASE_MODEL = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
SHELL_REF = os.path.abspath(
    "viewer/public/equipment/Female/ShellV1/shell_v1_hands.glb"
)
MESHY_INPUT_REF = os.path.abspath(
    "viewer/public/equipment/Female/Gloves/MeshyInputHands.glb"
)

GLOVES_DIR = os.path.abspath("viewer/public/equipment/Female/Gloves")


def _variant(name, axis_override=None):
    """Build a piece entry.

    `axis_override`, if set, skips the auto 48-combo and forces a specific
    axis mapping.  Format:
        {"perm": (0, 2, 1), "signs": (+1, +1, -1), "scale_anchor_mesh_axis": 0}

    Fields:
      perm   — tuple length 3.  body[XYZ] sources from meshy[perm[0..2]].
      signs  — tuple length 3.  Per-axis sign flip after permutation.
      scale_anchor_mesh_axis (optional, default = perm[1]):
        Which meshy axis (0=X, 1=Y, 2=Z) to use as the uniform-scale anchor.
        Default behaviour matches MIH's Y extent (the palm-to-fingertip dim)
        against meshy[perm[1]].  Override this when the gauntlet's
        palm-to-fingertip axis includes EXTRA geometry not present in MIH
        (e.g. a sleeve/cuff that extends past the wrist):  pegging the
        sleeve-extended axis to MIH's bare-hand reference shrinks the entire
        gauntlet by the ratio of (sleeve-included length) / (bare-hand
        length), so each hand comes out half-size.  Use the bilateral X
        axis (0) instead — it represents the same hand-span in both Meshy
        outputs and MIH, so the resulting scale puts the HAND region at the
        correct dimensions and lets the sleeve extend naturally past it.

    Used for the metal gauntlets:  Meshy normalised those exports with the
    bilateral-X axis dominating (X=±1), so the auto-fitter greedily picks the
    LONGEST non-X axis as the body-Y source — which collapses the gauntlet's
    fingertip→sleeve direction into the 7 cm hand-vertical range and yields
    a Z-squashed result.  Forcing the Ranged auto-pick `(0, 2, 1) / (+, +, -)`
    (which is what the calibrator chooses for all 6 Ranged colours, also
    derived from `meshy_input_hands`) preserves the gauntlet's shape;
    anchoring scale on mesh-X keeps each hand at the real bare-hand size.
    """
    entry = {
        "src": os.path.join(GLOVES_DIR, f"{name}.glb"),
        "out": os.path.join(GLOVES_DIR, f"{name}Weighted.glb"),
    }
    if axis_override is not None:
        entry["axis_override"] = axis_override
    return entry


# Axis mapping for the metal gauntlets.  The Ranged-colour gloves auto-pick
# perm XZY with signs (+, +, -) — and they were exported from Meshy starting
# from the SAME `meshy_input_hands` shell as the metal gauntlets.  So the
# metal gauntlets must use the SAME perm+signs to land in the correct
# orientation.  Scale is anchored on meshy-X (the bilateral hand-span) rather
# than the default perm[1] axis, because metal gauntlets have a cuff/sleeve
# that lengthens the perm[1] axis past the bare-hand reference — using the
# default would shrink the whole gauntlet by the sleeve-to-hand-length ratio.
_METAL_AXIS_OVERRIDE = {
    "perm":  (0, 2, 1),
    "signs": (+1, +1, -1),
    "scale_anchor_mesh_axis": 0,
}


# Each entry processes one Meshy-textured glove GLB through the return
# trip. The source GLB is NEVER modified; the weighted output is written
# to a sibling *Weighted.glb file.
PIECES = [
    _variant("GreenRangedGloves"),
    _variant("PurpleRangedGloves"),
    _variant("BlackRangedGloves"),
    _variant("RedRangedGloves"),
    _variant("BlueRangedGloves"),
    _variant("LeatherRangedGloves"),
    # Metal armor gauntlets — re-uploaded to Meshy from the bare-hand
    # `meshy_input_hands` shell (same as Mage gloves below), so the auto
    # 48-combo calibrator now works without the previous _METAL_AXIS_OVERRIDE
    # workaround.  The axis_override was needed when these were textured
    # from a sleeve-extended shell; the new sleeveless versions calibrate
    # cleanly with the default Y-axis scale anchor.
    _variant("IronGloves"),
    _variant("SteelGloves"),
    _variant("GoldGloves"),
    _variant("TitaniumGloves"),
    _variant("TungstenGloves"),
    _variant("LuminousGloves"),
    # Magic Armor gloves — Meshy-textured from the same `meshy_input_hands`
    # bilateral-hand shell as the Ranged colours.  No sleeve geometry, so
    # the auto 48-combo + Y-axis scale anchor calibration works cleanly
    # (no axis_override needed).
    _variant("LeatherMageGloves"),
    _variant("GreenMageGloves"),
    _variant("BlueMageGloves"),
    _variant("RedMageGloves"),
    _variant("BlackMageGloves"),
    _variant("PurpleMageGloves"),
    # White Skin Textures shell hands — textured from a remeshed MIH-layout
    # source.  Auto Y-anchor picks XYZ and squashes depth (avg dist ~1.9);
    # force the same XZY / ++- / X-anchor mapping used by metal gauntlets.
    _variant("WhiteSkinHands", axis_override=_METAL_AXIS_OVERRIDE),
]

REGIONS = ["base_body_hands"]

WEIGHT_NEIGHBORS = 12
WEIGHT_POWER = 1.5
MAX_INFLUENCES = 4


def suppress():
    dn = open(os.devnull, "w")
    s = os.dup(1)
    os.dup2(dn.fileno(), 1)
    return s, dn


def restore(s, dn):
    os.dup2(s, 1)
    os.close(s)
    dn.close()


def load_verts_from_glb(path):
    """Read vertex positions from a GLB in LOCAL mesh coordinates.

    We intentionally do NOT apply matrix_world. BaseFemaleV2 stores its
    body-region meshes in local centimeters under a 0.01-scaled armature,
    so reading .co (local) keeps everything in the same cm space that
    weight_green_ranged_armor.py uses. Applying matrix_world here would
    give meters and cause a 100x scale mismatch at weight-transfer time.

    The scene is reset afterwards; this is read-only.
    """
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()
    restore(s, dn)
    mesh_obj = None
    for o in bpy.data.objects:
        if o.type == "MESH" and "Icosphere" not in o.name:
            mesh_obj = o
            break
    if mesh_obj is None:
        raise RuntimeError(f"No mesh in {path}")
    return [v.co.copy() for v in mesh_obj.data.vertices]


def bounds_and_centroid(verts):
    xs = [v.x for v in verts]
    ys = [v.y for v in verts]
    zs = [v.z for v in verts]
    mn = Vector((min(xs), min(ys), min(zs)))
    mx = Vector((max(xs), max(ys), max(zs)))
    ctr = (mn + mx) / 2
    return mn, mx, ctr


def build_references():
    """Read shell centroids and MeshyInputHands KDTree once per session."""
    shell_verts = load_verts_from_glb(SHELL_REF)
    shell_min, shell_max, _ = bounds_and_centroid(shell_verts)
    shell_left = [v for v in shell_verts if v.x < 0.0]
    shell_right = [v for v in shell_verts if v.x > 0.0]
    left_ctr = sum(shell_left, Vector()) / len(shell_left)
    right_ctr = sum(shell_right, Vector()) / len(shell_right)
    print(f"  shell_v1_hands: {len(shell_verts)}v  "
          f"Y=[{shell_min.y:.3f},{shell_max.y:.3f}]  "
          f"left_ctr=({left_ctr.x:.2f},{left_ctr.y:.2f},{left_ctr.z:.2f})  "
          f"right_ctr=({right_ctr.x:.2f},{right_ctr.y:.2f},{right_ctr.z:.2f})")

    mih_verts = load_verts_from_glb(MESHY_INPUT_REF)
    mih_min, mih_max, mih_ctr = bounds_and_centroid(mih_verts)
    mih_centered = [v - mih_ctr for v in mih_verts]
    mih_X_ext = mih_max.x - mih_min.x
    mih_Y_ext = mih_max.y - mih_min.y
    mih_Z_ext = mih_max.z - mih_min.z
    print(f"  MeshyInputHands: {len(mih_verts)}v  "
          f"X=[{mih_min.x:.3f},{mih_max.x:.3f}]  "
          f"Y=[{mih_min.y:.3f},{mih_max.y:.3f}]  "
          f"Z=[{mih_min.z:.3f},{mih_max.z:.3f}]")

    mih_kd = KDTree(len(mih_centered))
    for i, co in enumerate(mih_centered):
        mih_kd.insert(co, i)
    mih_kd.balance()

    return {
        "left_ctr": left_ctr,
        "right_ctr": right_ctr,
        "mih_kd": mih_kd,
        "mih_X_ext": mih_X_ext,
        "mih_Y_ext": mih_Y_ext,
        "mih_Z_ext": mih_Z_ext,
    }


def process_piece(piece, refs):
    src = piece["src"]
    out = piece["out"]
    tag = os.path.splitext(os.path.basename(src))[0]
    print("=" * 60)
    print(f"Return trip -> {tag}")
    print("=" * 60)
    sys.stdout.flush()

    if not os.path.exists(src):
        print(f"  SKIP: source not found: {src}")
        return False

    # ------------------------------------------------------------------
    # Fresh scene + BaseFemaleV2 for each piece (we delete extras on export)
    # ------------------------------------------------------------------
    print("[1/5] Loading BaseFemaleV2 (armature + body region)")
    sys.stdout.flush()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=BASE_MODEL)
    bpy.context.view_layer.update()
    restore(s, dn)

    base_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    if not base_arm:
        raise RuntimeError("No armature in BaseFemaleV2")
    for rname in REGIONS:
        if rname not in region_meshes:
            raise RuntimeError(f"Region {rname} missing")

    pre_import = {o.name for o in bpy.data.objects}
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()
    restore(s, dn)

    new_objs = [o for o in bpy.data.objects if o.name not in pre_import]
    imported_meshes = [o for o in new_objs
                       if o.type == "MESH" and "Icosphere" not in o.name]
    if not imported_meshes:
        print(f"  SKIP: no mesh inside {src}")
        return False
    if len(imported_meshes) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for m in imported_meshes:
            m.select_set(True)
        bpy.context.view_layer.objects.active = imported_meshes[0]
        bpy.ops.object.join()
    glove = imported_meshes[0]
    print(f"      Meshy mesh: {glove.name}  ({len(glove.data.vertices)} verts)")

    # Stay in LOCAL cm / Y-up -- see loader docstring for why.
    mv_local = [v.co.copy() for v in glove.data.vertices]
    meshy_min, meshy_max, meshy_ctr = bounds_and_centroid(mv_local)
    print(f"      Meshy bounds (local cm): "
          f"X=[{meshy_min.x:.3f},{meshy_max.x:.3f}]  "
          f"Y=[{meshy_min.y:.3f},{meshy_max.y:.3f}]  "
          f"Z=[{meshy_min.z:.3f},{meshy_max.z:.3f}]")

    # ------------------------------------------------------------------
    # Calibrate orientation + uniform_scale vs MeshyInputHands
    # ------------------------------------------------------------------
    print("[2/5] Calibrating orientation + uniform scale")
    sys.stdout.flush()

    mv_centered = [v - meshy_ctr for v in mv_local]
    meshy_ext = meshy_max - meshy_min
    meshy_sizes = [meshy_ext.x, meshy_ext.y, meshy_ext.z]

    n_verts = len(mv_centered)
    step = max(1, n_verts // 300)
    sample = mv_centered[::step]

    mih_kd = refs["mih_kd"]
    mih_X_ext = refs["mih_X_ext"]
    mih_Y_ext = refs["mih_Y_ext"]
    mih_Z_ext = refs["mih_Z_ext"]
    mih_ext_per_body_ax = (mih_X_ext, mih_Y_ext, mih_Z_ext)

    axis_override = piece.get("axis_override")
    if axis_override is not None:
        # Forced mapping path — skip the 48-combo and use the caller's perm
        # and signs.  uniform_scale is derived from the ratio of a CHOSEN
        # mesh axis to its corresponding MIH body-axis extent.  Default is
        # mesh axis perm[1] (= body Y source, MIH Y extent), but the caller
        # can pick a different axis via `scale_anchor_mesh_axis` for cases
        # where the chosen axis includes geometry NOT present in MIH (e.g.
        # gauntlet sleeve extending past the bare-hand reference).
        best_perm  = tuple(axis_override["perm"])
        best_signs = tuple(axis_override["signs"])
        anchor_mesh_ax = int(axis_override.get(
            "scale_anchor_mesh_axis", best_perm[1]
        ))
        anchor_mesh_size = meshy_sizes[anchor_mesh_ax]
        if anchor_mesh_size < 1e-6:
            raise RuntimeError(
                f"axis_override picks meshy axis {anchor_mesh_ax} with zero "
                f"extent — cannot derive uniform scale"
            )
        anchor_body_ax = best_perm.index(anchor_mesh_ax)
        anchor_mih_size = mih_ext_per_body_ax[anchor_body_ax]
        best_scale = anchor_mih_size / anchor_mesh_size

        # Compute the per-vert distance score the auto-fitter would have
        # produced for this same mapping, purely as diagnostic telemetry.
        total = 0.0
        for mv in sample:
            new_co = Vector((0.0, 0.0, 0.0))
            for body_ax in range(3):
                ma = best_perm[body_ax]
                new_co[body_ax] = mv[ma] * best_signs[body_ax] * best_scale
            _, _, dist = mih_kd.find(new_co)
            total += dist
        best_score = total

        axis_names_local = ["X", "Y", "Z"]
        print(f"      scale anchor: mesh-{axis_names_local[anchor_mesh_ax]} "
              f"(size={anchor_mesh_size:.4f}) -> "
              f"MIH-{axis_names_local[anchor_body_ax]} "
              f"(size={anchor_mih_size:.4f})  =>  scale={best_scale:.4f}")
    else:
        best_score = float("inf")
        best_perm = (0, 1, 2)
        best_signs = (1, 1, 1)
        best_scale = 1.0

        for perm in itertools.permutations(range(3)):
            for signs in itertools.product((-1, 1), repeat=3):
                meshy_Y_axis = perm[1]
                meshy_Y_size = meshy_sizes[meshy_Y_axis]
                if meshy_Y_size < 1e-6:
                    continue
                uniform_scale = mih_Y_ext / meshy_Y_size

                total = 0.0
                for mv in sample:
                    new_co = Vector((0.0, 0.0, 0.0))
                    for body_ax in range(3):
                        ma = perm[body_ax]
                        new_co[body_ax] = mv[ma] * signs[body_ax] * uniform_scale
                    _, _, dist = mih_kd.find(new_co)
                    total += dist
                if total < best_score:
                    best_score = total
                    best_perm = perm
                    best_signs = signs
                    best_scale = uniform_scale

    axis_names = ["X", "Y", "Z"]
    perm_str = "".join(axis_names[i] for i in best_perm)
    sign_str = "".join("+" if s > 0 else "-" for s in best_signs)
    avg_dist = best_score / len(sample)
    mode_str = "FORCED" if axis_override is not None else "auto"
    print(f"      Axis mapping ({mode_str}): body[XYZ] <- meshy[{perm_str}], "
          f"signs: {sign_str},  uniform_scale={best_scale:.4f}")
    print(f"      Avg sample distance to MeshyInputHands: {avg_dist:.4f}")

    for v in glove.data.vertices:
        old = v.co - meshy_ctr
        new_co = Vector((0.0, 0.0, 0.0))
        for body_ax in range(3):
            ma = best_perm[body_ax]
            new_co[body_ax] = old[ma] * best_signs[body_ax] * best_scale
        v.co = new_co
    glove.data.update()

    # ------------------------------------------------------------------
    # Split by X sign and snap each half to shell per-hand centroids
    # ------------------------------------------------------------------
    print("[3/5] Splitting by X sign and snapping to per-hand centroids")
    sys.stdout.flush()

    left_idx = [i for i, v in enumerate(glove.data.vertices) if v.co.x < 0.0]
    right_idx = [i for i, v in enumerate(glove.data.vertices) if v.co.x > 0.0]
    neutral = len(glove.data.vertices) - len(left_idx) - len(right_idx)
    print(f"      Split: left={len(left_idx)}  right={len(right_idx)}  "
          f"on-plane={neutral}")
    if not left_idx or not right_idx:
        raise RuntimeError(
            "Split failed - one side is empty. Meshy may have merged the "
            "two gloves or the axis mapping is wrong."
        )

    def component_centroid(indices):
        s = Vector((0.0, 0.0, 0.0))
        for i in indices:
            s += glove.data.vertices[i].co
        return s / len(indices)

    left_comp_ctr = component_centroid(left_idx)
    right_comp_ctr = component_centroid(right_idx)

    left_offset = refs["left_ctr"] - left_comp_ctr
    right_offset = refs["right_ctr"] - right_comp_ctr
    for i in left_idx:
        glove.data.vertices[i].co = glove.data.vertices[i].co + left_offset
    for i in right_idx:
        glove.data.vertices[i].co = glove.data.vertices[i].co + right_offset
    glove.data.update()

    f_min, f_max, _ = bounds_and_centroid(
        [v.co.copy() for v in glove.data.vertices]
    )
    print(f"      Final bounds: X=[{f_min.x:.2f},{f_max.x:.2f}]  "
          f"Y=[{f_min.y:.2f},{f_max.y:.2f}]  Z=[{f_min.z:.2f},{f_max.z:.2f}]")

    # ------------------------------------------------------------------
    # KD-tree weight transfer from base_body_hands
    # ------------------------------------------------------------------
    print("[4/5] KD-tree weight transfer from base_body_hands")
    sys.stdout.flush()
    glove.vertex_groups.clear()
    for mod in list(glove.modifiers):
        if mod.type == "ARMATURE":
            glove.modifiers.remove(mod)

    all_positions = []
    all_weights = []
    for rname in REGIONS:
        src_region = region_meshes.get(rname)
        if not src_region:
            continue
        vg_names = {vg.index: vg.name for vg in src_region.vertex_groups}
        for v in src_region.data.vertices:
            groups = {}
            for g in v.groups:
                gname = vg_names.get(g.group)
                if gname and g.weight > 0.0001:
                    groups[gname] = g.weight
            all_positions.append(v.co.copy())
            all_weights.append(groups)

    kd = KDTree(len(all_positions))
    for i, pos in enumerate(all_positions):
        kd.insert(pos, i)
    kd.balance()

    total_near = 0.0
    sample_n = min(200, len(glove.data.vertices))
    step2 = max(1, len(glove.data.vertices) // sample_n)
    for i in range(0, len(glove.data.vertices), step2):
        _, _, d = kd.find(glove.data.vertices[i].co)
        total_near += d
    avg_fit = total_near / (len(glove.data.vertices) // step2)
    print(f"      Avg sample distance to nearest body_hands vert: {avg_fit:.4f}")

    transferred = 0
    for rv_idx, rv in enumerate(glove.data.vertices):
        neighbors = kd.find_n(rv.co, WEIGHT_NEIGHBORS)
        inv_weights = []
        for _co, idx, dist in neighbors:
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
                    if name not in [vg.name for vg in glove.vertex_groups]:
                        glove.vertex_groups.new(name=name)
                    glove.vertex_groups[name].add([rv_idx], nw, "REPLACE")
                    transferred += 1
    print(f"      Transferred {transferred} weight entries, "
          f"{len(glove.vertex_groups)} groups")

    # ------------------------------------------------------------------
    # Parent to armature & export
    # ------------------------------------------------------------------
    print(f"[5/5] Parent + export -> {out}")
    sys.stdout.flush()
    mod = glove.modifiers.new(name="Armature", type="ARMATURE")
    mod.object = base_arm

    if glove.parent:
        bpy.ops.object.select_all(action="DESELECT")
        glove.select_set(True)
        bpy.context.view_layer.objects.active = glove
        bpy.ops.object.parent_clear(type="CLEAR")
    glove.parent = base_arm
    glove.matrix_parent_inverse = Matrix.Identity(4)
    glove.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()

    keep = {glove.name, base_arm.name}
    bpy.ops.object.select_all(action="DESELECT")
    for obj in list(bpy.data.objects):
        if obj.name not in keep:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    bpy.ops.object.select_all(action="DESELECT")
    glove.select_set(True)
    base_arm.select_set(True)
    bpy.context.view_layer.objects.active = base_arm

    s, dn = suppress()
    bpy.ops.export_scene.gltf(
        filepath=out,
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
    return True


def main():
    print("=" * 60)
    print("Reading shared references")
    print("=" * 60)
    refs = build_references()

    only = None
    for arg in sys.argv:
        if arg.startswith("--only="):
            raw = arg.split("=", 1)[1]
            only = {p.strip() for p in raw.split(",") if p.strip()}

    ok = 0
    skipped = 0
    for piece in PIECES:
        if only is not None:
            piece_name = os.path.splitext(os.path.basename(piece["src"]))[0]
            if piece_name not in only:
                skipped += 1
                continue
        try:
            if process_piece(piece, refs):
                ok += 1
        except Exception as e:
            print(f"  ERROR processing {piece['src']}: {e}")

    print("=" * 60)
    print(f"Finished: {ok}/{len(PIECES) - skipped} pieces"
          + (f" (skipped {skipped})" if skipped else ""))
    print("=" * 60)
    sys.stdout.flush()


main()
