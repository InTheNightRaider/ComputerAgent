from __future__ import annotations

import platform
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / 'src-tauri' / 'target' / 'release' / 'bundle'

candidates = []
if platform.system() == 'Windows':
    candidates = list(BUNDLE_DIR.rglob('ComputerAgent.exe'))
elif platform.system() == 'Darwin':
    candidates = list(BUNDLE_DIR.rglob('ComputerAgent.app/Contents/MacOS/ComputerAgent'))
else:
    candidates = list(BUNDLE_DIR.rglob('computeragent')) + list(BUNDLE_DIR.rglob('ComputerAgent'))

if not candidates:
    raise SystemExit('No built ComputerAgent binary was found. Run the package script first.')

subprocess.Popen([str(candidates[0])])
print(f'Launched {candidates[0]}')
