"""
run_shells_v2.py
================
Regenerates all five shell pieces (Shells V2) using the improved
smooth-normal displacement algorithm in body_shell_extractor.py.

Layering order baked into thickness values:
    Head       6 mm  – thinnest, form-fitting skull cap
    Lower body 18 mm – base layer (legs / waist)
    Upper body 20 mm – laps over lower_body at waist
    Gloves     24 mm – over upper_body at wrists
    Boots      26 mm – over lower_body at shins / ankles

Run with:
    /Applications/Blender.app/Contents/MacOS/Blender --background \\
        --python run_shells_v2.py
"""

import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "equipment", "factory"))

import body_shell_extractor as bse

bse.extract_shells(
    rig_blend        = os.path.join(ROOT, "rig/output/rig.blend"),
    body_glb         = os.path.join(ROOT, "rig/CharacterMesh/BaseFemale.glb"),
    output_dir       = os.path.join(ROOT, "equipment/output/shells/"),
    slot_types       = ["head", "upper_body", "lower_body", "gloves", "boots"],
    thickness        = 0,          # 0 = use per-slot SHELL_THICKNESS defaults
    weight_threshold = 0.1,
    game_dir         = None,
)
