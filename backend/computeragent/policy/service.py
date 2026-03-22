from __future__ import annotations

from pathlib import Path

from ..models import Plan, ValidationIssue, ValidationResult

SUPPORTED_ACTIONS = {
    'research_docs', 'inspect_ui', 'build_ui_map', 'open_browser_context', 'browser_navigate', 'browser_click', 'browser_fill',
    'browser_select', 'browser_extract', 'browser_wait_for', 'browser_screenshot', 'browser_snapshot', 'request_foreground_control',
    'release_foreground_control', 'file_list', 'file_rename', 'file_move', 'file_copy', 'file_delete', 'mkdir', 'quarantine_file',
    'security_scan_quick', 'security_scan_deep', 'security_monitor_start', 'security_monitor_stop', 'summarize_results',
}
BLOCKED_TERMS = {'credential dump', 'persistence', 'privilege escalation', 'exploit', 'lateral movement'}
SYSTEM_PATH_MARKERS = {'/etc', '/usr', 'system32', 'appdata\\roaming\\microsoft\\windows\\start menu\\programs\\startup'}


class PolicyService:
    def validate(self, plan: Plan, settings: dict, project: dict | None = None) -> ValidationResult:
        issues: list[ValidationIssue] = [
            ValidationIssue(level='info', message='Your data stays on-device. Unsupported, offensive, and shell-based actions are blocked.'),
        ]
        allowed_dirs = [Path(path).resolve() for path in settings.get('allowed_directories', [])]
        if project:
            allowed_dirs.extend(Path(path).resolve() for path in project.get('approved_directories', []))
        preferred_domains = set(settings.get('preferred_docs_domains', []))
        for action in plan.actions:
            if action.type not in SUPPORTED_ACTIONS:
                issues.append(ValidationIssue(level='error', action_id=action.id, message=f'Unsupported action type: {action.type}'))
                continue
            if any(term in action.description.lower() for term in BLOCKED_TERMS):
                issues.append(ValidationIssue(level='error', action_id=action.id, message='Blocked offensive or high-risk security behavior.'))
            if action.execution_lane == 'reserved_control' and settings.get('require_approval_before_foreground_control', True) and not action.requires_confirmation:
                issues.append(ValidationIssue(level='warning', action_id=action.id, message='Foreground-control action should require explicit confirmation.'))
            if action.type.startswith('browser_') or action.type in {'open_browser_context', 'build_ui_map', 'inspect_ui'}:
                domain = str(action.params.get('domain', '')).replace('https://', '').replace('http://', '').split('/')[0]
                if domain and preferred_domains and domain not in preferred_domains:
                    issues.append(ValidationIssue(level='warning', action_id=action.id, message=f'Browser domain {domain} is outside the preferred docs/browser allowlist.'))
            if action.type in {'file_list', 'file_rename', 'file_move', 'file_copy', 'file_delete', 'mkdir', 'quarantine_file'}:
                for value in action.params.values():
                    if isinstance(value, str) and ('/' in value or '\\' in value):
                        path = Path(value).resolve()
                        path_str = str(path).lower()
                        if any(marker in path_str for marker in SYSTEM_PATH_MARKERS):
                            issues.append(ValidationIssue(level='warning', action_id=action.id, message=f'Path touches a system-sensitive location: {path}'))
                        if allowed_dirs and not any(self._is_relative_to(path, root) for root in allowed_dirs):
                            issues.append(ValidationIssue(level='error', action_id=action.id, message=f'Path is outside the approved directories: {path}'))
            if action.type in {'file_delete', 'quarantine_file'}:
                issues.append(ValidationIssue(level='warning', action_id=action.id, message='Destructive or containment action requires extra confirmation.'))
            if action.type == 'security_monitor_start':
                issues.append(ValidationIssue(level='info', action_id=action.id, message='Live monitoring runs in the background-safe lane and can continue while you work.'))
        return ValidationResult(allowed=not any(issue.level == 'error' for issue in issues), issues=issues)

    @staticmethod
    def _is_relative_to(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
