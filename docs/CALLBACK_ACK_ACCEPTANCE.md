# Техническое подтверждение кнопок Telegram

30.10.2026 — **локальный блок, в рабочем боте не включён**. Реальных Telegram запросов и изменений ресурсов нет. Пользователь без компьютера, действий сейчас не требуется.

## Проблема и решение

Python candidate подготавливал ответ на callback, но не имел пути `answerCallbackQuery`: это могло оставлять Telegram-индикатор нажатия до истечения тайм-аута. Добавлен отдельный default-off канал технического подтверждения, без смешения с ответом/доставкой сообщения.

- `tools/callback_ack.py`: `CallbackAckLedger`, отдельный приватный SQLite-файл schema v1 и namespace/bot binding, WAL/FULL, durable claim до injected API вызова. Сохраняет update ID, SHA-256 query ID, phase и фиксированный error code; не query ID, текст, URL или payload. Хеш не является гарантией анонимизации. Дедупликация по обоим IDs: несовпадение update/query запрещено. Состояния sending/api_confirmed/api_rejected/unknown, sending выдаётся как inflight_or_unknown. Ретраев для unknown/rejected/sending нет, reset/cleanup не добавлены. Схемы существующих inbox/dispatch не менялись.
- `tools/telegram_http.py`: отдельный `acknowledge`, только fixed-origin `answerCallbackQuery`, exact payload `callback_query_id`. Требует verified bot + explicit writes configuration. Text/alert/URL и произвольные методы отвергаются. По умолчанию network/writes по-прежнему выключены.
- `tools/report_worker.py`: необязательная пара `callback_ledger`/`acknowledge`, оба default=None; проверяется совпадение namespace/bot. После доверенной маршрутизации ACK выполняется **до** потенциально долгого message send, вне SQLite-транзакции. Затем existing fresh preparation заново проверяет policy/версии перед данными. ACK не разрешает доступ и может технически подтвердить нажатие, закончившееся cancelled, без текста/данных.
- При recovery уже существующей terminal business receipt worker может восстановить только техническую ACK-попытку, не отправляя сводку повторно. `verified_callback_query_id` проверяет private sender/chat и исходного bot; это structural helper для ранее проверенной durable polling очереди, не аутентификация произвольного JSON. Unsupported updates остаются deferred и автоматически не подтверждаются.
- `tools/academic_readiness.py`: optional callback state metadata/counts, namespace validation и fixed `callback_outcomes_need_review`; никакого retry/repair. Live flags остаются false.
- `tools/academic_overview_demo.py`: настоящий временный SQLite inbox→menu→callback→mock send/ACK→revoke, только искусственные данные и агрегатный вывод.

## Частичные сбои

ACK и business response имеют разные квитанции. API-confirmed ACK не доказывает доставку сообщения, принятие работы, состояние UI или доступ студента. API response success лишь подтверждает принятие технического запроса API; поведение настоящего Telegram-клиента не проверено.

Тайм-аут ACK не повторяет message send; timeout message send не запрещает отдельно подтверждённый ACK. Сбой ACK storage до claim оставляет update pending; после successful business receipt recovery не отправляет message заново. Если API принял ACK, но finalize потерян, durable sending не повторяется: требуется сверка. Callback может быть просрочен — 400 фиксируется как API rejection, без автоматического retry. Никакой exactly-once гарантии нет.

ACK выполняется после bounded local routing; тяжёлое сетевое чтение в factories/loaders по-прежнему запрещено. Он предшествует message send, но мгновенная реакция UI не гарантируется. Нельзя включать Python polling рядом с рабочим Apps Script poller.

## Тесты

26 новых тестов: `tests/test_callback_ack.py` (13), `tests/test_callback_worker.py` (10), `tests/test_callback_http.py` (3). До реализации воспроизведены отсутствующий module/method и unsupported worker parameters.

Проверены restart/duplicate/query-conflict, no raw query storage, default-off, private files/namespace, claim outside network transaction, timeout/rejected/nonboolean results, parallel claim, потеря ACK storage после API acceptance, независимость business/ACK, revoked callback без данных, mark recovery, paired/matching configuration, private group/foreign bot checks, read-only diagnostics unknown, ACK до message send, fixed HTTP endpoint и отказ text/URL/arbitrary method.

Полный `bash tools/check-local.sh`: **773 Python +448 Node PASS, 11 offline демонстраций**. Лог `/tmp/kulagina-callback-final-check.txt`. Целевой запуск: `python3 -m unittest discover -s tests -p 'test_callback_*.py'`.

| Проблема | Причина | Изменение | Тест / итог | Остаток |
|---|---|---|---|---|
| Нет подтверждения кнопки | Worker имел только sendMessage | Отдельный no-text ACK до send | Worker/HTTP/order PASS | Реальный UI не проверен |
| Повтор ACK при replay | Нужна отдельная квитанция | Durable CallbackAckLedger | Duplicate/restart/parallel PASS | Unknown требует сверки |
| ACK принимают за доставку | Техническое и бизнес-подтверждение различаются | Отдельное поле callback_ack и отдельный ledger | Independent failure PASS | Delivery по-прежнему unknown |
| Сбой ACK повторяет сводку | Общая обработка ошибок небезопасна | Recovery через existing business receipt | Mark/storage recovery PASS | Retention/backup отдельного ledger нужны |

## Что осталось для подключения

Отдельно согласовать реальный transport и ограниченный test actor, открыть приватный постоянный callback ledger с тем же namespace/bot, явно передать `client.acknowledge`, обеспечить backup/retention и мониторинг. Проверить один callback, stale/revoked callback, API rejection и восстановление в ограниченной среде. Existing source relay не исполняет этот Python runtime. Никаких live ресурсов/секретов/триггеров/deployment этот блок не меняет.
