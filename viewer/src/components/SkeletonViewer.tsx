import { useEffect, useMemo, useRef } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import type { GlbBoneInfo, BoneCategory, CharacterModel } from "../types";
import { CATEGORY_COLORS } from "../types";

interface SkeletonViewerProps {
  characterModel: CharacterModel | null;
  selectedBone: string | null;
  onSelectBone: (name: string | null) => void;
  meshVisible: boolean;
}

const SELECTED_COLOR = "#ffffff";

const _wp = new THREE.Vector3();
const _pp = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _u = new THREE.Vector3();
const _v = new THREE.Vector3();
const _tmpVec = new THREE.Vector3();
const _base = new THREE.Vector3();
const _color = new THREE.Color();

function JointSphere({
  bone,
  boneInfo,
  isSelected,
  onSelect,
  radius,
}: {
  bone: THREE.Bone;
  boneInfo: GlbBoneInfo;
  isSelected: boolean;
  onSelect: () => void;
  radius: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    bone.getWorldPosition(_wp);
    mesh.position.copy(_wp);
  });

  const color = isSelected
    ? SELECTED_COLOR
    : CATEGORY_COLORS[boneInfo.category as BoneCategory] ?? "#94a3b8";

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    onSelect();
  };

  return (
    <mesh
      ref={meshRef}
      onClick={handleClick}
      onPointerOver={(e) => {
        e.stopPropagation();
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        document.body.style.cursor = "default";
      }}
    >
      <sphereGeometry args={[radius, 12, 12]} />
      <meshStandardMaterial
        color={color}
        emissive={isSelected ? "#4a9eff" : "#000000"}
        emissiveIntensity={isSelected ? 0.8 : 0}
        roughness={0.4}
        metalness={0.1}
      />
    </mesh>
  );
}

function OctahedralBones({
  characterModel,
  selectedBone,
  meshVisible,
  onSelectBone,
}: {
  characterModel: CharacterModel;
  selectedBone: string | null;
  meshVisible: boolean;
  onSelectBone: (name: string | null) => void;
}) {
  const bonesWithParents = useMemo(() => {
    return characterModel.boneList.filter(
      (info) => info.parent && characterModel.boneObjMap.has(info.parent),
    );
  }, [characterModel]);

  // Geometry must be rebuilt whenever the bone list changes — buffer
  // size is baked in at allocation time.  A previous version used
  // useState(() => ...) which only ran on first mount; swapping to a
  // model with fewer bones left ghost triangles for the now-unused
  // tail slots, which read as leftover bones from the previous model.
  const geometry = useMemo(() => {
    const numBones = bonesWithParents.length;
    const vertsPerBone = 6;
    const geom = new THREE.BufferGeometry();
    const positions = new Float32Array(numBones * vertsPerBone * 3);
    const colors = new Float32Array(numBones * vertsPerBone * 3);
    geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(colors, 3));

    const indices: number[] = [];
    for (let i = 0; i < numBones; i++) {
      const b = i * 6;
      indices.push(
        b, b + 2, b + 3,
        b, b + 3, b + 4,
        b, b + 4, b + 5,
        b, b + 5, b + 2,
        b + 1, b + 3, b + 2,
        b + 1, b + 4, b + 3,
        b + 1, b + 5, b + 4,
        b + 1, b + 2, b + 5,
      );
    }
    geom.setIndex(indices);
    return geom;
  }, [bonesWithParents]);

  // Dispose previous geometry when a new one replaces it.
  useEffect(() => () => geometry.dispose(), [geometry]);

  const materialRef = useRef<THREE.MeshLambertMaterial>(null);

  useEffect(() => {
    const mat = materialRef.current;
    if (!mat) return;
    mat.opacity = meshVisible ? 0.2 : 0.8;
    mat.transparent = true;
    mat.depthWrite = !meshVisible;
    mat.needsUpdate = true;
  }, [meshVisible]);

  useFrame(() => {
    const posAttr = geometry.getAttribute("position") as THREE.BufferAttribute;
    const colAttr = geometry.getAttribute("color") as THREE.BufferAttribute;

    for (let i = 0; i < bonesWithParents.length; i++) {
      const info = bonesWithParents[i];
      const bone = characterModel.boneObjMap.get(info.name);
      const parentBone = characterModel.boneObjMap.get(info.parent!);
      if (!bone || !parentBone) continue;

      bone.getWorldPosition(_wp);
      parentBone.getWorldPosition(_pp);

      _dir.copy(_wp).sub(_pp);
      const len = _dir.length();
      const b = i * 6;

      if (len < 0.0001) {
        for (let j = 0; j < 6; j++) posAttr.setXYZ(b + j, _pp.x, _pp.y, _pp.z);
        continue;
      }

      _dir.normalize();

      _tmpVec.set(0, 0, 1);
      if (Math.abs(_dir.dot(_tmpVec)) > 0.9) _tmpVec.set(1, 0, 0);
      _u.crossVectors(_dir, _tmpVec).normalize();
      _v.crossVectors(_dir, _u);

      const w = len * 0.08;
      _base.copy(_pp).addScaledVector(_dir, len * 0.2);

      posAttr.setXYZ(b + 0, _pp.x, _pp.y, _pp.z);
      posAttr.setXYZ(b + 1, _wp.x, _wp.y, _wp.z);
      posAttr.setXYZ(b + 2, _base.x + _u.x * w, _base.y + _u.y * w, _base.z + _u.z * w);
      posAttr.setXYZ(b + 3, _base.x + _v.x * w, _base.y + _v.y * w, _base.z + _v.z * w);
      posAttr.setXYZ(b + 4, _base.x - _u.x * w, _base.y - _u.y * w, _base.z - _u.z * w);
      posAttr.setXYZ(b + 5, _base.x - _v.x * w, _base.y - _v.y * w, _base.z - _v.z * w);

      const isSelected = info.parent === selectedBone;
      const colorHex = isSelected
        ? SELECTED_COLOR
        : CATEGORY_COLORS[info.category as BoneCategory] ?? "#94a3b8";
      _color.set(colorHex);
      for (let j = 0; j < 6; j++) {
        colAttr.setXYZ(b + j, _color.r, _color.g, _color.b);
      }
    }

    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    geometry.computeVertexNormals();
  });

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    if (e.faceIndex == null) return;
    const boneIndex = Math.floor(e.faceIndex / 8);
    const info = bonesWithParents[boneIndex];
    if (info?.parent) {
      e.stopPropagation();
      onSelectBone(info.parent);
    }
  };

  return (
    <mesh
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
      <meshLambertMaterial
        ref={materialRef}
        vertexColors
        transparent
        opacity={meshVisible ? 0.2 : 0.8}
        side={THREE.DoubleSide}
        depthWrite={!meshVisible}
        flatShading
      />
    </mesh>
  );
}

function BoneEdges({
  characterModel,
  selectedBone,
  meshVisible,
}: {
  characterModel: CharacterModel;
  selectedBone: string | null;
  meshVisible: boolean;
}) {
  const bonesWithParents = useMemo(() => {
    return characterModel.boneList.filter(
      (info) => info.parent && characterModel.boneObjMap.has(info.parent),
    );
  }, [characterModel]);

  // See OctahedralBones — geometry size is tied to bone count, must
  // be rebuilt on model swap.
  const geometry = useMemo(() => {
    const numBones = bonesWithParents.length;
    const edgesPerBone = 12;
    const geom = new THREE.BufferGeometry();
    const positions = new Float32Array(numBones * edgesPerBone * 2 * 3);
    const colors = new Float32Array(numBones * edgesPerBone * 2 * 3);
    geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geom.setDrawRange(0, 0);
    return geom;
  }, [bonesWithParents]);

  useEffect(() => () => geometry.dispose(), [geometry]);

  useFrame(() => {
    const posAttr = geometry.getAttribute("position") as THREE.BufferAttribute;
    const colAttr = geometry.getAttribute("color") as THREE.BufferAttribute;
    let vi = 0;

    for (let i = 0; i < bonesWithParents.length; i++) {
      const info = bonesWithParents[i];
      const bone = characterModel.boneObjMap.get(info.name);
      const parentBone = characterModel.boneObjMap.get(info.parent!);
      if (!bone || !parentBone) continue;

      bone.getWorldPosition(_wp);
      parentBone.getWorldPosition(_pp);

      _dir.copy(_wp).sub(_pp);
      const len = _dir.length();
      if (len < 0.0001) continue;
      _dir.normalize();

      _tmpVec.set(0, 0, 1);
      if (Math.abs(_dir.dot(_tmpVec)) > 0.9) _tmpVec.set(1, 0, 0);
      _u.crossVectors(_dir, _tmpVec).normalize();
      _v.crossVectors(_dir, _u);

      const w = len * 0.08;
      _base.copy(_pp).addScaledVector(_dir, len * 0.2);

      const r0x = _base.x + _u.x * w, r0y = _base.y + _u.y * w, r0z = _base.z + _u.z * w;
      const r1x = _base.x + _v.x * w, r1y = _base.y + _v.y * w, r1z = _base.z + _v.z * w;
      const r2x = _base.x - _u.x * w, r2y = _base.y - _u.y * w, r2z = _base.z - _u.z * w;
      const r3x = _base.x - _v.x * w, r3y = _base.y - _v.y * w, r3z = _base.z - _v.z * w;

      const isSelected = info.parent === selectedBone;
      const colorHex = isSelected
        ? SELECTED_COLOR
        : CATEGORY_COLORS[info.category as BoneCategory] ?? "#94a3b8";
      _color.set(colorHex);

      const setEdge = (ax: number, ay: number, az: number, bx: number, by: number, bz: number) => {
        posAttr.setXYZ(vi, ax, ay, az);
        colAttr.setXYZ(vi, _color.r, _color.g, _color.b);
        vi++;
        posAttr.setXYZ(vi, bx, by, bz);
        colAttr.setXYZ(vi, _color.r, _color.g, _color.b);
        vi++;
      };

      // Head to ring (4 edges)
      setEdge(_pp.x, _pp.y, _pp.z, r0x, r0y, r0z);
      setEdge(_pp.x, _pp.y, _pp.z, r1x, r1y, r1z);
      setEdge(_pp.x, _pp.y, _pp.z, r2x, r2y, r2z);
      setEdge(_pp.x, _pp.y, _pp.z, r3x, r3y, r3z);
      // Tail to ring (4 edges)
      setEdge(_wp.x, _wp.y, _wp.z, r0x, r0y, r0z);
      setEdge(_wp.x, _wp.y, _wp.z, r1x, r1y, r1z);
      setEdge(_wp.x, _wp.y, _wp.z, r2x, r2y, r2z);
      setEdge(_wp.x, _wp.y, _wp.z, r3x, r3y, r3z);
      // Ring edges (4)
      setEdge(r0x, r0y, r0z, r1x, r1y, r1z);
      setEdge(r1x, r1y, r1z, r2x, r2y, r2z);
      setEdge(r2x, r2y, r2z, r3x, r3y, r3z);
      setEdge(r3x, r3y, r3z, r0x, r0y, r0z);
    }

    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    geometry.setDrawRange(0, vi);
  });

  return (
    <lineSegments geometry={geometry}>
      <lineBasicMaterial
        vertexColors
        transparent
        opacity={meshVisible ? 0.35 : 1.0}
        depthWrite={false}
      />
    </lineSegments>
  );
}

export default function SkeletonViewer({
  characterModel,
  selectedBone,
  onSelectBone,
  meshVisible,
}: SkeletonViewerProps) {
  if (!characterModel) return null;

  const jointRadius = meshVisible ? 0.008 : 0.014;

  return (
    <group>
      <OctahedralBones
        characterModel={characterModel}
        selectedBone={selectedBone}
        meshVisible={meshVisible}
        onSelectBone={onSelectBone}
      />
      <BoneEdges
        characterModel={characterModel}
        selectedBone={selectedBone}
        meshVisible={meshVisible}
      />
      {characterModel.boneList.map((info) => {
        const bone = characterModel.boneObjMap.get(info.name);
        if (!bone) return null;
        const isSelected = info.name === selectedBone;

        return (
          <JointSphere
            key={info.name}
            bone={bone}
            boneInfo={info}
            isSelected={isSelected}
            onSelect={() => onSelectBone(info.name)}
            radius={jointRadius}
          />
        );
      })}
    </group>
  );
}
