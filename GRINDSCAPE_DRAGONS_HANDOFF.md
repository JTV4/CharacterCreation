# Grindscape Handoff — Chromatic Dragons

> **Superseded 2026-08-28.** Use [`GRINDSCAPE_CREATURES_HANDOFF.md`](./GRINDSCAPE_CREATURES_HANDOFF.md) (dragons + hen + rooster, including color fire palettes). Kept for history.

**Source repo:** `CharacterCreation`  
**Destination:** Grindscape game client  
**Date:** 2026-08-27  
**Owner intent:** Replace the un-authored Cloudflare dragon GLBs with five skinned creatures that share one rig and the clip set below. Each GLB is a **single armature + skinned mesh** with clips baked in. Creatures do **not** load Mixamo files. Upload the five game-ready GLBs to **Cloudflare R2** (`assets.grindscape.com`); do not split clips into separate files.

Reference implementation (this repo’s Building Viewer):

- Catalog: `viewer/src/types/buildings.ts` → `green_dragon` / `blue_dragon` / `red_dragon` / `black_dragon` / `violet_dragon`
- Playback: `viewer/src/components/BuildingViewer.tsx` (`idle` / `walk` / `run` / `attack1` loop; `attack2` / `die` once + clamp)
- Fire VFX (viewer only): `viewer/src/components/DragonFireBreath.tsx` — keyed to clip **`attack1` only** (not `attack2`)
- Generator: `generate_green_dragon_firebreath.py`
- Clip-name rule: `.cursor/rules/creature-animation-naming.mdc`

Preview locally: `cd viewer && npm run dev` → Buildings → **Green / Blue / Red / Black / Violet Dragon**. Clip buttons are bottom-left. Default is `idle`. Use **attack2** to preview the melee bite.

---

## 1. What to ship

Five GLBs. Same clip set in each. Same rig.

| File | creatureTypeId | Display name | Component name |
|---|---|---|---|
| `GreenDragon.glb` | `green_dragon` | Green Dragon | `PioneeringGreenDragon` |
| `BlueDragon.glb` | `blue_dragon` | Blue Dragon | `PioneeringBlueDragon` |
| `RedDragon.glb` | `red_dragon` | Red Dragon | `PioneeringRedDragon` |
| `BlackDragon.glb` | `black_dragon` | Black Dragon | `PioneeringBlackDragon` |
| `VioletDragon.glb` | `violet_dragon` | Violet Dragon | `PioneeringVioletDragon` |

IDs are **lowercase snake_case**.

Unrigged textured meshes live at `~/Desktop/Models/Creatures/Dragons/{Color}Dragon.glb` (do not upload those). The generator binds them to the shared dragon armature and bakes clips.

Copy game-ready files from the viewer paths in §2. Desktop mirrors: `~/Desktop/Models/Creatures/{Color}Dragon.glb`.

---

## 2. GLBs — use these files

| File | Path | Size (approx.) |
|---|---|---|
| Green | `viewer/public/buildings/GreenDragon.glb` | ~1.4 MB |
| Blue | `viewer/public/buildings/BlueDragon.glb` | ~1.4 MB |
| Red | `viewer/public/buildings/RedDragon.glb` | ~1.4 MB |
| Black | `viewer/public/buildings/BlackDragon.glb` | ~1.4 MB |
| Violet | `viewer/public/buildings/VioletDragon.glb` | ~1.4 MB |

Textures are **packed inside the GLB**. PascalCase filenames, no spaces.

### Cloudflare R2 (`assets.grindscape.com`)

Source (un-authored) objects already at the bucket root used the old Cloudinary public IDs — **do not point the client at these**:

| Color | Existing R2 object |
|---|---|
| Green | `https://assets.grindscape.com/green_dragon_h5hwgg.glb` |
| Blue | `https://assets.grindscape.com/blue_dragon_aluniv.glb` |
| Red | `https://assets.grindscape.com/red_dragon_dycsmg.glb` |
| Black | `https://assets.grindscape.com/black_dragon_kxzdqp.glb` |
| Violet | `https://assets.grindscape.com/violet_dragon_qr1muu.glb` |

Upload **the five game-ready files from §2**. Suggested object keys:

- `GreenDragon.glb` / `BlueDragon.glb` / `RedDragon.glb` / `BlackDragon.glb` / `VioletDragon.glb`

Then point `creatureModelUrls.ts` at the new keys.

---

## 3. Animation clips (required)

Each GLB embeds **these 6 tracks** on the dragon armature. Names are **exact, lowercase**.

| Game state | Clip name | Duration | Playback | What it is |
|---|---|---|---|---|
| Idle | `idle` | 3.000 s (72 f @ 24 fps) | **Loop.** First/last pose match. | Breath, head look, wing lift, tail sway. |
| Walk | `walk` | 1.333 s (32 f @ 24 fps) | **Loop.** In-place; **no root motion.** | Diagonal trot. Server translates the entity. |
| Ranged attack | `attack1` | 2.000 s (48 f @ 24 fps) | **Loop.** | Fire-breath (rear-up then blast). This is the clip the existing attack state should keep using. |
| **Melee attack** | **`attack2`** | **1.500 s (36 f @ 24 fps)** | **Play once** (clamp at last frame), or loop if melee combat loops like `attack1`. | **Bite:** rear-up, jaws open, lunge forward, snap shut. **No fire.** Feet stay planted. |
| Die | `die` | 1.500 s (36 f @ 24 fps) | **Play once.** Clamp at last frame. | Legs sprawl, drop straight down (no side roll). |

**Extra (not a game state):** `run` — 0.667 s (16 f @ 24 fps), looping in-place gallop. Safe to ignore; do not rename it to `walk`.

**Shipped set:** `idle`, `walk`, `run`, `attack1`, `attack2`, `die`.

There is **no** `walk1` / `walk2` / `Idle` / `attack_melee` / `attack_fire`. Extra idles (`idle_1`…`idle_5`) are not shipped; `idle` is the only idle.

### Binding `attack2` (melee)

The current creature state machine only looks up `attack1` for the Attack state. **`attack2` will T-pose / be ignored until the client plays that clip name.**

To use the melee bite:

1. Do **not** rename `attack2` to `attack1` (that would replace fire-breath).
2. Add a melee / second-attack path that plays clip **`attack2`** (exact lowercase).
3. Do **not** spawn fire VFX on `attack2`. Fire is `attack1` only.
4. Suggested playback: play once per bite and clamp, **or** loop if your combat loop restarts the clip each swing the same way as `attack1`.

Attack lookup fallbacks (`attack`, `Attack`, `Melee`, …) must **not** be pointed at `attack2`. Those aliases still mean “the primary attack clip,” which is `attack1`.

Do **not** look for `death`, `dying`, `Death`, `Walking`, `Idle`, `Attack`, `Idle.001`, or `Armature|Idle`.

---

## 4. Coordinate / origin / scale

Authored in Blender **Z-up, metres**. Exported with `export_yup=True` (Blender → glTF: `X' = X`, `Y' = Z`, `Z' = −Y`).

### Authoring space (Blender, before export)

- Origin ≈ **waist**, feet sitting near **Z = 0**.
- **+Z** = up.
- **+Y** = forward (snout).
- **+X** = right.

### Runtime space (glTF / Three.js)

- **+Y** = up.
- Forward (snout) is **−Z** after the Blender Y-up export (same as existing creatures).
- Walk / run / attacks have **no root motion**.

All five colors are the same mesh scale. Size the hitbox / health bar from GLB bounds after upload; do not add an extra scale in the catalog.

---

## 5. Attack fire (`attack1` only)

`attack1` scales two mouth-parented bones, `FireMouth` and `FireBreath`, which carry emissive icosphere meshes (`DragonFire*` materials).

`attack2` keeps those bones scaled away. The **Building Viewer hides the packed fire meshes** and plays additive particle VFX (`DragonFireBreath.tsx`) only while `attack1` is active.

The game client can:

1. **Use the packed meshes** as-is (they scale up during `attack1` and stay tiny on `attack2` / idle / walk / die), or
2. **Hide `DragonFire*` / icosphere meshes** and attach its own VFX to `Bone.004` (snout) / `Bone.LowerJaw` / `FireBreath` **only on `attack1`**.

Three.js often drops dots in bone names (`Bone.004` → `Bone004`). Match with a normalized lookup.

---

## 6. Rig (for debugging T-poses only)

One armature named `Armature` per GLB. Not Mixamo names. If a dragon T-poses, clip-name lookup failed.

Clips key (among others): `Waist`, `Bone` (chest), `Bone.001`–`Bone.004` (neck / snout), `Bone.LowerJaw`, front legs `Bone_L` / `Bone_R` (+ `.001` elbow, `.002` wrist, `.003` foot), hind `Bone.006_L` / `Bone.006_R` (same suffixes), wings `Bone_L.016` / `Bone_R.016`, tail `Bone.006`–`Bone.009`, plus `FireMouth` / `FireBreath`.

---

## 7. Integrating-agent checklist

- [ ] Upload the five **game-ready** GLBs from `viewer/public/buildings/{Color}Dragon.glb` to Cloudflare R2. Do not upload the unrigged `~/Desktop/Models/Creatures/Dragons/` meshes.
- [ ] Point `creatureModelUrls.ts` at the new objects.
- [ ] Confirm clip names on the uploaded files are exactly `idle`, `walk`, `run`, `attack1`, `attack2`, `die`.
- [ ] Bind existing Attack state → **`attack1`** (fire-breath). Loop it as today.
- [ ] Bind melee / second attack → **`attack2`** (bite). Do not use attack-name fallbacks for this. No fire VFX.
- [ ] Bind `idle` / `walk` looping; `die` once with clamp.
- [ ] Ignore `run` unless you add a run state later. Do not map walk to `walk1`.
- [ ] Register `creatureTypeId` `green_dragon`, `blue_dragon`, `red_dragon`, `black_dragon`, `violet_dragon`.
- [ ] Decide whether in-game fire uses packed `DragonFire*` meshes or a client VFX pass (viewer hides the meshes). Fire on `attack1` only.
- [ ] Size hitbox from GLB bounds. No extra scale in the GLB.
