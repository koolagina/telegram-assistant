#!/usr/bin/env bash
# Offline acceptance only; no install, credentials, API calls, deployment or sends.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
"${KULAGINA_PYTHON:-python3}" -m unittest discover -s tests -p 'test_*.py'
node tests/run-current.cjs
node --test tests/consultation-export.cjs
node --test tests/consultation-connection-probe.cjs
node --test tests/consultation-owner-message.cjs
"${KULAGINA_PYTHON:-python3}" tools/review_demo.py
"${KULAGINA_PYTHON:-python3}" tools/assistant_demo.py
"${KULAGINA_PYTHON:-python3}" tools/decision_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_execution_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_workflow_demo.py
