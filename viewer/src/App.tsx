import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { useCharacterModel } from "./hooks/useCharacterModel";
import { useTransformShortcuts } from "./hooks/useTransformShortcuts";
import type { AnimSpec, AnimManifest } from "./types/animation";
import type { AnimationPlayerState } from "./hooks/useAnimationPlayer";
import type { BoneRestTransform, CharacterModel } from "./types";
import { animSpecToClip } from "./utils/animSpecToClip";
import type { EquipmentSpec, EquipmentState, EquipTransform, EquipmentSlotType, SlotTextures } from "./types/equipment";
import { normalizeEquipTransform } from "./types/equipment";
import { SLOT_TYPE_CONFIGS } from "./types/equipment";
import { NPC_GENDERS, NPCS, NPC_NAMES, NPC_VARIANTS } from "./types";
import type { BoneTransformOverride, ModelGender, GlbBoneInfo } from "./types";
import Scene from "./components/Scene";
import ViewportErrorBoundary from "./components/ViewportErrorBoundary";
import BoneSidebar from "./components/BoneSidebar";
import BoneInfoPanel from "./components/BoneInfoPanel";
import AnimationControls from "./components/AnimationControls";
import AnimationBridge from "./components/AnimationBridge";
import EquipmentPanel from "./components/EquipmentPanel";
import EquipmentMeshRenderer, { exportSlotAsGlb } from "./components/EquipmentMeshRenderer";
import MeshInfoPanel from "./components/MeshInfoPanel";
import ToolPanel from "./components/ToolPanel";
import ToolAttachment from "./components/ToolAttachment";
import PoseEditor from "./components/PoseEditor";
import type { PoseKeyframe, PoseAnimationConfig } from "./components/PoseEditor";
import SlotBoundsVisualizer from "./components/SlotBoundsVisualizer";
import { TOOLS, DEFAULT_TOOL_TRANSFORM, DEFAULT_TOOL_ATTACH_BONE, isSharedBucketTool, isSharedWateringCanTool } from "./types/tools";
import type { ToolTransform, GizmoMode } from "./types/tools";
import SkinTransferModal from "./components/SkinTransferModal";
import type { SkinTransferRequest } from "./components/SkinTransferModal";
import BuildingViewer from "./components/BuildingViewer";
import CategoryHome from "./components/CategoryHome";
import { ROUTES, usePath } from "./routing";
import { buildingsInCategory } from "./types/buildings";
import type { ViewerCatalogCategory } from "./types/buildings";

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

// Dedicated GLTFLoader for the Export panel's "bake NPC + animations"
// flow.  Kept separate from the viewer's main loader so that toggling
// downloads doesn't interact with the active character or its mixer.
const exportGltfLoader = new GLTFLoader();

// Fixed list of NPC clips to embed in every baked NPC GLB.  Any clip
// added here is fetched, composed against the NPC's rest pose, and
// embedded in the exported GLB.
const NPC_EMBEDDED_CLIPS: ReadonlyArray<{ id: string; file: string }> = [
  { id: "NPCIdle", file: "NPCIdle.anim.json" },
  { id: "NPCWalk", file: "NPCWalk.anim.json" },
];

function isNpcCharacter(model: string): boolean {
  // NPC manifest entries point at `../NPCs/<Variant>/<File>.glb` to
  // hop out of `/models/` and into `/NPCs/`.  Player rig entries are
  // bare filenames like `BaseFemale.glb`.
  return model.startsWith("../NPCs/");
}

// Lookup from manifest characterId -> friendly displayName for NPC
// slots that have been promoted to named characters via NPC_OVERRIDES
// (Slate, Marina, Willow, Milly, Ruben, Hunter, Hopper, Blaise).
// Built once at module load; the export panel uses it to label rows
// with the friendly name and tag the variant context underneath.
const NPC_DISPLAY_INFO_BY_CHAR_ID = new Map(
  NPCS.filter((n) => n.displayName).map((n) => [
    n.characterId,
    { displayName: n.displayName!, variantLabel: n.variant.label },
  ]),
);

// Resolve the on-disk download filename for an NPC export.  Promoted
// slots are saved as `<DisplayName>.glb` (e.g. `Slate.glb`); other
// slots keep their source filename basename.
function npcDownloadFilename(
  char: AnimManifest["characters"][number],
): string {
  const info = NPC_DISPLAY_INFO_BY_CHAR_ID.get(char.id);
  if (info) return `${info.displayName}.glb`;
  return char.model.split("/").pop() ?? `${char.id}.glb`;
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
  const [exportingChar, setExportingChar] = useState<string | null>(null);
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

  // Bake NPCIdle + NPCWalk against an NPC's own rest pose and download
  // a self-contained GLB with both clips embedded.  Uses delta-mode
  // composition (rest * delta -> absolute) so the exported clips look
  // correct on this specific NPC even though they live in source as
  // a single shared spec.  Each download is independent of the
  // currently-loaded viewer character.
  const handleDownloadNpcWithAnims = useCallback(
    async (char: AnimManifest["characters"][number]) => {
      setExportingChar(char.id);
      try {
        const url = `/models/${char.model}`;

        const gltf = await new Promise<{ scene: THREE.Group }>((resolve, reject) => {
          exportGltfLoader.load(url, resolve, undefined, reject);
        });
        const scene = gltf.scene;

        const boneRestPose = new Map<string, BoneRestTransform>();
        scene.traverse((child) => {
          if ((child as THREE.Bone).isBone) {
            boneRestPose.set(child.name, {
              position: child.position.clone(),
              quaternion: child.quaternion.clone(),
            });
          }
        });

        const specs = await Promise.all(
          NPC_EMBEDDED_CLIPS.map(async ({ file }) => {
            const res = await fetch(`/animations/${file}`);
            if (!res.ok) throw new Error(`HTTP ${res.status} for ${file}`);
            return (await res.json()) as AnimSpec;
          }),
        );
        const clips = specs.map((spec) => animSpecToClip(spec, boneRestPose));

        const { GLTFExporter } = await import("three/examples/jsm/exporters/GLTFExporter.js");
        const exporter = new GLTFExporter();
        const glb = await exporter.parseAsync(scene, {
          binary: true,
          animations: clips,
        });

        // Promoted NPCs (Slate, Marina, Willow, ...) download as
        // `<DisplayName>.glb` so the file the user gets matches the
        // friendly name shown in the UI.  Unpromoted slots fall back to
        // the source GLB filename.
        const downloadName = npcDownloadFilename(char);
        const blob = new Blob([glb as ArrayBuffer], { type: "model/gltf-binary" });
        const blobUrl = URL.createObjectURL(blob);
        triggerDownload(blobUrl, downloadName);
        URL.revokeObjectURL(blobUrl);
      } catch (err) {
        console.error(`Failed to export ${char.id} with animations:`, err);
      } finally {
        setExportingChar(null);
      }
    },
    [],
  );

  const playerChars = characters.filter((c) => !isNpcCharacter(c.model));
  const npcChars = characters.filter((c) => isNpcCharacter(c.model));

  return (
    <div className="export-dropdown" ref={ref}>
      <button className="export-btn" onClick={() => setOpen((o) => !o)}>
        Export
      </button>
      {open && (
        <div className="export-panel">
          <div className="export-panel-header">Player Rigs</div>
          <div className="export-panel-subhint">Mesh + Skeleton (pair with default idle animation)</div>
          <div className="export-panel-divider" />
          <div className="export-panel-list">
            {playerChars.map((char) => (
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
          <div className="export-panel-header">NPCs (with embedded animations)</div>
          <div className="export-panel-subhint">
            Mesh + Skeleton + {NPC_EMBEDDED_CLIPS.map((c) => c.id).join(" + ")} baked against this NPC&rsquo;s rest pose
          </div>
          <div className="export-panel-divider" />
          <div className="export-panel-list">
            {npcChars.map((char) => {
              const downloadName = npcDownloadFilename(char);
              const isBaking = exportingChar === char.id;
              const info = NPC_DISPLAY_INFO_BY_CHAR_ID.get(char.id);
              const labelText = info ? info.displayName : char.id;
              const labelTitle = info
                ? `${info.displayName} \u2014 ${info.variantLabel} (${char.id})`
                : char.id;
              return (
                <div key={char.id} className="export-panel-row export-panel-export-row">
                  <span className="export-panel-label" title={labelTitle}>{labelText}</span>
                  <button
                    className="export-panel-dl"
                    disabled={isBaking}
                    onClick={() => handleDownloadNpcWithAnims(char)}
                    title={`Bake ${NPC_EMBEDDED_CLIPS.map((c) => c.id).join(" + ")} into ${downloadName} and download`}
                  >
                    {isBaking ? "Baking..." : downloadName}
                  </button>
                </div>
              );
            })}
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
  "base_female_v2",
  "base_male_v2",
]);

// Maps hides_body_regions strings → mesh object names in BaseFemaleV2.glb
const REGION_TO_MESH: Record<string, string> = {
  head:         "base_body_head",
  neck:         "base_body_head",
  upper_torso:  "base_body_upper_torso",
  lower_torso:  "base_body_lower_torso",
  arm_upper:    "base_body_arm_upper",
  arm_lower:    "base_body_arm_lower",
  hands:        "base_body_hands",
  leg_upper:    "base_body_leg_upper",
  leg_thigh:    "base_body_leg_thigh",
  leg_knee:     "base_body_leg_knee",
  leg_shin:     "base_body_leg_shin",
  leg_ankle:    "base_body_leg_ankle",
  foot:         "base_body_foot",
};

const BODY_PART_NAMES = new Set([
  "base_body_head",
  "base_body_upper_torso",
  "base_body_lower_torso",
  "base_body_arm_upper",
  "base_body_arm_lower",
  "base_body_hands",
  "base_body_leg_upper",
  "base_body_leg_thigh",
  "base_body_leg_knee",
  "base_body_leg_shin",
  "base_body_leg_ankle",
  "base_body_foot",
]);

/** Segmented Mixamo bases that support per-region hide + Shell V1 equipment. */
const SEGMENTED_GENDERS = new Set<ModelGender>(["female_v2", "female_v3", "male_v2"]);

/**
 * Equipment gender gate. Female V3 shares Female V2's skeleton and region
 * layout, so it accepts `gender: "female_v2"` slots.
 */
function slotMatchesGender(
  slotGender: string | undefined,
  active: ModelGender,
): boolean {
  if (!slotGender) return true;
  if (slotGender === active) return true;
  if (active === "female_v3" && slotGender === "female_v2") return true;
  return false;
}

function CharacterViewer({ onHome }: { onHome: () => void }) {
  const [activeGender, setActiveGender] = useState<ModelGender>("female");
  const { model: characterModel, loading, error } = useCharacterModel(activeGender);
  const isNPC = NPC_GENDERS.has(activeGender);

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
    const specFiles = [
      "/equipment/equipment_spec.json",
      "/equipment/equipment_spec_female_v2.json",
      "/equipment/equipment_spec_male_v2.json",
    ];
    Promise.all(
      specFiles.map((url) =>
        fetch(url + "?t=" + Date.now(), { cache: "no-store" })
          .then((res) => {
            if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
            return res.json() as Promise<EquipmentSpec>;
          }),
      ),
    )
      .then((specs) => {
        const merged: EquipmentSpec = { meta: specs[0].meta, slots: [] };
        const seen = new Set<string>();
        for (const spec of specs) {
          for (const slot of spec.slots) {
            if (!seen.has(slot.id)) {
              seen.add(slot.id);
              merged.slots.push(slot);
            }
          }
        }
        setEquipSpec(merged);
        const initial: EquipmentState = {};
        for (const slot of merged.slots) {
          if (BODY_SLOT_IDS.has(slot.id)) continue;
          initial[slot.id] = false;
        }
        setEquipState(initial);
      })
      .catch((err) => {
        console.error("Failed to load equipment specs:", err);
        setEquipSpec(null);
      });
  }, []);

  const handleToggleSlot = useCallback((slotId: string, enabled: boolean) => {
    if (BODY_SLOT_IDS.has(slotId)) return;
    setEquipState((prev) => {
      const next = { ...prev, [slotId]: enabled };
      // Face feature types are mutually exclusive within each category
      // (eyes, brows, lashes, nose, mouth, ears).
      const FACE_EXCLUSIVE = new Set([
        "eyes", "eyebrows", "eyelashes", "nose", "mouth", "ears",
      ]);
      if (enabled && equipSpec) {
        const toggled = equipSpec.slots.find((s) => s.id === slotId);
        const cat = toggled?.category;
        if (cat && FACE_EXCLUSIVE.has(cat)) {
          for (const slot of equipSpec.slots) {
            if (slot.category === cat && slot.id !== slotId) {
              next[slot.id] = false;
            }
          }
        }
      }
      return next;
    });
  }, [equipSpec]);

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
  const [equipTransforms, setEquipTransforms] = useState<Record<string, EquipTransform>>(() => {
    try {
      const saved = localStorage.getItem("equipTransforms");
      if (!saved) return {};
      const parsed = JSON.parse(saved) as Record<string, EquipTransform>;
      const normalized: Record<string, EquipTransform> = {};
      for (const [id, t] of Object.entries(parsed)) {
        normalized[id] = normalizeEquipTransform(t);
      }
      return normalized;
    } catch {
      return {};
    }
  });
  const [equipGizmoMode, setEquipGizmoMode] = useState<GizmoMode>("translate");
  const [slotTextures, setSlotTextures] = useState<SlotTextures>({});
  const [skinTransferTarget, setSkinTransferTarget] = useState<string | null>(null);
  const [skinTransferRequest, setSkinTransferRequest] = useState<SkinTransferRequest | null>(null);

  const handleOpenSkinModal = useCallback((slotId: string) => {
    setSkinTransferTarget(slotId);
  }, []);

  const handleSkinTransfer = useCallback((req: SkinTransferRequest) => {
    setSkinTransferRequest(req);
  }, []);

  const [reweightedSlots, setReweightedSlots] = useState<Set<string>>(new Set());

  const handleSkinTransferDone = useCallback((reweightedSlotId?: string) => {
    setSkinTransferRequest(null);
    setSkinTransferTarget(null);
    if (reweightedSlotId) {
      setReweightedSlots((prev) => new Set([...prev, reweightedSlotId]));
    }
  }, []);

  const handleExportWeightedSlot = useCallback((slotId: string) => {
    const slotDef = equipSpec?.slots.find((s) => s.id === slotId);
    const raw = equipTransforms[slotId] ?? slotDef?.default_transform;
    const transform = raw ? normalizeEquipTransform(raw) : undefined;
    exportSlotAsGlb(slotId, `${slotId}_weighted.glb`, transform);
  }, [equipTransforms, equipSpec]);

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

  useEffect(() => {
    try {
      localStorage.setItem("equipTransforms", JSON.stringify(equipTransforms));
    } catch {
      // ignore storage errors
    }
  }, [equipTransforms]);

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
  const [toolTransforms, setToolTransforms] = useState<Record<string, ToolTransform>>(() => {
    try {
      const saved = localStorage.getItem("toolTransforms");
      if (!saved) return {};
      return JSON.parse(saved) as Record<string, ToolTransform>;
    } catch {
      return {};
    }
  });
  const [toolGizmoMode, setToolGizmoMode] = useState<GizmoMode>("translate");
  const [toolDetached, setToolDetached] = useState(false);

  const getToolDefault = useCallback((toolId: string | null): ToolTransform => {
    if (!toolId) return DEFAULT_TOOL_TRANSFORM;
    const tool = TOOLS.find((t) => t.id === toolId);
    return tool?.defaultTransform ?? DEFAULT_TOOL_TRANSFORM;
  }, []);

  const selectedToolTransform = useMemo(
    () => {
      if (!selectedToolId) return DEFAULT_TOOL_TRANSFORM;
      if (isSharedBucketTool(selectedToolId)) {
        return (
          toolTransforms.empty_bucket ??
          toolTransforms[selectedToolId] ??
          getToolDefault("empty_bucket")
        );
      }
      if (isSharedWateringCanTool(selectedToolId)) {
        return (
          toolTransforms.empty_tin_watering_can ??
          toolTransforms[selectedToolId] ??
          getToolDefault("empty_tin_watering_can")
        );
      }
      return toolTransforms[selectedToolId] ?? getToolDefault(selectedToolId);
    },
    [selectedToolId, toolTransforms, getToolDefault],
  );

  useEffect(() => {
    try {
      localStorage.setItem("toolTransforms", JSON.stringify(toolTransforms));
    } catch {
      // ignore storage errors
    }
  }, [toolTransforms]);

  const handleToolTransformChange = useCallback(
    (t: ToolTransform) => {
      if (!selectedToolId) return;
      const key = isSharedBucketTool(selectedToolId)
        ? "empty_bucket"
        : isSharedWateringCanTool(selectedToolId)
          ? "empty_tin_watering_can"
          : selectedToolId;
      setToolTransforms((prev) => ({ ...prev, [key]: t }));
    },
    [selectedToolId],
  );

  const handleResetToolTransform = useCallback(() => {
    if (!selectedToolId) return;
    const key = isSharedBucketTool(selectedToolId)
      ? "empty_bucket"
      : isSharedWateringCanTool(selectedToolId)
        ? "empty_tin_watering_can"
        : selectedToolId;
    setToolTransforms((prev) => ({
      ...prev,
      [key]: { ...getToolDefault(selectedToolId) },
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

  // Manual per-part visibility toggles (user-controlled)
  const [hiddenBodyParts, setHiddenBodyParts] = useState<Set<string>>(new Set());

  const handleToggleBodyPart = useCallback((partName: string) => {
    setHiddenBodyParts((prev) => {
      const next = new Set(prev);
      if (next.has(partName)) {
        next.delete(partName);
      } else {
        next.add(partName);
      }
      return next;
    });
  }, []);

  // Auto-hide body parts covered by equipped items (segmented V2/V3 bases)
  const autoHiddenBodyParts = useMemo<Set<string>>(() => {
    if (!SEGMENTED_GENDERS.has(activeGender)) return new Set();
    if (!equipSpec) return new Set();
    const hidden = new Set<string>();
    for (const slot of equipSpec.slots) {
      if (!effectiveEquipState[slot.id]) continue;
      for (const region of (slot.hides_body_regions ?? [])) {
        const meshName = REGION_TO_MESH[region];
        if (meshName) hidden.add(meshName);
      }
    }
    return hidden;
  }, [activeGender, equipSpec, effectiveEquipState]);

  // Apply visibility to scene: hide if auto-hidden OR manually hidden
  useEffect(() => {
    if (!characterModel) return;
    characterModel.scene.traverse((child) => {
      if (BODY_PART_NAMES.has(child.name)) {
        child.visible = !autoHiddenBodyParts.has(child.name) && !hiddenBodyParts.has(child.name);
      }
    });
  }, [characterModel, autoHiddenBodyParts, hiddenBodyParts]);

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

  // Map ModelGender → character-id used in the animation manifest's
  // `for_character` binding (e.g. `npc_finn` → "FinnFemale").  Player
  // rigs don't have a character-id binding right now, so they map to
  // null and any non-`for_character` animation in their category passes.
  const activeCharacterId = useMemo(() => {
    const npc = NPCS.find((n) => n.id === activeGender);
    return npc?.characterId ?? null;
  }, [activeGender]);

  // Animations available for the currently-active character.  Filtering
  // happens in two passes:
  //   1. Category gate — NPC-tagged entries only show while an NPC is
  //      active; everything else shows for the player rigs (Female/
  //      Male/V2 series).  Animations targeting Mixamo bones can't drive
  //      the NPC rig and vice versa, so mixing them just creates dead
  //      options in the picker.
  //   2. Character gate — per-character animations (those with a
  //      `for_character` field, e.g. `FinnWalk`) are hidden unless the
  //      active character matches.  This lets each NPC have a walk tuned
  //      to its own Hips rest height while still sharing the
  //      character-agnostic NPCIdle.
  const visibleAnimations = useMemo(
    () =>
      manifest.filter((a) => {
        if (isNPC ? a.category !== "npc" : a.category === "npc") return false;
        if (a.for_character && a.for_character !== activeCharacterId) return false;
        return true;
      }),
    [manifest, isNPC, activeCharacterId],
  );

  // When the active character changes, drop the active clip ONLY if
  // we cross the rig boundary (player <-> NPC).  In that case the
  // spec targets bones that don't exist on the new rig and would
  // produce a silent no-op or a deformed pose.
  //
  // NPC <-> NPC swaps no longer reset: both NPCIdle and NPCWalk are
  // delta-mode clips against the shared Meshy skeleton, so they apply
  // cleanly to every NPC in the roster.  The animation player rebinds
  // the active spec to the new skeleton (see useAnimationPlayer), so
  // the user can flip between NPCs while the idle/walk keeps running.
  const prevGenderRef = useRef(activeGender);
  useEffect(() => {
    if (prevGenderRef.current === activeGender) return;
    const prevWasNPC = NPC_GENDERS.has(prevGenderRef.current);
    const nowIsNPC = NPC_GENDERS.has(activeGender);
    prevGenderRef.current = activeGender;

    const crossesRigBoundary = prevWasNPC !== nowIsNPC;
    if (crossesRigBoundary) {
      setAnimSpec(null);
      setBoneOverrides(new Map());
      playerRef.current?.setAnimation(null);
      playerRef.current?.stop();
    }
  }, [activeGender]);

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
    () => {
      const identity = normalizeEquipTransform({
        position: [0, 0, 0],
        rotation: [0, 0, 0],
        scale: [1, 1, 1],
      });
      if (!selectedEquipSlot) return identity;
      const raw =
        equipTransforms[selectedEquipSlot]
        ?? selectedEquipSlotInfo?.default_transform
        ?? identity;
      return normalizeEquipTransform(raw);
    },
    [selectedEquipSlot, selectedEquipSlotInfo, equipTransforms],
  );

  // First-time mount: nothing rendered yet, so we hard-block on the
  // initial GLB load.  Subsequent gender swaps don't take this branch
  // because `useCharacterModel` keeps the previous model in `model`
  // until the next one finishes loading — that preserves Canvas state
  // (camera, mixer, etc.) across swaps.
  if (loading && !characterModel) {
    return <div className="loading-screen">Loading character model...</div>;
  }

  if (error && !characterModel) {
    return (
      <div className="error-screen">
        Failed to load character model: {error}
      </div>
    );
  }

  if (!characterModel) {
    return (
      <div className="error-screen">
        Failed to load character model: Unknown error
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
                className="model-toggle-btn buildings-mode-btn"
                onClick={onHome}
                title="Return to category home"
              >
                &larr; Home
              </button>
            </div>
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
              <button
                className={`model-toggle-btn ${activeGender === "female_v2" ? "active" : ""}`}
                onClick={() => setActiveGender("female_v2")}
                title="Female V2 — segmented body (each region can be hidden by equipment)"
              >
                Female V2
              </button>
              <button
                className={`model-toggle-btn ${activeGender === "female_v3" ? "active" : ""}`}
                onClick={() => setActiveGender("female_v3")}
                title="Female V3 — White-skinned modular base (same regions as V2, baked skin texture)"
              >
                Female V3
              </button>
              <button
                className={`model-toggle-btn ${activeGender === "male_v2" ? "active" : ""}`}
                onClick={() => setActiveGender("male_v2")}
                title="Male V2 — segmented body (morphed from female, same skeleton)"
              >
                Male V2
              </button>
              <button
                className={`model-toggle-btn ${activeGender === "grind_male" ? "active" : ""}`}
                onClick={() => setActiveGender("grind_male")}
                title="GrindMale — original male mesh designed from scratch for GrindScape"
              >
                GrindMale
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
            {!isNPC && (
              <div className="model-selector">
                <button
                  className={`model-toggle-btn ${showSlotBounds ? "active" : ""}`}
                  onClick={() => setShowSlotBounds((v) => !v)}
                  title="Show equipment slot bounding volumes"
                >
                  Slot Bounds
                </button>
              </div>
            )}
            {!isNPC && (
            <div className="body-parts-dropdown">
              {(() => {
                const totalHidden = new Set([...hiddenBodyParts, ...autoHiddenBodyParts]).size;
                return (
                  <button className={`model-toggle-btn body-parts-trigger${totalHidden > 0 ? " has-hidden" : ""}`}>
                    Body Parts{totalHidden > 0 ? ` (${totalHidden} hidden)` : ""}
                  </button>
                );
              })()}
              <div className="body-parts-menu">
                <div className="body-parts-menu-inner">
                  <div className="body-parts-menu-title">
                    Visibility
                    {SEGMENTED_GENDERS.has(activeGender) && autoHiddenBodyParts.size > 0 && (
                      <span className="body-parts-auto-label"> (auto)</span>
                    )}
                  </div>
                  {([
                    { id: "base_body_head",         label: "Head"              },
                    { id: "base_body_upper_torso",  label: "Upper Torso"       },
                    { id: "base_body_lower_torso",  label: "Lower Torso"       },
                    { id: "base_body_arm_upper",    label: "Arm — Upper"       },
                    { id: "base_body_arm_lower",    label: "Arm — Lower"       },
                    { id: "base_body_hands",        label: "Hands"             },
                    { id: "base_body_leg_upper",    label: "Leg — Upper Thigh" },
                    { id: "base_body_leg_thigh",    label: "Leg — Thigh"       },
                    { id: "base_body_leg_knee",     label: "Leg — Knee"        },
                    { id: "base_body_leg_shin",     label: "Leg — Shin"        },
                    { id: "base_body_leg_ankle",    label: "Leg — Ankle"       },
                    { id: "base_body_foot",         label: "Foot"              },
                  ] as const).map(({ id, label }) => {
                    const isAutoHidden = autoHiddenBodyParts.has(id);
                    const isManualHidden = hiddenBodyParts.has(id);
                    const isVisible = !isAutoHidden && !isManualHidden;
                    return (
                      <button
                        key={id}
                        className={`body-parts-item${isVisible ? " visible" : ""}${isAutoHidden ? " auto-hidden" : ""}`}
                        onClick={() => handleToggleBodyPart(id)}
                        title={isAutoHidden ? "Hidden by equipped item" : undefined}
                      >
                        <span className="body-parts-eye">
                          {isAutoHidden ? "🎽" : isManualHidden ? "🚫" : "👁"}
                        </span>
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
            )}
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
          <div className="top-right-cluster">
            <ExportPanel characters={characters} animations={manifest} characterModel={characterModel} />
            <div
              className="npc-dropdown"
              title="NPCs use a separate Meshy-generated rig (no Mixamo prefix, no fingers). Each name comes in 4 skin/sex variants; equipment, body-part hiding, and Female/Male animations don't apply."
            >
              <button
                className={`model-toggle-btn npc-trigger${isNPC ? " active" : ""}`}
              >
                {(() => {
                  const active = NPCS.find((n) => n.id === activeGender);
                  if (!active) return `NPCs (${NPCS.length}) \u25BE`;
                  return active.displayName
                    ? `NPC: ${active.displayName}`
                    : `NPC: ${active.name} \u00B7 ${active.variant.abbrev}`;
                })()}
              </button>
              <div className="npc-menu npc-menu-grid">
                <div className="npc-menu-inner">
                  <div className="npc-menu-title">
                    NPCs &mdash; {NPC_NAMES.length} names &times; {NPC_VARIANTS.length} variants
                  </div>
                  <div className="npc-grid-header">
                    <span />
                    {NPC_VARIANTS.map((variant) => (
                      <span
                        key={variant.key}
                        className="npc-grid-h"
                        title={variant.label}
                      >
                        {variant.abbrev}
                      </span>
                    ))}
                  </div>
                  {NPC_NAMES.map((name) => (
                    <div key={name} className="npc-grid-row">
                      <span className="npc-grid-name">{name}</span>
                      {NPC_VARIANTS.map((variant) => {
                        const npc = NPCS.find(
                          (n) => n.name === name && n.variant.key === variant.key,
                        );
                        if (!npc) return <span key={variant.key} />;
                        const active = activeGender === npc.id;
                        return (
                          <button
                            key={variant.key}
                            className={`npc-chip${active ? " active" : ""}`}
                            onClick={() => setActiveGender(npc.id)}
                            title={
                              npc.displayName
                                ? `${npc.displayName} (${name} \u00B7 ${variant.label})`
                                : `${name} (${variant.label})`
                            }
                          >
                            {variant.abbrev}
                          </button>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
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
            {equipSpec && !isNPC && (
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
                skinTransferRequest={skinTransferRequest}
                onSkinTransferDone={handleSkinTransferDone}
              />
            )}
            {showSlotBounds && equipSpec && !isNPC && (
              <SlotBoundsVisualizer
                slots={equipSpec.slots.filter(
                  (s) => !BODY_SLOT_IDS.has(s.id) && slotMatchesGender(s.gender, activeGender),
                )}
              />
            )}
            {selectedTool && (
              <ToolAttachment
                key={selectedTool.id}
                tool={selectedTool}
                boneName={selectedTool.attachBone ?? DEFAULT_TOOL_ATTACH_BONE}
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
          animations={visibleAnimations}
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
        {!poseMode && equipSpec && !isNPC && (
          <EquipmentPanel
            slots={equipSpec.slots.filter(
              (s) => !BODY_SLOT_IDS.has(s.id) && slotMatchesGender(s.gender, activeGender),
            )}
            equipState={equipState}
            onToggleSlot={handleToggleSlot}
            selectedSlot={selectedEquipSlot}
            onSelectSlot={setSelectedEquipSlot}
            onImportEquipment={handleImportEquipment}
            equipTransforms={equipTransforms}
            slotTextures={slotTextures}
            onSetSlotTexture={handleSetSlotTexture}
            onForceAutoSkin={handleOpenSkinModal}
            onExportWeightedSlot={handleExportWeightedSlot}
            reweightedSlots={reweightedSlots}
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
        {skinTransferTarget && equipSpec && (
          <SkinTransferModal
            targetSlotId={skinTransferTarget}
            slots={equipSpec.slots.filter(
              (s) => !BODY_SLOT_IDS.has(s.id) && slotMatchesGender(s.gender, activeGender),
            )}
            equipState={equipState}
            onTransfer={handleSkinTransfer}
            onClose={() => setSkinTransferTarget(null)}
            isBusy={skinTransferRequest !== null}
          />
        )}
      </div>
    </div>
  );
}

const CATALOG_PAGES: Record<
  string,
  { title: string; category: ViewerCatalogCategory }
> = {
  [ROUTES.buildings]: { title: "Buildings", category: "buildings" },
  [ROUTES.workstations]: { title: "Workstations", category: "workstations" },
  [ROUTES.creatures]: { title: "Creatures", category: "creatures" },
};

export default function App() {
  const { path, navigate } = usePath();

  if (path === ROUTES.home) {
    return <CategoryHome navigate={navigate} />;
  }

  if (path === ROUTES.avatar) {
    return <CharacterViewer onHome={() => navigate(ROUTES.home)} />;
  }

  const catalog = CATALOG_PAGES[path];
  if (catalog) {
    return (
      <BuildingViewer
        key={catalog.category}
        title={catalog.title}
        buildings={buildingsInCategory(catalog.category)}
        onHome={() => navigate(ROUTES.home)}
      />
    );
  }

  return <CategoryHome navigate={navigate} />;
}

