import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  ToolCategory,
  ToolCategoryInfo,
  ToolDefinition,
  ToolTransform,
  GizmoMode,
} from "../types/tools";
import { TOOL_CATEGORIES } from "../types/tools";

interface ToolPanelProps {
  tools: ToolDefinition[];
  selectedToolId: string | null;
  onSelectTool: (toolId: string | null) => void;
  transform: ToolTransform;
  gizmoMode: GizmoMode;
  onGizmoModeChange: (mode: GizmoMode) => void;
  onTransformChange: (t: ToolTransform) => void;
  onResetTransform: () => void;
  detached: boolean;
  onDetachedChange: (v: boolean) => void;
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

export default function ToolPanel({
  tools,
  selectedToolId,
  onSelectTool,
  transform,
  gizmoMode,
  onGizmoModeChange,
  onTransformChange,
  onResetTransform,
  detached,
  onDetachedChange,
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

  const activeTool = tools.find((t) => t.id === selectedToolId) ?? null;

  const categoryGroups = useMemo(() => {
    const map = new Map<ToolCategory, ToolDefinition[]>();
    for (const tool of tools) {
      const key: ToolCategory = tool.category ?? "other";
      let list = map.get(key);
      if (!list) {
        list = [];
        map.set(key, list);
      }
      list.push(tool);
    }
    const ordered: { info: ToolCategoryInfo; items: ToolDefinition[] }[] = [];
    for (const info of TOOL_CATEGORIES) {
      const items = map.get(info.key);
      if (items && items.length > 0) {
        ordered.push({ info, items });
        map.delete(info.key);
      }
    }
    for (const [key, items] of map) {
      if (items.length > 0) {
        ordered.push({
          info: {
            key,
            label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
            color: "#6b7280",
          },
          items,
        });
      }
    }
    return ordered;
  }, [tools]);

  const [collapsed, setCollapsed] = useState<Set<ToolCategory>>(() => new Set());

  const toggleCollapse = useCallback((key: ToolCategory) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const selectedCategory = activeTool?.category ?? null;
  useEffect(() => {
    if (!selectedCategory) return;
    setCollapsed((prev) => {
      if (!prev.has(selectedCategory)) return prev;
      const next = new Set(prev);
      next.delete(selectedCategory);
      return next;
    });
  }, [selectedCategory]);

  const [copied, setCopied] = useState(false);
  const handleCopyTransform = useCallback(() => {
    const lines = [
      `Tool: ${activeTool?.name ?? selectedToolId ?? "none"}`,
      `Position: [${transform.position.join(", ")}]`,
      `Rotation: [${transform.rotation.join(", ")}] deg`,
      `Scale: ${transform.scale}`,
      "",
      "JSON:",
      JSON.stringify({ position: transform.position, rotation: transform.rotation, scale: transform.scale }, null, 2),
    ];
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [transform, activeTool, selectedToolId]);

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
        {categoryGroups.map(({ info, items }) => {
          const isOpen = !collapsed.has(info.key);
          return (
            <div className="tool-category-group" key={info.key}>
              <div
                className="tool-category-header"
                onClick={() => toggleCollapse(info.key)}
              >
                <span
                  className="tool-category-dot"
                  style={{ background: info.color }}
                />
                <span className="tool-category-label">{info.label}</span>
                <span className="tool-category-count">({items.length})</span>
                <span
                  className={`tool-category-chevron ${isOpen ? "open" : ""}`}
                >
                  &#9654;
                </span>
              </div>
              {isOpen &&
                items.map((tool) => {
                  const active = selectedToolId === tool.id;
                  return (
                    <div key={tool.id} className="tool-row">
                      <button
                        type="button"
                        className={`tool-item ${active ? "active" : ""}`}
                        onClick={() => onSelectTool(active ? null : tool.id)}
                        title={active ? `Unequip ${tool.name}` : `Equip ${tool.name}`}
                      >
                        {tool.thumbnailUrl ? (
                          <img
                            className="tool-thumb"
                            src={tool.thumbnailUrl}
                            alt=""
                            draggable={false}
                          />
                        ) : (
                          <span
                            className="tool-dot"
                            style={{
                              background: active
                                ? tool.color
                                : "var(--bg-tertiary)",
                            }}
                          />
                        )}
                        <span className="tool-name">{tool.name}</span>
                        {active && (
                          <span className="tool-equipped-badge">Equipped</span>
                        )}
                      </button>
                      <a
                        className="tool-dl-btn"
                        href={tool.url}
                        download={`${tool.id}.glb`}
                        onClick={(e) => e.stopPropagation()}
                        title={`Download ${tool.name} GLB`}
                      >
                        GLB
                      </a>
                    </div>
                  );
                })}
            </div>
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

          <label className="tool-detach-toggle">
            <input
              type="checkbox"
              checked={detached}
              onChange={(e) => onDetachedChange(e.target.checked)}
            />
            <span>Detach from bone (preview raw position)</span>
          </label>

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
              <DraggableInput
                axis=""
                value={transform.scale}
                step={0.01}
                onChange={updateScale}
              />
            </div>
          </div>
          <button
            className="tool-copy-transform-btn"
            onClick={handleCopyTransform}
            title="Copy current transform as JSON to clipboard"
          >
            {copied ? "Copied!" : "Copy Transform"}
          </button>
        </div>
      )}
    </div>
  );
}
