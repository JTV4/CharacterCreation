#!/usr/bin/env python3
"""
upload_armor_to_cloudinary.py
=============================

Uploads the weighted .glb files for the 12 main armor sets
(6 metal + 6 mage) into Cloudinary under the existing GrindScape
inventory folder hierarchy:

    Inventory/Boots/
    Inventory/Gloves/
    Inventory/Helmets/      <-- both metal helmets and mage hats land here
    Inventory/LowerBody/
    Inventory/UpperBody/

This Cloudinary account uses *fixed folders* (the visible folder is the
`asset_folder` parameter; it is independent of `public_id`).  Existing
GrindScape items use flat public_ids (e.g. `purple_ranged_boots_cs1hlg`)
with `asset_folder='Inventory/Boots'`, so we follow the same pattern:
public_id is just the basename (e.g. `IronBoots`) and asset_folder is
the matching `Inventory/<Category>` path.

Credentials
-----------
The script reads Cloudinary credentials from environment variables
(or from a .env file at the repo root):

    CLOUDINARY_CLOUD_NAME   (defaults to "dyd9wffl9")
    CLOUDINARY_API_KEY      (required)
    CLOUDINARY_API_SECRET   (required)

You can also set CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
which the SDK auto-parses.

Usage
-----
    # Dry-run -- print every planned upload without touching Cloudinary
    python3 upload_armor_to_cloudinary.py --dry-run

    # Real upload (skips assets that already exist unless --overwrite)
    python3 upload_armor_to_cloudinary.py

    # Only one armor set
    python3 upload_armor_to_cloudinary.py --only iron
    python3 upload_armor_to_cloudinary.py --only leather_mage

    # Re-upload everything, overwriting existing public_ids
    python3 upload_armor_to_cloudinary.py --overwrite

    # Write a JSON report of public_id -> secure_url for spec patching
    python3 upload_armor_to_cloudinary.py --report cloudinary_urls.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# -------- credentials ---------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(REPO_ROOT / ".env.local", override=False)
except ImportError:
    pass

DEFAULT_CLOUD_NAME = "dyd9wffl9"

# -------- file -> Cloudinary destination map ----------------------------

EQUIP_DIR = REPO_ROOT / "viewer" / "public" / "equipment" / "Female"

# Cloudinary folder names use GrindScape's existing capitalization:
#   Helmets (plural), UpperBody / LowerBody (capital B).
# These are the actual asset_folder values items will be filed under.
CATEGORY_FOLDER = {
    "Helmet":    "Helmets",
    "Upperbody": "UpperBody",
    "Gloves":    "Gloves",
    "Lowerbody": "LowerBody",
    "Boots":     "Boots",
}

# Each tuple: (set_id, category_key, source_file, public_id_basename)
# category_key matches CATEGORY_FOLDER above; public_id is just the
# basename (e.g. "IronBoots") -- no folder prefix, no .glb extension.
ASSETS: List[Tuple[str, str, Path, str]] = []


def _add(set_id: str, category: str, src: str, base: str) -> None:
    ASSETS.append((set_id, category, EQUIP_DIR / src, base))


# ---- Metal armor (6 sets x 5 pieces) -----------------------------------
# Filenames standardised: <Metal>Helmet, <Metal>Platebody, <Metal>Gloves,
# <Metal>Plateskirt, <Metal>Boots.

_METALS = ["Iron", "Steel", "Gold", "Titanium", "Tungsten", "Luminous"]

for metal in _METALS:
    set_id = f"{metal.lower()}_armor"
    _add(set_id, "Helmet",    f"Hats/{metal}HelmetWeighted.glb",          f"{metal}Helmet")
    _add(set_id, "Upperbody", f"Upperbody/{metal}PlatebodyWeighted.glb",  f"{metal}Platebody")
    _add(set_id, "Gloves",    f"Gloves/{metal}GlovesWeighted.glb",        f"{metal}Gloves")
    _add(set_id, "Lowerbody", f"Lowerbody/{metal}PlateskirtWeighted.glb", f"{metal}Plateskirt")
    _add(set_id, "Boots",     f"Boots/{metal}BootsWeighted.glb",          f"{metal}Boots")

# ---- Mage armor (6 sets x 5 pieces) ------------------------------------
# Mage filenames: <Color>MageHat, <Color>MageTop, <Color>MageGloves,
# <Color>MageLowerbody (in /Robes), <Color>MageBoots.
# Hats go into Cloudinary's "Helmets" folder per the user's request.

_MAGE_COLORS = ["Leather", "Green", "Blue", "Red", "Black", "Purple"]

for color in _MAGE_COLORS:
    set_id = f"{color.lower()}_mage"
    _add(set_id, "Helmet",    f"Hats/{color}MageHatWeighted.glb",        f"{color}MageHat")
    _add(set_id, "Upperbody", f"Upperbody/{color}MageTopWeighted.glb",   f"{color}MageTop")
    _add(set_id, "Gloves",    f"Gloves/{color}MageGlovesWeighted.glb",   f"{color}MageGloves")
    _add(set_id, "Lowerbody", f"Robes/{color}MageLowerbodyWeighted.glb", f"{color}MageLowerbody")
    _add(set_id, "Boots",     f"Boots/{color}MageBootsWeighted.glb",     f"{color}MageBoots")


# -------- helpers -------------------------------------------------------

def _public_id(category: str, base: str) -> str:
    """Cloudinary public_id for an asset.

    We use a flat basename (e.g. "IronBoots") -- no folder prefix, no
    extension.  In fixed-folders mode, folder placement is controlled by
    the `asset_folder` upload parameter (see _asset_folder()), and
    Cloudinary auto-appends the .glb format to the URL.

    This matches GrindScape's existing items, e.g. public_id
    `purple_ranged_boots_cs1hlg` filed under asset_folder
    `Inventory/Boots`, served as `.../purple_ranged_boots_cs1hlg.glb`.
    """
    return base


def _asset_folder(category: str) -> str:
    """Cloudinary asset_folder (visible folder placement) for an asset."""
    folder_name = CATEGORY_FOLDER[category]
    return f"Inventory/{folder_name}"


def _validate_files() -> List[str]:
    missing: List[str] = []
    for _set_id, _cat, src_path, _base in ASSETS:
        if not src_path.exists():
            missing.append(str(src_path.relative_to(REPO_ROOT)))
    return missing


def _filter_assets(only: Optional[str]) -> List[Tuple[str, str, Path, str]]:
    if not only:
        return list(ASSETS)
    only_norm = only.strip().lower().replace("-", "_")
    return [a for a in ASSETS if a[0] == only_norm]


def _list_known_sets() -> List[str]:
    seen: List[str] = []
    for set_id, *_ in ASSETS:
        if set_id not in seen:
            seen.append(set_id)
    return seen


# -------- main ----------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="Upload one set only (e.g. iron, steel, leather_mage). Default: all.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned uploads without contacting Cloudinary.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing assets on Cloudinary.")
    parser.add_argument("--report", metavar="FILE", help="Write a JSON map {public_id: secure_url} after upload.")
    parser.add_argument("--cloud-name", default=os.environ.get("CLOUDINARY_CLOUD_NAME", DEFAULT_CLOUD_NAME))
    parser.add_argument("--api-key", default=os.environ.get("CLOUDINARY_API_KEY"))
    parser.add_argument("--api-secret", default=os.environ.get("CLOUDINARY_API_SECRET"))
    args = parser.parse_args(argv)

    # 1. Validate local files first
    missing = _validate_files()
    if missing:
        print("ERROR: missing local source files:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 2

    plan = _filter_assets(args.only)
    if args.only and not plan:
        print(f"ERROR: --only={args.only!r} matches nothing. Known sets:", file=sys.stderr)
        for s in _list_known_sets():
            print(f"  - {s}", file=sys.stderr)
        return 2

    print(f"Cloud name: {args.cloud_name}")
    print(f"Assets queued: {len(plan)}")
    print(f"Dry run: {args.dry_run}    Overwrite: {args.overwrite}")
    print()

    # 2. Dry-run path -- no SDK / network needed
    if args.dry_run:
        for set_id, category, src_path, base in plan:
            pid = _public_id(category, base)
            af = _asset_folder(category)
            rel = src_path.relative_to(REPO_ROOT)
            print(f"  [DRY] {rel}  ->  asset_folder={af}  public_id={pid}")
        return 0

    # 3. Real upload -- need credentials + SDK
    if not args.api_key or not args.api_secret:
        url_var = os.environ.get("CLOUDINARY_URL")
        if not url_var:
            print(
                "ERROR: Cloudinary credentials not found.\n"
                "Set CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET in the\n"
                "environment, or in a .env file at the repo root, or set\n"
                "CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME.\n",
                file=sys.stderr,
            )
            return 3

    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        print("ERROR: cloudinary SDK not installed. Run: pip install cloudinary", file=sys.stderr)
        return 4

    if args.api_key and args.api_secret:
        cloudinary.config(
            cloud_name=args.cloud_name,
            api_key=args.api_key,
            api_secret=args.api_secret,
            secure=True,
        )
    # else: SDK reads CLOUDINARY_URL automatically.

    report: Dict[str, str] = {}
    failures: List[Tuple[str, str]] = []

    for i, (set_id, category, src_path, base) in enumerate(plan, 1):
        pid = _public_id(category, base)
        af = _asset_folder(category)
        rel = src_path.relative_to(REPO_ROOT)
        print(f"[{i:>2}/{len(plan)}] {rel}  ->  {af}/{pid}", flush=True)
        try:
            result = cloudinary.uploader.upload(
                str(src_path),
                public_id=pid,
                asset_folder=af,
                resource_type="image",
                use_filename=False,
                unique_filename=False,
                overwrite=bool(args.overwrite),
                invalidate=bool(args.overwrite),
            )
            url = result.get("secure_url") or result.get("url") or ""
            # report key uses asset_folder/public_id form so we know
            # both the visible folder and the asset name.
            report[f"{af}/{pid}"] = url
            print(f"        OK  {url}")
        except Exception as exc:  # noqa: BLE001
            print(f"        FAIL  {exc}")
            failures.append((f"{af}/{pid}", str(exc)))

    print()
    print(f"Uploaded: {len(report)}    Failed: {len(failures)}")

    if args.report:
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
