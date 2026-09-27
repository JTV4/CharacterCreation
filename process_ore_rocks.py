"""
process_ore_rocks.py
====================
Import GrindScape world ore rocks and emit viewer copies:

  Full      — original GLB (ore spikes visible = has ore)
  Depleted  — spikes flattened into rock-textured caps (holes stay plugged)

The rock body already has sockets; ore primitives fill them. Deleting those
faces left gaping holes. Depleted keeps the ore triangles, projects spike
tips onto the socket plane, welds duplicated socket-rim verts, and fills
leftover small loops — never the open rock underside.

Sources:
  GrindScape/client/public/rocks/{IronOre,Coal,GoldOre,TitaniumOre,TungstenOre,LuminousOre}.glb

Outputs:
  viewer/public/rocks/<Name>.glb
  viewer/public/rocks/<Name>_Depleted.glb
  ~/Desktop/Models/Rocks/<Name>.glb
  ~/Desktop/Models/Rocks/<Name>_Depleted.glb

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python process_ore_rocks.py
"""

from __future__ import annotations

import os
import shutil

import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree


ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = "/Users/stephenvillavaso/Documents/GitHub/GrindScape/client/public/rocks"
VIEWER_DIR = os.path.join(ROOT, "viewer/public/rocks")
DESKTOP_DIR = os.path.expanduser("~/Desktop/Models/Rocks")

ROCKS = [
    "IronOre.glb",
    "Coal.glb",
    "GoldOre.glb",
    "TitaniumOre.glb",
    "TungstenOre.glb",
    "LuminousOre.glb",
]


def is_ore_material(name: str) -> bool:
    n = name.lower()
    if "rock" in n:
        return False
    return any(key in n for key in ("ore", "gold", "titanium", "tungsten", "luminous"))


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def pack_images() -> None:
    for img in bpy.data.images:
        if img.packed_file is None and img.filepath:
            try:
                img.pack()
            except Exception as exc:
                print(f"  warn: could not pack {img.name}: {exc}")


def _mean(vecs: list[Vector]) -> Vector:
    n = max(len(vecs), 1)
    acc = Vector((0.0, 0.0, 0.0))
    for v in vecs:
        acc += v
    return acc / n


def _connected_face_groups(faces: list) -> list[list]:
    remaining = set(faces)
    groups: list[list] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        group = [start]
        seen = {start}
        while stack:
            face = stack.pop()
            for vert in face.verts:
                for other in vert.link_faces:
                    if other in remaining and other not in seen:
                        remaining.discard(other)
                        seen.add(other)
                        group.append(other)
                        stack.append(other)
        groups.append(group)
    return groups


def _project_verts_to_plane(verts, center: Vector, normal: Vector) -> None:
    if normal.length < 1e-8:
        return
    n = normal.normalized()
    for v in verts:
        v.co = v.co - n * (v.co - center).dot(n)


def _ore_rock_gap(bm, ore_slots: set[int]) -> float | None:
    ore_verts = {v for f in bm.faces if f.material_index in ore_slots for v in f.verts}
    rock_verts = {v for f in bm.faces if f.material_index not in ore_slots for v in f.verts}
    ore_only = list(ore_verts - rock_verts)
    rock_only = list(rock_verts - ore_verts)
    if not ore_only or not rock_only:
        return 0.0 if (ore_verts & rock_verts) else None
    kd = KDTree(len(rock_only))
    for i, v in enumerate(rock_only):
        kd.insert(v.co, i)
    kd.balance()
    best = 1e9
    for v in ore_only:
        _co, _idx, dist = kd.find(v.co)
        if dist < best:
            best = dist
    return best


def _boundary_loops(bm) -> list[list]:
    boundary = [e for e in bm.edges if len(e.link_faces) == 1]
    used: set = set()
    loops: list[list] = []
    for start in boundary:
        if start in used:
            continue
        loop = []
        edge = start
        vert = edge.verts[0]
        while edge not in used:
            used.add(edge)
            loop.append(edge)
            vert = edge.other_vert(vert)
            nxt = None
            for cand in vert.link_edges:
                if cand is not edge and len(cand.link_faces) == 1 and cand not in used:
                    nxt = cand
                    break
            if nxt is None:
                break
            edge = nxt
        if loop:
            loops.append(loop)
    return loops


def _fill_all_but_longest_loop(bm, material_index: int) -> int:
    loops = _boundary_loops(bm)
    if len(loops) <= 1:
        return 0
    longest = max(range(len(loops)), key=lambda i: len(loops[i]))
    faces_before = len(bm.faces)
    for i, loop in enumerate(loops):
        if i == longest:
            continue
        bmesh.ops.holes_fill(bm, edges=loop, sides=0)
    for face in bm.faces:
        if face.material_index < 0:
            face.material_index = material_index
    return len(bm.faces) - faces_before


def _object_center(obj: bpy.types.Object) -> Vector:
    if not obj.data.vertices:
        return obj.matrix_world.translation.copy()
    acc = Vector((0.0, 0.0, 0.0))
    for v in obj.data.vertices:
        acc += obj.matrix_world @ v.co
    return acc / len(obj.data.vertices)


def join_ore_only_meshes() -> int:
    """glTF splits multi-material meshes; Luminous ships ore as separate objects."""
    ore_objs = []
    rock_objs = []
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.data is None:
            continue
        if obj.name.lower().startswith("base") or obj.name.lower().startswith("ico"):
            continue
        mats = [s for s in obj.data.materials if s is not None]
        if mats and all(is_ore_material(s.name) for s in mats):
            ore_objs.append(obj)
        else:
            rock_objs.append(obj)
    joined = 0
    for ore in list(ore_objs):
        if ore.name not in bpy.data.objects:
            continue
        if not rock_objs:
            break
        ore_c = _object_center(ore)
        target = min(rock_objs, key=lambda r: (_object_center(r) - ore_c).length)
        bpy.ops.object.select_all(action="DESELECT")
        target.select_set(True)
        ore.select_set(True)
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.join()
        joined += 1
    return joined


def _flatten_ore_on_mesh(obj: bpy.types.Object, rock_index: int, ore_slots: set[int]) -> int:
    """Weld socket rims, flatten spike interiors, fill remaining small holes."""
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    gap_before = _ore_rock_gap(bm, ore_slots)

    weld_dist = 0.002
    if gap_before is not None and 0 < gap_before < 0.08:
        weld_dist = max(0.002, gap_before * 2.0 + 1e-5)

    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=weld_dist)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    ore_faces = [f for f in bm.faces if f.material_index in ore_slots]
    rock_faces = [f for f in bm.faces if f.material_index not in ore_slots]
    if not ore_faces:
        bm.free()
        return 0

    ore_face_set = set(ore_faces)
    flattened = 0
    for group in _connected_face_groups(ore_faces):
        verts = {v for f in group for v in f.verts}
        rock_verts = {v for f in rock_faces for v in f.verts}
        boundary = verts & rock_verts
        interior = verts - rock_verts
        if not interior:
            continue
        if boundary:
            center = _mean([v.co.copy() for v in boundary])
            normal = Vector((0.0, 0.0, 0.0))
            for v in boundary:
                for f in v.link_faces:
                    if f not in ore_face_set:
                        normal += f.normal
            if normal.length < 1e-8:
                normal = Vector((0.0, 0.0, 1.0))
            _project_verts_to_plane(interior, center, normal)
        else:
            coords = [v.co.copy() for v in verts]
            center = _mean(coords)
            acc = Vector((0.0, 0.0, 0.0))
            for c in coords:
                d = c - center
                acc += Vector((abs(d.x), abs(d.y), abs(d.z)))
            axis = Vector((1.0, 0.0, 0.0))
            if acc.y >= acc.x and acc.y >= acc.z:
                axis = Vector((0.0, 1.0, 0.0))
            elif acc.z >= acc.x and acc.z >= acc.y:
                axis = Vector((0.0, 0.0, 1.0))
            projs = [(v, (v.co - center).dot(axis)) for v in verts]
            projs.sort(key=lambda item: item[1])
            base_n = max(3, len(projs) // 4)
            base = [item[0] for item in projs[:base_n]]
            base_center = _mean([v.co.copy() for v in base])
            _project_verts_to_plane(list(interior or verts), base_center, axis)
        flattened += len(interior)

    uv_lay = bm.loops.layers.uv.active
    rock_face_set = {f for f in bm.faces if f.material_index not in ore_slots}
    for face in list(bm.faces):
        if face.material_index not in ore_slots:
            continue
        if uv_lay is not None:
            for loop in face.loops:
                for other in loop.vert.link_loops:
                    if other.face in rock_face_set:
                        loop[uv_lay].uv = other[uv_lay].uv.copy()
                        break
        face.material_index = rock_index

    filled_n = _fill_all_but_longest_loop(bm, rock_index)

    keep_indices = [
        i
        for i, slot in enumerate(mesh.materials)
        if slot is not None and i not in ore_slots
    ]
    if not keep_indices:
        keep_indices = [rock_index]
    remap = {old: new for new, old in enumerate(keep_indices)}
    for face in bm.faces:
        face.material_index = remap.get(face.material_index, 0)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    keep = [mesh.materials[i] for i in keep_indices if i < len(mesh.materials)]
    mesh.materials.clear()
    for slot in keep:
        mesh.materials.append(slot)
    print(f"    weld dist={weld_dist:.4f} fill={filled_n}")
    return flattened


def flatten_spikes() -> int:
    """Keep socket-plugging ore triangles; flatten crystals into rock caps."""
    joined = join_ore_only_meshes()
    print(f"  joined {joined} ore-only meshes into rock bodies")

    rock_mat = None
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.data is None:
            continue
        for slot in obj.data.materials:
            if slot is not None and not is_ore_material(slot.name):
                rock_mat = slot
                break
        if rock_mat:
            break

    flattened = 0
    for obj in list(bpy.data.objects):
        if obj.type != "MESH" or obj.data is None:
            continue
        if obj.name.lower().startswith("ico"):
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        mesh = obj.data
        ore_slots = {
            i
            for i, slot in enumerate(mesh.materials)
            if slot is not None and is_ore_material(slot.name)
        }
        if not ore_slots:
            continue
        rock_index = next(
            (
                i
                for i, slot in enumerate(mesh.materials)
                if slot is not None and not is_ore_material(slot.name)
            ),
            None,
        )
        if rock_index is None:
            if rock_mat is None:
                continue
            mesh.materials.append(rock_mat)
            rock_index = len(mesh.materials) - 1
        n = _flatten_ore_on_mesh(obj, rock_index, ore_slots)
        flattened += n
        print(f"  flatten spikes on {obj.name}: {n} interior verts projected")
    return flattened


def export_glb(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_materials="EXPORT",
        export_image_format="AUTO",
        export_texcoords=True,
        export_normals=True,
    )


def copy_full(src_name: str) -> None:
    src = os.path.join(SRC_DIR, src_name)
    for dest_dir in (VIEWER_DIR, DESKTOP_DIR):
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, src_name)
        shutil.copy2(src, dest)
        print(f"  full -> {dest} ({os.path.getsize(dest) / 1024:.1f} KB)")


def write_depleted(src_name: str) -> None:
    src = os.path.join(SRC_DIR, src_name)
    stem, _ = os.path.splitext(src_name)
    print(f"\n=== {stem} depleted ===")
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=src)
    bpy.context.view_layer.update()
    pack_images()
    for obj in list(bpy.data.objects):
        if obj.type != "MESH" or obj.name.lower().startswith("ico"):
            bpy.data.objects.remove(obj, do_unlink=True)
    n = flatten_spikes()
    leftover = [o.name for o in bpy.data.objects if o.type == "MESH"]
    print(f"  flattened {n} spike verts; kept {leftover}")
    if not leftover:
        raise RuntimeError(f"{src_name}: depleting spikes deleted every mesh")

    out_name = f"{stem}_Depleted.glb"
    for dest_dir in (VIEWER_DIR, DESKTOP_DIR):
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, out_name)
        export_glb(path)
        print(f"  depleted -> {path} ({os.path.getsize(path) / 1024:.1f} KB)")


def main() -> None:
    print(f"Source: {SRC_DIR}")
    print(f"Viewer: {VIEWER_DIR}")
    for name in ROCKS:
        src = os.path.join(SRC_DIR, name)
        if not os.path.isfile(src):
            raise FileNotFoundError(src)
        print(f"\n=== {name} full ===")
        copy_full(name)
        write_depleted(name)
    print("\nDONE — full + depleted ore rocks exported.")


if __name__ == "__main__":
    main()
