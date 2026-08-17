"""
generate_equipment_shell_v1_male.py
===================================
Generates Male Equipment Shell V1 — 12 inflated shell meshes based on
BaseMaleV2. Same thickness tiers as the female Shell V1 set.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_equipment_shell_v1_male.py

Output:
  viewer/public/equipment/Male/ShellV1/*.glb  (12 files)
"""

import os
import bpy
import bmesh

SRC_GLB = os.path.abspath("viewer/public/models/BaseMaleV2.glb")
OUT_DIR = os.path.abspath("viewer/public/equipment/Male/ShellV1")
os.makedirs(OUT_DIR, exist_ok=True)

THICKNESS = {
    "base_body_head":        0.003,
    "base_body_upper_torso": 0.008,
    "base_body_lower_torso": 0.008,
    "base_body_arm_upper":   0.008,
    "base_body_arm_lower":   0.008,
    "base_body_hands":       0.010,
    "base_body_leg_upper":   0.006,
    "base_body_leg_thigh":   0.006,
    "base_body_leg_knee":    0.006,
    "base_body_leg_shin":    0.006,
    "base_body_leg_ankle":   0.012,
    "base_body_foot":        0.012,
}

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

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
bpy.context.view_layer.update()

armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes = {o.name: o for o in bpy.data.objects if o.type == "MESH"}

print(f"Loaded {len(region_meshes)} region meshes from BaseMaleV2.glb")
for name in sorted(region_meshes.keys()):
    print(f"  {name}: {len(region_meshes[name].data.vertices)} verts")

for region_name, thickness in THICKNESS.items():
    src = region_meshes.get(region_name)
    if not src:
        print(f"  WARNING: {region_name} not found in GLB, skipping")
        continue

    shell_name = SHELL_NAMES[region_name]

    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    bpy.ops.object.duplicate(linked=False)
    shell = bpy.context.active_object
    shell.name = shell_name
    shell.data.name = shell_name

    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(shell.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.normal_update()

    for v in bm.verts:
        if v.normal.length > 0.0001:
            v.co += v.normal.normalized() * thickness

    for f in bm.faces:
        f.smooth = True

    bmesh.update_edit_mesh(shell.data)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()

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

    bpy.ops.object.select_all(action="DESELECT")
    shell.select_set(True)
    bpy.ops.object.delete(use_global=False)

print(f"\nAll Male Equipment Shell V1 files exported to {OUT_DIR}")
