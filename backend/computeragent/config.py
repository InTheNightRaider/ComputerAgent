from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_SETTINGS = {
    'planner_mode': 'mock',
    'model_mode': 'Balanced',
    'local_model_provider': 'llama.cpp',
    'local_model_endpoint': 'http://127.0.0.1:8080',
    'theme': 'dark',
    'browser_automation_enabled': True,
    'browser_mode': 'headed',
    'browser_profile_path': '',
    'preferred_docs_domains': ['framer.com', 'www.framer.com', 'docs.google.com', 'chatgpt.com', 'chat.openai.com'],
    'docs_research_enabled': True,
    'allow_community_sources': False,
    'max_research_depth': 2,
    'project_memory_enabled': True,
    'allowed_directories': [],
    'backup_location': '.agent_backups',
    'quarantine_location': '.agent_quarantine',
    'logs_export_folder': 'logs',
    'retention_runs': 10,
    'security_watched_folders': [],
    'scan_exclusions': [],
    'yara_path': '',
    'clamav_path': '',
    'voice_mode': 'whisper_tiny',
    'require_approval_before_foreground_control': True,
    'maximum_concurrent_background_jobs': 2,
    'default_dry_run': True,
    'policy_whitelist_path': 'shared/policy-whitelist.json',
    'model_catalog_path': 'shared/model-stack-8gb.json',
    'model_install_root': 'models',
    'selected_model_profile': '8gb-open-source',
    'updater_mode': 'online_or_import_file',
    'release_channel': 'stable',
}


class SettingsManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.config_dir = data_dir / 'config'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.config_dir / 'settings.json'

    def _defaults(self) -> dict[str, Any]:
        defaults = DEFAULT_SETTINGS.copy()
        if not defaults['allowed_directories']:
            defaults['allowed_directories'] = [str((Path(__file__).resolve().parents[2] / 'demo_data').resolve())]
        if not defaults['security_watched_folders']:
            defaults['security_watched_folders'] = [str((Path(__file__).resolve().parents[2] / 'demo_data' / 'Security' / 'Downloads').resolve())]
        return defaults

    def load(self) -> dict[str, Any]:
        defaults = self._defaults()
        if not self.settings_path.exists():
            self.save(defaults)
            return defaults
        current = json.loads(self.settings_path.read_text(encoding='utf-8'))
        merged = defaults | current
        self.settings_path.write_text(json.dumps(merged, indent=2), encoding='utf-8')
        return merged

    def save(self, settings: dict[str, Any]) -> dict[str, Any]:
        merged = self._defaults() | settings
        self.settings_path.write_text(json.dumps(merged, indent=2), encoding='utf-8')
        return merged


def get_data_dir() -> Path:
    env_dir = os.environ.get('COMPUTERAGENT_DATA_DIR')
    base = Path(env_dir) if env_dir else Path(__file__).resolve().parents[2] / 'backend' / 'runtime'
    base.mkdir(parents=True, exist_ok=True)
    return base
