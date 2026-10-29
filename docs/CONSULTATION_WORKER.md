# Обработка кнопок консультаций — локальный кандидат

29.10.2026. `tools/consultation_worker.py` соединяет **существующие** TelegramInbox, ConsultationActions и DispatchLedger. Это bounded local worker для synthetic action sandbox, без polling/реального сервера. Нет Calendar/Google Sheets executor, настоящих отправок, callback acknowledgement или развёртывания. Исходный GAS-кандидат и все Google ресурсы сохранены.

## Два отдельных результата

1. `ConsultationActions.process_update` под одной private SQLite-транзакцией выполняет локальный handler и сохраняет private ответ в `action_updates`. Вложенные preview/confirm/cancel используют SAVEPOINT, поэтому локальные status/intent/plan/receipt либо фиксируются вместе, либо все откатываются. Внешние вызовы в этой транзакции запрещены.
2. После commit `ConsultationWorker` передаёт сохранённый **ответ интерфейса** в существующий DispatchLedger. Fresh callback только заново проверяет права владельца; он не вызывает handler, не создаёт intent/plan и не пишет решение. UI send использует отдельный durable claim/outcome.

`api_confirmed` здесь относится только к mock-проверенному ответу интерфейса Telegram, **не** к принятию/изменению встречи, доставке сообщения или уведомлению студента. Meeting plan остаётся `execution=not_executed`; notification-намерения плана не выполняются этим worker. В этом этапе все sender функции — моки.

## Маршрутизация и граница доверия

Только существующий private TelegramInbox, куда ранее сохранялась verified batch. Inbox JSON сам по себе не доказывает происхождение: настоящий collection/authentication остаётся отдельной задачей. Bot/project должны совпасть у inbox, DispatchLedger и явно привязанного action store; `bot_id` не задаётся Telegram-командой.

- Локальная команда `/consult_request ID` показывает карточку, `/consult_propose REF YYYY-MM-DD HH:MM` подготавливает предложение времени. Это **не установленные команды рабочего бота**.
- Callback `con:*` допускается только из private chat с совпадающими numeric from/chat ID, `is_bot=False`, от сообщения настроенного бота, с ограниченным ASCII payload. Identity Context создаёт adapter, роль не берётся из текста.
- Настроенный владелец должен иметь текущий `personal.read`: gate перед обработкой, внутри claim и после handler, отдельно перед UI dispatch. Студент/второй преподаватель не получают сохранённый ответ или право решения.
- `/progress`, другие команды, group/foreign-bot callbacks остаются pending/deferred для других handlers. Worker не заменяет весь bot dispatcher; без общей маршрутизации первые100 неподдержанных updates могут удерживать backlog.

`step(actions_enabled=False,dispatch_enabled=False)` выключен по умолчанию. `actions_enabled=True` позволяет только локальную обработку. Без dispatch остаётся `reply_ready` и pending inbox; следующий запуск использует receipt без повторного handler. Флаги не разрешают работать с настоящими ресурсами или запускать live poller параллельно действующему GAS.

## Повторы, сбои и восстановление

Private `action_updates` содержит update ID, canonical source payload hash, subject, reply JSON и reply hash. Сохранённый reply включает private callback tokens и текст: не логировать/экспортировать в чат/Git; private WAL/backup правила обязательны.

- Повтор update с тем же source hash/subject возвращает тот же reply при текущем доступе, без нового handler. Изменившийся input или испорченный receipt требует сверки; не перезаписывается.
- Сбой записи receipt, невалидный reply, revoke во время handler или остановка процесса откатывают локальное решение и receipt. Повтор допустим, поскольку никаких внешних side effects в транзакции не было.
- Reply получен, но UI ещё не отправлен: после restart читается сохранённый receipt, handler не повторяется. Старый preview не продлевается, истёкшая кнопка не создаёт новый intent сама.
- API-confirmed/cancelled UI outcome → handled; unknown/rejected → blocked без blind resend. active/inflight остаётся pending, не объявляется автоматически orphan/error. Для проверенного orphan требуется отдельный operator workflow.
- Если inbox mark не сохранился после API success, следующий запуск восстанавливает mark из DispatchLedger без старого private reply, handler или повторной отправки. Восстановление processing mark не является новым доступом к данным: допустимо и после revoke.
- Revoke после локального commit, до send: reply dispatch отменяется, уже сохранённый **локальный** plan не теряется и не исполняется. Реальный executor обязан отдельно повторять авторизацию и source/Calendar preconditions; в этом worker его нет.

## Локальная схема

`ConsultationActions` получает optional `bot_id`; без явного значения update worker не запускается. При первом явно настроенном открытии action store записывается immutable bot binding в `action_meta`; другой bot отвергается.

Старый synthetic v1 store с четырьмя таблицами получает **добавочную** `action_updates`; booking/intent/plan/owner namespace сохраняются. Миграция и bot binding находятся в одной транзакции. Не применять этот sandbox как миграцию рабочих Google данных или как mirror исходной таблицы. Тест подтверждает сохранность старого плана и его idempotent recovery. Существующие прямые локальные API и отсутствие bot_id совместимы, обработка updates без binding запрещена.

## Проверка

`python -m unittest discover -s tests -p test_consultation_worker.py`: **24 PASS**. Сначала тесты падали до появления модуля. Проверены две конкурентные connection, один handler, rollback локального решения при receipt insert failure/invalid reply/revoke/KeyboardInterrupt, restart, corrupt reply, bot binding/migration, forged/group callbacks, unknown send, mark failure, active peer и proposal replay.

Полный `bash tools/check-local.sh`: **483 Python PASS +110 Node PASS**, включая4offline demos. [Пример диалога](CONSULTATION_ACTIONS_DEMO.md) теперь проходит этот worker, нормализаторы источников и fake sender. Настоящих Apps Script/Telegram/Calendar/Sheets integration tests не было.

| Дефект/риск | Причина | Изменение | Тест/результат | Остаток |
|---|---|---|---|---|
| Повторное решение при retry ответа | Handler вызван внутри send preparation | Local handler/receipt atomic, read-only fresh send gate | Repeated prepare/restart PASS | Реальный Calendar executor отдельно |
| План сохранён, ответ потерян | Разные локальные commit | SAVEPOINT внутри outer update transaction | Receipt failure/stop rollback PASS | Несколько внешних сервисов не атомарны |
| Private ответ после revoke | Cached reply без новой policy | Owner gate перед dispatch | Revoke-before-send PASS | Внешняя authentication не подключена |
| Дубль после send success/mark failure | Повтор обработки pending inbox | Recovery по durable UI receipt без handler/send | Mark failure + revoke PASS | Coordinated backups/orphan recovery |
| Дубль при unknown send | Слепой retry | Blocked unknown/rejected; inflight pending | Mock timeout/stop/peer PASS | Нужна операторская сверка |
| Чужой bot/project использует локальные решения | Отсутствие stable binding | Explicit metadata + triple namespace/bot match | Mismatch/rebind/old-store preservation PASS | Реальные bindings только после sandbox-приёмки |

Следующие отдельные компоненты: verified live identity/collection/ownership/import completeness, source CAS/preflight и external executor с per-operation uncertain recovery; затем student agreement на предложенный перенос. До отдельного разрешения реальные Google/Telegram вызовы, триггеры и deploy не запускать.


## Отдельный Calendar-stage candidate — 29.10.2026

[CONSULTATION_EXECUTOR.md](CONSULTATION_EXECUTOR.md): disabled-by-default stage с original source/event evidence и read-only reconcile. Старые unbound local plans не исполняются автоматически. Ни actual APIs, ни source writes/notifications; external races требуют source CAS/writer coordination до live приёмки.521Python/110Node PASS,5offline demos.
