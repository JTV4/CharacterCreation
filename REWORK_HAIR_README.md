# GrindScape hair rework

Twelve solid, stylized hairstyles fitted to the current Male Rework and Female Rework heads.

Female: Ponytail, Bun, Short, Long, French Braid.
Male: Mullet, Mohawk, Buzz Cut, Ponytail, Short, Shaggy, Dreads.

## Front hairline revision

Revision 4 follows the supplied side-view redline: a mostly vertical temple descent, a small backward step, a second descent, and a near-horizontal return above the ear. This replaces the diagonal cut across the temple while retaining the level forehead edge. Small variations are applied by style. The preview includes a Side button. URLs use `hairline-20260927-v4` to refresh cached assets.

## Installed integration

CharacterCreation: `viewer/public/appearance/v6/Models/Hair/` and the Appearance panel.
GrindScape: `client/public/characters/appearance/Models/Hair/`, shared server/client catalogue, URL resolver and EquippedHair loader.

Use **Female Rework** or **Male Rework**, then the **Hairstyle** selector. Existing saved crop/swept/tied/bob selections resolve to buzz_cut/short/ponytail/short respectively. New selectors offer only the requested styles plus No hair. Hair URLs have a new cache version.

## Browser budget

Each style is one mesh, one opaque single-sided material, one draw call per render pass, one weighted head joint, no textures and no alpha blending. Hair color multiplies neutral vertex shading. No extra physics or per-strand simulation. All 12 GLBs together are 1.62 MiB uncompressed; individual files are 60–221 KiB. Geometry ranges from 1,660–6,294 triangles. Exact costs are in manifest.json.

GrindScape caches one decoded template per requested style. Instances share geometry while owning their skeleton and tint materials. Unmounting a player frees those instance resources without disposing another player's geometry. Failed downloads can retry.

## Preview

The Review directory is a self-contained browser viewer with orbit, front/back views, eight colors and a head-motion check. Serve it over HTTP (browsers block GLB fetches from file://):

```sh
python3 -m http.server 5178 --bind 127.0.0.1 --directory Review
```

Open http://127.0.0.1:5178. No CDN or internet connection is needed. The preview includes reference bases; these are not part of the hair download budget.

## Authoring

Sources contains editable Male_Hair.blend and Female_Hair.blend, a reproducible Blender generator, a GLB packer, and review-page sources. The generator is also installed as `CharacterCreation/generate_rework_hair.py`, with `pack_rework_hair.py` alongside it.

From CharacterCreation:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --python generate_rework_hair.py -- --output rework_hair
python3 pack_rework_hair.py rework_hair
```

The generator reads `viewer/public/appearance/v6/Models`; use --base-models to override. Run the packer after generation to prune unused joints, enable backface culling and normalize skinned mesh roots. The output is not automatically installed over runtime files.

## Verification

- All 12 packed GLBs: Khronos validator, zero errors and zero warnings.
- All 12 styles loaded and visually reviewed in browser WebGL.
- Skin follows animated head rotation; live GrindScape skeleton rebinding at 1.9/1.75 scale matches to less than 0.000001 model units.
- Concurrent load sharing, independent player colors/skeletons and disposal isolation checks pass.
- Three GrindScape catalogue/legacy alias/missing asset tests pass.
- CharacterCreation production build and focused type check for changed GrindScape hair files pass.
- Full GrindScape client type check remains blocked by existing errors elsewhere, including EquippedTool, player motion and construction components. No changed hair files appear in that error output.

Hair is rigidly attached to the head; long styles do not simulate cloth or hair physics. Bulky collars, capes and helmets may intersect long hair in extreme poses. Existing helmet/no-hair behavior remains the integration policy. No live multiplayer crowd FPS benchmark was performed.
