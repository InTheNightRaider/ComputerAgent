# Open-source model stack for the 8GB profile

This repo now includes a pinned open-source model/runtime manifest at `shared/model-stack-8gb.json` plus persistent installation-state tracking under the local runtime config directory.

## Selected vs ready
ComputerAgent now distinguishes four different ideas clearly:
- **Selected**: the component is pinned in the manifest.
- **Prepared**: the installer flow resolved expected target paths, but required artifacts are still missing.
- **Installed**: required artifacts for that component were found and registered locally.
- **Runnable**: the provider/runtime validation confirmed the required installed components are present *and* the local model endpoint is responding.

Installation states are persisted per component as:
- `not_installed`
- `prepared`
- `downloading`
- `installed`
- `failed`
- `deferred`

## What the default 8GB profile enables
The default `8gb-open-source` profile enables the components that are the best fit for a first local desktop install:
- **Mistral-7B-Instruct (GGUF)** via `llama.cpp`
- **Mistral tokenizer** utilities
- **e5-large-v2** for retrieval
- **Tesseract 5** for OCR (optional for runtime)
- **Whisper tiny** for speech-to-text (optional for runtime)
- **Rust rule engine** for local policy/rules
- **Qdrant** for local vector storage

## What is tracked but deferred by default
The manifest also tracks the larger open-source components you requested, but keeps them disabled in the default 8GB profile because of RAM/VRAM pressure or total stack size:
- `bge-large-zh-en`
- `openclip-vit-h-14`
- `video-clip-b`
- `faster-rcnn-r50-fpn`
- `flamingo-mono-v2`
- `stable-diffusion-1.5-fp16`
- `peft-lora`

## Prepare the stack
Dry run:

```bash
npm run install:model-stack:dry-run
```

Persist install/prepared state for the default profile:

```bash
npm run install:model-stack
```

Register existing local artifacts explicitly:

```bash
python scripts/install_open_source_stack.py   --local-artifact mistral-7b-instruct-gguf:model:C:/models/mistral-7b-instruct.gguf   --local-artifact mistral-tokenizer:tokenizer:C:/models/tokenizer.model   --local-artifact e5-large-v2:weights:C:/models/e5-large-v2/model.safetensors   --local-artifact rust-rule-engine:engine:C:/ComputerAgent/models/rule-engine.wasm   --local-artifact qdrant:binary:C:/ComputerAgent/models/qdrant.exe
```

## Validate the runtime
Once the backend is running, validate the local stack:

```bash
curl -X POST http://127.0.0.1:8765/models/validate
```

That returns both:
- `planning_runtime` readiness for the default LLM planning path
- `full_stack` readiness for the broader default 8GB stack

## End-to-end local planning path
The minimally working local inference path is:
1. Register/install the required artifacts for `mistral-7b-instruct-gguf`, `mistral-tokenizer`, and `e5-large-v2`.
2. Run a local `llama.cpp`-compatible server endpoint.
3. Set `planner_mode` to `llm` and point `local_model_endpoint` to that endpoint.
4. Send a planning request through the desktop app or `/messages` API.

If the model files or endpoint are missing, the backend returns a clear fallback note instead of pretending the stack is runnable.

## Desktop update flow
ComputerAgent supports two update paths:
1. **Online signed updates** via the Tauri/GitHub release workflow.
2. **Offline/imported updates** by distributing the signed installer or bundled release artifacts as files.

See `docs/windows-installer-updates.md` for the release/update process.

## Safety note
This stack is open-source, but the app still preserves baseline safety checks for destructive or high-risk actions. The repo does **not** remove all guardrails.
