import { useEffect, useRef } from "react";
import type { RigSpec, BoneTransformOverride } from "../types";
import type { AnimSpec } from "../types/animation";
import {
  useAnimationPlayer,
  type AnimationPlayerState,
} from "../hooks/useAnimationPlayer";

interface AnimationBridgeProps {
  rigSpec: RigSpec;
  animSpec: AnimSpec | null;
  onStateChange: (state: AnimationPlayerState) => void;
  commandRef: React.MutableRefObject<AnimationPlayerState | null>;
  boneOverrides: Map<string, BoneTransformOverride>;
  basePose?: Map<string, BoneTransformOverride>;
}

export default function AnimationBridge({
  rigSpec,
  animSpec,
  onStateChange,
  commandRef,
  boneOverrides,
  basePose,
}: AnimationBridgeProps) {
  const player = useAnimationPlayer(rigSpec, boneOverrides, basePose);
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
    animatedPositions,
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
  }, [currentTime, animatedPositions, isPlaying, boneOverrides]);

  return <primitive object={player.skeletonRoot} />;
}
