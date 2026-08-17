# Grindscape Handoff — Farming Vessels (Bucket + Watering Can)

**Source repo:** `CharacterCreation`  
**Destination:** Grindscape game client  
**Date:** 2026-08-13  
**Owner intent:** Ship empty + filled farming handhelds, play the pour/dump clips, and recreate the liquid / compost VFX in-game. The GLBs are static meshes only. **Do not expect water, milk, compost, slosh, or puddles inside the exported GLB.**

Reference implementation (viewer):

- Tools catalog: `viewer/src/types/tools.ts`
- Hand attach: `viewer/src/components/ToolAttachment.tsx`
- VFX: `viewer/src/components/VesselLiquid.tsx`
- Clips: `viewer/public/animations/FemaleWatering.anim.json`, `FemaleBucketPour.anim.json`
- Manifest: `viewer/public/animations/manifest.json`

Preview locally: `cd viewer && npm run dev` → Farming tools + `FemaleWatering` / `FemaleBucketPour`.

---

## 1. What to ship

### Items (inventory / equip)

| Game item | Mesh GLB | Contents | Pour clip |
|---|---|---|---|
| Empty Bucket | `EmptyBucket.glb` | none | none (or same dump pose with no VFX) |
| Water Bucket | `EmptyBucket.glb` | water | `FemaleBucketPour` |
| Milk Bucket | `EmptyBucket.glb` | milk | `FemaleBucketPour` |
| Compost Bucket | `EmptyBucket.glb` | compost | `FemaleBucketPour` |
| Empty Watering Can | `EmptyTinWateringCan.glb` | none | none |
| Watering Can (full) | `EmptyTinWateringCan.glb` | **water only** | `FemaleWatering` |

Rules:

- Bucket may hold **water, milk, or compost**.
- Watering can may hold **water only**. Never milk or compost.
- Empty variants use the **same mesh** and **same grip**. No fill mesh, no particles, no puddles.
- Full variants are **not** separate authored meshes. Fill + splash is runtime VFX parented to the tool.

Suggested IDs (match the viewer where possible):

- `empty_bucket`, `water_bucket`, `milk_bucket`, `compost_bucket`
- `empty_tin_watering_can`, `water_tin_watering_can`

All bucket IDs share one grip. Both can IDs share one grip.

---

## 2. GLBs — use these files

Processed, handheld-scale, origin at the grip. **Do not use the Desktop source files.**

| File | Path |
|---|---|
| Bucket | `viewer/public/tools/farming/EmptyBucket.glb` |
| Watering can | `viewer/public/tools/farming/EmptyTinWateringCan.glb` |

### Mesh / origin contract

**Bucket**

- Origin = top wooden handle (grip).
- Body hangs along model **−Y**. Height ≈ **0.32 m**.
- Interior fill (tool/model space):
  - body / liquid center: `(0, -0.178, 0)`
  - rim / mouth: `(0, -0.05, 0)`
  - radius `0.078`, bottom radius `0.068`, depth `0.118`
- Mouth / “out of the bucket” = tool **+Y**.

**Watering can**

- Origin = rear pouring handle.
- Spout along model **−X**.
- Interior fill (tool/model space):
  - body: `(-0.095, 0.055, 0)`, radius `0.066`, depth `0.118`
  - spout tip: `(-0.28, 0.099, 0)`
  - spout dir: `(-1, 0.18, 0)` normalized

### Cloudinary

If Grindscape loads tools from Cloudinary (same account as armor):

- Cloud: `dyd9wffl9`
- Credentials: `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` (or `CLOUDINARY_URL`) from CharacterCreation `.env`
- Pattern: `public_id` = basename, `asset_folder` = inventory/tools folder (follow existing hatchet / sword uploads)
- Suggested folder: `Inventory/Tools/Farming` (or whatever Grindscape already uses for handhelds)
- Suggested public IDs: `EmptyBucket`, `EmptyTinWateringCan`
- Upload as `resource_type: "raw"` or the same type existing `.glb` tools use
- Reference scripts: `upload_armor_to_cloudinary.py`, `upload_thumbnails_to_cloudinary.py`

Upload **two GLBs only**. Do not upload a GLB per fill type.

---

## 3. Attach like a sword / hatchet

- Bone: **`mixamorigRightHand`** (`DEFAULT_TOOL_ATTACH_BONE`)
- Parent the tool to that bone every frame (world pos / quat of the bone).
- Then apply the grip offset on a child.

### Default grip (XYZ Euler degrees, viewer space)

```
Bucket:        pos [0.04, 0.09, 0.02]   rot [-90, 0, 0]   scale 1
Watering can:  pos [0.04, 0.09, 0.02]   rot [  0, 0, 90]  scale 1
```

The viewer user may have tuned these in `localStorage` (`toolTransforms`). If the in-game hand looks off, copy the live gizmo values from the CharacterCreation viewer, not only the defaults.

Do **not** add a second “pour tilt” on the tool. The clip already orients the hand. Extra tool rotation pulls the handle out of the palm.

---

## 4. Animations

| Clip | File | Duration | Loop | Use with |
|---|---|---|---|---|
| `FemaleWatering` | `viewer/public/animations/FemaleWatering.anim.json` | 2.0 s | true | full watering can |
| `FemaleBucketPour` | `viewer/public/animations/FemaleBucketPour.anim.json` | 2.0 s | true | full bucket (any fill) |

Register both in Grindscape the same way other Mixamo work clips are registered (`FemaleIdle`, `FemaleFarming`, etc.).

### Clip format (critical)

- JSON spec, **not** baked into the tool GLB.
- `meta.absolute` is **unset / false**.
- Rotation keyframes are **deltas from bind / rest**:  
  `bone.quaternion = restQuat * keyframeQuat` (Three.js multiply order).
- Quaternion order: `[x, y, z, w]`.
- Start and end of both clips are **FemaleIdle** (same arm rest as `FemaleIdle.anim.json`).
- Converter: `viewer/src/utils/animSpecToClip.ts`

If Grindscape already consumes these `.anim.json` files, drop the two new files next to the others and add manifest rows.

### Pour windows (drive VFX + drain)

| Clip | Pour start | Pour end | Mode |
|---|---|---|---|
| `FemaleWatering` | 0.48 s | 1.78 s | stream from **spout** |
| `FemaleBucketPour` | 0.58 s | 1.55 s | dump from **rim** |

Fill drains with a smoothstep over that window. Loops refill because `currentTime` wraps.

Storyboard (both clips): idle hold → move to pour → hold / pulse → return to idle.

### Authored pour poses (pose-editor XYZ degrees, deltas from rest)

**Watering can (`FemaleWatering` hold)**

| Bone | Rotation |
|---|---|
| `mixamorigSpine` | `[39, 0, 0]` |
| `mixamorigSpine1` | `[10, 0, 0]` |
| `mixamorigRightArm` | `[75, 0.702, -64]` |
| `mixamorigRightForeArm` | `[0, 0, 16]` |
| `mixamorigRightHand` | `[0, 0, 41]` |

**Bucket dump (`FemaleBucketPour` hold)**

| Bone | Rotation |
|---|---|
| `mixamorigRightArm` | `[75.447, -0.191, -85]` |
| `mixamorigRightForeArm` | `[0, 0, -79]` |
| `mixamorigRightHand` | `[0, 0, -42]` |

Idle bookend for arms (same as `FemaleIdle`):

```
RightArm     (0.60838,  0.02168, -0.01819, 0.79314)
LeftArm      (0.60838, -0.02168,  0.01819, 0.79314)
RightForeArm (0.0, 0.0,  0.17365, 0.98481)
LeftForeArm  (0.0, 0.0, -0.17365, 0.98481)
```

---

## 5. VFX — reimplement in the game

**Copy the behavior from `VesselLiquid.tsx`. Do not bake it into the GLB.**

If the game is Y-up (likely), remap the viewer’s Z-up conventions:

| Viewer (CharacterCreation) | Typical game (Y-up) |
|---|---|
| Up = **+Z** | Up = **+Y** |
| Gravity = `(0, 0, -7.2)` | Gravity = `(0, -7.2, 0)` |
| Ground kill / puddle plane `z < 0.02` | `y` near the floor under the player |
| Character “front” ≈ **−Y** | Use the character’s forward |

### When VFX is on

| Equipped | In-vessel fill | Airborne splash while moving | Ground puddle / splat |
|---|---|---|---|
| Empty bucket / empty can | no | no | no |
| Water / milk bucket | yes | small slosh only | **only during `FemaleBucketPour` pour window** |
| Compost bucket | yes (packed dirt) | **no** | **only during `FemaleBucketPour` pour window** |
| Full watering can | yes | slosh / spout drip | **only during `FemaleWatering` pour window** |

Ground marks are **pour-only**. Movement splash must not paint the floor.

### Fill kinds

**Water** — blue, transmissive, small drops, wet puddles (~3 s).  
**Milk** — cream, more opaque, slower / heavier, wet puddles (~3.4 s).  
**Compost** — matte packed dirt / finished compost, not a liquid. Dark brown to near-black, crumbly like potting soil. Same dirt-pack clumps in the bucket and in the dump. **No movement splash** — chunks leave the bucket only during `FemaleBucketPour`. Ground marks are the same dirt packs, pour-only.

Palettes (from `VesselLiquid.tsx`):

```
water:    surface #2f9ee0  deep #1568a8  drop #6ec8ff  foam #dff4ff
milk:     surface #f3ead0  deep #e2d2a4  drop #fff6dc  foam #fffdf6
compost:  surface #3b2718  deep #24160c  drop #3b2718  packed dirt #2a1a10–#4a3420
```

### Emit rules

**Watering can + `FemaleWatering`**

- Emit **only from the spout**, not the fill hole.
- Stream follows spout world direction; force a downward component so it falls.
- Drain fill 0.48 → 1.78.

**Bucket + `FemaleBucketPour`**

- Emit from the **downhill lip of the open rim**.
- Spawn just outside the mouth (tool +Y) so particles are not born inside the mesh.
- Velocity = gravity first + a little out-of-mouth. Must read as falling **out of the bucket**.
- Drain fill 0.58 → 1.55.
- Particle count is **one bucket worth**: emit only as fill drains (~30 compost chunks, ~50–64 fluid drops). Do not keep spraying after the vessel is empty.
- Compost: fewer, larger, slower chunks.

**Compost while moving (not pouring)**

- Do **not** emit. Dirt stays packed in the bucket until `FemaleBucketPour`.

### Ground puddles (pour hits only)

- Water / milk: modest wet discs that hold ~3 s then fade. Bounce droplets do **not** add extra puddles.
- Compost: one small dirt clod per landed chunk (~2.0 s). No extra ground pile from bounce bits.

---

## 6. Inventory UX

**Primary (left) click** on a farming item in the inventory / hotbar **equips it** to the right hand. Clicking the already-equipped item unequips (or swaps if another vessel is selected). Do not require a separate Equip button.

Use the Cloudinary PNG thumbs below as the item icons (`icon` / `png` field on the game item). Folder: `Inventory/Tools/Farming`. Same `_thumb` convention as armor.

| Item | Thumbnail PNG |
|---|---|
| Empty Bucket | https://res.cloudinary.com/dyd9wffl9/image/upload/v1786666744/EmptyBucket_thumb.png |
| Water Bucket | https://res.cloudinary.com/dyd9wffl9/image/upload/v1786666745/WaterBucket_thumb.png |
| Milk Bucket | https://res.cloudinary.com/dyd9wffl9/image/upload/v1786666745/MilkBucket_thumb.png |
| Compost Bucket | https://res.cloudinary.com/dyd9wffl9/image/upload/v1786666743/CompostBucket_thumb.png |
| Empty Watering Can | https://res.cloudinary.com/dyd9wffl9/image/upload/v1786666744/EmptyTinWateringCan_thumb.png |
| Watering Can (full) | https://res.cloudinary.com/dyd9wffl9/image/upload/v1786666746/WaterTinWateringCan_thumb.png |

Local copies: `viewer/public/tools/farming/thumbs/*_thumb.png`

---

## 7. Game implementation checklist

1. Point each item’s inventory PNG at the Cloudinary URL in §6. Upload the two GLBs if handhelds are not loaded from this repo.
2. Add the six items. Empty = mesh only. Full = same mesh + contents flag (`water` | `milk` | `compost`).
3. **Primary click equips** the item to `mixamorigRightHand` with the grip offsets above.
4. Import `FemaleWatering` and `FemaleBucketPour` (compose rest × delta).
5. Wire:
   - Full watering can + use/farm-water → `FemaleWatering` + spout stream + puddles.
   - Full bucket + use/dump → `FemaleBucketPour` + rim dump + puddles (fluid matches contents).
   - Compost bucket dumps packed dirt only during `FemaleBucketPour` (no walk splash).
6. Empty items: no fill, no pour VFX.
7. After a successful pour, convert the item to the empty variant (or set fill = 0) if that is existing Grindscape item logic.
8. Do not play watering on a bucket or dump on a can. Do not put milk/compost in the can.

### Acceptance

- Empty bucket / empty can look empty in hand and on the ground.
- Water bucket dump: water leaves the rim, hits the floor, leaves a puddle.
- Milk bucket dump: same motion, cream fluid + puddle.
- Compost bucket: packed dark dirt in the bucket; dump pours those same dirt packs; ground dirt only during the pour.
- Watering can: water leaves the **spout**, lands in front, puddle only during `FemaleWatering`.
- Both clips start and end on idle. Handle stays in the palm (no extra tool tilt).

---

## 8. Files to copy

```
viewer/public/tools/farming/EmptyBucket.glb
viewer/public/tools/farming/EmptyTinWateringCan.glb
viewer/public/tools/farming/thumbs/*_thumb.png
viewer/public/animations/FemaleWatering.anim.json
viewer/public/animations/FemaleBucketPour.anim.json
viewer/src/components/VesselLiquid.tsx          # VFX spec / port
viewer/src/components/ToolAttachment.tsx        # attach pattern
viewer/src/types/tools.ts                       # ids + grips
viewer/src/utils/animSpecToClip.ts              # rest * delta
```

Source art on the desktop (`Desktop/Models/Farming/FarmingPlot/`) is **not** game-ready (wrong scale / origin). Ignore it.
