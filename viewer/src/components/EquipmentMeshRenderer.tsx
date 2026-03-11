import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TransformControls } from "@react-three/drei";
import type {
  EquipmentState,
  EquipmentSlot,
  EquipTransform,
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
}

const BODY_SLOT_IDS = new Set([
  "base_body",
  "base_male",
  "base_female",
  "base_male_with_skin_texture",
  "base_female_with_skin_texture",
]);

const FINE_BONE_SLOTS = new Set(["gloves", "ring"]);

interface LoadedSlot {
  scene: THREE.Group;
  skinnedMeshes: THREE.SkinnedMesh[];
}

const loader = new GLTFLoader();
const slotCache = new Map<string, LoadedSlot>();
const correctedSlots = new Set<string>();
const _identityMatrix = new THREE.Matrix4();
const _equipFacingCorrection = new THREE.Matrix4().makeRotationZ(Math.PI);
const _yupToZupCorrection = new THREE.Matrix4().makeRotationX(Math.PI / 2);

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

  useEffect(() => {
    const enabledSlots = equipmentSlotIds.filter((id) => equipState[id]);
    const toLoad = enabledSlots.filter(
      (id) => !slotCache.has(id) && !loadingRef.current.has(id),
    );

    if (toLoad.length === 0) return;

    let cancelled = false;
    for (const slotId of toLoad) {
      loadingRef.current.add(slotId);
      const slot = slotMap.get(slotId);
      const isExternal = !!slot?.url;
      const loadUrl = slot?.url ?? `/equipment/${slotId}.glb`;
      loader.load(
        loadUrl,
        (gltf) => {
          loadingRef.current.delete(slotId);
          if (cancelled) return;

          const scene = gltf.scene;
          scene.visible = true;

          const skinnedMeshes = findSkinnedMeshes(scene);

          const geoCorrection = isExternal
            ? _yupToZupCorrection
            : _equipFacingCorrection;

          const color = SLOT_COLORS[slotId] ?? "#94a3b8";
          scene.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              mesh.geometry.applyMatrix4(geoCorrection);
              if (!isExternal) {
                mesh.material = new THREE.MeshStandardMaterial({
                  color,
                  transparent: true,
                  opacity: 0.35,
                  side: THREE.DoubleSide,
                  depthWrite: false,
                });
              }
              mesh.frustumCulled = false;
            }
          });

          const loaded: LoadedSlot = { scene, skinnedMeshes };
          slotCache.set(slotId, loaded);
          setLoadedSlots((prev) => {
            const next = new Map(prev);
            next.set(slotId, loaded);
            return next;
          });
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

  useFrame(() => {
    const player = playerRef.current;
    if (!player) return;
    const animBones = player.boneObjMap;
    if (!animBones || animBones.size === 0) return;

    for (const [slotId, slot] of slotCache) {
      if (BODY_SLOT_IDS.has(slotId)) continue;
      if (!effectiveState[slotId]) continue;

      if (!boundRef.current.has(slotId)) {
        bindSlotSkeleton(slot, animBones, charBoneInverseMap, slotId);
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
