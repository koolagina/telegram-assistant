#!/usr/bin/env bash
# Offline acceptance only; no install, credentials, API calls, deployment or sends.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
"${KULAGINA_PYTHON:-python3}" -m unittest discover -s tests -p 'test_*.py'
node tests/run-current.cjs
node --test tests/consultation-export.cjs
node --test tests/consultation-connection-probe.cjs
node --test tests/consultation-owner-message.cjs
node --test tests/consultation-calendar-preview.cjs
node --test tests/consultation-calendar-smoke.cjs
node --test tests/nvsu-calendar-snapshot.cjs
node --test tests/nvsu-calendar-protection.cjs
node --test tests/apps-script-backup-setup.cjs
node --test tests/legacy-access-ack.cjs
node --test tests/nvsu-approved-import.cjs
"${KULAGINA_PYTHON:-python3}" tools/review_demo.py
"${KULAGINA_PYTHON:-python3}" tools/assistant_demo.py
"${KULAGINA_PYTHON:-python3}" tools/decision_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_execution_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_workflow_demo.py
