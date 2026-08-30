# Grindscape Handoff — Dragons + Hen + Rooster

**Source repo:** `CharacterCreation`  
**Destination:** Grindscape game client  
**Date:** 2026-08-28  
**Supersedes:** `GRINDSCAPE_DRAGONS_HANDOFF.md` (2026-08-27) and `GRINDSCAPE_FARM_CHICKENS_HANDOFF.md` (2026-08-17) for clip / VFX / facing. Use this file.

**Owner intent:** Ship seven authored creature GLBs. Each is a **single armature + skinned mesh** with clips baked in. Creatures do **not** load Mixamo files. Upload the game-ready GLBs; do not split clips into separate files.

**Purple Dragon** in this pipeline is **`VioletDragon.glb`** / `creatureTypeId` **`violet_dragon`**. There is no `PurpleDragon.glb`.

Reference implementation (Building Viewer):

- Catalog: `viewer/src/types/buildings.ts`
- Playback: `viewer/src/components/BuildingViewer.tsx`
- Dragon fire: `viewer/src/components/DragonFireBreath.tsx` (`attack1` only)
- Hen eggs: `viewer/src/components/ChickenEggBurst.tsx` (`attack2` only)
- Rooster fire: `viewer/src/components/RoosterButtFire.tsx` (`attack2` rump + `attack3` mouth)
- Generators: `generate_green_dragon_firebreath.py`, `generate_farm_chickens.py`
- Clip-name rule: `.cursor/rules/creature-animation-naming.mdc`

Preview: `cd viewer && npm run dev` → **Creatures**. Clip buttons bottom-left. Default `idle`.

Viewer loop regex: `idle` / `idle_N` / `walk` / `run` / `attack1` / `attack3`.  
Play once + clamp: `attack2`, `die`.

---

## What changed (read this first)

| Creature | Delta vs last handoff |
|---|---|
| All five dragons | Color-matched **thick** fire VFX on **`attack1`**. Packed `DragonFire*` meshes are hidden in the viewer. **`attack2` is melee bite — no fire.** |
| Purple | Same as Violet. Id `violet_dragon`, file `VioletDragon.glb`. |
| Hen | New **`attack2`**: jump + 180°, three eggs from the rump, three small omelets on the ground, jump + 180° back. Play once. |
| Rooster | New **`attack2`**: same jump-180, then **rump fire** (play once). New **`attack3`**: **mouth fire-breath**, no 180, **loop**. Fire VFX is a thick jet (billboard slices + large particles), not sparks. |

---

## 1. What to ship

### Dragons (same rig, same clip set)

| File | creatureTypeId | Display name | Component |
|---|---|---|---|
| `GreenDragon.glb` | `green_dragon` | Green Dragon | `PioneeringGreenDragon` |
| `BlueDragon.glb` | `blue_dragon` | Blue Dragon | `PioneeringBlueDragon` |
| `RedDragon.glb` | `red_dragon` | Red Dragon | `PioneeringRedDragon` |
| `VioletDragon.glb` | `violet_dragon` | Violet / Purple Dragon | `PioneeringVioletDragon` |
| `BlackDragon.glb` | `black_dragon` | Black Dragon | `PioneeringBlackDragon` |

### Farm birds (same bird rig; rooster has one extra clip)

| File | creatureTypeId | Display name |
|---|---|---|
| `Chicken.glb` | `chicken` | Chicken (hen) |
| `Rooster.glb` | `rooster` | Rooster |

IDs are **lowercase snake_case**. Replace placeholder `chimken` with `chicken`. Do **not** use `female_chicken` / `male_chicken`. Kill quests that alias `cow` → cows do **not** currently alias `chicken` → `rooster`; add that if `target: 'chicken'` should credit roosters.

Do **not** upload unrigged author sources:

- `~/Desktop/Models/Creatures/Dragons/{Color}Dragon.glb`
- `~/Desktop/Models/Creatures/FarmCreatures/Chicken.glb` / `Rooster.glb`

---

## 2. GLBs — use these files

| File | Path | Size |
|---|---|---|
| Green | `viewer/public/buildings/GreenDragon.glb` | ~1.4 MB |
| Blue | `viewer/public/buildings/BlueDragon.glb` | ~1.5 MB |
| Red | `viewer/public/buildings/RedDragon.glb` | ~1.4 MB |
| Violet / Purple | `viewer/public/buildings/VioletDragon.glb` | ~1.5 MB |
| Black | `viewer/public/buildings/BlackDragon.glb` | ~1.4 MB |
| Hen | `viewer/public/buildings/Chicken.glb` | ~718 KB |
| Rooster | `viewer/public/buildings/Rooster.glb` | ~557 KB |

Textures are **packed inside the GLB**. PascalCase filenames, no spaces.

### Cloudflare R2 (`assets.grindscape.com`)

Old un-authored dragon objects — **do not point the client at these**:

| Color | Existing R2 object (replace) |
|---|---|
| Green | `https://assets.grindscape.com/green_dragon_h5hwgg.glb` |
| Blue | `https://assets.grindscape.com/blue_dragon_aluniv.glb` |
| Red | `https://assets.grindscape.com/red_dragon_dycsmg.glb` |
| Black | `https://assets.grindscape.com/black_dragon_kxzdqp.glb` |
| Violet | `https://assets.grindscape.com/violet_dragon_qr1muu.glb` |

Upload the seven game-ready files from the table above. Suggested keys match the filenames. Then point `creatureModelUrls.ts` at the new objects.

Farm birds: upload to the same creature bucket / Cloudinary folder Grindscape already uses for creatures (not `Inventory/Tools`). Suggested public IDs: `Chicken`, `Rooster`.

---

## 3. Animation clips

Names are **exact, lowercase**. Mixamo / PascalCase aliases are not resolved except the existing `attack1` fallback list (`attack` → `Attack` → … → `Melee Attack`). That list still means **primary attack = `attack1`**. Do **not** point those aliases at `attack2` or `attack3`.

Do **not** look for `death`, `dying`, `Idle`, `walk1`, `Attack`, `attack_melee`, `attack_fire`.

### Dragons (all five)

| Game state | Clip | Duration | Playback | What it is |
|---|---|---|---|---|
| Idle | `idle` | 3.000 s (72 f @ 24 fps) | Loop | Breath, head look, wing lift, tail sway |
| Walk | `walk` | 1.333 s (32 f) | Loop, **no root motion** | Diagonal trot |
| Ranged | `attack1` | 2.000 s (48 f) | **Loop** | Fire-breath. Existing Attack state stays on this clip. |
| Melee | `attack2` | 1.500 s (36 f) | Play once (or loop if melee combat loops) | Bite. **No fire.** |
| Die | `die` | 1.500 s (36 f) | Play once, clamp | Legs sprawl, drop straight down |

Extra (not a game state): `run` — 0.667 s, looping in-place gallop. Safe to ignore. Do not rename it to `walk`.

**Shipped:** `idle`, `walk`, `run`, `attack1`, `attack2`, `die`.

`attack2` will T-pose / be ignored until the client plays that exact name. Do not rename `attack2` → `attack1`.

### Hen (`Chicken.glb`)

| Game state | Clip | Duration | Playback | What it is |
|---|---|---|---|---|
| Idle | `idle` | 2.000 s (48 f) | Loop | |
| Walk | `walk` | 0.833 s (20 f) | Loop, **no root motion** | |
| Peck | `attack1` | ~0.75 s (18 f) | Play once per peck (viewer loops all `attack1`) | Peck / lunge + wing flare |
| Egg burst | `attack2` | 2.000 s (48 f) | **Play once**, clamp | Jump 180 → three eggs → omelets → jump 180 back |
| Die | `die` | ~1.17 s (28 f) | Play once, clamp | Collapse onto the right side |

**No `attack3`.** **No `run`.**

### Rooster (`Rooster.glb`)

| Game state | Clip | Duration | Playback | What it is |
|---|---|---|---|---|
| Idle | `idle` | 2.000 s (48 f) | Loop | |
| Walk | `walk` | 0.833 s (20 f) | Loop, **no root motion** | |
| Peck | `attack1` | ~0.75 s (18 f) | Play once per peck | Same peck family as hen; hits harder |
| Rump fire | `attack2` | 2.000 s (48 f) | **Play once**, clamp | Same jump-180 as hen, then fire from the rump toward original front |
| Mouth fire | `attack3` | 2.000 s (48 f) | **Loop** | Faces forward. No 180. First/last pose match. |
| Die | `die` | ~1.17 s (28 f) | Play once, clamp | |

`attack3` is rooster-only. It is **not** a substitute for `attack1` or `attack2`. Bind it as a third combat path (ranged / breath). Loop it the same way dragon `attack1` loops.

---

## 4. Coordinate / origin / facing

Authored in Blender **Z-up, metres**. Exported with `export_yup=True`. Walk / attacks have **no root motion** — the server translates the entity.

The Building Viewer is **Z-up** and wraps every creature with `rotation.x = π/2`. **Do not copy that wrap into the game** if Grindscape is already Y-up. Use the glTF / Three.js Y-up convention below.

### Shared facing (glTF / Three.js Y-up)

Match **CowF / CowM / Sheep**: at `rotation.y = 0` the visual head / snout / beak is **+Z**. Walk uses `atan2(dx, dz)` with **no extra π**.

Do **not** add a dragon-only +π yaw. Older dragons faced −Z; the shipped GLBs are yawed to +Z like the cows. Viewer catalog includes Cow / Sheep under Creatures as the reference.

- **+Y** = up.
- Visual forward (cow head, bird beak, dragon snout) = **+Z**.
- Dragons: origin ≈ waist. Farm birds: origin = ground between the feet.
- Hen / rooster bone `Head` sits toward the **rump**; bone `Tail` / `MouthFire` sit toward the **beak**. Use the mesh, not the Head bone, for facing.

All five dragon colors share mesh scale. Size hitbox from GLB bounds. No extra catalog scale.

Stylized size (~waist-high on a 1.8 m player):

| | Height | Length | Width |
|---|---|---|---|
| Chicken | ~0.94 m | ~0.99 m | ~0.49 m |
| Rooster | ~0.96 m | ~1.00 m | ~0.55 m |

---

## 5. VFX contract

### Dragons — fire on `attack1` only

Packed bones `FireMouth` / `FireBreath` carry emissive `DragonFire*` icospheres. They scale up during `attack1` and stay tiny on every other clip.

The viewer **hides** those meshes and plays additive VFX (`DragonFireBreath.tsx`) while `attack1` is active:

- Attach: `Bone.004` / `Bone004` (snout), `Bone.LowerJaw`, `FireMouth`, `FireBreath`.
- Three.js often drops dots (`Bone.004` → `Bone004`). Normalize names.
- Timing on the 2.0 s clip (seconds, not 0–1): mouth glow ~0.58–1.82, jet ~0.80–1.72.
- Look: **thick jet** — camera-facing flame slices + ~1100 particles. Not sparks.

**Color the fire to match the dragon.** Do not ship orange on every color.

| Dragon | Hot | Mid | Ember | Light |
|---|---|---|---|---|
| Green | `(0.85, 1.0, 0.45)` | `(0.18, 0.95, 0.22)` | `(0.02, 0.32, 0.05)` | `#22ee44` |
| Blue | `(0.80, 0.94, 1.0)` | `(0.12, 0.48, 1.0)` | `(0.02, 0.10, 0.48)` | `#3b82ff` |
| Red | `(1.0, 0.55, 0.16)` | `(1.0, 0.16, 0.03)` | `(0.55, 0.02, 0.0)` | `#ff2a00` |
| Violet / Purple | `(0.96, 0.72, 1.0)` | `(0.70, 0.16, 1.0)` | `(0.28, 0.02, 0.48)` | `#c026ff` |
| Black | `(0.95, 0.88, 0.70)` | `(0.28, 0.10, 0.05)` | `(0.05, 0.04, 0.04)` | `#ff6a1a` |

Black uses a **white-hot core + dark ember** so it reads on a dark background.

Game can (a) keep packed `DragonFire*` meshes, or (b) hide them and attach client VFX as the viewer does. Either way: **no fire on `attack2`.**

### Hen — `attack2` eggs (baked in the GLB)

Bones / meshes are already in `Chicken.glb`. The game does not need extra egg models.

| Name | Parent | Role |
|---|---|---|
| `Egg_1`…`Egg_3` | `Body` | Fly the `ChickenEgg_*` spheres |
| `Fx` | armature (static) | World pad — **does not inherit Body yaw** |
| `Burst_1`…`Burst_3` | `Fx` | Plant `ChickenOmelet_*` on the ground |

Normalized clip time (`t = action.time / duration`):

| Event | t |
|---|---|
| Jump + 180° | 0.08–0.28 |
| Egg launches | **0.36, 0.44, 0.52** |
| Flight | 0.22 s of clip time each |
| Omelets appear | launch + 0.22 |
| Omelets fade | 0.94–1.00 |
| Jump + 180° back | 0.88–0.98 |

Omelets must **not** spin with the hen. That is why they parent to `Fx`, not `Body`. After the 180 they sit at world `(-side, -dist, ground)` in authoring space.

Optional: small sizzle particles at each egg world position on impact (`ChickenEggBurst.tsx`). Nice-to-have; the baked omelets already sell the attack.

### Rooster — fire on `attack2` and `attack3`

No packed fire meshes. Attach a **thick flame jet** (slices + large soft particles), not a spark spray.

| Clip | Bone | Parent | Bone +Y points | VFX window (normalized t) | Jet length |
|---|---|---|---|---|---|
| `attack2` | `ButtFire` | `Body` | visual **rump** | 0.36–0.80 | ~1.55 m |
| `attack3` | `MouthFire` | `Tail` | visual **face / beak** | 0.22–0.82 | ~1.85 m |

Detect bones case-insensitively (`/^buttfire$/i`, `/^mouthfire$/i`). Convert bone **world** pos/dir into the VFX host’s local space (invert `matrixWorld`) — bones report world space.

Orange / gold fire (not chromatic):

- Ember `(1.0, 0.12, 0.0)`, mid `(1.0, 0.38, 0.04)`, hot `(1.0, 0.72, 0.22)`
- After the `attack2` 180, rump fire goes toward the **original** front.
- `attack3` aims along `MouthFire` at the visual beak (forward, no spin).

Viewer reference: `RoosterButtFire.tsx` (9 flame slices + ~900 particles). Do not ship the earlier spark-only look.

---

## 6. Rig (T-pose debug only)

If a creature T-poses, clip-name lookup failed. Do not retarget Mixamo onto these.

**Dragons** — armature `Armature`. Keys include `Waist`, `Bone` (chest), `Bone.001`–`Bone.004` (neck / snout), `Bone.LowerJaw`, legs `Bone_L` / `Bone_R` / `Bone.006_L` / `Bone.006_R`, wings `Bone_L.016` / `Bone_R.016`, tail `Bone.006`–`Bone.009`, plus `FireMouth` / `FireBreath`.

**Farm birds** — `Root`, `Body`, `Neck`, `Head`, `Wing_L`, `WingTip_L`, `Wing_R`, `WingTip_R`, `Tail`, `Thigh_L`, `Shin_L`, `Foot_L`, `Thigh_R`, `Shin_R`, `Foot_R`.

Hen extras: `Egg_1`–`Egg_3`, `Fx`, `Burst_1`–`Burst_3`.  
Rooster extras: `ButtFire`, `MouthFire`.

---

## 7. Integrating-agent checklist

### All

- [ ] Upload the seven **game-ready** GLBs from `viewer/public/buildings/`. Do not upload Desktop author sources.
- [ ] Point `creatureModelUrls.ts` at the new objects.
- [ ] Confirm clip names are exact lowercase as listed above.
- [ ] Bind `idle` / `walk` looping; `die` once with clamp. No root motion on walk.

### Dragons

- [ ] Attack state → **`attack1`** (loop). Fire VFX on this clip only.
- [ ] Melee / second attack → **`attack2`** (bite). No fire. Do not use attack-name fallbacks for this.
- [ ] Ignore `run` unless you add a run state. Do not map walk to `walk1`.
- [ ] Register `green_dragon`, `blue_dragon`, `red_dragon`, `black_dragon`, `violet_dragon`.
- [ ] Color fire per §5 (green / blue / red / violet / black). Purple uses the violet palette.
- [ ] Hide or keep packed `DragonFire*` meshes; either is fine. Hide if you spawn client VFX.
- [ ] Size hitbox from GLB bounds. No extra scale.

### Farm birds

- [ ] Register `chicken` and `rooster`. Remap `chimken` → `chicken`.
- [ ] If quests use `target: 'chicken'`, alias rooster kills.
- [ ] **Facing:** hen, rooster, and all five dragons face **+Z** like CowF / Sheep. No extra yaw. Drop any dragon-only +π.
- [ ] Hen `attack2` → play once. Eggs / omelets are in the GLB; do not spin omelets with the body.
- [ ] Rooster `attack2` → play once + thick rump fire on `ButtFire` (t 0.36–0.80).
- [ ] Rooster `attack3` → **loop** + thick mouth fire on `MouthFire` (t 0.22–0.82).
- [ ] Do not play hen VFX on the rooster or rooster fire on the hen.
- [ ] Size hitbox from GLB bounds (~0.94 m / ~0.96 m tall).
