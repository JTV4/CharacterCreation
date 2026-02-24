import { useMemo, useRef } from "react";
import { ThreeEvent } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import type { BoneSpec, RigSpec, BoneCategory } from "../types";
import { CATEGORY_COLORS } from "../types";
import type { AnimatedBonePositions } from "../hooks/useAnimationPlayer";

interface SkeletonViewerProps {
  spec: RigSpec;
  selectedBone: string | null;
  onSelectBone: (name: string | null) => void;
  animatedPositions?: Map<string, AnimatedBonePositions> | null;
}

const SELECTED_COLOR = "#ffffff";
const SELECTED_EMISSIVE = "#4a9eff";
const JOINT_RADIUS = 0.006;

function createOctahedronGeometry(length: number): THREE.BufferGeometry {
  const w = Math.max(length * 0.1, 0.003);
  const neckRatio = 0.15;
  const neck = length * neckRatio;

  const vertices = new Float32Array([
    0, 0, 0,
    w, 0, neck,
    0, w, neck,
    -w, 0, neck,
    0, -w, neck,
    0, 0, length,
  ]);

  const indices = [
    0, 1, 2,
    0, 2, 3,
    0, 3, 4,
    0, 4, 1,
    5, 2, 1,
    5, 3, 2,
    5, 4, 3,
    5, 1, 4,
  ];

  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.BufferAttribute(vertices, 3));
  geom.setIndex(indices);
  geom.computeVertexNormals();
  return geom;
}

function BoneShape({
  bone,
  isSelected,
  onSelect,
  headOverride,
  tailOverride,
}: {
  bone: BoneSpec;
  isSelected: boolean;
  onSelect: () => void;
  headOverride?: [number, number, number];
  tailOverride?: [number, number, number];
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  const headPos = headOverride ?? bone.head;
  const tailPos = tailOverride ?? bone.tail;

  const { geometry, position, quaternion, length } = useMemo(() => {
    const head = new THREE.Vector3(...headPos);
    const tail = new THREE.Vector3(...tailPos);
    const dir = new THREE.Vector3().subVectors(tail, head);
    const len = dir.length();

    const geom = createOctahedronGeometry(len);

    const quat = new THREE.Quaternion();
    if (len > 0.0001) {
      const up = new THREE.Vector3(0, 0, 1);
      quat.setFromUnitVectors(up, dir.clone().normalize());
    }

    return { geometry: geom, position: head, quaternion: quat, length: len };
  }, [headPos, tailPos]);

  const color = isSelected
    ? SELECTED_COLOR
    : CATEGORY_COLORS[bone.category as BoneCategory] ?? "#94a3b8";

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    onSelect();
  };

  if (length < 0.0001) return null;

  return (
    <group position={position} quaternion={quaternion}>
      <mesh
        ref={meshRef}
        geometry={geometry}
        onClick={handleClick}
        onPointerOver={(e) => {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "default";
        }}
      >
        <meshStandardMaterial
          color={color}
          emissive={isSelected ? SELECTED_EMISSIVE : "#000000"}
          emissiveIntensity={isSelected ? 0.4 : 0}
          roughness={0.6}
          metalness={0.1}
          transparent
          opacity={isSelected ? 1.0 : 0.85}
          side={THREE.DoubleSide}
        />
      </mesh>
    </group>
  );
}

function JointSphere({ position, color }: { position: [number, number, number]; color: string }) {
  return (
    <mesh position={position}>
      <sphereGeometry args={[JOINT_RADIUS, 8, 8]} />
      <meshStandardMaterial color={color} roughness={0.5} />
    </mesh>
  );
}

function ParentLine({
  bone,
  parentBone,
}: {
  bone: BoneSpec;
  parentBone: BoneSpec;
}) {
  const points = useMemo(
    () =>
      [parentBone.tail, bone.head] as [
        [number, number, number],
        [number, number, number],
      ],
    [bone, parentBone],
  );

  return (
    <Line
      points={points}
      color="#3a3f55"
      lineWidth={1}
      transparent
      opacity={0.5}
    />
  );
}

export default function SkeletonViewer({
  spec,
  selectedBone,
  onSelectBone,
  animatedPositions,
}: SkeletonViewerProps) {
  const boneMap = useMemo(() => {
    const map = new Map<string, BoneSpec>();
    for (const b of spec.bones) map.set(b.name, b);
    return map;
  }, [spec]);

  return (
    <group>
      {spec.bones.map((bone) => {
        const parent = bone.parent ? boneMap.get(bone.parent) : undefined;
        const isSelected = bone.name === selectedBone;

        const animPos = animatedPositions?.get(bone.name);
        const headPos = animPos?.head ?? bone.head;
        const tailPos = animPos?.tail ?? bone.tail;

        const parentAnimPos = parent
          ? animatedPositions?.get(parent.name)
          : undefined;
        const parentTail = parentAnimPos?.tail ?? parent?.tail;

        return (
          <group key={bone.name}>
            <BoneShape
              bone={bone}
              isSelected={isSelected}
              onSelect={() => onSelectBone(bone.name)}
              headOverride={animPos ? headPos : undefined}
              tailOverride={animPos ? tailPos : undefined}
            />
            <JointSphere
              position={headPos}
              color={
                isSelected
                  ? SELECTED_EMISSIVE
                  : CATEGORY_COLORS[bone.category as BoneCategory] ?? "#94a3b8"
              }
            />
            {parent && parentTail && (
              <ParentLine
                bone={{ ...bone, head: headPos }}
                parentBone={{ ...parent, tail: parentTail }}
              />
            )}
          </group>
        );
      })}
    </group>
  );
}
