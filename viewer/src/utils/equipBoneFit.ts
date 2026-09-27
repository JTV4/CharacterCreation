import * as THREE from "three";
import type { BoneRestTransform } from "../types";
import type { EquipBoneOffset, EquipBoneOffsetMap } from "../types/equipment";
import { IDENTITY_BONE_OFFSET, isIdentityBoneOffset, normalizeBoneOffset } from "../types/equipment";

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

const _offsetPos = new THREE.Vector3();
const _offsetQuat = new THREE.Quaternion();
const _offsetEuler = new THREE.Euler();
const _offsetScl = new THREE.Vector3();
const _readEuler = new THREE.Euler();
const _readQuat = new THREE.Quaternion();
const _skinTmp = new THREE.Vector3();
const _skinAcc = new THREE.Vector3();
const _skinWorld = new THREE.Vector3();
const _skinMat = new THREE.Matrix4();

/** `mixamorig:LeftArm` and `mixamorigLeftArm` both become `mixamorigLeftArm`. */
export function canonicalBoneKey(name: string): string {
  if (name.startsWith("mixamorig:")) return `mixamorig${name.slice("mixamorig:".length)}`;
  return name;
}

export function mixamoColonName(key: string): string {
  if (key.startsWith("mixamorig:") || !key.startsWith("mixamorig")) return key;
  return `mixamorig:${key.slice("mixamorig".length)}`;
}

export function findAnimBone(
  animBones: Map<string, THREE.Bone>,
  name: string,
): THREE.Bone | undefined {
  const key = canonicalBoneKey(name);
  return (
    animBones.get(name) ??
    animBones.get(key) ??
    animBones.get(mixamoColonName(key))
  );
}

export function findBoneOffset(
  offsets: EquipBoneOffsetMap | undefined,
  name: string,
): EquipBoneOffset | undefined {
  if (!offsets) return undefined;
  const key = canonicalBoneKey(name);
  return offsets[name] ?? offsets[key] ?? offsets[mixamoColonName(key)];
}

export interface EquipProxyRig {
  root: THREE.Group;
  bones: THREE.Bone[];
  inverses: THREE.Matrix4[];
  byKey: Map<string, THREE.Bone>;
  sourceNames: string[];
}

export interface CreateProxyRigOptions {
  /** Original export skeleton bones, aligned with `sourceNames`. */
  sourceBones?: THREE.Bone[];
  /**
   * Applied as `I_zup = I_yup * Cinv` for bones that are not on the live
   * character (Cape_* chains). Mixamo matches keep the character inverses
   * unless `useEquipmentInverses` is set.
   */
  accessoryInverseCorrection?: THREE.Matrix4;
  /**
   * Use converted export inverses for every joint. Required when garment
   * verts are in export bind space: character rest-world inverses make
   * bindMatrix a no-op at rest and leave clothes un-lifted.
   */
  useEquipmentInverses?: boolean;
}

export function disposeProxyRig(rig: EquipProxyRig | undefined): void {
  if (!rig) return;
  rig.root.removeFromParent();
}

function registerProxyName(byKey: Map<string, THREE.Bone>, name: string, proxy: THREE.Bone): void {
  byKey.set(name, proxy);
  byKey.set(canonicalBoneKey(name), proxy);
}

/**
 * Parallel Mixamo hierarchy parented under the character armature (identity
 * group) so world space matches the body when offsets are zero.
 *
 * Unmatched accessory joints (Cape_*) keep their authored rest locals and
 * parent under the matching live spine — they are never remapped to hips.
 */
export function createProxyRig(
  sourceNames: string[],
  animBones: Map<string, THREE.Bone>,
  charBoneInverseMap: Map<string, THREE.Matrix4>,
  fallbackInverses: THREE.Matrix4[],
  options?: CreateProxyRigOptions,
): EquipProxyRig {
  const root = new THREE.Group();
  root.name = "EquipProxyRig";

  const bones: THREE.Bone[] = [];
  const inverses: THREE.Matrix4[] = [];
  const byKey = new Map<string, THREE.Bone>();
  const resolvedSources: string[] = [];
  const sourceBones = options?.sourceBones;
  const accessoryCinv = options?.accessoryInverseCorrection;

  for (let i = 0; i < sourceNames.length; i++) {
    const raw = sourceNames[i];
    const src = findAnimBone(animBones, raw);
    const sourceBone = sourceBones?.[i];
    const key = canonicalBoneKey(src?.name ?? raw);
    const proxy = new THREE.Bone();
    proxy.name = src?.name ?? sourceBone?.name ?? raw;
    bones.push(proxy);

    let inv: THREE.Matrix4;
    const useExportInv = !!options?.useEquipmentInverses || !src;
    if (useExportInv) {
      if (!src && sourceBone) {
        proxy.position.copy(sourceBone.position);
        proxy.quaternion.copy(sourceBone.quaternion);
        proxy.scale.copy(sourceBone.scale);
      }
      inv = fallbackInverses[i]?.clone() ?? new THREE.Matrix4();
      if (accessoryCinv) inv.multiply(accessoryCinv);
    } else {
      inv = (
        charBoneInverseMap.get(src!.name) ??
        charBoneInverseMap.get(key) ??
        charBoneInverseMap.get(mixamoColonName(key)) ??
        fallbackInverses[i]?.clone() ??
        new THREE.Matrix4()
      ).clone();
    }
    inverses.push(inv);
    registerProxyName(byKey, key, proxy);
    registerProxyName(byKey, proxy.name, proxy);
    registerProxyName(byKey, raw, proxy);
    if (sourceBone) registerProxyName(byKey, sourceBone.name, proxy);
    resolvedSources.push(src?.name ?? raw);
  }

  for (let i = 0; i < bones.length; i++) {
    const src = findAnimBone(animBones, resolvedSources[i]);
    const parentSrc = src?.parent ?? sourceBones?.[i]?.parent ?? null;
    if (parentSrc && (parentSrc as THREE.Bone).isBone) {
      const parentProxy =
        byKey.get(canonicalBoneKey(parentSrc.name)) ?? byKey.get(parentSrc.name);
      if (parentProxy && parentProxy !== bones[i]) {
        parentProxy.add(bones[i]);
        continue;
      }
    }
    root.add(bones[i]);
  }

  const attach = findArmature(animBones);
  if (attach) attach.add(root);

  return { root, bones, inverses, byKey, sourceNames: resolvedSources };
}

function findArmature(animBones: Map<string, THREE.Bone>): THREE.Object3D | null {
  const hips =
    findAnimBone(animBones, "mixamorigHips") ??
    findAnimBone(animBones, "mixamorig:Hips");
  return hips?.parent ?? null;
}

export function applyBoneOffsetToLocal(
  proxy: THREE.Bone,
  src: THREE.Bone,
  offset: EquipBoneOffset,
): void {
  _offsetPos.set(...offset.position);
  _offsetEuler.set(
    offset.rotation[0] * DEG2RAD,
    offset.rotation[1] * DEG2RAD,
    offset.rotation[2] * DEG2RAD,
    "XYZ",
  );
  _offsetQuat.setFromEuler(_offsetEuler);
  _offsetScl.set(...offset.scale);
  proxy.position.copy(src.position).add(_offsetPos);
  proxy.quaternion.copy(src.quaternion).multiply(_offsetQuat);
  proxy.scale.set(
    src.scale.x * _offsetScl.x,
    src.scale.y * _offsetScl.y,
    src.scale.z * _offsetScl.z,
  );
}

export function readBoneOffsetFromLocal(
  proxy: THREE.Bone,
  src: THREE.Bone,
): EquipBoneOffset {
  _readQuat.copy(src.quaternion).invert().multiply(proxy.quaternion);
  _readEuler.setFromQuaternion(_readQuat, "XYZ");
  const sx = src.scale.x !== 0 ? proxy.scale.x / src.scale.x : 1;
  const sy = src.scale.y !== 0 ? proxy.scale.y / src.scale.y : 1;
  const sz = src.scale.z !== 0 ? proxy.scale.z / src.scale.z : 1;
  return {
    position: [
      +(proxy.position.x - src.position.x).toFixed(5),
      +(proxy.position.y - src.position.y).toFixed(5),
      +(proxy.position.z - src.position.z).toFixed(5),
    ],
    rotation: [
      +(_readEuler.x * RAD2DEG).toFixed(2),
      +(_readEuler.y * RAD2DEG).toFixed(2),
      +(_readEuler.z * RAD2DEG).toFixed(2),
    ],
    scale: [+sx.toFixed(4), +sy.toFixed(4), +sz.toFixed(4)],
  };
}

export function syncProxyRig(
  rig: EquipProxyRig,
  animBones: Map<string, THREE.Bone>,
  offsets: EquipBoneOffsetMap | undefined,
  skipBoneKey?: string | null,
): void {
  const attach = findArmature(animBones);
  if (attach && rig.root.parent !== attach) {
    attach.add(rig.root);
  }
  rig.root.position.set(0, 0, 0);
  rig.root.quaternion.identity();
  rig.root.scale.set(1, 1, 1);

  const skip = skipBoneKey ? canonicalBoneKey(skipBoneKey) : null;
  for (let i = 0; i < rig.bones.length; i++) {
    const proxy = rig.bones[i];
    const key = canonicalBoneKey(proxy.name);
    if (skip && key === skip) continue;
    const src = findAnimBone(animBones, rig.sourceNames[i] ?? proxy.name);
    if (!src) continue;
    const raw = findBoneOffset(offsets, key);
    const offset = raw ? normalizeBoneOffset(raw) : IDENTITY_BONE_OFFSET;
    applyBoneOffsetToLocal(proxy, src, offset);
  }
  rig.root.updateMatrixWorld(true);
}

/**
 * Skin current proxy pose into bind-space positions (does not mutate live geo).
 * Call after posing proxies at rest + offsets.
 */
export function computeSkinnedBindPositions(sm: THREE.SkinnedMesh): Float32Array {
  sm.updateMatrixWorld(true);
  sm.skeleton.update();
  const pos = sm.geometry.getAttribute("position") as THREE.BufferAttribute;
  const si = sm.geometry.getAttribute("skinIndex") as THREE.BufferAttribute | undefined;
  const sw = sm.geometry.getAttribute("skinWeight") as THREE.BufferAttribute | undefined;
  const out = new Float32Array(pos.count * 3);
  if (!si || !sw) {
    for (let i = 0; i < pos.count; i++) {
      out[i * 3] = pos.getX(i);
      out[i * 3 + 1] = pos.getY(i);
      out[i * 3 + 2] = pos.getZ(i);
    }
    return out;
  }

  const bind = sm.bindMatrix;
  const bindInv = sm.bindMatrixInverse;
  const bones = sm.skeleton.bones;
  const invs = sm.skeleton.boneInverses;

  for (let i = 0; i < pos.count; i++) {
    _skinTmp.fromBufferAttribute(pos, i);
    _skinTmp.applyMatrix4(bind);
    _skinAcc.set(0, 0, 0);
    for (let k = 0; k < 4; k++) {
      const w = sw.getComponent(i, k);
      if (w === 0) continue;
      const bi = si.getComponent(i, k);
      if (bi < 0 || bi >= bones.length) continue;
      _skinMat.multiplyMatrices(bones[bi].matrixWorld, invs[bi]);
      _skinWorld.copy(_skinTmp).applyMatrix4(_skinMat);
      _skinAcc.addScaledVector(_skinWorld, w);
    }
    _skinAcc.applyMatrix4(bindInv);
    out[i * 3] = _skinAcc.x;
    out[i * 3 + 1] = _skinAcc.y;
    out[i * 3 + 2] = _skinAcc.z;
  }
  return out;
}

/** Pose proxies at character rest + offsets, then return baked bind positions. */
export function bakeOffsetsAtRest(
  sm: THREE.SkinnedMesh,
  rig: EquipProxyRig,
  animBones: Map<string, THREE.Bone>,
  restPose: Map<string, BoneRestTransform>,
  offsets: EquipBoneOffsetMap | undefined,
): Float32Array {
  const saved = rig.bones.map((b) => ({
    p: b.position.clone(),
    q: b.quaternion.clone(),
    s: b.scale.clone(),
  }));

  for (let i = 0; i < rig.bones.length; i++) {
    const proxy = rig.bones[i];
    const src = findAnimBone(animBones, rig.sourceNames[i] ?? proxy.name);
    const rest =
      (src && (restPose.get(src.name) ?? restPose.get(canonicalBoneKey(src.name)))) ??
      restPose.get(proxy.name);
    const raw = findBoneOffset(offsets, proxy.name);
    const offset = raw ? normalizeBoneOffset(raw) : IDENTITY_BONE_OFFSET;
    if (rest) {
      _offsetPos.set(...offset.position);
      _offsetEuler.set(
        offset.rotation[0] * DEG2RAD,
        offset.rotation[1] * DEG2RAD,
        offset.rotation[2] * DEG2RAD,
        "XYZ",
      );
      _offsetQuat.setFromEuler(_offsetEuler);
      proxy.position.copy(rest.position).add(_offsetPos);
      proxy.quaternion.copy(rest.quaternion).multiply(_offsetQuat);
      proxy.scale.set(offset.scale[0], offset.scale[1], offset.scale[2]);
    } else if (src) {
      applyBoneOffsetToLocal(proxy, src, offset);
    }
  }
  rig.root.updateMatrixWorld(true);
  const baked = computeSkinnedBindPositions(sm);

  for (let i = 0; i < rig.bones.length; i++) {
    rig.bones[i].position.copy(saved[i].p);
    rig.bones[i].quaternion.copy(saved[i].q);
    rig.bones[i].scale.copy(saved[i].s);
  }
  rig.root.updateMatrixWorld(true);
  return baked;
}

export function pruneOffsetMap(map: EquipBoneOffsetMap): EquipBoneOffsetMap {
  const next: EquipBoneOffsetMap = {};
  for (const [name, raw] of Object.entries(map)) {
    const offset = normalizeBoneOffset(raw);
    if (!isIdentityBoneOffset(offset)) next[canonicalBoneKey(name)] = offset;
  }
  return next;
}
