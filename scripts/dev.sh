#!/usr/bin/env bash
set -euo pipefail
python scripts/prepare_local_assets.py
npm --prefix frontend run tauri dev
