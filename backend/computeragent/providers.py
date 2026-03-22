from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .install_state import InstallStateManager
from .model_catalog import load_model_catalog, summarize_model_catalog


@dataclass
class ProviderConfig:
    provider: str
    endpoint: str
    model_mode: str
    repo_root: Path | None = None
    data_dir: Path | None = None
    catalog_path: str = 'shared/model-stack-8gb.json'


class LLMProviderAdapter:
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.repo_root = self.config.repo_root or Path(__file__).resolve().parents[2]
        self.data_dir = self.config.data_dir or (self.repo_root / 'backend' / 'runtime')
        self.catalog = load_model_catalog(self.repo_root, self.config.catalog_path)
        self.install_state = InstallStateManager(self.data_dir, self.repo_root)

    def describe(self) -> dict[str, object]:
        catalog = summarize_model_catalog(self.catalog)
        validation = self.install_state.validate_stack(self.catalog, self.config.endpoint)
        return {
            'provider': self.config.provider,
            'endpoint': self.config.endpoint,
            'model_mode': self.config.model_mode,
            'status': 'runnable' if validation['planning_runtime']['runnable'] else 'configured',
            'message': 'The unified agent can use deterministic planning now and can switch to the local 8GB stack when required artifacts and the local endpoint are available.',
            'catalog': catalog,
            'validation': validation,
        }

    def validate(self) -> dict[str, Any]:
        return self.install_state.validate_stack(self.catalog, self.config.endpoint)

    def generate_planning_text(self, prompt: str, system_prompt: str) -> str:
        validation = self.validate()
        if not validation['planning_runtime']['runnable']:
            missing = ', '.join(item['id'] for item in validation['planning_runtime']['missing_components']) or validation['planning_runtime']['endpoint']['detail']
            raise RuntimeError(f'Local planning runtime is not runnable yet: {missing}')
        payload = {
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.2,
        }
        request = urllib.request.Request(
            self.config.endpoint.rstrip('/') + '/v1/chat/completions',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        try:
            return str(data['choices'][0]['message']['content']).strip()
        except (KeyError, IndexError, TypeError) as exc:  # noqa: PERF203
            raise RuntimeError(f'Unexpected local provider response: {data}') from exc
