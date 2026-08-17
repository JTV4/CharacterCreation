"""
generate_female_face_accessories.py
===================================
Builds removable stylized face accessories for BaseFemaleV2:

  Eyebrows  — dark / soft / arched
  Eyelashes — natural / long
  Nose      — button / straight / soft
  Mouth     — neutral / soft smile / full lips
  Ears      — round / pointed

Geometry is authored as game-ready organic meshes (not primitive blobs),
skinned 100% to mixamorig:Head on the +local-Z face side (viewer remap).

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python generate_female_face_accessories.py
"""

from __future__ import annotations

import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
BODY_GLB = os.path.join(ROOT, "viewer/public/models/BaseFemaleV2.glb")
FACE_ROOT = os.path.join(ROOT, "viewer/public/equipment/Female")

# Bind-space landmarks (cm). +Z = viewer face side (same convention as eyes).
# Eyes sit at (±3.45, 164.2, 13.6).
BROW_L = Vector((-3.35, 167.55, 13.05))
BROW_R = Vector((3.35, 167.55, 13.05))
LASH_L = Vector((-3.45, 164.55, 13.85))
LASH_R = Vector((3.45, 164.55, 13.85))
NOSE_ROOT = Vector((0.0, 165.4, 12.6))   # between brows / bridge top
NOSE_TIP = Vector((0.0, 159.6, 14.35))
MOUTH_C = Vector((0.0, 156.05, 12.55))
EAR_L = Vector((-8.85, 163.6, 4.8))
EAR_R = Vector((8.85, 163.6, 4.8))


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_armature():
    bpy.ops.import_scene.gltf(filepath=BODY_GLB)
    bpy.context.view_layer.update()
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    for o in list(bpy.data.objects):
        if o.type == "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    head = next(
        b.name for b in arm.data.bones
        if b.name in ("mixamorig:Head", "mixamorigHead", "Head", "head")
    )
    return arm, head


def skin_to_head(mesh_obj, arm, head_name):
    mesh_obj.vertex_groups.clear()
    idxs = list(range(len(mesh_obj.data.vertices)))
    for bone_name in [b.name for b in arm.data.bones]:
        vg = mesh_obj.vertex_groups.new(name=bone_name)
        vg.add(idxs, 1.0 if bone_name == head_name else 0.0, "REPLACE")
    mesh_obj.parent = arm
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm


def export_glb(meshes, arm, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_yup=True,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
        export_image_format="AUTO",
    )
    print(f"  → {path}")


def save_rgba(path, img: np.ndarray):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    name = os.path.basename(path)
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    h, w = img.shape[:2]
    bl_img = bpy.data.images.new(name, width=w, height=h, alpha=True)
    bl_img.pixels = img[::-1].reshape(-1).tolist()
    bl_img.filepath_raw = path
    bl_img.file_format = "PNG"
    bl_img.save()
    return path


def make_skin_tex(path, rgb, size=256):
    """Soft skin with subtle pore/variation noise."""
    yy, xx = np.mgrid[0:size, 0:size]
    u = (xx + 0.5) / size
    v = (yy + 0.5) / size
    rng = np.random.default_rng(hash(path) % (2**32))
    n = rng.random((size, size)) * 0.06 - 0.03
    warm = 0.04 * np.sin(u * 18) * np.cos(v * 14)
    base = np.array(rgb, dtype=np.float32)
    img = np.zeros((size, size, 4), dtype=np.float32)
    img[..., 0] = np.clip(base[0] + n + warm, 0, 1)
    img[..., 1] = np.clip(base[1] + n * 0.8, 0, 1)
    img[..., 2] = np.clip(base[2] + n * 0.6 - warm * 0.3, 0, 1)
    img[..., 3] = 1.0
    return save_rgba(path, img)


def make_brow_tex(path, rgb, size=256):
    """Hair-strand brow texture (dark fibers on translucent-ish base → opaque)."""
    yy, xx = np.mgrid[0:size, 0:size]
    u = (xx + 0.5) / size
    v = (yy + 0.5) / size
    rng = np.random.default_rng(abs(hash(os.path.basename(path))) % (2**32))
    strands = np.zeros((size, size), dtype=np.float32)
    for _ in range(90):
        x0 = rng.uniform(0.02, 0.98)
        y0 = rng.uniform(0.15, 0.85)
        ang = rng.uniform(-0.35, 0.55)
        length = rng.uniform(0.18, 0.55)
        thick = rng.uniform(0.008, 0.018)
        for s in np.linspace(0, 1, 40):
            x = x0 + s * length * math.cos(ang)
            y = y0 + s * length * math.sin(ang) * 0.35
            if 0 <= x < 1 and 0 <= y < 1:
                ix = int(x * (size - 1))
                iy = int(y * (size - 1))
                r = max(1, int(thick * size))
                strands[
                    max(0, iy - r): min(size, iy + r + 1),
                    max(0, ix - r): min(size, ix + r + 1),
                ] = np.maximum(
                    strands[
                        max(0, iy - r): min(size, iy + r + 1),
                        max(0, ix - r): min(size, ix + r + 1),
                    ],
                    0.55 + 0.45 * (1 - s),
                )
    # Soft edge falloff along V (ribbon height)
    edge = np.clip(1.0 - abs(v - 0.5) * 2.4, 0, 1) ** 1.4
    edge *= np.clip(1.0 - abs(u - 0.5) * 1.85, 0.2, 1)
    dens = np.clip(strands * edge + edge * 0.35, 0, 1)
    dark = np.array([rgb[0] * 0.55, rgb[1] * 0.55, rgb[2] * 0.55], dtype=np.float32)
    base = np.array(rgb, dtype=np.float32)
    img = np.zeros((size, size, 4), dtype=np.float32)
    img[..., :3] = base[None, None, :] * dens[..., None] + dark[None, None, :] * (1 - dens[..., None]) * 0.4
    # Keep fully opaque so game materials don't need alpha clip
    img[..., 3] = 1.0
    # Darken where sparse so flat ribbon still reads as brow
    img[..., :3] *= (0.55 + 0.45 * dens[..., None])
    return save_rgba(path, img)


def make_lash_tex(path, rgb, size=128):
    img = np.zeros((size, size, 4), dtype=np.float32)
    base = np.array(rgb, dtype=np.float32)
    # Gradient tip lighter → base darker along V
    yy = np.linspace(0, 1, size)[:, None]
    img[..., :3] = base * (0.55 + 0.45 * (1 - yy))
    img[..., 3] = 1.0
    return save_rgba(path, img)


def make_lip_tex(path, lip_rgb, size=256):
    yy, xx = np.mgrid[0:size, 0:size]
    u = (xx + 0.5) / size * 2 - 1
    v = (yy + 0.5) / size * 2 - 1
    # Upper / lower lip regions
    upper = np.exp(-((v - 0.28) ** 2) / (2 * 0.18**2)) * np.exp(-(u**2) / (2 * 0.72**2))
    # Cupid's bow dip
    bow = np.exp(-((u) ** 2) / (2 * 0.12**2)) * 0.25
    upper = np.clip(upper - bow * (v > 0), 0, 1)
    lower = np.exp(-((v + 0.22) ** 2) / (2 * 0.22**2)) * np.exp(-(u**2) / (2 * 0.78**2))
    seam = np.exp(-(v**2) / (2 * 0.035**2)) * np.exp(-(u**2) / (2 * 0.85**2))
    mask = np.clip(np.maximum(upper, lower), 0, 1)
    base = np.array(lip_rgb, dtype=np.float32)
    highlight = np.clip(base * 1.25 + 0.08, 0, 1)
    dark = base * np.array([0.55, 0.4, 0.45], dtype=np.float32)
    gloss = np.exp(-((v - 0.15) ** 2) / (2 * 0.06**2)) * np.exp(-(u**2) / (2 * 0.5**2)) * 0.35
    col = (
        base[None, None, :] * mask[..., None]
        + dark[None, None, :] * seam[..., None] * 0.7
        + highlight[None, None, :] * gloss[..., None]
    )
    # Composite over skin-ish fill so opaque
    skin = np.array([0.88, 0.68, 0.60], dtype=np.float32)
    a = np.clip(mask * 1.6, 0, 1)
    out = np.zeros((size, size, 4), dtype=np.float32)
    out[..., :3] = col * a[..., None] + skin[None, None, :] * (1 - a[..., None])
    out[..., 3] = 1.0
    return save_rgba(path, out)


def apply_material(obj, tex_path, roughness=0.55, name="FaceMat", specular=0.2):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(tex_path)
    links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = roughness
    if "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = specular
    elif "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = specular
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def mesh_from_bmesh(name, bm) -> bpy.types.Object:
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True
    me = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return obj


def join_objects(objs, name):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    result = objs[0]
    result.name = name
    result.data.name = name
    return result


def finish_mesh(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_smooth()
    # Mild auto-smooth feel via custom normals not needed; ensure no sharp edges
    for p in obj.data.polygons:
        p.use_smooth = True


# ── Geometry helpers ──────────────────────────────────────────────────────────
def _lerp(a, b, t):
    return a + (b - a) * t


def _smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ── Eyebrows ──────────────────────────────────────────────────────────────────
def make_brow(name, center, sign, arch=0.55, thickness=0.38, taper=0.55, length=2.9):
    """
    Thick tapered brow ribbon with volume — follows a natural arch:
    low inner head, peak ~60%, tapering outer tip.
    """
    bm = bmesh.new()
    segs = 14
    rows = 4  # across brow height
    depth = 3  # front/back thickness rows

    # Build a grid: u along brow, v across height, w depth
    grid = [[[None for _ in range(depth)] for _ in range(rows)] for _ in range(segs + 1)]

    for i in range(segs + 1):
        t = i / segs
        # Inner (t=0) near glabella, outer (t=1) toward temple
        # Natural brow: slight inward start, then out
        along = 0.15 + t * length
        x = center.x + sign * along

        # Arch curve: rises then falls; peak near 0.55–0.65
        arch_y = arch * math.sin(math.pi * _smoothstep(t) ** 0.85)
        # Outer tip drops a bit
        tip_drop = 0.35 * (t ** 2.2)
        # Inner starts slightly lower
        inner_drop = 0.18 * ((1 - t) ** 2)
        y_mid = center.y + arch_y - tip_drop - inner_drop

        # Follow face curve slightly: outer Z pulls back a touch
        z_mid = center.z - 0.15 * t + 0.08 * math.sin(t * math.pi)

        # Height taper + thickness taper toward outer tip
        h = thickness * (1.0 - taper * t) * (0.85 + 0.15 * math.sin(t * math.pi))
        d = 0.28 * (1.0 - 0.45 * t)

        for j in range(rows):
            v = j / (rows - 1)
            # Slight upward bias on outer half (tail lifts)
            y = y_mid + (v - 0.5) * h + 0.08 * t * (v - 0.5)
            for k in range(depth):
                w = k / (depth - 1)
                z = z_mid + (w - 0.15) * d
                # Round the cross-section a bit
                y_round = y + 0.04 * math.sin(w * math.pi) * math.sin(v * math.pi)
                grid[i][j][k] = bm.verts.new((x, y_round, z))

    for i in range(segs):
        for j in range(rows - 1):
            for k in range(depth - 1):
                # two quads for the prism cell — front-facing primarily
                a = grid[i][j][k]
                b = grid[i + 1][j][k]
                c = grid[i + 1][j + 1][k]
                d = grid[i][j + 1][k]
                try:
                    bm.faces.new([a, b, c, d])
                except ValueError:
                    pass
                a2 = grid[i][j][k + 1]
                b2 = grid[i + 1][j][k + 1]
                c2 = grid[i + 1][j + 1][k + 1]
                d2 = grid[i][j + 1][k + 1]
                try:
                    bm.faces.new([a2, d2, c2, b2])
                except ValueError:
                    pass
        # Caps along height edges (top/bottom strips in depth)
        for k in range(depth - 1):
            for j_edge, j in ((0, 0), (1, rows - 1)):
                a = grid[i][j][k]
                b = grid[i + 1][j][k]
                c = grid[i + 1][j][k + 1]
                d = grid[i][j][k + 1]
                order = [a, b, c, d] if j_edge == 0 else [a, d, c, b]
                try:
                    bm.faces.new(order)
                except ValueError:
                    pass

    # End caps
    for i_end in (0, segs):
        for j in range(rows - 1):
            for k in range(depth - 1):
                a = grid[i_end][j][k]
                b = grid[i_end][j + 1][k]
                c = grid[i_end][j + 1][k + 1]
                d = grid[i_end][j][k + 1]
                order = [a, b, c, d] if i_end == 0 else [a, d, c, b]
                try:
                    bm.faces.new(order)
                except ValueError:
                    pass

    return mesh_from_bmesh(name, bm)


# ── Eyelashes ─────────────────────────────────────────────────────────────────
def make_lashes(name, center, sign, count=11, length=1.15, curl=0.55):
    """
    Individual curved tapered lash strands along the upper eyelid arc.
    Each lash is a thin triangular prism that curls up and out.
    """
    bm = bmesh.new()
    # Lid arc roughly matching eye width (~2.6 cm)
    half_w = 1.35

    for i in range(count):
        t = i / max(count - 1, 1)
        # Density heavier in center-outer
        lid_x = center.x + sign * (-half_w + 2 * half_w * t)
        # Lid arcs slightly: higher at outer third
        lid_y = center.y + 0.12 * math.sin(t * math.pi) - 0.05 * abs(t - 0.5)
        lid_z = center.z + 0.08 * math.sin(t * math.pi)

        # Curl direction: up (+Y) and slightly forward (+Z), with outward fan
        fan = (t - 0.5) * 0.9  # radians-ish lateral
        lash_len = length * (0.75 + 0.35 * math.sin(t * math.pi))
        # Outer lashes longer for "long" styles already via length param
        if t < 0.15 or t > 0.85:
            lash_len *= 0.72

        segs = 5
        prev_ring = None
        for s in range(segs + 1):
            u = s / segs
            # Ease curl: more bend toward tip
            bend = (u ** 1.35) * curl
            # Lateral outward
            lat = sign * fan * u * 0.55
            px = lid_x + lat
            py = lid_y + lash_len * u * 0.55 + bend * lash_len * 0.85
            pz = lid_z + lash_len * u * 0.25 + bend * 0.2

            # Taper width
            w = 0.06 * (1.0 - u * 0.92)
            d = 0.04 * (1.0 - u * 0.9)
            ring = [
                bm.verts.new((px - w, py, pz)),
                bm.verts.new((px + w, py, pz)),
                bm.verts.new((px, py, pz + d)),
            ]
            if prev_ring is not None:
                for a, b in ((0, 1), (1, 2), (2, 0)):
                    try:
                        bm.faces.new([prev_ring[a], prev_ring[b], ring[b], ring[a]])
                    except ValueError:
                        pass
            prev_ring = ring
        # Tip close
        tip = bm.verts.new((
            lid_x + sign * fan * 0.6,
            lid_y + lash_len * 0.55 + curl * lash_len * 0.95,
            lid_z + lash_len * 0.28 + curl * 0.25,
        ))
        try:
            bm.faces.new([prev_ring[0], prev_ring[1], tip])
            bm.faces.new([prev_ring[1], prev_ring[2], tip])
            bm.faces.new([prev_ring[2], prev_ring[0], tip])
        except ValueError:
            pass

    return mesh_from_bmesh(name, bm)


# ── Nose ──────────────────────────────────────────────────────────────────────
def make_nose(name, style="button"):
    """
    Organic stylized nose: bridge loft → tip bulb → alar wings + nostril caves.
    Styles vary bridge length, tip roundness, and width.
    """
    bm = bmesh.new()

    if style == "button":
        bridge_w, tip_r, length, tip_lift, wing_w = 0.55, 0.95, 5.4, 0.15, 1.15
    elif style == "straight":
        bridge_w, tip_r, length, tip_lift, wing_w = 0.48, 0.78, 6.0, 0.05, 1.05
    else:  # soft
        bridge_w, tip_r, length, tip_lift, wing_w = 0.62, 1.05, 5.5, 0.22, 1.25

    root = NOSE_ROOT
    tip = Vector((NOSE_TIP.x, root.y - length, NOSE_TIP.z + tip_lift * 0.3))
    # Blend tip toward landmark
    tip = Vector((0.0, _lerp(root.y, NOSE_TIP.y, 0.92), _lerp(root.z, NOSE_TIP.z, 0.95)))

    rings = 10
    segs = 12  # around cross-section (half used for front; full tube-ish)
    ring_verts = []

    for i in range(rings):
        t = i / (rings - 1)
        # Position along bridge → tip
        cy = _lerp(root.y, tip.y, t)
        # Bridge projects forward more toward tip
        cz = _lerp(root.z, tip.z, _smoothstep(t) ** 0.9)
        cx = 0.0

        # Cross-section radii
        # Narrow bridge mid, wider at tip
        rw = _lerp(bridge_w, tip_r, t ** 1.1)
        # Vertical squash of section
        rh = _lerp(0.55, tip_r * 0.95, t)
        # Flatten back against face (less -Z depth on back of nose)
        back = 0.35 + 0.25 * (1 - t)

        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            # Bias cross-section forward (+Z)
            # Use elliptical section with flattened back
            ox = math.cos(a) * rw
            # Front hemisphere fuller
            if math.sin(a) >= 0:  # +Z front in our mapping? wait:
                # We'll use: local section X = left/right, Y unused in section,
                # section angle: 0 = +X, pi/2 = +Z (front)
                pass
            # Remap: angle 0 at +Z (front), going around
            ang = 2 * math.pi * j / segs
            fx = math.sin(ang) * rw
            fz = math.cos(ang)
            if fz < 0:
                fz *= back  # flatten toward face
            else:
                fz *= 1.0
            fz *= rh
            # Slight tip bulb on last rings
            bulb = 1.0 + 0.18 * max(0, t - 0.7) / 0.3
            ring.append(bm.verts.new((cx + fx * bulb, cy, cz + fz * bulb)))
        ring_verts.append(ring)

    for i in range(rings - 1):
        for j in range(segs):
            j2 = (j + 1) % segs
            try:
                bm.faces.new([
                    ring_verts[i][j],
                    ring_verts[i][j2],
                    ring_verts[i + 1][j2],
                    ring_verts[i + 1][j],
                ])
            except ValueError:
                pass

    # Cap tip
    tip_v = bm.verts.new((tip.x, tip.y - tip_r * 0.25, tip.z + tip_r * 0.15))
    last = ring_verts[-1]
    for j in range(segs):
        j2 = (j + 1) % segs
        try:
            bm.faces.new([last[j], last[j2], tip_v])
        except ValueError:
            pass

    # Alar wings (nostril flares) — two soft lobes under tip
    for side in (-1, 1):
        wc = Vector((
            side * wing_w * 0.55,
            tip.y + 0.15,
            tip.z - 0.15,
        ))
        wr = wing_w * 0.42
        # Small icosphere-like via UV sphere verts
        w_segs, w_rings = 8, 5
        wing = []
        for ri in range(w_rings + 1):
            v = ri / w_rings
            phi = math.pi * v
            row = []
            for si in range(w_segs):
                th = 2 * math.pi * si / w_segs
                # Flattened wing: wider X, shorter Y, forward Z
                x = wc.x + math.sin(phi) * math.cos(th) * wr * 1.1
                y = wc.y + math.cos(phi) * wr * 0.55
                z = wc.z + math.sin(phi) * math.sin(th) * wr * 0.7 + wr * 0.25
                row.append(bm.verts.new((x, y, z)))
            wing.append(row)
        for ri in range(w_rings):
            for si in range(w_segs):
                s2 = (si + 1) % w_segs
                try:
                    bm.faces.new([wing[ri][si], wing[ri][s2], wing[ri + 1][s2], wing[ri + 1][si]])
                except ValueError:
                    pass

    # Mild nostril indents as inward cones under tip
    for side in (-1, 1):
        nc = Vector((side * 0.38, tip.y + 0.35, tip.z - 0.55))
        opening = []
        for j in range(8):
            a = 2 * math.pi * j / 8
            opening.append(bm.verts.new((
                nc.x + math.cos(a) * 0.28,
                nc.y + math.sin(a) * 0.18,
                nc.z,
            )))
        cave = bm.verts.new((nc.x, nc.y, nc.z - 0.35))
        for j in range(8):
            j2 = (j + 1) % 8
            try:
                bm.faces.new([opening[j], opening[j2], cave])
            except ValueError:
                pass

    return mesh_from_bmesh(name, bm)


# ── Mouth / Lips ──────────────────────────────────────────────────────────────
def make_mouth(name, style="neutral"):
    """
    Volumetric upper + lower lips with cupid's bow and lip seam.
    """
    bm = bmesh.new()
    c = MOUTH_C

    if style == "neutral":
        width, upper_h, lower_h, smile, fullness = 1.85, 0.42, 0.48, 0.0, 0.32
    elif style == "smile":
        width, upper_h, lower_h, smile, fullness = 2.0, 0.38, 0.45, 0.28, 0.30
    else:  # full
        width, upper_h, lower_h, smile, fullness = 1.95, 0.55, 0.62, 0.08, 0.48

    segs = 20

    def lip_profile(t, is_upper):
        """t in [0,1] left→right. Returns (x, y, z_front, half_height)."""
        # Map t to angle-like: -1..1
        u = t * 2 - 1
        x = c.x + u * width
        # Smile lifts corners
        corner = abs(u) ** 1.6
        y_smile = smile * corner
        if is_upper:
            # Cupid's bow: two peaks with center dip
            bow = 0.22 * math.cos(u * math.pi) ** 2
            dip = 0.12 * math.exp(-(u**2) / (2 * 0.08**2))
            y = c.y + upper_h * 0.15 + bow - dip + y_smile
            h = upper_h * (1.0 - 0.55 * corner)
        else:
            y = c.y - lower_h * 0.35 - 0.05 * (1 - corner) + y_smile * 0.5
            h = lower_h * (1.0 - 0.4 * corner)
        z = c.z + fullness * (1.0 - 0.35 * corner) * (0.85 if is_upper else 1.0)
        return x, y, z, h

    def build_lip(is_upper):
        # Cross-section rings along the lip
        rings = []
        for i in range(segs + 1):
            t = i / segs
            x, y, z, h = lip_profile(t, is_upper)
            # Elliptical cross-section (height × depth)
            cs = 6
            ring = []
            for j in range(cs):
                a = 2 * math.pi * j / cs
                # Bias bulk outward (+Z) and toward lip edge
                oy = math.sin(a) * h * 0.55
                oz = math.cos(a) * fullness * 0.55
                if oz < 0:
                    oz *= 0.35  # flat against teeth/face
                # Upper lip sits slightly above seam, lower below
                yy = y + oy + (0.06 if is_upper else -0.06)
                ring.append(bm.verts.new((x, yy, z + oz)))
            rings.append(ring)
        cs = 6
        for i in range(segs):
            for j in range(cs):
                j2 = (j + 1) % cs
                try:
                    bm.faces.new([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]])
                except ValueError:
                    pass
        # Cap ends
        for end in (0, segs):
            mid = bm.verts.new((
                rings[end][0].co.x,
                sum(v.co.y for v in rings[end]) / len(rings[end]),
                sum(v.co.z for v in rings[end]) / len(rings[end]),
            ))
            for j in range(cs):
                j2 = (j + 1) % cs
                order = (
                    [rings[end][j], rings[end][j2], mid]
                    if end == 0
                    else [rings[end][j2], rings[end][j], mid]
                )
                try:
                    bm.faces.new(order)
                except ValueError:
                    pass

    build_lip(True)
    build_lip(False)

    # Soft mouth corner pads
    for side in (-1, 1):
        pc = Vector((c.x + side * width * 0.95, c.y + smile * 0.9, c.z + fullness * 0.3))
        k_segs, k_rings = 6, 3
        corner_r = 0.18
        rows = []
        for ri in range(k_rings + 1):
            v = ri / k_rings
            phi = math.pi * v
            row = []
            for si in range(k_segs):
                th = 2 * math.pi * si / k_segs
                row.append(bm.verts.new((
                    pc.x + math.sin(phi) * math.cos(th) * corner_r,
                    pc.y + math.cos(phi) * corner_r * 0.7,
                    pc.z + math.sin(phi) * math.sin(th) * corner_r * 0.8,
                )))
            rows.append(row)
        for ri in range(k_rings):
            for si in range(k_segs):
                s2 = (si + 1) % k_segs
                try:
                    bm.faces.new([rows[ri][si], rows[ri][s2], rows[ri + 1][s2], rows[ri + 1][si]])
                except ValueError:
                    pass

    return mesh_from_bmesh(name, bm)


# ── Ears ──────────────────────────────────────────────────────────────────────
def make_ear(name, center, sign, style="round"):
    """
    Stylized ear with helix rim, concha bowl, and lobe.
    Round = human; pointed = elf-like tip.
    """
    bm = bmesh.new()

    height = 3.4 if style == "round" else 4.2
    width = 2.05 if style == "round" else 1.85
    depth = 1.15

    # Outer helix silhouette in YZ plane, extruded in ±X (out from head)
    # Parametric ear outline (unit space), then scaled
    outline = []
    n = 24
    for i in range(n):
        t = i / n
        a = t * 2 * math.pi
        # Base ellipse
        oy = math.sin(a)
        oz = math.cos(a)
        # Pinch top for pointed
        if style == "pointed" and oy > 0.35:
            tip = (oy - 0.35) / 0.65
            oy = 0.35 + tip * 1.15
            oz *= 1.0 - 0.55 * tip
        # Lobe fuller at bottom
        if oy < -0.3:
            oz *= 0.85
            oy = -0.3 + (oy + 0.3) * 1.15
        # Helix notch (antihelix suggestion) — slight dent on front edge
        outline.append((oy, oz))

    # Build outer rim + inner concha
    outer = []
    inner = []
    for oy, oz in outline:
        y = center.y + oy * height * 0.5
        z = center.z + oz * width * 0.5
        # Outer rim sticks out from head
        x_out = center.x + sign * (depth * 0.95)
        x_in = center.x + sign * (depth * 0.25)
        outer.append(bm.verts.new((x_out, y, z)))
        # Inner concha inset toward head and slightly smaller
        inner.append(bm.verts.new((
            x_in,
            center.y + oy * height * 0.32,
            center.z + oz * width * 0.28,
        )))

    # Rim band
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new([inner[i], inner[j], outer[j], outer[i]])
        except ValueError:
            pass

    # Concha floor (bowl)
    bowl = bm.verts.new((
        center.x + sign * (depth * 0.15),
        center.y - height * 0.05,
        center.z,
    ))
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new([inner[i], inner[j], bowl])
        except ValueError:
            pass

    # Helix thickness — back face of outer rim toward head attachment
    attach = []
    for oy, oz in outline:
        attach.append(bm.verts.new((
            center.x + sign * 0.08,
            center.y + oy * height * 0.48,
            center.z + oz * width * 0.42,
        )))
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new([outer[i], outer[j], attach[j], attach[i]])
        except ValueError:
            pass
    # Close attachment disk
    try:
        bm.faces.new(list(reversed(attach)))
    except ValueError:
        pass

    # Antihelix ridge (raised Y-curve inside ear)
    ridge = []
    for k in range(8):
        t = k / 7
        y = center.y + _lerp(height * 0.35, -height * 0.15, t)
        z = center.z + 0.15 * math.sin(t * math.pi)
        x = center.x + sign * (depth * 0.55)
        ridge.append(bm.verts.new((x, y, z)))
    for k in range(7):
        # small tube along ridge
        for side_z, side_x in ((0.12, 0.08),):
            pass
        a = ridge[k]
        b = ridge[k + 1]
        # Expand to a thin quad strip
        off = sign * 0.1
        try:
            v0 = a
            v1 = b
            v2 = bm.verts.new((b.co.x + off * 0.3, b.co.y, b.co.z + 0.12))
            v3 = bm.verts.new((a.co.x + off * 0.3, a.co.y, a.co.z + 0.12))
            bm.faces.new([v0, v1, v2, v3])
        except ValueError:
            pass

    # Earlobe bulb
    lobe_c = Vector((
        center.x + sign * depth * 0.55,
        center.y - height * 0.48,
        center.z - width * 0.05,
    ))
    lr = 0.55 if style == "round" else 0.42
    l_segs, l_rings = 8, 4
    lobe = []
    for ri in range(l_rings + 1):
        v = ri / l_rings
        phi = math.pi * v
        row = []
        for si in range(l_segs):
            th = 2 * math.pi * si / l_segs
            row.append(bm.verts.new((
                lobe_c.x + math.sin(phi) * math.cos(th) * lr * 0.7,
                lobe_c.y + math.cos(phi) * lr,
                lobe_c.z + math.sin(phi) * math.sin(th) * lr * 0.85,
            )))
        lobe.append(row)
    for ri in range(l_rings):
        for si in range(l_segs):
            s2 = (si + 1) % l_segs
            try:
                bm.faces.new([lobe[ri][si], lobe[ri][s2], lobe[ri + 1][s2], lobe[ri + 1][si]])
            except ValueError:
                pass

    return mesh_from_bmesh(name, bm)


def build_pair(builder_l, builder_r, name, tex_path, arm, head, roughness=0.55, specular=0.2):
    left = builder_l()
    right = builder_r()
    obj = join_objects([left, right], name)
    apply_material(obj, tex_path, roughness=roughness, name=f"{name}_Mat", specular=specular)
    finish_mesh(obj)
    skin_to_head(obj, arm, head)
    return obj


# ── Feature sets ──────────────────────────────────────────────────────────────
BROWS = [
    {"id": "dark_eyebrows", "name": "DarkEyebrows", "label": "Dark Eyebrows",
     "rgb": (0.16, 0.10, 0.07), "color": "#3F2A1D",
     "arch": 0.52, "thick": 0.42, "taper": 0.55, "length": 2.85},
    {"id": "soft_eyebrows", "name": "SoftEyebrows", "label": "Soft Eyebrows",
     "rgb": (0.42, 0.30, 0.18), "color": "#8B6914",
     "arch": 0.38, "thick": 0.48, "taper": 0.35, "length": 2.95},
    {"id": "arched_eyebrows", "name": "ArchedEyebrows", "label": "Arched Eyebrows",
     "rgb": (0.08, 0.05, 0.03), "color": "#1A120B",
     "arch": 0.82, "thick": 0.34, "taper": 0.7, "length": 2.8},
]

LASHES = [
    {"id": "natural_eyelashes", "name": "NaturalEyelashes", "label": "Natural Eyelashes",
     "rgb": (0.06, 0.04, 0.03), "color": "#1C1917",
     "count": 12, "length": 0.95, "curl": 0.45},
    {"id": "long_eyelashes", "name": "LongEyelashes", "label": "Long Eyelashes",
     "rgb": (0.03, 0.02, 0.015), "color": "#0C0A09",
     "count": 16, "length": 1.45, "curl": 0.75},
]

NOSES = [
    {"id": "button_nose", "name": "ButtonNose", "label": "Button Nose",
     "rgb": (0.91, 0.71, 0.63), "color": "#E8B4A0", "style": "button"},
    {"id": "straight_nose", "name": "StraightNose", "label": "Straight Nose",
     "rgb": (0.88, 0.66, 0.56), "color": "#E0A890", "style": "straight"},
    {"id": "soft_nose", "name": "SoftNose", "label": "Soft Nose",
     "rgb": (0.94, 0.77, 0.69), "color": "#EFC4B0", "style": "soft"},
]

MOUTHS = [
    {"id": "neutral_mouth", "name": "NeutralMouth", "label": "Neutral Mouth",
     "rgb": (0.78, 0.38, 0.42), "color": "#C7616B", "style": "neutral"},
    {"id": "soft_smile_mouth", "name": "SoftSmileMouth", "label": "Soft Smile Mouth",
     "rgb": (0.82, 0.40, 0.48), "color": "#D1667A", "style": "smile"},
    {"id": "full_lips_mouth", "name": "FullLipsMouth", "label": "Full Lips Mouth",
     "rgb": (0.72, 0.28, 0.36), "color": "#B8475C", "style": "full"},
]

EARS = [
    {"id": "round_ears", "name": "RoundEars", "label": "Round Ears",
     "rgb": (0.90, 0.70, 0.62), "color": "#E6B39E", "style": "round"},
    {"id": "pointed_ears", "name": "PointedEars", "label": "Pointed Ears",
     "rgb": (0.88, 0.68, 0.60), "color": "#E0AD99", "style": "pointed"},
]


def run_brows():
    out_dir = os.path.join(FACE_ROOT, "Eyebrows")
    tex_dir = os.path.join(out_dir, "Textures")
    slots = []
    for spec in BROWS:
        clear_scene()
        tex = make_brow_tex(os.path.join(tex_dir, f"{spec['name']}.png"), spec["rgb"])
        arm, head = load_armature()
        obj = build_pair(
            lambda s=spec: make_brow(
                f"{s['name']}_L", BROW_L, -1,
                arch=s["arch"], thickness=s["thick"], taper=s["taper"], length=s["length"],
            ),
            lambda s=spec: make_brow(
                f"{s['name']}_R", BROW_R, +1,
                arch=s["arch"], thickness=s["thick"], taper=s["taper"], length=s["length"],
            ),
            spec["name"], tex, arm, head, roughness=0.75, specular=0.05,
        )
        path = os.path.join(out_dir, f"{spec['name']}Weighted.glb")
        export_glb([obj], arm, path)
        slots.append((spec, path, "eyebrows"))
    return slots


def run_lashes():
    out_dir = os.path.join(FACE_ROOT, "Eyelashes")
    tex_dir = os.path.join(out_dir, "Textures")
    slots = []
    for spec in LASHES:
        clear_scene()
        tex = make_lash_tex(os.path.join(tex_dir, f"{spec['name']}.png"), spec["rgb"])
        arm, head = load_armature()
        obj = build_pair(
            lambda s=spec: make_lashes(
                f"{s['name']}_L", LASH_L, -1,
                count=s["count"], length=s["length"], curl=s["curl"],
            ),
            lambda s=spec: make_lashes(
                f"{s['name']}_R", LASH_R, +1,
                count=s["count"], length=s["length"], curl=s["curl"],
            ),
            spec["name"], tex, arm, head, roughness=0.55, specular=0.15,
        )
        path = os.path.join(out_dir, f"{spec['name']}Weighted.glb")
        export_glb([obj], arm, path)
        slots.append((spec, path, "eyelashes"))
    return slots


def run_noses():
    out_dir = os.path.join(FACE_ROOT, "Nose")
    tex_dir = os.path.join(out_dir, "Textures")
    slots = []
    for spec in NOSES:
        clear_scene()
        tex = make_skin_tex(os.path.join(tex_dir, f"{spec['name']}.png"), spec["rgb"])
        arm, head = load_armature()
        obj = make_nose(spec["name"], style=spec["style"])
        apply_material(obj, tex, roughness=0.62, name=f"{spec['name']}_Mat", specular=0.18)
        finish_mesh(obj)
        skin_to_head(obj, arm, head)
        path = os.path.join(out_dir, f"{spec['name']}Weighted.glb")
        export_glb([obj], arm, path)
        slots.append((spec, path, "nose"))
    return slots


def run_mouths():
    out_dir = os.path.join(FACE_ROOT, "Mouth")
    tex_dir = os.path.join(out_dir, "Textures")
    slots = []
    for spec in MOUTHS:
        clear_scene()
        tex = make_lip_tex(os.path.join(tex_dir, f"{spec['name']}.png"), spec["rgb"])
        arm, head = load_armature()
        obj = make_mouth(spec["name"], style=spec["style"])
        apply_material(obj, tex, roughness=0.38, name=f"{spec['name']}_Mat", specular=0.35)
        finish_mesh(obj)
        skin_to_head(obj, arm, head)
        path = os.path.join(out_dir, f"{spec['name']}Weighted.glb")
        export_glb([obj], arm, path)
        slots.append((spec, path, "mouth"))
    return slots


def run_ears():
    out_dir = os.path.join(FACE_ROOT, "Ears")
    tex_dir = os.path.join(out_dir, "Textures")
    slots = []
    for spec in EARS:
        clear_scene()
        tex = make_skin_tex(os.path.join(tex_dir, f"{spec['name']}.png"), spec["rgb"])
        arm, head = load_armature()
        obj = build_pair(
            lambda s=spec: make_ear(f"{s['name']}_L", EAR_L, -1, style=s["style"]),
            lambda s=spec: make_ear(f"{s['name']}_R", EAR_R, +1, style=s["style"]),
            spec["name"], tex, arm, head, roughness=0.65, specular=0.15,
        )
        path = os.path.join(out_dir, f"{spec['name']}Weighted.glb")
        export_glb([obj], arm, path)
        slots.append((spec, path, "ears"))
    return slots


def main():
    print("=" * 60)
    print("Generating Female V2 face accessories (redesign)")
    print("=" * 60)
    all_slots = []
    all_slots += run_brows()
    all_slots += run_lashes()
    all_slots += run_noses()
    all_slots += run_mouths()
    all_slots += run_ears()
    print(f"\nBuilt {len(all_slots)} accessories")
    man_path = os.path.join(FACE_ROOT, "face_accessories_manifest.json")
    man = []
    for spec, path, cat in all_slots:
        rel = "/equipment/Female/" + os.path.relpath(path, FACE_ROOT).replace("\\", "/")
        man.append({
            "id": spec["id"],
            "name": spec["label"],
            "category": cat,
            "collection": "face_accessories",
            "color": spec["color"],
            "url": rel,
        })
    with open(man_path, "w") as f:
        json.dump(man, f, indent=2)
    print("Manifest →", man_path)


if __name__ == "__main__":
    main()
