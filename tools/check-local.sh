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
node --test tests/legacy-file-recovery.cjs
node --test tests/legacy-file-review.cjs
node --test tests/legacy-update-queue.cjs
node --test tests/legacy-reply-recovery.cjs
node --test tests/legacy-task-binding.cjs
node --test tests/legacy-sheet-literals.cjs
node --test tests/legacy-reply-notifications.cjs
node --test tests/legacy-reply-notification-review.cjs
node --test tests/sheet-literal-probe.cjs
node --test tests/nvsu-approved-import.cjs
node --test tests/google-actions-bridge.cjs
"${KULAGINA_PYTHON:-python3}" tools/review_demo.py
"${KULAGINA_PYTHON:-python3}" tools/assistant_demo.py
"${KULAGINA_PYTHON:-python3}" tools/decision_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_execution_demo.py
"${KULAGINA_PYTHON:-python3}" tools/consultation_workflow_demo.py
