import { useEffect, useState } from "react";
import type { BoneNode, BoneSpec, RigSpec } from "../types";

function buildTree(spec: RigSpec): BoneNode[] {
  const mirrorMap = new Map<string, string>();
  for (const [l, r] of spec.mirror_pairs) {
    mirrorMap.set(l, r);
    mirrorMap.set(r, l);
  }

  const nodeMap = new Map<string, BoneNode>();
  for (const bone of spec.bones) {
    nodeMap.set(bone.name, {
      ...bone,
      children: [],
      mirrorOf: mirrorMap.get(bone.name) ?? null,
    });
  }

  const roots: BoneNode[] = [];
  for (const node of nodeMap.values()) {
    if (node.parent === null) {
      roots.push(node);
    } else {
      const parentNode = nodeMap.get(node.parent);
      if (parentNode) {
        parentNode.children.push(node);
      }
    }
  }

  return roots;
}

export interface SkeletonData {
  spec: RigSpec;
  tree: BoneNode[];
  boneMap: Map<string, BoneNode>;
}

export function useSkeletonData(): {
  data: SkeletonData | null;
  error: string | null;
  loading: boolean;
} {
  const [data, setData] = useState<SkeletonData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/rig_spec.json")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        return res.json() as Promise<RigSpec>;
      })
      .then((spec) => {
        const tree = buildTree(spec);

        const boneMap = new Map<string, BoneNode>();
        const mirrorMap = new Map<string, string>();
        for (const [l, r] of spec.mirror_pairs) {
          mirrorMap.set(l, r);
          mirrorMap.set(r, l);
        }
        for (const bone of spec.bones) {
          boneMap.set(bone.name, {
            ...bone,
            children: [],
            mirrorOf: mirrorMap.get(bone.name) ?? null,
          });
        }

        setData({ spec, tree, boneMap });
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });
  }, []);

  return { data, error, loading };
}
