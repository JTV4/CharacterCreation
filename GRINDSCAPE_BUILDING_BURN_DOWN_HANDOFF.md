# Grindscape Handoff — Building Burn Down

**Source repo:** `CharacterCreation`  
**Destination:** Grindscape game client  
**Date:** 2026-08-30  
**Owner intent:** A player can start a fire anywhere. If they light it **on the ground inside a building**, the fire starts at that point, spreads across the whole structure, and **burns the building down**. This is a **runtime VFX + mesh collapse** on the existing modular building GLBs — **not** a baked animation clip and **not** a new GLB upload.

Reference implementation (this repo’s Building Viewer):

- Catalog: `viewer/src/types/buildings.ts` → `*_burn_down` entries (`burnDown: true`)
- Effect: `viewer/src/components/BuildingBurnDown.tsx`
- Hook-up: `viewer/src/components/BuildingViewer.tsx` (renders `BuildingBurnDown` when `stage.burnDown`)
- Modular meshes: `viewer/public/buildings/Construction/Building{N}Animation_Modular.glb` + matching `building{n}_animation_manifest.json`

Preview locally: `cd viewer && npm run dev` → **Buildings** sidebar → any **… Burn Down** row → **Light Fire** (or click the floor). **Reset** restores the building.

---

## 1. What to ship

**No new GLBs.** Reuse the modular construction meshes already in game (the same files used for the 10-step assemble animation). Port the burn-down **behaviour** from `BuildingBurnDown.tsx`.

| Building | Game component | Modular GLB | Viewer sidebar |
|---|---|---|---|
| Bank | `PioneeringBuilding2` / `PioneeringBuilding2Whole` | `Building2Animation_Modular.glb` | Bank Burn Down |
| Manufacturing | `PioneeringBuilding7` / `PioneeringBuilding7Whole` | `Building7Animation_Modular.glb` | Manufacturing Burn Down |
| Forge | `PioneeringBuilding5` / `PioneeringBuilding5Whole` | `Building5Animation_Modular.glb` | Forge Burn Down |
| Chronocrafting | `PioneeringBuilding8` / `PioneeringBuilding8Whole` | `Building8Animation_Modular.glb` | Chronocrafting Burn Down |
| Cooking | `PioneeringBuilding1` / `PioneeringBuilding1Whole` | `Building1Animation_Modular.glb` | Cooking Burn Down |
| Merchant | `PioneeringBuilding4` / `PioneeringBuilding4Whole` | `Building4Animation_Modular.glb` | Merchant Burn Down |

Suggested feature id: `building_burn_down`. Suggested per-building keys: `bank`, `manufacturing`, `forge`, `chronocrafting`, `cooking`, `merchant`.

Same pattern works later for Apothecary (`Building3`) and Workshop (`Building6`) — they have the same `BA_Floor` / `BA_Wall` / `BA_Roof` / `BA_Trim` pieces. Not previewed yet; do not block this ship on them.

Do **not**:

- Bake a `burn` / `die` clip into the building GLB
- Upload a second “burned ruin” mesh unless you later author one
- Light the whole building at once — fire must **start at the ignition point** and crawl
- Spawn flames **under** the floor slab

---

## 2. Gameplay contract

1. Player starts a fire on the **ground** (existing fire-anywhere action).
2. If that point is **inside a completed building footprint** (on the floor / walkable slab), attach burn-down to **that building instance**.
3. Ignition world position = the fire’s ground hit (clamp onto the floor top; do not start on a wall or roof even if the ray hits one — drop XY onto the floor).
4. Fire spreads along the **building surface** (floor → walls → trim → roof), not through empty air.
5. Pieces **char** (albedo → charcoal, brief orange emissive at the fire front).
6. Pieces **collapse** after they have been on fire: walls lean inward and slump, roof drops and tilts, floor chars / thins / sinks. End state = smoldering rubble.
7. After rubble: building is unusable (no banking / crafting / etc.) until the player rebuilds with the existing construction stages.

Suggested total time (viewer tuning): **~8 s** to fully engulf, walls starting to fall **~1–5 s** after they catch, roof down around **6 s**, rubble shortly after. Tune to combat / trolling feel; keep the order (floor first, roof last).

If the fire is started **outside** a building, do not run this system. Ground campfires stay as they are.

---

## 3. Meshes — use the modular GLB, not Whole / Stage slices

Burn-down needs **named pieces** so floor / wall / roof can catch and fall independently.

| Use | Do not use |
|---|---|
| `Building{N}Animation_Modular.glb` | `Building{N}Whole.glb` (one blob / tile flood) |
| Piece nodes `BA_Floor_*`, `BA_Wall_*`, `BA_Trim_*`, `BA_Roof_*` | Legacy `Building{N}StageK.glb` bisects |
| Manifest only for piece ids / categories (optional) | Manifest assemble tweens (those are construction, not fire) |

Piece kind from **node name** (case-insensitive substring), same as the viewer:

| Name contains | Kind | Collapse |
|---|---|---|
| `floor` | floor | Char + thin/sink. Flames on the **top** of the slab only. |
| `wall` / `gable` | wall | Lean inward toward building center, then slump. |
| `trim` / `eave` / `door` | trim | Fall with the walls, slightly sooner. |
| `roof` / `tile` | roof | Drop toward the floor + random tilt. |
| anything else | other | Treat like wall. |

All six shipped buildings have at least `BA_Floor_01`, walls, and roof.

Show **all pieces** (the `complete` assemble set). Do not hide pieces the way construction stages do.

---

## 4. Coordinates (read this)

### Modular GLB file

Vertices are **Y-up, metres**. Nodes sit at identity; geometry is already in place. Floor is a thin slab near **Y ≈ 0**; height is **+Y**.

### This viewer (Z-up grid)

`BuildingBurnDown` wraps the GLB with **+90° about X** so the building sits on the viewer grid (`(x, y, z) → (x, −z, y)`). **Do not copy that wrap** if Grindscape buildings are already Y-up in world.

### Grindscape (typical Three / glTF Y-up)

- Ground = XZ plane, **+Y up**
- Ignition = `(x, floorTopY, z)`
- Flame “up” = **+Y**
- Never spawn VFX with Y below the floor top
- Collapse drop = **−Y**; wall lean in the XZ plane toward the building center

If you port the viewer file verbatim, swap every viewer “world Z is up” test (`floorZ`, `nrm.z`, card billboard around Z) to **Y-up**.

---

## 5. Algorithm (port this, don’t reinvent)

All of this lives in `viewer/src/components/BuildingBurnDown.tsx`. Copy the structure; fix the up-axis for the game.

### 5.1 Sample the surface

- Area-weighted triangle samples (~780) across all pieces.
- Extra **16×16 grid** on each floor piece’s **top** (`localMax.y` in the GLB), forced normal = world up. Floor was getting skipped without this.
- Reject underside-of-floor samples. **Never** keep points under the slab.
- Store each sample in **piece-local** space so flames ride the mesh when it collapses.

### 5.2 Spread (graph, not a sphere)

1. Connect samples within ~`0.042 × footprint` (and k-nearest if isolated).
2. Dijkstra from the sample nearest the ignition point.
3. Edge cost = `horiz / speedH + climb / speedV` (climbing is slower than crawling the floor).
4. Scale times so the last sample ignites at ~**8.2 s** (`TARGET_SPREAD_SEC`).
5. A piece’s `igniteAt` = min of its samples.

Result: fire starts on the boards at the click, crawls the floor, climbs walls, then takes the roof.

### 5.3 VFX

Three layers. The first one is what reads as “fire”; do not ship char-only walls.

| Layer | What |
|---|---|
| **Flame cards** | ~280 instanced vertical billboards. Teardrop shader (yellow core, orange body, red edge, rising noise). Additive. **~45% reserved for floor** once the floor is lit. |
| **Particles** | Additive wisps + embers + smoke. Spawn only at ignited samples with world-up ≥ floor top. |
| **Char** | Clone materials per mesh. Albedo → charcoal. Short orange emissive at the fire front, then die out. Walls must **not** just glow red. |

Billboard cards around **world up** so they stand on the floor / lick up the walls. Origin cluster (small campfire) at the ignition point on the floor.

**Floor clamp:** every flame / smoke / ember / card Y (or viewer Z) = `max(floorTop, position)`. No fire under the building.

### 5.4 Collapse

Per piece, after it has been burning:

| Kind | Starts | Motion |
|---|---|---|
| Floor | ~2.2 s after that floor catches (fallback ~6.4 s) | Sink slightly, scale thin on up-axis (boards burn away) |
| Trim | ~0.9 s after catch | Lean in + drop |
| Wall | ~1.15 s after catch (fallback ~4.6 s) | Lean ~60°+ toward center, slump down |
| Roof | ~1.6 s after catch (fallback ~5.6 s) | Drop almost to the floor, tilt |

Rotate around the piece’s **base** (bottom center of its AABB), not the scene origin. Pieces have identity transforms and world-space verts — use `T(base) * R * T(-base)`.

Fallback clock guarantees the building still comes down if a piece never got samples.

---

## 6. Viewer API (for the port)

```ts
type BurnPhase = "idle" | "ignited" | "spreading" | "engulfed" | "collapsing" | "rubble";

interface BurnDownCommands {
  igniteDefault: () => void; // floor-center ignition (debug)
  reset: () => void;         // restore meshes / materials / VFX
}
```

Game should call something like `igniteAt(worldPoint)` from the existing “place fire on ground” action, not a debug button. `reset` / teardown when the instance is destroyed or the player rebuilds.

Phases are UI-only in the viewer. In game, `rubble` is the moment to mark the building destroyed.

---

## 7. Integration notes

- Run burn-down on the **same scene graph** as the placed building (the modular complete mesh). Do not swap to `Building{N}Whole.glb` mid-burn.
- Clone materials before char so other instances of the same GLB stay clean.
- One burn per building instance. A second ground fire inside an already-burning building should not restart the clock.
- Construction-in-progress (only floor, or floor+walls) can still burn: only existing pieces ignite. Empty plot / INIT piles should not.
- After rubble, either leave the collapsed/charred meshes or hide them and show a burnt-plot decal. Rebuild = existing assemble animation from INIT.
- Performance: one Dijkstra at ignite (once), then per-frame particle + ~280 instance matrices. Fine for one burning building; cap concurrent burns if players grief many at once.

---

## 8. What not to copy blindly

| Viewer detail | Game |
|---|---|
| `rotation={[Math.PI / 2, 0, 0]}` wrap | Skip if the world is already Y-up |
| Click-to-ignite on the canvas | Use the real fire-on-ground action + footprint test |
| `Light Fire` / `Reset` overlay | Debug only |
| `Building{N}Whole.glb` complete stage | Wrong mesh for piece collapse |
| Dragon / rooster fire components | Different VFX; do not reuse those bones |

---

## 9. Preview checklist

`cd viewer && npm run dev` → Buildings:

- [ ] Bank Burn Down — floor fire → walls → roof → collapse
- [ ] Manufacturing Burn Down
- [ ] Forge Burn Down
- [ ] Chronocrafting Burn Down
- [ ] Cooking Burn Down
- [ ] Merchant Burn Down

On each: click a **floor** point (not the void under the slab). Flames stay **on/above** the boards. Building chars and falls. **Reset** works.

---

## 10. Files to read

| File | Why |
|---|---|
| `viewer/src/components/BuildingBurnDown.tsx` | Full implementation — port this |
| `viewer/src/components/BuildingViewer.tsx` | How the stage flag mounts it |
| `viewer/src/types/buildings.ts` | `burnDown` stage flag + GLB urls |
| `MODULAR_BUILDING_ANIMATIONS.md` | Piece names / assemble stages (construction, not fire) |
