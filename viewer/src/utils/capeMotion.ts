import * as THREE from "three";
import { createCapeGravity } from "./capeGravity";

export interface CapeMotion {
  update(deltaSeconds: number, speed: number): void;
  dispose(): void;
}

const CAPE_CLIP_NAMES = ["Cape_Idle", "Cape_Walk", "Cape_Run"] as const;

export function capeSpeedFromAnimId(animId: string | null | undefined): number {
  if (!animId) return 0;
  const name = animId.toLowerCase();
  if (name.includes("run")) return 1;
  if (name.includes("walk")) return 0.5;
  return 0;
}

/**
 * Blend authored traveling waves, then drape the cloth chains under world gravity.
 * Requires the GLB's Cape_* bones to survive binding (not remapped to hips).
 */
export function createCapeMotion(
  root: THREE.Object3D,
  clips: THREE.AnimationClip[],
  worldDown = new THREE.Vector3(0, -1, 0),
): CapeMotion | null {
  const found = CAPE_CLIP_NAMES.map((name) => clips.find((clip) => clip.name === name));
  if (found.some((clip) => !clip)) return null;
  for (const clip of found) {
    if (clip!.tracks.some((track) => !track.name.startsWith("Cape_"))) return null;
  }

  const mixer = new THREE.AnimationMixer(root);
  const actions = found.map((clip) =>
    mixer.clipAction(clip!).setLoop(THREE.LoopRepeat, Infinity).play(),
  );
  const weights = [1, 0, 0];
  actions.forEach((action, i) => action.setEffectiveWeight(weights[i]));
  const gravity = createCapeGravity(root, worldDown);
  let disposed = false;

  return {
    update(deltaSeconds: number, speed: number) {
      if (disposed) return;
      const dt = Math.min(0.1, Math.max(0, Number.isFinite(deltaSeconds) ? deltaSeconds : 0));
      const s = Math.min(1, Math.max(0, Number.isFinite(speed) ? speed : 0));
      const targets = s <= 0.5 ? [1 - s * 2, s * 2, 0] : [0, 2 - s * 2, s * 2 - 1];
      const blend = 1 - Math.exp(-4.5 * dt);
      actions.forEach((action, i) => {
        weights[i] += (targets[i] - weights[i]) * blend;
        action.setEffectiveWeight(weights[i]);
      });
      mixer.update(dt);
      gravity?.update(dt, s);
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      mixer.stopAllAction();
      mixer.uncacheRoot(root);
    },
  };
}
