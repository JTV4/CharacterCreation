import { appearancePosePairs, syncAppearancePose } from '../utils/appearancePose';
import { useEffect, useMemo, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { CharacterModel } from '../types';
import type { AppearanceSex } from './AppearancePanel';

interface Props {
  model: CharacterModel;
  sex: AppearanceSex;
  kind: 'Beard' | 'Mustache';
  style: string;
  color: string;
  visible: boolean;
  onError: (error: string | null) => void;
}

function disposeFeatures(scene: THREE.Group) {
  const materials = new Set<THREE.Material>();
  const skeletons = new Set<THREE.Skeleton>();
  scene.traverse(object => {
    if (object instanceof THREE.Mesh) {
      object.geometry.dispose();
      (Array.isArray(object.material) ? object.material : [object.material]).forEach(m => materials.add(m));
    }
    if (object instanceof THREE.SkinnedMesh) skeletons.add(object.skeleton);
  });
  materials.forEach(m => m.dispose());
  skeletons.forEach(s => s.dispose());
}

export default function FacialHair({ model, sex, kind, style, color, visible, onError }: Props) {
  const [scene, setScene] = useState<THREE.Group | null>(null);

  useEffect(() => {
    let cancelled = false;
    let owned: THREE.Group | null = null;
    setScene(null);
    if (sex !== 'Male' || style === 'none') return;
    new GLTFLoader().loadAsync(`/appearance/v6/Models/FacialHair/Male_${kind}_${style}.glb?v=beards-20260927-v5`)
      .then(gltf => {
        if (cancelled) { disposeFeatures(gltf.scene); return; }
        owned = gltf.scene;
        owned.traverse(object => {
          if (object instanceof THREE.Mesh) { object.visible = true; object.frustumCulled = false; }
        });
        setScene(owned);
      })
      .catch(error => { if (!cancelled) onError(`Facial hair could not load: ${error.message}`); });
    return () => { cancelled = true; if (owned) disposeFeatures(owned); };
  }, [sex, kind, style, model, onError]);

  useEffect(() => {
    scene?.traverse(object => {
      if (!(object instanceof THREE.Mesh)) return;
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
        (material as THREE.MeshStandardMaterial).color.set(color);
      }
    });
  }, [scene, color]);

  const bonePairs = useMemo(() => scene ? appearancePosePairs(scene, model.boneObjMap) : [], [scene, model]);

  useFrame(() => {
    if (scene) syncAppearancePose(scene, model.scene, bonePairs);
  });

  return scene ? <primitive object={scene} visible={visible} dispose={null} /> : null;
}
