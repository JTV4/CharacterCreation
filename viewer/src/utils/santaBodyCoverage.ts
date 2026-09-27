import * as THREE from "three";

// Reference hip matrices in the authored GLB Y-up frame. Reconstruct bind-space
// garment coverage from inverse bind matrices, independent of the current pose.
const HIP_REFERENCE: Record<string, number[]> = {"Male": [0.9316334128379822, 0, 0, 0, 0, 0.9316332617402172, 2.822348301365463e-07, 0, 0, -2.822348301365463e-07, 0.9316332617402172, 0, 0, 1.0497647103369034, -0.014389506827264033, 1], "Female": [0.9337649384877089, 0, 0, 0, 0, 0.9337648429737138, 2.8288058473984845e-07, 0, 0, -2.8288058473984845e-07, 0.9337648429737138, 0, 0, 1.1056271181354334, -0.01438950682726403, 1]};
export const SANTA_PARTS = ["upperbody", "lowerbody", "gloves", "boots"] as const;
export function santaCoverageMatrix(mesh: THREE.SkinnedMesh): THREE.Matrix4 | null {
  const sex = /Female/i.test(mesh.name) ? "Female" : "Male";
  const hip = mesh.skeleton.bones.findIndex(b => /Hips$/i.test(b.name));
  if (hip < 0) return null;
  return new THREE.Matrix4().fromArray(HIP_REFERENCE[sex])
    .multiply(mesh.skeleton.boneInverses[hip]).multiply(mesh.bindMatrix);
}
export function santaCovers(p: THREE.Vector3, female: boolean, part: string): boolean {
  const x = p.x, y = -p.z, z = p.y; // authored Blender Z-up coordinates
  const hip = female ? 1.10562706 : 1.04976475;
  const neck = (female ? 1.49183536 : 1.48498702) + .017;
  const wrist = female ? .52287912 : .58949119;
  if (part === "upperbody") {
    const a = Math.atan2(x, .02 - y);
    const limit = neck - (female ? .135 : .045) * Math.max(0, Math.cos(a)) ** 3
      + Math.max(0, Math.abs(x) - .09) * .8;
    return z > hip + .015 && z < limit - .018 && Math.abs(x) < wrist + .006;
  }
  if (part === "gloves") return Math.abs(x) > wrist - .022 && z > 1.20;
  if (part === "boots") return z < .430;
  if (part === "lowerbody") return z > (female ? hip - .270 : .12) && z < hip + .035;
  return false;
}
