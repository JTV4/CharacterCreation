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

export const WEAR_SLOTS = [
  "helmet",
  "amulet",
  "cape",
  "top",
  "gloves",
  "bottom",
  "boots",
] as const;

export type WearSlot = (typeof WEAR_SLOTS)[number];

export function isRangerSlotId(id: string): boolean {
  return id.startsWith("ranger_");
}

/** Authored clothing and armor fitted to the current appearance/rework bind pose. */
export function isReworkArmorSlotId(id: string): boolean {
  // Alpha hats are baked to a head bind pose; never run generic bounds auto-fit.
  if (/^(?:alpha_)?(?:boghop|inventioners|shardspire|wildplume|wayfinder)(?:_(?:male|female)_helmet)?$/.test(id)) return true;
  if (/^seasonal_(halloween|thanksgiving|santa)_(male|female)_cape$/.test(id)) return true;
  if (/^combat_(?:ranged|mage|melee)_[1-4]_(?:male|female)_(?:helmet|cape)$/.test(id)) return true;
  return /^(?:starter_(?:homestead|dockhand|woodland|townsfolk|artisan|wayfarer)|ranged_(?:leather|green|blue|red|black|purple)|mage_(?:leather|green|blue|red|black|luminous)|iron_l1|steel_rework|gold_rework|titanium_rework|tungsten_rework|luminous_rework|pumpkin_rework|halloween_witch_rework|santa_rework|thanksgiving_rework)_(male|female)_(helmet|upperbody|gloves|lowerbody|boots)$/.test(id);
}

export function rangerPieceFromId(id: string): string | null {
  const match = /^ranger_(?:male|female)_(hat|amulet|cape|upperbody|gloves|lowerbody|boots)$/.exec(id);
  return match?.[1] ?? null;
}

export interface EquipmentSlot {
  id: string;
  name: string;
  bilateral: boolean;
  /** Category for grouping in UI (e.g. "meshes", "equipment"). Defaults to "equipment". */
  category?: string;
  color?: string;
  /** If set, this slot only appears when the matching gender model is active. */
  gender?: string;
  /** Clothing line / set this slot belongs to (e.g. "crimson_wizard", "shell"). Derived automatically when absent. */
  collection?: string;
  /** Exclusive wear category so e.g. ranger top and the rework shirt do not stack. */
  wear_slot?: WearSlot;
  bones: SlotBone[];
  bounds: SlotBounds;
  rules: SlotRules;
  /** Body regions or explicit mesh names to hide when this slot is equipped. */
  hides_body_regions?: Array<BodyRegion | string>;
  /** Temporarily hide the chosen hairstyle beneath a fitted hood. */
  hides_hair?: boolean;
  /** Conceal crown hair while leaving exposed locks and ponytails visible. */
  hair_fit?: string;
  /** Hide only the black base garment faces beneath this wearable. */
  hides_base_clothing?: Array<"bra" | "underwear">;
  /**
   * Optional baked-in transform that the viewer applies as the default when
   * the user has no runtime override for this slot. Use this to persist
   * gizmo-tuned position/rotation/scale (e.g. a hat that needs +Z/-Y nudging
   * to sit on the head correctly) without re-baking the GLB itself.
   */
  default_transform?: Omit<EquipTransform, "scale"> & {
    scale?: number | [number, number, number];
  };
  /**
   * Per-bone local offsets applied only to this wearable (body stays put).
   * Keys are Mixamo names without a colon (`mixamorigLeftForeArm`).
   */
  default_bone_offsets?: EquipBoneOffsetMap;
  /** Optional URL to load mesh from (e.g. Cloudinary). If absent, loads from /equipment/{id}.glb */
  url?: string;
  mesh_type: string;
  mesh_params: Record<string, number | string>;
  /** Whether this slot was imported at runtime (not from the spec file). */
  source?: "spec" | "imported";
  /** URL of a reference GLB whose bounding box is used for scale-matching during auto-skin. */
  scale_reference?: string;
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

export interface SlotTextures {
  [slotId: string]: string;
}

export interface EquipTransform {
  position: [number, number, number];
  rotation: [number, number, number];
  /** Per-axis scale [x, y, z]. Legacy numeric scale is normalized on load. */
  scale: [number, number, number];
  /**
   * Extra half-gap (meters) added between left/right halves of a bilateral
   * face accessory (eyes, eyebrows, eyelashes, ears).
   * 0 = authored spacing; positive = wider; negative = closer.
   */
  eyeSeparation?: number;
  /**
   * Per-eye local rotation in degrees [x, y, z], applied around each
   * eye's own center. Only used by `category: "eyes"` slots.
   */
  eyeRotationL?: [number, number, number];
  eyeRotationR?: [number, number, number];
  /**
   * Rotation/scale pivot convention.
   * - "origin" (legacy): TRS around geometry/armature origin
   * - "com": TRS around the mesh center of mass (default for new edits)
   */
  pivot?: "origin" | "com";
}

/** Accept legacy uniform `scale: number` from JSON / localStorage. */
export type EquipScaleInput = number | [number, number, number];

export function normalizeEquipScale(scale: EquipScaleInput | undefined): [number, number, number] {
  if (scale == null) return [1, 1, 1];
  if (typeof scale === "number") return [scale, scale, scale];
  if (Array.isArray(scale) && scale.length >= 3) {
    return [scale[0], scale[1], scale[2]];
  }
  return [1, 1, 1];
}

/** Normalize a transform that may still carry a legacy numeric scale. */
export function normalizeEquipTransform(
  t: Omit<EquipTransform, "scale"> & { scale?: EquipScaleInput },
): EquipTransform {
  return {
    ...t,
    scale: normalizeEquipScale(t.scale),
  };
}

/** Local TRS added on top of the character bone for one wearable. */
export interface EquipBoneOffset {
  position: [number, number, number];
  rotation: [number, number, number];
  scale: [number, number, number];
}

/** boneName → offset */
export type EquipBoneOffsetMap = Record<string, EquipBoneOffset>;

/** slotId → bone offsets */
export type EquipBoneOffsets = Record<string, EquipBoneOffsetMap>;

export const IDENTITY_BONE_OFFSET: EquipBoneOffset = {
  position: [0, 0, 0],
  rotation: [0, 0, 0],
  scale: [1, 1, 1],
};

export function normalizeBoneOffset(
  t?: Partial<EquipBoneOffset> | null,
): EquipBoneOffset {
  return {
    position: (t?.position as [number, number, number] | undefined) ?? [0, 0, 0],
    rotation: (t?.rotation as [number, number, number] | undefined) ?? [0, 0, 0],
    scale: normalizeEquipScale(t?.scale as EquipScaleInput | undefined),
  };
}

export function isIdentityBoneOffset(t: EquipBoneOffset): boolean {
  return (
    t.position.every((v) => Math.abs(v) < 1e-6) &&
    t.rotation.every((v) => Math.abs(v) < 1e-4) &&
    t.scale.every((v) => Math.abs(v - 1) < 1e-6)
  );
}

export function shortBoneLabel(name: string): string {
  return name.replace(/^mixamorig:?/, "");
}

export const DEFAULT_EQUIP_TRANSFORM: EquipTransform = {
  position: [0, 0, 0],
  rotation: [0, 0, 0],
  scale: [1, 1, 1],
  eyeSeparation: 0,
  eyeRotationL: [0, 0, 0],
  eyeRotationR: [0, 0, 0],
  pivot: "com",
};

export const EQUIPMENT_SLOT_TYPES = [
  "head", "amulet", "upper_body", "gloves", "ring", "lower_body", "boots",
] as const;

export type EquipmentSlotType = (typeof EQUIPMENT_SLOT_TYPES)[number];

export interface SlotTypeConfig {
  bilateral: boolean;
  color: string;
  hides_body_regions: BodyRegion[];
  mesh_type: string;
  bones: SlotBone[];
  bounds: SlotBounds;
}

export const SLOT_TYPE_CONFIGS: Record<EquipmentSlotType, SlotTypeConfig> = {
  head: {
    bilateral: false,
    color: "#c084fc",
    hides_body_regions: ["head"],
    mesh_type: "dome",
    bones: [
      { name: "mixamorigHead", weight: 1.0 },
      { name: "mixamorigNeck", weight: 0.25 },
    ],
    bounds: { z_min: 1.61, z_max: 1.90, radius: 0.13 },
  },
  amulet: {
    bilateral: false,
    color: "#fbbf24",
    hides_body_regions: [],
    mesh_type: "pendant",
    bones: [
      { name: "mixamorigSpine2", weight: 0.7 },
      { name: "mixamorigNeck", weight: 1.0 },
    ],
    bounds: { z_min: 1.41, z_max: 1.59, radius: 0.06 },
  },
  upper_body: {
    bilateral: false,
    color: "#4a9eff",
    hides_body_regions: ["torso", "neck", "arms"],
    mesh_type: "torso",
    bones: [
      { name: "mixamorigHips", weight: 0.6 },
      { name: "mixamorigSpine", weight: 1.0 },
      { name: "mixamorigSpine1", weight: 1.0 },
      { name: "mixamorigSpine2", weight: 1.0 },
      { name: "mixamorigLeftShoulder", weight: 0.8 },
      { name: "mixamorigRightShoulder", weight: 0.8 },
      { name: "mixamorigLeftArm", weight: 1.0 },
      { name: "mixamorigRightArm", weight: 1.0 },
      { name: "mixamorigLeftForeArm", weight: 1.0 },
      { name: "mixamorigRightForeArm", weight: 1.0 },
      { name: "mixamorigLeftHand", weight: 0.1 },
      { name: "mixamorigRightHand", weight: 0.1 },
      { name: "mixamorigNeck", weight: 0.1 },
    ],
    bounds: { z_min: 1.01, z_max: 1.54, radius: 0.75 },
  },
  gloves: {
    bilateral: true,
    color: "#4adb7a",
    hides_body_regions: ["hands"],
    mesh_type: "glove",
    bones: [
      { name: "mixamorigLeftHand", weight: 1.0 },
      { name: "mixamorigLeftHandThumb1", weight: 1.0 },
      { name: "mixamorigLeftHandThumb2", weight: 1.0 },
      { name: "mixamorigLeftHandThumb3", weight: 1.0 },
      { name: "mixamorigLeftHandIndex1", weight: 1.0 },
      { name: "mixamorigLeftHandIndex2", weight: 1.0 },
      { name: "mixamorigLeftHandIndex3", weight: 1.0 },
      { name: "mixamorigLeftHandMiddle1", weight: 1.0 },
      { name: "mixamorigLeftHandMiddle2", weight: 1.0 },
      { name: "mixamorigLeftHandMiddle3", weight: 1.0 },
      { name: "mixamorigLeftHandRing1", weight: 1.0 },
      { name: "mixamorigLeftHandRing2", weight: 1.0 },
      { name: "mixamorigLeftHandRing3", weight: 1.0 },
      { name: "mixamorigLeftHandPinky1", weight: 1.0 },
      { name: "mixamorigLeftHandPinky2", weight: 1.0 },
      { name: "mixamorigLeftHandPinky3", weight: 1.0 },
      { name: "mixamorigRightHand", weight: 1.0 },
      { name: "mixamorigRightHandThumb1", weight: 1.0 },
      { name: "mixamorigRightHandThumb2", weight: 1.0 },
      { name: "mixamorigRightHandThumb3", weight: 1.0 },
      { name: "mixamorigRightHandIndex1", weight: 1.0 },
      { name: "mixamorigRightHandIndex2", weight: 1.0 },
      { name: "mixamorigRightHandIndex3", weight: 1.0 },
      { name: "mixamorigRightHandMiddle1", weight: 1.0 },
      { name: "mixamorigRightHandMiddle2", weight: 1.0 },
      { name: "mixamorigRightHandMiddle3", weight: 1.0 },
      { name: "mixamorigRightHandRing1", weight: 1.0 },
      { name: "mixamorigRightHandRing2", weight: 1.0 },
      { name: "mixamorigRightHandRing3", weight: 1.0 },
      { name: "mixamorigRightHandPinky1", weight: 1.0 },
      { name: "mixamorigRightHandPinky2", weight: 1.0 },
      { name: "mixamorigRightHandPinky3", weight: 1.0 },
    ],
    bounds: { z_min: 1.49, z_max: 1.54, radius: 0.20 },
  },
  ring: {
    bilateral: false,
    color: "#ffd93d",
    hides_body_regions: [],
    mesh_type: "torus",
    bones: [
      { name: "mixamorigLeftHandRing1", weight: 1.0 },
      { name: "mixamorigLeftHandRing2", weight: 0.4 },
    ],
    bounds: { z_min: 1.51, z_max: 1.53, radius: 0.015 },
  },
  lower_body: {
    bilateral: true,
    color: "#ff6b6b",
    hides_body_regions: ["torso", "legs"],
    mesh_type: "pants",
    bones: [
      { name: "mixamorigHips", weight: 1.0 },
      { name: "mixamorigLeftUpLeg", weight: 1.0 },
      { name: "mixamorigRightUpLeg", weight: 1.0 },
      { name: "mixamorigLeftLeg", weight: 0.8 },
      { name: "mixamorigRightLeg", weight: 0.8 },
    ],
    bounds: { z_min: 0.29, z_max: 1.09, radius: 0.18 },
  },
  boots: {
    bilateral: true,
    color: "#f97316",
    hides_body_regions: ["feet", "legs"],
    mesh_type: "boot",
    bones: [
      { name: "mixamorigLeftLeg", weight: 0.6 },
      { name: "mixamorigRightLeg", weight: 0.6 },
      { name: "mixamorigLeftFoot", weight: 1.0 },
      { name: "mixamorigRightFoot", weight: 1.0 },
      { name: "mixamorigLeftToeBase", weight: 1.0 },
      { name: "mixamorigRightToeBase", weight: 1.0 },
    ],
    bounds: { z_min: -0.02, z_max: 0.52, radius: 0.12 },
  },
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
  crimson_upperbody_f: "#9f1239",
  custom_head_f: "#d8b4fe",
  custom_upper_body_f: "#93c5fd",
  custom_gloves_f: "#6ee7b7",
  custom_lower_body_f: "#fca5a5",
  custom_boots_f: "#fdba74",
  shell_head: "#a78bfa",
  shell_upper_body: "#60a5fa",
  shell_gloves: "#34d399",
  shell_lower_body: "#f87171",
  shell_boots: "#fb923c",
  shell_upper_body_crimson: "#9f1239",
  rework_male_shirt: "#c4b5a0",
  ranger_male_hat: "#5c7a4a",
  ranger_male_amulet: "#c4a35a",
  ranger_male_cape: "#3d5c3a",
  ranger_male_upperbody: "#6b8f4e",
  ranger_male_gloves: "#8b6b3d",
  ranger_male_lowerbody: "#4a5c38",
  ranger_male_boots: "#5c4030",
  ranger_female_hat: "#5c7a4a",
  ranger_female_amulet: "#c4a35a",
  ranger_female_cape: "#3d5c3a",
  ranger_female_upperbody: "#6b8f4e",
  ranger_female_gloves: "#8b6b3d",
  ranger_female_lowerbody: "#4a5c38",
  ranger_female_boots: "#5c4030",
  green_dragon_wizard_hat_f: "#166534",
  green_dragon_top_f: "#15803d",
  green_dragon_legs_f: "#16a34a",
  green_dragon_gloves_f: "#22c55e",
  green_dragon_boots_f: "#4ade80",
};
