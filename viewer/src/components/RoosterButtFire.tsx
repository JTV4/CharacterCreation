import { useLayoutEffect, useMemo, useRef } from "react";
import type { MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

const COUNT = 900;
const SLICE_COUNT = 9;

const FIRE_SPECS: Record<
  string,
  { bone: RegExp; start: number; end: number; jet: number }
> = {
  attack2: { bone: /^buttfire$/i, start: 0.36, end: 0.80, jet: 1.55 },
  attack3: { bone: /^mouthfire$/i, start: 0.22, end: 0.82, jet: 1.85 },
};

const SLICE_VERT = `
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const SLICE_FRAG = `
  uniform float uTime;
  uniform float uAmt;
  uniform float uShift;
  varying vec2 vUv;
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(a, b, u.x) + (c - a) * u.y * (1.0 - u.x) + (d - b) * u.x * u.y;
  }
  float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 4; i++) {
      v += a * noise(p);
      p *= 2.07;
      a *= 0.52;
    }
    return v;
  }
  void main() {
    vec2 p = vUv * 2.0 - 1.0;
    float r = length(p);
    if (r > 1.0) discard;
    vec2 np = vec2(p.x * 2.8 + uShift, p.y * 2.8 - uTime * 4.2 + uShift);
    float n = fbm(np);
    float radial = pow(max(0.0, 1.0 - r), 0.42);
    float flame = radial * (0.55 + 0.45 * n) * uAmt;
    if (flame < 0.03) discard;
    vec3 ember = vec3(1.0, 0.12, 0.0);
    vec3 mid = vec3(1.0, 0.38, 0.04);
    vec3 hot = vec3(1.0, 0.72, 0.22);
    float heat = clamp((1.0 - r) * (0.45 + n * 0.7), 0.0, 1.0);
    vec3 col = mix(ember, mid, heat);
    col = mix(col, hot, heat * heat * 0.4);
    gl_FragColor = vec4(col * flame, 1.0);
  }
`;

function makeSliceMaterial(shift: number): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
    uniforms: {
      uTime: { value: 0 },
      uAmt: { value: 0 },
      uShift: { value: shift },
    },
    vertexShader: SLICE_VERT,
    fragmentShader: SLICE_FRAG,
  });
}

interface Particle {
  alive: boolean;
  age: number;
  life: number;
  seed: number;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  size: number;
  heat: number;
}

function findNamedBone(scene: THREE.Object3D, pattern: RegExp): THREE.Object3D | null {
  let found: THREE.Object3D | null = null;
  scene.traverse((obj) => {
    if (found) return;
    if (pattern.test(obj.name)) found = obj;
    const mesh = obj as THREE.SkinnedMesh;
    if (mesh.isSkinnedMesh && mesh.skeleton) {
      for (const bone of mesh.skeleton.bones) {
        if (pattern.test(bone.name)) {
          found = bone;
          return;
        }
      }
    }
  });
  return found;
}

export function roosterHasButtFire(scene: THREE.Object3D): boolean {
  return (
    findNamedBone(scene, /^buttfire$/i) !== null ||
    findNamedBone(scene, /^mouthfire$/i) !== null
  );
}

export function RoosterButtFire({
  scene,
  clipName,
  actionRef,
}: {
  scene: THREE.Object3D;
  clipName: string | null;
  actionRef: MutableRefObject<THREE.AnimationAction | null>;
}) {
  const { camera } = useThree();
  const pointsRef = useRef<THREE.Points>(null);
  const sliceRefs = useRef<(THREE.Mesh | null)[]>([]);
  const lightRef = useRef<THREE.PointLight>(null);
  const originsRef = useRef<{ attack2: THREE.Object3D | null; attack3: THREE.Object3D | null }>({
    attack2: null,
    attack3: null,
  });
  const tmpPos = useMemo(() => new THREE.Vector3(), []);
  const tmpDir = useMemo(() => new THREE.Vector3(), []);
  const tmpQuat = useMemo(() => new THREE.Quaternion(), []);
  const tmpSide = useMemo(() => new THREE.Vector3(), []);
  const tmpUp = useMemo(() => new THREE.Vector3(), []);
  const tmpSpawn = useMemo(() => new THREE.Vector3(), []);
  const tmpInv = useMemo(() => new THREE.Matrix4(), []);
  const particles = useRef<Particle[]>([]);

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(COUNT * 3), 3));
    geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(COUNT * 3), 3));
    geo.setAttribute("size", new THREE.BufferAttribute(new Float32Array(COUNT), 1));
    return geo;
  }, []);

  const material = useMemo(() => {
    return new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      toneMapped: false,
      vertexShader: `
        attribute float size;
        attribute vec3 color;
        varying vec3 vColor;
        varying float vDist;
        void main() {
          vColor = color;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vDist = max(0.001, -mv.z);
          gl_PointSize = size * (520.0 / vDist);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        void main() {
          vec2 p = gl_PointCoord * 2.0 - 1.0;
          float r = length(p);
          float a = exp(-r * r * 1.6);
          if (a < 0.03) discard;
          gl_FragColor = vec4(vColor * a, 1.0);
        }
      `,
    });
  }, []);

  const sliceGeo = useMemo(() => new THREE.PlaneGeometry(2, 2), []);
  const sliceMats = useMemo(
    () => Array.from({ length: SLICE_COUNT }, (_, i) => makeSliceMaterial(i * 1.41)),
    [],
  );

  useLayoutEffect(() => {
    originsRef.current = {
      attack2: findNamedBone(scene, FIRE_SPECS.attack2.bone),
      attack3: findNamedBone(scene, FIRE_SPECS.attack3.bone),
    };
    particles.current = Array.from({ length: COUNT }, () => ({
      alive: false,
      age: 0,
      life: 1,
      seed: Math.random() * 1000,
      x: 0,
      y: 0,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      size: 0.1,
      heat: 1,
    }));
    return () => {
      geometry.dispose();
      material.dispose();
      sliceGeo.dispose();
      for (const mat of sliceMats) mat.dispose();
    };
  }, [scene, geometry, material, sliceGeo, sliceMats]);

  useFrame((_, delta) => {
    const pts = pointsRef.current;
    const spec = clipName ? FIRE_SPECS[clipName.toLowerCase()] : undefined;
    const origin = spec
      ? clipName?.toLowerCase() === "attack3"
        ? originsRef.current.attack3
        : originsRef.current.attack2
      : null;
    if (!pts || !origin || !spec) {
      if (pts) pts.visible = false;
      if (lightRef.current) lightRef.current.intensity = 0;
      for (let i = 0; i < SLICE_COUNT; i++) {
        const mesh = sliceRefs.current[i];
        const mat = sliceMats[i];
        if (mesh) mesh.visible = false;
        if (mat) mat.uniforms.uAmt.value = 0;
      }
      return;
    }
    const action = actionRef.current;
    const active = !!action;
    const duration = action ? Math.max(action.getClip().duration, 0.001) : 2;
    const t = active ? action.time / duration : -1;
    const on =
      active && t >= spec.start && t <= spec.end
        ? THREE.MathUtils.smoothstep(t, spec.start, spec.start + 0.05) *
          (1 - THREE.MathUtils.smoothstep(t, spec.end - 0.08, spec.end))
        : 0;
    const flicker = 0.82 + 0.18 * Math.sin((action?.time ?? 0) * 37);

    origin.getWorldPosition(tmpPos);
    origin.getWorldQuaternion(tmpQuat);
    tmpDir.set(0, 1, 0).applyQuaternion(tmpQuat).normalize();
    const host = pts.parent;
    if (host) {
      host.updateWorldMatrix(true, false);
      tmpInv.copy(host.matrixWorld).invert();
      tmpPos.applyMatrix4(tmpInv);
      tmpDir.transformDirection(tmpInv).normalize();
    }
    tmpUp.copy(camera.up);
    if (host) tmpUp.transformDirection(tmpInv).normalize();
    tmpSide.crossVectors(tmpDir, tmpUp);
    if (tmpSide.lengthSq() < 1e-5) tmpSide.set(1, 0, 0);
    tmpSide.normalize();
    tmpUp.crossVectors(tmpSide, tmpDir).normalize();

    const jetLen = spec.jet * (0.75 + on * 0.35);
    const streaming = on > 0.03;
    for (let i = 0; i < SLICE_COUNT; i++) {
      const mesh = sliceRefs.current[i];
      const mat = sliceMats[i];
      if (!mesh || !mat) continue;
      mesh.visible = streaming;
      if (!streaming) {
        mat.uniforms.uAmt.value = 0;
        continue;
      }
      const u = i / Math.max(SLICE_COUNT - 1, 1);
      const along = 0.06 + u * jetLen;
      const rad = 0.28 + u * (0.55 + on * 0.28);
      mesh.position.copy(tmpPos).addScaledVector(tmpDir, along);
      mesh.up.copy(camera.up);
      mesh.lookAt(camera.position);
      mesh.scale.set(rad, rad * 1.15, 1);
      mat.uniforms.uTime.value = action?.time ?? 0;
      mat.uniforms.uAmt.value = on * flicker * (1.15 - u * 0.32);
    }

    let spawn = on * flicker * 320 * delta;
    const list = particles.current;
    for (const p of list) {
      if (!p.alive && spawn > 0 && on > 0.03) {
        const along = Math.pow(Math.random(), 0.6) * jetLen;
        const u = along / Math.max(jetLen, 0.001);
        const rad = (0.08 + u * 0.38) * Math.sqrt(Math.random());
        const ang = Math.random() * Math.PI * 2;
        tmpSpawn.copy(tmpPos).addScaledVector(tmpDir, along);
        tmpSpawn.addScaledVector(tmpSide, Math.cos(ang) * rad);
        tmpSpawn.addScaledVector(tmpUp, Math.sin(ang) * rad);
        p.alive = true;
        p.age = 0;
        p.life = 0.28 + Math.random() * 0.28;
        p.seed = Math.random() * 1000;
        p.x = tmpSpawn.x;
        p.y = tmpSpawn.y;
        p.z = tmpSpawn.z;
        const speed = 1.1 + (1 - u) * 1.4;
        p.vx = tmpDir.x * speed + tmpSide.x * Math.cos(ang) * 0.35;
        p.vy = tmpDir.y * speed + tmpSide.y * Math.cos(ang) * 0.35;
        p.vz = tmpDir.z * speed + tmpSide.z * Math.sin(ang) * 0.35;
        p.size = 0.32 + (1 - u) * 0.28 + Math.random() * 0.12;
        p.heat = 0.55 + (1 - u) * 0.4;
        spawn -= 1;
      }
      if (!p.alive) continue;
      p.age += delta;
      if (p.age >= p.life) {
        p.alive = false;
        continue;
      }
      const st = p.age * 12 + p.seed;
      p.vx += Math.sin(st * 1.6) * 0.7 * delta;
      p.vy += Math.cos(st * 2.0) * 0.6 * delta;
      p.vz += Math.sin(st * 1.2) * 0.7 * delta;
      p.x += p.vx * delta;
      p.y += p.vy * delta;
      p.z += p.vz * delta;
      p.vx *= 0.98;
      p.vz *= 0.98;
    }

    const pos = pts.geometry.getAttribute("position") as THREE.BufferAttribute;
    const col = pts.geometry.getAttribute("color") as THREE.BufferAttribute;
    const siz = pts.geometry.getAttribute("size") as THREE.BufferAttribute;
    let live = 0;
    for (let i = 0; i < COUNT; i++) {
      const p = list[i];
      if (!p?.alive) {
        pos.setXYZ(i, 0, 0, -40);
        siz.setX(i, 0);
        continue;
      }
      const u = p.age / p.life;
      pos.setXYZ(i, p.x, p.y, p.z);
      col.setXYZ(i, 1.0, 0.28 + p.heat * 0.42 - u * 0.1, 0.04 + (1 - u) * 0.06);
      siz.setX(i, p.size * (1.15 - u * 0.25));
      live += 1;
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    siz.needsUpdate = true;
    pts.visible = live > 0;
    if (lightRef.current) {
      lightRef.current.position.copy(tmpPos).addScaledVector(tmpDir, jetLen * 0.4);
      lightRef.current.intensity = on * 8;
    }
  });

  return (
    <>
      {sliceMats.map((mat, i) => (
        <mesh
          key={i}
          ref={(el) => {
            sliceRefs.current[i] = el;
          }}
          geometry={sliceGeo}
          material={mat}
          frustumCulled={false}
          visible={false}
        />
      ))}
      <points ref={pointsRef} frustumCulled={false}>
        <primitive object={geometry} attach="geometry" />
        <primitive object={material} attach="material" />
      </points>
      <pointLight ref={lightRef} color="#ff4a00" intensity={0} distance={5} decay={2} />
    </>
  );
}
