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

export type ModelGender = "female" | "male";
