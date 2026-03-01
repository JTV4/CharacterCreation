import { useCallback, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { BoneTransformOverride } from "../types";

const DEG2RAD = Math.PI / 180;

export interface PoseKeyframe {
  time: number;
  bones: Record<string, [number, number, number]>;
}

export interface PoseAnimationConfig {
  name: string;
  id: string;
  duration: number;
  fps: number;
  loop: boolean;
}

interface PoseEditorProps {
  enabled: boolean;
  onToggle: () => void;
  config: PoseAnimationConfig;
  onConfigChange: (config: PoseAnimationConfig) => void;
  keyframes: PoseKeyframe[];
  onKeyframesChange: (keyframes: PoseKeyframe[]) => void;
  currentTime: number;
  onCurrentTimeChange: (time: number) => void;
  boneOverrides: Map<string, BoneTransformOverride>;
  onLoadOverrides: (overrides: Map<string, BoneTransformOverride>) => void;
  onClearOverrides: () => void;
}

function eulerToQuat(degrees: [number, number, number]): [number, number, number, number] {
  const euler = new THREE.Euler(
    degrees[0] * DEG2RAD,
    degrees[1] * DEG2RAD,
    degrees[2] * DEG2RAD,
  );
  const q = new THREE.Quaternion().setFromEuler(euler);
  return [
    parseFloat(q.x.toFixed(4)),
    parseFloat(q.y.toFixed(4)),
    parseFloat(q.z.toFixed(4)),
    parseFloat(q.w.toFixed(4)),
  ];
}

function exportToAnimJson(config: PoseAnimationConfig, keyframes: PoseKeyframe[]): string {
  const sorted = [...keyframes].sort((a, b) => a.time - b.time);

  const allBones = new Set<string>();
  for (const kf of sorted) {
    for (const bone of Object.keys(kf.bones)) {
      allBones.add(bone);
    }
  }

  const tracks: any[] = [];

  for (const boneName of allBones) {
    const boneKeyframes: { time: number; value: [number, number, number, number] }[] = [];

    for (const kf of sorted) {
      const euler = kf.bones[boneName];
      if (!euler) continue;
      const isZero = euler[0] === 0 && euler[1] === 0 && euler[2] === 0;
      if (isZero && sorted.length > 1) {
        boneKeyframes.push({ time: kf.time, value: [0, 0, 0, 1] });
      } else if (!isZero) {
        boneKeyframes.push({ time: kf.time, value: eulerToQuat(euler) });
      }
    }

    if (boneKeyframes.length === 0) continue;

    tracks.push({
      bone: boneName,
      property: "rotation",
      interpolation: "linear",
      keyframes: boneKeyframes,
    });
  }

  const animSpec = {
    meta: {
      name: config.name,
      id: config.id,
      duration: config.duration,
      fps: config.fps,
      loop: config.loop,
    },
    tracks,
  };

  return JSON.stringify(animSpec, null, 2);
}

export default function PoseEditor({
  enabled,
  onToggle,
  config,
  onConfigChange,
  keyframes,
  onKeyframesChange,
  currentTime,
  onCurrentTimeChange,
  boneOverrides,
  onLoadOverrides,
  onClearOverrides,
}: PoseEditorProps) {
  const [selectedKfIndex, setSelectedKfIndex] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const sortedKeyframes = useMemo(
    () => [...keyframes].sort((a, b) => a.time - b.time),
    [keyframes],
  );

  const captureKeyframe = useCallback(() => {
    const bones: Record<string, [number, number, number]> = {};
    for (const [name, override] of boneOverrides) {
      const r = override.rotation;
      if (r[0] !== 0 || r[1] !== 0 || r[2] !== 0) {
        bones[name] = [...r];
      }
    }

    if (Object.keys(bones).length === 0) return;

    const existingIdx = keyframes.findIndex(
      (kf) => Math.abs(kf.time - currentTime) < 0.001,
    );

    if (existingIdx >= 0) {
      const next = [...keyframes];
      const merged = { ...next[existingIdx].bones, ...bones };
      next[existingIdx] = { time: currentTime, bones: merged };
      onKeyframesChange(next);
    } else {
      onKeyframesChange([...keyframes, { time: currentTime, bones }]);
    }
  }, [boneOverrides, currentTime, keyframes, onKeyframesChange]);

  const loadKeyframe = useCallback(
    (index: number) => {
      const kf = sortedKeyframes[index];
      if (!kf) return;

      const overrides = new Map<string, BoneTransformOverride>();
      for (const [boneName, rotation] of Object.entries(kf.bones)) {
        overrides.set(boneName, {
          position: [0, 0, 0],
          rotation: [...rotation],
          scale: [1, 1, 1],
        });
      }
      onLoadOverrides(overrides);
      onCurrentTimeChange(kf.time);
      setSelectedKfIndex(index);
    },
    [sortedKeyframes, onLoadOverrides, onCurrentTimeChange],
  );

  const deleteKeyframe = useCallback(
    (index: number) => {
      const kf = sortedKeyframes[index];
      if (!kf) return;
      const next = keyframes.filter(
        (k) => Math.abs(k.time - kf.time) >= 0.001,
      );
      onKeyframesChange(next);
      if (selectedKfIndex === index) setSelectedKfIndex(null);
    },
    [sortedKeyframes, keyframes, onKeyframesChange, selectedKfIndex],
  );

  const handleExport = useCallback(() => {
    if (keyframes.length === 0) return;
    const json = exportToAnimJson(config, keyframes);
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${config.id}.anim.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [config, keyframes]);

  const handleImport = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = () => {
        try {
          const spec = JSON.parse(reader.result as string);
          if (spec.meta) {
            onConfigChange({
              name: spec.meta.name ?? config.name,
              id: spec.meta.id ?? config.id,
              duration: spec.meta.duration ?? config.duration,
              fps: spec.meta.fps ?? config.fps,
              loop: spec.meta.loop ?? config.loop,
            });
          }

          if (spec.tracks) {
            const imported: PoseKeyframe[] = [];
            const timeMap = new Map<number, Record<string, [number, number, number]>>();

            for (const track of spec.tracks) {
              if (track.property !== "rotation") continue;
              for (const kf of track.keyframes) {
                const [x, y, z, w] = kf.value;
                const q = new THREE.Quaternion(x, y, z, w);
                const euler = new THREE.Euler().setFromQuaternion(q);
                const deg: [number, number, number] = [
                  parseFloat((euler.x / DEG2RAD).toFixed(1)),
                  parseFloat((euler.y / DEG2RAD).toFixed(1)),
                  parseFloat((euler.z / DEG2RAD).toFixed(1)),
                ];

                if (!timeMap.has(kf.time)) timeMap.set(kf.time, {});
                timeMap.get(kf.time)![track.bone] = deg;
              }
            }

            for (const [time, bones] of timeMap) {
              imported.push({ time, bones });
            }
            onKeyframesChange(imported);
          }
        } catch (err) {
          console.error("Failed to import animation:", err);
        }
      };
      reader.readAsText(file);
      e.target.value = "";
    },
    [config, onConfigChange, onKeyframesChange],
  );

  const overrideCount = useMemo(() => {
    let count = 0;
    for (const [, override] of boneOverrides) {
      const r = override.rotation;
      if (r[0] !== 0 || r[1] !== 0 || r[2] !== 0) count++;
    }
    return count;
  }, [boneOverrides]);

  return (
    <div className="pose-editor">
      <div className="pose-editor-header">
        <h2>Pose Editor</h2>
        <button
          className={`pose-toggle-btn ${enabled ? "active" : ""}`}
          onClick={onToggle}
        >
          {enabled ? "ON" : "OFF"}
        </button>
      </div>

      {enabled && (
        <>
          <div className="pose-section">
            <div className="pose-section-title">Animation Settings</div>
            <div className="pose-field">
              <label className="pose-label">Name</label>
              <input
                className="pose-input"
                value={config.name}
                onChange={(e) =>
                  onConfigChange({ ...config, name: e.target.value })
                }
              />
            </div>
            <div className="pose-field">
              <label className="pose-label">ID</label>
              <input
                className="pose-input"
                value={config.id}
                onChange={(e) =>
                  onConfigChange({ ...config, id: e.target.value })
                }
              />
            </div>
            <div className="pose-field-row">
              <div className="pose-field">
                <label className="pose-label">Duration (s)</label>
                <input
                  className="pose-input pose-input-sm"
                  type="number"
                  step={0.1}
                  min={0.1}
                  value={config.duration}
                  onChange={(e) =>
                    onConfigChange({
                      ...config,
                      duration: parseFloat(e.target.value) || 1,
                    })
                  }
                />
              </div>
              <div className="pose-field">
                <label className="pose-label">FPS</label>
                <input
                  className="pose-input pose-input-sm"
                  type="number"
                  step={1}
                  min={1}
                  value={config.fps}
                  onChange={(e) =>
                    onConfigChange({
                      ...config,
                      fps: parseInt(e.target.value) || 30,
                    })
                  }
                />
              </div>
              <div className="pose-field">
                <label className="pose-label">Loop</label>
                <input
                  type="checkbox"
                  checked={config.loop}
                  onChange={(e) =>
                    onConfigChange({ ...config, loop: e.target.checked })
                  }
                />
              </div>
            </div>
          </div>

          <div className="pose-section">
            <div className="pose-section-title">Capture</div>
            <div className="pose-field-row">
              <div className="pose-field" style={{ flex: 1 }}>
                <label className="pose-label">Time (s)</label>
                <input
                  className="pose-input"
                  type="number"
                  step={0.1}
                  min={0}
                  max={config.duration}
                  value={currentTime}
                  onChange={(e) =>
                    onCurrentTimeChange(
                      Math.max(
                        0,
                        Math.min(
                          config.duration,
                          parseFloat(e.target.value) || 0,
                        ),
                      ),
                    )
                  }
                />
              </div>
              <button
                className="pose-capture-btn"
                onClick={captureKeyframe}
                disabled={overrideCount === 0}
                title={
                  overrideCount === 0
                    ? "Rotate bones first using the Bone Inspector overrides"
                    : `Capture ${overrideCount} bone rotation(s) at t=${currentTime}s`
                }
              >
                Capture ({overrideCount})
              </button>
            </div>
            <button
              className="pose-clear-btn"
              onClick={onClearOverrides}
              disabled={overrideCount === 0}
            >
              Clear All Overrides
            </button>
          </div>

          <div className="pose-section">
            <div className="pose-section-title">
              Keyframes ({sortedKeyframes.length})
            </div>
            {sortedKeyframes.length === 0 ? (
              <p className="pose-empty">
                No keyframes yet. Rotate bones in the Bone Inspector, then
                capture.
              </p>
            ) : (
              <div className="pose-keyframe-list">
                {sortedKeyframes.map((kf, i) => {
                  const boneCount = Object.keys(kf.bones).length;
                  const isSelected = selectedKfIndex === i;
                  return (
                    <div
                      key={`${kf.time}-${i}`}
                      className={`pose-keyframe-item ${isSelected ? "selected" : ""}`}
                    >
                      <button
                        className="pose-kf-load"
                        onClick={() => loadKeyframe(i)}
                        title="Load this keyframe into overrides"
                      >
                        <span className="pose-kf-time">
                          {kf.time.toFixed(2)}s
                        </span>
                        <span className="pose-kf-bones">
                          {boneCount} bone{boneCount !== 1 ? "s" : ""}
                        </span>
                      </button>
                      <button
                        className="pose-kf-delete"
                        onClick={() => deleteKeyframe(i)}
                        title="Delete keyframe"
                      >
                        ×
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {sortedKeyframes.length > 0 && (
              <div className="pose-timeline-bar">
                {sortedKeyframes.map((kf, i) => (
                  <div
                    key={i}
                    className={`pose-timeline-dot ${selectedKfIndex === i ? "selected" : ""}`}
                    style={{
                      left: `${(kf.time / config.duration) * 100}%`,
                    }}
                    onClick={() => loadKeyframe(i)}
                    title={`t=${kf.time.toFixed(2)}s`}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="pose-section">
            <div className="pose-section-title">Import / Export</div>
            <div className="pose-export-row">
              <button
                className="pose-export-btn"
                onClick={handleExport}
                disabled={keyframes.length === 0}
              >
                Export .anim.json
              </button>
              <button
                className="pose-import-btn"
                onClick={() => fileInputRef.current?.click()}
              >
                Import
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                style={{ display: "none" }}
                onChange={handleImport}
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
