# Halloween Witch Hat — Rework

Copied from the Halloween Offering Shrine: purple ragged brim, bent crown, gold band/buckle, and the small hanging glowing pumpkin. Separate fits for BaseMaleRework and BaseFemaleRework. The original monument is unchanged.

## Use in CharacterCreation

Open Avatar, select Male Rework or Female Rework, then select the matching item in Equipment → Halloween Witch Hat. Use No hair, as with the viewer’s other fitted hats. The face stays visible; no body regions are hidden.

Installed assets: `viewer/public/equipment/Rework/HalloweenWitchHat/{Male,Female}/WitchHat.glb`.
Installed configuration: `viewer/public/equipment/equipment_spec_halloween_witch_rework.json`.

## Files

- `Male/WitchHat.glb` and `Female/WitchHat.glb`: wearable only, glTF Y-up, matching Rework rest pose and rig.
- Each `.blend`: packed fitting scene with the matching base model, consolidated wearable, and hidden editable source parts in EDITABLE_HAT_PARTS. Toggle the source parts only when editing; they duplicate the visible consolidated wearable.
- `FittedPreview.glb`: body and hat together for inspection, not the wearable export.
- Front, side, three-quarter, overhead and posed PNG previews.
- `build_witch_hat.py`: rebuild in this directory within CharacterCreation using Blender --background --python. Requires the sibling halloween_shrine source and viewer/public/models Rework bases.

## Fit and browser budget

Male has 2,258 triangles and 1,178 authored vertices; Female has 2,254 triangles and 1,176 authored vertices. Both use three material batches and no texture images. GLBs are approximately 356–360 KiB, including the compatible original rig. All hat and charm vertices are weighted 100% to mixamorig:Head. The charm follows the head rigidly; no dangling simulation is included.

The crown/band caps were opened for the wearer’s head. Male and female dimensions were adjusted separately. Tested with no hairstyle: zero body/hat triangle intersections in the rest pose, and head-turn attachment error below 0.000001 metres. Detailed results are in fit_report.json. Both versions were inspected in the running equipment viewer, including the FemaleIdle pose.

The viewer production build passes. Khronos glTF validation reports zero errors and one compatibility warning per file (NODE_SKINNED_MESH_NON_ROOT): the skinned wearable is parented under its exported armature. It uses the existing Rework authored-bind handling in the viewer. Full validator output is in validation_report.json.

## Revision 2 — closed crown/brim seam

Rebuilt the lower crown between the actual 40-vertex brim opening and 12-vertex upper crown ring. The boundaries coincide with their adjoining surfaces, closing the gap without capping across the wearer’s head. Added 28 triangles net. Both models retain zero body intersections and pass the rigid head-turn check. Viewer GLB URLs use `?v=2` to refresh cached assets.

## Revision 3 — continuous gold band

Replaced the independent gold tube with a closed strip derived from the actual crown surface. The band has a small outward offset and thickness, matching every crown panel around the full circumference. Both models pass explicit band/fabric intersection and band boundary-edge checks (zero for each). Added rear and left-side inspection renders. Viewer asset URLs use `?v=3`.
