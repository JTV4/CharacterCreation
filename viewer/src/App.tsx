import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useCharacterModel } from "./hooks/useCharacterModel";
import { useTransformShortcuts } from "./hooks/useTransformShortcuts";
import type { AnimSpec, AnimManifest } from "./types/animation";
import type { AnimationPlayerState } from "./hooks/useAnimationPlayer";
import type { CharacterModel } from "./types";
import { animSpecToClip } from "./utils/animSpecToClip";
import type { EquipmentSpec, EquipmentState, EquipTransform, EquipmentSlotType, SlotTextures } from "./types/equipment";
import { SLOT_TYPE_CONFIGS } from "./types/equipment";
import type { BoneTransformOverride, ModelGender, GlbBoneInfo } from "./types";
import Scene from "./components/Scene";
import ViewportErrorBoundary from "./components/ViewportErrorBoundary";
import BoneSidebar from "./components/BoneSidebar";
import BoneInfoPanel from "./components/BoneInfoPanel";
import AnimationControls from "./components/AnimationControls";
import AnimationBridge from "./components/AnimationBridge";
import EquipmentPanel from "./components/EquipmentPanel";
import EquipmentMeshRenderer from "./components/EquipmentMeshRenderer";
import MeshInfoPanel from "./components/MeshInfoPanel";
import ToolPanel from "./components/ToolPanel";
import ToolAttachment from "./components/ToolAttachment";
import PoseEditor from "./components/PoseEditor";
import type { PoseKeyframe, PoseAnimationConfig } from "./components/PoseEditor";
import SlotBoundsVisualizer from "./components/SlotBoundsVisualizer";
import { TOOLS, DEFAULT_TOOL_TRANSFORM } from "./types/tools";
import type { ToolTransform, GizmoMode } from "./types/tools";

function triggerDownload(href: string, filename: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function cloneBoneHierarchy(root: THREE.Object3D): THREE.Object3D {
  const scene = new THREE.Scene();
  function walk(src: THREE.Object3D, parent: THREE.Object3D) {
    for (const child of src.children) {
      if ((child as THREE.Bone).isBone) {
        const bone = new THREE.Bone();
        bone.name = child.name;
        bone.position.copy(child.position);
        bone.quaternion.copy(child.quaternion);
        bone.scale.copy(child.scale);
        parent.add(bone);
        walk(child, bone);
      } else if (child.children.length > 0) {
        const group = new THREE.Object3D();
        group.name = child.name;
        group.position.copy(child.position);
        group.quaternion.copy(child.quaternion);
        group.scale.copy(child.scale);
        parent.add(group);
        walk(child, group);
      }
    }
  }
  walk(root, scene);
  return scene;
}

function ExportPanel({
  characters,
  animations,
  characterModel,
}: {
  characters: AnimManifest["characters"];
  animations: AnimManifest["animations"];
  characterModel: CharacterModel | null;
}) {
  const [open, setOpen] = useState(false);
  const [exportingAnim, setExportingAnim] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: globalThis.MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const handleExportModel = (model: string) => {
    triggerDownload(`/models/${model}`, model);
  };

  const handleExportAnimGlb = useCallback(async (file: string, animId: string) => {
    if (!characterModel) return;
    setExportingAnim(animId);
    try {
      const res = await fetch(`/animations/${file}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const spec = await res.json() as AnimSpec;
      const clip = animSpecToClip(spec, characterModel.boneRestPose);
      const skeletonScene = cloneBoneHierarchy(characterModel.skeletonRoot);

      const { GLTFExporter } = await import("three/examples/jsm/exporters/GLTFExporter.js");
      const exporter = new GLTFExporter();
      const glb = await exporter.parseAsync(skeletonScene, {
        binary: true,
        animations: [clip],
      });
      const blob = new Blob([glb as ArrayBuffer], { type: "model/gltf-binary" });
      const url = URL.createObjectURL(blob);
      triggerDownload(url, `${animId}.glb`);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export animation as GLB:", err);
    } finally {
      setExportingAnim(null);
    }
  }, [characterModel]);

  return (
    <div className="export-dropdown" ref={ref}>
      <button className="export-btn" onClick={() => setOpen((o) => !o)}>
        Export
      </button>
      {open && (
        <div className="export-panel">
          <div className="export-panel-header">Character Models</div>
          <div className="export-panel-subhint">Mesh + Skeleton (pair with default idle animation)</div>
          <div className="export-panel-divider" />
          <div className="export-panel-list">
            {characters.map((char) => (
              <div key={char.id} className="export-panel-row export-panel-export-row">
                <span className="export-panel-label">{char.id}</span>
                <button
                  className="export-panel-dl"
                  onClick={() => handleExportModel(char.model)}
                >
                  {char.model}
                </button>
              </div>
            ))}
          </div>
          <div className="export-panel-divider" />
          <div className="export-panel-header">Animations</div>
          <div className="export-panel-subhint">Animation data only (GLB with skeleton)</div>
          <div className="export-panel-divider" />
          <div className="export-panel-list">
            {animations.map((anim) => (
              <div key={anim.id} className="export-panel-row export-panel-export-row">
                <span className="export-panel-label">{anim.id}</span>
                <button
                  className="export-panel-dl"
                  disabled={exportingAnim === anim.id}
                  onClick={() => handleExportAnimGlb(anim.file, anim.id)}
                >
                  {exportingAnim === anim.id ? "Exporting..." : `${anim.id}.glb`}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const BODY_SLOT_IDS = new Set([
  "base_body",
  "base_male",
  "base_female",
]);

export default function App() {
  const [activeGender, setActiveGender] = useState<ModelGender>("female");
  const { model: characterModel, loading, error } = useCharacterModel(activeGender);

  const [selectedBone, setSelectedBone] = useState<string | null>(null);
  const [showMesh, setShowMesh] = useState(true);

  const [characters, setCharacters] = useState<AnimManifest["characters"]>([]);
  const [manifest, setManifest] = useState<AnimManifest["animations"]>([]);
  const [animSpec, setAnimSpec] = useState<AnimSpec | null>(null);
  const [animState, setAnimState] = useState<{
    currentTime: number;
    isPlaying: boolean;
    duration: number;
    speed: number;
    loop: boolean;
    activeAnimId: string | null;
  }>({
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

  const { transformMode, enterMode } = useTransformShortcuts({
    selectedBone,
    boneOverrides,
    onSetBoneOverride: handleSetBoneOverride,
    playerRef,
  });

  const [equipSpec, setEquipSpec] = useState<EquipmentSpec | null>(null);
  const [equipState, setEquipState] = useState<EquipmentState>({});
  const equipSlotIds = useMemo(
    () => equipSpec?.slots.filter((s) => !BODY_SLOT_IDS.has(s.id)).map((s) => s.id) ?? [],
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
          if (BODY_SLOT_IDS.has(slot.id)) continue;
          initial[slot.id] = false;
        }
        setEquipState(initial);
      })
      .catch((err) => {
        console.error("Failed to load equipment spec:", err);
        setEquipSpec(null);
      });
  }, []);

  const handleToggleSlot = useCallback((slotId: string, enabled: boolean) => {
    if (BODY_SLOT_IDS.has(slotId)) return;
    setEquipState((prev) => ({ ...prev, [slotId]: enabled }));
  }, []);

  const handleImportEquipment = useCallback(
    (slotType: EquipmentSlotType, name: string, url: string) => {
      const slotId = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/_+$/, "");
      const config = SLOT_TYPE_CONFIGS[slotType];

      const newSlot = {
        id: slotId,
        name,
        bilateral: config.bilateral,
        color: config.color,
        bones: config.bones,
        bounds: config.bounds,
        rules: {},
        hides_body_regions: config.hides_body_regions,
        url,
        mesh_type: config.mesh_type,
        mesh_params: {},
        source: "imported" as const,
      };

      setEquipSpec((prev) => {
        if (!prev) return prev;
        const existing = prev.slots.findIndex((s) => s.id === slotId);
        const slots = [...prev.slots];
        if (existing >= 0) {
          slots[existing] = newSlot;
        } else {
          slots.push(newSlot);
        }
        return { ...prev, slots };
      });

      setEquipState((prev) => ({ ...prev, [slotId]: true }));
    },
    [],
  );

  const [selectedEquipSlot, setSelectedEquipSlot] = useState<string | null>(null);
  const [equipTransforms, setEquipTransforms] = useState<Record<string, EquipTransform>>({});
  const [equipGizmoMode, setEquipGizmoMode] = useState<GizmoMode>("translate");
  const [slotTextures, setSlotTextures] = useState<SlotTextures>({});

  const handleSetSlotTexture = useCallback((slotId: string, dataUrl: string | null) => {
    setSlotTextures((prev) => {
      const next = { ...prev };
      if (dataUrl) {
        next[slotId] = dataUrl;
      } else {
        delete next[slotId];
      }
      return next;
    });
  }, []);

  const handleEquipTransformChange = useCallback(
    (id: string, t: EquipTransform) => {
      setEquipTransforms((prev) => ({ ...prev, [id]: t }));
    },
    [],
  );

  const handleResetEquipTransform = useCallback((id: string) => {
    setEquipTransforms((prev) => {
      const next = { ...prev };
      delete next[id];
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
  const [toolDetached, setToolDetached] = useState(false);

  const getToolDefault = useCallback((toolId: string | null): ToolTransform => {
    if (!toolId) return DEFAULT_TOOL_TRANSFORM;
    const tool = TOOLS.find((t) => t.id === toolId);
    return tool?.defaultTransform ?? DEFAULT_TOOL_TRANSFORM;
  }, []);

  const selectedToolTransform = useMemo(
    () =>
      selectedToolId
        ? toolTransforms[selectedToolId] ?? getToolDefault(selectedToolId)
        : DEFAULT_TOOL_TRANSFORM,
    [selectedToolId, toolTransforms, getToolDefault],
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
      [selectedToolId]: { ...getToolDefault(selectedToolId) },
    }));
  }, [selectedToolId, getToolDefault]);

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
      if (BODY_SLOT_IDS.has(slot.id)) continue;
      const hiddenBy = slot.rules?.hidden_by ?? [];
      for (const blockerId of hiddenBy) {
        if (effective[blockerId]) {
          effective[slot.id] = false;
        }
      }
    }
    return effective;
  }, [equipSpec, equipState]);

  const [basePose] = useState<Map<string, BoneTransformOverride>>(new Map());
  const [showSlotBounds, setShowSlotBounds] = useState(false);

  useEffect(() => {
    fetch("/animations/manifest.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<AnimManifest>;
      })
      .then((m) => {
        setCharacters(m.characters ?? []);
        setManifest(m.animations);
      })
      .catch(() => setManifest([]));
  }, []);

  const handleSelectAnimation = useCallback(
    (id: string) => {
      if (id === "tpose") {
        setAnimSpec(null);
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
      currentTime: state.currentTime,
      isPlaying: state.isPlaying,
      duration: state.duration,
      speed: state.speed,
      loop: state.loop,
      activeAnimId: state.activeAnimId,
    });
  }, []);

  const boneList = characterModel?.boneList ?? [];
  const selectedBoneInfo = useMemo(() => {
    if (!selectedBone || !characterModel) return null;
    return characterModel.boneList.find((b) => b.name === selectedBone) ?? null;
  }, [selectedBone, characterModel]);

  const selectedEquipSlotInfo = useMemo(() => {
    if (!selectedEquipSlot || !equipSpec) return null;
    return equipSpec.slots.find((s) => s.id === selectedEquipSlot) ?? null;
  }, [selectedEquipSlot, equipSpec]);

  const selectedEquipTransform = useMemo(
    () => selectedEquipSlot
      ? equipTransforms[selectedEquipSlot] ?? { position: [0, 0, 0] as [number, number, number], rotation: [0, 0, 0] as [number, number, number], scale: 1 }
      : { position: [0, 0, 0] as [number, number, number], rotation: [0, 0, 0] as [number, number, number], scale: 1 },
    [selectedEquipSlot, equipTransforms],
  );

  if (loading) {
    return <div className="loading-screen">Loading character model...</div>;
  }

  if (error || !characterModel) {
    return (
      <div className="error-screen">
        Failed to load character model: {error ?? "Unknown error"}
      </div>
    );
  }

  return (
    <div className="app-layout">
      <BoneSidebar
        boneList={boneList}
        selectedBone={selectedBone}
        onSelectBone={setSelectedBone}
      />
      <div className="viewport-column">
        <div className="viewport">
          <div className="viewport-overlay">
            <div className="model-selector">
              <button
                className={`model-toggle-btn ${activeGender === "female" ? "active" : ""}`}
                onClick={() => setActiveGender("female")}
              >
                Female
              </button>
              <button
                className={`model-toggle-btn ${activeGender === "male" ? "active" : ""}`}
                onClick={() => setActiveGender("male")}
              >
                Male
              </button>
            </div>
            <div className="model-selector">
              <button
                className={`model-toggle-btn ${showMesh ? "active" : ""}`}
                onClick={() => setShowMesh(true)}
              >
                Mesh
              </button>
              <button
                className={`model-toggle-btn ${!showMesh ? "active" : ""}`}
                onClick={() => setShowMesh(false)}
              >
                Bones
              </button>
            </div>
            <div className="model-selector">
              <button
                className={`model-toggle-btn ${showSlotBounds ? "active" : ""}`}
                onClick={() => setShowSlotBounds((v) => !v)}
                title="Show equipment slot bounding volumes"
              >
                Slot Bounds
              </button>
            </div>
            <span>
              {boneList.length} bones
              {(animState.activeAnimId ?? "T-pose") && (
                <>
                  {" "}
                  &middot; {animState.activeAnimId ?? "T-pose"}
                  {animState.isPlaying ? " (playing)" : ""}
                </>
              )}
            </span>
          </div>
          <ExportPanel characters={characters} animations={manifest} characterModel={characterModel} />
          <ViewportErrorBoundary>
            <Scene
              characterModel={characterModel}
              selectedBone={selectedBone}
              onSelectBone={setSelectedBone}
              transformMode={transformMode}
              showMesh={showMesh}
            >
            <AnimationBridge
              characterModel={characterModel}
              animSpec={animSpec}
              onStateChange={handlePlayerState}
              commandRef={playerRef}
              boneOverrides={boneOverrides}
              basePose={basePose}
              showMesh={showMesh}
            />
            {equipSpec && (
              <EquipmentMeshRenderer
                slotIds={equipSlotIds}
                slots={equipSpec.slots}
                equipState={equipState}
                effectiveState={effectiveEquipState}
                playerRef={playerRef}
                characterModel={characterModel}
                selectedSlot={selectedEquipSlot}
                onSelectSlot={setSelectedEquipSlot}
                equipTransforms={equipTransforms}
                equipGizmoMode={equipGizmoMode}
                onEquipTransformChange={handleEquipTransformChange}
                slotTextures={slotTextures}
              />
            )}
            {showSlotBounds && equipSpec && (
              <SlotBoundsVisualizer
                slots={equipSpec.slots.filter(
                  (s) => !BODY_SLOT_IDS.has(s.id) && (!s.gender || s.gender === activeGender),
                )}
              />
            )}
            {selectedTool && (
              <ToolAttachment
                key={selectedTool.id}
                tool={selectedTool}
                boneName="mixamorigRightHand"
                playerRef={playerRef}
                transform={selectedToolTransform}
                gizmoMode={toolGizmoMode}
                onTransformChange={handleToolTransformChange}
                detached={toolDetached}
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
          activeAnimId={animState.activeAnimId ?? "tpose"}
          isPlaying={animState.isPlaying}
          currentTime={animState.currentTime}
          duration={animState.duration}
          speed={animState.speed}
          loop={animState.loop}
          hasTracks={(animSpec?.tracks.length ?? 0) > 0 || animState.duration > 0}
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
          bone={selectedBoneInfo}
          boneList={boneList}
          boneOverrides={boneOverrides}
          onSetBoneOverride={handleSetBoneOverride}
          playerRef={playerRef}
          transformMode={transformMode}
          onEnterMode={enterMode}
        />
        <MeshInfoPanel
          slot={selectedEquipSlotInfo}
          transform={selectedEquipTransform}
          gizmoMode={equipGizmoMode}
          onGizmoModeChange={setEquipGizmoMode}
          onTransformChange={(t) => {
            if (selectedEquipSlot) handleEquipTransformChange(selectedEquipSlot, t);
          }}
          onReset={() => {
            if (selectedEquipSlot) handleResetEquipTransform(selectedEquipSlot);
          }}
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
            slots={equipSpec.slots.filter(
              (s) => !BODY_SLOT_IDS.has(s.id) && (!s.gender || s.gender === activeGender),
            )}
            equipState={equipState}
            onToggleSlot={handleToggleSlot}
            selectedSlot={selectedEquipSlot}
            onSelectSlot={setSelectedEquipSlot}
            onImportEquipment={handleImportEquipment}
            equipTransforms={equipTransforms}
            slotTextures={slotTextures}
            onSetSlotTexture={handleSetSlotTexture}
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
            detached={toolDetached}
            onDetachedChange={setToolDetached}
          />
        )}
      </div>
    </div>
  );
}
