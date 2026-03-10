# MMORPG Character Creation

Character creation pipeline for an MMORPG. Uses Mixamo-rigged GLB character
models loaded directly in a browser-based React Three Fiber viewer with
JSON-driven animation, Blender-style bone visualization, interactive bone
manipulation, equipment, tool attachment, and pose editing systems.

## Folder Structure

```
CharacterCreation/
  rig/
    CharacterMesh/
      BaseFemale.glb               # Mixamo-rigged female character model
      BaseFemale.fbx               # FBX source
      Textures/                    # Character textures
    spec/
      rig_spec.json                # Legacy skeleton definition
    factory/
      rig_factory.py               # CLI entry — loads spec, validates, builds armature
      extract_anim_node.mjs        # Node.js animation extraction utility
      validation.py                # validate_rig_spec() checks
      exporter.py                  # GLB / FBX / .blend export helpers
      anim_baker.py                # Animation baking utilities
      __init__.py
    output/                        # Generated files (.blend, .glb, .fbx)
  animations/
    specs/                         # Source animation JSON files
    factory/
      anim_factory.py              # Imports anim JSON into Blender Actions
      anim_validation.py           # Validates anim specs against rig
      __init__.py
  equipment/
    spec/
      equipment_spec.json          # Slot definitions, bone mappings, mesh params
    factory/
      mesh_factory.py              # Generates weighted placeholder meshes per slot
      validation.py                # Equipment spec validation
    output/                        # Generated per-slot GLB files
  viewer/                          # React Three Fiber web viewer
    src/
      components/
        Scene.tsx                  # R3F Canvas + lighting + controls
        SkeletonViewer.tsx         # Blender-style octahedral bone visualization
        BoneSidebar.tsx            # Scrollable bone list grouped by category
        BoneInfoPanel.tsx          # Bone transforms + P/R/S toolbar
        AnimationControls.tsx      # Transport bar: selector, play/pause, scrubber
        AnimationBridge.tsx        # Bridges animation player to React + mesh toggle
        EquipmentPanel.tsx         # Equipment slot toggles
        EquipmentMeshRenderer.tsx  # Renders equipment meshes on the rig
        ToolPanel.tsx              # Tool selection and transform controls
        ToolAttachment.tsx         # Attaches tool GLB models to bones
        PoseEditor.tsx             # Keyframe authoring and animation export
        ViewportErrorBoundary.tsx  # Error boundary for the 3D viewport
      hooks/
        useCharacterModel.ts       # Loads Mixamo GLB, extracts bone data
        useAnimationPlayer.ts      # Three.js AnimationMixer playback engine
        useTransformShortcuts.ts   # P/R/S keyboard shortcuts + gizmo modes
      types/
        index.ts                   # Rig types, CharacterModel, BONE_ALIAS_MAP
        animation.ts               # Animation TypeScript types
        equipment.ts               # Equipment slot and spec types
        tools.ts                   # Tool definitions and transforms
      styles/
        index.css                  # Global styles
    public/
      models/
        BaseFemale.glb             # Character model served to viewer
      animations/
        manifest.json              # Lists available animations for the viewer
        idle.anim.json             # Idle animation spec
      equipment/                   # Copied from equipment/output/ for serving
        equipment_spec.json        # Slot definitions
        *.glb                      # Per-slot placeholder meshes
  README.md
```

## Prerequisites

| Tool    | Version     | Purpose                                  |
|---------|-------------|------------------------------------------|
| Node.js | 18+         | Viewer dev server                        |
| npm     | 9+          | Package management                       |
| Blender | 3.6+ / 4.x | Armature generation & animation export (optional) |

---

## Quick Start

### Launch the web viewer

```bash
cd viewer
npm install
npm run dev          # opens http://localhost:5173
```

The viewer loads the Mixamo-rigged character model from `public/models/`,
plays animations from `public/animations/`, and supports interactive bone
selection, mesh/bone view toggling, and transform manipulation.

---

## Character Model

### Rig

The character uses a **Mixamo auto-rigged** skeleton embedded in a GLB file.
The viewer loads the GLB directly via Three.js `GLTFLoader` and extracts the
bone hierarchy, rest poses, and skinned meshes at runtime -- no separate rig
spec file is needed for the viewer.

The `useCharacterModel` hook handles loading:

```typescript
const { model, loading, error } = useCharacterModel("female");
```

It returns a `CharacterModel` containing the scene graph, bone maps, rest
pose data, and the bone hierarchy tree.

### Gender support

Model URLs are configured in `useCharacterModel.ts`:

| Gender   | Path                       |
|----------|----------------------------|
| `female` | `/models/BaseFemale.glb`   |
| `male`   | `/models/BaseMale.glb`     |

### Bone alias map

A `BONE_ALIAS_MAP` in `viewer/src/types/index.ts` maps legacy generic bone
names (e.g. `spine_01`, `hand_L`) to Mixamo names (e.g. `mixamorigSpine`,
`mixamorigLeftHand`). This allows equipment and legacy systems to reference
bones by either naming convention.

---

## Viewer Features

### Mesh / Bone toggle

A toggle in the viewport overlay switches between **Mesh** view (character
skin visible) and **Bone** view (skin hidden, skeleton only). Bone shapes
and joint spheres scale up in Bone view for better visibility.

### Bone visualization

The `SkeletonViewer` component renders the skeleton using Blender-style
**octahedral bone shapes** with wireframe edges and joint spheres. Bones are
color-coded:

| Category | Color   |
|----------|---------|
| Spine    | Blue    |
| Arm      | Green   |
| Leg      | Red     |
| Finger   | Yellow  |
| Face     | Purple  |
| Other    | Gray    |

Selected bones highlight in white. Clicking an octahedral shape or joint
sphere selects the corresponding bone.

### Bone selection and transforms

Click any bone in the viewport or the sidebar list to select it. The
**BoneInfoPanel** on the right shows:

- Bone name, parent, side, and category
- **Transform toolbar** with P (Position), R (Rotate), S (Scale) buttons
- Numeric inputs for position, rotation (Euler degrees), and scale overrides
- Copy button to export the current bone transform to clipboard
- Reset button to clear overrides

### Keyboard shortcuts

| Key | Action                                  |
|-----|-----------------------------------------|
| `P` | Enter Position mode (drag to translate) |
| `R` | Enter Rotate mode (drag to rotate)      |
| `S` | Enter Scale mode (drag to scale)        |

These work when a bone is selected and the viewport is focused.

---

## Animation System

### Overview

Animations are defined as JSON spec files (`*.anim.json`). Each file contains
metadata and an array of keyframe tracks targeting specific bones by their
**Mixamo names**. The viewer plays them in real-time using Three.js
`AnimationMixer`.

### Available animations

| ID     | Name | Duration | Loop |
|--------|------|----------|------|
| `idle` | Idle | 6.0s     | yes  |

### Animation JSON format

```json
{
  "meta": {
    "name": "Idle",
    "id": "idle",
    "duration": 6.0,
    "fps": 30,
    "loop": true
  },
  "tracks": [
    {
      "bone": "mixamorigSpine",
      "property": "rotation",
      "interpolation": "linear",
      "keyframes": [
        { "time": 0.0, "value": [0, 0, 0, 1] },
        { "time": 3.0, "value": [-0.01309, 0, 0, 0.99991] },
        { "time": 6.0, "value": [0, 0, 0, 1] }
      ]
    }
  ]
}
```

**Fields:**

| Field                    | Description                                              |
|--------------------------|----------------------------------------------------------|
| `meta.name`              | Human-readable display name                              |
| `meta.id`                | Unique identifier (matches filename without `.anim.json`)|
| `meta.duration`          | Clip length in seconds                                   |
| `meta.fps`               | Frames per second (used by Blender import)               |
| `meta.loop`              | Whether the animation loops                              |
| `tracks[].bone`          | Target bone name (Mixamo name, e.g. `mixamorigHips`)     |
| `tracks[].property`      | `"rotation"` (quaternion) or `"position"` (vec3)         |
| `tracks[].interpolation` | `"linear"` (slerp/lerp) or `"step"` (discrete)          |
| `tracks[].keyframes[]`   | Array of `{ time, value }` pairs                         |

**Value formats:**

- **Rotation**: delta quaternion as `[x, y, z, w]` (applied relative to the bone's rest pose)
- **Position**: `[x, y, z]` delta in meters from the bone's rest position

### Adding a new animation

1. Create `viewer/public/animations/<id>.anim.json` with `meta` and `tracks`
2. Add an entry to `viewer/public/animations/manifest.json`:
   ```json
   { "id": "<id>", "file": "<id>.anim.json", "loop": true }
   ```
3. The viewer will list it in the animation dropdown

### Viewer animation controls

The viewer includes a transport bar below the 3D viewport:

- **Dropdown** to select any animation from the manifest
- **Play / Pause / Stop** buttons
- **Scrubber** for seeking to any point in the timeline
- **Speed** buttons: 0.25x, 0.5x, 1x, 2x
- **Loop** toggle checkbox
- **Time display** showing current time / total duration

---

## Equipment System

### Overview

The equipment system defines body slots (head, amulet, gloves, ring, upper
body, lower body, boots) with bone mappings, spatial boundaries, visibility
rules, and mesh generation parameters. Placeholder meshes are generated in
Blender and displayed in the viewer, toggled per-slot.

### Available slots

| Slot ID      | Name        | Bilateral | Mesh Type   |
|--------------|-------------|-----------|-------------|
| `base_body`  | Base Body   | no        | `base_body` |
| `base_male`  | Base Male   | no        | `external`  |
| `base_female`| Base Female | no        | `external`  |
| `head`       | Head        | no        | `dome`      |
| `amulet`     | Amulet      | no        | `pendant`   |
| `gloves`     | Gloves      | yes       | `glove`     |
| `ring`       | Ring        | no        | `torus`     |
| `upper_body` | Upper Body  | no        | `torso`     |
| `lower_body` | Lower Body  | yes       | `pants`     |
| `boots`      | Boots       | yes       | `boot`      |

### Visibility rules

Slots can declare `hidden_by` rules. For example, the `ring` slot specifies
`"hidden_by": ["gloves"]`, meaning a ring is hidden when gloves are equipped.

### Adding a new equipment slot

1. Add the slot definition to `equipment/spec/equipment_spec.json`
2. Implement a mesh generator function in `equipment/factory/mesh_factory.py`
   if the slot uses a new `mesh_type`
3. Re-run the mesh factory to generate the new GLB

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
by manipulating bone transforms and capturing them at specific times. Finished
poses can be exported as `.anim.json` files compatible with the animation
system.

### Workflow

1. **Enable** the Pose Editor from the viewer UI
2. **Configure** the animation: name, ID, duration, FPS, and loop setting
3. **Set the current time** on the timeline
4. **Manipulate bones** using P/R/S shortcuts or the BoneInfoPanel numeric inputs
5. **Capture keyframe** -- saves all current bone overrides at the current time
6. Repeat steps 3-5 for additional keyframes
7. **Export** -- generates a `.anim.json` file ready to drop into
   `viewer/public/animations/`

### Export format

The exported JSON matches the animation spec format exactly. Euler angles are
converted to delta quaternions in `[x, y, z, w]` format relative to the
bone's rest pose.

---

## Mixamo Bone Naming Reference

### Categories and counts

| Category | Count | Bones                                                                 |
|----------|-------|-----------------------------------------------------------------------|
| spine    | 6     | Hips, Spine, Spine1, Spine2, Neck, Head                              |
| arm      | 8     | LeftShoulder/RightShoulder, LeftArm/RightArm, LeftForeArm/RightForeArm, LeftHand/RightHand |
| finger   | 30    | Thumb/Index/Middle/Ring/Pinky 1/2/3 x Left/Right                     |
| leg      | 8     | LeftUpLeg/RightUpLeg, LeftLeg/RightLeg, LeftFoot/RightFoot, LeftToeBase/RightToeBase |
| **Total**| **52+**|                                                                      |

All bone names are prefixed with `mixamorig` (e.g. `mixamorigHips`,
`mixamorigLeftArm`). Three.js `GLTFLoader` strips the colon from
`mixamorig:Hips` to produce `mixamorigHips`.

### Hierarchy

```
mixamorigHips (C)
  mixamorigSpine (C)
    mixamorigSpine1 (C)
      mixamorigSpine2 (C)
        mixamorigNeck (C)
          mixamorigHead (C)
        mixamorigLeftShoulder (L)
          mixamorigLeftArm (L)
            mixamorigLeftForeArm (L)
              mixamorigLeftHand (L)
                mixamorigLeftHandThumb1..3
                mixamorigLeftHandIndex1..3
                mixamorigLeftHandMiddle1..3
                mixamorigLeftHandRing1..3
                mixamorigLeftHandPinky1..3
        mixamorigRightShoulder (R)
          mixamorigRightArm (R)
            mixamorigRightForeArm (R)
              mixamorigRightHand (R)
                mixamorigRightHandThumb1..3
                mixamorigRightHandIndex1..3
                mixamorigRightHandMiddle1..3
                mixamorigRightHandRing1..3
                mixamorigRightHandPinky1..3
  mixamorigLeftUpLeg (L)
    mixamorigLeftLeg (L)
      mixamorigLeftFoot (L)
        mixamorigLeftToeBase (L)
  mixamorigRightUpLeg (R)
    mixamorigRightLeg (R)
      mixamorigRightFoot (R)
        mixamorigRightToeBase (R)
```

### Legacy bone alias map

The `BONE_ALIAS_MAP` in `viewer/src/types/index.ts` maps generic names used
by the legacy rig spec and equipment system to their Mixamo equivalents:

| Legacy Name     | Mixamo Name               |
|-----------------|---------------------------|
| `root` / `pelvis` | `mixamorigHips`        |
| `spine_01`      | `mixamorigSpine`          |
| `spine_02`      | `mixamorigSpine1`         |
| `spine_03`      | `mixamorigSpine2`         |
| `neck_01`       | `mixamorigNeck`           |
| `head`          | `mixamorigHead`           |
| `clavicle_L/R`  | `mixamorigLeftShoulder` / `mixamorigRightShoulder` |
| `upperarm_L/R`  | `mixamorigLeftArm` / `mixamorigRightArm`           |
| `lowerarm_L/R`  | `mixamorigLeftForeArm` / `mixamorigRightForeArm`   |
| `hand_L/R`      | `mixamorigLeftHand` / `mixamorigRightHand`          |
| `thigh_L/R`     | `mixamorigLeftUpLeg` / `mixamorigRightUpLeg`        |
| `shin_L/R`      | `mixamorigLeftLeg` / `mixamorigRightLeg`            |
| `foot_L/R`      | `mixamorigLeftFoot` / `mixamorigRightFoot`          |
| `toe_L/R`       | `mixamorigLeftToeBase` / `mixamorigRightToeBase`    |
| `thumb_01_L`..  | `mixamorigLeftHandThumb1`.. (all 30 finger bones)   |

---

## Blender Integration (Optional)

### Generate equipment meshes

```bash
blender --background --python equipment/factory/mesh_factory.py -- \
  --rig-spec rig/spec/rig_spec.json \
  --equip-spec equipment/spec/equipment_spec.json \
  --rig-blend rig/output/rig.blend \
  --out equipment/output/
```

### Import animations into Blender

```bash
blender --background --python animations/factory/anim_factory.py -- \
  --rig rig/output/rig.blend \
  --anims animations/specs/ \
  --out rig/output/rig_animated.blend \
  --export-glb rig/output/rig_animated.glb
```

---

## Axis Conventions

| Property         | Value                         |
|------------------|-------------------------------|
| Scale            | 1 unit = 1 meter              |
| Up axis (viewer) | +Y (Three.js / glTF)         |
| Up axis (Blender)| +Z                            |
| Rest pose        | T-pose                        |

The `useCharacterModel` hook applies a 90-degree X rotation to convert from
glTF's coordinate system to the viewer's expected orientation.
