export interface SlotBone {
  name: string;
  weight: number;
}

export interface SlotBounds {
  z_min: number;
  z_max: number;
  radius: number;
}

export interface SlotRules {
  hidden_by?: string[];
}

/** Body regions that can be hidden when equipment covers them. */
export const BODY_REGIONS = [
  "head",
  "neck",
  "torso",
  "arms",
  "legs",
  "feet",
  "hands",
] as const;

export type BodyRegion = (typeof BODY_REGIONS)[number];

export interface EquipmentSlot {
  id: string;
  name: string;
  bilateral: boolean;
  /** Category for grouping in UI (e.g. "meshes", "equipment"). Defaults to "equipment". */
  category?: string;
  color?: string;
  /** If set, this slot only appears when the matching gender model is active. */
  gender?: "male" | "female";
  bones: SlotBone[];
  bounds: SlotBounds;
  rules: SlotRules;
  /** Body regions to hide when this slot is equipped. */
  hides_body_regions?: BodyRegion[];
  /** Optional URL to load mesh from (e.g. Cloudinary). If absent, loads from /equipment/{id}.glb */
  url?: string;
  mesh_type: string;
  mesh_params: Record<string, number | string>;
}

export interface EquipmentSpec {
  meta: {
    version: string;
    description: string;
    coordinate_system: {
      up: string;
      forward: string;
      right: string;
      scale: string;
    };
  };
  slots: EquipmentSlot[];
}

export interface EquipmentState {
  [slotId: string]: boolean;
}

export interface EquipTransform {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: number;
}

export const DEFAULT_EQUIP_TRANSFORM: EquipTransform = {
  position: [0, 0, 0],
  rotation: [0, 0, 0],
  scale: 1,
};

export const SLOT_COLORS: Record<string, string> = {
  base_body: "#e8b4a0",
  base_male: "#e8b4a0",
  base_female: "#e8b4a0",
  base_male_with_skin_texture: "#e8b4a0",
  base_female_with_skin_texture: "#e8b4a0",
  head: "#c084fc",
  amulet: "#fbbf24",
  upper_body: "#4a9eff",
  crimson_wizard_robe: "#7f1d1d",
  crimson_wizard_hat: "#991b1b",
  crimson_wizard_robe_bottom: "#b91c1c",
  crimson_wizard_gloves: "#dc2626",
  crimson_wizard_boots: "#ef4444",
  lower_body: "#ff6b6b",
  gloves: "#4adb7a",
  ring: "#ffd93d",
  boots: "#f97316",
};
