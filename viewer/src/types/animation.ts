export interface AnimKeyframe {
  time: number;
  value: number[];
}

export interface AnimTrack {
  bone: string;
  property: "rotation" | "position";
  interpolation: "linear" | "step";
  keyframes: AnimKeyframe[];
}

export interface AnimMeta {
  name: string;
  id: string;
  duration: number;
  fps: number;
  loop: boolean;
  /** When true, keyframe values are absolute (not deltas from rest pose). */
  absolute?: boolean;
}

export interface AnimSpec {
  meta: AnimMeta;
  tracks: AnimTrack[];
}

export interface CharacterManifestEntry {
  id: string;
  model: string;
  defaultAnimation: string;
}

export interface AnimManifestEntry {
  id: string;
  file: string;
  loop?: boolean;
  /**
   * Optional category tag.  Used by the viewer to filter the animation
   * picker so that, e.g., only NPC-rig animations show up while an NPC is
   * active.  Animations with no category default to the player rig
   * (Female/Male/V2 series) and are hidden when an NPC is selected.
   */
  category?: "npc";
  /**
   * Optional character-id binding.  When set, this animation is only
   * shown for the matching character (e.g. "FinnFemale" → only visible
   * when Finn is the active NPC).  Used for per-character walks whose
   * Hips bob is tuned to that specific character's rest height.
   * Animations without `for_character` are visible across all
   * characters that match their `category`.
   */
  for_character?: string;
}

export interface AnimManifest {
  characters: CharacterManifestEntry[];
  animations: AnimManifestEntry[];
}
