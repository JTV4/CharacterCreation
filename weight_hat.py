"""
weight_hat.py
=============
Properly weights the Green Dragon Wizard Hat using the full character rig,
matching the structure of test_wizard_hat_f.glb (the reference working hat).

Key insight from inspecting the working hat:
  - Uses the FULL rig skeleton (all generic-named bones)
  - Mesh vertices are stored AT head-height world coordinates (Z ~1.66-1.95)
  - Only the head bone has non-zero weights (100%)

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender --background \\
        --python weight_hat.py
"""

import bpy
import mathutils
import os

ROOT    = os.path.dirname(os.path.abspath(__file__))
HAT_IN  = os.path.join(ROOT, "viewer/public/equipment/Female/Hats/green_dragon_wizard_hat(F).glb")
RIG_GLB = os.path.join(ROOT, "rig/output/rig_tpose.glb")
OUT     = os.path.join(ROOT, "viewer/public/equipment/Female/Hats/green_dragon_wizard_hat(F).glb")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh, do_unlink=True)
    for arm in list(bpy.data.armatures):
        bpy.data.armatures.remove(arm, do_unlink=True)

def largest_mesh():
    best, best_count = None, 0
    for o in bpy.data.objects:
        if o.type == "MESH":
            n = len(o.data.vertices)
            if n > best_count:
                best_count, best = n, o
    return best

# ---------------------------------------------------------------------------
# 1. Load rig – collect the full armature and bone world positions
# ---------------------------------------------------------------------------
print("Loading rig …")
clear_scene()
bpy.ops.import_scene.gltf(filepath=RIG_GLB)

rig_arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if rig_arm is None:
    raise RuntimeError("No armature in rig GLB")

# Collect head bone world position (Blender Z-up after import)
bpy.context.view_layer.objects.active = rig_arm
bpy.ops.object.mode_set(mode="POSE")

head_bone_world_z = None
for pb in rig_arm.pose.bones:
    if pb.name.lower() in ("head", "mixamorighead"):
        head_bone_world_z = (rig_arm.matrix_world @ pb.head).z
        head_bone_name = pb.name
        print(f"  Head bone: '{pb.name}' world Z = {head_bone_world_z:.4f}")
        break

bpy.ops.object.mode_set(mode="OBJECT")

if head_bone_world_z is None:
    raise RuntimeError("Could not find 'head' bone in rig")

# ---------------------------------------------------------------------------
# 2. Load the hat mesh (keeping the rig in the scene)
# ---------------------------------------------------------------------------
print("Loading hat …")
bpy.ops.import_scene.gltf(filepath=HAT_IN)

hat_obj = largest_mesh()
if hat_obj is None:
    raise RuntimeError("No mesh found in hat GLB")

print(f"  Hat mesh: '{hat_obj.name}'  verts={len(hat_obj.data.vertices)}")

# Bake any existing transforms into vertex data
bpy.context.view_layer.objects.active = hat_obj
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# Get the hat's Z extents in local/world space (same after apply)
zs = [v.co.z for v in hat_obj.data.vertices]
z_min, z_max = min(zs), max(zs)
z_center = (z_min + z_max) / 2
print(f"  Hat Z range (before move): {z_min:.4f} → {z_max:.4f}  center={z_center:.4f}")

# ---------------------------------------------------------------------------
# 3. Move hat vertices to head-height world space
#    The hat's center-of-mass should sit just above the head bone.
#    We shift all vertices so the hat bottom aligns with the head bone Z.
# ---------------------------------------------------------------------------
# How much to offset: place the hat brim at the head bone height
offset_z = head_bone_world_z - z_min          # lifts brim to head bone Z
print(f"  Moving hat up by {offset_z:.4f} m (brim → head bone at Z={head_bone_world_z:.4f})")

bpy.context.view_layer.objects.active = hat_obj
bpy.ops.object.mode_set(mode="EDIT")
import bmesh
bm = bmesh.from_edit_mesh(hat_obj.data)
for v in bm.verts:
    v.co.z += offset_z
bmesh.update_edit_mesh(hat_obj.data)
bpy.ops.object.mode_set(mode="OBJECT")

zs2 = [v.co.z for v in hat_obj.data.vertices]
print(f"  Hat Z range (after move): {min(zs2):.4f} → {max(zs2):.4f}")

# ---------------------------------------------------------------------------
# 4. Assign vertex groups matching the full rig bones
#    All verts → 100% head bone; other bone groups created with 0 weight
#    (game rigs need all bones present to animate correctly)
# ---------------------------------------------------------------------------
print("Assigning vertex groups …")
hat_obj.vertex_groups.clear()

all_indices = list(range(len(hat_obj.data.vertices)))

bpy.context.view_layer.objects.active = rig_arm
bpy.ops.object.mode_set(mode="POSE")
all_bone_names = [pb.name for pb in rig_arm.pose.bones]
bpy.ops.object.mode_set(mode="OBJECT")

bpy.context.view_layer.objects.active = hat_obj

# Create a vertex group for every bone in the rig
for bone_name in all_bone_names:
    vg = hat_obj.vertex_groups.new(name=bone_name)
    if bone_name == head_bone_name:
        vg.add(all_indices, 1.0, "REPLACE")
    else:
        vg.add(all_indices, 0.0, "REPLACE")

print(f"  {len(all_bone_names)} vertex groups created; '{head_bone_name}' = 1.0, rest = 0.0")

# ---------------------------------------------------------------------------
# 5. Parent hat to the rig armature
# ---------------------------------------------------------------------------
hat_obj.parent = rig_arm
mod = hat_obj.modifiers.new("Armature", "ARMATURE")
mod.object = rig_arm

# ---------------------------------------------------------------------------
# 6. Export — select only the rig and the hat (not any debug meshes)
# ---------------------------------------------------------------------------
print(f"Exporting → {OUT}")
bpy.ops.object.select_all(action="DESELECT")
rig_arm.select_set(True)
hat_obj.select_set(True)
bpy.context.view_layer.objects.active = rig_arm

bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format="GLB",
    use_selection=True,
    export_skins=True,
    export_morph=False,
    export_animations=False,
    export_apply=False,
    export_yup=True,
)

print(f"\n✓ Done → {OUT}")
print(f"  {len(all_indices)} verts, all weighted 100% to '{head_bone_name}'")
print(f"  Hat world Z: {min(zs2):.4f} → {max(zs2):.4f}")
