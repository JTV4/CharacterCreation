import { Canvas, useThree, useFrame } from "@react-three/fiber";
import { OrbitControls, Grid, Text, Environment } from "@react-three/drei";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import {
  BUILDINGS,
  DEFAULT_BUILDING_STAGE_ID,
  type BuildingDefinition,
  type BuildingStage,
} from "../types/buildings";

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
    camera.position.lerp(target, 0.15);
    controls.update();
    if (camera.position.distanceTo(target) < 0.005) {
      camera.position.copy(target);
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
}: {
  url: string;
  clipName: string | null;
  onClips?: (names: string[]) => void;
}) {
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mixerRef = useRef<THREE.AnimationMixer | null>(null);
  const clipsRef = useRef<THREE.AnimationClip[]>([]);
  const actionRef = useRef<THREE.AnimationAction | null>(null);
  const onClipsRef = useRef(onClips);
  onClipsRef.current = onClips;

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
        setScene(gltf.scene);
        const clips = gltf.animations ?? [];
        clipsRef.current = clips;
        const order = ["idle", "walk", "attack1", "attack", "die"];
        const names = [...clips.map((c) => c.name)].sort((a, b) => {
          const ia = order.indexOf(a);
          const ib = order.indexOf(b);
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
    const loops = clipName === "idle" || clipName === "walk";
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
  return <primitive object={scene} />;
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
  onExitToCharacter: () => void;
}

export default function BuildingViewer({ onExitToCharacter }: BuildingViewerProps) {
  const [selectedStageId, setSelectedStageId] = useState<string>(
    DEFAULT_BUILDING_STAGE_ID,
  );

  const controlsRef = useRef<any>(null);
  const pendingViewRef = useRef<[number, number, number] | null>(null);

  const { building, stage } = useMemo(() => {
    for (const b of BUILDINGS) {
      const s = b.stages.find((s) => s.id === selectedStageId);
      if (s) return { building: b, stage: s };
    }
    const fallback = BUILDINGS[0];
    return { building: fallback, stage: fallback?.stages[0] };
  }, [selectedStageId]);

  const [clipName, setClipName] = useState<string | null>(null);
  const [clipNames, setClipNames] = useState<string[]>([]);

  useEffect(() => {
    setClipName(null);
    setClipNames([]);
  }, [stage?.url]);

  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    // On first render collapse every building EXCEPT the one that
    // owns the initially-selected stage.  Keeps the sidebar tidy when
    // the list grows past a handful of buildings.
    const active = BUILDINGS.find((b) =>
      b.stages.some((s) => s.id === DEFAULT_BUILDING_STAGE_ID),
    );
    return new Set(BUILDINGS.map((b) => b.id).filter((id) => id !== active?.id));
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
    const owner = BUILDINGS.find((b) =>
      b.stages.some((s) => s.id === selectedStageId),
    );
    if (!owner) return;
    setCollapsed((prev) => {
      if (!prev.has(owner.id)) return prev;
      const next = new Set(prev);
      next.delete(owner.id);
      return next;
    });
  }, [selectedStageId]);

  const handleClips = useCallback((names: string[]) => {
    setClipNames(names);
    setClipName((prev) => {
      if (prev && names.includes(prev)) return prev;
      if (names.includes("idle")) return "idle";
      if (names.includes("walk")) return "walk";
      return names[0] ?? null;
    });
  }, []);

  const handleSetView = useCallback((viewKey: string) => {
    const controls = controlsRef.current;
    if (!controls) return;
    const target = controls.target as THREE.Vector3;
    const cam = controls.object as THREE.Camera;
    const dist = cam.position.distanceTo(target);
    const offset = VIEW_OFFSETS[viewKey];
    if (!offset) return;
    pendingViewRef.current = [
      target.x + offset[0] * dist,
      target.y + offset[1] * dist,
      target.z + offset[2] * dist,
    ];
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
        No buildings configured — add one to <code>viewer/src/types/buildings.ts</code>.
      </div>
    );
  }

  return (
    <div className="app-layout">
      <BuildingSidebar
        buildings={BUILDINGS}
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
                onClick={onExitToCharacter}
                title="Return to the character viewer"
              >
                &larr; Characters
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
            camera={{ position: [4.5, 4.5, 3.0], fov: 45, near: 0.01, far: 100 }}
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

            {stage.assembly ? (
              <AssemblyBuildingModel
                key={stage.assembly.modularUrl}
                modularUrl={stage.assembly.modularUrl}
                manifestUrl={stage.assembly.manifestUrl}
                stageKey={stage.assembly.stageKey}
              />
            ) : (
              <BuildingModel
                key={stage.url}
                url={stage.url}
                clipName={clipName}
                onClips={handleClips}
              />
            )}

            <OrbitControls
              ref={controlsRef}
              makeDefault
              target={[0, 0, 0.75]}
              enableDamping
              dampingFactor={0.1}
              minDistance={0.5}
              maxDistance={30}
            />
            <CameraAnimator
              pendingViewRef={pendingViewRef}
              controlsRef={controlsRef}
            />
          </Canvas>

          {clipNames.length > 1 && (
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
  buildings,
  selectedStageId,
  onSelectStage,
  collapsed,
  onToggleCollapsed,
}: {
  buildings: BuildingDefinition[];
  selectedStageId: string;
  onSelectStage: (id: string) => void;
  collapsed: Set<string>;
  onToggleCollapsed: (buildingId: string) => void;
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Buildings</h2>
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
