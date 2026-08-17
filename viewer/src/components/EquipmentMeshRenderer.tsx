import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { useFrame, ThreeEvent } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { TransformControls } from "@react-three/drei";
import type {
  EquipmentState,
  EquipmentSlot,
  EquipTransform,
  SlotBone,
  SlotTextures,
} from "../types/equipment";
import type { GizmoMode } from "../types/tools";
import type { CharacterModel } from "../types";
import type { AnimationPlayerState } from "../hooks/useAnimationPlayer";
import { SLOT_COLORS, normalizeEquipTransform } from "../types/equipment";

interface EquipmentMeshRendererProps {
  slotIds: string[];
  slots: EquipmentSlot[];
  equipState: EquipmentState;
  effectiveState: EquipmentState;
  playerRef: React.MutableRefObject<AnimationPlayerState | null>;
  characterModel: CharacterModel | null;
  selectedSlot: string | null;
  onSelectSlot: (id: string | null) => void;
  equipTransforms: Record<string, EquipTransform>;
  equipGizmoMode: GizmoMode;
  onEquipTransformChange: (id: string, t: EquipTransform) => void;
  slotTextures?: SlotTextures;
  skinTransferRequest?: { targetSlotId: string; referenceSlotId: string } | null;
  onSkinTransferDone?: (reweightedSlotId?: string) => void;
}

const BODY_SLOT_IDS = new Set([
  "base_body",
  "base_male",
  "base_female",
]);

const FINE_BONE_SLOTS = new Set(["gloves", "ring"]);

const INFLATE_SLOTS = new Set([
  "shell_gloves", "custom_gloves_f", "meshy_crimson_gloves_f", "crimson_wizard_gloves",
]);
const INFLATE_AMOUNT = 0.0;
const FINGERTIP_EXTEND = 0.022;


// Render-order layers control draw priority. Lower numbers draw first (base layer).
// Higher-layer pieces overlap lower-layer pieces at transitions via polygon offset.
//   Layer 1 = Lowerbody (base layer, drawn first)
//   Layer 2 = Upperbody / Boots / Head (overlap lowerbody at waist/shin/neck)
//   Layer 3 = Gloves (overlap upperbody at arm transitions)
//   Layer 4 = Accessories (amulet, ring)
const SLOT_RENDER_ORDER: Record<string, number> = {
  lower_body: 1, shell_lower_body: 1, shell_lower_body_test_v1: 1, custom_lower_body_f: 1, meshy_crimson_lower_body_f: 1, red_lower_body_f: 1, green_dragon_legs_f: 1, green_ranged_lowerbody: 1, leather_ranged_lowerbody: 1, red_ranged_lowerbody: 1, purple_ranged_lowerbody: 1, black_ranged_lowerbody: 1, blue_ranged_lowerbody: 1,
  iron_armor_lowerbody: 1, steel_armor_lowerbody: 1, gold_armor_lowerbody: 1, titanium_armor_lowerbody: 1, tungsten_armor_lowerbody: 1, luminous_armor_lowerbody: 1,
  leather_magic_armor_lowerbody: 1, green_magic_armor_lowerbody: 1, blue_magic_armor_lowerbody: 1, red_magic_armor_lowerbody: 1, black_magic_armor_lowerbody: 1, purple_magic_armor_lowerbody: 1,
  default_armor_lowerbody: 1,
  crimson_wizard_robe_bottom: 1,
  upper_body: 2, shell_upper_body: 2, shell_upper_body_test_v1: 2, custom_upper_body_f: 2, custom_upper_body_f_textured: 2, custom_upper_body_f_crimson_meshy: 2, meshy_crimson_upperbody_f: 2, green_dragon_top_f: 2, green_ranged_upperbody: 2, leather_ranged_upperbody: 2, red_ranged_upperbody: 2, purple_ranged_upperbody: 2, black_ranged_upperbody: 2, blue_ranged_upperbody: 2,
  iron_armor_upperbody: 2, steel_armor_upperbody: 2, gold_armor_upperbody: 2, titanium_armor_upperbody: 2, tungsten_armor_upperbody: 2, luminous_armor_upperbody: 2,
  leather_magic_armor_upperbody: 2, green_magic_armor_upperbody: 2, blue_magic_armor_upperbody: 2, red_magic_armor_upperbody: 2, black_magic_armor_upperbody: 2, purple_magic_armor_upperbody: 2,
  default_armor_upperbody: 2,
  boots: 2, shell_boots: 2, shell_boots_test_v1: 2, custom_boots_f: 2, meshy_crimson_boots_f: 2, green_dragon_boots_f: 2, green_ranged_boots: 2, leather_ranged_boots: 2, red_ranged_boots: 2, purple_ranged_boots: 2, black_ranged_boots: 2, blue_ranged_boots: 2,
  iron_armor_boots: 2, steel_armor_boots: 2, gold_armor_boots: 2, titanium_armor_boots: 2, tungsten_armor_boots: 2, luminous_armor_boots: 2,
  leather_magic_armor_boots: 2, green_magic_armor_boots: 2, blue_magic_armor_boots: 2, red_magic_armor_boots: 2, black_magic_armor_boots: 2, purple_magic_armor_boots: 2,
  default_armor_boots: 2,
  crimson_wizard_robe: 2, crimson_upperbody_f: 2, crimson_upperbody_meshy_v2: 2, crimson_wizard_boots: 2,
  head: 2, shell_head: 2, shell_head_test_v1: 2, custom_head_f: 2, meshy_crimson_head_f: 2, meshy_crimson_wizard_hat_f: 2, crimson_wizard_hat: 2, green_dragon_wizard_hat_f: 2, green_ranged_hat: 2, leather_ranged_hat: 2, red_ranged_hat: 2, purple_ranged_hat: 2, black_ranged_hat: 2, blue_ranged_hat: 2,
  leather_magic_armor_hat: 2, green_magic_armor_hat: 2, blue_magic_armor_hat: 2, red_magic_armor_hat: 2, black_magic_armor_hat: 2, purple_magic_armor_hat: 2,
  boghop: 2, inventioners: 2, shardspire: 2, wildplume: 2, wayfinder: 2,
  iron_armor_head: 2, steel_armor_head: 2, gold_armor_head: 2, titanium_armor_head: 2, tungsten_armor_head: 2, luminous_armor_head: 2,
  gloves: 3, shell_gloves: 3, shell_gloves_test_v1: 3, custom_gloves_f: 3, meshy_crimson_gloves_f: 3, crimson_wizard_gloves: 3, green_dragon_gloves_f: 3, green_ranged_gloves: 3, red_ranged_gloves: 3, purple_ranged_gloves: 3, black_ranged_gloves: 3, blue_ranged_gloves: 3, leather_ranged_gloves: 3,
  iron_armor_gloves: 3, steel_armor_gloves: 3, gold_armor_gloves: 3, titanium_armor_gloves: 3, tungsten_armor_gloves: 3, luminous_armor_gloves: 3,
  leather_magic_armor_gloves: 3, green_magic_armor_gloves: 3, blue_magic_armor_gloves: 3, red_magic_armor_gloves: 3, black_magic_armor_gloves: 3, purple_magic_armor_gloves: 3,
  amulet: 4, ring: 4,
  // Removable face overlays — draw above the head/face
  brown_eyes: 4, blue_eyes: 4, green_eyes: 4, amber_eyes: 4, violet_eyes: 4,
  dark_eyebrows: 4, soft_eyebrows: 4, arched_eyebrows: 4,
  natural_eyelashes: 4, long_eyelashes: 4,
  button_nose: 4, straight_nose: 4, soft_nose: 4,
  neutral_mouth: 4, soft_smile_mouth: 4, full_lips_mouth: 4,
  round_ears: 4, pointed_ears: 4,
};

// Polygon offset per render-order layer. More negative = pushed closer to camera = wins at overlap.
const LAYER_POLYGON_OFFSET: Record<number, number> = {
  1: -1,   // lowerbody (base)
  2: -2,   // upperbody / boots / head
  3: -3,   // gloves
  4: -1,   // accessories
};

// All equipment writes stencil=1 so the base body mesh skips those pixels.
const STENCIL_WRITE_SLOTS = new Set([
  "lower_body", "shell_lower_body", "shell_lower_body_test_v1", "custom_lower_body_f", "meshy_crimson_lower_body_f", "red_lower_body_f", "green_dragon_legs_f", "green_ranged_lowerbody", "leather_ranged_lowerbody", "red_ranged_lowerbody", "purple_ranged_lowerbody", "black_ranged_lowerbody", "blue_ranged_lowerbody",
  "iron_armor_lowerbody", "steel_armor_lowerbody", "gold_armor_lowerbody", "titanium_armor_lowerbody", "tungsten_armor_lowerbody", "luminous_armor_lowerbody",
  "leather_magic_armor_lowerbody", "green_magic_armor_lowerbody", "blue_magic_armor_lowerbody", "red_magic_armor_lowerbody", "black_magic_armor_lowerbody", "purple_magic_armor_lowerbody",
  "default_armor_lowerbody",
  "crimson_wizard_robe_bottom",
  "upper_body", "shell_upper_body", "shell_upper_body_test_v1", "custom_upper_body_f", "custom_upper_body_f_textured", "custom_upper_body_f_crimson_meshy", "meshy_crimson_upperbody_f", "green_dragon_top_f", "green_ranged_upperbody", "leather_ranged_upperbody", "red_ranged_upperbody", "purple_ranged_upperbody", "black_ranged_upperbody", "blue_ranged_upperbody",
  "iron_armor_upperbody", "steel_armor_upperbody", "gold_armor_upperbody", "titanium_armor_upperbody", "tungsten_armor_upperbody", "luminous_armor_upperbody",
  "leather_magic_armor_upperbody", "green_magic_armor_upperbody", "blue_magic_armor_upperbody", "red_magic_armor_upperbody", "black_magic_armor_upperbody", "purple_magic_armor_upperbody",
  "default_armor_upperbody",
  "boots", "shell_boots", "shell_boots_test_v1", "custom_boots_f", "meshy_crimson_boots_f", "green_dragon_boots_f", "green_ranged_boots", "leather_ranged_boots", "red_ranged_boots", "purple_ranged_boots", "black_ranged_boots", "blue_ranged_boots",
  "iron_armor_boots", "steel_armor_boots", "gold_armor_boots", "titanium_armor_boots", "tungsten_armor_boots", "luminous_armor_boots",
  "leather_magic_armor_boots", "green_magic_armor_boots", "blue_magic_armor_boots", "red_magic_armor_boots", "black_magic_armor_boots", "purple_magic_armor_boots",
  "default_armor_boots",
  "crimson_wizard_robe", "crimson_upperbody_f", "crimson_upperbody_meshy_v2", "crimson_wizard_boots",
  "head", "shell_head", "shell_head_test_v1", "custom_head_f", "meshy_crimson_head_f", "meshy_crimson_wizard_hat_f", "crimson_wizard_hat", "green_dragon_wizard_hat_f", "green_ranged_hat", "leather_ranged_hat", "red_ranged_hat", "purple_ranged_hat", "black_ranged_hat", "blue_ranged_hat",
  "leather_magic_armor_hat", "green_magic_armor_hat", "blue_magic_armor_hat", "red_magic_armor_hat", "black_magic_armor_hat", "purple_magic_armor_hat",
  "boghop", "inventioners", "shardspire", "wildplume", "wayfinder",
  "iron_armor_head", "steel_armor_head", "gold_armor_head", "titanium_armor_head", "tungsten_armor_head", "luminous_armor_head",
  "gloves", "shell_gloves", "shell_gloves_test_v1", "custom_gloves_f", "meshy_crimson_gloves_f", "crimson_wizard_gloves", "green_dragon_gloves_f", "green_ranged_gloves", "red_ranged_gloves", "purple_ranged_gloves", "black_ranged_gloves", "blue_ranged_gloves", "leather_ranged_gloves",
  "iron_armor_gloves", "steel_armor_gloves", "gold_armor_gloves", "titanium_armor_gloves", "tungsten_armor_gloves", "luminous_armor_gloves",
  "leather_magic_armor_gloves", "green_magic_armor_gloves", "blue_magic_armor_gloves", "red_magic_armor_gloves", "black_magic_armor_gloves", "purple_magic_armor_gloves",
]);

interface LoadedSlot {
  scene: THREE.Group;
  skinnedMeshes: THREE.SkinnedMesh[];
  needsAutoSkin?: boolean;
  originalMaterials?: Map<THREE.Mesh, THREE.Material>;
  /** Geometry-space center of mass (post load correction). */
  centroid?: THREE.Vector3;
}

const loader = new GLTFLoader();
const slotCache = new Map<string, LoadedSlot>();
const correctedSlots = new Set<string>();
const _buildTimestamp = Date.now();
const textureLoader = new THREE.TextureLoader();
const textureCache = new Map<string, THREE.Texture>();

/**
 * Export the current in-memory SkinnedMesh as a binary GLB that matches the
 * structure of the original equipment files (UpperbodyTestV1, shell_*.glb, etc.)
 * and is compatible with external game engines that use the same Mixamo rig.
 *
 * Triggered by the "↓ W" (Download re-weighted) button in the Equipment panel.
 * Pass the slot's `equipTransform` to permanently bake position, rotation, and
 * scale into the exported geometry.
 *
 * ── EquipTransform baking ─────────────────────────────────────────────────────
 *   The viewer applies the user's gizmo transform (position / rotation / scale)
 *   via a bind-matrix offset in Z-up viewer space. The net skinning formula is:
 *
 *     vertex_world = Σ weight_i · bone_current · bone_inv · M_zup · vertex_zup
 *
 *   where M_zup is the full transform matrix (TRS) in Z-up. Because M_zup sits
 *   BEFORE the bone chain (not after), baking it permanently into the rest-pose
 *   vertex positions is mathematically correct for both T-pose and all animated
 *   poses, for single-bone AND multi-bone meshes alike:
 *
 *     vertex_yup_exported = Cinv · M_zup · vertex_zup
 *
 *   The boneInverses are NOT changed — they encode the skeleton rest pose only.
 *   Uniform scale is skinning-invariant; position and rotation also bake cleanly
 *   because they are applied inside the bone hierarchy, not outside it.
 *
 * ── Coordinate system ────────────────────────────────────────────────────────
 *   Viewer  = Z-up  (geometry was converted by _yupToZupCorrection on load).
 *   GLB/Blender = Y-up (glTF standard).
 *   Let C = _yupToZupCorrection, Cinv = C⁻¹.
 *
 *   Three components are converted consistently:
 *     Geometry    : v_yup    = Cinv · M_zup · v_zup   (bakes TRS + coord flip)
 *     BoneInverse : Minv_yup = Cinv · Minv_zup · C    (coord flip only)
 *     Bone world  : B_yup    = Minv_yup⁻¹             (B · Minv = I → T-pose)
 *
 * ── Bone structure ───────────────────────────────────────────────────────────
 *   • Names converted back to GENERIC (pelvis, spine_01, upperarm_L, …)
 *     so the viewer's BONE_NAME_REMAP re-maps them correctly on reload.
 *   • Full parent-child hierarchy rebuilt from _EXPORT_BONE_PARENT.
 *   • Each bone stores its LOCAL transform relative to its parent so the
 *     armature matches the original rig layout in Blender.
 *
 * ── GLB compatibility ────────────────────────────────────────────────────────
 *   The output GLB is structurally identical to UpperbodyTestV1.glb / the
 *   shell_*.glb files: generic bone names, full 55-bone skeleton, skinned mesh
 *   parented to the armature, Y-up, no animations. It can be imported directly
 *   into any engine that supports the same Mixamo rig without any modifications.
 */
export function exportSlotAsGlb(
  slotId: string,
  fileName?: string,
  /** Optional equipTransform for the slot — position, rotation, and scale are all baked into geometry. */
  equipTransform?: EquipTransform,
): void {
  const loaded = slotCache.get(slotId);
  if (!loaded || loaded.skinnedMeshes.length === 0) {
    console.warn(`[Export] No skinned mesh in cache for "${slotId}". Enable the item first.`);
    return;
  }

  const sm = loaded.skinnedMeshes[0];
  const oldSk = sm.skeleton;
  const boneCount = oldSk.bones.length;

  const C    = _yupToZupCorrection;
  const Cinv = C.clone().invert();

  // ── 1. Geometry: Z-up → Y-up (bake full position + rotation + scale) ─────
  // The equipTransform is applied in the viewer's Z-up space as:
  //   vertex_world = Σ(weight_i × bone_current × bone_inv × M_zup × vertex_zup)
  // Baking M_zup into vertex positions is correct for ALL bones because the
  // transform is applied BEFORE the bone hierarchy, not after — so it holds
  // for both T-pose and all animated poses.
  //   vertex_yup_exported = Cinv × M_zup × vertex_zup
  // The boneInverses are unchanged (they represent bone rest positions only).
  const _DEG2RAD = Math.PI / 180;
  const M_zup = new THREE.Matrix4(); // identity when no transform set
  if (equipTransform) {
    const { position, rotation, scale } = normalizeEquipTransform(equipTransform);
    const centroid = loaded.centroid ?? computeMeshCentroid(loaded.skinnedMeshes);
    const euler = new THREE.Euler(
      rotation[0] * _DEG2RAD,
      rotation[1] * _DEG2RAD,
      rotation[2] * _DEG2RAD,
    );
    const quat = new THREE.Quaternion().setFromEuler(euler);
    const useCom = equipTransform.pivot !== "origin";
    if (useCom) {
      // T(P+C) · R · S · T(-C) — same CoM pivot as the live viewer
      M_zup.compose(
        new THREE.Vector3(
          position[0] + centroid.x,
          position[1] + centroid.y,
          position[2] + centroid.z,
        ),
        quat,
        new THREE.Vector3(scale[0], scale[1], scale[2]),
      );
      M_zup.multiply(
        new THREE.Matrix4().makeTranslation(-centroid.x, -centroid.y, -centroid.z),
      );
    } else {
      M_zup.compose(
        new THREE.Vector3(...position),
        quat,
        new THREE.Vector3(scale[0], scale[1], scale[2]),
      );
    }
  }
  const geoClone = sm.geometry.clone();
  geoClone.applyMatrix4(M_zup); // bake position + rotation + scale in Z-up
  geoClone.applyMatrix4(Cinv);  // convert Z-up → Y-up for GLB
  geoClone.computeVertexNormals();

  // GLTFExporter needs integer skinIndex (Uint16).
  const siAttr = geoClone.getAttribute("skinIndex") as THREE.BufferAttribute;
  if (siAttr && siAttr.array instanceof Float32Array) {
    geoClone.setAttribute("skinIndex", new THREE.BufferAttribute(new Uint16Array(siAttr.array), 4));
  }

  // ── 2. BoneInverses: Z-up → Y-up ──────────────────────────────────────────
  //   Minv_yup = Cinv · Minv_zup · C
  const newInverses = oldSk.boneInverses.map((inv) =>
    Cinv.clone().multiply(inv).multiply(C),
  );

  // ── 3. World bind matrices (Y-up) ─────────────────────────────────────────
  //   B_yup = Minv_yup⁻¹  →  B_yup · Minv_yup = I  (T-pose rest in Blender)
  const bindWorldMatrices = newInverses.map((inv) => inv.clone().invert());

  // ── 4. Build bone objects with GENERIC names ───────────────────────────────
  const standaloneBones: THREE.Bone[] = oldSk.bones.map((b, i) => {
    const bone = new THREE.Bone();
    // Convert Mixamo name → generic; keep as-is if not in the map (jaw, eye_L…)
    bone.name = _MIXAMO_TO_GENERIC[b.name] ?? b.name;
    return bone;
  });

  // Index lookup by the ORIGINAL (Mixamo) name for parent resolution
  const boneByMixamo = new Map<string, number>();
  for (let i = 0; i < boneCount; i++) boneByMixamo.set(oldSk.bones[i].name, i);

  // ── 5. Parent-child hierarchy + LOCAL transforms ───────────────────────────
  const armature = new THREE.Object3D();
  armature.name = "Armature";

  for (let i = 0; i < boneCount; i++) {
    const mixamoName  = oldSk.bones[i].name;
    const parentMixamo = _EXPORT_BONE_PARENT[mixamoName];
    const parentIdx    = parentMixamo !== undefined ? boneByMixamo.get(parentMixamo) : undefined;

    if (parentIdx !== undefined) {
      // Local transform = parentWorld⁻¹ · childWorld
      const localMat = bindWorldMatrices[parentIdx].clone().invert()
        .multiply(bindWorldMatrices[i]);
      localMat.decompose(
        standaloneBones[i].position,
        standaloneBones[i].quaternion,
        standaloneBones[i].scale,
      );
      standaloneBones[parentIdx].add(standaloneBones[i]);
    } else {
      // Root bone (mixamorigHips or unmapped) — local = world
      bindWorldMatrices[i].decompose(
        standaloneBones[i].position,
        standaloneBones[i].quaternion,
        standaloneBones[i].scale,
      );
      armature.add(standaloneBones[i]);
    }
  }

  // Ensure world matrices are up-to-date before the exporter reads them
  armature.updateMatrixWorld(true);

  // ── 6. SkinnedMesh ─────────────────────────────────────────────────────────
  const newSm = new THREE.SkinnedMesh(geoClone, sm.material);
  newSm.name = sm.name || slotId;
  newSm.frustumCulled = false;

  const newSkeleton = new THREE.Skeleton(standaloneBones, newInverses);
  newSm.bind(newSkeleton, new THREE.Matrix4());

  const exportGroup = new THREE.Group();
  exportGroup.add(armature);
  exportGroup.add(newSm);

  // ── 7. Export ──────────────────────────────────────────────────────────────
  const exporter = new GLTFExporter();
  exporter.parse(
    exportGroup,
    (result) => {
      const blob = new Blob([result as ArrayBuffer], { type: "model/gltf-binary" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName ?? `${slotId}_weighted.glb`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      console.log(
        `[Export] "${a.download}" — ${sm.geometry.getAttribute("position").count} verts, ` +
        `${boneCount} bones`,
      );
    },
    (err) => {
      console.error("[Export] GLTFExporter failed:", err);
    },
    { binary: true },
  );
}

/**
 * Build a MeshStandardMaterial that uses triplanar world-space projection
 * instead of UV coordinates.  The texture is projected from all 3 axes and
 * blended by surface normal, giving a natural wrapped look on body meshes
 * without requiring a hand-authored UV layout.
 */
function createTriplanarMaterial(
  texture: THREE.Texture,
  scale = 1.0,
  sharpness = 2.0,
): THREE.MeshStandardMaterial {
  const mat = new THREE.MeshStandardMaterial({
    map: texture,
    side: THREE.FrontSide,
    depthWrite: true,
    polygonOffset: true,
    polygonOffsetFactor: -1,
    polygonOffsetUnits: -1,
  });

  mat.onBeforeCompile = (shader) => {
    shader.uniforms.tpScale = { value: scale };
    shader.uniforms.tpSharp = { value: sharpness };

    shader.vertexShader = shader.vertexShader.replace(
      "#include <common>",
      `#include <common>
       varying vec3 vTriPos;
       varying vec3 vTriNorm;`,
    );
    shader.vertexShader = shader.vertexShader.replace(
      "#include <project_vertex>",
      `#include <project_vertex>
       vTriPos  = (modelMatrix * vec4(transformed, 1.0)).xyz;
       vTriNorm = normalize(mat3(modelMatrix) * objectNormal);`,
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <common>",
      `#include <common>
       varying vec3 vTriPos;
       varying vec3 vTriNorm;
       uniform float tpScale;
       uniform float tpSharp;`,
    );
    shader.fragmentShader = shader.fragmentShader.replace(
      "#include <map_fragment>",
      `#ifdef USE_MAP
         vec3 tpW = pow(abs(vTriNorm), vec3(tpSharp));
         tpW /= (tpW.x + tpW.y + tpW.z);
         vec4 tpX = texture2D(map, vTriPos.yz * tpScale);
         vec4 tpY = texture2D(map, vTriPos.xz * tpScale);
         vec4 tpZ = texture2D(map, vTriPos.xy * tpScale);
         vec4 sampledDiffuseColor = tpX * tpW.x + tpY * tpW.y + tpZ * tpW.z;
         sampledDiffuseColor = sRGBTransferOETF(sampledDiffuseColor);
         diffuseColor *= sampledDiffuseColor;
       #endif`,
    );
  };

  return mat;
}
const _identityMatrix = new THREE.Matrix4();
const _equipFacingCorrection = new THREE.Matrix4().makeRotationZ(Math.PI);

// Character model is displayed at 1.9 / 1.75 scale (see useCharacterModel).
// External equipment GLBs are built at 1.75m rig height, so we bake the same
// scale into the geometry correction so equipment matches the character.
const _CHARACTER_HEIGHT_SCALE = 1.9 / 1.75;
const _yupToZupCorrection = new THREE.Matrix4().makeRotationX(Math.PI / 2);
_yupToZupCorrection.scale(
  new THREE.Vector3(
    _CHARACTER_HEIGHT_SCALE,
    _CHARACTER_HEIGHT_SCALE,
    _CHARACTER_HEIGHT_SCALE,
  ),
);

/**
 * Remap non-Mixamo bone names found in equipment GLBs to Mixamo names.
 * Covers the legacy generic rig AND the Decentraland Avatar_* rig.
 * Decentraland uses 4 finger bones per finger; the 4th maps to Mixamo's 3rd.
 */
const BONE_NAME_REMAP: Record<string, string> = {
  // --- Legacy generic rig ---
  pelvis: "mixamorigHips",
  spine_01: "mixamorigSpine",
  spine_02: "mixamorigSpine1",
  spine_03: "mixamorigSpine2",
  neck_01: "mixamorigNeck",
  head: "mixamorigHead",
  clavicle_L: "mixamorigLeftShoulder",
  clavicle_R: "mixamorigRightShoulder",
  upperarm_L: "mixamorigLeftArm",
  upperarm_R: "mixamorigRightArm",
  lowerarm_L: "mixamorigLeftForeArm",
  lowerarm_R: "mixamorigRightForeArm",
  hand_L: "mixamorigLeftHand",
  hand_R: "mixamorigRightHand",
  thigh_L: "mixamorigLeftUpLeg",
  thigh_R: "mixamorigRightUpLeg",
  shin_L: "mixamorigLeftLeg",
  shin_R: "mixamorigRightLeg",
  foot_L: "mixamorigLeftFoot",
  foot_R: "mixamorigRightFoot",
  toe_L: "mixamorigLeftToeBase",
  toe_R: "mixamorigRightToeBase",
  thumb_01_L: "mixamorigLeftHandThumb1",
  thumb_02_L: "mixamorigLeftHandThumb2",
  thumb_03_L: "mixamorigLeftHandThumb3",
  index_01_L: "mixamorigLeftHandIndex1",
  index_02_L: "mixamorigLeftHandIndex2",
  index_03_L: "mixamorigLeftHandIndex3",
  middle_01_L: "mixamorigLeftHandMiddle1",
  middle_02_L: "mixamorigLeftHandMiddle2",
  middle_03_L: "mixamorigLeftHandMiddle3",
  ring_01_L: "mixamorigLeftHandRing1",
  ring_02_L: "mixamorigLeftHandRing2",
  ring_03_L: "mixamorigLeftHandRing3",
  pinky_01_L: "mixamorigLeftHandPinky1",
  pinky_02_L: "mixamorigLeftHandPinky2",
  pinky_03_L: "mixamorigLeftHandPinky3",
  thumb_01_R: "mixamorigRightHandThumb1",
  thumb_02_R: "mixamorigRightHandThumb2",
  thumb_03_R: "mixamorigRightHandThumb3",
  index_01_R: "mixamorigRightHandIndex1",
  index_02_R: "mixamorigRightHandIndex2",
  index_03_R: "mixamorigRightHandIndex3",
  middle_01_R: "mixamorigRightHandMiddle1",
  middle_02_R: "mixamorigRightHandMiddle2",
  middle_03_R: "mixamorigRightHandMiddle3",
  ring_01_R: "mixamorigRightHandRing1",
  ring_02_R: "mixamorigRightHandRing2",
  ring_03_R: "mixamorigRightHandRing3",
  pinky_01_R: "mixamorigRightHandPinky1",
  pinky_02_R: "mixamorigRightHandPinky2",
  pinky_03_R: "mixamorigRightHandPinky3",

  // --- Decentraland Avatar_* rig ---
  Avatar_Hips: "mixamorigHips",
  Avatar_Spine: "mixamorigSpine",
  Avatar_Spine1: "mixamorigSpine1",
  Avatar_Spine2: "mixamorigSpine2",
  Avatar_Neck: "mixamorigNeck",
  Avatar_Head: "mixamorigHead",
  Avatar_LeftShoulder: "mixamorigLeftShoulder",
  Avatar_RightShoulder: "mixamorigRightShoulder",
  Avatar_LeftUpperArm: "mixamorigLeftArm",
  Avatar_RightUpperArm: "mixamorigRightArm",
  Avatar_LeftArm: "mixamorigLeftArm",
  Avatar_RightArm: "mixamorigRightArm",
  Avatar_LeftLowerArm: "mixamorigLeftForeArm",
  Avatar_RightLowerArm: "mixamorigRightForeArm",
  Avatar_LeftForeArm: "mixamorigLeftForeArm",
  Avatar_RightForeArm: "mixamorigRightForeArm",
  Avatar_LeftHand: "mixamorigLeftHand",
  Avatar_RightHand: "mixamorigRightHand",
  Avatar_LeftUpperLeg: "mixamorigLeftUpLeg",
  Avatar_RightUpperLeg: "mixamorigRightUpLeg",
  Avatar_LeftUpLeg: "mixamorigLeftUpLeg",
  Avatar_RightUpLeg: "mixamorigRightUpLeg",
  Avatar_LeftLowerLeg: "mixamorigLeftLeg",
  Avatar_RightLowerLeg: "mixamorigRightLeg",
  Avatar_LeftLeg: "mixamorigLeftLeg",
  Avatar_RightLeg: "mixamorigRightLeg",
  Avatar_LeftFoot: "mixamorigLeftFoot",
  Avatar_RightFoot: "mixamorigRightFoot",
  Avatar_LeftToeBase: "mixamorigLeftToeBase",
  Avatar_RightToeBase: "mixamorigRightToeBase",
  // Left hand (Decentraland has 4 bones per finger; 4th → Mixamo 3rd)
  Avatar_LeftHandThumb1: "mixamorigLeftHandThumb1",
  Avatar_LeftHandThumb2: "mixamorigLeftHandThumb2",
  Avatar_LeftHandThumb3: "mixamorigLeftHandThumb3",
  Avatar_LeftHandThumb4: "mixamorigLeftHandThumb3",
  Avatar_LeftHandIndex1: "mixamorigLeftHandIndex1",
  Avatar_LeftHandIndex2: "mixamorigLeftHandIndex2",
  Avatar_LeftHandIndex3: "mixamorigLeftHandIndex3",
  Avatar_LeftHandIndex4: "mixamorigLeftHandIndex3",
  Avatar_LeftHandMiddle1: "mixamorigLeftHandMiddle1",
  Avatar_LeftHandMiddle2: "mixamorigLeftHandMiddle2",
  Avatar_LeftHandMiddle3: "mixamorigLeftHandMiddle3",
  Avatar_LeftHandMiddle4: "mixamorigLeftHandMiddle3",
  Avatar_LeftHandRing1: "mixamorigLeftHandRing1",
  Avatar_LeftHandRing2: "mixamorigLeftHandRing2",
  Avatar_LeftHandRing3: "mixamorigLeftHandRing3",
  Avatar_LeftHandRing4: "mixamorigLeftHandRing3",
  Avatar_LeftHandPinky1: "mixamorigLeftHandPinky1",
  Avatar_LeftHandPinky2: "mixamorigLeftHandPinky2",
  Avatar_LeftHandPinky3: "mixamorigLeftHandPinky3",
  Avatar_LeftHandPinky4: "mixamorigLeftHandPinky3",
  // Right hand
  Avatar_RightHandThumb1: "mixamorigRightHandThumb1",
  Avatar_RightHandThumb2: "mixamorigRightHandThumb2",
  Avatar_RightHandThumb3: "mixamorigRightHandThumb3",
  Avatar_RightHandThumb4: "mixamorigRightHandThumb3",
  Avatar_RightHandIndex1: "mixamorigRightHandIndex1",
  Avatar_RightHandIndex2: "mixamorigRightHandIndex2",
  Avatar_RightHandIndex3: "mixamorigRightHandIndex3",
  Avatar_RightHandIndex4: "mixamorigRightHandIndex3",
  Avatar_RightHandMiddle1: "mixamorigRightHandMiddle1",
  Avatar_RightHandMiddle2: "mixamorigRightHandMiddle2",
  Avatar_RightHandMiddle3: "mixamorigRightHandMiddle3",
  Avatar_RightHandMiddle4: "mixamorigRightHandMiddle3",
  Avatar_RightHandRing1: "mixamorigRightHandRing1",
  Avatar_RightHandRing2: "mixamorigRightHandRing2",
  Avatar_RightHandRing3: "mixamorigRightHandRing3",
  Avatar_RightHandRing4: "mixamorigRightHandRing3",
  Avatar_RightHandPinky1: "mixamorigRightHandPinky1",
  Avatar_RightHandPinky2: "mixamorigRightHandPinky2",
  Avatar_RightHandPinky3: "mixamorigRightHandPinky3",
  Avatar_RightHandPinky4: "mixamorigRightHandPinky3",
};

/**
 * Reverse of BONE_NAME_REMAP — maps Mixamo names back to the generic rig names
 * used by the original equipment GLBs (pelvis, spine_01, upperarm_L, …).
 * Used when exporting so the output matches the UpperbodyTestV1/ShellV2 format.
 */
const _MIXAMO_TO_GENERIC: Record<string, string> = {};
for (const [generic, mixamo] of Object.entries(BONE_NAME_REMAP)) {
  if (!_MIXAMO_TO_GENERIC[mixamo]) _MIXAMO_TO_GENERIC[mixamo] = generic;
}

/**
 * Standard skeleton parent map keyed by bone name as it appears in oldSk.bones
 * after skin-transfer (Mixamo names for remapped bones; original for the rest).
 * Defines the parent-child hierarchy for the exported armature.
 */
const _EXPORT_BONE_PARENT: Record<string, string> = {
  // spine chain
  mixamorigSpine:  "mixamorigHips",
  mixamorigSpine1: "mixamorigSpine",
  mixamorigSpine2: "mixamorigSpine1",
  mixamorigNeck:   "mixamorigSpine2",
  mixamorigHead:   "mixamorigNeck",
  // left arm
  mixamorigLeftShoulder: "mixamorigSpine2",
  mixamorigLeftArm:      "mixamorigLeftShoulder",
  mixamorigLeftForeArm:  "mixamorigLeftArm",
  mixamorigLeftHand:     "mixamorigLeftForeArm",
  mixamorigLeftHandThumb1:  "mixamorigLeftHand",
  mixamorigLeftHandThumb2:  "mixamorigLeftHandThumb1",
  mixamorigLeftHandThumb3:  "mixamorigLeftHandThumb2",
  mixamorigLeftHandIndex1:  "mixamorigLeftHand",
  mixamorigLeftHandIndex2:  "mixamorigLeftHandIndex1",
  mixamorigLeftHandIndex3:  "mixamorigLeftHandIndex2",
  mixamorigLeftHandMiddle1: "mixamorigLeftHand",
  mixamorigLeftHandMiddle2: "mixamorigLeftHandMiddle1",
  mixamorigLeftHandMiddle3: "mixamorigLeftHandMiddle2",
  mixamorigLeftHandRing1:   "mixamorigLeftHand",
  mixamorigLeftHandRing2:   "mixamorigLeftHandRing1",
  mixamorigLeftHandRing3:   "mixamorigLeftHandRing2",
  mixamorigLeftHandPinky1:  "mixamorigLeftHand",
  mixamorigLeftHandPinky2:  "mixamorigLeftHandPinky1",
  mixamorigLeftHandPinky3:  "mixamorigLeftHandPinky2",
  // right arm
  mixamorigRightShoulder: "mixamorigSpine2",
  mixamorigRightArm:      "mixamorigRightShoulder",
  mixamorigRightForeArm:  "mixamorigRightArm",
  mixamorigRightHand:     "mixamorigRightForeArm",
  mixamorigRightHandThumb1:  "mixamorigRightHand",
  mixamorigRightHandThumb2:  "mixamorigRightHandThumb1",
  mixamorigRightHandThumb3:  "mixamorigRightHandThumb2",
  mixamorigRightHandIndex1:  "mixamorigRightHand",
  mixamorigRightHandIndex2:  "mixamorigRightHandIndex1",
  mixamorigRightHandIndex3:  "mixamorigRightHandIndex2",
  mixamorigRightHandMiddle1: "mixamorigRightHand",
  mixamorigRightHandMiddle2: "mixamorigRightHandMiddle1",
  mixamorigRightHandMiddle3: "mixamorigRightHandMiddle2",
  mixamorigRightHandRing1:   "mixamorigRightHand",
  mixamorigRightHandRing2:   "mixamorigRightHandRing1",
  mixamorigRightHandRing3:   "mixamorigRightHandRing2",
  mixamorigRightHandPinky1:  "mixamorigRightHand",
  mixamorigRightHandPinky2:  "mixamorigRightHandPinky1",
  mixamorigRightHandPinky3:  "mixamorigRightHandPinky2",
  // legs
  mixamorigLeftUpLeg:   "mixamorigHips",
  mixamorigLeftLeg:     "mixamorigLeftUpLeg",
  mixamorigLeftFoot:    "mixamorigLeftLeg",
  mixamorigLeftToeBase: "mixamorigLeftFoot",
  mixamorigRightUpLeg:   "mixamorigHips",
  mixamorigRightLeg:     "mixamorigRightUpLeg",
  mixamorigRightFoot:    "mixamorigRightLeg",
  mixamorigRightToeBase: "mixamorigRightFoot",
  // extra bones that weren't in BONE_NAME_REMAP (keep generic names after transfer)
  jaw:   "mixamorigHead",
  eye_L: "mixamorigHead",
  eye_R: "mixamorigHead",
};

function findSkinnedMeshes(root: THREE.Object3D): THREE.SkinnedMesh[] {
  const result: THREE.SkinnedMesh[] = [];
  root.traverse((child) => {
    if ((child as THREE.SkinnedMesh).isSkinnedMesh) {
      result.push(child as THREE.SkinnedMesh);
    }
  });
  return result;
}

function findRegularMeshes(root: THREE.Object3D): THREE.Mesh[] {
  const result: THREE.Mesh[] = [];
  root.traverse((child) => {
    if (
      (child as THREE.Mesh).isMesh &&
      !(child as THREE.SkinnedMesh).isSkinnedMesh
    ) {
      result.push(child as THREE.Mesh);
    }
  });
  return result;
}

/**
 * Converts an unrigged Mesh to a SkinnedMesh with proximity-based bone weights.
 * Port of the assign_weights() logic from equipment/factory/mesh_factory.py.
 */
function autoSkinMesh(
  mesh: THREE.Mesh,
  slotBones: SlotBone[],
  animBones: Map<string, THREE.Bone>,
  charBoneInverseMap: Map<string, THREE.Matrix4>,
  slotBounds: { z_min: number; z_max: number; radius: number },
): THREE.SkinnedMesh | null {
  const MAX_INFLUENCES = 4;
  const weightRadius = slotBounds.radius * 2.0;

  const usedBones: THREE.Bone[] = [];
  const usedInverses: THREE.Matrix4[] = [];
  const boneConfigs: { bone: THREE.Bone; specWeight: number; position: THREE.Vector3 }[] = [];

  for (const sb of slotBones) {
    const animBone = animBones.get(sb.name);
    const inv = charBoneInverseMap.get(sb.name);
    if (!animBone || !inv) continue;
    animBone.updateMatrixWorld(true);
    const pos = new THREE.Vector3().setFromMatrixPosition(animBone.matrixWorld);
    usedBones.push(animBone);
    usedInverses.push(inv.clone());
    boneConfigs.push({ bone: animBone, specWeight: sb.weight, position: pos });
  }

  if (usedBones.length === 0) return null;

  const geo = mesh.geometry.clone();
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  if (!position) return null;

  const vertexCount = position.count;
  const skinIndices = new Float32Array(vertexCount * 4);
  const skinWeights = new Float32Array(vertexCount * 4);

  const vtx = new THREE.Vector3();

  for (let vi = 0; vi < vertexCount; vi++) {
    vtx.set(position.getX(vi), position.getY(vi), position.getZ(vi));

    const influences: { idx: number; w: number }[] = [];

    for (let bi = 0; bi < boneConfigs.length; bi++) {
      const dist = vtx.distanceTo(boneConfigs[bi].position);
      if (dist > weightRadius) continue;
      const falloff = Math.max(0, 1 - dist / weightRadius);
      const w = Math.pow(falloff, 3) * boneConfigs[bi].specWeight;
      if (w > 0.001) {
        influences.push({ idx: bi, w });
      }
    }

    influences.sort((a, b) => b.w - a.w);
    const top = influences.slice(0, MAX_INFLUENCES);
    const totalW = top.reduce((s, i) => s + i.w, 0);

    const base = vi * 4;
    for (let j = 0; j < 4; j++) {
      if (j < top.length && totalW > 0) {
        skinIndices[base + j] = top[j].idx;
        skinWeights[base + j] = top[j].w / totalW;
      } else {
        skinIndices[base + j] = 0;
        skinWeights[base + j] = 0;
      }
    }
  }

  geo.setAttribute("skinIndex", new THREE.BufferAttribute(skinIndices, 4));
  geo.setAttribute("skinWeight", new THREE.BufferAttribute(skinWeights, 4));

  const skinnedMesh = new THREE.SkinnedMesh(geo, mesh.material);
  skinnedMesh.name = mesh.name;
  skinnedMesh.frustumCulled = false;

  const skeleton = new THREE.Skeleton(usedBones, usedInverses);
  skinnedMesh.bind(skeleton, new THREE.Matrix4());

  return skinnedMesh;
}

/**
 * Scale an unrigged mesh to fit within a slot's bounding volume,
 * then center it on the slot's midpoint.
 */
function scaleToSlotBounds(
  scene: THREE.Group,
  slotBounds: { z_min: number; z_max: number; radius: number },
): void {
  const box = new THREE.Box3().setFromObject(scene);
  const size = new THREE.Vector3();
  box.getSize(size);
  const center = new THREE.Vector3();
  box.getCenter(center);

  const maxCurrent = Math.max(size.x, size.y, size.z);
  if (maxCurrent < 0.0001) return;

  const slotHeight = slotBounds.z_max - slotBounds.z_min;
  const slotWidth = slotBounds.radius * 2;
  const maxTarget = Math.max(slotHeight, slotWidth);
  if (maxTarget < 0.0001) return;

  const scaleFactor = maxTarget / maxCurrent;

  scene.scale.multiplyScalar(scaleFactor);
  scene.updateMatrixWorld(true);

  const newBox = new THREE.Box3().setFromObject(scene);
  const newCenter = new THREE.Vector3();
  newBox.getCenter(newCenter);

  const targetCenter = new THREE.Vector3(
    0,
    0,
    (slotBounds.z_min + slotBounds.z_max) / 2,
  );
  const offset = targetCenter.sub(newCenter);
  scene.position.add(offset);
}

function smoothOutlierVertices(
  geo: THREE.BufferGeometry,
  threshold: number,
  maxPasses = 6,
): number {
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  const idx = geo.index;
  if (!position || !idx) return 0;

  const adjMap = new Map<number, Set<number>>();
  for (let t = 0; t < idx.count; t += 3) {
    const a = idx.getX(t), b = idx.getX(t + 1), c = idx.getX(t + 2);
    for (const [v1, v2] of [[a, b], [b, c], [c, a]] as [number, number][]) {
      if (!adjMap.has(v1)) adjMap.set(v1, new Set());
      if (!adjMap.has(v2)) adjMap.set(v2, new Set());
      adjMap.get(v1)!.add(v2);
      adjMap.get(v2)!.add(v1);
    }
  }

  let totalFixed = 0;
  for (let pass = 0; pass < maxPasses; pass++) {
    let passFixed = 0;
    for (let vi = 0; vi < position.count; vi++) {
      const neighbors = adjMap.get(vi);
      if (!neighbors || neighbors.size < 2) continue;
      const px = position.getX(vi), py = position.getY(vi), pz = position.getZ(vi);
      let sx = 0, sy = 0, sz = 0, cnt = 0;
      for (const ni of neighbors) {
        sx += position.getX(ni); sy += position.getY(ni); sz += position.getZ(ni); cnt++;
      }
      const ax = sx / cnt, ay = sy / cnt, az = sz / cnt;
      const d = Math.sqrt((px - ax) ** 2 + (py - ay) ** 2 + (pz - az) ** 2);
      if (d > threshold) {
        position.setXYZ(vi, ax, ay, az);
        passFixed++;
      }
    }
    totalFixed += passFixed;
    if (passFixed === 0) break;
  }

  if (totalFixed > 0) position.needsUpdate = true;
  return totalFixed;
}

function inflateGeometry(geo: THREE.BufferGeometry, amount: number): void {
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  let normal = geo.getAttribute("normal") as THREE.BufferAttribute;
  if (!position) return;
  if (!normal) {
    geo.computeVertexNormals();
    normal = geo.getAttribute("normal") as THREE.BufferAttribute;
    if (!normal) return;
  }
  for (let i = 0; i < position.count; i++) {
    const px = position.getX(i), py = position.getY(i), pz = position.getZ(i);
    const nx = normal.getX(i), ny = normal.getY(i), nz = normal.getZ(i);
    const absPx = Math.abs(px);
    if (absPx > 0.75) {
      const radialLen = Math.sqrt(px * px + py * py);
      if (radialLen > 0.01) {
        const dot = (px * nx + py * ny) / radialLen;
        if (dot < 0) continue;
      }
    }
    position.setXYZ(i, px + nx * amount, py + ny * amount, pz + nz * amount);
  }
  position.needsUpdate = true;
}

function extendFingertips(
  geo: THREE.BufferGeometry,
  skeleton: THREE.Skeleton,
  amount: number,
): void {
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  const skinIndex = geo.getAttribute("skinIndex") as THREE.BufferAttribute;
  const skinWeight = geo.getAttribute("skinWeight") as THREE.BufferAttribute;
  if (!position || !skinIndex || !skinWeight) return;

  const boneScale = new Map<number, number>();
  const thumbBones = new Set<number>();
  const indexBones = new Set<number>();
  const middleBones = new Set<number>();
  const pinkyBones = new Set<number>();

  for (let i = 0; i < skeleton.bones.length; i++) {
    const n = skeleton.bones[i].name;
    let s = 0;
    if (/_03_|_03$|03_[LR]|Thumb3|Index3|Middle3|Ring3|Pinky3/.test(n)) s = 1.0;
    else if (/_02_|_02$|02_[LR]|Thumb2|Index2|Middle2|Ring2|Pinky2/.test(n)) s = 0.6;
    else if (/_01_|_01$|01_[LR]|Thumb1|Index1|Middle1|Ring1|Pinky1/.test(n)) s = 0.2;
    if (s === 0) continue;
    boneScale.set(i, s);
    if (/[Tt]humb/.test(n)) thumbBones.add(i);
    if (/[Ii]ndex/.test(n)) indexBones.add(i);
    if (/[Mm]iddle/.test(n)) middleBones.add(i);
    if (/[Pp]inky/.test(n)) pinkyBones.add(i);
  }
  if (boneScale.size === 0) return;

  const siGet = [
    (vi: number) => skinIndex.getX(vi),
    (vi: number) => skinIndex.getY(vi),
    (vi: number) => skinIndex.getZ(vi),
    (vi: number) => skinIndex.getW(vi),
  ];
  const swGet = [
    (vi: number) => skinWeight.getX(vi),
    (vi: number) => skinWeight.getY(vi),
    (vi: number) => skinWeight.getZ(vi),
    (vi: number) => skinWeight.getW(vi),
  ];

  for (let vi = 0; vi < position.count; vi++) {
    let dx = 0, dy = 0;
    let matched = false;

    for (let slot = 0; slot < 4; slot++) {
      const bIdx = siGet[slot](vi);
      const bW = swGet[slot](vi);
      if (bW < 0.05) continue;

      const s = boneScale.get(bIdx);
      if (s === undefined) continue;

      const px = position.getX(vi);
      const sign = px > 0 ? 1 : -1;
      const contrib = amount * s * bW;
      dx += sign * contrib;

      if (thumbBones.has(bIdx)) {
        dy -= contrib * 1.2;
      } else if (indexBones.has(bIdx)) {
        dy -= contrib * 0.4;
      } else if (pinkyBones.has(bIdx)) {
        dy += contrib * 0.4;
      } else if (middleBones.has(bIdx)) {
        dy -= contrib * 0.3;
      }
      matched = true;
    }

    if (matched) {
      position.setXYZ(
        vi,
        position.getX(vi) + dx,
        position.getY(vi) + dy,
        position.getZ(vi),
      );
    }
  }
  position.needsUpdate = true;
}

function fixZeroWeightVertices(sm: THREE.SkinnedMesh): void {
  const geo = sm.geometry;
  const skinWeight = geo.getAttribute("skinWeight") as THREE.BufferAttribute;
  const skinIndex = geo.getAttribute("skinIndex") as THREE.BufferAttribute;
  const position = geo.getAttribute("position") as THREE.BufferAttribute;

  if (!skinWeight || !skinIndex || !position) return;

  const skeleton = sm.skeleton;
  const boneCount = skeleton.boneInverses.length;
  if (boneCount === 0) return;

  const bonePositions: THREE.Vector3[] = [];
  const tmpMatrix = new THREE.Matrix4();
  for (let i = 0; i < boneCount; i++) {
    tmpMatrix.copy(skeleton.boneInverses[i]).invert();
    bonePositions.push(new THREE.Vector3().setFromMatrixPosition(tmpMatrix));
  }

  let fixed = 0;
  let normalised = 0;
  const vtx = new THREE.Vector3();

  for (let i = 0; i < position.count; i++) {
    const totalW =
      skinWeight.getX(i) +
      skinWeight.getY(i) +
      skinWeight.getZ(i) +
      skinWeight.getW(i);

    if (totalW < 0.001) {
      vtx.fromBufferAttribute(position, i);
      let minDist = Infinity;
      let nearestIdx = 0;

      for (let b = 0; b < boneCount; b++) {
        const d = vtx.distanceToSquared(bonePositions[b]);
        if (d < minDist) {
          minDist = d;
          nearestIdx = b;
        }
      }

      skinIndex.setXYZW(i, nearestIdx, 0, 0, 0);
      skinWeight.setXYZW(i, 1, 0, 0, 0);
      fixed++;
    } else if (Math.abs(totalW - 1.0) > 0.01) {
      const inv = 1.0 / totalW;
      skinWeight.setXYZW(
        i,
        skinWeight.getX(i) * inv,
        skinWeight.getY(i) * inv,
        skinWeight.getZ(i) * inv,
        skinWeight.getW(i) * inv,
      );
      normalised++;
    }
  }

  if (fixed > 0 || normalised > 0) {
    skinWeight.needsUpdate = true;
    skinIndex.needsUpdate = true;
  }
}

/**
 * For fine-bone slots (gloves, ring), shifts equipment vertices to match
 * the character's bone positions. Computes per-bone positional deltas
 * (old rig display-space → character world-space) and applies weighted
 * corrections so finger geometry aligns with the Mixamo skeleton.
 */
function applyRestPoseCorrection(
  sm: THREE.SkinnedMesh,
  boneDeltas: THREE.Vector3[],
): void {
  const geo = sm.geometry;
  const position = geo.getAttribute("position") as THREE.BufferAttribute;
  const skinIndex = geo.getAttribute("skinIndex") as THREE.BufferAttribute;
  const skinWeight = geo.getAttribute("skinWeight") as THREE.BufferAttribute;

  if (!position || !skinIndex || !skinWeight) return;

  const correction = new THREE.Vector3();

  for (let i = 0; i < position.count; i++) {
    correction.set(0, 0, 0);

    const indices = [
      skinIndex.getX(i), skinIndex.getY(i),
      skinIndex.getZ(i), skinIndex.getW(i),
    ];
    const weights = [
      skinWeight.getX(i), skinWeight.getY(i),
      skinWeight.getZ(i), skinWeight.getW(i),
    ];

    for (let j = 0; j < 4; j++) {
      const w = weights[j];
      if (w === 0) continue;
      const bIdx = indices[j];
      if (bIdx >= boneDeltas.length) continue;
      correction.addScaledVector(boneDeltas[bIdx], w);
    }

    position.setXYZ(
      i,
      position.getX(i) + correction.x,
      position.getY(i) + correction.y,
      position.getZ(i) + correction.z,
    );
  }

  position.needsUpdate = true;
}

function bindSlotSkeleton(
  slot: LoadedSlot,
  animBones: Map<string, THREE.Bone>,
  charBoneInverseMap: Map<string, THREE.Matrix4>,
  slotId?: string,
): void {
  const _tmpMat = new THREE.Matrix4();
  const isFineSlot = slotId != null && FINE_BONE_SLOTS.has(slotId);
  const alreadyCorrected = slotId != null && correctedSlots.has(slotId);

  for (const sm of slot.skinnedMeshes) {
    const oldSk = sm.skeleton;
    if (!oldSk) continue;

    const newBones: THREE.Bone[] = [];
    const newInverses: THREE.Matrix4[] = [];
    const boneDeltas: THREE.Vector3[] = [];

    for (let i = 0; i < oldSk.bones.length; i++) {
      const rawName = oldSk.bones[i].name;
      const boneName = BONE_NAME_REMAP[rawName] ?? rawName;
      const animBone = animBones.get(boneName);
      const charInv = charBoneInverseMap.get(boneName);

      if (animBone && charInv) {
        newBones.push(animBone);
        newInverses.push(charInv.clone());

        if (isFineSlot && !alreadyCorrected) {
          animBone.updateMatrixWorld(true);
          _tmpMat.copy(oldSk.boneInverses[i]).invert();
          const equipPosDisplay = new THREE.Vector3(
            -_tmpMat.elements[12],
            -_tmpMat.elements[13],
            _tmpMat.elements[14],
          );
          const charPos = new THREE.Vector3(
            animBone.matrixWorld.elements[12],
            animBone.matrixWorld.elements[13],
            animBone.matrixWorld.elements[14],
          );
          boneDeltas.push(charPos.clone().sub(equipPosDisplay));
        }
      } else {
        newBones.push(oldSk.bones[i] as THREE.Bone);
        newInverses.push(oldSk.boneInverses[i].clone());

        if (isFineSlot && !alreadyCorrected) {
          boneDeltas.push(new THREE.Vector3(0, 0, 0));
        }
      }
    }

    if (isFineSlot && !alreadyCorrected) {
      applyRestPoseCorrection(sm, boneDeltas);
    }

    const newSkeleton = new THREE.Skeleton(newBones, newInverses);
    sm.bind(newSkeleton, _identityMatrix);

    fixZeroWeightVertices(sm);

  }

  if (isFineSlot && !alreadyCorrected) {
    correctedSlots.add(slotId!);
  }
}

const DEG2RAD = Math.PI / 180;
const RAD2DEG = 180 / Math.PI;

/** Vertex-average centroid in current geometry space (largest skinned mesh). */
function computeMeshCentroid(skinnedMeshes: THREE.SkinnedMesh[]): THREE.Vector3 {
  let best: THREE.SkinnedMesh | null = null;
  let bestCount = 0;
  for (const sm of skinnedMeshes) {
    const pos = sm.geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
    if (!pos || pos.count < 8) continue;
    if (pos.count > bestCount) {
      best = sm;
      bestCount = pos.count;
    }
  }
  const out = new THREE.Vector3();
  if (!best) return out;
  const pos = best.geometry.getAttribute("position") as THREE.BufferAttribute;
  const base = (best.geometry.userData.basePos as Float32Array | undefined) ?? null;
  let sx = 0, sy = 0, sz = 0;
  for (let i = 0; i < pos.count; i++) {
    const i3 = i * 3;
    if (base) {
      sx += base[i3];
      sy += base[i3 + 1];
      sz += base[i3 + 2];
    } else {
      sx += pos.getX(i);
      sy += pos.getY(i);
      sz += pos.getZ(i);
    }
  }
  out.set(sx / pos.count, sy / pos.count, sz / pos.count);
  return out;
}

/**
 * Build bind-matrix TRS.
 * CoM pivot: T(P+C) · R · S · T(-C)  — rotate/scale around mesh center of mass.
 * Origin pivot (legacy): T(P) · R · S.
 */
function composeEquipBindMatrix(
  out: THREE.Matrix4,
  transform: EquipTransform,
  centroid: THREE.Vector3 | undefined,
  negC: THREE.Matrix4,
  euler: THREE.Euler,
  quat: THREE.Quaternion,
  pos: THREE.Vector3,
  scl: THREE.Vector3,
): void {
  const useCom = transform.pivot !== "origin" && centroid != null;
  euler.set(
    transform.rotation[0] * DEG2RAD,
    transform.rotation[1] * DEG2RAD,
    transform.rotation[2] * DEG2RAD,
  );
  quat.setFromEuler(euler);
  scl.set(transform.scale[0], transform.scale[1], transform.scale[2]);
  if (useCom) {
    pos.set(
      transform.position[0] + centroid.x,
      transform.position[1] + centroid.y,
      transform.position[2] + centroid.z,
    );
    out.compose(pos, quat, scl);
    negC.makeTranslation(-centroid.x, -centroid.y, -centroid.z);
    out.multiply(negC);
  } else {
    pos.set(...transform.position);
    out.compose(pos, quat, scl);
  }
}

/** Convert a legacy origin-pivot transform to an equivalent CoM-pivot transform. */
function migrateOriginPivotToCom(
  transform: EquipTransform,
  centroid: THREE.Vector3,
): EquipTransform {
  if (transform.pivot === "com") return transform;
  const euler = new THREE.Euler(
    transform.rotation[0] * DEG2RAD,
    transform.rotation[1] * DEG2RAD,
    transform.rotation[2] * DEG2RAD,
  );
  const quat = new THREE.Quaternion().setFromEuler(euler);
  const scaledC = new THREE.Vector3(
    centroid.x * transform.scale[0],
    centroid.y * transform.scale[1],
    centroid.z * transform.scale[2],
  );
  scaledC.applyQuaternion(quat);
  return {
    ...transform,
    position: [
      +(transform.position[0] - centroid.x + scaledC.x).toFixed(4),
      +(transform.position[1] - centroid.y + scaledC.y).toFixed(4),
      +(transform.position[2] - centroid.z + scaledC.z).toFixed(4),
    ],
    pivot: "com",
  };
}

function findDominantBoneIndex(sm: THREE.SkinnedMesh): number {
  const bones = sm.skeleton?.bones;
  if (!bones?.length) return 0;
  const headIdx = bones.findIndex((b) => /head/i.test(b.name));
  if (headIdx >= 0) return headIdx;
  // Prefer bone with greatest total skin weight.
  const sw = sm.geometry.getAttribute("skinWeight") as THREE.BufferAttribute | undefined;
  const si = sm.geometry.getAttribute("skinIndex") as THREE.BufferAttribute | undefined;
  if (!sw || !si) return 0;
  const totals = new Float64Array(bones.length);
  const siArr = si.array as ArrayLike<number>;
  const swArr = sw.array as ArrayLike<number>;
  for (let i = 0; i < sw.count; i++) {
    const o = i * 4;
    for (let k = 0; k < 4; k++) {
      const idx = siArr[o + k];
      const w = swArr[o + k];
      if (idx >= 0 && idx < bones.length) totals[idx] += w;
    }
  }
  let best = 0;
  for (let i = 1; i < totals.length; i++) {
    if (totals[i] > totals[best]) best = i;
  }
  return best;
}

/** World-space location of the mesh CoM after skinning + bindMatrix. */
function skinnedCentroidWorld(
  sm: THREE.SkinnedMesh,
  localC: THREE.Vector3,
  bindMatrix: THREE.Matrix4,
  out: THREE.Vector3,
): THREE.Vector3 {
  const idx = findDominantBoneIndex(sm);
  const bone = sm.skeleton.bones[idx];
  const boneInverse = sm.skeleton.boneInverses[idx];
  out.copy(localC).applyMatrix4(bindMatrix).applyMatrix4(boneInverse);
  bone.updateMatrixWorld(true);
  out.applyMatrix4(bone.matrixWorld);
  return out;
}

function EquipmentSlotWrapper({
  slotId,
  slot,
  isSelected,
  onSelect,
  transform,
  gizmoMode,
  onTransformChange,
}: {
  slotId: string;
  slot: LoadedSlot;
  isSelected: boolean;
  onSelect: () => void;
  transform: EquipTransform;
  gizmoMode: GizmoMode;
  onTransformChange: (t: EquipTransform) => void;
}) {
  const isDraggingRef = useRef(false);
  const tcRef = useRef<any>(null);
  const gizmoProxy = useMemo(() => new THREE.Object3D(), []);
  const [gizmoReady, setGizmoReady] = useState(false);
  const worldComOffsetRef = useRef(new THREE.Vector3());
  const migratedRef = useRef(false);

  const _offsetMatrix = useMemo(() => new THREE.Matrix4(), []);
  const _negC = useMemo(() => new THREE.Matrix4(), []);
  const _euler = useMemo(() => new THREE.Euler(), []);
  const _quat = useMemo(() => new THREE.Quaternion(), []);
  const _pos = useMemo(() => new THREE.Vector3(), []);
  const _scl = useMemo(() => new THREE.Vector3(), []);
  const _worldCom = useMemo(() => new THREE.Vector3(), []);

  // Ensure centroid is cached on the loaded slot.
  useEffect(() => {
    if (!slot.skinnedMeshes.length) return;
    if (!slot.centroid) {
      slot.centroid = computeMeshCentroid(slot.skinnedMeshes);
    }
    setGizmoReady(true);
  }, [slot, slot.skinnedMeshes]);

  // One-time migrate legacy origin-pivot transforms → CoM pivot (same visuals).
  useEffect(() => {
    if (migratedRef.current) return;
    if (!slot.centroid) return;
    migratedRef.current = true;
    if (transform.pivot === "com") return;
    onTransformChange(migrateOriginPivotToCom(transform, slot.centroid));
  }, [slot.centroid, transform, onTransformChange]);

  // Bilateral pair spacing (+ per-eye socket rotations for eyes only).
  useEffect(() => {
    const isEyes = /_eyes$/.test(slotId);
    const isBilateralFace =
      isEyes ||
      /_eyebrows$/.test(slotId) ||
      /_eyelashes$/.test(slotId) ||
      /_ears$/.test(slotId);
    if (!isBilateralFace) return;

    const sep = transform.eyeSeparation ?? 0;
    const rotL = isEyes ? (transform.eyeRotationL ?? [0, 0, 0]) : [0, 0, 0];
    const rotR = isEyes ? (transform.eyeRotationR ?? [0, 0, 0]) : [0, 0, 0];
    const qL = new THREE.Quaternion().setFromEuler(
      new THREE.Euler(rotL[0] * DEG2RAD, rotL[1] * DEG2RAD, rotL[2] * DEG2RAD, "XYZ"),
    );
    const qR = new THREE.Quaternion().setFromEuler(
      new THREE.Euler(rotR[0] * DEG2RAD, rotR[1] * DEG2RAD, rotR[2] * DEG2RAD, "XYZ"),
    );
    const tmp = new THREE.Vector3();
    const applySideRot = isEyes;

    for (const sm of slot.skinnedMeshes) {
      const pos = sm.geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
      if (!pos) continue;
      if (!sm.geometry.userData.basePos) {
        sm.geometry.userData.basePos = new Float32Array(pos.array as ArrayLike<number>);
      }
      const base = sm.geometry.userData.basePos as Float32Array;
      const arr = pos.array as Float32Array;

      let lSumX = 0, lSumY = 0, lSumZ = 0, lCount = 0;
      let rSumX = 0, rSumY = 0, rSumZ = 0, rCount = 0;
      for (let i = 0; i < pos.count; i++) {
        const i3 = i * 3;
        const bx = base[i3];
        if (bx < -1e-5) {
          lSumX += bx; lSumY += base[i3 + 1]; lSumZ += base[i3 + 2]; lCount++;
        } else if (bx > 1e-5) {
          rSumX += bx; rSumY += base[i3 + 1]; rSumZ += base[i3 + 2]; rCount++;
        }
      }
      const cL = new THREE.Vector3(
        lCount ? lSumX / lCount : -0.035,
        lCount ? lSumY / lCount : 0,
        lCount ? lSumZ / lCount : 0,
      );
      const cR = new THREE.Vector3(
        rCount ? rSumX / rCount : 0.035,
        rCount ? rSumY / rCount : 0,
        rCount ? rSumZ / rCount : 0,
      );

      for (let i = 0; i < pos.count; i++) {
        const i3 = i * 3;
        const bx = base[i3];
        const by = base[i3 + 1];
        const bz = base[i3 + 2];
        const isLeft = bx < -1e-5;
        const isRight = bx > 1e-5;
        const sideSep = Math.abs(bx) < 1e-5 ? 0 : Math.sign(bx) * sep;

        if (applySideRot && (isLeft || isRight)) {
          const center = isLeft ? cL : cR;
          const quat = isLeft ? qL : qR;
          tmp.set(bx - center.x, by - center.y, bz - center.z);
          tmp.applyQuaternion(quat);
          arr[i3] = center.x + tmp.x + sideSep;
          arr[i3 + 1] = center.y + tmp.y;
          arr[i3 + 2] = center.z + tmp.z;
        } else {
          arr[i3] = bx + sideSep;
          arr[i3 + 1] = by;
          arr[i3 + 2] = bz;
        }
      }
      pos.needsUpdate = true;
      sm.geometry.computeBoundingSphere();
      sm.geometry.computeBoundingBox();
    }
    // Pair deform changes mass slightly — refresh centroid from deformed verts.
    slot.centroid = computeMeshCentroid(slot.skinnedMeshes);
  }, [
    slotId,
    slot,
    slot.skinnedMeshes,
    transform.eyeSeparation,
    transform.eyeRotationL,
    transform.eyeRotationR,
  ]);

  const applyBindFromTransform = useCallback(
    (t: EquipTransform) => {
      composeEquipBindMatrix(
        _offsetMatrix, t, slot.centroid, _negC, _euler, _quat, _pos, _scl,
      );
      for (const sm of slot.skinnedMeshes) {
        sm.bindMatrix.copy(_offsetMatrix);
        sm.bindMatrixInverse.copy(_offsetMatrix).invert();
      }
    },
    [slot, _offsetMatrix, _negC, _euler, _quat, _pos, _scl],
  );

  const readTransformFromGizmo = useCallback(() => {
    const proxy = gizmoProxy;
    // World CoM ≈ P + frozenOffset  ⇒  P = worldPos - offset
    const px = proxy.position.x - worldComOffsetRef.current.x;
    const py = proxy.position.y - worldComOffsetRef.current.y;
    const pz = proxy.position.z - worldComOffsetRef.current.z;
    onTransformChange({
      ...transform,
      position: [+px.toFixed(4), +py.toFixed(4), +pz.toFixed(4)],
      rotation: [
        +(proxy.rotation.x * RAD2DEG).toFixed(2),
        +(proxy.rotation.y * RAD2DEG).toFixed(2),
        +(proxy.rotation.z * RAD2DEG).toFixed(2),
      ],
      scale: [
        +proxy.scale.x.toFixed(4),
        +proxy.scale.y.toFixed(4),
        +proxy.scale.z.toFixed(4),
      ],
      pivot: "com",
    });
  }, [gizmoProxy, onTransformChange, transform]);

  const handleDraggingChanged = useCallback(
    (e: THREE.Event & { value: boolean }) => {
      isDraggingRef.current = e.value;
      if (e.value) {
        // Freeze worldCoM - P so translates stay stable while dragging.
        worldComOffsetRef.current.set(
          gizmoProxy.position.x - transform.position[0],
          gizmoProxy.position.y - transform.position[1],
          gizmoProxy.position.z - transform.position[2],
        );
      } else {
        readTransformFromGizmo();
      }
    },
    [gizmoProxy, transform.position, readTransformFromGizmo],
  );

  useEffect(() => {
    const tc = tcRef.current;
    if (!tc) return;
    tc.addEventListener("dragging-changed", handleDraggingChanged);
    return () => tc.removeEventListener("dragging-changed", handleDraggingChanged);
  }, [gizmoReady, isSelected, handleDraggingChanged]);

  useFrame(() => {
    if (isDraggingRef.current) {
      // Live-update bind matrix from gizmo proxy while dragging.
      const proxy = gizmoProxy;
      const live: EquipTransform = {
        ...transform,
        position: [
          proxy.position.x - worldComOffsetRef.current.x,
          proxy.position.y - worldComOffsetRef.current.y,
          proxy.position.z - worldComOffsetRef.current.z,
        ],
        rotation: [
          proxy.rotation.x * RAD2DEG,
          proxy.rotation.y * RAD2DEG,
          proxy.rotation.z * RAD2DEG,
        ],
        scale: [
          proxy.scale.x,
          proxy.scale.y,
          proxy.scale.z,
        ],
        pivot: "com",
      };
      applyBindFromTransform(live);
      return;
    }

    applyBindFromTransform(transform);

    // Keep gizmo at the skinned center of mass; rotation/scale mirror EquipTransform.
    const sm = slot.skinnedMeshes[0];
    if (sm?.skeleton && slot.centroid) {
      skinnedCentroidWorld(sm, slot.centroid, _offsetMatrix, _worldCom);
      gizmoProxy.position.copy(_worldCom);
      worldComOffsetRef.current.set(
        _worldCom.x - transform.position[0],
        _worldCom.y - transform.position[1],
        _worldCom.z - transform.position[2],
      );
    } else {
      gizmoProxy.position.set(...transform.position);
      worldComOffsetRef.current.set(0, 0, 0);
    }
    gizmoProxy.rotation.set(
      transform.rotation[0] * DEG2RAD,
      transform.rotation[1] * DEG2RAD,
      transform.rotation[2] * DEG2RAD,
    );
    gizmoProxy.scale.set(
      transform.scale[0],
      transform.scale[1],
      transform.scale[2],
    );
  });

  const handleClick = useCallback(
    (e: ThreeEvent<MouseEvent>) => {
      e.stopPropagation();
      onSelect();
    },
    [onSelect],
  );

  return (
    <>
      <group
        onClick={handleClick}
        onPointerOver={(e) => {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "default";
        }}
      >
        <primitive object={slot.scene} />
      </group>
      <primitive object={gizmoProxy} />
      {isSelected && gizmoReady && (
        <TransformControls
          ref={tcRef}
          object={gizmoProxy}
          mode={gizmoMode}
          size={0.5}
          onChange={() => {
            if (isDraggingRef.current) {
              readTransformFromGizmo();
            }
          }}
        />
      )}
    </>
  );
}

export default function EquipmentMeshRenderer({
  slotIds,
  slots,
  equipState,
  effectiveState,
  playerRef,
  characterModel,
  selectedSlot,
  onSelectSlot,
  equipTransforms,
  equipGizmoMode,
  onEquipTransformChange,
  slotTextures,
  skinTransferRequest,
  onSkinTransferDone,
}: EquipmentMeshRendererProps) {
  const groupRef = useRef<THREE.Group>(null);
  const [loadedSlots, setLoadedSlots] = useState<Map<string, LoadedSlot>>(
    new Map(),
  );
  const loadingRef = useRef<Set<string>>(new Set());
  const boundRef = useRef<Set<string>>(new Set());

  const equipmentSlotIds = useMemo(
    () => slotIds.filter((id) => !BODY_SLOT_IDS.has(id)),
    [slotIds],
  );

  useEffect(() => {
    for (const id of equipmentSlotIds) {
      if (!effectiveState[id]) {
        boundRef.current.delete(id);
      }
    }
  }, [equipmentSlotIds, effectiveState]);

  const slotMap = useMemo(
    () => new Map(slots.map((s) => [s.id, s])),
    [slots],
  );

  const charBoneInverseMap = useMemo(() => {
    if (!characterModel) return new Map<string, THREE.Matrix4>();
    return characterModel.boneRestWorldInverses;
  }, [characterModel]);

  const skinSlots = useMemo(
    () => slots.filter((s) => s.mesh_type === "skin_color" || s.mesh_type === "skin_texture"),
    [slots],
  );
  const skinTextureSlotIds = useMemo(
    () => new Set(skinSlots.map((s) => s.id)),
    [skinSlots],
  );

  const originalBodyMatsRef = useRef<Map<THREE.SkinnedMesh, THREE.Material | THREE.Material[]>>(new Map());

  useEffect(() => {
    if (!characterModel) return;
    const activeSkinSlot = skinSlots.find((s) => effectiveState[s.id]);

    if (activeSkinSlot) {
      if (activeSkinSlot.mesh_type === "skin_color" && activeSkinSlot.color) {
        const color = new THREE.Color(activeSkinSlot.color);
        for (const sm of characterModel.skinnedMeshes) {
          if (!originalBodyMatsRef.current.has(sm)) {
            originalBodyMatsRef.current.set(sm, sm.material);
          }
          const mats = Array.isArray(sm.material) ? sm.material : [sm.material];
          for (const m of mats) {
            if ((m as any).isMeshStandardMaterial) {
              const stdMat = m as THREE.MeshStandardMaterial;
              stdMat.color.copy(color);
              stdMat.map = null;
              stdMat.roughness = 0.7;
              stdMat.metalness = 0.0;
              stdMat.needsUpdate = true;
            }
          }
        }
      } else if (activeSkinSlot.mesh_type === "skin_texture" && activeSkinSlot.url) {
        loader.load(activeSkinSlot.url + "?v=" + Date.now(), (gltf) => {
          let skinTexture: THREE.Texture | null = null;
          gltf.scene.traverse((child) => {
            if (skinTexture) return;
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;
              const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
              for (const m of mats) {
                if ((m as any).isMeshStandardMaterial && (m as THREE.MeshStandardMaterial).map) {
                  skinTexture = (m as THREE.MeshStandardMaterial).map;
                  break;
                }
              }
            }
          });
          if (!skinTexture) return;
          for (const sm of characterModel.skinnedMeshes) {
            if (!originalBodyMatsRef.current.has(sm)) {
              originalBodyMatsRef.current.set(sm, sm.material);
            }
            const mats = Array.isArray(sm.material) ? sm.material : [sm.material];
            for (const m of mats) {
              if ((m as any).isMeshStandardMaterial) {
                const stdMat = m as THREE.MeshStandardMaterial;
                stdMat.map = skinTexture;
                stdMat.needsUpdate = true;
              }
            }
          }
        });
      }
    } else {
      for (const [sm, origMat] of originalBodyMatsRef.current) {
        sm.material = origMat;
      }
      originalBodyMatsRef.current.clear();
    }
  }, [characterModel, skinSlots, effectiveState]);

  useEffect(() => {
    const enabledSlots = equipmentSlotIds.filter((id) => equipState[id] && !skinTextureSlotIds.has(id));
    const toLoad = enabledSlots.filter(
      (id) => !slotCache.has(id) && !loadingRef.current.has(id),
    );

    if (toLoad.length === 0) return;

    let cancelled = false;
    for (const slotId of toLoad) {
      slotCache.delete(slotId);
      correctedSlots.delete(slotId);
      loadingRef.current.add(slotId);
      const slot = slotMap.get(slotId);
      const isExternal = !!slot?.url;
      const baseUrl = slot?.url ?? `/equipment/${slotId}.glb`;
      const loadUrl = `${baseUrl}${baseUrl.includes("?") ? "&" : "?"}v=${Date.now()}`;
      loader.load(
        loadUrl,
        (gltf) => {
          loadingRef.current.delete(slotId);

          const scene = gltf.scene;
          scene.visible = true;

          let skinnedMeshes = findSkinnedMeshes(scene);
          const isImported = slot?.source === "imported";
          let needsAutoSkin = false;

          const geoCorrection = isExternal
            ? _yupToZupCorrection
            : _equipFacingCorrection;

          const color = SLOT_COLORS[slotId] ?? "#94a3b8";
          const origMats = new Map<THREE.Mesh, THREE.Material>();
          scene.traverse((child) => {
            if ((child as THREE.Mesh).isMesh) {
              const mesh = child as THREE.Mesh;

              if (!isImported) {
                mesh.geometry.applyMatrix4(geoCorrection);
              }

              if (INFLATE_SLOTS.has(slotId)) {
                smoothOutlierVertices(mesh.geometry, 0.05);
                inflateGeometry(mesh.geometry, INFLATE_AMOUNT);
                if ((mesh as THREE.SkinnedMesh).isSkinnedMesh) {
                  extendFingertips(mesh.geometry, (mesh as THREE.SkinnedMesh).skeleton, FINGERTIP_EXTEND);
                }
              }

              const isMultiMaterial = Array.isArray(mesh.material);
              const materials: THREE.MeshStandardMaterial[] = isMultiMaterial
                ? (mesh.material as THREE.Material[]).filter((m): m is THREE.MeshStandardMaterial => (m as any).isMeshStandardMaterial)
                : ((mesh.material as any)?.isMeshStandardMaterial ? [mesh.material as THREE.MeshStandardMaterial] : []);
              const hasBakedTexture = materials.length > 0 && materials.some(m => m.map != null);

              const slotLayer = SLOT_RENDER_ORDER[slotId] ?? 2;
              const polyOffset = LAYER_POLYGON_OFFSET[slotLayer] ?? -1;

              for (const m of materials) {
                if (hasBakedTexture) {
                  m.side = THREE.DoubleSide;
                  m.transparent = false;
                  m.opacity = 1.0;
                  m.alphaTest = 0;
                  m.alphaMap = null;
                  m.depthWrite = true;
                  m.depthTest = true;
                  m.polygonOffset = true;
                  m.polygonOffsetFactor = polyOffset;
                  m.polygonOffsetUnits = polyOffset;
                  m.blending = THREE.NormalBlending;
                  if ((m as any).transmission !== undefined) (m as any).transmission = 0;
                  if ((m as any).transmissionMap !== undefined) (m as any).transmissionMap = null;
                  if ((m as any).ior !== undefined) (m as any).ior = 1.5;
                  if ((m as any).thickness !== undefined) (m as any).thickness = 0;
                  if ((m as any).thicknessMap !== undefined) (m as any).thicknessMap = null;
                  if ((m as any).attenuationDistance !== undefined) (m as any).attenuationDistance = Infinity;
                  m.needsUpdate = true;
                }
              }
              if (hasBakedTexture) {
                origMats.set(mesh, (isMultiMaterial ? (mesh.material as THREE.Material[])[0] : mesh.material) as THREE.Material);
              } else if (!isImported) {
                mesh.material = new THREE.MeshStandardMaterial({
                  color,
                  transparent: false,
                  opacity: 1.0,
                  side: THREE.DoubleSide,
                  depthWrite: true,
                  polygonOffset: true,
                  polygonOffsetFactor: polyOffset,
                  polygonOffsetUnits: polyOffset,
                });
              }

              const matForStencil = isMultiMaterial
                ? (mesh.material as THREE.Material[])
                : [mesh.material as THREE.Material];
              for (const sm of matForStencil) {
                if (STENCIL_WRITE_SLOTS.has(slotId)) {
                  (sm as any).stencilWrite = true;
                  (sm as any).stencilRef = 1;
                  (sm as any).stencilFunc = THREE.AlwaysStencilFunc;
                  (sm as any).stencilZPass = THREE.ReplaceStencilOp;
                  (sm as any).stencilZFail = THREE.KeepStencilOp;
                  (sm as any).stencilFail = THREE.KeepStencilOp;
                }
              }
              if (!hasBakedTexture && !isImported) {
                origMats.set(mesh, mesh.material as THREE.Material);
              } else if (isImported) {
                origMats.set(mesh, mesh.material as THREE.Material);
              }
              mesh.frustumCulled = false;
              const slotRenderOrder = SLOT_RENDER_ORDER[slotId] ?? 0;
              mesh.renderOrder = slotRenderOrder;
            }
          });

          if (skinnedMeshes.length === 0) {
            const regularMeshes = findRegularMeshes(scene);
            if (regularMeshes.length > 0 && slot) {
              if (isImported) {
                scene.rotation.set(Math.PI / 2, 0, 0);
                scene.updateMatrixWorld(true);
              }
              scaleToSlotBounds(scene, slot.bounds);
              needsAutoSkin = true;
            }
          }

          if (slotId.startsWith("green_ranged") || slotId.endsWith("_armor_gloves")) {
            console.log(`[EquipDbg] ${slotId}: skinnedMeshes=${skinnedMeshes.length}, needsAutoSkin=${needsAutoSkin}, isExternal=${isExternal}`);
            scene.traverse((child) => {
              if ((child as THREE.Mesh).isMesh) {
                const m = child as THREE.Mesh;
                const geo = m.geometry;
                const pos = geo.getAttribute("position") as THREE.BufferAttribute;
                const sw = geo.getAttribute("skinWeight") as THREE.BufferAttribute;
                const si = geo.getAttribute("skinIndex") as THREE.BufferAttribute;
                const isSkinned = (m as THREE.SkinnedMesh).isSkinnedMesh;
                const matArr = Array.isArray(m.material) ? m.material : [m.material];
                const hasTex = matArr.some((mt: any) => mt?.map != null);
                console.log(`[EquipDbg]   mesh "${m.name}" skinned=${isSkinned} verts=${pos?.count} hasWeights=${!!sw} hasIdx=${!!si} hasTex=${hasTex} visible=${m.visible} parent=${m.parent?.name}`);
                if (pos) {
                  const box = new THREE.Box3();
                  const v = new THREE.Vector3();
                  for (let i = 0; i < pos.count; i++) {
                    v.set(pos.getX(i), pos.getY(i), pos.getZ(i));
                    box.expandByPoint(v);
                  }
                  console.log(`[EquipDbg]   bounds: min=(${box.min.x.toFixed(3)},${box.min.y.toFixed(3)},${box.min.z.toFixed(3)}) max=(${box.max.x.toFixed(3)},${box.max.y.toFixed(3)},${box.max.z.toFixed(3)})`);
                }
                if (isSkinned) {
                  const sk = (m as THREE.SkinnedMesh).skeleton;
                  console.log(`[EquipDbg]   skeleton: bones=${sk?.bones.length} inverses=${sk?.boneInverses.length}`);
                  // Sample first 5 bone names so we can compare to the character's bone-name format.
                  const boneNames = sk?.bones.slice(0, 5).map(b => b.name).join(", ");
                  console.log(`[EquipDbg]   bone names (first 5): ${boneNames}`);
                }
              }
            });
          }

          const loaded: LoadedSlot = { scene, skinnedMeshes, needsAutoSkin, originalMaterials: origMats };
          slotCache.set(slotId, loaded);
          if (!cancelled) {
            setLoadedSlots((prev) => {
              const next = new Map(prev);
              next.set(slotId, loaded);
              return next;
            });
          }
        },
        undefined,
        (err) => {
          loadingRef.current.delete(slotId);
          console.warn(`Failed to load equipment mesh: ${loadUrl}`, err);
        },
      );
    }

    return () => {
      cancelled = true;
    };
  }, [equipmentSlotIds, equipState, slotMap]);

  useEffect(() => {
    if (!skinTransferRequest) return;
    const { targetSlotId, referenceSlotId } = skinTransferRequest;
    const targetDef = slotMap.get(targetSlotId);
    const refDef = slotMap.get(referenceSlotId);
    if (!targetDef || !refDef) {
      console.warn(`[SkinTransfer] Missing slot definition`, { targetSlotId, referenceSlotId });
      onSkinTransferDone?.();
      return;
    }

    const targetUrl = targetDef.url ?? `/equipment/${targetSlotId}.glb`;
    const refUrl = refDef.url ?? `/equipment/${referenceSlotId}.glb`;
    const geoCorrection = _yupToZupCorrection;

    console.log(`[SkinTransfer] Target: "${targetDef.name}" (${targetUrl})`);
    console.log(`[SkinTransfer] Reference: "${refDef.name}" (${refUrl})`);

    let loadsDone = 0;
    let targetGltf: { scene: THREE.Group } | null = null;
    let refGltf: { scene: THREE.Group } | null = null;

    const tryFinish = () => {
      loadsDone++;
      if (loadsDone < 2 || !targetGltf || !refGltf) return;

      const player = playerRef.current;
      const animBones = player?.boneObjMap;
      if (!animBones || animBones.size === 0) {
        console.warn(`[SkinTransfer] Animation bones not ready yet.`);
        onSkinTransferDone?.();
        return;
      }

      const tScene = targetGltf.scene;
      const rScene = refGltf.scene;
      tScene.visible = true;

      // --- Process reference: keep its SkinnedMesh with skeleton intact ---
      rScene.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          (child as THREE.Mesh).geometry.applyMatrix4(geoCorrection);
        }
      });
      const refSkinnedMeshes = findSkinnedMeshes(rScene);
      if (refSkinnedMeshes.length === 0) {
        console.warn(`[SkinTransfer] Reference has no skinned meshes. Cannot transfer.`);
        onSkinTransferDone?.();
        return;
      }
      const refSM = refSkinnedMeshes[0];
      console.log(
        `[SkinTransfer] Reference skinned mesh: "${refSM.name}", ` +
        `verts=${refSM.geometry.getAttribute("position").count}, ` +
        `bones=${refSM.skeleton.bones.length}`,
      );

      // Bake reference skeleton to get world-space vertex positions for matching
      refSM.updateMatrixWorld(true);
      const refGeo = refSM.geometry;
      const refPos = refGeo.getAttribute("position") as THREE.BufferAttribute;
      const refSkinIdx = refGeo.getAttribute("skinIndex") as THREE.BufferAttribute;
      const refSkinWt = refGeo.getAttribute("skinWeight") as THREE.BufferAttribute;
      const refWorldMatrix = refSM.matrixWorld;

      const refWorldVerts: THREE.Vector3[] = [];
      for (let i = 0; i < refPos.count; i++) {
        const v = new THREE.Vector3(refPos.getX(i), refPos.getY(i), refPos.getZ(i));
        v.applyMatrix4(refWorldMatrix);
        refWorldVerts.push(v);
      }

      // --- Process target: strip skeleton, apply geo correction ---
      const tSkinnedToStrip = findSkinnedMeshes(tScene);
      for (const sm of tSkinnedToStrip) {
        sm.geometry.applyMatrix4(geoCorrection);
        const reg = new THREE.Mesh(sm.geometry, sm.material);
        reg.name = sm.name;
        reg.frustumCulled = false;
        const p = sm.parent;
        if (p) { p.add(reg); p.remove(sm); }
      }
      const tRegular = findRegularMeshes(tScene);
      for (const mesh of tRegular) {
        if (!tSkinnedToStrip.some((sm) => sm.name === mesh.name)) {
          mesh.geometry.applyMatrix4(geoCorrection);
        }
      }

      // Bake target's world transforms into geometry
      tScene.updateMatrixWorld(true);
      for (const mesh of tRegular) {
        mesh.updateMatrixWorld(true);
        mesh.geometry.applyMatrix4(mesh.matrixWorld);
        mesh.position.set(0, 0, 0);
        mesh.rotation.set(0, 0, 0);
        mesh.scale.set(1, 1, 1);
        mesh.updateMatrix();
      }
      tScene.traverse((c) => {
        c.position.set(0, 0, 0);
        c.rotation.set(0, 0, 0);
        c.scale.set(1, 1, 1);
        c.updateMatrix();
      });
      tScene.updateMatrixWorld(true);

      if (tRegular.length === 0) {
        console.warn(`[SkinTransfer] Target has no regular meshes after strip.`);
        onSkinTransferDone?.();
        return;
      }

      const targetMesh = tRegular[0];
      const tPos = targetMesh.geometry.getAttribute("position") as THREE.BufferAttribute;

      console.log(
        `[SkinTransfer] Target mesh: "${targetMesh.name}", verts=${tPos.count}`,
      );

      // --- Per-axis scale + translate to match reference bounding box ---
      const refBox = new THREE.Box3();
      for (const v of refWorldVerts) refBox.expandByPoint(v);
      const refSize = new THREE.Vector3();
      const refCenter = new THREE.Vector3();
      refBox.getSize(refSize);
      refBox.getCenter(refCenter);

      const tBox = new THREE.Box3().setFromObject(tScene);
      const tSize = new THREE.Vector3();
      const tCenter = new THREE.Vector3();
      tBox.getSize(tSize);
      tBox.getCenter(tCenter);

      const sx = tSize.x > 0.0001 ? refSize.x / tSize.x : 1;
      const sy = tSize.y > 0.0001 ? refSize.y / tSize.y : 1;
      const sz = tSize.z > 0.0001 ? refSize.z / tSize.z : 1;

      console.log(
        `[SkinTransfer] Scale: [${sx.toFixed(4)}, ${sy.toFixed(4)}, ${sz.toFixed(4)}]`,
      );
      console.log(
        `[SkinTransfer] Ref bounds: size=[${refSize.x.toFixed(4)},${refSize.y.toFixed(4)},${refSize.z.toFixed(4)}] ` +
        `center=[${refCenter.x.toFixed(4)},${refCenter.y.toFixed(4)},${refCenter.z.toFixed(4)}]`,
      );

      // Apply per-axis scale and reposition to all target meshes
      for (const mesh of findRegularMeshes(tScene)) {
        const geo = mesh.geometry;
        const pos = geo.getAttribute("position") as THREE.BufferAttribute;
        for (let i = 0; i < pos.count; i++) {
          const x = (pos.getX(i) - tCenter.x) * sx + refCenter.x;
          const y = (pos.getY(i) - tCenter.y) * sy + refCenter.y;
          const z = (pos.getZ(i) - tCenter.z) * sz + refCenter.z;
          pos.setXYZ(i, x, y, z);
        }
        pos.needsUpdate = true;
        geo.computeBoundingBox();
        geo.computeBoundingSphere();
      }

      // --- Nearest-vertex weight transfer ---
      const tGeo = targetMesh.geometry;
      const tPosAttr = tGeo.getAttribute("position") as THREE.BufferAttribute;
      const vertCount = tPosAttr.count;
      const newSkinIndices = new Float32Array(vertCount * 4);
      const newSkinWeights = new Float32Array(vertCount * 4);

      let totalDist = 0;
      let maxDist = 0;
      const refVertCount = refWorldVerts.length;

      for (let vi = 0; vi < vertCount; vi++) {
        const tv = new THREE.Vector3(
          tPosAttr.getX(vi), tPosAttr.getY(vi), tPosAttr.getZ(vi),
        );

        let bestIdx = 0;
        let bestDist = Infinity;
        for (let ri = 0; ri < refVertCount; ri++) {
          const d = tv.distanceToSquared(refWorldVerts[ri]);
          if (d < bestDist) {
            bestDist = d;
            bestIdx = ri;
          }
        }
        const dist = Math.sqrt(bestDist);
        totalDist += dist;
        if (dist > maxDist) maxDist = dist;

        const base = vi * 4;
        const refSkinIdxArr = refSkinIdx.array as Float32Array;
        const refSkinWtArr = refSkinWt.array as Float32Array;
        const refBase = bestIdx * 4;
        for (let j = 0; j < 4; j++) {
          newSkinIndices[base + j] = refSkinIdxArr[refBase + j];
          newSkinWeights[base + j] = refSkinWtArr[refBase + j];
        }
      }

      console.log(
        `[SkinTransfer] Weight transfer: avgDist=${(totalDist / vertCount).toFixed(5)}, ` +
        `maxDist=${maxDist.toFixed(5)}`,
      );

      tGeo.setAttribute("skinIndex", new THREE.BufferAttribute(newSkinIndices, 4));
      tGeo.setAttribute("skinWeight", new THREE.BufferAttribute(newSkinWeights, 4));

      // --- Build SkinnedMesh using the reference's skeleton ---
      const refOldSk = refSM.skeleton;
      const newBones: THREE.Bone[] = [];
      const newInverses: THREE.Matrix4[] = [];

      for (let i = 0; i < refOldSk.bones.length; i++) {
        const rawName = refOldSk.bones[i].name;
        const boneName = BONE_NAME_REMAP[rawName] ?? rawName;
        const animBone = animBones.get(boneName);
        const charInv = charBoneInverseMap.get(boneName);
        if (animBone && charInv) {
          newBones.push(animBone);
          newInverses.push(charInv.clone());
        } else {
          newBones.push(refOldSk.bones[i] as THREE.Bone);
          newInverses.push(refOldSk.boneInverses[i].clone());
        }
      }

      // Preserve materials from target
      const origMats = new Map<THREE.Mesh, THREE.Material>();
      const isMultiMat = Array.isArray(targetMesh.material);
      const matList: THREE.MeshStandardMaterial[] = isMultiMat
        ? (targetMesh.material as THREE.Material[]).filter(
            (m): m is THREE.MeshStandardMaterial => (m as any).isMeshStandardMaterial,
          )
        : (targetMesh.material as any)?.isMeshStandardMaterial
          ? [targetMesh.material as THREE.MeshStandardMaterial]
          : [];
      const hasBakedTexture = matList.length > 0 && matList.some((m) => m.map != null);
      for (const m of matList) {
        if (hasBakedTexture) {
          m.side = THREE.DoubleSide;
          m.transparent = false;
          m.opacity = 1.0;
          m.depthWrite = true;
          m.needsUpdate = true;
        }
      }

      const skinnedMesh = new THREE.SkinnedMesh(tGeo, targetMesh.material);
      skinnedMesh.name = targetMesh.name;
      skinnedMesh.frustumCulled = false;
      skinnedMesh.renderOrder = SLOT_RENDER_ORDER[targetSlotId] ?? 0;

      const newSkeleton = new THREE.Skeleton(newBones, newInverses);
      skinnedMesh.bind(newSkeleton, _identityMatrix);

      origMats.set(skinnedMesh, (isMultiMat
        ? (targetMesh.material as THREE.Material[])[0]
        : targetMesh.material) as THREE.Material);

      // Replace the target mesh in the scene
      const parent = targetMesh.parent ?? tScene;
      parent.add(skinnedMesh);
      parent.remove(targetMesh);

      console.log(
        `[SkinTransfer] Created SkinnedMesh with ${newBones.length} bones, ` +
        `${vertCount} verts. Transfer complete.`,
      );

      // --- Install into slotCache ---
      const loaded: LoadedSlot = {
        scene: tScene,
        skinnedMeshes: [skinnedMesh],
        needsAutoSkin: false,
        originalMaterials: origMats,
      };

      const oldSlot = slotCache.get(targetSlotId);
      if (oldSlot) {
        oldSlot.scene.visible = false;
        oldSlot.scene.traverse((c) => {
          if ((c as THREE.Mesh).isMesh) (c as THREE.Mesh).geometry.dispose();
        });
      }

      slotCache.set(targetSlotId, loaded);
      boundRef.current.add(targetSlotId);
      correctedSlots.delete(targetSlotId);

      setLoadedSlots((prev) => {
        const next = new Map(prev);
        next.set(targetSlotId, loaded);
        return next;
      });

      // Clean up reference
      rScene.traverse((c) => {
        if ((c as THREE.Mesh).isMesh) (c as THREE.Mesh).geometry.dispose();
      });

      onSkinTransferDone?.(targetSlotId);
    };

    loader.load(
      `${targetUrl}?v=${Date.now()}`,
      (gltf) => { targetGltf = { scene: gltf.scene }; tryFinish(); },
      undefined,
      (err) => {
        console.warn(`[SkinTransfer] Failed to load target`, err);
        onSkinTransferDone?.();
      },
    );
    loader.load(
      `${refUrl}?v=${Date.now()}`,
      (gltf) => { refGltf = { scene: gltf.scene }; tryFinish(); },
      undefined,
      (err) => {
        console.warn(`[SkinTransfer] Failed to load reference`, err);
        onSkinTransferDone?.();
      },
    );
  }, [skinTransferRequest, slotMap, charBoneInverseMap, onSkinTransferDone]);

  useEffect(() => {
    if (!slotTextures) return;
    for (const [slotId, slot] of slotCache) {
      const texUrl = slotTextures[slotId];
      slot.scene.traverse((child) => {
        if (!(child as THREE.Mesh).isMesh) return;
        const mesh = child as THREE.Mesh;

        if (texUrl) {
          let tex = textureCache.get(texUrl);
          if (!tex) {
            tex = textureLoader.load(texUrl);
            tex.colorSpace = THREE.SRGBColorSpace;
            tex.wrapS = THREE.RepeatWrapping;
            tex.wrapT = THREE.RepeatWrapping;
            tex.magFilter = THREE.LinearFilter;
            tex.minFilter = THREE.LinearMipmapLinearFilter;
            textureCache.set(texUrl, tex);
          }
          const triMat = createTriplanarMaterial(tex, 0.8, 2.0);
          triMat.customProgramCacheKey = () => "triplanar_" + slotId;
          mesh.material = triMat;
        } else {
          const origMat = slot.originalMaterials?.get(mesh);
          if (origMat) {
            mesh.material = origMat;
          } else {
            const color = SLOT_COLORS[slotId] ?? "#94a3b8";
            const layer = SLOT_RENDER_ORDER[slotId] ?? 2;
            const po = LAYER_POLYGON_OFFSET[layer] ?? -1;
            mesh.material = new THREE.MeshStandardMaterial({
              color,
              transparent: false,
              opacity: 1.0,
              side: THREE.FrontSide,
              depthWrite: true,
              polygonOffset: true,
              polygonOffsetFactor: po,
              polygonOffsetUnits: po,
            });
          }
        }
      });
    }
  }, [slotTextures]);

  useFrame(() => {
    const player = playerRef.current;
    if (!player) return;
    const animBones = player.boneObjMap;
    if (!animBones || animBones.size === 0) return;

    for (const [slotId, slot] of slotCache) {
      if (BODY_SLOT_IDS.has(slotId)) continue;
      if (!effectiveState[slotId]) continue;

      if (!boundRef.current.has(slotId)) {
        if (slot.needsAutoSkin && slot.skinnedMeshes.length === 0) {
          const slotDef = slotMap.get(slotId);
          if (slotDef) {
            const regularMeshes = findRegularMeshes(slot.scene);
            for (const mesh of regularMeshes) {
              const sm = autoSkinMesh(
                mesh, slotDef.bones, animBones, charBoneInverseMap, slotDef.bounds,
              );
              if (sm) {
                const parent = mesh.parent;
                if (parent) {
                  parent.add(sm);
                  parent.remove(mesh);
                }
                slot.skinnedMeshes.push(sm);
                if (slot.originalMaterials) {
                  const origMat = slot.originalMaterials.get(mesh);
                  if (origMat) {
                    slot.originalMaterials.delete(mesh);
                    slot.originalMaterials.set(sm, origMat);
                  }
                }
              }
            }
            slot.needsAutoSkin = false;
          }
        }

        if (slot.skinnedMeshes.length > 0) {
          bindSlotSkeleton(slot, animBones, charBoneInverseMap, slotId);
          if (slotId.startsWith("green_ranged") || slotId.endsWith("_armor_gloves")) {
            for (const sm of slot.skinnedMeshes) {
              console.log(`[EquipDbg] ${slotId} after bind: bones=${sm.skeleton?.bones.length}, visible=${sm.visible}, bindMatrix=[${sm.bindMatrix.elements.slice(0,4).map((v: number) => v.toFixed(3))}...]`);
              const sw = sm.geometry.getAttribute("skinWeight") as THREE.BufferAttribute;
              if (sw) {
                let zeroCount = 0;
                for (let i = 0; i < sw.count; i++) {
                  const total = sw.getX(i) + sw.getY(i) + sw.getZ(i) + sw.getW(i);
                  if (total < 0.001) zeroCount++;
                }
                console.log(`[EquipDbg]   skinWeight: ${sw.count} verts, ${zeroCount} zero-weight`);
              }
              // Check how many bones in the skin map back to the character's animBones vs stay detached.
              const sk = sm.skeleton;
              if (sk) {
                let matched = 0, unmatched = 0;
                const sampleUnmatched: string[] = [];
                for (const b of sk.bones) {
                  const remapped = (BONE_NAME_REMAP as any)[b.name] ?? b.name;
                  if (animBones.has(remapped)) {
                    matched++;
                  } else {
                    unmatched++;
                    if (sampleUnmatched.length < 5) sampleUnmatched.push(`${b.name} -> ${remapped}`);
                  }
                }
                console.log(`[EquipDbg]   skeleton rebind: ${matched} bones matched character, ${unmatched} NOT matched`);
                if (unmatched > 0) console.log(`[EquipDbg]   unmatched samples: ${sampleUnmatched.join(" | ")}`);
                // Verify a sample mesh vert at rest gives an expected world transform via this skeleton.
                const v0 = new THREE.Vector3(sm.geometry.getAttribute("position").getX(0),
                                              sm.geometry.getAttribute("position").getY(0),
                                              sm.geometry.getAttribute("position").getZ(0));
                console.log(`[EquipDbg]   first vert (rest-pose, local): (${v0.x.toFixed(3)}, ${v0.y.toFixed(3)}, ${v0.z.toFixed(3)})`);
              }
            }
          }
        }
        slot.scene.visible = true;
        boundRef.current.add(slotId);
      }

    }
  });

  const identityTransform = useMemo<EquipTransform>(
    () => ({
      position: [0, 0, 0],
      rotation: [0, 0, 0],
      scale: [1, 1, 1],
      eyeSeparation: 0,
      eyeRotationL: [0, 0, 0],
      eyeRotationR: [0, 0, 0],
      pivot: "com",
    }),
    [],
  );

  return (
    <group ref={groupRef} name="equipment-meshes">
      {equipmentSlotIds.map((id) => {
        if (!effectiveState[id]) return null;
        if (skinTextureSlotIds.has(id)) return null;
        const slot = slotCache.get(id) ?? loadedSlots.get(id);
        if (!slot) return null;
        const slotDef = slotMap.get(id);
        const fallback = normalizeEquipTransform(
          slotDef?.default_transform ?? identityTransform,
        );
        return (
          <EquipmentSlotWrapper
            key={id}
            slotId={id}
            slot={slot}
            isSelected={selectedSlot === id}
            onSelect={() => onSelectSlot(id)}
            transform={normalizeEquipTransform(equipTransforms[id] ?? fallback)}
            gizmoMode={equipGizmoMode}
            onTransformChange={(t) => onEquipTransformChange(id, t)}
          />
        );
      })}
    </group>
  );
}
