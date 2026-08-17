# Grindscape Handoff — GrindScape Flagpole

**Source repo:** `CharacterCreation`  
**Destination:** Grindscape game client  
**Date:** 2026-08-16  
**Owner intent:** Place a branded village / castle banner in the world. One GLB. The cloth already has a looping wind clip baked in. **Do not author a second wave in a shader, cloth sim, or vertex animation.** Play the embedded glTF clip.

Reference implementation (this repo’s Building Viewer):

- Catalog: `viewer/src/types/buildings.ts` → id `grindscape_flag`
- Playback: `viewer/src/components/BuildingViewer.tsx` (`BuildingModel` — `AnimationMixer` + `LoopRepeat`)
- Generator: `generate_grindscape_flag.py`

Preview locally: `cd viewer && npm run dev` → Buildings → **GrindScape Flag**. The wave should start immediately.

Suggested game IDs (match the viewer where possible):

- structure / prop id: `grindscape_flag` (finished waving banner)
- construction id: `grindscape_flag_animation` (10-stage drop-in)
- React / component names: `PioneeringGrindScapeFlag`, `PioneeringGrindScapeFlagAnimation`

---

## 1. What to ship

**Finished banner:** one file (see §2).  
**Construction:** same 10-stage drop-in as the well / dock / workstations (see §5b).

| Piece | In the GLB? | Notes |
|---|---|---|
| Grey brick pedestal | yes | static mesh `flagpole_base` |
| Wooden pole + iron bands + gold finial | yes | static mesh `flagpole_shaft` |
| GS logo flag | yes | skinned mesh `flag_cloth` |
| Wind motion | yes | clip named **`wave`**, 4.0 s, loop |
| Extra VFX / particles / wind sound | no | optional in-game, not in the GLB |

Do **not** use `~/Desktop/Models/Buildings/GrindScapeFlag.glb` or the `.blend` next to it as the game source. Those are authoring mirrors. Copy from the viewer path below.

---

## 2. GLB — use this file

| File | Path | Size |
|---|---|---|
| Flagpole | `viewer/public/buildings/GrindScapeFlag.glb` | ~3.4 MB |

Textures are **packed inside the GLB** (brick albedo + normal + roughness, wood, iron, flag albedo with the GS logo). No sidecar PNGs are required at runtime.

### Cloudinary

If Grindscape loads world props from Cloudinary (same account as armor / tools):

- Cloud: `dyd9wffl9`
- Credentials: `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` (or `CLOUDINARY_URL`) from CharacterCreation `.env`
- Suggested folder: whatever Grindscape already uses for buildings / exterior props (not `Inventory/Tools`)
- Suggested public ID: `GrindScapeFlag`
- Upload as `resource_type: "raw"` or the same type existing `.glb` buildings use
- Reference scripts: `upload_armor_to_cloudinary.py`

Upload **this one GLB**. Do not upload the logo PNG, albedo, or blend separately.

---

## 3. Coordinate / origin contract

Authored in Blender **Z-up, metres**. The glTF exporter converts to **glTF / Three.js Y-up**.

### Authoring space (Blender, before export)

- Origin = world `(0, 0, 0)` = centre of the brick footprint, **ground plane at z = 0**.
- **+Z** = up (pole).
- **+X** = flag flies out from the pole (hoist on the pole, fly end toward +X).
- **+Y** = through the flag (billow / wind axis).
- Drop-in: put the origin on the terrain, rotate about **+Z** to face the banner.

### Runtime space (glTF after Blender export)

Standard Blender → glTF: `X' = X`, `Y' = Z`, `Z' = −Y`.

- Origin still the footprint centre, sitting on the ground.
- **+Y** = up (pole).
- **+X** = flag flies out.
- **−Z** = through the flag (billow). In Three.js this is the camera-forward axis if you look at the logo from in front of the cloth.

If Unity imports the same GLB, confirm the importer’s axis conversion once. Do not apply a second “make it Y-up” rotation on top of Three.js `GLTFLoader` — that loader already consumes glTF Y-up.

### Placement / clearance (authoring metres)

| | Value |
|---|---|
| Pedestal | grey brick, **0.92 × 0.92 m** plinth |
| Pedestal height | **0.80 m** to top of socket collar |
| Pole top (wood) | **z = 4.35 m** |
| Finial tip | **≈ 4.72 m** |
| Flag size | **1.72 m** fly × **1.08 m** hoist |
| Flag hoist | x ≈ **0.05 m** (just off the pole) |
| Flag vertical | z ≈ **3.23 → 4.31 m** (just under the collar) |
| Wind travel at fly edge | ≈ **±0.5 m** through the flag, **~1.0 m** peak-to-peak |

Keep **~1.2 m** empty on both sides of the flag plane and **~1.8 m** in the fly direction so the cloth does not clip buildings or trees at peak billow.

Yaw the whole prop so **+X (fly)** points the direction you want the banner to read. The wind clip billows **through** the cloth; it does not require a separate wind vector.

---

## 4. Scene graph (do not flatten)

Root of glTF scene `Scene` has three nodes:

```
flagpole_base          static mesh, material flag_brick
flagpole_shaft         static mesh, 3 primitives (flag_wood / flag_iron / flag_gold)
FlagArmature           skin + animation target
  ├─ flag_cloth        skinned mesh, material flag_cloth, doubleSided
  ├─ flag_top_0 … _8   top-hem bone chain (0 = hoist, 8 = fly)
  └─ flag_btm_0 … _8   bottom-hem bone chain
```

- **18 joints**, one skin named `FlagArmature`.
- `flag_cloth` is parented to the armature and uses that skin. Keep the node hierarchy. Joining, baking, or `gltfpack` without skins will freeze the flag.
- Pedestal and shaft are **not** skinned. Only `flag_cloth` moves.

### Materials

| Slot | Type | Notes |
|---|---|---|
| `flag_brick` | textured PBR | **grey** brick albedo + packed metallicRoughness + normal |
| `flag_wood` | textured PBR | pole |
| `flag_iron` | textured PBR | bands + collar |
| `flag_gold` | untextured PBR | finial (baseColor factor, metallic) |
| `flag_cloth` | textured PBR, **doubleSided** | GS logo on black cloth, gold hem |

`flag_cloth` **must stay double-sided**. The mesh is a single sheet. Backface culling makes the banner invisible from one side.

Do not swap the cloth albedo. The circular GS logo is already composited onto the rectangle (`flag_textures/FlagAlbedo.png` is generator output only).

---

## 5. Animation — play the baked clip

| | |
|---|---|
| Clip name | **`wave`** |
| Duration | **4.0 s** (sampler times ≈ 0.042 → 4.042 s at 24 fps; span is 4.0 s) |
| Loop | **yes**, `LoopRepeat` / wrap |
| Interpolation | sampled glTF (54 channels: 18 bones × 3 euler axes) |
| First / last pose | identical — seamless wrap, no hitch |

This is a **glTF animation on the armature**, not a Mixamo `.anim.json` and not a character clip. Do **not** run it through `animSpecToClip.ts` or compose with bind-pose deltas. `GLTFLoader` (Three) / the engine’s glTF importer already gives you a clip in world/armature space.

### Three.js / R3F (matches this repo’s viewer)

```ts
const mixer = new THREE.AnimationMixer(gltf.scene);
for (const clip of gltf.animations) {
  const action = mixer.clipAction(clip);
  action.loop = THREE.LoopRepeat;
  action.play();
}
// every frame:
mixer.update(deltaSeconds);
```

If you prefer to select by name: `gltf.animations.find(c => c.name === "wave" || c.name.includes("wave"))`. Play every clip on the file if in doubt — there is only one.

### Unity

- Import the GLB (or FBX if you reconvert — prefer the GLB).
- Animator / Playable on the armature, clip `wave`, **loop time on**.
- Enable **skinning**. Do not import as a static mesh.
- Humanoid avatar is **wrong** for this. Generic avatar.

### Do not

- Play the clip on the character skeleton.
- Add a cloth component, wind zone, or shader wave on `flag_cloth` (double motion).
- Call `export_apply` / freeze the armature before shipping.
- Strip `EXT` extras or run a meshopt/gltfpack pass that drops skins or animations without verifying the clip still plays.

---

## 5b. Construction — 10-stage modular assemble

Same drop-in pipeline as the well, dock, and workstations. **Do not Z-bisect `GrindScapeFlag.glb`** (that would destroy the wave armature). Use the authored modular files.

| File | Path |
|---|---|
| INIT | `viewer/public/buildings/Construction/GrindScapeFlag_INIT.glb` |
| Modular pieces | `viewer/public/buildings/Construction/GrindScapeFlagAnimation_Modular.glb` |
| Manifest | `viewer/public/buildings/Construction/grindscape_flag_animation_manifest.json` |

Reference: `viewer/src/components/BuildingViewer.tsx` → `AssemblyBuildingModel` (looks up piece ids by name, tweens `spawnOffset` → rest, stagger from the manifest). Viewer row: **GrindScape Flag Animation**.

### INIT (stage 1)

Resource piles only — **no flagpole mesh**.

| Pile | Source GLB |
|---|---|
| Sycamore logs | `LogPile_Sycamore.glb` |
| Iron ore | `OrePile_Iron.glb` |
| Raw catfish | `RawFishPile_Catfish.glb` |

### Stages 2–10 (manifest `stageOrder`)

| Stage key | Label | Piece that unlocks |
|---|---|---|
| `foundation` | 2 — Plinth | `flag_plinth` |
| `walls_a` | 3 — Pedestal | `flag_body` |
| `walls_b` | 4 — Cap | `flag_cap` |
| `walls_c` | 5 — Socket | `flag_socket` |
| `walls_d` | 6 — Lower Pole | `flag_pole_low` |
| `gable` | 7 — Mid Pole | `flag_pole_mid` |
| `framing` | 8 — Upper Pole | `flag_pole_high` |
| `eaves` | 9 — Finial | `flag_finial` |
| `complete` | 10 — Flag | `flag_cloth` |

Each stage’s `stages[key]` list is **cumulative** (everything unlocked so far). Tween: `staggerSec` 0.07, `easeOutCubic`, `startScale` 0.92, drop from `spawnOffset` z = 2.20 m (authoring Z-up).

The modular `flag_cloth` is the **rest-pose sheet** (no armature). For the finished, waving banner, swap to `GrindScapeFlag.glb` + clip `wave` after stage 10 (or keep a separate “complete” prop). Playing `wave` on the modular GLB will do nothing — skins were not exported there.

Generator: `generate_flagpole_animation.py`.

---

## 6. Scale / engine notes

- Scale is **1.0**. Real-world metres. A player (~1.8 m) stands well below the cloth; the logo sits ~3.2–4.3 m up.
- If Grindscape world props are authored at a different unit scale, scale the **root** uniformly. Do not scale only the cloth.
- Cast shadows: yes for pedestal + pole. The cloth can receive / cast; if overdraw is a problem, disable cloth shadows first.
- Lightmap / static batch: **only** `flagpole_base` and `flagpole_shaft`. Never lightmap-batch `flag_cloth` or the armature.

---

## 7. Game implementation checklist

1. Copy `viewer/public/buildings/GrindScapeFlag.glb` into the Grindscape prop / building pipeline (or upload that file to Cloudinary and point the prop URL at it).
2. Register a world prop `grindscape_flag` (or your existing building-prop table).
3. Place origin on the terrain. Rotate about up so the logo faces the plaza / road. Fly direction is local +X.
4. On load, create an `AnimationMixer` (or engine equivalent) on the glTF scene, play clip `wave`, loop forever.
5. `mixer.update(dt)` every frame while the prop is visible. Pause/stop when culled if you want; resume from current time is fine.
6. Leave materials as imported. Confirm `flag_cloth` is double-sided in the engine.
7. Do not attach this to a hand bone. It is a **placed structure**, not a tool.

### Acceptance

- Brick base sits flush on the ground (no floating, no buried plinth). Grey masonry, not red.
- Pole is vertical; gold spear finial is at the top.
- Black flag hangs off the **top** of the pole with the circular GS logo readable from the front.
- Cloth **flows** (travelling ripple + slow sway), not a rigid flap or a frozen sheet.
- Loop is seamless (no pop every 4 s).
- Back of the flag is visible (double-sided).
- Walking around the pole does not show a missing face or a detached hoist edge.

---

## 8. Files to copy

```
viewer/public/buildings/GrindScapeFlag.glb
viewer/public/buildings/Construction/GrindScapeFlag_INIT.glb
viewer/public/buildings/Construction/GrindScapeFlagAnimation_Modular.glb
viewer/public/buildings/Construction/grindscape_flag_animation_manifest.json
```

Optional (not required in-game; useful if the other agent needs to retune or preview):

```
generate_grindscape_flag.py
preview_grindscape_flag.py
flag_textures/GrindScapeLogo.png
viewer/src/types/buildings.ts          # catalog row
viewer/src/components/BuildingViewer.tsx  # mixer playback
```

Ignore:

- `~/Desktop/Models/Buildings/GrindScapeFlag.glb` / `.blend` (authoring only)
- `flag_textures/FlagAlbedo.png` (already packed in the GLB)
- `flag_wave_frames/` and `grindscape_flag_preview_*.png` (stills)

---

## 9. If the flag looks wrong

| Symptom | Cause | Fix |
|---|---|---|
| Frozen cloth | clip not played, or skins stripped | Play `wave` on `gltf.scene`; keep the armature |
| Invisible from one side | engine forced single-sided | `material.side = DoubleSide` / disable backface cull on `flag_cloth` |
| Lying on the ground / pole along Z | double axis conversion | Use glTF as Y-up in Three; don’t also remap |
| Logo stretched / missing | cloth material replaced | Keep packed `flag_cloth` albedo |
| Hoist crawling off the pole | root scaled non-uniformly, or clip applied to the wrong node | Mixer on `gltf.scene`, uniform scale on root |
| Two waves at once | extra cloth / wind shader | Remove the extra deform |
| Pop every 4 seconds | not looping, or restarting from rest | `LoopRepeat`; do not `stop()` + `play()` each cycle |
