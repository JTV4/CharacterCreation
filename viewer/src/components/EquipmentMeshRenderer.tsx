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

const BODY_SLOT_PREFIXES = [
  "equip_base_body_",
  "equip_base_male_",
  "equip_base_female_",
  "equip_base_male_with_skin_texture_",
  "equip_base_female_with_skin_texture_",
];

/** Parse body region from mesh name like "equip_base_body_head" or "equip_base_male_head" -> "head" */
function getBodyRegionFromMeshName(name: string): BodyRegion | null {
  let region: string | null = null;
  for (const prefix of BODY_SLOT_PREFIXES) {
    if (name.startsWith(prefix)) {
      region = name.slice(prefix.length);
      break;
    }
  }
  if (!region) return null;
  const valid: readonly string[] = [
    "head",
    "neck",
    "torso",
    "arms",
    "legs",
    "feet",
    "hands",
  ];
  return valid.includes(region) ? (region as BodyRegion) : null;
}

function computeHiddenBodyRegions(
  slots: EquipmentSlot[],
  effectiveState: EquipmentState,
): Set<BodyRegion> {
  const hidden = new Set<BodyRegion>();
  const bodySlotIds = new Set([
    "base_body",
    "base_male",
    "base_female",
    "base_male_with_skin_texture",
    "base_female_with_skin_texture",
  ]);
  for (const slot of slots) {
    if (bodySlotIds.has(slot.id)) continue;
    if (!effectiveState[slot.id]) continue;
    const regions = slot.hides_body_regions ?? [];
    for (const r of regions) {
      hidden.add(r);
    }
  }
  return hidden;
}

interface LoadedSlot {
  scene: THREE.Group;
  skinnedMeshes: THREE.SkinnedMesh[];
}

const loader = new GLTFLoader();
const slotCache = new Map<string, LoadedSlot>();
const _identityMatrix = new THREE.Matrix4();

function findSkinnedMeshes(root: THREE.Object3D): THREE.SkinnedMesh[] {
  const result: THREE.SkinnedMesh[] = [];
  root.traverse((child) => {
    if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
      result.push(child as THREE.SkinnedMesh);
    }
  });
  return result;
}

/**
 * Scan a SkinnedMesh for vertices with zero total weight and assign them
 * to the nearest bone so they don't stay frozen in bind pose.
 */
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
  restInverses: Map<string, THREE.Matrix4>,
): void {
  for (const sm of slot.skinnedMeshes) {
    const oldSk = sm.skeleton;
    if (!oldSk) continue;

    const newBones: THREE.Bone[] = [];
    const newInverses: THREE.Matrix4[] = [];

    for (let i = 0; i < oldSk.bones.length; i++) {
      const boneName = oldSk.bones[i].name;
      const animBone = animBones.get(boneName);
      const restInv = restInverses.get(boneName);

      if (animBone && restInv) {
        newBones.push(animBone);
        newInverses.push(restInv.clone());
      } else {
        newBones.push(oldSk.bones[i] as THREE.Bone);
        newInverses.push(oldSk.boneInverses[i].clone());
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

  useEffect(() => {
    for (const id of slotIds) {
      if (!effectiveState[id]) {
        boundRef.current.delete(id);
      }
    }
  }, [slotIds, effectiveState]);

  const slotMap = useMemo(
    () => new Map(slots.map((s) => [s.id, s])),
    [slots],
  );

  useEffect(() => {
    const enabledSlots = slotIds.filter((id) => equipState[id]);
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

          // External base body meshes may be Y-up (glTF) or Z-up (from skin_base_meshes).
          // Apply Y-up→Z-up fix only when mesh height is along Y (unskinned CharacterMesh).
          const isExternalBaseMesh =
            slotId === "base_male" ||
            slotId === "base_female" ||
            slotId === "base_male_with_skin_texture" ||
            slotId === "base_female_with_skin_texture";
          if (isExternalBaseMesh) {
            const box = new THREE.Box3().setFromObject(scene);
            const size = new THREE.Vector3();
            box.getSize(size);
            const heightAlongY = size.y;
            const heightAlongZ = size.z;
            if (heightAlongY > heightAlongZ) {
              scene.rotation.set(-Math.PI / 2, 0, Math.PI);
            }
          }

          const skinnedMeshes = findSkinnedMeshes(scene);

          const color = SLOT_COLORS[slotId] ?? "#94a3b8";
          const isBaseBody =
            slotId === "base_body" ||
            slotId === "base_male" ||
            slotId === "base_female";
          const preserveMaterials =
            slotId === "base_male_with_skin_texture" ||
            slotId === "base_female_with_skin_texture";
          scene.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              if (!preserveMaterials) {
                mesh.material = new THREE.MeshStandardMaterial({
                  color,
                  transparent: !isBaseBody,
                  opacity: isBaseBody ? 1 : 0.35,
                  side: THREE.DoubleSide,
                  depthWrite: isBaseBody,
                });
              }
              mesh.frustumCulled = false;
            }
          });

          const slot: LoadedSlot = { scene, skinnedMeshes };
          slotCache.set(slotId, slot);
          setLoadedSlots((prev) => {
            const next = new Map(prev);
            next.set(slotId, slot);
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
  }, [slotIds, equipState, slotMap]);

  const hiddenBodyRegions = useMemo(
    () => computeHiddenBodyRegions(slots, effectiveState),
    [slots, effectiveState],
  );

  useFrame(() => {
    const player = playerRef.current;
    if (!player) return;
    const animBones = player.boneObjMap;
    const restInverses = player.boneRestWorldInverses;
    if (!animBones || animBones.size === 0) return;
    if (!restInverses || restInverses.size === 0) return;

    for (const [slotId, slot] of slotCache) {
      if (!effectiveState[slotId]) continue;

      if (!boundRef.current.has(slotId)) {
        bindSlotSkeleton(slot, animBones, restInverses);
        slot.scene.visible = true;
        boundRef.current.add(slotId);
      }

      // Base body variants: hide regions covered by equipped slots (runs every frame for reactivity)
      const isBaseBodySlot =
        slotId === "base_body" ||
        slotId === "base_male" ||
        slotId === "base_female" ||
        slotId === "base_male_with_skin_texture" ||
        slotId === "base_female_with_skin_texture";
      if (isBaseBodySlot) {
        for (const sm of slot.skinnedMeshes) {
          const region = getBodyRegionFromMeshName(sm.name);
          sm.visible = region === null || !hiddenBodyRegions.has(region);
        }
      }
    }
  });

  return (
    <group ref={groupRef} name="equipment-meshes">
      {slotIds.map((id) => {
        if (!effectiveState[id]) return null;
        const slot = slotCache.get(id) ?? loadedSlots.get(id);
        if (!slot) return null;
        return <primitive key={id} object={slot.scene} />;
      })}
    </group>
  );
}
