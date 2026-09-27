# GrindScape Santa outfits

Ten independently rigged GLB pieces: Hat, Upperbody, Gloves, Lowerbody and Boots for Male and Female Rework. Red cloth, ivory trim, black leather boots/gloves and a black belt with brass buckle. Male trousers extend to the ankles under the boots. Female upperbody has an open chest neckline; the lowerbody is a flared skirt with integrated modesty shorts.

## Locations and use

- CharacterCreation: Avatar → Male Rework or Female Rework → Equipment → Santa Outfit. Toggle each piece independently. Choose No hair for the fitted hat.
- Viewer assets: `CharacterCreation/viewer/public/equipment/Rework/Santa/{Male,Female}/`.
- Game assets copied to `GrindScape/client/public/equipment/Rework/Santa/{Male,Female}/` with `equipment_spec_santa_rework.json`.
- Editable fit scenes: `Source/Male_Santa.blend` and `Source/Female_Santa.blend`; each contains the current body, original compatible armature and five independent outfit objects. The hidden Garment foundation is an authoring helper.
- `Source/Santa_Presentation.blend` is the posed two-character preview scene.
- `Source/build_santa.py` rebuilds the assets with Blender 4.1.1. It reads the local CharacterCreation appearance/v6 bases and existing Pumpkin glove/boot foundations. Set `CHARACTER_CREATION_PUBLIC` for another checkout location.

The CharacterCreation picker and coverage masks are installed. The game files are staged assets, not new inventory items or loot-table entries. When integrating into GrindScape, apply the supplied per-piece coverage masks; simply drawing an unmasked full body under clothes can expose skin at bent joints. The TypeScript coverage reference is in Runtime/. Its inverse-bind transform makes coverage independent of the current pose.

## Browser budget

| Piece | Male triangles | Female triangles |
|---|---:|---:|
| Hat | 1,756 | 1,756 |
| Upperbody | 6,371 | 4,653 |
| Gloves | 1,404 | 1,181 |
| Lowerbody | 3,142 | 5,704 |
| Boots | 6,783 | 5,276 |
| Total | 19,456 | 18,570 |

Each full set uses five opaque material batches, one per equip slot, with vertex colours and **zero texture images**. Skinning is limited to four normalized influences per vertex. Independent GLBs total 1116 KiB for Male and 1083 KiB for Female, including a compatible skeleton per file. No cloth simulation or extra animated bones are required.

## Animation review and limitations

30 clips × 25 samples × 2 bodies, plus each rest pose: 1,502 evaluated poses. All deformations remained finite. Preview sheets show idle, walking, both runs, kicking, kneeling, sword, ranged, bucket-pour, death, mining and hammering from front and rear. Both sets also loaded correctly and ran in the live CharacterCreation viewer. The viewer production build passes (existing large-bundle warnings remain).

Corrected issues include the trouser/boot overlap, discontinuous trouser surfaces, boot cuffs incorrectly borrowing the opposite leg's weights, and body visibility under covered areas. The female exposed neckline and bare legs remain visible.

**These outfits are not certified completely clipping-free across every animation.** Fishing moves the hand through the hat around 8% of the clip; bucket-pour puts the glove against/into the head around 58%. Those motions need outfit-aware animation adjustments to guarantee separation. Raw skirt/leg contact candidates also occur at the inner hem in high-knee motion; the supplied visual sheets show the resulting motion. Do not treat finite-deformation checks or raw BVH results as proof of no visible clipping. See QA/animation_review.json and QA/Revision1/contact_*.png.

The original revision-1 raw body intersection data in QA/Revision1 intentionally includes neckline facings that extend to skin and rolled trim contact. It is supplied for further diagnosis, not presented as a zero-overlap pass. Different hairstyles, mixed outfits, future clips and animation blends were not certified.

## Files checked

`validation.json` verifies all ten GLBs: header/buffer structure, triangle indices, finite positions, bone-name compatibility, normalized skin weights, exactly one material primitive per piece, no textures, file sizes and SHA-256 checksums. `geometry_report.json` contains authored bounds and counts. All deliverable meshes preserve the existing Mixamo bone names and rest-pose compatibility. Existing outfits and base files were not overwritten.

## Revision 2 — waist trim and hat seating

Removed the lower white coat-hem roll from the female upperbody; the red top now tucks into the skirt without that white ring showing through. Lowered both hats by 4 cm and refitted their crown and brim to the actual skull silhouettes. Focused checks report zero head/hat triangle intersections in rest and zero white waist faces on the female top. Refreshed all 12 front/back motion views for each body and added a close-up female waist side/rear review under Previews/Revision2. These focused checks do not supersede the documented extreme hand-contact limitations.



## Revision 3 — complete independent trousers

Removed the inward shrink of the male trouser calves and refitted the calf/ankle surface with 10 mm radial skin clearance. The pants now wrap the legs down to the ankles with boots unequipped. Expanded the boots around the corrected trousers, with extra clearance at the ankle seam and a tapered transition into the shafts. No triangles were added to the pants.

Focused unmasked lower-leg checks cover 30 clips × 25 samples plus rest (751 poses): zero skin/trouser intersections and zero trouser/boot intersections in the tested calf/ankle regions. The exact bounds and per-sample results are recorded in QA/revision3_pants_fit.json. Open hems and rolled cuff contact are outside that numeric test. Barefoot and booted rest, walk, run and kneel front/back renders are in Previews/Revision3; refreshed full-outfit motion sheets are also supplied. The earlier extreme upperbody animation limitations still apply.

Installed asset URLs use revision 3-final to invalidate cached meshes. Refresh CharacterCreation to load the updated pieces.

## Sole clearance revision

Corrected both boot variants after underside review showed the inherited toe/vamp surface extending through its own outsole. Raised the internal underside, lowered the tread, and added supported sole geometry with a shared lower-foot weight field. The hats, tops, gloves and bottoms are byte-for-byte unchanged.

Both bodies passed 30 clips × 25 samples plus rest (751 poses each): zero intersections of the tested bottom tread with either the boot toe/vamp or the unmasked anatomical foot. These tests include FemaleWalkV3 and are detailed in QA/sole_fit.json. Sidewalls and intentional joining seams are outside the numeric bottom-tread test. Previews/SoleFix contains underside rest and walking views with unmasked, bright-colored witness feet inside the boots. Refresh CharacterCreation to load the new cache-versioned boot files.
