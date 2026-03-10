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

/**
 * Maps generic/equipment bone names to Mixamo bone names.
 * Used to bridge equipment GLBs (generic naming) with character models (Mixamo naming).
 * Note: Three.js GLTFLoader sanitizes node names via PropertyBinding.sanitizeNodeName(),
 * which strips colons. Raw GLB has "mixamorig:Hips" but runtime name is "mixamorigHips".
 */
export const BONE_ALIAS_MAP: Record<string, string> = {
  root: "mixamorigHips",
  pelvis: "mixamorigHips",
  spine_01: "mixamorigSpine",
  spine_02: "mixamorigSpine1",
  spine_03: "mixamorigSpine2",
  neck_01: "mixamorigNeck",
  head: "mixamorigHead",

  clavicle_L: "mixamorigLeftShoulder",
  clavicle_R: "mixamorigRightShoulder",
  upperarm_L: "mixamorigLeftArm",
  upperarm_R: "mixamorigRightArm",
  lowerarm_L: "mixamorigLeftForeArm",
  lowerarm_R: "mixamorigRightForeArm",
  hand_L: "mixamorigLeftHand",
  hand_R: "mixamorigRightHand",

  thigh_L: "mixamorigLeftUpLeg",
  thigh_R: "mixamorigRightUpLeg",
  shin_L: "mixamorigLeftLeg",
  shin_R: "mixamorigRightLeg",
  foot_L: "mixamorigLeftFoot",
  foot_R: "mixamorigRightFoot",
  toe_L: "mixamorigLeftToeBase",
  toe_R: "mixamorigRightToeBase",

  thumb_01_L: "mixamorigLeftHandThumb1",
  thumb_02_L: "mixamorigLeftHandThumb2",
  thumb_03_L: "mixamorigLeftHandThumb3",
  index_01_L: "mixamorigLeftHandIndex1",
  index_02_L: "mixamorigLeftHandIndex2",
  index_03_L: "mixamorigLeftHandIndex3",
  middle_01_L: "mixamorigLeftHandMiddle1",
  middle_02_L: "mixamorigLeftHandMiddle2",
  middle_03_L: "mixamorigLeftHandMiddle3",
  ring_01_L: "mixamorigLeftHandRing1",
  ring_02_L: "mixamorigLeftHandRing2",
  ring_03_L: "mixamorigLeftHandRing3",
  pinky_01_L: "mixamorigLeftHandPinky1",
  pinky_02_L: "mixamorigLeftHandPinky2",
  pinky_03_L: "mixamorigLeftHandPinky3",

  thumb_01_R: "mixamorigRightHandThumb1",
  thumb_02_R: "mixamorigRightHandThumb2",
  thumb_03_R: "mixamorigRightHandThumb3",
  index_01_R: "mixamorigRightHandIndex1",
  index_02_R: "mixamorigRightHandIndex2",
  index_03_R: "mixamorigRightHandIndex3",
  middle_01_R: "mixamorigRightHandMiddle1",
  middle_02_R: "mixamorigRightHandMiddle2",
  middle_03_R: "mixamorigRightHandMiddle3",
  ring_01_R: "mixamorigRightHandRing1",
  ring_02_R: "mixamorigRightHandRing2",
  ring_03_R: "mixamorigRightHandRing3",
  pinky_01_R: "mixamorigRightHandPinky1",
  pinky_02_R: "mixamorigRightHandPinky2",
  pinky_03_R: "mixamorigRightHandPinky3",
};
