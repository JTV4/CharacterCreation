import { useImperativeHandle, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { ForwardedRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";

const loader = new GLTFLoader();
loader.setMeshoptDecoder(MeshoptDecoder);

const SAMPLE_COUNT = 780;
const FLAME_COUNT = 900;
const SMOKE_COUNT = 420;
const EMBER_COUNT = 220;
const FLAME_CARD_COUNT = 280;
const TARGET_SPREAD_SEC = 8.2;
const CONNECT_K = 6;
const CONNECT_SCALE = 0.042;

const CHAR = new THREE.Color(0x1a120e);
const GLOW = new THREE.Color(0xff3d08);

export type BurnPhase =
  | "idle"
  | "ignited"
  | "spreading"
  | "engulfed"
  | "collapsing"
  | "rubble";

export interface BurnDownCommands {
  igniteDefault: () => void;
  reset: () => void;
}

export interface BuildingBurnDownProps {
  url: string;
  onBounds?: (box: THREE.Box3) => void;
  onPhase?: (phase: BurnPhase) => void;
  commandRef?: ForwardedRef<BurnDownCommands | null>;
}

type PieceKind = "floor" | "wall" | "trim" | "roof" | "other";

interface PieceState {
  object: THREE.Object3D;
  kind: PieceKind;
  restPos: THREE.Vector3;
  restQuat: THREE.Quaternion;
  restScale: THREE.Vector3;
  base: THREE.Vector3;
  center: THREE.Vector3;
  height: number;
  localMin: THREE.Vector3;
  localMax: THREE.Vector3;
  leanAxis: THREE.Vector3;
  tiltAxis: THREE.Vector3;
  leanMax: number;
  dropMax: number;
  collapseDelay: number;
  collapseDur: number;
  igniteAt: number;
  mats: Array<{
    mat: THREE.MeshStandardMaterial;
    color: THREE.Color;
    emissive: THREE.Color;
    emissiveIntensity: number;
    roughness: number;
  }>;
}

interface Sample {
  piece: number;
  local: THREE.Vector3;
  rest: THREE.Vector3;
  nx: number;
  ny: number;
  nz: number;
  igniteAt: number;
}

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
  heat: number;
}

function kindOf(name: string): PieceKind {
  const n = name.toLowerCase();
  if (n.includes("floor")) return "floor";
  if (n.includes("roof") || n.includes("tile")) return "roof";
  if (n.includes("trim") || n.includes("eave") || n.includes("door")) return "trim";
  if (n.includes("wall") || n.includes("gable")) return "wall";
  return "other";
}

function hashName(name: string): number {
  let h = 2166136261;
  for (let i = 0; i < name.length; i++) {
    h ^= name.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967295;
}

function easeInOut(t: number): number {
  const u = THREE.MathUtils.clamp(t, 0, 1);
  return u * u * (3 - 2 * u);
}

function easeInCubic(t: number): number {
  const u = THREE.MathUtils.clamp(t, 0, 1);
  return u * u * u;
}

function collectMeshes(root: THREE.Object3D): THREE.Mesh[] {
  const out: THREE.Mesh[] = [];
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (mesh.isMesh && mesh.geometry) out.push(mesh);
  });
  return out;
}

function pieceRoot(mesh: THREE.Mesh, scene: THREE.Object3D): THREE.Object3D {
  let cur: THREE.Object3D = mesh;
  while (cur.parent && cur.parent !== scene) cur = cur.parent;
  return cur;
}

function triangleAreas(
  pos: THREE.BufferAttribute,
  index: THREE.BufferAttribute | null,
): { areas: Float32Array; total: number; count: number } {
  const count = index ? index.count / 3 : pos.count / 3;
  const areas = new Float32Array(count);
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  let total = 0;
  for (let t = 0; t < count; t++) {
    const i0 = index ? index.getX(t * 3) : t * 3;
    const i1 = index ? index.getX(t * 3 + 1) : t * 3 + 1;
    const i2 = index ? index.getX(t * 3 + 2) : t * 3 + 2;
    a.fromBufferAttribute(pos, i0);
    b.fromBufferAttribute(pos, i1);
    c.fromBufferAttribute(pos, i2);
    const area = b.sub(a).cross(c.sub(a)).length() * 0.5;
    areas[t] = area;
    total += area;
  }
  return { areas, total, count };
}

function pickTriangle(
  areas: Float32Array,
  total: number,
  rand: number,
): number {
  let x = rand * total;
  for (let i = 0; i < areas.length; i++) {
    x -= areas[i];
    if (x <= 0) return i;
  }
  return areas.length - 1;
}

function cloneMeshMaterials(mesh: THREE.Mesh): THREE.Material[] {
  const src = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
  const cloned = src.map((m) => m.clone());
  mesh.material = cloned.length === 1 ? cloned[0] : cloned;
  return cloned;
}

function makePoints(count: number, additive: boolean): {
  geometry: THREE.BufferGeometry;
  material: THREE.ShaderMaterial;
} {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  geometry.setAttribute("size", new THREE.BufferAttribute(new Float32Array(count), 1));
  const material = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
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
        gl_PointSize = size * (900.0 / vDist);
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: additive
      ? `
      varying vec3 vColor;
      void main() {
        vec2 p = gl_PointCoord * 2.0 - 1.0;
        float r = length(p);
        float a = exp(-r * r * 3.4);
        if (a < 0.035) discard;
        gl_FragColor = vec4(vColor * a, 1.0);
      }
    `
      : `
      varying vec3 vColor;
      void main() {
        vec2 p = gl_PointCoord * 2.0 - 1.0;
        float r = length(p);
        float a = exp(-r * r * 2.4);
        if (a < 0.03) discard;
        gl_FragColor = vec4(vColor, a * 0.55);
      }
    `,
  });
  return { geometry, material };
}

const FLAME_CARD_VERT = `
  varying vec2 vUv;
  varying float vSeed;
  void main() {
    vUv = uv;
    vSeed = float(gl_InstanceID) * 1.748;
    vec4 world = instanceMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * viewMatrix * world;
  }
`;

const FLAME_CARD_FRAG = `
  uniform float uTime;
  varying vec2 vUv;
  varying float vSeed;

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
    float y = vUv.y;
    float x = vUv.x * 2.0 - 1.0;
    vec2 np = vec2(x * 2.6 + vSeed, y * 3.4 - uTime * 3.6 + vSeed);
    float n = fbm(np);
    float n2 = fbm(np * 2.15 + 8.0);
    float taper = pow(max(0.0, 1.0 - y), 0.52);
    float wobble = (n - 0.5) * 0.22 * (1.0 - y);
    float halfW = taper * (0.38 + 0.32 * n + 0.12 * n2) + wobble;
    float shape = smoothstep(halfW, halfW * 0.28, abs(x));
    float tip = 1.0 - smoothstep(0.55, 1.0, y + n * 0.14);
    float base = smoothstep(0.0, 0.07, y);
    float flame = shape * tip * base;
    if (flame < 0.045) discard;
    float heat = clamp((1.0 - y) * 0.4 + (1.0 - abs(x)) * 0.38 + n * 0.4, 0.0, 1.0);
    vec3 ember = vec3(0.55, 0.02, 0.0);
    vec3 mid = vec3(1.0, 0.28, 0.03);
    vec3 hot = vec3(1.0, 0.82, 0.22);
    vec3 core = vec3(1.0, 0.96, 0.72);
    vec3 col = mix(ember, mid, heat);
    col = mix(col, hot, heat * heat * 0.7);
    col = mix(col, core, pow(heat, 3.2) * 0.45);
    gl_FragColor = vec4(col * (0.55 + flame * 1.15), 1.0);
  }
`;

function makeFlameCardMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    depthTest: true,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    toneMapped: false,
    uniforms: { uTime: { value: 0 } },
    vertexShader: FLAME_CARD_VERT,
    fragmentShader: FLAME_CARD_FRAG,
  });
}

function heapPush(heap: Array<[number, number]>, item: [number, number]) {
  heap.push(item);
  let i = heap.length - 1;
  while (i > 0) {
    const p = (i - 1) >> 1;
    if (heap[p][0] <= heap[i][0]) break;
    const tmp = heap[p];
    heap[p] = heap[i];
    heap[i] = tmp;
    i = p;
  }
}

function heapPop(heap: Array<[number, number]>): [number, number] {
  const top = heap[0];
  const last = heap.pop()!;
  if (heap.length === 0) return top;
  heap[0] = last;
  let i = 0;
  for (;;) {
    const l = i * 2 + 1;
    const r = l + 1;
    let s = i;
    if (l < heap.length && heap[l][0] < heap[s][0]) s = l;
    if (r < heap.length && heap[r][0] < heap[s][0]) s = r;
    if (s === i) break;
    const tmp = heap[i];
    heap[i] = heap[s];
    heap[s] = tmp;
    i = s;
  }
  return top;
}

function computeIgniteTimes(
  samples: Sample[],
  origin: THREE.Vector3,
  footprint: number,
  height: number,
): void {
  const n = samples.length;
  const neighbors: Array<Array<[number, number, number]>> = Array.from(
    { length: n },
    () => [],
  );
  const maxDist = Math.max(0.35, footprint * CONNECT_SCALE);
  const maxDistSq = maxDist * maxDist;

  for (let i = 0; i < n; i++) {
    const a = samples[i].rest;
    const near: Array<[number, number]> = [];
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      const dsq = a.distanceToSquared(samples[j].rest);
      if (dsq <= maxDistSq) {
        neighbors[i].push([j, Math.sqrt(dsq), samples[j].rest.z - a.z]);
      } else {
        near.push([dsq, j]);
      }
    }
    if (neighbors[i].length < 2) {
      near.sort((x, y) => x[0] - y[0]);
      for (let k = 0; k < CONNECT_K && k < near.length; k++) {
        const j = near[k][1];
        const d = Math.sqrt(near[k][0]);
        neighbors[i].push([j, d, samples[j].rest.z - a.z]);
      }
    }
  }

  let originIdx = 0;
  let best = Infinity;
  for (let i = 0; i < n; i++) {
    const d = samples[i].rest.distanceToSquared(origin);
    if (d < best) {
      best = d;
      originIdx = i;
    }
  }

  const speedH = Math.max(0.8, footprint / 6.4);
  const speedV = Math.max(0.35, height / 6.8);
  const dist = new Float64Array(n).fill(Infinity);
  dist[originIdx] = 0;
  const heap: Array<[number, number]> = [[0, originIdx]];
  while (heap.length) {
    const [t, i] = heapPop(heap);
    if (t !== dist[i]) continue;
    for (const [j, edge, dUp] of neighbors[i]) {
      const climb = Math.max(0, dUp);
      const nd = t + edge / speedH + climb / speedV;
      if (nd < dist[j]) {
        dist[j] = nd;
        heapPush(heap, [nd, j]);
      }
    }
  }

  let maxT = 0;
  for (let i = 0; i < n; i++) {
    if (!Number.isFinite(dist[i])) {
      const p = samples[i].rest;
      const horiz = Math.hypot(p.x - origin.x, p.y - origin.y);
      const climb = Math.max(0, p.z - origin.z);
      dist[i] = horiz / speedH + climb / speedV;
    }
    if (dist[i] > maxT) maxT = dist[i];
  }
  const scale = maxT > 0.001 ? TARGET_SPREAD_SEC / maxT : 1;
  for (let i = 0; i < n; i++) samples[i].igniteAt = dist[i] * scale;
}

function deadParticle(): Particle {
  return {
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
    heat: 1,
  };
}

function spawnPool(count: number): Particle[] {
  return Array.from({ length: count }, deadParticle);
}

function writeParticles(
  list: Particle[],
  geometry: THREE.BufferGeometry,
  colorFn: (p: Particle, out: THREE.Color) => void,
  tmp: THREE.Color,
) {
  const pos = geometry.getAttribute("position") as THREE.BufferAttribute;
  const col = geometry.getAttribute("color") as THREE.BufferAttribute;
  const size = geometry.getAttribute("size") as THREE.BufferAttribute;
  for (let i = 0; i < list.length; i++) {
    const p = list[i];
    if (!p.alive) {
      pos.setXYZ(i, 0, 0, -40);
      col.setXYZ(i, 0, 0, 0);
      size.setX(i, 0);
      continue;
    }
    pos.setXYZ(i, p.x, p.y, p.z);
    colorFn(p, tmp);
    col.setXYZ(i, tmp.r, tmp.g, tmp.b);
    const fade = 1 - p.age / p.life;
    size.setX(i, p.size * (0.45 + fade * 0.7));
  }
  pos.needsUpdate = true;
  col.needsUpdate = true;
  size.needsUpdate = true;
}

export function BuildingBurnDown({
  url,
  onBounds,
  onPhase,
  commandRef,
}: BuildingBurnDownProps) {
  const { camera, gl } = useThree();
  const [root, setRoot] = useState<THREE.Group | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wrapRef = useRef<THREE.Group>(null);
  const sceneRef = useRef<THREE.Group | null>(null);
  const piecesRef = useRef<PieceState[]>([]);
  const samplesRef = useRef<Sample[]>([]);
  const preparedRef = useRef(false);
  const tmpWorld = useMemo(() => new THREE.Vector3(), []);
  const tmpColor = useMemo(() => new THREE.Color(), []);
  const tmpQuat = useMemo(() => new THREE.Quaternion(), []);
  const tmpTilt = useMemo(() => new THREE.Quaternion(), []);
  const tmpPos = useMemo(() => new THREE.Vector3(), []);

  const originRef = useRef<THREE.Vector3 | null>(null);
  const clockRef = useRef(0);
  const phaseRef = useRef<BurnPhase>("idle");
  const footprintRef = useRef({ minX: -4, maxX: 4, minY: -4, maxY: 4, floorZ: 0, height: 4 });
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  const flames = useRef(spawnPool(FLAME_COUNT));
  const smoke = useRef(spawnPool(SMOKE_COUNT));
  const embers = useRef(spawnPool(EMBER_COUNT));
  const flamePts = useMemo(() => makePoints(FLAME_COUNT, true), []);
  const smokePts = useMemo(() => makePoints(SMOKE_COUNT, false), []);
  const emberPts = useMemo(() => makePoints(EMBER_COUNT, true), []);
  const flameCardGeo = useMemo(() => {
    const geo = new THREE.PlaneGeometry(1, 1);
    geo.translate(0, 0.5, 0);
    return geo;
  }, []);
  const flameCardMat = useMemo(() => makeFlameCardMaterial(), []);
  const flameMeshRef = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const tmpRight = useMemo(() => new THREE.Vector3(), []);
  const tmpUp = useMemo(() => new THREE.Vector3(), []);
  const tmpLook = useMemo(() => new THREE.Vector3(), []);
  const lightsRef = useRef<(THREE.PointLight | null)[]>([]);

  const setPhase = (phase: BurnPhase) => {
    if (phaseRef.current === phase) return;
    phaseRef.current = phase;
    onPhase?.(phase);
  };

  const bakeAfterMount = (gltfScene: THREE.Group) => {
    if (preparedRef.current) return;
    const wrap = wrapRef.current;
    if (!wrap || gltfScene.parent !== wrap) return;
    wrap.updateWorldMatrix(true, true);
    const wrapUp = new THREE.Vector3(0, 1, 0).transformDirection(wrap.matrixWorld);
    if (wrapUp.z < 0.85) return;
    preparedRef.current = true;

    const meshes = collectMeshes(gltfScene);
    const groups = new Map<THREE.Object3D, THREE.Mesh[]>();
    for (const mesh of meshes) {
      const piece = pieceRoot(mesh, gltfScene);
      const list = groups.get(piece) ?? [];
      list.push(mesh);
      groups.set(piece, list);
    }

    const pieces: PieceState[] = [];
    const worldBox = new THREE.Box3();
    const meshWorldBox = new THREE.Box3();
    const localBox = new THREE.Box3();
    const invPiece = new THREE.Matrix4();
    const meshToPiece = new THREE.Matrix4();
    const yupCenter = new THREE.Vector3();
    let yupCount = 0;

    for (const [object, pieceMeshes] of groups) {
      const kind = kindOf(object.name);
      object.updateWorldMatrix(true, true);
      invPiece.copy(object.matrixWorld).invert();
      meshWorldBox.makeEmpty();
      localBox.makeEmpty();
      const mats: PieceState["mats"] = [];
      for (const mesh of pieceMeshes) {
        mesh.updateWorldMatrix(true, false);
        meshWorldBox.expandByObject(mesh);
        mesh.geometry.computeBoundingBox();
        if (mesh.geometry.boundingBox) {
          const b = mesh.geometry.boundingBox.clone();
          meshToPiece.multiplyMatrices(invPiece, mesh.matrixWorld);
          b.applyMatrix4(meshToPiece);
          localBox.union(b);
        }
        for (const mat of cloneMeshMaterials(mesh)) {
          const std = mat as THREE.MeshStandardMaterial;
          if (!std.color) continue;
          if (std.emissive === undefined) {
            std.emissive = new THREE.Color(0x000000);
          }
          mats.push({
            mat: std,
            color: std.color.clone(),
            emissive: std.emissive.clone(),
            emissiveIntensity: std.emissiveIntensity ?? 1,
            roughness: std.roughness ?? 0.7,
          });
        }
      }
      if (meshWorldBox.isEmpty() || localBox.isEmpty()) continue;
      worldBox.union(meshWorldBox);
      const localCenter = localBox.getCenter(new THREE.Vector3());
      const localSize = localBox.getSize(new THREE.Vector3());
      const base = localCenter.clone();
      base.y = localBox.min.y;
      yupCenter.add(localCenter);
      yupCount++;
      const seed = hashName(object.name);
      pieces.push({
        object,
        kind,
        restPos: object.position.clone(),
        restQuat: object.quaternion.clone(),
        restScale: object.scale.clone(),
        base,
        center: localCenter,
        height: localSize.y,
        localMin: localBox.min.clone(),
        localMax: localBox.max.clone(),
        leanAxis: new THREE.Vector3(),
        tiltAxis: new THREE.Vector3(),
        leanMax:
          kind === "roof"
            ? 0.28 + seed * 0.35
            : kind === "floor"
              ? 0.06
              : 1.05 + seed * 0.25,
        dropMax:
          kind === "roof"
            ? Math.max(0.8, localCenter.y - 0.12)
            : kind === "floor"
              ? 0.12
              : Math.max(0.35, localSize.y * 0.72),
        collapseDelay:
          kind === "floor" ? 2.2 : kind === "roof" ? 1.6 : kind === "trim" ? 0.9 : 1.15,
        collapseDur: kind === "roof" ? 1.15 : kind === "floor" ? 2.4 : 1.25,
        igniteAt: Infinity,
        mats,
      });
    }

    if (yupCount > 0) yupCenter.multiplyScalar(1 / yupCount);
    for (const piece of pieces) {
      const fromCenter = new THREE.Vector3(
        piece.center.x - yupCenter.x,
        0,
        piece.center.z - yupCenter.z,
      );
      if (fromCenter.lengthSq() < 1e-5) fromCenter.set(1, 0, 0);
      fromCenter.normalize();
      piece.leanAxis.set(0, 1, 0).cross(fromCenter).normalize();
      if (piece.leanAxis.lengthSq() < 1e-5) piece.leanAxis.set(1, 0, 0);
      piece.tiltAxis.set(-fromCenter.z, 0, fromCenter.x).normalize();
      if (piece.tiltAxis.lengthSq() < 1e-5) piece.tiltAxis.set(1, 0, 0);
    }

    const size = worldBox.getSize(new THREE.Vector3());
    let floorTop = Number.POSITIVE_INFINITY;
    for (const piece of pieces) {
      if (piece.kind !== "floor") continue;
      const fb = new THREE.Box3().setFromObject(piece.object);
      if (!fb.isEmpty()) floorTop = Math.min(floorTop, fb.max.z);
    }
    if (!Number.isFinite(floorTop)) floorTop = 0.05;
    footprintRef.current = {
      minX: worldBox.min.x,
      maxX: worldBox.max.x,
      minY: worldBox.min.y,
      maxY: worldBox.max.y,
      floorZ: floorTop,
      height: Math.max(size.z, 1),
    };

    const areas: Array<{
      mesh: THREE.Mesh;
      piece: number;
      areas: Float32Array;
      total: number;
      weight: number;
    }> = [];
    let weightSum = 0;
    for (const mesh of meshes) {
      const pos = mesh.geometry.getAttribute("position") as THREE.BufferAttribute | undefined;
      if (!pos) continue;
      const pieceObj = pieceRoot(mesh, gltfScene);
      const piece = pieces.findIndex((p) => p.object === pieceObj);
      if (piece < 0) continue;
      const { areas: tri, total } = triangleAreas(pos, mesh.geometry.index);
      if (total <= 1e-8) continue;
      const kind = pieces[piece].kind;
      const w = total * (kind === "floor" ? 3.4 : kind === "wall" ? 1.05 : 0.85);
      areas.push({ mesh, piece, areas: tri, total, weight: w });
      weightSum += w;
    }

    const samples: Sample[] = [];
    const pa = new THREE.Vector3();
    const pb = new THREE.Vector3();
    const pc = new THREE.Vector3();
    const nrm = new THREE.Vector3();
    for (const entry of areas) {
      const want = Math.max(8, Math.round((entry.weight / weightSum) * SAMPLE_COUNT));
      const pos = entry.mesh.geometry.getAttribute("position") as THREE.BufferAttribute;
      const index = entry.mesh.geometry.index;
      entry.mesh.updateWorldMatrix(true, false);
      for (let s = 0; s < want && samples.length < SAMPLE_COUNT + 40; s++) {
        const t = pickTriangle(entry.areas, entry.total, Math.random());
        const i0 = index ? index.getX(t * 3) : t * 3;
        const i1 = index ? index.getX(t * 3 + 1) : t * 3 + 1;
        const i2 = index ? index.getX(t * 3 + 2) : t * 3 + 2;
        pa.fromBufferAttribute(pos, i0);
        pb.fromBufferAttribute(pos, i1);
        pc.fromBufferAttribute(pos, i2);
        let u = Math.random();
        let v = Math.random();
        if (u + v > 1) {
          u = 1 - u;
          v = 1 - v;
        }
        const w = 1 - u - v;
        const local = pa
          .clone()
          .multiplyScalar(w)
          .addScaledVector(pb, u)
          .addScaledVector(pc, v);
        nrm.subVectors(pb, pa).cross(pc.clone().sub(pa)).normalize();
        if (nrm.lengthSq() < 1e-6) nrm.set(0, 0, 1);
        const rest = local.clone().applyMatrix4(entry.mesh.matrixWorld);
        nrm.transformDirection(entry.mesh.matrixWorld);
        const kind = pieces[entry.piece]?.kind;
        if (kind === "floor") {
          if (nrm.z < -0.25) continue;
          rest.z = footprintRef.current.floorZ;
          nrm.set(0, 0, 1);
        } else {
          if (rest.z < footprintRef.current.floorZ - 0.03) continue;
          if (nrm.z < -0.7 && rest.z < footprintRef.current.floorZ + 0.2) continue;
        }
        samples.push({
          piece: entry.piece,
          local,
          rest,
          nx: nrm.x,
          ny: nrm.y,
          nz: nrm.z,
          igniteAt: Infinity,
        });
      }
    }

    const floorZ = footprintRef.current.floorZ;
    for (let pi = 0; pi < pieces.length; pi++) {
      const piece = pieces[pi];
      if (piece.kind !== "floor") continue;
      const cols = 16;
      const rows = 16;
      piece.object.updateWorldMatrix(true, false);
      for (let i = 0; i < cols; i++) {
        for (let j = 0; j < rows; j++) {
          const lx = THREE.MathUtils.lerp(
            piece.localMin.x,
            piece.localMax.x,
            (i + 0.5) / cols,
          );
          const lz = THREE.MathUtils.lerp(
            piece.localMin.z,
            piece.localMax.z,
            (j + 0.5) / rows,
          );
          const local = new THREE.Vector3(lx, piece.localMax.y, lz);
          const rest = local.clone().applyMatrix4(piece.object.matrixWorld);
          rest.z = floorZ;
          samples.push({
            piece: pi,
            local,
            rest,
            nx: 0,
            ny: 0,
            nz: 1,
            igniteAt: Infinity,
          });
        }
      }
    }

    piecesRef.current = pieces;
    samplesRef.current = samples;
    sceneRef.current = gltfScene;
    onBounds?.(worldBox.clone());
  };

  useLayoutEffect(() => {
    let cancelled = false;
    setRoot(null);
    setError(null);
    sceneRef.current = null;
    piecesRef.current = [];
    samplesRef.current = [];
    preparedRef.current = false;
    originRef.current = null;
    clockRef.current = 0;
    phaseRef.current = "idle";
    onPhase?.("idle");

    loader.load(
      url,
      (gltf) => {
        if (cancelled) return;
        setRoot(gltf.scene);
      },
      undefined,
      (err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      },
    );

    return () => {
      cancelled = true;
      for (const piece of piecesRef.current) {
        for (const entry of piece.mats) entry.mat.dispose();
      }
      piecesRef.current = [];
    };
  }, [url, onPhase]);

  useLayoutEffect(() => {
    if (!root) return;
    let frames = 0;
    let id = 0;
    const tryBake = () => {
      bakeAfterMount(root);
      if (!preparedRef.current && frames++ < 8) {
        id = requestAnimationFrame(tryBake);
      }
    };
    tryBake();
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [root]);

  useLayoutEffect(() => {
    return () => {
      flamePts.geometry.dispose();
      flamePts.material.dispose();
      smokePts.geometry.dispose();
      smokePts.material.dispose();
      emberPts.geometry.dispose();
      emberPts.material.dispose();
      flameCardGeo.dispose();
      flameCardMat.dispose();
    };
  }, [flamePts, smokePts, emberPts, flameCardGeo, flameCardMat]);

  useLayoutEffect(() => {
    const mesh = flameMeshRef.current;
    if (!mesh) return;
    dummy.matrix.makeScale(0, 0, 0);
    for (let i = 0; i < FLAME_CARD_COUNT; i++) mesh.setMatrixAt(i, dummy.matrix);
    mesh.instanceMatrix.needsUpdate = true;
  }, [root]);

  const reset = () => {
    originRef.current = null;
    clockRef.current = 0;
    setPhase("idle");
    for (const p of flames.current) p.alive = false;
    for (const p of smoke.current) p.alive = false;
    for (const p of embers.current) p.alive = false;
    for (const piece of piecesRef.current) {
      piece.object.position.copy(piece.restPos);
      piece.object.quaternion.copy(piece.restQuat);
      piece.object.scale.copy(piece.restScale);
      piece.igniteAt = Infinity;
      for (const entry of piece.mats) {
        entry.mat.color.copy(entry.color);
        if (entry.mat.emissive) entry.mat.emissive.copy(entry.emissive);
        entry.mat.emissiveIntensity = entry.emissiveIntensity;
        if (entry.mat.roughness !== undefined) entry.mat.roughness = entry.roughness;
      }
    }
    for (const sample of samplesRef.current) sample.igniteAt = Infinity;
    const mesh = flameMeshRef.current;
    if (mesh) {
      dummy.matrix.makeScale(0, 0, 0);
      for (let i = 0; i < FLAME_CARD_COUNT; i++) mesh.setMatrixAt(i, dummy.matrix);
      mesh.instanceMatrix.needsUpdate = true;
    }
  };

  const igniteAt = (worldPoint: THREE.Vector3) => {
    if (phaseRef.current !== "idle") return;
    const fp = footprintRef.current;
    const origin = worldPoint.clone();
    origin.z = fp.floorZ;
    origin.x = THREE.MathUtils.clamp(origin.x, fp.minX + 0.15, fp.maxX - 0.15);
    origin.y = THREE.MathUtils.clamp(origin.y, fp.minY + 0.15, fp.maxY - 0.15);
    const samples = samplesRef.current;
    if (samples.length === 0) return;
    computeIgniteTimes(samples, origin, Math.max(fp.maxX - fp.minX, fp.maxY - fp.minY), fp.height);
    for (let i = 0; i < piecesRef.current.length; i++) {
      let minT = Infinity;
      for (const sample of samples) {
        if (sample.piece === i && sample.igniteAt < minT) minT = sample.igniteAt;
      }
      piecesRef.current[i].igniteAt = minT;
    }
    originRef.current = origin;
    clockRef.current = 0;
    setPhase("ignited");
  };

  const igniteDefault = () => {
    const fp = footprintRef.current;
    igniteAt(
      new THREE.Vector3(
        (fp.minX + fp.maxX) * 0.5,
        (fp.minY + fp.maxY) * 0.5,
        fp.floorZ,
      ),
    );
  };

  useImperativeHandle(commandRef, () => ({ igniteDefault, reset }), [root]);

  const tryClick = (clientX: number, clientY: number) => {
    if (phaseRef.current !== "idle" || !root) return;
    const rect = gl.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((clientX - rect.left) / rect.width) * 2 - 1,
      -(((clientY - rect.top) / rect.height) * 2 - 1),
    );
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObject(root, true);
    const fp = footprintRef.current;
    if (hits.length > 0) {
      igniteAt(hits[0].point);
      return;
    }
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, 1), -fp.floorZ);
    const hit = new THREE.Vector3();
    if (raycaster.ray.intersectPlane(plane, hit)) {
      if (
        hit.x >= fp.minX - 0.4 &&
        hit.x <= fp.maxX + 0.4 &&
        hit.y >= fp.minY - 0.4 &&
        hit.y <= fp.maxY + 0.4
      ) {
        igniteAt(hit);
      }
    }
  };

  useLayoutEffect(() => {
    const el = gl.domElement;
    const onDown = (e: PointerEvent) => {
      dragRef.current = { x: e.clientX, y: e.clientY };
    };
    const onUp = (e: PointerEvent) => {
      const start = dragRef.current;
      dragRef.current = null;
      if (!start) return;
      const dx = e.clientX - start.x;
      const dy = e.clientY - start.y;
      if (dx * dx + dy * dy > 16) return;
      tryClick(e.clientX, e.clientY);
    };
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointerup", onUp);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointerup", onUp);
    };
  });

  const spawnFromList = (
    list: Particle[],
    want: number,
    setup: (p: Particle) => void,
  ) => {
    let left = want;
    for (const p of list) {
      if (left <= 0) return;
      if (p.alive) continue;
      p.alive = true;
      p.age = 0;
      setup(p);
      left--;
    }
  };

  useFrame((_, dt) => {
    const delta = Math.min(dt, 0.05);
    const samples = samplesRef.current;
    const pieces = piecesRef.current;
    const origin = originRef.current;
    const burning = origin !== null;
    if (burning) clockRef.current += delta;
    const t = clockRef.current;

    let ignited = 0;
    const live: Sample[] = [];
    const liveWorld: THREE.Vector3[] = [];
    if (burning) {
      for (const sample of samples) {
        if (t < sample.igniteAt) continue;
        ignited++;
        const piece = pieces[sample.piece];
        if (!piece) continue;
        tmpWorld.copy(sample.local);
        piece.object.localToWorld(tmpWorld);
        const floorZ = footprintRef.current.floorZ;
        if (piece.kind === "floor") {
          tmpWorld.z = floorZ;
        } else if (tmpWorld.z < floorZ - 0.03) {
          continue;
        } else {
          tmpWorld.z = Math.max(tmpWorld.z, floorZ);
        }
        live.push(sample);
        liveWorld.push(tmpWorld.clone());
      }
    }
    const floorLive: number[] = [];
    const otherLive: number[] = [];
    for (let i = 0; i < live.length; i++) {
      if (pieces[live[i].piece]?.kind === "floor") floorLive.push(i);
      else otherLive.push(i);
    }

    const frac = samples.length ? ignited / samples.length : 0;
    let collapsing = 0;
    for (const piece of pieces) {
      const age = t - piece.igniteAt;
      const burn = THREE.MathUtils.clamp(age / (piece.kind === "floor" ? 1.05 : 1.8), 0, 1);
      const glow =
        age < 0
          ? 0
          : THREE.MathUtils.clamp(1 - Math.abs(age - 1.1) / 1.6, 0, 1) *
            (piece.kind === "floor" ? 0.55 : 1);
      for (const entry of piece.mats) {
        entry.mat.color.copy(entry.color).lerp(CHAR, easeInOut(Math.min(1, burn * 1.35)));
        if (entry.mat.emissive) {
          entry.mat.emissive.copy(entry.emissive).lerp(GLOW, glow * 0.22);
        }
        entry.mat.emissiveIntensity = entry.emissiveIntensity + glow * 0.35;
        if (entry.mat.roughness !== undefined) {
          entry.mat.roughness = THREE.MathUtils.lerp(entry.roughness, 0.94, burn);
        }
      }

      const kindStart =
        piece.kind === "roof" ? 5.6 :
        piece.kind === "trim" ? 4.2 :
        piece.kind === "wall" ? 4.6 :
        piece.kind === "floor" ? 6.4 :
        16;
      const fromIgnite =
        age < piece.collapseDelay
          ? 0
          : easeInCubic((age - piece.collapseDelay) / piece.collapseDur);
      const fromClock =
        !burning || t < kindStart
          ? 0
          : easeInCubic((t - kindStart) / piece.collapseDur);
      const collapseT = Math.max(fromIgnite, fromClock);
      if (collapseT > 0.02) collapsing++;
      if (collapseT <= 0) {
        piece.object.position.copy(piece.restPos);
        piece.object.quaternion.copy(piece.restQuat);
        piece.object.scale.copy(piece.restScale);
        continue;
      }

      const angle = piece.leanMax * collapseT;
      tmpQuat.setFromAxisAngle(piece.leanAxis, -angle);
      if (piece.kind === "roof") {
        tmpTilt.setFromAxisAngle(
          piece.tiltAxis,
          (hashName(piece.object.name) - 0.5) * 0.9 * collapseT,
        );
        tmpQuat.multiply(tmpTilt);
      }
      tmpPos.copy(piece.base).negate().applyQuaternion(tmpQuat).add(piece.base);
      tmpPos.y -= piece.dropMax * collapseT;
      piece.object.position.copy(tmpPos);
      piece.object.quaternion.copy(tmpQuat);
      if (piece.kind === "roof") {
        const s = 1 - collapseT * 0.18;
        piece.object.scale.set(
          piece.restScale.x * s,
          piece.restScale.y * (1 - collapseT * 0.32),
          piece.restScale.z * s,
        );
      } else if (piece.kind === "floor") {
        piece.object.scale.set(
          piece.restScale.x * (1 - collapseT * 0.06),
          piece.restScale.y * (1 - collapseT * 0.7),
          piece.restScale.z * (1 - collapseT * 0.06),
        );
      } else {
        piece.object.scale.copy(piece.restScale);
      }
    }

    if (burning) {
      if (frac > 0.92 && collapsing > 2) setPhase("collapsing");
      else if (frac > 0.78) setPhase("engulfed");
      else if (frac > 0.08) setPhase("spreading");
      else setPhase("ignited");
      if (frac > 0.95 && collapsing >= Math.max(2, pieces.length - 1) && t > TARGET_SPREAD_SEC + 5.2) {
        setPhase("rubble");
      }
    }

    const intensity = burning ? THREE.MathUtils.clamp(0.15 + frac * 1.4 - (phaseRef.current === "rubble" ? 0.7 : 0), 0, 1.6) : 0;
    const floorZ = footprintRef.current.floorZ;
    if (burning && live.length > 0) {
      const flameWant = Math.ceil((phaseRef.current === "rubble" ? 10 : 28) * intensity * delta * 60);
      spawnFromList(flames.current, flameWant, (p) => {
        const i = (Math.random() * live.length) | 0;
        const s = live[i];
        const w = liveWorld[i];
        const upBias = 0.85 + Math.random() * 1.1;
        p.x = w.x + (Math.random() - 0.5) * 0.22;
        p.y = w.y + (Math.random() - 0.5) * 0.22;
        p.z = Math.max(floorZ, w.z + 0.08 + Math.random() * 0.18);
        p.vx = s.nx * 0.18 + (Math.random() - 0.5) * 0.22;
        p.vy = s.ny * 0.18 + (Math.random() - 0.5) * 0.22;
        p.vz = Math.abs(s.nz) * 0.2 + upBias + Math.random() * 0.7;
        p.life = 0.35 + Math.random() * 0.5;
        p.size = 0.55 + Math.random() * 0.85;
        p.heat = 0.7 + Math.random() * 0.3;
      });
      if (floorLive.length > 0) {
        spawnFromList(flames.current, Math.ceil(20 * intensity * delta * 60), (p) => {
          const i = floorLive[(Math.random() * floorLive.length) | 0];
          const w = liveWorld[i];
          p.x = w.x + (Math.random() - 0.5) * 0.28;
          p.y = w.y + (Math.random() - 0.5) * 0.28;
          p.z = Math.max(floorZ, w.z + 0.05);
          p.vx = (Math.random() - 0.5) * 0.2;
          p.vy = (Math.random() - 0.5) * 0.2;
          p.vz = 1.0 + Math.random() * 0.9;
          p.life = 0.4 + Math.random() * 0.45;
          p.size = 0.75 + Math.random() * 0.85;
          p.heat = 0.85 + Math.random() * 0.15;
        });
      }
      if (origin) {
        spawnFromList(flames.current, 8, (p) => {
          const a = Math.random() * Math.PI * 2;
          const r = Math.random() * 0.35;
          p.x = origin.x + Math.cos(a) * r;
          p.y = origin.y + Math.sin(a) * r;
          p.z = Math.max(floorZ, origin.z + 0.04);
          p.vx = (Math.random() - 0.5) * 0.16;
          p.vy = (Math.random() - 0.5) * 0.16;
          p.vz = 1.2 + Math.random() * 1.0;
          p.life = 0.4 + Math.random() * 0.4;
          p.size = 0.8 + Math.random() * 0.7;
          p.heat = 1;
        });
      }
      const smokeWant = Math.ceil((phaseRef.current === "rubble" ? 14 : 8) * (0.35 + frac) * delta * 60);
      spawnFromList(smoke.current, smokeWant, (p) => {
        const i = (Math.random() * live.length) | 0;
        const w = liveWorld[i];
        p.x = w.x + (Math.random() - 0.5) * 0.3;
        p.y = w.y + (Math.random() - 0.5) * 0.3;
        p.z = Math.max(floorZ, w.z + 0.2);
        p.vx = (Math.random() - 0.5) * 0.12;
        p.vy = (Math.random() - 0.5) * 0.12;
        p.vz = 0.55 + Math.random() * 0.55;
        p.life = 1.4 + Math.random() * 1.8;
        p.size = 0.55 + Math.random() * 0.85;
        p.heat = 0.2 + Math.random() * 0.25;
      });
      spawnFromList(embers.current, Math.ceil(10 * intensity * delta * 60), (p) => {
        const i = (Math.random() * live.length) | 0;
        const w = liveWorld[i];
        p.x = w.x;
        p.y = w.y;
        p.z = Math.max(floorZ, w.z + 0.1);
        p.vx = (Math.random() - 0.5) * 0.7;
        p.vy = (Math.random() - 0.5) * 0.7;
        p.vz = 1.2 + Math.random() * 1.6;
        p.life = 0.6 + Math.random() * 0.8;
        p.size = 0.05 + Math.random() * 0.06;
        p.heat = 1;
      });
    }

    const step = (list: Particle[], drag: number, gravity: number) => {
      for (const p of list) {
        if (!p.alive) continue;
        p.age += delta;
        if (p.age >= p.life) {
          p.alive = false;
          continue;
        }
        p.x += p.vx * delta;
        p.y += p.vy * delta;
        p.z = Math.max(floorZ, p.z + p.vz * delta);
        p.vx *= drag;
        p.vy *= drag;
        p.vz = p.vz * drag + gravity * delta;
      }
    };
    step(flames.current, 0.92, 0.15);
    step(smoke.current, 0.985, 0.05);
    step(embers.current, 0.96, -0.35);

    writeParticles(flames.current, flamePts.geometry, (p, out) => {
      const u = 1 - p.age / p.life;
      out.setRGB(
        1.0,
        0.22 + p.heat * 0.45 * u,
        0.03 + 0.08 * u,
      );
    }, tmpColor);
    writeParticles(smoke.current, smokePts.geometry, (p, out) => {
      const u = 1 - p.age / p.life;
      const g = 0.06 + 0.07 * u;
      out.setRGB(g, g * 0.95, g * 0.9);
    }, tmpColor);
    writeParticles(embers.current, emberPts.geometry, (_p, out) => {
      out.setRGB(1.0, 0.55, 0.12);
    }, tmpColor);

    const lights = lightsRef.current;
    if (liveWorld.length > 0) {
      for (let i = 0; i < lights.length; i++) {
        const light = lights[i];
        if (!light) continue;
        const pick = liveWorld[(i * 17 + (ignited % liveWorld.length)) % liveWorld.length];
        light.position.lerp(pick, 0.12);
        light.position.z += 0.35;
        light.intensity = 2.2 * intensity;
        light.distance = 10;
      }
    } else {
      for (const light of lights) {
        if (light) light.intensity = 0;
      }
    }

    flameCardMat.uniforms.uTime.value = t;
    const cards = flameMeshRef.current;
    if (cards) {
      const originSlots = burning && origin ? 14 : 0;
      const sampleSlots = FLAME_CARD_COUNT - originSlots;
      const floorWant =
        burning && floorLive.length > 0
          ? Math.min(floorLive.length, Math.max(56, Math.floor(sampleSlots * 0.48)))
          : 0;
      const otherWant =
        burning && otherLive.length > 0
          ? Math.min(otherLive.length, sampleSlots - floorWant)
          : 0;
      for (let c = 0; c < FLAME_CARD_COUNT; c++) {
        let px = 0;
        let py = 0;
        let pz = 0;
        let width = 0;
        let height = 0;
        let kind: PieceKind = "other";
        let i = -1;
        if (c < floorWant) {
          i = floorLive[Math.floor((c + 0.5) * floorLive.length / floorWant)];
          kind = "floor";
        } else if (c < floorWant + otherWant) {
          const k = c - floorWant;
          i = otherLive[Math.floor((k + 0.5) * otherLive.length / otherWant)];
          kind = pieces[live[i].piece]?.kind ?? "other";
        }
        if (i >= 0) {
          const s = live[i];
          const w = liveWorld[i];
          const flicker = 0.8 + 0.2 * Math.sin(t * 14.0 + c * 2.3);
          const seed = (c % 9) * 0.07;
          width = (kind === "floor" ? 1.05 : kind === "roof" ? 0.78 : 0.62) * flicker;
          height = (kind === "floor" ? 1.45 : kind === "roof" ? 1.35 : 1.5) * flicker + seed;
          px = w.x + s.nx * 0.05;
          py = w.y + s.ny * 0.05;
          pz = Math.max(floorZ, w.z + 0.02);
        } else if (origin && c >= sampleSlots) {
          const k = c - sampleSlots;
          const ang = (k / Math.max(1, originSlots)) * Math.PI * 2;
          const r = 0.1 + (k % 4) * 0.09;
          const flicker = 0.85 + 0.15 * Math.sin(t * 18.0 + k * 3.1);
          px = origin.x + Math.cos(ang) * r;
          py = origin.y + Math.sin(ang) * r;
          pz = Math.max(floorZ, origin.z);
          width = (1.05 + (k % 3) * 0.12) * flicker;
          height = (2.15 + (k % 5) * 0.18) * flicker;
        }
        if (width <= 0) {
          dummy.matrix.makeScale(0, 0, 0);
        } else {
          tmpLook.set(camera.position.x - px, camera.position.y - py, 0);
          if (tmpLook.lengthSq() < 1e-6) tmpLook.set(0, 1, 0);
          tmpLook.normalize();
          tmpRight.set(-tmpLook.y * width, tmpLook.x * width, 0);
          tmpUp.set(0, 0, height);
          dummy.matrix.makeBasis(tmpRight, tmpUp, tmpLook);
          dummy.matrix.setPosition(px, py, pz);
        }
        cards.setMatrixAt(c, dummy.matrix);
      }
      cards.instanceMatrix.needsUpdate = true;
    }
  });

  if (error) return null;
  if (!root) return null;

  const fp = footprintRef.current;
  const planeW = fp.maxX - fp.minX + 0.8;
  const planeH = fp.maxY - fp.minY + 0.8;

  return (
    <group>
      <group ref={wrapRef} rotation={[Math.PI / 2, 0, 0]}>
        <primitive object={root} />
      </group>
      <mesh
        position={[(fp.minX + fp.maxX) * 0.5, (fp.minY + fp.maxY) * 0.5, fp.floorZ]}
        visible={false}
      >
        <planeGeometry args={[planeW, planeH]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>
      <instancedMesh
        ref={flameMeshRef}
        args={[flameCardGeo, flameCardMat, FLAME_CARD_COUNT]}
        frustumCulled={false}
      />
      <points geometry={flamePts.geometry} material={flamePts.material} />
      <points geometry={smokePts.geometry} material={smokePts.material} />
      <points geometry={emberPts.geometry} material={emberPts.material} />
      <pointLight
        ref={(el) => {
          lightsRef.current[0] = el;
        }}
        color="#ff3a0a"
        intensity={0}
        distance={10}
      />
      <pointLight
        ref={(el) => {
          lightsRef.current[1] = el;
        }}
        color="#ff7a1a"
        intensity={0}
        distance={8}
      />
      <pointLight
        ref={(el) => {
          lightsRef.current[2] = el;
        }}
        color="#ff2a00"
        intensity={0}
        distance={9}
      />
    </group>
  );
}
