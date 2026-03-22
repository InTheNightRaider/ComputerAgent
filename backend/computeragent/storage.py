from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import Chat, ChatMessage, Project, RunRecord, SecurityFinding


class Storage:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.db_path = data_dir / 'computeragent.db'
        self.logs_dir = data_dir / 'logs'
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    approved_directories_json TEXT NOT NULL,
                    browser_memory_json TEXT NOT NULL,
                    docs_memory_json TEXT NOT NULL,
                    task_recipes_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    project_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    run_id TEXT,
                    plan_json TEXT,
                    sources_json TEXT NOT NULL,
                    findings_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    target_directory TEXT NOT NULL,
                    planner_mode TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    project_id TEXT,
                    plan_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    execution_summary_json TEXT,
                    rollback_available INTEGER NOT NULL DEFAULT 0,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    findings_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS rollback_entries (
                    run_id TEXT NOT NULL,
                    entry_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS security_findings (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    run_id TEXT,
                    finding_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS monitors (
                    id TEXT PRIMARY KEY,
                    folder_path TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    config_json TEXT NOT NULL
                );
                """
            )

    def append_jsonl(self, run_id: str, payload: dict[str, Any]) -> Path:
        export_path = self.logs_dir / f'{run_id}.jsonl'
        with export_path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(payload) + '\n')
        return export_path

    def create_project(self, project: Project) -> None:
        with self._connect() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    project.id,
                    project.name,
                    project.description,
                    project.created_at,
                    json.dumps(project.approved_directories),
                    json.dumps(project.browser_memory),
                    json.dumps(project.docs_memory),
                    json.dumps(project.task_recipes),
                ),
            )

    def list_projects(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM projects ORDER BY datetime(created_at) ASC').fetchall()
        return [
            {
                'id': row['id'],
                'name': row['name'],
                'description': row['description'],
                'created_at': row['created_at'],
                'approved_directories': json.loads(row['approved_directories_json']),
                'browser_memory': json.loads(row['browser_memory_json']),
                'docs_memory': json.loads(row['docs_memory_json']),
                'task_recipes': json.loads(row['task_recipes_json']),
            }
            for row in rows
        ]

    def get_project(self, project_id: str | None) -> dict[str, Any] | None:
        if not project_id:
            return None
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,)).fetchone()
        if not row:
            return None
        return {
            'id': row['id'],
            'name': row['name'],
            'description': row['description'],
            'created_at': row['created_at'],
            'approved_directories': json.loads(row['approved_directories_json']),
            'browser_memory': json.loads(row['browser_memory_json']),
            'docs_memory': json.loads(row['docs_memory_json']),
            'task_recipes': json.loads(row['task_recipes_json']),
        }

    def create_chat(self, chat: Chat) -> None:
        with self._connect() as conn:
            conn.execute('INSERT OR REPLACE INTO chats VALUES (?, ?, ?, ?, ?)', (chat.id, chat.title, chat.project_id, chat.created_at, chat.updated_at))

    def touch_chat(self, chat_id: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE chats SET updated_at = datetime('now') WHERE id = ?", (chat_id,))

    def list_chats(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM chats ORDER BY datetime(updated_at) DESC').fetchall()
        return [dict(row) for row in rows]

    def get_chat(self, chat_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM chats WHERE id = ?', (chat_id,)).fetchone()
        return dict(row) if row else None

    def save_message(self, message: ChatMessage) -> None:
        with self._connect() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    message.id,
                    message.chat_id,
                    message.role,
                    message.content,
                    message.created_at,
                    message.message_type,
                    message.run_id,
                    json.dumps(message.plan) if message.plan else None,
                    json.dumps(message.sources),
                    json.dumps(message.findings),
                    json.dumps(message.metadata),
                ),
            )
        self.touch_chat(message.chat_id)

    def list_messages(self, chat_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM messages WHERE chat_id = ? ORDER BY datetime(created_at) ASC', (chat_id,)).fetchall()
        return [
            {
                'id': row['id'],
                'chat_id': row['chat_id'],
                'role': row['role'],
                'content': row['content'],
                'created_at': row['created_at'],
                'message_type': row['message_type'],
                'run_id': row['run_id'],
                'plan': json.loads(row['plan_json']) if row['plan_json'] else None,
                'sources': json.loads(row['sources_json']),
                'findings': json.loads(row['findings_json']),
                'metadata': json.loads(row['metadata_json']),
            }
            for row in rows
        ]

    def save_run(self, run: RunRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (
                    run.run_id,
                    run.created_at,
                    run.prompt,
                    run.status,
                    run.target_directory,
                    run.planner_mode,
                    run.chat_id,
                    run.project_id,
                    json.dumps(run.plan),
                    json.dumps(run.validation),
                    json.dumps(run.execution_summary) if run.execution_summary else None,
                    1 if run.rollback_available else 0,
                    json.dumps(run.sources),
                    json.dumps(run.findings),
                ),
            )

    def load_runs(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM runs ORDER BY datetime(created_at) DESC').fetchall()
        return [self._row_to_run(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute('SELECT * FROM runs WHERE run_id = ?', (run_id,)).fetchone()
        return self._row_to_run(row) if row else None

    def _row_to_run(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            'run_id': row['run_id'],
            'created_at': row['created_at'],
            'prompt': row['prompt'],
            'status': row['status'],
            'target_directory': row['target_directory'],
            'planner_mode': row['planner_mode'],
            'chat_id': row['chat_id'],
            'project_id': row['project_id'],
            'plan': json.loads(row['plan_json']),
            'validation': json.loads(row['validation_json']),
            'execution_summary': json.loads(row['execution_summary_json']) if row['execution_summary_json'] else None,
            'rollback_available': bool(row['rollback_available']),
            'sources': json.loads(row['sources_json']),
            'findings': json.loads(row['findings_json']),
        }

    def save_rollback_entries(self, run_id: str, entries: list[dict[str, Any]]) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM rollback_entries WHERE run_id = ?', (run_id,))
            conn.executemany('INSERT INTO rollback_entries VALUES (?, ?)', [(run_id, json.dumps(entry)) for entry in entries])

    def load_rollback_entries(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute('SELECT entry_json FROM rollback_entries WHERE run_id = ?', (run_id,)).fetchall()
        return [json.loads(row['entry_json']) for row in rows]

    def save_security_finding(self, finding: SecurityFinding, project_id: str | None = None, run_id: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute('INSERT OR REPLACE INTO security_findings VALUES (?, ?, ?, ?)', (finding.id, project_id, run_id, json.dumps(finding.to_dict())))

    def list_security_findings(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute('SELECT finding_json FROM security_findings ORDER BY rowid DESC').fetchall()
        return [json.loads(row['finding_json']) for row in rows]

    def save_monitor(self, monitor_id: str, folder_path: str, active: bool, config: dict[str, Any], created_at: str) -> None:
        with self._connect() as conn:
            conn.execute('INSERT OR REPLACE INTO monitors VALUES (?, ?, ?, ?, ?)', (monitor_id, folder_path, 1 if active else 0, created_at, json.dumps(config)))

    def list_monitors(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute('SELECT * FROM monitors ORDER BY datetime(created_at) DESC').fetchall()
        return [
            {
                'id': row['id'],
                'folder_path': row['folder_path'],
                'active': bool(row['active']),
                'created_at': row['created_at'],
                'config': json.loads(row['config_json']),
            }
            for row in rows
        ]

    def prune_runs(self, max_runs: int) -> None:
        with self._connect() as conn:
            stale = conn.execute("SELECT run_id FROM runs ORDER BY datetime(created_at) DESC LIMIT -1 OFFSET ?", (max_runs,)).fetchall()
            ids = [row['run_id'] for row in stale]
            if ids:
                conn.executemany('DELETE FROM runs WHERE run_id = ?', [(run_id,) for run_id in ids])
                conn.executemany('DELETE FROM rollback_entries WHERE run_id = ?', [(run_id,) for run_id in ids])
