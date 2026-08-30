export type ToolCategory =
  | "swords"
  | "longbows"
  | "staves"
  | "pickaxes"
  | "hatchets"
  | "hammers"
  | "fishing_rods"
  | "farming"
  | "other";

export interface ToolCategoryInfo {
  key: ToolCategory;
  label: string;
  color: string;
}

/**
 * Display order for tool categories in the ToolPanel. Tools whose category
 * isn't listed fall through to "other" at the bottom.
 */
export const TOOL_CATEGORIES: ToolCategoryInfo[] = [
  { key: "swords",       label: "Swords",       color: "#94a3b8" },
  { key: "longbows",     label: "Longbows",     color: "#10b981" },
  { key: "staves",       label: "Staves",       color: "#a78bfa" },
  { key: "pickaxes",     label: "Pickaxes",     color: "#8b5cf6" },
  { key: "hatchets",     label: "Hatchets",     color: "#ec4899" },
  { key: "hammers",      label: "Hammers",      color: "#34d399" },
  { key: "fishing_rods", label: "Fishing Rods", color: "#3b82f6" },
  { key: "farming",      label: "Farming",      color: "#84cc16" },
  { key: "other",        label: "Other",        color: "#6b7280" },
];

export interface ToolDefinition {
  id: string;
  name: string;
  url: string;
  color: string;
  /** Grouping bucket used by the ToolPanel. Defaults to "other". */
  category?: ToolCategory;
  defaultTransform?: ToolTransform;
  /** Bone the tool is attached to. Defaults to the right hand. */
  attachBone?: string;
  /** Inventory / panel icon. */
  thumbnailUrl?: string;
}

export const DEFAULT_TOOL_ATTACH_BONE = "mixamorigRightHand";

export type GizmoMode = "translate" | "rotate" | "scale";

export interface ToolTransform {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: number;
}

export const DEFAULT_TOOL_TRANSFORM: ToolTransform = {
  position: [0, 0, 0],
  rotation: [0, 0, 0],
  scale: 1,
};

/** All bucket variants share one grip. Viewer overrides on any of these apply to all. */
export const SHARED_BUCKET_TOOL_IDS = [
  "empty_bucket",
  "water_bucket",
  "milk_bucket",
  "compost_bucket",
  "sand_bucket",
] as const;

export const BUCKET_GRIP_TRANSFORM: ToolTransform = {
  position: [0.04, 0.09, 0.02],
  rotation: [-90, 0, 0],
  scale: 1,
};

export const WATERING_CAN_GRIP_TRANSFORM: ToolTransform = {
  position: [0.04, 0.09, 0.02],
  rotation: [0, 0, 90],
  scale: 1,
};

/** Leather-wrap origin; pan along tool −Z, sieve faces +Y after glTF export. */
export const SAND_SIFTER_GRIP_TRANSFORM: ToolTransform = {
  position: [0.04, 0.09, 0.02],
  rotation: [-90, 0, 90],
  scale: 1,
};

/** Watering-can variants share one grip. */
export const SHARED_WATERING_CAN_TOOL_IDS = [
  "empty_tin_watering_can",
  "water_tin_watering_can",
] as const;

export function isSharedWateringCanTool(id: string | null): boolean {
  return !!id && (SHARED_WATERING_CAN_TOOL_IDS as readonly string[]).includes(id);
}

export function isSharedBucketTool(id: string | null): boolean {
  return !!id && (SHARED_BUCKET_TOOL_IDS as readonly string[]).includes(id);
}

export const TOOLS: ToolDefinition[] = [
  // Swords
  {
    id: "iron_sword",
    name: "Iron Sword",
    url: "/tools/Swords/IronSword.glb",
    color: "#94a3b8",
    category: "swords",
  },
  {
    id: "steel_sword",
    name: "Steel Sword",
    url: "/tools/Swords/SteelSword.glb",
    color: "#cbd5e1",
    category: "swords",
  },
  {
    id: "gold_sword",
    name: "Gold Sword",
    url: "/tools/Swords/GoldSword.glb",
    color: "#fbbf24",
    category: "swords",
  },
  {
    id: "titanium_sword",
    name: "Titanium Sword",
    url: "/tools/Swords/TitaniumSword.glb",
    color: "#e2e8f0",
    category: "swords",
  },
  {
    id: "tungsten_sword",
    name: "Tungsten Sword",
    url: "/tools/Swords/TungstenSword.glb",
    color: "#475569",
    category: "swords",
  },
  {
    id: "flourish_sword",
    name: "Flourish Sword",
    url: "/tools/Swords/FlourishSword.glb",
    color: "#fb923c",
    category: "swords",
  },
  {
    id: "fury_sword",
    name: "Fury Sword",
    url: "/tools/Swords/FurySword.glb",
    color: "#ef4444",
    category: "swords",
  },
  {
    id: "flow_sword",
    name: "Flow Sword",
    url: "/tools/Swords/FlowSword.glb",
    color: "#06b6d4",
    category: "swords",
  },
  {
    id: "enchanted_sword",
    name: "Enchanted Sword",
    url: "/tools/Swords/EnchantedSword.glb",
    color: "#a78bfa",
    category: "swords",
  },
  {
    id: "barbarian_axe",
    name: "Barbarian Axe",
    url: "/tools/Swords/BarbarianAxe.glb",
    color: "#b45309",
    category: "swords",
  },
  {
    id: "dragon_dagger",
    name: "Dragon Dagger",
    url: "/tools/Swords/DragonDagger.glb",
    color: "#059669",
    category: "swords",
  },
  {
    id: "spiked_club",
    name: "Spiked Club",
    url: "/tools/Swords/SpikedClub.glb",
    color: "#71717a",
    category: "swords",
  },
  {
    id: "ogre_maul",
    name: "Ogre Maul",
    url: "/tools/Swords/OgreMaul.glb",
    color: "#365314",
    category: "swords",
  },
  {
    id: "embervein_greatsword",
    name: "Embervein Greatsword",
    url: "/tools/Swords/EmberveinGreatsword.glb",
    color: "#dc2626",
    category: "swords",
  },

  // Longbows (held in the left hand)
  {
    id: "wrath_longbow",
    name: "Wrath Longbow",
    url: "/tools/Longbows/Wrath.glb",
    color: "#10b981",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },
  {
    id: "acacia_longbow",
    name: "Acacia Longbow",
    url: "/tools/Longbows/AcaciaLongbow.glb",
    color: "#92400e",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },
  {
    id: "calm_longbow",
    name: "Calm Longbow",
    url: "/tools/Longbows/Calm.glb",
    color: "#7dd3fc",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },
  {
    id: "embervein_longbow",
    name: "Embervein Longbow",
    url: "/tools/Longbows/EmberveinLongbow.glb",
    color: "#dc2626",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },
  {
    id: "growth_longbow",
    name: "Growth Longbow",
    url: "/tools/Longbows/Growth.glb",
    color: "#16a34a",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },
  {
    id: "pine_longbow",
    name: "Pine Longbow",
    url: "/tools/Longbows/PineLongbow.glb",
    color: "#15803d",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },
  {
    id: "poplar_longbow",
    name: "Poplar Longbow",
    url: "/tools/Longbows/PoplarLongbow.glb",
    color: "#ca8a04",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },
  {
    id: "sycamore_longbow",
    name: "Sycamore Longbow",
    url: "/tools/Longbows/SycamoreLongbow.glb",
    color: "#a16207",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },
  {
    id: "wisteria_longbow",
    name: "Wisteria Longbow",
    url: "/tools/Longbows/WisteriaLongbow.glb",
    color: "#a855f7",
    category: "longbows",
    attachBone: "mixamorigLeftHand",
    defaultTransform: {
      position: [-0.04, 0.19, 0.03],
      rotation: [0, 0, -170],
      scale: 0.76,
    },
  },

  // Staves
  {
    id: "dragons_eye_scepter",
    name: "Dragon's Eye Scepter",
    url: "/tools/Staves/DragonsEyeScepter.glb",
    color: "#ea580c",
    category: "staves",
  },
  {
    id: "embervein_staff",
    name: "Embervein Staff",
    url: "/tools/Staves/EmberveinStaff.glb",
    color: "#dc2626",
    category: "staves",
  },
  {
    id: "enchanted_staff",
    name: "Enchanted Staff",
    url: "/tools/Staves/EnchantedStaff.glb",
    color: "#a78bfa",
    category: "staves",
  },
  {
    id: "eternity_staff",
    name: "Eternity Staff",
    url: "/tools/Staves/EternityStaff.glb",
    color: "#6366f1",
    category: "staves",
  },
  {
    id: "peridot_staff",
    name: "Peridot Staff",
    url: "/tools/Staves/PeridotStaff.glb",
    color: "#84cc16",
    category: "staves",
  },
  {
    id: "renewal_staff",
    name: "Renewal Staff",
    url: "/tools/Staves/RenewalStaff.glb",
    color: "#22c55e",
    category: "staves",
  },
  {
    id: "rubellite_staff",
    name: "Rubellite Staff",
    url: "/tools/Staves/RubelliteStaff.glb",
    color: "#ec4899",
    category: "staves",
  },
  {
    id: "ruby_staff",
    name: "Ruby Staff",
    url: "/tools/Staves/RubyStaff.glb",
    color: "#dc2626",
    category: "staves",
  },
  {
    id: "serenity_staff",
    name: "Serenity Staff",
    url: "/tools/Staves/SerenityStaff.glb",
    color: "#0ea5e9",
    category: "staves",
  },
  {
    id: "spinel_staff",
    name: "Spinel Staff",
    url: "/tools/Staves/SpinelStaff.glb",
    color: "#d946ef",
    category: "staves",
  },
  {
    id: "topaz_staff",
    name: "Topaz Staff",
    url: "/tools/Staves/TopazStaff.glb",
    color: "#facc15",
    category: "staves",
  },

  // Pickaxes
  {
    id: "enchanted_pickaxe",
    name: "Enchanted Pickaxe",
    url: "/tools/pickaxes/enchanted_pickaxe.glb",
    color: "#a78bfa",
    category: "pickaxes",
  },
  {
    id: "tungsten_pickaxe",
    name: "Tungsten Pickaxe",
    url: "/tools/pickaxes/tungsten_pickaxe.glb",
    color: "#8b5cf6",
    category: "pickaxes",
  },
  {
    id: "titanium_pickaxe",
    name: "Titanium Pickaxe",
    url: "/tools/pickaxes/titanium_pickaxe.glb",
    color: "#7c3aed",
    category: "pickaxes",
  },
  {
    id: "steel_pickaxe",
    name: "Steel Pickaxe",
    url: "/tools/pickaxes/steel_pickaxe.glb",
    color: "#6d28d9",
    category: "pickaxes",
  },
  {
    id: "iron_pickaxe",
    name: "Iron Pickaxe",
    url: "/tools/pickaxes/iron_pickaxe.glb",
    color: "#5b21b6",
    category: "pickaxes",
  },
  {
    id: "gold_pickaxe",
    name: "Gold Pickaxe",
    url: "/tools/pickaxes/gold_pickaxe.glb",
    color: "#fbbf24",
    category: "pickaxes",
  },

  // Hatchets
  {
    id: "iron_hatchet",
    name: "Iron Hatchet",
    url: "/tools/hatchets/iron_hatchet.glb",
    color: "#f472b6",
    category: "hatchets",
  },
  {
    id: "enchanted_hatchet",
    name: "Enchanted Hatchet",
    url: "/tools/hatchets/enchanted_hatchet.glb",
    color: "#ec4899",
    category: "hatchets",
  },
  {
    id: "tungsten_hatchet",
    name: "Tungsten Hatchet",
    url: "/tools/hatchets/tungsten_hatchet.glb",
    color: "#db2777",
    category: "hatchets",
  },
  {
    id: "titanium_hatchet",
    name: "Titanium Hatchet",
    url: "/tools/hatchets/titanium_hatchet.glb",
    color: "#be185d",
    category: "hatchets",
  },
  {
    id: "steel_hatchet",
    name: "Steel Hatchet",
    url: "/tools/hatchets/steel_hatchet.glb",
    color: "#9d174d",
    category: "hatchets",
  },
  {
    id: "gold_hatchet",
    name: "Gold Hatchet",
    url: "/tools/hatchets/gold_hatchet.glb",
    color: "#f59e0b",
    category: "hatchets",
  },

  // Hammers
  {
    id: "iron_hammer",
    name: "Iron Hammer",
    url: "/tools/hammers/iron_hammer.glb",
    color: "#34d399",
    category: "hammers",
  },

  // Fishing Rods
  {
    id: "fungul_fishing_rod",
    name: "Fungul Fishing Rod",
    url: "/tools/fishing_rods/fungul_fishing_rod.glb",
    color: "#60a5fa",
    category: "fishing_rods",
  },
  {
    id: "skull_fishing_rod",
    name: "Skull Fishing Rod",
    url: "/tools/fishing_rods/skull_fishing_rod.glb",
    color: "#3b82f6",
    category: "fishing_rods",
  },
  {
    id: "fishing_rod",
    name: "Fishing Rod",
    url: "/tools/fishing_rods/fishing_rod.glb",
    color: "#2563eb",
    category: "fishing_rods",
  },
  {
    id: "crystal_fishing_rod",
    name: "Crystal Fishing Rod",
    url: "/tools/fishing_rods/crystal_fishing_rod.glb",
    color: "#93c5fd",
    category: "fishing_rods",
  },
  {
    id: "ethereal_fishing_rod",
    name: "Ethereal Fishing Rod",
    url: "/tools/fishing_rods/ethereal_fishing_rod.glb",
    color: "#bfdbfe",
    category: "fishing_rods",
  },
  {
    id: "verdant_fishing_rod",
    name: "Verdant Fishing Rod",
    url: "/tools/fishing_rods/verdant_fishing_rod.glb",
    color: "#4ade80",
    category: "fishing_rods",
  },

  // Farming
  {
    id: "empty_bucket",
    name: "Empty Bucket",
    url: "/tools/farming/EmptyBucket.glb",
    color: "#a3a3a3",
    category: "farming",
    defaultTransform: BUCKET_GRIP_TRANSFORM,
    thumbnailUrl: "/tools/farming/thumbs/EmptyBucket_thumb.png",
  },
  {
    id: "water_bucket",
    name: "Water Bucket",
    url: "/tools/farming/EmptyBucket.glb",
    color: "#38bdf8",
    category: "farming",
    defaultTransform: BUCKET_GRIP_TRANSFORM,
    thumbnailUrl: "/tools/farming/thumbs/WaterBucket_thumb.png",
  },
  {
    id: "milk_bucket",
    name: "Milk Bucket",
    url: "/tools/farming/EmptyBucket.glb",
    color: "#f5e6c8",
    category: "farming",
    defaultTransform: BUCKET_GRIP_TRANSFORM,
    thumbnailUrl: "/tools/farming/thumbs/MilkBucket_thumb.png",
  },
  {
    id: "compost_bucket",
    name: "Compost Bucket",
    url: "/tools/farming/EmptyBucket.glb",
    color: "#7a5a32",
    category: "farming",
    defaultTransform: BUCKET_GRIP_TRANSFORM,
    thumbnailUrl: "/tools/farming/thumbs/CompostBucket_thumb.png",
  },
  {
    id: "sand_bucket",
    name: "Sand Bucket",
    url: "/tools/farming/EmptyBucket.glb",
    color: "#d4b483",
    category: "farming",
    defaultTransform: BUCKET_GRIP_TRANSFORM,
    thumbnailUrl: "/tools/farming/thumbs/SandBucket_thumb.png",
  },
  {
    id: "empty_tin_watering_can",
    name: "Empty Watering Can",
    url: "/tools/farming/EmptyTinWateringCan.glb",
    color: "#a3a3a3",
    category: "farming",
    defaultTransform: WATERING_CAN_GRIP_TRANSFORM,
    thumbnailUrl: "/tools/farming/thumbs/EmptyTinWateringCan_thumb.png",
  },
  {
    id: "water_tin_watering_can",
    name: "Watering Can",
    url: "/tools/farming/EmptyTinWateringCan.glb",
    color: "#65a30d",
    category: "farming",
    defaultTransform: WATERING_CAN_GRIP_TRANSFORM,
    thumbnailUrl: "/tools/farming/thumbs/WaterTinWateringCan_thumb.png",
  },
  {
    id: "sand_sifter",
    name: "Sand Sifter",
    url: "/tools/farming/SandSifter.glb",
    color: "#a67c4a",
    category: "farming",
    defaultTransform: SAND_SIFTER_GRIP_TRANSFORM,
    thumbnailUrl: "/tools/farming/thumbs/SandSifter_thumb.png",
  },
];
