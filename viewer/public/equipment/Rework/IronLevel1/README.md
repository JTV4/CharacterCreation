# GrindScape — Iron Armor, Level 1

Five independent wearables for each active Male Rework and Female Rework body: Helmet, Upperbody, Gloves, Lowerbody, Boots. This is a new set, with separate meshes fitted to each body.

The charcoal forged iron, broad faceted plates, restrained edge wear, padded underlayers, and brown leather are based on the supplied iron bar. The starter design has no gold, jewels, horns, or elaborate ornament. The helmet leaves the face visible; the female cuirass provides full coverage.

## Use in CharacterCreation
Open http://localhost:5173/Avatar while the existing viewer development server is running. Select Male Rework or Female Rework, then enable the five pieces under **Iron Armor · Level 1**. Use No hair with the fitted helmet. Existing animation controls drive the wearables.

Installed assets: `viewer/public/equipment/Rework/IronLevel1/{Male,Female}/*.glb`.
The new manifest is `viewer/public/equipment/equipment_spec_iron_l1.json`.

## GrindScape handoff
The same ten GLBs are copied into `client/public/equipment/Rework/IronLevel1/{Male,Female}/`, with a manifest in `client/public/equipment/Rework/IronLevel1/equipment_spec_iron_l1.json`.
These are local game assets. The live item database, item IDs, combat bonuses, shop inventory, and crafting recipes have not been changed. Level 1 is recorded in the set manifest and mesh metadata.

## Package
- `Male/` and `Female/`: five separately equipable GLBs and a CompleteOutfit.glb containing all five pieces without the body.
- `Source/`: editable Blender files with the matching reference body and rig, plus generation and validation scripts.
- `Previews/`: front, three-quarter, back, and bent-joint fit-check renders of the real meshes.
- `IronArmor_Preview.png`: side-by-side preview of the real fitted meshes.
- `Reference/IronBar.png`: supplied design reference.
- `validation.json`: geometry counts and contributing bones.
- `roundtrip_validation.json`: export/reimport checks for all ten equipment files.

## Rig and materials
GLBs use glTF Y-up, meters, the original Mixamo bone names and bind transforms. Blender sources are Z-up and face -Y. Their centered origins match the current `appearance/v6/Models/BaseMale_Appearance.glb` and `BaseFemale_Appearance.glb`; soles are approximately Z=-0.889 m in Blender before the viewer's normal lift.

Do not apply an additional garment translation or rescale independently from the body. When sharing a live skeleton, retain the equipment's exported inverse bind matrices. Each vertex has at most four normalized influences. Both hands and both feet are included in their corresponding slot.

Materials are embedded PBR colors: dark iron, forge-tone variations, brighter iron edging, padded charcoal cloth, and leather. No external armor textures are needed. This set is approximately 38,000 triangles per complete outfit; it has one authored detail level, not a generated LOD chain. “Level 1” means item progression level.

## Verification
All ten GLBs were reimported into Blender: zero unweighted vertices, normalized weights, matching bone names, sub-micrometer rest-height differences, and finite posed coordinates. Both complete sets were viewed with the existing walking animation in CharacterCreation. Front/back and bent elbow/knee renders were visually inspected. This is a sampled fit check, not an exhaustive guarantee for every possible pose or mixed equipment combination.

CharacterCreation production build passed (`npm run build`). The integration preserves the iron PBR materials and uses the authored inverse binds. Existing stencil/type issues encountered during the build were corrected without changing character designs.
