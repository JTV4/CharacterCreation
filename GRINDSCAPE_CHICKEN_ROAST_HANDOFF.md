# Grindscape Handoff — Chicken & Rooster Catch Fire (Roast)

**Source repo:** `CharacterCreation`  
**Destination:** Grindscape game client  
**Date:** 2026-08-30  
**Depends on:** [`GRINDSCAPE_CREATURES_HANDOFF.md`](./GRINDSCAPE_CREATURES_HANDOFF.md) (hen + rooster GLBs and clips already shipped)

**Owner intent:** A player can start a fire anywhere. If a **chicken** or **rooster** walks onto that fire, it **stops in place**, **catches fire**, **roasts alive**, and becomes **cooked chicken**. This is **runtime VFX + the existing `die` clip** on `Chicken.glb` / `Rooster.glb`. **No new GLB. No baked `roast` clip. Do not spawn a second fire** — the ground fire already exists.

Reference implementation (this repo’s viewer):

- Catalog: `viewer/src/types/buildings.ts` → `farm_chicken_roast` / `farm_rooster_roast` (`roast: true`)
- Effect: `viewer/src/components/BirdRoast.tsx`
- Hook-up: `viewer/src/components/BuildingViewer.tsx` (renders `BirdRoast` when `stage.roast`)

Preview locally: `cd viewer && npm run dev` → **Creatures** → **Chickens** → **Chicken — Roast** or **Rooster — Roast** → **Roast**. **Reset** restores the live bird.

---

## 1. What to ship

**No new GLBs.** Use the farm birds already in game.

| Creature | creatureTypeId | GLB | Viewer row |
|---|---|---|---|
| Hen | `chicken` | `viewer/public/buildings/Chicken.glb` | Chicken — Roast |
| Rooster | `rooster` | `viewer/public/buildings/Rooster.glb` | Rooster — Roast |

Suggested feature id: `creature_roast` / `bird_roast`. Same behaviour on both types.

Do **not**:

- Bake a `roast` / `burn` / `cook` clip into the GLB
- Upload a roasted-bird mesh (the live mesh **cooks in place** via materials)
- Walk / lerp the entity to a fire marker
- Spawn a campfire, scorch decal, or extra fire prop for this preview
- Use rooster `attack2` (rump fire) or `attack3` (mouth fire) for this — those are combat, not dying on a campfire
- Play hen egg / omelet VFX (`attack2`) during the roast

---

## 2. Gameplay contract

1. Player (or world) already has a **ground fire**.
2. If a `chicken` or `rooster` **overlaps that fire** (feet / collider on the fire volume):
   - **Stop locomotion.** Do not path them to a point. Apply the roast **where they stand**.
   - Interrupt walk / idle / combat.
3. **Catch fire** — body flames + wisps on the bird mesh (not a ground ring).
4. After **~0.5 s**, play clip **`die`** (exact lowercase). **Play once, clamp** at the last pose. Same `die` already shipped (~1.17 s, collapse onto the right side).
5. Over **~2.55 s** from ignition, materials lerp from live feathers to **roasted chicken** (golden brown → darker roast). Brief orange emissive while burning, then it dies out.
6. When cooked (`roasting` → `cooked`):
   - Bird is dead. No more AI / loot-as-live-creature.
   - Convert to **cooked chicken** loot (existing cooking item). Despawn or hide the roasted corpse after pickup / despawn timer.
   - Suggested item: whatever Grindscape already uses for cooked chicken (inventory stack mesh `MeatStack_CookedChicken.glb` is the **item pile**, not the corpse).

If the fire is extinguished mid-roast, either finish the cook (simpler) or cancel and play a normal `die` / leftover-HP path. Do not leave them walking around half-orange.

Same sequence for hen and rooster. Rooster combat fire bones (`ButtFire`, `MouthFire`) stay unused.

---

## 3. Clips (existing — do not add)

| When | Clip | Playback |
|---|---|---|
| Before they hit the fire | `idle` / `walk` as now | Loop. Walk has **no root motion**. |
| Roast starts | keep `idle` ~0.5 s (they freeze / stand in the fire) | Then stop that action |
| Roast | **`die`** | **Play once, clamp.** Do not loop. |
| After `die` | hold last frame | Until loot / despawn |

Do **not** look for `roast`, `burn`, `cook`, `death`, or `dying`.

Do **not** play `attack1` / `attack2` / `attack3` as part of this.

---

## 4. VFX (port `BirdRoast.tsx`)

All fire is **on the bird**, in **place**.

| Layer | What |
|---|---|
| **Flame cards** | ~56 instanced vertical billboards sampled on the **Chicken** / **Rooster** mesh (skip `ChickenEgg_*` / omelets). Additive teardrop flame. Fade down once `cooked`. |
| **Wisps** | Additive sparks from the same surface samples. Fewer once cooked (smolder). |
| **Char / cook** | Clone materials per instance. Albedo → `#c47822` then `#5a2a0c`. Roughness up. Short orange emissive, then off. |
| **Light** | Optional small point light on the body while roasting. |

Hide egg / omelet / burst meshes for the hen during roast (same as the viewer).

**Do not** draw a ground campfire, scorch circle, or walk path. The game’s existing fire is the only ground fire.

### Coordinates

Farm birds are Y-up glTF, origin between the feet, facing **+Z** (same as cows / sheep). See the creatures handoff.

The viewer wraps creatures **+90° about X** for its Z-up grid. **Do not copy that wrap** if Grindscape is already Y-up. Billboard flame cards around **world up (+Y)**.

Sample points in **mesh-local** space and `localToWorld` each frame so flames follow `die` skinning.

---

## 5. Viewer API (for the port)

```ts
type RoastPhase = "idle" | "roasting" | "cooked";

interface RoastCommands {
  play: () => void;  // start roast in place (game: fire overlap)
  reset: () => void; // debug only — restore live bird
}
```

Game trigger is **fire overlap**, not a button. `play()` in the viewer is that trigger.

Viewer timings (tune if needed, keep the order):

| Time from ignite | What |
|---|---|
| 0 | Body fire + cook lerp starts. Clip still `idle`. |
| 0.5 s | Play `die` once, clamp |
| 2.55 s | Phase `cooked` — fully roasted, fire dies down to smolder |

---

## 6. Integration notes

- One roast per bird instance. Do not restart if they stay in the fire.
- Stop the server walk / pathing the moment roast starts (clip is in-place; no root motion).
- Do not move the transform toward the fire. The fire already intersects them.
- Rooster `attack2` / `attack3` fire VFX (`RoosterButtFire.tsx`) must **not** run during roast.
- Hen `ChickenEggBurst` must **not** run during roast.
- After `cooked`, treat as a corpse / cooking result: cooked chicken item, not a live farm animal.
- Other creatures (cows, sheep, dragons) are **out of scope** unless you later reuse the same “stand in fire → die + char” pattern.

---

## 7. What not to copy blindly

| Viewer detail | Game |
|---|---|
| **Roast** / **Reset** overlay | Debug only |
| Walk-to-fire (removed) | Never re-add |
| Ground scorch / campfire cards (removed) | Use the existing world fire |
| `rotation={[Math.PI / 2, 0, 0]}` wrap | Skip if the world is already Y-up |
| `MeatStack_CookedChicken.glb` as the roasting mesh | Item icon / loot pile only |

---

## 8. Preview checklist

`cd viewer && npm run dev` → Creatures → Chickens:

- [ ] **Chicken — Roast** — bird stays put; **Roast** → body fire → `die` → golden roast
- [ ] **Rooster — Roast** — same, no walk, no extra ground fire
- [ ] **Reset** restores live materials and `idle`
- [ ] Normal **Chicken** / **Rooster** rows still play `idle` / `walk` / `attack*` / `die` as before

---

## 9. Files to read

| File | Why |
|---|---|
| `viewer/src/components/BirdRoast.tsx` | Full implementation — port this |
| `viewer/src/components/BuildingViewer.tsx` | How `roast: true` mounts it |
| `viewer/src/types/buildings.ts` | `farm_chicken_roast` / `farm_rooster_roast` |
| `GRINDSCAPE_CREATURES_HANDOFF.md` | GLBs, `die` clip, facing, IDs |
| `GRINDSCAPE_BUILDING_BURN_DOWN_HANDOFF.md` | Related: fire-anywhere on **buildings** (separate system) |
