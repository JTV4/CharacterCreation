import * as THREE from 'three';

/** Automatically generated hat surface heights in unposed, Y-up metres. */
export interface HatHairFit { size: number; bounds: readonly number[]; heights: string }
interface MaskUniforms {
  hatHairEnabled: { value: number };
  hatHairCoverage: { value: THREE.DataTexture };
  hatHairBounds: { value: THREE.Vector4 };
  hatHairScale: { value: number };
}
const masks = new WeakMap<THREE.Material, MaskUniforms>();
const textures = new WeakMap<HatHairFit, THREE.DataTexture>();

function coverageTexture(fit: HatHairFit): THREE.DataTexture {
  let texture = textures.get(fit);
  if (!texture) {
    const bytes = atob(fit.heights);
    const data = new Float32Array(fit.size * fit.size);
    for (let i = 0; i < data.length; i++) {
      const height = bytes.charCodeAt(i * 2) | (bytes.charCodeAt(i * 2 + 1) << 8);
      data[i] = height ? height / 1000 : 1e6;
    }
    texture = new THREE.DataTexture(data, fit.size, fit.size, THREE.RedFormat, THREE.FloatType);
    texture.minFilter = texture.magFilter = THREE.NearestFilter;
    texture.generateMipmaps = false;
    texture.needsUpdate = true;
    textures.set(fit, texture);
  }
  return texture;
}

/**
 * Tuck hair beneath the actual hat surface. Outside its footprint hair remains.
 * Rest coordinates keep coverage attached during head animation. All hairstyles
 * share this operation; instance-owned materials preserve other players' hair.
 */
export function setHatHairMask(root: THREE.Object3D, fit: HatHairFit | undefined, geometryScale = 1): void {
  root.traverse((object) => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh) return;
    for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) {
      if (!(material as THREE.MeshStandardMaterial).isMeshStandardMaterial) continue;
      let uniforms = masks.get(material);
      if (!uniforms && fit) {
        uniforms = {
          hatHairEnabled: { value: 1 },
          hatHairCoverage: { value: coverageTexture(fit) },
          hatHairBounds: { value: new THREE.Vector4() },
          hatHairScale: { value: geometryScale },
        };
        masks.set(material, uniforms);
        const originalCompile = material.onBeforeCompile;
        const originalKey = material.customProgramCacheKey();
        const owned = uniforms;
        material.onBeforeCompile = (shader, renderer) => {
          originalCompile.call(material, shader, renderer);
          Object.assign(shader.uniforms, owned);
          shader.vertexShader = 'varying vec3 vHatHairRest;\nuniform float hatHairScale;\n' + shader.vertexShader;
          shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>',
            '#include <begin_vertex>\nvHatHairRest = position / hatHairScale;');
          shader.fragmentShader = 'varying vec3 vHatHairRest;\nuniform float hatHairEnabled;\nuniform sampler2D hatHairCoverage;\nuniform vec4 hatHairBounds;\n' + shader.fragmentShader;
          shader.fragmentShader = shader.fragmentShader.replace('#include <clipping_planes_fragment>',
            `#include <clipping_planes_fragment>
             if (hatHairEnabled > 0.5) {
               vec2 hatUV = (vHatHairRest.xz - hatHairBounds.xy) / hatHairBounds.zw;
               if (all(greaterThanEqual(hatUV, vec2(0.0))) && all(lessThanEqual(hatUV, vec2(1.0)))) {
                 float surfaceHeight = texture2D(hatHairCoverage, hatUV).r;
                 if (vHatHairRest.y >= surfaceHeight - 0.002) discard;
               }
             }`);
        };
        material.customProgramCacheKey = () => originalKey + '|hat-hair-coverage-v1';
        material.needsUpdate = true;
      }
      if (uniforms) {
        uniforms.hatHairEnabled.value = fit ? 1 : 0;
        if (fit) {
          uniforms.hatHairCoverage.value = coverageTexture(fit);
          uniforms.hatHairBounds.value.fromArray(fit.bounds);
        }
        uniforms.hatHairScale.value = geometryScale;
      }
    }
  });
}
