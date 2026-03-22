from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .storage import Storage


@dataclass
class AuditLogger:
    storage: Storage
    run_id: str
    entries: list[dict[str, Any]] = field(default_factory=list)
    _last_signature: str = field(default='GENESIS', init=False, repr=False)

    def log(self, level: str, message: str, action_id: str | None = None, detail: dict[str, Any] | None = None) -> None:
        payload = {
            'timestamp': datetime.utcnow().isoformat(),
            'run_id': self.run_id,
            'level': level,
            'action_id': action_id,
            'message': message,
            'detail': detail or {},
            'sequence': len(self.entries) + 1,
            'previous_signature': self._last_signature,
        }
        payload['signature'] = self._sign(payload)
        self._last_signature = payload['signature']
        self.entries.append(payload)
        self.storage.append_jsonl(self.run_id, payload)

    @staticmethod
    def _sign(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
