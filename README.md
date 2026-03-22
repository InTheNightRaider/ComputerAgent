# ComputerAgent

**Tagline:** Your desktop, fully automated.

ComputerAgent is a Tauri + React desktop app with a local Python backend. This repair pass focuses on making the repo launch/package cleanly, keeping generated outputs out of git, and aligning scripts/docs with the actual Windows-first development flow.

## Findings
- The PR was choking on tracked binary assets, especially generated icon files under `src-tauri/icons/`. Those are now generated locally instead of being committed.
- The root ignore rules were incomplete for Windows/Tauri/Python build artifacts.
- `scripts/install_deps.sh` depended on an npm script path instead of directly using the repo structure, which made the install flow more brittle than necessary.
- The README did not clearly separate development launch, packaged build, Windows commands, and local asset preparation.

## Repo structure
```text
ComputerAgent/
├── backend/
├── frontend/
├── src-tauri/
├── shared/
├── scripts/
├── demo_data/
└── docs/
```

## Prerequisites
### Windows (recommended first)
Install:
- Node.js 20+
- Python 3.11+
- Rust stable + Cargo
- Microsoft WebView2 runtime
- Visual Studio Build Tools with the C++ workload

### macOS / Linux
- Node.js 20+
- Python 3.11+
- Rust stable + Cargo
- Tauri system dependencies for your platform

## Install dependencies
### Windows PowerShell
```powershell
python scripts/prepare_local_assets.py
npm install --prefix frontend
py -m pip install -r backend/requirements.txt
```

### Git Bash / macOS / Linux
```bash
./scripts/install_deps.sh
```

## Development launch
### Windows PowerShell
```powershell
python scripts/prepare_local_assets.py
npm --prefix frontend run tauri dev
```

### Git Bash / macOS / Linux
```bash
./scripts/dev.sh
```

What this does:
- prepares local placeholder icon assets required by Tauri packaging/dev
- starts the Vite frontend on port `1420`
- launches the Tauri desktop shell
- lets the Tauri app spawn the local Python backend automatically

## Packaged build
### Windows PowerShell
```powershell
python scripts/prepare_local_assets.py
npm --prefix frontend run tauri build
```

### Git Bash / macOS / Linux
```bash
./scripts/package.sh
```

Expected output locations:
- bundled artifacts: `src-tauri/target/release/bundle/`
- Windows installer target: `src-tauri/target/release/bundle/nsis/`

## Launch a built app
```powershell
python scripts/launch_built.py
```

## Root npm scripts
From the repo root you can also use:
```bash
npm run prepare:assets
npm run install:frontend
npm run install:backend
npm run dev
npm run package
npm run test:backend
```

## Why this fixes the PR issue
The repo no longer tracks generated Tauri icon binaries. Instead, source-controlled code generates them locally when needed. Combined with stronger ignore rules for build outputs and local environments, this keeps future PRs source-only and avoids PR tooling failures on generated/binary artifacts.
