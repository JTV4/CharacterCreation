# MMORPG Rig Factory

Deterministic humanoid skeleton generator for an MMORPG pipeline. Produces a
canonical 56-bone rig (including full hands and face bones) from a single JSON
specification, builds it in Blender, visualizes it in a browser-based React
Three Fiber viewer, and supports JSON-driven animation, equipment, tool
attachment, and pose editing systems.

## Folder Structure

```
CharacterCreation/
  rig/
    spec/
      rig_spec.json              # Canonical skeleton definition (56 bones)
    factory/
      rig_factory.py             # CLI entry — loads spec, validates, builds armature
      validation.py              # validate_rig_spec() checks
      exporter.py                # GLB / FBX / .blend export helpers
      anim_baker.py              # Animation baking utilities
      __init__.py
    output/                      # Generated files (.blend, .glb, .fbx)
  animations/
    specs/                       # One JSON file per animation clip
      idle.anim.json
      idle_combat.anim.json
      idle_ready.anim.json
      walk.anim.json
      run.anim.json
      attack_with_fist.anim.json
      attack_uppercut.anim.json
      attack_with_kick.anim.json
      attack_with_kick_left.anim.json
      chop_tree.anim.json
      fishing.anim.json
    factory/
      anim_factory.py            # Imports anim JSON into Blender Actions
      anim_validation.py         # Validates anim specs against rig
      __init__.py
  equipment/
    spec/
      equipment_spec.json        # Slot definitions, bone mappings, mesh params
    factory/
      mesh_factory.py            # Generates weighted placeholder meshes per slot
      validation.py              # Equipment spec validation
    output/                      # Generated per-slot GLB files
  viewer/                        # React Three Fiber web viewer
    src/
      components/
        Scene.tsx                # R3F Canvas + lighting + controls
        SkeletonViewer.tsx       # Renders bones as octahedral shapes
        BoneSidebar.tsx          # Scrollable bone list grouped by category
        BoneInfoPanel.tsx        # Selected bone metadata and transforms
        AnimationControls.tsx    # Transport bar: selector, play/pause, scrubber
        AnimationBridge.tsx      # Bridges animation player to React state
        EquipmentPanel.tsx       # Equipment slot toggles
        EquipmentMeshRenderer.tsx# Renders equipment meshes on the rig
        ToolPanel.tsx            # Tool selection and transform controls
        ToolAttachment.tsx       # Attaches tool GLB models to bones
        PoseEditor.tsx           # Keyframe authoring and animation export
      hooks/
        useSkeletonData.ts       # Loads rig_spec.json, builds bone tree
        useAnimationPlayer.ts    # Three.js AnimationMixer playback engine
        useTransformShortcuts.ts # Keyboard shortcuts for gizmo modes
      types/
        index.ts                 # Rig TypeScript types
        animation.ts             # Animation TypeScript types
        equipment.ts             # Equipment slot and spec types
        tools.ts                 # Tool definitions and transforms
      styles/
        index.css                # Global styles
    public/
      rig_spec.json              # Copied from rig/spec/ for serving
      rig.glb                    # Exported rig model
      animations/                # Copied from animations/specs/ for serving
        manifest.json            # Lists available animations for the viewer
        *.anim.json              # Animation spec files
        *.glb                    # Exported animation GLB files
      equipment/                 # Copied from equipment/output/ for serving
        equipment_spec.json      # Slot definitions
        *.glb                    # Per-slot placeholder meshes
  README.md
```

## Prerequisites

| Tool    | Version     | Purpose                                  |
|---------|-------------|------------------------------------------|
| Blender | 3.6+ / 4.x | Armature generation & animation export   |
| Node.js | 18+         | Viewer dev server                        |
| npm     | 9+          | Package management                       |

---

## Quick Start

### 1. Generate the rig in Blender (headless)

```bash
blender --background --python rig/factory/rig_factory.py -- \
  --spec rig/spec/rig_spec.json \
  --out rig/output/rig.blend \
  --export-glb rig/output/rig.glb
```

Optional FBX export:

```bash
blender --background --python rig/factory/rig_factory.py -- \
  --spec rig/spec/rig_spec.json \
  --out rig/output/rig.blend \
  --export-fbx rig/output/rig.fbx
```

### 2. Generate equipment meshes (headless)

```bash
blender --background --python equipment/factory/mesh_factory.py -- \
  --rig-spec rig/spec/rig_spec.json \
  --equip-spec equipment/spec/equipment_spec.json \
  --rig-blend rig/output/rig.blend \
  --out equipment/output/
```

This reads the rig and equipment specs, generates weighted placeholder meshes
for each slot, and exports individual GLB files into `equipment/output/`.

### 3. Run inside Blender GUI

1. Open Blender
2. Go to the **Scripting** workspace
3. Open `rig/factory/rig_factory.py`
4. When running inside the GUI, call the functions directly from the Python
   console instead of using CLI args:

```python
import json, sys, os
os.chdir("/path/to/CharacterCreation")
sys.path.insert(0, "rig/factory")
from rig_factory import load_spec, build_armature
from validation import validate_rig_spec

spec = load_spec("rig/spec/rig_spec.json")
validate_rig_spec(spec)
build_armature(spec)
```

### 4. Launch the web viewer

```bash
cd viewer
npm install
npm run copy-spec   # copies rig, animations, and equipment into public/
npm run dev          # opens http://localhost:5173
```

The viewer renders the skeleton directly from `rig_spec.json`, loads animation
specs from `public/animations/`, displays equipment meshes from
`public/equipment/`, and supports tool attachment and pose editing. No Blender
export is required for visualization or animation preview.

---

## Animation System

### Overview

Animations are defined as JSON spec files in `animations/specs/`, one file per
clip. Each file contains metadata and an array of keyframe tracks targeting
specific bones. The viewer plays them back in real-time using Three.js
`AnimationMixer`; a Blender script can import them as Actions for GLB/FBX
export.

### Available animations

| ID                      | Name               | Duration | Loop  |
|-------------------------|--------------------|----------|-------|
| `idle`                  | Idle               | 3.0s     | yes   |
| `idle_combat`           | IdleCombat         | 2.0s     | yes   |
| `idle_ready`            | IdleReady          | 2.0s     | yes   |
| `walk`                  | Walk               | 1.0s     | yes   |
| `run`                   | Run                | 0.7s     | yes   |
| `attack_with_fist`      | AttackWithFist     | 0.8s     | no    |
| `attack_uppercut`       | AttackUppercut     | 0.8s     | no    |
| `attack_with_kick`      | AttackWithKick     | 1.0s     | no    |
| `attack_with_kick_left` | AttackWithKickLeft | 1.0s     | no    |
| `chop_tree`             | ChopTree           | 1.2s     | yes   |
| `fishing`               | Fishing            | 10.0s    | yes   |

### Animation JSON format

```json
{
  "meta": {
    "name": "Walk",
    "id": "walk",
    "duration": 1.0,
    "fps": 30,
    "loop": true
  },
  "tracks": [
    {
      "bone": "thigh_L",
      "property": "rotation",
      "interpolation": "linear",
      "keyframes": [
        { "time": 0.0, "value": [0, 0, 0, 1] },
        { "time": 0.5, "value": [0.259, 0, 0, 0.966] },
        { "time": 1.0, "value": [0, 0, 0, 1] }
      ]
    }
  ]
}
```

**Fields:**

| Field                  | Description                                                      |
|------------------------|------------------------------------------------------------------|
| `meta.name`            | Human-readable display name                                      |
| `meta.id`              | Unique identifier (matches filename without `.anim.json`)        |
| `meta.duration`        | Clip length in seconds                                           |
| `meta.fps`             | Frames per second (used by Blender import)                       |
| `meta.loop`            | Whether the animation loops                                      |
| `tracks[].bone`        | Target bone name (must exist in `rig_spec.json`)                 |
| `tracks[].property`    | `"rotation"` (quaternion) or `"position"` (vec3, root only)     |
| `tracks[].interpolation` | `"linear"` (slerp/lerp) or `"step"` (discrete)               |
| `tracks[].keyframes[]` | Array of `{ time, value }` pairs                                |

**Value formats:**
- Rotation: quaternion as `[x, y, z, w]` (unit-length)
- Position: `[x, y, z]` in meters (only allowed on the `root` bone)

### Adding a new animation

1. Create `animations/specs/<id>.anim.json` with `meta` and `tracks`
2. Add an entry to `viewer/public/animations/manifest.json`
3. Run `npm run copy-spec` from `viewer/` (or copy the file manually)
4. The viewer will list it in the animation dropdown

### Import animations into Blender

```bash
blender --background --python animations/factory/anim_factory.py -- \
  --rig rig/output/rig.blend \
  --anims animations/specs/ \
  --out rig/output/rig_animated.blend \
  --export-glb rig/output/rig_animated.glb
```

This opens the rig `.blend`, creates a Blender Action for each animation spec
that has tracks, pushes them onto NLA strips, saves a new `.blend`, and
optionally exports to GLB or FBX with animation data baked in.

CLI flags:

| Flag           | Required | Description                                  |
|----------------|----------|----------------------------------------------|
| `--rig`        | yes      | Path to the rig `.blend` file                |
| `--anims`      | yes      | Directory of `.anim.json` files or one file  |
| `--rig-spec`   | no       | Path to `rig_spec.json` for validation       |
| `--out`        | yes      | Output `.blend` path                         |
| `--export-glb` | no       | Also export as GLB                           |
| `--export-fbx` | no       | Also export as FBX                           |

### Animation validation

`animations/factory/anim_validation.py` checks:

- All referenced bone names exist in the rig
- `property` is `"rotation"` or `"position"`
- Position tracks are only allowed on the `root` bone
- Keyframe times are sorted and within `[0, duration]`
- Quaternion values are unit-length (within 0.01 tolerance)
- No duplicate bone + property track combinations
- Meta fields are present and valid (duration > 0, fps > 0, loop is boolean)

### Viewer animation controls

The viewer includes a transport bar below the 3D viewport:

- **Dropdown** to select any animation from the manifest
- **Play / Pause / Stop** buttons
- **Scrubber** for seeking to any point in the timeline
- **Speed** buttons: 0.25x, 0.5x, 1x, 2x
- **Loop** toggle checkbox
- **Time display** showing current time / total duration

Animations with no keyframe tracks display a "No keyframes yet" indicator and
disable the play button.

---

## Equipment System

### Overview

The equipment system defines body slots (head, amulet, gloves, ring, upper
body, lower body, boots) with bone mappings, spatial boundaries, visibility
rules, and mesh generation parameters. Placeholder meshes are generated in
Blender and displayed in the viewer, toggled per-slot.

### Available slots

| Slot ID      | Name        | Bilateral | Mesh Type   | Bones                                 |
|--------------|-------------|-----------|-------------|---------------------------------------|
| `base_body`  | Base Body   | no        | `base_body` | pelvis, spine, neck, head, arms, legs |
| `base_male`  | Base Male   | no        | `external`  | pelvis, spine, neck, head, arms, legs |
| `base_female`| Base Female | no        | `external`  | pelvis, spine, neck, head, arms, legs |
| `head`       | Head       | no        | `dome`      | head, neck_01                         |
| `amulet`     | Amulet     | no        | `pendant`  | spine_03, neck_01                     |
| `gloves`     | Gloves     | yes       | `glove`    | hand + all finger bones (L & R)       |
| `ring`       | Ring       | no        | `torus`    | middle_01_L, middle_02_L              |
| `upper_body` | Upper Body | no        | `torso`    | spine chain, clavicles, arms, hands   |
| `lower_body` | Lower Body | yes       | `pants`    | pelvis, thighs, shins                 |
| `boots`      | Boots      | yes       | `boot`     | shins, feet, toes                     |

**Bilateral** slots define bones for the left side; the factory mirrors them
for the right side automatically.

### Visibility rules

Slots can declare `hidden_by` rules. For example, the `ring` slot specifies
`"hidden_by": ["gloves"]`, meaning a ring is hidden when gloves are equipped.

### Equipment spec format

```json
{
  "meta": {
    "version": "1.0.0",
    "description": "Equipment slot definitions...",
    "coordinate_system": { "up": "+Z", "forward": "+Y", "right": "+X", "scale": "meters" }
  },
  "slots": [
    {
      "id": "head",
      "name": "Head",
      "bilateral": false,
      "color": "#c084fc",
      "bones": [
        { "name": "head", "weight": 1.0 },
        { "name": "neck_01", "weight": 0.25 }
      ],
      "bounds": {
        "z_min": 1.48,
        "z_max": 1.75,
        "radius": 0.13,
        "weight_radius": 0.20
      },
      "rules": {},
      "mesh_type": "dome",
      "mesh_params": { "segments": 16, "rings": 8, "offset_z": 0.02 }
    }
  ]
}
```

**Slot fields:**

| Field           | Description                                                    |
|-----------------|----------------------------------------------------------------|
| `id`            | Unique slot identifier                                         |
| `name`          | Human-readable display name                                    |
| `bilateral`     | If true, bones are defined for L side and mirrored for R       |
| `color`         | Display color in the viewer                                    |
| `bones[]`       | Array of `{ name, weight }` pairs for vertex weighting         |
| `bounds`        | Spatial boundaries (`z_min`, `z_max`, `radius`, `weight_radius`) |
| `rules`         | Visibility rules (e.g. `hidden_by`)                            |
| `mesh_type`     | Generator to use (`dome`, `pendant`, `glove`, `torus`, `torso`, `pants`, `boot`) |
| `mesh_params`   | Type-specific parameters passed to the mesh generator          |

### Generate equipment meshes

```bash
blender --background --python equipment/factory/mesh_factory.py -- \
  --rig-spec rig/spec/rig_spec.json \
  --equip-spec equipment/spec/equipment_spec.json \
  --rig-blend rig/output/rig.blend \
  --out equipment/output/
```

| Flag            | Required | Description                                  |
|-----------------|----------|----------------------------------------------|
| `--rig-spec`    | yes      | Path to `rig_spec.json`                      |
| `--equip-spec`  | yes      | Path to `equipment_spec.json`                |
| `--rig-blend`   | yes      | Path to the rig `.blend` file                |
| `--out`         | yes      | Output directory for per-slot GLB files      |

### Skin external base body meshes

To weight external meshes (e.g. Base Male, Base Female) to the canonical rig and
export skinned GLBs with the rig included:

```bash
blender --background --python equipment/factory/skin_base_meshes.py -- \
  --rig-blend rig/output/rig.blend \
  --out equipment/output/ \
  --base-male-path rig/CharacterMesh/BaseMale.glb \
  --base-female-path rig/CharacterMesh/BaseFemale.glb
```

This imports your meshes, strips any existing armature, applies Blender's
automatic weights to our rig, and exports skinned GLBs (mesh + rig) to
`equipment/output/`. The output files work in the viewer and can be exported
from the Equipment Panel.

**Optional:** Add `--game-out equipment/output/game` to also export Y-up GLBs
for game engines. Then run `npm run copy-spec` to sync the game folder.

| Flag               | Required | Description                                  |
|---------------------|----------|----------------------------------------------|
| `--rig-blend`       | yes      | Path to the rig `.blend` file                |
| `--out`             | yes      | Output directory for skinned GLB files       |
| `--base-male-path`  | no       | Local path to Base Male GLB                   |
| `--base-female-path`| no       | Local path to Base Female GLB                |
| `--base-male-url`   | no       | URL for Base Male (used if path not set)     |
| `--base-female-url` | no       | URL for Base Female (used if path not set)   |
| `--game-out`        | no       | Also export Y-up GLBs here for game engines  |
| `--scale`           | no       | Scale factor for imported meshes (default 1.0) |
| `--male-only`       | no       | Only process Base Male                       |
| `--female-only`     | no       | Only process Base Female                     |

After skinning, run `npm run copy-spec` from `viewer/` to sync the GLB files.
The viewer Equipment Panel lets you toggle between Base Body (procedural),
Base Male, and Base Female — only one body variant is shown at a time.

### Adding a new equipment slot

1. Add the slot definition to `equipment/spec/equipment_spec.json`
2. Implement a mesh generator function in `equipment/factory/mesh_factory.py`
   if the slot uses a new `mesh_type`
3. Re-run the mesh factory to generate the new GLB
4. Run `npm run copy-spec` from `viewer/` to sync to the viewer

---

## Tool Attachment System

### Overview

The viewer supports attaching 3D tool models (loaded from remote GLB URLs) to
the character's hand bone. Tools can be positioned, rotated, and scaled using
on-screen gizmo controls or numeric inputs.

### Available tools

| ID            | Name        |
|---------------|-------------|
| `fishing_rod` | Fishing Rod |
| `hammer`      | Hammer      |
| `hatchet`     | Hatchet     |
| `pickaxe`     | Pickaxe     |

Tools are defined in `viewer/src/types/tools.ts`. Each tool has an `id`,
display `name`, remote `url` (GLB), and a display `color`.

### Tool controls

When a tool is equipped the Tool Panel exposes:

- **Gizmo mode** buttons: Translate (T), Rotate (R), Scale (S)
- **Position** XYZ numeric inputs (step 0.01)
- **Rotation** XYZ numeric inputs in degrees (step 1)
- **Scale** uniform numeric input (step 0.01)
- **Reset** button to restore default transform

Keyboard shortcuts for gizmo modes work when the viewport is focused:
`T` for translate, `R` for rotate, `S` for scale.

### Adding a new tool

1. Add a new entry to the `TOOLS` array in `viewer/src/types/tools.ts`:
   ```json
   { "id": "sword", "name": "Sword", "url": "https://...", "color": "#f472b6" }
   ```
2. The tool will appear in the Tool Panel automatically

---

## Pose Editor

### Overview

The Pose Editor allows authoring animation keyframes directly in the viewer
by manipulating bone rotations and capturing them at specific times. Finished
poses can be exported as `.anim.json` files compatible with the animation
system.

### Workflow

1. **Enable** the Pose Editor from the viewer UI
2. **Configure** the animation: name, ID, duration, FPS, and loop setting
3. **Set the current time** on the timeline
4. **Rotate bones** using the bone transform controls
5. **Capture keyframe** — saves all current bone overrides at the current time
6. Repeat steps 3–5 for additional keyframes
7. **Export** — generates a `.anim.json` file ready to drop into
   `animations/specs/`

### Keyframe data

Each keyframe stores Euler angles (degrees) per bone. On export, the Pose
Editor converts these to unit quaternions in the standard `[x, y, z, w]`
format used by the animation system.

### Export format

The exported JSON matches the animation spec format exactly, so the file can
be placed directly into `animations/specs/` and added to the manifest.

---

## Axis Conventions

| Property         | Value                         |
|------------------|-------------------------------|
| Scale            | 1 unit = 1 meter              |
| Up axis          | +Z                            |
| Forward axis     | +Y                            |
| Right axis       | +X                            |
| Mirror rule      | **Left = -X**, Right = +X     |
| Rest pose        | T-pose                        |
| Character height | 1.75 m                        |

### Blender coordinate system note

Blender's 3D viewport uses **+Z up** and **-Y forward** by default (front
view, Numpad 1, looks from +Y toward -Y). In this rig the character's nose
points toward **+Y**, so in Blender's front view you see the character's back.
Use **Numpad 3** (right view) or rotate the view to see the front.

When exporting:

- **GLB/glTF**: The exporter converts to glTF's Y-up convention automatically
  (`export_yup=True`).
- **FBX (Unreal/Unity)**: The exporter applies axis conversion
  (`axis_forward="-Z"`, `axis_up="Y"`).

---

## Bone Naming Reference

### Categories and counts

| Category   | Count  | Bones                                                              |
|------------|--------|--------------------------------------------------------------------|
| other      | 1      | root                                                               |
| spine      | 6      | pelvis, spine_01, spine_02, spine_03, neck_01, head                |
| face       | 3      | jaw, eye_L, eye_R                                                  |
| arm        | 8      | clavicle_L/R, upperarm_L/R, lowerarm_L/R, hand_L/R                |
| finger     | 30     | thumb/index/middle/ring/pinky _01/_02/_03 x L/R                   |
| leg        | 8      | thigh_L/R, shin_L/R, foot_L/R, toe_L/R                            |
| **Total**  | **56** |                                                                    |

### Hierarchy

```
root (C)
  pelvis (C)
    spine_01 (C)
      spine_02 (C)
        spine_03 (C)
          neck_01 (C)
            head (C)
              jaw (C)
              eye_L (L)
              eye_R (R)
          clavicle_L (L)
            upperarm_L (L)
              lowerarm_L (L)
                hand_L (L)
                  thumb_01_L .. thumb_03_L
                  index_01_L .. index_03_L
                  middle_01_L .. middle_03_L
                  ring_01_L .. ring_03_L
                  pinky_01_L .. pinky_03_L
          clavicle_R (R)
            upperarm_R (R)
              lowerarm_R (R)
                hand_R (R)
                  (same finger pattern as L)
    thigh_L (L)
      shin_L (L)
        foot_L (L)
          toe_L (L)
    thigh_R (R)
      shin_R (R)
        foot_R (R)
          toe_R (R)
```

### Mirror pairs (24 pairs)

All bones ending in `_L` have a corresponding `_R` counterpart with the X
coordinate negated. The full list is in `rig_spec.json` under `mirror_pairs`.

---

## Rig Validation

`rig/factory/validation.py` — `validate_rig_spec()` checks:

- All bone names are unique
- All parent references resolve to existing bones
- No cycles in the hierarchy
- Every `_L` bone has a matching `_R` in `mirror_pairs`
- L/R pairs have correctly mirrored X positions (within 0.001 m tolerance)
- All required bones from the canonical list are present
- Exactly 15 finger bones per hand (5 digits x 3 joints)

---

## Extending the Rig

To add new bones:

1. Add the bone entry to `rig/spec/rig_spec.json` (follow the existing format)
2. If it's an L/R pair, add both sides and an entry in `mirror_pairs`
3. Update the `REQUIRED_BONES` set in `validation.py` if the bone is mandatory
4. Re-run the factory script and refresh the viewer

To adjust proportions, modify the `head` and `tail` positions in the spec.
The factory script will reproduce the exact same rig deterministically.

## Extending Animations

To add a new animation clip:

1. Create `animations/specs/<id>.anim.json` following the format above
2. Add an entry to `viewer/public/animations/manifest.json`:
   `{ "id": "<id>", "file": "<id>.anim.json" }`
3. Run `npm run copy-spec` from `viewer/` to sync files
4. Optionally import into Blender with `anim_factory.py` for GLB/FBX export

To author keyframes for an existing stub, either:
- Populate the `tracks` array manually in the `.anim.json` file
- Use the **Pose Editor** in the viewer to author keyframes visually and export
