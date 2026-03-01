import { useCallback } from "react";
import type { ToolDefinition, ToolTransform, GizmoMode } from "../types/tools";

interface ToolPanelProps {
  tools: ToolDefinition[];
  selectedToolId: string | null;
  onSelectTool: (toolId: string | null) => void;
  transform: ToolTransform;
  gizmoMode: GizmoMode;
  onGizmoModeChange: (mode: GizmoMode) => void;
  onTransformChange: (t: ToolTransform) => void;
  onResetTransform: () => void;
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
          <label key={axis} className="override-input-wrap">
            <span className="override-axis">{axis}</span>
            <input
              type="number"
              className="override-input"
              step={step}
              value={value[i]}
              onChange={(e) => {
                const next: [number, number, number] = [...value];
                next[i] = parseFloat(e.target.value) || 0;
                onChange(next);
              }}
            />
          </label>
        ))}
      </div>
    </div>
  );
}

export default function ToolPanel({
  tools,
  selectedToolId,
  onSelectTool,
  transform,
  gizmoMode,
  onGizmoModeChange,
  onTransformChange,
  onResetTransform,
}: ToolPanelProps) {
  const updatePosition = useCallback(
    (v: [number, number, number]) =>
      onTransformChange({ ...transform, position: v }),
    [transform, onTransformChange],
  );
  const updateRotation = useCallback(
    (v: [number, number, number]) =>
      onTransformChange({ ...transform, rotation: v }),
    [transform, onTransformChange],
  );
  const updateScale = useCallback(
    (s: number) => onTransformChange({ ...transform, scale: s }),
    [transform, onTransformChange],
  );

  const hasOffset =
    transform.position.some((v) => v !== 0) ||
    transform.rotation.some((v) => v !== 0) ||
    transform.scale !== 1;

  return (
    <div className="info-panel tool-panel">
      <div className="tool-header">
        <h2>Tools</h2>
        {selectedToolId && (
          <button
            className="tool-unequip-btn"
            onClick={() => onSelectTool(null)}
          >
            Unequip
          </button>
        )}
      </div>
      <div className="tool-list">
        {tools.map((tool) => {
          const active = selectedToolId === tool.id;
          return (
            <button
              key={tool.id}
              className={`tool-item ${active ? "active" : ""}`}
              onClick={() => onSelectTool(active ? null : tool.id)}
            >
              <span
                className="tool-dot"
                style={{
                  background: active ? tool.color : "var(--bg-tertiary)",
                }}
              />
              <span className="tool-name">{tool.name}</span>
              {active && (
                <span className="tool-equipped-badge">Equipped</span>
              )}
            </button>
          );
        })}
      </div>

      {selectedToolId && (
        <div className="tool-transform-section">
          <div className="tool-transform-header">
            <span className="tool-section-title">Transform</span>
            <div className="tool-gizmo-modes">
              {(["translate", "rotate", "scale"] as const).map((mode) => (
                <button
                  key={mode}
                  className={`tool-mode-btn ${gizmoMode === mode ? "active" : ""}`}
                  onClick={() => onGizmoModeChange(mode)}
                  title={
                    mode === "translate"
                      ? "Move (T)"
                      : mode === "rotate"
                        ? "Rotate (R)"
                        : "Scale (S)"
                  }
                >
                  {mode[0].toUpperCase()}
                </button>
              ))}
            </div>
            {hasOffset && (
              <button className="override-reset-btn" onClick={onResetTransform}>
                Reset
              </button>
            )}
          </div>

          <Vec3Input
            label="Position"
            value={transform.position}
            step={0.01}
            onChange={updatePosition}
          />
          <Vec3Input
            label="Rotation (°)"
            value={transform.rotation}
            step={1}
            onChange={updateRotation}
          />
          <div className="override-field">
            <span className="override-field-label">Scale</span>
            <div className="override-inputs">
              <label className="override-input-wrap" style={{ maxWidth: "33%" }}>
                <input
                  type="number"
                  className="override-input"
                  step={0.01}
                  value={transform.scale}
                  onChange={(e) =>
                    updateScale(parseFloat(e.target.value) || 1)
                  }
                />
              </label>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
