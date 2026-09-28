# Staff spells and fishing previews

In CharacterCreation, choose Male Rework or Female Rework, open **Tools**, equip a staff or rod, then use the **Preview** button above the tool list. The timeline pauses and seeks both the character and effect together. Arrow keys step a focused timeline by one frame; Shift + Arrow steps half a second.

## Staffs

Seven styles preserve the spell identities in GrindScape's item definitions: Topaz / Static Shock, Spinel / Chakra Blast, Peridot / Blitz, Ruby / Heart Breaker, Rubellite / Scarlet Scorch, Enchanted, and Embervein. Each has a charge at the staff focus, directed release, trail, and fading impact. Embervein retains its violet magic identity with warm accents.

Casting clips last 2.8 seconds with anticipation, release, and recovery. Each rework model has its own fitted clip. Effects use 96 reusable particle positions, up to six instanced cores, four arc strands, and one ring: four draw calls without bloom, lights, textures, or particle spawning.

## Fishing

All eight rods include a `FishingLineGuides` mesh and measured `FishingGrip` / `FishingTip` attachment nodes. Tidecaster and Enchanted Fishing Rod are available in the picker. The existing Fungal asset ID/file spelling is retained for compatibility; its display name is corrected.

The 10-second fishing loop raises the rod slightly, drops the line to a ground point 1.5 metres ahead, settles, then retrieves. Feet stay planted. The guide string is embedded in each downloadable rod GLB. The moving free line is a lightweight runtime tube (400 triangles), attached to the model's actual tip and driven by the animation timeline. There is no reel spool. The ground endpoint assumes the viewer's flat Z=0 ground; a game integration should supply its fishing surface point.

## Source and regeneration

- `viewer/src/utils/toolEffects.ts`: reusable bounded spell and line controllers, timings, palettes.
- `viewer/src/components/ToolEffects.tsx`: equipment attachment and viewer timeline integration.
- `viewer/src/data/toolEffectAnchors.json`: staff focus positions in tool-local glTF coordinates.
- `viewer/public/tools/fishing_rods/`: eight updated GLBs.
- `viewer/public/animations/{Female,Male}{Fishing,MagicCast}.anim.json`: four fitted delta clips. The manifest keeps legacy selection IDs and chooses male files for Male Rework.
- `scripts/skill-tools/build-motion.mjs`: deterministic 30 fps two-bone IK motion generator.
- `scripts/skill-tools/rig-rods.py`: Blender generator that replaces existing guide strings and tip nodes without adding duplicates.

From the repository root:

```sh
node scripts/skill-tools/build-motion.mjs
blender -b --python scripts/skill-tools/rig-rods.py
node scripts/skill-tools/verify.mjs
```

The animated spell/free-line effects are runtime code, not baked into the rod GLBs. GrindScape's game source has not been changed by this preview implementation.

## Verification

`verify.mjs` checks all four clips for finite normalized rotations, matching loop endpoints, sub-millimetre foot stability, and paused seeking. It checks all eight GLBs for one string mesh and one tip node, the free line's 1.5-metre landing point and loop reset, all seven effects' visibility/lifecycle, bounded geometry, and resource disposal. The viewer production build passes. All seven staff selections and all eight rod selections were exercised in the browser without console errors; male and female poses were inspected.

## Fishing grip and line alignment

Each rod has a measured handle centre. The mount puts this inside the right palm, removes sideways asset cant, and keeps the rod guides underneath the shaft. Both arms reach forward: the left hand supports the handle 10 cm ahead of the right hand, with the grip 30–31.5 cm ahead of the rig origin. The shaft angles upward; the authored rod flex is retained. The feet are spread 10 cm wider and stay planted during lift, hold, and retrieve. A slight forward spine bend and softened knees give the fishing stance a relaxed lean. The handle crosses each palm diagonally so the elbows remain below the hands, at least 10 cm below the shoulders, and outside the torso silhouette. An outward/downward elbow pole prevents the upper arms from folding into the chest. Arm lengths are preserved. Fingers conform to that diagonal handle, and wrist correction stays below 20 degrees on both rework rigs.

The rod string follows measured shaft sections, excluding bulky reel ornaments. Its final vertex ring and `FishingTip` share the same anchor. Animation updates first, attachment second, and the free line samples the final mounted tip in the same frame, including paused seeks and user transforms. Detaching still bypasses the hand mount for raw asset inspection.

Validation checks every sampled frame on both skeletons with all eight mounts: forward rod direction, torso clearance, both hands on the handle, lowered outward elbows, line continuity, and planted feet. Clothed browser close-ups, overhead views, and side views cover both models and the lift (1.5s), hold (3s), and retrieve (8s).

Outside fishing, rods use a separate forward-facing carry mount that pivots around the existing right palm. It points forward at a slight upward angle to clear the body and ground, with the grip shifted 5.5 cm up the handle from its pommel. The shared idle/walk/run clips and arm/leg motion are unchanged. A rod-only runtime finger contact pose closes the right hand around the mounted handle; it restores the original fingers before each mixer update and on unequip. Carry validation samples all seven idle/walk/run variants on both rigs with all eight rods.
