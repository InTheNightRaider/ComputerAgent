from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

ActionType = Literal[
    'research_docs',
    'inspect_ui',
    'build_ui_map',
    'open_browser_context',
    'browser_navigate',
    'browser_click',
    'browser_fill',
    'browser_select',
    'browser_extract',
    'browser_wait_for',
    'browser_screenshot',
    'browser_snapshot',
    'request_foreground_control',
    'release_foreground_control',
    'file_list',
    'file_backup',
    'file_rename',
    'file_move',
    'file_copy',
    'file_delete',
    'mkdir',
    'quarantine_file',
    'security_scan_quick',
    'security_scan_deep',
    'security_monitor_start',
    'security_monitor_stop',
    'summarize_results',
]
RiskLevel = Literal['low', 'medium', 'high']
ActionStatus = Literal['pending', 'approved', 'running', 'completed', 'failed', 'blocked', 'skipped']
ExecutionLane = Literal['background_safe', 'reserved_control']
MessageRole = Literal['system', 'user', 'assistant']


def utc_now() -> str:
    return datetime.utcnow().isoformat()


@dataclass
class PlanAction:
    id: str
    type: ActionType
    description: str
    params: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = 'low'
    requires_confirmation: bool = False
    execution_lane: ExecutionLane = 'background_safe'
    target_app: str = 'ComputerAgent'
    confidence: float = 0.8
    evidence: list[str] = field(default_factory=list)
    fallback_strategy: str = 'Ask for clarification before retrying.'
    status: ActionStatus = 'pending'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'PlanAction':
        return cls(**data)


@dataclass
class ValidationIssue:
    level: Literal['info', 'warning', 'error']
    message: str
    action_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    allowed: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {'allowed': self.allowed, 'issues': [issue.to_dict() for issue in self.issues]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ValidationResult':
        return cls(allowed=data.get('allowed', True), issues=[ValidationIssue(**issue) for issue in data.get('issues', [])])


@dataclass
class ResearchSource:
    title: str
    domain: str
    url: str
    summary: str
    official: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SecurityFinding:
    id: str
    title: str
    severity: Literal['info', 'low', 'medium', 'high', 'critical']
    confidence: float
    category: str
    evidence: list[str]
    affected_path_or_process: str
    first_seen: str
    recommended_action: str
    false_positive_possible: bool
    status: str = 'new'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    plan_id: str
    prompt: str
    mode: Literal['mock', 'llm'] = 'mock'
    created_at: str = field(default_factory=utc_now)
    target_directory: str = ''
    actions: list[PlanAction] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    validation: ValidationResult = field(default_factory=ValidationResult)
    sources: list[ResearchSource] = field(default_factory=list)
    findings: list[SecurityFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'plan_id': self.plan_id,
            'prompt': self.prompt,
            'mode': self.mode,
            'created_at': self.created_at,
            'target_directory': self.target_directory,
            'actions': [action.to_dict() for action in self.actions],
            'notes': self.notes,
            'validation': self.validation.to_dict(),
            'sources': [source.to_dict() for source in self.sources],
            'findings': [finding.to_dict() for finding in self.findings],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Plan':
        return cls(
            plan_id=data['plan_id'],
            prompt=data['prompt'],
            mode=data.get('mode', 'mock'),
            created_at=data.get('created_at', utc_now()),
            target_directory=data.get('target_directory', ''),
            actions=[PlanAction.from_dict(action) for action in data.get('actions', [])],
            notes=list(data.get('notes', [])),
            validation=ValidationResult.from_dict(data.get('validation', {})),
            sources=[ResearchSource(**item) for item in data.get('sources', [])],
            findings=[SecurityFinding(**item) for item in data.get('findings', [])],
        )


@dataclass
class ExecutionSummary:
    run_id: str
    success: bool
    completed_actions: int
    failed_actions: int
    rollback_available: bool
    message: str
    high_level_result: str = ''
    lane_usage: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackEntry:
    action_id: str
    operation: Literal['rename', 'move', 'delete', 'copy', 'mkdir', 'quarantine', 'backup']
    source: str | None = None
    destination: str | None = None
    backup_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunRecord:
    run_id: str
    prompt: str
    created_at: str
    status: Literal['planned', 'validated', 'executed', 'failed', 'rolled_back']
    target_directory: str
    planner_mode: str
    chat_id: str
    project_id: str | None
    plan: dict[str, Any]
    validation: dict[str, Any]
    execution_summary: dict[str, Any] | None = None
    rollback_available: bool = False
    sources: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Project:
    id: str
    name: str
    description: str = ''
    created_at: str = field(default_factory=utc_now)
    approved_directories: list[str] = field(default_factory=list)
    browser_memory: dict[str, Any] = field(default_factory=dict)
    docs_memory: dict[str, Any] = field(default_factory=dict)
    task_recipes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Chat:
    id: str
    title: str
    project_id: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChatMessage:
    id: str
    chat_id: str
    role: MessageRole
    content: str
    created_at: str = field(default_factory=utc_now)
    message_type: str = 'text'
    run_id: str | None = None
    plan: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
