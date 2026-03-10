import { useEffect, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  type ModelGender,
  type CharacterModel,
  type GlbBoneInfo,
  type GlbBoneNode,
  type BoneRestTransform,
  type BoneCategory,
  type Side,
} from "../types";

const loader = new GLTFLoader();

const MODEL_URLS: Record<ModelGender, string> = {
  female: "/models/BaseFemale.glb",
  male: "/models/BaseMale.glb",
};

function categorizeBone(name: string): BoneCategory {
  const n = name.toLowerCase();
  if (
    n.includes("spine") ||
    n.includes("hips") ||
    n.includes("neck") ||
    n.includes("head")
  )
    return "spine";
  if (n.includes("thumb") || n.includes("index") || n.includes("middle") || n.includes("ring") || n.includes("pinky"))
    return "finger";
  if (n.includes("shoulder") || n.includes("arm") || n.includes("hand") || n.includes("forearm"))
    return "arm";
  if (n.includes("upleg") || n.includes("leg") || n.includes("foot") || n.includes("toe"))
    return "leg";
  if (n.includes("eye") || n.includes("jaw"))
    return "face";
  return "other";
}

function detectSide(name: string): Side {
  if (name.includes("Left")) return "L";
  if (name.includes("Right")) return "R";
  return "C";
}

function findSkinnedMeshes(root: THREE.Object3D): THREE.SkinnedMesh[] {
  const result: THREE.SkinnedMesh[] = [];
  root.traverse((child) => {
    if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
      result.push(child as THREE.SkinnedMesh);
    }
  });
  return result;
}

function findAllBones(root: THREE.Object3D): THREE.Bone[] {
  const bones: THREE.Bone[] = [];
  root.traverse((child) => {
    if ((child as THREE.Bone).isBone) {
      bones.push(child as THREE.Bone);
    }
  });
  return bones;
}

function buildBoneList(bones: THREE.Bone[]): GlbBoneInfo[] {
  return bones.map((bone) => ({
    name: bone.name,
    parent: bone.parent && (bone.parent as THREE.Bone).isBone ? bone.parent.name : null,
    side: detectSide(bone.name),
    category: categorizeBone(bone.name),
  }));
}

function buildBoneTree(boneList: GlbBoneInfo[]): GlbBoneNode[] {
  const nodeMap = new Map<string, GlbBoneNode>();
  for (const info of boneList) {
    nodeMap.set(info.name, { ...info, children: [] });
  }

  const roots: GlbBoneNode[] = [];
  for (const node of nodeMap.values()) {
    if (node.parent === null) {
      roots.push(node);
    } else {
      const parentNode = nodeMap.get(node.parent);
      if (parentNode) {
        parentNode.children.push(node);
      } else {
        roots.push(node);
      }
    }
  }
  return roots;
}

function extractCharacterModel(gltf: { scene: THREE.Group }): CharacterModel {
  const scene = gltf.scene;

  scene.rotation.x = Math.PI / 2;

  const bones = findAllBones(scene);
  const skinnedMeshes = findSkinnedMeshes(scene);

  const boneObjMap = new Map<string, THREE.Bone>();
  for (const bone of bones) {
    boneObjMap.set(bone.name, bone);
  }

  scene.updateMatrixWorld(true);

  const boneRestPose = new Map<string, BoneRestTransform>();
  for (const bone of bones) {
    boneRestPose.set(bone.name, {
      position: bone.position.clone(),
      quaternion: bone.quaternion.clone(),
    });
  }

  const boneRestWorldInverses = new Map<string, THREE.Matrix4>();
  for (const bone of bones) {
    boneRestWorldInverses.set(bone.name, bone.matrixWorld.clone().invert());
  }

  let skeletonRoot: THREE.Object3D = scene;
  for (const bone of bones) {
    if (!bone.parent || !(bone.parent as THREE.Bone).isBone) {
      skeletonRoot = bone.parent ?? scene;
      break;
    }
  }

  const boneList = buildBoneList(bones);
  const boneTree = buildBoneTree(boneList);

  return {
    scene,
    skinnedMeshes,
    boneObjMap,
    boneRestPose,
    boneRestWorldInverses,
    skeletonRoot,
    boneList,
    boneTree,
  };
}

export function useCharacterModel(gender: ModelGender): {
  model: CharacterModel | null;
  loading: boolean;
  error: string | null;
} {
  const [model, setModel] = useState<CharacterModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setModel(null);

    const url = MODEL_URLS[gender];

    loader.load(
      url,
      (gltf) => {
        if (cancelled) return;
        try {
          const charModel = extractCharacterModel(gltf);
          setModel(charModel);
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
        }
        setLoading(false);
      },
      undefined,
      (err) => {
        if (cancelled) return;
        setError(`Failed to load ${url}: ${err}`);
        setLoading(false);
      },
    );

    return () => {
      cancelled = true;
    };
  }, [gender]);

  return { model, loading, error };
}
