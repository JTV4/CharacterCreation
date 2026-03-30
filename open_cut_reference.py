"""
open_cut_reference.py
======================
Generates cut_reference.blend — a Blender file that shows the BaseFemaleV2
split mesh with coloured visual markers at every bisect cut location.

PURPOSE
-------
This is a reference file for verifying and reproducing the body-region cuts
defined in split_base_female_v2.py. Open it in Blender to confirm each cut
plane lines up with the intended boundary on the character mesh. If cuts
need adjusting, move the markers to new positions, read their coordinates
from the N-panel (Item → Location), and update split_base_female_v2.py.

OUTPUT FILE
-----------
  cut_reference.blend

CONTENTS OF THE BLEND FILE
---------------------------
  BaseFemaleV2 mesh    The 12-region split body (imported from GLB)
  8 Z-plane discs      Thin coloured horizontal planes at each body cut height
  4 arm torus rings    Coloured rings at each elbow/wrist cut position
  12 text labels       Name + coordinate floating above each marker

BODY REGIONS (12 total)
-----------------------
  The base female mesh is split into these independently hideable pieces:

    head          — above the neck cut
    upper_torso   — neck to waist (minus arms)
    lower_torso   — waist to hip
    arm_upper     — shoulder to elbow
    arm_lower     — elbow to wrist
    hands         — wrist to fingertips
    leg_upper     — hip to mid-thigh
    leg_thigh     — mid-thigh to above-knee
    leg_knee      — above-knee to below-knee
    leg_shin      — below-knee to mid-shin
    leg_ankle     — mid-shin to ankle
    foot          — ankle down

CUT POSITIONS (world space, Z-up, meters)
------------------------------------------
  Body Z-plane cuts:
    Neck          Z = 1.486    head         | upper_torso
    Waist         Z = 1.240    upper_torso  | lower_torso
    Hip           Z = 1.066    lower_torso  | leg_upper
    Mid-Thigh     Z = 0.796    leg_upper    | leg_thigh
    Above Knee    Z = 0.572    leg_thigh    | leg_knee
    Below Knee    Z = 0.436    leg_knee     | leg_shin
    Mid-Shin      Z = 0.270    leg_shin     | leg_ankle
    Ankle         Z = 0.100    leg_ankle    | foot

  Arm X-plane cuts (bilateral, perpendicular to arm in T-pose):
    Elbow L       X =  0.305   arm_upper    | arm_lower
    Wrist L       X =  0.645   arm_lower    | hands
    Elbow R       X = -0.305   arm_upper    | arm_lower
    Wrist R       X = -0.645   arm_lower    | hands

MARKER COLOURS
--------------
  Red       Neck              Orange ring   Elbow L / R
  Green     Waist             Magenta ring  Wrist L / R
  Blue      Hip
  Yellow    Mid-Thigh
  Orange    Above Knee
  Cyan      Below Knee
  Purple    Mid-Shin
  Pink      Ankle

HOW TO ADJUST CUTS
------------------
  1. Open cut_reference.blend in Blender
  2. Select a cut marker (disc or ring)
  3. Press G then Z (for Z-planes) or G then X (for arm rings) to slide it
  4. Read the new position from the N-panel → Item → Location
  5. Update the values in split_base_female_v2.py
  6. Re-run: /Applications/Blender.app/Contents/MacOS/Blender --background
             --python split_base_female_v2.py
  7. Re-run this script to regenerate the reference blend

RELATED FILES
-------------
  split_base_female_v2.py    Blender script that performs the actual bisect
                             cuts and exports BaseFemaleV2.glb
  viewer/public/models/BaseFemaleV2.glb
                             The exported 12-region split mesh used by the
                             Three.js viewer

RUN
---
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python open_cut_reference.py
"""

import bpy
import os
import math

CLEAN_GLB = os.path.abspath("viewer/public/models/BaseFemaleV2.glb")
SAVE_PATH = os.path.abspath("cut_reference.blend")

# ── Cut positions (must match split_base_female_v2.py exactly) ────────────────
Z_CUTS = [
    ("Neck (head | upper_torso)",             1.486, (0.80, 0.20, 0.20, 0.5)),   # red
    ("Waist (upper_torso | lower_torso)",     1.24,  (0.20, 0.80, 0.20, 0.5)),   # green
    ("Hip (lower_torso | leg_upper)",         1.066, (0.20, 0.40, 0.90, 0.5)),   # blue
    ("Mid-Thigh (leg_upper | leg_thigh)",     0.796, (0.90, 0.70, 0.10, 0.5)),   # yellow
    ("Above Knee (leg_thigh | leg_knee)",     0.572, (0.90, 0.45, 0.10, 0.5)),   # orange
    ("Below Knee (leg_knee | leg_shin)",      0.436, (0.10, 0.75, 0.75, 0.5)),   # cyan
    ("Mid-Shin (leg_shin | leg_ankle)",       0.27,  (0.70, 0.20, 0.90, 0.5)),   # purple
    ("Ankle (leg_ankle | foot)",              0.10,  (0.90, 0.40, 0.70, 0.5)),   # pink
]

ARM_CUTS = [
    ("Elbow L (arm_upper | arm_lower)",  ( 0.305,  0.002, 1.412), (1.0, 0.55, 0.0, 0.7)),
    ("Wrist L (arm_lower | hands)",      ( 0.645,  0.002, 1.396), (1.0, 0.20, 0.55, 0.7)),
    ("Elbow R (arm_upper | arm_lower)",  (-0.305,  0.04,  1.412), (1.0, 0.55, 0.0, 0.7)),
    ("Wrist R (arm_lower | hands)",      (-0.645, -0.002, 1.396), (1.0, 0.20, 0.55, 0.7)),
]

# ── Setup scene ───────────────────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=CLEAN_GLB)
bpy.context.view_layer.update()

# ── Z-plane markers (thin colored discs + text labels) ───────────────────────
for name, z_val, color in Z_CUTS:
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, 0, z_val))
    plane = bpy.context.active_object
    plane.name = name
    plane.scale = (0.55, 0.55, 0.001)

    mat = bpy.data.materials.new(name=f"mat_{name}")
    mat.use_nodes = False
    mat.diffuse_color = color
    plane.data.materials.append(mat)

    plane.lock_location[0] = True
    plane.lock_location[1] = True

    # Text label floating above the disc
    bpy.ops.object.text_add(location=(0.42, 0, z_val + 0.01))
    txt = bpy.context.active_object
    txt.data.body = f"{name}  Z={z_val}"
    txt.data.size = 0.025
    txt.name = f"Label_{name}"
    txt.rotation_euler = (math.pi / 2, 0, 0)

    txt_mat = bpy.data.materials.new(name=f"txtmat_{name}")
    txt_mat.use_nodes = False
    txt_mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    txt.data.materials.append(txt_mat)

# ── Arm cut markers (torus rings + text labels) ──────────────────────────────
for name, pos, color in ARM_CUTS:
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.06,
        minor_radius=0.005,
        location=pos,
        rotation=(0, math.pi / 2, 0),
    )
    ring = bpy.context.active_object
    ring.name = name

    mat = bpy.data.materials.new(name=f"mat_{name}")
    mat.use_nodes = False
    mat.diffuse_color = color
    ring.data.materials.append(mat)

    # Text label above the ring
    bpy.ops.object.text_add(location=(pos[0], pos[1], pos[2] + 0.08))
    txt = bpy.context.active_object
    txt.data.body = f"{name}  X={pos[0]:.3f}"
    txt.data.size = 0.02
    txt.name = f"Label_{name}"
    txt.rotation_euler = (math.pi / 2, 0, 0)

    txt_mat = bpy.data.materials.new(name=f"txtmat_{name}")
    txt_mat.use_nodes = False
    txt_mat.diffuse_color = (color[0], color[1], color[2], 1.0)
    txt.data.materials.append(txt_mat)

# ── Save ──────────────────────────────────────────────────────────────────────
bpy.ops.wm.save_as_mainfile(filepath=SAVE_PATH)

print(f"\nSaved → {SAVE_PATH}")
print("\nCut markers:")
for name, z, _ in Z_CUTS:
    print(f"  {name:20s}  Z = {z}")
for name, pos, _ in ARM_CUTS:
    print(f"  {name:20s}  X = {pos[0]:.3f}  Y = {pos[1]:.3f}  Z = {pos[2]:.3f}")
