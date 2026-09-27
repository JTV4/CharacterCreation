# GrindScape Thanksgiving outfits

Ten separate skinned GLBs: Hat, Upperbody, Gloves, Lowerbody and Boots for Male Rework and Female Rework. A harvest/pilgrim theme with brimmed buckled hats, pumpkin-orange vests, chocolate sleeves and bottoms, flat cream collars/cuffs, dark leather gloves, and short buckled boots. The male wears complete ankle-length trousers; the female wears a skirt with a cream apron panel, open chest neckline and integrated modesty shorts. The belt is part of Upperbody; the apron is part of Lowerbody.

## Use

Refresh CharacterCreation, choose Male Rework or Female Rework, then Equipment → Thanksgiving Outfit. Toggle the five items individually. Choose No hair for the fitted hat. Each GLB uses the existing Mixamo skeleton and is compatible with the current appearance/v6 body.

Installed viewer assets: `CharacterCreation/viewer/public/equipment/Rework/Thanksgiving/{Male,Female}/`. The corresponding spec is `viewer/public/equipment/equipment_spec_thanksgiving_rework.json`.

Game assets are copied to `GrindScape/client/public/equipment/Rework/Thanksgiving/`. These are staged equipment assets and a spec, not new inventory/loot entries. Game integration should apply the supplied per-slot body coverage. Short-boot coverage ends at 0.265 m in authored Z-up space, preserving exposed calves. The Runtime folder includes the Thanksgiving coverage utility and the existing body-hide integration with its Santa dependency.

Editable scenes: `Source/Male_Thanksgiving.blend`, `Source/Female_Thanksgiving.blend`. Each includes the current body, compatible armature, and five separate outfit meshes. The hidden garment foundation is an authoring helper. `Source/Thanksgiving_Presentation.blend` is the two-character preview. `Source/build_thanksgiving.py` rebuilds the complete set with Blender 4.1.1; set CHARACTER_CREATION_PUBLIC to another CharacterCreation viewer/public folder when needed. It uses the local Pumpkin anatomical glove/boot foundations.

## Browser budget

| Piece | Male triangles | Female triangles |
|---|---:|---:|
| Hat | 846 | 846 |
| Upperbody | 5,057 | 4,125 |
| Gloves | 1,404 | 1,181 |
| Lowerbody | 3,142 | 5,552 |
| Boots | 6,809 | 5,542 |
| Total | 17,258 | 17,246 |

Five opaque material batches per equipped set, one per wearable; vertex colors; zero texture images; maximum four normalized skin influences per vertex. No cloth simulation or added bones. Independent GLBs total 813 KiB for Male and 823 KiB for Female, including a compatible skeleton in every file.

The collar/cuffs are cut into the shirt topology and the apron/hem share the skirt surface. This avoids overlay flicker and extra draw calls. The male trousers retain independent calf/ankle clearance with boots removed. The boots end at roughly 0.283 m, compared with the Santa boots at roughly 0.46 m.

## Review

30 clips × 25 samples × 2 bodies plus rest: 1,502 sampled poses, with finite deformations throughout. Twelve front/back motion views per body are supplied. The separate male lower-leg check reports zero intersections in its tested skin/trouser and trouser/boot regions across 751 poses. Both hats clear the skull at rest. All ten GLBs pass structure, bone, index, material, texture and weight checks. CharacterCreation's TypeScript/Vite production build passes; existing large-bundle warnings remain.

These are not certified completely clipping-free across every animation. Fishing brings the hand into the hat around 8% of the clip, and bucket-pour brings the glove into the head around 58%; eliminating those contacts requires outfit-aware animation changes. Raw skirt/leg candidates also remain at the inner hem in high-knee poses. Motion sheets and QA/ContactViews show the reviewed result. Other hairstyles, mixed outfits and all animation blends are not certified.

`QA/animation_review.json` explains the tests and their limits. `QA/raw_body_intersections.json` includes intentional neckline-facing and boundary contacts; its candidate counts are not a visible-clipping verdict. `QA/pants_fit.json` defines exact tested lower-leg regions. `validation.json` records per-file SHA-256 checksums, sizes and skinning validation; `geometry_report.json` contains authored counts and bounds.

## Sole clearance revision

Corrected both boot variants after underside review showed the inherited toe/vamp surface extending through its own outsole. Raised the internal underside, lowered the tread, and added supported sole geometry with a shared lower-foot weight field. The hats, tops, gloves and bottoms are byte-for-byte unchanged.

Both bodies passed 30 clips × 25 samples plus rest (751 poses each): zero intersections of the tested bottom tread with either the boot toe/vamp or the unmasked anatomical foot. These tests include FemaleWalkV3 and are detailed in QA/sole_fit.json. Sidewalls and intentional joining seams are outside the numeric bottom-tread test. Previews/SoleFix contains underside rest and walking views with unmasked, bright-colored witness feet inside the boots. Refresh CharacterCreation to load the new cache-versioned boot files.
