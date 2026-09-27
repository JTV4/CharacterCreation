"""
import_character_rework.py
==========================
Convert Desktop CharacterModelRework FBX bases to viewer GLBs.

Sources (Meshy Mixamo T-pose, 65 bones, five-finger hands):
  ~/Desktop/Models/CharacterModelRework/BaseMale.fbx
  ~/Desktop/Models/CharacterModelRework/BaseFamel.fbx   # filename typo

Outputs:
  viewer/public/models/BaseMaleRework.glb
  viewer/public/models/BaseFemaleRework.glb
  rework_previews/{male,female}_{3q,front,side,face}.png

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python import_character_rework.py
"""

from __future__ import annotations

import json
import math
import os
import shutil
import struct
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.expanduser("~/Desktop/Models/CharacterModelRework")
OUT_DIR = os.path.join(ROOT, "viewer/public/models")
DESKTOP = os.path.expanduser("~/Desktop/Models/Characters")
PREVIEW_DIR = os.path.join(ROOT, "rework_previews")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(DESKTOP, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)

JOBS = (
    {
        "src": os.path.join(SRC_DIR, "BaseMale.fbx"),
        "name": "BaseMaleRework",
        "skin": (0.72, 0.54, 0.40),
    },
    {
        "src": os.path.join(SRC_DIR, "BaseFamel.fbx"),
        "name": "BaseFemaleRework",
        "skin": (0.82, 0.62, 0.50),
    },
)

VIEWS = [
    ("3q", Vector((1.15, -1.45, 0.42)).normalized()),
    ("front", Vector((0.04, -1.00, 0.10)).normalized()),
    ("side", Vector((1.00, -0.08, 0.08)).normalized()),
    ("face", Vector((0.15, -1.00, 0.18)).normalized()),
]

V3_GLB = os.path.join(OUT_DIR, "BaseFemaleV3.glb")


def _script_args() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return []


def normalize_bone_name(name: str) -> str:
    if name.startswith("mixamorig:"):
        return name[len("mixamorig:") :]
    if name.startswith("mixamorig"):
        return name[len("mixamorig") :]
    return name


def _read_glb(path: str) -> tuple[dict, bytes]:
    with open(path, "rb") as fh:
        data = fh.read()
    offset = 12
    gltf = None
    bin_bytes = b""
    while offset < len(data):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset : offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            gltf = json.loads(chunk)
        elif chunk_type == 0x004E4942:
            bin_bytes = chunk
    if gltf is None:
        raise ValueError(f"No JSON chunk in {path}")
    return gltf, bin_bytes


def _write_glb(path: str, gltf: dict, bin_bytes: bytes) -> None:
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - (len(json_bytes) % 4)) % 4)
    bin_bytes = bin_bytes + (b"\x00" * ((4 - (len(bin_bytes) % 4)) % 4))
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(json_bytes), 0x4E4F534A))
        fh.write(json_bytes)
        fh.write(struct.pack("<II", len(bin_bytes), 0x004E4942))
        fh.write(bin_bytes)


def copy_v3_node_rotations(rework_path: str) -> None:
    """Copy Female V3 glTF node rotations onto a rework GLB. Leave bind translations/IBMs."""
    v3, _ = _read_glb(V3_GLB)
    dest, dest_bin = _read_glb(rework_path)
    v3_rots = {
        normalize_bone_name(node.get("name", "")): node["rotation"]
        for node in v3.get("nodes", [])
        if "rotation" in node and node.get("name")
    }
    copied = 0
    for node in dest.get("nodes", []):
        key = normalize_bone_name(node.get("name", ""))
        if key not in v3_rots:
            continue
        node["rotation"] = v3_rots[key]
        copied += 1
    _write_glb(rework_path, dest, dest_bin)
    shutil.copy2(rework_path, os.path.join(DESKTOP, os.path.basename(rework_path)))
    print(f"  copied {copied} V3 rest rotations -> {os.path.basename(rework_path)}")


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mesh_world_bbox(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    for v in ev.data.vertices:
        w = ev.matrix_world @ v.co
        mn = Vector((min(mn.x, w.x), min(mn.y, w.y), min(mn.z, w.z)))
        mx = Vector((max(mx.x, w.x), max(mx.y, w.y), max(mx.z, w.z)))
    return mn, mx


def assign_skin(obj: bpy.types.Object, color: tuple[float, float, float]) -> None:
    mat = bpy.data.materials.new(f"{obj.name}_skin")
    mat.use_nodes = True
    mat.use_backface_culling = False
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.58
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True


def fix_mixamo_scale(arm: bpy.types.Object, mesh: bpy.types.Object) -> None:
    """Bring the FBX to ~1.7–1.9 m without breaking skin bind."""
    bpy.context.view_layer.update()
    mn, mx = mesh_world_bbox(mesh)
    height = mx.z - mn.z
    hips = arm.data.bones.get("mixamorig:Hips")
    hips_z = (arm.matrix_world @ hips.head_local).z if hips else 0.0
    print(f"  pre-fix height={height:.4f}m hips_z={hips_z:.4f} arm.scale={tuple(arm.scale)}")

    # Typical Mixamo FBX: armature scale 0.01, mesh already in metres → 1.7 cm tall.
    # Resetting armature scale to 1 keeps bone centimetre rest poses * 1 (wrong).
    # Instead scale the object so the *visual* height is ~1.78 m.
    if height < 0.25:
        target = 1.78
        factor = target / max(height, 1e-6)
        print(f"  scaling armature by {factor:.3f} to reach {target}m")
        arm.scale *= factor
        bpy.context.view_layer.update()
        mn, mx = mesh_world_bbox(mesh)
        print(f"  post-fix height={mx.z - mn.z:.4f}m z=[{mn.z:.3f},{mx.z:.3f}]")


def export_glb(path: str, arm: bpy.types.Object, mesh: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    arm.hide_set(False)
    mesh.hide_set(False)
    arm.select_set(True)
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_materials="EXPORT",
        export_texcoords=True,
        export_normals=True,
        export_skins=True,
        export_all_influences=True,
        export_animations=False,
        export_morph=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )
    print(f"  -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def convert(job: dict) -> str:
    src = job["src"]
    if not os.path.isfile(src):
        raise FileNotFoundError(src)
    reset()
    print(f"\n=== {job['name']} ===")
    bpy.ops.import_scene.fbx(filepath=src)
    bpy.context.view_layer.update()

    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.data.objects if o.type == "MESH")
    mesh.name = job["name"]
    mesh.data.name = job["name"]
    print(f"  mesh={mesh.name} verts={len(mesh.data.vertices)} tris={sum(len(p.vertices) - 2 for p in mesh.data.polygons)}")
    print(f"  bones={len(arm.data.bones)} vgroups={len(mesh.vertex_groups)}")

    # Drop the 2-frame Mixamo bind clip so the viewer stays in rest pose.
    if arm.animation_data:
        arm.animation_data_clear()
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)

    assign_skin(mesh, job["skin"])
    fix_mixamo_scale(arm, mesh)

    dest = os.path.join(OUT_DIR, f"{job['name']}.glb")
    export_glb(dest, arm, mesh)
    shutil.copy2(dest, os.path.join(DESKTOP, f"{job['name']}.glb"))
    return dest


def preview(glb_path: str, prefix: str) -> None:
    reset()
    bpy.ops.import_scene.gltf(filepath=glb_path)
    bpy.context.view_layer.update()

    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 960
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    if hasattr(scene, "eevee"):
        scene.eevee.taa_render_samples = 32

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.15, 0.16, 0.18, 1.0)
    bg.inputs[1].default_value = 1.0
    scene.world = world

    bpy.ops.object.light_add(type="SUN", location=(5, -6, 8))
    key = bpy.context.object
    key.rotation_euler = (math.radians(50), math.radians(16), math.radians(30))
    key.data.energy = 3.4
    bpy.ops.object.light_add(type="SUN", location=(-5, 3, 4))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(55), math.radians(-20), math.radians(-35))
    fill.data.energy = 1.1

    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    gmat = bpy.data.materials.new("Ground")
    gmat.use_nodes = True
    gmat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.20, 0.18, 0.15, 1.0)
    ground.data.materials.append(gmat)

    cam_data = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.name != "Ground"]
    mn, mx = mesh_world_bbox(meshes[0])
    print(f"  preview bbox z=[{mn.z:.3f},{mx.z:.3f}] height={mx.z - mn.z:.3f}")

    for name, direction in VIEWS:
        center = (mn + mx) * 0.5
        if name == "face":
            center = Vector((center.x, center.y, mx.z - 0.16))
            zoom = 0.42
        else:
            zoom = 1.0
        size = (mx - mn).length
        cam.location = center + direction.normalized() * (size * 1.22 * 1.25 * zoom)
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = 50
        path = os.path.join(PREVIEW_DIR, f"{prefix}_{name}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("  wrote", path)


def rebuild_and_align(do_preview: bool = True) -> None:
    paths = []
    for job in JOBS:
        paths.append((convert(job), "male" if "Male" in job["name"] else "female"))
    for glb, _prefix in paths:
        copy_v3_node_rotations(glb)
    if do_preview:
        for glb, prefix in paths:
            preview(glb, prefix)
    print("DONE — rework bases exported with Female V3 rest rotations.")


def main() -> None:
    rebuild_and_align(do_preview=True)


if __name__ == "__main__":
    args = _script_args()
    if "--align-only" in args:
        rebuild_and_align(do_preview=False)
    else:
        main()
