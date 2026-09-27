import * as THREE from 'three';

/** A bounded, single-draw glint layer follows the cape's skinned embroidery. */
export function createCapeSparkles(root: THREE.Object3D) {
  const materials = new Set<THREE.MeshStandardMaterial>();
  const anchors: { mesh: THREE.SkinnedMesh; vertex: number }[] = [];
  root.traverse(object => {
    if (!(object instanceof THREE.SkinnedMesh)) return;
    const list = Array.isArray(object.material) ? object.material : [object.material];
    list.forEach((material, materialIndex) => {
      if (!(material instanceof THREE.MeshStandardMaterial) || !material.name.startsWith('SeasonalSparkle ')) return;
      materials.add(material);
      const geometry: THREE.BufferGeometry = object.geometry;
      const ranges = Array.isArray(object.material)
        ? geometry.groups.filter(group => group.materialIndex === materialIndex)
        : [{ start: 0, count: geometry.index?.count ?? geometry.attributes.position.count }];
      const vertices = new Set<number>();
      for (const range of ranges) {
        for (let i = range.start; i < range.start + range.count; i++) vertices.add(geometry.index?.getX(i) ?? i);
      }
      const indices = [...vertices];
      // Sample evenly over the authored sequins, independent of triangulation.
      for (let i = 0; i < 32 && indices.length; i++) {
        if (anchors.length === 32) break;
        anchors.push({ mesh: object, vertex: indices[Math.floor(i * indices.length / 32)] });
      }
    });
  });
  if (!anchors.length) return null;
  const time = { value: 0 };
  const restores: (() => void)[] = [];
  let disposed = false;
  for (const material of materials) {
    const before = material.onBeforeCompile, key = material.customProgramCacheKey;
    material.onBeforeCompile = (shader, renderer) => {
      before.call(material, shader, renderer);
      shader.uniforms.capeSparkleTime = time;
      shader.vertexShader = 'varying float capeSparklePhase;\n' + shader.vertexShader;
      shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>', `#include <begin_vertex>
        capeSparklePhase = dot(position, vec3(19.3, 37.1, 23.7));`);
      shader.fragmentShader = 'uniform float capeSparkleTime;\nvarying float capeSparklePhase;\n' + shader.fragmentShader;
      shader.fragmentShader = shader.fragmentShader.replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        float twinkle = pow(0.5 + 0.5 * sin(capeSparkleTime * 2.1 + capeSparklePhase), 12.0);
        totalEmissiveRadiance *= 0.15 + 3.0 * twinkle;`);
    };
    material.customProgramCacheKey = () => key.call(material) + '|seasonal-cape-twinkle-v2';
    material.needsUpdate = true;
    restores.push(() => { material.onBeforeCompile = before; material.customProgramCacheKey = key; material.needsUpdate = true; });
  }
  const positions = new THREE.BufferAttribute(new Float32Array(anchors.length * 3), 3).setUsage(THREE.DynamicDrawUsage);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', positions);
  geometry.setAttribute('phase', new THREE.Float32BufferAttribute(anchors.map((_, i) => i * 2.399963), 1));
  const color = [...materials][0].color.clone().lerp(new THREE.Color('white'), .35);
  const glintMaterial = new THREE.ShaderMaterial({
    name: 'Seasonal cape glints', transparent: true, depthWrite: false, depthTest: true,
    blending: THREE.AdditiveBlending, toneMapped: false,
    uniforms: { time, tint: { value: color }, pixelScale: { value: 500 }, size: { value: .065 } },
    vertexShader: `
      uniform float time, pixelScale, size;
      attribute float phase;
      varying float brightness;
      void main() {
        float pulse = pow(0.5 + 0.5 * sin(time * 2.7 + phase), 6.0);
        brightness = pulse;
        vec4 view = modelViewMatrix * vec4(position, 1.0);
        // A tiny surface lift keeps the halo clear of the embroidered face.
        view.z += size * 0.12;
        gl_Position = projectionMatrix * view;
        gl_PointSize = clamp(size * pixelScale * (0.7 + pulse * 0.8) / max(0.01, -view.z), 1.0, 48.0);
      }`,
    fragmentShader: `
      uniform vec3 tint;
      varying float brightness;
      void main() {
        vec2 p = abs(gl_PointCoord * 2.0 - 1.0);
        float core = exp(-dot(p, p) * 38.0);
        float rays = pow(max(0.0, 1.0 - p.x - p.y), 2.0)
          * (exp(-p.x * 36.0) + exp(-p.y * 36.0));
        float halo = exp(-dot(p, p) * 7.0) * 0.12;
        float alpha = (core + rays * 0.8 + halo) * brightness;
        if (alpha < 0.006) discard;
        gl_FragColor = vec4(mix(tint, vec3(1.0), core), min(1.0, alpha));
        #include <colorspace_fragment>
      }`,
  });
  const glints = new THREE.Points(geometry, glintMaterial);
  glints.name = 'Seasonal cape sparkles';
  glints.frustumCulled = false; // Only 32 points; bounds change with the skinned cloth.
  glints.userData.runtimeEffect = true;
  root.add(glints);
  const point = new THREE.Vector3(), scale = new THREE.Vector3(), inverse = new THREE.Matrix4();
  const viewport = new THREE.Vector4();
  glints.onBeforeRender = (renderer, _scene, camera) => {
    renderer.getCurrentViewport(viewport);
    glintMaterial.uniforms.pixelScale.value = viewport.w * .5 * camera.projectionMatrix.elements[5];
  };
  function updateAnchors() {
    root.updateWorldMatrix(true, true);
    inverse.copy(root.matrixWorld).invert();
    for (let i = 0; i < anchors.length; i++) {
      const { mesh, vertex } = anchors[i];
      mesh.getVertexPosition(vertex, point).applyMatrix4(mesh.matrixWorld).applyMatrix4(inverse);
      positions.setXYZ(i, point.x, point.y, point.z);
    }
    positions.needsUpdate = true;
    // Sprite size is in world units and follows character scaling.
    root.getWorldScale(scale);
    glintMaterial.uniforms.size.value = .065 * Math.max(Math.abs(scale.x), Math.abs(scale.y), Math.abs(scale.z));
  }
  updateAnchors();
  return {
    update(deltaSeconds: number) {
      if (disposed || !Number.isFinite(deltaSeconds)) return;
      time.value += Math.min(.1, Math.max(0, deltaSeconds));
      updateAnchors();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      root.remove(glints);
      geometry.dispose(); glintMaterial.dispose();
      restores.forEach(restore => restore());
    },
  };
}
