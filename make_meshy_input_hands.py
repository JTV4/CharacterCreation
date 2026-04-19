"""
make_meshy_input_hands.py
=========================
Generate a "Meshy-friendly" version of shell_v1_hands.glb where the two
gloves are translated close together (still side-by-side, separated by a
small gap) so Meshy AI's Text-to-Texture produces much better results
than the natural shoulder-width layout.

Pipeline (pure rigid translation — no scaling, no rotation):
  1. Import viewer/public/equipment/Female/ShellV1/shell_v1_hands.glb.
  2. Split verts by X sign:
       - left_hand  = verts with co.x < 0
       - right_hand = verts with co.x > 0
     (shell_v1_hands is cleanly split across the sagittal plane, so
     sign-based partitioning is robust.)
  3. Find each hand's inner X-edge (max.x for left, min.x for right) and
     translate each hand inward along X so the inner edges sit at
     ±GAP_CM / 2. Only X is touched — Y/Z/UVs are untouched.
  4. Strip the armature so the output is a clean static mesh GLB
     (Meshy ignores rig data anyway; removing it avoids any ambiguity).
  5. Export to viewer/public/equipment/Female/Gloves/MeshyInputHands.glb.

The **return trip** (after Meshy textures it) is a *separate* script.
It will use this same shell_v1_hands.glb as the "ground truth" reference
to (a) compute a single uniform scale factor via Y-extent matching and
(b) translate each of the two Meshy-output components to the original
per-hand centroids — undoing the translation applied here with zero
distortion.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python make_meshy_input_hands.py
"""

import os
import sys
import bpy

sys.stdout.reconfigure(line_buffering=True)

SHELL_HANDS = os.path.abspath(
    "viewer/public/equipment/Female/ShellV1/shell_v1_hands.glb"
)
OUT_GLB = os.path.abspath(
    "viewer/public/equipment/Female/Gloves/MeshyInputHands.glb"
)

# Distance between the inner edges of the two gloves, in the shell's
# native units (centimeters). 4 cm leaves a visible gap so Meshy doesn't
# fuse them into a single texture island, but keeps them close enough that
# Text-to-Texture treats them as one "gloves" subject.
GAP_CM = 4.0

OUT_NAME = "MeshyInputHands"


def suppress():
    dn = open(os.devnull, "w")
    s = os.dup(1)
    os.dup2(dn.fileno(), 1)
    return s, dn


def restore(s, dn):
    os.dup2(s, 1)
    os.close(s)
    dn.close()


def main():
    print("=" * 60)
    print("Generating Meshy-friendly input hands")
    print("=" * 60)
    sys.stdout.flush()

    bpy.ops.wm.read_factory_settings(use_empty=True)

    # ---- Import shell ------------------------------------------------
    print(f"[1/5] Loading {SHELL_HANDS}")
    sys.stdout.flush()
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=SHELL_HANDS)
    bpy.context.view_layer.update()
    restore(s, dn)

    shell_mesh = None
    for o in bpy.data.objects:
        if o.type == "MESH" and "Icosphere" not in o.name:
            shell_mesh = o
            break
    if shell_mesh is None:
        raise RuntimeError("Shell mesh not found in shell_v1_hands.glb")

    verts = shell_mesh.data.vertices
    xs = [v.co.x for v in verts]
    print(f"      Mesh: {shell_mesh.name} ({len(verts)} verts)  "
          f"X=[{min(xs):.3f},{max(xs):.3f}]")

    # ---- Split by X sign --------------------------------------------
    left_idx = [i for i, v in enumerate(verts) if v.co.x < 0.0]
    right_idx = [i for i, v in enumerate(verts) if v.co.x > 0.0]
    neutral = len(verts) - len(left_idx) - len(right_idx)
    print(f"[2/5] Splitting by X sign: "
          f"left={len(left_idx)}  right={len(right_idx)}  on-plane={neutral}")
    if neutral > 0:
        print("      WARNING: some verts lie exactly on X=0 and will not move")

    if not left_idx or not right_idx:
        raise RuntimeError(
            "Expected verts on both sides of X=0 but one side is empty."
        )

    left_max_x = max(verts[i].co.x for i in left_idx)   # inner edge of left hand
    right_min_x = min(verts[i].co.x for i in right_idx) # inner edge of right hand
    print(f"      Left  inner-X = {left_max_x:.3f}  (target: {-GAP_CM/2:.3f})")
    print(f"      Right inner-X = {right_min_x:.3f}  (target: {+GAP_CM/2:.3f})")

    # ---- Compute per-hand offsets -----------------------------------
    offset_left = (-GAP_CM / 2.0) - left_max_x   # left is negative -> move right (positive)
    offset_right = (+GAP_CM / 2.0) - right_min_x # right is positive -> move left (negative)
    print(f"[3/5] Offsets: left_hand += {offset_left:+.3f} X    "
          f"right_hand += {offset_right:+.3f} X")

    # ---- Apply translations (X only) --------------------------------
    for i in left_idx:
        v = verts[i]
        v.co = (v.co.x + offset_left, v.co.y, v.co.z)
    for i in right_idx:
        v = verts[i]
        v.co = (v.co.x + offset_right, v.co.y, v.co.z)
    shell_mesh.data.update()

    xs2 = [v.co.x for v in verts]
    print(f"      New X range: [{min(xs2):.3f}, {max(xs2):.3f}]  "
          f"(original was [{min(xs):.3f}, {max(xs):.3f}])")

    # ---- Strip armature (clean static mesh for Meshy) ---------------
    print("[4/5] Stripping armature / parenting, clearing vertex groups")
    for mod in list(shell_mesh.modifiers):
        if mod.type == "ARMATURE":
            shell_mesh.modifiers.remove(mod)
    shell_mesh.vertex_groups.clear()

    if shell_mesh.parent:
        bpy.ops.object.select_all(action="DESELECT")
        shell_mesh.select_set(True)
        bpy.context.view_layer.objects.active = shell_mesh
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")

    shell_mesh.name = OUT_NAME
    shell_mesh.data.name = OUT_NAME

    # Delete every other object (armatures, icospheres, etc.) so the
    # export is strictly {the mesh}.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in list(bpy.data.objects):
        if obj.name != shell_mesh.name:
            obj.select_set(True)
    if bpy.context.selected_objects:
        bpy.ops.object.delete(use_global=False)

    # ---- Export ------------------------------------------------------
    print(f"[5/5] Exporting -> {OUT_GLB}")
    sys.stdout.flush()
    os.makedirs(os.path.dirname(OUT_GLB), exist_ok=True)

    bpy.ops.object.select_all(action="DESELECT")
    shell_mesh.select_set(True)
    bpy.context.view_layer.objects.active = shell_mesh

    s, dn = suppress()
    bpy.ops.export_scene.gltf(
        filepath=OUT_GLB,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=False,
        export_animations=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_image_format="AUTO",
    )
    restore(s, dn)
    print("Done.")
    sys.stdout.flush()


main()
