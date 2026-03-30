"""
extract_lower_body_shell.py
===========================
Re-extracts shell_lower_body.glb with:
  - 18 mm outward displacement (more clearance for extreme leg-kick poses)
  - Wall solidify disabled  (prevents spike artifacts at boundary caps)

Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
      --python extract_lower_body_shell.py
"""

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "equipment", "factory"))

import body_shell_extractor as bse

bse.SHELL_THICKNESS["lower_body"]      = 0.028   # 28 mm
bse.SHELL_WALL_THICKNESS["lower_body"] = 0.0     # disable wall solidify

ROOT = os.path.dirname(os.path.abspath(__file__))

bse.extract_shells(
    rig_blend        = os.path.join(ROOT, "rig/output/rig.blend"),
    body_glb         = os.path.join(ROOT, "rig/CharacterMesh/BaseFemale.glb"),
    output_dir       = os.path.join(ROOT, "equipment/output/shells/"),
    slot_types       = ["lower_body"],
    thickness        = 0,
    weight_threshold = 0.1,
    game_dir         = None,
)
