#!/usr/bin/env node
/**
 * Bake a Z>=0 floor constraint into the hammer kneel/stand hip tracks.
 * Samples each clip on BaseFemale.glb (viewer transforms) and lifts hips
 * whenever feet/toes/knees would go below the floor.
 */
import { readFileSync, writeFileSync } from "fs";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const HEIGHT_SCALE = 1.9 / 1.75;
// Mixamo cm on hips local +Z → viewer world −Z drop magnitude.
const WORLD_PER_CM = 0.01 * HEIGHT_SCALE;
const CONTACT = [
  "mixamorigLeftFoot",
  "mixamorigLeftToeBase",
  "mixamorigRightFoot",
  "mixamorigRightToeBase",
  "mixamorigRightLeg",
  "mixamorigLeftLeg",
];
const FILES = [
  "public/animations/FemaleHammerKneel.anim.json",
  "public/animations/FemaleHammering.anim.json",
  "public/animations/FemaleHammerStand.anim.json",
];

const u8 = readFileSync("public/models/BaseFemale.glb");
const ab = u8.buffer.slice(u8.byteOffset, u8.byteOffset + u8.byteLength);
const gltf = await new Promise((res, rej) =>
  new GLTFLoader().parse(ab, "", res, rej),
);
const scene = gltf.scene;
scene.rotation.x = Math.PI / 2;
scene.scale.setScalar(HEIGHT_SCALE);
const bones = new Map();
scene.traverse((o) => {
  if (o.isBone) bones.set(o.name, o);
});
const rest = new Map();
for (const [n, b] of bones) {
  rest.set(n, { pos: b.position.clone(), quat: b.quaternion.clone() });
}

function applySpec(spec, t, hipsZOverride = null) {
  for (const [n, b] of bones) {
    const r = rest.get(n);
    b.position.copy(r.pos);
    b.quaternion.copy(r.quat);
  }
  for (const track of spec.tracks) {
    const b = bones.get(track.bone);
    if (!b) continue;
    const r = rest.get(track.bone);
    const kfs = track.keyframes;
    let i = 0;
    while (i < kfs.length - 1 && kfs[i + 1].time < t - 1e-9) i++;
    const a = kfs[i];
    const c = kfs[Math.min(i + 1, kfs.length - 1)];
    const span = c.time - a.time;
    const u = span <= 1e-9 ? 0 : Math.min(1, Math.max(0, (t - a.time) / span));

    if (track.property === "position") {
      let x = a.value[0] * (1 - u) + c.value[0] * u;
      let y = a.value[1] * (1 - u) + c.value[1] * u;
      let z = a.value[2] * (1 - u) + c.value[2] * u;
      if (track.bone === "mixamorigHips" && hipsZOverride != null) z = hipsZOverride;
      b.position.set(r.pos.x + x, r.pos.y + y, r.pos.z + z);
    } else {
      const qa = new THREE.Quaternion(a.value[0], a.value[1], a.value[2], a.value[3]);
      const qb = new THREE.Quaternion(c.value[0], c.value[1], c.value[2], c.value[3]);
      b.quaternion.copy(r.quat).multiply(qa.clone().slerp(qb, u));
    }
  }
  let root = bones.get("mixamorigHips");
  while (root.parent) root = root.parent;
  root.updateMatrixWorld(true);
}

function minContactZ() {
  let minZ = Infinity;
  const v = new THREE.Vector3();
  for (const n of CONTACT) {
    bones.get(n).getWorldPosition(v);
    if (v.z < minZ) minZ = v.z;
  }
  return minZ;
}

function sampleHipsZ(spec, t) {
  const track = spec.tracks.find(
    (tr) => tr.bone === "mixamorigHips" && tr.property === "position",
  );
  const kfs = track.keyframes;
  let i = 0;
  while (i < kfs.length - 1 && kfs[i + 1].time < t - 1e-9) i++;
  const a = kfs[i];
  const c = kfs[Math.min(i + 1, kfs.length - 1)];
  const span = c.time - a.time;
  const u = span <= 1e-9 ? 0 : Math.min(1, Math.max(0, (t - a.time) / span));
  return a.value[2] * (1 - u) + c.value[2] * u;
}

for (const file of FILES) {
  const spec = JSON.parse(readFileSync(file, "utf8"));
  const dur = spec.meta.duration;
  const samples = 40;
  const corrections = []; // {t, z}

  for (let i = 0; i <= samples; i++) {
    const t = (dur * i) / samples;
    const baseZ = sampleHipsZ(spec, t);
    applySpec(spec, t);
    let minZ = minContactZ();
    let z = baseZ;
    // Iteratively lift (decrease +Z) until contacts clear the floor.
    let guard = 0;
    while (minZ < -0.0005 && guard < 8) {
      z = z + minZ / WORLD_PER_CM; // minZ<0 → smaller hip Z → raise body
      applySpec(spec, t, z);
      minZ = minContactZ();
      guard++;
    }
    corrections.push({ t: +t.toFixed(5), z: +z.toFixed(5) });
  }

  // Replace hips position track with baked keys.
  const hipTrack = spec.tracks.find(
    (tr) => tr.bone === "mixamorigHips" && tr.property === "position",
  );
  hipTrack.keyframes = corrections.map(({ t, z }) => ({
    time: t,
    value: [0, 0, z],
  }));

  // Verify
  let worst = 0;
  for (let i = 0; i <= samples; i++) {
    const t = (dur * i) / samples;
    applySpec(spec, t);
    worst = Math.min(worst, minContactZ());
  }

  writeFileSync(file, JSON.stringify(spec, null, 2) + "\n");
  console.log(
    `${file.split("/").pop()}: baked ${corrections.length} hip keys, worst minZ=${worst.toFixed(5)}`,
  );
}
