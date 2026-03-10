import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import type { GlbBoneInfo, BoneCategory, BoneTransformOverride } from "../types";
import { CATEGORY_COLORS } from "../types";
import type { AnimationPlayerState } from "../hooks/useAnimationPlayer";

const RAD2DEG = 180 / Math.PI;

type TransformMode = "position" | "rotate" | "scale" | null;

interface BoneInfoPanelProps {
  bone: GlbBoneInfo | null;
  boneList: GlbBoneInfo[];
  boneOverrides: Map<string, BoneTransformOverride>;
  onSetBoneOverride: (boneName: string, override: BoneTransformOverride | null) => void;
  playerRef: React.MutableRefObject<AnimationPlayerState | null>;
  transformMode: TransformMode;
  onEnterMode: (mode: "position" | "rotate" | "scale") => void;
}

const DEFAULT_OVERRIDE: BoneTransformOverride = {
  position: [0, 0, 0],
  rotation: [0, 0, 0],
  scale: [1, 1, 1],
};

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

function computeBoneDeltaFromRest(
  boneName: string,
  playerRef: React.MutableRefObject<AnimationPlayerState | null>,
): BoneTransformOverride | null {
  const player = playerRef.current;
  if (!player) return null;
  const obj = player.boneObjMap.get(boneName);
  const rest = player.boneRestPose.get(boneName);
  if (!obj || !rest) return null;

  const deltaPos: [number, number, number] = [
    obj.position.x - rest.position.x,
    obj.position.y - rest.position.y,
    obj.position.z - rest.position.z,
  ];

  const invRest = rest.quaternion.clone().invert();
  const deltaQuat = invRest.multiply(obj.quaternion.clone());
  const euler = new THREE.Euler().setFromQuaternion(deltaQuat, "XYZ");
  const deltaRot: [number, number, number] = [
    parseFloat((euler.x * RAD2DEG).toFixed(3)),
    parseFloat((euler.y * RAD2DEG).toFixed(3)),
    parseFloat((euler.z * RAD2DEG).toFixed(3)),
  ];

  const deltaScale: [number, number, number] = [
    parseFloat(obj.scale.x.toFixed(3)),
    parseFloat(obj.scale.y.toFixed(3)),
    parseFloat(obj.scale.z.toFixed(3)),
  ];

  return { position: deltaPos, rotation: deltaRot, scale: deltaScale };
}

function getAncestorChain(boneName: string, boneList: GlbBoneInfo[]): string[] {
  const boneMap = new Map(boneList.map((b) => [b.name, b]));
  const chain: string[] = [];
  let current: string | null = boneName;
  while (current) {
    chain.unshift(current);
    const b = boneMap.get(current);
    current = b?.parent ?? null;
  }
  return chain;
}

export default function BoneInfoPanel({
  bone,
  boneList,
  boneOverrides,
  onSetBoneOverride,
  playerRef,
  transformMode,
  onEnterMode,
}: BoneInfoPanelProps) {
  const [livePose, setLivePose] = useState<BoneTransformOverride>(DEFAULT_OVERRIDE);

  useEffect(() => {
    if (!bone) return;
    const poll = () => {
      const delta = computeBoneDeltaFromRest(bone.name, playerRef);
      if (delta) setLivePose(delta);
    };
    poll();
    const id = setInterval(poll, 66);
    return () => clearInterval(id);
  }, [bone, playerRef]);

  const hasOverride = bone ? boneOverrides.has(bone.name) : false;
  const displayValues = bone && hasOverride
    ? boneOverrides.get(bone.name)!
    : livePose;

  const updateField = useCallback(
    (field: keyof BoneTransformOverride, value: [number, number, number]) => {
      if (!bone) return;
      let current = boneOverrides.get(bone.name);
      if (!current) {
        const delta = computeBoneDeltaFromRest(bone.name, playerRef);
        current = delta ?? { ...DEFAULT_OVERRIDE };
      }
      onSetBoneOverride(bone.name, { ...current, [field]: value });
    },
    [bone, boneOverrides, onSetBoneOverride, playerRef],
  );

  const handleReset = useCallback(() => {
    if (!bone) return;
    onSetBoneOverride(bone.name, null);
  }, [bone, onSetBoneOverride]);

  const handleCopyTransform = useCallback(() => {
    if (!bone) return;
    const fmt = (v: [number, number, number]) => `[${v.map((n) => n.toFixed(3)).join(", ")}]`;
    const text = [
      `Bone: ${bone.name}`,
      `Position: ${fmt(displayValues.position)}`,
      `Rotation: ${fmt(displayValues.rotation)}`,
      `Scale: ${fmt(displayValues.scale)}`,
    ].join("\n");
    navigator.clipboard.writeText(text);
  }, [bone, displayValues]);

  if (!bone) {
    return (
      <div className="info-panel">
        <h2>Bone Inspector</h2>
        <p className="info-empty">Select a bone to view its properties</p>
      </div>
    );
  }

  const catColor = CATEGORY_COLORS[bone.category as BoneCategory] ?? "#94a3b8";

  return (
    <div className="info-panel">
      <h2>Bone Inspector</h2>

      <div className="info-section">
        <div className="info-section-title">Identity</div>
        <div className="info-row">
          <span className="info-label">Name</span>
          <span className="info-value">{bone.name}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Parent</span>
          <span className="info-value">{bone.parent ?? "none"}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Side</span>
          <span className="info-value">{bone.side}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Category</span>
          <span
            className="info-value category-badge"
            style={{ background: catColor + "30", color: catColor }}
          >
            {bone.category}
          </span>
        </div>
      </div>

      <div className="info-section">
        <div className="info-section-title" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span>Transform Overrides</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="override-copy-btn" onClick={handleCopyTransform} title="Copy bone transform to clipboard">
              Copy
            </button>
            {hasOverride && (
              <button className="override-reset-btn" onClick={handleReset}>
                Reset
              </button>
            )}
          </div>
        </div>
        <div className="transform-toolbar">
          {(["position", "rotate", "scale"] as const).map((m) => {
            const label = m === "position" ? "P" : m === "rotate" ? "R" : "S";
            const title = m === "position"
              ? "Position (P) — drag mouse to move"
              : m === "rotate"
                ? "Rotate (R) — drag mouse to rotate"
                : "Scale (S) — drag mouse to scale";
            const isActive = transformMode === m;
            return (
              <button
                key={m}
                className={`transform-toolbar-btn${isActive ? " active" : ""}`}
                title={title}
                onClick={() => onEnterMode(m)}
                disabled={isActive}
              >
                {label}
                <span className="transform-toolbar-label">
                  {m === "position" ? "Position" : m === "rotate" ? "Rotate" : "Scale"}
                </span>
              </button>
            );
          })}
        </div>
        <Vec3Input
          label="Position"
          value={displayValues.position}
          step={0.01}
          onChange={(v) => updateField("position", v)}
        />
        <Vec3Input
          label="Rotation"
          value={displayValues.rotation}
          step={1}
          onChange={(v) => updateField("rotation", v)}
        />
        <Vec3Input
          label="Scale"
          value={displayValues.scale}
          step={0.01}
          onChange={(v) => updateField("scale", v)}
        />
      </div>

      {bone.parent && (
        <div className="info-section">
          <div className="info-section-title">Hierarchy</div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.8 }}>
            {getAncestorChain(bone.name, boneList).map((name, i, arr) => (
              <span key={name}>
                <span style={{ color: name === bone.name ? "var(--accent)" : undefined }}>
                  {name}
                </span>
                {i < arr.length - 1 && (
                  <span style={{ color: "var(--text-muted)", margin: "0 4px" }}>
                    &rarr;
                  </span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
