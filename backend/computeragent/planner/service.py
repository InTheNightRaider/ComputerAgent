from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from ..models import Plan, PlanAction, ResearchSource, SecurityFinding


class PlannerService:
    def _base_action(self, **kwargs) -> PlanAction:
        defaults = {
            'risk_level': 'low',
            'requires_confirmation': False,
            'execution_lane': 'background_safe',
            'target_app': 'ComputerAgent',
            'confidence': 0.82,
            'evidence': [],
            'fallback_strategy': 'Ask the user for clarification before continuing.',
        }
        defaults.update(kwargs)
        return PlanAction(**defaults)

    def file_plan(self, prompt: str, target_directory: str) -> Plan:
        target = Path(target_directory)
        actions: list[PlanAction] = []
        lowered = prompt.lower()
        if 'rename' in lowered and 'pdf' in lowered:
            actions.append(self._base_action(id='file_list', type='file_list', description='List PDF files in the approved folder.', params={'directory': str(target), 'pattern': '.pdf'}, evidence=['Prompt references PDF rename.']))
            for index, file_path in enumerate(sorted(target.glob('*.pdf')), start=1):
                date_prefix = datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y%m%d')
                stem = re.sub(r'[^a-zA-Z0-9]+', '_', file_path.stem).strip('_').lower() or f'document_{index}'
                actions.append(self._base_action(id=f'rename_pdf_{index}', type='file_rename', description=f'Rename {file_path.name} to {date_prefix}_{stem}{file_path.suffix.lower()}.', params={'source': str(file_path), 'destination': str(file_path.with_name(f'{date_prefix}_{stem}{file_path.suffix.lower()}') )}, risk_level='medium', confidence=0.9, evidence=[f'Found file: {file_path.name}'], fallback_strategy='Keep the original file untouched if the rename target collides.'))
        elif 'move' in lowered and 'png' in lowered:
            images_dir = target / 'Images'
            actions.append(self._base_action(id='mkdir_images', type='mkdir', description='Create an Images folder inside the selected directory.', params={'path': str(images_dir)}, confidence=0.92, evidence=['Prompt requests a dedicated Images folder.']))
            for index, file_path in enumerate(sorted(target.glob('*.png')), start=1):
                actions.append(self._base_action(id=f'move_png_{index}', type='file_move', description=f'Move {file_path.name} into Images/.', params={'source': str(file_path), 'destination': str(images_dir / file_path.name)}, risk_level='medium', confidence=0.9, evidence=[f'Found file: {file_path.name}'], fallback_strategy='Leave the file in place if the destination already exists.'))
        else:
            actions.append(self._base_action(id='file_list', type='file_list', description='List files in the approved folder for a safe first pass.', params={'directory': str(target), 'recursive': True}, evidence=['No deterministic file recipe matched exactly, so the agent starts with inspection.']))
        actions.append(self._base_action(id='summarize', type='summarize_results', description='Summarize the file workflow outcome.', params={'kind': 'file_summary'}, confidence=0.95))
        return Plan(plan_id=f'plan_{uuid4().hex[:10]}', prompt=prompt, target_directory=str(target.resolve()), actions=actions, notes=['Direct filesystem APIs are used instead of screen clicking.'])

    def browser_plan(self, prompt: str, platform: str, sources: list[ResearchSource], actions: list[PlanAction]) -> Plan:
        plan = Plan(plan_id=f'plan_{uuid4().hex[:10]}', prompt=prompt, target_directory='', actions=actions, notes=['Browser tasks use DOM/accessibility-first planning and prefer isolated contexts.'], sources=sources)
        return plan

    def security_plan(self, prompt: str, target_directory: str, findings: list[SecurityFinding], monitor: bool = False) -> Plan:
        action_type = 'security_monitor_start' if monitor else 'security_scan_quick'
        description = 'Start a defensive live monitor on the selected folder.' if monitor else 'Run a defensive quick scan against the selected paths.'
        actions = [
            self._base_action(
                id='security_action',
                type=action_type,
                description=description,
                params={'target_directory': target_directory},
                risk_level='medium',
                requires_confirmation=monitor,
                execution_lane='background_safe',
                target_app='Security',
                confidence=0.88,
                evidence=['The prompt explicitly requested a defensive security workflow.'],
                fallback_strategy='Stay in report-only mode if monitoring is not approved.',
            ),
            self._base_action(id='summarize', type='summarize_results', description='Summarize the security findings and next steps.', params={'kind': 'security_summary'}, target_app='Security', confidence=0.94),
        ]
        return Plan(plan_id=f'plan_{uuid4().hex[:10]}', prompt=prompt, target_directory=target_directory, actions=actions, notes=['Security workflows are defensive only.'], findings=findings)
