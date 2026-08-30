# Grindscape Handoff — Sand Bucket

**Source repo:** `CharacterCreation`  
**Destination:** Grindscape game client  
**Date:** 2026-08-24  
**Depends on:** `GRINDSCAPE_FARMING_VESSELS_HANDOFF.md` (already shipped)

This is a **delta** on the existing farming-vessel work. Water / milk / compost / watering can do not change. Sand is a new fill kind on the **same** bucket mesh, plus one new locomotion clip for running while a bucket is in hand.

---

## 1. What to ship

| Game item | Mesh GLB | Contents | Dump clip | Run clip |
|---|---|---|---|---|
| Sand Bucket | `EmptyBucket.glb` | sand | `FemaleBucketPour` | `FemaleBucketRun` |

Rules (same contract as compost):

- **Do not** author or upload a second filled GLB. Sand is runtime VFX parented to `EmptyBucket.glb`, exactly like compost.
- Same grip as every other bucket (`SHARED_BUCKET_TOOL_IDS` now includes `sand_bucket`).
- Watering can still holds **water only**. Never sand.
- Suggested id: `sand_bucket`.
- After a successful dump, convert to `empty_bucket` (or fill = 0) using existing vessel logic.

`FemaleBucketRun` is **not sand-only**. Use it whenever the player sprints with **any** bucket in the right hand (`empty_bucket`, `water_bucket`, `milk_bucket`, `compost_bucket`, `sand_bucket`). `FemaleRun` / `FemaleRunV3` will pump the right arm and yank the handle out of the palm.

---

## 2. GLB

Same file already in game from the vessels handoff:

```
viewer/public/tools/farming/EmptyBucket.glb
```

Origin, scale, interior fill, and mouth (+Y) are unchanged. Copy from §2 of the vessels handoff.

Do **not** upload `SandBucket.glb`. If Cloudinary still needs a public id for the item, point the 3D url at the existing `EmptyBucket` asset.

---

## 3. Thumbnail

Local: `viewer/public/tools/farming/thumbs/SandBucket_thumb.png`

Cloudinary (folder `Inventory/Tools/Farming`, same `_thumb` convention):

| Item | Thumbnail PNG |
|---|---|
| Sand Bucket | https://res.cloudinary.com/dyd9wffl9/image/upload/v1787618210/SandBucket_thumb.png |

Wire this to the item’s `icon` / `png` field. Primary click still equips, same as the other farming items.

---

## 4. Animation — `FemaleBucketRun` (new)

| Clip | File | Duration | Loop | Use with |
|---|---|---|---|---|
| `FemaleBucketRun` | `viewer/public/animations/FemaleBucketRun.anim.json` | 0.854 s | true | any equipped bucket, sprint / run |

Register it the same way as `FemaleRunV3` / `FemaleBucketPour`.

### Format

Identical to the other Mixamo JSON specs:

- `meta.absolute` unset / false
- Rotation keys are **deltas from bind / rest**: `bone.quaternion = restQuat * keyframeQuat`
- Quaternion order `[x, y, z, w]`
- Converter: `viewer/src/utils/animSpecToClip.ts`

### What it is

`FemaleRunV3` legs, hips, torso, and **left** arm. Right arm / forearm / hand / shoulder pinned to the **FemaleIdle hang** so the bucket stays in `mixamorigRightHand`. Right fingers use the `FemaleBucketPour` grip.

Do **not** play this clip on a watering can, sword, or empty hand. Those keep `FemaleRun` / `FemaleRunV3`.

Dump while moving still uses `FemaleBucketPour` (not this clip).

---

## 5. VFX — sand is compost’s twin

Port from `viewer/src/components/VesselLiquid.tsx`. Kind flag is now `water | milk | compost | sand`.

Sand is **chunky packed grains**, not a liquid. Same emit / drain rules as compost:

- In-vessel fill: yes (tan packs, not a transmissive surface)
- Movement slosh splash: **no**
- Ground marks: **only during `FemaleBucketPour` pour window** (0.58 → 1.55)
- One bucket worth of chunks; stop when fill hits 0
- Ground clod life ~2.0 s

Palette:

```
sand:  surface #d4b483  deep #b8955c  drop #c4a46a  packed grains #a67c4a–#e6d09a
```

Do not reuse the compost browns. Sand must read as dry beach / builder’s sand.

---

## 6. Integrating-agent checklist

1. Add item `sand_bucket`. Mesh = existing `EmptyBucket.glb`. Icon = Cloudinary thumb in §3. Contents flag = `sand`.
2. Equip on primary click to `mixamorigRightHand` with the shared bucket grip.
3. Import `FemaleBucketRun` (rest × delta). Play it instead of `FemaleRun*` while any bucket is equipped and the player is running.
4. Dump: `FemaleBucketPour` + rim dump VFX using the **sand** palette (same window as compost).
5. No sand in the watering can. Empty bucket: no fill, no dump VFX.
6. After dump, empty the item.

### Acceptance

- Inventory icon is the wooden bucket with a tan sand mound (not brown compost).
- Equipped sand bucket shows packed sand in the vessel.
- Run: bucket stays in the right hand; arm does not pump.
- Dump: sand leaves the rim and leaves tan clods on the ground, pour-window only.
- Water / milk / compost / watering can still behave as in the vessels handoff.

---

## 7. Files

```
viewer/public/tools/farming/EmptyBucket.glb              # unchanged; do not ship a new mesh
viewer/public/tools/farming/thumbs/SandBucket_thumb.png
viewer/public/animations/FemaleBucketRun.anim.json
viewer/public/animations/manifest.json                   # FemaleBucketRun row
viewer/src/types/tools.ts                                # sand_bucket + shared grip
viewer/src/components/VesselLiquid.tsx                   # kind: "sand"
```

Generator (this repo only, not needed in-game): `generate_female_bucket_run.py`, `render_farming_tool_thumbnails.py`.
