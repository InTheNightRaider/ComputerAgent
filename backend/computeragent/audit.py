from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .storage import Storage


@dataclass
class AuditLogger:
    storage: Storage
    run_id: str
    entries: list[dict[str, Any]] = field(default_factory=list)

    def log(self, level: str, message: str, action_id: str | None = None, detail: dict[str, Any] | None = None) -> None:
        payload = {
            'timestamp': datetime.utcnow().isoformat(),
            'run_id': self.run_id,
            'level': level,
            'action_id': action_id,
            'message': message,
            'detail': detail or {},
        }
        self.entries.append(payload)
        self.storage.append_jsonl(self.run_id, payload)
