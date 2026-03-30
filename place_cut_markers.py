"""
place_cut_markers.py
====================
Creates visible cut-plane markers at the current default Z heights.

HOW TO USE:
  1. Open BaseFemaleClean.glb in Blender  (File → Import → glTF 2.0)
  2. Open the Scripting workspace, paste this script, and click Run
  3. You will see 5 coloured flat planes appear on the character —
     one for each seam between body regions.
  4. Select any plane and press G → Z to slide it up/down to exactly
     where you want that cut.
  5. When happy with all positions, open the N panel (press N),
     go to the Item tab, and read the Location Z for each plane.
  6. Tell your AI assistant the 5 Z values and it will regenerate
     the body split with those exact cut heights.

Plane names and what they control:
  CUT_neck    — head  ↕ upper_torso  (default 1.45 m)
  CUT_waist   — upper_torso ↕ lower_torso  (default 1.10 m)
  CUT_hip     — lower_torso ↕ upper_leg  (default 0.93 m)
  CUT_knee    — upper_leg  ↕ lower_leg  (default 0.51 m)
  CUT_ankle   — lower_leg  ↕ feet  (default 0.10 m)
"""

import bpy

# Current default cut heights in metres
CUTS = {
    "CUT_neck":  1.45,
    "CUT_waist": 1.10,
    "CUT_hip":   0.93,
    "CUT_knee":  0.51,
    "CUT_ankle": 0.10,
}

# Distinct colours so the planes are easy to tell apart
COLORS = {
    "CUT_neck":  (0.8, 0.2, 0.2, 0.4),   # red
    "CUT_waist": (0.2, 0.8, 0.2, 0.4),   # green
    "CUT_hip":   (0.2, 0.4, 0.9, 0.4),   # blue
    "CUT_knee":  (0.9, 0.7, 0.1, 0.4),   # yellow
    "CUT_ankle": (0.7, 0.2, 0.9, 0.4),   # purple
}

for name, z in CUTS.items():
    # Remove any existing marker with this name
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)

    # Add a plane mesh
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, 0, z))
    plane = bpy.context.active_object
    plane.name = name

    # Flatten to a very thin disc so it looks like a cut line
    plane.scale = (0.55, 0.55, 0.001)

    # Assign a coloured material so each cut is easy to identify
    mat = bpy.data.materials.new(name=f"mat_{name}")
    mat.use_nodes = False
    mat.diffuse_color = COLORS[name]
    plane.data.materials.append(mat)

    # Lock X and Y so it can only slide on Z
    plane.lock_location[0] = True
    plane.lock_location[1] = True

print("Cut markers created!")
print("Move each CUT_* plane along Z, then read back Location Z from the N panel.")
print()
for name, z in CUTS.items():
    print(f"  {name}: default Z = {z} m")
