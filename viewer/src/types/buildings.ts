export interface BuildingStage {
  /** Stable id, e.g. "building1_stage1" or "building1_complete". */
  id: string;
  /** Display label shown in the sidebar and above the viewport. */
  label: string;
  /** Short subtitle describing what this stage represents. */
  description: string;
  /** Public URL of the GLB, relative to `viewer/public/`. */
  url: string;
  /**
   * Optional modular assembly playback. When set, the Building Viewer
   * loads `modularUrl` once and tweens pieces into place for `stageKey`
   * instead of hard-swapping a bisected mesh.
   */
    assembly?: {
      modularUrl: string;
      manifestUrl: string;
      /** Key into building_animation_manifest.json `stages`. */
      stageKey: string;
    };
}

export interface BuildingDefinition {
  /** Stable id / buildingKey, e.g. "building1".  Used as the URL and
   * dictionary key throughout the viewer and any downstream game
   * systems that reference a specific building. */
  id: string;
  /** Short label, e.g. "Building 1".  Kept alongside the human name
   * because tooling, filenames, and generator output still key off
   * the Building-N numbering. */
  label: string;
  /** Human-facing structure name shown in the sidebar and viewport
   * header, e.g. "Apothecary Building". */
  structureName: string;
  /** Canonical React component name for this building, e.g.
   * "PioneeringBuilding1".  Not rendered by the viewer itself — it's
   * carried on the definition so downstream game code (which mounts
   * each building via a dedicated component) can look it up here
   * instead of duplicating the mapping. */
  componentName: string;
  /** Ordered stages: earliest construction step first, completed last. */
  stages: BuildingStage[];
}

/**
 * Registry of buildings shown in the Buildings view.
 *
 * The full source-to-viewer pipeline for these entries is driven by
 * `generate_construction_stages.py` at the repo root, which:
 *   1. Loads each `~/Desktop/Models/Buildings/BuildingN.glb`
 *   2. Auto-detects the walkable floor Z (the mesh's lowest +Z-facing
 *      face) so the Stage-1 cut sits above it and the wooden floor
 *      shows through — the base plate at z=0 is normal-inverted and
 *      invisible from above, so a naïve fraction cut fails silently.
 *   3. Emits three `BuildingNStageK.glb` files into both
 *      `~/Desktop/Models/Buildings/Construction/` (asset library) and
 *      `viewer/public/buildings/Construction/` (served by Vite).
 *   4. Mirrors the source `BuildingN.glb` into
 *      `viewer/public/buildings/` so the "Complete" stage is browsable.
 *
 * To add a new building:
 *   1. Drop `BuildingN.glb` into `~/Desktop/Models/Buildings/`.
 *   2. Append `N` to `BUILDING_IDS` in `generate_construction_stages.py`
 *      and re-run the script.
 *   3. Append a new entry here.
 *
 * Building6 is deliberately excluded (per user request).
 *
 * Standalone structures without a construction-stage sequence (e.g. the
 * fishing dock) live in `EXTRA_STRUCTURES` further down and are
 * concatenated onto `BUILDINGS` — no numeric id, no BUILDING_META entry,
 * no changes to the construction-stage generator required.
 */
const BUILDING_IDS = [1, 2, 3, 4, 5, 7, 8] as const;

/**
 * Structure names and canonical React component names per building id.
 * Keep this dictionary as the single source of truth — the sidebar,
 * viewport header, and any downstream game code all key off it, so a
 * one-line change here renames a building everywhere.
 */
const BUILDING_META: Record<
  (typeof BUILDING_IDS)[number],
  { structureName: string; componentName: string }
> = {
  1: { structureName: "Cooking Building",       componentName: "PioneeringBuilding1" },
  2: { structureName: "Pioneering Bank",        componentName: "PioneeringBuilding2" },
  3: { structureName: "Apothecary Building",    componentName: "PioneeringBuilding3" },
  4: { structureName: "Merchant Building",      componentName: "PioneeringBuilding4" },
  5: { structureName: "Forge Building",         componentName: "PioneeringBuilding5" },
  7: { structureName: "Manufacturing Building", componentName: "PioneeringBuilding7" },
  8: { structureName: "Chronocrafting Building",componentName: "PioneeringBuilding8" },
};

function makeBuildingEntry(id: number): BuildingDefinition {
  const meta = BUILDING_META[id as keyof typeof BUILDING_META];
  return {
    id: `building${id}`,
    label: `Building ${id}`,
    structureName: meta.structureName,
    componentName: meta.componentName,
    stages: [
      {
        id: `building${id}_stage0`,
        label: "Stage 0 — Ground Breaking",
        description:
          "Cleared plot with corner survey stakes, string outline, and dirt pile",
        url: `/buildings/Construction/Building${id}Stage0.glb`,
      },
      {
        id: `building${id}_stage1`,
        label: "Stage 1 — Foundation",
        description: "Initial structure with floor slab",
        url: `/buildings/Construction/Building${id}Stage1.glb`,
      },
      {
        id: `building${id}_stage2`,
        label: "Stage 2 — Framing",
        description: "Partial walls with scaffolding, clearly under construction",
        url: `/buildings/Construction/Building${id}Stage2.glb`,
      },
      {
        id: `building${id}_stage3`,
        label: "Stage 3 — Near-Complete",
        description: "Walls up, roof still off, scaffolding remains",
        url: `/buildings/Construction/Building${id}Stage3.glb`,
      },
      {
        id: `building${id}_complete`,
        label: "Complete",
        description: "Finished building (source model)",
        url: `/buildings/Building${id}.glb`,
      },
    ],
  };
}

/** Shared 10-stage modular assembly bookmarks for BuildingNAnimation assets. */
const ANIMATION_ASSEMBLY_STEPS: {
  key: string;
  label: string;
  description: string;
}[] = [
  {
    key: "foundation",
    label: "2 — Foundation",
    description: "Floor slab drops into place",
  },
  {
    key: "walls_a",
    label: "3 — Walls A",
    description: "First wall-panel batch settles onto the foundation",
  },
  {
    key: "walls_b",
    label: "4 — Walls B",
    description: "Second wall-panel batch drops in",
  },
  {
    key: "walls_c",
    label: "5 — Walls C",
    description: "Third wall-panel batch settles",
  },
  {
    key: "walls_d",
    label: "6 — Walls D",
    description: "Final main wall panels close the shell",
  },
  {
    key: "gable",
    label: "7 — Gable",
    description: "Upper gable / high plaster panel settles",
  },
  {
    key: "framing",
    label: "8 — Framing",
    description: "Lower wood-trim framing drops onto the walls",
  },
  {
    key: "eaves",
    label: "9 — Eaves",
    description: "Upper trim / eaves framing settles under the roof line",
  },
  {
    key: "complete",
    label: "10 — Complete",
    description: "Roof tiles drop in — full modular building settled",
  },
];

function makeAnimationStages(opts: {
  idPrefix: string;
  buildingN: number;
  modularFile: string;
  manifestFile: string;
  /** Override site-prep INIT url (defaults to Building{N}Whole_INIT.glb). */
  initUrl?: string;
  /** Override site-prep INIT description. */
  initDescription?: string;
  /** Optional custom assembly step labels/descriptions (same stage keys). */
  assemblySteps?: {
    key: string;
    label: string;
    description: string;
  }[];
}): BuildingStage[] {
  const modularUrl = `/buildings/Construction/${opts.modularFile}`;
  const manifestUrl = `/buildings/Construction/${opts.manifestFile}`;
  const init: BuildingStage = {
    id: `${opts.idPrefix}_init`,
    label: "1 — Site Prep",
    description:
      opts.initDescription ??
      "Resource piles on site — no building mesh or floor pad yet",
    url:
      opts.initUrl ??
      `/buildings/Construction/Building${opts.buildingN}Whole_INIT.glb`,
  };
  const steps = opts.assemblySteps ?? ANIMATION_ASSEMBLY_STEPS;
  const assemblyStages: BuildingStage[] = steps.map((step) => ({
    id: `${opts.idPrefix}_${step.key}`,
    label: step.label,
    description: step.description,
    url: modularUrl,
    assembly: {
      modularUrl,
      manifestUrl,
      stageKey: step.key,
    },
  }));
  return [init, ...assemblyStages];
}

/**
 * Standalone structures that don't fit the numbered "Building N" pipeline
 * (no construction-stage sequence, no source in `~/Desktop/Models/Buildings/BuildingN.glb`).
 *
 * These are hand-crafted `BuildingDefinition`s that get appended to the
 * numeric buildings below, so they show up alongside them in the sidebar
 * with the same expand/collapse UX.  Typically 1 stage ("Complete") but
 * the shape supports more if a standalone structure later grows its own
 * construction sequence.
 *
 * Pipeline handoff:
 *   - Source GLB lives directly at `viewer/public/buildings/<Name>.glb`
 *     (mirrored from `~/Desktop/Models/Buildings/<Name>.glb` by whichever
 *     Blender script generates it — e.g. `generate_fishing_dock.py`).
 *   - No numeric id, so `BUILDING_IDS` / `BUILDING_META` /
 *     `generate_construction_stages.py` all stay unchanged.
 */
const EXTRA_STRUCTURES: BuildingDefinition[] = [
  {
    // FishingDock — pier assemble shore → water (Y-axis slices).
    id: "fishing_dock",
    label: "Waterside Structure",
    structureName: "Fishing Dock Animation",
    componentName: "PioneeringFishingDock",
    stages: makeAnimationStages({
      idPrefix: "fishing_dock",
      buildingN: 0,
      modularFile: "FishingDockAnimation_Modular.glb",
      manifestFile: "fishing_dock_animation_manifest.json",
      initUrl: "/buildings/Construction/FishingDock_INIT.glb",
      initDescription:
        "Site prep — Sycamore log stacks + GrindCoins staged at the shore",
      assemblySteps: [
        {
          key: "foundation",
          label: "2 — Shore Footings",
          description: "First pier section settles on the shore",
        },
        {
          key: "walls_a",
          label: "3 — Near Pilings",
          description: "Pilings / frame continue out from shore",
        },
        {
          key: "walls_b",
          label: "4 — Near Deck",
          description: "Near deck section drops onto the frame",
        },
        {
          key: "walls_c",
          label: "5 — Mid Span",
          description: "Mid-pier section settles over the water",
        },
        {
          key: "walls_d",
          label: "6 — Mid Deck",
          description: "Mid deck planks continue the walkway",
        },
        {
          key: "gable",
          label: "7 — Outer Span",
          description: "Outer pier section reaches farther out",
        },
        {
          key: "framing",
          label: "8 — Outer Deck",
          description: "Outer deck section settles toward the end",
        },
        {
          key: "eaves",
          label: "9 — Water End",
          description: "End of the pier approaches the deep water",
        },
        {
          key: "complete",
          label: "10 — Complete",
          description:
            "Final end section + ladder / cleats — full fishing dock settled",
        },
      ],
    }),
  },
  {
    // Dock_ano5au — Cloudinary dock; pier assemble shore → water.
    id: "dock",
    label: "Waterside Structure",
    structureName: "Dock",
    componentName: "PioneeringDock",
    stages: [
      {
        id: "dock_complete",
        label: "Complete",
        description: "Wooden dock / pier (Dock_ano5au)",
        url: "/buildings/Dock.glb",
      },
    ],
  },
  {
    id: "dock_animation",
    label: "Waterside Structure",
    structureName: "Dock Animation",
    componentName: "PioneeringDockAnimation",
    stages: makeAnimationStages({
      idPrefix: "dock_animation",
      buildingN: 0,
      modularFile: "DockAnimation_Modular.glb",
      manifestFile: "dock_animation_manifest.json",
      initUrl: "/buildings/Construction/Dock_INIT.glb",
      initDescription:
        "Site prep — Sycamore log stacks + GrindCoins staged at the shore",
      assemblySteps: [
        {
          key: "foundation",
          label: "2 — Shore Footings",
          description: "First pier section settles on the shore",
        },
        {
          key: "walls_a",
          label: "3 — Near Pilings",
          description: "Pilings / frame continue out from shore",
        },
        {
          key: "walls_b",
          label: "4 — Near Deck",
          description: "Near deck section drops onto the frame",
        },
        {
          key: "walls_c",
          label: "5 — Mid Span",
          description: "Mid-pier section settles over the water",
        },
        {
          key: "walls_d",
          label: "6 — Mid Deck",
          description: "Mid deck planks continue the walkway",
        },
        {
          key: "gable",
          label: "7 — Outer Span",
          description: "Outer pier section reaches farther out",
        },
        {
          key: "framing",
          label: "8 — Outer Deck",
          description: "Outer deck section settles toward the end",
        },
        {
          key: "eaves",
          label: "9 — Water End",
          description: "End of the pier approaches the deep water",
        },
        {
          key: "complete",
          label: "10 — Complete",
          description: "Final end section — full dock settled",
        },
      ],
    }),
  },
  {
    id: "bridge",
    label: "Water Crossing",
    structureName: "Arched Bridge",
    componentName: "PioneeringBridge",
    stages: [
      {
        id: "bridge_complete",
        label: "Complete",
        description:
          "Wooden arched bridge — 15 m span, 2 m wide, ~2 m rise at center (30° tangent)",
        url: "/buildings/Bridge.glb",
      },
    ],
  },
  {
    id: "supported_bridge",
    label: "Water Crossing",
    structureName: "Supported Arch Bridge",
    componentName: "PioneeringSupportedBridge",
    stages: [
      {
        id: "supported_bridge_complete",
        label: "Complete",
        description:
          "Elevated arched wooden bridge — 15 m span, 4 m wide, on 3 pairs of piers (ends + center) with ~1.5 m deck clearance",
        url: "/buildings/SupportedBridge.glb",
      },
    ],
  },
  {
    id: "wooden_boat",
    label: "Waterside Structure",
    structureName: "Wooden Rowboat",
    componentName: "PioneeringWoodenBoat",
    stages: [
      {
        id: "wooden_boat_complete",
        label: "Complete",
        description:
          "Small wooden rowboat — 3.5 m × 1.36 m, hollow interior with 3 thwart benches",
        url: "/buildings/WoodenBoat.glb",
      },
    ],
  },
  {
    id: "boat_paddle",
    label: "Boat Equipment",
    structureName: "Wooden Paddle",
    componentName: "PioneeringBoatPaddle",
    stages: [
      {
        id: "boat_paddle_complete",
        label: "Complete",
        description:
          "Single-blade canoe paddle — 1.40 m long, leaf-shape blade, cylindrical shaft, T-grip",
        url: "/buildings/BoatPaddle.glb",
      },
    ],
  },
  {
    id: "rope",
    label: "Boat Equipment",
    structureName: "Coiled Rope",
    componentName: "PioneeringRope",
    stages: [
      {
        id: "rope_complete",
        label: "Complete",
        description:
          "Flat-coiled hemp rope — 6 turns, ~48 cm outer diameter, 30 mm rope, smooth-shaded tube",
        url: "/buildings/Rope.glb",
      },
    ],
  },
  {
    id: "oak_leaf",
    label: "Foliage",
    structureName: "Oak Leaf",
    componentName: "PioneeringOakLeaf",
    stages: [
      {
        id: "oak_leaf_large",
        label: "Large",
        description:
          "Large oak leaf — 32 cm long × 15 cm wide, English-oak silhouette with 5 lobes per side, distinct top / underside materials",
        url: "/buildings/OakLeaf.glb",
      },
    ],
  },
  {
    // Fortnite-style landmark trees — tall bare trunk, foliage
    // clustered near the top.  Generated by `generate_tree_set.py`.
    // Each stage is its own GLB with unique bark/leaf atlases
    // (tree_bark + tree_leaves MASK).  Switch stages to cycle species.
    id: "trees",
    label: "Foliage",
    structureName: "Trees",
    componentName: "PioneeringTrees",
    stages: [
      {
        id: "tree_sycamore",
        label: "Sycamore",
        description:
          "Tall Fortnite-style sycamore — ~9 m bare trunk, broad rounded crown at the top (~13 m, 986 tris)",
        url: "/buildings/SycamoreTree.glb",
      },
      {
        id: "tree_poplar",
        label: "Poplar",
        description:
          "Very tall columnar poplar — ~11.5 m trunk, narrow upright crown (~16 m, 1073 tris)",
        url: "/buildings/PoplarTree.glb",
      },
      {
        id: "tree_evergreen",
        label: "Evergreen",
        description:
          "Conical evergreen — layered needle-card whorls tapering to a tip (~13 m, 1727 tris)",
        url: "/buildings/EvergreenTree.glb",
      },
      {
        id: "tree_oak",
        label: "Oak",
        description:
          "Stout Fortnite-style oak — thick trunk, wide irregular crown (~12 m, 923 tris)",
        url: "/buildings/OakTree.glb",
      },
      {
        id: "tree_willow",
        label: "Weeping Willow",
        description:
          "Weeping willow — sturdy upward branches, dense rounded volume of bright hanging willow-leaf curtains; tree_bark / tree_leaves",
        url: "/buildings/WeepingWillowTree.glb",
      },
      {
        id: "tree_lumenbark",
        label: "Lumenbark",
        description:
          "Original fantasy tree — pale lavender bark, teal/magenta orb canopy in spiral tiers (~15 m, 850 tris)",
        url: "/buildings/LumenbarkTree.glb",
      },
      {
        id: "tree_palm",
        label: "Palm",
        description:
          "Tropical palm — ringed columnar trunk, crownshaft swell, multi-segment arched fronds + coconut cluster; tree_bark / tree_leaves",
        url: "/buildings/PalmTree.glb",
      },
      {
        id: "tree_palm_leaning",
        label: "Leaning Palm",
        description:
          "Beach palm that hangs over — trunk curves so the crown leans ~70° from vertical, fronds spill outward; tree_bark / tree_leaves",
        url: "/buildings/PalmTreeLeaning.glb",
      },
    ],
  },
  {
    id: "rock_path",
    label: "Environment Prop",
    structureName: "Rock Walk Path",
    componentName: "PioneeringRockPath",
    stages: [
      {
        id: "rock_path_complete",
        label: "Complete",
        description:
          "Stepping-stone path — 10 flat walkable stones along a 5 m gentle arc, plus 4 scattered edge rocks; single joined mesh, shares the `rock_stone` material with the standalone Rocks",
        url: "/buildings/RockPath.glb",
      },
    ],
  },
  {
    // Modular fortification kit — 4 pieces that snap together to build
    // a curtain wall.  All four share a common material palette
    // (`castle_stone_main` / `..._trim` / `..._dark` / `castle_door_wood`
    // / `..._iron`) and a common vertical layer stack (plinth → body →
    // coping → merlons) so tower + wall + gatehouse read as one set
    // even before textures are painted.
    //
    // Piece dimensions and modular fit — generated by
    // `generate_castle_wall_set.py` at the repo root:
    //
    //   • Pillar         1.2 × 1.2 × 5.0 m crenellated corner tower.
    //   • Pillar Cone    rectangular shaft + conical roof (same footprint).
    //   • Pillar Round   round shaft + conical roof (same footprint).
    //   • Wall           4.0 × 0.5 × 3.5 m tileable run.
    //   • Wall Window    same wall module with centered pointed arched window.
    //   • Window Frame   insert frame+leaded glass for Wall Window opening.
    //   • Window Clear   same insert, textured oak + see-through tinted glass.
    //   • Window Open    same as Clear but without the inner T mullions.
    //   • Window Plain   same as Window Frame (leaded) without T mullions.
    //   • Entrance       5.0 × 1.2 × 5.0 m gatehouse, 2.4 m arched opening.
    //   • Door           hinged double doors matching the entrance arch.
    id: "castle_wall_set",
    label: "Fortification",
    structureName: "Castle Wall Set",
    componentName: "PioneeringCastleWallSet",
    stages: [
      {
        id: "castle_wall_pillar",
        label: "Pillar (Tower)",
        description:
          "1.2 × 1.2 × 5.0 m corner tower — plinth, crenellated top, cruciform arrow slits on all four faces (228 tris)",
        url: "/buildings/CastlePillar.glb",
      },
      {
        id: "castle_wall_pillar_cone",
        label: "Pillar Cone (Rect)",
        description:
          "1.2 × 1.2 m rectangular pillar with conical stone roof, square plinth, cross arrow slits — same modular footprint as the crenellated pillar",
        url: "/buildings/CastlePillarCone.glb",
      },
      {
        id: "castle_wall_pillar_round_cone",
        label: "Pillar Cone (Round)",
        description:
          "1.2 m Ø round pillar with conical stone roof, square plinth, cross arrow slits — snaps into the same wall slots as the square tower",
        url: "/buildings/CastlePillarRoundCone.glb",
      },
      {
        id: "castle_wall_segment",
        label: "Wall Segment",
        description:
          "4.0 × 0.5 × 3.5 m tileable curtain wall — machicolation frieze along the outside face, five merlons across the top, two arrow slits (264 tris)",
        url: "/buildings/CastleWallSegment.glb",
      },
      {
        id: "castle_wall_window",
        label: "Wall Window",
        description:
          "Same 4.0 × 0.5 × 3.5 m wall module with a centered pointed Gothic arched window opening, stone sill, frieze, and five merlons — tiles with Wall Segment",
        url: "/buildings/CastleWallWindow.glb",
      },
      {
        id: "castle_wall_window_frame",
        label: "Window Frame",
        description:
          "Textured oak frame + leaded diamond glass + cross mullion sized to the Wall Window opening (shared arch constants, ~1.8 cm clearance) — place at the same origin as Wall Window to slide in",
        url: "/buildings/CastleWallWindowFrame.glb",
      },
      {
        id: "castle_wall_window_frame_clear",
        label: "Window Frame Clear",
        description:
          "Same insert as Window Frame with textured oak frame + see-through tinted glass (alpha/transmission, no opaque glass map) — place at the same origin as Wall Window to slide in",
        url: "/buildings/CastleWallWindowFrameClear.glb",
      },
      {
        id: "castle_wall_window_frame_open",
        label: "Window Frame Open",
        description:
          "Same as Window Frame Clear (textured oak + see-through glass) but without the inner T / cross mullions — place at the same origin as Wall Window to slide in",
        url: "/buildings/CastleWallWindowFrameOpen.glb",
      },
      {
        id: "castle_wall_window_frame_plain",
        label: "Window Frame Plain",
        description:
          "Same as Window Frame (textured oak + leaded diamond glass) but without the inner T / cross mullions — place at the same origin as Wall Window to slide in",
        url: "/buildings/CastleWallWindowFramePlain.glb",
      },
      {
        id: "castle_wall_entrance",
        label: "Arched Entrance",
        description:
          "5.0 × 1.2 × 5.0 m gatehouse — 2.4 m opening with a smooth 32-segment semicircular arch (r=1.2 m, peak z=3.7 m) built as extruded spandrel bmeshes so the arch reads as one continuous stone curve, flanking crenellated towers (352 tris)",
        url: "/buildings/CastleEntrance.glb",
      },
      {
        id: "castle_wall_double_door",
        label: "Double Door",
        description:
          "Wooden double door with iron banding, studs, ring pulls, and 3 hinges per panel — arched panel tops share the entrance's 32-segment arch so the closed door's silhouette matches the gate opening exactly; each panel origin at its outer hinge so a game engine rotates around local +Z to swing open (2 × 784 = 1568 tris)",
        url: "/buildings/CastleDoubleDoor.glb",
      },
    ],
  },
  {
    // Textured curtain + keep kit — assemble an outer wall ring and a
    // 2-storey keep inside the courtyard.  Generated by
    // `generate_castle_keep_kit.py`.  Shared 4 m module; gate doors
    // match CastleCurtainEntrance arch; tower cone seats on pillar top;
    // keep footprint 8×8 m, storey height 3.5 m.
    id: "castle_keep_kit",
    label: "Castle",
    structureName: "Castle Keep Kit",
    componentName: "PioneeringCastleKeepKit",
    stages: [
      {
        id: "castle_keep_curtain_wall",
        label: "Curtain Wall",
        description:
          "4.0 × 0.5 × 3.5 m textured outer wall — plinth, merlons, arrow slits; castle_stone / castle_stone_dark",
        url: "/buildings/CastleCurtainWall.glb",
      },
      {
        id: "castle_keep_curtain_entrance",
        label: "Curtain Gatehouse",
        description:
          "5.0 × 1.2 m arched gatehouse — 2.4 m opening (spring z=2.4, peak z=3.6) matches gate doors exactly",
        url: "/buildings/CastleCurtainEntrance.glb",
      },
      {
        id: "castle_keep_curtain_doors",
        label: "Gate Double Doors",
        description:
          "Hinged arched pair with iron bands, straps, knuckles, ring pulls — origins on outer hinges (rotate local +Z to open)",
        url: "/buildings/CastleCurtainDoubleDoor.glb",
      },
      {
        id: "castle_keep_tower_pillar",
        label: "Round Tower",
        description:
          "1.2 m Ø × 3.5 m round tower pillar — place at curtain corners/intervals; cone cap seats on top",
        url: "/buildings/CastleTowerPillar.glb",
      },
      {
        id: "castle_keep_tower_cone",
        label: "Tower Cone Roof",
        description:
          "Cone roof/cap that fits the round tower — origin at base centre (place at pillar top z=3.5)",
        url: "/buildings/CastleTowerCone.glb",
      },
      {
        id: "castle_keep_courtyard_floor",
        label: "Courtyard Floor",
        description:
          "4 × 4 m stone courtyard tile — tile on a grid inside the curtain walls",
        url: "/buildings/CastleCourtyardFloor.glb",
      },
      {
        id: "castle_keep_curtain_parapet",
        label: "Curtain Parapet",
        description:
          "~1.15 m crenellated walkway rail — place atop curtain wall at z=3.5",
        url: "/buildings/CastleCurtainParapet.glb",
      },
      {
        id: "castle_keep_wall",
        label: "Keep Wall",
        description:
          "4.0 m keep exterior wall with two windows — one 3.5 m storey; stack for 2nd floor",
        url: "/buildings/CastleKeepWall.glb",
      },
      {
        id: "castle_keep_door_wall",
        label: "Keep Door Wall",
        description:
          "Keep facade bay with arched doorway sized for CastleKeepDoor",
        url: "/buildings/CastleKeepDoorWall.glb",
      },
      {
        id: "castle_keep_door",
        label: "Keep Door",
        description:
          "Hinged double leaf fitting keep arch — hinges + handles; rotate local +Z to open",
        url: "/buildings/CastleKeepDoor.glb",
      },
      {
        id: "castle_keep_floor_l1",
        label: "Keep Floor L1",
        description: "8 × 8 m ground-floor slab for the keep",
        url: "/buildings/CastleKeepFloorL1.glb",
      },
      {
        id: "castle_keep_floor_l2",
        label: "Keep Floor L2",
        description:
          "8 × 8 m second-floor slab at z=3.5 with stair cutout",
        url: "/buildings/CastleKeepFloorL2.glb",
      },
      {
        id: "castle_keep_stairs",
        label: "Keep Stairs",
        description:
          "Straight stair rising 3.5 m (L1→L2) with stringers and rail — fits L2 cutout",
        url: "/buildings/CastleKeepStairs.glb",
      },
      {
        id: "castle_keep_roof",
        label: "Keep Roof",
        description:
          "Pitched tiled roof for the 8×8 keep — place at z=7.0 (two storeys)",
        url: "/buildings/CastleKeepRoof.glb",
      },
      {
        id: "castle_keep_assembled",
        label: "Keep Assembled (Preview)",
        description:
          "Preview of keep walls + floors + stairs + roof + doors for silhouette check — use individual pieces for assembly",
        url: "/buildings/CastleKeepAssembled.glb",
      },
    ],
  },
  {
    // Full keep from GrindMooreCastleKeep.glb — solid-color source
    // textured via `texture_grindmoore_castle.py` with atlases in
    // grindmoore_castle_textures/ (stone main/dark/light, roof tiles,
    // door wood, window glass).
    id: "grindmoore_castle_keep",
    label: "Castle",
    structureName: "GrindMoore Castle Keep",
    componentName: "PioneeringGrindMooreCastleKeep",
    stages: [
      {
        id: "grindmoore_castle_keep_complete",
        label: "Complete",
        description:
          "Textured keep — stone walls/battlements, clay roof, wood doors, glass windows (castle_stone / castle_stone_dark / castle_stone_light / castle_roof_tiles / castle_wood / castle_glass)",
        url: "/buildings/GrindMooreCastleKeep.glb",
      },
    ],
  },
  {
    // Modular wooden fence kit — 4 pieces that snap on a 3.0 m
    // post-centre grid.  Generated by `generate_wooden_fence.py`:
    //
    //   • Fence Section  two round wooden rails spanning the clear
    //                    gap between posts (place at mid-span).
    //   • Gate           matching hinged leaf (frame + 2 round rails
    //                    + brace + iron hinges); origin on the left
    //                    hinge line — rotate around local +Z to open.
    //   • End Post       square grey concrete / brick anchor for
    //                    straight-run ends.
    //   • Corner Post    larger concrete anchor with a distinct cap
    //                    nub for 90° corners.
    //
    // Materials: fence_wood_rail / fence_wood_frame / fence_concrete /
    // fence_concrete_trim / fence_iron (placeholder colours — texture
    // later).
    id: "wooden_fence",
    label: "Exterior Prop",
    structureName: "Wooden Fence",
    componentName: "PioneeringWoodenFence",
    stages: [
      {
        id: "fence_section",
        label: "Fence Section",
        description:
          "3.0 m modular bay — two horizontal round wooden rails (z=0.40 / 0.95 m) spanning the clear gap between posts",
        url: "/buildings/FenceSection.glb",
      },
      {
        id: "fence_gate",
        label: "Gate",
        description:
          "3.0 m matching hinged gate — frame, two round rails, diagonal brace, three iron strap hinges; origin on left hinge line (rotate local +Z to open)",
        url: "/buildings/FenceGate.glb",
      },
      {
        id: "fence_end_post",
        label: "End Post",
        description:
          "Square grey concrete / brick anchor — 0.32 × 0.32 × 1.25 m with plinth and flat cap",
        url: "/buildings/FenceEndPost.glb",
      },
      {
        id: "fence_corner_post",
        label: "Corner Post",
        description:
          "Larger corner anchor — 0.38 × 0.38 × 1.35 m with plinth, cap, and top nub so corners read distinctly from end posts",
        url: "/buildings/FenceCornerPost.glb",
      },
    ],
  },
  {
    // Brick-base GrindScape banner. Generated by generate_grindscape_flag.py.
    // GLB includes a seamless 4 s `wave` clip skinned to two hem bone
    // chains — the Building Viewer plays embedded animations automatically.
    id: "grindscape_flag",
    label: "Exterior Prop",
    structureName: "GrindScape Flag",
    componentName: "PioneeringGrindScapeFlag",
    stages: [
      {
        id: "grindscape_flag_complete",
        label: "Complete",
        description:
          "Grey-brick pedestal, tall wooden pole, gold spear finial, GS logo flag flowing in a seamless 4 s wind loop",
        url: "/buildings/GrindScapeFlag.glb",
      },
    ],
  },
  {
    // 10-stage drop-in for the GrindScape banner. Generated by
    // generate_flagpole_animation.py — authored pieces (not Z-bisect)
    // so the pole grows in tapered thirds and the cloth arrives last.
    id: "grindscape_flag_animation",
    label: "Exterior Prop",
    structureName: "GrindScape Flag Animation",
    componentName: "PioneeringGrindScapeFlagAnimation",
    stages: makeAnimationStages({
      idPrefix: "grindscape_flag_animation",
      buildingN: 0,
      modularFile: "GrindScapeFlagAnimation_Modular.glb",
      manifestFile: "grindscape_flag_animation_manifest.json",
      initUrl: "/buildings/Construction/GrindScapeFlag_INIT.glb",
      initDescription:
        "Site prep — Raw Catfish, Sycamore log stack, Iron ore (no flagpole mesh)",
      assemblySteps: [
        {
          key: "foundation",
          label: "2 — Plinth",
          description: "Grey-brick plinth pad drops onto the plot",
        },
        {
          key: "walls_a",
          label: "3 — Pedestal",
          description: "Pedestal body stacks onto the plinth",
        },
        {
          key: "walls_b",
          label: "4 — Cap",
          description: "Overhanging brick cap settles on the pedestal",
        },
        {
          key: "walls_c",
          label: "5 — Socket",
          description: "Pole socket collar seats in the cap",
        },
        {
          key: "walls_d",
          label: "6 — Lower Pole",
          description: "Lower third of the wooden shaft + iron band",
        },
        {
          key: "gable",
          label: "7 — Mid Pole",
          description: "Middle shaft section continues the taper",
        },
        {
          key: "framing",
          label: "8 — Upper Pole",
          description: "Upper shaft reaches the collar height",
        },
        {
          key: "eaves",
          label: "9 — Finial",
          description: "Iron collar and gold spear finial cap the pole",
        },
        {
          key: "complete",
          label: "10 — Flag",
          description: "GS logo cloth hangs off the pole — banner complete",
        },
      ],
    }),
  },
  {
    // Six rug silhouettes under one sidebar row — switch stages to
    // cycle Rectangle → Square → Circle → Oval → Runner → Hexagon.
    // Generated by `generate_rugs.py` at the repo root.  All share
    // `rug_top` / `rug_underside` material slots (placeholder colours
    // only — texture later).  Origin at footprint centre, bottom face
    // on z=0.
    id: "rugs",
    label: "Interior Prop",
    structureName: "Rugs",
    componentName: "PioneeringRugs",
    stages: [
      {
        id: "rug_rectangle",
        label: "Rectangle",
        description:
          "Classic area rug — 2.0 × 1.4 m rectangle, 1.5 cm pile, rug_top / rug_underside materials",
        url: "/buildings/RugRectangle.glb",
      },
      {
        id: "rug_square",
        label: "Square",
        description:
          "Square area rug — 1.6 × 1.6 m",
        url: "/buildings/RugSquare.glb",
      },
      {
        id: "rug_circle",
        label: "Circle",
        description:
          "Round rug — 1.6 m diameter, 24-segment outline",
        url: "/buildings/RugCircle.glb",
      },
      {
        id: "rug_oval",
        label: "Oval",
        description:
          "Elongated oval — 2.2 × 1.2 m, 28-segment ellipse",
        url: "/buildings/RugOval.glb",
      },
      {
        id: "rug_runner",
        label: "Runner",
        description:
          "Hallway runner — 3.0 × 0.65 m narrow rectangle",
        url: "/buildings/RugRunner.glb",
      },
      {
        id: "rug_hexagon",
        label: "Hexagon",
        description:
          "Regular hexagon — ~1.7 m flat-to-flat, flat side facing −Y",
        url: "/buildings/RugHexagon.glb",
      },
    ],
  },
  {
    // Spiral staircase — open + railed variants under one sidebar row.
    // Generated by `generate_spiral_staircase.py` at the repo root.
    //
    //   • Open    12 wedge treads around a square central post, one
    //             full CCW turn, ~2.5 m climb (no rail).
    //   • Railed  Same core plus outer balusters and a piecewise
    //             handrail that follows the outer tread edge.
    //
    // Named material slots (stair_steps / stair_post / stair_baluster /
    // stair_rail) are placeholder colours only — texture later.
    id: "spiral_staircase",
    label: "Interior Prop",
    structureName: "Spiral Staircase",
    componentName: "PioneeringSpiralStaircase",
    stages: [
      {
        id: "spiral_staircase_open",
        label: "Open",
        description:
          "12 wedge stone treads around a square wooden post — one full turn, 0.22 m rise per step, walkable tread r=0.28–1.35 m, no rail (636 tris)",
        url: "/buildings/SpiralStaircaseOpen.glb",
      },
      {
        id: "spiral_staircase_railed",
        label: "Railed",
        description:
          "Same spiral plus outer balusters and a piecewise wooden handrail following the outer tread edge (936 tris)",
        url: "/buildings/SpiralStaircase.glb",
      },
    ],
  },
  {
    // Resource singles + piles from Exodus-SDK7
    // (extract_woodchopping_logs / extract_resource_singles /
    //  generate_log_piles / generate_ore_piles / generate_fish_piles /
    //  generate_raw_fish_piles / generate_meat_stacks).
    id: "resources",
    label: "Resources",
    structureName: "Resources",
    componentName: "PioneeringResources",
    stages: [
      {
        id: "sycamore_log",
        label: "Sycamore Log",
        description:
          "Single sycamore woodchopping log with embedded bark + end-cap textures",
        url: "/buildings/SycamoreLog.glb",
      },
      {
        id: "poplar_log",
        label: "Poplar Log",
        description:
          "Single poplar woodchopping log with embedded bark + end-cap textures",
        url: "/buildings/PoplarLog.glb",
      },
      {
        id: "pine_log",
        label: "Pine Log",
        description:
          "Single pine woodchopping log with embedded bark + end-cap textures",
        url: "/buildings/PineLog.glb",
      },
      {
        id: "acacia_log",
        label: "Acacia Log",
        description:
          "Single acacia woodchopping log with embedded bark + end-cap textures",
        url: "/buildings/AcaciaLog.glb",
      },
      {
        id: "wisteria_log",
        label: "Wisteria Log",
        description:
          "Single wisteria woodchopping log with embedded bark + end-cap textures",
        url: "/buildings/WisteriaLog.glb",
      },
      {
        id: "iron_ore",
        label: "Iron Ore",
        description: "Single iron ore chunk from Mining/ore",
        url: "/buildings/IronOre.glb",
      },
      {
        id: "coal_ore",
        label: "Coal Ore",
        description: "Single coal ore chunk (steel_ore.glb source)",
        url: "/buildings/CoalOre.glb",
      },
      {
        id: "gold_ore",
        label: "Gold Ore",
        description: "Single gold ore chunk from Mining/ore",
        url: "/buildings/GoldOre.glb",
      },
      {
        id: "titanium_ore",
        label: "Titanium Ore",
        description: "Single titanium ore chunk from Mining/ore",
        url: "/buildings/TitaniumOre.glb",
      },
      {
        id: "tungsten_ore",
        label: "Tungsten Ore",
        description: "Single tungsten ore chunk from Mining/ore",
        url: "/buildings/TungstenOre.glb",
      },
      {
        id: "raw_catfish",
        label: "Raw Catfish",
        description: "Single raw catfish from Fishing/fish",
        url: "/buildings/RawCatfish.glb",
      },
      {
        id: "raw_bass",
        label: "Raw Bass",
        description: "Single raw bass from Fishing/fish",
        url: "/buildings/RawBass.glb",
      },
      {
        id: "raw_trout",
        label: "Raw Trout",
        description: "Single raw trout from Fishing/fish",
        url: "/buildings/RawTrout.glb",
      },
      {
        id: "raw_gar",
        label: "Raw Gar",
        description: "Single raw gar from Fishing/fish",
        url: "/buildings/RawGar.glb",
      },
      {
        id: "raw_walleye",
        label: "Raw Walleye",
        description: "Single raw walleye from Fishing/fish",
        url: "/buildings/RawWalleye.glb",
      },
      {
        id: "log_pile_pine",
        label: "Logs — Pine",
        description:
          "Pyramid woodpile — 10 pine logs stacked 4→3→2→1 with hexagonal nest",
        url: "/buildings/LogPile_Pine.glb",
      },
      {
        id: "log_pile_poplar",
        label: "Logs — Poplar",
        description:
          "Pyramid woodpile — 10 poplar logs stacked 4→3→2→1 with hexagonal nest",
        url: "/buildings/LogPile_Poplar.glb",
      },
      {
        id: "log_pile_sycamore",
        label: "Logs — Sycamore",
        description:
          "Pyramid woodpile — 10 sycamore logs stacked 4→3→2→1 with hexagonal nest",
        url: "/buildings/LogPile_Sycamore.glb",
      },
      {
        id: "log_pile_blue_willow",
        label: "Logs — Blue Willow",
        description:
          "Pyramid woodpile — 10 blue willow logs stacked 4→3→2→1 with hexagonal nest",
        url: "/buildings/LogPile_BlueWillow.glb",
      },
      {
        id: "log_pile_weeping_willow",
        label: "Logs — Weeping Willow",
        description:
          "Pyramid woodpile — 10 weeping willow logs stacked 4→3→2→1 with hexagonal nest",
        url: "/buildings/LogPile_WeepingWillow.glb",
      },
      {
        id: "ore_pile_iron",
        label: "Ore — Iron",
        description:
          "Square-pyramid ore pile — 14 iron chunks stacked 3×3 → 2×2 → 1",
        url: "/buildings/OrePile_Iron.glb",
      },
      {
        id: "ore_pile_coal",
        label: "Ore — Coal",
        description:
          "Square-pyramid ore pile — 14 coal chunks stacked 3×3 → 2×2 → 1 (steel_ore.glb chunk)",
        url: "/buildings/OrePile_Coal.glb",
      },
      {
        id: "ore_pile_gold",
        label: "Ore — Gold",
        description:
          "Square-pyramid ore pile — 14 gold chunks stacked 3×3 → 2×2 → 1",
        url: "/buildings/OrePile_Gold.glb",
      },
      {
        id: "ore_pile_titanium",
        label: "Ore — Titanium",
        description:
          "Square-pyramid ore pile — 14 titanium chunks stacked 3×3 → 2×2 → 1",
        url: "/buildings/OrePile_Titanium.glb",
      },
      {
        id: "ore_pile_tungsten",
        label: "Ore — Tungsten",
        description:
          "Square-pyramid ore pile — 14 tungsten chunks stacked 3×3 → 2×2 → 1",
        url: "/buildings/OrePile_Tungsten.glb",
      },
      {
        id: "ore_pile_luminous",
        label: "Ore — Luminous",
        description:
          "Square-pyramid ore pile — 14 luminous chunks stacked 3×3 → 2×2 → 1",
        url: "/buildings/OrePile_Luminous.glb",
      },
      {
        id: "fish_pile_bass",
        label: "Fish — Cooked Bass",
        description:
          "Tossed heap of cooked bass — 14 fish piled loosely (burnt skipped)",
        url: "/buildings/FishPile_Bass.glb",
      },
      {
        id: "fish_pile_catfish",
        label: "Fish — Cooked Catfish",
        description:
          "Tossed heap of cooked catfish — 14 fish piled loosely (burnt skipped)",
        url: "/buildings/FishPile_Catfish.glb",
      },
      {
        id: "fish_pile_gar",
        label: "Fish — Cooked Gar",
        description:
          "Tossed heap of cooked gar — 14 fish piled loosely (burnt skipped)",
        url: "/buildings/FishPile_Gar.glb",
      },
      {
        id: "fish_pile_trout",
        label: "Fish — Cooked Trout",
        description:
          "Tossed heap of cooked trout — 14 fish piled loosely (burnt skipped)",
        url: "/buildings/FishPile_Trout.glb",
      },
      {
        id: "fish_pile_walleye",
        label: "Fish — Cooked Walleye",
        description:
          "Tossed heap of cooked walleye — 14 fish piled loosely (burnt skipped)",
        url: "/buildings/FishPile_Walleye.glb",
      },
      {
        id: "raw_fish_pile_bass",
        label: "Fish — Raw Bass",
        description:
          "Tossed heap of raw bass — 14 fish piled loosely",
        url: "/buildings/RawFishPile_Bass.glb",
      },
      {
        id: "raw_fish_pile_catfish",
        label: "Fish — Raw Catfish",
        description:
          "Tossed heap of raw catfish — 14 fish piled loosely",
        url: "/buildings/RawFishPile_Catfish.glb",
      },
      {
        id: "raw_fish_pile_gar",
        label: "Fish — Raw Gar",
        description:
          "Tossed heap of raw gar — 14 fish piled loosely",
        url: "/buildings/RawFishPile_Gar.glb",
      },
      {
        id: "raw_fish_pile_trout",
        label: "Fish — Raw Trout",
        description:
          "Tossed heap of raw trout — 14 fish piled loosely",
        url: "/buildings/RawFishPile_Trout.glb",
      },
      {
        id: "raw_fish_pile_walleye",
        label: "Fish — Raw Walleye",
        description:
          "Tossed heap of raw walleye — 14 fish piled loosely",
        url: "/buildings/RawFishPile_Walleye.glb",
      },
      {
        id: "meat_stack_raw_beef",
        label: "Meat — Raw Beef",
        description: "Stack of 10 raw beef cuts with light offset / yaw jitter",
        url: "/buildings/MeatStack_RawBeef.glb",
      },
      {
        id: "meat_stack_cooked_beef",
        label: "Meat — Cooked Beef",
        description: "Stack of 10 cooked beef cuts with light offset / yaw jitter",
        url: "/buildings/MeatStack_CookedBeef.glb",
      },
      {
        id: "meat_stack_raw_lamb",
        label: "Meat — Raw Lamb",
        description: "Stack of 10 raw lamb cuts with light offset / yaw jitter",
        url: "/buildings/MeatStack_RawLamb.glb",
      },
      {
        id: "meat_stack_cooked_lamb",
        label: "Meat — Cooked Lamb",
        description: "Stack of 10 cooked lamb cuts with light offset / yaw jitter",
        url: "/buildings/MeatStack_CookedLamb.glb",
      },
      {
        id: "meat_stack_raw_chicken",
        label: "Meat — Raw Chicken",
        description: "Stack of 10 raw chicken pieces with light offset / yaw jitter",
        url: "/buildings/MeatStack_RawChicken.glb",
      },
      {
        id: "meat_stack_cooked_chicken",
        label: "Meat — Cooked Chicken",
        description: "Stack of 10 cooked chicken pieces with light offset / yaw jitter",
        url: "/buildings/MeatStack_CookedChicken.glb",
      },
      {
        id: "meat_stack_raw_deer",
        label: "Meat — Raw Deer",
        description: "Stack of 10 raw deer cuts with light offset / yaw jitter",
        url: "/buildings/MeatStack_RawDeer.glb",
      },
      {
        id: "meat_stack_cooked_deer",
        label: "Meat — Cooked Deer",
        description: "Stack of 10 cooked deer cuts with light offset / yaw jitter",
        url: "/buildings/MeatStack_CookedDeer.glb",
      },
      {
        id: "clay_pile",
        label: "Clay",
        description:
          "Single clay mound GLB from Desktop/Models/Rocks/Clay.glb",
        url: "/buildings/Clay.glb",
      },
      {
        id: "grind_coin",
        label: "GrindCoin",
        description:
          "Single gold GrindCoin (~1 m Ø) from generate_grind_coin.py — also saved as Desktop/GrindScape/GrindCoin2.glb",
        url: "/buildings/GrindCoin.glb",
      },
      {
        id: "coin_pile_grind",
        label: "Coins — GrindCoin Pile",
        description:
          "Stacked treasure heap of 16 authored GrindCoins (generate_grind_coin.py)",
        url: "/buildings/CoinPile_Grind.glb",
      },
    ],
  },
  {
    // Four size variants under one registry entry — each rock is a
    // fully-baked standalone GLB, but they share the sidebar row so
    // "Rocks" doesn't quadruple the length of the environment list.
    // Switching stages cycles Small → Medium → Large → Huge.
    id: "rocks",
    label: "Environment Prop",
    structureName: "Rocks",
    componentName: "PioneeringRocks",
    stages: [
      {
        id: "rocks_small",
        label: "Small",
        description:
          "Hand-sized stone — ~20 cm, 16-point convex hull, chunky angular facets",
        url: "/buildings/SmallRock.glb",
      },
      {
        id: "rocks_medium",
        label: "Medium",
        description:
          "Knee-high garden stone — ~55 cm, 24-point convex hull",
        url: "/buildings/MediumRock.glb",
      },
      {
        id: "rocks_large",
        label: "Large",
        description:
          "Waist-high boulder — ~1.3 m, 36-point convex hull",
        url: "/buildings/LargeRock.glb",
      },
      {
        id: "rocks_huge",
        label: "Huge",
        description:
          "Car-sized landmark boulder — ~2.9 m, 50-point convex hull, smoother massive silhouette",
        url: "/buildings/HugeRock.glb",
      },
    ],
  },
  {
    // Plaster wall modules:
    //   Straight Base/Clay — source Wall_Plaster_Straight_Base.glb (+ clay retexture)
    //   Panel — original half-timber design from generate_plaster_wall_panel.py
    id: "wall_plaster",
    label: "Plaster Wall",
    structureName: "Plaster Wall",
    componentName: "PioneeringWallPlaster",
    stages: [
      {
        id: "wall_plaster_straight_base",
        label: "Straight (Base)",
        description:
          "2.0 × ~0.4 × 3.1 m plaster wall segment — timber trim, plaster face, brick return; original authored textures",
        url: "/buildings/WallPlasterStraightBase.glb",
      },
      {
        id: "wall_plaster_straight_clay",
        label: "Straight (Clay)",
        description:
          "Same mesh/UVs as Straight (Base) with a fresh Warm Clay set — peach plaster, terracotta brick, honey/walnut wood trim",
        url: "/buildings/WallPlasterStraightClay.glb",
      },
      {
        id: "wall_plaster_panel",
        label: "Panel (Half-Timber)",
        description:
          "Original 2.0 × 0.34 × 3.0 m design — slate ashlar plinth + quoins, charcoal timber frame with braces, four recessed limestone plaster panels, wood corbels, stone coping (new geometry, not derived from Straight Base)",
        url: "/buildings/WallPlasterPanel.glb",
      },
    ],
  },
  // Workstations — modular 10-stage assemble (`generate_workstation_animation.py`).
  // INIT = required resource piles only; stages 2–10 = modular drop-in.
  ...([
    {
      id: "manufacturing_workbench",
      structureName: "Manufacturing Workbench",
      componentName: "PioneeringManufacturingWorkbench",
      materials: "Sycamore logs, Iron ore, GrindCoins",
      modularFile: "ManufacturingWorkbenchAnimation_Modular.glb",
      manifestFile: "manufacturing_workbench_animation_manifest.json",
      initFile: "ManufacturingWorkbench_INIT.glb",
    },
    {
      id: "chronocrafting_workbench",
      structureName: "Chronocrafting Workbench",
      componentName: "PioneeringChronocraftingWorkbench",
      materials: "Sycamore logs, GrindCoins",
      modularFile: "ChronocraftingWorkbenchAnimation_Modular.glb",
      manifestFile: "chronocrafting_workbench_animation_manifest.json",
      initFile: "ChronocraftingWorkbench_INIT.glb",
    },
    {
      id: "cooking_range",
      structureName: "Cooking Range",
      componentName: "PioneeringCookingRange",
      materials: "Clay, Raw Catfish, GrindCoins",
      modularFile: "CookingRangeAnimation_Modular.glb",
      manifestFile: "cooking_range_animation_manifest.json",
      initFile: "CookingRange_INIT.glb",
    },
    {
      id: "furnace",
      structureName: "Furnace",
      componentName: "PioneeringFurnace",
      materials: "Sycamore logs, Clay, GrindCoins",
      modularFile: "FurnaceAnimation_Modular.glb",
      manifestFile: "furnace_animation_manifest.json",
      initFile: "Furnace_INIT.glb",
    },
    {
      id: "spinning_wheel",
      structureName: "Spinning Wheel",
      componentName: "PioneeringSpinningWheel",
      materials: "Flax, Sycamore logs, GrindCoins",
      modularFile: "SpinningWheelAnimation_Modular.glb",
      manifestFile: "spinning_wheel_animation_manifest.json",
      initFile: "SpinningWheel_INIT.glb",
    },
    {
      id: "anvil",
      structureName: "Anvil",
      componentName: "PioneeringAnvil",
      materials: "Iron ore, GrindCoins",
      modularFile: "AnvilAnimation_Modular.glb",
      manifestFile: "anvil_animation_manifest.json",
      initFile: "Anvil_INIT.glb",
    },
    {
      id: "tanning_rack",
      structureName: "Tanning Rack",
      componentName: "PioneeringTanningRack",
      materials: "Cow hide, Sycamore logs, GrindCoins",
      modularFile: "TanningRackAnimation_Modular.glb",
      manifestFile: "tanning_rack_animation_manifest.json",
      initFile: "TanningRack_INIT.glb",
    },
    {
      id: "bank_chest",
      structureName: "Bank Chest",
      componentName: "PioneeringBankChest",
      materials: "Poplar logs, GrindCoins",
      modularFile: "BankChestAnimation_Modular.glb",
      manifestFile: "bank_chest_animation_manifest.json",
      initFile: "BankChest_INIT.glb",
    },
  ] as const).map(
    ({
      id,
      structureName,
      componentName,
      materials,
      modularFile,
      manifestFile,
      initFile,
    }) => ({
      id,
      label: "Workstations",
      structureName,
      componentName,
      stages: makeAnimationStages({
        idPrefix: id,
        buildingN: 0,
        modularFile,
        manifestFile,
        initUrl: `/buildings/Construction/${initFile}`,
        initDescription: `Site prep — ${materials} (no station mesh)`,
      }),
    }),
  ),
  // Remaining INIT-only pads (not yet modularized).
  ...([
    {
      id: "crafting_workbench",
      structureName: "Crafting Workbench",
      componentName: "PioneeringCraftingWorkbench",
      materials: "Sycamore logs, Iron ore, GrindCoins",
      url: "/buildings/Construction/CraftingWorkbench_INIT.glb",
    },
  ] as const).map(({ id, structureName, componentName, materials, url }) => ({
    id,
    label: "Workstations",
    structureName,
    componentName,
    stages: [
      {
        id: `${id}_init`,
        label: "1 — Site Prep",
        description: `Compact pad with ${materials} (no station mesh)`,
        url,
      },
    ],
  })),
  {
    // Bridge4_ujuvoa — span assemble one bank → the other (Y-axis slices).
    id: "bridge4_animation",
    label: "Exterior Prop",
    structureName: "Bridge Animation",
    componentName: "PioneeringBridge4Animation",
    stages: makeAnimationStages({
      idPrefix: "bridge4_animation",
      buildingN: 0,
      modularFile: "Bridge4Animation_Modular.glb",
      manifestFile: "bridge4_animation_manifest.json",
      initUrl: "/buildings/Construction/Bridge4_INIT.glb",
      initDescription:
        "Site prep — Sycamore log stacks + GrindCoins staged at the near bank",
      assemblySteps: [
        {
          key: "foundation",
          label: "2 — Near Bank",
          description: "First span section settles on the near bank",
        },
        {
          key: "walls_a",
          label: "3 — Span A",
          description: "Bridge continues out from the near bank",
        },
        {
          key: "walls_b",
          label: "4 — Span B",
          description: "Next span section drops in along the crossing",
        },
        {
          key: "walls_c",
          label: "5 — Span C",
          description: "Mid-span section settles",
        },
        {
          key: "walls_d",
          label: "6 — Span D",
          description: "Bridge continues toward the far bank",
        },
        {
          key: "gable",
          label: "7 — Span E",
          description: "Far-side approach section drops in",
        },
        {
          key: "framing",
          label: "8 — Span F",
          description: "Nearly across — remaining deck sections settle",
        },
        {
          key: "eaves",
          label: "9 — Far Approach",
          description: "Last mid sections meet the far bank approach",
        },
        {
          key: "complete",
          label: "10 — Far Bank",
          description: "Far bank section drops in — full crossing complete",
        },
      ],
    }),
  },
  {
    // Well_qsaz5n — modular assemble bottom → top.
    id: "well_animation",
    label: "Exterior Prop",
    structureName: "Well Animation",
    componentName: "PioneeringWellAnimation",
    stages: makeAnimationStages({
      idPrefix: "well_animation",
      buildingN: 0,
      modularFile: "WellAnimation_Modular.glb",
      manifestFile: "well_animation_manifest.json",
      initUrl: "/buildings/Construction/Well_INIT.glb",
      initDescription:
        "Site prep — Sycamore logs, Clay, GrindCoins (no well mesh)",
    }),
  },
  {
    // Exact Building1Whole_jal0l1 GLB with Age-of-Empires construction
    // stages from `generate_building1_whole_construction.py`:
    //   INIT → P1 → P2 → P3 → Completed
    id: "building1_whole",
    label: "Medieval Building",
    structureName: "Cooking Building",
    componentName: "PioneeringBuilding1Whole",
    stages: [
      {
        id: "building1_whole_init",
        label: "INIT",
        description:
          "Resource piles only — Sycamore logs, Iron ore, Raw Catfish, Cooked Catfish, Clay, GrindCoin pile (no dirt pad / building mesh)",
        url: "/buildings/Construction/Building1Whole_INIT.glb",
      },
      {
        id: "building1_whole_p1",
        label: "P1",
        description:
          "Foundation rising — rock base / low walls with short scaffolding (AoE early build)",
        url: "/buildings/Construction/Building1Whole_P1.glb",
      },
      {
        id: "building1_whole_p2",
        label: "P2",
        description:
          "Walls mid-height with jagged masonry top and full scaffolding (AoE framing)",
        url: "/buildings/Construction/Building1Whole_P2.glb",
      },
      {
        id: "building1_whole_p3",
        label: "P3",
        description:
          "Nearly complete — walls and door in, roof half-up, scaffolding remains (AoE late build)",
        url: "/buildings/Construction/Building1Whole_P3.glb",
      },
      {
        id: "building1_whole_complete",
        label: "Completed",
        description:
          "Finished cooking building — exact source Building1Whole (walls / door / round-tile roof)",
        url: "/buildings/Building1Whole.glb",
      },
    ],
  },
  // Building2–8 Whole: same INIT materials + AoE stages from
  // `generate_building_whole_construction.py` (sources in
  // ~/Desktop/Buildings/NewBuildings/Completed).
  ...([
    { n: 2, structureName: "Pioneering Bank", componentName: "PioneeringBuilding2Whole" },
    { n: 3, structureName: "Apothecary Building", componentName: "PioneeringBuilding3Whole" },
    { n: 4, structureName: "Merchant Building", componentName: "PioneeringBuilding4Whole" },
    { n: 5, structureName: "Forge Building", componentName: "PioneeringBuilding5Whole" },
    { n: 6, structureName: "Workshop Building", componentName: "PioneeringBuilding6Whole" },
    { n: 7, structureName: "Manufacturing Building", componentName: "PioneeringBuilding7Whole" },
    { n: 8, structureName: "Chronocrafting Building", componentName: "PioneeringBuilding8Whole" },
  ] as const).map(({ n, structureName, componentName }) => ({
    id: `building${n}_whole`,
    label: "Medieval Building",
    structureName,
    componentName,
    stages: [
      {
        id: `building${n}_whole_init`,
        label: "INIT",
        description:
          "Resource piles only — Sycamore logs, Iron ore, Raw Catfish, Cooked Catfish, Clay, GrindCoin pile (no dirt pad / building mesh)",
        url: `/buildings/Construction/Building${n}Whole_INIT.glb`,
      },
      {
        id: `building${n}_whole_p1`,
        label: "P1",
        description:
          "Foundation rising — rock base / low walls with short scaffolding (AoE early build)",
        url: `/buildings/Construction/Building${n}Whole_P1.glb`,
      },
      {
        id: `building${n}_whole_p2`,
        label: "P2",
        description:
          "Walls mid-height with jagged masonry top and full scaffolding (AoE framing)",
        url: `/buildings/Construction/Building${n}Whole_P2.glb`,
      },
      {
        id: `building${n}_whole_p3`,
        label: "P3",
        description:
          "Nearly complete — walls and door in, roof half-up, scaffolding remains (AoE late build)",
        url: `/buildings/Construction/Building${n}Whole_P3.glb`,
      },
      {
        id: `building${n}_whole_complete`,
        label: "Completed",
        description: `Finished building — exact source Building${n}Whole`,
        url: `/buildings/Building${n}Whole.glb`,
      },
    ],
  })),
  {
    // Forge Building5Whole split into modular pieces (no Z-bisect) with
    // staggered drop-in playback — see `generate_building_animation.py`.
    id: "building_animation",
    label: "Medieval Building",
    structureName: "Building Animation",
    componentName: "PioneeringBuildingAnimation",
    stages: makeAnimationStages({
      idPrefix: "building_animation",
      buildingN: 5,
      modularFile: "BuildingAnimation_Modular.glb",
      manifestFile: "building_animation_manifest.json",
    }),
  },
  ...([
    { n: 1, id: "cooking_animation", structureName: "Cooking Animation", componentName: "PioneeringCookingAnimation" },
    { n: 2, id: "bank_animation", structureName: "Bank Animation", componentName: "PioneeringBankAnimation" },
    { n: 3, id: "apothecary_animation", structureName: "Apothecary Animation", componentName: "PioneeringApothecaryAnimation" },
    { n: 4, id: "merchant_animation", structureName: "Merchant Animation", componentName: "PioneeringMerchantAnimation" },
    { n: 6, id: "workshop_animation", structureName: "Workshop Animation", componentName: "PioneeringWorkshopAnimation" },
    { n: 7, id: "manufacturing_animation", structureName: "Manufacturing Animation", componentName: "PioneeringManufacturingAnimation" },
    { n: 8, id: "chronocrafting_animation", structureName: "Chronocrafting Animation", componentName: "PioneeringChronocraftingAnimation" },
  ] as const).map(({ n, id, structureName, componentName }) => ({
    id,
    label: "Medieval Building",
    structureName,
    componentName,
    stages: makeAnimationStages({
      idPrefix: id,
      buildingN: n,
      modularFile: `Building${n}Animation_Modular.glb`,
      manifestFile: `building${n}_animation_manifest.json`,
    }),
  })),
  {
    // SheepFence_nkdpvz — perimeter walk from west of gate → around → gate last.
    id: "sheep_fence_animation",
    label: "Exterior Prop",
    structureName: "Sheep Fence Animation",
    componentName: "PioneeringSheepFenceAnimation",
    stages: makeAnimationStages({
      idPrefix: "sheep_fence_animation",
      buildingN: 9,
      modularFile: "SheepFenceAnimation_Modular.glb",
      manifestFile: "sheep_fence_animation_manifest.json",
      initUrl: "/buildings/Construction/SheepFence_INIT.glb",
      initDescription:
        "Two sycamore log stacks at pasture center — fence materials only",
      assemblySteps: [
        {
          key: "foundation",
          label: "2 — Gate West",
          description: "Start at the west hinge post and first south-run panels",
        },
        {
          key: "walls_a",
          label: "3 — South Run",
          description: "Fence continues west along the south side",
        },
        {
          key: "walls_b",
          label: "4 — West Side",
          description: "Turn the corner — west side rises north",
        },
        {
          key: "walls_c",
          label: "5 — North West",
          description: "North run begins from the west corner",
        },
        {
          key: "walls_d",
          label: "6 — North Run",
          description: "North side continues east across the pasture",
        },
        {
          key: "gable",
          label: "7 — East Side",
          description: "East side drops in heading south",
        },
        {
          key: "framing",
          label: "8 — South East",
          description: "South run returns toward the gate opening",
        },
        {
          key: "eaves",
          label: "9 — Gate Approach",
          description: "Final panels meet the east side of the gate opening",
        },
        {
          key: "complete",
          label: "10 — Gate",
          description: "Gate leaf + forged iron fittings close the loop",
        },
      ],
    }),
  },
  {
    id: "sheep_fence",
    label: "Exterior Prop",
    structureName: "Sheep Fence",
    componentName: "PioneeringSheepFence",
    stages: [
      {
        id: "sheep_fence_complete",
        label: "Complete",
        description:
          "Pasture sheep fence — wood rails/posts + forged iron fittings (SheepFence_nkdpvz)",
        url: "/buildings/SheepFence.glb",
      },
    ],
  },
  {
    // CowFence.glb (GrindScape 7e88fe87-662e-4acb-8dc0-406e744b0258) —
    // perimeter walk from one gate post → around → other post last.
    // Swinging gate is a separate Cow Gate structure, not in this mesh.
    id: "cow_fence_animation",
    label: "Exterior Prop",
    structureName: "Cow Fence Animation",
    componentName: "PioneeringCowFenceAnimation",
    stages: makeAnimationStages({
      idPrefix: "cow_fence_animation",
      buildingN: 10,
      modularFile: "CowFenceAnimation_Modular.glb",
      manifestFile: "cow_fence_animation_manifest.json",
      initUrl: "/buildings/Construction/CowFence_INIT.glb",
      initDescription:
        "Two sycamore log stacks + GrindCoins at pasture center — fence materials only",
      assemblySteps: [
        {
          key: "foundation",
          label: "2 — Gate North",
          description: "Start at the north post of the west gate opening",
        },
        {
          key: "walls_a",
          label: "3 — West Run",
          description: "Fence continues north along the west side",
        },
        {
          key: "walls_b",
          label: "4 — North West",
          description: "Turn the corner — north side heads east",
        },
        {
          key: "walls_c",
          label: "5 — North Run",
          description: "North run continues across the pasture",
        },
        {
          key: "walls_d",
          label: "6 — East Side",
          description: "East side drops in heading south",
        },
        {
          key: "gable",
          label: "7 — South East",
          description: "Curved south-east corner of the cow pasture",
        },
        {
          key: "framing",
          label: "8 — South Run",
          description: "South side returns west toward the gate",
        },
        {
          key: "eaves",
          label: "9 — Gate Approach",
          description: "Final panels meet the south side of the gate opening",
        },
        {
          key: "complete",
          label: "10 — Gate Opening",
          description:
            "Last posts flank the west opening (swinging gate is a separate structure)",
        },
      ],
    }),
  },
  {
    id: "cow_fence",
    label: "Exterior Prop",
    structureName: "Cow Fence",
    componentName: "PioneeringCowFence",
    stages: [
      {
        id: "cow_fence_complete",
        label: "Complete",
        description:
          "Cow pasture fence — wood rails/posts with west gate gap (GrindScape CowFence.glb)",
        url: "/buildings/CowFence.glb",
      },
    ],
  },
  {
    // Farm hen + rooster. Authored FarmCreatures meshes, rigged by
    // generate_farm_chickens.py — bird armature + idle / walk / attack1 / die.
    id: "farm_chickens",
    label: "Farm Animal",
    structureName: "Chickens",
    componentName: "PioneeringChickens",
    stages: [
      {
        id: "farm_chicken",
        label: "Chicken",
        description:
          "Authored hen — skinned bird rig, clips: idle (loop), walk (loop), attack1, die",
        url: "/buildings/Chicken.glb",
      },
      {
        id: "farm_rooster",
        label: "Rooster",
        description:
          "Authored rooster — same clip set, prouder walk and a harder lunge",
        url: "/buildings/Rooster.glb",
      },
    ],
  },
];

export const BUILDINGS: BuildingDefinition[] = [
  ...BUILDING_IDS.map(makeBuildingEntry),
  ...EXTRA_STRUCTURES,
];

export const DEFAULT_BUILDING_STAGE_ID: string =
  BUILDINGS[0]?.stages[0]?.id ?? "";
