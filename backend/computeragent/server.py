from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from .audit import AuditLogger
from .audio.service import VoiceTranscriptionService
from .browser.service import BrowserAutomationService
from .config import SettingsManager, get_data_dir
from .core.agent import UnifiedAgent
from .executor import Executor
from .install_state import InstallStateManager
from .model_catalog import load_model_catalog, summarize_model_catalog
from .models import Chat, ChatMessage, Plan, Project, RunRecord
from .planner.service import PlannerService
from .policy.service import PolicyService
from .providers import LLMProviderAdapter, ProviderConfig
from .research.service import ResearchService
from .security.service import SecurityService
from .storage import Storage

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = get_data_dir()
SETTINGS = SettingsManager(DATA_DIR)
STORAGE = Storage(DATA_DIR)
RESEARCH = ResearchService(REPO_ROOT)
BROWSER = BrowserAutomationService(REPO_ROOT, DATA_DIR)
SECURITY = SecurityService(STORAGE, DATA_DIR)
VOICE = VoiceTranscriptionService()
INSTALL_STATE = InstallStateManager(DATA_DIR, REPO_ROOT)
AGENT = UnifiedAgent(STORAGE, PlannerService(), PolicyService(), RESEARCH, BROWSER, SECURITY, SETTINGS, repo_root=REPO_ROOT, data_dir=DATA_DIR)


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')
    handler.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    handler.end_headers()
    handler.wfile.write(body)


def parse_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get('Content-Length', '0'))
    return json.loads(handler.rfile.read(length).decode('utf-8')) if length else {}


def load_models_payload(settings: dict) -> dict:
    catalog = load_model_catalog(REPO_ROOT, settings.get('model_catalog_path', 'shared/model-stack-8gb.json'))
    provider = LLMProviderAdapter(ProviderConfig(settings['local_model_provider'], settings['local_model_endpoint'], settings['model_mode'], repo_root=REPO_ROOT, data_dir=DATA_DIR, catalog_path=settings.get('model_catalog_path', 'shared/model-stack-8gb.json')))
    validation = provider.validate()
    state = INSTALL_STATE.load(catalog)
    return {
        'catalog': catalog,
        'catalog_summary': summarize_model_catalog(catalog),
        'install_state': state,
        'validation': validation,
        'provider': provider.describe(),
    }


def ensure_seed_data() -> None:
    if STORAGE.list_projects():
        return
    demo_project = Project(
        id='project_demo_framer',
        name='Website Revamp',
        description='Demo project for browser research, Framer workflows, and file organization.',
        approved_directories=[str((REPO_ROOT / 'demo_data').resolve())],
        browser_memory={'platforms': ['Framer']},
        docs_memory={'cached_platforms': ['Framer', 'Google Docs']},
        task_recipes=[{'title': 'Framer localization review', 'prompt': 'Research how Framer localization works, then inspect my current Framer editor and suggest the next steps.'}],
    )
    STORAGE.create_project(demo_project)
    default_chat = Chat(id='chat_demo_framer', title='Framer localization plan', project_id=demo_project.id)
    STORAGE.create_chat(default_chat)
    welcome = ChatMessage(
        id='msg_welcome',
        chat_id=default_chat.id,
        role='assistant',
        content='Welcome to ComputerAgent. Ask one unified local agent to research docs, inspect browser workflows, manage files, or run defensive security checks.',
        message_type='system',
    )
    STORAGE.save_message(welcome)
    general_chat = Chat(id='chat_unattached', title='General chat', project_id=None)
    STORAGE.create_chat(general_chat)


class ComputerAgentHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):  # noqa: N802
        json_response(self, {'ok': True})

    def do_GET(self):  # noqa: N802
        ensure_seed_data()
        parsed = urlparse(self.path)
        settings = SETTINGS.load()
        if parsed.path == '/health':
            payload = load_models_payload(settings)
            return json_response(self, {
                'status': 'ok',
                'data_dir': str(DATA_DIR),
                'llm_adapter': payload['provider'],
                'voice': VOICE.status(),
                'model_stack': payload['validation'],
            })
        if parsed.path == '/bootstrap':
            payload = load_models_payload(settings)
            return json_response(self, {
                'settings': settings,
                'projects': STORAGE.list_projects(),
                'chats': STORAGE.list_chats(),
                'sample_prompts': [
                    'Rename all PDFs in this folder to YYYYMMDD_title.',
                    'Organize my Projects folder by year.',
                    'Research how Framer localization works, then inspect my current Framer editor and suggest the next steps.',
                    'Use ChatGPT to draft a company update, then open Google Docs and paste it with the correct headers.',
                    'Update the hero text in my Framer site draft.',
                    'Scan my Downloads folder for suspicious files.',
                    'Check this PC for common persistence indicators.',
                    'Monitor Desktop and Downloads for suspicious executable drops.',
                    'Move all PNG files into an Images folder while I continue working.',
                ],
                'demo_paths': {
                    'inbox': str((REPO_ROOT / 'demo_data' / 'Inbox').resolve()),
                    'projects': str((REPO_ROOT / 'demo_data' / 'Projects').resolve()),
                    'downloads': str((REPO_ROOT / 'demo_data' / 'Security' / 'Downloads').resolve()),
                },
                'security': {
                    'findings': STORAGE.list_security_findings(),
                    'monitors': STORAGE.list_monitors(),
                },
                'model_stack': payload,
            })
        if parsed.path == '/models':
            return json_response(self, load_models_payload(settings))
        if parsed.path == '/models/install-status':
            catalog = load_model_catalog(REPO_ROOT, settings.get('model_catalog_path', 'shared/model-stack-8gb.json'))
            return json_response(self, {'install_state': INSTALL_STATE.load(catalog)})
        if parsed.path.startswith('/chats/') and parsed.path.endswith('/messages'):
            chat_id = parsed.path.split('/')[2]
            return json_response(self, {'messages': STORAGE.list_messages(chat_id)})
        if parsed.path == '/history':
            return json_response(self, {'runs': STORAGE.load_runs()})
        if parsed.path == '/security/findings':
            return json_response(self, {'findings': STORAGE.list_security_findings(), 'monitors': STORAGE.list_monitors()})
        if parsed.path == '/settings':
            return json_response(self, settings)
        if parsed.path.startswith('/history/'):
            run_id = parsed.path.split('/')[-1]
            run = STORAGE.get_run(run_id)
            return json_response(self, run or {'detail': 'Run not found'}, status=200 if run else 404)
        return json_response(self, {'detail': 'Not found'}, status=404)

    def do_POST(self):  # noqa: N802
        ensure_seed_data()
        parsed = urlparse(self.path)
        payload = parse_json(self)
        if parsed.path in {'/bootstrap', '/models/validate'}:
            settings = SETTINGS.load() if parsed.path == '/bootstrap' else (SETTINGS.load() | payload)
            return json_response(self, load_models_payload(settings))
        if parsed.path == '/models/install':
            settings = SETTINGS.load()
            catalog = load_model_catalog(REPO_ROOT, settings.get('model_catalog_path', 'shared/model-stack-8gb.json'))
            result = INSTALL_STATE.install_components(
                catalog,
                dry_run=bool(payload.get('dry_run', True)),
                allow_oversized=bool(payload.get('allow_oversized', False)),
                local_overrides=payload.get('local_overrides'),
                download_missing=bool(payload.get('download_missing', False)),
            )
            return json_response(self, result)
        if parsed.path == '/settings':
            return json_response(self, SETTINGS.save(payload))
        if parsed.path == '/projects':
            project = Project(id=f'project_{uuid4().hex[:10]}', name=payload.get('name', 'Untitled project'), description=payload.get('description', ''), approved_directories=payload.get('approved_directories', []))
            STORAGE.create_project(project)
            return json_response(self, {'project': project.to_dict()})
        if parsed.path == '/chats':
            chat = Chat(id=f'chat_{uuid4().hex[:10]}', title=payload.get('title', 'New chat'), project_id=payload.get('project_id'))
            STORAGE.create_chat(chat)
            return json_response(self, {'chat': chat.to_dict()})
        if parsed.path == '/messages':
            chat_id = payload['chat_id']
            prompt = payload['content'].strip()
            project_id = payload.get('project_id')
            current_url = payload.get('current_url', '')
            target_directory = payload.get('target_directory', '')
            user_message = ChatMessage(id=f'msg_{uuid4().hex[:10]}', chat_id=chat_id, role='user', content=prompt)
            STORAGE.save_message(user_message)
            result = AGENT.handle_user_message(chat_id, project_id, prompt, current_url=current_url, target_directory=target_directory)
            SETTINGS.save(SETTINGS.load())
            return json_response(self, result)
        if parsed.path == '/execute':
            stored = STORAGE.get_run(payload['run_id'])
            if not stored:
                return json_response(self, {'detail': 'Run not found'}, status=404)
            if not payload.get('approved', False):
                return json_response(self, {'detail': 'Plan approval is required before execution.'}, status=400)
            plan = Plan.from_dict(stored['plan'])
            logger = AuditLogger(STORAGE, payload['run_id'])
            executor = Executor(SETTINGS.load(), logger, payload['run_id'], DATA_DIR, BROWSER, SECURITY)
            summary, rollback_entries, findings = executor.execute(plan, dry_run=bool(payload.get('dry_run', True)))
            updated = RunRecord(
                run_id=stored['run_id'],
                prompt=stored['prompt'],
                created_at=stored['created_at'],
                status='executed' if summary.success else 'failed',
                target_directory=stored['target_directory'],
                planner_mode=stored['planner_mode'],
                chat_id=stored['chat_id'],
                project_id=stored['project_id'],
                plan=stored['plan'],
                validation=stored['validation'],
                execution_summary=summary.to_dict(),
                rollback_available=summary.rollback_available,
                sources=stored['sources'],
                findings=stored['findings'] + findings,
            )
            STORAGE.save_run(updated)
            if rollback_entries:
                STORAGE.save_rollback_entries(payload['run_id'], rollback_entries)
            assistant = ChatMessage(
                id=f'msg_{uuid4().hex[:10]}',
                chat_id=stored['chat_id'],
                role='assistant',
                content=summary.message,
                message_type='execution_summary',
                run_id=stored['run_id'],
                plan=stored['plan'],
                sources=stored['sources'],
                findings=stored['findings'] + findings,
                metadata={'summary': summary.to_dict()},
            )
            STORAGE.save_message(assistant)
            return json_response(self, {'summary': summary.to_dict(), 'logs': logger.entries, 'rollback_entries': rollback_entries, 'findings': findings})
        if parsed.path.startswith('/rollback/'):
            run_id = parsed.path.split('/')[-1]
            stored = STORAGE.get_run(run_id)
            if not stored:
                return json_response(self, {'detail': 'Run not found'}, status=404)
            entries = STORAGE.load_rollback_entries(run_id)
            logger = AuditLogger(STORAGE, run_id)
            messages = Executor(SETTINGS.load(), logger, run_id, DATA_DIR, BROWSER, SECURITY).rollback(entries)
            updated = RunRecord(
                run_id=stored['run_id'],
                prompt=stored['prompt'],
                created_at=stored['created_at'],
                status='rolled_back',
                target_directory=stored['target_directory'],
                planner_mode=stored['planner_mode'],
                chat_id=stored['chat_id'],
                project_id=stored['project_id'],
                plan=stored['plan'],
                validation=stored['validation'],
                execution_summary=stored['execution_summary'],
                rollback_available=False,
                sources=stored['sources'],
                findings=stored['findings'],
            )
            STORAGE.save_run(updated)
            return json_response(self, {'status': 'rolled_back', 'messages': messages, 'logs': logger.entries})
        if parsed.path == '/security/quick-scan':
            findings = SECURITY.quick_scan(payload.get('paths', SETTINGS.load().get('security_watched_folders', [])))
            return json_response(self, {'findings': [finding.to_dict() for finding in findings]})
        if parsed.path == '/security/monitor/start':
            monitor = SECURITY.start_monitor(payload['folder_path'])
            return json_response(self, monitor)
        if parsed.path == '/security/monitor/stop':
            return json_response(self, SECURITY.stop_monitor(payload['monitor_id']))
        return json_response(self, {'detail': 'Not found'}, status=404)

    def log_message(self, format: str, *args):
        return


def main() -> None:
    ensure_seed_data()
    port = int(os.environ.get('COMPUTERAGENT_BACKEND_PORT', '8765'))
    server = ThreadingHTTPServer(('127.0.0.1', port), ComputerAgentHandler)
    print(f'ComputerAgent backend listening on http://127.0.0.1:{port}')
    server.serve_forever()


if __name__ == '__main__':
    main()
