import { useState, useMemo } from "react";
import type { BoneNode, BoneSpec, BoneCategory, RigSpec } from "../types";
import { CATEGORY_COLORS, CATEGORY_ORDER } from "../types";

interface BoneSidebarProps {
  spec: RigSpec;
  tree: BoneNode[];
  selectedBone: string | null;
  onSelectBone: (name: string | null) => void;
}

interface CategoryGroup {
  category: BoneCategory;
  bones: BoneSpec[];
}

export default function BoneSidebar({
  spec,
  selectedBone,
  onSelectBone,
}: BoneSidebarProps) {
  const [search, setSearch] = useState("");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const groups: CategoryGroup[] = useMemo(() => {
    const map = new Map<BoneCategory, BoneSpec[]>();
    for (const bone of spec.bones) {
      const list = map.get(bone.category) ?? [];
      list.push(bone);
      map.set(bone.category, list);
    }
    return CATEGORY_ORDER.filter((c) => map.has(c)).map((c) => ({
      category: c,
      bones: map.get(c)!,
    }));
  }, [spec]);

  const filteredGroups = useMemo(() => {
    if (!search.trim()) return groups;
    const q = search.toLowerCase();
    return groups
      .map((g) => ({
        ...g,
        bones: g.bones.filter((b) => b.name.toLowerCase().includes(q)),
      }))
      .filter((g) => g.bones.length > 0);
  }, [groups, search]);

  const toggleCollapse = (cat: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Bones</h2>
        <input
          className="search-input"
          type="text"
          placeholder="Filter bones..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="sidebar-body">
        {filteredGroups.map((group) => {
          const isOpen = !collapsed.has(group.category);
          return (
            <div className="category-group" key={group.category}>
              <div
                className="category-header"
                onClick={() => toggleCollapse(group.category)}
              >
                <span
                  className="category-dot"
                  style={{ background: CATEGORY_COLORS[group.category] }}
                />
                {group.category}
                <span className="category-count">({group.bones.length})</span>
                <span
                  className={`category-chevron ${isOpen ? "open" : ""}`}
                >
                  &#9654;
                </span>
              </div>
              {isOpen &&
                group.bones.map((bone) => (
                  <div
                    key={bone.name}
                    className={`bone-item ${
                      selectedBone === bone.name ? "selected" : ""
                    }`}
                    onClick={() => onSelectBone(bone.name)}
                  >
                    <span>{bone.name}</span>
                    {bone.side !== "C" && (
                      <span className="bone-side-badge">{bone.side}</span>
                    )}
                  </div>
                ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
