import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import ts from 'typescript';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

const viewer = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const threeURL = pathToFileURL(path.join(viewer, 'node_modules/three/build/three.module.js')).href;
const moduleURL = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
const compile = name => ts.transpileModule(fs.readFileSync(path.join(viewer, 'src/utils', name), 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022},
}).outputText.replaceAll('"three"', JSON.stringify(threeURL));
const gravityURL = moduleURL(compile('capeGravity.ts'));
const {createCapeMotion} = await import(moduleURL(compile('capeMotion.ts').replace('"./capeGravity"', JSON.stringify(gravityURL))));

async function simulate(sex, fps, zUp = false, scale = 1) {
  const bytes = fs.readFileSync(path.join(viewer, `public/equipment/CombatCapes/${sex}/mage_2/Cape.glb`));
  const gltf = await new GLTFLoader().parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
  const scene = gltf.scene;
  scene.scale.setScalar(scale);
  if (zUp) scene.rotation.x = Math.PI / 2;
  scene.updateMatrixWorld(true);
  const spine = scene.getObjectByName('mixamorigSpine2');
  const parent = spine.parent.getWorldQuaternion(new THREE.Quaternion());
  const world = spine.getWorldQuaternion(new THREE.Quaternion());
  world.premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), 65 * Math.PI / 180));
  spine.quaternion.copy(parent.invert().multiply(world));
  scene.updateMatrixWorld(true);
  const up = zUp ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(0, 1, 0);
  const start = scene.getObjectByName('Cape_C_01'), tip = scene.getObjectByName('Cape_C_06');
  const direction = () => start.getWorldPosition(new THREE.Vector3()).sub(tip.getWorldPosition(new THREE.Vector3())).normalize().dot(up);
  const before = direction();
  const attachment = scene.getObjectByName('Cape_Root');
  const fixedPoint = attachment.getWorldPosition(new THREE.Vector3());
  const spineRotation = spine.quaternion.clone();
  const motion = createCapeMotion(scene, gltf.animations, up.clone().negate());
  assert(motion);
  for (let frame = 0; frame < 6 * fps; frame++) motion.update(1 / fps, 0);
  scene.updateMatrixWorld(true);
  const after = direction();
  assert(after > .8 && after > before + .25, `${sex}: bent cape must fall toward gravity (${before} -> ${after})`);
  assert(attachment.getWorldPosition(new THREE.Vector3()).distanceTo(fixedPoint) < 1e-6, 'Shoulder attachment must stay fixed');
  assert(spine.quaternion.angleTo(spineRotation) < 1e-6, 'Cape simulation must not rotate the character');
  const result = tip.getWorldPosition(new THREE.Vector3());
  for (const [dt, speed] of [[NaN, NaN], [-1, -1], [10, 1], [0, .5]]) motion.update(dt, speed);
  scene.traverse(o => {
    assert([...o.position, ...o.quaternion, ...o.scale].every(Number.isFinite), 'All simulated transforms must stay finite');
  });
  motion.dispose();
  const disposedRotation = tip.quaternion.clone();
  motion.update(1, 1);
  assert(tip.quaternion.equals(disposedRotation), 'Disposed simulation must stop');
  return result;
}

for (const sex of ['Male', 'Female']) {
  const baseline = await simulate(sex, 60);
  await simulate(sex, 60, true, 1.9 / 1.75);
  for (const fps of [30, 120]) {
    assert((await simulate(sex, fps)).distanceTo(baseline) < .025, `${sex}: fixed-step gravity must agree across frame rates`);
  }
  const zUp = await simulate(sex, 60, true);
  const converted = baseline.clone().applyAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2);
  assert(zUp.distanceTo(converted) < .002, `${sex}: gravity must work in the viewer's Z-up coordinates`);
}
console.log('PASS: gravity drape on both models; fixed attachments; body isolation; 30/60/120 FPS; Y-up and Z-up; viewer scale; invalid time steps; disposal.');
