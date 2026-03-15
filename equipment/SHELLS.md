# Body Shell Mesh Documentation

Comprehensive reference for the five body shell meshes: **Head**, **Upper Body**, **Gloves**, **Lower Body**, and **Boots**. Each shell is a conforming equipment mesh extracted from the base character model — identical topology, pre-rigged to the same skeleton, offset outward so it sits just above the skin with zero clipping or gaps.

---

## Table of Contents

- [Concept](#concept)
- [Shell Overview](#shell-overview)
- [Per-Shell Specifications](#per-shell-specifications)
  - [Head](#head)
  - [Upper Body](#upper-body)
  - [Gloves](#gloves)
  - [Lower Body](#lower-body)
  - [Boots](#boots)
- [Overlap System](#overlap-system)
- [Extraction Pipeline](#extraction-pipeline)
  - [Prerequisites](#prerequisites)
  - [Step-by-Step Process](#step-by-step-process)
  - [Running the Extractor](#running-the-extractor)
  - [CLI Options](#cli-options)
- [Viewer Integration](#viewer-integration)
  - [equipment_spec.json Entries](#equipment_specjson-entries)
  - [Rendering Pipeline](#rendering-pipeline)
  - [Stencil and Render Order](#stencil-and-render-order)
  - [Base Body Stencil Masking](#base-body-stencil-masking)
- [Texture Baking](#texture-baking)
  - [Texture Sources](#texture-sources)
  - [Baking onto Shells](#baking-onto-shells)
  - [Baking onto Custom Equipment](#baking-onto-custom-equipment)
  - [Adding a Textured Custom Mesh to the Viewer](#adding-a-textured-custom-mesh-to-the-viewer)
  - [Meshy AI Text-to-Texture Pipeline (Recommended)](#meshy-ai-text-to-texture-pipeline-recommended)
- [Duplicating a Shell for a New Character](#duplicating-a-shell-for-a-new-character)
- [Custom Equipment Meshes](#custom-equipment-meshes)
  - [Step 1 — Download the Shell](#step-1--download-the-shell)
  - [Step 2 — Edit in Blender](#step-2--edit-in-blender)
  - [Step 3 — Place in Source Directory](#step-3--place-in-source-directory)
  - [Step 4 — Register in equipment_spec.json](#step-4--register-in-equipment_specjson)
  - [Step 5 — Transfer Weights](#step-5--transfer-weights)
  - [Troubleshooting](#troubleshooting)
  - [End-to-End Example: Custom Female Boots](#end-to-end-example-custom-female-boots)
- [File Locations](#file-locations)

---

## Concept

A "shell" is a slice of the base character mesh (e.g. `BaseFemale.glb`) that has been:

1. **Segmented** by bone weights — each face is assigned to exactly one equipment slot based on which slot's bones have the strongest influence.
2. **Offset outward** — either by vertex displacement along normals (most slots) or Blender's Solidify modifier (Head only), pushing the extracted surface away from the body by a configurable thickness in meters.
3. **Re-rigged** — The shell retains all the original vertex groups and is parented to the rig armature, so it animates identically to the character.
4. **UV-unwrapped** — Smart UV projection is applied after offset so the shell is ready for texturing (AI-generated or hand-painted).

Because the shell geometry is derived directly from the character mesh, it is guaranteed to match the body perfectly. This is the foundation for the equipment texturing pipeline: generate a textured 3D model externally (e.g. via Meshy AI), then bake that model's texture onto the shell using `texture_baker.py`.

---

## Shell Overview

| Shell        | Slot ID            | Thickness | Offset Mode | Smooth (iters / factor) | Bilateral | Body Regions Hidden      |
|--------------|--------------------|-----------|-------------|-------------------------|-----------|--------------------------|
| Head         | `shell_head`       | 5 mm      | solidify    | N/A                     | No        | head                     |
| Upper Body   | `shell_upper_body` | 12 mm     | displace    | 10 / 0.5                | No        | torso, neck, arms        |
| Gloves       | `shell_gloves`     | 15 mm     | displace    | 10 / 0.5                | Yes       | hands                    |
| Lower Body   | `shell_lower_body` | 10 mm     | displace    | 10 / 0.5                | Yes       | torso, legs              |
| Boots        | `shell_boots`      | 40 mm     | displace    | 20 / 0.5                | Yes       | feet, legs               |

**Thickness** controls how far the shell sits above the skin surface. Larger values make the equipment visually bulkier.

**Offset Mode** determines how the thickness is applied:
- `solidify` — Uses Blender's Solidify modifier, creating inner/outer surfaces with walls. Only used for Head.
- `displace` — Pushes each vertex outward along its normal by the thickness amount, then applies a Corrective Smooth modifier to eliminate warping. Used for Upper Body, Gloves, Lower Body, and Boots.

**Smooth** (displace mode only) — The Corrective Smooth modifier parameters applied after vertex displacement. Higher iterations produce smoother results but can reduce effective thickness.

**Bilateral** means the slot covers both left and right sides of the body (e.g. both hands for gloves, both legs for boots/lower body).

**Body Regions Hidden** lists which parts of the base character mesh are hidden when the shell is equipped, preventing the skin from showing through.

---

## Per-Shell Specifications

### Head

**Slot ID:** `shell_head`
**Output file:** `shell_head.glb`
**Thickness:** 0.005 m (5 mm)
**Offset mode:** solidify
**Bilateral:** No

#### Extractor Config (body_shell_extractor.py)

```python
SHELL_THICKNESS["head"] = 0.005
SHELL_OFFSET_MODE["head"] = "solidify"
SHELL_THICKNESS_CLAMP["head"] = 2.0
SHELL_EVEN_OFFSET["head"] = True
```

#### Rig Bones (Extractor)

These are the canonical rig bone names used during extraction (Mixamo names are auto-mapped):

| Rig Bone | Mixamo Equivalent   |
|----------|---------------------|
| `head`   | `mixamorigHead`     |
| `eye_L`  | `mixamorigLeftEye`  |
| `eye_R`  | `mixamorigRightEye` |

#### Viewer Bones (equipment_spec.json)

| Bone Name        | Weight |
|------------------|--------|
| `mixamorigHead`  | 1.0    |
| `mixamorigNeck`  | 0.25   |

#### Spatial Bounds

| Property        | Value |
|-----------------|-------|
| `z_min`         | 1.61  |
| `z_max`         | 1.9   |
| `radius`        | 0.13  |
| `weight_radius` | 0.2   |

#### Overlap Partners

| Partner      | Direction                                   |
|--------------|---------------------------------------------|
| `upper_body` | Upper body expands into head's territory    |

#### What It Covers

The head shell covers the entire skull, face, jaw area, and eyes. The neck is primarily claimed by upper_body via dominant-slot assignment, but the head shell's equipment_spec entry includes the neck bone at a low weight (0.25) so the viewer can smoothly blend skinning at the boundary.

---

### Upper Body

**Slot ID:** `shell_upper_body`
**Output file:** `shell_upper_body.glb`
**Thickness:** 0.012 m (12 mm)
**Offset mode:** displace
**Corrective Smooth:** 10 iterations, factor 0.5
**Bilateral:** No

#### Extractor Config (body_shell_extractor.py)

```python
SHELL_THICKNESS["upper_body"] = 0.012
SHELL_OFFSET_MODE["upper_body"] = "displace"
SHELL_SMOOTH_ITERS["upper_body"] = 10
SHELL_SMOOTH_FACTOR["upper_body"] = 0.5
```

#### Rig Bones (Extractor)

| Rig Bone      | Mixamo Equivalent          |
|---------------|----------------------------|
| `pelvis`      | `mixamorigHips`            |
| `spine_01`    | `mixamorigSpine`           |
| `spine_02`    | `mixamorigSpine1`          |
| `spine_03`    | `mixamorigSpine2`          |
| `clavicle_L`  | `mixamorigLeftShoulder`    |
| `clavicle_R`  | `mixamorigRightShoulder`   |
| `upperarm_L`  | `mixamorigLeftArm`         |
| `upperarm_R`  | `mixamorigRightArm`        |
| `lowerarm_L`  | `mixamorigLeftForeArm`     |
| `lowerarm_R`  | `mixamorigRightForeArm`    |
| `hand_L`      | `mixamorigLeftHand`        |
| `hand_R`      | `mixamorigRightHand`       |
| `thigh_L`     | `mixamorigLeftUpLeg`       |
| `thigh_R`     | `mixamorigRightUpLeg`      |

#### Viewer Bones (equipment_spec.json)

| Bone Name                  | Weight |
|----------------------------|--------|
| `mixamorigHips`            | 0.6    |
| `mixamorigSpine`           | 1.0    |
| `mixamorigSpine1`          | 1.0    |
| `mixamorigSpine2`          | 1.0    |
| `mixamorigLeftShoulder`    | 0.8    |
| `mixamorigRightShoulder`   | 0.8    |
| `mixamorigLeftArm`         | 1.0    |
| `mixamorigRightArm`        | 1.0    |
| `mixamorigLeftForeArm`     | 1.0    |
| `mixamorigRightForeArm`    | 1.0    |
| `mixamorigLeftHand`        | 0.1    |
| `mixamorigRightHand`       | 0.1    |
| `mixamorigNeck`            | 0.1    |

#### Spatial Bounds

| Property        | Value |
|-----------------|-------|
| `z_min`         | 1.01  |
| `z_max`         | 1.54  |
| `radius`        | 0.75  |
| `weight_radius` | 0.3   |

#### Overlap Partners

| Partner       | Direction                                              |
|---------------|--------------------------------------------------------|
| `lower_body`  | Upper body extends past the waist into the hip area    |
| `head`        | Upper body expands into head's neck territory          |
| `gloves`      | Upper body expands into gloves' wrist territory        |

#### What It Covers

The upper body shell covers the entire torso (hips to neck), both shoulders, upper arms, forearms, and extends to the hands. It is the largest shell by surface area. The extractor includes `hand_L`/`hand_R` and `thigh_L`/`thigh_R` in the bone list so the shell extends into adjacent regions for seamless overlap. The hips bone is shared with lower_body — dominant-slot assignment decides which faces go where, and the overlap system lets both shells claim the waist transition zone.

---

### Gloves

**Slot ID:** `shell_gloves`
**Output file:** `shell_gloves.glb`
**Thickness:** 0.015 m (15 mm)
**Offset mode:** displace
**Corrective Smooth:** 10 iterations, factor 0.5
**Bilateral:** Yes

#### Extractor Config (body_shell_extractor.py)

```python
SHELL_THICKNESS["gloves"] = 0.015
SHELL_OFFSET_MODE["gloves"] = "displace"
SHELL_SMOOTH_ITERS["gloves"] = 10
SHELL_SMOOTH_FACTOR["gloves"] = 0.5
```

#### Rig Bones (Extractor)

Both forearms, hands, and all 30 finger bones:

| Rig Bone       | Mixamo Equivalent              |
|----------------|--------------------------------|
| `lowerarm_L`   | `mixamorigLeftForeArm`         |
| `lowerarm_R`   | `mixamorigRightForeArm`        |
| `hand_L`       | `mixamorigLeftHand`            |
| `thumb_01_L`   | `mixamorigLeftHandThumb1`      |
| `thumb_02_L`   | `mixamorigLeftHandThumb2`      |
| `thumb_03_L`   | `mixamorigLeftHandThumb3`      |
| `index_01_L`   | `mixamorigLeftHandIndex1`      |
| `index_02_L`   | `mixamorigLeftHandIndex2`      |
| `index_03_L`   | `mixamorigLeftHandIndex3`      |
| `middle_01_L`  | `mixamorigLeftHandMiddle1`     |
| `middle_02_L`  | `mixamorigLeftHandMiddle2`     |
| `middle_03_L`  | `mixamorigLeftHandMiddle3`     |
| `ring_01_L`    | `mixamorigLeftHandRing1`       |
| `ring_02_L`    | `mixamorigLeftHandRing2`       |
| `ring_03_L`    | `mixamorigLeftHandRing3`       |
| `pinky_01_L`   | `mixamorigLeftHandPinky1`      |
| `pinky_02_L`   | `mixamorigLeftHandPinky2`      |
| `pinky_03_L`   | `mixamorigLeftHandPinky3`      |
| `hand_R`       | `mixamorigRightHand`           |
| `thumb_01_R`   | `mixamorigRightHandThumb1`     |
| `thumb_02_R`   | `mixamorigRightHandThumb2`     |
| `thumb_03_R`   | `mixamorigRightHandThumb3`     |
| `index_01_R`   | `mixamorigRightHandIndex1`     |
| `index_02_R`   | `mixamorigRightHandIndex2`     |
| `index_03_R`   | `mixamorigRightHandIndex3`     |
| `middle_01_R`  | `mixamorigRightHandMiddle1`    |
| `middle_02_R`  | `mixamorigRightHandMiddle2`    |
| `middle_03_R`  | `mixamorigRightHandMiddle3`    |
| `ring_01_R`    | `mixamorigRightHandRing1`      |
| `ring_02_R`    | `mixamorigRightHandRing2`      |
| `ring_03_R`    | `mixamorigRightHandRing3`      |
| `pinky_01_R`   | `mixamorigRightHandPinky1`     |
| `pinky_02_R`   | `mixamorigRightHandPinky2`     |
| `pinky_03_R`   | `mixamorigRightHandPinky3`     |

#### Spatial Bounds

| Property        | Value |
|-----------------|-------|
| `z_min`         | 1.49  |
| `z_max`         | 1.54  |
| `radius`        | 0.20  |
| `weight_radius` | 0.15  |

#### Overlap Partners

| Partner      | Direction                                          |
|--------------|----------------------------------------------------|
| `upper_body` | Upper body expands into gloves' wrist territory    |

#### Viewer Special Handling

Gloves are a **fine-bone slot** (listed in `FINE_BONE_SLOTS` in `EquipmentMeshRenderer.tsx`). The viewer applies a one-time **rest-pose vertex correction** that shifts each vertex to match the character's actual bone positions. This is necessary because the shell's rest pose (from `rig.blend`) may differ slightly from the character model's rest pose, and the small finger bones amplify even tiny misalignments.

#### What It Covers

The gloves shell covers both forearms, hands, and all five fingers per hand. The extractor includes `lowerarm_L`/`lowerarm_R` so the shell extends up the forearm for a seamless transition with the upper body sleeve. The wrist boundary transitions into upper_body territory via the overlap system.

---

### Lower Body

**Slot ID:** `shell_lower_body`
**Output file:** `shell_lower_body.glb`
**Thickness:** 0.01 m (10 mm)
**Offset mode:** displace
**Corrective Smooth:** 10 iterations, factor 0.5
**Bilateral:** Yes

#### Extractor Config (body_shell_extractor.py)

```python
SHELL_THICKNESS["lower_body"] = 0.01
SHELL_OFFSET_MODE["lower_body"] = "displace"
SHELL_SMOOTH_ITERS["lower_body"] = 10
SHELL_SMOOTH_FACTOR["lower_body"] = 0.5
```

#### Rig Bones (Extractor)

| Rig Bone  | Mixamo Equivalent         |
|-----------|---------------------------|
| `pelvis`  | `mixamorigHips`           |
| `thigh_L` | `mixamorigLeftUpLeg`      |
| `thigh_R` | `mixamorigRightUpLeg`     |
| `shin_L`  | `mixamorigLeftLeg`        |
| `shin_R`  | `mixamorigRightLeg`       |
| `foot_L`  | `mixamorigLeftFoot`       |
| `foot_R`  | `mixamorigRightFoot`      |
| `toe_L`   | `mixamorigLeftToeBase`    |
| `toe_R`   | `mixamorigRightToeBase`   |

#### Viewer Bones (equipment_spec.json)

| Bone Name               | Weight |
|-------------------------|--------|
| `mixamorigHips`         | 1.0    |
| `mixamorigLeftUpLeg`    | 1.0    |
| `mixamorigRightUpLeg`   | 1.0    |
| `mixamorigLeftLeg`      | 0.8    |
| `mixamorigRightLeg`     | 0.8    |

#### Spatial Bounds

| Property        | Value |
|-----------------|-------|
| `z_min`         | 0.29  |
| `z_max`         | 1.09  |
| `radius`        | 0.18  |
| `weight_radius` | 0.15  |

#### Overlap Partners

| Partner      | Direction                                                |
|--------------|----------------------------------------------------------|
| `boots`      | Lower body and boots share the shin region               |
| `upper_body` | Upper body extends past the waist into lower body's area |

#### What It Covers

The lower body shell covers the hips, both thighs, shins, feet, and toes. During extraction it claims the pelvis area jointly with upper_body (pelvis bone appears in both), with dominant-slot assignment splitting faces at the waist. The shin region is shared with boots via overlap expansion.

#### Stencil Behavior

Lower body uses **stencil testing** — it only renders where upper_body/boots have NOT already written to the stencil buffer. This prevents lower body geometry from poking through upper body or boots at overlap boundaries:

```
Stencil test: render only where stencilRef != 1
```

---

### Boots

**Slot ID:** `shell_boots`
**Output file:** `shell_boots.glb`
**Thickness:** 0.04 m (40 mm)
**Offset mode:** displace
**Corrective Smooth:** 20 iterations, factor 0.5
**Bilateral:** Yes

#### Extractor Config (body_shell_extractor.py)

```python
SHELL_THICKNESS["boots"] = 0.04
SHELL_OFFSET_MODE["boots"] = "displace"
SHELL_SMOOTH_ITERS["boots"] = 20
SHELL_SMOOTH_FACTOR["boots"] = 0.5
```

#### Rig Bones (Extractor)

| Rig Bone | Mixamo Equivalent         |
|----------|---------------------------|
| `shin_L` | `mixamorigLeftLeg`        |
| `shin_R` | `mixamorigRightLeg`       |
| `foot_L` | `mixamorigLeftFoot`       |
| `foot_R` | `mixamorigRightFoot`      |
| `toe_L`  | `mixamorigLeftToeBase`    |
| `toe_R`  | `mixamorigRightToeBase`   |

#### Viewer Bones (equipment_spec.json)

| Bone Name               | Weight |
|-------------------------|--------|
| `mixamorigLeftLeg`      | 0.6    |
| `mixamorigRightLeg`     | 0.6    |
| `mixamorigLeftFoot`     | 1.0    |
| `mixamorigRightFoot`    | 1.0    |
| `mixamorigLeftToeBase`  | 1.0    |
| `mixamorigRightToeBase` | 1.0    |

#### Spatial Bounds

| Property        | Value  |
|-----------------|--------|
| `z_min`         | -0.02  |
| `z_max`         | 0.52   |
| `radius`        | 0.12   |
| `weight_radius` | 0.12   |

#### Overlap Partners

| Partner      | Direction                                         |
|--------------|---------------------------------------------------|
| `lower_body` | Boots and lower body share the shin region        |

#### What It Covers

The boots shell covers both shins (from about mid-calf), feet, and toes. The shin bones are shared with lower_body — the overlap system lets both shells claim shin faces, with boots sitting outside due to their higher thickness (40 mm vs 10 mm). This creates the visual layering of boots over pants. Boots use 20 corrective smooth iterations (vs 10 for other displace slots) because the foot/ankle geometry warps more during vertex displacement and needs extra smoothing.

#### Stencil Behavior

Boots use **stencil writing** — they write to the stencil buffer so that lower_body fragments behind the boots are discarded:

```
Stencil write: replace stencilRef = 1 on Z-pass
```

---

## Overlap System

Overlaps allow adjacent shell pairs to share faces at their boundary regions. Without overlaps, there would be a visible gap between shells where the body skin shows through.

### How Overlap Expansion Works

1. After dominant-slot face assignment, the system builds a separate "face view" per slot.
2. For each overlap pair `(slotA, slotB)`:
   - Faces assigned to `slotB` are also given to `slotA` if `slotA`'s bones have weight > `OVERLAP_WEIGHT_THRESHOLD` (0.01) on those faces.
   - Vice versa: faces assigned to `slotA` are also given to `slotB` under the same condition.
3. Each slot's extraction then uses its expanded face view, so both shells include the shared transition faces.

### Configured Overlap Pairs

| Pair                        | Shared Region | Why                                                        |
|-----------------------------|---------------|------------------------------------------------------------|
| `lower_body` + `boots`      | Shin area     | Boots sit on top of pants at the calf                      |
| `upper_body` + `lower_body` | Waist/hips    | Shirt extends slightly past the waistline                  |
| `upper_body` + `head`       | Neck          | Shirt collar overlaps with the base of the head shell      |
| `upper_body` + `gloves`     | Wrist         | Sleeves overlap with the start of the glove shell          |

### Visual Layering via Thickness

When two shells overlap the same body region, the thicker shell visually sits on top:

```
boots (40 mm) sits outside lower_body (10 mm) at the shin
upper_body (12 mm) sits outside lower_body (10 mm) at the waist
upper_body (12 mm) sits outside head (5 mm) at the neck
```

---

## Extraction Pipeline

### Prerequisites

| Tool    | Version | Purpose                                                    |
|---------|---------|------------------------------------------------------------|
| Blender | 4.1+    | Mesh extraction, Solidify/Displace, Corrective Smooth, GLB export |

Required input files:

| File                              | Description                              |
|-----------------------------------|------------------------------------------|
| `rig/output/rig.blend`           | Canonical armature with generic bone names |
| `rig/CharacterMesh/BaseFemale.glb` | Mixamo-rigged base character mesh        |

### Step-by-Step Process

The extractor (`equipment/factory/body_shell_extractor.py`) performs these steps in order:

**Step 1 — Import body mesh**
- Loads the base character GLB into a clean Blender scene.
- Joins multiple mesh objects into a single mesh (if the GLB contains more than one).
- Filters out debug/placeholder objects (meshes with fewer than 100 vertices).
- Applies all transforms (location, rotation, scale).

**Step 2 — Rename vertex groups**
- Detects Mixamo vertex group names (prefixed with `mixamorig:`).
- Renames them to canonical rig bone names using the `MIXAMO_TO_RIG` mapping table.
- Example: `mixamorig:LeftHand` becomes `hand_L`.

**Step 3 — Load rig armature**
- Removes all objects except the body mesh.
- Appends the armature from `rig.blend`.
- Parents the body mesh to the rig armature with an Armature modifier.

**Step 4 — Dominant-slot face assignment**
- For every face in the body mesh, sums the total bone weight per slot across the face's vertices.
- Assigns each face to whichever slot scores highest.
- This guarantees non-overlapping, seamless coverage.
- A `weight_threshold` of 0.1 filters out insignificant weights.

**Step 5 — Neighbor-majority smoothing**
- Builds a face adjacency graph (faces sharing an edge are neighbors).
- Iterates up to 5 times: any face whose slot differs from 60%+ of its neighbors is flipped to the majority slot.
- Produces smooth, clean boundary lines between all slots.

**Step 6 — Overlap expansion**
- For each configured overlap pair, expands each slot's face view into its partner's territory wherever it has bone weight above `OVERLAP_WEIGHT_THRESHOLD` (0.01).

**Step 7 — Per-slot extraction**
For each slot:
1. Duplicates the body mesh.
2. Selects only the faces belonging to this slot (from the expanded face view).
3. Inverts selection and deletes non-selected faces.
4. Cleans up: removes loose vertices/edges, merges doubles (threshold 0.0001).
5. Recalculates normals (outward-facing).

**Step 8 — Boundary smoothing and capping**
- Finds all open boundary edges (edges with only one adjacent face — e.g. the wrist edge of the gloves).
- Laplacian-smooths boundary vertices (8 iterations, factor 0.5): each boundary vertex is moved toward the average position of its boundary neighbors, producing a rounder loop.
- Walks each connected boundary loop and fills it with an n-gon cap face.
- Recalculates normals outward.
- The resulting mesh is fully closed, giving Solidify/Displace clean input with no ragged rim artifacts or spike holes.

**Step 9 — Offset (Solidify or Displace)**

The offset mode is controlled by `SHELL_OFFSET_MODE` per slot. There are two modes:

**Solidify mode** (Head only):
- Applies Blender's Solidify modifier with:
  - `thickness` = per-slot value from `SHELL_THICKNESS`
  - `offset = -1.0` (grows outward from original surface)
  - `use_even_offset` = per-slot value from `SHELL_EVEN_OFFSET` (default `True`)
  - `use_quality_normals = True`
  - `thickness_clamp` = per-slot value from `SHELL_THICKNESS_CLAMP` (default `2.0`)
- After applying: merges doubles (threshold 0.0002), recalculates normals.
- Spike removal: deletes any vertices with edges longer than 6x the median edge length.

**Displace mode** (Upper Body, Gloves, Lower Body, Boots):
- Pushes every vertex outward along its vertex normal by `SHELL_THICKNESS[slot]` meters:
  ```python
  for v in mesh_data.vertices:
      v.co += v.normal * thickness
  ```
- Applies Blender's **Corrective Smooth** modifier to eliminate warping caused by uneven normals:
  - `smooth_type = 'LENGTH_WEIGHTED'`
  - `use_only_smooth = True`
  - `iterations` = per-slot value from `SHELL_SMOOTH_ITERS`
  - `factor` = per-slot value from `SHELL_SMOOTH_FACTOR`
- Recalculates normals outward.
- Produces a single-surface shell (no inner/outer walls like Solidify).

Current displace config:

| Slot         | Thickness | Smooth Iters | Smooth Factor |
|--------------|-----------|--------------|---------------|
| `upper_body` | 0.012 m   | 10           | 0.5           |
| `gloves`     | 0.015 m   | 10           | 0.5           |
| `lower_body` | 0.01 m    | 10           | 0.5           |
| `boots`      | 0.04 m    | 20           | 0.5           |

**Step 10 — UV unwrap**
- Applies Smart UV Project with `angle_limit=1.15192` (66 degrees) and `island_margin=0.02`.

**Step 11 — Export**
- Parents the shell mesh to the rig armature.
- Exports as a skinned GLB with:
  - `export_yup = True` (Y-up coordinate system for glTF compliance)
  - `export_skins = True`
  - `export_all_influences = True`
  - `export_def_bones = True`
  - `export_animations = False`

### Running the Extractor

**All five shells at once (using per-slot default thicknesses):**

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/body_shell_extractor.py -- \
  --rig-blend rig/output/rig.blend \
  --body-glb rig/CharacterMesh/BaseFemale.glb \
  --out equipment/output/shells/ \
  --thickness 0 \
  --slots head,upper_body,gloves,lower_body,boots
```

**A single shell (e.g. boots only):**

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/body_shell_extractor.py -- \
  --rig-blend rig/output/rig.blend \
  --body-glb rig/CharacterMesh/BaseFemale.glb \
  --out equipment/output/shells/ \
  --thickness 0 \
  --slots boots
```

**Copy to viewer after extraction:**

```bash
cp equipment/output/shells/shell_*.glb viewer/public/equipment/
```

### CLI Options

| Flag                | Default            | Description                                                   |
|---------------------|--------------------|---------------------------------------------------------------|
| `--rig-blend`       | (required)         | Path to the rig `.blend` file containing the armature         |
| `--body-glb`        | (required)         | Path to the Mixamo-rigged base character GLB                  |
| `--out`             | (required)         | Output directory for shell GLB files                          |
| `--thickness`       | 0.005              | Uniform thickness in meters; set `0` for per-slot defaults    |
| `--slots`           | all five           | Comma-separated slot names to extract                         |
| `--weight-threshold`| 0.1                | Min bone weight to include a vertex in a slot                 |
| `--game-out`        | none               | Optional second output directory (Y-up) for game engine use   |

---

## Viewer Integration

### equipment_spec.json Entries

Each shell has an entry in `viewer/public/equipment/equipment_spec.json`. These entries tell the viewer how to load, position, and render the shell.

**Head:**
```json
{
  "id": "shell_head",
  "name": "Shell: Head",
  "bilateral": false,
  "color": "#a78bfa",
  "bones": [
    { "name": "mixamorigHead", "weight": 1.0 },
    { "name": "mixamorigNeck", "weight": 0.25 }
  ],
  "bounds": { "z_min": 1.61, "z_max": 1.9, "radius": 0.13, "weight_radius": 0.2 },
  "rules": {},
  "hides_body_regions": ["head"],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/shell_head.glb"
}
```

**Upper Body:**
```json
{
  "id": "shell_upper_body",
  "name": "Shell: Upper Body",
  "bilateral": false,
  "color": "#60a5fa",
  "bones": [
    { "name": "mixamorigHips", "weight": 0.6 },
    { "name": "mixamorigSpine", "weight": 1.0 },
    { "name": "mixamorigSpine1", "weight": 1.0 },
    { "name": "mixamorigSpine2", "weight": 1.0 },
    { "name": "mixamorigLeftShoulder", "weight": 0.8 },
    { "name": "mixamorigRightShoulder", "weight": 0.8 },
    { "name": "mixamorigLeftArm", "weight": 1.0 },
    { "name": "mixamorigRightArm", "weight": 1.0 },
    { "name": "mixamorigLeftForeArm", "weight": 1.0 },
    { "name": "mixamorigRightForeArm", "weight": 1.0 },
    { "name": "mixamorigLeftHand", "weight": 0.1 },
    { "name": "mixamorigRightHand", "weight": 0.1 },
    { "name": "mixamorigNeck", "weight": 0.1 }
  ],
  "bounds": { "z_min": 1.01, "z_max": 1.54, "radius": 0.75, "weight_radius": 0.3 },
  "rules": {},
  "hides_body_regions": ["torso", "neck", "arms"],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/shell_upper_body.glb"
}
```

**Gloves:**
```json
{
  "id": "shell_gloves",
  "name": "Shell: Gloves",
  "bilateral": true,
  "color": "#34d399",
  "bones": [
    { "name": "mixamorigLeftHand", "weight": 1.0 },
    { "name": "mixamorigLeftHandThumb1", "weight": 1.0 },
    { "name": "mixamorigLeftHandThumb2", "weight": 1.0 },
    { "name": "mixamorigLeftHandThumb3", "weight": 1.0 },
    { "name": "mixamorigLeftHandIndex1", "weight": 1.0 },
    { "name": "mixamorigLeftHandIndex2", "weight": 1.0 },
    { "name": "mixamorigLeftHandIndex3", "weight": 1.0 },
    { "name": "mixamorigLeftHandMiddle1", "weight": 1.0 },
    { "name": "mixamorigLeftHandMiddle2", "weight": 1.0 },
    { "name": "mixamorigLeftHandMiddle3", "weight": 1.0 },
    { "name": "mixamorigLeftHandRing1", "weight": 1.0 },
    { "name": "mixamorigLeftHandRing2", "weight": 1.0 },
    { "name": "mixamorigLeftHandRing3", "weight": 1.0 },
    { "name": "mixamorigLeftHandPinky1", "weight": 1.0 },
    { "name": "mixamorigLeftHandPinky2", "weight": 1.0 },
    { "name": "mixamorigLeftHandPinky3", "weight": 1.0 },
    { "name": "mixamorigRightHand", "weight": 1.0 },
    { "name": "mixamorigRightHandThumb1", "weight": 1.0 },
    { "name": "mixamorigRightHandThumb2", "weight": 1.0 },
    { "name": "mixamorigRightHandThumb3", "weight": 1.0 },
    { "name": "mixamorigRightHandIndex1", "weight": 1.0 },
    { "name": "mixamorigRightHandIndex2", "weight": 1.0 },
    { "name": "mixamorigRightHandIndex3", "weight": 1.0 },
    { "name": "mixamorigRightHandMiddle1", "weight": 1.0 },
    { "name": "mixamorigRightHandMiddle2", "weight": 1.0 },
    { "name": "mixamorigRightHandMiddle3", "weight": 1.0 },
    { "name": "mixamorigRightHandRing1", "weight": 1.0 },
    { "name": "mixamorigRightHandRing2", "weight": 1.0 },
    { "name": "mixamorigRightHandRing3", "weight": 1.0 },
    { "name": "mixamorigRightHandPinky1", "weight": 1.0 },
    { "name": "mixamorigRightHandPinky2", "weight": 1.0 },
    { "name": "mixamorigRightHandPinky3", "weight": 1.0 }
  ],
  "bounds": { "z_min": 1.49, "z_max": 1.54, "radius": 0.20, "weight_radius": 0.15 },
  "rules": {},
  "hides_body_regions": ["hands"],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/shell_gloves.glb"
}
```

**Lower Body:**
```json
{
  "id": "shell_lower_body",
  "name": "Shell: Lower Body",
  "bilateral": true,
  "color": "#f87171",
  "bones": [
    { "name": "mixamorigHips", "weight": 1.0 },
    { "name": "mixamorigLeftUpLeg", "weight": 1.0 },
    { "name": "mixamorigRightUpLeg", "weight": 1.0 },
    { "name": "mixamorigLeftLeg", "weight": 0.8 },
    { "name": "mixamorigRightLeg", "weight": 0.8 }
  ],
  "bounds": { "z_min": 0.29, "z_max": 1.09, "radius": 0.18, "weight_radius": 0.15 },
  "rules": {},
  "hides_body_regions": ["torso", "legs"],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/shell_lower_body.glb"
}
```

**Boots:**
```json
{
  "id": "shell_boots",
  "name": "Shell: Boots",
  "bilateral": true,
  "color": "#fb923c",
  "bones": [
    { "name": "mixamorigLeftLeg", "weight": 0.6 },
    { "name": "mixamorigRightLeg", "weight": 0.6 },
    { "name": "mixamorigLeftFoot", "weight": 1.0 },
    { "name": "mixamorigRightFoot", "weight": 1.0 },
    { "name": "mixamorigLeftToeBase", "weight": 1.0 },
    { "name": "mixamorigRightToeBase", "weight": 1.0 }
  ],
  "bounds": { "z_min": -0.02, "z_max": 0.52, "radius": 0.12, "weight_radius": 0.12 },
  "rules": {},
  "hides_body_regions": ["feet", "legs"],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/shell_boots.glb"
}
```

### Rendering Pipeline

When the viewer loads a shell GLB, `EquipmentMeshRenderer.tsx` processes it:

1. **Coordinate correction** — Shell GLBs are exported Y-up; the viewer applies a Y-up to Z-up rotation (90 degrees around X) plus a scale factor of `1.9 / 1.75 = 1.0857` to match the character's display height.

2. **Embedded texture detection** — If the GLB's material already has a `map` (texture), it is preserved with `FrontSide` rendering and `polygonOffset`. Baked variants render with their embedded texture. Plain shells receive a flat-color `MeshStandardMaterial` using the slot's color from `SLOT_COLORS`.

3. **Skeleton rebinding** — The shell's skeleton bones are remapped from their original names (generic rig names like `hand_L`, `spine_01`) to Mixamo names (`mixamorigLeftHand`, `mixamorigSpine`) using `BONE_NAME_REMAP`. The bones are then rebound to the character's live animation skeleton using the character's rest-pose inverse bind matrices.

4. **Zero-weight repair** — Vertices with zero total skin weight are assigned to their nearest bone to prevent them from collapsing to the world origin.

5. **Cache busting** — Each GLB URL gets `?v=<timestamp>` appended so regenerated shells are fetched immediately.

### Stencil and Render Order

Shells use a stencil buffer strategy to handle visual layering at overlap regions:

| Shell          | Render Order | Stencil Behavior                        |
|----------------|--------------|-----------------------------------------|
| `shell_head`          | 3     | None                                    |
| `shell_upper_body`    | 1     | Writes `stencilRef = 1`                |
| `shell_gloves`        | 3     | None                                    |
| `shell_lower_body`    | 2     | Tests: renders only where ref != 1     |
| `shell_boots`         | 1     | Writes `stencilRef = 1`                |

Render order 1 draws first. Upper body and boots write to the stencil buffer. Lower body (render order 2) then only renders where upper body and boots have NOT written, preventing overlap artifacts.

### Base Body Stencil Masking

The base character mesh (rendered by `AnimationBridge.tsx`) also uses the stencil buffer to prevent the body from showing through shells during animation:

| Property        | Value                          |
|-----------------|--------------------------------|
| `renderOrder`   | 10 (renders after all shells)  |
| `stencilWrite`  | true                           |
| `stencilRef`    | 1                              |
| `stencilFunc`   | `NotEqualStencilFunc`          |
| `stencilFail`   | `KeepStencilOp`                |
| `stencilZFail`  | `KeepStencilOp`                |
| `stencilZPass`  | `KeepStencilOp`                |

The flow:
1. Shells with stencil write (upper body, boots) render first at renderOrder 1, writing `stencilRef = 1` wherever they draw pixels.
2. Lower body renders at renderOrder 2, only where ref != 1 (avoiding overlap with upper body/boots).
3. Remaining shells (head, gloves) render at renderOrder 3.
4. The base body mesh renders last at renderOrder 10 with `NotEqualStencilFunc` — it only draws pixels where NO shell has written to the stencil buffer. This prevents the body from poking through thin shell regions during animations (e.g. armpits, ankles).

---

## Texture Baking

The texture baker (`texture_baker.py`) transfers textures from a source 3D model onto any target mesh — shells or custom equipment. The original target file is never modified; the baker always produces a new `_textured.glb` file.

### Texture Sources

The baker needs a **source GLB with embedded textures** to project onto your target mesh. Here's how to provide one:

| Method | Best For | How |
|--------|----------|-----|
| **AI-generated model** | Production-quality textures with unique art | Generate a textured 3D model via [Meshy AI](https://meshy.ai), [Tripo](https://tripo3d.ai), or similar. Download the GLB and use it as `--source`. |
| **Hand-textured model** | Full artistic control | Create or texture a model in Blender/Substance Painter, export as GLB with embedded textures. |
| **Reference model** | Matching an existing asset's look | Use any textured GLB (armor from a game asset pack, a clothing model, etc.) as the source. The baker auto-aligns it to the target. |

The source model does **not** need to match the target's topology or rigging — the baker projects textures via ray casting, so any overlapping geometry works. Closer shape matches produce better coverage.

### Baking onto Shells

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/texture_baker.py -- \
  --source  path/to/textured_model.glb \
  --target  viewer/public/equipment/shell_upper_body.glb \
  --out     viewer/public/equipment/shell_upper_body_crimson.glb \
  --resolution 2048
```

### Baking onto Custom Equipment

For custom meshes, `--out` is optional. If omitted, the output is auto-named `<target_name>_textured.glb` in the same directory as the target:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/texture_baker.py -- \
  --source  path/to/textured_model.glb \
  --target  viewer/public/equipment/custom_upper_body_f.glb
```

This produces `viewer/public/equipment/custom_upper_body_f_textured.glb` — the original `custom_upper_body_f.glb` is untouched.

**Batch bake all custom pieces:**

```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
SCRIPT=equipment/factory/texture_baker.py
OUT=viewer/public/equipment

$BLENDER --background --python $SCRIPT -- \
  --source path/to/armor_upperbody.glb \
  --target $OUT/custom_upper_body_f.glb

$BLENDER --background --python $SCRIPT -- \
  --source path/to/armor_boots.glb \
  --target $OUT/custom_boots_f.glb

$BLENDER --background --python $SCRIPT -- \
  --source path/to/armor_gloves.glb \
  --target $OUT/custom_gloves_f.glb

$BLENDER --background --python $SCRIPT -- \
  --source path/to/armor_lowerbody.glb \
  --target $OUT/custom_lower_body_f.glb
```

### Adding a Textured Custom Mesh to the Viewer

After baking, register the textured variant as a new slot in `equipment_spec.json`:

```json
{
  "id": "custom_upper_body_f_textured",
  "name": "Custom Upper Body Textured (Female)",
  "bilateral": false,
  "color": "#93c5fd",
  "bones": [ /* copy from custom_upper_body_f entry */ ],
  "bounds": { /* copy from custom_upper_body_f entry */ },
  "rules": {},
  "hides_body_regions": ["torso", "neck", "arms"],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/custom_upper_body_f_textured.glb"
}
```

The viewer automatically detects the embedded texture and renders it instead of applying a flat color.

### What It Does

1. Imports both the source model (with textures) and the target mesh.
2. Auto-aligns the source to the target's bounding box.
3. Samples the source texture's average color as a fill color for ray misses.
4. Rewires the source's Principled BSDF to an Emission shader for raw color capture.
5. Uses Cycles "Selected to Active" EMIT bake to project the source's texture onto the target's UVs.
6. Replaces pure-black pixels (ray misses) with the sampled fill color.
7. Exports the target mesh with the baked texture embedded in a new GLB (original file unchanged).

### Baker CLI Options

| Flag               | Default | Description                                        |
|--------------------|---------|----------------------------------------------------|
| `--source`         | —       | Source GLB with textures (required)                |
| `--target`         | —       | Target mesh GLB — shell or custom (required). `--shell` also accepted for backward compatibility. |
| `--out`            | auto    | Output path. If omitted, generates `<target>_textured.glb` in the same directory. |
| `--texture-out`    | auto    | Standalone PNG path for the baked texture           |
| `--resolution`     | 2048    | Texture resolution in pixels                       |
| `--cage-extrusion` | 0.15    | Ray start distance from surface in meters          |
| `--samples`        | 4       | Cycles render samples                              |

### Tips for Best Results

- **Source coverage matters** — The bake only captures areas where the source mesh overlaps the target. If the source is a short vest, the target's sleeves will show the fill color.
- **Increase `--cage-extrusion`** for loosely fitting source models (e.g. `0.5` for armor with protruding details).
- **Resolution** — 2048 is a good default. Use 1024 for faster iteration, 4096 for production quality.
- **Source must have textures** — The baker reads from the source's material nodes. Vertex-color-only models will produce flat bakes.
- **Custom meshes need UVs** — If the custom mesh has no UV layer, the baker auto-generates one via Smart UV Project.

### Meshy AI Text-to-Texture Pipeline (Recommended)

The most reliable way to texture custom equipment is to have **Meshy AI texture your actual mesh** rather than generating a separate model and trying to transfer its texture. This guarantees the texture maps directly to your geometry with zero ray misses.

#### Why this is the recommended approach

| Approach | Pros | Cons |
|----------|------|------|
| **Meshy Text-to-Texture** (recommended) | Textures your exact mesh; 100% coverage; perfect UV mapping | Requires Meshy AI account |
| 3D Bake (`--source` mode) | Works with any textured model | Ray misses where shapes differ; distortion at boundaries |
| Image Apply (`--image` mode) | Fast; no baking needed | UV layout determines appearance; may look stretched |

#### Prerequisites

Before starting, you need a **custom mesh** for the target slot. Follow the [Custom Equipment Meshes](#custom-equipment-meshes) section to create one (edit a shell in Blender, weight-transfer it, and verify it works in the viewer). The Meshy pipeline textures this existing custom mesh — it does not create new geometry.

You will need:
- A working custom mesh GLB (e.g. `custom_upper_body_f.glb`) already in `viewer/public/equipment/`
- The corresponding shell GLB (e.g. `shell_upper_body.glb`) in `equipment/output/shells/`
- A [Meshy AI](https://meshy.ai) account

#### Per-slot reference

Use this table to look up the correct shell, bones, bounds, and stencil group for each slot type:

| Slot | Shell Source | Stencil Group | Render Order | `hides_body_regions` |
|------|-------------|---------------|--------------|----------------------|
| Head | `shell_head.glb` | `STENCIL_WRITE_SLOTS` | 3 | `["head"]` |
| Upper Body | `shell_upper_body.glb` | `STENCIL_WRITE_SLOTS` | 1 | `["torso", "neck", "arms"]` |
| Gloves | `shell_gloves.glb` | `STENCIL_WRITE_SLOTS` | 3 | `["hands"]` |
| Lower Body | `shell_lower_body.glb` | `STENCIL_TEST_SLOTS` | 2 | `["torso", "legs"]` |
| Boots | `shell_boots.glb` | `STENCIL_WRITE_SLOTS` | 1 | `["feet", "legs"]` |

Copy the `bones` and `bounds` arrays from the matching shell entry in `equipment_spec.json`.

---

#### Step-by-step workflow

The full pipeline has 7 steps. Each step is explained below with commands for every slot type.

**Step 1 — Export your custom mesh for upload**

Copy the already-working custom mesh. This is the mesh Meshy will texture — **upload the custom mesh, NOT the shell**.

```bash
# Upper Body
cp viewer/public/equipment/custom_upper_body_f.glb ~/Desktop/custom_upper_body_f.glb

# Head
cp viewer/public/equipment/custom_head_f.glb ~/Desktop/custom_head_f.glb

# Lower Body
cp viewer/public/equipment/custom_lower_body_f.glb ~/Desktop/custom_lower_body_f.glb

# Boots
cp viewer/public/equipment/custom_boots_f.glb ~/Desktop/custom_boots_f.glb

# Gloves
cp viewer/public/equipment/custom_gloves_f.glb ~/Desktop/custom_gloves_f.glb
```

**Step 2 — Upload to Meshy AI**

1. Go to [meshy.ai](https://meshy.ai) and sign in
2. Select **Text to Texture** (NOT Text-to-3D or Image-to-3D — only Text-to-Texture preserves your geometry)
3. Upload the custom mesh GLB from Step 1
4. Enter a prompt describing the texture you want, e.g.:
   > Medieval crimson and gold fantasy armor with ornate filigree details, dark leather underlayer, gemstone accents
5. Generate and wait for the result

> **Important:** Meshy's "Text to Texture" preserves your mesh geometry but may slightly change the face count (typically losing ~4% of faces) and can flip the vertex winding order on some faces. Both issues are handled automatically by the viewer.

**Step 3 — Download the textured GLB**

Meshy outputs a GLB with your mesh geometry + AI-generated textures baked into it. Download the GLB file.

**Step 4 — Place in the source directory**

```bash
# Upper Body example
cp ~/Downloads/meshy_output.glb \
  viewer/public/equipment/Female/Upperbody/UpperbodyCrimsonMeshy.glb

# Head example
cp ~/Downloads/meshy_output.glb \
  viewer/public/equipment/Female/Head/HeadCrimsonMeshy.glb

# Lower Body example
cp ~/Downloads/meshy_output.glb \
  viewer/public/equipment/Female/Lowerbody/LowerbodyCrimsonMeshy.glb

# Boots example
cp ~/Downloads/meshy_output.glb \
  viewer/public/equipment/Female/Boots/BootsCrimsonMeshy.glb

# Gloves example
cp ~/Downloads/meshy_output.glb \
  viewer/public/equipment/Female/Gloves/GlovesCrimsonMeshy.glb
```

**Step 5 — Run weight transfer with `--reference` alignment**

The Meshy output has no skeleton and may be at a different origin/scale than the original. Use `transfer_weights.py` with:
- `--source` — the shell GLB (provides bone weights + armature)
- `--target` — the Meshy-textured GLB (receives weights)
- `--reference` — the original custom mesh (provides correct position/scale)
- `--method surface` — recommended for Meshy meshes (copies known-good weights from the shell via nearest-polygon interpolation)
- `--output` — the final rigged GLB

The `--reference` flag is critical: it aligns the Meshy output to match the exact position and scale of the original custom mesh. Without it, the mesh may be misaligned because Meshy resets the origin on export.

```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
SCRIPT=equipment/factory/transfer_weights.py
SHELLS=equipment/output/shells
OUT=viewer/public/equipment

# Upper Body
$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_upper_body.glb \
  --target viewer/public/equipment/Female/Upperbody/UpperbodyCrimsonMeshy.glb \
  --reference viewer/public/equipment/custom_upper_body_f.glb \
  --method surface \
  --output $OUT/meshy_crimson_upperbody_f.glb

# Head
$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_head.glb \
  --target viewer/public/equipment/Female/Head/HeadCrimsonMeshy.glb \
  --reference viewer/public/equipment/custom_head_f.glb \
  --method surface \
  --output $OUT/meshy_crimson_head_f.glb

# Lower Body
$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_lower_body.glb \
  --target viewer/public/equipment/Female/Lowerbody/LowerbodyCrimsonMeshy.glb \
  --reference viewer/public/equipment/custom_lower_body_f.glb \
  --method surface \
  --output $OUT/meshy_crimson_lower_body_f.glb

# Boots
$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_boots.glb \
  --target viewer/public/equipment/Female/Boots/BootsCrimsonMeshy.glb \
  --reference viewer/public/equipment/custom_boots_f.glb \
  --method surface \
  --output $OUT/meshy_crimson_boots_f.glb

# Gloves
$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_gloves.glb \
  --target viewer/public/equipment/Female/Gloves/GlovesCrimsonMeshy.glb \
  --reference viewer/public/equipment/custom_gloves_f.glb \
  --method surface \
  --output $OUT/meshy_crimson_gloves_f.glb
```

**Step 6 — Register in equipment_spec.json**

Add a new slot entry in **both** spec files (`equipment/spec/equipment_spec.json` and `viewer/public/equipment/equipment_spec.json`). Copy the `bones` and `bounds` arrays from the matching custom mesh entry and update `id`, `name`, `color`, and `url`.

Example for Upper Body:

```json
{
  "id": "meshy_crimson_upperbody_f",
  "name": "Meshy Crimson Upperbody (Female)",
  "bilateral": false,
  "color": "#b91c1c",
  "bones": [
    { "name": "mixamorigHips", "weight": 0.6 },
    { "name": "mixamorigSpine", "weight": 1.0 },
    { "name": "mixamorigSpine1", "weight": 1.0 },
    { "name": "mixamorigSpine2", "weight": 1.0 },
    { "name": "mixamorigLeftShoulder", "weight": 0.8 },
    { "name": "mixamorigRightShoulder", "weight": 0.8 },
    { "name": "mixamorigLeftArm", "weight": 1.0 },
    { "name": "mixamorigRightArm", "weight": 1.0 },
    { "name": "mixamorigLeftForeArm", "weight": 1.0 },
    { "name": "mixamorigRightForeArm", "weight": 1.0 },
    { "name": "mixamorigLeftHand", "weight": 0.1 },
    { "name": "mixamorigRightHand", "weight": 0.1 },
    { "name": "mixamorigNeck", "weight": 0.1 }
  ],
  "bounds": { "z_min": 1.01, "z_max": 1.54, "radius": 0.75, "weight_radius": 0.3 },
  "rules": {},
  "hides_body_regions": ["torso", "neck", "arms"],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/meshy_crimson_upperbody_f.glb"
}
```

**Step 7 — Register in EquipmentMeshRenderer.tsx**

Add the new slot ID to the appropriate constants in `viewer/src/components/EquipmentMeshRenderer.tsx`. Use the [Per-slot reference](#per-slot-reference) table above to determine the correct stencil group and render order.

```typescript
// SLOT_RENDER_ORDER — add with the correct render order for the slot type
const SLOT_RENDER_ORDER: Record<string, number> = {
  // ... existing entries ...
  meshy_crimson_upperbody_f: 1,  // Upper Body → render order 1
};

// STENCIL_WRITE_SLOTS or STENCIL_TEST_SLOTS — add to the correct set
const STENCIL_WRITE_SLOTS = new Set([
  // ... existing entries ...
  "meshy_crimson_upperbody_f",   // Upper Body → WRITE
]);
```

| Slot Type | Add to | Render Order |
|-----------|--------|--------------|
| Head | `STENCIL_WRITE_SLOTS` | 3 |
| Upper Body | `STENCIL_WRITE_SLOTS` | 1 |
| Gloves | `STENCIL_WRITE_SLOTS` | 3 |
| Lower Body | `STENCIL_TEST_SLOTS` | 2 |
| Boots | `STENCIL_WRITE_SLOTS` | 1 |

---

#### How the viewer handles Meshy meshes

When the viewer loads a mesh with a baked texture (detected by checking if the material has a texture map), it automatically:

1. **Forces `DoubleSide` rendering** — Meshy's re-export can flip the vertex winding order on some faces. `DoubleSide` renders both front and back faces, preventing see-through artifacts on one side.
2. **Forces full opacity** — Sets `transparent: false`, `opacity: 1.0`, `alphaTest: 0` to override any transparency settings Meshy may have exported.
3. **Zeros PBR transmission** — Clears `transmission`, `thickness`, and `ior` properties in case Meshy exported glass-like materials.
4. **Handles multi-material meshes** — If the GLB has multiple materials, all of them receive the above fixes.

These overrides are applied in `EquipmentMeshRenderer.tsx` and require no manual configuration.

---

#### Key flags for `transfer_weights.py`

| Flag | Required | Description |
|------|----------|-------------|
| `--source` | Yes | Shell GLB (weight + armature donor). Must match the slot type. |
| `--target` | Yes | Meshy-textured GLB (receives weights). |
| `--output` | Yes | Output path for the rigged GLB. |
| `--reference` | Recommended | Original custom mesh GLB (provides correct position/scale). Use this when the Meshy output has a different origin. |
| `--method` | Optional | `surface` (recommended for Meshy), `auto`, or `bone`. Default: `auto`. |
| `--no-align` | Optional | Skip alignment entirely. Use only if the target is already in the correct coordinate space. |
| `--fit` | Optional | Scale multiplier for auto-alignment (default 0.85). Not used with `--reference`. |

**When to use `--reference` vs auto-alignment:**

- **Use `--reference`** (recommended) when you have the original custom mesh that Meshy textured. The script matches the Meshy output's bounding box to the reference's bounding box exactly.
- **Use auto-alignment** (no `--reference`) when you don't have the original mesh. The script aligns to the shell using bounding-box matching with the `--fit` scale factor.
- **Use `--no-align`** when the mesh is already in the correct position (rare).

---

#### Troubleshooting Meshy meshes

| Symptom | Cause | Fix |
|---------|-------|-----|
| Mesh is see-through on one side | Meshy flipped vertex winding order | The viewer handles this automatically with `DoubleSide` rendering. If you see this, ensure the slot's material override is active (check `hasBakedTexture` detection). |
| Mesh is too large or too small | Alignment used auto-fit instead of reference | Re-run with `--reference <original_custom_mesh.glb>` to match the original size exactly. |
| Mesh is positioned at the character's feet | Meshy reset the origin to the bottom of the mesh | Use `--reference` to align to the original custom mesh position. |
| Arms are rigid during animation | Weight transfer used `bone` or `auto` method | Re-run with `--method surface` which copies proven shell weights via nearest-polygon interpolation. |
| Texture looks correct but body clips through at edges | Normal gap between armor boundary and body — the armor doesn't cover the body at arm holes, neckline, and waist | This is expected for armor with openings. The stencil system hides the body where armor renders; gaps at openings are a mesh design limitation. |
| Mesh doesn't appear in the Equipment panel | Slot not registered in `equipment_spec.json` or `gender` doesn't match | Verify the entry exists in both spec files and `gender` matches the active character. |
| Mesh appears as solid color (no texture) | Texture map not detected | Ensure the Meshy GLB actually contains a texture (open in a GLB viewer). The viewer detects baked textures via `material.map != null`. |

---

#### End-to-end example: Meshy Crimson Upper Body (Female)

This is the exact workflow used to create the `meshy_crimson_upperbody_f` slot.

**1. Started with** `custom_upper_body_f.glb` — an already-working custom upper body mesh edited from `shell_upper_body.glb`.

**2. Uploaded** `custom_upper_body_f.glb` to Meshy AI → Text to Texture with the prompt:
> Medieval crimson and gold fantasy armor with ornate filigree details, dark leather underlayer, gemstone accents

**3. Downloaded** the textured GLB from Meshy and saved it as:
```
viewer/public/equipment/Female/Upperbody/UpperbodyCrimsonMeshy.glb
```

**4. Ran weight transfer** with `--reference` to match the original custom mesh position:
```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/transfer_weights.py -- \
  --source equipment/output/shells/shell_upper_body.glb \
  --target viewer/public/equipment/Female/Upperbody/UpperbodyCrimsonMeshy.glb \
  --reference viewer/public/equipment/custom_upper_body_f.glb \
  --method surface \
  --output viewer/public/equipment/meshy_crimson_upperbody_f.glb
```

**5. Added spec entry** to both `equipment/spec/equipment_spec.json` and `viewer/public/equipment/equipment_spec.json` (see Step 6 above for the full JSON).

**6. Registered in viewer code** — added `meshy_crimson_upperbody_f` to `SLOT_RENDER_ORDER` (value 1) and `STENCIL_WRITE_SLOTS` in `EquipmentMeshRenderer.tsx`.

**7. Verified** — hard-refreshed the viewer, equipped the slot, confirmed the mesh is fully opaque, correctly weighted, and follows animations.

---

#### Agent Quickstart: Adding a Meshy-textured GLB

For AI agents: this is the minimal, exact recipe. Given a Meshy-textured GLB at `viewer/public/equipment/Female/<Slot>/<Name>.glb`, execute these three steps:

**1. Weight transfer** — Run `transfer_weights.py` using the slot's shell as `--source`, the Meshy GLB as `--target`, and the existing custom mesh as `--reference`:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/transfer_weights.py -- \
  --source equipment/output/shells/<SHELL>.glb \
  --target viewer/public/equipment/Female/<Slot>/<MeshyFile>.glb \
  --reference viewer/public/equipment/<custom_SLOT_f>.glb \
  --method surface \
  --output viewer/public/equipment/<output_id>.glb
```

Lookup table for `<SHELL>` and `<custom_SLOT_f>`:

| Slot | Shell | Reference | Example output ID |
|------|-------|-----------|-------------------|
| Head | `shell_head.glb` | `custom_head_f.glb` | `meshy_crimson_head_f` |
| Upper Body | `shell_upper_body.glb` | `custom_upper_body_f.glb` | `meshy_crimson_upperbody_f` |
| Gloves | `shell_gloves.glb` | `custom_gloves_f.glb` | `meshy_crimson_gloves_f` |
| Lower Body | `shell_lower_body.glb` | `custom_lower_body_f.glb` | `meshy_crimson_lower_body_f` |
| Boots | `shell_boots.glb` | `custom_boots_f.glb` | `meshy_crimson_boots_f` |

**2. Add spec entry** — Add a JSON entry to **both** `equipment/spec/equipment_spec.json` and `viewer/public/equipment/equipment_spec.json`. Copy `bones`, `bounds`, `bilateral`, `hides_body_regions` from the matching `custom_<slot>_f` entry. Set a unique `id`, `name`, `color`, and `url` pointing to the output GLB.

**3. Register in viewer** — In `viewer/src/components/EquipmentMeshRenderer.tsx`:
- Add the new ID to `SLOT_RENDER_ORDER` with the correct render order (Head=3, Upper Body=1, Gloves=3, Lower Body=2, Boots=1).
- Add the new ID to `STENCIL_WRITE_SLOTS` (all slots except Lower Body, which goes in `STENCIL_TEST_SLOTS`).

That's it. The viewer automatically handles DoubleSide rendering, opacity forcing, and PBR overrides for any mesh with a baked texture.

---

## Duplicating a Shell for a New Character

To create the same five shells for a different character model (e.g. `BaseMale.glb`):

### Step 1 — Verify the character model

Ensure the new character model:
- Is Mixamo-rigged (vertex groups use `mixamorig:` prefix names)
- Is a skinned GLB with bone weights on all vertices
- Uses the same bone hierarchy as the existing character

### Step 2 — Run the extractor

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/body_shell_extractor.py -- \
  --rig-blend rig/output/rig.blend \
  --body-glb rig/CharacterMesh/BaseMale.glb \
  --out equipment/output/shells_male/ \
  --thickness 0 \
  --slots head,upper_body,gloves,lower_body,boots
```

### Step 3 — Copy to viewer

```bash
cp equipment/output/shells_male/shell_*.glb viewer/public/equipment/
```

Or use gender-specific paths:

```bash
mkdir -p viewer/public/equipment/Male/shells/
cp equipment/output/shells_male/shell_*.glb viewer/public/equipment/Male/shells/
```

### Step 4 — Add equipment_spec.json entries

For each shell, create a new entry in `viewer/public/equipment/equipment_spec.json`. Use the same structure as the existing entries but update:
- `id` — Use a unique ID (e.g. `shell_head_male`)
- `name` — Update display name
- `gender` — Set to `"male"`
- `url` — Point to the new file location

### Step 5 — Add slot colors

Add the new slot IDs to `SLOT_COLORS` in `viewer/src/types/equipment.ts`.

### Step 6 — Update render order / stencil sets (if needed)

If the new shells use the same layering strategy, add their IDs to the appropriate sets in `EquipmentMeshRenderer.tsx`:
- `SLOT_RENDER_ORDER` — Same render order values as the female equivalents
- `STENCIL_WRITE_SLOTS` — Add upper_body and boots variants
- `STENCIL_TEST_SLOTS` — Add lower_body variant

### Adjusting Thickness

If the new character has different proportions, you may need to adjust thicknesses. Edit `SHELL_THICKNESS` in `body_shell_extractor.py`:

```python
SHELL_THICKNESS: dict[str, float] = {
    "head": 0.005,        # 5 mm — solidify mode, tight fit for helmets/hats
    "upper_body": 0.012,  # 12 mm — displace mode, moderate offset for armor/shirts
    "lower_body": 0.01,   # 10 mm — displace mode, sits under boots at overlap
    "gloves": 0.015,      # 15 mm — displace mode, covers hands and forearms
    "boots": 0.04,        # 40 mm — displace mode, thick, sits outside pants
}
```

Or pass `--thickness <value>` to override all slots with a uniform thickness.

### Adjusting Corrective Smooth (Displace Slots Only)

If displacement warping is too severe or the mesh isn't smooth enough, adjust corrective smooth parameters:

```python
SHELL_SMOOTH_ITERS: dict[str, int] = {
    "head": 10,        # N/A for solidify, but present as default
    "upper_body": 10,
    "lower_body": 10,
    "gloves": 10,
    "boots": 20,       # Higher because foot/ankle geometry warps more
}

SHELL_SMOOTH_FACTOR: dict[str, float] = {
    "head": 0.5,
    "upper_body": 0.5,
    "lower_body": 0.5,
    "gloves": 0.5,
    "boots": 0.5,
}
```

Higher iterations smooth more aggressively but can reduce effective thickness. The stencil masking system prevents the body from showing through even if smoothing reduces thickness below the original displacement.

### Adjusting Overlap

If you need different overlap behavior, edit `OVERLAP_PAIRS` in `body_shell_extractor.py`:

```python
OVERLAP_PAIRS: list[tuple[str, str]] = [
    ("lower_body", "boots"),       # Pants + boots share shin
    ("upper_body", "lower_body"),  # Shirt extends past waist
    ("upper_body", "head"),        # Collar overlaps with head base
    ("upper_body", "gloves"),      # Sleeves overlap with wrist
]
```

To control how aggressively shells expand into each other's territory, adjust `OVERLAP_WEIGHT_THRESHOLD` (default 0.01; lower = more overlap).

---

## Custom Equipment Meshes

Custom equipment meshes are hand-edited versions of the generated body shells. Instead of using a shell as-is, you download it, reshape it in Blender to create a unique silhouette (crop, bisect, cap, sculpt, etc.), then re-import it into the viewer. Because the edited mesh no longer has the shell's original vertex weights, a weight-transfer step re-rigs it to the character skeleton so it deforms correctly during animation.

### Overview

| Step | Action | Tool |
|------|--------|------|
| 1 | Download the shell GLB for the target slot | Viewer (download button) or file system |
| 2 | Edit the mesh in Blender (bisect, cap, reshape) | Blender |
| 3 | Export the edited mesh as GLB from Blender | Blender |
| 4 | Place the exported GLB in the source directory | File system |
| 5 | Register the custom slot in `equipment_spec.json` | Text editor |
| 6 | Transfer weights from the original shell back onto the edited mesh | `transfer_weights.py` (Blender CLI) |

### Step 1 — Download the Shell

Get the generated shell GLB for the body region you want to customize. Either:

- Use the **download button** on the shell's row in the Equipment panel (the viewer exports the rigged GLB directly), or
- Copy the file from the file system:

```bash
cp equipment/output/shells/shell_upper_body.glb ~/Desktop/shell_upper_body.glb
```

Available shells to start from:

| Shell | File | Body Region |
|-------|------|-------------|
| Head | `shell_head.glb` | Skull, face, jaw |
| Upper Body | `shell_upper_body.glb` | Torso, arms, shoulders |
| Gloves | `shell_gloves.glb` | Forearms, hands, fingers |
| Lower Body | `shell_lower_body.glb` | Hips, thighs, shins |
| Boots | `shell_boots.glb` | Shins, feet, toes |

### Step 2 — Edit in Blender

Open the shell GLB in Blender and modify the mesh to create your custom equipment shape.

#### Common editing operations

**Bisect** — Cut the mesh along a plane to shorten it (e.g. turn full-length pants into shorts, or trim boot height):

1. Enter Edit Mode (`Tab`)
2. Select all geometry (`A`)
3. `Mesh → Bisect` — draw a cut line across the mesh
4. Check **Fill** and **Clear Inner** (or **Clear Outer**) to cap and remove the unwanted half

**Cap open boundaries** — If you deleted part of the mesh, the cut edges will be open. Close them:

1. Select the open edge loop (`Alt+Click` on a boundary edge)
2. `Face → Fill` (`F`) to create an n-gon cap
3. Optionally add a **Grid Fill** for cleaner topology

**Sculpting / reshaping** — Use Blender's sculpt tools or proportional editing to reshape the silhouette (e.g. add armor bulk, flare a skirt, etc.)

**Important**: Do NOT modify or delete the armature. The mesh's skeleton will be replaced during the weight-transfer step, but keeping it intact during editing ensures the mesh stays in the correct rest pose.

#### Blender export settings

When exporting from Blender:

1. `File → Export → glTF 2.0 (.glb)`
2. Ensure these settings:
   - **Format**: glTF Binary (`.glb`)
   - **Include → Selected Objects**: off (export everything)
   - **Transform → +Y Up**: checked (this is critical — the viewer expects Y-up GLBs)
3. Save as `<SlotName>.glb` (e.g. `Upperbody.glb`, `Boots.glb`)

> **+Y Up must be checked.** The viewer applies a Y-up to Z-up correction when loading equipment GLBs. If you export without Y-up, the mesh will appear sideways or face-down in the viewer.

### Step 3 — Place in Source Directory

Copy your exported GLB into the source directory under `rig/CharacterMesh/`, organized by gender and slot:

```
rig/CharacterMesh/
  Female/
    Head/
      Headglb.glb
    Upperbody/
      Upperbody.glb
    Gloves/
      Gloves.glb
    Lowerbody/
      Lowerbody.glb
    Boots/
      Boots.glb
  Male/
    Head/
      Head.glb
    Upperbody/
      Upperbody.glb
    ...
```

This is where the weight-transfer script reads the edited meshes from.

### Step 4 — Register in equipment_spec.json

Add a custom slot entry in **both** spec files:

- `equipment/spec/equipment_spec.json` (source of truth)
- `viewer/public/equipment/equipment_spec.json` (served to viewer)

The custom entry mirrors the corresponding shell entry but with a unique `id`, `name`, `color`, and `url` pointing to the custom GLB. Copy the `bones`, `bounds`, `hides_body_regions`, and stencil/render behavior from the matching shell.

#### Template

```json
{
  "id": "custom_<slot>_f",
  "name": "Custom <Slot Name> (Female)",
  "bilateral": <true|false>,
  "color": "<hex color>",
  "bones": [ /* copy from matching shell entry */ ],
  "bounds": { /* copy from matching shell entry */ },
  "rules": {},
  "hides_body_regions": [ /* copy from matching shell entry */ ],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/custom_<slot>_f.glb"
}
```

#### Naming convention

| Gender | Slot | ID | URL |
|--------|------|----|-----|
| Female | Head | `custom_head_f` | `/equipment/custom_head_f.glb` |
| Female | Upper Body | `custom_upper_body_f` | `/equipment/custom_upper_body_f.glb` |
| Female | Gloves | `custom_gloves_f` | `/equipment/custom_gloves_f.glb` |
| Female | Lower Body | `custom_lower_body_f` | `/equipment/custom_lower_body_f.glb` |
| Female | Boots | `custom_boots_f` | `/equipment/custom_boots_f.glb` |
| Male | Head | `custom_head_m` | `/equipment/custom_head_m.glb` |
| Male | Upper Body | `custom_upper_body_m` | `/equipment/custom_upper_body_m.glb` |
| ... | ... | ... | ... |

#### Viewer code registration

Custom slots must also be registered in `EquipmentMeshRenderer.tsx` to participate in stencil/render-order logic. Add the custom slot ID to the same groups as its parent shell:

```typescript
// SLOT_RENDER_ORDER — same render order as the parent shell
upper_body: 1, shell_upper_body: 1, custom_upper_body_f: 1,
boots: 1, shell_boots: 1, custom_boots_f: 1,

// STENCIL_WRITE_SLOTS — upper body and boots write stencil
"upper_body", "shell_upper_body", "custom_upper_body_f",
"boots", "shell_boots", "custom_boots_f",

// STENCIL_TEST_SLOTS — lower body tests stencil
"lower_body", "shell_lower_body", "custom_lower_body_f",
```

### Step 5 — Transfer Weights

The edited mesh has no vertex weights (or stale weights from the shell). The `transfer_weights.py` script copies weights from the original shell onto your edited mesh and re-parents it to the shell's armature, producing a GLB that the viewer processes identically to a generated shell.

#### How it works

1. **Imports** the source shell GLB (generated by `body_shell_extractor.py`) and the target edited GLB into Blender
2. **Transfers vertex weights** from the source mesh to the target using Blender's Data Transfer modifier with `POLYINTERP_NEAREST` mapping — this interpolates weights from the nearest source polygon, producing smooth deformation even on reshaped geometry
3. **Reparents** the target mesh to the source shell's armature — this gives the output the same skeleton format as the generated shells (legacy bone names like `pelvis`, identity-scale inverse bind matrices)
4. **Exports** with `export_yup=True` using the same export flags as `body_shell_extractor.py`

The output GLB matches the shell format exactly, so the viewer's skeleton binding, bone name remapping, and coordinate correction all work identically.

#### Running the weight transfer

**Single slot:**

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/transfer_weights.py -- \
  --source equipment/output/shells/shell_upper_body.glb \
  --target "rig/CharacterMesh/Female/Upperbody/Upperbody.glb" \
  --output viewer/public/equipment/custom_upper_body_f.glb
```

**All five slots:**

```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
SCRIPT=equipment/factory/transfer_weights.py
SHELLS=equipment/output/shells
SRC=rig/CharacterMesh/Female
OUT=viewer/public/equipment

$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_head.glb \
  --target "$SRC/Head/Headglb.glb" \
  --output $OUT/custom_head_f.glb

$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_upper_body.glb \
  --target "$SRC/Upperbody/Upperbody.glb" \
  --output $OUT/custom_upper_body_f.glb

$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_gloves.glb \
  --target "$SRC/Gloves/Gloves.glb" \
  --output $OUT/custom_gloves_f.glb

$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_lower_body.glb \
  --target "$SRC/Lowerbody/Lowerbody.glb" \
  --output $OUT/custom_lower_body_f.glb

$BLENDER --background --python $SCRIPT -- \
  --source $SHELLS/shell_boots.glb \
  --target "$SRC/Boots/Boots.glb" \
  --output $OUT/custom_boots_f.glb
```

#### CLI options

| Flag | Required | Description |
|------|----------|-------------|
| `--source` | Yes | Path to the generated shell GLB (weight + armature donor) |
| `--target` | Yes | Path to the user-edited GLB (receives weights) |
| `--output` | Yes | Output path for the re-weighted custom GLB |

#### Verifying the result

After running the weight transfer:

1. Refresh the viewer (`Cmd+Shift+R` / `Ctrl+Shift+R`)
2. Enable the custom slot in the Equipment panel
3. Play an animation — the custom mesh should follow the character smoothly with no clipping or gaps
4. Check boundary areas (wrists, waist, ankles) where the mesh was trimmed — these are most likely to show weight artifacts

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Mesh is sideways or face-down | Exported from Blender without **+Y Up** checked | Re-export with +Y Up enabled |
| Mesh doesn't appear at all | `url` in `equipment_spec.json` doesn't match the actual file path | Verify the URL matches and the GLB exists at `viewer/public/equipment/` |
| Mesh appears but deforms badly (clipping, gaps) | Weight transfer used wrong source or armature | Re-run `transfer_weights.py` with the correct `--source` shell for the slot |
| Mesh floats or is offset from the body | Edited mesh was moved in Blender (not at origin) | In Blender, apply transforms (`Ctrl+A → All Transforms`) before exporting |
| Vertices collapse to origin during animation | Some vertices have zero bone weight | `transfer_weights.py` should transfer weights to all vertices; if not, increase source shell coverage or manually paint weights in Blender |
| Mesh appears in the wrong slot's position | Used the wrong shell as `--source` (e.g. boots shell for upper body) | Match each slot to its corresponding shell: `shell_upper_body.glb` for upper body, etc. |
| Custom slot not visible in Equipment panel | `gender` field doesn't match the active character | Ensure the `gender` field is `"female"` or `"male"` matching the loaded character |

### End-to-End Example: Custom Female Boots

This example walks through creating shortened ankle boots from the full-height boot shell.

**1. Get the shell:**

```bash
cp equipment/output/shells/shell_boots.glb ~/Desktop/shell_boots_to_edit.glb
```

**2. Edit in Blender:**

- Open `shell_boots_to_edit.glb` in Blender
- Enter Edit Mode, select all, use `Mesh → Bisect` to cut at mid-shin height
- Check **Fill** and **Clear Outer** to remove the upper portion and cap the cut
- Optionally sculpt the ankle area for a cleaner silhouette
- Export as `Boots.glb` with **+Y Up** checked

**3. Place source file:**

```bash
cp ~/Desktop/Boots.glb rig/CharacterMesh/Female/Boots/Boots.glb
```

**4. Add spec entry** (add to both `equipment/spec/equipment_spec.json` and `viewer/public/equipment/equipment_spec.json`):

```json
{
  "id": "custom_boots_f",
  "name": "Custom Boots (Female)",
  "bilateral": true,
  "color": "#fdba74",
  "bones": [
    { "name": "mixamorigLeftLeg", "weight": 0.6 },
    { "name": "mixamorigRightLeg", "weight": 0.6 },
    { "name": "mixamorigLeftFoot", "weight": 1.0 },
    { "name": "mixamorigRightFoot", "weight": 1.0 },
    { "name": "mixamorigLeftToeBase", "weight": 1.0 },
    { "name": "mixamorigRightToeBase", "weight": 1.0 }
  ],
  "bounds": { "z_min": -0.02, "z_max": 0.52, "radius": 0.12, "weight_radius": 0.12 },
  "rules": {},
  "hides_body_regions": ["feet", "legs"],
  "mesh_type": "external",
  "mesh_params": {},
  "gender": "female",
  "url": "/equipment/custom_boots_f.glb"
}
```

**5. Transfer weights:**

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/transfer_weights.py -- \
  --source equipment/output/shells/shell_boots.glb \
  --target "rig/CharacterMesh/Female/Boots/Boots.glb" \
  --output viewer/public/equipment/custom_boots_f.glb
```

**6. Verify:**

- Refresh the viewer
- Enable "Custom Boots (Female)" in the Equipment panel
- Play an animation and confirm the boots deform correctly

---

## File Locations

| File | Purpose |
|------|---------|
| `equipment/factory/body_shell_extractor.py` | Shell extraction script (run via Blender CLI) |
| `equipment/factory/transfer_weights.py` | Weight transfer script for custom meshes (run via Blender CLI) |
| `equipment/factory/texture_baker.py` | Texture baking script (run via Blender CLI) |
| `equipment/output/shells/shell_*.glb` | Generated shell GLBs (extraction output) |
| `rig/CharacterMesh/Female/<Slot>/<Slot>.glb` | User-edited custom meshes (input to weight transfer) |
| `viewer/public/equipment/shell_*.glb` | Shell GLBs served to the viewer |
| `viewer/public/equipment/custom_*_f.glb` | Custom female equipment GLBs (weight-transfer output) |
| `viewer/public/equipment/custom_*_m.glb` | Custom male equipment GLBs (weight-transfer output) |
| `equipment/spec/equipment_spec.json` | Slot definitions (source of truth) |
| `viewer/public/equipment/equipment_spec.json` | Slot definitions loaded by the viewer (keep in sync) |
| `viewer/src/components/EquipmentMeshRenderer.tsx` | Viewer rendering logic for shells and custom equipment |
| `viewer/src/components/AnimationBridge.tsx` | Base body mesh rendering with stencil masking |
| `viewer/src/types/equipment.ts` | `SLOT_COLORS` and TypeScript types |
| `rig/output/rig.blend` | Canonical armature (input to extractor) |
| `rig/CharacterMesh/BaseFemale.glb` | Base character mesh (input to extractor) |
