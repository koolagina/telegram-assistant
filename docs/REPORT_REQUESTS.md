# Telegram report adapter: trusted polling input — 28.10.2026

Добавлен tools/telegram_report_adapter.py. Инъецируемый fetch_verified_updates — только доверенный серверный Bot API transport с проверенным TLS/ботом; настоящий HTTP-клиент/проверка происхождения/secret handling не реализованы. Структура ok/result и имя класса не доказывают authenticity. Нельзя подключать public JSON body, LLM args или непроверенный webhook к этому callable. Поддержан только reports-only разбор verified polling input, без изменения действующего GAS poller/webhook.

Для message используются числовые from.id и chat.id: только private, равные положительные integer IDs, from.is_bot=false, валидные message id/date. Username, display name и student/teacher ID из текста не назначают роль; binding ищется по каноническому str(from.id) в текущей policy. Callback требует private message для фактического нажавшего from.id и сообщения от configured bot id с is_bot=true. Inline/inaccessible(date0)/group/mismatched sender callbacks не маршрутизируются. Обрабатываются только progress/report commands и progress callbacks; прочие команды/edited messages остаются другим обработчикам.

До чтения payload проверяются API envelope, batch≤100, update integer IDs/uniqueness и ровно один update payload key. Найден и воспроизведён отдельным красным тестом случай message+edited_message: теперь двусмысленная пачка отклоняется. Prepared TelegramPreparation содержит update/chat/reply/callback-query reference, но не API success/delivered. Нет offset/ack/durable update queue/outbox/sendMessage/answerCallbackQuery или reconnect/retry. Повторная пачка заново проверяет current policy, но не является реализованной дедупликацией будущей отправки; future transport обязан reprepare непосредственно перед send и отдельно вести durable delivery state.

11 adapter tests +1 integrated durable-policy test, полный Python **313 PASS**. Первый запуск без модуля красный; ambiguity test red→green. Проверены private/canonical sender vs username, group/mismatch/bot/bool IDs, teacher spoof attempt, bot-owned callback, forwarded foreign reference, API failure/duplicate IDs/ambiguity, edited/unsupported/inaccessible/inline updates, source failure sanitization и current revoke. Integrated assistant session использует явно fake numeric Telegram subjects103/104/101, не настоящие IDs. Никаких реальных Telegram API/аккаунтов/сообщений/почты/журнала/deploy.

Реальную authentication/adapters нельзя считать готовыми: transport verification и административная верификация account binding ещё требуют подключения к отдельной test environment. Локальная часть только корректно строит Context из уже доверенного источника и вызывает существующую policy. Полноценная semantic evaluation/порог принятия не реализованы.

---

# Durable links/policy и сквозной локальный сценарий — 28.10.2026

Добавлены tools/report_registry.py и tools/policy_store.py, отдельные private SQLite WAL/FULL файлы (directory0700/file0600, symlink/foreign schema/namespace mismatch refusal). Существующие MaterialCatalog schema, Google Sheets и GAS snapshots не менялись.

ReportRegistry хранит immutable ReportLink. Публикация разрешается только после local done с matching check/material identity и needs_teacher_review/credit_written=false. Повтор той же связи идемпотентен; один report/check нельзя перепривязать другой ownership relation. Register — только trusted ingestion API, не пользовательский endpoint. Нет выдачи прав из факта публикации. Перерыв после material commit до link publication восстанавливается retry, как и timeout после accepted publication. Это не транзакция между двумя DB; при потерянной истории read остаётся unavailable, не создаёт оценку заново. Backups должны учитывать обе DB и WAL.

PolicyStore сохраняет полные снимки существующего AccessPolicy: teachers/students, confirmed bindings/capabilities, enrollments, teaching/full academic/substitution grants и lectures с aware датами. Пустая DB даёт пустую deny-all policy, не admin/binding. Save требует expected_revision и BEGIN IMMEDIATE; stale writer не перезаписывает новый revoke. Load читает только последнюю валидную ревизию, corruption останавливает доступ без fallback к старым grants. Snapshot не authentication: записи/подтверждения может создавать только доверенная административная процедура, не LLM/student payload. Нет public provisioning endpoint, секретов, реальных аккаунтов или автоматического owner grant. Ручное восстановление старой копии policy DB требует отдельной сверки revoked grants; внешнего anti-rollback witness нет.

tools/assistant_demo.py соединяет все локальные компоненты с настоящими temporary SQLite, но synthetic Word/PPTX/identities/authentication/validator. ReportReader получает свежие links и policy на каждый запрос. Сценарий: review→persist→publish→bare progress→button→restart→own result; foreign/forwarded и revoked access denied. Отзыв сохраняется после создания новой session. Демо специально создаёт явно fake bindings только для namespace synthetic-assistant и временного каталога; этот bootstrap запрещено копировать в production. Synthetic PPTX ZIP timestamps сделаны стабильными для воспроизводимых content-bound revision IDs.

Добавлено23tests:8 registry,8 policy store,7 end-to-end. Первые запуски каждого нового модуля красные до реализации. Проверены restart/idempotence/immutable ownership/unique check, namespace/permissions/foreign DB/symlink, pending/corrupt/sanitized loader failures, full snapshot roundtrip/неподтверждённые bindings/CAS revoke/no fallback, durable page navigation и частичные сбои до/после link commit. Итог: **301 Python PASS +101 Node PASS** (Node64+37, оба запускались в этом этапе). Сквозной demo реально запущен локально; network запрещена отдельным test mock. Это не подтверждение Apps Script/Telegram/Google/Yandex/почты.

Команды: `python tools/assistant_demo.py`; `python tools/review_demo.py`; `python -m unittest discover -s tests -p 'test_*.py'`; `node tests/run-current.cjs`. Демонстрационный вывод: LOCAL_ASSISTANT_DEMO.md. Полное состояние и пределы: LOCAL_ASSISTANT_STATUS.md.

Остались real authentication adapters и trusted account enrollment/provisioning, server runtime/transport с безопасной отправкой и повторной авторизацией, live file bindings/валидатор критериев и semantic reviewer, test integration и согласованный rollout. Полный journal progress и grade write не подключены; numeric pass threshold не придуман. Никаких реальных API/писем/журнала/триггеров/deploy в этом этапе.

---

# Локальные кнопки /progress — 28.10.2026

PreparedReply получил immutable rows ReplyButton(label,callback_data): отдельная кнопка открытия каждой работы, назад/далее для страниц, возврат к списку из результата. Это только модель inline keyboard, не вызов Telegram API и не включённый processCallback_ рабочего GAS. Старые текстовые команды сохранены.

Callback ASCII ≤64bytes: progress:p:N для страницы, progress:o:REFERENCE для открытия. Reference — первые32hex SHA-256 digest исходной связи report/check/enrollment/student/discipline/group. Это не секрет/подпись/access token; lookup всегда повторно требует current self policy, read заново проверяет purpose/ownership. Смена связи в trusted registry делает старую reference неразрешимой; если digest совпал у нескольких связей, отказ, не первый match. Reference не включает права владельца и не разрешает открывать чужое при пересылке. Stable hash не является anonymization guarantee или rate limiter; private callbacks не логировать.

prepare_progress_callback допускает только две явные формы, не выполняет произвольные commands/roles/recipients. Каждый click заново готовит ответ через существующий policy-gated flow. Повторный click здесь read-only, не отправляет уведомление и не начисляет баллы. Перед реальным send/answerCallbackQuery будущий transport отдельно проверяет актуальные права/контекст, соблюдает private chat и formatting. Нет реального callback receipt/delivery/expiry/replay journal: это navigation references, не операции записи.

8 новых synthetic tests, первый запуск красный без callback implementation; полный Python **278 PASS**. Проверены own open/back, forwarded foreign denial, revoked binding, replaced check reference, malformed/overlong payload без чтения, self page navigation, forced collision rejection, Unicode longID callback bytes. Node не перезапускался (последний101 PASS), GAS не менялся. TG/почта/журнал/production не затронуты.

Следующий шаг — локальный сквозной сценарий request→page→button→report с настоящим внутренним хранилищем и synthetic identities; реальная интеграция/identity registry persistence/semantic grading остаются отдельно неподключёнными.

---

# /progress без ID и self-only страницы — 28.10.2026

В tools/report_access.py добавлен list_self: Student определяется только по действующему confirmed Context/Binding и progress.self; caller не задаёт student_id. Link registry неизменяемый и trusted, принадлежность enrollment сверяется текущей policy. Чужие links не загружаются и не входят в пагинацию. Порядок стабилен по opaque report id; по5своих links на страницу, page — целое1..1000000, не credential. Page numbers не гарантируют неизменный набор при замене registry; это не cursor snapshot.

В tools/report_requests.py bare `/progress` открывает первую страницу, `/progress page N` — указанную. Собственная работа открывается существующим `/progress REPORT_ID`. Страница показывает только краткие assignment/status и reference, без внутренних observations. Пустая страница явно пуста. Если payload собственного отчёта pending/corrupt/unavailable, показывается только подтверждённая self reference и «результат пока недоступен»; до этого и перед возвратом повторно проверяются актуальная self identity/права. Отзыв или rebind на другого студента во время чтения не возвращают прежнюю страницу. Teacher/group chat/unconfirmed/scopeless Context не получают student list. Общий list всех студентов не реализован.

10 новых tests, исходный запуск2fail/6error до реализации; полный Python **270 PASS**. Проверены bare command, foreign links без чтения/подсчёта, disjoint pages5+2, denied contexts, invalid page безpayload, revoke/rebind duringload, empty page, invalid identity parameters и own pending slot. Node не перезапускался (последний101 PASS, GAS не менялся). Никаких реальных Telegram updates, доставок, почты, записей Excel или deploy.

Это локальный кандидат обработчика, а не установленная команда рабочего бота. Перед transport send заново получать разрешённый ответ; PreparedReply не receipt и не cached authorization. Permanent identity/link storage, real TG authentication/transport, OAuth/email service и semantic grading остаются неподключёнными. Текущий список касается только локальных review reports, не полного ΣА/ΣТ/ΣДЗ учебного журнала.

---

# Подготовка локального ответа на запрос отчёта — 28.10.2026

tools/report_requests.py реализует только in-process команды `/progress REPORT_ID` и `/report REPORT_ID`, возвращающие PreparedReply. Это не включённые Telegram handler/webhook и не почтовая рассылка. Context/reader даёт trusted runtime, из текста извлекается только opaque report reference. Неверные команды/попытка передать дополнительные identity/role/recipient параметры не вызывают payload loader. `/progress` требует student self purpose, `/report` — teacher student.report; ReportReader получил необязательный purpose, который лишь сужает доступ и проверяется до/после load. Смена роли/отзыв во время запроса не разрешает незаметно сменить тип ответа.

Текст обычный: parse_mode=None и link_preview_disabled=True. Требования/наблюдения не интерпретируются как HTML/Markdown, управляющие/Bidi символы удаляются, длина ограничена3500 UTF-16 units (emoji учитываются), сокращение явно помечается. Заголовок всегда сообщает о необходимости проверки преподавателя; grade/credit не обещаются. Внутренние notes приходят только из teacher projection. Отказ одинаков для чужого/неизвестного отчёта. Повторная подготовка заново проверяет текущие права, не кеширует allow.

PreparedReply.status=prepared означает только локально подготовленный текст, не запись об отправке/успехAPI/доставку. Сохранённый текст не является credential: перед будущей отправкой transport должен заново подготовить ответ и сохранить явно указанные параметры форматирования. Email/ChatGPT adapters не реализованы. Актуальное дополнение ниже/выше реализует локальные bare `/progress` и self-only pagination; arbitrary student ID по-прежнему не принимается.

10 новых synthetic tests (первый запуск красный без модуля), полный Python **260 PASS**. Проверены self/teacher ответы, command purpose, чужой/unknown одинаковые ответы, revoke, invalid request без чтения, UTF-16/controls, plaintext markup, retry и downgrade during load. Node не перезапускался, GAS не менялся (последний101 PASS). Реальные сообщения/письма/API/журнал/deploy не выполнялись.

---
