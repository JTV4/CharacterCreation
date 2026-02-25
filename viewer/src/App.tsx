import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSkeletonData } from "./hooks/useSkeletonData";
import { useTransformShortcuts } from "./hooks/useTransformShortcuts";
import type { AnimSpec, AnimManifest } from "./types/animation";
import type { AnimationPlayerState, AnimatedBonePositions } from "./hooks/useAnimationPlayer";
import type { EquipmentSpec, EquipmentState } from "./types/equipment";
import type { BoneTransformOverride } from "./types";
import Scene from "./components/Scene";
import BoneSidebar from "./components/BoneSidebar";
import BoneInfoPanel from "./components/BoneInfoPanel";
import AnimationControls from "./components/AnimationControls";
import AnimationBridge from "./components/AnimationBridge";
import EquipmentPanel from "./components/EquipmentPanel";
import EquipmentMeshRenderer from "./components/EquipmentMeshRenderer";

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
  });

  const [equipSpec, setEquipSpec] = useState<EquipmentSpec | null>(null);
  const [equipState, setEquipState] = useState<EquipmentState>({});

  useEffect(() => {
    fetch("/equipment/equipment_spec.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<EquipmentSpec>;
      })
      .then((spec) => {
        setEquipSpec(spec);
        const initial: EquipmentState = {};
        for (const slot of spec.slots) {
          initial[slot.id] = false;
        }
        setEquipState(initial);
      })
      .catch(() => setEquipSpec(null));
  }, []);

  const handleToggleSlot = useCallback((slotId: string, enabled: boolean) => {
    setEquipState((prev) => ({ ...prev, [slotId]: enabled }));
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

  useEffect(() => {
    fetch("/animations/manifest.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<AnimManifest>;
      })
      .then((m) => setManifest(m.animations))
      .catch(() => setManifest([]));
  }, []);

  const handleSelectAnimation = useCallback(
    (id: string) => {
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
            {animState.activeAnimId && (
              <>
                {" "}
                &middot; {animState.activeAnimId}
                {animState.isPlaying ? " (playing)" : ""}
              </>
            )}
          </div>
          <a
            className="export-btn"
            href="/rig.glb"
            download="rig.glb"
          >
            Export GLB
          </a>
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
            />
            {equipSpec && (
              <EquipmentMeshRenderer
                slotIds={equipSpec.slots.map((s) => s.id)}
                equipState={equipState}
                effectiveState={effectiveEquipState}
                playerRef={playerRef}
              />
            )}
          </Scene>
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
          activeAnimId={animState.activeAnimId}
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
        />
        {equipSpec && (
          <EquipmentPanel
            slots={equipSpec.slots}
            equipState={equipState}
            onToggleSlot={handleToggleSlot}
          />
        )}
      </div>
    </div>
  );
}
