"""
inspect_building1.py
====================
Diagnostic pass over `Building1.glb` before we design the construction-stage
generator.  We need three facts to pick the right slicing strategy:

  1. Is the building ONE merged mesh or several named parts
     (e.g. `Roof`, `Walls`, `Floor`, `Windows`)?  Named parts let us
     hide/delete by name — much cleaner than a Z-slice.  A single
     merged mesh forces us to bisect by height.

  2. What is the world-space bounding box?  Z-min / Z-max drive the
     stage cuts (5% / 50% / 85% of height).

  3. Per-mesh vertex/face counts, materials, UV layers — needed to
     size Stage-1's floor cap and to know whether we'll bake decent
     textures on the sliced walls.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python inspect_building1.py
"""

import os
import bpy

SRC_GLB = os.path.expanduser(
    "~/Desktop/Models/Buildings/Building1.glb"
)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SRC_GLB)
bpy.context.view_layer.update()

print()
print("=" * 72)
print(f"INSPECTING: {SRC_GLB}")
print("=" * 72)

all_objs = list(bpy.data.objects)
mesh_objs = [o for o in all_objs if o.type == "MESH"]
other_objs = [o for o in all_objs if o.type != "MESH"]

print(f"\nTotal objects: {len(all_objs)}")
print(f"  Meshes:  {len(mesh_objs)}")
print(f"  Other:   {len(other_objs)} ({', '.join(sorted({o.type for o in other_objs})) or 'none'})")

print("\n--- Mesh inventory (world-space) ---")
scene_min = [ float("inf")] * 3
scene_max = [-float("inf")] * 3

for obj in mesh_objs:
    verts_local = [v.co for v in obj.data.vertices]
    if not verts_local:
        print(f"  {obj.name}: EMPTY MESH")
        continue

    world_coords = [obj.matrix_world @ v for v in verts_local]
    xs = [c.x for c in world_coords]
    ys = [c.y for c in world_coords]
    zs = [c.z for c in world_coords]
    xr = (min(xs), max(xs))
    yr = (min(ys), max(ys))
    zr = (min(zs), max(zs))

    for i, r in enumerate((xr, yr, zr)):
        if r[0] < scene_min[i]:
            scene_min[i] = r[0]
        if r[1] > scene_max[i]:
            scene_max[i] = r[1]

    n_v = len(obj.data.vertices)
    n_f = len(obj.data.polygons)
    n_uv = len(obj.data.uv_layers)
    n_mat = len(obj.data.materials)
    mat_names = ", ".join(m.name if m else "<none>" for m in obj.data.materials)

    print(f"  {obj.name}")
    print(f"    verts={n_v:>6}  faces={n_f:>6}  uv_layers={n_uv}  materials={n_mat} [{mat_names}]")
    print(f"    X: [{xr[0]:+8.3f}, {xr[1]:+8.3f}]  span={xr[1]-xr[0]:.3f}")
    print(f"    Y: [{yr[0]:+8.3f}, {yr[1]:+8.3f}]  span={yr[1]-yr[0]:.3f}")
    print(f"    Z: [{zr[0]:+8.3f}, {zr[1]:+8.3f}]  span={zr[1]-zr[0]:.3f}")

print("\n--- Scene bounding box (world) ---")
if all(v != float("inf") for v in scene_min):
    print(f"  X: [{scene_min[0]:+8.3f}, {scene_max[0]:+8.3f}]  span={scene_max[0]-scene_min[0]:.3f}")
    print(f"  Y: [{scene_min[1]:+8.3f}, {scene_max[1]:+8.3f}]  span={scene_max[1]-scene_min[1]:.3f}")
    print(f"  Z: [{scene_min[2]:+8.3f}, {scene_max[2]:+8.3f}]  span={scene_max[2]-scene_min[2]:.3f}")
    height = scene_max[2] - scene_min[2]
    print(f"\n  Suggested stage cut heights (Z):")
    print(f"    Stage 1 (foundation, 5%):    z <= {scene_min[2] + 0.05 * height:+.3f}")
    print(f"    Stage 2 (half walls, 50%):   z <= {scene_min[2] + 0.50 * height:+.3f}")
    print(f"    Stage 3 (walls no roof, 85%): z <= {scene_min[2] + 0.85 * height:+.3f}")
else:
    print("  <no mesh geometry found>")

print("\n" + "=" * 72)
print("INSPECTION COMPLETE")
print("=" * 72)
