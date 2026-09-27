import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import SectionCollapse from "./SectionCollapse";
import type {
  EquipmentSlot,
  EquipTransform,
  EquipBoneOffset,
  EquipBoneOffsetMap,
} from "../types/equipment";
import {
  SLOT_COLORS,
  IDENTITY_BONE_OFFSET,
  isIdentityBoneOffset,
  normalizeBoneOffset,
  shortBoneLabel,
} from "../types/equipment";
import { canonicalBoneKey } from "../utils/equipBoneFit";
import type { GizmoMode } from "../types/tools";

interface MeshInfoPanelProps {
  slot: EquipmentSlot | null;
  transform: EquipTransform;
  gizmoMode: GizmoMode;
  onGizmoModeChange: (mode: GizmoMode) => void;
  onTransformChange: (t: EquipTransform) => void;
  onReset: () => void;
  selectedBone: string | null;
  onSelectBone: (name: string | null) => void;
  boneOffsets: EquipBoneOffsetMap;
  onBoneOffsetChange: (boneName: string, offset: EquipBoneOffset | null) => void;
  onResetAllBones: () => void;
  allBoneNames?: string[];
}

const DRAG_THRESHOLD = 3;

const FACE_PAIR_CATEGORIES = new Set(["eyes", "eyebrows", "eyelashes", "ears"]);

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
  selectedBone,
  onSelectBone,
  boneOffsets,
  onBoneOffsetChange,
  onResetAllBones,
  allBoneNames,
}: MeshInfoPanelProps) {
  const isEyes = slot?.category === "eyes";
  const isFacePair = !!slot?.category && FACE_PAIR_CATEGORIES.has(slot.category);
  const pairSeparation = transform.eyeSeparation ?? 0;
  const eyeRotationL = transform.eyeRotationL ?? ([0, 0, 0] as [number, number, number]);
  const eyeRotationR = transform.eyeRotationR ?? ([0, 0, 0] as [number, number, number]);
  const eyeRotDirty =
    eyeRotationL.some((v) => v !== 0) || eyeRotationR.some((v) => v !== 0);

  const hasOffset =
    transform.position.some((v) => v !== 0) ||
    transform.rotation.some((v) => v !== 0) ||
    transform.scale.some((v) => v !== 1) ||
    (isFacePair && pairSeparation !== 0) ||
    (isEyes && eyeRotDirty);

  const [showAllBones, setShowAllBones] = useState(false);

  const fitBoneNames = useMemo(() => {
    if (!slot) return [];
    const declared = slot.bones.map((b) => canonicalBoneKey(b.name));
    const extra = Object.keys(boneOffsets).map(canonicalBoneKey);
    if (!showAllBones) {
      return Array.from(new Set([...declared, ...extra]));
    }
    const all = (allBoneNames ?? []).map(canonicalBoneKey);
    return Array.from(new Set([...declared, ...extra, ...all]));
  }, [slot, boneOffsets, showAllBones, allBoneNames]);

  const selectedOffset = selectedBone
    ? normalizeBoneOffset(boneOffsets[canonicalBoneKey(selectedBone)])
    : IDENTITY_BONE_OFFSET;
  const boneDirty = selectedBone ? !isIdentityBoneOffset(selectedOffset) : false;
  const anyBoneDirty = Object.values(boneOffsets).some((o) => !isIdentityBoneOffset(normalizeBoneOffset(o)));

  const handleCopyTransform = useCallback(() => {
    if (!slot) return;
    const fmt = (v: [number, number, number]) =>
      `[${v.map((n) => n.toFixed(4)).join(", ")}]`;
    const lines = [
      `Equipment: ${slot.id}`,
      `Name: ${slot.name}`,
      `Position: ${fmt(transform.position)}`,
      `Rotation: ${fmt(transform.rotation)}`,
      `Scale: ${fmt(transform.scale)}`,
    ];
    if (slot.category && FACE_PAIR_CATEGORIES.has(slot.category)) {
      lines.push(`Pair Separation: ${(transform.eyeSeparation ?? 0).toFixed(4)}`);
    }
    if (slot.category === "eyes") {
      lines.push(`Eye Rotation L: ${fmt(transform.eyeRotationL ?? [0, 0, 0])}`);
      lines.push(`Eye Rotation R: ${fmt(transform.eyeRotationR ?? [0, 0, 0])}`);
    }
    const dirtyBones = Object.entries(boneOffsets).filter(
      ([, o]) => !isIdentityBoneOffset(normalizeBoneOffset(o)),
    );
    if (dirtyBones.length) {
      lines.push("Bone offsets:");
      for (const [name, o] of dirtyBones) {
        const n = normalizeBoneOffset(o);
        lines.push(`  ${name} p=${fmt(n.position)} r=${fmt(n.rotation)} s=${fmt(n.scale)}`);
      }
    }
    navigator.clipboard.writeText(lines.join("\n"));
  }, [slot, transform, boneOffsets]);

  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (slot) setOpen(true);
  }, [slot?.id]);

  if (!slot) {
    return (
      <div className="info-panel">
        <SectionCollapse title="Mesh Inspector" open={open} onToggle={() => setOpen((v) => !v)} />
        {open && <p className="info-empty">Select a mesh to view its properties</p>}
      </div>
    );
  }

  const color = slot.color ?? SLOT_COLORS[slot.id] ?? "#94a3b8";

  return (
    <div className="info-panel">
      <SectionCollapse title="Mesh Inspector" open={open} onToggle={() => setOpen((v) => !v)} />
      {open && <>
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
          step={0.001}
          onChange={(v) => onTransformChange({ ...transform, position: v })}
        />
        <Vec3Input
          label="Rotation"
          value={transform.rotation}
          step={1}
          onChange={(v) => onTransformChange({ ...transform, rotation: v })}
        />
        <Vec3Input
          label="Scale"
          value={transform.scale}
          step={0.01}
          onChange={(v) => onTransformChange({ ...transform, scale: v })}
        />
        {isFacePair && (
          <div className="override-field">
            <span
              className="override-field-label"
              title="Extra distance between left and right sides (meters). 0 = authored spacing; positive = wider; negative = closer."
            >
              {isEyes ? "Eye Dist" : "Pair Dist"}
            </span>
            <div className="override-inputs">
              <DraggableInput
                axis=""
                value={pairSeparation}
                step={0.001}
                onChange={(v) =>
                  onTransformChange({
                    ...transform,
                    eyeSeparation: parseFloat(Math.max(-0.05, Math.min(0.08, v)).toFixed(4)),
                  })
                }
              />
            </div>
          </div>
        )}
        {isEyes && (
          <>
            <Vec3Input
              label="Eye Rot L"
              value={eyeRotationL}
              step={1}
              onChange={(v) => onTransformChange({ ...transform, eyeRotationL: v })}
            />
            <Vec3Input
              label="Eye Rot R"
              value={eyeRotationR}
              step={1}
              onChange={(v) => onTransformChange({ ...transform, eyeRotationR: v })}
            />
          </>
        )}
      </div>

      <div className="info-section">
        <div className="info-section-title" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span>Fit bones</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              className="override-copy-btn"
              onClick={() => setShowAllBones((v) => !v)}
              title="List every Mixamo bone, not just this slot's influences"
            >
              {showAllBones ? "Slot bones" : "All bones"}
            </button>
            {anyBoneDirty && (
              <button className="override-reset-btn" onClick={onResetAllBones}>
                Reset all
              </button>
            )}
          </div>
        </div>
        <p className="equip-bone-hint">
          Move a wearable bone without moving the body. Offsets save automatically.
        </p>
        <button
          className={`equip-bone-row${selectedBone == null ? " selected" : ""}`}
          onClick={() => onSelectBone(null)}
        >
          Whole mesh
        </button>
        <div className="equip-bone-list">
          {fitBoneNames.map((name) => {
            const dirty = !isIdentityBoneOffset(normalizeBoneOffset(boneOffsets[name]));
            const isSel = selectedBone != null && canonicalBoneKey(selectedBone) === name;
            return (
              <button
                key={name}
                className={`equip-bone-row${isSel ? " selected" : ""}${dirty ? " dirty" : ""}`}
                onClick={() => onSelectBone(isSel ? null : name)}
              >
                <span>{shortBoneLabel(name)}</span>
                {dirty && <span className="equip-bone-dot" />}
              </button>
            );
          })}
        </div>
        {selectedBone && (
          <>
            <div className="transform-toolbar" style={{ marginTop: 8 }}>
              {(["translate", "rotate", "scale"] as const).map((m) => {
                const label = m === "translate" ? "T" : m === "rotate" ? "R" : "S";
                const isActive = gizmoMode === m;
                return (
                  <button
                    key={m}
                    className={`transform-toolbar-btn${isActive ? " active" : ""}`}
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
              label="Bone position"
              value={selectedOffset.position}
              step={0.001}
              onChange={(v) =>
                onBoneOffsetChange(canonicalBoneKey(selectedBone), { ...selectedOffset, position: v })
              }
            />
            <Vec3Input
              label="Bone rotation"
              value={selectedOffset.rotation}
              step={1}
              onChange={(v) =>
                onBoneOffsetChange(canonicalBoneKey(selectedBone), { ...selectedOffset, rotation: v })
              }
            />
            <Vec3Input
              label="Bone scale"
              value={selectedOffset.scale}
              step={0.01}
              onChange={(v) =>
                onBoneOffsetChange(canonicalBoneKey(selectedBone), { ...selectedOffset, scale: v })
              }
            />
            {boneDirty && (
              <button
                className="override-reset-btn"
                style={{ marginTop: 8 }}
                onClick={() => onBoneOffsetChange(canonicalBoneKey(selectedBone), null)}
              >
                Reset bone
              </button>
            )}
          </>
        )}
      </div>
      </>}
    </div>
  );
}
