import { useState, useMemo, useCallback } from "react";
import type { EquipmentSlot, EquipmentState } from "../types/equipment";

export interface SkinTransferRequest {
  targetSlotId: string;
  referenceSlotId: string;
}

interface SkinTransferModalProps {
  targetSlotId: string;
  slots: EquipmentSlot[];
  equipState: EquipmentState;
  onTransfer: (request: SkinTransferRequest) => void;
  onClose: () => void;
  isBusy?: boolean;
}

export default function SkinTransferModal({
  targetSlotId,
  slots,
  equipState,
  onTransfer,
  onClose,
  isBusy,
}: SkinTransferModalProps) {
  const [selectedRef, setSelectedRef] = useState<string | null>(null);

  const targetSlot = useMemo(
    () => slots.find((s) => s.id === targetSlotId) ?? null,
    [slots, targetSlotId],
  );

  const referenceSlots = useMemo(() => {
    return slots.filter(
      (s) => s.id !== targetSlotId && s.mesh_type === "external",
    );
  }, [slots, targetSlotId]);

  const grouped = useMemo(() => {
    const map = new Map<string, EquipmentSlot[]>();
    for (const s of referenceSlots) {
      const key = s.collection ?? "other";
      let list = map.get(key);
      if (!list) {
        list = [];
        map.set(key, list);
      }
      list.push(s);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [referenceSlots]);

  const handleTransfer = useCallback(() => {
    if (!selectedRef) return;
    onTransfer({ targetSlotId, referenceSlotId: selectedRef });
  }, [selectedRef, targetSlotId, onTransfer]);

  return (
    <div className="skin-transfer-overlay" onClick={onClose}>
      <div
        className="skin-transfer-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="skin-transfer-header">
          <h3>Skin Transfer</h3>
          <button className="skin-transfer-close" onClick={onClose}>
            &times;
          </button>
        </div>

        <div className="skin-transfer-target">
          <span className="skin-transfer-label">Target</span>
          <span className="skin-transfer-value">
            {targetSlot?.name ?? targetSlotId}
          </span>
        </div>

        <div className="skin-transfer-label">Copy weights &amp; scale from:</div>

        <div className="skin-transfer-list">
          {grouped.map(([collection, items]) => (
            <div key={collection} className="skin-transfer-group">
              <div className="skin-transfer-group-label">
                {collection.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </div>
              {items.map((s) => {
                const isSelected = selectedRef === s.id;
                const isActive = equipState[s.id];
                return (
                  <button
                    key={s.id}
                    className={`skin-transfer-item ${isSelected ? "selected" : ""} ${isActive ? "active" : ""}`}
                    onClick={() => setSelectedRef(s.id)}
                  >
                    <span
                      className="skin-transfer-dot"
                      style={{ background: s.color ?? "#94a3b8" }}
                    />
                    {s.name}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        <button
          className="skin-transfer-apply"
          disabled={!selectedRef || isBusy}
          onClick={handleTransfer}
        >
          {isBusy ? "Transferring…" : "Transfer Skin"}
        </button>
      </div>
    </div>
  );
}
