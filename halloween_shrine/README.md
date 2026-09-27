# Harvest Warden — Halloween offering shrine

An original Blender-built interpretation of the supplied reference for GrindScape: pumpkin-headed timber effigy, crooked witch hat, five hanging jack-o'-lanterns, folded straw, purple bat pennants, stone dais, gilded seals and a coin basin.

This deliverable contains static art only. Coin payments, rewards, interaction code, collision logic and placement in the live game are not implemented.

## Files

- `HalloweenOfferingShrine.blend`: editable source with individual named parts, consolidated runtime meshes, and a separate preview rig.
- `HalloweenOfferingShrine_Web.glb`: recommended game export, quantized with gltfpack. Standard glTF 2.0 and `KHR_mesh_quantization`; no Draco or Meshopt decoder needed.
- `HalloweenOfferingShrine_LOD1_Web.glb`: distance model. Select one LOD at a time in the consuming application.
- `HalloweenOfferingShrine.glb` and `HalloweenOfferingShrine_LOD1.glb`: full-precision interchange versions.
- `generate_halloween_shrine.py`: deterministic Blender generator.
- `hero.png`, `front.png`, `game_view.png`, `rear.png`: rendered inspection views.
- `preview.html` and `vendor/`: local interactive GLB inspector. Vendor files are the project's existing Three.js version, with its license.
- `asset_stats.json`, `validation_summary.json`: geometry and validation results.

## Coordinates and use

| Game export | Triangles | File size | Visible material batches |
| --- | ---: | ---: | ---: |
| Main Web GLB | 18,153 | 702.3 KiB | 3 |
| LOD1 Web GLB | 8,891 | 435.5 KiB | 3 |

Both Web exports passed Khronos glTF Validator with **0 errors and 0 warnings**. Informational empty-node messages refer to the intentional integration markers.

One unit is one meter. Ground-centered origin, approximately 6.42 m wide, 3.46 m deep and 5.80 m high, including overhead boughs. The base itself is approximately 4.67 m wide and 3.46 m deep. Blender is Z-up with the offering side toward -Y. Game GLBs are standard Y-up with the offering side toward +Z. Start with scale `[1, 1, 1]`.

Three consolidated visible mesh/material batches: `Shrine_Structure`, `Shrine_Gold`, and `Shrine_Embers`. Matte surfaces and gold use vertex colors; there are no textures, transparency, skinning or animation. The straw uses opaque geometry, avoiding alpha sorting. Emission uses a constant amber value with `KHR_materials_emissive_strength`. The GLB contains no cameras, lights or studio floor. Bloom is optional and supplied by the game; emission remains visible without it and does not illuminate surrounding scenery by itself.

Three empty transform nodes are reserved for later integration:

| Node | GLB position (X,Y,Z) | Intended use |
| --- | --- | --- |
| `OfferingPoint` | (0, 1.5, 0.78) | Coin / reward effect origin |
| `InteractionPoint` | (0, 0, 2.2) | Approach position in front of steps |
| `NameplatePoint` | (0, 5.95, 0) | Label position |

These are markers, not functioning interactions. Use a simple base-sized collision volume when integrating, rather than the full branch bounds. No collider is embedded in the art export. Actual collision and approach distances should be verified against the eventual world placement and player controller.

## Existing project conventions checked

- GrindScape `client/components/terrain/objects/MedievalBuilding1.tsx`: `useGLTF`, named structure meshes, default scale `[1,1,1]`, separate interaction/collision handling.
- GrindScape `client/components/terrain/forging/Furnace.tsx`: GLB-based workstations and external hotspot interaction logic.
- CharacterCreation `generate_storehouse.py` and its rendered previews: meter-scale medieval stone/timber construction, standard Blender GLB export and named modular parts.
- CharacterCreation `viewer/src/components/BuildingViewer.tsx`: building inspection workflow. That viewer currently uses a Z-up camera; the supplied independent inspector correctly displays the standard Y-up game export.

The existing game and viewer source files were not modified. All new work resides in this folder; final Web GLBs are also copied to `viewer/public/buildings/Halloween/` for the project's asset library.

## Rebuild

From this folder:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python generate_halloween_shrine.py
gltfpack -i HalloweenOfferingShrine.glb -o HalloweenOfferingShrine_Web.glb -kn -km -ke
gltfpack -i HalloweenOfferingShrine_LOD1.glb -o HalloweenOfferingShrine_LOD1_Web.glb -kn -km -ke
```

To inspect locally:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open `http://127.0.0.1:8765/preview.html`. The inspector includes hero, elevated game and rear views, LOD switching, wireframe and night lighting. All dependencies are local; no CDN or network asset service is used.

## Verification scope

The game-ready exports are checked with Khronos glTF Validator and loaded visually in a Three.js browser viewer. Renders inspect front, rear and elevated views. Geometry size and draw-call figures describe this asset only; frame rate within the full GrindScape scene has not been benchmarked. Shadow passes and additional game effects can add rendering work.
