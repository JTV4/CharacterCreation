import * as THREE from "three";

type Particle = {
  position: THREE.Vector3;
  previous: THREE.Vector3;
  goal: THREE.Vector3;
};
type Strand = {
  bones: THREE.Bone[];
  axes: THREE.Vector3[];
  particles: Particle[];
  lengths: number[];
};
type Collider = { a: THREE.Bone; b: THREE.Bone; radius: number };

/** A small cloth lattice driving the existing three cape chains. */
export function createCapeGravity(root: THREE.Object3D, down: THREE.Vector3) {
  const lanes = ["L", "C", "R"];
  const strands: Strand[] = [];
  root.updateWorldMatrix(true, true);
  for (const lane of lanes) {
    const bones = Array.from({ length: 6 }, (_, i) =>
      root.getObjectByName(`Cape_${lane}_${String(i + 1).padStart(2, "0")}`),
    );
    if (bones.some(b => !(b instanceof THREE.Bone))) return null;
    const chain = bones as THREE.Bone[];
    const axes = chain.map((_, i) =>
      (chain[Math.min(i + 1, 5)].position.clone()).normalize(),
    );
    const positions = chain.map(b => b.getWorldPosition(new THREE.Vector3()));
    const end = positions[5].clone().add(positions[5].clone().sub(positions[4]));
    positions.push(end);
    strands.push({
      bones: chain,
      axes,
      particles: positions.map(position => ({ position, previous: position.clone(), goal: position.clone() })),
      lengths: positions.slice(1).map((p, i) => p.distanceTo(positions[i])),
    });
  }

  const find = (suffix: string) =>
    (root.getObjectByName(`mixamorig${suffix}`) ?? root.getObjectByName(`mixamorig:${suffix}`)) as THREE.Bone | undefined;
  const colliders: Collider[] = [];
  const rootScale = root.getWorldScale(new THREE.Vector3());
  const envelopeScale = Math.max(Math.abs(rootScale.x), Math.abs(rootScale.y), Math.abs(rootScale.z));
  const addCollider = (a: string, b: string, radius: number) => {
    const first = find(a), last = find(b);
    if (first && last) colliders.push({ a: first, b: last, radius });
  };
  // Conservative clothing envelopes, including fitted plate and hip skirts.
  addCollider("Spine2", "Spine1", .20);
  addCollider("Spine1", "Hips", .20);
  addCollider("Hips", "Hips", .28);
  for (const side of ["Left", "Right"]) {
    addCollider(`${side}Arm`, `${side}ForeArm`, .105);
    addCollider(`${side}ForeArm`, `${side}Hand`, .08);
    addCollider(`${side}UpLeg`, `${side}Leg`, .235);
    addCollider(`${side}Leg`, `${side}Foot`, .175);
    addCollider(`${side}Foot`, `${side}ToeBase`, .22);
    addCollider(`${side}Hand`, `${side}HandMiddle1`, .115);
  }
  const leftShoulder = find("LeftArm"), rightShoulder = find("RightArm");
  const gravity = down.clone().normalize();
  const up = gravity.clone().negate();
  const back = new THREE.Vector3();
  const across = new THREE.Vector3();
  const delta = new THREE.Vector3(), correction = new THREE.Vector3();
  const a = new THREE.Vector3(), b = new THREE.Vector3(), closest = new THREE.Vector3();
  const segment = new THREE.Vector3(), normal = new THREE.Vector3();
  const velocity = new THREE.Vector3(), acceleration = new THREE.Vector3();
  const invParent = new THREE.Matrix4();
  const currentAxis = new THREE.Vector3(), targetAxis = new THREE.Vector3();
  const rotation = new THREE.Quaternion();
  const capsulePositions = colliders.map(() => ({ a: new THREE.Vector3(), b: new THREE.Vector3() }));
  let accumulator = 0, time = 0, initialized = false;
  const step = 1 / 120;

  const constrain = (p: Particle, q: Particle, length: number, pFixed: boolean, strength = 1) => {
    delta.subVectors(q.position, p.position);
    const distance = delta.length();
    if (distance < 1e-8) return;
    correction.copy(delta).multiplyScalar((distance - length) / distance * strength);
    if (pFixed) q.position.sub(correction);
    else {
      correction.multiplyScalar(.5);
      p.position.add(correction);
      q.position.sub(correction);
    }
  };

  const collide = (position: THREE.Vector3) => {
    for (let i = 0; i < colliders.length; i++) {
      const c = capsulePositions[i];
      segment.subVectors(c.b, c.a);
      const t = THREE.MathUtils.clamp(delta.subVectors(position, c.a).dot(segment) / Math.max(segment.lengthSq(), 1e-10), 0, 1);
      closest.copy(c.a).addScaledVector(segment, t);
      normal.subVectors(position, closest);
      const distance = normal.length(), radius = (colliders[i].radius + .012) * envelopeScale;
      if (distance < radius) {
        if (distance < 1e-6) normal.copy(back);
        else normal.multiplyScalar(1 / distance);
        position.copy(closest).addScaledVector(normal, radius);
      }
    }
    // World-origin floor, leaving room for the cloth thickness and hem trim.
    const height = position.dot(up);
    if (height < .035 * envelopeScale) position.addScaledVector(up, .035 * envelopeScale - height);
  };

  const midpoint = new THREE.Vector3(), midpointBefore = new THREE.Vector3();
  const collideEdge = (p: Particle, q: Particle, pinned: boolean) => {
    midpoint.addVectors(p.position, q.position).multiplyScalar(.5);
    midpointBefore.copy(midpoint);
    collide(midpoint);
    midpoint.sub(midpointBefore);
    if (!pinned) p.position.add(midpoint);
    q.position.addScaledVector(midpoint, pinned ? 2 : 1);
  };

  return {
    update(dt: number, speed: number) {
      root.updateWorldMatrix(true, true);
      for (const strand of strands) {
        for (let i = 0; i < 6; i++) strand.bones[i].getWorldPosition(strand.particles[i].goal);
        // The final virtual particle follows the last bone's local tail.
        strand.bones[5].localToWorld(strand.particles[6].goal.copy(strand.axes[5]).multiplyScalar(strand.bones[5].position.length()));
      }
      if (leftShoulder && rightShoulder) {
        leftShoulder.getWorldPosition(a); rightShoulder.getWorldPosition(b);
        across.subVectors(a, b).projectOnPlane(up).normalize();
        back.crossVectors(up, across).normalize();
      } else back.set(0, 0, 1).cross(up).normalize();
      if (!initialized || strands.some(s => s.particles[0].position.distanceTo(s.particles[0].goal) > .6)) {
        for (const s of strands) for (const p of s.particles) {
          p.position.copy(p.goal); p.previous.copy(p.goal);
        }
        initialized = true;
        accumulator = 0;
      }
      for (let i = 0; i < colliders.length; i++) {
        colliders[i].a.getWorldPosition(capsulePositions[i].a);
        colliders[i].b.getWorldPosition(capsulePositions[i].b);
      }
      accumulator += dt;
      const iterations = Math.min(12, Math.floor((accumulator + 1e-8) / step));
      for (let sub = 0; sub < iterations; sub++) {
        accumulator -= step; time += step;
        for (let lane = 0; lane < strands.length; lane++) {
          const s = strands[lane];
          s.particles[0].position.lerp(s.particles[0].goal, 1 / (iterations - sub));
          for (let i = 1; i < s.particles.length; i++) {
            const p = s.particles[i];
            velocity.subVectors(p.position, p.previous).multiplyScalar(Math.exp(-3.8 * step));
            p.previous.copy(p.position);
            acceleration.copy(gravity).multiplyScalar(9.81 * envelopeScale);
            // Retain the authored waves with light attraction, rather than
            // pinning the fabric to the torso's changing orientation.
            acceleration.addScaledVector(delta.subVectors(p.goal, p.position), 3.0);
            const ripple = Math.sin(time * (1.3 + speed * 1.1) - i * .85 + lane * .7);
            acceleration.addScaledVector(back, (.65 + speed * 4.0 + ripple * (.6 + speed * .6)) * envelopeScale);
            p.position.add(velocity).addScaledVector(acceleration, step * step);
          }
        }
        for (let pass = 0; pass < 8; pass++) {
          for (const s of strands) {
            for (let i = 0; i < 6; i++) constrain(s.particles[i], s.particles[i + 1], s.lengths[i], i === 0);
            for (let i = 0; i < 5; i++) constrain(s.particles[i], s.particles[i + 2], s.lengths[i] + s.lengths[i + 1], i === 0, .12);
          }
          // Crosswise ties stop independent chains from folding through
          // each other while still allowing the edges to flutter.
          for (let lane = 0; lane < 2; lane++) for (let i = 1; i < 7; i++) {
            const p = strands[lane].particles[i], q = strands[lane + 1].particles[i];
            constrain(p, q, p.goal.distanceTo(q.goal), false, .65);
          }
          // Check the spans as well as the joints so sleeves and bent knees
          // cannot pass between the sparse cloth particles.
          for (const s of strands) {
            for (let i = 0; i < 6; i++) collideEdge(s.particles[i], s.particles[i + 1], i === 0);
            for (let i = 1; i < 7; i++) collide(s.particles[i].position);
          }
          for (let lane = 0; lane < 2; lane++) for (let i = 1; i < 7; i++) {
            collideEdge(strands[lane].particles[i], strands[lane + 1].particles[i], false);
          }
        }
      }
      for (const s of strands) for (let i = 0; i < 6; i++) {
        const bone = s.bones[i];
        bone.getWorldPosition(a);
        targetAxis.subVectors(s.particles[i + 1].position, a);
        if (targetAxis.lengthSq() < 1e-10 || !bone.parent) continue;
        invParent.copy(bone.parent.matrixWorld).invert();
        targetAxis.transformDirection(invParent);
        currentAxis.copy(s.axes[i]).applyQuaternion(bone.quaternion).normalize();
        rotation.setFromUnitVectors(currentAxis, targetAxis);
        bone.quaternion.premultiply(rotation).normalize();
        bone.updateMatrix(); bone.updateWorldMatrix(false, true);
      }
    },
  };
}
