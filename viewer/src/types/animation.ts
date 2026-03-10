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

export interface AnimManifestEntry {
  id: string;
  file: string;
  glb?: string;
  loop?: boolean;
}

export interface AnimManifest {
  animations: AnimManifestEntry[];
}
