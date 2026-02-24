import type { BoneNode, BoneCategory, RigSpec } from "../types";
import { CATEGORY_COLORS } from "../types";

interface BoneInfoPanelProps {
  bone: BoneNode | null;
  spec: RigSpec;
}

function formatVec(v: [number, number, number]): string {
  return `[${v.map((n) => n.toFixed(3)).join(", ")}]`;
}

function formatRoll(r: number): string {
  const deg = (r * 180) / Math.PI;
  return `${r.toFixed(4)} rad (${deg.toFixed(1)}\u00B0)`;
}

function boneLength(head: [number, number, number], tail: [number, number, number]): string {
  const dx = tail[0] - head[0];
  const dy = tail[1] - head[1];
  const dz = tail[2] - head[2];
  return Math.sqrt(dx * dx + dy * dy + dz * dz).toFixed(4);
}

export default function BoneInfoPanel({ bone, spec }: BoneInfoPanelProps) {
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
        <div className="info-section-title">Transform</div>
        <div className="info-row">
          <span className="info-label">Head</span>
        </div>
        <div className="info-vector">{formatVec(bone.head)}</div>
        <div className="info-row" style={{ marginTop: 6 }}>
          <span className="info-label">Tail</span>
        </div>
        <div className="info-vector">{formatVec(bone.tail)}</div>
        <div className="info-row" style={{ marginTop: 6 }}>
          <span className="info-label">Roll</span>
          <span className="info-value">{formatRoll(bone.roll)}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Length</span>
          <span className="info-value">{boneLength(bone.head, bone.tail)} m</span>
        </div>
      </div>

      <div className="info-section">
        <div className="info-section-title">Properties</div>
        <div className="info-row">
          <span className="info-label">Deform</span>
          <span className="info-value">{bone.deform ? "Yes" : "No"}</span>
        </div>
        {bone.mirrorOf && (
          <div className="info-row">
            <span className="info-label">Mirror</span>
            <span className="info-value">{bone.mirrorOf}</span>
          </div>
        )}
      </div>

      {bone.parent && (
        <div className="info-section">
          <div className="info-section-title">Hierarchy</div>
          <div style={{ fontSize: 11, color: "var(--text-secondary)", lineHeight: 1.8 }}>
            {getAncestorChain(bone.name, spec).map((name, i, arr) => (
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

function getAncestorChain(boneName: string, spec: RigSpec): string[] {
  const boneMap = new Map(spec.bones.map((b) => [b.name, b]));
  const chain: string[] = [];
  let current: string | null = boneName;
  while (current) {
    chain.unshift(current);
    const b = boneMap.get(current);
    current = b?.parent ?? null;
  }
  return chain;
}
