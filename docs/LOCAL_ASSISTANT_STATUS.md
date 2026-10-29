# 29.10.2026 — причины защиты событий: read-only диагностический кандидат

Подготовлен standalone `src/tools/nvsu_calendar_protection.gs` / `inspectKulaginaNvsuProtectionReadOnly`: существующий явно выбранный Calendar, фиксированная неделя02–08.11, только GET metadata/events с полной ограниченной пагинацией. Один агрегатный JSON с числом событий/защищённых событий и счётчиками причин; без IDs, текстов, extension keys/values, участников и credentials. Ошибка/неполное чтение не выдаёт частичные счётчики. Никаких записей, Properties updates, отправок, триггеров или deployment.

Причины повторяют критерии существующего snapshot helper, а не доказывают ownership. Несколько причин могут относиться к одному событию; сумма счётчиков может превышать число событий. Даже если защита исчезла, событие не становится автоматически принадлежащим синхронизатору. Ledger/ownership остаются отдельным условием; автоматического adoption нет. Предыдущие11точных совпадений не отменены, повторный экспорт chunks не требуется.

8новыхNode tests first red→green; полный **590Python +168Node PASS**,6offline demos. Диагностический helper **ещё не запущен live**. Следующий необходимый вход — ручной агрегатный JSON пользователя. [Инструкция](NVSU_PRIVATE_COMPARISON.md#причины-защиты-следующий-ручной-шаг).

---

# 29.10.2026 — неделя 02–08.11 совпадает с календарём

Получены обе части пользовательского read-only снимка; целостность подтверждена общим SHA-256. Свежий публичный источник прочитан существующим `nvsu_source.fetch_week` с проверкой преподавателя/выбранной недели, статус parsed. Сравнение существующим `nvsu_sync.plan_sync` через private snapshot adapter: **11 занятий источника, 11 событий календаря, 11 точных совпадений времени/дисциплины/аудитории, 0 отсутствующих, 0 дублирующихся совпадений, 0 неизвестных событий**. Это результат для конкретной недели и пользовательского снимка, не полного семестра/атомарного live Calendar.

Все 11 событий имеют protected=true. Планировщик классифицирует их как review_overlap; это защитный запрет мутаций, а не расхождение расписания. Причина protected в этом снимке не раскрыта; нельзя предполагать конкретные заметки/участников/повторы. Ownership синхронизатора не установлен; ручные события не присваиваются. Предварительный вывод: **по снимку добавлений/обновлений/удалений не требуется**. Исполнимый план не выпущен, ready_for_apply=false, teaching_schedule_verified=false; флаг полноты календаря/запись студентов/автоматизация не включены.

В `tools/nvsu_private_snapshot.py` добавлены отдельные агрегаты exact/protected/missing/duplicate, чтобы не путать review_overlap с отсутствующими занятиями. Три новых регрессионных теста сначала завершились ошибкой отсутствующих полей, затем прошли: protected exact, duplicate exact, wrong room. Полный `bash tools/check-local.sh`: **590 Python +160 Node PASS**, 6 offline demos. Реальные календарные события/таблицы/бот/триггеры не менялись. Частные снимки/хеши/IDs не сохранены в Git.

Следующие границы: проверить остальные актуальные недели и надёжное владение ранее импортированными событиями/ledger, затем свежий read-only план перед разрешёнными изменениями. Нельзя считать exact hash match разрешением обновить/удалить существующее событие. [Подробности](NVSU_PRIVATE_COMPARISON.md).

---

# 29.10.2026 — read-only снимок для сверки НВГУ подготовлен

Новый standalone `src/tools/nvsu_calendar_snapshot.gs`: fixed week 02–08.11, только GET выбранного Calendar, полная bounded pagination, без raw IDs/названий/описаний/участников в логе; chunked private snapshot с checksum. Не запущен live. `tools/nvsu_private_snapshot.py` декодирует полный набор и использует существующий `nvsu_sync.plan_sync` для агрегатной классификации; ledger/ownership не меняет, всегда non-applicable/review required/teaching completeness false. Хеши не шифрование; время/равенство строк остаются приватными данными.

10 новых Python +9 Node tests, включая JS→Python transfer и red→green invalid-time regression. Полный `bash tools/check-local.sh`: **587 Python +160 Node PASS**, 6 offline demos. Рабочий код бота и реальные ресурсы не менялись; необходимый следующий вход — ручной read-only снимок пользователя. [Инструкция и ограничения](NVSU_PRIVATE_COMPARISON.md).

---

# 29.10.2026 — реальный Calendar TEST завершён

По предоставленному пользователем журналу `testKulaginaCalendarOnce`: `status=complete`, `create_verified=true`, `update_verified=true`, `cleanup_confirmed=true`, `cleanup_required=false`. Проверялось только временное TEST-событие 30.10.2026 10:00–10:20 (Asia/Yekaterinburg). Три запроса записи: создание, обновление, удаление; сообщений не отправлено. Повторять тест или выполнять cleanup не требуется. Это результат ручного запуска в Apps Script пользователя, не прямого доступа Codex к Google и не развёртывание нового бота.

`teaching_schedule_verified=false`: полнота занятий и отсутствие конфликтов консультаций ещё не подтверждены. Свежая read-only проверка публичного НВГУ: неделя 26.10–01.11 — «Расписание отсутствует», неделя 02.11–08.11 — 11 занятий. Это состояние источника, а не результат импорта или сравнения с календарём. Частные снимки/идентификаторы в Git не сохранены.

Следующий этап: read-only сравнение конкретной недели НВГУ с существующим календарём через имеющиеся `nvsu_calendar.py` / `nvsu_sync.py`, с сохранением ручных событий и отдельной проверкой принадлежности событий синхронизатору. До такого сравнения нет согласованного плана реальных изменений; не включать `ASSISTANT_CALENDAR_HAS_ALL_LESSONS`, запись студентов, триггеры или deployment.

Последняя полная локальная проверка кода: **577 Python +151 Node PASS**, 6 offline demos. В этом шаге изменена только документация; полный набор повторно не запускался. Успешный TEST не проверяет частичные сбои реального Calendar, Google Sheets CAS, весь консультационный сценарий или production-версию.

---

# Актуально29.10.2026: Calendar REST preview ready, CRUD pending

User actual preview13:21:43 after API activation:30Oct10:00–10:20+05,busy0,2GET,writes0. One-shot exact-window TEST CRUD helper/readonly inspect готов,577Python/151Node PASS, ещё не executed live. Owner message receipt ранее подтверждён, full timetable/production rollout/Sheets CAS не проверены. CONSULTATION_PERSONAL_RESOURCES.md.

---

# Актуально29.10.2026: owner message received, Calendar REST preview pending

Owner manual test API ack + human receipt подтверждены по пользовательским данным. Calendar native metadata/timezone доступны; REST/write/full timetable ещё не проверены. Standalone GET-only preview готов,577Python/140Node PASS, ещё не executed live. CONSULTATION_PERSONAL_RESOURCES.md.

---

# Актуально29.10.2026: manual metadata successful, send probe pending

Пользовательский JSON подтвердил реальный getMe/Calendar read metadata/timezone; owner identity/delivery/send/write/full timetable ещё не проверены. Direct runtime credentials в Codex не появились. Owner-only durable once send helper подготовлен, не выполнялся на реальном ресурсе.577Python/130Node PASS. CONSULTATION_PERSONAL_RESOURCES.md.

---

# Актуально29.10.2026: разрешены owner-resource тесты

577Python/120Node PASS. Standalone metadata-only Apps Script probe подготовлен, не установлен/не запущен. Реального bot token/ready Google connection из чата нет; selectors сами доступ не доказывают. Отдельные test resources больше не требуются по user override. Инструкция без secret transfer/publication: CONSULTATION_PERSONAL_RESOURCES.md. Existing data/poller/webhook/triggers/deploy не менялись.

---

# Актуально29.10.2026:577Python/110Node PASS

Bound consultation flow проверен целиком на synthetic inbox/Calendar/notice mocks,6demos. Safe legacy prefix replacement сохраняет manual suffix. Google Sheets source CAS/real bindings/full-import verification/rollout отсутствуют. Нужен выбор отдельных test bot/Calendar для следующей разрешённой приёмки: CONSULTATION_SANDBOX_ACCEPTANCE.md. Production не менялся.

---

# Дополнение29.10.2026: original owner consent

Registry и bound worker готовы,572Python/110Node PASS. Original source/event evidence до confirm, stable timestamp/replay, atomic local publication+claim, no locked Calendar reads. Все API mocks/default off, no production. CONSULTATION_CONSENT.md.

---

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
