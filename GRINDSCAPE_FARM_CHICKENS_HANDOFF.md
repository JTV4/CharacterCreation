# Grindscape Handoff — Farm Chicken & Rooster

**Source repo:** `CharacterCreation`  
**Destination:** Grindscape game client  
**Date:** 2026-08-17  
**Owner intent:** Replace the placeholder `chimken` farm bird with two authored creatures (hen + rooster). Each GLB is a **single skinned mesh + armature** with **all four combat clips baked in**. Creatures do **not** load Mixamo files. Upload the two GLBs to Cloudinary; do not split clips into separate files.

Reference implementation (this repo’s Building Viewer):

- Catalog: `viewer/src/types/buildings.ts` → id `farm_chickens`
- Playback: `viewer/src/components/BuildingViewer.tsx` (`BuildingModel` — clip picker, `idle`/`walk` loop, `attack1`/`die` `LoopOnce` + clamp)
- Generator: `generate_farm_chickens.py`

Preview locally: `cd viewer && npm run dev` → Buildings → **Farm Animal / Chickens**. Clip buttons are bottom-left (`idle`, `walk`, `attack1`, `die`). Default is `idle`.

---

## 1. What to ship

Two GLBs. Same clip set in each. Same pattern as the cow pair (`CowF` / `CowM`).

| File | Role | creatureTypeId | Display name |
|---|---|---|---|
| `Chicken.glb` | hen | `chicken` | Chicken |
| `Rooster.glb` | rooster | `rooster` | Rooster |

IDs are **lowercase snake_case**. We are **not** using `female_chicken` / `male_chicken`.

**`chimken`:** replace it. Do **not** keep it as a third type. Point any existing spawn / loot / cooking-quest references at `chicken`. Kill quests that auto-alias `cow` → `female_cow` / `male_cow` do **not** currently alias `chicken` → `rooster`. If `target: 'chicken'` should credit rooster kills, add that alias in the quest layer (`chicken` → `chicken` | `rooster`).

Do **not** use:

- `~/Desktop/Models/Creatures/FarmCreatures/Chicken.glb` / `Rooster.glb` (unrigged author sources)
- `~/Desktop/Models/Buildings/Chicken.glb` / `Rooster.glb` (authoring mirrors)

Copy from the viewer paths in §2.

---

## 2. GLBs — use these files

| File | Path | Size |
|---|---|---|
| Hen | `viewer/public/buildings/Chicken.glb` | ~492 KB |
| Rooster | `viewer/public/buildings/Rooster.glb` | ~504 KB |

Textures are **packed inside the GLB** (one base-color map per bird). No sidecar PNGs. PascalCase, no spaces. Cloudinary appending a suffix (`Chicken_xxxxxx.glb`) is fine.

### Cloudinary

If Grindscape loads creatures from Cloudinary (same account as armor / tools / buildings):

- Cloud: `dyd9wffl9`
- Credentials: `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` (or `CLOUDINARY_URL`) from CharacterCreation `.env`
- Suggested folder: whatever Grindscape already uses for **creatures** (not `Inventory/Tools`)
- Suggested public IDs: `Chicken`, `Rooster`
- Upload as `resource_type: "raw"` or the same type existing creature `.glb` files use
- Reference scripts: `upload_armor_to_cloudinary.py`

Upload **these two GLBs only**. Do not upload `.blend` files or the unrigged FarmCreatures sources.

---

## 3. Animation clips (required)

Each GLB embeds **all 4 clips** on the bird armature. Names are **exact, lowercase**. Confirmed in the exported glTF JSON:

| Game state | Clip name | Duration | Playback |
|---|---|---|---|
| Idle | `idle` | 2.000 s (48 f @ 24 fps) | Loop. First/last pose match. |
| Walk | `walk` | 0.833 s (20 f @ 24 fps) | Loop. In-place; **no root motion**. Server translates the entity. |
| Attack | `attack1` | 0.708 s (17 f @ 24 fps) | Play once. Engine clamps at last frame. Peck / lunge + wing flare. Rooster hits harder. |
| Die | `die` | 1.125 s (27 f @ 24 fps) | Play once. Engine clamps at last frame. Collapse onto the right side. |

**Canonical set shipped:** `idle`, `walk`, `attack1`, `die`.

There is **no** extra `attack` clip (the engine alias is unnecessary if `attack1` is present). There are **no** `idle_1`…`idle_5` / `Eating` / `Grazing` extras; `idle` is the only idle.

Do **not** look for `death`, `dying`, `Death`, `Walking`, `Idle`, `Attack`, `Idle.001`, or `Armature|Idle`. Clips target the character armature only — no leftover prop actions (`Cylinder.002Action`, etc.).

---

## 4. Coordinate / origin / scale

Authored in Blender **Z-up, metres**. Exported with `export_yup=True` (standard Blender → glTF: `X' = X`, `Y' = Z`, `Z' = −Y`). Location / rotation / scale applied before export. Armature root scale `(1, 1, 1)`.

### Authoring space (Blender, before export)

- Origin = world `(0, 0, 0)` = **ground between the feet**.
- **+Z** = up.
- **+Y** = forward (beak).
- **+X** = right.

### Runtime space (glTF / Three.js)

- Origin still between the feet, sitting on the ground plane.
- **+Y** = up.
- Forward (beak) is **−Z** after the Blender Y-up export (same as existing creatures).
- No leftover 90° rest rotation on the armature.

### Size vs ~1.8 m player (bind-pose AABB, metres)

Authored mesh scale was kept (not shrunk to a real hen). Stylized / readable: about **waist-high** on a 1.8 m player. Real hen height is ~0.40 m; these are ~2.3× that.

| | Height (up) | Length (beak → tail) | Width |
|---|---|---|---|
| **Chicken** | **0.94 m** | 0.99 m | 0.49 m |
| **Rooster** | **0.96 m** | 1.00 m | 0.55 m |

Bind-pose bounds (Blender Z-up, origin at feet):

- Chicken: X `[−0.246, +0.248]`, Y `[−0.397, +0.594]`, Z `[0.000, +0.939]`
- Rooster: X `[−0.273, +0.277]`, Y `[−0.326, +0.674]`, Z `[0.000, +0.957]`

Hitbox / health-bar height can be taken from GLB bounds after upload. Mesh is a single skinned body (hen ~5.0k verts / 5.4k tris, rooster ~5.2k verts / 5.4k tris).

---

## 5. Rig (for debugging T-poses only)

One armature per GLB. Clips key these bones (not Mixamo names):

`Root`, `Body`, `Neck`, `Head`, `Wing_L`, `WingTip_L`, `Wing_R`, `WingTip_R`, `Tail`, `Thigh_L`, `Shin_L`, `Foot_L`, `Thigh_R`, `Shin_R`, `Foot_R`

If a bird T-poses in game, the clip name lookup failed (wrong name or clip targeting a non-armature node). Do not retarget Mixamo onto these.

---

## 6. Integrating-agent checklist

- [ ] Upload `viewer/public/buildings/Chicken.glb` and `Rooster.glb` to Cloudinary; paste URLs back into the creature catalog.
- [ ] Confirm clip names on the uploaded files are exactly `idle`, `walk`, `attack1`, `die`.
- [ ] Register `creatureTypeId` `chicken` and `rooster` (not `female_chicken` / `male_chicken`).
- [ ] Remove / remap placeholder `chimken` → `chicken`.
- [ ] If cooking / kill quests use `target: 'chicken'`, add an alias so rooster kills count (same idea as cow).
- [ ] Size hitbox from GLB bounds (~0.94 m / ~0.96 m tall). No extra scale in the GLB.
- [ ] Play `idle` / `walk` looping; `attack1` / `die` once with clamp. Do not add root motion on walk.
