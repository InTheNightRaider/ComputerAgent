# ComputerAgent integrated MVP architecture

## Final folder structure
- `frontend/` — React + TypeScript desktop UI with unified chat, sidebar, security/history/settings views, and right-hand approval drawer.
- `src-tauri/` — Tauri shell, packaging config, icons, and local Python backend lifecycle management.
- `backend/` — one shared local-agent backend with routing, planner, policy, execution, research, browser, security, memory, audio, and storage modules.
- `shared/` — unified action schema and sample plan payloads.
- `demo_data/` — safe demo files, browser recipes, local research cache, and benign security examples.
- `docs/` — setup, architecture, packaging, and next-step notes.

## Single-agent architecture
ComputerAgent runs as one local “mind” with these shared layers:
1. **Chat + project memory**: projects, chats, and messages are stored in SQLite and exposed through one chat-first UX.
2. **Unified intent router**: the agent classifies each message into browser, research, security, file, or general help while staying inside one conversation loop.
3. **Shared planning system**: every non-trivial action becomes one structured plan format with execution lanes, evidence, fallback strategy, and target app metadata.
4. **Shared policy layer**: validation runs before execution and enforces directory scopes, browser/domain preferences, destructive-action warnings, and defensive-only security behavior.
5. **Shared execution system**: file actions execute directly, browser actions stay DOM/accessibility-first through an adapter, research uses local cached sources, and security scans/monitors run as background-safe tasks.
6. **Shared observability**: runs, messages, findings, rollback data, and JSONL audit logs all live in local storage.

## Implemented MVP behavior
- **Files**: list, rename, move, copy, mkdir, quarantine/delete-to-backup, summarize, rollback.
- **Browser/web**: research-first plans, isolated browser-context actions, DOM/accessibility-first UI-map planning, snapshots, and supervised foreground-control requests.
- **Research**: local official-doc cache lookup with per-source summaries and platform grounding.
- **Security**: quick scans, live monitor start/stop, suspicious file heuristics, and findings persistence.
- **Voice**: local-first composer microphone using a frontend speech adapter when available, with graceful fallback.

## Cleanly stubbed for later
- Full Playwright execution beyond the adapter-ready mock path.
- Local speech model integration beyond Web Speech fallback.
- Deeper multi-platform docs crawling and richer browser locator memory.
- YARA/ClamAV integrations when local binaries are installed.
