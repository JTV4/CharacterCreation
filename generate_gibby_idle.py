"""
generate_gibby_idle.py
======================
Bakes an ``idle`` clip into ``viewer/public/NPCs/Gibby.glb``.

Reads the un-animated-beyond-Walking author source at
``~/Desktop/Characters/Gibby.glb`` so re-runs stay compact.

Idempotent: always rebuilds from the author source.

Run:
  python3 generate_gibby_idle.py
"""

from __future__ import annotations

import json
import os
import struct
import sys

import extract_npc_animations as npc

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE_GLB = os.path.expanduser("~/Desktop/Characters/Gibby.glb")
OUT_GLB = os.path.join(REPO_ROOT, "viewer/public/NPCs/Gibby.glb")
CLIP_NAME = "idle"


def delta_tracks_to_absolute(delta_tracks, gltf_json):
    abs_tracks = []
    for track in delta_tracks:
        kind = "rotation" if track["property"] == "rotation" else "translation"
        rest = npc.get_bone_rest(gltf_json, track["bone"], kind)
        keyframes = []
        for kf in track["keyframes"]:
            if track["property"] == "rotation":
                value = npc.quat_normalize(npc.quat_mul(rest, kf["value"]))
            else:
                value = [rest[i] + kf["value"][i] for i in range(3)]
            keyframes.append({"time": kf["time"], "value": value})
        abs_tracks.append({**track, "keyframes": keyframes})
    return abs_tracks


def _pad4(buf: bytes, pad: bytes) -> bytes:
    extra = (4 - (len(buf) % 4)) % 4
    return buf + pad * extra


def append_f32(bin_blob: bytearray, values) -> tuple[int, int]:
    """Append tightly packed float32s. Returns (byteOffset, byteLength)."""
    while len(bin_blob) % 4:
        bin_blob.append(0)
    offset = len(bin_blob)
    flat: list[float] = []
    for v in values:
        if isinstance(v, (int, float)):
            flat.append(float(v))
        else:
            flat.extend(float(x) for x in v)
    packed = struct.pack(f"<{len(flat)}f", *flat)
    bin_blob.extend(packed)
    return offset, len(packed)


def add_accessor(gltf, bin_blob, values, typ: str):
    offset, length = append_f32(bin_blob, values)
    bv_idx = len(gltf["bufferViews"])
    gltf["bufferViews"].append({
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": length,
    })
    count = len(values)
    if typ == "SCALAR":
        nums = [float(v) for v in values]
        acc = {
            "bufferView": bv_idx,
            "componentType": 5126,
            "count": count,
            "type": "SCALAR",
            "min": [min(nums)],
            "max": [max(nums)],
        }
    else:
        acc = {
            "bufferView": bv_idx,
            "componentType": 5126,
            "count": count,
            "type": typ,
        }
    acc_idx = len(gltf["accessors"])
    gltf["accessors"].append(acc)
    return acc_idx


def embed_idle(gltf, bin_blob, abs_tracks, duration: float):
    gltf["animations"] = [
        a for a in gltf.get("animations", []) if a.get("name") != CLIP_NAME
    ]
    name_to_idx = {
        n.get("name"): i for i, n in enumerate(gltf["nodes"]) if n.get("name")
    }

    samplers = []
    channels = []
    times_cache: dict[tuple[float, ...], int] = {}

    for track in abs_tracks:
        node_idx = name_to_idx.get(track["bone"])
        if node_idx is None:
            print(f"  skip unknown bone {track['bone']!r}")
            continue
        times = tuple(round(kf["time"], 6) for kf in track["keyframes"])
        if times not in times_cache:
            times_cache[times] = add_accessor(
                gltf, bin_blob, list(times), "SCALAR",
            )
        typ = "VEC4" if track["property"] == "rotation" else "VEC3"
        out_idx = add_accessor(
            gltf, bin_blob, [kf["value"] for kf in track["keyframes"]], typ,
        )
        samp_idx = len(samplers)
        samplers.append({
            "input": times_cache[times],
            "interpolation": "LINEAR",
            "output": out_idx,
        })
        path = "rotation" if track["property"] == "rotation" else "translation"
        channels.append({
            "sampler": samp_idx,
            "target": {"node": node_idx, "path": path},
        })

    gltf["animations"].append({
        "name": CLIP_NAME,
        "samplers": samplers,
        "channels": channels,
    })
    gltf["buffers"][0]["byteLength"] = len(bin_blob)
    print(f"  embedded {CLIP_NAME!r}: {len(channels)} channels, {duration:.1f}s")


def write_glb(path, gltf, bin_blob: bytes):
    json_bytes = _pad4(
        json.dumps(gltf, separators=(",", ":")).encode("utf-8"),
        b" ",
    )
    bin_bytes = _pad4(bytes(bin_blob), b"\x00")
    length = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    header = struct.pack("<4sII", b"glTF", 2, length)
    json_chunk = struct.pack("<I4s", len(json_bytes), b"JSON") + json_bytes
    bin_chunk = struct.pack("<I4s", len(bin_bytes), b"BIN\x00") + bin_bytes
    with open(path, "wb") as f:
        f.write(header + json_chunk + bin_chunk)
    print(f"  wrote {os.path.relpath(path, REPO_ROOT)}  ({length} bytes)")


def main():
    if not os.path.isfile(SOURCE_GLB):
        raise SystemExit(f"author source missing: {SOURCE_GLB}")
    print(f"source: {SOURCE_GLB}")
    print(f"output: {os.path.relpath(OUT_GLB, REPO_ROOT)}")
    gltf, bin_data = npc.parse_glb(SOURCE_GLB)
    bin_blob = bytearray(bin_data)

    walk_tracks, walk_dur = npc.extract_walking_tracks(
        gltf, bin_data, "Walking",
    )
    print(f"  walking source: {len(walk_tracks)} tracks, {walk_dur:.3f}s")

    idle_delta, idle_dur = npc.build_idle_delta_tracks(walk_tracks, gltf)
    idle_abs = delta_tracks_to_absolute(idle_delta, gltf)
    embed_idle(gltf, bin_blob, idle_abs, idle_dur)
    write_glb(OUT_GLB, gltf, bin_blob)
    print("done")


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
