"""
process_sand_sifter.py
======================
Import the Desktop SandSifter, put the origin on the leather wrap
(grip), align handle +Y / sieve +Z in Blender, and export a handheld
GLB for the viewer.

Source (do not overwrite): ~/Desktop/Models/SandSifter/SandSifter.glb
Output: viewer/public/tools/farming/SandSifter.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python process_sand_sifter.py
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.expanduser("~/Desktop/Models/SandSifter/SandSifter.glb")
OUT = os.path.join(ROOT, "viewer/public/tools/farming/SandSifter.glb")


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def select_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def mesh_obj() -> bpy.types.Object:
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh in SandSifter.glb")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    mesh.name = "SandSifter"
    mesh.data.name = "SandSifter"
    select_active(mesh)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return mesh


def grip_centroid(mesh: bpy.types.Object) -> Vector:
    # Leather wrap lives on the thin handle, not the pommel ring (most
    # -X) and not the pan (X > ~0.35). See _preview_sandsifter X-bands.
    pts = [
        v.co.copy()
        for v in mesh.data.vertices
        if -0.13 <= v.co.x <= 0.06
    ]
    if len(pts) < 8:
        pts = [v.co.copy() for v in mesh.data.vertices if v.co.x < 0.1]
    n = max(len(pts), 1)
    return Vector((
        sum(p.x for p in pts) / n,
        sum(p.y for p in pts) / n,
        sum(p.z for p in pts) / n,
    ))


def report(mesh: bpy.types.Object, label: str) -> None:
    verts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    xs, ys, zs = [v.x for v in verts], [v.y for v in verts], [v.z for v in verts]
    print(
        f"  [{label}] X[{min(xs):+.3f},{max(xs):+.3f}] "
        f"Y[{min(ys):+.3f},{max(ys):+.3f}] Z[{min(zs):+.3f},{max(zs):+.3f}] "
        f"size=({max(xs)-min(xs):.3f},{max(ys)-min(ys):.3f},{max(zs)-min(zs):.3f})"
    )


def export_glb(path: str, mesh: bpy.types.Object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    select_active(mesh)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_animations=False,
        export_skins=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )


def main() -> None:
    if not os.path.isfile(SRC):
        raise FileNotFoundError(SRC)
    print("=== Process SandSifter ===")
    print(f"  source: {SRC}")
    reset()
    bpy.ops.import_scene.gltf(filepath=SRC)
    mesh = mesh_obj()
    report(mesh, "imported")

    grip = grip_centroid(mesh)
    print(f"  grip centroid (pre): ({grip.x:+.4f}, {grip.y:+.4f}, {grip.z:+.4f})")
    mesh.location -= grip
    mesh.rotation_mode = "XYZ"
    # Pan is +X after import. Rz(+90) sends +X → +Y so the handle/pan
    # run along +Y and the sieve stays +Z (up).
    mesh.rotation_euler = (0.0, 0.0, math.radians(90.0))
    select_active(mesh)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    report(mesh, "grip origin")

    export_glb(OUT, mesh)
    print(f"  -> {OUT} ({os.path.getsize(OUT) / 1024.0:.1f} KB)")
    print("DONE")


if __name__ == "__main__":
    main()
