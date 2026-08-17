"""
inspect_stage_outputs.py
========================
Load each Building1 stage output back into Blender and print:
  - Root object count & names
  - Per-object transform (location, rotation_euler, scale)
  - Per-mesh vertex/face count and WORLD-SPACE bounding box

Goal: verify that every stage GLB has an identity root transform
(location=0, rotation=0, scale=1) AND the same XY footprint as the
source Complete building, so the viewer never "jumps" or "resizes"
when the user flips between stages.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python inspect_stage_outputs.py
"""
import os
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(HERE, "viewer/public/buildings")

FILES = [
    # Original source (before normalization — for reference only)
    "~/Desktop/Models/Buildings/Building1.glb",
    # Normalized viewer copies — these are the ones the browser loads
    f"{VIEWER}/Building1.glb",
    f"{VIEWER}/Construction/Building1Stage0.glb",
    f"{VIEWER}/Construction/Building1Stage1.glb",
    f"{VIEWER}/Construction/Building1Stage2.glb",
    f"{VIEWER}/Construction/Building1Stage3.glb",
]


def inspect(path: str) -> None:
    path = os.path.expanduser(path)
    print("\n" + "=" * 72)
    print(f"FILE: {path}")
    print("=" * 72)
    if not os.path.exists(path):
        print("  [MISSING]")
        return

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()

    objs = list(bpy.data.objects)
    print(f"  {len(objs)} objects: {[o.name for o in objs]}")
    for o in objs:
        loc = tuple(round(v, 4) for v in o.location)
        rot = tuple(round(v, 4) for v in o.rotation_euler)
        sca = tuple(round(v, 4) for v in o.scale)
        print(f"    {o.name}  type={o.type}  loc={loc}  rot={rot}  scale={sca}")
        if o.type == "MESH":
            me = o.data
            n_v = len(me.vertices)
            n_f = len(me.polygons)
            world_verts = [o.matrix_world @ v.co for v in me.vertices]
            if world_verts:
                xs = [v.x for v in world_verts]
                ys = [v.y for v in world_verts]
                zs = [v.z for v in world_verts]
                print(f"      verts={n_v}  faces={n_f}")
                print(f"      world bounds: "
                      f"X[{min(xs):+.3f}, {max(xs):+.3f}] "
                      f"Y[{min(ys):+.3f}, {max(ys):+.3f}] "
                      f"Z[{min(zs):+.3f}, {max(zs):+.3f}]")


for f in FILES:
    inspect(f)
