"""
generate_equipment_shell_v1.py
===============================
Generates Equipment Shell V1 — a full set of 12 inflated shell meshes based
on the BaseFemaleV2 split body. Each shell is a duplicate of its body region
inflated outward along vertex normals to create a clothing-like layer.

THICKNESS TIERS (from thinnest to thickest)
--------------------------------------------
  Tier 1  (0.003m)  head
  Tier 2  (0.006m)  leg_upper, leg_thigh, leg_knee, leg_shin
  Tier 3  (0.008m)  upper_torso, lower_torso, arm_upper, arm_lower
  Tier 4  (0.010m)  hands (gloves)
  Tier 5  (0.012m)  leg_ankle, foot (boots)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_equipment_shell_v1.py

Output:
  viewer/public/equipment/Female/ShellV1/*.glb  (12 files)
"""

import os
import bpy
import bmesh
from mathutils import Vector

SRC_GLB = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
OUT_DIR = os.path.abspath("viewer/public/equipment/Female/ShellV1")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Thickness per region ──────────────────────────────────────────────────────
THICKNESS = {
    "base_body_head":        0.003,   # Tier 1 — thinnest (helmet/hat)
    "base_body_upper_torso": 0.008,   # Tier 3 — medium (shirt/armor)
    "base_body_lower_torso": 0.008,   # Tier 3
    "base_body_arm_upper":   0.008,   # Tier 3
    "base_body_arm_lower":   0.008,   # Tier 3
    "base_body_hands":       0.010,   # Tier 4 — gloves (thicker than body)
    "base_body_leg_upper":   0.006,   # Tier 2 — legs (thinner than body)
    "base_body_leg_thigh":   0.006,   # Tier 2
    "base_body_leg_knee":    0.006,   # Tier 2
    "base_body_leg_shin":    0.006,   # Tier 2
    "base_body_leg_ankle":   0.012,   # Tier 5 — boots (thickest)
    "base_body_foot":        0.012,   # Tier 5
}

# Output filenames
SHELL_NAMES = {
    "base_body_head":        "shell_v1_head",
    "base_body_upper_torso": "shell_v1_upper_torso",
    "base_body_lower_torso": "shell_v1_lower_torso",
    "base_body_arm_upper":   "shell_v1_arm_upper",
    "base_body_arm_lower":   "shell_v1_arm_lower",
    "base_body_hands":       "shell_v1_hands",
    "base_body_leg_upper":   "shell_v1_leg_upper",
    "base_body_leg_thigh":   "shell_v1_leg_thigh",
    "base_body_leg_knee":    "shell_v1_leg_knee",
    "base_body_leg_shin":    "shell_v1_leg_shin",
    "base_body_leg_ankle":   "shell_v1_leg_ankle",
    "base_body_foot":        "shell_v1_foot",
}

# ── 1. Load the split mesh ────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

print(f"Loaded {len(region_meshes)} region meshes from BaseFemaleV2.glb")
for name in sorted(region_meshes.keys()):
    print(f"  {name}: {len(region_meshes[name].data.vertices)} verts")

# ── 2. Generate each shell ────────────────────────────────────────────────────
for region_name, thickness in THICKNESS.items():
    src = region_meshes.get(region_name)
    if not src:
        print(f"  WARNING: {region_name} not found in GLB, skipping")
        continue

    shell_name = SHELL_NAMES[region_name]

    # Duplicate the region mesh
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    bpy.ops.object.duplicate(linked=False)
    shell = bpy.context.active_object
    shell.name = shell_name
    shell.data.name = shell_name

    # Inflate: push each vertex outward along its normal
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(shell.data)

    # Compute normals
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()

    for v in bm.verts:
        if v.normal.length > 0.0001:
            v.co += v.normal.normalized() * thickness

    # Keep smooth shading
    for f in bm.faces:
        f.smooth = True

    bmesh.update_edit_mesh(shell.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()

    # Export this shell as individual GLB
    out_path = os.path.join(OUT_DIR, f"{shell_name}.glb")

    bpy.ops.object.select_all(action="DESELECT")
    shell.select_set(True)
    if armature:
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature

    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
    )

    print(f"  {shell_name}: {len(shell.data.vertices)} verts, thickness={thickness}m → {out_path}")

    # Remove the shell copy (keep source for next region)
    bpy.ops.object.select_all(action="DESELECT")
    shell.select_set(True)
    bpy.ops.object.delete(use_global=False)

print(f"\nAll Equipment Shell V1 files exported to {OUT_DIR}")
