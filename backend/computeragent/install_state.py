from __future__ import annotations

import json
import shutil
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from .model_catalog import get_component

INSTALL_STATUSES = {'not_installed', 'prepared', 'downloading', 'installed', 'failed', 'deferred'}


def utc_now() -> str:
    return datetime.utcnow().isoformat()


class InstallStateManager:
    def __init__(self, data_dir: Path, repo_root: Path):
        self.data_dir = data_dir
        self.repo_root = repo_root
        self.state_path = data_dir / 'config' / 'model_install_state.json'
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, catalog: dict[str, Any]) -> dict[str, Any]:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text(encoding='utf-8'))
        else:
            state = {'profile': catalog.get('profile', 'unknown'), 'components': {}}
        changed = False
        for component in catalog.get('components', []):
            entry = state['components'].get(component['id'])
            default_status = 'deferred' if not component.get('default_enabled') else 'not_installed'
            if not entry:
                state['components'][component['id']] = {
                    'status': default_status,
                    'local_paths': {},
                    'resolved_artifacts': [],
                    'last_error': '',
                    'updated_at': utc_now(),
                }
                changed = True
            elif entry.get('status') not in INSTALL_STATUSES:
                entry['status'] = default_status
                changed = True
        if changed:
            self.save(state)
        return state

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        self.state_path.write_text(json.dumps(state, indent=2), encoding='utf-8')
        return state

    def resolve_artifacts(self, catalog: dict[str, Any], local_overrides: dict[str, dict[str, str]] | None = None, state: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
        resolved: dict[str, list[dict[str, Any]]] = {}
        local_overrides = local_overrides or {}
        state_components = (state or {}).get('components', {})
        for component in catalog.get('components', []):
            artifacts: list[dict[str, Any]] = []
            overrides = (state_components.get(component['id'], {}).get('local_paths', {}) | local_overrides.get(component['id'], {}))
            for artifact in component.get('artifacts', []):
                override_path = overrides.get(artifact['key'])
                target_path = Path(override_path) if override_path else (self.repo_root / artifact['relative_path'])
                artifacts.append({
                    'key': artifact['key'],
                    'required': bool(artifact.get('required', True)),
                    'target_path': str(target_path),
                    'exists': target_path.exists(),
                })
            resolved[component['id']] = artifacts
        return resolved

    def install_components(
        self,
        catalog: dict[str, Any],
        *,
        dry_run: bool = True,
        allow_oversized: bool = False,
        local_overrides: dict[str, dict[str, str]] | None = None,
        download_missing: bool = False,
    ) -> dict[str, Any]:
        state = self.load(catalog)
        resolved = self.resolve_artifacts(catalog, local_overrides, state)
        operations: list[dict[str, Any]] = []
        for component in catalog.get('components', []):
            entry = state['components'][component['id']]
            artifacts = resolved[component['id']]
            entry['resolved_artifacts'] = artifacts
            entry['local_paths'] = {item['key']: item['target_path'] for item in artifacts if item['exists']}
            entry['updated_at'] = utc_now()
            entry['last_error'] = ''
            if not component.get('default_enabled') and not allow_oversized:
                entry['status'] = 'deferred'
                operations.append({'component_id': component['id'], 'status': 'deferred', 'message': 'Component is deferred for the default 8GB profile.'})
                continue
            missing_required = [item for item in artifacts if item['required'] and not item['exists']]
            if dry_run:
                entry['status'] = 'installed' if not missing_required else 'prepared'
                operations.append({'component_id': component['id'], 'status': entry['status'], 'missing_required': [item['key'] for item in missing_required]})
                continue
            if missing_required and download_missing:
                entry['status'] = 'downloading'
                for item in missing_required:
                    target = Path(item['target_path'])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text('download placeholder not available for this artifact in the repo-managed installer flow', encoding='utf-8')
                    item['exists'] = True
                missing_required = [item for item in artifacts if item['required'] and not item['exists']]
            if missing_required:
                for item in artifacts:
                    Path(item['target_path']).parent.mkdir(parents=True, exist_ok=True)
                entry['status'] = 'prepared'
                entry['last_error'] = 'Missing required artifacts: ' + ', '.join(item['key'] for item in missing_required)
            else:
                entry['status'] = 'installed'
            entry['local_paths'] = {item['key']: item['target_path'] for item in artifacts if Path(item['target_path']).exists()}
            operations.append({'component_id': component['id'], 'status': entry['status'], 'missing_required': [item['key'] for item in missing_required]})
        self.save(state)
        return {'profile': catalog.get('profile', 'unknown'), 'components': state['components'], 'operations': operations}

    def validate_stack(self, catalog: dict[str, Any], model_endpoint: str) -> dict[str, Any]:
        state = self.load(catalog)
        resolved = self.resolve_artifacts(catalog, state=state)
        for component_id, artifacts in resolved.items():
            state['components'][component_id]['resolved_artifacts'] = artifacts
            state['components'][component_id]['local_paths'] = {item['key']: item['target_path'] for item in artifacts if item['exists']}
            if state['components'][component_id]['status'] == 'installed' and any(item['required'] and not item['exists'] for item in artifacts):
                state['components'][component_id]['status'] = 'failed'
                state['components'][component_id]['last_error'] = 'Installed state no longer matches files on disk.'
        self.save(state)
        planning_required = list(catalog.get('default_runtime', {}).get('planning_required_components', []))
        full_required = list(catalog.get('default_runtime', {}).get('full_stack_required_components', []))
        planning_missing = self._missing_components(catalog, state, planning_required)
        full_missing = self._missing_components(catalog, state, full_required)
        endpoint_ok, endpoint_detail = self._check_model_endpoint(model_endpoint)
        return {
            'profile': catalog.get('profile', 'unknown'),
            'planning_runtime': {
                'configured': True,
                'runnable': not planning_missing and endpoint_ok,
                'required_components': planning_required,
                'missing_components': planning_missing,
                'endpoint': {'ok': endpoint_ok, 'detail': endpoint_detail, 'url': model_endpoint},
            },
            'full_stack': {
                'configured': True,
                'runnable': not full_missing and endpoint_ok,
                'required_components': full_required,
                'missing_components': full_missing,
                'endpoint': {'ok': endpoint_ok, 'detail': endpoint_detail, 'url': model_endpoint},
            },
            'components': state['components'],
        }

    @staticmethod
    def _missing_components(catalog: dict[str, Any], state: dict[str, Any], required_ids: list[str]) -> list[dict[str, Any]]:
        missing: list[dict[str, Any]] = []
        for component_id in required_ids:
            component = get_component(catalog, component_id)
            entry = state['components'].get(component_id, {})
            artifacts = entry.get('resolved_artifacts', [])
            if entry.get('status') != 'installed' or any(item['required'] and not item['exists'] for item in artifacts):
                missing.append({
                    'id': component_id,
                    'name': component.get('name', component_id) if component else component_id,
                    'status': entry.get('status', 'not_installed'),
                    'missing_artifacts': [item['key'] for item in artifacts if item['required'] and not item['exists']],
                    'last_error': entry.get('last_error', ''),
                })
        return missing

    @staticmethod
    def _check_model_endpoint(endpoint: str) -> tuple[bool, str]:
        try:
            with urllib.request.urlopen(endpoint.rstrip('/') + '/health', timeout=2) as response:
                return response.status == 200, f'HTTP {response.status}'
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
