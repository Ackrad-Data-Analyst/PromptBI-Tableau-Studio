#!/usr/bin/env bash
set -euo pipefail

python3 -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or newer is required'"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[tableau,static,dev]'

echo "Setup complete. Run: bash run.sh"
