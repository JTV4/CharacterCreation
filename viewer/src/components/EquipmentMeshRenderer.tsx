import { useEffect, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { EquipmentState } from "../types/equipment";
import type { AnimationPlayerState } from "../hooks/useAnimationPlayer";
import { SLOT_COLORS } from "../types/equipment";

interface EquipmentMeshRendererProps {
  slotIds: string[];
  equipState: EquipmentState;
  effectiveState: EquipmentState;
  playerRef: React.MutableRefObject<AnimationPlayerState | null>;
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

export default function EquipmentMeshRenderer({
  slotIds,
  equipState,
  effectiveState,
  playerRef,
}: EquipmentMeshRendererProps) {
  const groupRef = useRef<THREE.Group>(null);
  const [loadedSlots, setLoadedSlots] = useState<Map<string, LoadedSlot>>(
    new Map(),
  );
  const loadingRef = useRef<Set<string>>(new Set());
  const initializedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const enabledSlots = slotIds.filter((id) => equipState[id]);
    const toLoad = enabledSlots.filter(
      (id) => !slotCache.has(id) && !loadingRef.current.has(id),
    );

    if (toLoad.length === 0) return;

    let cancelled = false;
    for (const slotId of toLoad) {
      loadingRef.current.add(slotId);
      const url = `/equipment/${slotId}.glb`;
      loader.load(
        url,
        (gltf) => {
          loadingRef.current.delete(slotId);
          if (cancelled) return;

          const scene = gltf.scene;
          const skinnedMeshes = findSkinnedMeshes(scene);

          const color = SLOT_COLORS[slotId] ?? "#94a3b8";
          scene.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              (child as THREE.Mesh).material = new THREE.MeshStandardMaterial({
                color,
                transparent: true,
                opacity: 0.35,
                side: THREE.DoubleSide,
                depthWrite: false,
              });
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
          console.warn(`Failed to load equipment mesh: ${url}`, err);
        },
      );
    }

    return () => {
      cancelled = true;
    };
  }, [slotIds, equipState]);

  useFrame(() => {
    const player = playerRef.current;
    if (!player) return;
    const animBones = player.boneObjMap;
    const restInverses = player.boneRestWorldInverses;
    if (!animBones || animBones.size === 0) return;
    if (!restInverses || restInverses.size === 0) return;

    for (const [slotId, slot] of slotCache) {
      if (!effectiveState[slotId]) continue;
      if (initializedRef.current.has(slotId)) continue;

      // One-time: rebind every skinned mesh to the animation player's bones.
      // This makes the GLTF mesh share the exact same skeleton as the
      // animation player, so Three.js's built-in skeleton.update() produces
      // correct bone matrices automatically every frame.
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
      }

      initializedRef.current.add(slotId);
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
