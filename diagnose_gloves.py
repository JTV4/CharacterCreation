"""
diagnose_gloves.py
Inspect shell_gloves.glb geometry and identify the palm inner crease zone.
Run: /Applications/Blender.app/Contents/MacOS/Blender --background --python diagnose_gloves.py
"""
import bpy

GLB = "viewer/public/equipment/shell_gloves.glb"

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=GLB)

m = next(o for o in bpy.data.objects if o.type == 'MESH' and len(o.vertex_groups) > 0)
vgs = {vg.index: vg.name for vg in m.vertex_groups}

xs = [v.co.x for v in m.data.vertices]
ys = [v.co.y for v in m.data.vertices]
zs = [v.co.z for v in m.data.vertices]
print(f"MESH: {m.name}  verts={len(m.data.vertices)}")
print(f"Bounds X:{min(xs):.3f}..{max(xs):.3f}  Y:{min(ys):.3f}..{max(ys):.3f}  Z:{min(zs):.3f}..{max(zs):.3f}")
print(f"Vertex groups (first 10): {list(vgs.values())[:10]}")

# The hands sit at |X| > 0.45 in T-pose.
# The palm inner surface (where clipping happens) is the concave side.
# Print cross-sections at different X slices to understand palm geometry.
print("\n--- Left hand cross-section (X > 0.45) ---")
left_hand = [v for v in m.data.vertices if v.co.x > 0.45]
if left_hand:
    lxs = [v.co.x for v in left_hand]
    lys = [v.co.y for v in left_hand]
    lzs = [v.co.z for v in left_hand]
    print(f"  Left hand: {len(left_hand)} verts")
    print(f"  X:{min(lxs):.3f}..{max(lxs):.3f}  Y:{min(lys):.3f}..{max(lys):.3f}  Z:{min(lzs):.3f}..{max(lzs):.3f}")

print("\n--- Right hand cross-section (X < -0.45) ---")
right_hand = [v for v in m.data.vertices if v.co.x < -0.45]
if right_hand:
    rxs = [v.co.x for v in right_hand]
    rys = [v.co.y for v in right_hand]
    rzs = [v.co.z for v in right_hand]
    print(f"  Right hand: {len(right_hand)} verts")
    print(f"  X:{min(rxs):.3f}..{max(rxs):.3f}  Y:{min(rys):.3f}..{max(rys):.3f}  Z:{min(rzs):.3f}..{max(rzs):.3f}")

# Find the palm area: wrist-to-knuckle zone, inner face
# In T-pose the palm faces down (-Y) and the dorsum faces up (+Y)
# Inner palm crease in Z-up space: the palm side has lower Y values
print("\n--- Palm zone candidates (left hand X>0.45, wrist-to-knuckle) ---")
# Look at the wrist-to-knuckle region (exclude fingertips)
palm_zone = [v for v in left_hand if v.co.x < 0.70]  # wrist + palm, before fingers spread
if palm_zone:
    pxs = [v.co.x for v in palm_zone]
    pys = [v.co.y for v in palm_zone]
    pzs = [v.co.z for v in palm_zone]
    print(f"  Palm zone (X 0.45-0.70): {len(palm_zone)} verts")
    print(f"  X:{min(pxs):.3f}..{max(pxs):.3f}  Y:{min(pys):.3f}..{max(pys):.3f}  Z:{min(pzs):.3f}..{max(pzs):.3f}")
    # The inner surface (palm) vs dorsum:
    y_mid = (min(pys) + max(pys)) / 2
    inner_palm = [v for v in palm_zone if v.co.y < y_mid]
    dorsum     = [v for v in palm_zone if v.co.y >= y_mid]
    print(f"  Inner palm (Y < {y_mid:.3f}): {len(inner_palm)} verts  Y range: {min(v.co.y for v in inner_palm):.3f}..{max(v.co.y for v in inner_palm):.3f}")
    print(f"  Dorsum     (Y >= {y_mid:.3f}): {len(dorsum)} verts  Y range: {min(v.co.y for v in dorsum):.3f}..{max(v.co.y for v in dorsum):.3f}")

# Middle finger zone
print("\n--- Middle finger zone (left, X roughly 0.58-0.80, Z around knuckle height) ---")
mid_finger = [v for v in m.data.vertices if 0.55 < v.co.x < 0.82 and v.co.z < 1.49]
if mid_finger:
    mxs = [v.co.x for v in mid_finger]
    mys = [v.co.y for v in mid_finger]
    mzs = [v.co.z for v in mid_finger]
    print(f"  {len(mid_finger)} verts  X:{min(mxs):.3f}..{max(mxs):.3f}  Y:{min(mys):.3f}..{max(mys):.3f}  Z:{min(mzs):.3f}..{max(mzs):.3f}")
