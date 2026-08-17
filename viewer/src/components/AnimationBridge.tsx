import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { CharacterModel, BoneTransformOverride } from "../types";
import type { AnimSpec } from "../types/animation";
import {
  useAnimationPlayer,
  type AnimationPlayerState,
} from "../hooks/useAnimationPlayer";

interface AnimationBridgeProps {
  characterModel: CharacterModel | null;
  animSpec: AnimSpec | null;
  onStateChange: (state: AnimationPlayerState) => void;
  commandRef: React.MutableRefObject<AnimationPlayerState | null>;
  boneOverrides: Map<string, BoneTransformOverride>;
  basePose?: Map<string, BoneTransformOverride>;
  showMesh: boolean;
}

export default function AnimationBridge({
  characterModel,
  animSpec,
  onStateChange,
  commandRef,
  boneOverrides,
  basePose,
  showMesh,
}: AnimationBridgeProps) {
  const player = useAnimationPlayer(characterModel, boneOverrides, basePose);

  useEffect(() => {
    if (!characterModel) return;
    characterModel.scene.traverse((child) => {
      if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
        child.visible = showMesh;
        child.renderOrder = 10;
        const mat = (child as THREE.SkinnedMesh).material as THREE.MeshStandardMaterial;
        if (mat?.isMaterial) {
          mat.stencilWrite = false;
          mat.stencilTest = false;
          mat.needsUpdate = true;
        }
      }
    });
  }, [characterModel, showMesh]);
  const onStateChangeRef = useRef(onStateChange);
  onStateChangeRef.current = onStateChange;

  useEffect(() => {
    commandRef.current = player;
  }, [player, commandRef]);

  useEffect(() => {
    player.setAnimation(animSpec);
  }, [animSpec]);

  const {
    isPlaying,
    currentTime,
    activeAnimId,
    duration,
    speed,
    loop,
  } = player;

  useEffect(() => {
    onStateChangeRef.current(player);
  }, [isPlaying, activeAnimId, duration, speed, loop]);

  const pendingRef = useRef(false);
  const prevOverridesRef = useRef(boneOverrides);
  const prevTimeRef = useRef(currentTime);

  useEffect(() => {
    if (isPlaying) {
      onStateChangeRef.current(player);
      prevTimeRef.current = currentTime;
      return;
    }

    const timeChanged = currentTime !== prevTimeRef.current;
    const overridesChanged = boneOverrides !== prevOverridesRef.current;
    prevTimeRef.current = currentTime;
    prevOverridesRef.current = boneOverrides;

    if (timeChanged || overridesChanged) {
      if (!pendingRef.current) {
        pendingRef.current = true;
        setTimeout(() => {
          pendingRef.current = false;
          onStateChangeRef.current(player);
        }, 32);
      }
    }
  }, [currentTime, isPlaying, boneOverrides]);

  if (!characterModel) return null;

  // Force a fresh primitive node when the underlying scene swaps.
  // R3F binds a `<primitive>` to its initial THREE object and does
  // not transparently replace it when the `object` prop changes,
  // which would leave the previous character's mesh + skeleton in
  // the scene graph alongside the new one.  Keying on the scene's
  // uuid forces a clean unmount/mount on each model load.
  return (
    <primitive key={characterModel.scene.uuid} object={characterModel.scene} />
  );
}
