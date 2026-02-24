import { useState } from "react";
import { useSkeletonData } from "./hooks/useSkeletonData";
import Scene from "./components/Scene";
import BoneSidebar from "./components/BoneSidebar";
import BoneInfoPanel from "./components/BoneInfoPanel";

export default function App() {
  const { data, error, loading } = useSkeletonData();
  const [selectedBone, setSelectedBone] = useState<string | null>(null);

  if (loading) {
    return <div className="loading-screen">Loading rig spec...</div>;
  }

  if (error || !data) {
    return (
      <div className="error-screen">
        Failed to load rig spec: {error ?? "Unknown error"}
      </div>
    );
  }

  const selected = selectedBone ? data.boneMap.get(selectedBone) ?? null : null;

  return (
    <div className="app-layout">
      <BoneSidebar
        spec={data.spec}
        tree={data.tree}
        selectedBone={selectedBone}
        onSelectBone={setSelectedBone}
      />
      <div className="viewport">
        <div className="viewport-overlay">
          {data.spec.bones.length} bones &middot;{" "}
          {data.spec.meta.rest_pose.toUpperCase()} &middot;{" "}
          {data.spec.meta.scale}
        </div>
        <Scene
          spec={data.spec}
          selectedBone={selectedBone}
          onSelectBone={setSelectedBone}
        />
      </div>
      <BoneInfoPanel bone={selected} spec={data.spec} />
    </div>
  );
}
