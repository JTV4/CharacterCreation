import { useCallback, useRef } from "react";
import type { AnimSpec, AnimManifest } from "../types/animation";

interface AnimationControlsProps {
  animations: AnimManifest["animations"];
  activeAnimId: string | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  speed: number;
  loop: boolean;
  hasTracks: boolean;
  onSelectAnimation: (id: string) => void;
  onPlay: () => void;
  onPause: () => void;
  onStop: () => void;
  onSeek: (time: number) => void;
  onSetSpeed: (speed: number) => void;
  onSetLoop: (loop: boolean) => void;
}

const SPEED_OPTIONS = [0.25, 0.5, 1, 2];

export default function AnimationControls({
  animations,
  activeAnimId,
  isPlaying,
  currentTime,
  duration,
  speed,
  loop,
  hasTracks,
  onSelectAnimation,
  onPlay,
  onPause,
  onStop,
  onSeek,
  onSetSpeed,
  onSetLoop,
}: AnimationControlsProps) {
  const scrubberRef = useRef<HTMLDivElement>(null);

  const handleScrub = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!scrubberRef.current || duration <= 0) return;
      const rect = scrubberRef.current.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      onSeek(ratio * duration);
    },
    [duration, onSeek],
  );

  const handleScrubDrag = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.buttons !== 1) return;
      handleScrub(e);
    },
    [handleScrub],
  );

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="anim-controls">
      <div className="anim-controls-row">
        <select
          className="anim-select"
          value={activeAnimId ?? ""}
          onChange={(e) => onSelectAnimation(e.target.value)}
        >
          <option value="tpose">
            T-pose
          </option>
          {animations.map((a) => (
            <option key={a.id} value={a.id}>
              {a.id}
            </option>
          ))}
        </select>

        <div className="anim-transport">
          <button
            className="anim-btn"
            onClick={onStop}
            disabled={!activeAnimId}
            title="Stop"
          >
            &#9632;
          </button>
          <button
            className="anim-btn anim-btn-play"
            onClick={isPlaying ? onPause : onPlay}
            disabled={!activeAnimId || !hasTracks}
            title={isPlaying ? "Pause" : "Play"}
          >
            {isPlaying ? "\u23F8" : "\u25B6"}
          </button>
        </div>

        <div
          className="anim-scrubber"
          ref={scrubberRef}
          onClick={handleScrub}
          onMouseMove={handleScrubDrag}
        >
          <div className="anim-scrubber-track">
            <div
              className="anim-scrubber-fill"
              style={{ width: `${progress}%` }}
            />
            <div
              className="anim-scrubber-head"
              style={{ left: `${progress}%` }}
            />
          </div>
        </div>

        <span className="anim-time">
          {currentTime.toFixed(2)}s / {duration.toFixed(2)}s
        </span>
      </div>

      <div className="anim-controls-row anim-controls-secondary">
        <label className="anim-loop-label">
          <input
            type="checkbox"
            checked={loop}
            onChange={(e) => onSetLoop(e.target.checked)}
          />
          Loop
        </label>

        <div className="anim-speed">
          <span className="anim-speed-label">Speed:</span>
          {SPEED_OPTIONS.map((s) => (
            <button
              key={s}
              className={`anim-speed-btn ${speed === s ? "active" : ""}`}
              onClick={() => onSetSpeed(s)}
            >
              {s}x
            </button>
          ))}
        </div>

        {!hasTracks && activeAnimId && (
          <span className="anim-no-tracks">No keyframes yet</span>
        )}
      </div>
    </div>
  );
}
