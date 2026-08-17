"""
render_thumbnails.py
====================
Render 64x64 transparent PNG thumbnails for individual armor GLB pieces.

Each piece is loaded standalone, framed to its bounding box from a 3/4-front
angle, lit with a single sun + ambient world to keep textures readable, and
rendered through Eevee with `film_transparent` for a clean alpha cutout
suitable for UI use at small sizes.

Usage:
    /Applications/Blender.app/Contents/MacOS/Blender --background \
        --python render_thumbnails.py -- --pieces=/path/to/pieces.json

The `--pieces=` argument points to a JSON file with a list of:
    [{"glb": "/abs/path/to/piece.glb", "out": "/abs/path/to/thumb.png"}, ...]

This indirection keeps the Blender command-line short when rendering many
pieces in one batch.
"""

import json
import math
import os
import sys

import bpy
from mathutils import Vector


THUMB_SIZE = 64
# 3/4 front view (camera positioned in +X, -Y, +Z octant looking back at the
# mesh centre), tuned to give equal weight to silhouette and front-facing
# detail at 64 px.  Blender world is Z-up, so +Z is "above the mesh".
CAMERA_OFFSET_DIRECTION = Vector((0.55, -0.85, 0.20)).normalized()
# Visual padding around the mesh's screen-space bbox.  1.10 keeps a small
# gutter so silhouette anti-aliasing isn't clipped by the 64×64 frame, but
# isn't so loose that thin / wide pieces (gloves, sleeve sets) shrink to
# pixel dust because their bounding box has a high aspect ratio.
FRAME_MARGIN = 1.10
# Render at 4× resolution (256×256) and downscale at save time so silhouette
# anti-aliasing has more samples to average; the final PNG is still a
# 64×64 RGBA file.
SUPERSAMPLE = 4


def _parse_args():
    """Pick up the JSON manifest path passed after `--`."""
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    pieces_json = None
    for a in args:
        if a.startswith("--pieces="):
            pieces_json = a.split("=", 1)[1]
    if not pieces_json:
        print("ERROR: pass --pieces=/abs/path/manifest.json after `--`")
        sys.exit(2)
    with open(pieces_json) as f:
        return json.load(f)


def _reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _setup_world_and_render():
    """One-time-per-render setup: transparent film, Eevee, neutral world."""
    scene = bpy.context.scene

    scene.render.engine = "BLENDER_EEVEE"
    # Render at SUPERSAMPLE × THUMB_SIZE then let Pillow downscale on save —
    # supersampling gives noticeably cleaner edges than 64×64 native + Eevee
    # TAA, especially on thin geometry like sleeve trim.
    scene.render.resolution_x = THUMB_SIZE * SUPERSAMPLE
    scene.render.resolution_y = THUMB_SIZE * SUPERSAMPLE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    # Anti-aliasing samples — keeps silhouette edges clean without
    # adding meaningful render time per piece.
    scene.eevee.taa_render_samples = 32

    # Neutral 50% grey ambient world so PBR materials don't go pitch-black
    # in shadowed areas.  The transparent film still produces an alpha
    # cutout — world contributes only to lit surface shading, not pixels
    # that miss all geometry.
    world = bpy.data.worlds.new("ThumbWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)
    bg.inputs[1].default_value = 0.6
    scene.world = world


def _add_lights():
    """Three-point-ish lighting with a strong key + soft fill."""
    bpy.ops.object.light_add(type="SUN", location=(2, -3, 3))
    key = bpy.context.object
    key.rotation_euler = (math.radians(45), math.radians(15), math.radians(20))
    key.data.energy = 3.5

    bpy.ops.object.light_add(type="SUN", location=(-3, -1, 2))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(60), math.radians(-20), math.radians(-30))
    fill.data.energy = 1.2


def _world_bbox(objs):
    """AABB of all mesh vertices in world space.

    Iterating actual `.data.vertices` (not `obj.bound_box`) is critical
    here because Mage GLBs are imported under an armature whose
    matrix_world bakes in a 0.01 scale (centimetres-as-metres convention
    used by BaseFemaleV2).  The cached bound_box on the mesh object
    doesn't pick up that armature scale on first import, so framing math
    based on it places the camera kilometres away from a 0.5 cm bbox.
    Walking vertices directly forces a correct world-space evaluation.
    """
    bpy.context.view_layer.update()
    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    for obj in objs:
        if obj.type != "MESH" or obj.data is None or len(obj.data.vertices) == 0:
            continue
        mw = obj.matrix_world
        for v in obj.data.vertices:
            wv = mw @ v.co
            mn = Vector(min(mn[i], wv[i]) for i in range(3))
            mx = Vector(max(mx[i], wv[i]) for i in range(3))
    return mn, mx


def _fit_camera(objs, frame_region=None):
    """Aim a 50 mm camera at the mesh centre and pick a distance that fits
    the *projected* bbox into the 1:1 square frame with FRAME_MARGIN of
    padding.  Returns the camera object.

    Why projected-bbox fitting (not bounding-sphere):
      Bilateral pieces like the bare-hand gloves have two small clusters
      of geometry separated by ≈ 60 cm, so their bounding sphere has a
      huge radius even though each glove is only ≈ 7 cm tall.  A
      sphere-fit camera distance ends up framing mostly empty space and
      the actual hands shrink to pixel dust.  Projecting bbox corners
      onto the camera's right / up axes and fitting the larger of the
      two resulting screen-space half-widths matches the silhouette
      seen by the camera, so wide/thin pieces fill the frame correctly.

    `frame_region` (optional dict) lets callers crop the framing bbox to
    one half of an axis — e.g. {"axis": "x", "keep": "positive"} for
    gloves, where focusing on a single hand makes a far more readable
    64 × 64 thumbnail than trying to fit the wide bilateral pair.
    Vertices outside the kept half are NOT deleted; they just don't
    influence the camera fit (they may still appear in the render if
    the camera FOV happens to see them, which the supersample/Lanczos
    downscale tolerates well).
    """
    mn, mx = _world_bbox(objs)
    if frame_region:
        ax = {"x": 0, "y": 1, "z": 2}[frame_region["axis"]]
        if frame_region["keep"] == "positive":
            mn = Vector(tuple(0.0 if i == ax else mn[i] for i in range(3)))
        elif frame_region["keep"] == "negative":
            mx = Vector(tuple(0.0 if i == ax else mx[i] for i in range(3)))
    centre = (mn + mx) * 0.5
    corners = [Vector((x, y, z))
               for x in (mn.x, mx.x)
               for y in (mn.y, mx.y)
               for z in (mn.z, mx.z)]

    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.lens = 50.0
    cam.data.sensor_fit = "AUTO"
    cam.data.sensor_width = 36.0

    # Build the camera-space basis.  The render frame is 1:1 (square), so
    # the same FOV applies to both axes — we can use a single FOV.
    forward = -CAMERA_OFFSET_DIRECTION  # camera-to-centre direction
    world_up = Vector((0.0, 0.0, 1.0))
    right = forward.cross(world_up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up = right.cross(forward).normalized()

    extents_right = max(abs((c - centre).dot(right)) for c in corners)
    extents_up    = max(abs((c - centre).dot(up))    for c in corners)
    half_extent = max(extents_right, extents_up, 1e-3)

    fov = 2.0 * math.atan((cam.data.sensor_width * 0.5) / cam.data.lens)
    distance = (half_extent * FRAME_MARGIN) / math.tan(fov * 0.5)

    cam.location = centre + CAMERA_OFFSET_DIRECTION * distance

    # Track-to constraint so the camera stays aimed at the mesh centre even
    # if we tweak the offset direction later.
    target = bpy.data.objects.new("ThumbTarget", None)
    target.location = centre
    bpy.context.collection.objects.link(target)
    track = cam.constraints.new(type="TRACK_TO")
    track.target = target
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"

    bpy.context.scene.camera = cam
    return cam


def _render_one(glb_path: str, out_path: str, frame_region=None):
    print(f"\n=== {os.path.basename(glb_path)} → {out_path} ===")
    _reset_scene()
    _setup_world_and_render()
    _add_lights()

    bpy.ops.import_scene.gltf(filepath=glb_path)
    # Filter out non-renderable helpers.  The Mage / Ranged GLBs include a
    # `Icosphere` debug placeholder (~2 m radius) alongside the actual armor
    # mesh; same convention as `weight_meshy_gloves.py`.  Without this skip
    # the camera frames the huge sphere and the armor renders as a few
    # pixels in the corner.
    mesh_objs = [
        o for o in bpy.context.scene.objects
        if o.type == "MESH" and "Icosphere" not in o.name
    ]
    # Hide the Icosphere from the render too, in case its material renders
    # any pixels into the alpha cutout.
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and "Icosphere" in o.name:
            o.hide_render = True
    if not mesh_objs:
        print(f"  WARN: no mesh objects in {glb_path} — skipping")
        return False

    _fit_camera(mesh_objs, frame_region=frame_region)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Blender's bundled Python doesn't ship Pillow, so we render the
    # supersampled file to the FINAL output path and rely on a post-
    # processing pass (system Python + Pillow, in the wrapper script) to
    # downscale these in-place to THUMB_SIZE × THUMB_SIZE.
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

    if os.path.exists(out_path):
        print(f"  OK ({os.path.getsize(out_path)} bytes, supersampled — needs post-resize)")
        return True
    print("  FAIL: render did not produce an output file")
    return False


def main():
    pieces = _parse_args()
    print(f"Rendering {len(pieces)} thumbnail(s)")
    ok = 0
    for p in pieces:
        try:
            if _render_one(p["glb"], p["out"], frame_region=p.get("frame_region")):
                ok += 1
        except Exception as e:
            print(f"  ERROR {p['glb']}: {e}")
    print(f"\nDone: {ok}/{len(pieces)} thumbnails written")


main()
