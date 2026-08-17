import { useEffect, useMemo, useRef } from "react";
import type { MutableRefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import type { AnimationPlayerState } from "../hooks/useAnimationPlayer";

export const WATERING_ANIM_IDS = new Set(["FemaleWatering"]);
export const BUCKET_POUR_ANIM_IDS = new Set(["FemaleBucketPour"]);

type PourMode = "stream" | "dump";

const POUR_WINDOWS: Record<string, { start: number; end: number; mode: PourMode }> = {
  FemaleWatering: { start: 0.48, end: 1.78, mode: "stream" },
  FemaleBucketPour: { start: 0.58, end: 1.55, mode: "dump" },
};

export type LiquidKind = "water" | "milk" | "compost";

export interface VesselLiquidConfig {
  body: THREE.Vector3;
  radius: number;
  depth: number;
  kind: LiquidKind;
  spout?: THREE.Vector3;
  spoutDir?: THREE.Vector3;
  /** Open rim / mouth center in tool space (bucket dump emit). */
  rim?: THREE.Vector3;
  /** Keep the liquid volume inside the vessel; only the surface tilts a little. */
  confine?: boolean;
  /** Bottom radius when the vessel tapers. Defaults to radius. */
  bottomRadius?: number;
  /** Max slosh tilt in radians. */
  maxSlosh?: number;
  /** Droplet size / speed multiplier vs the watering can. */
  splashScale?: number;
}

const WATERING_CAN_WATER: VesselLiquidConfig = {
  body: new THREE.Vector3(-0.095, 0.055, 0),
  radius: 0.066,
  depth: 0.118,
  kind: "water",
  spout: new THREE.Vector3(-0.28, 0.099, 0),
  spoutDir: new THREE.Vector3(-1, 0.18, 0).normalize(),
};

const BUCKET_LIQUID = {
  body: new THREE.Vector3(0, -0.178, 0),
  rim: new THREE.Vector3(0, -0.05, 0),
  radius: 0.078,
  bottomRadius: 0.068,
  depth: 0.118,
  confine: true,
  maxSlosh: 0.09,
  splashScale: 2.4,
} as const;

export const VESSEL_LIQUID_BY_TOOL: Record<string, VesselLiquidConfig> = {
  water_tin_watering_can: WATERING_CAN_WATER,
  water_bucket: {
    ...BUCKET_LIQUID,
    body: BUCKET_LIQUID.body.clone(),
    rim: BUCKET_LIQUID.rim.clone(),
    kind: "water",
  },
  milk_bucket: {
    ...BUCKET_LIQUID,
    body: BUCKET_LIQUID.body.clone(),
    rim: BUCKET_LIQUID.rim.clone(),
    kind: "milk",
  },
  compost_bucket: {
    ...BUCKET_LIQUID,
    body: BUCKET_LIQUID.body.clone(),
    rim: BUCKET_LIQUID.rim.clone(),
    kind: "compost",
    maxSlosh: 0.03,
    splashScale: 1,
  },
};

const PALETTE = {
  water: {
    surface: new THREE.Color("#2f9ee0"),
    deep: new THREE.Color("#1568a8"),
    drop: "#6ec8ff",
    emissive: "#1a6fa8",
    foam: new THREE.Color("#dff4ff"),
    straw: new THREE.Color("#dff4ff"),
    highlight: new THREE.Vector3(0.18, 0.32, 0.4),
  },
  milk: {
    surface: new THREE.Color("#f3ead0"),
    deep: new THREE.Color("#e2d2a4"),
    drop: "#fff6dc",
    emissive: "#c4a86a",
    foam: new THREE.Color("#fffdf6"),
    straw: new THREE.Color("#fffdf6"),
    highlight: new THREE.Vector3(0.22, 0.18, 0.1),
  },
  compost: {
    surface: new THREE.Color("#3b2718"),
    deep: new THREE.Color("#24160c"),
    drop: "#3b2718",
    emissive: "#000000",
    foam: new THREE.Color("#2a1a10"),
    straw: new THREE.Color("#4a3420"),
    highlight: new THREE.Vector3(0, 0, 0),
  },
} as const;

const DIRT_COLORS = [
  new THREE.Color("#2a1a10"),
  new THREE.Color("#3b2718"),
  new THREE.Color("#4a3420"),
  new THREE.Color("#301e10"),
  new THREE.Color("#24160c"),
  new THREE.Color("#3f2c18"),
];

function dirtColor(seed: number, target: THREE.Color) {
  target.copy(DIRT_COLORS[Math.floor(seed * DIRT_COLORS.length) % DIRT_COLORS.length]);
  return target;
}

type CompostPack = {
  p: [number, number, number];
  r: [number, number, number];
  s: [number, number, number];
  c: string;
};

const COMPOST_LIFT = 0.078;

function makeCompostPackLayout(radius: number, depth: number): CompostPack[] {
  const hex = ["#2a1a10", "#3b2718", "#4a3420", "#301e10", "#24160c", "#3f2c18"];
  const packs: CompostPack[] = [];
  const lift = COMPOST_LIFT;
  const layers = [
    { y: lift + 0.04, ring: 0.12, n: 1, s: 0.03 },
    { y: lift + 0.028, ring: 0.46, n: 6, s: 0.026 },
    { y: lift + 0.014, ring: 0.7, n: 8, s: 0.024 },
    { y: lift + 0.0, ring: 0.86, n: 9, s: 0.022 },
    { y: lift - 0.018, ring: 0.8, n: 8, s: 0.023 },
    { y: lift - 0.038, ring: 0.64, n: 7, s: 0.022 },
    { y: lift - 0.058, ring: 0.48, n: 5, s: 0.021 },
    { y: -depth * 0.28, ring: 0.4, n: 4, s: 0.02 },
  ];
  let i = 0;
  for (const layer of layers) {
    for (let k = 0; k < layer.n; k++) {
      const a = layer.n === 1 ? 0 : (k / layer.n) * Math.PI * 2 + layer.y * 8;
      const jitter = 0.82 + ((k * 13 + i * 7) % 9) * 0.02;
      const x = Math.cos(a) * radius * layer.ring * jitter;
      const z = Math.sin(a) * radius * layer.ring * jitter;
      const s = layer.s * (0.92 + (k % 4) * 0.07);
      packs.push({
        p: [x, layer.y, z],
        r: [k * 0.9, i * 0.45, k * 0.35],
        s: [s * 1.25, s * 1.4, s * 1.2],
        c: hex[(k + i) % hex.length],
      });
      i++;
    }
  }
  return packs;
}

function makeDirtTexture() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const img = ctx.createImageData(size, size);
  for (let i = 0; i < size * size; i++) {
    const n = 26 + ((i * 13) % 19) + ((i * 7) % 9);
    const j = i * 4;
    img.data[j] = n + 16;
    img.data[j + 1] = n + 6;
    img.data[j + 2] = Math.max(8, n - 4);
    img.data[j + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  for (let k = 0; k < 280; k++) {
    ctx.fillStyle = k % 4 === 0 ? "rgb(18,12,7)" : "rgb(62,44,28)";
    ctx.fillRect((k * 17) % size, (k * 29) % size, 1 + (k % 2), 1 + (k % 2));
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2.5, 2.5);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

function makeCompostDirtMaterial(tex: THREE.Texture, color: string | THREE.Color) {
  return new THREE.MeshLambertMaterial({
    map: tex,
    color,
    flatShading: true,
  });
}

const MAX_DROPS = 260;
const MAX_SPLATS = 96;
const GROUND_Z = 0.02;
const GRAVITY = new THREE.Vector3(0, 0, -7.2);

const _worldPos = new THREE.Vector3();
const _worldQuat = new THREE.Quaternion();
const _invQuat = new THREE.Quaternion();
const _worldVel = new THREE.Vector3();
const _worldAcc = new THREE.Vector3();
const _localAcc = new THREE.Vector3();
const _localG = new THREE.Vector3();
const _spoutWorld = new THREE.Vector3();
const _spoutDirW = new THREE.Vector3();
const _upWorld = new THREE.Vector3();
const _emitPos = new THREE.Vector3();
const _emitVel = new THREE.Vector3();
const _tmp = new THREE.Vector3();
const _color = new THREE.Color();
const _dummy = new THREE.Object3D();

interface Drop {
  pos: THREE.Vector3;
  vel: THREE.Vector3;
  life: number;
  maxLife: number;
  size: number;
  seed: number;
  splash?: boolean;
  fromPour?: boolean;
}

interface Splat {
  pos: THREE.Vector3;
  life: number;
  maxLife: number;
  maxSize: number;
}

function makeLiquidMaterial(kind: LiquidKind, surface: boolean) {
  const pal = PALETTE[kind];
  const milk = kind === "milk";
  const compost = kind === "compost";

  if (compost) {
    return new THREE.MeshLambertMaterial({
      color: surface ? pal.surface : pal.deep,
      flatShading: true,
    });
  }

  const mat = new THREE.MeshPhysicalMaterial({
    color: surface ? pal.surface : pal.deep,
    roughness: milk ? 0.38 : 0.12,
    metalness: 0.02,
    transparent: true,
    opacity: milk ? (surface ? 0.94 : 0.88) : surface ? 0.78 : 0.55,
    transmission: milk ? 0.04 : surface ? 0.35 : 0.2,
    thickness: milk ? 0.08 : 0.04,
    ior: milk ? 1.42 : 1.33,
    side: THREE.DoubleSide,
    depthWrite: false,
  });

  if (!surface) return mat;

  const hx = pal.highlight.x;
  const hy = pal.highlight.y;
  const hz = pal.highlight.z;

  mat.onBeforeCompile = (shader) => {
    shader.uniforms.uTime = { value: 0 };
    shader.uniforms.uSlosh = { value: 0 };
    mat.userData.shader = shader;
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
         uniform float uTime;
         uniform float uSlosh;
         varying float vWave;`,
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
         float w1 = sin(position.x * 52.0 + uTime * 6.2);
         float w2 = sin(position.y * 44.0 - uTime * 4.8);
         float w3 = sin((position.x + position.y) * 28.0 + uTime * 7.4);
         vWave = (w1 + w2 * 0.7 + w3 * 0.5) * (0.0016 + uSlosh * 0.007);
         transformed.z += vWave;`,
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
         varying float vWave;`,
      )
      .replace(
        "#include <opaque_fragment>",
        `gl_FragColor.rgb += vec3(${hx}, ${hy}, ${hz}) * smoothstep(0.0, 0.004, vWave);
         #include <opaque_fragment>`,
      );
  };

  return mat;
}

function pourState(player: AnimationPlayerState | null): {
  fill: number;
  pouring: boolean;
  mode: PourMode | "none";
} {
  const window = player?.activeAnimId ? POUR_WINDOWS[player.activeAnimId] : undefined;
  if (!window) return { fill: 1, pouring: false, mode: "none" };
  const t = player!.currentTime;
  const u = THREE.MathUtils.clamp((t - window.start) / (window.end - window.start), 0, 1);
  const drained = u * u * (3 - 2 * u);
  const fill = 1 - drained;
  return { fill, pouring: t >= window.start && fill > 0.015, mode: window.mode };
}

export default function VesselLiquid({
  config,
  playerRef,
}: {
  config: VesselLiquidConfig;
  playerRef?: MutableRefObject<AnimationPlayerState | null>;
}) {
  const {
    body,
    radius,
    depth,
    kind,
    spout,
    spoutDir,
    rim,
    confine = false,
    bottomRadius,
    maxSlosh = 0.38,
    splashScale = 1,
  } = config;
  const pal = PALETTE[kind];
  const viscous = kind === "milk";
  const chunky = kind === "compost";
  const innerBottom = bottomRadius ?? radius;

  const groupRef = useRef<THREE.Group>(null);
  const sloshRef = useRef<THREE.Group>(null);
  const volumeRef = useRef<THREE.Mesh>(null);
  const surfaceRef = useRef<THREE.Mesh>(null);
  const packsRef = useRef<THREE.Group>(null);
  const dirtTex = useMemo(() => (chunky ? makeDirtTexture() : null), [chunky]);
  const compostPacks = useMemo(
    () => (chunky ? makeCompostPackLayout(radius, depth) : []),
    [chunky, radius, depth],
  );
  const surfaceMat = useMemo(() => {
    if (chunky && dirtTex) return makeCompostDirtMaterial(dirtTex, pal.surface);
    return makeLiquidMaterial(kind, true);
  }, [kind, chunky, dirtTex, pal.surface]);
  const volumeMat = useMemo(() => {
    if (chunky && dirtTex) return makeCompostDirtMaterial(dirtTex, pal.deep);
    return makeLiquidMaterial(kind, false);
  }, [kind, chunky, dirtTex, pal.deep]);
  const dropMat = useMemo(
    () =>
      chunky && dirtTex
        ? makeCompostDirtMaterial(dirtTex, "#ffffff")
        : new THREE.MeshStandardMaterial({
            color: pal.drop,
            emissive: pal.emissive,
            emissiveIntensity: viscous ? 0.2 : 0.45,
            roughness: viscous ? 0.45 : 0.2,
            metalness: 0,
            transparent: true,
            opacity: 0.92,
            depthWrite: false,
          }),
    [pal.drop, pal.emissive, viscous, chunky, dirtTex],
  );

  const splatMat = useMemo(
    () =>
      chunky && dirtTex
        ? makeCompostDirtMaterial(dirtTex, "#ffffff")
        : new THREE.MeshStandardMaterial({
            color: pal.surface,
            emissive: pal.emissive,
            emissiveIntensity: viscous ? 0.1 : 0.22,
            roughness: viscous ? 0.42 : 0.16,
            metalness: 0,
            transparent: true,
            opacity: 0.82,
            depthWrite: false,
            side: THREE.DoubleSide,
          }),
    [pal.surface, pal.emissive, viscous, chunky, dirtTex],
  );

  const { scene } = useThree();
  const dropsRef = useRef<Drop[]>([]);
  const splatsRef = useRef<Splat[]>([]);
  const meshRef = useRef<THREE.InstancedMesh | null>(null);
  const splatMeshRef = useRef<THREE.InstancedMesh | null>(null);
  const prevPos = useRef(new THREE.Vector3());
  const prevVel = useRef(new THREE.Vector3());
  const slosh = useRef({ x: 0, z: 0, vx: 0, vz: 0 });
  const warmup = useRef(0);
  const emitCool = useRef(0);
  const seeded = useRef(false);
  const fillRef = useRef(1);
  const pourBudgetRef = useRef(0);
  const pourQuota = chunky ? compostPacks.length || 32 : viscous ? 52 : 64;

  useEffect(() => {
    const dropGeom = chunky ? new THREE.IcosahedronGeometry(1, 0) : new THREE.SphereGeometry(1, 8, 6);
    const mesh = new THREE.InstancedMesh(dropGeom, dropMat, MAX_DROPS);
    mesh.frustumCulled = false;
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_DROPS * 3), 3);
    mesh.count = 0;
    meshRef.current = mesh;
    scene.add(mesh);

    const splatGeom = chunky ? new THREE.IcosahedronGeometry(1, 0) : new THREE.CircleGeometry(1, 20);
    const splats = new THREE.InstancedMesh(splatGeom, splatMat, MAX_SPLATS);
    splats.frustumCulled = false;
    splats.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    splats.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_SPLATS * 3), 3);
    splats.count = 0;
    splatMeshRef.current = splats;
    scene.add(splats);

    return () => {
      scene.remove(mesh);
      scene.remove(splats);
      mesh.geometry.dispose();
      splats.geometry.dispose();
    };
  }, [scene, dropMat, splatMat, chunky]);

  useEffect(() => {
    return () => {
      surfaceMat.dispose();
      volumeMat.dispose();
      dropMat.dispose();
      splatMat.dispose();
      dirtTex?.dispose();
    };
  }, [surfaceMat, volumeMat, dropMat, splatMat, dirtTex]);

  useFrame((_, dt) => {
    const group = groupRef.current;
    const sloshGrp = sloshRef.current;
    if (!group) return;

    const clamped = Math.min(dt, 1 / 30);
    group.getWorldPosition(_worldPos);
    group.getWorldQuaternion(_worldQuat);

    if (!seeded.current) {
      prevPos.current.copy(_worldPos);
      prevVel.current.set(0, 0, 0);
      seeded.current = true;
      return;
    }

    _worldVel.copy(_worldPos).sub(prevPos.current).divideScalar(clamped);
    _worldAcc.copy(_worldVel).sub(prevVel.current).divideScalar(clamped);
    prevPos.current.copy(_worldPos);
    prevVel.current.copy(_worldVel);

    warmup.current += clamped;
    const live = warmup.current > 0.12;

    _invQuat.copy(_worldQuat).invert();
    _localAcc.copy(_worldAcc).applyQuaternion(_invQuat);
    _localG.copy(GRAVITY).applyQuaternion(_invQuat);

    const targetX = THREE.MathUtils.clamp(-_localAcc.x * 0.012 - _localG.x * 0.04, -maxSlosh, maxSlosh);
    const targetZ = THREE.MathUtils.clamp(-_localAcc.z * 0.012 - _localG.z * 0.04, -maxSlosh, maxSlosh);

    const s = slosh.current;
    const spring = chunky ? 16 : viscous ? 22 : 38;
    const damp = chunky ? 9.4 : viscous ? 8.2 : 6.5;
    s.vx += (targetX - s.x) * spring * clamped - s.vx * damp * clamped;
    s.vz += (targetZ - s.z) * spring * clamped - s.vz * damp * clamped;
    s.x = THREE.MathUtils.clamp(s.x + s.vx * clamped, -maxSlosh, maxSlosh);
    s.z = THREE.MathUtils.clamp(s.z + s.vz * clamped, -maxSlosh, maxSlosh);

    const { fill, pouring, mode } = pourState(playerRef?.current ?? null);
    const prevFill = fillRef.current;
    if (fill < prevFill - 1e-5) {
      pourBudgetRef.current += (prevFill - fill) * pourQuota;
    } else if (fill > prevFill + 0.05) {
      pourBudgetRef.current = 0;
    }
    fillRef.current = fill;
    const volume = volumeRef.current;
    const surface = surfaceRef.current;
    const shown = fill > 0.03;
    if (volume) {
      volume.visible = shown;
      volume.scale.y = Math.max(fill, 0.001);
      volume.position.y = -depth + (depth * fill) * 0.5 + (chunky ? COMPOST_LIFT : 0);
    }
    if (surface) {
      surface.visible = !chunky && shown;
      surface.position.y = -depth * (1 - fill);
    }
    if (packsRef.current) {
      const surfaceY = -depth * (1 - fill) + (chunky ? COMPOST_LIFT : 0);
      packsRef.current.visible = shown;
      for (const child of packsRef.current.children) {
        child.visible = child.position.y <= surfaceY + 0.05;
      }
    }

    if (sloshGrp) {
      if (confine) {
        sloshGrp.rotation.z = -s.x * 0.35;
        sloshGrp.rotation.x = s.z * 0.35;
      } else {
        sloshGrp.rotation.z = -s.x;
        sloshGrp.rotation.x = s.z;
      }
    }

    const sloshMag = Math.hypot(s.x, s.z);
    const sloshSpeed = Math.hypot(s.vx, s.vz);
    const shader = surfaceMat.userData.shader as
      | { uniforms: { uTime: { value: number }; uSlosh: { value: number } } }
      | undefined;
    if (shader) {
      shader.uniforms.uTime.value += clamped;
      shader.uniforms.uSlosh.value = sloshMag + sloshSpeed * 0.15;
    }

    if (spout && spoutDir) {
      _spoutWorld.copy(spout).applyMatrix4(group.matrixWorld);
      _spoutDirW.copy(spoutDir).applyQuaternion(_worldQuat);
    }
    _upWorld.set(0, 1, 0).applyQuaternion(_worldQuat);

    const scripted = mode !== "none";
    const dump = mode === "dump";
    const stream = mode === "stream";
    const spoutDown = spout ? -_spoutDirW.z : 0;
    const rimPour = !spout && -_upWorld.z > 0.22;
    const speed = _worldVel.length();
    const shake = live ? _worldAcc.length() : 0;

    emitCool.current -= clamped;
    if (live && emitCool.current <= 0) {
      const moveSplash = !chunky && !scripted;
      const sloshBurst =
        moveSplash &&
        (chunky
          ? sloshSpeed > 0.55 || sloshMag > 0.06 || shake > 2.4
          : sloshSpeed > 1.6 || sloshMag > 0.16 || shake > 8);
      const pour = pouring || (!scripted && (spoutDown > 0.22 || rimPour));
      const travelSplash = moveSplash && (chunky ? speed > 0.22 && shake > 1.1 : speed > 0.55 && shake > 3.5);

      if (sloshBurst || pour || travelSplash) {
        if (dump && pouring) {
          const want = chunky ? 1 + (Math.random() < 0.4 ? 1 : 0) : 2 + Math.floor(Math.random() * 2);
          const n = takePourBudget(want, fill);
          for (let i = 0; i < n; i++) spawnDumpDrop(group);
          emitCool.current = chunky ? 0.045 : 0.024;
        } else if (stream && pouring) {
          const n = takePourBudget(1 + (Math.random() < 0.5 ? 1 : 0), fill);
          for (let i = 0; i < n; i++) spawnDrop(group, false, radius, body, true, true);
          emitCool.current = 0.022;
        } else {
          const burstMul = splashScale > 1 ? 2 : 1;
          const n = pour
            ? (4 + Math.floor(Math.random() * 4)) * burstMul
            : sloshBurst
              ? ((chunky ? 3 : 2) + Math.floor(Math.random() * (chunky ? 5 : 4))) * burstMul
              : (1 + Math.floor(Math.random() * 2)) * burstMul;
          for (let i = 0; i < n; i++) {
            const fromSurface =
              !stream &&
              (!spout || ((sloshBurst && Math.random() < 0.45) || rimPour));
            spawnDrop(group, fromSurface, radius, body, false, pouring);
          }
          emitCool.current = pour ? 0.028 : sloshBurst ? (chunky ? 0.032 : 0.045) : 0.07;
        }
      }
    }

    stepDrops(clamped, pal.surface, pal.foam);
  });

  function takePourBudget(want: number, fill: number) {
    if (pourBudgetRef.current <= 0) return 0;
    const available = fill < 0.05 ? Math.ceil(pourBudgetRef.current) : Math.floor(pourBudgetRef.current);
    const n = Math.min(want, Math.max(0, available));
    pourBudgetRef.current = Math.max(0, pourBudgetRef.current - n);
    return n;
  }

  function allocDrop(): Drop {
    const drops = dropsRef.current;
    if (drops.length >= MAX_DROPS) return drops[Math.floor(Math.random() * drops.length)];
    const drop: Drop = {
      pos: new THREE.Vector3(),
      vel: new THREE.Vector3(),
      life: 0,
      maxLife: 0,
      size: 0,
      seed: 0,
    };
    drops.push(drop);
    return drop;
  }

  function spawnDumpDrop(group: THREE.Group) {
    const drop = allocDrop();
    const mouth = rim ?? _tmp.set(0, -0.05, 0);

    // Spill over the downhill lip of the open rim (tool +Y is the mouth).
    const gx = _localG.x;
    const gz = _localG.z;
    const glen = Math.hypot(gx, gz);
    const ang = glen > 1e-4 ? Math.atan2(gz, gx) : Math.random() * Math.PI * 2;
    const lip = 0.78 + Math.random() * 0.22;
    _tmp.set(Math.cos(ang) * radius * lip, (Math.random() - 0.5) * 0.012, Math.sin(ang) * radius * lip);
    _emitPos.set(mouth.x + _tmp.x, mouth.y + _tmp.y, mouth.z + _tmp.z);

    // Nudge the spawn just outside the mouth so drops aren't born inside the mesh.
    const out = _upWorld.z < 0 ? 0.028 : 0.012;
    _emitPos.y += out;
    _emitPos.applyMatrix4(group.matrixWorld);

    // Fall out: gravity first, plus a little push out of the opening.
    _emitVel.copy(GRAVITY).normalize().multiplyScalar(1.7 + Math.random() * 0.5);
    if (_upWorld.z < 0.05) {
      _emitVel.addScaledVector(_upWorld, 0.45 + Math.random() * 0.25);
    } else if (glen > 1e-4) {
      _tmp.set(gx / glen, 0, gz / glen).applyQuaternion(_worldQuat);
      _emitVel.addScaledVector(_tmp, 0.55 + Math.random() * 0.25);
    }
    _emitVel.add(_worldVel);
    _emitVel.x += (Math.random() - 0.5) * 0.16;
    _emitVel.y += (Math.random() - 0.5) * 0.16;
    _emitVel.z = Math.min(_emitVel.z, chunky ? -0.95 : -1.15);
    if (viscous) _emitVel.multiplyScalar(0.82);
    if (chunky) {
      _emitVel.multiplyScalar(0.78);
      // Character faces −Y in this Z-up viewer. Throw the dump farther out in front.
      _emitPos.y -= 0.08;
      _emitVel.y -= 1.15 + Math.random() * 0.3;
    }

    drop.pos.copy(_emitPos);
    drop.vel.copy(_emitVel);
    drop.maxLife = (chunky ? 1.05 : 0.9) + Math.random() * 0.35;
    drop.life = drop.maxLife;
    drop.size = chunky ? 0.02 + Math.random() * 0.01 : ((0.007 + Math.random() * 0.006) * (viscous ? 1.15 : 1) * Math.min(splashScale, 1.35));
    drop.seed = Math.random();
    drop.splash = false;
    drop.fromPour = true;
  }

  function spawnDrop(
    group: THREE.Group,
    fromSurface: boolean,
    vesselRadius: number,
    vesselBody: THREE.Vector3,
    stream = false,
    fromPour = false,
  ) {
    const drop = allocDrop();
    const sizeMul = (chunky ? 1 : viscous ? 1.15 : 1) * Math.min(splashScale, 1.35);

    if (fromSurface) {
      const ang = Math.atan2(slosh.current.z, slosh.current.x) + (Math.random() - 0.5) * 1.1;
      _tmp.set(Math.cos(ang) * vesselRadius * 0.82, 0.006, Math.sin(ang) * vesselRadius * 0.82);
      _emitPos.copy(vesselBody).add(_tmp).applyMatrix4(group.matrixWorld);
      _emitVel
        .copy(_tmp)
        .applyQuaternion(_worldQuat)
        .multiplyScalar((1.8 + slosh.current.vx * slosh.current.vx) * splashScale)
        .add(_worldVel)
        .add(_tmp.copy(GRAVITY).multiplyScalar(-0.04));
      _emitVel.z += (0.35 + Math.random() * 0.45) * splashScale;
    } else {
      _emitPos.copy(_spoutWorld);
      _emitPos.x += (Math.random() - 0.5) * 0.012;
      _emitPos.y += (Math.random() - 0.5) * 0.012;
      _emitPos.z += (Math.random() - 0.5) * 0.008;
      if (stream) {
        _emitVel.copy(_spoutDirW);
        if (_emitVel.lengthSq() < 1e-6) _emitVel.set(0, -0.5, -0.85);
        _emitVel.normalize();
        _emitVel.z = Math.min(_emitVel.z, -0.55);
        _emitVel.normalize();
        _emitVel.multiplyScalar(1.15 + Math.random() * 0.4);
        _emitVel.x += (Math.random() - 0.5) * 0.08;
        _emitVel.y += (Math.random() - 0.5) * 0.08;
        _emitVel.add(_worldVel);
      } else {
        const jet = 0.55 + Math.random() * 0.7;
        _emitVel.copy(_spoutDirW).multiplyScalar(jet).add(_worldVel);
        _emitVel.x += (Math.random() - 0.5) * 0.18;
        _emitVel.y += (Math.random() - 0.5) * 0.18;
        _emitVel.z += 0.08 + Math.random() * 0.22;
      }
    }

    drop.pos.copy(_emitPos);
    drop.vel.copy(_emitVel);
    drop.maxLife = stream
      ? 0.7 + Math.random() * 0.4
      : (chunky ? 0.7 : viscous ? 0.45 : 0.35) + Math.random() * 0.45;
    drop.life = drop.maxLife;
    drop.size = (chunky ? 0.01 : 0.0045) + Math.random() * (chunky ? 0.012 : 0.0055);
    drop.size *= sizeMul;
    drop.seed = Math.random();
    drop.splash = false;
    drop.fromPour = fromPour;
  }

  function spawnSplat(x: number, y: number, dropSize: number) {
    const splats = splatsRef.current;
    const splat: Splat =
      splats.length >= MAX_SPLATS
        ? splats[Math.floor(Math.random() * splats.length)]
        : { pos: new THREE.Vector3(), life: 0, maxLife: 0, maxSize: 0 };
    if (splats.length < MAX_SPLATS) splats.push(splat);
    splat.pos.set(x, y, GROUND_Z);
    splat.maxLife = (chunky ? 2.0 : viscous ? 3.4 : 3.0) + Math.random() * 0.5;
    splat.life = splat.maxLife;
    splat.maxSize = dropSize * (chunky ? 1.65 : viscous ? 8 : 7.2) * (0.85 + Math.random() * 0.25);
  }

  function spawnSplashDrops(x: number, y: number, impactSpeed: number) {
    const n = chunky ? (Math.random() < 0.35 ? 1 : 0) : 1 + Math.floor(Math.random() * 2);
    const sizeMul = (chunky ? 1 : viscous ? 1.05 : 1) * Math.min(splashScale, 1.2);
    for (let i = 0; i < n; i++) {
      const drop = allocDrop();
      const ang = Math.random() * Math.PI * 2;
      const speed = (0.45 + Math.random() * 0.65) * (0.7 + impactSpeed * 0.1);
      drop.pos.set(x, y, GROUND_Z + 0.012);
      drop.vel.set(
        Math.cos(ang) * speed,
        Math.sin(ang) * speed - 0.12,
        0.7 + Math.random() * 0.85,
      );
      drop.maxLife = 0.22 + Math.random() * 0.16;
      drop.life = drop.maxLife;
      drop.size = (0.0025 + Math.random() * 0.003) * sizeMul;
      drop.seed = Math.random();
      drop.splash = true;
      drop.fromPour = false;
    }
  }

  function stepDrops(dt: number, base: THREE.Color, foam: THREE.Color) {
    const mesh = meshRef.current;
    if (!mesh) return;
    const drops = dropsRef.current;
    const hits: Array<{ x: number; y: number; size: number; speed: number; splash: boolean; fromPour: boolean }> = [];
    let w = 0;
    for (let i = 0; i < drops.length; i++) {
      const d = drops[i];
      d.life -= dt;
      if (d.life <= 0) continue;
      d.vel.addScaledVector(GRAVITY, dt);
      d.vel.multiplyScalar(chunky ? 0.96 : viscous ? 0.972 : 0.985);
      d.pos.addScaledVector(d.vel, dt);
      if (d.pos.z < GROUND_Z) {
        hits.push({
          x: d.pos.x,
          y: d.pos.y,
          size: d.size,
          speed: d.vel.length(),
          splash: !!d.splash,
          fromPour: !!d.fromPour,
        });
        continue;
      }
      const t = d.life / d.maxLife;
      const size = chunky ? d.size * (0.88 + t * 0.12) : d.size * (0.35 + t * 0.65);
      _dummy.position.copy(d.pos);
      if (chunky) {
        const a = d.seed * Math.PI * 2;
        _dummy.rotation.set(d.life * 3.1 + a, d.life * 2.2, a * 1.6);
        _dummy.scale.set(size * 1.3, size * 1.15, size * 1.25);
        dirtColor(d.seed, _color);
      } else {
        _dummy.rotation.set(0, 0, 0);
        _dummy.scale.setScalar(size);
        _color.copy(base).lerp(foam, 1 - t);
      }
      _dummy.updateMatrix();
      mesh.setMatrixAt(w, _dummy.matrix);
      mesh.setColorAt(w, _color);
      if (i !== w) drops[w] = d;
      w++;
    }
    drops.length = w;
    mesh.count = w;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;

    for (const hit of hits) {
      if (!hit.fromPour) continue;
      spawnSplat(hit.x, hit.y, hit.size);
      if (!chunky && !hit.splash && Math.random() < 0.38) spawnSplashDrops(hit.x, hit.y, hit.speed);
    }

    const splatMesh = splatMeshRef.current;
    if (!splatMesh) return;
    const splats = splatsRef.current;
    let sw = 0;
    for (let i = 0; i < splats.length; i++) {
      const s = splats[i];
      s.life -= dt;
      if (s.life <= 0) continue;
      const u = 1 - s.life / s.maxLife;
      const grow = u < 0.12 ? u / 0.12 : u > 0.72 ? 1 - (u - 0.72) / 0.28 : 1;
      const size = s.maxSize * (0.35 + grow * 0.65);
      _dummy.position.copy(s.pos);
      if (chunky) {
        const yaw = s.pos.x * 13.1 + s.pos.y * 8.7;
        _dummy.rotation.set(0.45, 0.2, yaw);
        _dummy.scale.set(size * 1.15, size * 0.85, size * 0.38);
        dirtColor((Math.abs(s.pos.x * 7.1 + s.pos.y) % 1), _color);
      } else {
        _dummy.rotation.set(0, 0, 0);
        _dummy.scale.set(size, size, 1);
        _color.copy(base).lerp(foam, u);
      }
      _dummy.updateMatrix();
      splatMesh.setMatrixAt(sw, _dummy.matrix);
      splatMesh.setColorAt(sw, _color);
      if (i !== sw) splats[sw] = s;
      sw++;
    }
    splats.length = sw;
    splatMesh.count = sw;
    splatMesh.instanceMatrix.needsUpdate = true;
    if (splatMesh.instanceColor) splatMesh.instanceColor.needsUpdate = true;
  }

  return (
    <group ref={groupRef}>
      <group ref={sloshRef} position={body.toArray()}>
        <mesh ref={volumeRef} position={[0, -depth * 0.5, 0]} material={volumeMat} renderOrder={2}>
          <cylinderGeometry args={[radius * 0.96, innerBottom, depth, 24, 1, !chunky]} />
        </mesh>
        {!chunky && (
          <mesh ref={surfaceRef} rotation={[-Math.PI / 2, 0, 0]} material={surfaceMat} renderOrder={3}>
            <circleGeometry args={[radius * 0.96, 32]} />
          </mesh>
        )}
        {chunky && (
          <group ref={packsRef}>
            {compostPacks.map((n, i) => (
              <mesh key={i} position={n.p} rotation={n.r} scale={n.s} renderOrder={4}>
                <icosahedronGeometry args={[1, 0]} />
                <meshLambertMaterial map={dirtTex ?? undefined} color={n.c} flatShading />
              </mesh>
            ))}
          </group>
        )}
      </group>
    </group>
  );
}
