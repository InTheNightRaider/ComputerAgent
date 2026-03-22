#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.computeragent.config import get_data_dir
from backend.computeragent.install_state import InstallStateManager
from backend.computeragent.model_catalog import load_model_catalog

DEFAULT_MANIFEST = REPO_ROOT / 'shared' / 'model-stack-8gb.json'


def main() -> None:
    parser = argparse.ArgumentParser(description='Prepare or install the open-source model/runtime stack manifests for ComputerAgent.')
    parser.add_argument('--manifest', default=str(DEFAULT_MANIFEST), help='Path to the model catalog JSON file.')
    parser.add_argument('--allow-oversized', action='store_true', help='Also prepare deferred components that are not in the default 8GB profile.')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be prepared without persisting install state.')
    parser.add_argument('--download-missing', action='store_true', help='Create placeholder local targets for missing required artifacts.')
    parser.add_argument('--local-artifact', action='append', default=[], help='Register a local artifact in the form component_id:artifact_key:path')
    args = parser.parse_args()

    overrides: dict[str, dict[str, str]] = {}
    for item in args.local_artifact:
        component_id, artifact_key, path = item.split(':', 2)
        overrides.setdefault(component_id, {})[artifact_key] = path

    catalog = load_model_catalog(REPO_ROOT, args.manifest)
    manager = InstallStateManager(get_data_dir(), REPO_ROOT)
    result = manager.install_components(
        catalog,
        dry_run=args.dry_run,
        allow_oversized=args.allow_oversized,
        local_overrides=overrides,
        download_missing=args.download_missing,
    )
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
