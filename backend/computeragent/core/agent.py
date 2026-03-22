from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from ..browser.service import BrowserAutomationService
from ..models import ChatMessage, Plan, Project, ResearchSource, RunRecord, utc_now
from ..planner.service import PlannerService
from ..policy.service import PolicyService
from ..research.service import ResearchService
from ..security.service import SecurityService
from ..storage import Storage


class UnifiedAgent:
    def __init__(
        self,
        storage: Storage,
        planner: PlannerService,
        policy: PolicyService,
        research: ResearchService,
        browser: BrowserAutomationService,
        security: SecurityService,
        settings_manager,
    ):
        self.storage = storage
        self.planner = planner
        self.policy = policy
        self.research = research
        self.browser = browser
        self.security = security
        self.settings_manager = settings_manager

    def handle_user_message(self, chat_id: str, project_id: str | None, prompt: str, current_url: str = '', target_directory: str = '') -> dict:
        settings = self.settings_manager.load()
        project = self.storage.get_project(project_id)
        intent = self._classify(prompt)
        if intent == 'browser':
            platform = 'Framer' if 'framer' in prompt.lower() else 'Web app'
            research_summary, sources = self.research.research(platform, prompt, settings.get('max_research_depth', 2))
            browser_actions = self.browser.build_browser_actions(platform, prompt, current_url)
            plan = self.planner.browser_plan(prompt, platform, sources, browser_actions)
            plan.notes.append(research_summary)
            response = f"I researched {platform} guidance first, then prepared a browser-first plan that relies on DOM/accessibility understanding before any UI action."
        elif intent == 'security':
            scan_targets = [target_directory] if target_directory else settings.get('security_watched_folders', [])
            findings = self.security.quick_scan(scan_targets[:1]) if ('check' in prompt.lower() or 'scan' in prompt.lower()) else []
            monitor = 'monitor' in prompt.lower()
            plan = self.planner.security_plan(prompt, scan_targets[0] if scan_targets else '', findings, monitor=monitor)
            response = 'I prepared a defensive-only security workflow with findings, safe containment options, and background monitoring controls.'
        elif intent == 'files':
            directory = target_directory or (project.get('approved_directories', ['']) if project else [''])[0]
            plan = self.planner.file_plan(prompt, directory)
            response = 'I translated your request into direct filesystem actions so the work can run in the background-safe lane.'
        else:
            research_summary, sources = self.research.research('general', prompt, 1)
            plan = Plan(plan_id=f'plan_{uuid4().hex[:10]}', prompt=prompt, notes=['No execution needed yet.'], sources=sources)
            response = f'{research_summary} I can turn this into a structured plan when you want execution.'
        plan.validation = self.policy.validate(plan, settings, project)
        run_id = f'run_{uuid4().hex[:10]}'
        self.storage.save_run(
            RunRecord(
                run_id=run_id,
                prompt=prompt,
                created_at=utc_now(),
                status='validated' if plan.validation.allowed else 'failed',
                target_directory=plan.target_directory,
                planner_mode=settings.get('planner_mode', 'mock'),
                chat_id=chat_id,
                project_id=project_id,
                plan=plan.to_dict(),
                validation=plan.validation.to_dict(),
                rollback_available=False,
                sources=[source.to_dict() for source in plan.sources],
                findings=[finding.to_dict() for finding in plan.findings],
            )
        )
        assistant_message = ChatMessage(
            id=f'msg_{uuid4().hex[:10]}',
            chat_id=chat_id,
            role='assistant',
            content=response,
            message_type='agent_response',
            run_id=run_id,
            plan=plan.to_dict(),
            sources=[source.to_dict() for source in plan.sources],
            findings=[finding.to_dict() for finding in plan.findings],
            metadata={'intent': intent},
        )
        self.storage.save_message(assistant_message)
        return {'message': assistant_message.to_dict(), 'run_id': run_id, 'plan': plan.to_dict(), 'intent': intent}

    @staticmethod
    def _classify(prompt: str) -> str:
        lowered = prompt.lower()
        if any(keyword in lowered for keyword in ['framer', 'browser', 'web', 'site', 'publish', 'hero text', 'localization']):
            return 'browser'
        if any(keyword in lowered for keyword in ['scan', 'compromised', 'persistence', 'suspicious', 'monitor', 'quarantine', 'startup items']):
            return 'security'
        if any(keyword in lowered for keyword in ['rename', 'move', 'folder', 'file', 'png', 'pdf', 'organize', 'documents']):
            return 'files'
        return 'general'
