import * as THREE from "three";
import { THANKSGIVING_PARTS, thanksgivingCoverageMatrix, thanksgivingCovers } from "./thanksgivingBodyCoverage";
import { SANTA_PARTS, santaCoverageMatrix, santaCovers } from "./santaBodyCoverage";

const HIDE_BONE_COUNT = 96;

/**
 * Mixamo bone tests for one-piece rework bodies.
 * Matches the named region meshes on Female/Male V2.
 */
const REGION_BONE_TEST: Record<string, (boneName: string) => boolean> = {
  base_body_head: (n) => /Head/i.test(n),
  base_body_upper_torso: (n) => /Spine1|Spine2/i.test(n),
  base_body_lower_torso: (n) => /mixamorig:?Hips$/i.test(n) || /mixamorig:?Spine$/i.test(n),
  base_body_arm_upper: (n) => /Shoulder/i.test(n) || /(?:Left|Right)Arm$/i.test(n),
  base_body_arm_lower: (n) => /ForeArm/i.test(n),
  base_body_hands: (n) => /Hand/i.test(n),
  base_body_leg_upper: (n) => /UpLeg/i.test(n),
  base_body_leg_thigh: (n) => /UpLeg/i.test(n),
  // Knee has no exclusive Mixamo joint; pants also hide thigh+shin.
  base_body_leg_knee: () => false,
  base_body_leg_shin: (n) => /(?:Left|Right)Leg$/i.test(n) && !/UpLeg/i.test(n),
  base_body_leg_ankle: (n) => /Foot/i.test(n),
  base_body_foot: (n) => /Foot|Toe/i.test(n),
};

export interface ReworkHideStats {
  meshName: string | null;
  hiddenRegions: string[];
  hiddenClothing: string[];
  hiddenBoneNames: string[];
  hiddenVertCount: number;
  totalVerts: number;
  trianglesKept: number;
  trianglesTotal: number;
}

function boneIsHidden(boneName: string, regions: Set<string>): boolean {
  for (const region of regions) {
    const test = REGION_BONE_TEST[region];
    if (test?.(boneName)) return true;
  }
  return false;
}

function hideAmount(
  si: THREE.BufferAttribute,
  sw: THREE.BufferAttribute,
  i: number,
  hidden: Float32Array,
): number {
  return (
    sw.getX(i) * (hidden[si.getX(i)] ?? 0) +
    sw.getY(i) * (hidden[si.getY(i)] ?? 0) +
    sw.getZ(i) * (hidden[si.getZ(i)] ?? 0) +
    sw.getW(i) * (hidden[si.getW(i)] ?? 0)
  );
}

/**
 * Reversibly hide covered body regions on the one-piece rework mesh
 * by dropping triangles whose skin weights belong to hidden joints.
 * Segmented V2/V3 should keep using mesh.visible instead.
 */
export function applyReworkBodyRegionHide(
  scene: THREE.Object3D,
  hiddenRegions: Set<string>,
  hiddenClothing: Set<string> = new Set(),
): ReworkHideStats | null {
  const matches: THREE.SkinnedMesh[] = [];
  scene.traverse((child) => {
    if (matches.length) return;
    const sm = child as THREE.SkinnedMesh;
    if (sm.isSkinnedMesh && /Base(Female|Male)Rework/i.test(sm.name)) matches.push(sm);
  });
  const mesh = matches[0];
  if (!mesh) return null;

  const geo = mesh.geometry;
  const index = geo.index;
  const si = geo.getAttribute("skinIndex") as THREE.BufferAttribute | undefined;
  const sw = geo.getAttribute("skinWeight") as THREE.BufferAttribute | undefined;
  if (!index || !si || !sw) return null;

  if (!geo.userData._reworkHideOrigIndex) {
    geo.userData._reworkHideOrigIndex = index.array.slice();
  }
  const orig = geo.userData._reworkHideOrigIndex as ArrayLike<number>;
  const trianglesTotal = Math.floor(orig.length / 3);

  // The rework body contains modeled garments in the same primitive as skin.
  // Classify only wholly black garment triangles, using their anatomical joints
  // to exclude facial details. Cache in bind space; animation never changes it.
  if (!geo.userData._reworkBaseClothingFaces) {
    const colors = geo.getAttribute("color");
    const tags = new Uint8Array(trianglesTotal);
    const torsoJoints = mesh.skeleton.bones.map((b) => /Spine(?:1|2)?$|Shoulder$/i.test(b.name));
    const pelvisJoints = mesh.skeleton.bones.map((b) => /Hips$|UpLeg$/i.test(b.name));
    if (colors) {
      for (let f = 0; f < trianglesTotal; f++) {
        const corners = [orig[f * 3], orig[f * 3 + 1], orig[f * 3 + 2]];
        if (!corners.every((v) => colors.getX(v) === 0 && colors.getY(v) === 0 && colors.getZ(v) === 0)) continue;
        let torso = 0, pelvis = 0;
        for (const v of corners) {
          for (let j = 0; j < 4; j++) {
            const bone = si.getComponent(v, j), weight = sw.getComponent(v, j);
            if (torsoJoints[bone]) torso += weight;
            if (pelvisJoints[bone]) pelvis += weight;
          }
        }
        if (Math.max(torso, pelvis) > 1.5) tags[f] = torso > pelvis ? 1 : 2;
      }
    }
    geo.userData._reworkBaseClothingFaces = tags;
  }
  const clothingFaces = geo.userData._reworkBaseClothingFaces as Uint8Array;

  const hidden = new Float32Array(HIDE_BONE_COUNT);
  const hiddenBoneNames: string[] = [];
  mesh.skeleton.bones.forEach((bone, i) => {
    if (i >= HIDE_BONE_COUNT) return;
    if (boneIsHidden(bone.name, hiddenRegions)) {
      hidden[i] = 1;
      hiddenBoneNames.push(bone.name);
    }
  });

  if (hiddenBoneNames.length === 0 && hiddenClothing.size === 0 && !hiddenRegions.has("base_body_fitted_shoulders") && !SANTA_PARTS.some(part => hiddenRegions.has(`base_body_santa_${part}`)) && !THANKSGIVING_PARTS.some(part => hiddenRegions.has(`base_body_thanksgiving_${part}`))) {
    const restored = Array.from(orig);
    geo.setIndex(restored);
    geo.index!.needsUpdate = true;
    return {
      meshName: mesh.name,
      hiddenRegions: [...hiddenRegions],
      hiddenClothing: [],
      hiddenBoneNames,
      hiddenVertCount: 0,
      totalVerts: si.count,
      trianglesKept: trianglesTotal,
      trianglesTotal,
    };
  }

  let hiddenVertCount = 0;
  const hideVert = new Uint8Array(si.count);
  for (let i = 0; i < si.count; i++) {
    if (hideAmount(si, sw, i, hidden) > 0.5) {
      hideVert[i] = 1;
      hiddenVertCount++;
    }
  }

  // Fitted vests cover the shoulder bridge, including triangles primarily
  // weighted to Spine2. Classify in immutable hip bind space so the mask follows
  // the skin through animation and leaves the open central neckline visible.
  const fittedShoulders = hiddenRegions.has("base_body_fitted_shoulders");
  const shoulderCovered = new Uint8Array(si.count);
  if (fittedShoulders && /Female/i.test(mesh.name)) {
    const hip = mesh.skeleton.bones.findIndex((b) => /Hips$/i.test(b.name));
    const position = geo.getAttribute("position");
    if (hip >= 0 && position) {
      const toHip = mesh.skeleton.boneInverses[hip].clone().multiply(mesh.bindMatrix);
      const p = new THREE.Vector3();
      for (let i = 0; i < position.count; i++) {
        p.fromBufferAttribute(position, i).applyMatrix4(toHip);
        // Aligned rework skeleton is metre scale in hip-local coordinates.
        if (Math.abs(p.x) > 0.078 && Math.abs(p.x) < 0.29 && p.y > 0.33 && p.y < 0.48) shoulderCovered[i] = 1;
      }
    }
  }

  // Only drop fully covered triangles at open garment boundaries. A majority
  // test would cut jagged holes into the neckline and the exposed calf.
  const santaMasks = SANTA_PARTS.filter(part => hiddenRegions.has(`base_body_santa_${part}`)).map(part => {
    const mask = new Uint8Array(si.count);
    const toAuthor = santaCoverageMatrix(mesh);
    const pos = geo.getAttribute("position");
    if (toAuthor && pos) {
      const point = new THREE.Vector3();
      for (let i = 0; i < pos.count; i++) {
        point.fromBufferAttribute(pos, i).applyMatrix4(toAuthor);
        if (santaCovers(point, /Female/i.test(mesh.name), part)) mask[i] = 1;
      }
    }
    return mask;
  });

  const thanksgivingMasks = THANKSGIVING_PARTS.filter(part => hiddenRegions.has(`base_body_thanksgiving_${part}`)).map(part => {
    const mask = new Uint8Array(si.count);
    const toAuthor = thanksgivingCoverageMatrix(mesh);
    const pos = geo.getAttribute("position");
    if (toAuthor && pos) {
      const point = new THREE.Vector3();
      for (let i = 0; i < pos.count; i++) {
        point.fromBufferAttribute(pos, i).applyMatrix4(toAuthor);
        if (thanksgivingCovers(point, /Female/i.test(mesh.name), part)) mask[i] = 1;
      }
    }
    return mask;
  });

  const kept: number[] = [];
  for (let t = 0; t < orig.length; t += 3) {
    const garment = clothingFaces[t / 3];
    if ((garment === 1 && hiddenClothing.has("bra")) ||
        (garment === 2 && hiddenClothing.has("underwear"))) continue;
    const a = orig[t];
    const b = orig[t + 1];
    const c = orig[t + 2];
    if (fittedShoulders && shoulderCovered[a] + shoulderCovered[b] + shoulderCovered[c] >= 2) continue;
    if (santaMasks.some(mask => mask[a] && mask[b] && mask[c])) continue;
    if (thanksgivingMasks.some(mask => mask[a] && mask[b] && mask[c])) continue;
    const hiddenCorners = hideVert[a] + hideVert[b] + hideVert[c];
    if (hiddenCorners >= 2) continue;
    kept.push(a, b, c);
  }
  geo.setIndex(kept);
  geo.index!.needsUpdate = true;

  return {
    meshName: mesh.name,
    hiddenRegions: [...hiddenRegions],
    hiddenClothing: [...hiddenClothing],
    hiddenBoneNames,
    hiddenVertCount,
    totalVerts: si.count,
    trianglesKept: Math.floor(kept.length / 3),
    trianglesTotal,
  };
}
