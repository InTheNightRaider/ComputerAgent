# Windows installer and update publishing

This project is now configured for a **Windows-first NSIS installer** build and for **signed updater artifacts** using Tauri's official updater flow.

## What is configured
- `src-tauri/tauri.conf.json` bundles **NSIS** installers.
- `createUpdaterArtifacts` is enabled so signed updater artifacts are generated during Tauri builds.
- `.github/workflows/windows-release.yml` publishes Windows releases from git tags like `app-v1.0.0`.

## One-time setup

### 1. Generate your updater signing key
Run this from the repo root in PowerShell:

```powershell
npm --prefix frontend run tauri signer generate -- -w "$HOME/.tauri/computeragent.key"
```

Store the generated **private key** safely. Never commit it.

### 2. Add GitHub repository secrets
Add these repository secrets:
- `TAURI_SIGNING_PRIVATE_KEY`
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`

You can store either the private key content or a secure path/value depending on your release environment.

### 3. Local Windows installer build
From PowerShell:

```powershell
python scripts/prepare_local_assets.py
npm install --prefix frontend
npm run package:windows
```

Expected installer output:
- `src-tauri/target/release/bundle/nsis/`

## Publishing an update

### Option A: push a version tag

```powershell
git tag app-v0.1.0
git push origin app-v0.1.0
```

That triggers `.github/workflows/windows-release.yml`, which uses Tauri's GitHub release flow to build the Windows installer and signed updater artifacts.

### Option B: run manually
Use **Actions -> publish-windows -> Run workflow** in GitHub.

## Desktop installation flow
1. Download the generated `*-setup.exe` from the GitHub release assets.
2. Run the installer on Windows.
3. Install ComputerAgent normally from the desktop installer.
4. Publish newer tagged releases to deliver updated signed installer/update artifacts.

## Notes
- This uses the official Tauri updater artifact flow, which requires signing and should not be used without protecting the private key.
- The workflow is intentionally Windows-only for now so the installer/update path stays focused and predictable.


## Offline/imported update flow

If you do not want to rely on the online updater path, you can also distribute the signed installer/update artifacts as files. In practice that means shipping the generated Windows installer (`*-setup.exe`) or the signed updater bundle from the GitHub release assets, then having the user run/import that file locally to move to the newer version.
