# Источники заявок и занятости — кандидат, 29.10.2026

Готовы read-only экспортёр и нормализаторы снимков. **Это не подключённая интеграция:** реальные Google данные/токены не читались, экспортёр не установлен и не запускался на таблице. `src/telegram_assistant_v2_0_5_candidate.gs` и все архивные снимки сохранены. Нет новых колонок, Google Sheets статусов, trigger/webhook изменений или реальных отправок.

## Существующая схема

Экспортируется только лист `Заявки на консультации`, строго 11 колонок из CFG текущего GAS-кандидата:

| № | Поле | Нормализация / ограничение |
|---|---|---|
| 1 | ID заявки | Непустая строка, одинаковые копии объединяются; конфликт останавливает source |
| 2 | Дата создания | Aware datetime/RFC3339 либо пусто; неизвестная дата не заменяется временем чтения |
| 3 | Студент | Приватная текстовая метка, не student identity/основание доступа |
| 4 | Telegram chat ID | Положительный private numeric subject; строковые ведущие нули сохраняются, float/bool не принимаются |
| 5 | Желаемая дата | ISO date/date/aware datetime, в Asia/Yekaterinburg; числовые serials не угадываются |
| 6 | Желаемое время | HH:MM/time/aware datetime, в Asia/Yekaterinburg; секунды не округляются |
| 7 | Длительность, мин | Ровно integer20; это существующее согласованное правило |
| 8 | Тема | Приватный текст; формулы/HTML из него не выполняются |
| 9 | Статус | Только существующие статусы 2.0.5; неизвестный статус — ошибка source |
| 10 | Решение / причина | Приватный текст, участвует в версии строки |
| 11 | ID события календаря | Пусто допустимо в промежуточном source; само наличие не доказывает ownership |

Python тест отдельно сравнивает HEADERS со схемой неизменённого GAS-кандидата. Numeric ID уже потерявший ведущие нули в исходном Sheets не восстанавливается догадкой.

## Экспорт без побочных записей

`src/tools/consultation_snapshot_export.gs` содержит единственную функцию `exportConsultationSnapshotReadOnly(spreadsheetId)`. Это отдельный **неустановленный helper**, не новый entrypoint бота. Требует явный ID и timezone Asia/Yekaterinburg, вызывает только openById/getSheetByName/getDataRange/getValues и преобразование дат. Не вызывает tab_/rows_/initialize/log_, не создаёт листы, не пишет/рассылает/публикует данные, не ищет ресурсы автоматически.

Один range read включает заголовки; missing sheet/schema/extra columns/неполная строка/неверный Date — безопасная ошибка без исходных данных. Только полностью пустой padding пропускается. Истинный `observed_at` фиксируется **до** чтения; `complete=true` означает полный прочитанный лист, **не** полноту расписания, авторизацию пользователя или атомарность с Calendar. Строгая typed-time проверка учитывает timezone, секунды и миллисекунды. Исторические time-cell даты и реальные Sheets форматы требуют отдельной sandbox-приёмки.

Результат format_version1 — объект с spreadsheet_id/sheet_name/headers/rows/observed_at/complete/timezone. Он содержит персональные данные. Не использовать Logger/публичный endpoint, не публиковать/добавлять в Git, не присылать в чат. Передача только через согласованный закрытый authenticated канал; такой live канал пока отсутствует. Не устанавливать helper в production ради проверки.

## Python вход

`tools/consultation_feed.py`:

- `decode_sheet_export`: JSON≤2MiB, формат1, запрет дублирующихся ключей, точные поля; декодирование не доказывает происхождение.
- `ConsultationFeed.snapshot/batch`: configured spreadsheet identity, exact headers/timezone, typed rows≤10000, freshness≤5min до/после обработки. Возвращает ConsultationEvidence/ConsultationBatch с исходной датой и полнотой; не «освежает» источник временем клика. Partial source остаётся partial для очереди.
- `ConsultationEvidence.revision`: hash всех 11 нормализованных полей и исходного ресурса. Equivalent aware timezone representations не меняют смысл/версию. Изменение темы, получателя, event ID, статуса/решения меняет версию.
- `require_revision`: trusted read guard, сверяет новую полную свежую строку с ожидаемой версией. Это не authorization, не write lock и не compare-and-set в Google. Future executor обязан применять guard под актуальными owner правами непосредственно перед операцией и ещё раз проверять внешние preconditions.
- `ConsultationRecord.source_version` — дополнительное optional поле только Python модели (default empty для прежних callers). ConsultationSource переносит его в DecisionItem; старые кнопки `/decisions` теперь инвалидируются и при невидимом изменении получателя/event ID. Google схема не менялась.

Все feed/accessors — server-side trusted APIs, не публичные endpoints. Owner gate очереди остаётся до/после source reads; exporter/decoder сами не устанавливают teacher/student роли. Telegram subject из ячейки ещё нужно связать с подтверждённой student identity, не использовать его как автоматически выданное право.

## Занятость и полнота

`read_calendar_snapshot` явно читает через **существующий** injected `GoogleCalendarAdapter.list_events`. Не загружает credentials, не запускает polling; отдельное разрешение требуется даже для real reads. Моки проверяют все страницы, all-day и recurring instances; отсутствие location не делает событие свободным, ошибка второй страницы не возвращает пустой результат. Возраст считается от начала запроса, exception детали скрываются.

`BusyFeed` объединяет заданные target и teaching CalendarSnapshot. При одном календаре читает один снимок, при разных одинаковые event IDs остаются двумя событиями (qualified identity); чужой event не исключается как собственный резерв. Неполный/просроченный/чужой snapshot вызывает ошибку, а не «свободно». Доступный диапазон — пересечение подтверждённых диапазонов; внешние ручные события также занимают время. Нормализатор не удаляет/не обновляет события.

Собственный резерв определяется **только** trusted HoldBinding по calendar/event/consultation ID и точному start/end. Название, description marker, кабинет и совпавшее время без binding недостаточны. Несколько bindings/изменившийся hold требуют сверки. Источник verified bindings из настоящего реестра операций пока не подключён.

`TeachingVerification` — отдельная доверенная аттестация проверенного импорта занятий. Она привязана к преподавателю, календарю, диапазону, hash фактического calendar snapshot, версии НВГУ, observation timestamps источника и проверки. Нормализатор **не выдаёт** эту аттестацию и не проверяет правильность самого импорта НВГУ. Реальный verifier/права выдачи/сбор source evidence — отдельная интеграционная задача. Нельзя создавать аттестацию из пользовательской галочки, пустого календаря, одного успешного HTTP или `source_reports_no_schedule` без проверки нужной недели/даты и результата импорта.

Отсутствующая/устаревшая/несовпавшая аттестация → `teaching_complete=false`; локальный ConsultationActions блокирует решение. Явное отсутствие расписания само по себе не меняет этот флаг. Время аттестации не может предшествовать source, который она якобы проверила. BusySnapshot сохраняет самый ранний observation timestamp, включая verification/source при подтверждённой полноте; возраст проверяется после сборки.

## Интеграционный предел

Demo `python tools/consultation_demo.py` теперь использует настоящие нормализаторы, **искусственные** Sheet/Calendar snapshots и искусственную аттестацию. Только synthetic record явно добавляется в временный action sandbox. Это не импорт рабочих строк в локальную authoritative базу. Status локальной модели не меняет source, и source не переписывается plan-ом.

Не подключены: настоящий приватный collection/transport/authentication, live student identity/ownership, verifier полноты завершённого импорта, authoritative source CAS, dispatcher, external executor/reconciliation и согласие студента на перенос. Не передавать intents/plans handlers в read-only `ReportWorker.prepare_fresh`. Наличие модулей не разрешает включать флаги полноты или действующие триггеры.

## Приёмка

`bash tools/check-local.sh`: **459 Python PASS +110 Node PASS** (101 прежний +9 export). Новые29 Python tests охватывают контракт/даты/revision/частичные данные, source guard, старые refs, coverage/ownership/подмену ресурса, timestamps, Google mock pagination/all-day/recurrence/error. Девять новых Node VM-тестов — read-only helper, без реального Apps Script. Полная проверка включает4offline demos. Сначала тесты падали до реализации; отдельно red→green исправлены stale age, невидимая смена адресата/event ID, impossible verification chronology и округление typed time.

| Риск | Защита | Тест | Остаётся |
|---|---|---|---|
| Сдвиг колонок/типов | Exact schema + typed dates | GAS contract/invalid rows PASS | Проверить реальные Sheets даты в sandbox |
| Ложное свободное время после сбоя | Полный snapshot, age/range, explicit attestation | Partial/stale/page failure PASS | Реальная полнота НВГУ ещё не проверена |
| Старая кнопка после смены адресата/event | Полная row revision в reference | Red→green PASS | CAS перед реальной записью |
| Принятие чужого события за свой hold | Calendar-qualified ID + trusted binding + времена | Same ID across calendars/forged marker PASS | Live ownership collection |
| Потеря точности времени | Отказ subminute typed time, без округления | Node red→green PASS | Реальная historical time-cell приёмка |
