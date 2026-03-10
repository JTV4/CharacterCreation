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
}

export interface AnimManifest {
  characters: CharacterManifestEntry[];
  animations: AnimManifestEntry[];
}
