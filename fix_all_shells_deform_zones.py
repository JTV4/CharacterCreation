"""
fix_all_shells_deform_zones.py
================================
Applies targeted directional clearance pushes to all four thin shells.
Weights are NOT changed.  Each push only affects the specific deformation
zone that compresses against the body during animation.

Shell thicknesses are now 50% of original (9-13 mm), so effective clearance
in high-deformation zones (armpits, groin, inner knees, inner palm) is
roughly 6-9 mm before these fixes.  Each push adds 10-16 mm of targeted
clearance in the direction the body presses against the shell.

UPPER BODY — armpits (±X direction, same fix that worked before)
  Inner armpit crease folds when arm drops in idle. Push outward along ±X.

LOWER BODY — groin + inner knees
  Groin: thigh lifts toward torso; push upward (+Z) on inner groin.
  Inner knee: knee bends; push in ±X (medial) direction.

GLOVES — inner palm / inner fingers (-Y direction)
  Inner palm folds against thigh in idle. Push in -Y.

BOOTS — inner ankle/shin crease (-Y or ±X)
  Ankle rolls inward; push inner ankle outward in ±X.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python fix_all_shells_deform_zones.py
"""

import bpy, bmesh, math, os

BASE = "/Users/stephenvillavaso/Documents/GitHub/CharacterCreation"

def gauss(px,py,pz, cx,cy,cz, sig):
    d2=(px-cx)**2+(py-cy)**2+(pz-cz)**2
    return math.exp(-d2/(2*sig**2))

def apply_push(bm_verts, centres, push_vec_fn, peak, sigma, cutoff_mult=3.5):
    """Push each vertex by push_vec_fn(best_gauss) × peak."""
    cutoff_d = sigma * cutoff_mult
    moved = 0
    for v in bm_verts:
        x,y,z = v.co.x, v.co.y, v.co.z
        best = 0.0
        for (cx,cy,cz) in centres:
            d = math.sqrt((x-cx)**2+(y-cy)**2+(z-cz)**2)
            if d < cutoff_d:
                best = max(best, gauss(x,y,z,cx,cy,cz,sigma))
        if best < 0.01:
            continue
        dx, dy, dz = push_vec_fn(x, y, z)
        v.co.x += dx * peak * best
        v.co.y += dy * peak * best
        v.co.z += dz * peak * best
        moved += 1
    return moved

def process(glb_path, fixes):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh_objs = [o for o in bpy.data.objects if o.type=='MESH' and o.vertex_groups]
    armatures = [o for o in bpy.data.objects if o.type=='ARMATURE']

    for obj in mesh_objs:
        mesh = obj.data
        bm = bmesh.new(); bm.from_mesh(mesh); bm.verts.ensure_lookup_table()
        all_v = list(bm.verts)
        total = 0
        for fix in fixes:
            n = apply_push(all_v, fix['centres'], fix['vec'], fix['peak'], fix['sigma'])
            total += n
            print(f"  [{obj.name}] {fix['label']}: {n} verts")
        bm.normal_update(); bm.to_mesh(mesh); bm.free(); mesh.update()

    bpy.ops.object.select_all(action='DESELECT')
    for o in mesh_objs+armatures: o.select_set(True)
    if armatures: bpy.context.view_layer.objects.active = armatures[0]
    bpy.ops.export_scene.gltf(
        filepath=glb_path, export_format='GLB', use_selection=True,
        export_apply=False, export_yup=True, export_skins=True,
        export_all_influences=True, export_def_bones=True,
        export_animations=False, export_materials='EXPORT',
    )
    print(f"  → {os.path.basename(glb_path)}")


# ─────────────────────────────────────────────────────────────────────────────
# UPPER BODY  (Z-up Blender coords, metres)
# Armpit crease: inner armpit at X≈±0.18–0.27, Y≈-0.04, Z≈1.30–1.42
# Push left armpit in +X, right armpit in -X (global, pose-independent)
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== upper_body ===")
process(f"{BASE}/viewer/public/equipment/shell_upper_body.glb", [
    {
        'label': 'left armpit +X',
        'centres': [( 0.195, -0.04, 1.36)],
        'vec':     lambda x,y,z: (1,0,0),   # always +X for left side
        'peak':    0.016,
        'sigma':   0.065,
    },
    {
        'label': 'right armpit -X',
        'centres': [(-0.195, -0.04, 1.36)],
        'vec':     lambda x,y,z: (-1,0,0),  # always -X for right side
        'peak':    0.016,
        'sigma':   0.065,
    },
])

# ─────────────────────────────────────────────────────────────────────────────
# LOWER BODY  (metres, Z-up)
# Groin: inner thigh / crotch area folds when leg lifts.
#   Centre: X≈0, Y≈-0.04, Z≈1.00 — push upward (+Z)
# Inner knee: medial knee compresses when knee bends.
#   Left medial knee: X≈0.10, Y≈-0.01, Z≈0.55 — push +X
#   Right medial knee: X≈-0.10, Y≈-0.01, Z≈0.55 — push -X
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== lower_body ===")
process(f"{BASE}/viewer/public/equipment/shell_lower_body.glb", [
    {
        'label': 'groin +Z',
        'centres': [(0.0, -0.04, 1.00), (0.06, -0.04, 1.00), (-0.06, -0.04, 1.00)],
        'vec':     lambda x,y,z: (0,0,1),
        'peak':    0.014,
        'sigma':   0.060,
    },
    {
        'label': 'left inner knee +X',
        'centres': [(0.10, -0.01, 0.55)],
        'vec':     lambda x,y,z: (1,0,0),
        'peak':    0.012,
        'sigma':   0.055,
    },
    {
        'label': 'right inner knee -X',
        'centres': [(-0.10, -0.01, 0.55)],
        'vec':     lambda x,y,z: (-1,0,0),
        'peak':    0.012,
        'sigma':   0.055,
    },
])

# ─────────────────────────────────────────────────────────────────────────────
# GLOVES  (metres, Z-up)
# Inner palm/finger surfaces fold against thigh in idle.
# Push in -Y (palm-facing direction).
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== gloves ===")
process(f"{BASE}/viewer/public/equipment/shell_gloves.glb", [
    {
        'label': 'left inner palm -Y',
        'centres': [( 0.62, -0.050, 1.390)],
        'vec':     lambda x,y,z: (0,-1,0) if y < 0.005 else (0,0,0),
        'peak':    0.014,
        'sigma':   0.075,
    },
    {
        'label': 'right inner palm -Y',
        'centres': [(-0.62, -0.050, 1.390)],
        'vec':     lambda x,y,z: (0,-1,0) if y < 0.005 else (0,0,0),
        'peak':    0.014,
        'sigma':   0.075,
    },
])

# ─────────────────────────────────────────────────────────────────────────────
# BOOTS  (metres, Z-up)
# Inner ankle: ankle rolls inward; medial ankle area.
#   Left medial ankle: X≈0.07, Y≈0, Z≈0.10 — push +X
#   Right medial ankle: X≈-0.07, Y≈0, Z≈0.10 — push -X
# Achilles/heel crease: heel compresses upward when foot bends.
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== boots ===")
process(f"{BASE}/viewer/public/equipment/shell_boots.glb", [
    {
        'label': 'left inner ankle +X',
        'centres': [(0.07, 0.00, 0.10)],
        'vec':     lambda x,y,z: (1,0,0),
        'peak':    0.012,
        'sigma':   0.050,
    },
    {
        'label': 'right inner ankle -X',
        'centres': [(-0.07, 0.00, 0.10)],
        'vec':     lambda x,y,z: (-1,0,0),
        'peak':    0.012,
        'sigma':   0.050,
    },
])

# Copy everything to output/shells too
import shutil
for name in ['shell_upper_body','shell_lower_body','shell_gloves','shell_boots']:
    src = f"{BASE}/viewer/public/equipment/{name}.glb"
    dst = f"{BASE}/equipment/output/shells/{name}.glb"
    shutil.copy(src, dst)
print("\nAll shells synced to equipment/output/shells/")
