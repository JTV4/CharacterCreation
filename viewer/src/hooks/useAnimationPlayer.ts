import { useCallback, useEffect, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { CharacterModel, BoneTransformOverride, BoneRestTransform } from "../types";
import type { AnimSpec } from "../types/animation";
import { animSpecToClip } from "../utils/animSpecToClip";

export interface AnimationPlayerState {
  boneObjMap: Map<string, THREE.Bone>;
  boneRestPose: Map<string, BoneRestTransform>;
  boneRestWorldInverses: Map<string, THREE.Matrix4>;
  skeletonRoot: THREE.Object3D;
  currentTime: number;
  isPlaying: boolean;
  duration: number;
  speed: number;
  loop: boolean;
  activeAnimId: string | null;
  play: () => void;
  pause: () => void;
  stop: () => void;
  seek: (time: number) => void;
  setSpeed: (speed: number) => void;
  setLoop: (loop: boolean) => void;
  setAnimation: (spec: AnimSpec | null) => void;
}

const DEG2RAD = Math.PI / 180;
const _overrideQuat = new THREE.Quaternion();
const _overrideEuler = new THREE.Euler();

export function useAnimationPlayer(
  characterModel: CharacterModel | null,
  boneOverrides?: Map<string, BoneTransformOverride>,
  basePose?: Map<string, BoneTransformOverride>,
): AnimationPlayerState {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [speed, setSpeedState] = useState(1);
  const [loop, setLoopState] = useState(true);
  const [activeAnimId, setActiveAnimId] = useState<string | null>(null);

  const animSpecRef = useRef<AnimSpec | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const actionRef = useRef<THREE.AnimationAction | null>(null);
  const durationRef = useRef(0);

  const boneObjMap = characterModel?.boneObjMap ?? new Map<string, THREE.Bone>();
  const boneRestPose = characterModel?.boneRestPose ?? new Map<string, BoneRestTransform>();
  const boneRestWorldInverses = characterModel?.boneRestWorldInverses ?? new Map<string, THREE.Matrix4>();
  const skeletonRoot = characterModel?.skeletonRoot ?? new THREE.Object3D();

  const frozenPose = useRef(new Map<string, { pos: THREE.Vector3; quat: THREE.Quaternion; scl: THREE.Vector3 }>());

  useEffect(() => {
    if (!characterModel) return;
    for (const [name, rest] of characterModel.boneRestPose) {
      frozenPose.current.set(name, {
        pos: rest.position.clone(),
        quat: rest.quaternion.clone(),
        scl: new THREE.Vector3(1, 1, 1),
      });
    }
  }, [characterModel]);

  const captureFrozenPose = useCallback(() => {
    for (const [name, obj] of boneObjMap) {
      let entry = frozenPose.current.get(name);
      if (!entry) {
        entry = { pos: new THREE.Vector3(), quat: new THREE.Quaternion(), scl: new THREE.Vector3(1, 1, 1) };
        frozenPose.current.set(name, entry);
      }
      entry.pos.copy(obj.position);
      entry.quat.copy(obj.quaternion);
      entry.scl.copy(obj.scale);
    }
  }, [boneObjMap]);

  const basePoseRef = useRef(basePose);
  basePoseRef.current = basePose;

  const applyBasePose = useCallback(() => {
    const bp = basePoseRef.current;
    if (!bp || bp.size === 0) return;
    const euler = new THREE.Euler();
    const quat = new THREE.Quaternion();
    for (const [name, base] of bp) {
      const obj = boneObjMap.get(name);
      const rest = boneRestPose.get(name);
      if (!obj || !rest) continue;
      obj.position.set(
        rest.position.x + base.position[0],
        rest.position.y + base.position[1],
        rest.position.z + base.position[2],
      );
      euler.set(
        base.rotation[0] * DEG2RAD,
        base.rotation[1] * DEG2RAD,
        base.rotation[2] * DEG2RAD,
      );
      quat.setFromEuler(euler);
      obj.quaternion.copy(rest.quaternion).multiply(quat);
      obj.scale.set(base.scale[0], base.scale[1], base.scale[2]);
    }
  }, [boneObjMap, boneRestPose]);

  const setAnimation = useCallback(
    (spec: AnimSpec | null) => {
      if (!characterModel) return;

      if (actionRef.current) {
        actionRef.current.stop();
        actionRef.current = null;
      }
      if (mixerRef.current) {
        mixerRef.current.stopAllAction();
        mixerRef.current.uncacheRoot(skeletonRoot);
        mixerRef.current = null;
      }

      for (const [name, obj] of boneObjMap) {
        const rest = boneRestPose.get(name);
        if (rest) {
          obj.position.copy(rest.position);
          obj.quaternion.copy(rest.quaternion);
        }
      }
      applyBasePose();
      captureFrozenPose();

      animSpecRef.current = spec;

      if (!spec || spec.tracks.length === 0) {
        setActiveAnimId(spec?.meta.id ?? null);
        setIsPlaying(false);
        setCurrentTime(0);
        durationRef.current = spec?.meta.duration ?? 0;
        return;
      }

      const mixer = new THREE.AnimationMixer(skeletonRoot);
      const clip = animSpecToClip(spec, boneRestPose);

      clip.tracks.forEach((track) => {
        const dotIdx = track.name.indexOf(".");
        const boneName = track.name.substring(0, dotIdx);
        const propName = track.name.substring(dotIdx + 1);
        track.name = boneObjMap.has(boneName)
          ? `${boneObjMap.get(boneName)!.uuid}.${propName}`
          : track.name;
      });

      const action = mixer.clipAction(clip);
      action.setLoop(
        spec.meta.loop ? THREE.LoopRepeat : THREE.LoopOnce,
        spec.meta.loop ? Infinity : 1,
      );
      action.clampWhenFinished = !spec.meta.loop;

      mixerRef.current = mixer;
      actionRef.current = action;
      durationRef.current = spec.meta.duration;

      action.reset();
      action.play();
      action.paused = true;
      mixer.setTime(0);
      skeletonRoot.updateMatrixWorld(true);
      captureFrozenPose();

      setActiveAnimId(spec.meta.id);
      setLoopState(spec.meta.loop);
      setCurrentTime(0);
      setIsPlaying(false);
    },
    [characterModel, skeletonRoot, boneObjMap, boneRestPose, captureFrozenPose, applyBasePose],
  );

  const play = useCallback(() => {
    if (!actionRef.current) return;
    actionRef.current.paused = false;
    actionRef.current.play();
    setIsPlaying(true);
  }, []);

  const pause = useCallback(() => {
    if (!actionRef.current) return;
    actionRef.current.paused = true;
    setIsPlaying(false);
  }, []);

  const stop = useCallback(() => {
    if (!actionRef.current || !mixerRef.current) return;
    actionRef.current.stop();
    actionRef.current.reset();
    mixerRef.current.setTime(0);
    setIsPlaying(false);
    setCurrentTime(0);

    applyBasePose();
    skeletonRoot.updateMatrixWorld(true);
    captureFrozenPose();
  }, [skeletonRoot, captureFrozenPose, applyBasePose]);

  const seek = useCallback(
    (time: number) => {
      if (!mixerRef.current || !actionRef.current) return;
      const wasPlaying = !actionRef.current.paused && actionRef.current.isRunning();

      actionRef.current.reset();
      actionRef.current.play();
      actionRef.current.paused = true;
      mixerRef.current.setTime(time);

      skeletonRoot.updateMatrixWorld(true);
      captureFrozenPose();
      setCurrentTime(time);

      if (wasPlaying) {
        actionRef.current.paused = false;
        setIsPlaying(true);
      }
    },
    [skeletonRoot, captureFrozenPose],
  );

  const setSpeed = useCallback((s: number) => {
    setSpeedState(s);
    if (mixerRef.current) {
      mixerRef.current.timeScale = s;
    }
  }, []);

  const setLoop = useCallback(
    (l: boolean) => {
      setLoopState(l);
      if (actionRef.current) {
        actionRef.current.setLoop(
          l ? THREE.LoopRepeat : THREE.LoopOnce,
          l ? Infinity : 1,
        );
        actionRef.current.clampWhenFinished = !l;
      }
    },
    [],
  );

  const prevOverridesRef = useRef(boneOverrides);
  const overridesDirtyRef = useRef(false);
  if (boneOverrides !== prevOverridesRef.current) {
    prevOverridesRef.current = boneOverrides;
    overridesDirtyRef.current = true;
  }

  useFrame((_, delta) => {
    if (!characterModel) return;

    const playing = !!(mixerRef.current && isPlaying);
    const hasOverrides = !!(boneOverrides && boneOverrides.size > 0);
    const dirty = overridesDirtyRef.current;

    if (!playing && !hasOverrides) return;
    if (!playing && !dirty) return;
    overridesDirtyRef.current = false;

    if (playing) {
      mixerRef.current!.update(delta);
      captureFrozenPose();
    }

    if (hasOverrides) {
      for (const [name, override] of boneOverrides!) {
        const obj = boneObjMap.get(name);
        if (!obj) continue;
        const rest = boneRestPose.get(name);
        if (!rest) continue;

        obj.position.set(
          rest.position.x + override.position[0],
          rest.position.y + override.position[1],
          rest.position.z + override.position[2],
        );
        _overrideEuler.set(
          override.rotation[0] * DEG2RAD,
          override.rotation[1] * DEG2RAD,
          override.rotation[2] * DEG2RAD,
        );
        _overrideQuat.setFromEuler(_overrideEuler);
        obj.quaternion.copy(rest.quaternion).multiply(_overrideQuat);
        obj.scale.set(override.scale[0], override.scale[1], override.scale[2]);
      }
    }

    skeletonRoot.updateMatrixWorld(true);

    if (playing) {
      const time = actionRef.current?.time ?? 0;
      setCurrentTime(time);
    }
  });

  useEffect(() => {
    if (!basePose || basePose.size === 0) return;
    if (isPlaying) return;
    applyBasePose();
    skeletonRoot.updateMatrixWorld(true);
    captureFrozenPose();
  }, [basePose]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => {
      if (mixerRef.current) {
        mixerRef.current.stopAllAction();
        mixerRef.current.uncacheRoot(skeletonRoot);
      }
    };
  }, [skeletonRoot]);

  // When the active character swaps (e.g. user flips between NPCs),
  // rebind the currently-active animation spec onto the new skeleton
  // so the clip keeps playing without the user re-selecting it.  We
  // capture the pre-swap play state and time *before* calling
  // setAnimation (which resets both), then restore them on the new
  // skeleton.  The mixer that was bound to the old skeleton is
  // already stopped + uncached by the [skeletonRoot] cleanup above.
  const prevModelRef = useRef(characterModel);
  useEffect(() => {
    if (prevModelRef.current === characterModel) return;
    prevModelRef.current = characterModel;

    const spec = animSpecRef.current;
    if (!characterModel || !spec) return;

    const wasPlaying = isPlaying;
    const wasTime = currentTime;

    setAnimation(spec);
    if (wasTime > 0) seek(wasTime);
    if (wasPlaying) play();
    // We intentionally trigger only on character/skeleton swap; the
    // captured isPlaying/currentTime are read as the latest React
    // state from the render that produced the swap.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [characterModel]);

  return {
    boneObjMap,
    boneRestPose,
    boneRestWorldInverses,
    skeletonRoot,
    currentTime,
    isPlaying,
    duration: durationRef.current,
    speed,
    loop,
    activeAnimId,
    play,
    pause,
    stop,
    seek,
    setSpeed,
    setLoop,
    setAnimation,
  };
}
