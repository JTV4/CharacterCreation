import { useCallback, useEffect, useRef, useState } from "react";
import type { EquipmentSlot, EquipTransform } from "../types/equipment";
import { DEFAULT_EQUIP_TRANSFORM, SLOT_COLORS } from "../types/equipment";
import type { GizmoMode } from "../types/tools";

interface MeshInfoPanelProps {
  slot: EquipmentSlot | null;
  transform: EquipTransform;
  gizmoMode: GizmoMode;
  onGizmoModeChange: (mode: GizmoMode) => void;
  onTransformChange: (t: EquipTransform) => void;
  onReset: () => void;
}

const DRAG_THRESHOLD = 3;

function DraggableInput({
  axis,
  value,
  step,
  onChange,
}: {
  axis: string;
  value: number;
  step: number;
  onChange: (v: number) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localText, setLocalText] = useState(String(value));
  const focused = useRef(false);

  useEffect(() => {
    if (!focused.current) {
      setLocalText(String(value));
    }
  }, [value]);

  const dragState = useRef<{
    startX: number;
    startValue: number;
    dragging: boolean;
    totalDx: number;
  } | null>(null);

  const sensitivity = step * 0.5;

  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      if (document.activeElement === inputRef.current) return;

      e.preventDefault();
      dragState.current = {
        startX: e.clientX,
        startValue: value,
        dragging: false,
        totalDx: 0,
      };

      const cleanup = () => {
        dragState.current = null;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        window.removeEventListener("pointermove", handleMove);
        window.removeEventListener("pointerup", handleUp);
        window.removeEventListener("keydown", handleKeyDown);
      };

      const handleMove = (ev: PointerEvent) => {
        const state = dragState.current;
        if (!state) return;

        if (!state.dragging) {
          if (Math.abs(ev.clientX - state.startX) > DRAG_THRESHOLD) {
            state.dragging = true;
            state.totalDx = ev.clientX - state.startX;
            document.body.style.cursor = "ew-resize";
            document.body.style.userSelect = "none";
          }
          return;
        }

        state.totalDx = ev.clientX - state.startX;
        const rawNext = state.startValue + state.totalDx * sensitivity;
        const rounded = Math.round(rawNext / step) * step;
        onChange(parseFloat(rounded.toFixed(6)));
      };

      const handleKeyDown = (ev: KeyboardEvent) => {
        if (ev.key === "Escape") {
          ev.preventDefault();
          const state = dragState.current;
          if (state?.dragging) {
            onChange(state.startValue);
          }
          cleanup();
        }
      };

      const handleUp = () => {
        const state = dragState.current;
        const wasDragging = state?.dragging ?? false;
        cleanup();

        if (!wasDragging && inputRef.current) {
          inputRef.current.focus();
          inputRef.current.select();
        }
      };

      window.addEventListener("pointermove", handleMove);
      window.addEventListener("pointerup", handleUp);
      window.addEventListener("keydown", handleKeyDown);
    },
    [value, step, sensitivity, onChange],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const text = e.target.value;
      setLocalText(text);
      const num = parseFloat(text);
      if (!isNaN(num)) {
        onChange(num);
      }
    },
    [onChange],
  );

  const handleFocus = useCallback(() => {
    focused.current = true;
  }, []);

  const handleBlur = useCallback(() => {
    focused.current = false;
    const num = parseFloat(localText);
    if (isNaN(num) || localText.trim() === "") {
      setLocalText(String(value));
    } else {
      setLocalText(String(num));
    }
  }, [localText, value]);

  return (
    <label className="override-input-wrap draggable-input-wrap">
      <span className="override-axis">{axis}</span>
      <input
        ref={inputRef}
        type="number"
        className="override-input"
        step={step}
        value={localText}
        onChange={handleInputChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onPointerDown={handlePointerDown}
      />
    </label>
  );
}

function Vec3Input({
  label,
  value,
  step,
  onChange,
}: {
  label: string;
  value: [number, number, number];
  step: number;
  onChange: (v: [number, number, number]) => void;
}) {
  const labels = ["X", "Y", "Z"];
  return (
    <div className="override-field">
      <span className="override-field-label">{label}</span>
      <div className="override-inputs">
        {labels.map((axis, i) => (
          <DraggableInput
            key={axis}
            axis={axis}
            value={value[i]}
            step={step}
            onChange={(v) => {
              const next: [number, number, number] = [...value];
              next[i] = v;
              onChange(next);
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default function MeshInfoPanel({
  slot,
  transform,
  gizmoMode,
  onGizmoModeChange,
  onTransformChange,
  onReset,
}: MeshInfoPanelProps) {
  const hasOffset =
    transform.position.some((v) => v !== 0) ||
    transform.rotation.some((v) => v !== 0) ||
    transform.scale !== 1;

  const handleCopyTransform = useCallback(() => {
    if (!slot) return;
    const fmt = (v: [number, number, number]) =>
      `[${v.map((n) => n.toFixed(4)).join(", ")}]`;
    const text = [
      `Equipment: ${slot.id}`,
      `Name: ${slot.name}`,
      `Position: ${fmt(transform.position)}`,
      `Rotation: ${fmt(transform.rotation)}`,
      `Scale: ${transform.scale.toFixed(4)}`,
    ].join("\n");
    navigator.clipboard.writeText(text);
  }, [slot, transform]);

  if (!slot) {
    return (
      <div className="info-panel">
        <h2>Mesh Inspector</h2>
        <p className="info-empty">Select a mesh to view its properties</p>
      </div>
    );
  }

  const color = slot.color ?? SLOT_COLORS[slot.id] ?? "#94a3b8";

  return (
    <div className="info-panel">
      <h2>Mesh Inspector</h2>

      <div className="info-section">
        <div className="info-section-title">Identity</div>
        <div className="info-row">
          <span className="info-label">Name</span>
          <span className="info-value">{slot.name}</span>
        </div>
        <div className="info-row">
          <span className="info-label">ID</span>
          <span className="info-value" style={{ fontSize: 11 }}>{slot.id}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Type</span>
          <span
            className="info-value category-badge"
            style={{ background: color + "30", color }}
          >
            {slot.mesh_type}
          </span>
        </div>
        <div className="info-row">
          <span className="info-label">Bilateral</span>
          <span className="info-value">{slot.bilateral ? "L+R" : "No"}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Bones</span>
          <span className="info-value">{slot.bones.length}</span>
        </div>
        {slot.gender && (
          <div className="info-row">
            <span className="info-label">Gender</span>
            <span className="info-value">{slot.gender}</span>
          </div>
        )}
      </div>

      <div className="info-section">
        <div className="info-section-title" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span>Transform</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="override-copy-btn" onClick={handleCopyTransform} title="Copy mesh transform to clipboard">
              Copy
            </button>
            {hasOffset && (
              <button className="override-reset-btn" onClick={onReset}>
                Reset
              </button>
            )}
          </div>
        </div>
        <div className="transform-toolbar">
          {(["translate", "rotate", "scale"] as const).map((m) => {
            const label = m === "translate" ? "T" : m === "rotate" ? "R" : "S";
            const title = m === "translate"
              ? "Translate (T) — drag gizmo to move"
              : m === "rotate"
                ? "Rotate (R) — drag gizmo to rotate"
                : "Scale (S) — drag gizmo to scale";
            const isActive = gizmoMode === m;
            return (
              <button
                key={m}
                className={`transform-toolbar-btn${isActive ? " active" : ""}`}
                title={title}
                onClick={() => onGizmoModeChange(m)}
                disabled={isActive}
              >
                {label}
                <span className="transform-toolbar-label">
                  {m === "translate" ? "Translate" : m === "rotate" ? "Rotate" : "Scale"}
                </span>
              </button>
            );
          })}
        </div>
        <Vec3Input
          label="Position"
          value={transform.position}
          step={0.01}
          onChange={(v) => onTransformChange({ ...transform, position: v })}
        />
        <Vec3Input
          label="Rotation"
          value={transform.rotation}
          step={1}
          onChange={(v) => onTransformChange({ ...transform, rotation: v })}
        />
        <div className="override-field">
          <span className="override-field-label">Scale</span>
          <div className="override-inputs">
            <DraggableInput
              axis=""
              value={transform.scale}
              step={0.01}
              onChange={(v) => onTransformChange({ ...transform, scale: v })}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
