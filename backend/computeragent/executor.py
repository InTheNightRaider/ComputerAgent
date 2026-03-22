from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .audit import AuditLogger
from .browser.service import BrowserAutomationService
from .models import ExecutionSummary, Plan, PlanAction, RollbackEntry
from .security.service import SecurityService


class Executor:
    def __init__(
        self,
        settings: dict,
        logger: AuditLogger,
        run_id: str,
        data_dir: Path,
        browser_service: BrowserAutomationService,
        security_service: SecurityService,
    ):
        self.settings = settings
        self.logger = logger
        self.run_id = run_id
        self.data_dir = data_dir
        self.browser_service = browser_service
        self.security_service = security_service
        self.rollback_entries: list[dict[str, Any]] = []
        self.summary_lines: list[str] = []
        self.generated_findings: list[dict[str, Any]] = []

    def execute(self, plan: Plan, dry_run: bool = True) -> tuple[ExecutionSummary, list[dict[str, Any]], list[dict[str, Any]]]:
        completed = 0
        failed = 0
        lanes: set[str] = set()
        for action in plan.actions:
            lanes.add(action.execution_lane)
            self.logger.log('info', f'Starting action: {action.description}', action.id, {'lane': action.execution_lane})
            try:
                if action.type == 'file_list':
                    self._list_files(action.params)
                elif action.type == 'file_backup':
                    self._backup(action.id, action.params, dry_run)
                elif action.type == 'mkdir':
                    self._mkdir(action.id, action.params, dry_run)
                elif action.type == 'file_rename':
                    self._rename(action.id, action.params, dry_run)
                elif action.type == 'file_move':
                    self._move(action.id, action.params, dry_run)
                elif action.type == 'file_copy':
                    self._copy(action.id, action.params, dry_run)
                elif action.type in {'file_delete', 'quarantine_file'}:
                    self._delete_or_quarantine(action.id, action, dry_run)
                elif action.type in {'open_browser_context', 'browser_snapshot', 'build_ui_map', 'browser_navigate', 'browser_click', 'browser_fill', 'browser_select', 'browser_extract', 'browser_wait_for', 'browser_screenshot', 'inspect_ui', 'request_foreground_control', 'release_foreground_control'}:
                    self.summary_lines.append(self.browser_service.execute(action))
                elif action.type == 'security_scan_quick':
                    findings = self.security_service.quick_scan([action.params['target_directory']])
                    self.generated_findings.extend([finding.to_dict() for finding in findings])
                    self.summary_lines.append(f'Quick scan found {len(findings)} suspicious items.')
                elif action.type == 'security_monitor_start':
                    if dry_run:
                        self.summary_lines.append('Dry run: would start a background monitor.')
                    else:
                        monitor = self.security_service.start_monitor(action.params['target_directory'])
                        self.summary_lines.append(f"Started live monitor {monitor['id']} for {monitor['folder_path']}.")
                elif action.type == 'security_monitor_stop':
                    if not dry_run:
                        result = self.security_service.stop_monitor(action.params['monitor_id'])
                        self.summary_lines.append(f"Stopped monitor {result['id']}.")
                elif action.type in {'research_docs', 'summarize_results'}:
                    self.summary_lines.append(self._summarize(action.params))
                completed += 1
                self.logger.log('info', f'Completed action: {action.id}', action.id)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.logger.log('error', f'Action failed: {exc}', action.id)
        success = failed == 0
        summary = ExecutionSummary(
            run_id=self.run_id,
            success=success,
            completed_actions=completed,
            failed_actions=failed,
            rollback_available=bool(self.rollback_entries) and not dry_run,
            message='Execution completed successfully.' if success else 'Execution finished with at least one failed step.',
            high_level_result='Background-safe tasks can continue while you work. Reserved-control tasks stay proposal-first until explicitly approved.',
            lane_usage=sorted(lanes),
            highlights=self.summary_lines,
        )
        return summary, self.rollback_entries, self.generated_findings

    def rollback(self, entries: list[dict[str, Any]]) -> list[str]:
        messages: list[str] = []
        for entry in reversed(entries):
            op = entry['operation']
            metadata = entry.get('metadata', {})
            if op in {'rename', 'move'}:
                src = Path(entry['destination'])
                dest = Path(entry['source'])
                if src.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dest))
                    messages.append(f'Restored {dest.name}.')
                elif entry.get('backup_path'):
                    backup = Path(entry['backup_path'])
                    if backup.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup, dest)
                        messages.append(f'Restored {dest.name} from backup snapshot.')
                replaced_backup = metadata.get('replaced_destination_backup')
                if replaced_backup and dest.exists() and Path(replaced_backup).exists():
                    Path(replaced_backup).unlink(missing_ok=True)
            elif op in {'delete', 'quarantine'}:
                backup = Path(entry['backup_path'])
                dest = Path(entry['source'])
                if backup.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(backup), str(dest))
                    messages.append(f'Restored {dest.name} from backup/quarantine.')
            elif op in {'copy', 'backup'}:
                dest = Path(entry['destination'])
                if dest.exists() and op == 'copy':
                    dest.unlink()
                    messages.append(f'Removed copied file {dest.name}.')
            elif op == 'mkdir':
                folder = Path(entry['destination'])
                if folder.exists() and folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
                    messages.append(f'Removed folder {folder.name}.')
        return messages

    def _backup_dir(self, working_path: Path, key: str) -> Path:
        configured = self.settings.get(key, '.agent_backups')
        configured_path = Path(configured)
        if not configured_path.is_absolute():
            name = configured_path.name if configured_path.name.startswith('.') else f'.{configured_path.name}'
            path = working_path / name
        else:
            path = configured_path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _timestamped_backup_path(self, source: Path, key: str = 'backup_location') -> Path:
        backup_dir = self._backup_dir(source.parent, key)
        return backup_dir / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{source.name}"

    def _snapshot_before_mutation(self, source: Path) -> str:
        backup_path = self._timestamped_backup_path(source)
        shutil.copy2(source, backup_path)
        return str(backup_path)

    def _list_files(self, params: dict[str, Any]) -> None:
        directory = Path(params['directory'])
        recursive = bool(params.get('recursive', False))
        patterns = [p.strip() for p in str(params.get('pattern', '')).split(',') if p.strip()]
        files = directory.rglob('*') if recursive else directory.glob('*')
        matched = [file_path.name for file_path in files if file_path.is_file() and (not patterns or any(file_path.name.lower().endswith(pattern.lower()) for pattern in patterns))]
        self.summary_lines.append(f'Found {len(matched)} matching files in {directory.name}.')
        self.logger.log('info', 'Listed files.', detail={'count': len(matched), 'samples': matched[:10]})

    def _backup(self, action_id: str, params: dict[str, Any], dry_run: bool) -> None:
        source = Path(params['source'])
        backup_path = self._timestamped_backup_path(source)
        if dry_run:
            self.summary_lines.append(f'Dry run: would back up {source.name} into {backup_path.parent.name}/.')
            return
        shutil.copy2(source, backup_path)
        self.summary_lines.append(f'Created hidden backup for {source.name}.')
        self.rollback_entries.append(RollbackEntry(action_id=action_id, operation='backup', source=str(source), destination=str(backup_path), backup_path=str(backup_path)).to_dict())

    def _mkdir(self, action_id: str, params: dict[str, Any], dry_run: bool) -> None:
        path = Path(params['path'])
        if dry_run:
            self.summary_lines.append(f'Dry run: would ensure folder {path.name} exists.')
            return
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            self.rollback_entries.append(RollbackEntry(action_id=action_id, operation='mkdir', destination=str(path)).to_dict())

    def _rename(self, action_id: str, params: dict[str, Any], dry_run: bool) -> None:
        source = Path(params['source'])
        destination = Path(params['destination'])
        if dry_run:
            self.summary_lines.append(f'Dry run: would rename {source.name} to {destination.name}.')
            return
        if destination.exists():
            raise FileExistsError(f'Destination already exists: {destination}')
        backup_path = self._snapshot_before_mutation(source)
        source.rename(destination)
        self.rollback_entries.append(RollbackEntry(action_id=action_id, operation='rename', source=str(source), destination=str(destination), backup_path=backup_path).to_dict())

    def _move(self, action_id: str, params: dict[str, Any], dry_run: bool) -> None:
        source = Path(params['source'])
        destination = Path(params['destination'])
        if dry_run:
            self.summary_lines.append(f'Dry run: would move {source.name} to {destination.parent.name}/.')
            return
        if destination.exists():
            raise FileExistsError(f'Destination already exists: {destination}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        backup_path = self._snapshot_before_mutation(source)
        shutil.move(str(source), str(destination))
        self.rollback_entries.append(RollbackEntry(action_id=action_id, operation='move', source=str(source), destination=str(destination), backup_path=backup_path).to_dict())

    def _copy(self, action_id: str, params: dict[str, Any], dry_run: bool) -> None:
        source = Path(params['source'])
        destination = Path(params['destination'])
        if dry_run:
            self.summary_lines.append(f'Dry run: would copy {source.name} to {destination.name}.')
            return
        if destination.exists():
            raise FileExistsError(f'Destination already exists: {destination}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self.rollback_entries.append(RollbackEntry(action_id=action_id, operation='copy', source=str(source), destination=str(destination)).to_dict())

    def _delete_or_quarantine(self, action_id: str, action: PlanAction, dry_run: bool) -> None:
        source = Path(action.params['source'])
        key = 'quarantine_location' if action.type == 'quarantine_file' else 'backup_location'
        backup_path = self._timestamped_backup_path(source, key)
        if dry_run:
            self.summary_lines.append(f'Dry run: would move {source.name} into {backup_path.parent.name}.')
            return
        shutil.move(str(source), str(backup_path))
        operation = 'quarantine' if action.type == 'quarantine_file' else 'delete'
        self.rollback_entries.append(RollbackEntry(action_id=action_id, operation=operation, source=str(source), backup_path=str(backup_path)).to_dict())

    def _summarize(self, params: dict[str, Any]) -> str:
        return f"Prepared {str(params.get('kind', 'summary')).replace('_', ' ')}."
