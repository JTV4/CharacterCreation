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
  eyebrowStyle: string;
  eyelashStyle: string;
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

export default function FacialFeatures({ model, sex, eyebrowStyle, eyelashStyle, color, visible, onError }: Props) {
  const [scene, setScene] = useState<THREE.Group | null>(null);

  useEffect(() => {
    let cancelled = false;
    let owned: THREE.Group | null = null;
    setScene(null);
    new GLTFLoader().loadAsync(`/appearance/v6/Models/Face/${sex}_FaceOptions.glb?v=face-options-bold-20260927-v2`)
      .then(gltf => {
        if (cancelled) { disposeFeatures(gltf.scene); return; }
        owned = gltf.scene;
        owned.traverse(object => {
          if (object instanceof THREE.Mesh) { object.visible = false; object.frustumCulled = false; }
        });
        setScene(owned);
      })
      .catch(error => { if (!cancelled) onError(`Eyebrows and eyelashes could not load: ${error.message}`); });
    return () => { cancelled = true; if (owned) disposeFeatures(owned); };
  }, [sex, model, onError]);

  useEffect(() => {
    scene?.traverse(object => {
      if (!(object instanceof THREE.Mesh)) return;
      object.visible = object.name === `Brow_${eyebrowStyle}` || object.name === `Lash_${eyelashStyle}`;
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
        if (material.name === 'GS_Brows') (material as THREE.MeshStandardMaterial).color.set(color);
      }
    });
  }, [scene, eyebrowStyle, eyelashStyle, color]);

  const bonePairs = useMemo(() => scene ? appearancePosePairs(scene, model.boneObjMap) : [], [scene, model]);

  useFrame(() => {
    if (scene) syncAppearancePose(scene, model.scene, bonePairs);
  });

  return scene ? <primitive object={scene} visible={visible} dispose={null} /> : null;
}
