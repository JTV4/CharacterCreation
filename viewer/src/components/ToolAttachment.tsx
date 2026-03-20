import { useCallback, useEffect, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TransformControls } from "@react-three/drei";
import type { AnimationPlayerState } from "../hooks/useAnimationPlayer";
import type { ToolDefinition, ToolTransform, GizmoMode } from "../types/tools";

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
  const offsetRef = useRef<THREE.Group | null>(null);
  const [model, setModel] = useState<THREE.Group | null>(null);
  const [offsetObj, setOffsetObj] = useState<THREE.Object3D | null>(null);
  const isDraggingRef = useRef(false);

  const offsetCallback = useCallback((obj: THREE.Group | null) => {
    offsetRef.current = obj;
    setOffsetObj(obj);
  }, []);

  useEffect(() => {
    const cached = modelCache.get(tool.id);
    if (cached) {
      setModel(cached.clone());
      return;
    }

    let cancelled = false;
    loader.load(
      tool.url,
      (gltf) => {
        if (cancelled) return;
        modelCache.set(tool.id, gltf.scene);
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

  useFrame(() => {
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
  });

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
          <primitive object={model} />
        </group>
      </group>
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
