export interface ToolDefinition {
  id: string;
  name: string;
  url: string;
  color: string;
}

export type GizmoMode = "translate" | "rotate" | "scale";

export interface ToolTransform {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: number;
}

export const DEFAULT_TOOL_TRANSFORM: ToolTransform = {
  position: [0.1282, 0.0945, -0.0398],
  rotation: [0, 0, 0],
  scale: 1,
};

export const TOOLS: ToolDefinition[] = [
  {
    id: "fishing_rod",
    name: "Fishing Rod",
    url: "https://res.cloudinary.com/dyd9wffl9/image/upload/v1769791003/crystal_fishing_rod_c4tuf5.glb",
    color: "#60a5fa",
  },
  {
    id: "hammer",
    name: "Hammer",
    url: "https://res.cloudinary.com/dyd9wffl9/image/upload/v1770086230/iron_hammer_vkdfzz.glb",
    color: "#a78bfa",
  },
  {
    id: "hatchet",
    name: "Hatchet",
    url: "https://res.cloudinary.com/dyd9wffl9/image/upload/v1768359621/Iron_Hatchet_w1trho.glb",
    color: "#f472b6",
  },
  {
    id: "pickaxe",
    name: "Pickaxe",
    url: "https://res.cloudinary.com/dyd9wffl9/image/upload/v1768359074/Enchanted_Pickaxe_kkyzjm.glb",
    color: "#34d399",
  },
];
