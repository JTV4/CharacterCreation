#!/usr/bin/env node
/**
 * Extract animation data from a GLB file and write it as .anim.json spec.
 *
 * Usage:
 *   node rig/factory/extract_anim_node.mjs \
 *     --glb viewer/public/animations/Walk.glb \
 *     --out animations/specs/walk.anim.json \
 *     --id walk --name Walk --loop --fps 24
 */

import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { dirname, resolve, basename } from "path";
import { parseArgs } from "util";

const { values: args } = parseArgs({
  options: {
    glb: { type: "string" },
    out: { type: "string" },
    id: { type: "string" },
    name: { type: "string" },
    loop: { type: "boolean", default: false },
    fps: { type: "string", default: "24" },
  },
});

if (!args.glb || !args.out || !args.id || !args.name) {
  console.error("Usage: node extract_anim_node.mjs --glb <path> --out <path> --id <id> --name <name> [--loop] [--fps 24]");
  process.exit(1);
}

const fps = parseInt(args.fps, 10);

function parseGLB(buffer) {
  const view = new DataView(buffer.buffer, buffer.byteOffset, buffer.byteLength);
  const magic = view.getUint32(0, true);
  if (magic !== 0x46546C67) throw new Error("Not a GLB file");
  const version = view.getUint32(4, true);
  if (version !== 2) throw new Error(`Unsupported GLB version: ${version}`);

  let offset = 12;
  let json = null;
  let bin = null;

  while (offset < buffer.byteLength) {
    const chunkLength = view.getUint32(offset, true);
    const chunkType = view.getUint32(offset + 4, true);
    const chunkData = buffer.subarray(offset + 8, offset + 8 + chunkLength);

    if (chunkType === 0x4E4F534A) {
      json = JSON.parse(new TextDecoder().decode(chunkData));
    } else if (chunkType === 0x004E4942) {
      bin = chunkData;
    }

    offset += 8 + chunkLength;
  }

  return { json, bin };
}

function readAccessor(gltf, bin, accessorIndex) {
  const accessor = gltf.accessors[accessorIndex];
  const bufferView = gltf.bufferViews[accessor.bufferView];

  const byteOffset = (bufferView.byteOffset ?? 0) + (accessor.byteOffset ?? 0);
  const componentType = accessor.componentType;
  const count = accessor.count;

  const typeSize = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 }[accessor.type] ?? 1;
  const totalComponents = count * typeSize;

  let arr;
  if (componentType === 5126) {
    arr = new Float32Array(bin.buffer, bin.byteOffset + byteOffset, totalComponents);
  } else if (componentType === 5123) {
    arr = new Uint16Array(bin.buffer, bin.byteOffset + byteOffset, totalComponents);
  } else if (componentType === 5125) {
    arr = new Uint32Array(bin.buffer, bin.byteOffset + byteOffset, totalComponents);
  } else {
    throw new Error(`Unsupported component type: ${componentType}`);
  }

  return { data: Array.from(arr), typeSize, count };
}

function getNodeName(gltf, nodeIndex) {
  const node = gltf.nodes[nodeIndex];
  return node?.name ?? `node_${nodeIndex}`;
}

function stripMixamoPrefix(name) {
  return name.replace(/^mixamorig:/, "");
}

const MIXAMO_TO_GENERIC = {
  Hips: "root",
  Spine: "spine_01",
  Spine1: "spine_02",
  Spine2: "spine_03",
  Neck: "neck_01",
  Head: "head",
  HeadTop_End: "head_end",

  LeftShoulder: "clavicle_L",
  LeftArm: "upperarm_L",
  LeftForeArm: "lowerarm_L",
  LeftHand: "hand_L",

  RightShoulder: "clavicle_R",
  RightArm: "upperarm_R",
  RightForeArm: "lowerarm_R",
  RightHand: "hand_R",

  LeftUpLeg: "thigh_L",
  LeftLeg: "shin_L",
  LeftFoot: "foot_L",
  LeftToeBase: "toe_L",
  LeftToe_End: "toe_end_L",

  RightUpLeg: "thigh_R",
  RightLeg: "shin_R",
  RightFoot: "foot_R",
  RightToeBase: "toe_R",
  RightToe_End: "toe_end_R",

  LeftEye: "eye_L",
  RightEye: "eye_R",
  Jaw: "jaw",

  LeftHandThumb1: "thumb_01_L",
  LeftHandThumb2: "thumb_02_L",
  LeftHandThumb3: "thumb_03_L",
  LeftHandThumb4: "thumb_04_L",
  LeftHandIndex1: "index_01_L",
  LeftHandIndex2: "index_02_L",
  LeftHandIndex3: "index_03_L",
  LeftHandIndex4: "index_04_L",
  LeftHandMiddle1: "middle_01_L",
  LeftHandMiddle2: "middle_02_L",
  LeftHandMiddle3: "middle_03_L",
  LeftHandMiddle4: "middle_04_L",
  LeftHandRing1: "ring_01_L",
  LeftHandRing2: "ring_02_L",
  LeftHandRing3: "ring_03_L",
  LeftHandRing4: "ring_04_L",
  LeftHandPinky1: "pinky_01_L",
  LeftHandPinky2: "pinky_02_L",
  LeftHandPinky3: "pinky_03_L",
  LeftHandPinky4: "pinky_04_L",

  RightHandThumb1: "thumb_01_R",
  RightHandThumb2: "thumb_02_R",
  RightHandThumb3: "thumb_03_R",
  RightHandThumb4: "thumb_04_R",
  RightHandIndex1: "index_01_R",
  RightHandIndex2: "index_02_R",
  RightHandIndex3: "index_03_R",
  RightHandIndex4: "index_04_R",
  RightHandMiddle1: "middle_01_R",
  RightHandMiddle2: "middle_02_R",
  RightHandMiddle3: "middle_03_R",
  RightHandMiddle4: "middle_04_R",
  RightHandRing1: "ring_01_R",
  RightHandRing2: "ring_02_R",
  RightHandRing3: "ring_03_R",
  RightHandRing4: "ring_04_R",
  RightHandPinky1: "pinky_01_R",
  RightHandPinky2: "pinky_02_R",
  RightHandPinky3: "pinky_03_R",
  RightHandPinky4: "pinky_04_R",
};

function toGenericBoneName(rawName) {
  const stripped = stripMixamoPrefix(rawName);
  return MIXAMO_TO_GENERIC[stripped] ?? stripped;
}

function quatInverse(q) {
  const [x, y, z, w] = q;
  const dot = x * x + y * y + z * z + w * w;
  if (dot === 0) return [0, 0, 0, 1];
  const inv = 1.0 / dot;
  return [-x * inv, -y * inv, -z * inv, w * inv];
}

function quatMultiply(a, b) {
  const [ax, ay, az, aw] = a;
  const [bx, by, bz, bw] = b;
  return [
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
    aw * bw - ax * bx - ay * by - az * bz,
  ];
}

function getNodeRestPose(gltf, nodeIndex) {
  const node = gltf.nodes[nodeIndex];
  return {
    rotation: node.rotation ?? [0, 0, 0, 1],
    translation: node.translation ?? [0, 0, 0],
  };
}

function extractAnimations(glbPath) {
  const buf = readFileSync(glbPath);
  const { json: gltf, bin } = parseGLB(buf);

  if (!gltf.animations || gltf.animations.length === 0) {
    console.error("No animations found in GLB");
    process.exit(1);
  }

  const anim = gltf.animations[0];
  console.log(`  Extracting animation: "${anim.name || "(unnamed)"}"`);
  console.log(`  Channels: ${anim.channels.length}, Samplers: ${anim.samplers.length}`);

  const nodeNames = (gltf.nodes ?? []).map((n, i) => n.name ?? `node_${i}`);
  console.log(`  Nodes: ${nodeNames.join(", ")}`);

  const tracks = [];
  let maxTime = 0;

  for (const channel of anim.channels) {
    const sampler = anim.samplers[channel.sampler];
    const targetNode = channel.target.node;
    const targetPath = channel.target.path;

    if (targetPath !== "rotation" && targetPath !== "translation") continue;

    const rawName = getNodeName(gltf, targetNode);
    const boneName = toGenericBoneName(rawName);
    const rest = getNodeRestPose(gltf, targetNode);
    const restQuatInv = quatInverse(rest.rotation);

    const input = readAccessor(gltf, bin, sampler.input);
    const output = readAccessor(gltf, bin, sampler.output);

    const interp = sampler.interpolation === "STEP" ? "step" : "linear";

    const keyframes = [];

    for (let i = 0; i < input.count; i++) {
      const time = round(input.data[i], 4);
      if (time > maxTime) maxTime = time;

      let value;
      if (targetPath === "rotation") {
        const absQuat = [
          output.data[i * 4 + 0],
          output.data[i * 4 + 1],
          output.data[i * 4 + 2],
          output.data[i * 4 + 3],
        ];
        const delta = quatMultiply(restQuatInv, absQuat);
        value = [round(delta[0], 6), round(delta[1], 6), round(delta[2], 6), round(delta[3], 6)];
      } else {
        value = [
          round(output.data[i * 3 + 0] - rest.translation[0], 6),
          round(output.data[i * 3 + 1] - rest.translation[1], 6),
          round(output.data[i * 3 + 2] - rest.translation[2], 6),
        ];
      }

      keyframes.push({ time, value });
    }

    const property = targetPath === "translation" ? "position" : "rotation";
    tracks.push({ bone: boneName, property, interpolation: interp, keyframes });
  }

  const duration = round(maxTime, 4);
  console.log(`  Duration: ${duration}s, Tracks: ${tracks.length}`);

  return { tracks, duration };
}

function round(val, decimals) {
  const factor = Math.pow(10, decimals);
  return Math.round(val * factor) / factor;
}

const glbPath = resolve(args.glb);
const outPath = resolve(args.out);

console.log(`\n=== Extract Animation from GLB ===`);
console.log(`  Input:  ${basename(glbPath)}`);
console.log(`  Output: ${basename(outPath)}`);

const { tracks, duration } = extractAnimations(glbPath);

const spec = {
  meta: {
    name: args.name,
    id: args.id,
    duration,
    fps,
    loop: args.loop,
  },
  tracks,
};

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, JSON.stringify(spec, null, 2));

console.log(`\n  Wrote ${tracks.length} tracks to ${outPath}`);
console.log(`=== Done ===\n`);
