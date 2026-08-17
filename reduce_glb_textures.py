"""
reduce_glb_textures.py
======================
Downscale embedded textures in a GLB from any size to a target size (default
1024×1024) and write a new GLB with the shrunken textures.  Used to keep
Meshy-textured pieces light enough to load smoothly in the viewer without
having to round-trip them through Blender.

The script does NOT touch geometry, skinning, animations, materials,
samplers, or texture indices — it only rewrites the binary image bytes
embedded in the GLB and updates the corresponding bufferView byteOffset /
byteLength entries.  Image format is preserved (JPEG stays JPEG, PNG stays
PNG) so material setups don't need to be regenerated.

Run:
    python3 reduce_glb_textures.py <input.glb> <output.glb> [--max=1024]
    python3 reduce_glb_textures.py --batch <input_dir> <output_dir> [--max=1024]

`--batch` mode skips files whose name starts with "Original" — those
already-textured Meshy uploads aren't the targets we want to shrink in our
typical workflow.

Alignment notes
---------------
GLB bufferViews referenced by accessors carrying vertex data MUST be aligned
on 4-byte boundaries (or 2-byte for indices).  The new BIN chunk is rebuilt
by concatenating bufferViews IN ORIGINAL INDEX ORDER, padding each section
to 4 bytes of zeroes so accessors remain correctly aligned.  Image
bufferViews have no alignment requirement, but we pad them too — costs at
most 3 bytes per image and keeps the code simple.
"""
import argparse
import json
import os
import struct
import sys
from io import BytesIO
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required.  Install with `pip install Pillow`.")
    sys.exit(1)


GLB_MAGIC = b"glTF"
CHUNK_JSON = 0x4E4F534A  # "JSON"
CHUNK_BIN  = 0x004E4942  # "BIN\0"


def _pad4(n: int) -> int:
    """Round up to the next multiple of 4."""
    return (n + 3) & ~3


def _read_glb(path: str):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != GLB_MAGIC:
        raise ValueError(f"{path}: not a GLB (missing magic)")
    version = struct.unpack("<I", data[4:8])[0]
    total_len = struct.unpack("<I", data[8:12])[0]
    if total_len != len(data):
        # Some exporters write a slightly off total; warn but proceed.
        print(f"  WARN: header total ({total_len}) != file size ({len(data)})")

    cursor = 12
    chunks = []
    while cursor < len(data):
        clen = struct.unpack("<I", data[cursor:cursor+4])[0]
        ctype = struct.unpack("<I", data[cursor+4:cursor+8])[0]
        cdata = data[cursor+8:cursor+8+clen]
        chunks.append((ctype, cdata))
        cursor += 8 + clen

    if not chunks or chunks[0][0] != CHUNK_JSON:
        raise ValueError(f"{path}: first chunk is not JSON")
    j = json.loads(chunks[0][1].decode("utf-8"))
    bin_data = b""
    for ctype, cdata in chunks[1:]:
        if ctype == CHUNK_BIN:
            bin_data = cdata
            break
    return version, j, bin_data


def _resize_image_bytes(blob: bytes, mime: str, max_size: int):
    """Decode `blob`, resize to (max_size, max_size) preserving format, and
    return (new_blob, original_size_tuple, new_size_tuple)."""
    im = Image.open(BytesIO(blob))
    orig_size = im.size
    w, h = im.size
    if max(w, h) <= max_size:
        return blob, orig_size, orig_size  # already small enough

    scale = max_size / max(w, h)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    im = im.convert(im.mode)  # ensures palette images become RGB
    im_resized = im.resize((new_w, new_h), Image.LANCZOS)

    out = BytesIO()
    if mime == "image/jpeg":
        # Meshy textures are JPEG.  Quality 88 is visually lossless for PBR
        # at 1024 and keeps file size down by ~3-4×.
        if im_resized.mode in ("RGBA", "LA"):
            im_resized = im_resized.convert("RGB")
        im_resized.save(out, format="JPEG", quality=88, optimize=True)
    elif mime == "image/png":
        im_resized.save(out, format="PNG", optimize=True)
    else:
        # Fall back to preserving the format Pillow detects.
        fmt = (im.format or "JPEG").upper()
        if fmt == "JPEG" and im_resized.mode in ("RGBA", "LA"):
            im_resized = im_resized.convert("RGB")
        im_resized.save(out, format=fmt, optimize=True)
    return out.getvalue(), orig_size, (new_w, new_h)


def reduce_one(input_path: str, output_path: str, max_size: int = 1024,
               verbose: bool = True) -> bool:
    """Reduce all embedded textures in `input_path` and write `output_path`.
    Returns True on success."""
    if verbose:
        print(f"\n=== {os.path.basename(input_path)} ===")
    version, j, bin_data = _read_glb(input_path)

    images = j.get("images", [])
    buffer_views = j.get("bufferViews", [])
    if not images:
        if verbose:
            print("  (no embedded images — copying as-is)")
        with open(input_path, "rb") as src, open(output_path, "wb") as dst:
            dst.write(src.read())
        return True

    image_bv_indices = {}  # bufferView index → (image index, mime)
    for img_idx, img in enumerate(images):
        bv_idx = img.get("bufferView")
        if bv_idx is None:
            continue
        mime = img.get("mimeType") or "image/jpeg"
        image_bv_indices[bv_idx] = (img_idx, mime)

    new_bv_data = []
    saved_bytes = 0
    total_in = 0
    total_out = 0
    for bv_idx, bv in enumerate(buffer_views):
        offset = bv.get("byteOffset", 0)
        length = bv.get("byteLength", 0)
        original = bin_data[offset:offset+length]

        if bv_idx in image_bv_indices:
            img_idx, mime = image_bv_indices[bv_idx]
            try:
                new_blob, orig_size, new_size = _resize_image_bytes(original, mime, max_size)
            except Exception as e:
                if verbose:
                    print(f"  WARN: image[{img_idx}] decode/resize failed → keeping original ({e})")
                new_blob = original
                orig_size = new_size = None
            new_bv_data.append(new_blob)
            saved_bytes += len(original) - len(new_blob)
            if verbose:
                if orig_size is None:
                    print(f"  image[{img_idx}] bv={bv_idx} kept original ({len(original)/1e6:.2f} MB)")
                else:
                    print(f"  image[{img_idx}] bv={bv_idx}  {orig_size[0]}x{orig_size[1]} "
                          f"({len(original)/1e6:.2f} MB) → {new_size[0]}x{new_size[1]} "
                          f"({len(new_blob)/1e6:.2f} MB)")
        else:
            new_bv_data.append(original)
        total_in += len(original)
        total_out += len(new_bv_data[-1])

    # Rebuild bufferView offsets/lengths and the BIN chunk.
    new_bin = bytearray()
    for bv_idx, blob in enumerate(new_bv_data):
        # Pad to 4-byte boundary before placing the next bufferView.  Vertex
        # / index accessors that point into these bufferViews need this.
        pad = _pad4(len(new_bin)) - len(new_bin)
        if pad:
            new_bin.extend(b"\x00" * pad)
        bv = buffer_views[bv_idx]
        bv["byteOffset"] = len(new_bin)
        bv["byteLength"] = len(blob)
        new_bin.extend(blob)
    # Pad the entire BIN chunk to 4-byte boundary (GLB spec).
    pad = _pad4(len(new_bin)) - len(new_bin)
    if pad:
        new_bin.extend(b"\x00" * pad)

    # Update the single buffer's byteLength to match the new BIN size.
    if j.get("buffers"):
        j["buffers"][0]["byteLength"] = len(new_bin)

    # Encode the new JSON chunk, padded to 4 bytes with spaces.
    new_json_bytes = json.dumps(j, separators=(",", ":")).encode("utf-8")
    pad = _pad4(len(new_json_bytes)) - len(new_json_bytes)
    if pad:
        new_json_bytes = new_json_bytes + b" " * pad

    # Build new GLB.
    json_chunk_header = struct.pack("<II", len(new_json_bytes), CHUNK_JSON)
    bin_chunk_header  = struct.pack("<II", len(new_bin), CHUNK_BIN)
    body = json_chunk_header + new_json_bytes + bin_chunk_header + bytes(new_bin)
    total_len = 12 + len(body)
    header = b"glTF" + struct.pack("<II", version, total_len)

    with open(output_path, "wb") as f:
        f.write(header + body)

    if verbose:
        before = os.path.getsize(input_path) / 1e6
        after  = os.path.getsize(output_path) / 1e6
        ratio  = (1.0 - after / before) * 100 if before > 0 else 0.0
        print(f"  TOTAL  {before:.2f} MB → {after:.2f} MB  ({ratio:+.1f}%)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--max", type=int, default=1024,
                    help="Target max texture dimension (default 1024)")
    ap.add_argument("--batch", action="store_true",
                    help="Treat input/output as directories and process every "
                         "non-Original*.glb file inside")
    args = ap.parse_args()

    if args.batch:
        in_dir = Path(args.input)
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        glbs = sorted(p for p in in_dir.glob("*.glb")
                      if not p.name.lower().startswith("original")
                      and not p.name.lower().startswith("originalblueranged")
                      and not p.name.lower().startswith("meshy_ai_"))
        print(f"Batch: {len(glbs)} GLBs from {in_dir} → {out_dir}")
        for src in glbs:
            dst = out_dir / src.name
            reduce_one(str(src), str(dst), args.max)
    else:
        reduce_one(args.input, args.output, args.max)


if __name__ == "__main__":
    main()
