from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import ResearchSource


class ResearchService:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.research_dir = repo_root / 'demo_data' / 'research'

    def research(self, platform: str, prompt: str, depth: int = 2) -> tuple[str, list[ResearchSource]]:
        catalog_path = self.research_dir / f'{platform.lower()}.json'
        if catalog_path.exists():
            payload = json.loads(catalog_path.read_text(encoding='utf-8'))
            sources = [ResearchSource(**source) for source in payload.get('sources', [])[: max(depth, 1)]]
            summary = payload.get('summary', 'Local research cache available.')
            return summary, sources
        return (
            f'No cached official research bundle exists yet for {platform}. In the MVP, the agent records the gap and stays conservative.',
            [
                ResearchSource(
                    title=f'{platform} docs research placeholder',
                    domain=platform.lower(),
                    url='',
                    summary='No local cached docs were found. Add an official docs cache to improve grounded planning.',
                    official=False,
                )
            ],
        )
