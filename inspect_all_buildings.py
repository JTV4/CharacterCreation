"""
inspect_all_buildings.py
========================
Bulk diagnostic: run the same structural + walkable-floor detection on
every building in `~/Desktop/Models/Buildings/` (except Building6, which
the user has excluded).  For each building we report:

  1. mesh count / total verts / material list  — tells us whether it's
     a single-mesh baked asset (like Building1) or something we could
     slice by named parts.
  2. World-space bounding box  — needed to pick Z-cut heights per
     stage.
  3. Lowest +Z-facing face  — the "walkable floor" height; the Stage-1
     cut MUST sit above this or the slice renders as an invisible
     underside plate + wireframe stubs (the mistake we hit on
     Building1's first pass).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python inspect_all_buildings.py
"""

import os
import bpy

BUILDING_IDS = (2, 3, 4, 5, 7, 8)
BUILDINGS_DIR = os.path.expanduser("~/Desktop/Models/Buildings")


def inspect_one(building_id: int) -> None:
    path = os.path.join(BUILDINGS_DIR, f"Building{building_id}.glb")
    print()
    print("=" * 72)
    print(f"BUILDING {building_id}   {path}")
    print("=" * 72)

    if not os.path.exists(path):
        print(f"  MISSING: file not found")
        return

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    bpy.context.view_layer.update()

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    others = [o for o in bpy.data.objects if o.type != "MESH"]
    if not meshes:
        print("  NO MESHES")
        return

    print(f"\n  Meshes: {len(meshes)}   Other objects: {len(others)}")
    for m in meshes:
        n_v = len(m.data.vertices)
        n_f = len(m.data.polygons)
        mats = ", ".join(mm.name if mm else "<none>" for mm in m.data.materials) or "<none>"
        print(f"    {m.name:<30}  verts={n_v:>6}  faces={n_f:>6}  mats=[{mats}]")

    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    me = obj.data

    verts_w = [obj.matrix_world @ v.co for v in me.vertices]
    xs = [v.x for v in verts_w]; ys = [v.y for v in verts_w]; zs = [v.z for v in verts_w]
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    z_min, z_max = min(zs), max(zs)
    H = z_max - z_min
    print(f"\n  Bounds (world): X[{x_min:+.3f}, {x_max:+.3f}]  "
          f"Y[{y_min:+.3f}, {y_max:+.3f}]  Z[{z_min:+.3f}, {z_max:+.3f}]  H={H:.3f}")

    lowest_up = None
    lowest_down = None
    for f in me.polygons:
        if f.normal.z > 0.85 and (lowest_up is None or f.center.z < lowest_up.center.z):
            lowest_up = f
        if f.normal.z < -0.85 and (lowest_down is None or f.center.z < lowest_down.center.z):
            lowest_down = f

    up_z = lowest_up.center.z if lowest_up else None
    down_z = lowest_down.center.z if lowest_down else None
    print(f"  Lowest +Z-facing face (walkable floor):  z={up_z}")
    print(f"  Lowest -Z-facing face (base underside):  z={down_z}")

    if up_z is not None:
        kick = 0.10
        recommended_cut = max(0.10 * H + z_min, up_z + kick)
        print(f"  Recommended Stage-1 cut Z:  {recommended_cut:+.3f}  "
              f"(= max(z_min + 10%*H = {z_min + 0.10*H:+.3f}, "
              f"floor + {kick:.2f} = {up_z + kick:+.3f}))")
        rec_frac = (recommended_cut - z_min) / H
        print(f"  Recommended Stage-1 fraction of H: {rec_frac:.3f}")


def main():
    for bid in BUILDING_IDS:
        inspect_one(bid)
    print("\n" + "=" * 72)
    print("ALL INSPECTIONS COMPLETE")
    print("=" * 72)


if __name__ == "__main__":
    main()
