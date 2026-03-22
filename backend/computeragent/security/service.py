from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..models import SecurityFinding
from ..storage import Storage

SUSPICIOUS_EXTENSIONS = {'.exe', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.scr'}
SUSPICIOUS_NAMES = {'invoice', 'urgent', 'reset-password', 'update-now'}


class SecurityService:
    def __init__(self, storage: Storage, data_dir: Path):
        self.storage = storage
        self.data_dir = data_dir
        self.monitor_threads: dict[str, threading.Thread] = {}
        self.monitor_stop_flags: dict[str, threading.Event] = {}

    def quick_scan(self, target_paths: list[str]) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for raw_path in target_paths:
            root = Path(raw_path)
            if not root.exists():
                continue
            for file_path in root.rglob('*'):
                if not file_path.is_file():
                    continue
                suffix = file_path.suffix.lower()
                score = 0.0
                evidence: list[str] = []
                if suffix in SUSPICIOUS_EXTENSIONS:
                    score += 0.4
                    evidence.append(f'Suspicious extension detected: {suffix}')
                if file_path.name.startswith('.') and suffix in SUSPICIOUS_EXTENSIONS:
                    score += 0.3
                    evidence.append('Hidden script or executable in a user folder.')
                if any(token in file_path.stem.lower() for token in SUSPICIOUS_NAMES):
                    score += 0.2
                    evidence.append('Filename matches a common lure pattern.')
                try:
                    sample = file_path.read_bytes()[:128]
                    if suffix == '.txt' and sample.startswith(b'MZ'):
                        score += 0.6
                        evidence.append('Extension/content mismatch suggests a disguised executable.')
                except OSError:
                    evidence.append('File could not be opened during scan.')
                if score <= 0:
                    continue
                severity = 'low' if score < 0.5 else 'medium' if score < 0.8 else 'high'
                finding = SecurityFinding(
                    id=f'finding_{uuid4().hex[:10]}',
                    title=f'Suspicious file observed: {file_path.name}',
                    severity=severity,
                    confidence=round(min(score, 0.98), 2),
                    category='file_suspicion',
                    evidence=evidence,
                    affected_path_or_process=str(file_path),
                    first_seen=time.strftime('%Y-%m-%dT%H:%M:%S'),
                    recommended_action='Review the file and quarantine it if the path or extension looks unexpected.',
                    false_positive_possible=True,
                )
                findings.append(finding)
                self.storage.save_security_finding(finding)
        return findings

    def start_monitor(self, folder_path: str, interval_seconds: int = 5) -> dict[str, Any]:
        monitor_id = f'monitor_{uuid4().hex[:8]}'
        stop_flag = threading.Event()
        baseline = self._snapshot(folder_path)

        def worker() -> None:
            current_baseline = baseline
            while not stop_flag.wait(interval_seconds):
                latest = self._snapshot(folder_path)
                new_paths = sorted(set(latest) - set(current_baseline))
                if new_paths:
                    findings = self.quick_scan(new_paths)
                    if not findings:
                        for path in new_paths:
                            if Path(path).suffix.lower() in SUSPICIOUS_EXTENSIONS:
                                finding = SecurityFinding(
                                    id=f'finding_{uuid4().hex[:10]}',
                                    title='New executable or script detected in watched folder',
                                    severity='medium',
                                    confidence=0.62,
                                    category='live_monitor',
                                    evidence=['A new executable or script appeared in a watched folder.'],
                                    affected_path_or_process=path,
                                    first_seen=time.strftime('%Y-%m-%dT%H:%M:%S'),
                                    recommended_action='Review and quarantine if unexpected.',
                                    false_positive_possible=True,
                                )
                                self.storage.save_security_finding(finding)
                current_baseline = latest

        thread = threading.Thread(target=worker, daemon=True)
        self.monitor_stop_flags[monitor_id] = stop_flag
        self.monitor_threads[monitor_id] = thread
        self.storage.save_monitor(monitor_id, folder_path, True, {'interval_seconds': interval_seconds}, time.strftime('%Y-%m-%dT%H:%M:%S'))
        thread.start()
        return {'id': monitor_id, 'folder_path': folder_path, 'active': True, 'interval_seconds': interval_seconds}

    def stop_monitor(self, monitor_id: str) -> dict[str, Any]:
        stop_flag = self.monitor_stop_flags.get(monitor_id)
        if stop_flag:
            stop_flag.set()
        return {'id': monitor_id, 'active': False}

    @staticmethod
    def _snapshot(folder_path: str) -> dict[str, str]:
        root = Path(folder_path)
        if not root.exists():
            return {}
        snapshot = {}
        for file_path in root.rglob('*'):
            if file_path.is_file():
                snapshot[str(file_path)] = str(file_path.stat().st_mtime)
        return snapshot
