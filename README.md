# MMORPG Character Creation

Character creation pipeline for an MMORPG. Uses **Mixamo-rigged** GLB character
models loaded directly in a browser-based React Three Fiber viewer with
JSON-driven animation, Blender-style bone visualization, interactive bone
manipulation, equipment with interactive mesh positioning, tool attachment,
and pose editing systems.

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
      Female/                      # User-edited custom meshes (per-slot)
        Head/Headglb.glb
        Upperbody/Upperbody.glb
        Gloves/Gloves.glb
        Lowerbody/Lowerbody.glb
        Boots/Boots.glb
    output/
      rig.blend                    # Canonical armature with generic bone names
  equipment/
    spec/
      equipment_spec.json          # Slot definitions, bone mappings, mesh params
    factory/
      body_shell_extractor.py      # Generates per-slot body shells from base mesh
      transfer_weights.py          # Transfers weights from shells to custom meshes
      texture_baker.py             # Bakes textures from source models onto shells
      equipment_fitter.py          # Fits external meshes to character skeleton
    output/
      shells/                      # Generated body shell GLB files
        shell_head.glb
        shell_upper_body.glb
        shell_gloves.glb
        shell_lower_body.glb
        shell_boots.glb
  viewer/                          # React Three Fiber web viewer
    src/
      components/
        Scene.tsx                  # R3F Canvas + lighting + controls
        SkeletonViewer.tsx         # Blender-style octahedral bone visualization
        BoneSidebar.tsx            # Scrollable bone list grouped by category
        BoneInfoPanel.tsx          # Bone transforms + P/R/S toolbar
        MeshInfoPanel.tsx          # Equipment mesh transforms + T/R/S gizmo + Copy
        AnimationControls.tsx      # Transport bar: selector, play/pause, scrubber
        AnimationBridge.tsx        # Bridges animation player to React + mesh toggle
        EquipmentPanel.tsx         # Equipment slot toggles + selection
        EquipmentMeshRenderer.tsx  # Renders equipment meshes on the rig + gizmo
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
        equipment.ts               # Equipment slot and spec types + SLOT_COLORS
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
        shell_*.glb                # Body shell meshes (per-slot)
        shell_*_<variant>.glb      # Baked textured shell variants
        custom_*_f.glb             # Custom female equipment (weight-transferred)
        custom_*_m.glb             # Custom male equipment (weight-transferred)
        *_diffuse.png              # Standalone baked texture files
        *.glb                      # Other per-slot equipment meshes
  README.md
```

## Prerequisites

| Tool    | Version     | Purpose                                          |
|---------|-------------|--------------------------------------------------|
| Node.js | 18+         | Viewer dev server                                |
| npm     | 9+          | Package management                               |
| Blender | 3.6+        | Body shell extraction and texture baking (CLI)   |

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

### Mesh Inspector

Click any enabled equipment mesh in the 3D viewport (or click its row in the
Equipment panel) to select it. The **MeshInfoPanel** on the right shows:

- **Identity** — mesh name, slot ID, mesh type, bilateral flag, bone count,
  and gender filter
- **Transform toolbar** with T (Translate), R (Rotate), S (Scale) gizmo mode
  buttons
- Numeric inputs for position, rotation (Euler degrees), and uniform scale
- **Copy** button — exports the current mesh transform to the clipboard in a
  paste-friendly format:
  ```
  Equipment: crimson_wizard_boots
  Name: Crimson Wizard Boots
  Position: [0.0000, 0.0500, -0.0200]
  Rotation: [0.00, 10.00, 0.00]
  Scale: 1.0000
  ```
- **Reset** button to return the mesh to its default position

The 3D gizmo (colored arrows / rings / scale handles) appears on the selected
mesh in the viewport. Drag to reposition, then Copy the values.

Under the hood, mesh transforms are applied by modifying each `SkinnedMesh`'s
**bind matrix** every frame, which is the correct way to offset skinned meshes
that share bones with the character skeleton.

### Equipment GLB download

Each equipment slot in the Equipment panel has a download button that exports
the slot's rigged GLB file directly from the browser. Downloaded files retain
the full skeleton and skinning data, making them ready for import into
Blender, game engines, or AI texturing services.

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
rules, and mesh generation parameters. Equipment meshes come in three forms:

- **Body shells** — Generated from the base character mesh using
  `body_shell_extractor.py`. These conform perfectly to the character and
  serve as base geometry for AI texturing. See [Body Shell System](#body-shell-system).
- **Custom meshes** — Hand-edited versions of body shells, reshaped in Blender
  and re-weighted using `transfer_weights.py`. See the Custom Equipment Meshes
  section in `equipment/SHELLS.md` for the full workflow.
- **External meshes** — Loaded from remote URLs (e.g. Cloudinary). These are
  pre-authored 3D models fitted to the character.
- **Local meshes** — GLB files in `viewer/public/equipment/`.

Equipment meshes can be **selected and repositioned** in the viewport using
the Mesh Inspector panel and 3D transform gizmos. This allows visual
positioning of new meshes, after which the transform values can be copied and
fed back into the spec.

### Generic Slots

| Slot ID      | Name       | Bones                          | Color   |
|--------------|------------|--------------------------------|---------|
| `head`       | Head       | Head                           | Purple  |
| `amulet`     | Amulet     | Neck, Head, Spine2             | Slate   |
| `upper_body` | Upper Body | Spine chain, shoulders, arms   | Blue    |
| `lower_body` | Lower Body | Hips, legs                     | Red     |
| `boots`      | Boots      | Feet, toes, lower legs         | Orange  |
| `gloves`     | Gloves     | Hands + all finger bones (L/R) | Green   |
| `ring`       | Ring       | Ring finger bones (L)          | Yellow  |

### Body Shell Slots

| Slot ID            | Name             | Bones                   | Thickness |
|--------------------|------------------|-------------------------|-----------|
| `shell_head`       | Shell Head       | Head, neck, jaw, eyes   | 5 mm      |
| `shell_upper_body` | Shell Upper Body | Spine, arms             | 5 mm      |
| `shell_gloves`     | Shell Gloves     | Forearms, hands, fingers| 30 mm     |
| `shell_lower_body` | Shell Lower Body | Hips, legs, feet, toes  | 5 mm      |
| `shell_boots`      | Shell Boots      | Shins, feet, toes       | 60 mm     |

These are auto-generated by `body_shell_extractor.py` and have
`"mesh_type": "external"` in the equipment spec.

### Crimson Wizard Set (Female)

| Slot ID                    | Name                     | Type   |
|----------------------------|--------------------------|--------|
| `crimson_wizard_robe`      | Crimson Wizard Robe      | torso  |
| `crimson_wizard_hat`       | Crimson Wizard Hat       | dome   |
| `crimson_wizard_robe_bottom` | Crimson Wizard Robe Bottom | pants |
| `crimson_wizard_gloves`    | Crimson Wizard Gloves    | glove  |
| `crimson_wizard_boots`     | Crimson Wizard Boots     | boot   |

These slots have `"gender": "female"` and load meshes from remote Cloudinary
URLs specified in their `url` field. They only appear in the Equipment panel
when the Female model is active.

Slot definitions live in `equipment_spec.json` and use Mixamo bone names.

### equipment_spec.json format

Each slot is a JSON object in the top-level array:

```json
{
  "id": "shell_boots",
  "name": "Shell: Boots",
  "bilateral": false,
  "color": "#fb923c",
  "gender": "female",
  "bones": [
    { "name": "mixamorigLeftLeg", "weight": 1.0 },
    { "name": "mixamorigLeftFoot", "weight": 1.0 }
  ],
  "bounds": { "z_min": 0.0, "z_max": 0.5, "radius": 0.15 },
  "rules": {},
  "hides_body_regions": ["feet"],
  "mesh_type": "external",
  "mesh_params": {},
  "url": "/equipment/shell_boots.glb"
}
```

| Field                | Type     | Description                                                   |
|----------------------|----------|---------------------------------------------------------------|
| `id`                 | string   | Unique slot identifier (used as cache key and file fallback)  |
| `name`               | string   | Display name in the Equipment panel                           |
| `bilateral`          | boolean  | Whether the slot has left/right variants                      |
| `color`              | string   | Hex color for the slot's panel indicator                      |
| `gender`             | string?  | `"male"` or `"female"` — omit for gender-neutral slots       |
| `bones`              | array    | Mixamo bone names with influence weights                      |
| `bounds`             | object   | Spatial bounding box (`z_min`, `z_max`, `radius`)             |
| `rules`              | object   | Visibility rules (e.g. `"hidden_by": ["gloves"]`)            |
| `hides_body_regions` | array?   | Body regions to hide when equipped                            |
| `mesh_type`          | string   | `"external"` (GLB with URL), `"cylinder"`, `"dome"`, etc.    |
| `mesh_params`        | object   | Parameters for procedural mesh generation                     |
| `url`                | string?  | GLB URL — if absent, loads from `/equipment/{id}.glb`         |
| `source`             | string?  | `"imported"` for runtime-loaded meshes (set by viewer)        |

The spec is stored in two locations that must be kept in sync:
- `equipment/spec/equipment_spec.json` — source of truth
- `viewer/public/equipment/equipment_spec.json` — served to the viewer

### Equipment mesh binding

`EquipmentMeshRenderer` loads per-slot GLB files and binds them to the
character's Mixamo skeleton at runtime:

1. **GLB loading** — Each slot's mesh is loaded via `GLTFLoader` and cached
   in a module-level `slotCache`. External meshes (those with a `url` field)
   get a Y-up to Z-up correction; local meshes get a 180-degree Z rotation
   to correct facing direction.
2. **Skeleton rebinding** — The equipment's original skeleton bones are
   remapped to the character's live animation bones using the character's
   rest-pose inverse bind matrices (`boneRestWorldInverses`).
3. **Bone name remapping** — Equipment GLBs authored with non-Mixamo bone
   names are transparently mapped via `BONE_NAME_REMAP`, which covers:
   - **Legacy generic rig** names (`hand_L`, `spine_01`, etc.)
   - **Decentraland Avatar_\* rig** names (`Avatar_LeftHand`, etc.), including
     4-bone-per-finger mapping (Decentraland's 4th finger bone maps to
     Mixamo's 3rd)
4. **Fine-bone vertex correction** — For slots with many small bones
   (`gloves`, `ring`), a rest-pose vertex correction shifts vertices to
   match the character's actual bone positions so finger geometry aligns
   precisely with the Mixamo skeleton. This correction is applied once per
   cached mesh to prevent compounding on re-equip.
5. **Zero-weight repair** — Any vertices with zero total skin weight are
   assigned to their nearest bone to prevent them from collapsing to origin.

### Interactive mesh transforms

Equipment meshes can be selected (click in viewport or panel) and
repositioned using the Mesh Inspector's transform controls. Transforms are
applied by modifying each `SkinnedMesh`'s **bind matrix** (`bindMatrix` and
`bindMatrixInverse`) every frame via `useFrame`. This is necessary because
skinned meshes share bones with the character skeleton — simply moving a
parent group does not affect the rendered vertex positions since the bone
world matrices already place vertices in world space.

### Visibility rules

Slots can declare `hidden_by` rules. For example, the `ring` slot specifies
`"hidden_by": ["gloves"]`, meaning a ring is hidden when gloves are equipped.

### Adding a new equipment slot

1. Add the slot definition to `equipment/spec/equipment_spec.json` with
   Mixamo bone names, bounds, and mesh parameters
2. Copy the spec to `viewer/public/equipment/equipment_spec.json`
3. Provide the mesh in one of two ways:
   - **Local**: Place the GLB in `viewer/public/equipment/<slot_id>.glb`
   - **Remote**: Set a `url` field in the slot definition (e.g. a Cloudinary
     URL). The viewer will fetch it at runtime.
4. If the slot has fine bone detail (like individual fingers), add its ID
   to the `FINE_BONE_SLOTS` set in `EquipmentMeshRenderer.tsx`
5. Add the slot's color to `SLOT_COLORS` in `viewer/src/types/equipment.ts`
6. If the slot is gender-specific, add `"gender": "male"` or
   `"gender": "female"` to the slot definition

### Positioning a new equipment mesh

1. Enable the slot in the Equipment panel
2. Click the mesh in the viewport (or click its row in the panel) to select it
3. Use the 3D gizmo or the Mesh Inspector's numeric inputs to adjust
   position, rotation, and scale until the mesh fits the character
4. Click **Copy** in the Mesh Inspector to copy the transform values
5. Provide the copied values to update the equipment spec or mesh origin

---

## Body Shell System

The body shell system generates **conforming equipment meshes** by extracting
regions of the base character mesh and offsetting them outward with Blender's
Solidify modifier. This guarantees equipment pieces perfectly match the
character's topology — no clipping, no gaps — and are pre-rigged to the same
skeleton for animation.

### How it works

1. **Import** — The Mixamo-rigged base mesh (`rig/CharacterMesh/BaseFemale.glb`)
   is loaded into Blender headlessly. Vertex groups are renamed from Mixamo
   names to the canonical rig bone names via `MIXAMO_TO_RIG`.

2. **Face assignment** — Each face of the body mesh is assigned to exactly one
   equipment slot using **dominant-slot assignment**: for every face, the total
   bone weight per slot is summed across the face's vertices, and the face goes
   to whichever slot scores highest. A **neighbor-majority smoothing** pass then
   eliminates jagged boundary spikes by flipping outlier faces to match their
   neighbors.

3. **Overlap expansion** — Slot pairs listed in `OVERLAP_PAIRS` are allowed to
   share faces in their overlap region. For each pair, faces assigned to one
   slot are also given to the partner slot wherever the partner has sufficient
   bone weight (controlled by `OVERLAP_WEIGHT_THRESHOLD`). This lets boots and
   lower body overlap on the shin, with boots sitting outside due to greater
   thickness.

4. **Extraction** — For each slot, the assigned faces are duplicated from the
   body mesh, non-selected geometry is deleted, and a Solidify modifier
   (`offset = -1`, outward growth) adds wall thickness. A post-solidify spike
   removal pass detects and deletes vertices with abnormally long edges.

5. **Export** — Each shell is parented to the rig armature from `rig.blend` and
   exported as a skinned GLB with Y-up orientation. Files land in
   `equipment/output/shells/` and are copied to `viewer/public/equipment/`.

### Running the extractor

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/body_shell_extractor.py -- \
  --rig-blend rig/output/rig.blend \
  --body-glb rig/CharacterMesh/BaseFemale.glb \
  --out equipment/output/shells/ \
  --thickness 0 \
  --slots upper_body,lower_body,boots,gloves,head
```

Set `--thickness 0` to use the per-slot defaults defined in `SHELL_THICKNESS`.
After extraction, copy the shells to the viewer:

```bash
cp equipment/output/shells/shell_*.glb viewer/public/equipment/
```

### Configuration reference

All configuration lives at the top of `equipment/factory/body_shell_extractor.py`:

| Constant                   | Purpose                                                              |
|----------------------------|----------------------------------------------------------------------|
| `SLOT_BONES`               | Maps each slot to its rig bone names                                 |
| `SHELL_THICKNESS`          | Per-slot Solidify thickness in meters (0 = no solidify)              |
| `OVERLAP_PAIRS`            | Slot pairs that share faces in their overlap region                   |
| `OVERLAP_WEIGHT_THRESHOLD` | Min bone weight for overlap expansion (lower = more overlap)         |
| `MIXAMO_TO_RIG`            | Vertex group name mapping from Mixamo to canonical rig names         |

### Current slot configuration

| Slot          | Bones                                         | Thickness | Notes                              |
|---------------|-----------------------------------------------|-----------|------------------------------------|
| `head`        | head, neck_01, spine_03, jaw, eyes            | 5 mm      | Covers head and upper neck         |
| `upper_body`  | pelvis, spine chain, clavicles, arms          | 5 mm      | Torso and arms to the wrist        |
| `gloves`      | lowerarm, hands, all finger bones             | 30 mm     | Forearms and hands                 |
| `lower_body`  | pelvis, thighs, shins, feet, toes             | 5 mm      | Hips to ankles                     |
| `boots`       | shins, feet, toes                             | 60 mm     | Knee to toe, sits outside pants    |

### Overlap pairs

| Pair                         | Effect                                                    |
|------------------------------|-----------------------------------------------------------|
| `lower_body` + `boots`       | Pants and boots share the shin region                     |
| `upper_body` + `lower_body`  | Shirt extends slightly past the waist into the hip area   |

### Viewer rendering

`EquipmentMeshRenderer.tsx` handles shell display:

- **Coordinate correction** — Shell GLBs are exported Y-up; the viewer applies
  a Y-up → Z-up rotation matrix plus a scale factor (`1.9 / 1.75`) to match
  the character's display height.
- **Embedded texture detection** — On load, the renderer checks if the GLB
  already has a `map` (texture) on its material. Baked variants are rendered
  with their embedded texture at full brightness; plain shells get a colored
  `MeshStandardMaterial` from `SLOT_COLORS`.
- **Original material tracking** — Each mesh's original material is stored in
  a `Map<Mesh, Material>`. When a runtime texture upload is removed, the mesh
  reverts to its original state (either the baked texture or the flat color).
- **Material** — All equipment meshes use `FrontSide` rendering with
  `polygonOffset` to avoid Z-fighting with the base mesh.
- **Cache busting** — Each GLB URL gets a `v=<timestamp>` query param so
  regenerated shells are fetched without manual cache clearing.

---

## Texture Bake System

The texture bake pipeline transfers textures from a source 3D model (e.g. a
Meshy AI export) onto any target mesh — body shells or custom equipment — using
Blender's Cycles renderer. The result is a **new** GLB with the target's
conforming geometry, rigging, and the source model's appearance baked into an
embedded texture. The original target file is never modified.

### How it works

1. **Import** — Both the source model (with textures) and the target mesh are
   imported into Blender.
2. **Auto-alignment** — The source is uniformly scaled and translated to match
   the target's bounding box, compensating for size/position differences.
3. **Dominant color sampling** — The source texture's average color is computed
   by sampling ~2000 pixels. This fill color replaces any black pixels from
   ray misses in the final output.
4. **Material rewiring** — The source model's Principled BSDF is replaced with
   an Emission shader that pipes the Base Color texture directly, bypassing
   metallic/roughness darkening. This captures raw texture colors at full
   brightness.
5. **Cycles bake** — A "Selected to Active" EMIT bake projects the source
   texture onto the target's UV layout. Rays cast from the target surface
   (plus cage extrusion) hit the source mesh and capture its color.
6. **Post-processing** — Any pure-black pixels (inner faces or ray misses) are
   replaced with the sampled dominant color so uncovered areas blend instead
   of appearing as black patches.
7. **Export** — The target mesh, armature, and embedded baked texture are
   exported as a new GLB file.

### Running the texture baker

**Bake onto a shell (explicit output path):**

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/texture_baker.py -- \
  --source  path/to/textured_model.glb \
  --target  viewer/public/equipment/shell_upper_body.glb \
  --out     viewer/public/equipment/shell_upper_body_crimson.glb \
  --resolution 2048
```

**Bake onto a custom mesh (auto-named output):**

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python equipment/factory/texture_baker.py -- \
  --source  path/to/textured_model.glb \
  --target  viewer/public/equipment/custom_upper_body_f.glb
```

When `--out` is omitted, the output is auto-named `<target>_textured.glb` in
the same directory (e.g. `custom_upper_body_f_textured.glb`). The original
file is never overwritten.

### CLI options

| Flag               | Default | Description                                        |
|--------------------|---------|----------------------------------------------------|
| `--source`         | —       | Path to source GLB with textures (required)        |
| `--target`         | —       | Target mesh GLB — shell or custom (required). `--shell` also accepted. |
| `--out`            | auto    | Output path. If omitted, generates `<target>_textured.glb`. |
| `--texture-out`    | auto    | Optional standalone PNG path for the baked texture  |
| `--resolution`     | 2048    | Baked texture resolution in pixels                 |
| `--cage-extrusion` | 0.15    | Ray start distance from surface in meters          |
| `--samples`        | 4       | Cycles render samples (higher = smoother)          |

The `--texture-out` defaults to `<out_basename>_diffuse.png` beside the
output GLB.

### Adding a baked variant to the viewer

After running the baker:

1. The output GLB is already in `viewer/public/equipment/`
2. Add a slot entry to `viewer/public/equipment/equipment_spec.json`:

```json
{
  "id": "custom_upper_body_f_textured",
  "name": "Custom Upper Body Textured (Female)",
  "url": "/equipment/custom_upper_body_f_textured.glb",
  "mesh_type": "external",
  ...
}
```

3. Add the slot color to `SLOT_COLORS` in `viewer/src/types/equipment.ts`
4. The viewer automatically preserves the GLB's embedded texture instead of
   overriding with a flat color

### Tips for best results

- **Source coverage matters** — The bake only captures areas where the source
  mesh overlaps the shell. If the source is a short vest, the shell's sleeves
  will show the fill color.
- **Increase `--cage-extrusion`** for loosely fitting source models (e.g.
  `0.5` for armor with protruding details).
- **Resolution** — 2048 is a good default. Use 1024 for faster iteration, 4096
  for production quality.
- **Source must have textures** — The baker reads from the source's material
  nodes. Vertex-color-only models will produce flat bakes.

---

## Viewer Texture Upload

The viewer supports uploading texture images directly onto equipment slots at
runtime using **triplanar world-space projection**. This is useful for quick
previews with pattern/fabric textures without going through the full bake
pipeline.

### How to use

1. Enable an equipment slot in the Equipment panel
2. Click the **Tex** button on the slot's row
3. Select an image file (PNG, JPG, etc.) from disk
4. The texture is projected onto the mesh from all 3 world-space axes and
   blended by surface normal, giving a natural wrapped appearance
5. To remove the texture, click the **Tex x** button (reverts to the
   original material — either the flat color or a baked texture)

### How triplanar projection works

Instead of relying on UV coordinates, the shader samples the texture three
times using world-space XY, XZ, and YZ coordinates, then blends the samples
based on the surface normal direction. Faces pointing sideways get the YZ
projection, top/bottom faces get XZ, and front/back faces get XY.

Parameters (configured in `EquipmentMeshRenderer.tsx`):

| Parameter   | Value | Effect                                              |
|-------------|-------|-----------------------------------------------------|
| `scale`     | 0.8   | Texture size on the mesh (lower = larger)           |
| `sharpness` | 2.0   | Blend sharpness between projection axes             |

### Limitations

- Triplanar projection works best with tileable or symmetrical textures.
  UV-atlas textures (like those from Meshy AI) will not map correctly — use
  the [Texture Bake System](#texture-bake-system) for those.
- Uploaded textures are stored in memory and do not persist across page
  reloads.

---

### Workflow: creating textured equipment

**Full pipeline (recommended for production):**

1. Run `body_shell_extractor.py` to generate body shells
2. Generate a textured 3D model from an AI service (e.g. Meshy AI) using the
   shell as a reference
3. Run `texture_baker.py` to bake the AI model's texture onto the shell
4. Add the baked GLB to `equipment_spec.json` as a new slot
5. The baked shell renders with the texture embedded, retains perfect character
   conformance, and animates with the skeleton

**Quick preview (for iteration):**

1. Enable a body shell slot in the viewer
2. Click the **Tex** button and upload a texture image
3. The texture is projected via triplanar mapping for an instant preview
4. Iterate on the texture, then use the full bake pipeline for final quality

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
