from __future__ import annotations


class VoiceTranscriptionService:
    def status(self) -> dict[str, str]:
        return {
            'mode': 'web_speech_fallback',
            'status': 'frontend_managed',
            'message': 'The MVP uses a local-first frontend speech adapter when the Web Speech API is available and falls back to editable manual input otherwise.',
        }
