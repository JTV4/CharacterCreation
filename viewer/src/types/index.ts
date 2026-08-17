import * as THREE from "three";

export type Side = "C" | "L" | "R";
export type BoneCategory =
  | "spine"
  | "arm"
  | "leg"
  | "finger"
  | "face"
  | "other";

export interface GlbBoneInfo {
  name: string;
  parent: string | null;
  side: Side;
  category: BoneCategory;
}

export interface GlbBoneNode extends GlbBoneInfo {
  children: GlbBoneNode[];
}

export interface CharacterModel {
  scene: THREE.Group;
  skinnedMeshes: THREE.SkinnedMesh[];
  boneObjMap: Map<string, THREE.Bone>;
  boneRestPose: Map<string, BoneRestTransform>;
  boneRestWorldInverses: Map<string, THREE.Matrix4>;
  skeletonRoot: THREE.Object3D;
  boneList: GlbBoneInfo[];
  boneTree: GlbBoneNode[];
}

export interface BoneRestTransform {
  position: THREE.Vector3;
  quaternion: THREE.Quaternion;
}

export const CATEGORY_COLORS: Record<BoneCategory, string> = {
  spine: "#4a9eff",
  arm: "#4adb7a",
  leg: "#ff6b6b",
  finger: "#ffd93d",
  face: "#c084fc",
  other: "#94a3b8",
};

export const CATEGORY_ORDER: BoneCategory[] = [
  "spine",
  "arm",
  "finger",
  "leg",
  "face",
  "other",
];

export interface BoneTransformOverride {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
}

/**
 * NPC roster — single source of truth.
 *
 * The viewer ships 8 character names, each in 4 skin/sex variants, for
 * a total of 32 NPCs.  Each NPC is its own GLB inside
 * `viewer/public/NPCs/<Variant>/<Name><Variant>.glb`.  The `NPCS` array
 * is generated from the `NPC_NAMES` x `NPC_VARIANTS` matrix below, so
 * adding a new character or variant only takes one entry in the right
 * list — every downstream consumer (URL resolver, dropdown, animation
 * manifest filter) reads from this array.
 *
 * To add a new NPC name:
 *   1. Drop GLBs into all four variant folders following the existing
 *      naming pattern.
 *   2. Append the name to `NPC_NAMES`.
 *   3. Add a `{ id, model, defaultAnimation }` row per variant to
 *      `viewer/public/animations/manifest.json` (see code there for
 *      the format) so the export panel can list them.
 *
 * To add a new variant: append to `NPC_VARIANTS`, drop GLBs into a new
 * folder, then mirror in manifest.json as above.
 */
export const NPC_NAMES = [
  "Apothecary",
  "Banker",
  "Blaise",
  "Chip",
  "Chronocrafter",
  "Cole",
  "Farmer",
  "Finn",
  "Hopper",
  "Hunter",
  "Manny",
  "Merchant",
  "Pyromaniac",
  "Ruben",
  "Scavenger",
] as const;

export type NpcName = (typeof NPC_NAMES)[number];

export const NPC_VARIANTS = [
  { folder: "BlackFemale", label: "Black Female", abbrev: "BF", key: "black_female" },
  { folder: "BlackMale",   label: "Black Male",   abbrev: "BM", key: "black_male"   },
  { folder: "WhiteFemale", label: "White Female", abbrev: "WF", key: "white_female" },
  { folder: "WhiteMale",   label: "White Male",   abbrev: "WM", key: "white_male"   },
] as const;

export type NpcVariant = (typeof NPC_VARIANTS)[number];
export type NpcVariantKey = NpcVariant["key"];
export type NpcVariantFolder = NpcVariant["folder"];

export type NpcGenderId = `npc_${Lowercase<NpcName>}_${NpcVariantKey}`;

export type ModelGender =
  | "female"
  | "male"
  | "female_v2"
  | "female_v3"
  | "male_v2"
  | "grind_male"
  | NpcGenderId;

export interface NpcEntry {
  /** ModelGender id, e.g. "npc_finn_white_female". */
  id: NpcGenderId;
  /** Combined display label, e.g. "Finn (White Female)" or just "Marina"
   *  when the slot has been promoted to a named character via
   *  `NPC_OVERRIDES`. */
  label: string;
  /** Character name, e.g. "Finn".  Used for grouping in the dropdown
   *  grid (the row header).  This stays as the original Meshy name even
   *  for promoted slots so the grid layout is preserved. */
  name: NpcName;
  /** Variant metadata (folder, label, abbrev, key). */
  variant: NpcVariant;
  /** Path under `viewer/public/NPCs/`, e.g. "WhiteFemale/FinnWhiteFemale.glb". */
  file: string;
  /** Manifest character entry id, e.g. "FinnWhiteFemale". */
  characterId: string;
  /** Optional friendly name for promoted NPCs (e.g. "Marina" for the
   *  Finn / White Female slot).  When set, it's used as the trigger
   *  button label and chip tooltip; absent otherwise. */
  displayName?: string;
}

/**
 * Per-cell overrides that promote a specific (name, variant) pair to a
 * named character.  `displayName` is required; `file` and `characterId`
 * are only needed when the underlying GLB has been renamed on disk
 * (e.g. ColeBlackFemale.glb -> SlateBlackFemale.glb).  For slots whose
 * promoted name is already in `NPC_NAMES` (Ruben, Hunter, Hopper,
 * Blaise) the file stays put and only the display label changes.
 */
type NpcOverrideKey = `${NpcName}/${NpcVariantFolder}`;

interface NpcOverride {
  displayName: string;
  file?: string;
  characterId?: string;
}

const NPC_OVERRIDES: Partial<Record<NpcOverrideKey, NpcOverride>> = {
  // First-pass promotions: Meshy placeholder slots that were renamed to
  // named characters.  The four with `file`/`characterId` overrides
  // were also renamed on disk (e.g. ColeBlackFemale.glb ->
  // SlateBlackFemale.glb); the four without them keep their source
  // filename and just gain a friendly display label.
  "Cole/BlackFemale":  { displayName: "Slate",  file: "BlackFemale/SlateBlackFemale.glb",  characterId: "SlateBlackFemale"  },
  "Ruben/BlackMale":   { displayName: "Ruben"  },
  "Hunter/WhiteMale":  { displayName: "Hunter" },
  "Finn/WhiteFemale":  { displayName: "Marina", file: "WhiteFemale/MarinaWhiteFemale.glb", characterId: "MarinaWhiteFemale" },
  "Chip/WhiteFemale":  { displayName: "Willow", file: "WhiteFemale/WillowWhiteFemale.glb", characterId: "WillowWhiteFemale" },
  "Hopper/WhiteMale":  { displayName: "Hopper" },
  "Blaise/BlackMale":  { displayName: "Blaise" },
  "Manny/WhiteFemale": { displayName: "Milly",  file: "WhiteFemale/MillyWhiteFemale.glb",  characterId: "MillyWhiteFemale"  },

  // Profession NPCs: each profession ships in all four variants and
  // every cell promotes to a named character.  Files keep the
  // `<Profession><Variant>.glb` naming on disk, so only displayName is
  // overridden — the generator's default file/characterId match.
  // Pyromaniac
  "Pyromaniac/BlackMale":   { displayName: "Flint"  },
  "Pyromaniac/WhiteMale":   { displayName: "Torch"  },
  "Pyromaniac/WhiteFemale": { displayName: "Ember"  },
  "Pyromaniac/BlackFemale": { displayName: "Sienna" },
  // Banker
  "Banker/BlackMale":       { displayName: "Sterling" },
  "Banker/WhiteMale":       { displayName: "Booker"   },
  "Banker/WhiteFemale":     { displayName: "Penny"    },
  "Banker/BlackFemale":     { displayName: "Aurelia"  },
  // Merchant
  "Merchant/BlackMale":     { displayName: "Mercer" },
  "Merchant/WhiteMale":     { displayName: "Porter" },
  "Merchant/WhiteFemale":   { displayName: "Marla"  },
  "Merchant/BlackFemale":   { displayName: "Veda"   },
  // Farmer
  "Farmer/BlackMale":       { displayName: "Silas"  },
  "Farmer/WhiteMale":       { displayName: "Rowan"  },
  "Farmer/WhiteFemale":     { displayName: "Hazel"  },
  "Farmer/BlackFemale":     { displayName: "Clover" },
  // Apothecary
  "Apothecary/BlackMale":   { displayName: "Basil" },
  "Apothecary/WhiteMale":   { displayName: "Sage"  },
  "Apothecary/WhiteFemale": { displayName: "Flora" },
  "Apothecary/BlackFemale": { displayName: "Zora"  },
  // Chronocrafter
  "Chronocrafter/BlackMale":   { displayName: "Orin"  },
  "Chronocrafter/WhiteMale":   { displayName: "Cyrus" },
  "Chronocrafter/WhiteFemale": { displayName: "Lyra"  },
  "Chronocrafter/BlackFemale": { displayName: "Nova"  },
  // Scavenger
  "Scavenger/BlackMale":       { displayName: "Miles"  },
  "Scavenger/WhiteMale":       { displayName: "Bran"   },
  "Scavenger/WhiteFemale":     { displayName: "Meadow" },
  "Scavenger/BlackFemale":     { displayName: "Mia"    },
};

export const NPCS: readonly NpcEntry[] = NPC_NAMES.flatMap((name) =>
  NPC_VARIANTS.map((variant) => {
    const overrideKey = `${name}/${variant.folder}` as NpcOverrideKey;
    const ov = NPC_OVERRIDES[overrideKey];
    const file = ov?.file ?? `${variant.folder}/${name}${variant.folder}.glb`;
    const characterId = ov?.characterId ?? `${name}${variant.folder}`;
    const displayName = ov?.displayName;
    return {
      id: `npc_${name.toLowerCase()}_${variant.key}` as NpcGenderId,
      label: displayName ?? `${name} (${variant.label})`,
      name,
      variant,
      file,
      characterId,
      displayName,
    };
  }),
);

export const NPC_GENDERS: ReadonlySet<ModelGender> = new Set(
  NPCS.map((n) => n.id),
);
