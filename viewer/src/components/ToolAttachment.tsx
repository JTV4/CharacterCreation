import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TransformControls } from "@react-three/drei";
import type { AnimationPlayerState } from "../hooks/useAnimationPlayer";
import type { ToolDefinition, ToolTransform, GizmoMode } from "../types/tools";
import { fishingMount, createFishingCarryMount } from "../utils/fishingMount";
import { createFishingGrip } from "../utils/fishingGrip";
import ToolEffects from "./ToolEffects";
import VesselLiquid, { VESSEL_LIQUID_BY_TOOL } from "./VesselLiquid";

interface ToolAttachmentProps {
  tool: ToolDefinition;
  boneName: string;
  playerRef: React.MutableRefObject<AnimationPlayerState | null>;
  transform: ToolTransform;
  gizmoMode: GizmoMode;
  onTransformChange: (t: ToolTransform) => void;
  detached?: boolean;
}

const loader = new GLTFLoader();
const modelCache = new Map<string, THREE.Group>();
const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

const _pos = new THREE.Vector3();
const _quat = new THREE.Quaternion();

export default function ToolAttachment({
  tool,
  boneName,
  playerRef,
  transform,
  gizmoMode,
  onTransformChange,
  detached = false,
}: ToolAttachmentProps) {
  const boneGroupRef = useRef<THREE.Group>(null);
  const mountRef = useRef<THREE.Group>(null);
  const offsetRef = useRef<THREE.Group | null>(null);
  const [model, setModel] = useState<THREE.Group | null>(null);
  const [offsetObj, setOffsetObj] = useState<THREE.Object3D | null>(null);
  const isDraggingRef = useRef(false);

  const offsetCallback = useCallback((obj: THREE.Group | null) => {
    offsetRef.current = obj;
    setOffsetObj(obj);
  }, []);

  useEffect(() => {
    const cached = modelCache.get(tool.url);
    if (cached) {
      setModel(cached.clone());
      return;
    }

    let cancelled = false;
    loader.load(
      tool.url,
      (gltf) => {
        if (cancelled) return;
        modelCache.set(tool.url, gltf.scene);
        setModel(gltf.scene.clone());
      },
      undefined,
      (err) => console.warn(`Failed to load tool ${tool.name}:`, err),
    );

    return () => {
      cancelled = true;
    };
  }, [tool.id, tool.url, tool.name]);

  useEffect(() => {
    if (isDraggingRef.current) return;
    const obj = offsetRef.current;
    if (!obj) return;
    obj.position.set(...transform.position);
    obj.rotation.set(
      transform.rotation[0] * DEG2RAD,
      transform.rotation[1] * DEG2RAD,
      transform.rotation[2] * DEG2RAD,
    );
    obj.scale.setScalar(transform.scale);
  }, [transform, offsetObj]);

  const mount = useMemo(() => model && tool.category === "fishing_rods" && !detached ? fishingMount(model) : { position: new THREE.Vector3(), quaternion: new THREE.Quaternion() }, [model, tool.category, detached]);
  const carryMount = useMemo(() => model && tool.category === "fishing_rods" ? createFishingCarryMount(model) : null, [model, tool.category]);
  const carryRight = useMemo(() => new THREE.Vector3(), []);
  const carryLeft = useMemo(() => new THREE.Vector3(), []);
  const syncAttachment = useCallback(() => {
    const group = boneGroupRef.current;
    if (!group) return;

    if (detached) {
      group.position.set(0, 0, 0);
      group.quaternion.identity();
      group.scale.setScalar(1);
      return;
    }

    const player = playerRef.current;
    if (!player) return;

    const bone = player.boneObjMap.get(boneName);
    if (!bone) return;

    bone.getWorldPosition(_pos);
    bone.getWorldQuaternion(_quat);

    group.position.copy(_pos);
    group.quaternion.copy(_quat);
    group.scale.setScalar(1);
    const mounted = mountRef.current;
    if (mounted && carryMount) {
      let current = mount;
      if (!/Fishing$/.test(player.activeAnimId ?? '')) {
        const right = player.boneObjMap.get('mixamorigRightArm');
        const left = player.boneObjMap.get('mixamorigLeftArm');
        if (right && left) {
          right.getWorldPosition(carryRight);left.getWorldPosition(carryLeft);
          carryRight.sub(carryLeft);carryRight.z=0;carryRight.normalize();
        } else carryRight.set(-1,0,0);
        current = carryMount(_quat, carryRight);
      }
      mounted.position.copy(current.position);mounted.quaternion.copy(current.quaternion);
    }
    group.updateMatrixWorld(true);
  }, [boneName, detached, playerRef, carryMount, carryRight, carryLeft, mount]);
  const fingerGrip = useMemo(() => createFishingGrip(), []);
  useEffect(() => () => fingerGrip.restore(), [fingerGrip, tool.id, detached]);
  useFrame(() => fingerGrip.restore(), -3);
  useFrame(() => {
    syncAttachment();
    const player = playerRef.current;
    if (carryMount && model && player && !detached && !/Fishing$/.test(player.activeAnimId ?? '')) {
      fingerGrip.apply(player.boneObjMap, model);
    }
  }, -1);



  const readTransform = useCallback(() => {
    const obj = offsetRef.current;
    if (!obj) return;
    onTransformChange({
      position: [
        +obj.position.x.toFixed(4),
        +obj.position.y.toFixed(4),
        +obj.position.z.toFixed(4),
      ],
      rotation: [
        +(obj.rotation.x * RAD2DEG).toFixed(2),
        +(obj.rotation.y * RAD2DEG).toFixed(2),
        +(obj.rotation.z * RAD2DEG).toFixed(2),
      ],
      scale: +obj.scale.x.toFixed(4),
    });
  }, [onTransformChange]);

  const handleDraggingChanged = useCallback(
    (e: THREE.Event & { value: boolean }) => {
      isDraggingRef.current = e.value;
      if (!e.value) readTransform();
    },
    [readTransform],
  );

  const tcRef = useRef<any>(null);

  useEffect(() => {
    const tc = tcRef.current;
    if (!tc) return;
    tc.addEventListener("dragging-changed", handleDraggingChanged);
    return () => tc.removeEventListener("dragging-changed", handleDraggingChanged);
  }, [offsetObj, handleDraggingChanged]);

  if (!model) return null;

  return (
    <>
      <group ref={boneGroupRef}>
        <group ref={offsetCallback}>
          <group ref={mountRef} position={mount.position} quaternion={mount.quaternion}>
            <primitive object={model} />
          </group>
          {VESSEL_LIQUID_BY_TOOL[tool.id] && (
            <VesselLiquid config={VESSEL_LIQUID_BY_TOOL[tool.id]} playerRef={playerRef} />
          )}
        </group>
      </group>
      <ToolEffects tool={tool} model={model} playerRef={playerRef} detached={detached} syncAttachment={syncAttachment} />
      {offsetObj && (
        <TransformControls
          ref={tcRef}
          object={offsetObj}
          mode={gizmoMode}
          size={0.5}
          onChange={readTransform}
        />
      )}
    </>
  );
}
