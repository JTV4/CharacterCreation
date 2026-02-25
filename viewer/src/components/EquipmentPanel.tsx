import { useCallback, useState } from "react";
import type { EquipmentSlot, EquipmentState } from "../types/equipment";
import { SLOT_COLORS } from "../types/equipment";

const DEFAULT_COLOR = "#94a3b8";

interface EquipmentPanelProps {
  slots: EquipmentSlot[];
  equipState: EquipmentState;
  onToggleSlot: (slotId: string, enabled: boolean) => void;
}

type ExportFormat = "viewer" | "game";

function downloadSlot(slotId: string, format: ExportFormat) {
  const path = format === "game"
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
    setTimeout(() => downloadSlot(slot.id, format), enabled.indexOf(slot) * 200);
  }
}

export default function EquipmentPanel({
  slots,
  equipState,
  onToggleSlot,
}: EquipmentPanelProps) {
  const [exportFormat, setExportFormat] = useState<ExportFormat>("game");

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
        {slots.map((slot) => {
          const enabled = equipState[slot.id] ?? false;
          const blocker = isHiddenByRule(slot);
          const blocked = blocker !== null;
          const color = slot.color ?? SLOT_COLORS[slot.id] ?? DEFAULT_COLOR;

          return (
            <div
              key={slot.id}
              className={`equip-slot ${enabled && !blocked ? "active" : ""} ${blocked ? "blocked" : ""}`}
            >
              <label className="equip-toggle">
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
                <span className="equip-name">{slot.name}</span>
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
                className="equip-export-btn"
                onClick={() => downloadSlot(slot.id, exportFormat)}
                title={`Export ${slot.name} GLB (${exportFormat === "game" ? "Y-up" : "Z-up"})`}
              >
                GLB
              </button>
              <span className="equip-bone-count">
                {slot.bones.length} bones
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
