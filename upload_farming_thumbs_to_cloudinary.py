#!/usr/bin/env python3
"""Upload farming vessel thumbnails to Inventory/Tools/Farming on Cloudinary."""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent
THUMB_DIR = REPO / "viewer/public/tools/farming/thumbs"
REPORT = REPO / "cloudinary_thumbnail_urls.json"
ASSET_FOLDER = "Inventory/Tools/Farming"

try:
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    load_dotenv(REPO / ".env.local", override=False)
except ImportError:
    pass

import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME", "dyd9wffl9"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True,
)

report = {}
if REPORT.exists():
    report = json.loads(REPORT.read_text())

for png in sorted(THUMB_DIR.glob("*_thumb.png")):
    pid = png.stem
    print(f"Uploading {png.name} -> {ASSET_FOLDER}/{pid}")
    result = cloudinary.uploader.upload(
        str(png),
        public_id=pid,
        asset_folder=ASSET_FOLDER,
        resource_type="image",
        use_filename=False,
        unique_filename=False,
        overwrite=True,
        invalidate=True,
    )
    url = result.get("secure_url") or result.get("url") or ""
    report[f"{ASSET_FOLDER}/{pid}"] = url
    print(f"  {url}")

REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(f"Wrote {REPORT}")
