# Дополнение29.10.2026: local status + notices

Fixture SQLite CAS/finalization/outbox готовы;548Python/110Node PASS. Real Google Sheets claim/CAS/Telegram notifications не подключены,6demos только mocks. Original consent registry и live evidence/writer coordination/verifier/rollout остаются. CONSULTATION_WORKFLOW.md.

---

# Дополнение 29.10.2026: Calendar-stage executor

Disabled-by-default candidate с original-evidence preflight/ETag/claims/reconciliation готов;521Python/110Node PASS. Mock-only HTTP, реального Google вызова нет. Только Calendar stage: source_status=not_written,notifications=not_sent. Live binding/consent bridge/source CAS/координация writers/finalization/уведомления/приёмка — отдельно. Контракт CONSULTATION_EXECUTOR.md.

---

# Дополнение 29.10.2026: action worker

Отдельный локальный consultation worker готов: atomic handler+receipt, separate UI dispatch, defaults off. 24 новыхtests, полный483Python/110Node PASS. Demo synthetic, sender mock. Никакого real action executor/authoritative Sheet update/student notification/развёртывания. Контракт CONSULTATION_WORKER.md.

---

# Дополнение 29.10.2026: источники консультаций

Read-only helper/нормализаторы и optional source_version для queue refs готовы;459Python/110Node PASS. Полнота не выводится из пустого Calendar: trusted verifier attestation required, в demo только fake. Реальные Google reads/writes отсутствуют, exporter не установлен. Следующие границы подключения: live collection/auth/ownership, verifier законченного НВГУ import, CAS/dispatcher/executor. Контракт CONSULTATION_FEED.md.

---

# Дополнение 29.10.2026: решения по консультациям

Локальный sandbox core/UI сохраняет планы approve/reject/propose с отдельным подтверждением, без реального исполнения. Полная проверка: 430 Python +101 Node PASS; 30 новых тестов, пример CONSULTATION_ACTIONS_DEMO.md. Не подключено к рабочему боту или read-only worker. Нужны live sources/полнота НВГУ, отдельный dispatcher/executor и принятие студентом предлагаемого времени; реальные статусы не менялись. Контракт CONSULTATION_ACTIONS.md.

---

# Локальный кандидат единого помощника — 29.10.2026

Основной GAS-кандидат: `src/telegram_assistant_v2_0_5_candidate.gs`; он не изменён этим этапом. Python-компоненты находятся в `tools/`. Архивные snapshots сохранены. Какая версия реально развёрнута, по локальному репозиторию не подтверждено; новых deploy/триггеров/webhook не выполнялось.

| Компонент | Реализовано локально | Ещё не подключено/не доказано |
|---|---|---|
| Материалы | Проверка source metadata/hash, Word text/drafts, версии и история | Live bindings, полный semantic validator; публичный DOCX adapter тестировался моками |
| Проверка работ | Manifest PPTX count, version-bound minimum, exact evidence quotes | Научная оценка, авторство, графика/формы, автооценка/проходной порог |
| Хранилище результатов | MaterialCatalog SQLite, immutable done, needs_recheck | Реальный ingestion/backup runtime; done не означает принятую отработку |
| Принадлежность | ReportRegistry private SQLite, immutable links, unique check, retry | Trusted publication adapter для реальных submission/enrollment |
| Права | AccessPolicy, PolicyStore version snapshots/CAS/no older fallback | Реальная authentication и административная процедура подтверждения/отзыва |
| Запросы | Self list/page/buttons, teacher report, current-policy gating, verified-input TG parser | Mock-tested fixed-origin HTTP и dispatch ledger добавлены; store-before-ack inbox и bounded ReportWorker добавлены; остаются live runtime/sends/delivery |
| Очередь решений | Owner-only /decisions,3sources,filters,pages,details,partial warnings | Live consultation feed, отдельные подтверждения действий/resolutions |
| Учебный журнал | Read-only локальное чтение структуры XLSX | Полный расчёт успеваемости, синхронизация отметок, запись реального журнала |
| Production | Исходники и локальные тесты | Разрешённая sandbox-приёмка, bindings, rollout |

## Проверка одной командой

```bash
bash tools/check-local.sh
```

Нужны Python с зависимостью из `requirements-lecture.txt` и Node.js. Скрипт не устанавливает пакеты, не использует секреты, сеть, рабочие таблицы или отправки. Создаёт только временные SQLite в synthetic demos, удаляемые при завершении. Отдельные команды:

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/run-current.cjs
python tools/review_demo.py
python tools/assistant_demo.py
python tools/decision_demo.py
```

Подтверждено: **400 Python +101 Node PASS**. Демо прошло работу с настоящими локальными SQLite, собственную/чужую кнопку, повторную загрузку, страницы, перезапуск, отзыв прав, stale write и сбои публикации до/после accepted commit. Ни один такой тест не подтверждает реальную доставку или работу production API.

## Данные и восстановление

Все registry/policy entries в демо искусственные. Не переносить `synthetic_policy`/confirmed fake bindings в рабочую систему. `PolicyStore` сам по себе пуст и deny-all до явного trusted provisioning. Снимок JSON — приватные данные, не конфигурация из публичного запроса и не место для секретов.

Данные SQLite/WAL и `.assistant-state/` исключены из Git. Хранилища имеют отдельный project namespace, directory0700/file0600; это локальные права файлов, не шифрование или защита от администратора машины. Результат фиксируется до публикации immutable link: незавершённая публикация повторяется, не меняя владельца. Для замены ошибочной ownership relation нужен отдельный проверяемый процесс, не overwrite.

Backup/restore нескольких DB должен быть согласован; не копировать только main SQLite без WAL. Старый backup policy может вернуть ранее отозванные grants: внешний anti-rollback witness и реальная административная сверка не реализованы. Повреждённый текущий снимок не заменяется более старым автоматически.

## Дальнейшая последовательность

1. Подготовить проверяемый authentication/provisioning adapter для отдельной тестовой среды; не считать Telegram username, email из текста или ChatGPT args подтверждённой identity.
2. Подключить trusted ingestion и актуальные материалы, утвердить полноту критериев. Проходной порог нужен до автоматического принятия; сейчас все отчёты требуют преподавателя.
3. Связать реализованные HTTP/inbox/dispatch кандидаты в серверный runtime с единственным polling owner, проверенным provisioning и операторской сверкой blocked/unknown; не запускать рядом с рабочим GAS poller. Повторная policy и prepared/API success/delivery уже проверены локально, не на реальной доставке.
4. Провести отдельно разрешённую интеграционную приёмку на test bot/resources, затем согласованный rollout. Реальные письма, изменения журнала и production не входят в текущие локальные действия.

Telegram adapter принимает только инъецируемый trusted verified polling transport; произвольный JSON не аутентифицируется. Новый модуль не выполняет getUpdates/offset/ack и не подключён к существующему poller. Fake numeric subjects демонстрации не являются реальными bindings.

HTTP-клиент и dispatch ledger теперь реализованы и проверены только mock transport. Network/writes/dispatch default off; реальных API-вызовов нет. Durable inbox/cursor реализован и проверен моками; live runtime/retention/idle reset/единственный polling owner требуют sandbox-приёмки; api_confirmed не delivery, unknown не повторяется автоматически. Подробности TELEGRAM_TRANSPORT.md.

ReportWorker теперь связывает inbox→reports→dispatch и восстанавливает mark по API receipt без повторной отправки; только bounded local step, не live scheduler/полный bot dispatcher. Unknown/rejected → blocked для оператора; unsupported остаётся pending. Общий dispatcher/backoff/monitoring/операторский recovery и callback acknowledgement ещё не реализованы.

Owner decision menu реализован локально и opt-in подключён к adapter/worker, но не к рабочему GAS. Демонстрация DECISION_QUEUE_DEMO.md, контракт DECISION_QUEUE.md. Нормальный inflight оставляется pending, не выдаётся за сбой без подтверждения orphan; old statements о безусловной blocked маркировке inflight superseded.
