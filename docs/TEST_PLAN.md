# Локальное чтение XLSX — 28.10.2026

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/run-current.cjs
```

Актуальный запуск: **80/80 Python PASS** (64 НВГУ + 16 XLSX), **101/101 Node PASS** (64 совместимости + 37 консультаций). Новых зависимостей нет. Google/Telegram/Яндекс API не вызываются.

`tests/test_gradebook_read.py` создаёт только синтетические XLSX во временном каталоге: настоящий журнал и студенческие данные в fixtures не включены. Сначала зафиксирован красный запуск без reader; затем дополнительные три падающих теста воспроизвели скрытие данных объединением, неизвестный тип пустой ячейки и утечку непроверенного атрибута state в структурный вывод. Все три дефекта исправлены и покрыты регрессиями.

Проверены: relationship target вместо предположения sheet1.xml; несколько заголовков групп без назначения академической личности; merged anchor и конфликтующие значения; shared/inline strings; формула отдельно от кеша, пустой кеш отдельно от нуля; происхождение shared formula без ложной подстановки выражения; числа/ошибки; даты 1900/1904 и фиктивное 29.02.1900; реальные позиции итогов; скрытые колонки; CLI/repr без значений; external/traversal/DTD/повреждённые ссылки/ограничения размера.

Дополнительно модуль локально прочитал все 22 листа прикреплённой актуальной книги: 3722 формульные ячейки, 759 пустых/отсутствующих кешей, 286 merges, по шесть структурных А/Т/ДЗ-троек на листе. SHA-256 исходного файла до/после чтения совпадает. Формулы не пересчитывались; результаты оценивания не проверялись. Это чтение локальной копии, не проверка Яндекс API, актуальности файла на Диске, прав или записи XLSX.

Reader не проверяет academic identity, не вычисляет успеваемость, не формирует student reports и не открывает `/progress`. Для них отдельные тесты policy/Enrollment остаются следующей задачей. Подробности: [GRADEBOOK_STRUCTURE_AUDIT.md](GRADEBOOK_STRUCTURE_AUDIT.md).

---

# НВГУ / Google transport: актуальные локальные проверки — 27.10.2026

```bash
python -m unittest discover -s tests -p 'test_nvsu*.py'
node tests/run-current.cjs
node --test tests/regression.cjs
node tests/audit.cjs
```

- Python **64 PASS**: parser 8, sync 24, Google/state 24, source/CLI 8. Все Calendar HTTP замоканы; fixtures очищены, настоящий ADC не используется.
- Текущий Apps Script 2.0.5 **101 PASS** (64 существующего поведения + 37 консультаций). Отдельно исторические regression 69 PASS и audit 19 PASS; они пересекаются с текущими и не являются дополнительными уникальными тестами.
- `tests/test_nvsu_google.py`: default readonly без HTTP-мутаций, explicit Calendar ID, страницы/all-day/manual events, whitelist, детерминированный insert/409, If-Match/412, restart после принятого create/update/delete, SQLite lock/target, fresh source/TTL/hash, новые конфликты, защита linked events, явное локальное подтверждение, expired readonly reconciliation. Два ownership-теста сначала падали, затем исправление проверено.
- `tests/test_nvsu_source.py`: реальный исследованный URL недели через mock fetch, HTTP/MIME/UTF8/size/redirect ошибки, wrong week, невозможная дата, переход года, offline CLI без ADC, приватные файлы и отсутствие apply.
- Отдельный venv: установка `requirements-calendar.txt`, `pip check` PASS. SDK/scopes smoke использует AnonymousCredentials и подменённый google.auth.default; credential-файлы и сеть не используются этим smoke.

Следующая интеграционная приёмка — **не запускалась**: Calendar API/ADC/ACL на согласованной sandbox; readonly plan с фактическими данными; резервная копия/ledger; после отдельного разрешения insert/replay/update/delete своего события, 412/тайм-аут/ручные правки, визуальная сверка текущей/соседних недель с источником. Проверить отсутствие дублей и лишних полей. Не изменять рабочие триггеры/бот. Полноту источника для консультаций не включать до приёмки. Инструкции и демонстрационный план: [NVSU_CONNECTION_PLAN.md](NVSU_CONNECTION_PLAN.md).

---

# План тестирования

## Unit tests
- Проверка статуса доступа: `Одобрен`, `Не одобрен`, `Доступ отключён`, пустое значение, неизвестный пользователь.
- Даты: ISO, dd.MM.yyyy, високосный год, 30 февраля, пустое значение, строка с пробелами.
- Разбор команды и текста поручения: фамилии с пробелами, кириллица, пустые поля, delimiter отсутствует.
- Нормализация ID и сравнение chat ID без потери ведущих/знаковых символов.
- Формирование сообщений, ограничения длины Telegram, обработка ошибок API.

## Integration tests (только на тестовых ресурсах)
- Telegram update обрабатывается один раз даже при повторной доставке.
- Устаревший callback не блокирует следующие updates.
- Ошибка обработки одного update не приводит к вечному блокированию очереди.
- Сбой после отправки Telegram, но до записи статуса, не создаёт бесконтрольные дубликаты.
- Отправка поручения одобренному адресату; отклонение неизвестного/неодобренного.
- Приём текста, документа, фотографии; ошибка сохранения Drive.
- Триггеры: опрос, отправка поручений, напоминания, ежедневная сводка.
- Консультация: конфликт времени, повторная проверка слота, отказ владельца, повторная заявка.
- Парсер расписания: текущая/предыдущая/следующая неделя, пустая страница, HTTP 403/500, изменённая разметка, устаревший кеш.

## Acceptance
- Нет доступа к production-данным из тестов.
- Каждый результат внешнего действия подтверждён ответом сервиса и журналом.
- Успешное локальное тестирование не называется подтверждением production-доставки.
- Перед релизом: резервная копия, журнал изменений, инструкция отката и явное подтверждение владельца.

## Этап 1 — регрессии кандидата 2.0.3

Исполняемый локальный suite: `node --test tests/regression.cjs` из корня проекта. Требуется Node.js с built-in test runner (проверено v24.19.0), сторонних пакетов нет. По умолчанию загружается только новый кандидат, транспорт и Google-сервисы заменены in-memory mocks, реальная сеть/секреты не используются. Clock фиксирован на 26.10.2026, Utilities — ограниченный mock +05:00.

Итог текущего запуска: **58 тестов, 58 PASS, 0 FAIL, 0 skipped**. Большинство defect regression-тестов сначала запускались с правильными ожиданиями на неисправленном коде (red), затем повторялись после исправлений (green); промежуточные результаты сохранены в отчёте. Для сверки исходной проблемы можно использовать `RUN_CANDIDATE=src/telegram_assistant_v2_0_2_candidate.gs node --test tests/regression.cjs`: это диагностический запуск, часть тестов нового API заведомо не поддерживается старой версией. Не считать его release suite для 2.0.2.

| Группа / префикс тестов | Что проверяется |
|---|---|
| `consult:` | Повтор после отказа уведомления/append, разные message IDs, невозможная дата и неодобренный пользователь |
| `file:` | Upload до отказа Sheets, accepted-create timeout, временно невидимый файл, download failure, фактический и заявленный размер, public folder refusal, разные сообщения и фото |
| `recurrence:`, `repeat:` | Отказ marker/append, занятый lock, weekly/off/revoked, draft/confirm, owner-only и неверная cadence |
| `command retry:` | `/assign`, `/repeat`, `/broadcast` не дублируют строки после отказа ответа |
| `reply recovery` | Дата/текст дозаписываются после статуса; последующие ручные «Выполнено»/комментарий сохраняются |
| `queue:` | Durable payload до ack, 3 попытки, следующий update, отказ inbox/DEAD/offset, pre-dispatch attempts, explicit replay |
| `delivery:` | Принятый send + отказ записи, UNKNOWN без resends, flush до send, сохранение message_id до SENT, восстановление task trigger |
| `broadcast:` | Frozen/deduplicated recipients, отказ конечного статуса, oversized draft, revoked → SKIPPED |
| `calendar:` | Accepted create + timeout, отказ записи event ID в заявке, all-day конфликт, неверная длительность, конфликт перед create |
| `timetable:` | Stale no-schedule не блокирует fetch, время и предупреждение fallback, отказ append сохраняет старый snapshot |
| `registry:` | ID без имени/контракта не пишет в первый лист; явная схема сохраняет ручной next step |
| `config:`, `schema:`, `compatibility:`, `static:` | Fail closed без ID, blank/reordered headers, дополнительные колонки, неизменность всех CFG headers/SHA исходников, синтаксис и уникальность функций |
| `regression:`, `lock:`, `idempotency:` | Точный допуск и даты, owner inbox и `/add`, истёкший callback, владение lock, отказ при существующих дублях ID |

`node tests/audit.cjs` — отдельные **19 исторических audit probes** на 1.4.3/2.0.2. Они специально подтверждают наличие старых дефектов; PASS этого файла не доказывает исправление нового кандидата.

### Обязательная изолированная интеграционная приёмка — пока не выполнена

1. Отдельный test bot и тестовый Apps Script project, копии Sheets, закрытая папка и отдельный Calendar; никаких ID production. Не загружать несколько snapshots в один project одновременно.
2. Проверить новые Script Properties из отчёта, OAuth/scopes, реальные заголовки и validation (включая «Черновик»); проверить права новых технических листов. Registry включать только с отдельным ID, явным именем листа и проверенным девятиколоночным контрактом заголовков из отчёта.
3. Реальный typed round-trip дат и времени из Sheets, включая Date из getValues; all-day/recurring события, смежные интервалы, +05:00. Повторно проверить owner confirm и доступ студента.
4. Telegram 429/403/timeout после принятого send; сохранённый message_id/UNKNOWN; повтор delivery/confirm, прерывание execution между каждым внешним действием и checkpoint. Никаких auto reset UNKNOWN в READY.
5. Drive inherited sharing, lookup после create timeout, duplicate names, удалённый/перемещённый файл, отсутствие прав, blob limits и квоты Properties; не публиковать файлы и не очищать markers без сверки.
6. DEAD/replay с частичными side effects, payload limit >45000, сбой сохранения журнала, истечение времени execution; политика retention/архивации payload и технических листов.
7. Документированное исследование реального источника НВГУ и обезличенные successful HTML fixtures для prev/current/next недель; до этого не считать text snapshot структурированным расписанием. Проверить изменённую страницу, 200 maintenance, 403/500 и stale fallback.

Тесты выше в текущем этапе **не запускались**. Локальный suite не является подтверждением Telegram-доставки, GAS trigger execution, Google permissions/consistency или готовности к production. Rollout с backup/rollback и явным разрешением — отдельная задача.

Доступность источника НВГУ проверена отдельной read-only HTTPS-попыткой: прокси отказал в CONNECT (`Tunnel connection failed: 403 Forbidden`). HTML не получен, реальные недели/селекторы не подтверждены. Это не результат парсерного или интеграционного теста; T01 требует разрешённого доступа к `tm.nvsu.ru` либо подтверждённых fixtures.


## Продолжение — кандидат 2.0.4 (текущий)

По умолчанию `node --test tests/regression.cjs` теперь загружает `src/telegram_assistant_v2_0_4_candidate.gs`. Результат: **69 PASS, 0 FAIL, 0 skipped**. Раздел о 58 тестах выше — исторический итог 2.0.3. Старые исходники защищены SHA-256; дополнительно фиксируется SHA 2.0.3.

Новые проверки (`navigation:` и `callback authorization:`):

- Два просмотра одного чата сохраняют разные target URL, callback не длиннее 64 байт.
- Другой чат не использует чужую кнопку; отсутствие ссылок не переназначает старые кнопки.
- TTL 1 час, неизвестные/legacy callbacks, повреждённые записи не вызывают fetch; cleanup не затрагивает секреты и активное состояние других чатов; максимум 40 активных ссылок на чат.
- HTTP, чужой host, подменённый URL отбрасываются.
- Renderer передаёт chat ID; обе ссылки prev/next проходят через реальный router в mock-окружении; отозванный доступ блокирует переход.
- Non-private callback и from.id, отличный от chat ID, не меняют выбранное поручение; прежняя проверка expired acknowledgement остаётся зелёной.

Начальный red-запуск: `RUN_CANDIDATE=src/telegram_assistant_v2_0_3_candidate.gs node --test --test-name-pattern='navigation:|callback authorization:' tests/regression.cjs` на первых восьми тестах дал 1 PASS / 7 FAIL. Это диагностический baseline; текущий полный suite содержит дополнительные проверки.

URL `/test-only/week-*` — явно синтетические fixtures навигации, а не предположение об endpoints реального сайта. Проверка реальных недель/HTML/занятий и Apps Script Properties/TTL в живой sandbox не выполнялась. Для T01 сохранён черновик разрешения домена `tm.nvsu.ru`; backend подтвердил сохранение с необходимостью публикации среды. До применения настроек и повторной загрузки HTTP-доступ не считается работающим.


## Консультации — кандидат 2.0.5 (текущий)

Главная команда: `node tests/run-current.cjs` — **101 PASS, 0 FAIL, 0 skipped**: 64 проверки неизменённого поведения из regression suite, явно запущенные на 2.0.5, плюс 37 проверок в `tests/consultations.cjs`. Runner сохраняет exit status любой упавшей группы. Прежние ожидания 30 минут и отсутствия Calendar event до approve заменены согласованными правилами в новом suite, а не отключены ради зелёного результата.

Исторический `node --test tests/regression.cjs` по умолчанию всё ещё проверяет 2.0.4 — 69 PASS. `node tests/audit.cjs` — 19 исторических probes старых snapshots. Не складывать эти пересекающиеся группы в число уникальных сценариев текущего кандидата. Общая fixture вынесена в `tests/helpers/apps-script.cjs`, прежние suites проверены после рефакторинга.

Новые тесты покрывают:

- 20 минут, 317, 09:00–18:00, lunch 11:40–12:20, weekend, края интервалов и booking/cancel ровно за 30 минут.
- Отсутствие полного источника занятий и частично заполненный Calendar: никакой заявки/резерва; обычная занятость и урок блокируют слот.
- Студенческое меню, все страницы свободного времени, bulk чтение календаря, тему, preview/submit/discard, stale tokens, прерывание `/tasks` без вмешательства в поручения.
- Provisional event сразу после submit; стабильный ID, повторные запросы, accepted-create timeout, failure записи event ID в Sheets, запрет второго резерва в тот же интервал.
- Approve обновляет то же событие, повторно проверяет уроки; студент не может нажать чужое owner-действие.
- Только свои заявки; cancel pending/confirmed, foreign event marker refusal, reject удаляет предварительную запись, delete accepted + timeout завершается повтором без дублей уведомлений.
- Durable consumed-topic key: replay темы не становится ответом на поручение и не перезаписывает новый draft.
- Typed Date/date-only/time-only cells: корректное время события и уведомлений без 1899/UTC-сдвига; неизменность 2.0.4 по SHA и всех CFG headers.

До live sandbox остаются: реальные callback bytes/сроки, Telegram UNKNOWN/429/403, Calendar visibility после create/delete и внешние гонки, scopes/права, валидация новых статусов, запрет чужого delete, полный диапазон занятий/праздники и отсутствие дублей импорта. Владелица подтвердила, что занятия есть лишь частично; флаг полной занятости включать нельзя до проверенного импорта из НВГУ. Проверка скорости чтения общего Calendar ассистентом по расписанию не выполнялась.

### Исследование источника НВГУ и read-only preview

`python -m unittest discover -s tests -p 'test_nvsu_preview.py'` — 8 PASS. Parser также запущен на реально загруженных HTTP 200 HTML трёх недель: 13 занятий / explicit no-schedule / 11 занятий. ICS исследован и не импортировался: содержит даты за пределами выбранной недели и не имеет UID. Сравнение выполнено только с искусственным частичным Calendar JSON; реальные события не читались и не менялись. Методика и provenance очищенных fixtures — в `docs/NVSU_SOURCE.md`.


## Уточнённые правила переноса расписания

`python -m unittest discover -s tests -p 'test_nvsu*.py'` — **32 PASS / 0 FAIL** (8 parser/preview + 24 sync-model). Тесты: только time/title/location в видимом payload, объединение строк разных групп/source IDs, конкретная дата/неделя, empty-week без новых событий, update того же ID по изменённым времени/дисциплине/аудитории/дню, повторный импорт без дублей, смена source ID, первичное ручное совпадение, неоднозначность, ручные изменения, scoped removal и preflight после preview.

`apply_sync_plan` испытывается только с MemoryCalendar. Реальный Google adapter отсутствует, list-backed ledger не является durable storage, совместимость/идемпотентность Google API не заявляется. Перед включением импорта нужны реальные sandbox tests и долговременный ledger. Описание: `docs/NVSU_SYNC_RULES.md`.
