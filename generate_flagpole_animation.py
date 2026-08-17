"""
generate_flagpole_animation.py
==============================
10-stage modular assemble for the GrindScape flagpole, matching the
workstation / well / dock drop-in contract:

  1 INIT       — Raw Catfish, Sycamore logs, Iron ore (no flagpole mesh)
  2–10         — plinth → pedestal → cap → socket → pole thirds →
                 finial → flag cloth

Pieces are authored (not Z-bisected) so the pole grows in clean
tapered segments and the cloth arrives as a whole sheet.  The waving
armature stays on GrindScapeFlag.glb (the Complete viewer row); this
modular GLB is static rest-pose geometry for the construction tween.

Outputs:
  viewer/public/buildings/Construction/GrindScapeFlagAnimation_Modular.glb
  viewer/public/buildings/Construction/grindscape_flag_animation_manifest.json
  viewer/public/buildings/Construction/GrindScapeFlag_INIT.glb
  (~/Desktop/Models/Buildings/Construction/ mirrors)

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_flagpole_animation.py
"""

from __future__ import annotations

import json
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import generate_grindscape_flag as gf
import generate_workstation_animation as ws

VIEWER_OUT = os.path.join(ROOT, "viewer/public/buildings/Construction")
DESKTOP_OUT = os.path.expanduser("~/Desktop/Models/Buildings/Construction")
os.makedirs(VIEWER_OUT, exist_ok=True)
os.makedirs(DESKTOP_OUT, exist_ok=True)

OUT_GLB = "GrindScapeFlagAnimation_Modular.glb"
OUT_MANIFEST = "grindscape_flag_animation_manifest.json"
OUT_INIT = "GrindScapeFlag_INIT.glb"

DROP_Z = 2.20
OUTWARD = 0.28
STAGE_ORDER = [
    "foundation",
    "walls_a",
    "walls_b",
    "walls_c",
    "walls_d",
    "gable",
    "framing",
    "eaves",
    "complete",
]

# (key, object name, nx, ny, yaw, scale) — fractions of half-footprint
INIT_PILES = [
    ("sycamore_logs", "pile_sycamore_logs", -0.38, -0.22, 0.05, 0.18),
    ("iron_ore", "pile_iron_ore", 0.40, -0.18, 0.25, 0.18),
    ("raw_catfish", "pile_raw_catfish", 0.0, 0.34, 0.40, 0.30),
]


def bake_world(obj: bpy.types.Object) -> None:
    """Origin at (0,0,0), transforms applied — same rest-pose contract
    as Well / workstation modular pieces."""
    gf.set_origin(obj, (0.0, 0.0, 0.0))
    gf.select_active(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def piece_from(parts: list[bpy.types.Object], name: str, *, smooth: bool) -> bpy.types.Object:
    joined = gf.join_group(parts, name)
    bake_world(joined)
    gf.select_active(joined)
    if smooth:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40.0))
    else:
        bpy.ops.object.shade_flat()
    if joined.data:
        joined.data.name = name
    return joined


def spawn_offset(stagger: int, centroid: Vector) -> list[float]:
    outward = Vector((centroid.x, centroid.y, 0.0))
    if outward.length > 1e-4:
        outward.normalize()
    else:
        outward = Vector((1.0, 0.0, 0.0))
    return [
        round(outward.x * OUTWARD, 4),
        round(outward.y * OUTWARD, 4),
        round(DROP_Z, 4),
    ]


def build_modular_pieces() -> list[tuple[str, str, bpy.types.Object]]:
    gf.composite_flag_albedo(gf.LOGO_PATH, gf.ALBEDO_PATH)
    mats = gf.materials()
    pedestal = gf.build_pedestal(mats)
    # build_pedestal returns [plinth, body, cap, socket]
    plinth, body, cap, socket = pedestal
    pole_secs = gf.build_pole_sections(mats)
    finial_parts = gf.build_finial(mats)
    cloth = gf.build_flag_mesh(mats)

    pieces: list[tuple[str, str, bpy.types.Object]] = [
        ("flag_plinth", "Floor", piece_from([plinth], "flag_plinth", smooth=False)),
        ("flag_body", "Floor", piece_from([body], "flag_body", smooth=False)),
        ("flag_cap", "Wall", piece_from([cap], "flag_cap", smooth=False)),
        ("flag_socket", "Wall", piece_from([socket], "flag_socket", smooth=False)),
        ("flag_pole_low", "Wall", piece_from(pole_secs[0], "flag_pole_low", smooth=True)),
        ("flag_pole_mid", "Wall", piece_from(pole_secs[1], "flag_pole_mid", smooth=True)),
        ("flag_pole_high", "Trim", piece_from(pole_secs[2], "flag_pole_high", smooth=True)),
        ("flag_finial", "Trim", piece_from(finial_parts, "flag_finial", smooth=True)),
        ("flag_cloth", "Roof", piece_from([cloth], "flag_cloth", smooth=True)),
    ]
    return pieces


def write_manifest(pieces: list[tuple[str, str, bpy.types.Object]]) -> dict:
    piece_defs = []
    ordered_ids: list[str] = []
    for stagger, (pid, cat, obj) in enumerate(pieces):
        ordered_ids.append(pid)
        c = Vector((0.0, 0.0, 0.0))
        verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
        if verts:
            c = sum(verts, Vector((0.0, 0.0, 0.0))) / len(verts)
        piece_defs.append(
            {
                "id": pid,
                "category": cat,
                "staggerIndex": stagger,
                "spawnOffset": spawn_offset(stagger, c),
                "spawnYawDeg": round(10.0 * math.sin(stagger * 0.7), 2),
                "durationSec": 0.40,
            }
        )

    cumulative: list[str] = []
    stages: dict[str, list[str]] = {}
    for key, pid in zip(STAGE_ORDER, ordered_ids):
        cumulative.append(pid)
        stages[key] = list(cumulative)
    stages["complete"] = list(ordered_ids)

    return {
        "source": "GrindScapeFlag.glb",
        "structureName": "GrindScape Flag",
        "coordinateSystem": "Z-up",
        "assembleAxis": "Z",
        "pieces": piece_defs,
        "stages": stages,
        "stageOrder": list(STAGE_ORDER),
        "tween": {
            "staggerSec": 0.07,
            "ease": "easeOutCubic",
            "startScale": 0.92,
        },
    }


def export_modular(objs: list[bpy.types.Object], filename: str) -> None:
    for out_dir in (VIEWER_OUT, DESKTOP_OUT):
        path = os.path.join(out_dir, filename)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objs:
            obj.hide_set(False)
            obj.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.export_scene.gltf(
            filepath=path,
            export_format="GLB",
            use_selection=True,
            export_apply=True,
            export_materials="EXPORT",
            export_image_format="AUTO",
            export_texcoords=True,
            export_normals=True,
            export_skins=False,
            export_animations=False,
            export_cameras=False,
            export_lights=False,
        )
        print(f"  -> {path} ({os.path.getsize(path) / 1024.0:.1f} KB)")


def main() -> None:
    print("=== GrindScape Flag modular animation ===")
    gf.clear_scene()
    pieces = build_modular_pieces()
    for pid, cat, obj in pieces:
        gf.report(obj, f"{pid}/{cat}")

    manifest = write_manifest(pieces)
    for out_dir in (VIEWER_OUT, DESKTOP_OUT):
        path = os.path.join(out_dir, OUT_MANIFEST)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
            fh.write("\n")
        print(f"  -> {path}")

    export_modular([p[2] for p in pieces], OUT_GLB)

    half = gf.PLINTH_XY / 2.0
    footprint = ((-half, half), (-half, half))
    print("=== INIT (Raw Catfish, Sycamore logs, Iron ore) ===")
    ws.export_init(footprint, INIT_PILES, OUT_INIT)
    print("DONE")


if __name__ == "__main__":
    main()
