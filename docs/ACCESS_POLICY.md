# Академическая identity и policy — локальная модель

Дата: 28.10.2026. Код: `tools/assistant_access.py`; синтетические тесты: `tests/test_assistant_access.py`. Никакие реальные аккаунты, адреса или IDs не подключены. Модуль не изменяет Apps Script-кандидат и не выполняет сетевых запросов/записей.

## Что реализовано

| Сущность | Назначение |
|---|---|
| Teacher / Student | Устойчивые строковые ID, точные сравнения без потери ведущих нулей, флаг действующего доступа; ФИО не является ключом и в модели не хранится |
| Binding | Подтверждённая сервером связь channel+subject → teacher/student, индивидуальные capabilities; по умолчанию confirmed=false |
| Enrollment | Студент, дисциплина, группа и интервал действия [from, until); неоднозначные пересекающиеся действующие Enrollment одной дисциплины отклоняются |
| TeachingGrant | Явные права преподавателя на точную пару дисциплина+группа с интервалом действия |
| AcademicReadGrant | Явный полный доступ к чтению академических данных проекта: расписания всех преподавателей и отчёты по всем известным Enrollment, включая историю; не глобальный owner |
| Lecture | Авторитетный session ID, назначенный преподаватель, группы, тип, время и статус; verified=false по умолчанию |
| SubstitutionGrant | Отдельное временное право конкретного преподавателя на конкретную lecture; не предоставляет обратного права, чтения чужих отчётов или личных данных |
| Context / Decision | Проверенный транспортом субъект/канал и минимальный результат allow/deny без отражения чужого ID/причины отсутствия записи |

Запрос принимает ID существующего серверного ресурса, а не произвольный объект с caller-provided teacher_id/group. Один channel+subject не может быть одновременно привязан к двум личностям/ролям. Неизвестные роли/действия, неактивные/неподтверждённые bindings, несуществующие записи, чужие/истёкшие права дают отказ. Snapshot, records и capabilities неизменяемы.

## Разрешения

- `schedule.read`: обычный преподаватель видит только своё расписание. Действующий AcademicReadGrant позволяет видеть расписание любого известного преподавателя проекта. Право замещения само по себе не даёт такого расширения.
- `student.report`: преподаватель читает отчёт конкретного действующего Enrollment только по своей дисциплине/группе. Общая группа доступна обоим лишь при двух явных grants. Обычные TeachingGrant не открывают закрытые/исторические Enrollment. По уточнению пользователя действующий AcademicReadGrant разрешает чтение всех известных академических Enrollment проекта, включая архивные/неактивные записи; отсутствие записи не подменяется данными.
- `progress.self`: студент читает только собственный ID при наличии действующего Enrollment. Эта проверка не вычисляет оценки и не извлекает записи книги; report service должен дополнительно ограничивать результат разрешёнными Enrollment.
- `personal.read`: только собственный Teacher ID и отдельная capability, которую второй преподаватель автоматически не получает. Глобальные owner-команды этим модулем не предоставляются.
- `lecture.open` / `lecture.code.read`: только private Telegram, текущая verified lecture со статусом confirmed; свой преподаватель или действующий session-specific substitution grant. `зач`, exam, practice, unknown type, cancelled и неподтверждённые занятия закрыты. Полное 90-секундное открытие должно помещаться и в паре, и в сроке замещения. `lecture.code.read` проверяет право, а наличие/срок конкретного окна проверит будущий window controller.

Ни одна capability не разрешает send/write/deploy. Права чтения отчёта для email не разрешают отправку. ChatGPT ограничен schedule.read / student.report / progress.self и пересечением OAuth scopes с серверными grants; даже широкий scope не даёт lecture.open, код лекции или personal.read. Неизвестный канал запрещён. Отказ одинаков для отсутствующего и чужого ресурса, чтобы не раскрывать существование студента.

## Граница доверия — обязательно для будущего подключения

**Это authorization policy, не authentication и не действующая система защиты endpoint.** Все records должны поступать из подтверждённого серверного реестра. В этом этапе реестра с долговременным хранением, admin-процедуры привязки и настоящих аккаунтов нет.

`Context(authenticated=True)` допустимо создавать только проверенному транспортному адаптеру после проверки отправителя/подписи, канала, OAuth issuer/audience/expiry/scopes либо другого согласованного механизма. Этот флаг сам по себе ничего не доказывает: JSON клиента, LLM arguments, текст письма, username или команда Telegram не могут конструировать Context, Binding или grants. Валидация email-адреса/письма, OAuth и Telegram здесь не реализована.

В private Telegram адаптер должен установить подтверждённый subject из transport identity; для callback/событий с отдельным sender проверить совпадение. Подставленное поле role модель Context вообще не принимает. Но отсутствие параметра role не заменяет криптографическую проверку транспорта.

Каждый запрос, повторный показ кода и отдача кешированного отчёта должны проверяться против **текущего** registry snapshot. Модель намеренно не кеширует решения и не выдаёт переиспользуемых токенов. Неизменяемый старый snapshot не узнаёт об отзыве самостоятельно: адаптер обязан загрузить актуальное состояние/ревизию, иначе обещание «отзыв действует со следующего запроса» не выполнено. Автоматического обновления snapshot и durable registry пока нет.

Готовый отчёт нужно минимизировать по разрешённому объекту; выдавать raw Workbook/Registry/все группы после одного allow нельзя. Вложения, письма и данные журналов не становятся доверенными инструкциями. Право администратора подтверждать роли/grants — отдельная серверная операция, которой в публичном API пока нет.

## Пример потока (проект интеграции, не запущенный endpoint)

1. Transport проверяет реальный запрос и создаёт Context, не принимая actor/role от пользователя.
2. Сервер читает актуальную версию identity registry и ресурса; конфликты/отсутствие подтверждения дают отказ.
3. `policy.authorize(context, action, target_id, now=aware_server_time)` проверяет доступ.
4. Report/controller повторно ограничивает данные/состояние операции и возвращает минимальный DTO; writer/sender требуют своих отдельных разрешений и журнала.

Пока шаги 1/2/4 не подключены, код нельзя рекламировать как включённый `/progress` или возможность открыть реальные lecture-коды.

## Проверки

```bash
python -m unittest discover -s tests -p 'test_assistant_access.py'
python -m unittest discover -s tests -p 'test_*.py'
node tests/run-current.cjs
```

Актуальный результат после уточнения полного академического чтения: **36/36 policy PASS**, **116/116 всего Python PASS** (64 НВГУ + 16 XLSX + 36 policy), **101/101 текущего Node candidate PASS**. Только вымышленные IDs, без сети/персональных данных. Начальные tests были красными до добавления модуля. Ещё четыре красных случая выявили: неоднозначные пересекающиеся Enrollment, замещение короче открываемого окна, невалидные request types и registry ID types. Исправлены и покрыты регрессиями. Дополнительно проверены отсутствие reverse grant, отсутствие report/personal расширения замещения, 90s boundary, точные ID, immutable snapshot, одинаковый отказ missing/foreign и канал/scopes.

Не проверялись реальные OAuth/Telegram/email, отозванные серверные credentials, актуальность registry cache в работающем сервисе, вычисление/отправка отчётов или журнал. Apps Script и кодовое окно пока не реализованы.

## Следующий пакет

Сначала controller лекционного окна на синтетических данных: криптографический код, 90 секунд, одно активное окно на session, lock/durable state, повторный запрос без продления, повторная проверка policy при показе/открытии, аудит фактического/назначенного преподавателя и rate limiting. Полный `/progress` требует подтверждённой карты Student/Enrollment → workbook cells и расчётов. Подключение каналов — отдельно, после серверной authentication/registry реализации и sandbox-приёмки. Безопасная запись XLSX не предполагается готовой.


## Уточнение полного доступа пользователя — 28.10.2026

По явному запросу пользователь получает проектное полное академическое чтение, включая расписание второго преподавателя и данные всех студентов. Локальная модель реализует это отдельным AcademicReadGrant, привязанным к подтверждённому Teacher, с интервалом действия и отзывом. Для реализации потребуются реальная подтверждённая привязка аккаунта и запись grant в trusted registry; они пока не созданы.

Full read не назначается автоматически второму преподавателю/студентам и не превращается в право записи журнала, отправки писем, доступа к чужим личным входящим/задачам или управления произвольной лекцией. Лекционное замещение продолжает проверяться отдельным SubstitutionGrant. Подтверждённые Binding/capabilities и ограничения каналов/scopes проверяются до полного чтения; отозванный/истёкший grant прекращает расширенный доступ. Это разрешение на учебные данные данного проекта, не доступ ко всему содержимому личного Диска/почтового ящика.

Добавлено 6 синтетических тестов: полное чтение чужого расписания/студенческого отчёта, отсутствие обратных прав, известные исторические записи, несуществующие IDs, запрет write/send/личных данных/кодовых полномочий через full read, сроки/revoke/auth, channel scopes/capabilities и валидация grant. Сначала запуск был красным до добавления AcademicReadGrant; затем все 36 policy/116 Python/101 Node PASS.

# Доступ к локальным отчётам — 28.10.2026

Добавлен tools/report_access.py: ReportReader использует существующую AccessPolicy и trusted ReportLink(report/check/enrollment/student/discipline/group). Link создаётся серверным registry, не из запроса студента. Текущий enrollment должен совпасть с исходной привязкой во всех четырёх полях; переиспользование enrollment ID не переносит чужой отчёт новому студенту. Policy/clock получают свежие значения перед чтением payload и после него. При отзыве/изменении binding/grant запрос блокируется или получает более ограниченную student projection. Нельзя кешировать решение allow как credential.

Студенту доступен только собственный report при действующем enrollment и progress.self; краткий ответ исключает evidence/internal reviewer notes. Преподаватель получает evidence/observations только при student.report для точной discipline/group либо явном full AcademicReadGrant. Full grant владельца включает известную историю, второй преподаватель автоматически его не получает. Unknown/missing/forbidden/corrupt/pending дают одинаковый Report unavailable без private деталей. Loader не вызывается до авторизации. Result check/material identity сверяется с trusted link/хранилищем, неожиданным полям нет выдачи. Выход — detached JSON projection, не ссылка на сохранённый dict.

Поддерживаются существующие channel policy: private confirmed Telegram, scope-bound отдельный ChatGPT context, confirmed email read. Это только разрешение на чтение, не отправка письма или реальный OAuth/TG endpoint. ReportReader не аутентифицирует пользователя; Context, links, policy provider, clock и loader — доверенные runtime adapters. Persistent links/identity registry ещё не реализованы. Повторная проверка уменьшает окно отзыва, но не является транзакцией между registry и отправкой; будущий transport обязан сверять права перед фактической отправкой и применять безопасное форматирование.

13 новых synthetic tests (первый запуск красный до модуля), полный Python **250 PASS**: self/foreign isolation, exact teaching grants, owner full read, revocation/rebind during load, reused enrollment, private/confirmed channel, ChatGPT scope, email read, historical restrictions, pending/version mismatch, detached output и sanitized failures. Node не перезапускался, GAS не менялся (последний101 PASS). Ни реальных student identities, ни выдачи данных, отправок, API calls или записи журнала нет.

| Риск | Защита | Проверка | Остаток |
|---|---|---|---|
| Чужой результат по report ID | current policy до payload | self/foreign и exact grants PASS | Нужен реальный authentication adapter |
| Отозванный доступ к кешу/отчёту | повторная policy перед ответом | revoke и downgrade during load PASS | Сверка перед transport send ещё не подключена |
| Enrollment перепривязан | immutable original relation + current equality | reused enrollment PASS | Нужен durable trusted link registry |
| Внутренние заметки студенту | отдельная минимальная projection | notes/evidence omitted PASS | Утверждённый формат обратной связи ещё не реализован |

Дальше — локальные обработчики запросов/рендеринг, затем защищённые реальные adapters в отдельной среде. Научная semantic evaluation/автопринятие/запись оценок остаются неподключёнными.

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
