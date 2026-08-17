"""
build_base_female_v3.py
=======================
Assemble the White SkinTextures Shell V1 pieces into BaseFemaleV3.glb —
a modular Female V2-compatible base with baked white skin textures.

Each piece is renamed to match BaseFemaleV2 region names (base_body_*),
parented to a single Mixamo armature from BaseFemaleV2, and exported.

Inputs:
  viewer/public/equipment/Female/SkinTextures/White/shell_v1_*.glb
  viewer/public/models/BaseFemaleV2.glb   (armature donor)

Output:
  viewer/public/models/BaseFemaleV3.glb
  rig/CharacterMesh/BaseFemaleV3.glb     (mirror copy)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python build_base_female_v3.py
"""

from __future__ import annotations

import os
import shutil
import sys

import bpy
from mathutils import Matrix

sys.stdout.reconfigure(line_buffering=True)

WHITE_DIR = os.path.abspath("viewer/public/equipment/Female/SkinTextures/White")
BASE_V2 = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
OUT = os.path.abspath("viewer/public/models/BaseFemaleV3.glb")
OUT_MIRROR = os.path.abspath("rig/CharacterMesh/BaseFemaleV3.glb")

# Shell V1 filename → BaseFemaleV2 mesh name
PIECES = [
    ("shell_v1_head.glb", "base_body_head"),
    ("shell_v1_upper_torso.glb", "base_body_upper_torso"),
    ("shell_v1_lower_torso.glb", "base_body_lower_torso"),
    ("shell_v1_arm_upper.glb", "base_body_arm_upper"),
    ("shell_v1_arm_lower.glb", "base_body_arm_lower"),
    ("shell_v1_hands.glb", "base_body_hands"),
    ("shell_v1_leg_upper.glb", "base_body_leg_upper"),
    ("shell_v1_leg_thigh.glb", "base_body_leg_thigh"),
    ("shell_v1_leg_knee.glb", "base_body_leg_knee"),
    ("shell_v1_leg_shin.glb", "base_body_leg_shin"),
    ("shell_v1_leg_ankle.glb", "base_body_leg_ankle"),
    ("shell_v1_foot.glb", "base_body_foot"),
]


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
    print("build_base_female_v3.py")
    print("=" * 60)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    # ---- Armature from BaseFemaleV2 ---------------------------------
    print("[1/3] Loading BaseFemaleV2 armature")
    s, dn = suppress()
    bpy.ops.import_scene.gltf(filepath=BASE_V2)
    bpy.context.view_layer.update()
    restore(s, dn)

    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    if not arm:
        raise RuntimeError("No armature in BaseFemaleV2")
    print(f"  Armature: {arm.name} ({len(arm.data.bones)} bones)")

    # Remove V2 body meshes + icospheres — we only need the armature
    for o in list(bpy.data.objects):
        if o.type == "MESH":
            bpy.data.objects.remove(o, do_unlink=True)

    # ---- Import each White piece, rename, rebind --------------------
    print("[2/3] Importing White SkinTextures pieces")
    body_meshes = []
    for fname, target_name in PIECES:
        path = os.path.join(WHITE_DIR, fname)
        if not os.path.exists(path):
            raise RuntimeError(f"Missing piece: {path}")

        pre = {o.name for o in bpy.data.objects}
        s, dn = suppress()
        bpy.ops.import_scene.gltf(filepath=path)
        bpy.context.view_layer.update()
        restore(s, dn)

        new_objs = [o for o in bpy.data.objects if o.name not in pre]
        meshes = [
            o for o in new_objs
            if o.type == "MESH" and "Icosphere" not in o.name
        ]
        armatures = [o for o in new_objs if o.type == "ARMATURE"]

        if not meshes:
            raise RuntimeError(f"No mesh in {fname}")
        mesh = max(meshes, key=lambda m: len(m.data.vertices))

        # Drop extra meshes / imported armatures from this piece
        for o in new_objs:
            if o != mesh and o.type in ("MESH", "ARMATURE"):
                bpy.data.objects.remove(o, do_unlink=True)

        mesh.name = target_name
        mesh.data.name = target_name

        # Clear existing armature mods / parent, bind to shared arm
        for mod in list(mesh.modifiers):
            if mod.type == "ARMATURE":
                mesh.modifiers.remove(mod)
        if mesh.parent:
            bpy.ops.object.select_all(action="DESELECT")
            mesh.select_set(True)
            bpy.context.view_layer.objects.active = mesh
            bpy.ops.object.parent_clear(type="CLEAR")

        mesh.parent = arm
        mesh.matrix_parent_inverse = Matrix.Identity(4)
        mesh.matrix_basis = Matrix.Identity(4)

        mod = mesh.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = arm

        print(
            f"  {target_name}: {len(mesh.data.vertices)}v / "
            f"{len(mesh.data.polygons)}f  "
            f"groups={len(mesh.vertex_groups)}  "
            f"mats={len(mesh.data.materials)}"
        )
        body_meshes.append(mesh)

    bpy.context.view_layer.update()

    # ---- Export -----------------------------------------------------
    print("[3/3] Exporting BaseFemaleV3.glb")
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    for m in body_meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = arm

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    s, dn = suppress()
    bpy.ops.export_scene.gltf(
        filepath=OUT,
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
    print(f"  → {OUT}")

    os.makedirs(os.path.dirname(OUT_MIRROR), exist_ok=True)
    shutil.copy2(OUT, OUT_MIRROR)
    print(f"  → {OUT_MIRROR}")

    print("=" * 60)
    print(f"Done: Female V3 with {len(body_meshes)} body regions")
    print("=" * 60)


if __name__ == "__main__":
    main()
