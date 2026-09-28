import * as T from 'three';

/** The handle crosses the curled fingers; the guides face down below the shaft. */
export function fishingMount(model: T.Object3D) {
  const grip = model.getObjectByName('FishingGrip')?.position.clone() ?? new T.Vector3(-.03, .12, .04);
  const tip = model.getObjectByName('FishingTip')?.position ?? new T.Vector3(.8, 0, .09);
  // Remove the source asset's sideways cant while retaining its downward flex.
  const heading = tip.clone().sub(grip); heading.y = 0; heading.normalize();
  // A diagonal grip lets the forearms reach forward with the elbows down.
  // Keep this basis in sync with the fishing hand frame in build-motion.mjs.
  const diagonal = .55, inward = .9;
  const axis = new T.Vector3(Math.cos(diagonal), Math.sin(diagonal), 0);
  const up = new T.Vector3(Math.sqrt(1-inward*inward)*Math.sin(diagonal), -Math.sqrt(1-inward*inward)*Math.cos(diagonal), inward);
  const quaternion = new T.Quaternion().setFromRotationMatrix(new T.Matrix4().makeBasis(axis, up, new T.Vector3().crossVectors(axis, up)))
    .multiply(new T.Quaternion().setFromUnitVectors(heading, new T.Vector3(1, 0, 0)));
  const position = new T.Vector3(0, .105, .024).sub(grip.applyQuaternion(quaternion));
  return { position, quaternion };
}

/** A separate forward-facing carry frame, pivoting around the palm without changing locomotion. */
export function createFishingCarryMount(model: T.Object3D) {
  const grip = model.getObjectByName('FishingGrip')?.position.clone() ?? new T.Vector3(-.03,.12,.04);
  const heading = (model.getObjectByName('FishingTip')?.position.clone() ?? new T.Vector3(.8,0,.09)).sub(grip);
  // Carry slightly farther up the handle so the palm surrounds the shaft, not its pommel.
  grip.addScaledVector(heading.clone().normalize(),.055);
  heading.y=0; heading.normalize();
  const correction=new T.Quaternion().setFromUnitVectors(heading,new T.Vector3(1,0,0));
  const axis=new T.Vector3(), up=new T.Vector3(), across=new T.Vector3(), forward=new T.Vector3();
  const matrix=new T.Matrix4(), inverse=new T.Quaternion();
  const result={position:new T.Vector3(),quaternion:new T.Quaternion()};
  return (handWorld: T.Quaternion, bodyRight: T.Vector3) => {
    forward.set(0,0,1).cross(bodyRight).normalize();
    // Point forward with a slight upward angle, clear of the ground throughout arm swing.
    axis.set(0,0,.50).addScaledVector(bodyRight,.10).addScaledVector(forward,1).normalize();
    up.copy(forward).negate().addScaledVector(axis,forward.dot(axis)).normalize();
    across.crossVectors(axis,up);
    result.quaternion.setFromRotationMatrix(matrix.makeBasis(axis,up,across));
    inverse.copy(handWorld).invert();result.quaternion.premultiply(inverse).multiply(correction);
    result.position.set(0,.095,.050).sub(up.copy(grip).applyQuaternion(result.quaternion));
    return result;
  };
}
