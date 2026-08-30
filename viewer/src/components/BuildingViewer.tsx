import { Canvas, useThree, useFrame } from "@react-three/fiber";
import { TrackballControls, Grid, Text, Environment } from "@react-three/drei";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import {
  type BuildingDefinition,
  type BuildingStage,
} from "../types/buildings";
import { DragonFireBreath, dragonHasFireBreath, hideDragonFireMeshes } from "./DragonFireBreath";
import { ChickenEggBurst, chickenHasEggBurst } from "./ChickenEggBurst";
import { RoosterButtFire, roosterHasButtFire } from "./RoosterButtFire";
import {
  BuildingBurnDown,
  type BurnDownCommands,
  type BurnPhase,
} from "./BuildingBurnDown";
import { BirdRoast, type RoastCommands, type RoastPhase } from "./BirdRoast";

// Optimized building stages (gltfpack -cc) require EXT_meshopt_compression.
const buildingGltfLoader = new GLTFLoader();
buildingGltfLoader.setMeshoptDecoder(MeshoptDecoder);

type AssemblyStageKey = string;

interface AssemblyPieceDef {
  id: string;
  category: string;
  staggerIndex: number;
  spawnOffset: [number, number, number];
  spawnYawDeg: number;
  durationSec: number;
}

interface AssemblyManifest {
  pieces: AssemblyPieceDef[];
  stages: Record<string, string[]>;
  tween: {
    staggerSec: number;
    ease: string;
    startScale: number;
  };
}

interface PieceAnim {
  object: THREE.Object3D;
  restPos: THREE.Vector3;
  restQuat: THREE.Quaternion;
  restScale: THREE.Vector3;
  spawnPos: THREE.Vector3;
  spawnQuat: THREE.Quaternion;
  startScale: number;
  duration: number;
  delay: number;
  /** Animation clock start (performance.now), or null if settled/hidden. */
  startedAt: number | null;
  visible: boolean;
  settled: boolean;
}

function easeOutCubic(t: number): number {
  const u = 1 - Math.min(1, Math.max(0, t));
  return 1 - u * u * u;
}

// Six pre-set orbit views mirroring the character viewer so the two
// viewports feel consistent when the user flips between them.
const AXIS_VIEWS = [
  { key: "+X", label: "Right",  colorClass: "axis-x" },
  { key: "-X", label: "Left",   colorClass: "axis-x" },
  { key: "+Y", label: "Front",  colorClass: "axis-y" },
  { key: "-Y", label: "Back",   colorClass: "axis-y" },
  { key: "+Z", label: "Top",    colorClass: "axis-z" },
  { key: "-Z", label: "Bottom", colorClass: "axis-z" },
] as const;

const VIEW_OFFSETS: Record<string, [number, number, number]> = {
  "+X": [1, 0, 0],
  "-X": [-1, 0, 0],
  "+Y": [0, 1, 0],
  "-Y": [0, -1, 0],
  "+Z": [0, -0.001, 1],
  "-Z": [0, -0.001, -1],
};

const BUILDING_TARGET: [number, number, number] = [0, 0, 0.75];
const BUILDING_CAMERA: [number, number, number] = [4.5, 4.5, 3.0];

/**
 * Creatures are glTF Y-up. Grindscape cows / sheep / birds / dragons face
 * +Z at rest. The viewer grid is Z-up, so we rotate +90° about X: +Z
 * becomes −Y. Camera sits on −Y (in front of the face), looking +Y.
 */
const CREATURE_HEIGHT = 2.8;
const CREATURE_TARGET: [number, number, number] = [0, 0, CREATURE_HEIGHT];
const CREATURE_CAMERA: [number, number, number] = [0, -12, CREATURE_HEIGHT];
const CREATURE_MODEL_ROTATION: [number, number, number] = [Math.PI / 2, 0, 0];
/** After the X wrap, +Z-facing GLBs look toward −Y. */
const CREATURE_FACE_SIGN = -1;

function CameraSnap({
  position,
  target,
}: {
  position: [number, number, number];
  target: [number, number, number];
}) {
  const { camera, controls } = useThree();
  useLayoutEffect(() => {
    camera.up.set(0, 0, 1);
    camera.position.set(...position);
    const c = controls as any;
    if (c?.target) {
      c.target.set(...target);
      resetTrackballSpin(c);
      c.update?.();
    }
  }, [camera, controls, position, target]);
  return null;
}

function frameCreatureBox(
  box: THREE.Box3,
  faceSign: number,
): {
  camera: [number, number, number];
  target: [number, number, number];
} {
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const dist = Math.max(size.x, size.z, 0.25) * 1.55;
  const height = Math.max(center.z, size.z * 0.4);
  return {
    camera: [center.x, center.y + faceSign * dist, height],
    target: [center.x, center.y, height],
  };
}

function frameBuildingBox(box: THREE.Box3): {
  camera: [number, number, number];
  target: [number, number, number];
} {
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  const dist = Math.max(size.x, size.y, size.z, 1) * 1.15;
  const targetZ = center.z * 0.45;
  return {
    camera: [center.x + dist * 0.62, center.y + dist * 0.72, targetZ + size.z * 0.42],
    target: [center.x, center.y, targetZ],
  };
}

const BURN_PHASE_LABEL: Record<BurnPhase, string> = {
  idle: "Click the floor to start a fire",
  ignited: "Fire started on the floor",
  spreading: "Fire spreading through the bank",
  engulfed: "Building fully engulfed",
  collapsing: "Structure collapsing",
  rubble: "Burned down",
};

const ROAST_PHASE_LABEL: Record<RoastPhase, string> = {
  idle: "Play Roast — bird catches fire and cooks",
  roasting: "On fire — roasting",
  cooked: "Cooked chicken",
};

function resetTrackballSpin(controls: any) {
  if (!controls) return;
  if (typeof controls._lastAngle === "number") controls._lastAngle = 0;
  if (controls._moveCurr && controls._movePrev) {
    controls._movePrev.copy(controls._moveCurr);
  }
}

function CameraAnimator({
  pendingViewRef,
  controlsRef,
}: {
  pendingViewRef: React.MutableRefObject<[number, number, number] | null>;
  controlsRef: React.MutableRefObject<any>;
}) {
  const { camera } = useThree();
  const targetPos = useRef<THREE.Vector3 | null>(null);

  useFrame(() => {
    if (pendingViewRef.current) {
      targetPos.current = new THREE.Vector3(...pendingViewRef.current);
      pendingViewRef.current = null;
    }
    const target = targetPos.current;
    const controls = controlsRef.current;
    if (!target || !controls) return;
    resetTrackballSpin(controls);
    camera.position.lerp(target, 0.15);
    camera.up.set(0, 0, 1);
    controls.update();
    if (camera.position.distanceTo(target) < 0.005) {
      camera.position.copy(target);
      camera.up.set(0, 0, 1);
      resetTrackballSpin(controls);
      controls.update();
      targetPos.current = null;
    }
  });

  return null;
}

// Load a GLB and mount its scene graph.  Kept as a small component so
// GLB swaps are just a React key-change and Three tears down the old
// scene automatically.
function BuildingModel({
  url,
  clipName,
  onClips,
  onScene,
}: {
  url: string;
  clipName: string | null;
  onClips?: (names: string[]) => void;
  onScene?: (scene: THREE.Group | null, loadedUrl: string) => void;
}) {
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clipsRef = useRef<THREE.AnimationClip[]>([]);
  const actionRef = useRef<THREE.AnimationAction | null>(null);
  const onClipsRef = useRef(onClips);
  onClipsRef.current = onClips;
  const onSceneRef = useRef(onScene);
  onSceneRef.current = onScene;

  useEffect(() => {
    let cancelled = false;
    setScene(null);
    setError(null);
    mixerRef.current = null;
    clipsRef.current = [];
    actionRef.current = null;
    buildingGltfLoader.load(
      url,
      (gltf) => {
        if (cancelled) return;
        hideDragonFireMeshes(gltf.scene);
        setScene(gltf.scene);
        onSceneRef.current?.(gltf.scene, url);
        const clips = gltf.animations ?? [];
        clipsRef.current = clips;
        const order = ["idle", "walk", "run", "attack1", "attack2", "attack3", "die"];
        const names = [...clips.map((c) => c.name)].sort((a, b) => {
          const ia = order.indexOf(a.toLowerCase());
          const ib = order.indexOf(b.toLowerCase());
          return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
        });
        onClipsRef.current?.(names);
        if (clips.length > 0) {
          mixerRef.current = new THREE.AnimationMixer(gltf.scene);
        }
      },
      undefined,
      (err) => {
        console.error(`Failed to load building GLB ${url}:`, err);
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      },
    );
    return () => {
      cancelled = true;
      onSceneRef.current?.(null, url);
      mixerRef.current?.stopAllAction();
      mixerRef.current = null;
    };
  }, [url]);

  useEffect(() => {
    const mixer = mixerRef.current;
    const clips = clipsRef.current;
    if (!mixer || clips.length === 0) return;
    mixer.stopAllAction();
    actionRef.current = null;
    if (!clipName) return;
    const clip = clips.find((c) => c.name === clipName) ?? clips[0];
    if (!clip) return;
    const action = mixer.clipAction(clip);
    const loops = /^(idle(_\d+)?|walk|run|attack1|attack3)$/i.test(clipName);
    action.reset();
    action.loop = loops ? THREE.LoopRepeat : THREE.LoopOnce;
    action.clampWhenFinished = !loops;
    action.play();
    actionRef.current = action;
  }, [clipName, scene]);

  useFrame((_, delta) => {
    mixerRef.current?.update(delta);
  });

  if (error) {
    return (
      <Text
        position={[0, 1.2, 0]}
        fontSize={0.25}
        color="#f87171"
        anchorX="center"
        anchorY="middle"
        maxWidth={8}
      >
        {`Failed to load GLB\n${url}\n${error}`}
      </Text>
    );
  }
  if (!scene) return null;
  return (
    <>
      <primitive object={scene} />
      {dragonHasFireBreath(scene) && (
        <DragonFireBreath
          scene={scene}
          clipName={clipName}
          actionRef={actionRef}
          url={url}
        />
      )}
      {chickenHasEggBurst(scene) && (
        <ChickenEggBurst
          scene={scene}
          clipName={clipName}
          actionRef={actionRef}
        />
      )}
      {roosterHasButtFire(scene) && (
        <RoosterButtFire
          scene={scene}
          clipName={clipName}
          actionRef={actionRef}
        />
      )}
    </>
  );
}

/**
 * Modular forge assembly: one GLB of named pieces + a JSON manifest.
 * Selecting a stageKey tweens newly unlocked pieces from a spawn offset
 * down into rest pose (Z-up), matching Winter Cats-style piece drops.
 */
function AssemblyBuildingModel({
  modularUrl,
  manifestUrl,
  stageKey,
}: {
  modularUrl: string;
  manifestUrl: string;
  stageKey: AssemblyStageKey;
}) {
  const [root, setRoot] = useState<THREE.Group | null>(null);
  const [error, setError] = useState<string | null>(null);
  const piecesRef = useRef<Map<string, PieceAnim>>(new Map());
  const manifestRef = useRef<AssemblyManifest | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRoot(null);
    setError(null);
    piecesRef.current = new Map();
    manifestRef.current = null;

    Promise.all([
      new Promise<THREE.Group>((resolve, reject) => {
        buildingGltfLoader.load(
          modularUrl,
          (gltf) => resolve(gltf.scene),
          undefined,
          reject,
        );
      }),
      fetch(manifestUrl).then((r) => {
        if (!r.ok) throw new Error(`manifest ${r.status}`);
        return r.json() as Promise<AssemblyManifest>;
      }),
    ])
      .then(([scene, manifest]) => {
        if (cancelled) return;
        manifestRef.current = manifest;
        const byName = new Map<string, THREE.Object3D>();
        scene.traverse((obj) => {
          if (obj.name) byName.set(obj.name, obj);
        });

        const startScale = manifest.tween?.startScale ?? 0.92;
        const staggerSec = manifest.tween?.staggerSec ?? 0.07;
        const map = new Map<string, PieceAnim>();

        for (const def of manifest.pieces) {
          const obj = byName.get(def.id);
          if (!obj) {
            console.warn(`Assembly piece missing in GLB: ${def.id}`);
            continue;
          }
          const restPos = obj.position.clone();
          const restQuat = obj.quaternion.clone();
          const restScale = obj.scale.clone();
          const spawnPos = restPos
            .clone()
            .add(new THREE.Vector3(...def.spawnOffset));
          const spawnQuat = restQuat
            .clone()
            .multiply(
              new THREE.Quaternion().setFromAxisAngle(
                new THREE.Vector3(0, 0, 1),
                THREE.MathUtils.degToRad(def.spawnYawDeg),
              ),
            );
          obj.visible = false;
          map.set(def.id, {
            object: obj,
            restPos,
            restQuat,
            restScale,
            spawnPos,
            spawnQuat,
            startScale,
            duration: def.durationSec || 0.45,
            delay: (def.staggerIndex ?? 0) * staggerSec,
            startedAt: null,
            visible: false,
            settled: false,
          });
        }

        piecesRef.current = map;
        setRoot(scene);
      })
      .catch((err) => {
        console.error("Failed to load assembly assets:", err);
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [modularUrl, manifestUrl]);

  // Apply stage unlock set whenever stageKey (or freshly loaded root) changes.
  useEffect(() => {
    const manifest = manifestRef.current;
    const pieces = piecesRef.current;
    if (!manifest || pieces.size === 0) return;

    const unlocked = new Set(manifest.stages[stageKey] ?? []);
    const staggerSec = manifest.tween?.staggerSec ?? 0.07;
    const now = performance.now();

    // Newly unlocked pieces get a local stagger (0,1,2…) so walls don't
    // wait on foundation's global staggerIndex before dropping.
    const newcomers: PieceAnim[] = [];

    for (const [id, anim] of pieces) {
      const shouldShow = unlocked.has(id);
      if (!shouldShow) {
        anim.object.visible = false;
        anim.visible = false;
        anim.settled = false;
        anim.startedAt = null;
        continue;
      }
      // Already settled or mid-animation — leave alone.
      if (anim.settled || (anim.visible && anim.startedAt !== null)) {
        continue;
      }
      newcomers.push(anim);
    }

    newcomers.sort((a, b) => a.delay - b.delay);
    newcomers.forEach((anim, i) => {
      anim.delay = i * staggerSec;
      anim.visible = true;
      anim.settled = false;
      anim.startedAt = now;
      anim.object.visible = true;
      anim.object.position.copy(anim.spawnPos);
      anim.object.quaternion.copy(anim.spawnQuat);
      const s = anim.startScale;
      anim.object.scale.set(
        anim.restScale.x * s,
        anim.restScale.y * s,
        anim.restScale.z * s,
      );
    });
  }, [stageKey, root]);

  useFrame(() => {
    const pieces = piecesRef.current;
    if (pieces.size === 0) return;
    const now = performance.now();
    for (const anim of pieces.values()) {
      if (!anim.visible || anim.settled || anim.startedAt === null) continue;
      const elapsed = (now - anim.startedAt) / 1000 - anim.delay;
      if (elapsed < 0) {
        anim.object.position.copy(anim.spawnPos);
        anim.object.quaternion.copy(anim.spawnQuat);
        continue;
      }
      const t = easeOutCubic(elapsed / anim.duration);
      anim.object.position.lerpVectors(anim.spawnPos, anim.restPos, t);
      anim.object.quaternion.slerpQuaternions(anim.spawnQuat, anim.restQuat, t);
      const s = THREE.MathUtils.lerp(anim.startScale, 1, t);
      anim.object.scale.set(
        anim.restScale.x * s,
        anim.restScale.y * s,
        anim.restScale.z * s,
      );
      if (t >= 1) {
        anim.object.position.copy(anim.restPos);
        anim.object.quaternion.copy(anim.restQuat);
        anim.object.scale.copy(anim.restScale);
        anim.settled = true;
        anim.startedAt = null;
      }
    }
  });

  if (error) {
    return (
      <Text
        position={[0, 1.2, 0]}
        fontSize={0.25}
        color="#f87171"
        anchorX="center"
        anchorY="middle"
        maxWidth={8}
      >
        {`Failed to load assembly\n${error}`}
      </Text>
    );
  }
  if (!root) return null;
  return <primitive object={root} />;
}

export interface BuildingViewerProps {
  buildings: BuildingDefinition[];
  title: string;
  onHome: () => void;
}

export default function BuildingViewer({
  buildings,
  title,
  onHome,
}: BuildingViewerProps) {
  const defaultStageId = buildings[0]?.stages[0]?.id ?? "";
  const [selectedStageId, setSelectedStageId] = useState<string>(defaultStageId);

  const controlsRef = useRef<any>(null);
  const pendingViewRef = useRef<[number, number, number] | null>(null);

  const { building, stage } = useMemo(() => {
    for (const b of buildings) {
      const s = b.stages.find((s) => s.id === selectedStageId);
      if (s) return { building: b, stage: s };
    }
    const fallback = buildings[0];
    return { building: fallback, stage: fallback?.stages[0] };
  }, [buildings, selectedStageId]);

  const [clipName, setClipName] = useState<string | null>(null);
  const [clipNames, setClipNames] = useState<string[]>([]);
  const creatureRootRef = useRef<THREE.Group>(null);
  const [creatureScene, setCreatureScene] = useState<{
    scene: THREE.Group;
    url: string;
  } | null>(null);
  const [creatureFrame, setCreatureFrame] = useState<{
    camera: [number, number, number];
    target: [number, number, number];
  } | null>(null);
  const burnCommands = useRef<BurnDownCommands | null>(null);
  const [burnPhase, setBurnPhase] = useState<BurnPhase>("idle");
  const [burnFrame, setBurnFrame] = useState<{
    camera: [number, number, number];
    target: [number, number, number];
  } | null>(null);
  const roastCommands = useRef<RoastCommands | null>(null);
  const [roastPhase, setRoastPhase] = useState<RoastPhase>("idle");

  useEffect(() => {
    setClipName(null);
    setClipNames([]);
    setBurnPhase("idle");
    setRoastPhase("idle");
    if (!stage?.burnDown) setBurnFrame(null);
  }, [stage?.url, stage?.burnDown]);

  const handleBurnBounds = useCallback((box: THREE.Box3) => {
    if (box.isEmpty()) return;
    setBurnFrame(frameBuildingBox(box));
  }, []);

  const handleBurnPhase = useCallback((phase: BurnPhase) => {
    setBurnPhase(phase);
  }, []);

  const handleRoastBounds = useCallback((box: THREE.Box3) => {
    if (box.isEmpty()) return;
    setCreatureFrame(frameCreatureBox(box, CREATURE_FACE_SIGN));
  }, []);

  const handleRoastPhase = useCallback((phase: RoastPhase) => {
    setRoastPhase(phase);
  }, []);

  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    // On first render collapse every building EXCEPT the one that
    // owns the initially-selected stage.  Keeps the sidebar tidy when
    // the list grows past a handful of buildings.
    const active = buildings.find((b) =>
      b.stages.some((s) => s.id === defaultStageId),
    );
    return new Set(buildings.map((b) => b.id).filter((id) => id !== active?.id));
  });

  const toggleCollapsed = useCallback((buildingId: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(buildingId)) next.delete(buildingId);
      else next.add(buildingId);
      return next;
    });
  }, []);

  // When the user picks a stage from a collapsed group (e.g. via
  // keyboard / URL / future deep-linking), make sure that group is
  // expanded so the selection is visible.
  useEffect(() => {
    const owner = buildings.find((b) =>
      b.stages.some((s) => s.id === selectedStageId),
    );
    if (!owner) return;
    setCollapsed((prev) => {
      if (!prev.has(owner.id)) return prev;
      const next = new Set(prev);
      next.delete(owner.id);
      return next;
    });
  }, [buildings, selectedStageId]);

  const handleClips = useCallback((names: string[]) => {
    setClipNames(names);
    setClipName((prev) => {
      if (prev && names.includes(prev)) return prev;
      const pick = (want: string[]) =>
        names.find((n) => want.includes(n.toLowerCase()));
      return pick(["idle"]) ?? pick(["walk"]) ?? names[0] ?? null;
    });
  }, []);

  const handleCreatureScene = useCallback(
    (s: THREE.Group | null, loadedUrl: string) => {
      if (!s) {
        setCreatureScene((prev) => (prev?.url === loadedUrl ? null : prev));
        return;
      }
      setCreatureScene({ scene: s, url: loadedUrl });
    },
    [],
  );

  const orbitTarget =
    title === "Creatures"
      ? (creatureFrame?.target ?? CREATURE_TARGET)
      : (stage?.burnDown ? (burnFrame?.target ?? BUILDING_TARGET) : BUILDING_TARGET);
  const cameraStart =
    title === "Creatures"
      ? (creatureFrame?.camera ?? CREATURE_CAMERA)
      : (stage?.burnDown ? (burnFrame?.camera ?? BUILDING_CAMERA) : BUILDING_CAMERA);

  useLayoutEffect(() => {
    if (stage?.roast) return;
    if (title !== "Creatures" || !creatureScene || creatureScene.url !== stage?.url) {
      setCreatureFrame(null);
      return;
    }
    const root = creatureRootRef.current;
    if (!root) return;
    let attached: THREE.Object3D | null = creatureScene.scene;
    while (attached && attached !== root) attached = attached.parent;
    if (attached !== root) return;
    root.updateWorldMatrix(true, true);
    const box = new THREE.Box3().setFromObject(root);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    setCreatureFrame(frameCreatureBox(box, CREATURE_FACE_SIGN));
  }, [title, creatureScene, stage?.url, stage?.roast]);

  const handleSetView = useCallback((viewKey: string) => {
    const controls = controlsRef.current;
    if (!controls) return;
    const target = controls.target as THREE.Vector3;
    const cam = controls.object as THREE.Camera;
    const dist = cam.position.distanceTo(target);
    const offset = VIEW_OFFSETS[viewKey];
    if (!offset) return;
    resetTrackballSpin(controls);
    const desired: [number, number, number] = [
      target.x + offset[0] * dist,
      target.y + offset[1] * dist,
      target.z + offset[2] * dist,
    ];
    pendingViewRef.current = desired;
  }, []);

  const handleDownload = useCallback(() => {
    if (!stage) return;
    const a = document.createElement("a");
    a.href = stage.url;
    a.download = stage.url.split("/").pop() ?? "building.glb";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [stage]);

  if (!building || !stage) {
    return (
      <div className="error-screen">
        No {title.toLowerCase()} configured — add one to{" "}
        <code>viewer/src/types/buildings.ts</code>.
      </div>
    );
  }

  return (
    <div className="app-layout">
      <BuildingSidebar
        title={title}
        buildings={buildings}
        selectedStageId={selectedStageId}
        onSelectStage={setSelectedStageId}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
      />
      <div className="viewport-column">
        <div className="viewport">
          <div className="viewport-overlay">
            <div className="model-selector">
              <button
                className="model-toggle-btn"
                onClick={onHome}
                title="Return to category home"
              >
                &larr; Home
              </button>
            </div>
            <span className="building-header-title">
              {building.structureName} &middot; {stage.label}
            </span>
            <span className="building-header-sub">
              {building.label} &middot; {stage.description}
            </span>
          </div>
          <div className="top-right-cluster">
            <button
              className="export-btn"
              onClick={handleDownload}
              title={`Download ${stage.url.split("/").pop()}`}
            >
              Download GLB
            </button>
          </div>
          <Canvas
            gl={{ stencil: true }}
            camera={{
              position: cameraStart,
              up: [0, 0, 1],
              fov: 45,
              near: 0.01,
              far: 100,
            }}
            style={{ width: "100%", height: "100%" }}
            onCreated={({ camera }) => {
              camera.up.set(0, 0, 1);
            }}
          >
            <ambientLight intensity={0.4} />
            <Environment preset="studio" environmentIntensity={0.2} />
            <directionalLight position={[0, 8, 6]}   intensity={0.7} />
            <directionalLight position={[0, -8, 6]}  intensity={0.7} />
            <directionalLight position={[8, 0, 6]}   intensity={0.7} />
            <directionalLight position={[-8, 0, 6]}  intensity={0.7} />

            <Grid
              args={[20, 20]}
              rotation={[Math.PI / 2, 0, 0]}
              cellSize={0.25}
              cellThickness={0.5}
              cellColor="#2a2d3a"
              sectionSize={1}
              sectionThickness={1}
              sectionColor="#3a3d4a"
              fadeDistance={16}
              fadeStrength={1}
              infiniteGrid
            />

            <axesHelper args={[1.5]} />
            <Text position={[1.7, 0, 0]} fontSize={0.12} color="#ff4444" anchorX="left">+X</Text>
            <Text position={[0, 1.7, 0]} fontSize={0.12} color="#44ff44" anchorX="left">+Y</Text>
            <Text position={[0, 0, 1.7]} fontSize={0.12} color="#4488ff" anchorX="left">+Z</Text>

            {stage.burnDown ? (
              <BuildingBurnDown
                key={stage.url}
                url={stage.url}
                onBounds={handleBurnBounds}
                onPhase={handleBurnPhase}
                commandRef={burnCommands}
              />
            ) : stage.roast ? (
              <BirdRoast
                key={stage.url}
                url={stage.url}
                onBounds={handleRoastBounds}
                onPhase={handleRoastPhase}
                commandRef={roastCommands}
              />
            ) : stage.assembly ? (
              <AssemblyBuildingModel
                key={stage.assembly.modularUrl}
                modularUrl={stage.assembly.modularUrl}
                manifestUrl={stage.assembly.manifestUrl}
                stageKey={stage.assembly.stageKey}
              />
            ) : (
              <group
                ref={creatureRootRef}
                rotation={
                  title === "Creatures" ? CREATURE_MODEL_ROTATION : [0, 0, 0]
                }
              >
                <BuildingModel
                  key={stage.url}
                  url={stage.url}
                  clipName={clipName}
                  onClips={handleClips}
                  onScene={title === "Creatures" ? handleCreatureScene : undefined}
                />
              </group>
            )}

            {title === "Creatures" && creatureFrame && (
              <CameraSnap
                position={creatureFrame.camera}
                target={creatureFrame.target}
              />
            )}
            {stage.burnDown && burnFrame && (
              <CameraSnap
                position={burnFrame.camera}
                target={burnFrame.target}
              />
            )}
            <TrackballControls
              ref={controlsRef}
              makeDefault
              target={orbitTarget}
              staticMoving={false}
              dynamicDampingFactor={0.1}
              rotateSpeed={5}
              minDistance={0.5}
              maxDistance={stage.burnDown ? 80 : 30}
            />
            <CameraAnimator
              pendingViewRef={pendingViewRef}
              controlsRef={controlsRef}
            />
          </Canvas>

          {stage.roast && (
            <div className="clip-controls">
              <button
                className={`clip-btn fire${roastPhase === "idle" ? " active" : ""}`}
                onClick={() => roastCommands.current?.play()}
                disabled={roastPhase !== "idle"}
                title="Roast the bird in place"
              >
                Roast
              </button>
              <button
                className="clip-btn"
                onClick={() => roastCommands.current?.reset()}
                disabled={roastPhase === "idle"}
                title="Restore the bird"
              >
                Reset
              </button>
              <span className="burn-status">{ROAST_PHASE_LABEL[roastPhase]}</span>
            </div>
          )}
          {stage.burnDown && (
            <div className="clip-controls">
              <button
                className={`clip-btn fire${burnPhase === "idle" ? " active" : ""}`}
                onClick={() => burnCommands.current?.igniteDefault()}
                disabled={burnPhase !== "idle" || !burnFrame}
                title="Start a fire at the center of the bank floor"
              >
                Light Fire
              </button>
              <button
                className="clip-btn"
                onClick={() => burnCommands.current?.reset()}
                disabled={burnPhase === "idle"}
                title="Restore the bank and clear the fire"
              >
                Reset
              </button>
              <span className="burn-status">{BURN_PHASE_LABEL[burnPhase]}</span>
            </div>
          )}
          {clipNames.length > 1 && !stage.roast && (
            <div className="clip-controls">
              {clipNames.map((name) => (
                <button
                  key={name}
                  className={`clip-btn${clipName === name ? " active" : ""}`}
                  onClick={() => setClipName(name)}
                  title={`Play ${name}`}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
          <div className="axis-view-controls">
            {AXIS_VIEWS.map(({ key, label, colorClass }) => (
              <button
                key={key}
                className="axis-view-btn"
                onClick={() => handleSetView(key)}
                title={`${label} (${key})`}
              >
                <span className={`axis-view-tag ${colorClass}`}>{key}</span>
                <span className="axis-view-desc">{label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// Left sidebar mirroring the character viewer's `.sidebar` shape so the
// two viewers feel visually consistent when the user swaps modes.
function BuildingSidebar({
  title,
  buildings,
  selectedStageId,
  onSelectStage,
  collapsed,
  onToggleCollapsed,
}: {
  title: string;
  buildings: BuildingDefinition[];
  selectedStageId: string;
  onSelectStage: (id: string) => void;
  collapsed: Set<string>;
  onToggleCollapsed: (buildingId: string) => void;
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>{title}</h2>
      </div>
      <div className="sidebar-body">
        {buildings.map((b) => (
          <BuildingGroup
            key={b.id}
            building={b}
            selectedStageId={selectedStageId}
            onSelectStage={onSelectStage}
            isCollapsed={collapsed.has(b.id)}
            onToggleCollapsed={onToggleCollapsed}
          />
        ))}
      </div>
    </div>
  );
}

function BuildingGroup({
  building,
  selectedStageId,
  onSelectStage,
  isCollapsed,
  onToggleCollapsed,
}: {
  building: BuildingDefinition;
  selectedStageId: string;
  onSelectStage: (id: string) => void;
  isCollapsed: boolean;
  onToggleCollapsed: (buildingId: string) => void;
}) {
  return (
    <div className="category-group">
      <div
        className="category-header"
        onClick={() => onToggleCollapsed(building.id)}
        title={`${building.label} · ${building.componentName}`}
      >
        <span className="category-dot" style={{ background: "#4a9eff" }} />
        <span style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0 }}>
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {building.structureName}
          </span>
          <span style={{ fontSize: "0.75em", opacity: 0.6 }}>{building.label}</span>
        </span>
        <span className="category-count">({building.stages.length})</span>
        <span className={`category-chevron ${isCollapsed ? "" : "open"}`}>
          &#9654;
        </span>
      </div>
      {!isCollapsed &&
        building.stages.map((stage) =>
          renderStageRow(stage, selectedStageId, onSelectStage),
        )}
    </div>
  );
}

function renderStageRow(
  stage: BuildingStage,
  selectedStageId: string,
  onSelectStage: (id: string) => void,
) {
  const active = stage.id === selectedStageId;
  return (
    <div
      key={stage.id}
      className={`bone-item building-stage-row${active ? " selected" : ""}`}
      onClick={() => onSelectStage(stage.id)}
      title={stage.description}
    >
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {stage.label}
      </span>
    </div>
  );
}
