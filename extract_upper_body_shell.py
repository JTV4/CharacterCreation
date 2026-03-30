"""
extract_upper_body_shell.py
===========================
Re-extracts shell_upper_body.glb with:
  - 20 mm outward displacement (enough clearance for animated arm poses)
  - Wall solidify disabled  (the 2 mm wall was creating spikes at wrist/neck caps)

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python extract_upper_body_shell.py
"""

import sys, os

# Patch the factory module so our overrides take effect before it uses them
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "equipment", "factory"))

import body_shell_extractor as bse

# ── Overrides ─────────────────────────────────────────────────────────────────
bse.SHELL_THICKNESS["upper_body"]      = 0.020   # 20 mm
bse.SHELL_WALL_THICKNESS["upper_body"] = 0.0     # disable wall solidify (no spike risk)

ROOT = os.path.dirname(os.path.abspath(__file__))

bse.extract_shells(
    rig_blend       = os.path.join(ROOT, "rig/output/rig.blend"),
    body_glb        = os.path.join(ROOT, "rig/CharacterMesh/BaseFemale.glb"),
    output_dir      = os.path.join(ROOT, "equipment/output/shells/"),
    slot_types      = ["upper_body"],
    thickness       = 0,      # 0 = use per-slot defaults (which we patched above)
    weight_threshold= 0.1,
    game_dir        = None,
)
