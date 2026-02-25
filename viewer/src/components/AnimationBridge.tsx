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
}

export default function AnimationBridge({
  rigSpec,
  animSpec,
  onStateChange,
  commandRef,
  boneOverrides,
}: AnimationBridgeProps) {
  const player = useAnimationPlayer(rigSpec, boneOverrides);
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
  }, [
    isPlaying,
    currentTime,
    activeAnimId,
    duration,
    speed,
    loop,
    animatedPositions,
  ]);

  return null;
}
