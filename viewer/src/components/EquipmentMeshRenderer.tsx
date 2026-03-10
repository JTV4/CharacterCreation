import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type {
  EquipmentState,
  EquipmentSlot,
  BodyRegion,
} from "../types/equipment";
import type { AnimationPlayerState } from "../hooks/useAnimationPlayer";
import { SLOT_COLORS } from "../types/equipment";

interface EquipmentMeshRendererProps {
  slotIds: string[];
  slots: EquipmentSlot[];
  equipState: EquipmentState;
  effectiveState: EquipmentState;
  playerRef: React.MutableRefObject<AnimationPlayerState | null>;
}

const BODY_SLOT_IDS = new Set([
  "base_body",
  "base_male",
  "base_female",
  "base_male_with_skin_texture",
  "base_female_with_skin_texture",
]);

interface LoadedSlot {
  scene: THREE.Group;
  skinnedMeshes: THREE.SkinnedMesh[];
}

const loader = new GLTFLoader();
const slotCache = new Map<string, LoadedSlot>();
const _identityMatrix = new THREE.Matrix4();
const _flipY = new THREE.Matrix4().makeRotationY(Math.PI);

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

function bindSlotSkeleton(
  slot: LoadedSlot,
  animBones: Map<string, THREE.Bone>,
): void {
  for (const sm of slot.skinnedMeshes) {
    const oldSk = sm.skeleton;
    if (!oldSk) continue;

    const newBones: THREE.Bone[] = [];
    const newInverses: THREE.Matrix4[] = [];

    for (let i = 0; i < oldSk.bones.length; i++) {
      const boneName = oldSk.bones[i].name;
      const animBone = animBones.get(boneName);

      const correctedInverse = oldSk.boneInverses[i].clone().multiply(_flipY);
      if (animBone) {
        newBones.push(animBone);
        newInverses.push(correctedInverse);
      } else {
        newBones.push(oldSk.bones[i] as THREE.Bone);
        newInverses.push(correctedInverse);
      }
    }

    const newSkeleton = new THREE.Skeleton(newBones, newInverses);
    sm.bind(newSkeleton, _identityMatrix);

    fixZeroWeightVertices(sm);
  }
}

export default function EquipmentMeshRenderer({
  slotIds,
  slots,
  equipState,
  effectiveState,
  playerRef,
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
      const loadUrl = slot?.url ?? `/equipment/${slotId}.glb`;
      loader.load(
        loadUrl,
        (gltf) => {
          loadingRef.current.delete(slotId);
          if (cancelled) return;

          const scene = gltf.scene;
          scene.visible = true;

          const skinnedMeshes = findSkinnedMeshes(scene);

          const color = SLOT_COLORS[slotId] ?? "#94a3b8";
          scene.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              mesh.material = new THREE.MeshStandardMaterial({
                color,
                transparent: true,
                opacity: 0.35,
                side: THREE.DoubleSide,
                depthWrite: false,
              });
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
        bindSlotSkeleton(slot, animBones);
        slot.scene.visible = true;
        boundRef.current.add(slotId);
      }
    }
  });

  return (
    <group ref={groupRef} name="equipment-meshes">
      {equipmentSlotIds.map((id) => {
        if (!effectiveState[id]) return null;
        const slot = slotCache.get(id) ?? loadedSlots.get(id);
        if (!slot) return null;
        return <primitive key={id} object={slot.scene} />;
      })}
    </group>
  );
}
