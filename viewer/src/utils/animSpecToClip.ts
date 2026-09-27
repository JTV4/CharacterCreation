import * as THREE from "three";
import type { AnimSpec } from "../types/animation";
import type { BoneRestTransform } from "../types";

/** Skill clips key Mixamo hip offsets in centimetres. V3 rest is cm-scale; rework is metres. */
function positionDeltaScale(boneRestPose: Map<string, BoneRestTransform>): number {
  const hips = boneRestPose.get("mixamorigHips") ?? boneRestPose.get("mixamorig:Hips");
  if (!hips) return 1;
  return hips.position.length() > 5 ? 1 : 0.01;
}

export function animSpecToClip(
  animSpec: AnimSpec,
  boneRestPose: Map<string, BoneRestTransform>,
  positionScaleOverride?: number,
): THREE.AnimationClip {
  const tracks: THREE.KeyframeTrack[] = [];
  const absolute = animSpec.meta.absolute === true;
  const posScale = absolute ? 1 : (positionScaleOverride ?? positionDeltaScale(boneRestPose));

  for (const track of animSpec.tracks) {
    const times = track.keyframes.map((kf) => kf.time);
    const rest = boneRestPose.get(track.bone);

    if (track.property === "rotation") {
      const values: number[] = [];
      if (absolute) {
        for (const kf of track.keyframes) {
          values.push(kf.value[0], kf.value[1], kf.value[2], kf.value[3]);
        }
      } else {
        const restQuat = rest?.quaternion ?? new THREE.Quaternion();
        for (const kf of track.keyframes) {
          const delta = new THREE.Quaternion(
            kf.value[0], kf.value[1], kf.value[2], kf.value[3],
          );
          const composed = restQuat.clone().multiply(delta);
          values.push(composed.x, composed.y, composed.z, composed.w);
        }
      }
      const trackName = `${track.bone}.quaternion`;
      const kfTrack = new THREE.QuaternionKeyframeTrack(trackName, times, values);
      if (track.interpolation === "step") {
        kfTrack.setInterpolation(THREE.DiscreteInterpolant as any);
      }
      tracks.push(kfTrack);
    } else if (track.property === "position") {
      const values: number[] = [];
      if (absolute) {
        for (const kf of track.keyframes) {
          values.push(kf.value[0], kf.value[1], kf.value[2]);
        }
      } else {
        const restPos = rest?.position ?? new THREE.Vector3();
        for (const kf of track.keyframes) {
          values.push(
            restPos.x + kf.value[0] * posScale,
            restPos.y + kf.value[1] * posScale,
            restPos.z + kf.value[2] * posScale,
          );
        }
      }
      const trackName = `${track.bone}.position`;
      const kfTrack = new THREE.VectorKeyframeTrack(trackName, times, values);
      if (track.interpolation === "step") {
        kfTrack.setInterpolation(THREE.DiscreteInterpolant as any);
      }
      tracks.push(kfTrack);
    }
  }

  return new THREE.AnimationClip(
    animSpec.meta.name,
    animSpec.meta.duration,
    tracks,
  );
}
