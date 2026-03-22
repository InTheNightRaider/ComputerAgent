from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from backend.computeragent.audit import AuditLogger
from backend.computeragent.browser.service import BrowserAutomationService
from backend.computeragent.config import SettingsManager
from backend.computeragent.core.agent import UnifiedAgent
from backend.computeragent.executor import Executor
from backend.computeragent.install_state import InstallStateManager
from backend.computeragent.model_catalog import load_model_catalog, summarize_model_catalog
from backend.computeragent.models import Chat, Plan, PlanAction
from backend.computeragent.planner.service import PlannerService
from backend.computeragent.policy.service import PolicyService
from backend.computeragent.providers import LLMProviderAdapter, ProviderConfig
from backend.computeragent.research.service import ResearchService
from backend.computeragent.security.service import SecurityService
from backend.computeragent.storage import Storage


class MockLlamaHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == '/health':
            body = json.dumps({'status': 'ok'}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        if self.path == '/v1/chat/completions':
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
            user_text = payload.get('messages', [])[-1].get('content', '') if payload.get('messages') else ''
            body = json.dumps({'choices': [{'message': {'content': f'Local LLM plan for: {user_text}'}}]}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


class IntegratedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.repo_root = Path(__file__).resolve().parents[2]
        self.storage = Storage(self.data_dir)
        self.settings = SettingsManager(self.data_dir)
        self.browser = BrowserAutomationService(self.repo_root, self.data_dir)
        self.security = SecurityService(self.storage, self.data_dir)
        self.agent = UnifiedAgent(
            self.storage,
            PlannerService(),
            PolicyService(self.repo_root),
            ResearchService(self.repo_root),
            self.browser,
            self.security,
            self.settings,
            repo_root=self.repo_root,
            data_dir=self.data_dir,
        )
        self.install_state = InstallStateManager(self.data_dir, self.repo_root)
        self.catalog = load_model_catalog(self.repo_root)
        self.storage.create_chat(Chat(id='chat_test', title='Test chat'))

    def tearDown(self):
        self.temp_dir.cleanup()

    def _mark_default_stack_installed(self, endpoint: str = 'http://127.0.0.1:9') -> None:
        overrides = {}
        for component_id in ['mistral-7b-instruct-gguf', 'mistral-tokenizer', 'e5-large-v2', 'rust-rule-engine', 'qdrant']:
            component = next(item for item in self.catalog['components'] if item['id'] == component_id)
            overrides[component_id] = {}
            for artifact in component['artifacts']:
                path = self.data_dir / f'{component_id}_{artifact["key"]}'
                path.write_text('ok', encoding='utf-8')
                overrides[component_id][artifact['key']] = str(path)
        self.install_state.install_components(self.catalog, dry_run=False, local_overrides=overrides)
        self.settings.save({'planner_mode': 'llm', 'local_model_endpoint': endpoint, 'local_model_provider': 'llama.cpp'})

    def test_file_prompt_creates_background_safe_plan(self):
        with tempfile.TemporaryDirectory() as work:
            work_path = Path(work)
            self.settings.save({'allowed_directories': [str(work_path)]})
            (work_path / 'example.png').write_text('png', encoding='utf-8')
            result = self.agent.handle_user_message('chat_test', None, 'Move all PNG files into an Images folder while I continue working.', target_directory=str(work_path))
        self.assertEqual(result['intent'], 'files')
        self.assertTrue(any(action['execution_lane'] == 'background_safe' for action in result['plan']['actions']))
        self.assertTrue(any(action['type'] == 'file_backup' for action in result['plan']['actions']))
        self.assertTrue(result['plan']['validation']['allowed'])

    def test_browser_prompt_uses_research_and_ui_map(self):
        result = self.agent.handle_user_message('chat_test', None, 'Research how Framer localization works, then inspect my current Framer editor and suggest the next steps.', current_url='https://www.framer.com')
        action_types = [action['type'] for action in result['plan']['actions']]
        self.assertIn('build_ui_map', action_types)
        self.assertGreaterEqual(len(result['plan']['sources']), 1)

    def test_google_docs_prompt_builds_document_plan(self):
        result = self.agent.handle_user_message('chat_test', None, 'Use ChatGPT in the browser to draft a board update for Acme Holdings, then open Google Docs and paste it with the exact Acme headers.', current_url='https://docs.google.com')
        action_types = [action['type'] for action in result['plan']['actions']]
        self.assertEqual(result['intent'], 'browser')
        self.assertIn('browser_fill', action_types)
        self.assertIn('request_foreground_control', action_types)
        self.assertIn('Acme Holdings', ' '.join(result['plan']['notes']))

    def test_security_scan_flags_benign_demo_sample(self):
        downloads = self.repo_root / 'demo_data' / 'Security' / 'Downloads'
        findings = self.security.quick_scan([str(downloads)])
        self.assertTrue(any('Suspicious file observed' in finding.title for finding in findings))

    def test_executor_rollback_restores_renamed_file_and_keeps_hidden_backup(self):
        with tempfile.TemporaryDirectory() as work:
            work_path = Path(work)
            source = work_path / 'doc.pdf'
            destination = work_path / 'renamed.pdf'
            source.write_text('example', encoding='utf-8')
            plan = PlannerService().file_plan('Rename all PDFs in this folder to YYYYMMDD_title.', str(work_path))
            for action in plan.actions:
                if action.type == 'file_rename':
                    action.params = {'source': str(source), 'destination': str(destination)}
                if action.type == 'file_backup':
                    action.params = {'source': str(source)}
            logger = AuditLogger(self.storage, 'run_test')
            executor = Executor(self.settings.load(), logger, 'run_test', self.data_dir, self.browser, self.security)
            summary, rollback_entries, _ = executor.execute(plan, dry_run=False)
            self.assertTrue(summary.success)
            self.assertTrue(destination.exists())
            self.assertTrue((work_path / '.agent_backups').exists())
            messages = executor.rollback(rollback_entries)
            self.assertTrue(source.exists())
            self.assertTrue(messages)

    def test_policy_whitelist_blocks_unknown_action(self):
        settings = self.settings.load()
        plan = Plan(plan_id='plan_test', prompt='test', actions=[PlanAction(id='x', type='summarize_results', description='ok'), PlanAction(id='y', type='browser_wait_for', description='wait')])
        result = PolicyService(self.repo_root).validate(plan, settings)
        self.assertTrue(result.allowed)
        bad_plan = Plan(plan_id='plan_bad', prompt='test', actions=[PlanAction(id='bad', type='research_docs', description='credential dump the system')])
        result = PolicyService(self.repo_root).validate(bad_plan, settings)
        self.assertFalse(result.allowed)

    def test_audit_log_entries_chain_signatures(self):
        logger = AuditLogger(self.storage, 'run_audit')
        logger.log('info', 'first')
        logger.log('info', 'second')
        self.assertEqual(logger.entries[0]['sequence'], 1)
        self.assertEqual(logger.entries[1]['previous_signature'], logger.entries[0]['signature'])
        self.assertNotEqual(logger.entries[0]['signature'], logger.entries[1]['signature'])

    def test_model_catalog_exposes_8gb_default_stack(self):
        summary = summarize_model_catalog(self.catalog)
        enabled_ids = {item['id'] for item in summary['default_enabled_components']}
        self.assertIn('mistral-7b-instruct-gguf', enabled_ids)
        self.assertIn('qdrant', enabled_ids)
        self.assertNotIn('stable-diffusion-1.5-fp16', enabled_ids)

    def test_install_state_transitions(self):
        result = self.install_state.install_components(self.catalog, dry_run=True)
        component_state = result['components']['mistral-7b-instruct-gguf']
        self.assertEqual(component_state['status'], 'prepared')
        self.assertEqual(result['components']['stable-diffusion-1.5-fp16']['status'], 'deferred')

    def test_provider_reports_missing_artifacts(self):
        provider = LLMProviderAdapter(ProviderConfig('llama.cpp', 'http://127.0.0.1:8080', 'Balanced', repo_root=self.repo_root, data_dir=self.data_dir))
        description = provider.describe()
        self.assertEqual(description['provider'], 'llama.cpp')
        self.assertFalse(description['validation']['planning_runtime']['runnable'])
        self.assertTrue(description['validation']['planning_runtime']['missing_components'])

    def test_successful_validation_of_mocked_installed_stack(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), MockLlamaHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f'http://127.0.0.1:{server.server_address[1]}'
            self._mark_default_stack_installed(endpoint)
            provider = LLMProviderAdapter(ProviderConfig('llama.cpp', endpoint, 'Balanced', repo_root=self.repo_root, data_dir=self.data_dir))
            validation = provider.validate()
            self.assertTrue(validation['planning_runtime']['runnable'])
            self.assertTrue(validation['full_stack']['runnable'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_end_to_end_llm_planning_workflow(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), MockLlamaHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f'http://127.0.0.1:{server.server_address[1]}'
            self._mark_default_stack_installed(endpoint)
            result = self.agent.handle_user_message('chat_test', None, 'Please create a planning outline for organizing the project files.', target_directory=str(self.repo_root / 'demo_data'))
            self.assertIn('Local LLM plan for:', result['message']['content'])
            self.assertTrue(any('LLM planner:' in note for note in result['plan']['notes']))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
