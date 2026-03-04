import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useSkeletonData } from "./hooks/useSkeletonData";
import { useTransformShortcuts } from "./hooks/useTransformShortcuts";
import type { AnimSpec, AnimManifest } from "./types/animation";
import type { AnimationPlayerState, AnimatedBonePositions } from "./hooks/useAnimationPlayer";
import type { EquipmentSpec, EquipmentState } from "./types/equipment";
import type { BoneTransformOverride } from "./types";
import Scene from "./components/Scene";
import ViewportErrorBoundary from "./components/ViewportErrorBoundary";
import BoneSidebar from "./components/BoneSidebar";
import BoneInfoPanel from "./components/BoneInfoPanel";
import AnimationControls from "./components/AnimationControls";
import AnimationBridge from "./components/AnimationBridge";
import EquipmentPanel from "./components/EquipmentPanel";
import EquipmentMeshRenderer from "./components/EquipmentMeshRenderer";
import ToolPanel from "./components/ToolPanel";
import ToolAttachment from "./components/ToolAttachment";
import PoseEditor from "./components/PoseEditor";
import type { PoseKeyframe, PoseAnimationConfig } from "./components/PoseEditor";
import { TOOLS, DEFAULT_TOOL_TRANSFORM } from "./types/tools";
import type { ToolTransform, GizmoMode } from "./types/tools";

const STUB_ANIMS = new Set(["idle_combat", "idle_ready"]);
const RAD2DEG = 180 / Math.PI;

function computeBasePoseFromSpec(spec: AnimSpec): Map<string, BoneTransformOverride> {
  const pose = new Map<string, BoneTransformOverride>();
  for (const track of spec.tracks) {
    const kf0 = track.keyframes[0];
    if (!kf0) continue;
    const existing = pose.get(track.bone) ?? {
      position: [0, 0, 0] as [number, number, number],
      rotation: [0, 0, 0] as [number, number, number],
      scale: [1, 1, 1] as [number, number, number],
    };
    if (track.property === "rotation") {
      const q = new THREE.Quaternion(kf0.value[0], kf0.value[1], kf0.value[2], kf0.value[3]);
      const e = new THREE.Euler().setFromQuaternion(q, "XYZ");
      existing.rotation = [
        parseFloat((e.x * RAD2DEG).toFixed(3)),
        parseFloat((e.y * RAD2DEG).toFixed(3)),
        parseFloat((e.z * RAD2DEG).toFixed(3)),
      ];
    } else if (track.property === "position") {
      existing.position = [kf0.value[0], kf0.value[1], kf0.value[2]];
    }
    pose.set(track.bone, existing);
  }
  return pose;
}

function animDisplayName(id: string): string {
  return id.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join("");
}

function triggerDownload(href: string, filename: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function ExportPanel({ animations }: { animations: AnimManifest["animations"] }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const [available, setAvailable] = useState<AnimManifest["animations"]>([]);
  const [checked, setChecked] = useState<Set<string>>(new Set());

  useEffect(() => {
    const candidates = animations.filter((a) => !STUB_ANIMS.has(a.id));
    Promise.all(
      candidates.map((a) =>
        fetch(`/animations/${a.file}`)
          .then((r) => (r.ok ? (r.json() as Promise<AnimSpec>) : null))
          .then((spec) => (spec && spec.tracks?.length > 0 ? a : null))
          .catch(() => null),
      ),
    ).then((results) => {
      const real = results.filter((r): r is AnimManifest["animations"][number] => r !== null);
      setAvailable(real);
    });
  }, [animations]);

  useEffect(() => {
    if (!open) return;
    const close = (e: globalThis.MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const allChecked = available.length > 0 && checked.size === available.length;
  const someChecked = checked.size > 0 && !allChecked;

  const toggleAll = () => {
    if (allChecked) {
      setChecked(new Set());
    } else {
      setChecked(new Set(available.map((a) => a.id)));
    }
  };

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleExport = () => {
    if (checked.size === 0) return;

    if (checked.size === 1) {
      const id = [...checked][0];
      const name = animDisplayName(id);
      triggerDownload(`/animations/${name}.glb`, `${name}.glb`);
    } else {
      triggerDownload("/rig.glb", "rig.glb");
    }
    setOpen(false);
  };

  return (
    <div className="export-dropdown" ref={ref}>
      <button className="export-btn" onClick={() => setOpen((o) => !o)}>
        Export GLB
      </button>
      {open && (
        <div className="export-panel">
          <div className="export-panel-header">Export Animations</div>
          <button
            type="button"
            className="export-panel-row export-panel-standalone"
            onClick={() => {
              triggerDownload("/rig_tpose.glb", "rig_tpose.glb");
            }}
            title="Rig only, no animations"
          >
            <span style={{ width: 22, flexShrink: 0 }} aria-hidden />
            <span className="export-panel-label">Rig (T-pose)</span>
            <span className="export-panel-hint">rig_tpose.glb</span>
          </button>
          <div className="export-panel-divider" />
          <label className="export-panel-row export-panel-all">
            <input
              type="checkbox"
              checked={allChecked}
              ref={(el) => { if (el) el.indeterminate = someChecked; }}
              onChange={toggleAll}
            />
            <span className="export-panel-label">All Animations</span>
            <span className="export-panel-hint">rig.glb</span>
          </label>
          <div className="export-panel-divider" />
          <div className="export-panel-list">
            {available.map((anim) => {
              const name = animDisplayName(anim.id);
              return (
                <label key={anim.id} className="export-panel-row">
                  <input
                    type="checkbox"
                    checked={checked.has(anim.id)}
                    onChange={() => toggle(anim.id)}
                  />
                  <span className="export-panel-label">{name}</span>
                  <span className="export-panel-hint">{name}.glb</span>
                </label>
              );
            })}
          </div>
          <div className="export-panel-divider" />
          <div className="export-panel-footer">
            <span className="export-panel-count">
              {checked.size} of {available.length} selected
            </span>
            <button
              className="export-panel-go"
              disabled={checked.size === 0}
              onClick={handleExport}
            >
              Export{checked.size > 0 ? ` (${checked.size})` : ""}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const { data, error, loading } = useSkeletonData();
  const [selectedBone, setSelectedBone] = useState<string | null>(null);

  const [manifest, setManifest] = useState<AnimManifest["animations"]>([]);
  const [animSpec, setAnimSpec] = useState<AnimSpec | null>(null);
  const [animState, setAnimState] = useState<{
    animatedPositions: Map<string, AnimatedBonePositions> | null;
    currentTime: number;
    isPlaying: boolean;
    duration: number;
    speed: number;
    loop: boolean;
    activeAnimId: string | null;
  }>({
    animatedPositions: null,
    currentTime: 0,
    isPlaying: false,
    duration: 0,
    speed: 1,
    loop: true,
    activeAnimId: null,
  });

  const playerRef = useRef<AnimationPlayerState | null>(null);

  const [boneOverrides, setBoneOverrides] = useState<Map<string, BoneTransformOverride>>(new Map());

  const handleSetBoneOverride = useCallback(
    (boneName: string, override: BoneTransformOverride | null) => {
      setBoneOverrides((prev) => {
        const next = new Map(prev);
        if (override) {
          next.set(boneName, override);
        } else {
          next.delete(boneName);
        }
        return next;
      });
    },
    [],
  );

  const { transformMode } = useTransformShortcuts({
    selectedBone,
    boneOverrides,
    onSetBoneOverride: handleSetBoneOverride,
    playerRef,
  });

  const [equipSpec, setEquipSpec] = useState<EquipmentSpec | null>(null);
  const [equipState, setEquipState] = useState<EquipmentState>({});
  const equipSlotIds = useMemo(
    () => equipSpec?.slots.map((s) => s.id) ?? [],
    [equipSpec],
  );

  useEffect(() => {
    fetch("/equipment/equipment_spec.json?t=" + Date.now(), {
      cache: "no-store",
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<EquipmentSpec>;
      })
      .then((spec) => {
        setEquipSpec(spec);
        const initial: EquipmentState = {};
        for (const slot of spec.slots) {
          initial[slot.id] = slot.id === "base_body";
        }
        setEquipState(initial);
      })
      .catch((err) => {
        console.error("Failed to load equipment spec:", err);
        setEquipSpec(null);
      });
  }, []);

  const BODY_SLOT_IDS = [
    "base_body",
    "base_male",
    "base_female",
    "base_male_with_skin_texture",
    "base_female_with_skin_texture",
  ];

  const handleToggleSlot = useCallback((slotId: string, enabled: boolean) => {
    setEquipState((prev) => {
      const next = { ...prev, [slotId]: enabled };
      if (enabled && BODY_SLOT_IDS.includes(slotId)) {
        for (const other of BODY_SLOT_IDS) {
          if (other !== slotId) next[other] = false;
        }
      }
      return next;
    });
  }, []);

  const [selectedToolId, setSelectedToolId] = useState<string | null>(null);
  const selectedTool = useMemo(
    () => TOOLS.find((t) => t.id === selectedToolId) ?? null,
    [selectedToolId],
  );
  const [toolTransforms, setToolTransforms] = useState<Record<string, ToolTransform>>({});
  const [toolGizmoMode, setToolGizmoMode] = useState<GizmoMode>("translate");

  const selectedToolTransform = useMemo(
    () =>
      selectedToolId
        ? toolTransforms[selectedToolId] ?? DEFAULT_TOOL_TRANSFORM
        : DEFAULT_TOOL_TRANSFORM,
    [selectedToolId, toolTransforms],
  );

  const handleToolTransformChange = useCallback(
    (t: ToolTransform) => {
      if (!selectedToolId) return;
      setToolTransforms((prev) => ({ ...prev, [selectedToolId]: t }));
    },
    [selectedToolId],
  );

  const handleResetToolTransform = useCallback(() => {
    if (!selectedToolId) return;
    setToolTransforms((prev) => ({
      ...prev,
      [selectedToolId]: { ...DEFAULT_TOOL_TRANSFORM },
    }));
  }, [selectedToolId]);

  const [poseMode, setPoseMode] = useState(false);
  const [poseConfig, setPoseConfig] = useState<PoseAnimationConfig>({
    name: "NewAnimation",
    id: "new_animation",
    duration: 3.0,
    fps: 30,
    loop: true,
  });
  const [poseKeyframes, setPoseKeyframes] = useState<PoseKeyframe[]>([]);
  const [poseCurrentTime, setPoseCurrentTime] = useState(0);

  const handleTogglePoseMode = useCallback(() => {
    setPoseMode((prev) => !prev);
  }, []);

  const handleLoadOverrides = useCallback(
    (overrides: Map<string, BoneTransformOverride>) => {
      setBoneOverrides(overrides);
    },
    [],
  );

  const handleClearOverrides = useCallback(() => {
    setBoneOverrides(new Map());
  }, []);

  const effectiveEquipState = useMemo(() => {
    if (!equipSpec) return equipState;
    const effective = { ...equipState };
    for (const slot of equipSpec.slots) {
      const hiddenBy = slot.rules?.hidden_by ?? [];
      for (const blockerId of hiddenBy) {
        if (effective[blockerId]) {
          effective[slot.id] = false;
        }
      }
    }
    return effective;
  }, [equipSpec, equipState]);

  const [basePose, setBasePose] = useState<Map<string, BoneTransformOverride>>(new Map());
  const initialAnimLoaded = useRef(false);

  useEffect(() => {
    fetch("/animations/manifest.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<AnimManifest>;
      })
      .then((m) => setManifest(m.animations))
      .catch(() => setManifest([]));
  }, []);

  useEffect(() => {
    if (initialAnimLoaded.current || manifest.length === 0) return;
    const idle = manifest.find((a) => a.id === "idle");
    if (!idle) return;
    initialAnimLoaded.current = true;
    fetch(`/animations/${idle.file}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<AnimSpec>;
      })
      .then((spec) => {
        setBasePose(computeBasePoseFromSpec(spec));
        setAnimSpec(spec);
      })
      .catch((err) => console.error("Failed to auto-load idle:", err));
  }, [manifest]);

  const handleSelectAnimation = useCallback(
    (id: string) => {
      if (id === "tpose") {
        setAnimSpec(null);
        setBasePose(new Map());
        setBoneOverrides(new Map());
        playerRef.current?.setAnimation(null);
        playerRef.current?.stop();
        return;
      }
      const entry = manifest.find((a) => a.id === id);
      if (!entry) return;
      fetch(`/animations/${entry.file}`)
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json() as Promise<AnimSpec>;
        })
        .then((spec) => setAnimSpec(spec))
        .catch((err) => console.error("Failed to load animation:", err));
    },
    [manifest],
  );

  const handlePlayerState = useCallback((state: AnimationPlayerState) => {
    setAnimState({
      animatedPositions: state.animatedPositions,
      currentTime: state.currentTime,
      isPlaying: state.isPlaying,
      duration: state.duration,
      speed: state.speed,
      loop: state.loop,
      activeAnimId: state.activeAnimId,
    });
  }, []);

  if (loading) {
    return <div className="loading-screen">Loading rig spec...</div>;
  }

  if (error || !data) {
    return (
      <div className="error-screen">
        Failed to load rig spec: {error ?? "Unknown error"}
      </div>
    );
  }

  const selected = selectedBone ? data.boneMap.get(selectedBone) ?? null : null;

  return (
    <div className="app-layout">
      <BoneSidebar
        spec={data.spec}
        tree={data.tree}
        selectedBone={selectedBone}
        onSelectBone={setSelectedBone}
      />
      <div className="viewport-column">
        <div className="viewport">
          <div className="viewport-overlay">
            {data.spec.bones.length} bones &middot;{" "}
            {data.spec.meta.rest_pose.toUpperCase()} &middot;{" "}
            {data.spec.meta.scale}
            {(animSpec === null ? "T-pose" : animState.activeAnimId) && (
              <>
                {" "}
                &middot; {animSpec === null ? "T-pose" : animState.activeAnimId}
                {animState.isPlaying ? " (playing)" : ""}
              </>
            )}
          </div>
          <ExportPanel animations={manifest} />
          <ViewportErrorBoundary>
            <Scene
              spec={data.spec}
              selectedBone={selectedBone}
              onSelectBone={setSelectedBone}
              animatedPositions={animState.animatedPositions}
              transformMode={transformMode}
            >
            <AnimationBridge
              rigSpec={data.spec}
              animSpec={animSpec}
              onStateChange={handlePlayerState}
              commandRef={playerRef}
              boneOverrides={boneOverrides}
              basePose={basePose}
            />
            {equipSpec && (
              <EquipmentMeshRenderer
                slotIds={equipSlotIds}
                slots={equipSpec.slots}
                equipState={equipState}
                effectiveState={effectiveEquipState}
                playerRef={playerRef}
              />
            )}
            {selectedTool && (
              <ToolAttachment
                key={selectedTool.id}
                tool={selectedTool}
                boneName="hand_R"
                playerRef={playerRef}
                transform={selectedToolTransform}
                gizmoMode={toolGizmoMode}
                onTransformChange={handleToolTransformChange}
              />
            )}
            </Scene>
          </ViewportErrorBoundary>
          {transformMode && (
            <div className="transform-mode-indicator">
              <div className="transform-mode-label">
                {transformMode === "scale"
                  ? "Scale (S)"
                  : transformMode === "rotate"
                    ? "Rotate (R)"
                    : "Move (P)"}
              </div>
              <div className="transform-mode-hint">
                Move mouse to adjust &middot; Click to confirm &middot; Esc to
                cancel
              </div>
            </div>
          )}
        </div>
        <AnimationControls
          animations={manifest}
          activeAnimId={animSpec === null ? "tpose" : animState.activeAnimId}
          isPlaying={animState.isPlaying}
          currentTime={animState.currentTime}
          duration={animState.duration}
          speed={animState.speed}
          loop={animState.loop}
          hasTracks={(animSpec?.tracks.length ?? 0) > 0}
          onSelectAnimation={handleSelectAnimation}
          onPlay={() => playerRef.current?.play()}
          onPause={() => playerRef.current?.pause()}
          onStop={() => playerRef.current?.stop()}
          onSeek={(t) => playerRef.current?.seek(t)}
          onSetSpeed={(s) => playerRef.current?.setSpeed(s)}
          onSetLoop={(l) => playerRef.current?.setLoop(l)}
        />
      </div>
      <div className="right-panel">
        <BoneInfoPanel
          bone={selected}
          spec={data.spec}
          boneOverrides={boneOverrides}
          onSetBoneOverride={handleSetBoneOverride}
          playerRef={playerRef}
        />
        <PoseEditor
          enabled={poseMode}
          onToggle={handleTogglePoseMode}
          config={poseConfig}
          onConfigChange={setPoseConfig}
          keyframes={poseKeyframes}
          onKeyframesChange={setPoseKeyframes}
          currentTime={poseCurrentTime}
          onCurrentTimeChange={setPoseCurrentTime}
          boneOverrides={boneOverrides}
          onLoadOverrides={handleLoadOverrides}
          onClearOverrides={handleClearOverrides}
        />
        {!poseMode && equipSpec && (
          <EquipmentPanel
            slots={equipSpec.slots}
            equipState={equipState}
            onToggleSlot={handleToggleSlot}
          />
        )}
        {!poseMode && (
          <ToolPanel
            tools={TOOLS}
            selectedToolId={selectedToolId}
            onSelectTool={setSelectedToolId}
            transform={selectedToolTransform}
            gizmoMode={toolGizmoMode}
            onGizmoModeChange={setToolGizmoMode}
            onTransformChange={handleToolTransformChange}
            onResetTransform={handleResetToolTransform}
          />
        )}
      </div>
    </div>
  );
}
