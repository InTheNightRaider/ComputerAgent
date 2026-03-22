from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from ..models import ChatMessage, Plan, RunRecord, utc_now
from ..providers import LLMProviderAdapter, ProviderConfig


class UnifiedAgent:
    def __init__(
        self,
        storage,
        planner,
        policy,
        research,
        browser,
        security,
        settings_manager,
        repo_root: Path | None = None,
        data_dir: Path | None = None,
    ):
        self.storage = storage
        self.planner = planner
        self.policy = policy
        self.research = research
        self.browser = browser
        self.security = security
        self.settings_manager = settings_manager
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        self.data_dir = data_dir or (self.repo_root / 'backend' / 'runtime')

    def handle_user_message(self, chat_id: str, project_id: str | None, prompt: str, current_url: str = '', target_directory: str = '') -> dict:
        settings = self.settings_manager.load()
        project = self.storage.get_project(project_id)
        request = self.planner.receive_request(prompt, project.get('name') if project else None, current_url=current_url, target_directory=target_directory)
        intent = str(request['intent'])
        llm_note = None
        if intent == 'browser':
            platform = 'Google Docs' if request.get('google_docs_requested') else 'Framer' if 'framer' in prompt.lower() else 'Web app'
            research_summary, sources = self.research.research(platform, prompt, settings.get('max_research_depth', 2))
            browser_actions = self.browser.build_browser_actions(platform, prompt, current_url, str(request.get('company') or 'General'))
            plan = self.planner.browser_plan(prompt, platform, sources, browser_actions, company=str(request.get('company') or 'General'))
            plan.notes.append(research_summary)
            response = 'I prepared a browser-first plan that researches the target flow, builds a DOM/UI map, and uses approval windows before any live document or site edits.'
        elif intent == 'security':
            scan_targets = [target_directory] if target_directory else settings.get('security_watched_folders', [])
            findings = self.security.quick_scan(scan_targets[:1]) if ('check' in prompt.lower() or 'scan' in prompt.lower()) else []
            monitor = 'monitor' in prompt.lower()
            plan = self.planner.security_plan(prompt, scan_targets[0] if scan_targets else '', findings, monitor=monitor)
            response = 'I prepared a defensive-only security workflow with findings, safe containment options, and background monitoring controls.'
        elif intent == 'files':
            directory = target_directory or (project.get('approved_directories', ['']) if project else [''])[0]
            plan = self.planner.file_plan(prompt, directory)
            response = 'I translated your request into direct filesystem actions with hidden rollback backups so the work can run in the background-safe lane.'
        else:
            research_summary, sources = self.research.research('general', prompt, 1)
            plan = Plan(plan_id=f'plan_{uuid4().hex[:10]}', prompt=prompt, notes=[self.planner.build_prompt_template(request), 'No execution needed yet.'], sources=sources)
            response = f'{research_summary} I can turn this into a structured plan when you want execution.'
        if settings.get('planner_mode') == 'llm':
            provider = LLMProviderAdapter(ProviderConfig(settings['local_model_provider'], settings['local_model_endpoint'], settings['model_mode'], repo_root=self.repo_root, data_dir=self.data_dir, catalog_path=settings.get('model_catalog_path', 'shared/model-stack-8gb.json')))
            try:
                llm_note = provider.generate_planning_text(prompt, self.planner.build_prompt_template(request))
                plan.notes.append(f'LLM planner: {llm_note}')
                response = llm_note
            except RuntimeError as exc:
                llm_note = f'Local LLM unavailable: {exc}'
                plan.notes.append(llm_note)
                response = f'{response} {llm_note}'
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
            metadata={'intent': intent, 'request': request, 'llm_note': llm_note},
        )
        self.storage.save_message(assistant_message)
        return {'message': assistant_message.to_dict(), 'run_id': run_id, 'plan': plan.to_dict(), 'intent': intent, 'request': request}
