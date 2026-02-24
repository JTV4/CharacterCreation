export type Side = "C" | "L" | "R";
export type BoneCategory =
  | "spine"
  | "arm"
  | "leg"
  | "finger"
  | "face"
  | "other";

export interface BoneSpec {
  name: string;
  parent: string | null;
  side: Side;
  head: [number, number, number];
  tail: [number, number, number];
  roll: number;
  deform: boolean;
  category: BoneCategory;
}

export interface RigMeta {
  version: string;
  scale: string;
  rest_pose: string;
  forward_axis: string;
  up_axis: string;
  right_axis: string;
  mirror_convention: string;
  character_height: number;
}

export interface RigSpec {
  meta: RigMeta;
  bones: BoneSpec[];
  mirror_pairs: [string, string][];
}

export interface BoneNode extends BoneSpec {
  children: BoneNode[];
  mirrorOf: string | null;
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
