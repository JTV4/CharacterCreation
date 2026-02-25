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

export interface EquipmentSlot {
  id: string;
  name: string;
  bilateral: boolean;
  color?: string;
  bones: SlotBone[];
  bounds: SlotBounds;
  rules: SlotRules;
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

export const SLOT_COLORS: Record<string, string> = {
  head: "#c084fc",
  amulet: "#fbbf24",
  gloves: "#4adb7a",
  ring: "#ffd93d",
  upper_body: "#4a9eff",
  lower_body: "#ff6b6b",
  boots: "#f97316",
};
