import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";
import SkeletonViewer from "./SkeletonViewer";
import type { RigSpec } from "../types";
import type { AnimatedBonePositions } from "../hooks/useAnimationPlayer";
import type { TransformMode } from "../hooks/useTransformShortcuts";

interface SceneProps {
  spec: RigSpec;
  selectedBone: string | null;
  onSelectBone: (name: string | null) => void;
  animatedPositions?: Map<string, AnimatedBonePositions> | null;
  transformMode?: TransformMode;
  children?: React.ReactNode;
}

export default function Scene({
  spec,
  selectedBone,
  onSelectBone,
  animatedPositions,
  transformMode,
  children,
}: SceneProps) {
  const cursorStyle = transformMode === "scale"
    ? "ew-resize"
    : transformMode === "rotate"
      ? "grab"
      : transformMode === "position"
        ? "move"
        : undefined;
  return (
    <Canvas
      camera={{ position: [2, 1.5, 2], fov: 45, near: 0.01, far: 100 }}
      style={{ width: "100%", height: "100%", cursor: cursorStyle }}
      onPointerMissed={() => { if (!transformMode) onSelectBone(null); }}
    >
      <ambientLight intensity={0.5} />
      <directionalLight position={[5, 8, 5]} intensity={1} />
      <directionalLight position={[-3, 4, -2]} intensity={0.3} />

      <Grid
        args={[10, 10]}
        cellSize={0.1}
        cellThickness={0.5}
        cellColor="#2a2d3a"
        sectionSize={1}
        sectionThickness={1}
        sectionColor="#3a3d4a"
        fadeDistance={8}
        fadeStrength={1}
        infiniteGrid
      />

      <axesHelper args={[0.3]} />

      <SkeletonViewer
        spec={spec}
        selectedBone={selectedBone}
        onSelectBone={onSelectBone}
        animatedPositions={animatedPositions}
      />

      {children}

      <OrbitControls
        enabled={!transformMode}
        target={[0, 0, 0.9]}
        enableDamping
        dampingFactor={0.1}
        minDistance={0.5}
        maxDistance={10}
      />
    </Canvas>
  );
}
