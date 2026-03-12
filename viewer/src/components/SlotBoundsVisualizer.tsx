import { useMemo } from "react";
import * as THREE from "three";
import { Text } from "@react-three/drei";

interface SlotBounds {
  z_min: number;
  z_max: number;
  radius: number;
}

interface SlotDef {
  id: string;
  name: string;
  bounds: SlotBounds;
}

const SLOT_COLORS: Record<string, string> = {
  helmet: "#ff6b6b",
  head: "#ff6b6b",
  amulet: "#ffd93d",
  upper_body: "#6bcb77",
  gloves: "#4d96ff",
  ring: "#ff6bff",
  lower_body: "#ff9f43",
  boots: "#a55eea",
};

const SEEN_BOUNDS_KEY = (b: SlotBounds) =>
  `${b.z_min}_${b.z_max}_${b.radius}`;

interface SlotBoundsVisualizerProps {
  slots: SlotDef[];
}

function BoundsCylinder({
  slot,
  color,
}: {
  slot: SlotDef;
  color: string;
}) {
  const { z_min, z_max, radius } = slot.bounds;
  const height = z_max - z_min;
  const centerZ = (z_min + z_max) / 2;

  const edgesGeo = useMemo(() => {
    const cylGeo = new THREE.CylinderGeometry(radius, radius, height, 24, 1, true);
    cylGeo.rotateX(Math.PI / 2);
    const edges = new THREE.EdgesGeometry(cylGeo);
    cylGeo.dispose();
    return edges;
  }, [radius, height]);

  const labelOffset = radius + 0.05;

  return (
    <group position={[0, 0, centerZ]}>
      <lineSegments geometry={edgesGeo}>
        <lineBasicMaterial color={color} transparent opacity={0.6} depthTest={false} />
      </lineSegments>

      {/* Top cap ring */}
      <mesh position={[0, 0, height / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[radius - 0.002, radius, 24]} />
        <meshBasicMaterial color={color} transparent opacity={0.15} side={THREE.DoubleSide} depthTest={false} />
      </mesh>

      {/* Bottom cap ring */}
      <mesh position={[0, 0, -height / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[radius - 0.002, radius, 24]} />
        <meshBasicMaterial color={color} transparent opacity={0.15} side={THREE.DoubleSide} depthTest={false} />
      </mesh>

      <Text
        position={[labelOffset, 0, height / 2 + 0.02]}
        fontSize={0.05}
        color={color}
        anchorX="left"
        anchorY="bottom"
        depthTest={false}
        renderOrder={999}
      >
        {slot.name}
      </Text>
      <Text
        position={[labelOffset, 0, height / 2 - 0.04]}
        fontSize={0.03}
        color={color}
        anchorX="left"
        anchorY="top"
        depthTest={false}
        renderOrder={999}
      >
        {`r=${radius}m  h=${height.toFixed(2)}m`}
      </Text>
    </group>
  );
}

export default function SlotBoundsVisualizer({ slots }: SlotBoundsVisualizerProps) {
  const uniqueSlots = useMemo(() => {
    const seen = new Set<string>();
    const result: { slot: SlotDef; color: string }[] = [];
    for (const slot of slots) {
      const key = SEEN_BOUNDS_KEY(slot.bounds);
      if (seen.has(key)) continue;
      seen.add(key);

      const slotType = slot.id.replace(/_[mf]$/, "").replace(/^(base_|decentraland_|f_|m_)/, "");
      const color = SLOT_COLORS[slotType] ?? SLOT_COLORS[slot.id] ?? "#888888";
      result.push({ slot, color });
    }
    return result;
  }, [slots]);

  return (
    <group>
      {uniqueSlots.map(({ slot, color }) => (
        <BoundsCylinder key={slot.id} slot={slot} color={color} />
      ))}
    </group>
  );
}
