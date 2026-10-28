#!/usr/bin/env bash
# Offline acceptance only; no install, credentials, API calls, deployment or sends.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
"${KULAGINA_PYTHON:-python3}" -m unittest discover -s tests -p 'test_*.py'
node tests/run-current.cjs
"${KULAGINA_PYTHON:-python3}" tools/review_demo.py
"${KULAGINA_PYTHON:-python3}" tools/assistant_demo.py
