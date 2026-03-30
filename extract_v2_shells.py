"""
extract_v2_shells.py
=====================
Creates 8 individually-hideable shell pieces for the Female V2 body.
Each shell exactly wraps its corresponding body region mesh and is exported
as a fully-weighted skinned GLB.

Source:  viewer/public/models/BaseFemaleV2.glb
         (8 named region meshes)

Output:  viewer/public/equipment/shell_v2_{region}.glb  (8 files)

Regions & thicknesses:
  head          →  6 mm  (solidify)
  upper_torso   → 10 mm  (chest + shoulders)
  lower_torso   → 10 mm  (belly + waist + hips)
  arms          → 10 mm
  hands         → 12 mm
  upper_leg     →  9 mm  (thighs)
  lower_leg     →  9 mm  (shins / knees)
  feet          → 13 mm

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python extract_v2_shells.py
"""

from __future__ import annotations
import bpy, bmesh, math, os, shutil

SRC_GLB  = "viewer/public/models/BaseFemaleV2.glb"
OUT_DIR  = "viewer/public/equipment"

# ── Per-region configuration ──────────────────────────────────────────────────
REGIONS = {
    "head": {
        "thickness": 0.006,
        "mode": "solidify",
        "normal_smooth": 0,
        "corrective_smooth": 10,
        "corrective_factor": 0.5,
        "deform_fixes": [],
    },
    "upper_torso": {
        "thickness": 0.010,
        "mode": "displace",
        "normal_smooth": 20,          # armpits are concave
        "corrective_smooth": 15,
        "corrective_factor": 0.5,
        "deform_fixes": [
            # Left armpit crease → push +X
            {"centres": [(0.195, -0.04, 1.36)], "vec": (1,0,0),  "peak": 0.016, "sigma": 0.065},
            # Right armpit crease → push -X
            {"centres": [(-0.195, -0.04, 1.36)], "vec": (-1,0,0), "peak": 0.016, "sigma": 0.065},
        ],
    },
    "lower_torso": {
        "thickness": 0.010,
        "mode": "displace",
        "normal_smooth": 20,
        "corrective_smooth": 15,
        "corrective_factor": 0.5,
        "deform_fixes": [
            # Hip-crease → push +Z (where lower torso meets upper leg)
            {"centres": [(0.08,-0.03,0.98),(-0.08,-0.03,0.98),(0.0,-0.03,0.98)],
             "vec": (0,0,1), "peak": 0.014, "sigma": 0.060},
        ],
    },
    "arms": {
        "thickness": 0.010,
        "mode": "displace",
        "normal_smooth": 20,
        "corrective_smooth": 15,
        "corrective_factor": 0.5,
        "deform_fixes": [
            # Armpit end of arm shell
            {"centres": [(0.195, -0.04, 1.36)],  "vec": (1,0,0),  "peak": 0.016, "sigma": 0.065},
            {"centres": [(-0.195, -0.04, 1.36)], "vec": (-1,0,0), "peak": 0.016, "sigma": 0.065},
        ],
    },
    "hands": {
        "thickness": 0.012,
        "mode": "displace",
        "normal_smooth": 10,
        "corrective_smooth": 15,
        "corrective_factor": 0.5,
        "deform_fixes": [
            # Left inner palm → push -Y
            {"centres": [(0.62, -0.050, 1.390)], "vec": (0,-1,0), "peak": 0.014, "sigma": 0.075,
             "y_gate": 0.005},
            # Right inner palm → push -Y
            {"centres": [(-0.62, -0.050, 1.390)], "vec": (0,-1,0), "peak": 0.014, "sigma": 0.075,
             "y_gate": 0.005},
        ],
    },
    "upper_leg": {
        "thickness": 0.009,
        "mode": "displace",
        "normal_smooth": 25,          # inner groin is the worst concave zone
        "corrective_smooth": 15,
        "corrective_factor": 0.5,
        "deform_fixes": [
            # Groin / inner thigh → push +Z
            {"centres": [(0.0,-0.04,1.00),(0.07,-0.04,1.00),(-0.07,-0.04,1.00)],
             "vec": (0,0,1), "peak": 0.014, "sigma": 0.060},
            # Left inner thigh (lower) → push +X
            {"centres": [(0.09,-0.01,0.72)], "vec": (1,0,0), "peak": 0.011, "sigma": 0.055},
            # Right inner thigh (lower) → push -X
            {"centres": [(-0.09,-0.01,0.72)], "vec": (-1,0,0), "peak": 0.011, "sigma": 0.055},
        ],
    },
    "lower_leg": {
        "thickness": 0.009,
        "mode": "displace",
        "normal_smooth": 20,
        "corrective_smooth": 15,
        "corrective_factor": 0.5,
        "deform_fixes": [
            # Left inner knee → push +X
            {"centres": [(0.10,-0.01,0.55)], "vec": (1,0,0), "peak": 0.012, "sigma": 0.055},
            # Right inner knee → push -X
            {"centres": [(-0.10,-0.01,0.55)], "vec": (-1,0,0), "peak": 0.012, "sigma": 0.055},
            # Left inner ankle → push +X
            {"centres": [(0.06, 0.00, 0.13)], "vec": (1,0,0), "peak": 0.010, "sigma": 0.045},
            # Right inner ankle → push -X
            {"centres": [(-0.06, 0.00, 0.13)], "vec": (-1,0,0), "peak": 0.010, "sigma": 0.045},
        ],
    },
    "feet": {
        "thickness": 0.013,
        "mode": "displace",
        "normal_smooth": 10,
        "corrective_smooth": 20,
        "corrective_factor": 0.5,
        "deform_fixes": [
            # Left inner ankle → push +X
            {"centres": [(0.07, 0.00, 0.10)], "vec": (1,0,0), "peak": 0.012, "sigma": 0.050},
            # Right inner ankle → push -X
            {"centres": [(-0.07, 0.00, 0.10)], "vec": (-1,0,0), "peak": 0.012, "sigma": 0.050},
        ],
    },
}

REGION_ORDER = [
    "head", "upper_torso", "lower_torso",
    "arms", "hands",
    "upper_leg", "lower_leg", "feet",
]

# Mixamo → generic rig bone name mapping (same as body_shell_extractor.py)
# This is required so the viewer's BONE_NAME_REMAP can bind equipment bones
# to the character skeleton (BONE_NAME_REMAP maps generic → mixamorigXxx).
MIXAMO_TO_RIG: dict[str, str] = {
    "mixamorig:Hips":           "pelvis",
    "mixamorig:Spine":          "spine_01",
    "mixamorig:Spine1":         "spine_02",
    "mixamorig:Spine2":         "spine_03",
    "mixamorig:Neck":           "neck_01",
    "mixamorig:Head":           "head",
    "mixamorig:HeadTop_End":    "head",
    "mixamorig:LeftShoulder":   "clavicle_L",
    "mixamorig:RightShoulder":  "clavicle_R",
    "mixamorig:LeftArm":        "upperarm_L",
    "mixamorig:RightArm":       "upperarm_R",
    "mixamorig:LeftForeArm":    "lowerarm_L",
    "mixamorig:RightForeArm":   "lowerarm_R",
    "mixamorig:LeftHand":       "hand_L",
    "mixamorig:RightHand":      "hand_R",
    "mixamorig:LeftUpLeg":      "thigh_L",
    "mixamorig:RightUpLeg":     "thigh_R",
    "mixamorig:LeftLeg":        "shin_L",
    "mixamorig:RightLeg":       "shin_R",
    "mixamorig:LeftFoot":       "foot_L",
    "mixamorig:RightFoot":      "foot_R",
    "mixamorig:LeftToeBase":    "toe_L",
    "mixamorig:RightToeBase":   "toe_R",
    "mixamorig:LeftToe_End":    "toe_L",
    "mixamorig:RightToe_End":   "toe_R",
    "mixamorig:Jaw":            "jaw",
    "mixamorig:LeftEye":        "eye_L",
    "mixamorig:RightEye":       "eye_R",
    # Fingers — left
    "mixamorig:LeftHandThumb1": "thumb_01_L",
    "mixamorig:LeftHandThumb2": "thumb_02_L",
    "mixamorig:LeftHandThumb3": "thumb_03_L",
    "mixamorig:LeftHandThumb4": "thumb_03_L",
    "mixamorig:LeftHandIndex1": "index_01_L",
    "mixamorig:LeftHandIndex2": "index_02_L",
    "mixamorig:LeftHandIndex3": "index_03_L",
    "mixamorig:LeftHandIndex4": "index_03_L",
    "mixamorig:LeftHandMiddle1":"middle_01_L",
    "mixamorig:LeftHandMiddle2":"middle_02_L",
    "mixamorig:LeftHandMiddle3":"middle_03_L",
    "mixamorig:LeftHandMiddle4":"middle_03_L",
    "mixamorig:LeftHandRing1":  "ring_01_L",
    "mixamorig:LeftHandRing2":  "ring_02_L",
    "mixamorig:LeftHandRing3":  "ring_03_L",
    "mixamorig:LeftHandRing4":  "ring_03_L",
    "mixamorig:LeftHandPinky1": "pinky_01_L",
    "mixamorig:LeftHandPinky2": "pinky_02_L",
    "mixamorig:LeftHandPinky3": "pinky_03_L",
    "mixamorig:LeftHandPinky4": "pinky_03_L",
    # Fingers — right
    "mixamorig:RightHandThumb1":"thumb_01_R",
    "mixamorig:RightHandThumb2":"thumb_02_R",
    "mixamorig:RightHandThumb3":"thumb_03_R",
    "mixamorig:RightHandThumb4":"thumb_03_R",
    "mixamorig:RightHandIndex1":"index_01_R",
    "mixamorig:RightHandIndex2":"index_02_R",
    "mixamorig:RightHandIndex3":"index_03_R",
    "mixamorig:RightHandIndex4":"index_03_R",
    "mixamorig:RightHandMiddle1":"middle_01_R",
    "mixamorig:RightHandMiddle2":"middle_02_R",
    "mixamorig:RightHandMiddle3":"middle_03_R",
    "mixamorig:RightHandMiddle4":"middle_03_R",
    "mixamorig:RightHandRing1": "ring_01_R",
    "mixamorig:RightHandRing2": "ring_02_R",
    "mixamorig:RightHandRing3": "ring_03_R",
    "mixamorig:RightHandRing4": "ring_03_R",
    "mixamorig:RightHandPinky1":"pinky_01_R",
    "mixamorig:RightHandPinky2":"pinky_02_R",
    "mixamorig:RightHandPinky3":"pinky_03_R",
    "mixamorig:RightHandPinky4":"pinky_03_R",
}


# ── Helper: compute smoothed vertex normals ───────────────────────────────────
def compute_smooth_normals(mesh_data, iterations: int) -> dict:
    from mathutils import Vector
    neighbors: dict[int, list[int]] = {v.index: [] for v in mesh_data.vertices}
    for edge in mesh_data.edges:
        v0, v1 = edge.vertices[0], edge.vertices[1]
        neighbors[v0].append(v1)
        neighbors[v1].append(v0)
    normals: dict = {v.index: v.normal.copy() for v in mesh_data.vertices}
    for _ in range(iterations):
        new_normals = {}
        for v in mesh_data.vertices:
            n = normals[v.index].copy()
            for ni in neighbors[v.index]:
                n += normals[ni]
            n.normalize()
            new_normals[v.index] = n
        normals = new_normals
    return normals


# ── Helper: Gaussian deformation-zone push ────────────────────────────────────
def gauss(px, py, pz, cx, cy, cz, sig):
    d2 = (px-cx)**2 + (py-cy)**2 + (pz-cz)**2
    return math.exp(-d2 / (2*sig**2))

def apply_deform_fix(mesh_data, fix: dict):
    centres = fix["centres"]
    vx, vy, vz = fix["vec"]
    peak   = fix["peak"]
    sigma  = fix["sigma"]
    y_gate = fix.get("y_gate", None)   # optional: only push verts where y < gate
    cutoff = sigma * 3.5

    moved = 0
    for v in mesh_data.vertices:
        x, y, z = v.co.x, v.co.y, v.co.z
        # Optional gate to restrict to one face of the mesh
        if y_gate is not None and y >= y_gate:
            continue
        best = 0.0
        for (cx, cy, cz) in centres:
            d = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
            if d < cutoff:
                best = max(best, gauss(x,y,z, cx,cy,cz, sigma))
        if best < 0.01:
            continue
        v.co.x += vx * peak * best
        v.co.y += vy * peak * best
        v.co.z += vz * peak * best
        moved += 1
    return moved


# ── Helper: export single shell + armature ────────────────────────────────────
def export_shell(shell_obj, armature_obj, filepath):
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    # Hide everything except shell + armature
    for obj in bpy.data.objects:
        obj.hide_set(obj not in (shell_obj, armature_obj))
        obj.hide_render = obj not in (shell_obj, armature_obj)

    bpy.ops.object.select_all(action="DESELECT")
    shell_obj.select_set(True)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj

    bpy.ops.export_scene.gltf(
        filepath=os.path.abspath(filepath),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_skins=True,
        export_all_influences=True,
        export_def_bones=True,
        export_animations=False,
        export_materials="EXPORT",
    )
    # Unhide all
    for obj in bpy.data.objects:
        obj.hide_set(False)
        obj.hide_render = False


# ── Main ──────────────────────────────────────────────────────────────────────
print("\n=== Female V2 Shell Extractor ===")

# Load the V2 body
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.abspath(SRC_GLB))

# Identify armature and region meshes
armature = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
region_meshes: dict[str, bpy.types.Object] = {}
for obj in bpy.data.objects:
    if obj.type == "MESH":
        for region in REGION_ORDER:
            if obj.name == f"base_body_{region}":
                region_meshes[region] = obj

print(f"Armature: {armature.name if armature else 'NONE'}")
print(f"Found regions: {list(region_meshes.keys())}")

# Rename armature bones Mixamo → generic rig names once (affects all exports)
if armature:
    arm_renamed = 0
    for bone in armature.data.bones:
        new_name = MIXAMO_TO_RIG.get(bone.name)
        if new_name and new_name != bone.name:
            bone.name = new_name
            arm_renamed += 1
    print(f"Renamed {arm_renamed} armature bones (Mixamo → rig)")

for region in REGION_ORDER:
    if region not in region_meshes:
        print(f"  WARNING: base_body_{region} not found, skipping")
        continue

    cfg = REGIONS[region]
    src  = region_meshes[region]
    thickness = cfg["thickness"]
    print(f"\n--- {region} (thickness={thickness*1000:.0f}mm, mode={cfg['mode']}) ---")

    # ── 1. Duplicate region mesh ──────────────────────────────────────────────
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    bpy.context.view_layer.objects.active = src
    bpy.ops.object.duplicate(linked=False)
    shell = bpy.context.active_object
    shell.name = f"shell_v2_{region}"
    shell.data.name = f"shell_v2_{region}"

    # Detach from parent so modifiers work cleanly.
    # Reset scale to 1 so the shell does NOT inherit the armature's 0.01× cm scale.
    # export_apply=True (below) will bake the armature's 0.01× scale back into the
    # vertex positions at export time, giving correct meter-scale output.
    if shell.parent:
        shell.parent = None
    shell.location = (0.0, 0.0, 0.0)
    shell.rotation_euler = (0.0, 0.0, 0.0)
    shell.scale = (1.0, 1.0, 1.0)
    for mod in list(shell.modifiers):
        if mod.type == "ARMATURE":
            shell.modifiers.remove(mod)

    # ── Rename vertex groups: Mixamo → generic rig names ─────────────────────
    # Required so the viewer's BONE_NAME_REMAP can bind this shell to the
    # character skeleton (matches the naming convention of existing shells).
    renamed = 0
    for vg in shell.vertex_groups:
        new_name = MIXAMO_TO_RIG.get(vg.name)
        if new_name and new_name != vg.name:
            vg.name = new_name
            renamed += 1
    print(f"  Renamed {renamed} vertex groups (Mixamo → rig)")

    # ── 2. Inflate outward ────────────────────────────────────────────────────
    bpy.context.view_layer.objects.active = shell
    bpy.ops.object.select_all(action="DESELECT")
    shell.select_set(True)

    mesh_data = shell.data

    if cfg["mode"] == "solidify":
        # Head: solidify modifier (even-offset, closed cap)
        bpy.ops.object.mode_set(mode="OBJECT")
        mod = shell.modifiers.new("Solidify", type="SOLIDIFY")
        mod.thickness        = thickness
        mod.offset           = -1.0
        mod.use_even_offset  = True
        mod.use_quality_normals = True
        mod.thickness_clamp  = 2.0
        bpy.ops.object.modifier_apply(modifier=mod.name)

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.0002)
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        print(f"  Solidify applied ({thickness*1000:.1f}mm) → "
              f"{len(mesh_data.vertices)} verts")

    else:
        # Displace: smooth normals → push outward → corrective smooth
        n_smooth = cfg["normal_smooth"]
        if n_smooth > 0:
            smooth_norms = compute_smooth_normals(mesh_data, n_smooth)
            for v in mesh_data.vertices:
                v.co += smooth_norms[v.index] * thickness
            print(f"  Displaced {len(mesh_data.vertices)} verts by {thickness*1000:.1f}mm "
                  f"(smooth-normal, {n_smooth} iters)")
        else:
            for v in mesh_data.vertices:
                v.co += v.normal * thickness
            print(f"  Displaced {len(mesh_data.vertices)} verts by {thickness*1000:.1f}mm (raw normal)")
        mesh_data.update()

        # Corrective smooth
        cs_iters  = cfg["corrective_smooth"]
        cs_factor = cfg["corrective_factor"]
        sm_mod = shell.modifiers.new("CorrectiveSmooth", type="CORRECTIVE_SMOOTH")
        sm_mod.factor      = cs_factor
        sm_mod.iterations  = cs_iters
        sm_mod.smooth_type = "LENGTH_WEIGHTED"
        sm_mod.use_only_smooth = True
        bpy.ops.object.modifier_apply(modifier=sm_mod.name)
        print(f"  Corrective smooth ({cs_iters} iters, factor={cs_factor})")

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")

    # ── 3. Deformation-zone fixes ─────────────────────────────────────────────
    total_pushed = 0
    for fix in cfg["deform_fixes"]:
        n = apply_deform_fix(mesh_data, fix)
        total_pushed += n
    if total_pushed:
        mesh_data.update()
        print(f"  Deform-zone fixes: {total_pushed} verts pushed")

    # ── 4. UV unwrap ──────────────────────────────────────────────────────────
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    print(f"  UV unwrapped")

    # ── 5. Re-parent to armature ──────────────────────────────────────────────
    if armature:
        shell.parent = armature
        arm_mod = shell.modifiers.new("Armature", type="ARMATURE")
        arm_mod.object = armature

    # ── 6. Export ─────────────────────────────────────────────────────────────
    out_path = os.path.join(OUT_DIR, f"shell_v2_{region}.glb")
    export_shell(shell, armature, out_path)
    print(f"  → {out_path}")

print("\n=== All V2 shells exported ===")
