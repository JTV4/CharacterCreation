import { useLayoutEffect, useMemo, useRef } from "react";
import type { MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

const COUNT = 1100;
const SLICE_COUNT = 11;
const MOUTH_START = 0.58;
const MOUTH_END = 1.82;
const STREAM_START = 0.80;
const STREAM_END = 1.72;
const CLIP_LEN = 2.0;
const JAW_LEN_REST = 0.58;

const FIRE_CLIPS = new Set(["attack1"]);

const KIND_MOUTH = 0;
const KIND_JET = 1;
const KIND_EMBER = 2;

interface Particle {
  alive: boolean;
  kind: number;
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

function normName(name: string): string {
  return name.toLowerCase().replace(/[._\s-]/g, "");
}

function findNamed(scene: THREE.Object3D, wanted: string): THREE.Object3D | undefined {
  const w = normName(wanted);
  let found: THREE.Object3D | undefined;
  scene.traverse((obj) => {
    if (found) return;
    if (obj.name && normName(obj.name) === w) {
      found = obj;
      return;
    }
    const mesh = obj as THREE.SkinnedMesh;
    if (mesh.isSkinnedMesh && mesh.skeleton) {
      for (const bone of mesh.skeleton.bones) {
        if (normName(bone.name) === w) {
          found = bone;
          return;
        }
      }
    }
  });
  return found;
}

function isFireClip(name: string | null): boolean {
  return !!name && FIRE_CLIPS.has(name.toLowerCase());
}

function findMouth(scene: THREE.Object3D): {
  upper: THREE.Object3D;
  jaw?: THREE.Object3D;
  fire?: THREE.Object3D;
  fireBreath?: THREE.Object3D;
} | null {
  const upper =
    findNamed(scene, "Bone.004") ??
    findNamed(scene, "Bone004") ??
    findNamed(scene, "Bone.FireFX");
  const jaw = findNamed(scene, "Bone.LowerJaw") ?? findNamed(scene, "BoneLowerJaw");
  const fireMouth = findNamed(scene, "FireMouth");
  const fireBreath = findNamed(scene, "FireBreath");
  const fire = fireMouth ?? fireBreath ?? findNamed(scene, "Bone.FireFX");
  if (upper) return { upper, jaw, fire, fireBreath };
  if (fire) return { upper: fire, jaw, fire, fireBreath };
  return null;
}

export function hideDragonFireMeshes(scene: THREE.Object3D): string[] {
  const hidden: string[] = [];
  scene.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    const mats = mesh.isMesh
      ? Array.isArray(mesh.material)
        ? mesh.material
        : [mesh.material]
      : [];
    const fireMat = mats.some((m) => !!m && /dragonfire/i.test(m.name || ""));
    const fireName = /dragonfire|icosphere/i.test(obj.name || "");
    if (!fireMat && !fireName) return;
    obj.visible = false;
    hidden.push(obj.name || "(unnamed)");
    for (const mat of mats) {
      if (!mat) continue;
      const std = mat as THREE.MeshStandardMaterial;
      if ("emissive" in std) std.emissive.setRGB(0, 0, 0);
      if ("emissiveIntensity" in std) std.emissiveIntensity = 0;
      if ("color" in std) std.color.setRGB(0, 0, 0);
      std.transparent = true;
      std.opacity = 0;
      std.needsUpdate = true;
    }
  });
  return hidden;
}

function plateau(time: number, a: number, b: number, c: number, d: number): number {
  if (time < a || time > d) return 0;
  const rise = THREE.MathUtils.smoothstep(time, a, b);
  const fall = 1 - THREE.MathUtils.smoothstep(time, c, d);
  return rise * fall;
}

function mouthFill(time: number): number {
  const base = plateau(time, MOUTH_START, MOUTH_START + 0.18, MOUTH_END - 0.28, MOUTH_END);
  const flicker = 0.78 + 0.22 * Math.sin(time * 31.0) * Math.sin(time * 13.0);
  return base * flicker;
}

function streamFill(time: number): number {
  const base = plateau(time, STREAM_START, STREAM_START + 0.16, STREAM_END - 0.28, STREAM_END);
  const flicker = 0.80 + 0.20 * Math.sin(time * 37.0);
  return base * flicker;
}

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
  uniform vec3 uHot;
  uniform vec3 uMid;
  uniform vec3 uEmber;
  varying vec2 vUv;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
  }
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
    vec2 np = vec2(p.x * 3.4 + uShift, p.y * 3.4 - uTime * 4.8 + uShift);
    float n = fbm(np);
    float n2 = fbm(np * 2.2 + 9.0);
    float radial = pow(max(0.0, 1.0 - r), 0.55);
    float wisps = 0.5 + 0.5 * n + 0.18 * n2;
    float flame = radial * wisps * uAmt;
    if (flame < 0.04) discard;
    vec3 ember = uEmber;
    vec3 mid = uMid;
    vec3 hot = uHot;
    float heat = clamp((1.0 - r) * (0.4 + n * 0.8), 0.0, 1.0);
    vec3 col = mix(ember, mid, heat);
    col = mix(col, hot, heat * heat * 0.35);
    gl_FragColor = vec4(col * flame, 1.0);
  }
`;

export interface FirePalette {
  hot: [number, number, number];
  mid: [number, number, number];
  ember: [number, number, number];
  light: string;
}

const FIRE_PALETTES: Record<string, FirePalette> = {
  green: {
    hot: [0.85, 1.0, 0.45],
    mid: [0.18, 0.95, 0.22],
    ember: [0.02, 0.32, 0.05],
    light: "#22ee44",
  },
  blue: {
    hot: [0.80, 0.94, 1.0],
    mid: [0.12, 0.48, 1.0],
    ember: [0.02, 0.10, 0.48],
    light: "#3b82ff",
  },
  red: {
    hot: [1.0, 0.55, 0.16],
    mid: [1.0, 0.16, 0.03],
    ember: [0.55, 0.02, 0.0],
    light: "#ff2a00",
  },
  violet: {
    hot: [0.96, 0.72, 1.0],
    mid: [0.70, 0.16, 1.0],
    ember: [0.28, 0.02, 0.48],
    light: "#c026ff",
  },
  black: {
    hot: [0.95, 0.88, 0.70],
    mid: [0.28, 0.10, 0.05],
    ember: [0.05, 0.04, 0.04],
    light: "#ff6a1a",
  },
};

export function firePaletteFor(scene: THREE.Object3D, url?: string): FirePalette {
  let names = url ?? "";
  scene.traverse((obj) => {
    if (obj.name) names += ` ${obj.name}`;
  });
  const blob = names.toLowerCase();
  if (blob.includes("green")) return FIRE_PALETTES.green;
  if (blob.includes("blue")) return FIRE_PALETTES.blue;
  if (blob.includes("violet") || blob.includes("purple")) return FIRE_PALETTES.violet;
  if (blob.includes("black")) return FIRE_PALETTES.black;
  if (blob.includes("red")) return FIRE_PALETTES.red;
  return FIRE_PALETTES.red;
}

function makeSliceMaterial(shift: number, pal: FirePalette): THREE.ShaderMaterial {
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
      uHot: { value: new THREE.Vector3(...pal.hot) },
      uMid: { value: new THREE.Vector3(...pal.mid) },
      uEmber: { value: new THREE.Vector3(...pal.ember) },
    },
    vertexShader: SLICE_VERT,
    fragmentShader: SLICE_FRAG,
  });
}

export function DragonFireBreath({
  scene,
  clipName,
  actionRef,
  url,
}: {
  scene: THREE.Object3D;
  clipName: string | null;
  actionRef: MutableRefObject<THREE.AnimationAction | null>;
  url?: string;
}) {
  const { camera } = useThree();
  const pointsRef = useRef<THREE.Points>(null);
  const sliceRefs = useRef<(THREE.Mesh | null)[]>([]);
  const mouthLightRef = useRef<THREE.PointLight>(null);
  const jetLightRef = useRef<THREE.PointLight>(null);
  const particles = useRef<Particle[]>([]);
  const mouthRef = useRef<ReturnType<typeof findMouth>>(null);
  const tmpPos = useMemo(() => new THREE.Vector3(), []);
  const tmpJaw = useMemo(() => new THREE.Vector3(), []);
  const tmpDir = useMemo(() => new THREE.Vector3(), []);
  const tmpQuat = useMemo(() => new THREE.Quaternion(), []);
  const tmpSide = useMemo(() => new THREE.Vector3(), []);
  const tmpUp = useMemo(() => new THREE.Vector3(), []);
  const tmpSpawn = useMemo(() => new THREE.Vector3(), []);
  const tmpInv = useMemo(() => new THREE.Matrix4(), []);
  const jawLenRef = useRef(JAW_LEN_REST);

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
      uniforms: {},
      vertexShader: `
        attribute float size;
        attribute vec3 color;
        varying vec3 vColor;
        varying float vDist;
        void main() {
          vColor = color;
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vDist = max(0.001, -mv.z);
          gl_PointSize = size * (360.0 / vDist);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        void main() {
          vec2 p = gl_PointCoord * 2.0 - 1.0;
          float r = length(p);
          float a = exp(-r * r * 3.2);
          if (a < 0.04) discard;
          gl_FragColor = vec4(vColor * a, 1.0);
        }
      `,
    });
  }, []);

  const palette = useMemo(() => firePaletteFor(scene, url), [scene, url]);
  const sliceGeo = useMemo(() => new THREE.PlaneGeometry(2, 2), []);
  const sliceMats = useMemo(
    () => Array.from({ length: SLICE_COUNT }, (_, i) => makeSliceMaterial(i * 1.37, palette)),
    [palette],
  );

  useLayoutEffect(() => {
    hideDragonFireMeshes(scene);
    mouthRef.current = findMouth(scene);
    const found = mouthRef.current;
    if (found?.upper && found.fireBreath) {
      found.upper.getWorldPosition(tmpPos);
      found.fireBreath.getWorldPosition(tmpJaw);
      jawLenRef.current = THREE.MathUtils.clamp(
        tmpPos.distanceTo(tmpJaw),
        0.4,
        1.2,
      );
    }
    particles.current = Array.from({ length: COUNT }, () => ({
      alive: false,
      kind: KIND_JET,
      age: 0,
      life: 1,
      seed: Math.random() * 1000,
      x: 0,
      y: 0,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      size: 0.12,
      heat: 1,
    }));
    return () => {
      sliceGeo.dispose();
      for (const mat of sliceMats) mat.dispose();
    };
  }, [scene, sliceGeo, sliceMats]);

  useFrame((_, delta) => {
    const pts = pointsRef.current;
    const mouth = mouthRef.current;
    if (!pts || !mouth) return;

    const action = actionRef.current;
    const time = action ? action.time : 0;
    const active = isFireClip(clipName) && !!action;
    const clipT = active
      ? time % Math.max(action.getClip().duration, CLIP_LEN)
      : 0;
    const mouthAmt = active ? mouthFill(clipT) : 0;
    const streamAmt = active ? streamFill(clipT) : 0;

    // Bones report world space. This component is parented under the
    // creature X-wrap group, so mesh.position is local — writing world
    // coords double-applies the wrap and puts the jet on the back (-Y).
    const hinge = mouth.upper;
    hinge.getWorldPosition(tmpPos);
    hinge.getWorldQuaternion(tmpQuat);
    tmpDir.set(0, 1, 0).applyQuaternion(tmpQuat).normalize();
    if (tmpDir.lengthSq() < 0.01) tmpDir.set(0, 1, 0);
    tmpPos.addScaledVector(tmpDir, jawLenRef.current);
    const host = pointsRef.current.parent;
    if (host) {
      host.updateWorldMatrix(true, false);
      tmpInv.copy(host.matrixWorld).invert();
      tmpPos.applyMatrix4(tmpInv);
      tmpDir.transformDirection(tmpInv).normalize();
    }
    tmpUp.set(0, 0, 1);
    if (host) tmpUp.transformDirection(tmpInv).normalize();
    tmpSide.crossVectors(tmpDir, tmpUp);
    if (tmpSide.lengthSq() < 1e-5) tmpSide.set(1, 0, 0);
    tmpSide.normalize();
    tmpUp.crossVectors(tmpSide, tmpDir).normalize();

    let jawGap = 0.28;
    if (mouth.jaw) {
      mouth.jaw.getWorldPosition(tmpJaw);
      jawGap = tmpPos.distanceTo(tmpJaw);
    }
    const gap = THREE.MathUtils.clamp(jawGap, 0.18, 0.55);
    const jetLen = 0.55 + streamAmt * 3.5;
    const on = streamAmt > 0.03;

    for (let i = 0; i < SLICE_COUNT; i++) {
      const mesh = sliceRefs.current[i];
      const mat = sliceMats[i];
      if (!mesh || !mat) continue;
      mesh.visible = on;
      if (!on) {
        mat.uniforms.uAmt.value = 0;
        continue;
      }
      const u = i / Math.max(SLICE_COUNT - 1, 1);
      const along = 0.12 + u * jetLen;
      const rad = 0.22 + u * (0.72 + streamAmt * 0.45);
      mesh.position.copy(tmpPos).addScaledVector(tmpDir, along);
      mesh.up.copy(camera.up);
      mesh.lookAt(camera.position);
      mesh.scale.set(rad, rad, 1);
      mat.uniforms.uTime.value = clipT;
      mat.uniforms.uAmt.value = streamAmt * (1.05 - u * 0.28);
    }

    const list = particles.current;
    let mouthSpawn = mouthAmt * 70 * delta;
    let jetSpawn = streamAmt * 240 * delta;
    let emberSpawn = streamAmt * 28 * delta;

    const spawnAt = (
      p: Particle,
      along: number,
      rx: number,
      ry: number,
      speed: number,
      kind: number,
    ) => {
      tmpSpawn.copy(tmpPos);
      tmpSpawn.addScaledVector(tmpDir, along);
      tmpSpawn.addScaledVector(tmpSide, rx);
      tmpSpawn.addScaledVector(tmpUp, ry);
      p.alive = true;
      p.kind = kind;
      p.age = 0;
      p.seed = Math.random() * 1000;
      p.x = tmpSpawn.x;
      p.y = tmpSpawn.y;
      p.z = tmpSpawn.z;
      const jitter = kind === KIND_JET ? 0.55 : 0.35;
      p.vx = tmpDir.x * speed + tmpSide.x * rx * jitter + tmpUp.x * ry * jitter;
      p.vy = tmpDir.y * speed + tmpSide.y * rx * jitter + tmpUp.y * ry * jitter;
      p.vz = tmpDir.z * speed + tmpSide.z * rx * jitter + tmpUp.z * ry * jitter;
    };

    for (const p of list) {
      if (!p.alive) {
        if (mouthSpawn > 0 && mouthAmt > 0.03) {
          const ang = Math.random() * Math.PI * 2;
          const rad = Math.sqrt(Math.random()) * gap * 0.35;
          spawnAt(
            p,
            -0.12 + Math.random() * 0.22,
            Math.cos(ang) * rad,
            Math.sin(ang) * rad,
            0.15 + Math.random() * 0.35,
            KIND_MOUTH,
          );
          p.life = 0.16 + Math.random() * 0.18;
          p.size = 0.16 + Math.random() * 0.18;
          p.heat = 0.7 + Math.random() * 0.2;
          mouthSpawn -= 1;
        } else if (jetSpawn > 0 && streamAmt > 0.03) {
          const along = Math.pow(Math.random(), 0.65) * jetLen;
          const t = along / Math.max(jetLen, 0.001);
          const maxR = 0.1 + t * (0.58 + streamAmt * 0.42);
          const rad = maxR * Math.sqrt(Math.random());
          const ang = Math.random() * Math.PI * 2;
          spawnAt(
            p,
            along,
            Math.cos(ang) * rad,
            Math.sin(ang) * rad,
            1.6 + (1.0 - t) * 2.4 + Math.random() * 1.4,
            KIND_JET,
          );
          p.life = 0.28 + Math.random() * 0.32;
          p.size = 0.22 + (1.0 - t) * 0.2 + Math.random() * 0.16;
          p.heat = 0.45 + (1.0 - t) * 0.35;
          jetSpawn -= 1;
        } else if (emberSpawn > 0 && streamAmt > 0.03) {
          const along = 0.55 * jetLen + Math.random() * 0.55 * jetLen;
          const t = along / Math.max(jetLen, 0.001);
          const maxR = 0.2 + t * 0.7;
          const rad = maxR * Math.sqrt(Math.random());
          const ang = Math.random() * Math.PI * 2;
          spawnAt(
            p,
            along,
            Math.cos(ang) * rad,
            Math.sin(ang) * rad,
            1.2 + Math.random() * 1.6,
            KIND_EMBER,
          );
          p.life = 0.4 + Math.random() * 0.35;
          p.size = 0.04 + Math.random() * 0.06;
          p.heat = 0.2 + Math.random() * 0.2;
          emberSpawn -= 1;
        }
      }

      if (!p.alive) continue;
      p.age += delta;
      if (p.age >= p.life) {
        p.alive = false;
        continue;
      }
      const turb = 0.9 + (p.kind === KIND_MOUTH ? 1.2 : 0);
      const st = p.age * 11.0 + p.seed;
      p.vx += Math.sin(st * 1.7) * turb * delta;
      p.vy += Math.cos(st * 2.1) * turb * 0.85 * delta;
      p.vz += Math.sin(st * 1.3 + 2.0) * turb * delta;
      const rise = p.kind === KIND_JET ? 0.12 : p.kind === KIND_EMBER ? 0.7 : 0.2;
      p.vx += camera.up.x * rise * delta;
      p.vy += camera.up.y * rise * delta;
      p.vz += camera.up.z * rise * delta;
      p.x += p.vx * delta;
      p.y += p.vy * delta;
      p.z += p.vz * delta;
      p.vx *= p.kind === KIND_JET ? 0.982 : 0.94;
      p.vz *= p.kind === KIND_JET ? 0.982 : 0.94;
    }

    const pos = pts.geometry.getAttribute("position") as THREE.BufferAttribute;
    const col = pts.geometry.getAttribute("color") as THREE.BufferAttribute;
    const siz = pts.geometry.getAttribute("size") as THREE.BufferAttribute;
    for (let i = 0; i < COUNT; i++) {
      const p = list[i];
      if (!p?.alive) {
        pos.setXYZ(i, 0, -99, 0);
        col.setXYZ(i, 0, 0, 0);
        siz.setX(i, 0);
        continue;
      }
      const u = p.age / p.life;
      pos.setXYZ(i, p.x, p.y, p.z);
      const hot = palette.hot;
      const mid = palette.mid;
      const ember = palette.ember;
      let r = mid[0];
      let g = mid[1];
      let b = mid[2];
      if (p.kind === KIND_MOUTH) {
        const k = 1.0 - u * 0.35;
        r = hot[0] * k + mid[0] * (1 - k);
        g = hot[1] * k + mid[1] * (1 - k);
        b = hot[2] * k + mid[2] * (1 - k);
      } else if (p.kind === KIND_JET) {
        const k = Math.max(0, p.heat - u * 0.35);
        r = mid[0] * (1 - k) + hot[0] * k;
        g = mid[1] * (1 - k) + hot[1] * k;
        b = mid[2] * (1 - k) + hot[2] * k;
      } else {
        r = ember[0] * (1 - u) + mid[0] * u * 0.4;
        g = ember[1] * (1 - u) + mid[1] * u * 0.4;
        b = ember[2] * (1 - u) + mid[2] * u * 0.4;
      }
      col.setXYZ(i, r, g, b);
      const grow = p.kind === KIND_EMBER ? 1.0 - u * 0.4 : 0.95 + u * 0.45;
      siz.setX(i, p.size * grow * (1.0 - u * 0.28));
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    siz.needsUpdate = true;

    if (mouthLightRef.current) {
      mouthLightRef.current.position.copy(tmpPos).addScaledVector(tmpDir, 0.12);
      mouthLightRef.current.intensity = mouthAmt * 7 + streamAmt * 4;
    }
    if (jetLightRef.current) {
      jetLightRef.current.position.copy(tmpPos).addScaledVector(tmpDir, jetLen * 0.45);
      jetLightRef.current.intensity = streamAmt * 9;
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
      <pointLight
        ref={mouthLightRef}
        color={palette.light}
        intensity={0}
        distance={3.5}
        decay={2}
      />
      <pointLight
        ref={jetLightRef}
        color={palette.light}
        intensity={0}
        distance={6}
        decay={2}
      />
    </>
  );
}

export function dragonHasFireBreath(scene: THREE.Object3D): boolean {
  return findMouth(scene) !== null;
}
