import { useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ForwardedRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";

const loader = new GLTFLoader();
loader.setMeshoptDecoder(MeshoptDecoder);

const BIRD_CARDS = 56;
const WISP_COUNT = 280;
const DIE_DELAY = 0.5;
const COOKED_AT = 2.55;

const COOKED = new THREE.Color(0xc47822);
const COOKED_DARK = new THREE.Color(0x5a2a0c);

export type RoastPhase = "idle" | "roasting" | "cooked";

export interface RoastCommands {
  play: () => void;
  reset: () => void;
}

export interface BirdRoastProps {
  url: string;
  onBounds?: (box: THREE.Box3) => void;
  onPhase?: (phase: RoastPhase) => void;
  commandRef?: ForwardedRef<RoastCommands | null>;
}

interface Sample {
  local: THREE.Vector3;
  mesh: THREE.Mesh;
}

interface MatEntry {
  mat: THREE.MeshStandardMaterial;
  color: THREE.Color;
  emissive: THREE.Color;
  emissiveIntensity: number;
  roughness: number;
}

interface Wisp {
  alive: boolean;
  age: number;
  life: number;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  size: number;
}

const FLAME_VERT = `
  varying vec2 vUv;
  varying float vSeed;
  void main() {
    vUv = uv;
    vSeed = float(gl_InstanceID) * 1.61;
    vec4 world = instanceMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

const FLAME_FRAG = `
  uniform float uTime;
  varying vec2 vUv;
  varying float vSeed;
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
    float y = vUv.y;
    float x = vUv.x * 2.0 - 1.0;
    vec2 np = vec2(x * 2.8 + vSeed, y * 3.2 - uTime * 3.8 + vSeed);
    float n = fbm(np);
    float taper = pow(max(0.0, 1.0 - y), 0.5);
    float halfW = taper * (0.4 + 0.3 * n) + (n - 0.5) * 0.16 * (1.0 - y);
    float shape = smoothstep(halfW, halfW * 0.28, abs(x));
    float tip = 1.0 - smoothstep(0.55, 1.0, y + n * 0.12);
    float flame = shape * tip * smoothstep(0.0, 0.06, y);
    if (flame < 0.045) discard;
    float heat = clamp((1.0 - y) * 0.4 + (1.0 - abs(x)) * 0.4 + n * 0.35, 0.0, 1.0);
    vec3 col = mix(vec3(0.55, 0.02, 0.0), vec3(1.0, 0.3, 0.03), heat);
    col = mix(col, vec3(1.0, 0.82, 0.22), heat * heat * 0.7);
    gl_FragColor = vec4(col * (0.55 + flame * 1.15), 1.0);
  }
`;

function hideProps(scene: THREE.Object3D) {
  scene.traverse((obj) => {
    if (/egg|omelet|burst/i.test(obj.name)) obj.visible = false;
  });
}

function easeInOut(t: number): number {
  const u = THREE.MathUtils.clamp(t, 0, 1);
  return u * u * (3 - 2 * u);
}

export function BirdRoast({ url, onBounds, onPhase, commandRef }: BirdRoastProps) {
  const { camera } = useThree();
  const [root, setRoot] = useState<THREE.Group | null>(null);
  const wrapRef = useRef<THREE.Group>(null);
  const birdRef = useRef<THREE.Group>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clipsRef = useRef<THREE.AnimationClip[]>([]);
  const actionRef = useRef<THREE.AnimationAction | null>(null);
  const matsRef = useRef<MatEntry[]>([]);
  const samplesRef = useRef<Sample[]>([]);
  const phaseRef = useRef<RoastPhase>("idle");
  const roastClock = useRef(0);
  const playedDie = useRef(false);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const tmpWorld = useMemo(() => new THREE.Vector3(), []);
  const tmpLook = useMemo(() => new THREE.Vector3(), []);
  const tmpRight = useMemo(() => new THREE.Vector3(), []);
  const tmpUp = useMemo(() => new THREE.Vector3(), []);
  const tmpColor = useMemo(() => new THREE.Color(), []);
  const flameMeshRef = useRef<THREE.InstancedMesh>(null);
  const wisps = useRef<Wisp[]>(
    Array.from({ length: WISP_COUNT }, () => ({
      alive: false,
      age: 0,
      life: 1,
      x: 0,
      y: 0,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      size: 0.1,
    })),
  );

  const flameGeo = useMemo(() => {
    const geo = new THREE.PlaneGeometry(1, 1);
    geo.translate(0, 0.5, 0);
    return geo;
  }, []);
  const flameMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        depthTest: true,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
        uniforms: { uTime: { value: 0 } },
        vertexShader: FLAME_VERT,
        fragmentShader: FLAME_FRAG,
      }),
    [],
  );
  const wispGeo = useMemo(() => {
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(WISP_COUNT * 3), 3));
    geo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(WISP_COUNT * 3), 3));
    geo.setAttribute("size", new THREE.BufferAttribute(new Float32Array(WISP_COUNT), 1));
    return geo;
  }, []);
  const wispMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
        vertexShader: `
          attribute float size;
          attribute vec3 color;
          varying vec3 vColor;
          void main() {
            vColor = color;
            vec4 mv = modelViewMatrix * vec4(position, 1.0);
            gl_PointSize = size * (720.0 / max(0.001, -mv.z));
            gl_Position = projectionMatrix * mv;
          }
        `,
        fragmentShader: `
          varying vec3 vColor;
          void main() {
            vec2 p = gl_PointCoord * 2.0 - 1.0;
            float a = exp(-dot(p, p) * 3.2);
            if (a < 0.04) discard;
            gl_FragColor = vec4(vColor * a, 1.0);
          }
        `,
      }),
    [],
  );

  const setPhase = (phase: RoastPhase) => {
    if (phaseRef.current === phase) return;
    phaseRef.current = phase;
    onPhase?.(phase);
  };

  const playClip = (name: string, loop: boolean) => {
    const mixer = mixerRef.current;
    if (!mixer) return;
    const clip = clipsRef.current.find((c) => c.name === name);
    if (!clip) return;
    mixer.stopAllAction();
    const action = mixer.clipAction(clip);
    action.reset();
    action.loop = loop ? THREE.LoopRepeat : THREE.LoopOnce;
    action.clampWhenFinished = !loop;
    action.play();
    actionRef.current = action;
  };

  const bake = (scene: THREE.Group) => {
    hideProps(scene);
    const mats: MatEntry[] = [];
    const samples: Sample[] = [];
    scene.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh || !mesh.geometry) return;
      if (/egg|omelet/i.test(mesh.name)) return;
      const src = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const cloned = src.map((m) => m.clone());
      mesh.material = cloned.length === 1 ? cloned[0] : cloned;
      for (const mat of cloned) {
        const std = mat as THREE.MeshStandardMaterial;
        if (!std.color) continue;
        if (!std.emissive) std.emissive = new THREE.Color(0x000000);
        mats.push({
          mat: std,
          color: std.color.clone(),
          emissive: std.emissive.clone(),
          emissiveIntensity: std.emissiveIntensity ?? 1,
          roughness: std.roughness ?? 0.7,
        });
      }
      const pos = mesh.geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
      if (!pos) return;
      const index = mesh.geometry.index;
      const tri = index ? index.count / 3 : pos.count / 3;
      const take = Math.min(90, Math.max(24, Math.floor(tri * 0.08)));
      for (let i = 0; i < take; i++) {
        const t = Math.floor(Math.random() * tri);
        const i0 = index ? index.getX(t * 3) : t * 3;
        const a = new THREE.Vector3().fromBufferAttribute(pos, i0);
        samples.push({ local: a, mesh });
      }
    });
    matsRef.current = mats;
    samplesRef.current = samples;
    wrapRef.current?.updateWorldMatrix(true, true);
    const box = new THREE.Box3();
    if (wrapRef.current) box.expandByObject(wrapRef.current);
    if (!box.isEmpty()) onBounds?.(box);
  };

  const reset = () => {
    setPhase("idle");
    roastClock.current = 0;
    playedDie.current = false;
    playClip("idle", true);
    for (const entry of matsRef.current) {
      entry.mat.color.copy(entry.color);
      if (entry.mat.emissive) entry.mat.emissive.copy(entry.emissive);
      entry.mat.emissiveIntensity = entry.emissiveIntensity;
      if (entry.mat.roughness !== undefined) entry.mat.roughness = entry.roughness;
    }
    for (const p of wisps.current) p.alive = false;
    const mesh = flameMeshRef.current;
    if (mesh) {
      dummy.matrix.makeScale(0, 0, 0);
      for (let i = 0; i < BIRD_CARDS; i++) mesh.setMatrixAt(i, dummy.matrix);
      mesh.instanceMatrix.needsUpdate = true;
    }
  };

  const play = () => {
    if (phaseRef.current !== "idle") return;
    roastClock.current = 0;
    playedDie.current = false;
    playClip("idle", true);
    setPhase("roasting");
  };

  useLayoutEffect(() => {
    let cancelled = false;
    setRoot(null);
    mixerRef.current = null;
    clipsRef.current = [];
    phaseRef.current = "idle";
    onPhase?.("idle");
    loader.load(
      url,
      (gltf) => {
        if (cancelled) return;
        hideProps(gltf.scene);
        clipsRef.current = gltf.animations ?? [];
        if (clipsRef.current.length) mixerRef.current = new THREE.AnimationMixer(gltf.scene);
        setRoot(gltf.scene);
      },
      undefined,
      (err) => console.error("BirdRoast load failed", err),
    );
    return () => {
      cancelled = true;
      mixerRef.current?.stopAllAction();
      for (const entry of matsRef.current) entry.mat.dispose();
      matsRef.current = [];
    };
  }, [url, onPhase]);

  useLayoutEffect(() => {
    if (!root) return;
    const id = requestAnimationFrame(() => {
      bake(root);
      reset();
    });
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [root]);

  useLayoutEffect(() => {
    return () => {
      flameGeo.dispose();
      flameMat.dispose();
      wispGeo.dispose();
      wispMat.dispose();
    };
  }, [flameGeo, flameMat, wispGeo, wispMat]);

  useImperativeHandle(commandRef, () => ({ play, reset }), [root]);

  const placeCard = (
    mesh: THREE.InstancedMesh,
    index: number,
    x: number,
    y: number,
    z: number,
    width: number,
    height: number,
  ) => {
    tmpLook.set(camera.position.x - x, camera.position.y - y, 0);
    if (tmpLook.lengthSq() < 1e-6) tmpLook.set(0, 1, 0);
    tmpLook.normalize();
    tmpRight.set(-tmpLook.y * width, tmpLook.x * width, 0);
    tmpUp.set(0, 0, height);
    dummy.matrix.makeBasis(tmpRight, tmpUp, tmpLook);
    dummy.matrix.setPosition(x, y, z);
    mesh.setMatrixAt(index, dummy.matrix);
  };

  useFrame((_, dt) => {
    const delta = Math.min(dt, 0.05);
    mixerRef.current?.update(delta);
    const phase = phaseRef.current;

    if (phase === "roasting" || phase === "cooked") {
      roastClock.current += delta;
      const t = roastClock.current;
      if (!playedDie.current && t >= DIE_DELAY) {
        playedDie.current = true;
        playClip("die", false);
      }
      if (phase === "roasting" && t >= COOKED_AT) setPhase("cooked");

      const cook = easeInOut(THREE.MathUtils.clamp(t / COOKED_AT, 0, 1));
      const glow = phase === "cooked" ? 0.08 : THREE.MathUtils.clamp(1 - Math.abs(t - 1.1) / 1.4, 0, 1);
      for (const entry of matsRef.current) {
        tmpColor.copy(entry.color).lerp(COOKED, cook * 0.72).lerp(COOKED_DARK, cook * 0.45);
        entry.mat.color.copy(tmpColor);
        if (entry.mat.emissive) {
          entry.mat.emissive.setRGB(1.0, 0.28, 0.04).multiplyScalar(glow * 0.35);
        }
        entry.mat.emissiveIntensity = entry.emissiveIntensity + glow * 0.55;
        if (entry.mat.roughness !== undefined) {
          entry.mat.roughness = THREE.MathUtils.lerp(entry.roughness, 0.82, cook);
        }
      }
    }

    const cards = flameMeshRef.current;
    const bodyOn = phase === "roasting" || phase === "cooked";
    const bodyAmt = phase === "cooked" ? 0.28 : 1;
    flameMat.uniforms.uTime.value = roastClock.current;

    if (cards) {
      dummy.matrix.makeScale(0, 0, 0);
      for (let i = 0; i < BIRD_CARDS; i++) cards.setMatrixAt(i, dummy.matrix);

      if (bodyOn && samplesRef.current.length > 0) {
        const n = Math.min(BIRD_CARDS, samplesRef.current.length);
        const fade = bodyAmt * (0.75 + 0.25 * Math.sin(roastClock.current * 11));
        for (let i = 0; i < n; i++) {
          const s = samplesRef.current[Math.floor((i + 0.5) * samplesRef.current.length / n)];
          s.mesh.localToWorld(tmpWorld.copy(s.local));
          const flicker = 0.8 + 0.2 * Math.sin(roastClock.current * 14 + i * 2.1);
          placeCard(
            cards,
            i,
            tmpWorld.x,
            tmpWorld.y,
            tmpWorld.z,
            0.22 * flicker * fade,
            0.42 * flicker * fade,
          );
        }
      }
      cards.instanceMatrix.needsUpdate = true;
    }

    const pos = wispGeo.getAttribute("position") as THREE.BufferAttribute;
    const col = wispGeo.getAttribute("color") as THREE.BufferAttribute;
    const size = wispGeo.getAttribute("size") as THREE.BufferAttribute;
    if (bodyOn) {
      let want = phase === "cooked" ? 4 : 14;
      for (const p of wisps.current) {
        if (want <= 0) break;
        if (p.alive) continue;
        p.alive = true;
        p.age = 0;
        p.life = 0.28 + Math.random() * 0.4;
        if (samplesRef.current.length) {
          const s = samplesRef.current[(Math.random() * samplesRef.current.length) | 0];
          s.mesh.localToWorld(tmpWorld.copy(s.local));
          p.x = tmpWorld.x;
          p.y = tmpWorld.y;
          p.z = tmpWorld.z;
        }
        p.vx = (Math.random() - 0.5) * 0.25;
        p.vy = (Math.random() - 0.5) * 0.25;
        p.vz = 0.7 + Math.random() * 0.9;
        p.size = 0.28 + Math.random() * 0.35;
        want--;
      }
    }
    for (let i = 0; i < wisps.current.length; i++) {
      const p = wisps.current[i];
      if (!p.alive) {
        pos.setXYZ(i, 0, 0, -20);
        size.setX(i, 0);
        continue;
      }
      p.age += delta;
      if (p.age >= p.life) {
        p.alive = false;
        pos.setXYZ(i, 0, 0, -20);
        size.setX(i, 0);
        continue;
      }
      p.x += p.vx * delta;
      p.y += p.vy * delta;
      p.z += p.vz * delta;
      pos.setXYZ(i, p.x, p.y, p.z);
      col.setXYZ(i, 1.0, 0.35, 0.05);
      size.setX(i, p.size * (1 - p.age / p.life));
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    size.needsUpdate = true;
  });

  if (!root) return null;

  return (
    <group>
      <group ref={wrapRef} rotation={[Math.PI / 2, 0, 0]}>
        <group ref={birdRef}>
          <primitive object={root} />
        </group>
        <pointLight position={[0, 0.35, 0.2]} color="#ff4a12" intensity={2.2} distance={3.5} />
      </group>
      <instancedMesh
        ref={flameMeshRef}
        args={[flameGeo, flameMat, BIRD_CARDS]}
        frustumCulled={false}
      />
      <points geometry={wispGeo} material={wispMat} />
    </group>
  );
}
