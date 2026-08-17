"""
inspect_building1_floor.py
==========================
Focused diagnostic: figure out WHERE the "wooden floor" actually lives
in Building1.glb.  Stage 1 (bisect at z <= 0.076) currently shows a
wireframe of wall stubs with no visible floor — but Stage 2 clearly
shows a brown wooden floor inside the walls.  Something at z > 0.076
is being culled by our Stage 1 cut, OR the floor at z=0 has a normal
that points down (-Z) and gets backface-culled from an above camera.

This script bucketizes faces by their centroid Z and reports normal
directions per bucket, so we can see:
  - Is there a horizontal (Z-facing) face near z=0?  Which way does
    it point?
  - Are there stacked horizontal surfaces at other Z levels (e.g.
    an actual floor plane at z=0.1 instead of z=0)?
  - What Z ranges contain the bulk of the geometry?

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python inspect_building1_floor.py
"""

import os
import bpy
from mathutils import Vector

SRC_GLB = os.path.expanduser(
    "~/Desktop/Models/Buildings/Building1.glb"
)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
bpy.context.view_layer.update()

meshes = [o for o in bpy.data.objects if o.type == "MESH"]
if not meshes:
    raise RuntimeError("No meshes found")

# Bake parent transforms.
bpy.ops.object.select_all(action="DESELECT")
for m in meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

obj = meshes[0]
me = obj.data

print()
print("=" * 72)
print(f"BUILDING1 FLOOR DIAGNOSTIC")
print("=" * 72)

# Bucket faces by centroid Z (0.05m bands).  For each bucket, count
# faces AND count those with a horizontal-facing normal (|nz| > 0.9).
BUCKET = 0.05
buckets = {}   # bucket_z_min -> {"n": count, "up": count, "down": count}
for f in me.polygons:
    z = f.center.z
    key = round(z / BUCKET) * BUCKET
    b = buckets.setdefault(key, {"n": 0, "up": 0, "down": 0})
    b["n"] += 1
    nz = f.normal.z
    if nz > 0.9:
        b["up"] += 1
    elif nz < -0.9:
        b["down"] += 1

print(f"\nFace count by Z band (bucket = {BUCKET:.2f} m):")
print(f"  {'Z band':>12}   {'faces':>6}   {'horiz +Z (floor-up)':>22}   {'horiz -Z (floor-down)':>22}")
for key in sorted(buckets):
    b = buckets[key]
    print(
        f"  [{key:+.3f}, {key+BUCKET:+.3f}]"
        f"   {b['n']:>6}   {b['up']:>22}   {b['down']:>22}"
    )

# Now zoom into the sub-bucket around z=0 to pinpoint the exact
# floor face(s), and print centroid + normal + material for each
# candidate.
print("\nCandidate FLOOR faces (centroid z in [-0.02, +0.10], |nz| > 0.85):")
for f in me.polygons:
    z = f.center.z
    if -0.02 <= z <= 0.10 and abs(f.normal.z) > 0.85:
        v_zs = [me.vertices[vi].co.z for vi in f.vertices]
        print(
            f"  face #{f.index:>4}"
            f"   center=({f.center.x:+.3f}, {f.center.y:+.3f}, {f.center.z:+.3f})"
            f"   normal=({f.normal.x:+.2f}, {f.normal.y:+.2f}, {f.normal.z:+.2f})"
            f"   vert-Zs={[f'{z:+.3f}' for z in v_zs]}"
            f"   mat_index={f.material_index}"
        )

# Also: what's the LOWEST horizontal (+Z) face in the whole mesh?
lowest_up = None
for f in me.polygons:
    if f.normal.z > 0.85:
        if lowest_up is None or f.center.z < lowest_up.center.z:
            lowest_up = f
if lowest_up is not None:
    print(f"\nLowest upward-facing (+Z) face:")
    print(f"  z={lowest_up.center.z:+.4f}   normal.z={lowest_up.normal.z:+.3f}")

lowest_down = None
for f in me.polygons:
    if f.normal.z < -0.85:
        if lowest_down is None or f.center.z < lowest_down.center.z:
            lowest_down = f
if lowest_down is not None:
    print(f"\nLowest downward-facing (-Z) face:")
    print(f"  z={lowest_down.center.z:+.4f}   normal.z={lowest_down.normal.z:+.3f}")

print("\n" + "=" * 72)
