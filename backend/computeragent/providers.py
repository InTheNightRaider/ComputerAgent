from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderConfig:
    provider: str
    endpoint: str
    model_mode: str


class LLMProviderAdapter:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def describe(self) -> dict[str, str]:
        return {
            'provider': self.config.provider,
            'endpoint': self.config.endpoint,
            'model_mode': self.config.model_mode,
            'status': 'adapter_ready',
            'message': 'The unified agent can fall back to deterministic planning now and connect to local Ollama or llama.cpp later.',
        }
