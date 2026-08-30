import { useLayoutEffect, useMemo, useRef } from "react";
import type { MutableRefObject } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

const COUNT = 240;
const CLIP_NAME = "attack2";
const LAUNCHES = [0.36, 0.44, 0.52];
const FLIGHT = 0.22;
const BOOM_COUNT = 18;

interface Particle {
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
  cr: number;
  cg: number;
  cb: number;
}

function findEggs(scene: THREE.Object3D): THREE.Object3D[] {
  const found: THREE.Object3D[] = [];
  scene.traverse((obj) => {
    if (/^ChickenEgg_\d+$/.test(obj.name) || /^Egg_\d+$/.test(obj.name)) {
      found.push(obj);
    }
  });
  found.sort((a, b) => a.name.localeCompare(b.name));
  return found.filter((obj, i, all) => all.findIndex((o) => o.name === obj.name) === i);
}

export function chickenHasEggBurst(scene: THREE.Object3D): boolean {
  let hit = false;
  scene.traverse((obj) => {
    if (hit) return;
    if (/^ChickenEgg_/.test(obj.name) || /^Egg_/.test(obj.name)) hit = true;
  });
  return hit;
}

export function ChickenEggBurst({
  scene,
  clipName,
  actionRef,
}: {
  scene: THREE.Object3D;
  clipName: string | null;
  actionRef: MutableRefObject<THREE.AnimationAction | null>;
}) {
  const pointsRef = useRef<THREE.Points>(null);
  const eggsRef = useRef<THREE.Object3D[]>([]);
  const firedRef = useRef([false, false, false]);
  const prevTRef = useRef(-1);
  const tmpWorld = useMemo(() => new THREE.Vector3(), []);
  const tmpLocal = useMemo(() => new THREE.Vector3(), []);
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
      blending: THREE.NormalBlending,
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
          gl_PointSize = size * (280.0 / vDist);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        varying vec3 vColor;
        void main() {
          vec2 p = gl_PointCoord * 2.0 - 1.0;
          float r = length(p);
          if (r > 1.0) discard;
          float a = exp(-r * r * 2.6) * 0.95;
          gl_FragColor = vec4(vColor, a);
        }
      `,
    });
  }, []);

  useLayoutEffect(() => {
    eggsRef.current = findEggs(scene);
    firedRef.current = [false, false, false];
    prevTRef.current = -1;
    particles.current = Array.from({ length: COUNT }, () => ({
      alive: false,
      age: 0,
      life: 1,
      x: 0,
      y: 0,
      z: 0,
      vx: 0,
      vy: 0,
      vz: 0,
      size: 0.08,
      cr: 1,
      cg: 0.8,
      cb: 0.2,
    }));
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [scene, geometry, material]);

  useFrame((_, delta) => {
    const pts = pointsRef.current;
    if (!pts) return;
    const action = actionRef.current;
    const active = clipName?.toLowerCase() === CLIP_NAME && !!action;
    const duration = action ? Math.max(action.getClip().duration, 0.001) : 2;
    const t = active ? action.time / duration : -1;
    if (t < 0.05 && prevTRef.current > 0.2) {
      firedRef.current = [false, false, false];
    }
    prevTRef.current = t;

    const host = pts.parent;
    if (host) {
      host.updateWorldMatrix(true, false);
      tmpInv.copy(host.matrixWorld).invert();
    }

    if (active) {
      for (let i = 0; i < LAUNCHES.length; i++) {
        const impact = LAUNCHES[i] + FLIGHT;
        if (firedRef.current[i] || t < impact) continue;
        firedRef.current[i] = true;
        const egg = eggsRef.current[i] ?? eggsRef.current[0];
        if (egg) {
          egg.getWorldPosition(tmpWorld);
        } else {
          tmpWorld.set(0, 0, 0.04);
        }
        tmpLocal.copy(tmpWorld);
        if (host) tmpLocal.applyMatrix4(tmpInv);
        spawnBoom(particles.current, tmpLocal);
      }
    }

    const pos = pts.geometry.getAttribute("position") as THREE.BufferAttribute;
    const col = pts.geometry.getAttribute("color") as THREE.BufferAttribute;
    const siz = pts.geometry.getAttribute("size") as THREE.BufferAttribute;
    const dt = Math.min(delta, 0.05);
    let live = 0;
    for (let i = 0; i < COUNT; i++) {
      const p = particles.current[i];
      if (!p?.alive) {
        pos.setXYZ(i, 0, 0, -40);
        siz.setX(i, 0);
        continue;
      }
      p.age += dt;
      if (p.age >= p.life) {
        p.alive = false;
        pos.setXYZ(i, 0, 0, -40);
        siz.setX(i, 0);
        continue;
      }
      p.vz -= 9.2 * dt;
      p.vx *= 0.98;
      p.vy *= 0.98;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.z += p.vz * dt;
      if (p.z < 0.02) {
        p.z = 0.02;
        p.vz *= -0.18;
        p.vx *= 0.7;
        p.vy *= 0.7;
      }
      const u = p.age / p.life;
      pos.setXYZ(i, p.x, p.y, p.z);
      col.setXYZ(i, p.cr, p.cg, p.cb);
      siz.setX(i, p.size * (1.0 - u * u));
      live += 1;
    }
    pos.needsUpdate = true;
    col.needsUpdate = true;
    siz.needsUpdate = true;
    pts.visible = live > 0;
  });

  return (
    <points ref={pointsRef} frustumCulled={false}>
      <primitive object={geometry} attach="geometry" />
      <primitive object={material} attach="material" />
    </points>
  );
}

function spawnBoom(pool: Particle[], origin: THREE.Vector3) {
  let spawned = 0;
  for (const p of pool) {
    if (p.alive || spawned >= BOOM_COUNT) continue;
    const kind = spawned % 3;
    const yaw = Math.random() * Math.PI * 2;
    const up = 0.35 + Math.random() * 0.7;
    const out = 0.12 + Math.random() * 0.28;
    p.alive = true;
    p.age = 0;
    p.life = 0.18 + Math.random() * 0.16;
    p.x = origin.x;
    p.y = origin.y;
    p.z = origin.z + 0.03;
    p.vx = Math.cos(yaw) * out;
    p.vy = Math.sin(yaw) * out;
    p.vz = up;
    if (kind === 0) {
      p.cr = 1.0;
      p.cg = 0.78;
      p.cb = 0.22;
      p.size = 0.05 + Math.random() * 0.03;
    } else if (kind === 1) {
      p.cr = 0.98;
      p.cg = 0.92;
      p.cb = 0.62;
      p.size = 0.045 + Math.random() * 0.025;
    } else {
      p.cr = 0.95;
      p.cg = 0.95;
      p.cb = 0.90;
      p.size = 0.04 + Math.random() * 0.02;
    }
    spawned += 1;
  }
}
