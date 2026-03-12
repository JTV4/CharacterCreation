import { useCallback, useMemo, useState, useRef } from "react";
import type {
  EquipmentSlot,
  EquipmentState,
  EquipmentSlotType,
  EquipTransform,
  SlotTextures,
} from "../types/equipment";
import {
  SLOT_COLORS,
  EQUIPMENT_SLOT_TYPES,
  SLOT_TYPE_CONFIGS,
} from "../types/equipment";

const DEFAULT_COLOR = "#94a3b8";

interface EquipmentPanelProps {
  slots: EquipmentSlot[];
  equipState: EquipmentState;
  onToggleSlot: (slotId: string, enabled: boolean) => void;
  selectedSlot: string | null;
  onSelectSlot: (id: string | null) => void;
  onImportEquipment: (slotType: EquipmentSlotType, name: string, url: string) => void;
  equipTransforms: Record<string, EquipTransform>;
  slotTextures: SlotTextures;
  onSetSlotTexture: (slotId: string, dataUrl: string | null) => void;
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

function buildSpecEntry(slot: EquipmentSlot, transform: EquipTransform | undefined): string {
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
  if (transform) entry.transform = transform;
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
  slotTextures,
  onSetSlotTexture,
}: EquipmentPanelProps) {
  const [exportFormat, setExportFormat] = useState<ExportFormat>("game");
  const [copiedSlot, setCopiedSlot] = useState<string | null>(null);
  const textureInputRef = useRef<HTMLInputElement>(null);
  const [textureTargetSlot, setTextureTargetSlot] = useState<string | null>(null);

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

  const slotsByCategory = useMemo(() => {
    const meshes: EquipmentSlot[] = [];
    const equipment: EquipmentSlot[] = [];
    const imported: EquipmentSlot[] = [];
    for (const slot of slots) {
      if (slot.source === "imported") {
        imported.push(slot);
      } else if (slot.category === "meshes") {
        meshes.push(slot);
      } else {
        equipment.push(slot);
      }
    }
    return { meshes, equipment, imported };
  }, [slots]);

  const handleCopySpec = useCallback(
    (slot: EquipmentSlot) => {
      const transform = equipTransforms[slot.id];
      const json = buildSpecEntry(slot, transform);
      navigator.clipboard.writeText(json).then(() => {
        setCopiedSlot(slot.id);
        setTimeout(() => setCopiedSlot(null), 2000);
      });
    },
    [equipTransforms],
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
          if (enabled && !blocked) {
            onSelectSlot(isSelected ? null : slot.id);
          }
        }}
        style={{ cursor: enabled && !blocked ? "pointer" : undefined }}
      >
        <label className="equip-toggle" onClick={(e) => e.stopPropagation()}>
          <input
            type="checkbox"
            checked={enabled && !blocked}
            disabled={blocked}
            onChange={(e) => onToggleSlot(slot.id, e.target.checked)}
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
        {isImported && (
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
        )}
        {!isImported && (
          <button
            className="equip-export-btn"
            onClick={(e) => {
              e.stopPropagation();
              downloadSlot(slot.id, exportFormat, slot.url);
            }}
            title={`Download ${slot.name} GLB (rigged)`}
          >
            GLB
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
        <span className="equip-bone-count">
          {slot.bones.length} bones
        </span>
      </div>
    );
  };

  return (
    <div className="info-panel equip-panel">
      <div className="equip-header">
        <h2>Equipment</h2>
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
        {slotsByCategory.imported.length > 0 && (
          <>
            <div className="equip-category-label">Imported</div>
            {slotsByCategory.imported.map(renderSlotRow)}
          </>
        )}
        {slotsByCategory.meshes.length > 0 && (
          <>
            <div className="equip-category-label">Meshes</div>
            {slotsByCategory.meshes.map(renderSlotRow)}
          </>
        )}
        {slotsByCategory.equipment.length > 0 && (
          <>
            <div className="equip-category-label">Equipment</div>
            {slotsByCategory.equipment.map(renderSlotRow)}
          </>
        )}
      </div>
    </div>
  );
}
