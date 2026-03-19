import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TransformControls } from "@react-three/drei";
import type {
  EquipmentState,
  EquipmentSlot,
  EquipTransform,
  SlotBone,
  SlotTextures,
} from "../types/equipment";
import type { GizmoMode } from "../types/tools";
import type { CharacterModel } from "../types";
import type { AnimationPlayerState } from "../hooks/useAnimationPlayer";
import { SLOT_COLORS } from "../types/equipment";

interface EquipmentMeshRendererProps {
  slotIds: string[];
  slots: EquipmentSlot[];
  equipState: EquipmentState;
  effectiveState: EquipmentState;
  playerRef: React.MutableRefObject<AnimationPlayerState | null>;
  characterModel: CharacterModel | null;
  selectedSlot: string | null;
  onSelectSlot: (id: string | null) => void;
  equipTransforms: Record<string, EquipTransform>;
  equipGizmoMode: GizmoMode;
  onEquipTransformChange: (id: string, t: EquipTransform) => void;
  slotTextures?: SlotTextures;
}

const BODY_SLOT_IDS = new Set([
  "base_body",
  "base_male",
  "base_female",
]);

const FINE_BONE_SLOTS = new Set(["gloves", "ring"]);

const INFLATE_SLOTS = new Set([
  "shell_gloves", "custom_gloves_f", "meshy_crimson_gloves_f", "crimson_wizard_gloves",
]);
const INFLATE_AMOUNT = 0.0;
const FINGERTIP_EXTEND = 0.022;

const SLOT_RENDER_ORDER: Record<string, number> = {
  upper_body: 1, shell_upper_body: 1, shell_upper_body_test_v1: 1, custom_upper_body_f: 1, custom_upper_body_f_textured: 1, custom_upper_body_f_crimson_meshy: 1, meshy_crimson_upperbody_f: 1,
  boots: 1, shell_boots: 1, shell_boots_test_v1: 1, custom_boots_f: 1, meshy_crimson_boots_f: 1,
  crimson_wizard_robe: 1, crimson_upperbody_f: 1, crimson_upperbody_meshy_v2: 1, crimson_wizard_boots: 1,
  lower_body: 2, shell_lower_body: 2, shell_lower_body_test_v1: 2, custom_lower_body_f: 2, meshy_crimson_lower_body_f: 2, red_lower_body_f: 2,
  crimson_wizard_robe_bottom: 2,
  head: 3, shell_head: 3, shell_head_test_v1: 3, custom_head_f: 3, meshy_crimson_head_f: 3, meshy_crimson_wizard_hat_f: 3, crimson_wizard_hat: 3,
  gloves: 3, shell_gloves: 3, shell_gloves_test_v1: 3, custom_gloves_f: 3, meshy_crimson_gloves_f: 3, crimson_wizard_gloves: 3,
  amulet: 4, ring: 4,
};

const STENCIL_WRITE_SLOTS = new Set([
  "upper_body", "shell_upper_body", "shell_upper_body_test_v1", "custom_upper_body_f", "custom_upper_body_f_textured", "custom_upper_body_f_crimson_meshy", "meshy_crimson_upperbody_f",
  "boots", "shell_boots", "shell_boots_test_v1", "custom_boots_f", "meshy_crimson_boots_f",
  "crimson_wizard_robe", "crimson_upperbody_f", "crimson_upperbody_meshy_v2", "crimson_wizard_boots",
  "meshy_crimson_head_f", "meshy_crimson_wizard_hat_f", "meshy_crimson_gloves_f",
]);
const STENCIL_TEST_SLOTS = new Set([
  "lower_body", "shell_lower_body", "custom_lower_body_f", "meshy_crimson_lower_body_f", "red_lower_body_f",
  "crimson_wizard_robe_bottom",
]);

interface LoadedSlot {
  scene: THREE.Group;
  skinnedMeshes: THREE.SkinnedMesh[];
  needsAutoSkin?: boolean;
  originalMaterials?: Map<THREE.Mesh, THREE.Material>;
}

const loader = new GLTFLoader();
const slotCache = new Map<string, LoadedSlot>();
const correctedSlots = new Set<string>();
const _buildTimestamp = Date.now();
const textureLoader = new THREE.TextureLoader();
const textureCache = new Map<string, THREE.Texture>();

/**
 * Build a MeshStandardMaterial that uses triplanar world-space projection
 * instead of UV coordinates.  The texture is projected from all 3 axes and
 * blended by surface normal, giving a natural wrapped look on body meshes
 * without requiring a hand-authored UV layout.
 */
function createTriplanarMaterial(
  texture: THREE.Texture,
  scale = 1.0,
  sharpness = 2.0,
): THREE.MeshStandardMaterial {
  const mat = new THREE.MeshStandardMaterial({
    map: texture,
    side: THREE.FrontSide,
    depthWrite: true,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
  });

  mat.onBeforeCompile = (shader) => {
    shader.uniforms.tpScale = { value: scale };
    shader.uniforms.tpSharp = { value: sharpness };

    shader.vertexShader = shader.vertexShader.replace(
      "#include <common>",
      `#include <common>
       varying vec3 vTriPos;
       varying vec3 vTriNorm;`,
    );
    shader.vertexShader = shader.vertexShader.replace(
      "#include <project_vertex>",
      `#include <project_vertex>
       vTriPos  = (modelMatrix * vec4(transformed, 1.0)).xyz;
       vTriNorm = normalize(mat3(modelMatrix) * objectNormal);`,
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <common>",
      `#include <common>
       varying vec3 vTriPos;
       varying vec3 vTriNorm;
       uniform float tpScale;
       uniform float tpSharp;`,
    );
    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <map_fragment>",
      `#ifdef USE_MAP
         vec3 tpW = pow(abs(vTriNorm), vec3(tpSharp));
         tpW /= (tpW.x + tpW.y + tpW.z);
         vec4 tpX = texture2D(map, vTriPos.yz * tpScale);
         vec4 tpY = texture2D(map, vTriPos.xz * tpScale);
         vec4 tpZ = texture2D(map, vTriPos.xy * tpScale);
         vec4 sampledDiffuseColor = tpX * tpW.x + tpY * tpW.y + tpZ * tpW.z;
         sampledDiffuseColor = sRGBTransferOETF(sampledDiffuseColor);
         diffuseColor *= sampledDiffuseColor;
       #endif`,
    );
  };

  return mat;
}
const _identityMatrix = new THREE.Matrix4();
const _equipFacingCorrection = new THREE.Matrix4().makeRotationZ(Math.PI);

// Character model is displayed at 1.9 / 1.75 scale (see useCharacterModel).
// External equipment GLBs are built at 1.75m rig height, so we bake the same
// scale into the geometry correction so equipment matches the character.
const _CHARACTER_HEIGHT_SCALE = 1.9 / 1.75;
const _yupToZupCorrection = new THREE.Matrix4().makeRotationX(Math.PI / 2);
_yupToZupCorrection.scale(
  new THREE.Vector3(
    _CHARACTER_HEIGHT_SCALE,
    _CHARACTER_HEIGHT_SCALE,
    _CHARACTER_HEIGHT_SCALE,
  ),
);

/**
 * Remap non-Mixamo bone names found in equipment GLBs to Mixamo names.
 * Covers the legacy generic rig AND the Decentraland Avatar_* rig.
 * Decentraland uses 4 finger bones per finger; the 4th maps to Mixamo's 3rd.
 */
const BONE_NAME_REMAP: Record<string, string> = {
  // --- Legacy generic rig ---
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

  // --- Decentraland Avatar_* rig ---
  Avatar_Hips: "mixamorigHips",
  Avatar_Spine: "mixamorigSpine",
  Avatar_Spine1: "mixamorigSpine1",
  Avatar_Spine2: "mixamorigSpine2",
  Avatar_Neck: "mixamorigNeck",
  Avatar_Head: "mixamorigHead",
  Avatar_LeftShoulder: "mixamorigLeftShoulder",
  Avatar_RightShoulder: "mixamorigRightShoulder",
  Avatar_LeftUpperArm: "mixamorigLeftArm",
  Avatar_RightUpperArm: "mixamorigRightArm",
  Avatar_LeftArm: "mixamorigLeftArm",
  Avatar_RightArm: "mixamorigRightArm",
  Avatar_LeftLowerArm: "mixamorigLeftForeArm",
  Avatar_RightLowerArm: "mixamorigRightForeArm",
  Avatar_LeftForeArm: "mixamorigLeftForeArm",
  Avatar_RightForeArm: "mixamorigRightForeArm",
  Avatar_LeftHand: "mixamorigLeftHand",
  Avatar_RightHand: "mixamorigRightHand",
  Avatar_LeftUpperLeg: "mixamorigLeftUpLeg",
  Avatar_RightUpperLeg: "mixamorigRightUpLeg",
  Avatar_LeftUpLeg: "mixamorigLeftUpLeg",
  Avatar_RightUpLeg: "mixamorigRightUpLeg",
  Avatar_LeftLowerLeg: "mixamorigLeftLeg",
  Avatar_RightLowerLeg: "mixamorigRightLeg",
  Avatar_LeftLeg: "mixamorigLeftLeg",
  Avatar_RightLeg: "mixamorigRightLeg",
  Avatar_LeftFoot: "mixamorigLeftFoot",
  Avatar_RightFoot: "mixamorigRightFoot",
  Avatar_LeftToeBase: "mixamorigLeftToeBase",
  Avatar_RightToeBase: "mixamorigRightToeBase",
  // Left hand (Decentraland has 4 bones per finger; 4th → Mixamo 3rd)
  Avatar_LeftHandThumb1: "mixamorigLeftHandThumb1",
  Avatar_LeftHandThumb2: "mixamorigLeftHandThumb2",
  Avatar_LeftHandThumb3: "mixamorigLeftHandThumb3",
  Avatar_LeftHandThumb4: "mixamorigLeftHandThumb3",
  Avatar_LeftHandIndex1: "mixamorigLeftHandIndex1",
  Avatar_LeftHandIndex2: "mixamorigLeftHandIndex2",
  Avatar_LeftHandIndex3: "mixamorigLeftHandIndex3",
  Avatar_LeftHandIndex4: "mixamorigLeftHandIndex3",
  Avatar_LeftHandMiddle1: "mixamorigLeftHandMiddle1",
  Avatar_LeftHandMiddle2: "mixamorigLeftHandMiddle2",
  Avatar_LeftHandMiddle3: "mixamorigLeftHandMiddle3",
  Avatar_LeftHandMiddle4: "mixamorigLeftHandMiddle3",
  Avatar_LeftHandRing1: "mixamorigLeftHandRing1",
  Avatar_LeftHandRing2: "mixamorigLeftHandRing2",
  Avatar_LeftHandRing3: "mixamorigLeftHandRing3",
  Avatar_LeftHandRing4: "mixamorigLeftHandRing3",
  Avatar_LeftHandPinky1: "mixamorigLeftHandPinky1",
  Avatar_LeftHandPinky2: "mixamorigLeftHandPinky2",
  Avatar_LeftHandPinky3: "mixamorigLeftHandPinky3",
  Avatar_LeftHandPinky4: "mixamorigLeftHandPinky3",
  // Right hand
  Avatar_RightHandThumb1: "mixamorigRightHandThumb1",
  Avatar_RightHandThumb2: "mixamorigRightHandThumb2",
  Avatar_RightHandThumb3: "mixamorigRightHandThumb3",
  Avatar_RightHandThumb4: "mixamorigRightHandThumb3",
  Avatar_RightHandIndex1: "mixamorigRightHandIndex1",
  Avatar_RightHandIndex2: "mixamorigRightHandIndex2",
  Avatar_RightHandIndex3: "mixamorigRightHandIndex3",
  Avatar_RightHandIndex4: "mixamorigRightHandIndex3",
  Avatar_RightHandMiddle1: "mixamorigRightHandMiddle1",
  Avatar_RightHandMiddle2: "mixamorigRightHandMiddle2",
  Avatar_RightHandMiddle3: "mixamorigRightHandMiddle3",
  Avatar_RightHandMiddle4: "mixamorigRightHandMiddle3",
  Avatar_RightHandRing1: "mixamorigRightHandRing1",
  Avatar_RightHandRing2: "mixamorigRightHandRing2",
  Avatar_RightHandRing3: "mixamorigRightHandRing3",
  Avatar_RightHandRing4: "mixamorigRightHandRing3",
  Avatar_RightHandPinky1: "mixamorigRightHandPinky1",
  Avatar_RightHandPinky2: "mixamorigRightHandPinky2",
  Avatar_RightHandPinky3: "mixamorigRightHandPinky3",
  Avatar_RightHandPinky4: "mixamorigRightHandPinky3",
};

function findSkinnedMeshes(root: THREE.Object3D): THREE.SkinnedMesh[] {
  const result: THREE.SkinnedMesh[] = [];
  root.traverse((child) => {
    if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
      result.push(child as THREE.SkinnedMesh);
    }
  });
  return result;
}

function findRegularMeshes(root: THREE.Object3D): THREE.Mesh[] {
  const result: THREE.Mesh[] = [];
  root.traverse((child) => {
    if (
      (child as THREE.Mesh).isMesh &&
      !(child as THREE.SkinnedMesh).isSkinnedMesh
    ) {
      result.push(child as THREE.Mesh);
    }
  });
  return result;
}

/**
 * Converts an unrigged Mesh to a SkinnedMesh with proximity-based bone weights.
 * Port of the assign_weights() logic from equipment/factory/mesh_factory.py.
 */
function autoSkinMesh(
  mesh: THREE.Mesh,
  slotBones: SlotBone[],
  animBones: Map<string, THREE.Bone>,
  charBoneInverseMap: Map<string, THREE.Matrix4>,
  slotBounds: { z_min: number; z_max: number; radius: number },
): THREE.SkinnedMesh | null {
  const MAX_INFLUENCES = 4;
  const weightRadius = slotBounds.radius * 2.0;

  const usedBones: THREE.Bone[] = [];
  const usedInverses: THREE.Matrix4[] = [];
  const boneConfigs: { bone: THREE.Bone; specWeight: number; position: THREE.Vector3 }[] = [];

  for (const sb of slotBones) {
    const animBone = animBones.get(sb.name);
    const inv = charBoneInverseMap.get(sb.name);
    if (!animBone || !inv) continue;
    animBone.updateMatrixWorld(true);
    const pos = new THREE.Vector3().setFromMatrixPosition(animBone.matrixWorld);
    usedBones.push(animBone);
    usedInverses.push(inv.clone());
    boneConfigs.push({ bone: animBone, specWeight: sb.weight, position: pos });
  }

  if (usedBones.length === 0) return null;

  const geo = mesh.geometry.clone();
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  if (!position) return null;

  const vertexCount = position.count;
  const skinIndices = new Float32Array(vertexCount * 4);
  const skinWeights = new Float32Array(vertexCount * 4);

  const vtx = new THREE.Vector3();

  for (let vi = 0; vi < vertexCount; vi++) {
    vtx.set(position.getX(vi), position.getY(vi), position.getZ(vi));

    const influences: { idx: number; w: number }[] = [];

    for (let bi = 0; bi < boneConfigs.length; bi++) {
      const dist = vtx.distanceTo(boneConfigs[bi].position);
      if (dist > weightRadius) continue;
      const falloff = Math.max(0, 1 - dist / weightRadius);
      const w = Math.pow(falloff, 3) * boneConfigs[bi].specWeight;
      if (w > 0.001) {
        influences.push({ idx: bi, w });
      }
    }

    influences.sort((a, b) => b.w - a.w);
    const top = influences.slice(0, MAX_INFLUENCES);
    const totalW = top.reduce((s, i) => s + i.w, 0);

    const base = vi * 4;
    for (let j = 0; j < 4; j++) {
      if (j < top.length && totalW > 0) {
        skinIndices[base + j] = top[j].idx;
        skinWeights[base + j] = top[j].w / totalW;
      } else {
        skinIndices[base + j] = 0;
        skinWeights[base + j] = 0;
      }
    }
  }

  geo.setAttribute("skinIndex", new THREE.BufferAttribute(skinIndices, 4));
  geo.setAttribute("skinWeight", new THREE.BufferAttribute(skinWeights, 4));

  const skinnedMesh = new THREE.SkinnedMesh(geo, mesh.material);
  skinnedMesh.name = mesh.name;
  skinnedMesh.frustumCulled = false;

  const skeleton = new THREE.Skeleton(usedBones, usedInverses);
  skinnedMesh.bind(skeleton, new THREE.Matrix4());

  return skinnedMesh;
}

/**
 * Scale an unrigged mesh to fit within a slot's bounding volume,
 * then center it on the slot's midpoint.
 */
function scaleToSlotBounds(
  scene: THREE.Group,
  slotBounds: { z_min: number; z_max: number; radius: number },
): void {
  const box = new THREE.Box3().setFromObject(scene);
  const size = new THREE.Vector3();
  box.getSize(size);
  const center = new THREE.Vector3();
  box.getCenter(center);

  const maxCurrent = Math.max(size.x, size.y, size.z);
  if (maxCurrent < 0.0001) return;

  const slotHeight = slotBounds.z_max - slotBounds.z_min;
  const slotWidth = slotBounds.radius * 2;
  const maxTarget = Math.max(slotHeight, slotWidth);
  if (maxTarget < 0.0001) return;

  const scaleFactor = maxTarget / maxCurrent;

  scene.scale.multiplyScalar(scaleFactor);
  scene.updateMatrixWorld(true);

  const newBox = new THREE.Box3().setFromObject(scene);
  const newCenter = new THREE.Vector3();
  newBox.getCenter(newCenter);

  const targetCenter = new THREE.Vector3(
    0,
    0,
    (slotBounds.z_min + slotBounds.z_max) / 2,
  );
  const offset = targetCenter.sub(newCenter);
  scene.position.add(offset);
}

function smoothOutlierVertices(
  geo: THREE.BufferGeometry,
  threshold: number,
  maxPasses = 6,
): number {
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  const idx = geo.index;
  if (!position || !idx) return 0;

  const adjMap = new Map<number, Set<number>>();
  for (let t = 0; t < idx.count; t += 3) {
    const a = idx.getX(t), b = idx.getX(t + 1), c = idx.getX(t + 2);
    for (const [v1, v2] of [[a, b], [b, c], [c, a]] as [number, number][]) {
      if (!adjMap.has(v1)) adjMap.set(v1, new Set());
      if (!adjMap.has(v2)) adjMap.set(v2, new Set());
      adjMap.get(v1)!.add(v2);
      adjMap.get(v2)!.add(v1);
    }
  }

  let totalFixed = 0;
  for (let pass = 0; pass < maxPasses; pass++) {
    let passFixed = 0;
    for (let vi = 0; vi < position.count; vi++) {
      const neighbors = adjMap.get(vi);
      if (!neighbors || neighbors.size < 2) continue;
      const px = position.getX(vi), py = position.getY(vi), pz = position.getZ(vi);
      let sx = 0, sy = 0, sz = 0, cnt = 0;
      for (const ni of neighbors) {
        sx += position.getX(ni); sy += position.getY(ni); sz += position.getZ(ni); cnt++;
      }
      const ax = sx / cnt, ay = sy / cnt, az = sz / cnt;
      const d = Math.sqrt((px - ax) ** 2 + (py - ay) ** 2 + (pz - az) ** 2);
      if (d > threshold) {
        position.setXYZ(vi, ax, ay, az);
        passFixed++;
      }
    }
    totalFixed += passFixed;
    if (passFixed === 0) break;
  }

  if (totalFixed > 0) position.needsUpdate = true;
  return totalFixed;
}

function inflateGeometry(geo: THREE.BufferGeometry, amount: number): void {
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  let normal = geo.getAttribute("normal") as THREE.BufferAttribute;
  if (!position) return;
  if (!normal) {
    geo.computeVertexNormals();
    normal = geo.getAttribute("normal") as THREE.BufferAttribute;
    if (!normal) return;
  }
  for (let i = 0; i < position.count; i++) {
    const px = position.getX(i), py = position.getY(i), pz = position.getZ(i);
    const nx = normal.getX(i), ny = normal.getY(i), nz = normal.getZ(i);
    const absPx = Math.abs(px);
    if (absPx > 0.75) {
      const radialLen = Math.sqrt(px * px + py * py);
      if (radialLen > 0.01) {
        const dot = (px * nx + py * ny) / radialLen;
        if (dot < 0) continue;
      }
    }
    position.setXYZ(i, px + nx * amount, py + ny * amount, pz + nz * amount);
  }
  position.needsUpdate = true;
}

function extendFingertips(
  geo: THREE.BufferGeometry,
  skeleton: THREE.Skeleton,
  amount: number,
): void {
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  const skinIndex = geo.getAttribute("skinIndex") as THREE.BufferAttribute;
  const skinWeight = geo.getAttribute("skinWeight") as THREE.BufferAttribute;
  if (!position || !skinIndex || !skinWeight) return;

  const boneScale = new Map<number, number>();
  const thumbBones = new Set<number>();
  const indexBones = new Set<number>();
  const middleBones = new Set<number>();
  const pinkyBones = new Set<number>();

  for (let i = 0; i < skeleton.bones.length; i++) {
    const n = skeleton.bones[i].name;
    let s = 0;
    if (/_03_|_03$|03_[LR]|Thumb3|Index3|Middle3|Ring3|Pinky3/.test(n)) s = 1.0;
    else if (/_02_|_02$|02_[LR]|Thumb2|Index2|Middle2|Ring2|Pinky2/.test(n)) s = 0.6;
    else if (/_01_|_01$|01_[LR]|Thumb1|Index1|Middle1|Ring1|Pinky1/.test(n)) s = 0.2;
    if (s === 0) continue;
    boneScale.set(i, s);
    if (/[Tt]humb/.test(n)) thumbBones.add(i);
    if (/[Ii]ndex/.test(n)) indexBones.add(i);
    if (/[Mm]iddle/.test(n)) middleBones.add(i);
    if (/[Pp]inky/.test(n)) pinkyBones.add(i);
  }
  if (boneScale.size === 0) return;

  const siGet = [
    (vi: number) => skinIndex.getX(vi),
    (vi: number) => skinIndex.getY(vi),
    (vi: number) => skinIndex.getZ(vi),
    (vi: number) => skinIndex.getW(vi),
  ];
  const swGet = [
    (vi: number) => skinWeight.getX(vi),
    (vi: number) => skinWeight.getY(vi),
    (vi: number) => skinWeight.getZ(vi),
    (vi: number) => skinWeight.getW(vi),
  ];

  for (let vi = 0; vi < position.count; vi++) {
    let dx = 0, dy = 0;
    let matched = false;

    for (let slot = 0; slot < 4; slot++) {
      const bIdx = siGet[slot](vi);
      const bW = swGet[slot](vi);
      if (bW < 0.05) continue;

      const s = boneScale.get(bIdx);
      if (s === undefined) continue;

      const px = position.getX(vi);
      const sign = px > 0 ? 1 : -1;
      const contrib = amount * s * bW;
      dx += sign * contrib;

      if (thumbBones.has(bIdx)) {
        dy -= contrib * 1.2;
      } else if (indexBones.has(bIdx)) {
        dy -= contrib * 0.4;
      } else if (pinkyBones.has(bIdx)) {
        dy += contrib * 0.4;
      } else if (middleBones.has(bIdx)) {
        dy -= contrib * 0.3;
      }
      matched = true;
    }

    if (matched) {
      position.setXYZ(
        vi,
        position.getX(vi) + dx,
        position.getY(vi) + dy,
        position.getZ(vi),
      );
    }
  }
  position.needsUpdate = true;
}

function fixZeroWeightVertices(sm: THREE.SkinnedMesh): void {
  const geo = sm.geometry;
  const skinWeight = geo.getAttribute("skinWeight") as THREE.BufferAttribute;
  const skinIndex = geo.getAttribute("skinIndex") as THREE.BufferAttribute;
  const position = geo.getAttribute("position") as THREE.BufferAttribute;

  if (!skinWeight || !skinIndex || !position) return;

  const skeleton = sm.skeleton;
  const boneCount = skeleton.boneInverses.length;
  if (boneCount === 0) return;

  const bonePositions: THREE.Vector3[] = [];
  const tmpMatrix = new THREE.Matrix4();
  for (let i = 0; i < boneCount; i++) {
    tmpMatrix.copy(skeleton.boneInverses[i]).invert();
    bonePositions.push(new THREE.Vector3().setFromMatrixPosition(tmpMatrix));
  }

  let fixed = 0;
  const vtx = new THREE.Vector3();

  for (let i = 0; i < position.count; i++) {
    const totalW =
      skinWeight.getX(i) +
      skinWeight.getY(i) +
      skinWeight.getZ(i) +
      skinWeight.getW(i);

    if (totalW > 0.001) continue;

    vtx.fromBufferAttribute(position, i);
    let minDist = Infinity;
    let nearestIdx = 0;

    for (let b = 0; b < boneCount; b++) {
      const d = vtx.distanceToSquared(bonePositions[b]);
      if (d < minDist) {
        minDist = d;
        nearestIdx = b;
      }
    }

    skinIndex.setXYZW(i, nearestIdx, 0, 0, 0);
    skinWeight.setXYZW(i, 1, 0, 0, 0);
    fixed++;
  }

  if (fixed > 0) {
    skinWeight.needsUpdate = true;
    skinIndex.needsUpdate = true;
  }
}

/**
 * For fine-bone slots (gloves, ring), shifts equipment vertices to match
 * the character's bone positions. Computes per-bone positional deltas
 * (old rig display-space → character world-space) and applies weighted
 * corrections so finger geometry aligns with the Mixamo skeleton.
 */
function applyRestPoseCorrection(
  sm: THREE.SkinnedMesh,
  boneDeltas: THREE.Vector3[],
): void {
  const geo = sm.geometry;
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  const skinIndex = geo.getAttribute("skinIndex") as THREE.BufferAttribute;
  const skinWeight = geo.getAttribute("skinWeight") as THREE.BufferAttribute;

  if (!position || !skinIndex || !skinWeight) return;

  const correction = new THREE.Vector3();

  for (let i = 0; i < position.count; i++) {
    correction.set(0, 0, 0);

    const indices = [
      skinIndex.getX(i), skinIndex.getY(i),
      skinIndex.getZ(i), skinIndex.getW(i),
    ];
    const weights = [
      skinWeight.getX(i), skinWeight.getY(i),
      skinWeight.getZ(i), skinWeight.getW(i),
    ];

    for (let j = 0; j < 4; j++) {
      const w = weights[j];
      if (w === 0) continue;
      const bIdx = indices[j];
      if (bIdx >= boneDeltas.length) continue;
      correction.addScaledVector(boneDeltas[bIdx], w);
    }

    position.setXYZ(
      i,
      position.getX(i) + correction.x,
      position.getY(i) + correction.y,
      position.getZ(i) + correction.z,
    );
  }

  position.needsUpdate = true;
}

function bindSlotSkeleton(
  slot: LoadedSlot,
  animBones: Map<string, THREE.Bone>,
  charBoneInverseMap: Map<string, THREE.Matrix4>,
  slotId?: string,
): void {
  const _tmpMat = new THREE.Matrix4();
  const isFineSlot = slotId != null && FINE_BONE_SLOTS.has(slotId);
  const alreadyCorrected = slotId != null && correctedSlots.has(slotId);

  for (const sm of slot.skinnedMeshes) {
    const oldSk = sm.skeleton;
    if (!oldSk) continue;

    const newBones: THREE.Bone[] = [];
    const newInverses: THREE.Matrix4[] = [];
    const boneDeltas: THREE.Vector3[] = [];

    for (let i = 0; i < oldSk.bones.length; i++) {
      const rawName = oldSk.bones[i].name;
      const boneName = BONE_NAME_REMAP[rawName] ?? rawName;
      const animBone = animBones.get(boneName);
      const charInv = charBoneInverseMap.get(boneName);

      if (animBone && charInv) {
        newBones.push(animBone);
        newInverses.push(charInv.clone());

        if (isFineSlot && !alreadyCorrected) {
          animBone.updateMatrixWorld(true);
          _tmpMat.copy(oldSk.boneInverses[i]).invert();
          const equipPosDisplay = new THREE.Vector3(
            -_tmpMat.elements[12],
            -_tmpMat.elements[13],
            _tmpMat.elements[14],
          );
          const charPos = new THREE.Vector3(
            animBone.matrixWorld.elements[12],
            animBone.matrixWorld.elements[13],
            animBone.matrixWorld.elements[14],
          );
          boneDeltas.push(charPos.clone().sub(equipPosDisplay));
        }
      } else {
        newBones.push(oldSk.bones[i] as THREE.Bone);
        newInverses.push(oldSk.boneInverses[i].clone());

        if (isFineSlot && !alreadyCorrected) {
          boneDeltas.push(new THREE.Vector3(0, 0, 0));
        }
      }
    }

    if (isFineSlot && !alreadyCorrected) {
      applyRestPoseCorrection(sm, boneDeltas);
    }

    const newSkeleton = new THREE.Skeleton(newBones, newInverses);
    sm.bind(newSkeleton, _identityMatrix);

    fixZeroWeightVertices(sm);

  }

  if (isFineSlot && !alreadyCorrected) {
    correctedSlots.add(slotId!);
  }
}

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

function EquipmentSlotWrapper({
  slotId,
  slot,
  isSelected,
  onSelect,
  transform,
  gizmoMode,
  onTransformChange,
}: {
  slotId: string;
  slot: LoadedSlot;
  isSelected: boolean;
  onSelect: () => void;
  transform: EquipTransform;
  gizmoMode: GizmoMode;
  onTransformChange: (t: EquipTransform) => void;
}) {
  const isDraggingRef = useRef(false);
  const tcRef = useRef<any>(null);
  const [sceneObj, setSceneObj] = useState<THREE.Object3D | null>(null);

  useEffect(() => {
    setSceneObj(slot.scene);
  }, [slot.scene]);

  const _offsetMatrix = useMemo(() => new THREE.Matrix4(), []);
  const _euler = useMemo(() => new THREE.Euler(), []);
  const _quat = useMemo(() => new THREE.Quaternion(), []);
  const _pos = useMemo(() => new THREE.Vector3(), []);
  const _scl = useMemo(() => new THREE.Vector3(), []);

  useFrame(() => {
    if (isDraggingRef.current) return;

    const scene = slot.scene;

    scene.position.set(...transform.position);
    scene.rotation.set(
      transform.rotation[0] * DEG2RAD,
      transform.rotation[1] * DEG2RAD,
      transform.rotation[2] * DEG2RAD,
    );
    scene.scale.setScalar(transform.scale);

    _euler.set(
      transform.rotation[0] * DEG2RAD,
      transform.rotation[1] * DEG2RAD,
      transform.rotation[2] * DEG2RAD,
    );
    _quat.setFromEuler(_euler);
    _pos.set(...transform.position);
    _scl.set(transform.scale, transform.scale, transform.scale);
    _offsetMatrix.compose(_pos, _quat, _scl);

    for (const sm of slot.skinnedMeshes) {
      sm.bindMatrix.copy(_offsetMatrix);
      sm.bindMatrixInverse.copy(_offsetMatrix).invert();
    }
  });

  const readTransform = useCallback(() => {
    const scene = slot.scene;
    onTransformChange({
      position: [
        +scene.position.x.toFixed(4),
        +scene.position.y.toFixed(4),
        +scene.position.z.toFixed(4),
      ],
      rotation: [
        +(scene.rotation.x * RAD2DEG).toFixed(2),
        +(scene.rotation.y * RAD2DEG).toFixed(2),
        +(scene.rotation.z * RAD2DEG).toFixed(2),
      ],
      scale: +scene.scale.x.toFixed(4),
    });
  }, [slot.scene, onTransformChange]);

  const handleDraggingChanged = useCallback(
    (e: THREE.Event & { value: boolean }) => {
      isDraggingRef.current = e.value;
      if (!e.value) {
        const scene = slot.scene;
        _euler.copy(scene.rotation);
        _quat.setFromEuler(_euler);
        _pos.copy(scene.position);
        _scl.copy(scene.scale);
        _offsetMatrix.compose(_pos, _quat, _scl);

        for (const sm of slot.skinnedMeshes) {
          sm.bindMatrix.copy(_offsetMatrix);
          sm.bindMatrixInverse.copy(_offsetMatrix).invert();
        }

        readTransform();
      }
    },
    [slot, readTransform, _euler, _quat, _pos, _scl, _offsetMatrix],
  );

  useEffect(() => {
    const tc = tcRef.current;
    if (!tc) return;
    tc.addEventListener("dragging-changed", handleDraggingChanged);
    return () => tc.removeEventListener("dragging-changed", handleDraggingChanged);
  }, [sceneObj, handleDraggingChanged]);

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      onSelect();
    },
    [onSelect],
  );

  return (
    <>
      <group
        onClick={handleClick}
        onPointerOver={(e) => {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "default";
        }}
      >
        <primitive object={slot.scene} />
      </group>
      {isSelected && sceneObj && (
        <TransformControls
          ref={tcRef}
          object={sceneObj}
          mode={gizmoMode}
          size={0.5}
          onChange={() => {
            if (isDraggingRef.current) {
              const scene = slot.scene;
              _euler.copy(scene.rotation);
              _quat.setFromEuler(_euler);
              _pos.copy(scene.position);
              _scl.copy(scene.scale);
              _offsetMatrix.compose(_pos, _quat, _scl);
              for (const sm of slot.skinnedMeshes) {
                sm.bindMatrix.copy(_offsetMatrix);
                sm.bindMatrixInverse.copy(_offsetMatrix).invert();
              }
            }
          }}
        />
      )}
    </>
  );
}

export default function EquipmentMeshRenderer({
  slotIds,
  slots,
  equipState,
  effectiveState,
  playerRef,
  characterModel,
  selectedSlot,
  onSelectSlot,
  equipTransforms,
  equipGizmoMode,
  onEquipTransformChange,
  slotTextures,
}: EquipmentMeshRendererProps) {
  const groupRef = useRef<THREE.Group>(null);
  const [loadedSlots, setLoadedSlots] = useState<Map<string, LoadedSlot>>(
    new Map(),
  );
  const loadingRef = useRef<Set<string>>(new Set());
  const boundRef = useRef<Set<string>>(new Set());

  const equipmentSlotIds = useMemo(
    () => slotIds.filter((id) => !BODY_SLOT_IDS.has(id)),
    [slotIds],
  );

  useEffect(() => {
    for (const id of equipmentSlotIds) {
      if (!effectiveState[id]) {
        boundRef.current.delete(id);
      }
    }
  }, [equipmentSlotIds, effectiveState]);

  const slotMap = useMemo(
    () => new Map(slots.map((s) => [s.id, s])),
    [slots],
  );

  const charBoneInverseMap = useMemo(() => {
    if (!characterModel) return new Map<string, THREE.Matrix4>();
    return characterModel.boneRestWorldInverses;
  }, [characterModel]);

  const skinSlots = useMemo(
    () => slots.filter((s) => s.mesh_type === "skin_color" || s.mesh_type === "skin_texture"),
    [slots],
  );
  const skinTextureSlotIds = useMemo(
    () => new Set(skinSlots.map((s) => s.id)),
    [skinSlots],
  );

  const originalBodyMatsRef = useRef<Map<THREE.SkinnedMesh, THREE.Material | THREE.Material[]>>(new Map());

  useEffect(() => {
    if (!characterModel) return;
    const activeSkinSlot = skinSlots.find((s) => effectiveState[s.id]);

    if (activeSkinSlot) {
      if (activeSkinSlot.mesh_type === "skin_color" && activeSkinSlot.color) {
        const color = new THREE.Color(activeSkinSlot.color);
        for (const sm of characterModel.skinnedMeshes) {
          if (!originalBodyMatsRef.current.has(sm)) {
            originalBodyMatsRef.current.set(sm, sm.material);
          }
          const mats = Array.isArray(sm.material) ? sm.material : [sm.material];
          for (const m of mats) {
            if ((m as any).isMeshStandardMaterial) {
              const stdMat = m as THREE.MeshStandardMaterial;
              stdMat.color.copy(color);
              stdMat.map = null;
              stdMat.roughness = 0.7;
              stdMat.metalness = 0.0;
              stdMat.needsUpdate = true;
            }
          }
        }
      } else if (activeSkinSlot.mesh_type === "skin_texture" && activeSkinSlot.url) {
        loader.load(activeSkinSlot.url + "?v=" + Date.now(), (gltf) => {
          let skinTexture: THREE.Texture | null = null;
          gltf.scene.traverse((child) => {
            if (skinTexture) return;
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
              for (const m of mats) {
                if ((m as any).isMeshStandardMaterial && (m as THREE.MeshStandardMaterial).map) {
                  skinTexture = (m as THREE.MeshStandardMaterial).map;
                  break;
                }
              }
            }
          });
          if (!skinTexture) return;
          for (const sm of characterModel.skinnedMeshes) {
            if (!originalBodyMatsRef.current.has(sm)) {
              originalBodyMatsRef.current.set(sm, sm.material);
            }
            const mats = Array.isArray(sm.material) ? sm.material : [sm.material];
            for (const m of mats) {
              if ((m as any).isMeshStandardMaterial) {
                const stdMat = m as THREE.MeshStandardMaterial;
                stdMat.map = skinTexture;
                stdMat.needsUpdate = true;
              }
            }
          }
        });
      }
    } else {
      for (const [sm, origMat] of originalBodyMatsRef.current) {
        sm.material = origMat;
      }
      originalBodyMatsRef.current.clear();
    }
  }, [characterModel, skinSlots, effectiveState]);

  useEffect(() => {
    const enabledSlots = equipmentSlotIds.filter((id) => equipState[id] && !skinTextureSlotIds.has(id));
    const toLoad = enabledSlots.filter(
      (id) => !slotCache.has(id) && !loadingRef.current.has(id),
    );

    if (toLoad.length === 0) return;

    let cancelled = false;
    for (const slotId of toLoad) {
      slotCache.delete(slotId);
      correctedSlots.delete(slotId);
      loadingRef.current.add(slotId);
      const slot = slotMap.get(slotId);
      const isExternal = !!slot?.url;
      const baseUrl = slot?.url ?? `/equipment/${slotId}.glb`;
      const loadUrl = `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}v=${Date.now()}`;
      loader.load(
        loadUrl,
        (gltf) => {
          loadingRef.current.delete(slotId);

          const scene = gltf.scene;
          scene.visible = true;

          let skinnedMeshes = findSkinnedMeshes(scene);
          const isImported = slot?.source === "imported";
          let needsAutoSkin = false;

          const geoCorrection = isExternal
            ? _yupToZupCorrection
            : _equipFacingCorrection;

          const color = SLOT_COLORS[slotId] ?? "#94a3b8";
          const origMats = new Map<THREE.Mesh, THREE.Material>();
          scene.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;

              if (!isImported) {
                mesh.geometry.applyMatrix4(geoCorrection);
              }

              if (INFLATE_SLOTS.has(slotId)) {
                smoothOutlierVertices(mesh.geometry, 0.05);
                inflateGeometry(mesh.geometry, INFLATE_AMOUNT);
                if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) {
                  extendFingertips(mesh.geometry, (mesh as THREE.SkinnedMesh).skeleton, FINGERTIP_EXTEND);
                }
              }

              const isMultiMaterial = Array.isArray(mesh.material);
              const materials: THREE.MeshStandardMaterial[] = isMultiMaterial
                ? (mesh.material as THREE.Material[]).filter((m): m is THREE.MeshStandardMaterial => (m as any).isMeshStandardMaterial)
                : ((mesh.material as any)?.isMeshStandardMaterial ? [mesh.material as THREE.MeshStandardMaterial] : []);
              const hasBakedTexture = materials.length > 0 && materials.some(m => m.map != null);

              for (const m of materials) {
                if (hasBakedTexture) {
                  m.side = THREE.DoubleSide;
                  m.transparent = false;
                  m.opacity = 1.0;
                  m.alphaTest = 0;
                  m.depthWrite = true;
                  m.polygonOffset = true;
                  m.polygonOffsetFactor = -1;
                  m.polygonOffsetUnits = -1;
                  m.blending = THREE.NormalBlending;
                  if ((m as any).transmission !== undefined) (m as any).transmission = 0;
                  if ((m as any).ior !== undefined) (m as any).ior = 1.5;
                  if ((m as any).thickness !== undefined) (m as any).thickness = 0;
                  m.needsUpdate = true;
                }
              }
              if (hasBakedTexture) {
                origMats.set(mesh, (isMultiMaterial ? (mesh.material as THREE.Material[])[0] : mesh.material) as THREE.Material);
              } else if (!isImported) {
                mesh.material = new THREE.MeshStandardMaterial({
                  color,
                  transparent: false,
                  opacity: 1.0,
                  side: THREE.DoubleSide,
                  depthWrite: true,
                  polygonOffset: true,
                  polygonOffsetFactor: -1,
                  polygonOffsetUnits: -1,
                });
              }

              const matForStencil = isMultiMaterial
                ? (mesh.material as THREE.Material[])
                : [mesh.material as THREE.Material];
              for (const sm of matForStencil) {
                if (STENCIL_WRITE_SLOTS.has(slotId)) {
                  (sm as any).stencilWrite = true;
                  (sm as any).stencilRef = 1;
                  (sm as any).stencilFunc = THREE.AlwaysStencilFunc;
                  (sm as any).stencilZPass = THREE.ReplaceStencilOp;
                  (sm as any).stencilZFail = THREE.KeepStencilOp;
                  (sm as any).stencilFail = THREE.KeepStencilOp;
                } else if (STENCIL_TEST_SLOTS.has(slotId)) {
                  (sm as any).stencilWrite = true;
                  (sm as any).stencilRef = 1;
                  (sm as any).stencilFunc = THREE.NotEqualStencilFunc;
                  (sm as any).stencilZPass = THREE.KeepStencilOp;
                  (sm as any).stencilZFail = THREE.KeepStencilOp;
                  (sm as any).stencilFail = THREE.KeepStencilOp;
                }
              }
              if (!hasBakedTexture && !isImported) {
                origMats.set(mesh, mesh.material as THREE.Material);
              } else if (isImported) {
                origMats.set(mesh, mesh.material as THREE.Material);
              }
              mesh.frustumCulled = false;
              const slotRenderOrder = SLOT_RENDER_ORDER[slotId] ?? 0;
              mesh.renderOrder = slotRenderOrder;
            }
          });

          if (skinnedMeshes.length === 0) {
            const regularMeshes = findRegularMeshes(scene);
            if (regularMeshes.length > 0 && slot) {
              if (isImported) {
                scene.rotation.set(Math.PI / 2, 0, 0);
                scene.updateMatrixWorld(true);
              }
              scaleToSlotBounds(scene, slot.bounds);
              needsAutoSkin = true;
            }
          }

          const loaded: LoadedSlot = { scene, skinnedMeshes, needsAutoSkin, originalMaterials: origMats };
          slotCache.set(slotId, loaded);
          if (!cancelled) {
            setLoadedSlots((prev) => {
              const next = new Map(prev);
              next.set(slotId, loaded);
              return next;
            });
          }
        },
        undefined,
        (err) => {
          loadingRef.current.delete(slotId);
          console.warn(`Failed to load equipment mesh: ${loadUrl}`, err);
        },
      );
    }

    return () => {
      cancelled = true;
    };
  }, [equipmentSlotIds, equipState, slotMap]);

  useEffect(() => {
    if (!slotTextures) return;
    for (const [slotId, slot] of slotCache) {
      const texUrl = slotTextures[slotId];
      slot.scene.traverse((child) => {
        if (!(child as THREE.Mesh).isMesh) return;
        const mesh = child as THREE.Mesh;

        if (texUrl) {
          let tex = textureCache.get(texUrl);
          if (!tex) {
            tex = textureLoader.load(texUrl);
            tex.colorSpace = THREE.SRGBColorSpace;
            tex.wrapS = THREE.RepeatWrapping;
            tex.wrapT = THREE.RepeatWrapping;
            tex.magFilter = THREE.LinearFilter;
            tex.minFilter = THREE.LinearMipmapLinearFilter;
            textureCache.set(texUrl, tex);
          }
          const triMat = createTriplanarMaterial(tex, 0.8, 2.0);
          triMat.customProgramCacheKey = () => "triplanar_" + slotId;
          mesh.material = triMat;
        } else {
          const origMat = slot.originalMaterials?.get(mesh);
          if (origMat) {
            mesh.material = origMat;
          } else {
            const color = SLOT_COLORS[slotId] ?? "#94a3b8";
            mesh.material = new THREE.MeshStandardMaterial({
              color,
              transparent: false,
              opacity: 1.0,
              side: THREE.FrontSide,
              depthWrite: true,
              polygonOffset: true,
              polygonOffsetFactor: -1,
              polygonOffsetUnits: -1,
            });
          }
        }
      });
    }
  }, [slotTextures, loadedSlots]);

  useFrame(() => {
    const player = playerRef.current;
    if (!player) return;
    const animBones = player.boneObjMap;
    if (!animBones || animBones.size === 0) return;

    for (const [slotId, slot] of slotCache) {
      if (BODY_SLOT_IDS.has(slotId)) continue;
      if (!effectiveState[slotId]) continue;

      if (!boundRef.current.has(slotId)) {
        if (slot.needsAutoSkin && slot.skinnedMeshes.length === 0) {
          const slotDef = slotMap.get(slotId);
          if (slotDef) {
            const regularMeshes = findRegularMeshes(slot.scene);
            for (const mesh of regularMeshes) {
              const sm = autoSkinMesh(
                mesh, slotDef.bones, animBones, charBoneInverseMap, slotDef.bounds,
              );
              if (sm) {
                const parent = mesh.parent;
                if (parent) {
                  parent.add(sm);
                  parent.remove(mesh);
                }
                slot.skinnedMeshes.push(sm);
              }
            }
            slot.needsAutoSkin = false;
          }
        }

        if (slot.skinnedMeshes.length > 0) {
          bindSlotSkeleton(slot, animBones, charBoneInverseMap, slotId);
        }
        slot.scene.visible = true;
        boundRef.current.add(slotId);
      }

    }
  });

  const defaultTransform = useMemo<EquipTransform>(
    () => ({ position: [0, 0, 0], rotation: [0, 0, 0], scale: 1 }),
    [],
  );

  return (
    <group ref={groupRef} name="equipment-meshes">
      {equipmentSlotIds.map((id) => {
        if (!effectiveState[id]) return null;
        if (skinTextureSlotIds.has(id)) return null;
        const slot = slotCache.get(id) ?? loadedSlots.get(id);
        if (!slot) return null;
        return (
          <EquipmentSlotWrapper
            key={id}
            slotId={id}
            slot={slot}
            isSelected={selectedSlot === id}
            onSelect={() => onSelectSlot(id)}
            transform={equipTransforms[id] ?? defaultTransform}
            gizmoMode={equipGizmoMode}
            onTransformChange={(t) => onEquipTransformChange(id, t)}
          />
        );
      })}
    </group>
  );
}
