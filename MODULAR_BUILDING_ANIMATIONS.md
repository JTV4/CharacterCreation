# Modular 10-Step Building Animations

Documentation for GrindScape **pioneering construction** piece-by-piece assemble animations produced in this CharacterCreation repo and previewed in the Building Viewer.

These are **not** height-sliced mesh swaps (legacy Stage0–3 / AoE P1–P3). Each upgrade unlocks named mesh pieces that **tween from a spawn offset into rest pose**.

---

## Overview

| Concept | Detail |
|--------|--------|
| Bookmarks | **10** total: Site Prep (INIT) + **9** cumulative assembly stages |
| Stage keys (2–10) | `foundation` → `walls_a` → `walls_b` → `walls_c` → `walls_d` → `gable` → `framing` → `eaves` → `complete` |
| Coordinate system | **Z-up** |
| Playback | One modular GLB + JSON manifest; change `stageKey` to unlock more pieces |
| Reference player | `AssemblyBuildingModel` in `viewer/src/components/BuildingViewer.tsx` |
| Registry | `makeAnimationStages()` in `viewer/src/types/buildings.ts` |

**Asset trio per structure** (under `viewer/public/buildings/Construction/`):

1. `*_INIT.glb` — Site Prep only (resource piles; no finished mesh)
2. `*Animation_Modular.glb` — All named pieces in rest pose (`BA_*` nodes)
3. `*_animation_manifest.json` — Piece defs, cumulative `stages`, tween settings

Public URL prefix: `/buildings/Construction/…`

---

## The 10 stages

### Shared building labels

Default labels for medieval buildings / workstations / well (Z assemble):

| # | Key | Label | Typical meaning |
|---|-----|--------|-----------------|
| 1 | *(INIT GLB)* | Site Prep | Resource piles on site — no structure mesh |
| 2 | `foundation` | Foundation | Floor / base piece(s) drop in first |
| 3 | `walls_a` | Walls A | First wall / band batch |
| 4 | `walls_b` | Walls B | Second batch |
| 5 | `walls_c` | Walls C | Third batch |
| 6 | `walls_d` | Walls D | Final main shell batch |
| 7 | `gable` | Gable | Upper / high panel band |
| 8 | `framing` | Framing | Lower trim / framing |
| 9 | `eaves` | Eaves | Upper trim under roof line |
| 10 | `complete` | Complete | Roof / last pieces — full settle |

Keys stay the same for every modular asset. **Display labels** may be overridden (dock, bridge, sheep fence) so the UI describes span progress or perimeter walk instead of walls/roof.

### Custom label sets

| Asset | Assemble progress | Labels (2→10) |
|-------|-------------------|---------------|
| Dock / Fishing Dock | Shore → water (`Y`) | Shore Footings → Near Pilings → … → Water End → Complete |
| Bridge | Near bank → far bank (`Y`) | Near Bank → Span A…F → Far Approach → Far Bank |
| Sheep Fence | Perimeter walk → gate last | Gate West → South Run → … → Gate Approach → Gate |
| Well / workstations / buildings | Bottom → top (`Z`, default) | Shared Foundation → Complete labels |

---

## Playback contract (GrindScape)

Implement the same behavior as `AssemblyBuildingModel`:

1. **Map upgrade level → bookmark**  
   Level 1 → show INIT GLB. Levels 2–10 → modular GLB + `stageKey` from `stageOrder`.

2. **Load once**  
   Load modular GLB + manifest when leaving Site Prep. Keep them mounted while advancing stages.

3. **Match pieces by name**  
   Manifest `pieces[].id` must equal GLB node names (e.g. `BA_Floor_01`).

4. **Stages are cumulative**  
   `manifest.stages[stageKey]` is the full set of piece IDs visible at that bookmark (not a delta). Example: `eaves` includes everything unlocked so far; `complete` includes all pieces.

5. **Animate only newcomers**  
   When `stageKey` advances, tween pieces that were not unlocked before. Already settled pieces stay put. Hide pieces not in the unlocked set (scrubbing backward).

6. **Tween (per piece)**  
   - Start: `restPos + spawnOffset`, yaw = rest × `spawnYawDeg` about **Z**, scale × `startScale`  
   - End: rest position / rotation / scale  
   - Ease: `easeOutCubic` (or manifest `tween.ease`)  
   - Stagger: newly unlocked pieces get local delays `i * staggerSec` (do not wait on earlier stages’ global `staggerIndex`)  
   - Duration: `pieces[].durationSec` (often ~0.40–0.45)

7. **Assemble axis is visual intent**  
   Manifest may include `assembleAxis`: `"Z"` (height), `"Y"` or `"X"` (lateral span). Game logic should treat progress as **along that axis**, not always “building up.”

8. **Finish**  
   Leave modular `complete` visible, or swap to the static finished GLB (`/buildings/<Name>.glb`) for perf.

### Suggested tween defaults

From manifests (buildings often use slightly higher stagger):

```json
{
  "staggerSec": 0.06,
  "ease": "easeOutCubic",
  "startScale": 0.92
}
```

Buildings from `generate_building_animation.py` commonly use `staggerSec: 0.07`.

---

## Manifest schema

```json
{
  "source": "Building1Whole.glb",
  "structureName": "Cooking Animation",
  "coordinateSystem": "Z-up",
  "assembleAxis": "Z",
  "pieces": [
    {
      "id": "BA_Floor_01",
      "category": "Floor",
      "staggerIndex": 0,
      "spawnOffset": [-0.04, 0.55, 2.8],
      "spawnYawDeg": -12.0,
      "durationSec": 0.45
    }
  ],
  "stages": {
    "foundation": ["BA_Floor_01"],
    "walls_a": ["BA_Floor_01", "BA_Wall_01"],
    "complete": ["…all piece ids…"]
  },
  "stageOrder": [
    "foundation",
    "walls_a",
    "walls_b",
    "walls_c",
    "walls_d",
    "gable",
    "framing",
    "eaves",
    "complete"
  ],
  "tween": {
    "staggerSec": 0.07,
    "ease": "easeOutCubic",
    "startScale": 0.92
  }
}
```

| Field | Role |
|-------|------|
| `pieces` | Per-piece spawn + duration; `id` = GLB object name |
| `stages` | Cumulative unlock lists keyed by stage key |
| `stageOrder` | Canonical order for levels 2–10 |
| `tween` | Shared stagger / ease / start scale |
| `assembleAxis` | Optional; how pieces were sliced (`Z` / `Y` / `X`) |

INIT is **not** listed in the manifest — it is a separate GLB shown only for bookmark 1.

---

## Asset inventory

Paths relative to `viewer/public/buildings/`.

### Medieval buildings

Generator: `generate_building_animation.py`

| Structure | Modular GLB | Manifest | INIT |
|-----------|-------------|----------|------|
| Cooking (B1) | `Construction/Building1Animation_Modular.glb` | `building1_animation_manifest.json` | `Building1Whole_INIT.glb` |
| Bank (B2) | `Building2Animation_Modular.glb` | `building2_animation_manifest.json` | `Building2Whole_INIT.glb` |
| Apothecary (B3) | `Building3Animation_Modular.glb` | `building3_animation_manifest.json` | `Building3Whole_INIT.glb` |
| Merchant (B4) | `Building4Animation_Modular.glb` | `building4_animation_manifest.json` | `Building4Whole_INIT.glb` |
| Forge (B5) | `Building5Animation_Modular.glb` (+ legacy `BuildingAnimation_Modular.glb`) | `building5_…` / `building_animation_manifest.json` | `Building5Whole_INIT.glb` |
| Workshop (B6)* | `Building6Animation_Modular.glb` | `building6_animation_manifest.json` | `Building6Whole_INIT.glb` |
| Manufacturing (B7) | `Building7Animation_Modular.glb` | `building7_animation_manifest.json` | `Building7Whole_INIT.glb` |
| Chronocrafting (B8)* | `Building8Animation_Modular.glb` | `building8_animation_manifest.json` | `Building8Whole_INIT.glb` |
| Sheep Fence | `SheepFenceAnimation_Modular.glb` | `sheep_fence_animation_manifest.json` | `SheepFence_INIT.glb` |
| Cow Fence | `CowFenceAnimation_Modular.glb` | `cow_fence_animation_manifest.json` | `CowFence_INIT.glb` |

\* **GrindScape game numbering** (authoritative for wiring): B1 Cooking … B5 Forge, **B6 Chronocrafting**, **B7 Manufacturing**, **no B8**. CharacterCreation sidebar labels may still say “Workshop” / “Chronocrafting Building (8)” — do not copy those ids blindly into game pioneering tables.

Viewer registry ids (examples): `cooking_animation`, `bank_animation`, `apothecary_animation`, `merchant_animation`, `workshop_animation`, `manufacturing_animation`, `chronocrafting_animation`, `sheep_fence_animation`, `cow_fence_animation`, `building_animation` (forge legacy).

### Workstations

Generator: `generate_workstation_animation.py`  
Sources: `Workstations/<Name>.glb`  
Default assemble: **Z** (bottom → top)

| Structure | Modular | Manifest | INIT materials (typical) |
|-----------|---------|----------|---------------------------|
| Manufacturing Workbench | `ManufacturingWorkbenchAnimation_Modular.glb` | `manufacturing_workbench_animation_manifest.json` | Sycamore logs, Iron ore, GrindCoins |
| Chronocrafting Workbench | `ChronocraftingWorkbenchAnimation_Modular.glb` | `chronocrafting_workbench_…` | Sycamore logs, GrindCoins |
| Cooking Range | `CookingRangeAnimation_Modular.glb` | `cooking_range_…` | Clay, Raw Catfish, GrindCoins |
| Furnace | `FurnaceAnimation_Modular.glb` | `furnace_…` | Sycamore logs, Clay, GrindCoins |
| Spinning Wheel | `SpinningWheelAnimation_Modular.glb` | `spinning_wheel_…` | Flax, Sycamore logs, GrindCoins |
| Anvil | `AnvilAnimation_Modular.glb` | `anvil_…` | Iron ore, GrindCoins |
| Tanning Rack | `TanningRackAnimation_Modular.glb` | `tanning_rack_…` | Cow hide, Sycamore logs, GrindCoins |
| Bank Chest | `BankChestAnimation_Modular.glb` | `bank_chest_…` | Poplar logs, GrindCoins |

INIT-only (not modularized yet): Crafting Workbench.

### Exterior / waterside

Same workstation generator; custom `assemble_axis`:

| Structure | Axis | Modular | Manifest | INIT |
|-----------|------|---------|----------|------|
| Bridge | **Y** (bank → bank) | `Bridge4Animation_Modular.glb` | `bridge4_animation_manifest.json` | `Bridge4_INIT.glb` |
| Well | **Z** | `WellAnimation_Modular.glb` | `well_animation_manifest.json` | `Well_INIT.glb` |
| Fishing Dock | **Y** (shore → water) | `FishingDockAnimation_Modular.glb` | `fishing_dock_animation_manifest.json` | `FishingDock_INIT.glb` |
| Dock (`Dock_ano5au`) | **Y** (shore → water) | `DockAnimation_Modular.glb` | `dock_animation_manifest.json` | `Dock_INIT.glb` |

Static completes (when not animating): e.g. `/buildings/Dock.glb`, `/buildings/SheepFence.glb`, `/buildings/CowFence.glb`.

---

## Generators

### Buildings / sheep fence

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python generate_building_animation.py
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python generate_building_animation.py -- 1 2 3
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python generate_building_animation.py -- cow
```

- Splits `BuildingNWhole` meshes into modular `BA_*` pieces (authored floor first for buildings).
- Sheep Fence (id 9): perimeter path; gate last; logs-only INIT at center.
- Cow Fence (id 10): same perimeter walk on GrindScape `CowFence.glb` (structure `7e88fe87-662e-4acb-8dc0-406e744b0258`). Loose boards are clustered into bay pieces; last stage is the west gate opening (swinging gate is a separate Cow Gate structure). INIT is two sycamore stacks + GrindCoins.
- Writes Construction GLBs + manifests; mirrors to `~/Desktop/Models/Buildings/Construction/` when present.

### Workstations / bridge / well / docks

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python generate_workstation_animation.py
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python generate_workstation_animation.py -- furnace dock bridge4
```

- Targets ~9 pieces via axis banding (`Z` default; `Y` for dock/bridge).
- Emits INIT piles from pile GLBs under `viewer/public/buildings/`.

### Viewer registration

After new assets exist, register with `makeAnimationStages({ idPrefix, modularFile, manifestFile, initUrl?, assemblySteps? })` in `viewer/src/types/buildings.ts`.

---

## Related systems (do not confuse)

| System | What it is |
|--------|------------|
| **Modular 10-step (this doc)** | Piece drop-in via manifest + modular GLB |
| **AoE Whole stages** | Hard-swap `INIT` / `P1` / `P2` / `P3` / Completed GLBs (`generate_building*_whole_construction.py`) |
| **Legacy Stage0–3** | Older bisect construction GLBs on numeric `buildingN` entries |
| **Character animations** | e.g. `FemaleFishing`, `FemaleWellFill` — player loops, not structure assemble |

---

## GrindScape wiring checklist

- [ ] Upgrade level 1 → INIT GLB (or equivalent VFX at footprint)
- [ ] Levels 2–10 → load modular + manifest; set `stageKey` from `stageOrder[level - 2]`
- [ ] Hide INIT when first modular stage starts
- [ ] Use cumulative unlock + newcomer-only tweens
- [ ] Respect `assembleAxis` for UX copy / progress (height vs span vs perimeter)
- [ ] Use game building numbers (B6 Chronocrafting, B7 Manufacturing), not CharacterCreation “Workshop / B8” labels
- [ ] Optional: on complete, swap to static finished mesh

---

## One-liner

> Pioneering modular construction = **Site Prep INIT** + **one multi-node GLB** + **JSON manifest**; nine cumulative keys (`foundation`…`complete`) unlock `BA_*` pieces that ease from spawn offset into rest pose (Z-up), matching `AssemblyBuildingModel`.
