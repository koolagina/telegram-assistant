# Согласованный импорт18занятий: ручной Apps Script runner — 29.10.2026

В ответ на конкретный вопрос о добавлении18согласованных занятий пользователь ответил«+». Это разрешает **только эти18созданий на09–22ноября2026 в выбранном Calendar**, со свежей проверкой источника/дублей. Не распространяется на изменение11старых событий, удаление, рабочий legacy hotfix, данные Sheets/студентов, уведомления, триггеры, webhook/poller или deployment. Повторного разрешения на тот же объём не требовать.

## Что подготовлено

- `tools/nvsu_approved_import.py` получает trusted fresh `nvsu_source.fetch_week` proofs и исходный согласованный payload preview. Использует существующий `nvsu_sync.plan_sync` для9+9create-only операций и сравнивает **точное множество18четырёхполевых payloads**, не только количество. Изменение времени/дисциплины/аудитории/набора вызывает отказ. Старый Calendar snapshot не выдаётся за live evidence.
- В приватный self-contained `.gs` компилируются эти операции, original target hash, source raw SHA-256 и срок технической свежести24ч. В Git только generic executor template/generator/tests, без target hash/lesson data/raw source/Calendar IDs/секретов. HTML parser не переписан, неизвестная разметка не угадывается.
- `src/tools/nvsu_approved_import.gs` — тонкий **create-only transport** для этого плана в уже авторизованном пользовательском Apps Script. Не общий scheduler и не новая система синхронизации. Fixed plan/2weeks/18creates; PATCH/DELETE/getUpdates/sendMessage отсутствуют. Не требует новой clasp write-авторизации или push всего проекта.
- Перед компиляцией повторно прочитаны обе недели НВГУ: HTTP200, без redirect, исходные18payloads не изменились. Частный generated wrapper проверен на exact serialized digest; в составе всех переданных JS-файлов51globalfunction без collisions, совместная syntax PASS.

**Реальный runner ещё не запускался**, фактических Calendar inserts в этом этапе нет. Полнота всего календаря/работа консультаций остаются неподтверждёнными. Минимальный legacy access/ACK patch всё ещё не установлен.

## Один ручной запуск пользователя

Из этой облачной среды нет authenticated Calendar/Apps Script connection; Windows clasp OAuth не передавался сюда. Поэтому исполнение происходит вручную в уже работающем Apps Script пользователя. Готовый приватный `.gs`/`.txt` выдаётся в чате как локальный artifact; его нельзя публиковать в Git/issues.

1. В существующем Apps Script добавить отдельный файл **ИмпортЗанятий**.
2. Заменить только шаблонную myFunction **нового файла** всем содержимым подготовленного private `.gs`/`.txt`. Основной `Код.gs`, manifest и остальные helpers не заменять. Public generic template из GitHub сам по себе не содержит утверждённого плана и для запуска недостаточен.
3. Сохранить и выполнить **`importApprovedKulaginaNvsuLessons`**. Не нажимать deployment/не запускать setupAutomation/initialize/старый TESTCRUD.
4. Передать только один sanitized JSON из журнала. При `complete`: API receipts18 и последующая GET-проверка18. До такого результата не заявлять импорт завершённым.

Если файл технически устарел (`plan_expired`), исходное разрешение не теряется: обновить свежие proofs того же точного набора, не добавляя занятия/расширяя даты. При изменившемся source/payload/target нужен новый review, а не обход guard. Новую сериализацию нельзя применять поверх старого уже начатого journal: plan digest mismatch останавливается.

## Проверки перед каждым созданием

- Hash существующего `ASSISTANT_CALENDAR_ID` должен совпасть с утверждённым target. `primary`, default Calendar и неизвестный/другой timezone запрещены. CalendarApp identity + Calendar REST metadata + calendarList owner проверяются отдельно.
- Свежий GET **той же публичной страницы конкретной недели** должен вернуть тот же exact raw-byte hash, который Python parser проверил для lecturer3648/даты. URL allowlist fixed HTTPS host/path/date, no redirects, HTML/content-size guard; Google bearer не передаётся НВГУ. Любая перемена HTML требует свежего parser review даже если кажется косметической. Это консервативная проверка неизменности, а не новый HTML parser.
- Обе недели до начала должны оставаться пустыми. Каждый последующий полный bounded Calendar GET допускает только уже ACKed события текущего journal, с неизменными time/title/room и без ручных decorations. Новое событие, manual edit, исчезнувшее ACKed событие, unread page/повтор token/duplicate IDs/лимит останавливают импорт.
- Ещё до записи проверяется отсутствие всех18deterministic IDs; существующие события не усыновляются. ID формируется **как в nvsu_google.GoogleCalendarAdapter.event_id**: nvsu+SHA256(calendar_id+NUL+operation_key), а operation_key выдаёт существующий planner.
- Payload содержит только технический event ID и время/summary/location; нет attendees/описаний/groups/streams/служебного текста. `sendUpdates=none`, никаких student/owner messages. Собственные reminders/visibility overrides не добавляются. Google Calendar использует свои обычные настройки напоминаний.

Чтение источника/Calendar и создание события не являются общей атомарной транзакцией. Параллельную ручную правку между GET и POST можно обнаружить следующей/финальной проверкой; при этом runner останавливается, но уже созданные события не удаляет самостоятельно. Каждый POST ограничен только events.insert. API error/409/тайм-аут не повторяется автоматически. Native/REST/HTML network вне ScriptLock; блокировка кратковременна и используется только для local CAS claim/receipt.

## Journal и повторный запуск

До первого POST durable claim: `KULAGINA_NVSU_IMPORT_20261109_20261116_V1`, привязанный к plan digest/target hash/run ID/18статусам. Перед каждым POST SENDING фиксируется до сети. После верифицированного API receipt записывается отдельный `KULAGINA_NVSU_BINDING_<eventId>` с operation_key/source_refs/last_event/ownership created/ETag и API receipt; затем root status CONFIRMED. Малые отдельные записи не превышают per-property лимит для проверенного bounded плана. Это внешняя техническая provenance, не видимая подпись в событии.

После18ACK выполняются повторные source/full-week/known-ID GETs и только затем root COMPLETE. Successful повтор проверяет18событий без нового POST и возвращает already_complete. Изменённое/удалённое событие не восстанавливается молча.

При accepted-then-timeout/потере receipt/частичном сбое повторный запуск выполняет **только GET-сверку известных IDs** и возвращает in_progress_or_review. Может показать matching event без подтверждённого API receipt; это **не доказательство API attribution** и не auto ownership promotion. Непопробованные операции тоже не продолжаются автоматически. Не сбрасывать/не удалять journal и не создавать новый marker ради повтора; восстановление требует рассмотрения точных receipts/свежего источника/Calendar, в рамках уже разрешённых18. Active run и crashed run не различаются по одному INFLIGHT: orphan не объявляется автоматически.

Binding records совместимы по полям с существующей внешней моделью ownership, но автоматический перенос в SQLite StateStore **не реализован**. До trusted migration нельзя запускать Python apply с новой пустой DB/считать Script Properties полноценной общей БД. Старые11событий по-прежнему не имеют доказанного ownership и не меняются.

Этот runner — разовая доставка согласованного create-only плана, не завершённая автоматическая синхронизация будущих изменений. Обновление занятий/перенос trusted ledger/полнота источника для консультаций остаются отдельными этапами.

## Локальные проверки

5новыхPython tests: точное18payloads/старые operation keys, changed approval/source/calendar/busy target reject, live proof/date/URL/digest guards, stale/incomplete/duplicate proof, render digest/ручной entrypoint.14новыхNode tests:18creates, replay0POST, wrongtarget/source/expiry, existingIDnotadopted, pagination/owner/lock, timeoutaccepted/receiptfailure/no retry, newmanualevent/sourcechange/deletion midrun, manualedit aftercomplete, corrupt/mismatchedjournal, bad/out-of-scope/oversized/overlapping operations, slow-source expiry before POST (отдельно red→green). HTTP asserts подтверждают no network under lock и no Google header to NVSU. Сначала tests red до реализации, затем green.

Полный `bash tools/check-local.sh`: **596Python +201Node PASS**,6offline demos. Actual private wrapper checksum/scope и combined syntax51functions отдельно PASS. Только public NVSU GET выполнены из Codex; реальная18create приёмка ожидает пользовательский JSON. Calendar writes/messages/trigger changes/deployment из этой среды:0.
