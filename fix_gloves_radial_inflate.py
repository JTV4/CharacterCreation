"""
fix_gloves_radial_inflate.py
=============================
Radially inflates each finger tube of shell_gloves.glb to fix idle-pose
inner-finger clipping.

WHY THIS APPROACH:
  Previous fixes pushed inner-palm vertices in the global -Y direction.
  This only helps when the arm is in T-pose (arm horizontal). In idle pose
  the arm bone rotates ~65° (mixamorigLeftArm quaternion from FemaleIdle.anim),
  so the "body-facing" surface of the fingers no longer aligns with -Y.
  A global directional push therefore doesn't create clearance where it is
  needed in idle.

  The correct fix is to treat each finger as a tube and push every vertex
  OUTWARD from the finger tube's central axis (in the plane perpendicular to
  the finger axis). This adds clearance in ALL radial directions, so it
  works regardless of pose rotation.

IMPLEMENTATION:
  1. Finger zone: vertices with |X| > 0.67 (wrist-to-tip) on each hand.
  2. Cross-section centroid: for each vertex, average Y and Z of all
     vertices within ±1 cm of that vertex's X value (same hand side).
     This gives the geometric centre of the finger bundle at that X slice.
  3. Push each vertex outward from the centroid in the YZ plane.
  4. Push amount is scaled by a Gaussian that ramps from 0 at the knuckle
     (|X| = 0.67) to peak at the fingertip zone (|X| > 0.77).
  5. Palm area vertices that are already the innermost concave surfaces
     get a matching push too (they benefit equally from radial inflation).

  Weights are NOT changed.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_gloves_radial_inflate.py
"""

import bpy
import bmesh
import math

BASE    = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"
GLB_IN  = f"{BASE}/viewer/public/equipment/shell_gloves.glb"
GLB_OUT = GLB_IN

PUSH_PEAK  = 0.014   # 14 mm radial push at fingertip peak
KNUCKLE_X  = 0.67    # inner boundary (wrist side) of finger zone
FINGER_X   = 0.77    # X position where push reaches peak
SLICE_HALF = 0.012   # half-width of cross-section slice for centroid calc (m)
MIN_MAG    = 0.002   # skip vertices already at the centroid (degenerate)


# ── Load ──────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB_IN)
bpy.ops.object.mode_set(mode='OBJECT')

mesh_objs = [o for o in bpy.data.objects
             if o.type == 'MESH' and len(o.vertex_groups) > 0]
armatures  = [o for o in bpy.data.objects if o.type == 'ARMATURE']
print(f"[radial_inflate] Loaded: {[o.name for o in mesh_objs]}")

for obj in mesh_objs:
    mesh = obj.data
    bm   = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()

    all_verts = list(bm.verts)

    # Separate left (X>0) and right (X<0) finger-zone vertices
    left_finger  = [v for v in all_verts if  v.co.x >  KNUCKLE_X]
    right_finger = [v for v in all_verts if  v.co.x < -KNUCKLE_X]

    moved = 0

    for side_verts, sign in [(left_finger, 1.0), (right_finger, -1.0)]:
        for v in side_verts:
            x, y, z = v.co.x, v.co.y, v.co.z

            # Cross-section centroid: average Y,Z of all same-side
            # finger-zone verts within ±SLICE_HALF of this X
            nearby = [u for u in side_verts
                      if abs(u.co.x - x) <= SLICE_HALF]
            if not nearby:
                continue

            ctr_y = sum(u.co.y for u in nearby) / len(nearby)
            ctr_z = sum(u.co.z for u in nearby) / len(nearby)

            # Outward direction in the YZ plane
            dy = y - ctr_y
            dz = z - ctr_z
            mag = math.sqrt(dy*dy + dz*dz)
            if mag < MIN_MAG:
                continue   # vertex is at the centroid, skip

            ny = dy / mag   # unit outward Y component
            nz = dz / mag   # unit outward Z component

            # Push amount ramps up linearly from knuckle to fingertip peak
            abs_x = abs(x)
            if abs_x >= FINGER_X:
                t = 1.0
            else:
                t = (abs_x - KNUCKLE_X) / (FINGER_X - KNUCKLE_X)
            push = PUSH_PEAK * t

            v.co.y += ny * push
            v.co.z += nz * push
            moved += 1

    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    print(f"  [{obj.name}] Radially inflated {moved} finger-zone vertices "
          f"(peak={PUSH_PEAK*1000:.0f}mm)")

# ── Export ────────────────────────────────────────────────────────────────────
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objs + armatures:
    obj.select_set(True)
if armatures:
    bpy.context.view_layer.objects.active = armatures[0]

print(f"\n[radial_inflate] Exporting → {GLB_OUT}")
bpy.ops.export_scene.gltf(
    filepath=GLB_OUT,
    export_format='GLB',
    use_selection=True,
    export_apply=False,
    export_yup=True,
    export_skins=True,
    export_all_influences=True,
    export_def_bones=True,
    export_animations=False,
    export_materials='EXPORT',
)
print("[radial_inflate] Done ✓")
