#!/usr/bin/env node
/**
 * Bake a position/rotation/scale transform into a GLB file's geometry.
 *
 * Usage:
 *   node bake-tool-transform.mjs <input.glb> <output.glb> \
 *     --position 0.12,0.09,-0.04 \
 *     --rotation 90,0,45 \
 *     --scale 1.5
 *
 * Or pass a JSON file copied from the viewer's "Copy Transform" button:
 *   node bake-tool-transform.mjs <input.glb> <output.glb> --json transform.json
 *
 * The transform values match the viewer's ToolPanel:
 *   position: [x, y, z] in world units
 *   rotation: [x, y, z] in degrees
 *   scale:    uniform scalar
 */

import { readFileSync, writeFileSync } from "fs";
import { argv, exit } from "process";

const DEG2RAD = Math.PI / 180;

// ---- Minimal math helpers (no three.js dependency) ----

function quatFromEulerXYZ(xDeg, yDeg, zDeg) {
  const x = xDeg * DEG2RAD, y = yDeg * DEG2RAD, z = zDeg * DEG2RAD;
  const cx = Math.cos(x / 2), sx = Math.sin(x / 2);
  const cy = Math.cos(y / 2), sy = Math.sin(y / 2);
  const cz = Math.cos(z / 2), sz = Math.sin(z / 2);
  return [
    sx * cy * cz + cx * sy * sz,
    cx * sy * cz - sx * cy * sz,
    cx * cy * sz + sx * sy * cz,
    cx * cy * cz - sx * sy * sz,
  ];
}

function mat4FromTRS(pos, rotDeg, scale) {
  const [qx, qy, qz, qw] = quatFromEulerXYZ(rotDeg[0], rotDeg[1], rotDeg[2]);
  const s = scale;
  const x2 = qx + qx, y2 = qy + qy, z2 = qz + qz;
  const xx = qx * x2, xy = qx * y2, xz = qx * z2;
  const yy = qy * y2, yz = qy * z2, zz = qz * z2;
  const wx = qw * x2, wy = qw * y2, wz = qw * z2;
  return [
    (1 - (yy + zz)) * s, (xy + wz) * s,       (xz - wy) * s,       0,
    (xy - wz) * s,       (1 - (xx + zz)) * s,  (yz + wx) * s,       0,
    (xz + wy) * s,       (yz - wx) * s,        (1 - (xx + yy)) * s, 0,
    pos[0],              pos[1],               pos[2],              1,
  ];
}

function transformPoint(m, x, y, z) {
  return [
    m[0]*x + m[4]*y + m[8]*z  + m[12],
    m[1]*x + m[5]*y + m[9]*z  + m[13],
    m[2]*x + m[6]*y + m[10]*z + m[14],
  ];
}

function transformNormal(m, x, y, z) {
  const nx = m[0]*x + m[4]*y + m[8]*z;
  const ny = m[1]*x + m[5]*y + m[9]*z;
  const nz = m[2]*x + m[6]*y + m[10]*z;
  const len = Math.sqrt(nx*nx + ny*ny + nz*nz) || 1;
  return [nx/len, ny/len, nz/len];
}

// ---- GLB parsing ----

function parseGlb(buf) {
  const magic = buf.readUInt32LE(0);
  if (magic !== 0x46546C67) throw new Error("Not a GLB file");
  const jsonLen = buf.readUInt32LE(12);
  const jsonStr = buf.subarray(20, 20 + jsonLen).toString("utf8");
  const gltf = JSON.parse(jsonStr);
  const binStart = 20 + jsonLen;
  const binChunkLen = buf.readUInt32LE(binStart);
  const binData = buf.subarray(binStart + 8, binStart + 8 + binChunkLen);
  return { gltf, binData: Buffer.from(binData) };
}

function buildGlb(gltf, binData) {
  let jsonStr = JSON.stringify(gltf);
  while (jsonStr.length % 4 !== 0) jsonStr += " ";
  const jsonBuf = Buffer.from(jsonStr, "utf8");
  let padBin = binData;
  if (binData.length % 4 !== 0) {
    padBin = Buffer.alloc(Math.ceil(binData.length / 4) * 4);
    binData.copy(padBin);
  }
  const totalLen = 12 + 8 + jsonBuf.length + 8 + padBin.length;
  const out = Buffer.alloc(totalLen);
  out.writeUInt32LE(0x46546C67, 0);
  out.writeUInt32LE(2, 4);
  out.writeUInt32LE(totalLen, 8);
  out.writeUInt32LE(jsonBuf.length, 12);
  out.writeUInt32LE(0x4E4F534A, 16);
  jsonBuf.copy(out, 20);
  const binOff = 20 + jsonBuf.length;
  out.writeUInt32LE(padBin.length, binOff);
  out.writeUInt32LE(0x004E4942, binOff + 4);
  padBin.copy(out, binOff + 8);
  return out;
}

// ---- Transform application ----

function getAccessorData(gltf, binData, accessorIdx) {
  const acc = gltf.accessors[accessorIdx];
  const bv = gltf.bufferViews[acc.bufferView];
  const offset = (bv.byteOffset || 0) + (acc.byteOffset || 0);
  const compMap = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 };
  const typeCountMap = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };
  const compSize = compMap[acc.componentType] || 4;
  const count = acc.count * (typeCountMap[acc.type] || 1);
  const stride = bv.byteStride || (compSize * (typeCountMap[acc.type] || 1));
  const elemCount = typeCountMap[acc.type] || 1;

  if (acc.componentType !== 5126) return null;

  const values = [];
  for (let i = 0; i < acc.count; i++) {
    const base = offset + i * stride;
    for (let j = 0; j < elemCount; j++) {
      values.push(binData.readFloatLE(base + j * 4));
    }
  }
  return { values, offset, stride, elemCount, count: acc.count, acc, bv };
}

function writeAccessorData(binData, info, values) {
  const { offset, stride, elemCount } = info;
  for (let i = 0; i < info.count; i++) {
    const base = offset + i * stride;
    for (let j = 0; j < elemCount; j++) {
      binData.writeFloatLE(values[i * elemCount + j], base + j * 4);
    }
  }
}

function updateMinMax(acc, values, elemCount) {
  if (!acc.min || !acc.max) return;
  const min = new Array(elemCount).fill(Infinity);
  const max = new Array(elemCount).fill(-Infinity);
  for (let i = 0; i < values.length / elemCount; i++) {
    for (let j = 0; j < elemCount; j++) {
      const v = values[i * elemCount + j];
      if (v < min[j]) min[j] = v;
      if (v > max[j]) max[j] = v;
    }
  }
  acc.min = min;
  acc.max = max;
}

function applyTransformToMesh(gltf, binData, meshIdx, mat) {
  const mesh = gltf.meshes[meshIdx];
  for (const prim of mesh.primitives) {
    if (prim.attributes.POSITION != null) {
      const info = getAccessorData(gltf, binData, prim.attributes.POSITION);
      if (info) {
        const newVals = [];
        for (let i = 0; i < info.count; i++) {
          const [x, y, z] = transformPoint(
            mat,
            info.values[i*3], info.values[i*3+1], info.values[i*3+2]
          );
          newVals.push(x, y, z);
        }
        writeAccessorData(binData, info, newVals);
        updateMinMax(info.acc, newVals, 3);
      }
    }
    if (prim.attributes.NORMAL != null) {
      const info = getAccessorData(gltf, binData, prim.attributes.NORMAL);
      if (info) {
        const newVals = [];
        for (let i = 0; i < info.count; i++) {
          const [nx, ny, nz] = transformNormal(
            mat,
            info.values[i*3], info.values[i*3+1], info.values[i*3+2]
          );
          newVals.push(nx, ny, nz);
        }
        writeAccessorData(binData, info, newVals);
      }
    }
  }
}

// ---- CLI ----

function parseArgs() {
  const args = argv.slice(2);
  if (args.length < 2) {
    console.error("Usage: bake-tool-transform.mjs <input.glb> <output.glb> [options]");
    console.error("  --position x,y,z   Position offset");
    console.error("  --rotation x,y,z   Rotation in degrees (XYZ Euler)");
    console.error("  --scale s           Uniform scale");
    console.error("  --json file.json    Read transform from JSON file");
    exit(1);
  }
  const inputPath = args[0];
  const outputPath = args[1];
  let position = [0, 0, 0];
  let rotation = [0, 0, 0];
  let scale = 1;

  for (let i = 2; i < args.length; i++) {
    if (args[i] === "--json" && args[i + 1]) {
      const json = JSON.parse(readFileSync(args[++i], "utf8"));
      position = json.position || position;
      rotation = json.rotation || rotation;
      scale = json.scale ?? scale;
    } else if (args[i] === "--position" && args[i + 1]) {
      position = args[++i].split(",").map(Number);
    } else if (args[i] === "--rotation" && args[i + 1]) {
      rotation = args[++i].split(",").map(Number);
    } else if (args[i] === "--scale" && args[i + 1]) {
      scale = parseFloat(args[++i]);
    }
  }

  return { inputPath, outputPath, position, rotation, scale };
}

function main() {
  const { inputPath, outputPath, position, rotation, scale } = parseArgs();

  console.log(`Input:    ${inputPath}`);
  console.log(`Output:   ${outputPath}`);
  console.log(`Position: [${position}]`);
  console.log(`Rotation: [${rotation}] deg`);
  console.log(`Scale:    ${scale}`);

  const buf = readFileSync(inputPath);
  const { gltf, binData } = parseGlb(buf);
  const mat = mat4FromTRS(position, rotation, scale);

  const meshCount = gltf.meshes?.length ?? 0;
  for (let i = 0; i < meshCount; i++) {
    applyTransformToMesh(gltf, binData, i, mat);
  }

  // Clear any node transforms on the root so the baked geometry IS the origin
  if (gltf.nodes) {
    for (const node of gltf.nodes) {
      if (node.mesh != null) {
        delete node.translation;
        delete node.rotation;
        delete node.scale;
        delete node.matrix;
      }
    }
  }

  const out = buildGlb(gltf, binData);
  writeFileSync(outputPath, out);
  console.log(`\nWrote ${out.length} bytes to ${outputPath}`);
}

main();
