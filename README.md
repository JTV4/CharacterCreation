# MMORPG Character Creation

Character creation pipeline for an MMORPG. Uses **Mixamo-rigged** GLB character
models loaded directly in a browser-based React Three Fiber viewer with
JSON-driven animation, Blender-style bone visualization, interactive bone
manipulation, equipment, tool attachment, and pose editing systems.

> **Rig**: All bones use Mixamo naming (e.g. `mixamorigHips`, `mixamorigLeftArm`).
> There is no legacy/generic bone system — everything references Mixamo names
> directly.

## Folder Structure

```
CharacterCreation/
  rig/
    CharacterMesh/
      BaseFemale.glb               # Mixamo-rigged female character model
      BaseFemale.fbx               # FBX source
      Textures/                    # Character textures
  equipment/
    spec/
      equipment_spec.json          # Slot definitions, bone mappings, mesh params
    factory/
      mesh_factory.py              # Generates weighted placeholder meshes per slot
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
        index.ts                   # Rig types, CharacterModel, ModelGender
        animation.ts               # Animation & manifest TypeScript types
        equipment.ts               # Equipment slot and spec types
        tools.ts                   # Tool definitions and transforms
      styles/
        index.css                  # Global styles
    public/
      models/
        BaseFemale.glb             # Character model served to viewer
      animations/
        manifest.json              # Characters + animation registry
        FemaleIdle.anim.json       # Female idle animation
        FemaleWalk.anim.json       # Female walk cycle
        FemaleRun.anim.json        # Female run cycle
      equipment/                   # Copied from equipment/output/ for serving
        equipment_spec.json        # Slot definitions
        *.glb                      # Per-slot placeholder meshes
  README.md
```

## Prerequisites

| Tool    | Version     | Purpose                    |
|---------|-------------|----------------------------|
| Node.js | 18+         | Viewer dev server          |
| npm     | 9+          | Package management         |

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
bone hierarchy, rest poses, and skinned meshes at runtime.

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

---

## Export System

The viewer includes an **Export** panel for downloading character assets.
Exports are split into two categories:

### Character Models (mesh + skeleton)

These GLB files contain the character mesh and skeleton. They are the
"base" files a game loads once at startup. Pair each with its default idle
animation.

| Character   | File             | Default Animation |
|-------------|------------------|-------------------|
| BaseFemale  | `BaseFemale.glb` | `FemaleIdle`      |
| BaseMale    | `BaseMale.glb`   | `MaleIdle`        |

### Animations (data only, no mesh)

Animation files are lightweight `.anim.json` specs containing only keyframe
data — no mesh or skeleton geometry. A game loads these on demand and applies
them to the already-loaded character skeleton.

| ID           | File                    | Duration | Loop |
|--------------|-------------------------|----------|------|
| `FemaleIdle` | `FemaleIdle.anim.json`  | 6.0s     | yes  |
| `FemaleWalk` | `FemaleWalk.anim.json`  | 1.0s     | yes  |
| `FemaleRun`  | `FemaleRun.anim.json`   | 0.65s    | yes  |

### Manifest format

The manifest at `viewer/public/animations/manifest.json` registers both
character models and animations:

```json
{
  "characters": [
    { "id": "BaseFemale", "model": "BaseFemale.glb", "defaultAnimation": "FemaleIdle" },
    { "id": "BaseMale", "model": "BaseMale.glb", "defaultAnimation": "MaleIdle" }
  ],
  "animations": [
    { "id": "FemaleIdle", "file": "FemaleIdle.anim.json", "loop": true },
    { "id": "FemaleWalk", "file": "FemaleWalk.anim.json", "loop": true },
    { "id": "FemaleRun", "file": "FemaleRun.anim.json", "loop": true }
  ]
}
```

### Game integration pattern

```
1. Load BaseFemale.glb  →  mesh + skeleton (one-time)
2. Load FemaleIdle.anim.json  →  apply as default animation
3. On walk:  load FemaleWalk.anim.json  →  swap animation (no mesh reload)
4. On run:   load FemaleRun.anim.json   →  swap animation (no mesh reload)
```

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

### Naming convention

Animation files follow the pattern `<Gender><Action>.anim.json`:

- `FemaleIdle`, `FemaleWalk`, `FemaleRun`
- `MaleIdle`, `MaleWalk`, `MaleRun`

The `id` and `name` in the meta block match the filename (without `.anim.json`).

### Animation JSON format

```json
{
  "meta": {
    "name": "FemaleIdle",
    "id": "FemaleIdle",
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

1. Create `viewer/public/animations/<Gender><Action>.anim.json` with `meta` and `tracks`
2. Add an entry to `viewer/public/animations/manifest.json` under `"animations"`:
   ```json
   { "id": "FemaleRun", "file": "FemaleRun.anim.json", "loop": true }
   ```
3. The viewer will list it in the animation dropdown and the Export panel

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

### Visibility rules

Slots can declare `hidden_by` rules. For example, the `ring` slot specifies
`"hidden_by": ["gloves"]`, meaning a ring is hidden when gloves are equipped.

---

## Tool Attachment System

The viewer supports attaching 3D tool models (loaded from remote GLB URLs) to
the character's hand bone. Tools can be positioned, rotated, and scaled using
on-screen gizmo controls or numeric inputs.

| ID            | Name        |
|---------------|-------------|
| `fishing_rod` | Fishing Rod |
| `hammer`      | Hammer      |
| `hatchet`     | Hatchet     |
| `pickaxe`     | Pickaxe     |

Tools are defined in `viewer/src/types/tools.ts`.

---

## Pose Editor

The Pose Editor allows authoring animation keyframes directly in the viewer
by manipulating bone transforms and capturing them at specific times. Finished
poses can be exported as `.anim.json` files compatible with the animation
system.

### Workflow

1. Enable the Pose Editor from the viewer UI
2. Configure the animation: name, ID, duration, FPS, and loop setting
3. Set the current time on the timeline
4. Manipulate bones using P/R/S shortcuts or the BoneInfoPanel numeric inputs
5. Capture keyframe — saves all current bone overrides at the current time
6. Repeat steps 3-5 for additional keyframes
7. Export — generates a `.anim.json` file ready to drop into
   `viewer/public/animations/`

---

## Mixamo Bone Naming Reference

All bone names use the `mixamorig` prefix. Three.js `GLTFLoader` strips the
colon from `mixamorig:Hips` to produce `mixamorigHips`.

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

### Categories

| Category | Count | Bones                                                                 |
|----------|-------|-----------------------------------------------------------------------|
| spine    | 6     | Hips, Spine, Spine1, Spine2, Neck, Head                              |
| arm      | 8     | LeftShoulder/RightShoulder, LeftArm/RightArm, LeftForeArm/RightForeArm, LeftHand/RightHand |
| finger   | 30    | Thumb/Index/Middle/Ring/Pinky 1/2/3 x Left/Right                     |
| leg      | 8     | LeftUpLeg/RightUpLeg, LeftLeg/RightLeg, LeftFoot/RightFoot, LeftToeBase/RightToeBase |
| **Total**| **52+**|                                                                      |

---

## Axis Conventions

| Property         | Value                   |
|------------------|-------------------------|
| Scale            | 1 unit = 1 meter        |
| Up axis (viewer) | +Z (Blender-like)       |
| Up axis (glTF)   | +Y                      |
| Rest pose        | T-pose                  |

The `useCharacterModel` hook applies a 90-degree X rotation to convert from
glTF's Y-up coordinate system to the viewer's Z-up orientation.
