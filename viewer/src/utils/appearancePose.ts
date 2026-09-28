import * as THREE from 'three';

/** glTF marks only skin joints as Bones. Unweighted ancestors may be Object3Ds. */
export function appearancePosePairs(scene: THREE.Object3D, bones: Map<string, THREE.Bone>): Array<[THREE.Object3D, THREE.Bone]> {
  const pairs: Array<[THREE.Object3D, THREE.Bone]> = [];
  scene.traverse(object => {
    const source = bones.get(object.name);
    if (source) pairs.push([object, source]);
  });
  return pairs;
}

export function syncAppearancePose(scene: THREE.Object3D, body: THREE.Object3D, pairs: Array<[THREE.Object3D, THREE.Bone]>): void {
  scene.position.copy(body.position);
  scene.quaternion.copy(body.quaternion);
  scene.scale.copy(body.scale);
  for (const [target, source] of pairs) {
    target.position.copy(source.position);
    target.quaternion.copy(source.quaternion);
    target.scale.copy(source.scale);
  }
  scene.updateMatrixWorld(true);
}
