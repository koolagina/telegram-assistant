# Календарный этап консультации — кандидат, 29.10.2026

Реализованы `tools/consultation_executor.py`, `consultation_calendar.py` и offline `consultation_execution_demo.py`. Это отдельный **выключенный по умолчанию** Calendar-stage executor. Все вызовы в этом этапе — injected mocks, включая HTTP session существующего GoogleCalendarAdapter. Реальные Google/Telegram ресурсы, статусы заявок, почта, триггеры и развёртывание не затрагивались. GAS snapshots и 11 колонок сохранены.

## Что исполнимо

Только лично подтверждённые approve/reject и только предварительный резерв уже существующей заявки. Create отсутствует, перенос по propose запрещён. Подтверждение меняет выбранные поля того же event; отказ удаляет только точно связанный event. Время не меняется, другие события не затрагиваются.

`BoundPlan` должен поступать из доверенного immutable registry решения владельца: исходный confirmed plan, owner/calendar ID, **оригинальная** версия строки, fingerprint события (включая ETag/время/текст/приватные свойства) и время решения. Конструктор этого типа не доказывает consent: его выдача должна быть частью trusted owner-confirmation bridge, не публичного запроса/LLM/студенческой команды. Такой live bridge пока отсутствует.

Прежние local action plans не содержат этой исходной привязки и **не принимаются автоматически**. Нельзя дооформлять старое решение по вновь прочитанной строке/событию: это разрешило бы изменить тему/адресата после решения преподавателя. Demo создаёт BoundPlan только из искусственных данных и синтетического подтверждения.

## Проверка до Calendar запроса

- Текущий `personal.read` настроенного владельца перед private reads и непосредственно перед mutation. Student binding должен быть confirmed/active, current Student active; адресат в исходном plan должен соответствовать той же identity, что и subject текущей строки. Отдельное право на запись реальных ресурсов этим не выдаётся.
- Plan age меньше5мин, время aware, approve только будущее, будни09–18,20мин, обед11:40–12:20. Это срок исполнения конкретного подтверждения, не TTL резерва. Более позднее исполнение требует нового проверенного решения, а не фонового удаления события.
- Полная свежая ConsultationFeed, exact original row revision/status pending/start/event ID. После Calendar reads строка сверяется повторно через require_revision. Это read guard, **не Google CAS**.
- Trusted HoldBinding calendar/event/request/start/end. Title/description/наша метка операции сами по себе ownership не доказывают. Полный свежий BusySnapshot, проверенная полнота занятий и диапазон, own hold, отсутствие других пересечений для approve.
- Актуальный CalendarRecord должен совпасть с оригинальным fingerprint/ETag. All-day/recurrence/attendees/attachments/conference/special events защищены. Уже имеющаяся метка прежней попытки требует сверки, не перезаписывается новым запуском.

Preflight выполняется до claim и после него, **вне SQLite-транзакции**. Если источник/права/занятость/ETag изменились после claim, mutation не вызывается, исход blocked_preflight. Сбой записи такого исхода оставляет durable claim, возвращает needs_recovery и не разрешает повтор.

## Журнал и повтор

Отдельная private SQLite WAL/FULL с namespace/owner/calendar/source binding. До возможного внешнего side effect фиксируется `applying` + immutable request/hash/plan hash. Unique plan ID и уникальные booking/event ID препятствуют двум конкурирующим начальным решениям по одному резерву. Журнал не меняет исходные планы и authoritative Sheets.

Повтор/перезапуск читает receipt, не вызывает mutation. Applying отображается inflight_or_unknown: это может быть активный peer. Unknown/rejected/blocked не сбрасываются автоматически. Другой plan для уже claimed booking/event требует операторской сверки. Поддержка последующей отмены уже подтверждённой встречи — отдельный тип операции, здесь его нет.

В сети не держится SQLite lock. Если процесс прервался или сохранение API receipt не удалось после принятого запроса, остаётся durable claim. Уникальные constraints не обеспечат защиту при потере/откате всего journal: coordinated backup и проверка прежних меток обязательны, ручное удаление DB не является восстановлением.

## Google port

`ConsultationCalendarPort` использует существующий `GoogleCalendarAdapter` и его HTTP/TLS/error handling, без новых credentials, ADC bootstrap, auto-discovery или HTTP клиента. Для реальных read вызовов также требуется отдельное разрешение.

- Writes запрещены и executor flag, и default `adapter.allow_writes=False`. Флаг не заменяет разрешение пользователя.
- PATCH/DELETE по exact event ID, `If-Match` с исходным ETag. Нет POST/create, слепого повторного PATCH/DELETE или повторного GET с подменой stale precondition на новый ETag.
- PATCH меняет summary «Консультация — подтверждена», location «Кабинет317» и технические extendedProperties; description меняется только для точно распознанного исходного bot prefix. Существующие private/shared properties копируются, добавляется private operation marker. Время, произвольные заметки, reminders и остальные поля не переписываются. Google `sendUpdates=none`, Telegram здесь не вызывается.
- Известный prefix текущего GAS-кандидата «Заявка ID; тема: ТОЧНАЯ_ТЕМА; предварительная запись, решение преподавателя ещё не получено.» заменяется на подтверждённый статус; весь suffix, включая marker/ручные заметки, сохраняется побайтно. Точное совпадение привязано к original source/event evidence. Если pending phrase есть, но prefix другой, approve блокируется для сверки; не угадывать шаблон. Reject не переписывает description. При read-only reconcile проверяется и новая description, если она входила в mutation.
- 4xx, кроме408, — явное API rejection, без auto retry. Timeout/5xx/неправильный acknowledgement/неизвестная ошибка — unknown. MutationReceipt валидируется по calendar/event/method/operation identity; PATCH response должен подтвердить нужные поля и исходные времена.

## Read-only восстановление

`reconcile` не отправляет mutations, не создаёт/не повторяет запрос и не сбрасывает attempt в ready. Текущие owner права обязательны.

| Наблюдение | Исход | Что оно означает |
|---|---|---|
| Matching operation marker, title/location/extensions и время | calendar_reconciled_present | Фактическое нужное состояние наблюдается; повтор PATCH не нужен |
| После своего durable delete claim exact event отсутствует | calendar_reconciled_absent | Резерв сейчас отсутствует; не приписываем удаление именно нашему API запросу |
| Исходное/чужое/вручную изменённое состояние, другой marker | unknown/inflight сохраняется | Требуется сверка, повтор записи не разрешён |
| Долгое/неудачное чтение, revoke | Ошибка сверки | Не превращать отсутствие данных в отсутствие события |

Ни reconciled state, ни API-confirmed Calendar receipt не доказывают запись в Sheets или отправку/доставку сообщений. Реальное подтверждение встречи как всего workflow не объявляется завершённым.

## Оставшиеся границы подключения

1. Trusted bridge реального owner consent с original source/event evidence и stable immutable plan IDs. Не выставлять этот executor как endpoint для произвольного BoundPlan.
2. Verified live identity/collection/ownership/full-import verifier. В mocks completeness true — исключительно fixture, не подтверждение завершённого НВГУ импорта.
3. **Source CAS/claim и координация внешних writers.** Между последней проверкой строки и Calendar API остаётся гонка; Calendar ETag защищает Calendar event, но не Google Sheet и не появление другого занятого события. Реальное включение до решения этой границы запрещено. API Calendar не предоставляет транзакционный запрет новых пересечений от независимых writers.
4. Завершение authoritative статуса/решения заявки только по подтверждённому Calendar-stage outcome с row preconditions. Здесь `source_status=not_written` всегда. Безусловное перезаписывание изменившейся строки недопустимо.
5. Независимые durable уведомления студенту/владельцу после окончательной сверки статуса, с отдельными per-recipient outcomes. Здесь `notifications=not_sent` всегда, ни один sender не вызывается. Сбой одного уведомления не должен повторять Calendar или лишать второго адресата сообщения.
6. Операторский recovery для blocked/rejected/старых attempts, проверка реальных legacy description форматов, права/квоты и разрешённая sandbox-приёмка. Propose/student agreement/перенос — отдельно. Никаких production polling/triggers/deploy.

## Тесты

`bash tools/check-local.sh`: **577 Python PASS +110 Node PASS**,6offline demos. Текущий Calendar-stage corpus: **43 Python tests** (33executor/demo +10port); из них5добавлены для safe legacy description после исходного этапа38tests. Сначала тесты падали до реализации; дополнительные red→green regressions: prior marker, stale absence, blocked receipt write failure.

Проверены update/delete того же hold, conditional ETag/412, сохранение времени/заметок/custom properties, wrong owner/student/revoke, row/event/coverage/ownership mismatch, pre/post claim changes, malformed receipt, accepted→timeout, restart/peer/KeyboardInterrupt/write failure, source recheck после Calendar read, same-booking competing plan, read-only recovery и default disabled. Integration test использует реальный port/executor/SQLite с fake HTTP session, не реальный Google API.

[Демонстрация сбоя и восстановления](CONSULTATION_EXECUTION_DEMO.md): `python tools/consultation_execution_demo.py` — один mock PATCH, unknown, затем read-only confirmation, без повторного PATCH. Реальных API/данных студентов/сообщений не было.


| Дефект/риск | Причина | Исправление | Тест / результат | Остаток |
|---|---|---|---|---|
| Дубль после accepted→timeout | Исход API не сохранён | Durable claim до вызова; retry запрещён, marker/postcondition reconcile | Executor+port fake HTTP PASS | Реальное API поведение не проверялось |
| Затирание ручной правки | Новый ETag подставлен без решения | Original event fingerprint и If-Match,412 terminal | Manual edit/412 PASS | Между разными сервисами нет транзакции |
| Удаление чужого hold | Title/description как ownership | Exact trusted binding + original event/source proof | Missing/foreign hold PASS | Live ownership registry ещё не подключён |
| Повтор после прежней неизвестной операции | Старая private marker перезаписана | Prior marker требует сверки даже при новом подтверждении | Red→green PASS | Нужен operator workflow |
| Ложное отсутствие при долгом read | Нет свежести у None | Возраст read до/после запроса, без state promotion | Slow absence red→green PASS | Trusted port обязан читать actual source |
| Повтор после отказа и сбоя journal | blocked outcome не сохранился | Сохранённый applying claim остаётся, needs_recovery | Blocked receipt failure red→green PASS | Не автоматический retry; операторская сверка |
| Незаметная смена строки/получателя | План без original binding | Unbound deny; original row hash/current student, source reread | Changed topic/student/source-during-read PASS | Source CAS/writer coordination до real enable |
