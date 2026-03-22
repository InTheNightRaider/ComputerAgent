from __future__ import annotations

import json
from pathlib import Path

from ..models import PlanAction


class BrowserAutomationService:
    def __init__(self, repo_root: Path, data_dir: Path):
        self.repo_root = repo_root
        self.data_dir = data_dir
        self.recipe_path = repo_root / 'demo_data' / 'browser' / 'recipes.json'
        self.snapshot_dir = data_dir / 'browser_snapshots'
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def build_browser_actions(self, platform: str, prompt: str, current_url: str = '', company: str = 'General') -> list[PlanAction]:
        evidence = [f'Platform profile: {platform}', 'Primary control surface: DOM and accessibility tree.']
        lowered = prompt.lower()
        document_request = 'document' in lowered or 'google docs' in lowered
        chatgpt_requested = 'chatgpt' in lowered or document_request
        actions = [
            PlanAction(
                id='open_browser_context',
                type='open_browser_context',
                description='Open an isolated automation browser context.',
                params={'mode': 'headed', 'current_url': current_url},
                risk_level='low',
                execution_lane='background_safe',
                target_app='Browser',
                confidence=0.88,
                evidence=evidence,
                fallback_strategy='Pause for a human login handoff if the site requires authentication.',
            ),
            PlanAction(
                id='browser_snapshot',
                type='browser_snapshot',
                description='Capture DOM/accessibility metadata before any browser changes.',
                params={'url': current_url or 'about:blank', 'platform': platform},
                risk_level='low',
                execution_lane='background_safe',
                target_app=platform,
                confidence=0.8,
                evidence=evidence,
                fallback_strategy='Take a screenshot if the DOM is not informative enough.',
            ),
            PlanAction(
                id='build_ui_map',
                type='build_ui_map',
                description=f'Build a resilient UI map for {platform} using roles, labels, visible text, and structure.',
                params={'platform': platform, 'prompt': prompt},
                risk_level='low',
                execution_lane='background_safe',
                target_app=platform,
                confidence=0.82,
                evidence=evidence,
                fallback_strategy='Store locator hints and ask for confirmation before any uncertain click path.',
            ),
        ]
        if document_request:
            actions.extend([
                PlanAction(
                    id='navigate_google_docs',
                    type='browser_navigate',
                    description='Open Google Docs in a dedicated tab for document assembly.',
                    params={'url': 'https://docs.google.com/document/u/0/', 'domain': 'docs.google.com'},
                    risk_level='low',
                    execution_lane='background_safe',
                    target_app='Google Docs',
                    confidence=0.9,
                    evidence=['The prompt requests a document workflow.'],
                    fallback_strategy='Stop at the draft outline if Google Docs is unavailable.',
                ),
                PlanAction(
                    id='extract_document_outline',
                    type='browser_extract',
                    description=f'Prepare the company-specific outline and header order for {company}.',
                    params={'kind': 'document_outline', 'company': company, 'sections': ['Company Heading', 'Document Title', 'Executive Summary', 'Key Sections', 'Action Items', 'Approval Footer']},
                    risk_level='low',
                    execution_lane='background_safe',
                    target_app='ComputerAgent',
                    confidence=0.87,
                    evidence=['Document requests need deterministic structure before any paste step.'],
                    fallback_strategy='Ask the user to confirm the outline if company formatting is ambiguous.',
                ),
            ])
            if chatgpt_requested:
                actions.append(
                    PlanAction(
                        id='navigate_chatgpt',
                        type='browser_navigate',
                        description='Open ChatGPT to draft the document body before pasting into Google Docs.',
                        params={'url': 'https://chatgpt.com/', 'domain': 'chatgpt.com'},
                        risk_level='low',
                        execution_lane='background_safe',
                        target_app='ChatGPT',
                        confidence=0.74,
                        evidence=['The requested workflow explicitly allows browser-assisted drafting.'],
                        fallback_strategy='Skip drafting and prepare only the document skeleton if ChatGPT access is unavailable.',
                    )
                )
            actions.extend([
                PlanAction(
                    id='request_foreground_control',
                    type='request_foreground_control',
                    description='Request approval before pasting or editing the live document in the visible browser session.',
                    params={'reason': 'Live document editing requires precise user-visible input'},
                    risk_level='medium',
                    requires_confirmation=True,
                    execution_lane='reserved_control',
                    target_app='Google Docs',
                    confidence=0.78,
                    evidence=['Live document edits should never be fully automatic without an approval window.'],
                    fallback_strategy='Return the outline and exact content blocks for manual paste.',
                ),
                PlanAction(
                    id='fill_google_doc',
                    type='browser_fill',
                    description=f'Paste the approved {company} document structure into Google Docs with exact headers and spacing.',
                    params={'target': 'google_doc_body', 'document_profile': company, 'mode': 'paste_approved_content'},
                    risk_level='medium',
                    requires_confirmation=True,
                    execution_lane='reserved_control',
                    target_app='Google Docs',
                    confidence=0.7,
                    evidence=['Document formatting must be preserved exactly in the live document editor.'],
                    fallback_strategy='Return the exact formatted content for the user to paste manually.',
                ),
            ])
        elif 'update' in lowered or 'publish' in lowered:
            actions.append(
                PlanAction(
                    id='request_foreground_control',
                    type='request_foreground_control',
                    description='Request approval before any visible browser interaction that could affect the user session.',
                    params={'reason': 'Potential shared-session UI interaction'},
                    risk_level='medium',
                    requires_confirmation=True,
                    execution_lane='reserved_control',
                    target_app=platform,
                    confidence=0.72,
                    evidence=['Foreground control is only proposed because the prompt suggests UI changes.'],
                    fallback_strategy='Stay in inspection-only mode if approval is not granted.',
                )
            )
        actions.append(
            PlanAction(
                id='summarize_results',
                type='summarize_results',
                description='Summarize the browser research and recommended next steps.',
                params={'kind': 'browser_summary'},
                risk_level='low',
                execution_lane='background_safe',
                target_app='ComputerAgent',
                confidence=0.9,
                evidence=['Browser actions remain proposal-first in the MVP.'],
                fallback_strategy='Return an explanation-only response if browser automation is unavailable.',
            )
        )
        return actions

    def execute(self, action: PlanAction) -> str:
        if action.type == 'browser_snapshot':
            snapshot_path = self.snapshot_dir / f"{action.id}.json"
            payload = {
                'captured_for': action.params,
                'mode': 'mock_snapshot',
                'note': 'Playwright-first execution is adapter-ready; this MVP records a structured browser snapshot placeholder.',
            }
            snapshot_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            return f'Saved browser snapshot metadata to {snapshot_path.name}.'
        if action.type == 'build_ui_map':
            return 'Built a mock DOM/accessibility UI map using the local platform recipe profile.'
        if action.type == 'open_browser_context':
            return 'Prepared an isolated browser context placeholder.'
        if action.type == 'request_foreground_control':
            return 'Foreground control request recorded for explicit approval.'
        if action.type == 'browser_navigate':
            return f"Prepared navigation to {action.params.get('url', 'the requested page')}."
        if action.type == 'browser_extract' and action.params.get('kind') == 'document_outline':
            return f"Prepared a company-specific document outline for {action.params.get('company', 'General')}."
        if action.type == 'browser_fill':
            return f"Prepared a live paste plan for the {action.params.get('document_profile', 'General')} document profile."
        return f'Browser action {action.type} recorded in mock mode.'
