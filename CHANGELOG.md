# 29.10.2026 — original-evidence consultation consent registry/worker

- OwnerReview captures source/event/actor before final confirm; immutable BoundPlan+source claim publication atomic, original confirmation timestamp survives retry.
- Bound worker uses verified update idempotency; Calendar reads outside SQLite locks, fresh UI dispatch read-only, legacy proposals retained, all flags default off.
- 24новыхtests,572Python/110Node PASS; private read-before-owner gate fixed red→green. No live resources/deploy. docs/CONSULTATION_CONSENT.md.

# 29.10.2026 — local source finalization + independent consultation notices

- Fixture SQLite CAS/claim + orchestration Calendar evidence→atomic status/reason and2notice jobs; eleven fields/status names preserved, custom note/event ID retained.
- Independent business-key outbox, fresh owner/recipient/revision gates, durable send claims and no retry unknown/inflight; failed student notice does not block owner.
-27новыхPython tests;548Python/110Node PASS,6offline demos. No actual Sheets/Calendar/Telegram API or deploy. Live consent/source CAS/writer coordination/verification/rollout still separate. docs/CONSULTATION_WORKFLOW.md.

# 29.10.2026 — consultation Calendar-stage executor candidate

- Strict original-evidence BoundPlan, current owner/student/source/hold/busy/teaching/ETag preflight. Unbound legacy plans denied, propose/create absent.
- Separate private durable claims before side effect, unknown/inflight no retry; read-only marker/state/absence recovery. Calendar API receipt does not finalize Sheet or notify students.
- Port reuses existing GoogleCalendarAdapter, conditional same-event PATCH/DELETE, no time/note rewrite, private operation marker, sendUpdates=none. Defaults off, all tests mocked.
- 38 новыхPython tests;521Python/110Node PASS,5offline demos. Source CAS/writer coordination/finalization/notifications/template/sandbox acceptance remain; production unchanged. docs/CONSULTATION_EXECUTOR.md.

# 29.10.2026 — atomic local consultation worker

- Existing inbox/action sandbox/dispatch связаны отдельным opt-in worker; action processing вне read-only send preparation. Локальный receipt атомарен с plan/intent/status через SAVEPOINT.
- Добавочная action_updates, private reply hashes, immutable explicit bot binding; compatibility с synthetic v1 plans и direct API без bot_id.
- Fresh owner gate перед UI send, no duplicate handler/restart/unknown resend; defaults off. Demo теперь проходит worker и injected mock sender.
- 24 новых tests, полный483Python/110Node PASS. Нет actual Calendar/Sheet execution, notify/student agreement, polling/deploy или real sends. Контракт docs/CONSULTATION_WORKER.md.

# 29.10.2026 — read-only вход заявок и занятости

- ConsultationFeed/BusyFeed: existing 11 columns, typed dates, freshness/coverage, private row revisions, verified binding-only hold, calendar-qualified IDs; существующий GoogleCalendarAdapter, без нового Calendar transport.
- Отдельный consultation_snapshot_export.gs helper кандидат читает существующий лист без initialize/tab_/rows_/log_; не установлен, не запускался на real данных. Bounded private JSON decoder не выдаёт authorization.
- Red→green: invisible recipient/event change invalidates decision ref, age checked after assembly, source verification chronology, subminute typed time rejected without rounding.
- 29 новых Python+9Node VM tests; полный459Python/110Node PASS,4offline demos. Live auth/collection/import verification/CAS/executor не подключены; working GAS/resources сохранены. Контракт docs/CONSULTATION_FEED.md.

# 29.10.2026 — локальные планы решений по консультациям

- Добавлены offline core/UI/demo и 30 тестов: preview/explicit confirm/cancel, revision/expiry/owner gates, same-event calendar plan, два уведомления-намерения, предложение без снятия резерва.
- Durable atomic plan/status/intent, повторы/две connection/restart без дубля, rollback при частичном сбое SQLite. Регрессия: доступ студента повторно проверяется после чтения занятости.
- Ни реальных API, ни production/deploy; авторитетные Sheets/GAS сохранены. Live dispatcher, executor и согласие студента на перенос — следующие отдельные этапы. Документация: docs/CONSULTATION_ACTIONS.md.

# Owner decision queue — 29.10.2026

- Current-source read-only owner dashboard: consultations/reviews/technical, dates/filters/pagination/detail/version references, partial source warnings.
- Normalized dated consultation feed contract; actual local review/dispatch sources, personal+academic permission gates, opt-in adapter/worker integration.
- Исправлены false active-send incident и concurrent worker blocking; inflight остаётся pending без resend до проверенного исхода.
- 34decision+2worker tests,400Python+101Node PASS;3offline demos. Никаких live API, grades, source mutations или deployment.

# Reports-only queue worker and failure recovery — 29.10.2026

- Bounded worker соединяет inbox/current policy/dispatch; API receipt recovery не повторяет send после mark failure, unsupported updates сохраняются для других handlers.
- Итого51новыйtest транспортного блока; полныйPython364+Node101 PASS, вся приёмка offline/mock-only. Real runtime/сервисы/журнал/deploy не затронуты.

# Mock-tested Telegram HTTP and durable dispatch ledger — 28.10.2026

- Fixed-origin bounded POST/no redirect HTTP, configured bot verification, default network/writes off.
- Durable per-update claim, fresh preparation, api_confirmed/rejected/unknown/cancelled; no blind retry after timeout/process stop/result persistence failure.
- 13ledger+10HTTP+8integration+10inbox tests, Python354 PASS; реальные API/отправки не выполнялись. Durable store-before-ack inbox/cursor добавлен, real worker отсутствует, GAS неизменён.

# Trusted-input Telegram report adapter — 28.10.2026

- Private numeric from/chat identity parsing, bot-owned callbacks и reports-only routing через существующую current policy; без настоящего API/offset/ack/send.
- Ambiguous message+edited update defect воспроизведён и исправлен.11adapter+1integration tests, полныйPython313 PASS.
- Реальные credentials/authentication/bindings/transport/deploy отсутствуют, GAS неизменён.

# Durable local assistant integration — 28.10.2026

- ReportRegistry: immutable ownership/check links с безопасным retry публикации после partial failure.
- PolicyStore: private versioned AccessPolicy snapshots, CAS revoke protection, no automatic roles/older fallback.
- Полный offline assistant_demo с SQLite, navigation, restart, revoke и duplicate recovery; synthetic fixtures only.
- 23 новых tests;301Python+101Node PASS. Production/API/письма/журнал не затронуты.

# Local progress inline-button model — 28.10.2026

- PreparedReply keyboard rows, open/page/back callbacks с short source-bound references и current self authorization; без Telegram API.
- 8 новых tests, полныйPython278 PASS; Node не перезапускался, GAS неизменён. Production не подключён.

# Self-only progress list and pagination — 28.10.2026

- Bare progress + page N, trusted self resolution, five own reports per page, no foreign reads/counts, revoke/rebind checks.
- 10 новых tests, полныйPython270 PASS; Node не перезапускался, GAS неизменён. Real commands/transport не подключены.

# Prepare policy-gated local report replies — 28.10.2026

- Локальные progress/report requests, purpose narrowing, bounded Unicode plain-text replies; без отправки/доставки.
- 10 новых tests, полныйPython260 PASS; Node не перезапускался, GAS неизменён. Production не подключён.

# Policy-gated local report retrieval — 28.10.2026

- ReportReader: trusted ownership links, current policy before/after load, student/teacher projections, revoke/rebind protection, uniform safe denial.
- 13 новых synthetic tests, полныйPython250 PASS. Node не перезапускался, GAS неизменён. Нет real identity/transport/send/gradebook integration.

# Validate content observation citations — 28.10.2026

- Finding/Citation binding к current plan/work и точным slide text offsets; отдельные needs_review наблюдения без grades/credit/перезаписи structural статуса.
- 9 evidence tests +2 demo tests; полныйPython237 PASS. Node не перезапускался, GAS неизменён. Semantic generation/production отсутствуют.

# Bind slide criteria to versioned rules — 28.10.2026

- Исправлена воспроизводимая подмена minimum runtime параметром: структурный criterion читается из versioned rules; legacy params только сверяются.
- Добавлены source-bound minimum-slide suggestions (всегда review), M04 local upload дал40.
- 10 новых tests, полныйPython226 PASS; Node не перезапускался (последний101 PASS). Live операции отсутствуют.

# Structural homework review pilot — 28.10.2026

- PPTX manifest reader и локальный отчёт minimum slides с evidence/version binding. Никаких оценок, автопринятия или внешних операций.
- 14 новых synthetic tests, полныйPython216 PASS; Node не перезапускался (последний101 PASS), GAS без изменений.

# Source-to-catalog pipeline — 28.10.2026

- MaterialProvider связывает свежую загрузку, DOCX extraction и trusted source-bound validation с существующей историей версий; без автоматического approval.
- 10 новых end-to-end/offline tests + 5 draft tests, полный Python202 PASS. GAS не менялся, Node не перезапускался (последний101 PASS). M04 upload прочитан только локально: четыре source-bound draft sections. Нет live source reads, grades, mail или deployment.

# Read-only public DOCX refresh — 28.10.2026

- Добавлен material_source: metadata before/after, SHA-256/size, bounded HTTPS GET, no redirects/cache/token/writes.
- 8 новых offline tests; полный Python187 PASS. GAS не менялся, Node не перезапускался (последний101 PASS). Live интеграция/semantic rubric validator ещё отсутствуют.

# Локальный DOCX extractor — 28.10.2026

- `tools/material_docx.py`: bounded text/table extraction, review flags, no network/execution or automatic rubric approval.
- 11 новых синтетических tests; полный Python 179 PASS. Последний Node 101 PASS, не перезапускался. Live adapter/grader и рабочие ресурсы не менялись.

# Changelog

## Актуальные материалы и версии проверок — 2026-10-28

- Прочитан M04 upload; вопросы M02 исключены пользователем. Подтверждено №ДЗ→такая же №лекция, не все темы работы.
- Добавлен local material_versions.py: SQLite history, source/rubric/parser versions, fresh-provider prepare/finish, no stale fallback, needs_recheck/CAS и immutable completed results.
- 14 synthetic tests, полный Python 168 PASS, Node 101 PASS. Live watcher/parser/grader, почта и журнал не подключены/не менялись.

## Частичный каталог учебных DOCX — 2026-10-28

- Прочитаны 3/5 материалов: инструкция, дистанционная ссылка, задания шести практик; каталог docs/MATERIALS_CATALOG.md.
- Два файла вопросов/lecture makeup не скачиваются HTTP500/503, содержание не выдумывается. Raw DOCX/контакты не включены в Git.
- Зафиксированы конфликты старых правил с новым ТЗ; оценки/письма/журнал/живые документы не менялись. Только аудит/документация, tests не запускались.

## Уточнение положения журнала — 2026-10-28

- Direct public-folder metadata подтвердили 1 XLSX + 5 DOCX; XLSX совпадает с загруженным журналом по имени, размеру и MD5 metadata. Remote content не скачивался.
- Личный Disk scan не охватывал public context; расположение книги теперь известно. Новых Actions/токенов/публикации среды нет.
- Зафиксирована необходимость отдельного решения о закрытом хранении журнала; sharing/данные не изменялись. Только документация, tests не перезапускались.

## Read-only metadata inventory Яндекса — 2026-10-28

- Добавлены отдельный manual workflow и bounded поиск spreadsheet metadata по имени; папка проверяется без чтения содержимого. Нет downloads/writes/публикации имён/путей.
- 8 новых tests, полный Python 154 PASS. Real run 40647021089: materials readable, journal not_found_in_scan (0, scan_complete), OAuth работает.
- Запрошено расположение журнала; публичный доступ не нужен. Node не запускался, GAS не менялся.

## Проверка Яндекс Диска через GitHub Actions — 2026-10-28

- Добавлен ручной fixed metadata GET с repository Secret, без auto triggers, файловых списков и изменений; timeout 2 минуты.
- 8 probe mock tests PASS, полный Python 146 PASS. Реальный Actions run выполнен: secret получен, API Яндекса вернул HTTP401/token_rejected, доступ не подтверждён.
- Публикация среды/Почта/журнал/бот не запускались; Node в этом этапе не перезапускался. Подробности docs/YANDEX_CONNECTION.md.

## Локальные lecture windows — 2026-10-28 — не развёрнуто

- Добавлен контроллер 90-секундных кодов с SQLite restart/retry/concurrency и AES-GCM; ключ не хранится в БД.
- AEAD связывает срок/источник/оператора; актуальные права и замещение перепроверяются, новые регистрации после revoke закрыты.
- Один local attendance на lecture+student, persistent failed-attempt limit, receipt not_synced; нет записи XLSX/отправки/QR.
- 22 windows tests PASS (также cryptography 50.0.2), полный Python 138 PASS, Node 101 PASS. Четыре воспроизведённых дефекта исправлены.

## Полный академический доступ пользователя — 2026-10-28

- По запросу добавлен отдельный AcademicReadGrant для чтения расписаний и всех известных учебных данных/истории студентов проекта.
- Второй преподаватель и студенты не получают расширения автоматически; запись/отправка/личные данные/lecture полномочия остаются отдельными.
- 6 новых тестов: всего 36 policy, 116 Python, 101 Node PASS. Нет real account bindings или deployment.

## Локальная модель доступа двух преподавателей/студентов — 2026-10-28

- Добавлено academic authorization-ядро: подтверждённые bindings, Teacher/Student/Enrollment, предметные grants и отдельное session-specific замещение. Default deny, точные ID, неизменяемые snapshots, ограничения Telegram/email/ChatGPT и проверка временных интервалов.
- 30 policy tests PASS, полный Python 110 PASS, текущий Node 101 PASS. Исправлены четыре воспроизведённых краевых сценария.
- Нет реальных account bindings/authentication/persistent registry, `/progress` и lecture-коды ещё не подключены. Apps Script/внешние данные и публикация среды не менялись.

## Согласование lecture-кодов в Telegram и замещения — 2026-10-28

- Вместо фиксированных утренних окон: запрос кода кнопкой, 90 секунд от успешного открытия, доступ обоим преподавателям.
- Пользователю предусмотрено отдельное право замещения второго преподавателя; личные данные и обратные права автоматически не открываются.
- Добавлены требования конкурентного/повторного открытия, единственного присутствия и будущие тесты. Это изменение контракта, без реализации и deployment; тесты не запускались.

## Требования совместной работы преподавателей — 2026-10-28

- Подтверждён один бот для двух отдельных аккаунтов: собственное расписание и учебные отчёты по назначенным дисциплинам/группам.
- Зафиксированы изоляция личных данных, отсутствие автоматического второго owner и общая policy Telegram/email/ChatGPT.
- Дополнены план и будущие критерии приёмки. Это документация, код/реальные права не изменены; тесты повторно не запускались.

## Локальное чтение учебного XLSX — 2026-10-28 — не развёрнуто

- Добавлен read-only gradebook_read.py: relationships, merged cells, shared formulas/cache, даты Excel, скрытые поля, структурный CLI без имён/оценок.
- Добавлены 16 синтетических тестов, включая три воспроизведённых дефекта защиты структуры/вывода.
- Проверено чтение загруженного актуального журнала: исходный файл не менялся; данные не копируются в fixtures.
- 80 Python PASS и 101 текущего Node candidate PASS. Нет сети, записи XLSX, отправки, подключения `/progress` или публикации среды.

## НВГУ / подготовка подключения Calendar — 2026-10-27 — не развёрнуто

- Существующий parser/sync дополнен Google v3 адаптером (readonly default), SQLite ledger/checkpoints и проверенным fetch выбранной недели.
- Защищены ручные события; стабильные insert IDs, ETag PATCH/DELETE, восстановление после неизвестного результата и readonly reconciliation.
- Добавлен только preparation CLI без apply; fixture/snapshot не могут применяться к Calendar.
- Предварительный план и условия подключения: docs/NVSU_CONNECTION_PLAN.md. Реальный календарь/бот/триггеры не изменены.
- 64 Python PASS, 101 текущего Node candidate PASS; исторические suites отдельно 69/19 PASS.

## Уточнение импорта НВГУ — 2026-10-27 — локальная модель

- Для Calendar оставлены только время, дисциплина и аудитория; группы/потоки и тип занятия исключены.
- Дубликаты групповых строк объединяются даже при различных ID источника.
- Конкретная дата проверяется относительно выбранной недели. Проверенное «Расписание отсутствует» даёт нулевой список занятий и не создаёт событий.
- Добавлен read-only sync plan: обновление того же event ID вместо повторного create, пропуск неизменённого, внешние bindings, ручные/неоднозначные совпадения на сверку.
- Тестовая модель адаптера проверяет replay и preflight. Реального Google-адаптера, production-изменений и записи Calendar нет.
- Python suite: 32 PASS; Apps Script candidates сохранены.

## 2.0.5 candidate — 2026-10-27 — не развёрнут

- Раздел консультаций: «Записаться», «Мои заявки», «Правила». Пошаговый диалог день → время → тема → preview → submit.
- Согласованные правила: 20 минут, кабинет 317, будни 09:00–18:00, обед 11:40–12:20, запись/отмена минимум за 30 минут.
- После submit создаётся предварительное занятое событие в целевом Calendar. Личное approve обновляет то же событие; reject/cancel удаляет только событие заявки по проверенному marker. Обе стороны уведомляются через outbox.
- Дедупликация заявки/события, recovery create/delete timeout, owner-only callbacks, фильтрация своих заявок, защита от старых submit и повторной доставки темы.
- Поддержка typed Date/time cells Sheets; время в уведомлениях форматируется в Asia/Yekaterinburg.
- Общий mock вынесен в tests/helpers, добавлен runner текущего кандидата: 101 локальная проверка прошла (64 сохранённых + 37 новых). Старые 69 тестов продолжают проходить на 2.0.4 отдельно.
- Исследован реальный источник НВГУ после восстановления HTTP-доступа; добавлен read-only HTML parser/preview и 8 Python tests. Найден небезопасный для прямого импорта multiweek ICS без UID. Записей Calendar нет.
- Пункт 11 AGENTS.md уточнён по явному разрешению владелицы на предварительные календарные записи; рабочие ресурсы не подключались.

Блокер: занятия внесены в Calendar лишь частично. До проверенного импорта/полного источника подбор и создание заявок закрыты. Импорт НВГУ, реальная синхронизация ассистента, Google API и Telegram ещё не проверены. Предыдущие версии сохранены; production не менялся.

## 2.0.4 candidate — не развёрнут

- Новый отдельный кандидат; 2.0.3 и исходные snapshots сохранены.
- Кнопки недель используют индивидуальные tokens, chat scope, TTL 1 час и ограничение 40 активных ссылок на чат; общие URLs больше не используются.
- Legacy/unknown/expired/tampered callbacks отклоняются; target URL ограничен HTTPS и точным host НВГУ.
- Callback требует private chat и совпадения from.id с chat ID; текущая проверка доступа сохранена.
- 69 локальных тестов прошли, включая 58 прежних проверок и сохранность 2.0.3.
- Сохранён черновик разрешения `tm.nvsu.ru` в облачной среде. Изменение не применено и не опубликовано; parser НВГУ остаётся заблокирован до доступа к реальному HTML.

Реальные интеграции, доставка Telegram, семантика недель и полнота расписания не проверены. Изменений production нет.

## 2.0.3 candidate — 2026-10-26 — не развёрнут

- Отдельный кандидат `src/telegram_assistant_v2_0_3_candidate.gs`; snapshots 1.4.3/2.0.2 сохранены без изменений.
- Детерминированные chat/message ID и append-once для консультаций, поручений, правил повторов и черновиков рассылок.
- Идемпотентное сохранение вложений в явно заданную закрытую папку; остановка при неопределённом create; ошибки файла больше не маскируются успешным ответом.
- Генерация повторов под общим lock с поиском существующего rule/date ID; preview и `/confirmrepeat ID` для новых правил.
- Durable update inbox с payload, bounded attempts, DEAD и операторским replay без перемотки offset.
- Журнал отправок с message_id, восстановлением известных результатов и запретом автоматического повтора UNKNOWN.
- Зафиксированная аудитория рассылок, дедупликация chat ID и результаты по адресатам; лимит текста 3000 символов.
- Calendar operation ledger, request markers, recovery принятого create и частичной записи консультации; явный тестовый Calendar вместо default.
- Реестр требует явный лист и контракт девяти заголовков; синхронизация сохраняет ручной следующий шаг. Durable reconcile/backfill пока отсутствует.
- Проверка обязательных заголовков существующих листов, resource IDs только из конфигурации; бизнес-колонки не менялись. Добавлены отдельные технические листы.
- Исправлена дозапись полей ответа после частичного сбоя. Снимки расписания сохраняются без очистки предыдущей версии; stale fallback имеет дату и предупреждение, вывод не объявляется проверенным расписанием.
- 58 локальных regression/static/compatibility tests прошли; 19 исторических audit probes сохранены отдельно.

Ограничения: реальные Apps Script/Telegram/Sheets/Drive/Calendar не тестировались; parser НВГУ, часть авторизации callback, literal/formula handling, общий реестр, rate limiting и ряд уведомлений требуют дальнейших исправлений. UNKNOWN требует ручной сверки; exactly-once внешних действий не обещается. Подробности и схема технических листов — в `docs/AUDIT_REPORT.md`.
