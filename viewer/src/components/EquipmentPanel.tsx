import { useCallback, useEffect, useMemo, useState, useRef } from "react";
import SectionCollapse from "./SectionCollapse";
import type {
  EquipmentSlot,
  EquipmentState,
  EquipmentSlotType,
  EquipTransform,
  EquipBoneOffsetMap,
  SlotTextures,
} from "../types/equipment";
import { pruneOffsetMap } from "../utils/equipBoneFit";
import {
  SLOT_COLORS,
  EQUIPMENT_SLOT_TYPES,
  SLOT_TYPE_CONFIGS,
} from "../types/equipment";

const DEFAULT_COLOR = "#94a3b8";

const PRIMITIVE_IDS = new Set([
  "head", "amulet", "gloves", "ring", "upper_body", "lower_body", "boots",
]);

interface CollectionInfo {
  key: string;
  label: string;
  color: string;
}

const COLLECTION_ORDER: CollectionInfo[] = [
  {"key": "combat_ranged_1", "label": "Ranged \u00b7 Pathfinder", "color": "#8ea189"},
  {"key": "combat_ranged_2", "label": "Ranged \u00b7 Greenwarden", "color": "#8ea189"},
  {"key": "combat_ranged_3", "label": "Ranged \u00b7 Outrider", "color": "#8ea189"},
  {"key": "combat_ranged_4", "label": "Ranged \u00b7 Wild Sovereign", "color": "#8ea189"},
  {"key": "combat_mage_1", "label": "Mage \u00b7 Adept", "color": "#8ea189"},
  {"key": "combat_mage_2", "label": "Mage \u00b7 Spellweaver", "color": "#8ea189"},
  {"key": "combat_mage_3", "label": "Mage \u00b7 Moonkeeper", "color": "#8ea189"},
  {"key": "combat_mage_4", "label": "Mage \u00b7 Archon", "color": "#8ea189"},
  {"key": "combat_melee_1", "label": "Melee \u00b7 Vanguard", "color": "#8ea189"},
  {"key": "combat_melee_2", "label": "Melee \u00b7 Sentinel", "color": "#8ea189"},
  {"key": "combat_melee_3", "label": "Melee \u00b7 Campaigner", "color": "#8ea189"},
  {"key": "combat_melee_4", "label": "Melee \u00b7 High Marshal", "color": "#8ea189"},
  { key: "starter_clothes", label: "Starter Clothes", color: "#baa481" },
  { key: "iron_l1",              label: "Iron Armor · Level 1",  color: "#747a80" },
  { key: "steel_rework",         label: "Steel Armor · Rework", color: "#a2b8c4" },
  { key: "gold_rework",          label: "Gold Armor · Rework",  color: "#dfaf46" },
  { key: "titanium_rework",      label: "Titanium Armor · Rework", color: "#bb8178" },
  { key: "tungsten_rework", label: "Tungsten Armor · Rework", color: "#7935b4" },
  { key: "luminous_rework", label: "Luminous Armor · Rework", color: "#49b6ae" },
  { key: "thanksgiving_rework", label: "Thanksgiving Outfit", color: "#b86728" },
  { key: "santa_rework", label: "Santa Outfit", color: "#c01828" },
  { key: "pumpkin_rework",       label: "Pumpkin Outfit",       color: "#ed822d" },
  { key: "halloween_witch_rework", label: "Halloween Witch Hat", color: "#6e368f" },
  { key: "rework",               label: "Rework Clothes",       color: "#c4b5a0" },
  { key: "ranged_leather", label: "Leather Ranging Armor · Tier 1", color: "#895638" },
  { key: "ranged_green", label: "Green Ranged Armor · Tier 2", color: "#467a43" },
  { key: "ranged_blue", label: "Blue Ranged Armor · Tier 3", color: "#365fa3" },
  { key: "ranged_red", label: "Red Ranged Armor · Tier 4", color: "#a43b32" },
  { key: "ranged_black", label: "Black Ranged Armor · Tier 5", color: "#303139" },
  { key: "ranged_purple", label: "Purple Ranged Armor · Tier 6", color: "#794c99" },
  { key: "mage_leather", label: "Leather Mage · Level 1", color: "#795338" },
  { key: "mage_green", label: "Green Mage · Level 10", color: "#396c46" },
  { key: "mage_blue", label: "Blue Mage · Level 20", color: "#36548e" },
  { key: "mage_red", label: "Red Mage · Level 30", color: "#94382d" },
  { key: "mage_black", label: "Black Mage · Level 40", color: "#303038" },
  { key: "mage_luminous", label: "Luminous Mage · Level 50", color: "#7139aa" },
  { key: "ranger",               label: "Ranger Outfit",        color: "#6b8f4e" },
  { key: "base",                 label: "Base Meshes",          color: "#e8b4a0" },
  { key: "skin",                 label: "Skin Colors",          color: "#f0c8a0" },
  { key: "skin_textures_white",  label: "White",                color: "#f5f0e8" },
  { key: "face_accessories",     label: "Face Accessories",     color: "#60a5fa" },
  { key: "hair",                 label: "Hair",                 color: "#a16207" },
  { key: "textured_hair",        label: "Textured Hair",        color: "#d97706" },
  { key: "primitives",           label: "Primitives",           color: "#94a3b8" },
  { key: "crimson_wizard",       label: "Crimson Wizard",       color: "#b91c1c" },
  { key: "green_dragon_wizard",  label: "Green Dragon Wizard",  color: "#16a34a" },
  { key: "shell",                label: "Shell",                color: "#60a5fa" },
  { key: "shell_v1",             label: "Equipment Shell V1",   color: "#66bb6a" },
  { key: "shell_v2",             label: "Shells V2",            color: "#3b82f6" },
  { key: "robes",                label: "Robes",                color: "#9c27b0" },
  { key: "skirts",               label: "Skirts",               color: "#e91e63" },
  { key: "upperbody_armor",      label: "Upperbody Armor",      color: "#ff5722" },
  { key: "textured_shell_v2",   label: "Textured Shells V2",   color: "#8b5cf6" },
  { key: "green_ranged",         label: "Green Ranged Armor",   color: "#2e7d32" },
  { key: "purple_ranged",        label: "Purple Ranged Armor",  color: "#7b1fa2" },
  { key: "black_ranged",         label: "Black Ranged Armor",   color: "#212121" },
  { key: "red_ranged",           label: "Red Ranged Armor",     color: "#c62828" },
  { key: "blue_ranged",          label: "Blue Ranged Armor",    color: "#1565c0" },
  { key: "leather_ranged",       label: "Leather Armor",        color: "#8b4513" },
  { key: "iron_armor",           label: "Iron Armor",           color: "#9ca3af" },
  { key: "steel_armor",          label: "Steel Armor",          color: "#64748b" },
  { key: "gold_armor",           label: "Gold Armor",           color: "#f59e0b" },
  { key: "titanium_armor",       label: "Titanium Armor",       color: "#cbd5e1" },
  { key: "tungsten_armor",       label: "Tungsten Armor",       color: "#475569" },
  { key: "luminous_armor",       label: "Luminous Armor",       color: "#22d3ee" },
  { key: "leather_magic_armor",  label: "Leather Magic Armor",  color: "#a16207" },
  { key: "green_magic_armor",    label: "Green Magic Armor",    color: "#15803d" },
  { key: "blue_magic_armor",     label: "Blue Magic Armor",     color: "#1d4ed8" },
  { key: "red_magic_armor",      label: "Red Magic Armor",      color: "#b91c1c" },
  { key: "black_magic_armor",    label: "Black Magic Armor",    color: "#171717" },
  { key: "purple_magic_armor",   label: "Purple Magic Armor",   color: "#7e22ce" },
  { key: "default_armor",        label: "Default Armor",        color: "#a8a29e" },
  { key: "alpha_pass",           label: "Alpha Pass",           color: "#eab308" },
  { key: "meshy_input",          label: "Meshy Input (pre-texture)", color: "#f59e0b" },
  { key: "test",                 label: "Test",                 color: "#a78bfa" },
  { key: "custom",               label: "Custom",               color: "#f59e0b" },
  { key: "other",                label: "Other",                color: "#6b7280" },
  { key: "imported",             label: "Imported",             color: "#10b981" },
];

function deriveCollection(slot: EquipmentSlot): string {
  if (slot.category === "alpha_pass") return "alpha_pass";
  if (slot.collection) return slot.collection;
  if (slot.source === "imported") return "imported";
  if (slot.category === "meshes") return "base";
  if (slot.category === "skin_textures") return "skin";
  if (slot.category === "skin_textures_white") return "skin_textures_white";
  if (
    slot.category === "eyes" ||
    slot.category === "eyebrows" ||
    slot.category === "eyelashes" ||
    slot.category === "nose" ||
    slot.category === "mouth" ||
    slot.category === "ears"
  ) {
    return "face_accessories";
  }
  if (slot.category === "hair") return "hair";
  if (slot.category === "textured_hair") return "textured_hair";
  if (slot.category === "robes") return "robes";
  if (slot.category === "skirts") return "skirts";
  if (slot.category === "upperbody_armor") return "upperbody_armor";
  if (slot.category === "textured_shell_v2") return "textured_shell_v2";
  if (slot.category === "green_ranged_armor") return "green_ranged";
  if (slot.category === "purple_ranged_armor") return "purple_ranged";
  if (slot.category === "black_ranged_armor") return "black_ranged";
  if (slot.category === "red_ranged_armor") return "red_ranged";
  if (slot.category === "blue_ranged_armor") return "blue_ranged";
  if (slot.category === "leather_ranged_armor") return "leather_ranged";
  if (slot.category === "iron_armor") return "iron_armor";
  if (slot.category === "steel_armor") return "steel_armor";
  if (slot.category === "gold_armor") return "gold_armor";
  if (slot.category === "titanium_armor") return "titanium_armor";
  if (slot.category === "tungsten_armor") return "tungsten_armor";
  if (slot.category === "luminous_armor") return "luminous_armor";
  if (slot.category === "leather_magic_armor") return "leather_magic_armor";
  if (slot.category === "green_magic_armor") return "green_magic_armor";
  if (slot.category === "blue_magic_armor") return "blue_magic_armor";
  if (slot.category === "red_magic_armor") return "red_magic_armor";
  if (slot.category === "black_magic_armor") return "black_magic_armor";
  if (slot.category === "purple_magic_armor") return "purple_magic_armor";
  if (slot.category === "default_armor") return "default_armor";
  if (slot.category === "alpha_pass") return "alpha_pass";
  if (slot.category === "meshy_input") return "meshy_input";

  const id = slot.id;
  if (PRIMITIVE_IDS.has(id)) return "primitives";
  if (id.includes("green_dragon")) return "green_dragon_wizard";
  if (id.includes("crimson")) return "crimson_wizard";
  if (id.startsWith("shell_v1_")) return "shell_v1";
  if (id.startsWith("shell_v2_")) return "shell_v2";
  if (id.startsWith("shell_") && !id.includes("test")) return "shell";
  if (id.includes("test_v")) return "test";
  if (id.startsWith("custom_")) return "custom";
  return "other";
}

interface EquipmentPanelProps {
  slots: EquipmentSlot[];
  equipState: EquipmentState;
  onToggleSlot: (slotId: string, enabled: boolean) => void;
  selectedSlot: string | null;
  onSelectSlot: (id: string | null) => void;
  onImportEquipment: (slotType: EquipmentSlotType, name: string, url: string) => void;
  equipTransforms: Record<string, EquipTransform>;
  equipBoneOffsets?: Record<string, EquipBoneOffsetMap>;
  slotTextures: SlotTextures;
  onSetSlotTexture: (slotId: string, dataUrl: string | null) => void;
  onForceAutoSkin?: (slotId: string) => void;
  onExportWeightedSlot?: (slotId: string) => void;
  reweightedSlots?: Set<string>;
}

type ExportFormat = "viewer" | "game";

function downloadSlot(slotId: string, format: ExportFormat, slotUrl?: string) {
  const path = slotUrl
    ? slotUrl
    : format === "game"
      ? `/equipment/game/${slotId}.glb`
      : `/equipment/${slotId}.glb`;
  const a = document.createElement("a");
  a.href = path;
  a.download = `${slotId}.glb`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function downloadAllEnabled(
  slots: EquipmentSlot[],
  equipState: EquipmentState,
  format: ExportFormat,
) {
  const enabled = slots.filter((s) => equipState[s.id]);
  for (const slot of enabled) {
    setTimeout(() => downloadSlot(slot.id, format, slot.url), enabled.indexOf(slot) * 200);
  }
}

function buildSpecEntry(
  slot: EquipmentSlot,
  transform: EquipTransform | undefined,
  boneOffsets?: EquipBoneOffsetMap,
): string {
  const entry: Record<string, unknown> = {
    id: slot.id,
    name: slot.name,
    bilateral: slot.bilateral,
    color: slot.color,
    bones: slot.bones,
    bounds: slot.bounds,
    rules: slot.rules,
    hides_body_regions: slot.hides_body_regions,
    mesh_type: slot.mesh_type,
    mesh_params: slot.mesh_params,
  };
  if (slot.url) entry.url = slot.url;
  if (slot.gender) entry.gender = slot.gender;
  if (slot.collection) entry.collection = slot.collection;
  if (slot.wear_slot) entry.wear_slot = slot.wear_slot;
  if (slot.hair_fit) entry.hair_fit = slot.hair_fit;
  if (slot.hides_hair !== undefined) entry.hides_hair = slot.hides_hair;
  if (transform) entry.transform = transform;
  if (boneOffsets && Object.keys(boneOffsets).length > 0) {
    entry.default_bone_offsets = pruneOffsetMap(boneOffsets);
  }
  return JSON.stringify(entry, null, 2);
}

function ImportSection({
  onImport,
}: {
  onImport: (slotType: EquipmentSlotType, name: string, url: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [slotType, setSlotType] = useState<EquipmentSlotType>("upper_body");
  const [name, setName] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [importMode, setImportMode] = useState<"url" | "file">("url");
  const fileRef = useRef<HTMLInputElement>(null);
  const [fileUrl, setFileUrl] = useState<string | null>(null);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const objectUrl = URL.createObjectURL(file);
    setFileUrl(objectUrl);
    if (!name) setName(file.name.replace(/\.glb$/i, "").replace(/[_-]/g, " "));
  }, [name]);

  const handleImport = useCallback(() => {
    const resolvedUrl = importMode === "url" ? urlInput.trim() : fileUrl;
    if (!resolvedUrl || !name.trim()) return;
    onImport(slotType, name.trim(), resolvedUrl);
    setName("");
    setUrlInput("");
    setFileUrl(null);
    if (fileRef.current) fileRef.current.value = "";
    setExpanded(false);
  }, [slotType, name, urlInput, fileUrl, importMode, onImport]);

  const canImport = name.trim() && (importMode === "url" ? urlInput.trim() : fileUrl);

  if (!expanded) {
    return (
      <button className="equip-import-toggle" onClick={() => setExpanded(true)}>
        + Import Equipment
      </button>
    );
  }

  return (
    <div className="equip-import-section">
      <div className="equip-import-header">
        <span>Import Equipment</span>
        <button className="equip-import-close" onClick={() => setExpanded(false)}>
          &times;
        </button>
      </div>

      <div className="equip-import-row">
        <label>Slot Type</label>
        <select
          value={slotType}
          onChange={(e) => setSlotType(e.target.value as EquipmentSlotType)}
        >
          {EQUIPMENT_SLOT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
            </option>
          ))}
        </select>
      </div>

      <div className="equip-import-row">
        <label>Name</label>
        <input
          type="text"
          placeholder="e.g. Mystic Helmet"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="equip-import-row">
        <label>Source</label>
        <div className="equip-import-mode">
          <button
            className={`equip-format-btn ${importMode === "url" ? "active" : ""}`}
            onClick={() => setImportMode("url")}
          >
            URL
          </button>
          <button
            className={`equip-format-btn ${importMode === "file" ? "active" : ""}`}
            onClick={() => setImportMode("file")}
          >
            File
          </button>
        </div>
      </div>

      {importMode === "url" ? (
        <div className="equip-import-row">
          <label>URL</label>
          <input
            type="text"
            placeholder="https://... .glb"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
          />
        </div>
      ) : (
        <div className="equip-import-row">
          <label>GLB File</label>
          <input
            ref={fileRef}
            type="file"
            accept=".glb"
            onChange={handleFileChange}
          />
        </div>
      )}

      <button
        className="equip-import-btn"
        disabled={!canImport}
        onClick={handleImport}
      >
        Import
      </button>
    </div>
  );
}

export default function EquipmentPanel({
  slots,
  equipState,
  onToggleSlot,
  selectedSlot,
  onSelectSlot,
  onImportEquipment,
  equipTransforms,
  equipBoneOffsets,
  slotTextures,
  onSetSlotTexture,
  onForceAutoSkin,
  onExportWeightedSlot,
  reweightedSlots,
}: EquipmentPanelProps) {
  const [exportFormat, setExportFormat] = useState<ExportFormat>("game");
  const [copiedSlot, setCopiedSlot] = useState<string | null>(null);
  const textureInputRef = useRef<HTMLInputElement>(null);
  const [textureTargetSlot, setTextureTargetSlot] = useState<string | null>(null);
  const [sectionOpen, setSectionOpen] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    if (!selectedSlot) return;
    const slot = slots.find((s) => s.id === selectedSlot);
    if (!slot) return;
    const key = deriveCollection(slot);
    setExpanded((prev) => {
      if (prev.has(key)) return prev;
      const next = new Set(prev);
      next.add(key);
      return next;
    });
  }, [selectedSlot, slots]);

  const toggleCollapse = useCallback((key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const handleTextureClick = useCallback((slotId: string) => {
    setTextureTargetSlot(slotId);
    if (textureInputRef.current) {
      textureInputRef.current.value = "";
      textureInputRef.current.click();
    }
  }, []);

  const handleTextureFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !textureTargetSlot) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        onSetSlotTexture(textureTargetSlot, reader.result);
      }
    };
    reader.readAsDataURL(file);
  }, [textureTargetSlot, onSetSlotTexture]);

  const isHiddenByRule = useCallback(
    (slot: EquipmentSlot): string | null => {
      const hiddenBy = slot.rules?.hidden_by ?? [];
      for (const blockerId of hiddenBy) {
        if (equipState[blockerId]) return blockerId;
      }
      return null;
    },
    [equipState],
  );

  const anyEnabled = slots.some((s) => equipState[s.id]);

  const collectionGroups = useMemo(() => {
    const map = new Map<string, EquipmentSlot[]>();
    for (const slot of slots) {
      const key = deriveCollection(slot);
      let list = map.get(key);
      if (!list) { list = []; map.set(key, list); }
      list.push(slot);
    }
    const ordered: { info: CollectionInfo; items: EquipmentSlot[] }[] = [];
    for (const info of COLLECTION_ORDER) {
      const items = map.get(info.key);
      if (items && items.length > 0) ordered.push({ info, items });
      map.delete(info.key);
    }
    for (const [key, items] of map) {
      if (items.length > 0) {
        ordered.push({
          info: { key, label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()), color: "#6b7280" },
          items,
        });
      }
    }
    return ordered;
  }, [slots]);

  const handleCopySpec = useCallback(
    (slot: EquipmentSlot) => {
      const transform = equipTransforms[slot.id];
      const json = buildSpecEntry(slot, transform, equipBoneOffsets?.[slot.id]);
      navigator.clipboard.writeText(json).then(() => {
        setCopiedSlot(slot.id);
        setTimeout(() => setCopiedSlot(null), 2000);
      });
    },
    [equipTransforms, equipBoneOffsets],
  );

  const renderSlotRow = (slot: EquipmentSlot) => {
    const enabled = equipState[slot.id] ?? false;
    const blocker = isHiddenByRule(slot);
    const blocked = blocker !== null;
    const color = slot.color ?? SLOT_COLORS[slot.id] ?? DEFAULT_COLOR;
    const isSelected = selectedSlot === slot.id;
    const isImported = slot.source === "imported";

    return (
      <div
        key={slot.id}
        className={`equip-slot ${enabled && !blocked ? "active" : ""} ${blocked ? "blocked" : ""} ${isSelected ? "equip-selected" : ""}`}
        onClick={() => {
          if (blocked) return;
          if (!enabled) {
            // Not equipped → equip and select
            onToggleSlot(slot.id, true);
            onSelectSlot(slot.id);
          } else if (isSelected) {
            // Equipped and already selected → clicking again unequips
            onToggleSlot(slot.id, false);
            onSelectSlot(null);
          } else {
            // Equipped but not selected → select it
            onSelectSlot(slot.id);
          }
        }}
        style={{ cursor: blocked ? "default" : "pointer" }}
      >
        <label className="equip-toggle" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={enabled && !blocked}
            disabled={blocked}
            onChange={(e) => {
              onToggleSlot(slot.id, e.target.checked);
              if (e.target.checked) onSelectSlot(slot.id);
              else if (isSelected) onSelectSlot(null);
            }}
          />
          <span
            className="equip-dot"
            style={{ background: enabled && !blocked ? color : "var(--bg-tertiary)" }}
          />
          <span className="equip-name" title={slot.name}>{slot.name}</span>
        </label>
        {slot.bilateral && (
          <span className="equip-badge bilateral">L+R</span>
        )}
        {blocked && (
          <span className="equip-badge hidden-badge">
            hidden by {blocker}
          </span>
        )}
        <button
          className="equip-copy-spec-btn"
          onClick={(e) => {
            e.stopPropagation();
            handleCopySpec(slot);
          }}
          title="Copy equipment_spec.json entry to clipboard"
        >
          {copiedSlot === slot.id ? "Copied!" : "Spec"}
        </button>
        {!isImported && (
          <button
            className="equip-export-btn"
            onClick={(e) => {
              e.stopPropagation();
              downloadSlot(slot.id, exportFormat, slot.url);
            }}
            title={`Download ${slot.name} GLB`}
          >
            GLB
          </button>
        )}
        {enabled && !blocked && !isImported && onExportWeightedSlot && (
          <button
            className={`equip-export-weighted-btn${reweightedSlots?.has(slot.id) ? " reweighted" : ""}`}
            onClick={(e) => {
              e.stopPropagation();
              onExportWeightedSlot(slot.id);
            }}
            title={
              reweightedSlots?.has(slot.id)
                ? `Download re-weighted GLB for ${slot.name} (skin transfer applied)`
                : `Download current in-memory GLB for ${slot.name}`
            }
          >
            ↓ W
          </button>
        )}
        {slotTextures[slot.id] ? (
          <button
            className="equip-texture-btn has-texture"
            onClick={(e) => {
              e.stopPropagation();
              onSetSlotTexture(slot.id, null);
            }}
            title="Remove texture"
          >
            Tex &times;
          </button>
        ) : (
          <button
            className="equip-texture-btn"
            onClick={(e) => {
              e.stopPropagation();
              handleTextureClick(slot.id);
            }}
            title="Upload texture image"
          >
            Tex
          </button>
        )}
        {enabled && !blocked && onForceAutoSkin && (
          <button
            className="equip-autoskin-btn"
            onClick={(e) => {
              e.stopPropagation();
              onForceAutoSkin(slot.id);
            }}
            title="Force auto-skin this mesh to the character skeleton"
          >
            Skin
          </button>
        )}
        <span className="equip-bone-count">
          {slot.bones.length} bones
        </span>
      </div>
    );
  };

  return (
    <div className="info-panel equip-panel">
      <div className="equip-header">
        <SectionCollapse title="Equipment" open={sectionOpen} onToggle={() => setSectionOpen((v) => !v)} />
        {anyEnabled && (
          <button
            className="equip-export-all-btn"
            onClick={() => downloadAllEnabled(slots, equipState, exportFormat)}
            title="Export all enabled equipment as GLB"
          >
            Export All
          </button>
        )}
      </div>

      {sectionOpen && <>
      <ImportSection onImport={onImportEquipment} />

      <input
        ref={textureInputRef}
        type="file"
        accept="image/*"
        style={{ display: "none" }}
        onChange={handleTextureFileChange}
      />

      <div className="equip-format-row">
        <span className="equip-format-label">Export format:</span>
        <button
          className={`equip-format-btn ${exportFormat === "game" ? "active" : ""}`}
          onClick={() => setExportFormat("game")}
          title="Y-up (glTF standard) — compatible with most game engines"
        >
          Game (Y-up)
        </button>
        <button
          className={`equip-format-btn ${exportFormat === "viewer" ? "active" : ""}`}
          onClick={() => setExportFormat("viewer")}
          title="Z-up (Blender convention) — matches this viewer's coordinate system"
        >
          Viewer (Z-up)
        </button>
      </div>

      <div className="equip-slots">
        {collectionGroups.map(({ info, items }) => {
          const isOpen = expanded.has(info.key);
          return (
            <div className="equip-collection-group" key={info.key}>
              <div
                className="equip-collection-header"
                onClick={() => toggleCollapse(info.key)}
              >
                <span
                  className="equip-collection-dot"
                  style={{ background: info.color }}
                />
                <span className="equip-collection-label">{info.label}</span>
                <span className="equip-collection-count">({items.length})</span>
                <span className={`equip-collection-chevron ${isOpen ? "open" : ""}`}>
                  &#9654;
                </span>
              </div>
              {isOpen && items.map(renderSlotRow)}
            </div>
          );
        })}
      </div>
      </>}
    </div>
  );
}
