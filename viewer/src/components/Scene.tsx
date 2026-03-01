import { Canvas, useThree, useFrame } from "@react-three/fiber";
import { OrbitControls, Grid, Text } from "@react-three/drei";
import { useRef, useCallback } from "react";
import * as THREE from "three";
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

const ORBIT_TARGET: [number, number, number] = [0, 0, 0.9];

const AXIS_VIEWS = [
  { key: "+X", label: "Right", colorClass: "axis-x" },
  { key: "-X", label: "Left", colorClass: "axis-x" },
  { key: "+Y", label: "Front", colorClass: "axis-y" },
  { key: "-Y", label: "Back", colorClass: "axis-y" },
  { key: "+Z", label: "Top", colorClass: "axis-z" },
  { key: "-Z", label: "Bottom", colorClass: "axis-z" },
] as const;

const VIEW_OFFSETS: Record<string, [number, number, number]> = {
  "+X": [1, 0, 0],
  "-X": [-1, 0, 0],
  "+Y": [0, 1, 0],
  "-Y": [0, -1, 0],
  "+Z": [0, -0.001, 1],
  "-Z": [0, -0.001, -1],
};

function CameraAnimator({
  pendingViewRef,
  controlsRef,
}: {
  pendingViewRef: React.MutableRefObject<[number, number, number] | null>;
  controlsRef: React.MutableRefObject<any>;
}) {
  const { camera } = useThree();
  const targetPos = useRef<THREE.Vector3 | null>(null);

  useFrame(() => {
    if (pendingViewRef.current) {
      targetPos.current = new THREE.Vector3(...pendingViewRef.current);
      pendingViewRef.current = null;
    }

    const target = targetPos.current;
    const controls = controlsRef.current;
    if (!target || !controls) return;

    camera.position.lerp(target, 0.15);
    controls.update();

    if (camera.position.distanceTo(target) < 0.005) {
      camera.position.copy(target);
      controls.update();
      targetPos.current = null;
    }
  });

  return null;
}

export default function Scene({
  spec,
  selectedBone,
  onSelectBone,
  animatedPositions,
  transformMode,
  children,
}: SceneProps) {
  const controlsRef = useRef<any>(null);
  const pendingViewRef = useRef<[number, number, number] | null>(null);

  const handleSetView = useCallback((viewKey: string) => {
    const controls = controlsRef.current;
    if (!controls) return;

    const target = controls.target as THREE.Vector3;
    const cam = controls.object as THREE.Camera;
    const dist = cam.position.distanceTo(target);
    const offset = VIEW_OFFSETS[viewKey];
    if (!offset) return;

    pendingViewRef.current = [
      target.x + offset[0] * dist,
      target.y + offset[1] * dist,
      target.z + offset[2] * dist,
    ];
  }, []);

  const cursorStyle =
    transformMode === "scale"
      ? "ew-resize"
      : transformMode === "rotate"
        ? "grab"
        : transformMode === "position"
          ? "move"
          : undefined;

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      <Canvas
        camera={{ position: [2, 1.5, 2], fov: 45, near: 0.01, far: 100 }}
        style={{ width: "100%", height: "100%", cursor: cursorStyle }}
        onPointerMissed={() => {
          if (!transformMode) onSelectBone(null);
        }}
        onCreated={({ camera }) => {
          camera.up.set(0, 0, 1);
        }}
      >
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 8, 5]} intensity={1} />
        <directionalLight position={[-3, 4, -2]} intensity={0.3} />

        <Grid
          args={[10, 10]}
          rotation={[Math.PI / 2, 0, 0]}
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

        <axesHelper args={[1]} />
        <Text position={[1.1, 0, 0]} fontSize={0.1} color="#ff4444" anchorX="left">
          +X
        </Text>
        <Text position={[0, 1.1, 0]} fontSize={0.1} color="#44ff44" anchorX="left">
          +Y
        </Text>
        <Text position={[0, 0, 1.1]} fontSize={0.1} color="#4488ff" anchorX="left">
          +Z
        </Text>

        <SkeletonViewer
          spec={spec}
          selectedBone={selectedBone}
          onSelectBone={onSelectBone}
          animatedPositions={animatedPositions}
        />

        {children}

        <OrbitControls
          ref={controlsRef}
          makeDefault
          enabled={!transformMode}
          target={ORBIT_TARGET}
          enableDamping
          dampingFactor={0.1}
          minDistance={0.5}
          maxDistance={10}
        />

        <CameraAnimator
          pendingViewRef={pendingViewRef}
          controlsRef={controlsRef}
        />
      </Canvas>

      <div className="axis-view-controls">
        {AXIS_VIEWS.map(({ key, label, colorClass }) => (
          <button
            key={key}
            className="axis-view-btn"
            onClick={() => handleSetView(key)}
            title={`${label} (${key})`}
          >
            <span className={`axis-view-tag ${colorClass}`}>{key}</span>
            <span className="axis-view-desc">{label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
