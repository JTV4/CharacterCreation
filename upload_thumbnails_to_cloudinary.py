#!/usr/bin/env python3
"""
upload_thumbnails_to_cloudinary.py
==================================

Uploads the 90 inventory thumbnail PNGs from ~/Desktop/Shells/BaseFemale/
into the same GrindScape Cloudinary folders that hold the matching .glb
models (Inventory/Helmets, UpperBody, Gloves, LowerBody, Boots).

To avoid colliding with existing `.glb` public_ids in those folders
(e.g. `LeatherMageHat`), every thumbnail gets a `_thumb` suffix on its
public_id.  The other agent can derive a thumbnail URL from a .glb URL
by swapping `.glb` for `_thumb.png`.

    .glb        -> https://res.cloudinary.com/dyd9wffl9/image/upload/v.../LeatherMageHat.glb
    thumbnail   -> https://res.cloudinary.com/dyd9wffl9/image/upload/v.../LeatherMageHat_thumb.png

Folder mapping (per user):

    Head/Thumbnails/         -> Inventory/Helmets   (metal helmets)
    Hats/Thumbnails/         -> Inventory/Helmets   (mage + ranged hats)
    Upperbody/Thumbnails/    -> Inventory/UpperBody
    Gloves/Thumbnails/       -> Inventory/Gloves
    Lowerbody/Thumbnails/    -> Inventory/LowerBody
    Boots/Thumbnails/        -> Inventory/Boots

Reads credentials from .env (CLOUDINARY_CLOUD_NAME / API_KEY / API_SECRET).
Writes a JSON report keyed by "Inventory/<Folder>/<public_id>".

Usage:
    python3 upload_thumbnails_to_cloudinary.py                # upload all 90
    python3 upload_thumbnails_to_cloudinary.py --dry-run      # preview
    python3 upload_thumbnails_to_cloudinary.py --overwrite    # replace existing
    python3 upload_thumbnails_to_cloudinary.py --report cloudinary_thumbnail_urls.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / ".env.local", override=False)
except ImportError:
    pass

DEFAULT_CLOUD_NAME = "dyd9wffl9"

# Source root for the local PNG thumbnails
SHELL_ROOT = Path("/Users/stephenvillavaso/Desktop/Shells/BaseFemale")

# (source_subdir, cloudinary_asset_folder)
# Both Head/ and Hats/ thumbnails land in the same Cloudinary
# Inventory/Helmets folder.
SOURCES: List[Tuple[str, str]] = [
    ("Head/Thumbnails",       "Helmets"),
    ("Hats/Thumbnails",       "Helmets"),
    ("Upperbody/Thumbnails",  "UpperBody"),
    ("Gloves/Thumbnails",     "Gloves"),
    ("Lowerbody/Thumbnails",  "LowerBody"),
    ("Boots/Thumbnails",      "Boots"),
]

THUMB_SUFFIX = "_thumb"


def _collect_assets() -> List[Tuple[Path, str, str]]:
    """Return [(src_png_path, asset_folder, public_id)] for every PNG."""
    assets: List[Tuple[Path, str, str]] = []
    for subdir, category in SOURCES:
        src_dir = SHELL_ROOT / subdir
        if not src_dir.is_dir():
            print(f"  WARN: source dir missing: {src_dir}", file=sys.stderr)
            continue
        for png in sorted(src_dir.glob("*.png")):
            base = png.stem  # filename without .png
            public_id = f"{base}{THUMB_SUFFIX}"
            asset_folder = f"Inventory/{category}"
            assets.append((png, asset_folder, public_id))
    return assets


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned uploads without contacting Cloudinary.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing assets on Cloudinary.")
    parser.add_argument("--report", metavar="FILE",
                        default="cloudinary_thumbnail_urls.json",
                        help="JSON map written after upload (default: cloudinary_thumbnail_urls.json).")
    parser.add_argument("--cloud-name", default=os.environ.get("CLOUDINARY_CLOUD_NAME", DEFAULT_CLOUD_NAME))
    parser.add_argument("--api-key", default=os.environ.get("CLOUDINARY_API_KEY"))
    parser.add_argument("--api-secret", default=os.environ.get("CLOUDINARY_API_SECRET"))
    args = parser.parse_args(argv)

    plan = _collect_assets()
    if not plan:
        print("ERROR: no source PNGs found.", file=sys.stderr)
        return 2

    # Sanity: alert on any public_id duplicates within the plan
    seen: Dict[str, Path] = {}
    dups: List[Tuple[str, Path, Path]] = []
    for src, af, pid in plan:
        key = f"{af}/{pid}"
        if key in seen:
            dups.append((key, seen[key], src))
        else:
            seen[key] = src
    if dups:
        print("ERROR: duplicate (asset_folder, public_id) pairs detected:", file=sys.stderr)
        for k, a, b in dups:
            print(f"  {k}: {a}  AND  {b}", file=sys.stderr)
        return 2

    print(f"Cloud name: {args.cloud_name}")
    print(f"Thumbnails queued: {len(plan)}")
    print(f"Dry run: {args.dry_run}    Overwrite: {args.overwrite}")
    print()

    if args.dry_run:
        for src, af, pid in plan:
            rel = src.name
            print(f"  [DRY] {rel}  ->  asset_folder={af}  public_id={pid}")
        return 0

    if not args.api_key or not args.api_secret:
        if not os.environ.get("CLOUDINARY_URL"):
            print(
                "ERROR: Cloudinary credentials not found. Set CLOUDINARY_API_KEY\n"
                "and CLOUDINARY_API_SECRET in .env at the repo root.\n",
                file=sys.stderr,
            )
            return 3

    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        print("ERROR: cloudinary SDK not installed. pip install cloudinary", file=sys.stderr)
        return 4

    if args.api_key and args.api_secret:
        cloudinary.config(
            cloud_name=args.cloud_name,
            api_key=args.api_key,
            api_secret=args.api_secret,
            secure=True,
        )

    report: Dict[str, str] = {}
    failures: List[Tuple[str, str]] = []

    for i, (src, af, pid) in enumerate(plan, 1):
        rel = src.name
        print(f"[{i:>2}/{len(plan)}] {rel}  ->  {af}/{pid}", flush=True)
        try:
            result = cloudinary.uploader.upload(
                str(src),
                public_id=pid,
                asset_folder=af,
                resource_type="image",
                use_filename=False,
                unique_filename=False,
                overwrite=bool(args.overwrite),
                invalidate=bool(args.overwrite),
            )
            url = result.get("secure_url") or result.get("url") or ""
            report[f"{af}/{pid}"] = url
            print(f"        OK  {url}")
        except Exception as exc:  # noqa: BLE001
            print(f"        FAIL  {exc}")
            failures.append((f"{af}/{pid}", str(exc)))

    print()
    print(f"Uploaded: {len(report)}    Failed: {len(failures)}")

    out = REPO_ROOT / args.report
    out.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"Wrote URL report -> {out.relative_to(REPO_ROOT)}")

    if failures:
        print("\nFailures:", file=sys.stderr)
        for pid, msg in failures:
            print(f"  - {pid}: {msg}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
