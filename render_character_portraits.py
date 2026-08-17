"""
render_character_portraits.py
==============================
For each GLB in /tmp/character_glbs/, render a transparent-background
portrait to ~/Desktop/CharacterPortraits/<CleanName>.png.

Design decisions:
- Transparent PNG (RGBA + film_transparent=True) so the portraits can
  drop into any UI background.
- 3/4 hero angle (front-right, slightly above eye-level) — reads
  better as a character portrait than a pure front view.
- Auto-fit camera per character based on the mesh bounding box, so
  height variations, arm-out T-poses, etc. all frame correctly
  without hand-tuning per character.
- Portrait aspect (768 × 1152) — full-body vertical framing.
- 3-point studio lighting: warm key, cool fill, back rim.

Naming:
  "Lyra_u2akko.glb" → "Lyra.png"  (strip the _<hash> suffix that
  Cloudinary adds when uploading).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python /tmp/render_character_portraits.py
"""

import bpy
import glob
import math
import os
from mathutils import Vector

INPUT_DIR  = "/tmp/character_glbs"
OUTPUT_DIR = os.path.expanduser("~/Desktop/CharacterPortraits")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PORTRAIT_W = 768
PORTRAIT_H = 1152
FRAME_MARGIN = 1.15                              # ~7% padding on the tighter axis
CAMERA_DIR = Vector((0.32, -1.00, 0.12))         # front-right 3/4, slight tilt-up


def clean_name(filename: str) -> str:
    """'Lyra_u2akko.glb' → 'Lyra',   'Aurelia_tmbqdy.glb' → 'Aurelia'.

    Strips the '_<hash>' suffix that Cloudinary appends when uploading.
    Cloudinary hashes are 5-10 character alphanumeric strings (e.g.
    'u2akko', 'tmbqdy', 'xypj16') — they may or may not contain
    digits.  We use a length-based heuristic because a digit-only
    check misses all-letter hashes like 'tmbqdy'.  If the name has
    no such suffix, returns the plain stem unchanged.
    """
    stem = os.path.splitext(os.path.basename(filename))[0]
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isalnum() and 4 <= len(parts[1]) <= 10:
        return parts[0]
    return stem


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = PORTRAIT_W
    scene.render.resolution_y = PORTRAIT_H
    scene.render.resolution_percentage = 100
    # Transparent film — the background renders as (0,0,0,0) so the PNG
    # alpha channel is 0 wherever the character isn't.
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.compression = 90
    scene.eevee.taa_render_samples = 64


def add_studio_lights():
    """Classic 3-point light rig scaled for a ~1.8 m character."""
    # Key light — warm, upper front-right
    bpy.ops.object.light_add(type="AREA", location=(1.8, -1.8, 2.4))
    key = bpy.context.object
    key.rotation_euler = (math.radians(55), 0, math.radians(45))
    key.data.energy = 600
    key.data.size = 2.0
    key.data.color = (1.0, 0.98, 0.94)

    # Fill light — cool, opposite side, lower intensity
    bpy.ops.object.light_add(type="AREA", location=(-2.2, -1.2, 1.8))
    fill = bpy.context.object
    fill.rotation_euler = (math.radians(65), 0, math.radians(-45))
    fill.data.energy = 250
    fill.data.size = 2.5
    fill.data.color = (0.90, 0.95, 1.00)

    # Rim light — behind, adds edge separation from any background
    bpy.ops.object.light_add(type="AREA", location=(0.5, 2.5, 2.6))
    rim = bpy.context.object
    rim.rotation_euler = (math.radians(-55), 0, math.radians(180))
    rim.data.energy = 400
    rim.data.size = 2.0
    rim.data.color = (1.0, 1.0, 1.0)


# Blender-primitive names to skip when computing the character bbox.
# These GLBs ship with a stray Icosphere (42 verts, radius 1, centred
# at origin) that would otherwise dominate the AABB and cause the
# camera to frame a 2×2×2 cube around the character instead of the
# character itself — cropping the head off the top of the portrait
# and leaving a huge empty gap below the feet.
PRIMITIVE_NAMES = {"Icosphere", "Cube", "Sphere", "Cylinder",
                   "Plane", "Cone", "Torus"}


def is_character_mesh(obj) -> bool:
    """Filter for meshes that are actually part of the character.

    Rejects Blender default-primitive names (matches "Icosphere",
    "Icosphere.001", etc.) since those are debug artifacts left in
    the export.  Anything with a real character-body name (`char1`,
    `Body`, `Hair`, etc.) passes through.
    """
    stem = obj.name.split(".")[0]      # strip Blender's .001/.002 suffix
    return stem not in PRIMITIVE_NAMES


def world_bbox(objs):
    """AABB of all mesh vertices across `objs` after applying world
    transforms AND armature deformation.

    CRITICAL: these GLBs ship with an `NPCIdle_Armature` action that
    poses the character at import time — the raw `obj.data.vertices`
    are in the REST pose (hip-centred, Z ∈ [-1, +0.7]), but the
    actually-rendered mesh is in the IDLE pose (feet-planted,
    Z ∈ [+0, +1.7]).  If we compute the AABB from rest vertices, the
    camera targets ~0.85 m below the character's real position, so
    the render shows only the boots with the head cropped off.
    Reading verts through the evaluated depsgraph gives us the
    posed positions that Blender will actually render.

    Primitive-named meshes (Icosphere, Cube, etc.) are filtered out
    — they're debug artifacts left in the export."""
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()

    mn = Vector((float("inf"),) * 3)
    mx = Vector((float("-inf"),) * 3)
    kept = 0

    def _accumulate(obj):
        nonlocal mn, mx
        obj_eval = obj.evaluated_get(deps)
        mesh_eval = obj_eval.to_mesh()
        mw = obj_eval.matrix_world
        for v in mesh_eval.vertices:
            wv = mw @ v.co
            mn = Vector(min(mn[i], wv[i]) for i in range(3))
            mx = Vector(max(mx[i], wv[i]) for i in range(3))
        obj_eval.to_mesh_clear()

    for obj in objs:
        if obj.type != "MESH" or obj.data is None:
            continue
        if not is_character_mesh(obj):
            continue
        kept += 1
        _accumulate(obj)
    if kept == 0:
        # Fallback: no character-shaped mesh found — use whatever's
        # present rather than crashing.
        for obj in objs:
            if obj.type != "MESH" or obj.data is None:
                continue
            _accumulate(obj)
    return mn, mx


def fit_camera(objs):
    """Place an ORTHOGRAPHIC camera along CAMERA_DIR and size it so
    every corner of the mesh AABB fits inside the frame with
    FRAME_MARGIN headroom.

    Why ortho instead of perspective:
      Perspective FOV math has to agree with Blender's `sensor_fit`
      / `sensor_width` / `sensor_height` interactions, which behave
      differently for portrait vs landscape and use the fixed
      `sensor_height` default (24 mm) in unexpected code paths.
      Orthographic projection sidesteps all of that — `ortho_scale`
      is the exact world-space horizontal extent captured by the
      frame (Blender-defined), so we just size it directly to fit
      the character.  Bonus: ortho gives distortion-free portraits,
      which is actually preferable for UI character thumbnails.
    """
    mn, mx = world_bbox(objs)
    centre = (mn + mx) * 0.5
    corners = [Vector((x, y, z))
               for x in (mn.x, mx.x)
               for y in (mn.y, mx.y)
               for z in (mn.z, mx.z)]

    bpy.ops.object.camera_add()
    cam = bpy.context.object
    cam.data.type = "ORTHO"
    # Lock sensor_fit to HORIZONTAL so `ortho_scale` deterministically
    # means "horizontal world extent captured by the frame".  With
    # sensor_fit=AUTO, Blender changes the meaning of ortho_scale
    # between portrait and landscape aspect ratios, which broke our
    # vertical/horizontal fit math.
    cam.data.sensor_fit = "HORIZONTAL"

    camera_dir = CAMERA_DIR.normalized()
    forward = -camera_dir                              # camera looks along -camera_dir
    world_up = Vector((0, 0, 1))

    # Build the camera's local basis using the standard "look-at with
    # world-up hint" recipe.  `right` and `up` here are the camera's
    # own axes expressed in world space and are used to project the
    # AABB corners onto the camera's screen plane.
    right = forward.cross(world_up)
    right = right.normalized() if right.length > 1e-6 else Vector((1, 0, 0))
    up = right.cross(forward).normalized()

    extents_right = max(abs((c - centre).dot(right)) for c in corners)
    extents_up    = max(abs((c - centre).dot(up))    for c in corners)

    # With sensor_fit=HORIZONTAL, ortho_scale = horizontal world
    # extent captured by the frame, and vertical extent = ortho_scale
    # * (H/W).  For the character to fit we need:
    #   horizontal: 2 * extents_right      ≤ ortho_scale
    #   vertical:   2 * extents_up * (W/H) ≤ ortho_scale
    aspect = PORTRAIT_W / PORTRAIT_H       # W/H  (0.667 for portrait)
    ortho_scale = max(2.0 * extents_right,
                      2.0 * extents_up * aspect)
    cam.data.ortho_scale = ortho_scale * FRAME_MARGIN

    # Ortho projection has no perspective foreshortening, so the
    # camera's exact distance from the target only matters for
    # clipping.  Push the camera far enough back that the whole
    # character is between the near and far clip planes with room
    # to spare — 10× the character's diagonal is generous.
    diagonal = (mx - mn).length
    distance = max(diagonal * 5.0, 5.0)
    cam.location = centre + camera_dir * distance
    cam.data.clip_start = 0.1
    cam.data.clip_end = distance * 3.0

    # Direct look-at rotation.  `to_track_quat('-Z', 'Y')` gives the
    # quaternion that rotates the default camera orientation
    # (-Z forward, +Y up) so its -Z aligns with `forward`, keeping
    # +Y as vertical as possible.
    look_dir = (centre - cam.location).normalized()
    cam.rotation_euler = look_dir.to_track_quat("-Z", "Y").to_euler()

    bpy.context.scene.camera = cam
    return cam


def render_one(glb_path: str) -> tuple[str, int] | None:
    name = clean_name(glb_path)
    out_path = os.path.join(OUTPUT_DIR, f"{name}.png")

    reset_scene()
    setup_render()
    add_studio_lights()

    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    new_meshes = [o for o in bpy.context.scene.objects
                  if o not in before and o.type == "MESH"]
    if not new_meshes:
        print(f"  SKIP {name}: no meshes found in GLB")
        return None

    fit_camera(new_meshes)
    bpy.context.scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)

    size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
    return name, size


def main():
    glbs = sorted(glob.glob(os.path.join(INPUT_DIR, "*.glb")))
    print(f"Rendering {len(glbs)} portraits → {OUTPUT_DIR}")
    print(f"Portrait size: {PORTRAIT_W}×{PORTRAIT_H}  (transparent PNG, 85 mm 3/4 view)")
    print()

    results = []
    for glb in glbs:
        r = render_one(glb)
        if r:
            name, size = r
            print(f"  OK  {name:<10}  {size:>8} bytes")
            results.append(r)

    print()
    print(f"── Done: {len(results)}/{len(glbs)} portraits written ──")


if __name__ == "__main__":
    main()
