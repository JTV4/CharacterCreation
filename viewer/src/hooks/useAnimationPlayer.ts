import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { RigSpec, BoneSpec } from "../types";
import type { AnimSpec } from "../types/animation";

export interface AnimatedBonePositions {
  head: [number, number, number];
  tail: [number, number, number];
}

export interface AnimationPlayerState {
  animatedPositions: Map<string, AnimatedBonePositions> | null;
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

interface BoneRest {
  bone: BoneSpec;
  localPos: THREE.Vector3;
  localQuat: THREE.Quaternion;
  tailOffset: THREE.Vector3;
}

function computeRestTransforms(
  rigSpec: RigSpec,
): Map<string, BoneRest> {
  const boneMap = new Map<string, BoneSpec>();
  for (const b of rigSpec.bones) boneMap.set(b.name, b);

  const restMap = new Map<string, BoneRest>();
  const worldQuats = new Map<string, THREE.Quaternion>();
  const sorted = topoSort(rigSpec.bones);

  for (const bone of sorted) {
    const head = new THREE.Vector3(...bone.head);
    const tail = new THREE.Vector3(...bone.tail);

    const dir = new THREE.Vector3().subVectors(tail, head);
    const len = dir.length();
    const absoluteQuat = new THREE.Quaternion();
    if (len > 0.0001) {
      absoluteQuat.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
    }

    const tailOffset = new THREE.Vector3(0, len, 0);

    let localPos: THREE.Vector3;
    let localQuat: THREE.Quaternion;

    if (bone.parent) {
      const parentBone = boneMap.get(bone.parent)!;
      const parentHead = new THREE.Vector3(...parentBone.head);
      const parentWorldQuat = worldQuats.get(bone.parent)!;
      const invParentWorldQuat = parentWorldQuat.clone().invert();

      const worldOffset = head.clone().sub(parentHead);
      localPos = worldOffset.clone().applyQuaternion(invParentWorldQuat);
      localQuat = invParentWorldQuat.clone().multiply(absoluteQuat);
    } else {
      localPos = head.clone();
      localQuat = absoluteQuat.clone();
    }

    worldQuats.set(bone.name, absoluteQuat);
    restMap.set(bone.name, { bone, localPos, localQuat, tailOffset });
  }

  return restMap;
}

function buildBoneHierarchy(
  rigSpec: RigSpec,
  restTransforms: Map<string, BoneRest>,
): { rootObj: THREE.Object3D; objMap: Map<string, THREE.Object3D> } {
  const rootObj = new THREE.Object3D();
  rootObj.name = "__anim_root__";

  const objMap = new Map<string, THREE.Object3D>();
  const boneMap = new Map<string, BoneSpec>();
  for (const b of rigSpec.bones) boneMap.set(b.name, b);

  const sorted = topoSort(rigSpec.bones);

  for (const bone of sorted) {
    const rest = restTransforms.get(bone.name)!;
    const obj = new THREE.Object3D();
    obj.name = bone.name;
    obj.position.copy(rest.localPos);
    obj.quaternion.copy(rest.localQuat);

    if (bone.parent) {
      const parentObj = objMap.get(bone.parent);
      if (parentObj) {
        parentObj.add(obj);
      } else {
        rootObj.add(obj);
      }
    } else {
      rootObj.add(obj);
    }

    objMap.set(bone.name, obj);
  }

  rootObj.updateMatrixWorld(true);
  return { rootObj, objMap };
}

function topoSort(bones: BoneSpec[]): BoneSpec[] {
  const map = new Map<string, BoneSpec>();
  for (const b of bones) map.set(b.name, b);
  const sorted: BoneSpec[] = [];
  const visited = new Set<string>();

  function visit(name: string) {
    if (visited.has(name)) return;
    const bone = map.get(name);
    if (!bone) return;
    if (bone.parent) visit(bone.parent);
    visited.add(name);
    sorted.push(bone);
  }

  for (const b of bones) visit(b.name);
  return sorted;
}

function animSpecToClip(
  animSpec: AnimSpec,
  restTransforms: Map<string, BoneRest>,
): THREE.AnimationClip {
  const tracks: THREE.KeyframeTrack[] = [];

  for (const track of animSpec.tracks) {
    const times = track.keyframes.map((kf) => kf.time);
    const rest = restTransforms.get(track.bone);

    if (track.property === "rotation") {
      const restQuat = rest?.localQuat ?? new THREE.Quaternion();
      const values: number[] = [];
      for (const kf of track.keyframes) {
        const delta = new THREE.Quaternion(
          kf.value[0], kf.value[1], kf.value[2], kf.value[3],
        );
        const composed = restQuat.clone().multiply(delta);
        values.push(composed.x, composed.y, composed.z, composed.w);
      }
      const trackName = `${track.bone}.quaternion`;
      const kfTrack = new THREE.QuaternionKeyframeTrack(trackName, times, values);
      if (track.interpolation === "step") {
        kfTrack.setInterpolation(THREE.DiscreteInterpolant as any);
      }
      tracks.push(kfTrack);
    } else if (track.property === "position") {
      const restPos = rest?.localPos ?? new THREE.Vector3();
      const values: number[] = [];
      for (const kf of track.keyframes) {
        values.push(
          restPos.x + kf.value[0],
          restPos.y + kf.value[1],
          restPos.z + kf.value[2],
        );
      }
      const trackName = `${track.bone}.position`;
      const kfTrack = new THREE.VectorKeyframeTrack(trackName, times, values);
      if (track.interpolation === "step") {
        kfTrack.setInterpolation(THREE.DiscreteInterpolant as any);
      }
      tracks.push(kfTrack);
    }
  }

  return new THREE.AnimationClip(
    animSpec.meta.name,
    animSpec.meta.duration,
    tracks,
  );
}

function extractWorldPositions(
  rigSpec: RigSpec,
  objMap: Map<string, THREE.Object3D>,
  restTransforms: Map<string, BoneRest>,
): Map<string, AnimatedBonePositions> {
  const result = new Map<string, AnimatedBonePositions>();

  for (const bone of rigSpec.bones) {
    const obj = objMap.get(bone.name);
    if (!obj) continue;

    const worldPos = new THREE.Vector3();
    obj.getWorldPosition(worldPos);

    const rest = restTransforms.get(bone.name)!;
    const worldTail = rest.tailOffset.clone();
    obj.localToWorld(worldTail);

    result.set(bone.name, {
      head: [worldPos.x, worldPos.y, worldPos.z],
      tail: [worldTail.x, worldTail.y, worldTail.z],
    });
  }

  return result;
}

export function useAnimationPlayer(rigSpec: RigSpec): AnimationPlayerState {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [speed, setSpeedState] = useState(1);
  const [loop, setLoopState] = useState(true);
  const [activeAnimId, setActiveAnimId] = useState<string | null>(null);
  const [animatedPositions, setAnimatedPositions] =
    useState<Map<string, AnimatedBonePositions> | null>(null);

  const animSpecRef = useRef<AnimSpec | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const actionRef = useRef<THREE.AnimationAction | null>(null);

  const restTransforms = useMemo(() => computeRestTransforms(rigSpec), [rigSpec]);

  const { rootObj, objMap } = useMemo(
    () => buildBoneHierarchy(rigSpec, restTransforms),
    [rigSpec, restTransforms],
  );

  const durationRef = useRef(0);

  const setAnimation = useCallback(
    (spec: AnimSpec | null) => {
      if (actionRef.current) {
        actionRef.current.stop();
        actionRef.current = null;
      }
      if (mixerRef.current) {
        mixerRef.current.stopAllAction();
        mixerRef.current.uncacheRoot(rootObj);
        mixerRef.current = null;
      }

      for (const [name, obj] of objMap) {
        const rest = restTransforms.get(name);
        if (rest) {
          obj.position.copy(rest.localPos);
          obj.quaternion.copy(rest.localQuat);
        }
      }

      animSpecRef.current = spec;

      if (!spec || spec.tracks.length === 0) {
        setActiveAnimId(spec?.meta.id ?? null);
        setIsPlaying(false);
        setCurrentTime(0);
        durationRef.current = spec?.meta.duration ?? 0;
        setAnimatedPositions(null);
        return;
      }

      const mixer = new THREE.AnimationMixer(rootObj);
      const clip = animSpecToClip(spec, restTransforms);

      clip.tracks.forEach((track) => {
        const dotIdx = track.name.indexOf(".");
        const boneName = track.name.substring(0, dotIdx);
        const propName = track.name.substring(dotIdx + 1);
        track.name = objMap.has(boneName)
          ? `${objMap.get(boneName)!.uuid}.${propName}`
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
      setActiveAnimId(spec.meta.id);
      setLoopState(spec.meta.loop);
      setCurrentTime(0);
      setIsPlaying(false);
    },
    [rootObj, objMap, restTransforms],
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

    rootObj.updateMatrixWorld(true);
    setAnimatedPositions(
      extractWorldPositions(rigSpec, objMap, restTransforms),
    );
  }, [rigSpec, rootObj, objMap, restTransforms]);

  const seek = useCallback(
    (time: number) => {
      if (!mixerRef.current || !actionRef.current) return;
      const wasPlaying = !actionRef.current.paused && actionRef.current.isRunning();

      actionRef.current.reset();
      actionRef.current.play();
      actionRef.current.paused = true;
      mixerRef.current.setTime(time);

      rootObj.updateMatrixWorld(true);
      setCurrentTime(time);
      setAnimatedPositions(
        extractWorldPositions(rigSpec, objMap, restTransforms),
      );

      if (wasPlaying) {
        actionRef.current.paused = false;
        setIsPlaying(true);
      }
    },
    [rigSpec, rootObj, objMap, restTransforms],
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

  useFrame((_, delta) => {
    if (!mixerRef.current || !isPlaying) return;

    mixerRef.current.update(delta);
    rootObj.updateMatrixWorld(true);

    const time = actionRef.current?.time ?? 0;
    setCurrentTime(time);
    setAnimatedPositions(
      extractWorldPositions(rigSpec, objMap, restTransforms),
    );
  });

  useEffect(() => {
    return () => {
      if (mixerRef.current) {
        mixerRef.current.stopAllAction();
        mixerRef.current.uncacheRoot(rootObj);
      }
    };
  }, [rootObj]);

  return {
    animatedPositions,
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
