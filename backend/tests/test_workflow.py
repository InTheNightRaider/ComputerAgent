from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.computeragent.browser.service import BrowserAutomationService
from backend.computeragent.config import SettingsManager
from backend.computeragent.core.agent import UnifiedAgent
from backend.computeragent.executor import Executor
from backend.computeragent.models import Chat
from backend.computeragent.planner.service import PlannerService
from backend.computeragent.policy.service import PolicyService
from backend.computeragent.research.service import ResearchService
from backend.computeragent.security.service import SecurityService
from backend.computeragent.storage import Storage
from backend.computeragent.audit import AuditLogger


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
            PolicyService(),
            ResearchService(self.repo_root),
            self.browser,
            self.security,
            self.settings,
        )
        self.storage.create_chat(Chat(id='chat_test', title='Test chat'))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_file_prompt_creates_background_safe_plan(self):
        inbox = self.repo_root / 'demo_data' / 'Inbox'
        result = self.agent.handle_user_message('chat_test', None, 'Move all PNG files into an Images folder while I continue working.', target_directory=str(inbox))
        self.assertEqual(result['intent'], 'files')
        self.assertTrue(any(action['execution_lane'] == 'background_safe' for action in result['plan']['actions']))
        self.assertTrue(result['plan']['validation']['allowed'])

    def test_browser_prompt_uses_research_and_ui_map(self):
        result = self.agent.handle_user_message('chat_test', None, 'Research how Framer localization works, then inspect my current Framer editor and suggest the next steps.', current_url='https://www.framer.com')
        action_types = [action['type'] for action in result['plan']['actions']]
        self.assertIn('build_ui_map', action_types)
        self.assertGreaterEqual(len(result['plan']['sources']), 1)

    def test_security_scan_flags_benign_demo_sample(self):
        downloads = self.repo_root / 'demo_data' / 'Security' / 'Downloads'
        findings = self.security.quick_scan([str(downloads)])
        self.assertTrue(any('Suspicious file observed' in finding.title for finding in findings))

    def test_executor_rollback_restores_renamed_file(self):
        with tempfile.TemporaryDirectory() as work:
            work_path = Path(work)
            source = work_path / 'doc.pdf'
            destination = work_path / 'renamed.pdf'
            source.write_text('example', encoding='utf-8')
            plan = PlannerService().file_plan('Rename all PDFs in this folder to YYYYMMDD_title.', str(work_path))
            for action in plan.actions:
                if action.type == 'file_rename':
                    action.params = {'source': str(source), 'destination': str(destination)}
            logger = AuditLogger(self.storage, 'run_test')
            executor = Executor(self.settings.load(), logger, 'run_test', self.data_dir, self.browser, self.security)
            summary, rollback_entries, _ = executor.execute(plan, dry_run=False)
            self.assertTrue(summary.success)
            self.assertTrue(destination.exists())
            messages = executor.rollback(rollback_entries)
            self.assertTrue(source.exists())
            self.assertTrue(messages)


if __name__ == '__main__':
    unittest.main()
