export interface ToolDefinition {
  id: string;
  name: string;
  url: string;
  color: string;
  defaultTransform?: ToolTransform;
}

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

export const TOOLS: ToolDefinition[] = [
  // Fishing Rods
  {
    id: "fungul_fishing_rod",
    name: "Fungul Fishing Rod",
    url: "/tools/fishing_rods/fungul_fishing_rod.glb",
    color: "#60a5fa",
  },
  {
    id: "skull_fishing_rod",
    name: "Skull Fishing Rod",
    url: "/tools/fishing_rods/skull_fishing_rod.glb",
    color: "#3b82f6",
  },
  {
    id: "fishing_rod",
    name: "Fishing Rod",
    url: "/tools/fishing_rods/fishing_rod.glb",
    color: "#2563eb",
  },
  {
    id: "crystal_fishing_rod",
    name: "Crystal Fishing Rod",
    url: "/tools/fishing_rods/crystal_fishing_rod.glb",
    color: "#93c5fd",
  },
  {
    id: "ethereal_fishing_rod",
    name: "Ethereal Fishing Rod",
    url: "/tools/fishing_rods/ethereal_fishing_rod.glb",
    color: "#bfdbfe",
  },
  {
    id: "verdant_fishing_rod",
    name: "Verdant Fishing Rod",
    url: "/tools/fishing_rods/verdant_fishing_rod.glb",
    color: "#4ade80",
  },
  // Pickaxes
  {
    id: "enchanted_pickaxe",
    name: "Enchanted Pickaxe",
    url: "/tools/pickaxes/enchanted_pickaxe.glb",
    color: "#a78bfa",
  },
  {
    id: "tungsten_pickaxe",
    name: "Tungsten Pickaxe",
    url: "/tools/pickaxes/tungsten_pickaxe.glb",
    color: "#8b5cf6",
  },
  {
    id: "titanium_pickaxe",
    name: "Titanium Pickaxe",
    url: "/tools/pickaxes/titanium_pickaxe.glb",
    color: "#7c3aed",
  },
  {
    id: "steel_pickaxe",
    name: "Steel Pickaxe",
    url: "/tools/pickaxes/steel_pickaxe.glb",
    color: "#6d28d9",
  },
  {
    id: "iron_pickaxe",
    name: "Iron Pickaxe",
    url: "/tools/pickaxes/iron_pickaxe.glb",
    color: "#5b21b6",
  },
  {
    id: "gold_pickaxe",
    name: "Gold Pickaxe",
    url: "/tools/pickaxes/gold_pickaxe.glb",
    color: "#fbbf24",
  },
  // Hatchets
  {
    id: "iron_hatchet",
    name: "Iron Hatchet",
    url: "/tools/hatchets/iron_hatchet.glb",
    color: "#f472b6",
  },
  {
    id: "enchanted_hatchet",
    name: "Enchanted Hatchet",
    url: "/tools/hatchets/enchanted_hatchet.glb",
    color: "#ec4899",
  },
  {
    id: "tungsten_hatchet",
    name: "Tungsten Hatchet",
    url: "/tools/hatchets/tungsten_hatchet.glb",
    color: "#db2777",
  },
  {
    id: "titanium_hatchet",
    name: "Titanium Hatchet",
    url: "/tools/hatchets/titanium_hatchet.glb",
    color: "#be185d",
  },
  {
    id: "steel_hatchet",
    name: "Steel Hatchet",
    url: "/tools/hatchets/steel_hatchet.glb",
    color: "#9d174d",
  },
  {
    id: "gold_hatchet",
    name: "Gold Hatchet",
    url: "/tools/hatchets/gold_hatchet.glb",
    color: "#f59e0b",
  },
  // Hammers
  {
    id: "iron_hammer",
    name: "Iron Hammer",
    url: "/tools/hammers/iron_hammer.glb",
    color: "#34d399",
  },
];
