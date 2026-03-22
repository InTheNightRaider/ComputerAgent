from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import Plan, ValidationIssue, ValidationResult

REQUIRED_WHITELIST_KEYS = {
    'version',
    'supported_actions',
    'blocked_terms',
    'system_path_markers',
    'preferred_browser_domains',
    'reserved_control_actions',
}


class PolicyService:
    def __init__(self, repo_root: Path | None = None):
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]

    def validate(self, plan: Plan, settings: dict, project: dict | None = None) -> ValidationResult:
        issues: list[ValidationIssue] = [
            ValidationIssue(level='info', message='Your data stays on-device. Unsupported, offensive, and shell-based actions are blocked.'),
        ]
        whitelist, whitelist_issues = self._load_whitelist(settings)
        issues.extend(whitelist_issues)
        supported_actions = set(whitelist.get('supported_actions', []))
        blocked_terms = {term.lower() for term in whitelist.get('blocked_terms', [])}
        system_path_markers = {marker.lower() for marker in whitelist.get('system_path_markers', [])}
        reserved_control_actions = set(whitelist.get('reserved_control_actions', []))
        allowed_dirs = [Path(path).resolve() for path in settings.get('allowed_directories', [])]
        if project:
            allowed_dirs.extend(Path(path).resolve() for path in project.get('approved_directories', []))
        preferred_domains = set(settings.get('preferred_docs_domains') or whitelist.get('preferred_browser_domains', []))
        for action in plan.actions:
            if action.type not in supported_actions:
                issues.append(ValidationIssue(level='error', action_id=action.id, message=f'Unsupported action type: {action.type}'))
                continue
            description_lower = action.description.lower()
            if any(term in description_lower for term in blocked_terms):
                issues.append(ValidationIssue(level='error', action_id=action.id, message='Blocked offensive or high-risk security behavior.'))
            if action.type in reserved_control_actions and settings.get('require_approval_before_foreground_control', True) and not action.requires_confirmation:
                issues.append(ValidationIssue(level='warning', action_id=action.id, message='Foreground-control action should require explicit confirmation.'))
            if action.type.startswith('browser_') or action.type in {'open_browser_context', 'build_ui_map', 'inspect_ui'}:
                domain = str(action.params.get('domain', '')).replace('https://', '').replace('http://', '').split('/')[0]
                if domain and preferred_domains and domain not in preferred_domains:
                    issues.append(ValidationIssue(level='warning', action_id=action.id, message=f'Browser domain {domain} is outside the preferred docs/browser allowlist.'))
            if action.type in {'file_list', 'file_backup', 'file_rename', 'file_move', 'file_copy', 'file_delete', 'mkdir', 'quarantine_file'}:
                for value in action.params.values():
                    if isinstance(value, str) and ('/' in value or '\\' in value):
                        path = Path(value).resolve()
                        path_str = str(path).lower()
                        if any(marker in path_str for marker in system_path_markers):
                            issues.append(ValidationIssue(level='warning', action_id=action.id, message=f'Path touches a system-sensitive location: {path}'))
                        if allowed_dirs and not any(self._is_relative_to(path, root) for root in allowed_dirs):
                            issues.append(ValidationIssue(level='error', action_id=action.id, message=f'Path is outside the approved directories: {path}'))
            if action.type in {'file_delete', 'quarantine_file'}:
                issues.append(ValidationIssue(level='warning', action_id=action.id, message='Destructive or containment action requires extra confirmation.'))
            if action.type == 'security_monitor_start':
                issues.append(ValidationIssue(level='info', action_id=action.id, message='Live monitoring runs in the background-safe lane and can continue while you work.'))
        return ValidationResult(allowed=not any(issue.level == 'error' for issue in issues), issues=issues)

    def _load_whitelist(self, settings: dict[str, Any]) -> tuple[dict[str, Any], list[ValidationIssue]]:
        configured = settings.get('policy_whitelist_path', 'shared/policy-whitelist.json')
        path = Path(configured)
        if not path.is_absolute():
            path = (self.repo_root / path).resolve()
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return {}, [ValidationIssue(level='error', message=f'Policy whitelist file is missing: {path}')]
        except json.JSONDecodeError as exc:
            return {}, [ValidationIssue(level='error', message=f'Policy whitelist is invalid JSON: {exc}')]
        missing = sorted(REQUIRED_WHITELIST_KEYS - data.keys())
        if missing:
            return data, [ValidationIssue(level='error', message=f'Policy whitelist is missing required keys: {", ".join(missing)}')]
        return data, []

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
