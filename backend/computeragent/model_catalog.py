from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_model_catalog(repo_root: Path, path: str = 'shared/model-stack-8gb.json') -> dict[str, Any]:
    catalog_path = Path(path)
    if not catalog_path.is_absolute():
        catalog_path = (repo_root / catalog_path).resolve()
    return json.loads(catalog_path.read_text(encoding='utf-8'))


def get_component(catalog: dict[str, Any], component_id: str) -> dict[str, Any] | None:
    return next((item for item in catalog.get('components', []) if item.get('id') == component_id), None)


def summarize_model_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    components = catalog.get('components', [])
    enabled = [item for item in components if item.get('default_enabled')]
    deferred = [item for item in components if not item.get('default_enabled')]
    return {
        'profile': catalog.get('profile', 'unknown'),
        'open_source_only': bool(catalog.get('open_source_only', True)),
        'planning_required_components': list(catalog.get('default_runtime', {}).get('planning_required_components', [])),
        'full_stack_required_components': list(catalog.get('default_runtime', {}).get('full_stack_required_components', [])),
        'default_enabled_components': [
            {
                'id': item['id'],
                'name': item['name'],
                'runtime': item['runtime'],
                'reason': item.get('selection_reason', ''),
            }
            for item in enabled
        ],
        'deferred_components': [
            {
                'id': item['id'],
                'name': item['name'],
                'reason': item.get('selection_reason', ''),
            }
            for item in deferred
        ],
    }
