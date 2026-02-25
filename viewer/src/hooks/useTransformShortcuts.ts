import { useEffect, useRef, useState } from "react";
import type { BoneTransformOverride } from "../types";

export type TransformMode = "position" | "rotate" | "scale" | null;

const DEFAULT_OVERRIDE: BoneTransformOverride = {
  position: [0, 0, 0],
  rotation: [0, 0, 0],
  scale: [1, 1, 1],
};

function isDefaultOverride(o: BoneTransformOverride): boolean {
  return (
    o.position[0] === 0 && o.position[1] === 0 && o.position[2] === 0 &&
    o.rotation[0] === 0 && o.rotation[1] === 0 && o.rotation[2] === 0 &&
    o.scale[0] === 1 && o.scale[1] === 1 && o.scale[2] === 1
  );
}

interface Params {
  selectedBone: string | null;
  boneOverrides: Map<string, BoneTransformOverride>;
  onSetBoneOverride: (boneName: string, override: BoneTransformOverride | null) => void;
}

export function useTransformShortcuts({
  selectedBone,
  boneOverrides,
  onSetBoneOverride,
}: Params): { transformMode: TransformMode } {
  const [mode, setMode] = useState<TransformMode>(null);

  const startRef = useRef<{
    mouseX: number;
    mouseY: number;
    override: BoneTransformOverride;
    boneName: string;
  } | null>(null);

  const mousePosRef = useRef({ x: 0, y: 0 });

  // Cancel if bone gets deselected while in a mode
  useEffect(() => {
    if (!selectedBone && mode) {
      if (startRef.current) {
        const { boneName, override } = startRef.current;
        onSetBoneOverride(boneName, isDefaultOverride(override) ? null : override);
      }
      startRef.current = null;
      setMode(null);
    }
  }, [selectedBone, mode, onSetBoneOverride]);

  // Global mouse tracking + live transform while in mode
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mousePosRef.current = { x: e.clientX, y: e.clientY };

      if (!mode || !startRef.current) return;

      const dx = e.clientX - startRef.current.mouseX;
      const dy = e.clientY - startRef.current.mouseY;
      const s = startRef.current.override;
      const boneName = startRef.current.boneName;
      let next: BoneTransformOverride;

      switch (mode) {
        case "scale": {
          const f = Math.max(0.01, 1 + dx * 0.005);
          next = {
            ...s,
            scale: [s.scale[0] * f, s.scale[1] * f, s.scale[2] * f],
          };
          break;
        }
        case "rotate":
          next = {
            ...s,
            rotation: [
              s.rotation[0] - dy * 0.3,
              s.rotation[1] + dx * 0.3,
              s.rotation[2],
            ],
          };
          break;
        case "position":
          next = {
            ...s,
            position: [
              s.position[0] + dx * 0.001,
              s.position[1],
              s.position[2] - dy * 0.001,
            ],
          };
          break;
        default:
          return;
      }

      onSetBoneOverride(boneName, next);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, [mode, onSetBoneOverride]);

  // Keyboard: enter mode (S/R/P), cancel (Escape)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      const key = e.key.toLowerCase();

      if (mode && key === "escape") {
        if (startRef.current) {
          const { boneName, override } = startRef.current;
          onSetBoneOverride(boneName, isDefaultOverride(override) ? null : override);
        }
        startRef.current = null;
        setMode(null);
        e.preventDefault();
        return;
      }

      if (mode) return;
      if (!selectedBone) return;

      let next: TransformMode = null;
      if (key === "s") next = "scale";
      else if (key === "r") next = "rotate";
      else if (key === "p") next = "position";

      if (next) {
        e.preventDefault();
        const cur = boneOverrides.get(selectedBone) ?? { ...DEFAULT_OVERRIDE };
        startRef.current = {
          mouseX: mousePosRef.current.x,
          mouseY: mousePosRef.current.y,
          override: {
            position: [...cur.position],
            rotation: [...cur.rotation],
            scale: [...cur.scale],
          },
          boneName: selectedBone,
        };
        setMode(next);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mode, selectedBone, boneOverrides, onSetBoneOverride]);

  // Confirm on pointer down (left click), cancel on right click
  useEffect(() => {
    if (!mode) return;

    const handlePointerDown = (e: PointerEvent) => {
      if (e.button === 2 && startRef.current) {
        const { boneName, override } = startRef.current;
        onSetBoneOverride(boneName, isDefaultOverride(override) ? null : override);
      }
      e.stopPropagation();
      e.preventDefault();
      startRef.current = null;
      setMode(null);
    };

    window.addEventListener("pointerdown", handlePointerDown, true);
    return () => window.removeEventListener("pointerdown", handlePointerDown, true);
  }, [mode, onSetBoneOverride]);

  return { transformMode: mode };
}
