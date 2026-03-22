#!/usr/bin/env bash
set -euo pipefail
python scripts/prepare_local_assets.py
npm install --prefix frontend
python -m pip install -r backend/requirements.txt
