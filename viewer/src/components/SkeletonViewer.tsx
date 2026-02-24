import { useMemo, useRef } from "react";
import { ThreeEvent } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import type { BoneSpec, RigSpec, BoneCategory } from "../types";
import { CATEGORY_COLORS } from "../types";

interface SkeletonViewerProps {
  spec: RigSpec;
  selectedBone: string | null;
  onSelectBone: (name: string | null) => void;
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
}: {
  bone: BoneSpec;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  const { geometry, position, quaternion, length } = useMemo(() => {
    const head = new THREE.Vector3(...bone.head);
    const tail = new THREE.Vector3(...bone.tail);
    const dir = new THREE.Vector3().subVectors(tail, head);
    const len = dir.length();

    const geom = createOctahedronGeometry(len);

    const quat = new THREE.Quaternion();
    if (len > 0.0001) {
      const up = new THREE.Vector3(0, 0, 1);
      quat.setFromUnitVectors(up, dir.clone().normalize());
    }

    return { geometry: geom, position: head, quaternion: quat, length: len };
  }, [bone]);

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

        return (
          <group key={bone.name}>
            <BoneShape
              bone={bone}
              isSelected={isSelected}
              onSelect={() => onSelectBone(bone.name)}
            />
            <JointSphere
              position={bone.head}
              color={
                isSelected
                  ? SELECTED_EMISSIVE
                  : CATEGORY_COLORS[bone.category as BoneCategory] ?? "#94a3b8"
              }
            />
            {parent && <ParentLine bone={bone} parentBone={parent} />}
          </group>
        );
      })}
    </group>
  );
}
