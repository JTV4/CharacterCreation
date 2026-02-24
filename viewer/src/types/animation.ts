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
}

export interface AnimSpec {
  meta: AnimMeta;
  tracks: AnimTrack[];
}

export interface AnimManifest {
  animations: { id: string; file: string }[];
}
