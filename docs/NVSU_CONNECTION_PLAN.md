# 29.10.2026 —18созданий разрешены, ограниченный runner подготовлен

User «+» ответил на конкретный вопрос о18реальных занятиях09–22ноября; scope принят, повторного разрешения не требуется. Остальные11events/Sheets/legacycode/triggers/webhook/poll/deploy/studentmessages не разрешены этим ответом. Свежие2NVSUproofs HTTP200/no redirect совпали с исходными18payloads.

Existingplan_sync operationkeys/renderpayloads используются в private bounded AppScript handoff. Generic nvsu_approved_import.gs — create-only transport/18max, targethash/sourcebytehash/date guards, full fresh Calendar checks/owner, same deterministicIDs as GoogleCalendarAdapter, durable pre-POST claim/APIreceipts/known-IDreadonlyreconcile. No PATCH/DELETE/resend unknown; successfulreplay0POST, partialrunnotresumedblindly. Root/binding records external to events, no visible service text/groups. No new parser/general sync engine. Privatecapsule outsideGit; publictemplates contain no targetID/hash/lesson data.

5Python+14Node newtests firstred→green. Полный **596Python +201Node PASS**,6offline demos; privatewrapperdigest/combined51globalfunctionsyntaxPASS. Реальные Calendarwrites0 — нужен manual AppsScript run из авторизованного пользователя; OAuth изWindows не подключаетCodexcloud. Готовыйprivaterunner ещё не installed/executed, legacyhotfix тоженеinstalled. [Инструкция/сбои/границы](NVSU_APPROVED_IMPORT.md).

---

# 29.10.2026 — четыре недели сравнены;18занятий отсутствуют в Calendar

Полный пользовательский Novemberbatch принят:2части/checksumvalid/4правильные недели/одинtarget. Источник freshly fetched существующим parser. НВГУ/Calendar/exact/missing:02–08ноября11/11/11/0;09–15ноября9/0/0/9;16–22ноября9/0/0/9;23–29ноября0/0/0/0(явное«Расписание отсутствует»).11существующих protectedсобытий совпадают и сохраняются;0duplicateexact/unknown. Это выбранныйCalendar/конкретныйпериод, не все календари/семестр.

Предварительный план:18create candidates,0updates/0deletes/11preserved. Private human-readable18row preview иpayload-onlyJSON подготовлены внеGit; source refs/groups/streams не включены вeventpayload. Existingnvsu_sync используется без новогоалгоритма; always ready_for_applyfalse/teachingverifiedfalse/ownershipfalse. Реальные Calendar/code/данные не менялись; TESTразрешение не разрешает18настоящихзанятий. Перед записью нужно отдельное userразрешение иfreshsource/Calendar/ledger/idempotency/reconciliation proof.

Точечные проверки:78Python NVSUtests PASS+13Node exporttests PASS. Последний full591Python187Node/6demos не повторялся, codeunchanged. [Предварительный план и ограничения](NVSU_NOVEMBER_REVIEW.md). Legacy access/ACK candidate по-прежнему не установлен.

---

# 29.10.2026 — четыре недели ноября: источник проверен, Calendar-снимок подготовлен

Свежие разрешённые public GET через существующий `nvsu_source.fetch_week`:02–08.11 parsed11;09–15.11 parsed9;16–22.11 parsed9;23–29.11 source_reports_no_schedule0. Учебная неделя/дата/преподаватель проверены существующим parser; это не результат Calendar-импорта. Private source proofs вне Git. Отсутствие расписания не разрешает удаление ручных/неподтверждённых событий.

Расширен существующий `src/tools/nvsu_calendar_snapshot.gs`: старый `exportKulaginaNvsuWeekReadOnly` сохранён; общий внутренний collector используется новой `exportKulaginaNvsuNovemberReadOnly` для четырёх фиксированных недель02–29.11. GET-only, прежняя защита/редакция полей, единый checksum/chunks только после всех недель. До24REST GET/200событий суммарно; ошибка любой недели/смена target/лимиты не выдают частичный успешный снимок. Новое чтение пока не executed live; бот/настройки/события не менялись.

`tools/nvsu_private_snapshot.py` принимает явный November batch, проверяет4даты/порядок/один target/лимиты и вызывает прежний `compare_snapshot`/`nvsu_sync.plan_sync` по каждой неделе. Никакого нового sync engine/ownership ledger/write adapter; всегда ready_for_apply=false/teaching_schedule_verified=false. Период не включает30ноября и не доказывает весь семестр.

1новыйPython test и4Node tests сначала red→green; старые weekly tests сохранены. Полный `bash tools/check-local.sh`: **591Python +172Node PASS**,6offline demos; отдельно проверен настоящий JS batch→Python decoder/comparator. Следующий необходимый вход — один ручной four-week export пользователя. [Инструкция](NVSU_PRIVATE_COMPARISON.md#четыре-недели-ноября-одним-запуском).

---

# 29.10.2026 — реальная диагностика защиты получена

Пользователь предоставил status=complete для недели02–08.11: events11/protected11; attendees11, description5; all_day/tentative/recurrence/extended_properties/attachments/conference/transparent/special_event0; Calendar writes0/messages0. Это ручное read-only свидетельство Apps Script пользователя, не прямой Google-доступ из Codex. Повторная диагностика сейчас не нужна.

Причина защиты11событий — truthy поле attendees; ещё5имеют truthy description. Нельзя считать attendees11 числом людей/непустых списков или доказательством приглашений: helper считает наличие поля, в том числе пустой массив. Дополнительные свойства в этих событиях не обнаружены, но это не доказывает отсутствия внешнего ledger/истории импорта. Владение синхронизатора не подтверждено. Не удалять участников/описания ради снятия защиты, не создавать дубли и не присваивать события автоматически.

Прежняя сверка11точных совпадений остаётся отдельным свидетельством; агрегатная диагностика её не обновляет и не доказывает неизменность полей между чтениями. Для существующей недели нет выявленной причины менять календарь. Дальнейшая безопасная последовательность: проверить остальные нужные недели; получить подтверждённый существующий ledger/происхождение перед любыми мутациями старых событий; сформировать свежий конкретный read-only план; реальные изменения/автоматизацию согласовать отдельно. Флаг полноты и запись студентов остаются выключенными.

В этом шаге изменена только документация. Последняя полная локальная проверка: **590Python +168Node PASS**,6offline demos; повторно не запускалась. Бот/Calendar/Sheets/триггеры не изменялись. [Подробности](NVSU_PRIVATE_COMPARISON.md).

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

# Подключение НВГУ → Google Calendar — 27.10.2026

Реализованы недостающие Google transport, чтение Calendar и постоянный журнал поверх существующих `nvsu_preview.py` / `nvsu_sync.py`. Реальный календарь не читался и не изменялся; бот, `.gs`, webhook и триггеры не изменены. Python-компонент остаётся отдельным от Apps Script.

## Что готово

| Компонент | Поведение |
|---|---|
| `tools/nvsu_source.py` | Получение публичной страницы конкретной недели по исследованному URL; HTTPS, проверка HTTP/HTML/размера, преподавателя, дат и полноты через прежний parser. Служебные setlink/setvisit не вызываются |
| `tools/nvsu_google.py` | Calendar v3, ADC, пагинация, явный Calendar ID без `primary`, read-only по умолчанию; модель title → API summary |
| `tools/nvsu_state.py` | SQLite WAL/FULL, отдельный ledger на календарь, одновременный запуск блокируется; план связан с источником/целью и действует 15 минут |
| `tools/nvsu_calendar.py` | Только подготовка: свежий публичный источник + явно разрешённое read-only чтение Calendar либо локальные fixtures/snapshot. Команды apply нет |
| Существующий `nvsu_sync.py` | Дедупликация групп, сохранение event ID, минимальный PATCH времени/дисциплины/кабинета; добавлены hooks постоянных checkpoints |

При вставке ID детерминирован и проверяется до POST; после потерянного ответа повтор использует тот же ID. PATCH/DELETE используют If-Match: изменение после preview останавливает операцию. Автоматического повтора неизвестных HTTP-мутаций нет. Журнал различает PREPARED, APPLYING и COMMITTED; `reconcile_plan` может проверить ранее принятый результат только чтением, даже после истечения плана. Неразрешённая операция блокирует новый план. После сверки требуется свежий план для следующих изменений.

Создание пишет только summary, start, end, location и технический ID. Группы/потоки/ссылки/описания не переносятся. All-day, recurring, события с заметками/участниками/специальными атрибутами защищены. Точное ручное совпадение даёт локальную связь `linked_existing`, без создания дубля и без права будущего удаления/замены. Передача такой записи синхронизатору требует отдельного решения по конкретному событию, свежего источника и проверки ETag (`confirm_existing_binding`; меняет только локальную связь). Сейчас эта передача не выполнялась.

## Предварительный план изменений

**План для настоящего Calendar пока не определён:** целевой Calendar ID отсутствует, его события и права не проверены. Отсутствие snapshot не считается пустым календарём. Поэтому число реальных create/update/delete неизвестно.

Проверяемый пример на очищенном fixture следующей недели и искусственном Calendar snapshot:

| Параметр | Результат |
|---|---|
| Неделя | 02–08.11.2026, Asia/Yekaterinburg |
| Источник / цель | `fixture` / `snapshot`, не настоящие данные Calendar |
| Уникальные занятия | 11 |
| Точное уже существующее занятие | 1 локальная связь, событие сохранить |
| Предлагается создать | 10 |
| Обновить / удалить | 0 / 0 |
| Реальные изменения | 0 |

Этот пример нельзя применить: executor отвергает fixture/snapshot-планы. JSON и SQLite примера сохранены только во временном закрытом каталоге, не в Git; в отчёт не включены пользовательские события. `ready` в модели означает отсутствие логических конфликтов, а не разрешение реальных операций.

## Что нужно для безопасного подключения

1. Указать явно выбранный Calendar через защищённую настройку `ASSISTANT_CALENDAR_ID` или `--calendar-id`. Сначала отдельный тестовый календарь/копия; не передавать токены в чат. Указатель ADC в окружении обнаружен, его содержимое не читалось; доступ и OAuth scopes не проверены. Runtime не сообщает готовой Google identity.
2. Подтвердить разрешение на чтение выбранного ресурса. Проверить Calendar API, ADC/identity и ACL на этот конкретный календарь. Существующую identity не заменять и повторную авторизацию без диагностики не запускать.
3. Подготовить свежий план против фактических событий и существующего ledger, разобрать review и ручные соответствия. Проверить текущую и соседние учебные недели и источник для каждой даты. План не является резервной копией всего календаря.
4. Перед отдельным разрешением на запись сохранить резервную копию и SQLite state, проверить create → повтор → изменение → удаление исключительно собственного тестового события, тайм-ауты/412 и ручные правки в sandbox. Проверить фактические права, часовой пояс, отсутствие лишних полей и дублей. Обновлённый реальный план согласовать отдельно.
5. Автоматизацию/расписание запуска проектировать после приёмки. Не запускать Apps Script setupAutomation и не включать `ASSISTANT_CALENDAR_HAS_ALL_LESSONS=true`: полнота импорта ещё не подтверждена. Связь Python → GAS/бот автоматически не появилась.

## Команды

Локальные проверки не обращаются к Google:

```bash
python -m unittest discover -s tests -p 'test_nvsu*.py'
node tests/run-current.cjs
python -m venv /tmp/nvsu-calendar-venv
/tmp/nvsu-calendar-venv/bin/python -m pip install -r requirements-calendar.txt
/tmp/nvsu-calendar-venv/bin/python -m pip check
```

Следующая команда — инструкция для будущего **разрешённого чтения**; в этом этапе не запускалась. Значения выбрать явно; имя преподавателя брать из подтверждённой страницы, не угадывать. State и планы содержат личные данные: каталог 0700, файлы 0600, вне Git. Не создавать новую пустую базу при потере старого ledger.

```bash
/tmp/nvsu-calendar-venv/bin/python tools/nvsu_calendar.py \
  --date YYYY-MM-DD --lecturer-id 3648 --teacher-name 'ПОДТВЕРЖДЁННОЕ_ИМЯ' \
  --calendar-id "$ASSISTANT_CALENDAR_ID" --fetch-source --live-read \
  --state-db .nvsu-state/calendar.sqlite3 --output .nvsu-state/plan-new.json
```

Для offline-плана заменить `--fetch-source` на `--html PATH`, `--live-read` на `--calendar-snapshot PATH`. Snapshot — явный JSON-массив событий модели `{id,start,end,title,location,...}`, не произвольный экспорт Google/ICS. Пустой массив допускается только как явно предоставленные тестовые данные. CLI отказывается перезаписывать существующий plan.

## Проверки и оставшийся риск

Python: 64 PASS (8 parser + 24 прежней sync-модели + 24 Google/state + 8 source/CLI). Node: 101 PASS текущего 2.0.5 (64 совместимости + 37 консультаций); отдельно исторические regression 69 PASS и audit 19 PASS (включая воспроизведение старых дефектов). Наборы пересекаются, их нельзя складывать как уникальные тесты. SDK импортируется, read-only scopes проверены с AnonymousCredentials/подменённым ADC без чтения credential-файлов; `pip check` успешен.

Проверены переход года/недель, неверная дата/чужая неделя, no-schedule, неполный HTML, HTTP-ошибки, группы-дубли, поля событий, страницы API, all-day/recurring/manual protection, идемпотентные ID, тайм-аут после принятого create/update/delete с переоткрытием SQLite, ETag412, появление нового конфликта, истечение/подмена плана, readonly reconciliation и явное подтверждение локального владения.

Локальные HTTP-моки не подтверждают OAuth, ACL, квоты, eventual consistency и поведение реального API. Между чтением конфликтов и вставкой остаётся окно конкурентной записи сторонним клиентом: Google Calendar не даёт транзакционную блокировку слота; перед реальной автоматизацией нужна интеграционная проверка и повторная сверка. Неизвестные результаты остаются на review, а не повторяются вслепую. SQLite рассчитан на один writer/один устойчивый локальный диск; для нескольких машин нужен отдельный проект координации. Не переносить только main SQLite-файл при активном WAL: использовать SQLite backup/остановленный процесс. Потерю журнала не компенсировать массовым присвоением ручных событий.
