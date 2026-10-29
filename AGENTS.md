# AGENTS.md — постоянные инструкции для Kulagina Telegram Assistant

## 1. Главный принцип и границы разрешения

Сохранять все работающие функции Telegram-ассистента Кулагиной Л. С. Изменять код минимально: небольшие понятные патчи, без переписывания проекта и необоснованного рефакторинга. Не расширять задачу незаметно для пользователя.

- До изменения изучить относящийся к задаче код, README.md, docs/REQUIREMENTS.md, актуальный раздел docs/AUDIT_REPORT.md и docs/TEST_PLAN.md.
- Сохранять существующие пользовательские изменения, исходные снимки, структуры данных и рабочие сценарии. Не выполнять reset, очистку данных или массовую замену файлов ради удобства.
- Разрешение на локальную разработку и тесты с моками не разрешает реальные отправки, чтение или изменение пользовательских данных, настройку Apps Script, публикацию и развёртывание.
- Реальные запросы Telegram/Google, триггеры, webhook, операции с таблицами, календарями, файлами и правами выполнять только в явно разрешённом объёме и на согласованных ресурсах. По умолчанию production не использовать как тестовую среду. Явное уточнение владельца29.10.2026 «можно тестить в моих» разрешает только ограниченные тесты на его ресурсах в объёме docs/CONSULTATION_PERSONAL_RESOURCES.md; не требовать повторно отдельные ресурсы. Рабочие записи/студенческие рассылки/poller/webhook/triggers/deploy этим не разрешены.
- До разрешённого изменения внешнего ресурса подготовить проверяемый результат локально. Предпочитать отдельные test resources, кроме явно разрешённого владельцем ограниченного теста на его ресурсах; предусмотреть резервирование и откат.
- Не считать наличие файла, успешный локальный тест или сохранённую конфигурацию подтверждением публикации, активных триггеров, реальной доставки или работоспособности production.

## 2. Основной проект и состояние компонентов

Рабочий кандидат для локальной разработки: src/telegram_assistant_v2_0_5_candidate.gs. Это не подтверждённая копия развёрнутого production-проекта.

Предыдущие версии — архивные снимки: src/archive/telegram_assistant_v1_4_3_reference.gs и кандидаты 2.0.2, 2.0.3, 2.0.4. Не удалять и не перезаписывать их. Не объединять несколько снимков в одном Apps Script project: у них одинаковые глобальные функции и CFG. Новый снимок создавать отдельно, если это требуется задачей; не менять активный entrypoint без объяснения.

Карта реализации:

| Компонент | Файлы / функции | Назначение и состояние |
|---|---|---|
| Telegram input | pollTelegramUpdates → processInboxItem_ → processMessage_ / processCallback_ | Опрос, долговременная очередь, проверка доступа и маршрутизация |
| Доступ | register_, accessStatus_, ownerApprove_, ownerRevoke_ | Регистрация и точный статус одобрения |
| Поручения / ответы | sendPendingTasks, chooseTask_, activeTasks_, storeFile_ | Выдача, выбор поручения, приём текста и вложений |
| Личные задачи / реестр | ownerAdd_, ownerDone_, syncGeneralTask_, updateGeneralTaskStatus_ | Основная запись и отдельная проекция задач; ошибки синхронизации требуют сверки |
| Отправки | tg_, send_, sendOnce_, deliverySheet_ | API transport и outbox; не все существующие отправки используют outbox |
| Консультации | consultationPolicy_, consultationAvailability_, studentRequestConsultation_, ownerApproveConsultation_, finishConsultationCancellation_ | Диалог, резерв, личное решение и отмена; реализованы в кандидате, не проверены на реальных API |
| Повторы / рассылки | generateRecurringAssignments, ownerConfirmRecurring_, ownerPrepareBroadcast_, ownerConfirmBroadcast_ | Правила, подтверждение, зафиксированная аудитория и результаты отправки |
| Напоминания / сводка | remindDeadlines, sendDailyBriefing | Сроки, календарь и личные задачи |
| НВГУ в Apps Script | fetchTimetable_, checkTimetable_, sendTimetablePage_ | Текстовый снимок и эвристика навигации; не равны проверенному Python parser |
| Проверенный разбор НВГУ | tools/nvsu_preview.py | Локальный HTML parser и read-only CLI, проверяющий выбранную дату/неделю |
| Модель синхронизации | tools/nvsu_sync.py | План обновлений и протокольная модель; Google transport — tools/nvsu_google.py, durable state — tools/nvsu_state.py |
| Локальное чтение XLSX | tools/gradebook_read.py | Только структура/кеши/даты локальной копии; raw cells приватны, CLI без значений, нет записи и академической identity |
| Локальная академическая policy | tools/assistant_access.py | Только authorization по trusted snapshot; два преподавателя, self-progress, session-specific замещение; нет реальной authentication/registry/transport |
| Локальные lecture windows | tools/lecture_windows.py | SQLite/AES-GCM, 90s/request recovery/local attendance; без Telegram/QR/real registry/XLSX sync; receipt not_synced |
| GitHub Actions Disk probe | .github/workflows/yandex-disk-read-check.yml, tools/yandex_disk_probe.py | Только manual metadata GET корня; secret остаётся в Actions, повторный metadata GET прошёл (run 40646446786); нет почты/записи/индексации |

Python parser/sync ещё не подключены к Apps Script. tools/nvsu_calendar.py готовит read-only план; Google-адаптер по умолчанию запрещает запись, tools/nvsu_state.py хранит SQLite ledger/checkpoints. Локальные HTTP-моки не подтверждают реальную Google-интеграцию. Не запускать execute_plan или подтверждение владения ручными событиями без соответствующего разрешения.

В репозитории не подтверждены deployment-манифест, OAuth scopes, фактические bindings и установленные в Google триггеры. Не придумывать отсутствующие настройки, endpoint, manifests или схему деплоя. Текущее состояние внешней среды устанавливать отдельно разрешёнными проверками.

## 3. Техническая карта ресурсов

Ниже перечислены существующие имена Script Properties из кода, а не их значения. Облачные переменные окружения не считать автоматически установленными Script Properties.

| Настройка | Ресурс / назначение |
|---|---|
| TELEGRAM_BOT_TOKEN | Токен согласованного бота; значение только в защищённых настройках |
| OWNER_CHAT_ID | Проверка владельца и адрес уведомлений; значение не сохранять в Git |
| ASSISTANT_SPREADSHEET_ID | Основная Google Таблица |
| ASSISTANT_DRIVE_FOLDER_ID | Явно выбранная закрытая папка вложений |
| ASSISTANT_CALENDAR_ID | Целевой календарь событий и консультаций |
| ASSISTANT_TEACHING_CALENDAR_ID | Отдельный проверенный полный источник занятий, если используется |
| ASSISTANT_CALENDAR_HAS_ALL_LESSONS | Только значение true разрешает использовать целевой Calendar как полный источник занятий; не включать без проверки полноты |
| ASSISTANT_REGISTRY_SPREADSHEET_ID | Отдельная книга общего реестра задач |
| ASSISTANT_REGISTRY_SHEET_NAME | Явное имя листа общего реестра |
| ASSISTANT_REGISTRY_HEADERS_JSON | Проверенный контракт девяти заголовков реестра |

В основной книге:

- Бизнес-листы: «Студенты», «Поручения», «Ответы», «Входящие», «Личные задачи», «Журнал бота», «Заявки на консультации», «Расписание НВГУ», «Рассылки», «Повторяющиеся поручения».
- Технические листы: «Очередь updates», «Исходящие операции», «Снимки операций», «Операции календаря», «Снимки расписания».
- Схемы задаются CFG.*Headers и заголовками технических функций. Код использует числовые индексы колонок; перестановка заголовков меняет смысл данных.
- Общий реестр — отдельная книга. Семантический порядок девяти полей: ID, направление, задача, статус, приоритет, срок, следующий шаг, контекст, обновлено. Фактические названия не угадывать. Ручной следующий шаг сохранять.
- Основная книга и общий реестр содержат разные проекции задач; без явного правила не вводить двустороннюю синхронизацию и не смешивать поручения студентов с личными задачами.

Состояние также хранится в Script Properties и CacheService: offset/retry-контекст, SELECTED_TASK_, CONSULT_DRAFT_, TIMETABLE_LINK_, markers файлов и кеш уведомления владельца. Не переносить эти состояния между разными ботами/ресурсами вслепую. Кеш не является долговременным доказательством отправки.

Реальные IDs, принадлежность ресурсов к production/sandbox и полнота календаря не следуют из имён настроек. Не подставлять ID из архивного кода и не печатать секреты для диагностики.

## 4. Триггеры и опасные операции

setupAutomation описывает следующие триггеры; их реальное наличие отдельно не подтверждено:

| Обработчик | Настройка в коде |
|---|---|
| pollTelegramUpdates | Каждую минуту |
| sendPendingTasks | Каждые 5 минут |
| sendDailyBriefing | Ежедневно, atHour(7) |
| checkTimetableTrigger | Ежедневно, около 07:30 |
| generateRecurringAssignments | Ежедневно, atHour(8) |
| remindDeadlines | Ежедневно, atHour(9) |

Часовой пояс: Asia/Yekaterinburg. Apps Script выбирает время внутри интервала; nearMinute не гарантирует точную минуту.

Не запускать без соответствующего разрешения:

- setupAutomation: вызывает initialize, удаляет webhook через deleteWebhook, удаляет/создаёт триггеры. Это не команда проверки готовности.
- initialize: создаёт листы, заголовки, меняет validation поручений и проверяет папку Drive.
- pollTelegramUpdates и replayDeadUpdate_: могут запустить все побочные действия обработчиков, включая отправки и записи Calendar/Sheets/Drive.
- sendPendingTasks, remindDeadlines, sendDailyBriefing, генерацию повторов и подтверждение рассылок: они изменяют данные или отправляют сообщения.
- Календарные create/update/delete, сохранение файлов, изменения sharing и Script Properties, миграции/очистку таблиц, публикацию и rollout.

Даже tab_, rows_ и log_ не считать строго read-only: они могут создать отсутствующий лист/заголовки или добавить запись. Не использовать их как безопасные production-пробы. Локальные тесты должны подменять все Google/Telegram-сервисы.

## 5. Расписание НВГУ и календарная синхронизация

Публичный источник: https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/3648

- В Calendar переносить только время начала/окончания, дисциплину и аудиторию. Никаких групп, потоков, типа занятия, ссылок и служебных описаний в видимом событии.
- В модели адаптера разрешены start/end/title/location. tools/nvsu_google.py переводит title в summary API; реальное подключение ещё не проверено. Технические event IDs и source references хранить в отдельном ledger.
- Одно занятие, повторённое для нескольких групп/потоков, объединять по времени, дисциплине и аудитории. Разные source IDs не означают разные реальные занятия.
- Проверять конкретную дату, выбранную неделю, преподавателя, HTTP-статус, структуру, полноту и свежесть ответа. Не подменять сбой загрузки пустым расписанием или старым актуальным снимком.
- «Расписание отсутствует» на проверенной странице нужной недели означает отсутствие занятий: новые события не добавлять. Это правило не распространяется на чужую неделю, неизвестную разметку или ошибку API.
- Повторный перенос должен сохранять event ID: неизменённое пропускать, изменённые время/дисциплину/кабинет обновлять. Не использовать изменяемое время или номер строки как единственную постоянную идентичность.
- Не удалять существующее событие без надёжной связи с синхронизатором, актуального полного источника и проверки области дат. Ручные события, чужие записи, ручные правки и заметки автоматически не удалять и не затирать.
- Неоднозначное соответствие, пересечение, смена source identity и изменение Calendar после preview требуют сверки; не создавать вероятный дубль ради завершения импорта.
- До реального импорта подготовить dry-run против тестового Calendar, проверить повторный запуск, durable ledger, сбои после принятого create/update/delete и конкурентные ручные правки. Отсутствие выгрузки Calendar/bindings не считать пустыми данными.
- Не придумывать HTML-селекторы или параметры недель. Использовать подтверждённое исследование и очищенные fixtures с provenance.
- Исследованный ICS содержит несколько недель, не имеет UID и повторяет многогрупповые занятия. Не импортировать его вслепую.
- Чтение публичного расписания допустимо в рамках задачи; служебные ссылки setlink/setvisit не вызывать как операции. Не отключать TLS/проверку артефактов для обхода ошибок.

Контракты и подтверждённая структура: docs/NVSU_SOURCE.md и docs/NVSU_SYNC_RULES.md. GAS-просмотр расписания пока расходится с Python parser; новые правила не считать автоматически подключёнными к боту.

## 6. Консультации

Согласованные правила: 20 минут, очно в кабинете 317, будни 09:00–18:00, обед 11:40–12:20, Asia/Yekaterinburg. Запись и самостоятельная отмена минимум за 30 минут; ровно 30 минут допускается. Праздники/отпуск и иные нерабочие дни требуют явных блокировок; отдельный производственный календарь не подключён.

- Календарь заполнен занятиями лишь частично. Пока импорт не завершён и не проверен, не считать свободный промежуток доказательством отсутствия пары и не включать ASSISTANT_CALENDAR_HAS_ALL_LESSONS=true.
- Не назначать консультации поверх занятий/других событий. Проверять весь интервал, all-day события, обед и повторно занятость перед записью/подтверждением.
- Меню: «Записаться», «Мои заявки», «Правила». Студент видит и отменяет только свои заявки. Личное решение принимает владелица.
- По явному решению владелицы после submit создаётся предварительное занятое событие «Ожидает подтверждения». Просмотр слота и ввод темы ещё не создают резерв. Предварительная запись не означает одобрения встречи.
- Подтверждение обновляет то же событие. Отказ/отмена удаляют только событие своей заявки с проверенной принадлежностью; обе стороны уведомляются через контролируемую отправку.
- Повторные нажатия, stale callbacks, replay темы и частичные сбои не должны создавать вторую заявку/встречу или превращать тему в ответ на поручение.
- Ассистент по расписанию читает тот же Calendar; скорость его синхронизации не проверена. Не обещать мгновенную реакцию другого сервиса или прочтение уведомления человеком.
- У предварительных резервов нет согласованного автоматического срока снятия. Не вводить срок/лимит заявок и не удалять их фоново без отдельного решения.

Сценарий и статусы: docs/CONSULTATIONS.md. Реальные календарные операции при разработке не выполнять без разрешения.

## 7. Telegram, поручения и идемпотентность

- Согласован будущий режим двух преподавателей: отдельные подтверждённые Telegram accounts, своё расписание и предметные права по дисциплинам/группам. Не назначать второго глобальным owner; личные задачи/входящие/чужие консультации изолированы. Сейчас 2.0.5 всё ещё имеет одного OWNER_CHAT_ID; локальное ядро tools/assistant_access.py реализовано, но real identity/transport/registry ещё не подключены. Контракт — docs/REQUIREMENTS.md, раздел F и docs/ACCESS_POLICY.md.
- По явному уточнению пользователя ему нужен полный академический read-access, включая расписание второго преподавателя и данные всех студентов/историю проекта. Реализован отдельный AcademicReadGrant; не распространять его на второго преподавателя/студентов и не путать с owner/write/send или личной почтой. Реальный account binding пока не подключён. Контракт — docs/REQUIREMENTS.md, раздел I.
- Academic Context создаётся только trusted authenticated adapter, не из JSON/LLM arguments. Grants берутся из актуального подтверждённого registry на каждый запрос: immutable старый snapshot не узнаёт о revoke автоматически. Локальная policy не является выданными реальными правами.
- lecture_windows.py требует явный 32-byte ключ из secure runtime и текущий trusted registry provider; не генерировать новый ключ взамен потерянного при restart. Private SQLite/WAL/аудит содержат личные IDs, не добавлять в Git. Student ID для register должен разрешаться сервером, не браться напрямую из формы. Public QR/auth/network limiter/XLSX sync ещё не готовы. Контракт — docs/LECTURE_WINDOWS.md.
- Коды лекций согласованы по запросу через Telegram обоим преподавателям; пользователю также доступно явное замещение второго преподавателя, без автоматического обратного права и без глобального owner. Серверное окно — 90 секунд по кнопке, одна активная регистрация на Session, `зач` исключён. Контракт — docs/REQUIREMENTS.md, раздел G; локальное ядро реализовано, transport/production не подключены.
- Точный статус «Одобрен» должен разрешать доступ; «Не одобрен», пустое/неизвестное значение и отозванный доступ — нет. Сравнивать ID как строки; не терять знак/ведущие символы через преобразование в число.
- Callback принимать только из private chat при совпадении from.id и chat ID и действующем доступе. Owner-only действия проверять явно. Истёкшая answerCallbackQuery не должна блокировать следующие updates.
- Связывать ответ с устойчивым ID поручения и адресатом, проверять статус и уникальность. Legacy task:<номер строки> и смешение ID/индекса остаются риском; не расширять эту схему и не считать её исправленной.
- Обеспечивать дедупликацию updates, команд, ответов, файлов, рассылок, резервов и повторных запусков. Сохранять payload/стадию/попытки до продвижения offset, ограничивать retries, предусматривать DEAD/replay.
- Различать намерение/запись об отправке, успешный ответ Telegram API с message_id, фактическую доставку и прочтение. Статус «Отправлено» не доказывает прочтение и не является отдельным подтверждением фактической доставки клиенту.
- Не считать любой send_ защищённым от дублей: часть напоминаний/сводок/уведомлений обходит outbox, а кеш уведомлений временный. Сбой первого уведомления не должен лишать второго адресата уведомления; учитывать этот существующий риск.
- UNKNOWN/SENDING без подтверждённого результата не сбрасывать в READY/«Не отправлено» вслепую. Не обещать exactly-once там, где внешний API его не гарантирует.
- Сохранять контроль длины сообщения, per-recipient результаты, аудиторию рассылки и обработку API errors/429. Не отключать проверки, чтобы тест стал зелёным.
- Справка, пасхалки и диалоги не должны перехватывать рабочие ответы. Меню/help и маршрутизатор должны описывать одни и те же реально доступные действия; известное расхождение студенческого /faq не считать устранённым без правки и теста.

## 8. Данные и восстановление

- Сохранять существующие заголовки, порядок колонок и статусы. Новые поля/статусы — через явный контракт, проверку validation, совместимость, резервную копию и план миграции. Не делать слепую миграцию рабочих данных.
- Ошибку схемы или неоднозначный ID считать причиной остановки/сверки, а не поводом выбрать первую строку. Не допускать формул Sheets из пользовательского текста.
- Для файлов использовать явную закрытую папку и постоянный ключ. Не включать публичный sharing, не менять существующие права автоматически; проверить наследуемый доступ и фактический размер.
- Поддерживать частичное восстановление по стадиям, а не одному конечному статусу. Учитывать отсутствие общей транзакции между Sheets, Drive, Calendar и Telegram.
- Сохранять смысл операций очереди PENDING/PROCESSING/RETRY/DONE/DEAD, отправок READY/SENDING/SENT/UNKNOWN/SKIPPED и календарных CREATING/CREATED. Не менять значения или markers без анализа всех читателей.
- Для консультаций учитывать промежуточные состояния создания/отмены/отказа и конечные состояния заявки. Не объявлять неопределённую операцию успешно завершённой.
- replayDeadUpdate_ и ручное восстановление разрешены только после сверки частичных side effects и с сохранённым payload. Не перематывать offset, не удалять ledger/markers и не запускать повторную отправку без обоснования.
- Технические payload, темы, файлы и логи содержат персональные данные. Не переносить их в Git/fixtures, не очищать без retention/recovery-политики. Контролировать рост листов, Properties/Cache и квоты.
- Не записывать секреты, реальные значения OWNER_CHAT_ID, OAuth/cookie, токены и приватные ссылки в исходники, Git, отчёты и тестовые данные. Не печатать полный environment, Script Properties или credential files. Проверять имена/наличие, редактировать секретные данные в сообщениях ошибок.

## 9. Проверки и критерии готовности

Из корня репозитория:

~~~sh
# Текущий кандидат 2.0.5: сохранённые сценарии и консультации
node tests/run-current.cjs

# Python: НВГУ/XLSX/policy/lecture windows; cryptography из requirements-lecture.txt
python -m unittest discover -s tests -p 'test_*.py'

# История: по умолчанию regression.cjs проверяет 2.0.4
node --test tests/regression.cjs

# История: воспроизводит дефекты 1.4.3/2.0.2
node tests/audit.cjs
~~~

- Не путать исторические PASS с исправлением текущего кандидата. Runner явно выбирает 2.0.5; отдельные старые ожидания заменены согласованной политикой консультаций, а не отключены ради зелёного результата.
- Локальные зависимости: Node.js с built-in test runner; Python со стандартной библиотекой и timezone data для zoneinfo. Для Google transport: requirements-calendar.txt. Полный Python suite также требует cryptography из requirements-lecture.txt; НВГУ/XLSX/policy сами используют stdlib, Google SDK для offline suite не нужен. Не придумывать package manifests, версии-пины или deployment-настройки, которых нет в проекте.
- Для исправления сначала добавить падающий тест, затем минимальную правку. Проверять положительный путь, ошибки, пустые/неверные данные, роли, границы времени, повторную доставку и сбой между внешним действием и checkpoint. Не создавать тривиальные тесты, повторяющие реализацию.
- Использовать tests/helpers/apps-script.cjs, tests/consultations.cjs, существующие regression cases и очищенные tests/fixtures/nvsu с provenance. Моки не должны обращаться к реальным API или использовать настоящие секреты.
- Проверять весь требуемый набор и реальный exit status; различать PASS/FAIL/skipped/unrun, выбранный target и число выполненных тестов. Не складывать пересекающиеся исторические suites в число уникальных проверок.
- Для изменения только инструкций проверить содержание и diff; не заявлять о запуске тестов, если они не запускались. Не создавать лишние файлы или правки вне разрешённого объёма.
- Локальный VM/MemoryCalendar не доказывает GAS compatibility, OAuth scopes, права, квоты, консистентность API, работу триггеров или реальную доставку. Проверки внешних интеграций проводить отдельно на разрешённой sandbox.
- Production rollout не автоматизировать в рамках обычной разработки: отдельное разрешение, подтверждённые проверки, backup и rollback.

## 10. Отчётность и последовательность работы

После изменений кратко сообщить:

1. Какие файлы/функции изменены и какое поведение получилось.
2. Какие команды и тесты реально выполнены, их target и результат.
3. Что не проверялось локально и требует разрешённой интеграционной среды.
4. Какие риски/блокеры остались и какое конкретное действие пользователя нужно, если оно необходимо.

Поддерживать актуальные требования и отчёт по объёму задачи, явно отделяя новые результаты от исторических разделов. Основные справочники: docs/REQUIREMENTS.md, docs/AUDIT_REPORT.md, docs/TEST_PLAN.md, docs/CONSULTATIONS.md, docs/NVSU_SOURCE.md, docs/NVSU_SYNC_RULES.md и CHANGELOG.md.

Последовательность: инвентаризация → воспроизводимый тест → минимальное исправление → локальные проверки → разрешённая sandbox-приёмка → отдельно согласованный rollout. Двигаться самостоятельно внутри разрешённой задачи; если нужен внешний доступ или решение владельца, завершить независимую работу и назвать точный блокер. При явно ограниченном объёме менять только разрешённые файлы/ресурсы.


## 11. Проверка Яндекс Диска без публикации среды

По запросу пользователя разрешена ручная проверка read-only metadata через GitHub Actions с repository Secret YANDEX_DISK_TOKEN. Workflow только workflow_dispatch, timeout 2 минуты, без cron/автозапусков/печати секретов/списка файлов. Не переносить secret в Codex и не извлекать через логи. Если API401/403 или secret unavailable — сначала диагноз/значимое изменение, не повторять неизменный запуск. Первый run вернул HTTP401; после изменения секрета повторный run 40646446786 дал read_verified. Подтверждено только чтение metadata type корня, не почта/конкретные учебные файлы/полный набор scopes (docs/YANDEX_CONNECTION.md). Это не разрешение на письма, upload/XLSX write, произвольные downloads или deployment. При изменении workflow сохранять fixed endpoint, redirect refusal, минимальные permissions и no secret output.


После отдельного разрешения пользователя добавлен manual metadata inventory yandex-resource-inventory.yml: bounded spreadsheet-name scan и проверка type согласованной папки, без names/paths в выводе, downloads/writes. Real run 40647021089: папка доступна, журнал по загруженному имени не найден; нужно уточнение. Не делать журнал публичным и не повторять тот же scan без новых сведений. Учётные данные/приватные пути и книги не записывать в Git. Контракт/результаты — docs/YANDEX_CONNECTION.md.


Пользователь уточнил источник: журнал находится в той же согласованной общей папке материалов. Direct public metadata GET подтвердил единственный XLSX с совпадающими размером/MD5 загруженной копии и 5 DOCX, no subfolders. Новый remote content не скачивался. Не повторять вопрос о расположении и не трактовать прежний personal-files not_found как отсутствие этой книги. Sharing/перенос не менять: журнал в общей папке требует отдельного решения о закрытом хранении перед production. Приватные пути/hash и назначения DOCX не придумывать/не публиковать; подробности docs/YANDEX_CONNECTION.md.


Материалы: docs/MATERIALS_CATALOG.md, 4/5 DOCX прочитаны; M04 получен загрузкой пользователя, M02 исключён пользователем из обязательных источников. Старые >60/минимум отработок/удаление писем не отменяют новое ТЗ >56/все обязательные лекции/read-only почты. Не оценивать реальные работы автоматически и не путать practice задания с lecture makeup. Одно письмо может содержать несколько работ, неоднозначность — review. Raw DOCX/контакты/приглашения не переносить в Git.


Пользователь загрузил M04 lecture makeup; он прочитан, M02 (вопросы) исключён из обязательных источников, не запрашивать его снова. Mapping прямо подтверждён: №ДЗ1→Л1, 2→Л2, 3→Л3, 4→Л4, несмотря на широту тем. M04 comic разрешает ИИ-графику с доработкой; rubric weights не дают проходного порога. Обновления файлов должны учитываться в новых проверках с версией source/rubric/parser; pending source drift → needs_recheck, completed results не менять автоматически, source errors без stale fallback. Локальное ядро tools/material_versions.py реализовано (14 tests), но live watcher/DOCX parser/grader/плюс не подключены. Контракты docs/MATERIAL_VERSIONS.md и MATERIALS_CATALOG.md §5; private .materials-state не переносить в Git.


Локальный `tools/material_docx.py` извлекает untrusted текст/таблицы (11 tests; полный Python179). Каждый результат criteria-not-validated; не конвертировать его автоматически в утверждённый rubric/MaterialRead. Review flags означают потенциально неполное извлечение, не пустые требования. Сеть/внешние ссылки/содержимое embedded objects не исполняются. Live refresh и semantic rubric extraction остаются неподключёнными.


`tools/material_source.py` — read-only public DOCX adapter, explicit resource only, metadata/hash before-after, no cache/token/writes. 8 offline tests, полный Python187 PASS. Не запускать как scan/downloader произвольной папки; не добавлять XLSX, секреты или signed URLs в логи. Live binding и semantic rubric validator не подключены; read bytes не означает утверждённые criteria.


`tools/material_pipeline.py` связывает source/Word/trusted validator с MaterialCatalog (10 новых tests; полныйPython202). Не считать ValidatedRubrics семантическим доказательством: validator — trusted application code, без default approval; требуется связь с текущим SHA/parser и review flags. Производственный validator/grader отсутствует. Не подменять его сырым текстом Word, callback из документа или старым approval. SQL schema/GAS не менялись.


`tools/material_drafts.py` — unapproved numbered section drafts с точными paragraph indices и исходным текстом, без threshold/оценки. 5tests, M04 local upload успешно дал 4sections; это не live freshness или автоматическое утверждение rubric. Не превращать draft в validated approval автоматически. Пользователь разрешил продолжать независимую разработку без промежуточных подтверждений; решения о неуказанном проходном пороге и разрешения на реальные внешние действия остаются отдельными.


`tools/assignment_review.py` — PPTX structural pilot (14tests, полныйPython216). Проверяет только explicitly configured minimum slides через manifest/relationships; threshold/index должен задавать trusted validator, не студент. Любой report.status=needs_teacher_review, storage done не означает принятие/grade/credit. Не трактовать 40слайдов как качественную работу или slide count как число кадров комикса. Presentation content не исполнять/не отправлять внешним сервисам; исходники/real students не включать в Git.


Текущее правило assignment_review: minimum/index только из plan.rules.structural_checks (один slide_count criterion), runtime args лишь проверяются на совпадение; старые rules без machine criterion требуют review. Нельзя подставлять default40 или override1. material_criteria выдаёт source-bound suggestion с quote/paragraph index, всегда requires_review; не использовать как автоматическое approved rubric. Новые10tests, полныйPython226 PASS; M04 local40 подтверждён только для upload. Форматы Sheets/SQLite не менялись.


content_evidence.py проверяет source-bound Finding/Citation и exact quote offsets, не генерирует и не подтверждает научную правильность (9tests, полныйPython237). Observation status всегда needs_review; нельзя превращать supported в принятый ДЗ или переписывать им structural status. Quotes/comments приватны, выдача требует academic policy. Semantic evaluator и внешние сервисы не подключены.


report_access.py выдаёт только policy-gated projections (13tests, полныйPython250). ReportLink и Context создаёт trusted server registry/authadapter, не Telegram text/LLM/request payload. Проверять current policy перед payload и после него, final send отдельно; student projection без internal notes/evidence. Unknown/denied одинаковы. Ни registry persistence, ни authentication/real transports модуль не реализует. Не обходить ReportReader прямым MaterialCatalog.result в публичном endpoint.


report_requests.py — локальная подготовка /progress REPORT_ID и /report REPORT_ID (10tests, полныйPython260), не реальные bot handlers/send. purpose ReportReader только сужает права; source text не задаёт role/identity/recipient. PreparedReply не credential/receipt: перед send заново проверять policy, parse_mode=None, link previews disabled; не печатать private text в логи. Локальные resolver/pagination добавлены ниже; real transport остаётся неподключённым.


Bare /progress и page N реализованы локально через list_self (10tests, полныйPython270). Student берётся только из current authenticated binding/progress.self, не command args. Чужие links не читаются/не считаются; current self/ownership перепроверяются перед возвратом. Собственный unavailable slot безpayload допустим только после такой проверки. Это список local review reports, не полный journal progress и не включённый Telegram handler.


Локальные progress buttons/callbacks добавлены в PreparedReply/report_requests (8tests, полныйPython278). ASCII reference≤64bytes не credential: always current self lookup/read, forged/foreign/revoked/ambiguous refs deny. Не переносить callback как authorization cache и не трактовать повторный read как send/receipt. Реальный TG callback adapter/answerCallbackQuery отсутствует; source GAS не менялся.


Актуально: report_registry.py хранит private immutable ownership links; policy_store.py — versioned AccessPolicy с expected_revision CAS, no older fallback/automatic roles (23 новыхtests вместе с demo, полныйPython301/Node101 PASS). Только trusted ingestion/admin code может публиковать links/policy; не загружать их из student/LLM payload. assistant_demo.py — strictly synthetic bootstrap в temporary DB, не production authentication/provisioning. Runtime каждый request берёт current links/policy; WAL/backups нескольких DB требуют согласованного восстановления, особенно revoked grants. Контракт LOCAL_ASSISTANT_STATUS.md.


telegram_report_adapter.py — only trusted verified polling input parser (11tests+1integrated;Python313). fetch_verified_updates должен быть server-side authenticated/TLS Bot API transport; JSON ok/result не доказывает origin. Не принимать public body/LLM args/unverified webhook как verified input. Только numeric private from/chat, current confirmed binding; callbacks message от configured bot. Реальные HTTP/offset/ack/outbox/sends не реализованы, repeated prepare не delivery dedupe. Numeric subjects103/104/101 в assistant_demo исключительно fake; не переносить в production.


telegram_http.py и report_dispatch.py реализованы mock-only (41tests всего с inbox/integration,Python354). Network/writes/dispatch default off; flags не разрешение на реальные ресурсы. Verify configured bot, fixed HTTPS/no redirects, не логировать request URLs/токены/HTTP traces. Fresh local preparation перед durable claim/send; api_confirmed не delivery, unknown/inflight не повторять вслепую. Durable inbox/cursor/ack реализован в telegram_inbox.py и проверен только моками; реальный getUpdates не запускать без отдельной sandbox-приёмки/разрешения, не совмещать с действующим poller. Под claim lock нельзя выполнять сетевой polling; prepare_fresh читает verified local inbox/current policy. Контракт TELEGRAM_TRANSPORT.md.


telegram_inbox.py сохраняет всю verified batch+cursor атомарно до ack, включая неизвестные update types; source ack не означает processing/delivery. Same-bot/CAS/hash checks обязательны; не брать cursor из текущего max processed. Низкие IDs не считать автоматически reset; retention/idle reset/failover и восстановление backup требуют сверки. ПолныйPython354/Node101 PASS, реальных API/отправок не было.


report_worker.py — bounded reports-only queue step (10tests, итого51новыйtest блока/Python364+Node101). Default dispatch off; bot+project namespace должны совпадать. Recover existing receipt без private reread/send; unknown/rejected → blocked, unsupported → deferred/pending для других функций. Не использовать как замену всему боту: нужен общий dispatcher/backoff/monitoring/operator recovery; callback ack не реализован. Реальных transport API/deploy не было.


/decisions реализован локально в decision_queue/sources/requests (34tests+2worker regressions;Python400/Node101). personal.read на configured owner до/после source reads, reviews ещё student.report+original relation. Источники только trusted local snapshots; ConsultationBatch обязан сохранять true observed_at/complete, не time-of-click. Никаких approve/reject/grade/send/retry/hide действий из очереди. Worker/adapter decision factory optional; без неё route не активируется. Active inflight не считать failure/orphan автоматически и не блокировать работу peer: остаётся pending, monitor proof нужен отдельно. Existing Sheets/GAS/immutable report history не менялись; контракт DECISION_QUEUE.md.


consultation_actions/requests/demo.py — offline SQLite sandbox plans only (30tests). preview/confirm/cancel пишут локальные intents/plans; НЕ вызывать из read-only ReportWorker prepare_fresh или sender retry. Не считать локальную смену статуса исполненной Calendar/Sheet операцией. Ни real executor, ни live dispatcher, ни student agreement on proposed time нет. Весь store только trusted synthetic fixtures; reference не authorization. Контракт docs/CONSULTATION_ACTIONS.md; real execution требует отдельного разрешения и claim/reconcile защиты от частичных сбоев.


consultation_feed.py и src/tools/consultation_snapshot_export.gs — read-only candidate (29Python+9Node новыхtests,459Python/110Node полныйPASS). Exporter не установлен: не запускать на real Sheets без разрешения, результат приватен, без Logger/public endpoint/Git. Точные11headers/current GAS не менять; JSON decoder не authentication. BusyFeed требует explicit trusted TeachingVerification, сам не выдаёт proof полноты НВГУ; demo verification fake. HoldBinding только проверенный ledger, не title/description. Row revision/source_version включает адресата/eventID, stale queue refs deny. require_revision не Google CAS. Контракт docs/CONSULTATION_FEED.md; live source collection/auth/verifier/dispatcher/executor остаются отдельно.


consultation_worker.py — отдельный LOCAL action dispatcher (24новыхtests,483Python/110Node полныйPASS). ConsultationActions.process_update atomic status/intent/plan/private reply receipt через nested SAVEPOINT, action_updates additive migration только synthetic store; bot binding immutable/explicit для worker. Никаких network/внешних side effects внутри process callback/транзакции. DispatchLedger fresh callback только read-only owner gate/cached reply, не handler. api_confirmed здесь про UI response, plan remains not_executed; notification intents не sends. Defaults off; real runtime/executor/auth/source verifier/CAS/orphan recovery всё ещё отдельно. Контракт docs/CONSULTATION_WORKER.md.


consultation_executor/calendar/execution_demo.py — отдельный Calendar-stage candidate (38новыхPython,521Python/110Node PASS). Defaults off, все вызовы mock-only; existing GoogleCalendarAdapter transport. BoundPlan только trusted original consent/source/event evidence, не auto-upgrade старых plans/не public payload. Durable claim перед PATCH/DELETE, If-Match; no create/no time rewrite/no retry unknown/inflight. reconcile readonly по marker/postcondition/absence (не attribution API). source_status=not_written,notifications=not_sent всегда; source CAS/writer coordination/live bridge/finalization/notifications/template/приёмка отсутствуют, live use запрещён. Контракт docs/CONSULTATION_EXECUTOR.md.


consultation_workflow.py — LOCAL SQLite fixture CAS/claim/finalization/business outbox (27новыхtests,548Python/110Node PASS). Не Google Sheet adapter/real lock, не импортировать рабочие данные. Stage evidence только executor journal; atomic status/reason+2jobs, no Calendar in notice/source transaction. Notice business keys не update IDs, current same-entity/row gates; unknown/inflight/rejected no retry; per-recipient failure independent. Defaults off. Real consent/live CAS/writer coordination/verifier/rollout и future cancellations/operator recovery всё ещё отдельно. Контракт docs/CONSULTATION_WORKFLOW.md.


consultation_consent.py/bound_worker.py — LOCAL original review→owner confirm→BoundPlan/source claim (24новыхtests,572Python/110Node PASS). Evidence фиксируется до click, не auto-promote старые планы/не refresh consent time на retry. Calendar reads вне всех SQLite locks; UI fresh callback read-only. Registry view/token приватны, loader trusted-only. workflow_reviews additive, source nested SAVEPOINT; core/source partial publication требует original-evidence recovery, expired orphan не исполняется/не удаляется сам. Bound/unbound workers не запускать как competing consumer тех же routes. Legacy proposals остаются local без переноса, все flags off; live boundaries сохраняются. docs/CONSULTATION_CONSENT.md.


Safe legacy description fix: exact source-bound current GAS bot prefix меняется, suffix/marker/ручные notes сохраняются; unknown pending phrase/template → deny approve/review. Optional description patched fields входят в reconcile.5новыхtests,577Python/110Node PASS,6offline demos. Bound workflow demo использует synthetic inbox/consent registry, не handwritten consent. Следующий real resource выбор/объём только по docs/CONSULTATION_SANDBOX_ACCEPTANCE.md; реальные token/IDs не в чат/Git, никакого implicit permission из общих +/«продолжай». Working resources untouched, real Sheets CAS/import/writer coordination остаются.


29.10.2026: User разрешил «можно тестить в моих». Текущий read-only probe src/tools/consultation_connection_probe.gs — standalone, existing Script Properties only, getMe+explicit Calendar metadata, no events/poll/send.10Node VM tests,577Python/120Node полныйPASS; real probe не запущен. Из этого чата bot token отсутствует, ready Google identity не подтверждён (selectors есть, connections=[]); не брать значения из архивов/secret files. Manual showKulaginaConnectionProbe logs only safe JSON, не требовать cloud publication/передачи token. docs/CONSULTATION_PERSONAL_RESOURCES.md; реальные student/data writes/deploy по-прежнему не разрешены.


29.10.2026 user-run metadata JSON реально подтвердил getMe/explicit Calendar metadata/timezone (12:30:08), no writes/sends/poll; не приписывать это Codex direct connection или delivery/full timetable/deployment. consultation_owner_message_probe.gs — one generic OWNER_CHAT_ID message candidate, yet unexecuted live; separate durable KULAGINA_OWNER_MESSAGE_PROBE_V1 claim before HTTP, short locks not around network, no retry unknown/rejected/target change. Не сбрасывать receipt/не отправлять студентам/не менять рабочие settings.10Node tests,577Python/130Node PASS; docs/CONSULTATION_PERSONAL_RESOURCES.md.


29.10.2026 user сообщил api_confirmed owner probe12:57:58 и отдельно подтвердил receipt («да»). Proof только одного сообщения, API deliverednull не менять, не делать общий delivery/auth/deployment вывод. Следующий consultation_calendar_preview.gs GET-only existing Apps Script OAuth/Calendar REST, no secret/ID/event text output/writes/props/poll.20min TEST-only weekday slot/30min lead послеread, unread page not empty; no teaching completeness.10Node tests,577Python/140Node PASS. Actual REST preview ещё не выполнен; ждать sanitized JSON, не запрашивать заново owner-test permission/отправку. docs/CONSULTATION_PERSONAL_RESOURCES.md.


29.10.2026 user Calendar REST preview succeeded13:21:43 after API enable:30Oct10:00–10:20+05,busy0,no writes. consultation_calendar_smoke.gs prepared NOT executed live: exact-window one TEST create/PATCH/DELETE, stable eventID/private marker/durable KULAGINA_CALENDAR_TEST_V1 applying phases, owner-role/fresh busy guard, If-Match/ack ETag. No date fallback/forced cleanup/manual notes overwrite/no retry unknown/reset receipt. inspectKulaginaCalendarTest GET-only exact ID/no mutation.11Node tests,577Python/151Node PASS. No student/Sheet/poll/triggers/deploy; actual CRUD awaits user log. docs/CONSULTATION_PERSONAL_RESOURCES.md.


## Read-only private Calendar comparison — 29.10.2026

User-run CRUD complete/cleanup confirmed: не повторять smoke и не сбрасывать receipt. Новый nvsu_calendar_snapshot.gs только GET фиксированной недели02–08.11, не executed live. Частный chunked log содержит time/hash equality, не считать анонимным/не Git. nvsu_private_snapshot.py использует текущий plan_sync только для агрегатов, не реального ledger/ownership; всегда ready_for_apply=false/teaching_schedule_verified=false. Не преобразовывать hashes в real IDs и snapshot counts в исполнимый план. Unknown/moved/protected события требуют review. Доверенные источник/дата/полнота/реальный ledger устанавливаются отдельно. Новый suite включён в tools/check-local.sh;587Python/160Node PASS,6demos. Инструкция docs/NVSU_PRIVATE_COMPARISON.md.


## Реальная недельная сверка — 29.10.2026

User snapshot02–08.11 accepted:2chunks checksum valid; freshNVSU11/source vs11/events exact time/title/room,missing0,duplicate exact0,unknown0. Все protected: review_overlap не считать отсутствующим занятием/ошибкой и не снимать защиту. nvsu_private_snapshot теперь имеет separate exact/protected/missing/duplicate aggregate counts,3regressions/590Python+160Node PASS. No Calendar writes/ownership/full teaching verification; screenshot/manual snapshot не direct Google connection. Не повторять выполненный экспорт без свежей необходимости, не Git private artifacts. Remaining: other relevant weeks/ownership ledger/coordinated live updates. docs/NVSU_PRIVATE_COMPARISON.md.


## Protection diagnosis candidate — 29.10.2026

nvsu_calendar_protection.gs / inspectKulaginaNvsuProtectionReadOnly — standalone GET-only fixed02–08.11 aggregate reasons,not executed live. No event text/IDs/extension contents/sends/writes/settings. Reasons mirror previous snapshot flag, not ownership, counts overlap and empty arrays/objects may protect. Do not auto-adopt plain events or strip metadata to bypass protection.8newNode tests/full590Python168Node PASS,6demos. Existing verified11exact snapshot unchanged; next manual aggregate only, no repeatCRUD/chunks. docs/NVSU_PRIVATE_COMPARISON.md.


## Four-week November snapshot — 29.10.2026

Protection diagnosis received complete: attendees-field11/description5, no writes/ownership proof. Не повторять эту диагностику. Существующий nvsu_calendar_snapshot.gs расширен новым exportKulaginaNvsuNovemberReadOnly через тот же internal collector; old weekly entrypoint сохранён. Fixed02–29Nov,4weeks/one buffered batch/24GET/200total events; allfail/no partial chunks on incompleteweek/targetchange/limits. Новая Calendar-проверка не executed live. Pythonbatch comparator delegates to old planner, не ownership/writepermission/full semester proof; Nov30outside. Freshpublicsource11/9/9/0, last explicit no schedule не deletion authority.1newPython4newNode/full591Python172Node PASS6demos. Пользователь заменяет только свой вспомогательный файл экспорта, не основнойбот/не duplicateglobals. docs/NVSU_PRIVATE_COMPARISON.md.


## Clasp backup preparation — 29.10.2026

User approved preparing backup connection; Windows device. tools/clasp pins3.4.1; prepare-backup.cjs local-only creates fresh private config/readonly bootstrap and prints explicit login/pull commands, no OAuth/remoteIO. WindowsACL mocked/no realWindowslogin. Readonly scope builder verified offline; no broaddefault/includeextras/ADC. Never push partialhelper set: updateContent replacesprojectfiles; triggers can run changedcode without deployment. No Google auth/sourcebackup/directCodex connection yet; Windowslogin stays local. Authfiles/privateprojectconfig/working source outsideGit; no credentialuploads/callbacks inchat.6Node/full591Python178Node PASS6demos. Latestmanualsnapshot weekly02–08.11again/11exact; not fourweekbatch. docs/APPS_SCRIPT_CONNECTION.md.


## Windows backup received as report — 29.10.2026

User reported custom Desktop OAuth success then Pulled8files (manifest+main+6helpers). Standard OAuth client had been blocked; ownclient used, no security-policy bypass. Files remain user-local, not in Codex; no inspectedsource/deploymentversion/independent grants orACL evidence. Do not replay successfullogin/pull or overwritebackup; credentials/clientsecret/callbacks/IDs notGit/chat. Need private mainsource+manifest copies for firstdiff, redacthardcodedsecrets in separatecopies only. No implicitpushauthorization; fullproject/helperreview stillrequired. Docs only/last591Python178Node PASS6demos not rerun. docs/APPS_SCRIPT_CONNECTION.md.


## Uploaded main source reviewed — 29.10.2026

Actualuploadedmain445lines/37functions differsarchive1.4.3onlyversionheader and unguardedcallback ACK;36functionblocksidentical. Mockreproducednegativeapproval/expiredcallbackblocking; candidate2.0.5fixes,101NodecandidatePASS.5baseheadersmatch butresourceconfig changes. UploadedmanifestV8/AsiaYekaterinburg/Calendarv3alias known; not proof of deployment or existingendpoint.6helperscontents stillmissing, nofullprojectcollisioncheck. No copiedrawsource/hardcodedresourceID inGit. Preferminimalcompatiblepatchfirst; nofull2.0.5push orarchive merge/bootstrapmanifestupload. docs/APPS_SCRIPT_SOURCE_REVIEW.md.


## Complete helper review/minimal legacy candidate — 29.10.2026

All8uploadfiles reviewed/49globals/no collisions. Novemberexport exists already; no helpercopyneeded, monthlyexecutionstillpending. Sourcevalidationshashes only inGit, rawsource/IDs private. tools/clasp/prepare-legacy-candidate.cjs builds fresh private8file candidate with2changes(accessStatus_ exactapproval/callbackACK),7filesbytepreserved; fullactualuploadsetverified offline. ExpectedpinhashesCLIhardcoded; mismatch/unknownfiles/symlinks/collisions/syntax failclosed; no auth/targetconfig copying, noremoteIO/ready_for_pushfalse. SharedcreatePrivateDirectory inprepare-backup.cjs preservesACL guards.9newNode/full591Python187Node PASS6demos; actualprobe10PASS extra. Candidate2.0.5unchanged, no productionpush/deploy/writeOAuthgrant; newlegacyWindowsbuildernotyetuserexecuted. Partialoutputerrorstop/noretryoverexisting, originalbackupuntouched. docs/LEGACY_ACCESS_ACK_CANDIDATE.md.


## Four-week comparison received — 29.10.2026

ActualuserNovemberbatch2chunks validchecksum/4weeks/sametarget accepted. FreshNVSU/Calendar:11/11exactfirstweek,9/0second,9/0third,0/0last explicitnoschedule. Missing18/duplicatesexact0/unknown0. Private18payloadhumanpreview prepared;18create0update0delete11preserve, not executable/ownershipfalse/teachingfalse. No redoexportnow; realclasswrites need separateuserpermission/freshCalendarSource/ledger/unknownrecovery, no inferencefromTEST permission.78Python+13Node targetedPASS,codeunchanged,lastfull591Python187Node6demos not rerun. No Googlecalls fromCodex/calendarwrites, legacyhotfixstilluninstalled. docs/NVSU_NOVEMBER_REVIEW.md.


## Approved18 import handoff — 29.10.2026

User reply«+»to explicit18Calendarcreate permission question authorizes exactly18payloads09–22Nov/sametarget, not otherCalendar writes/old11edits/Sheets/studentmessages/legacycode/triggers/deploy. No repeatpermissionrequest for thisscope. nvsu_approved_import.py usesexistingplanner/exactapprovedset/freshsource; .gs generic thincreate-onlytransport, not new parser/general sync. Privatecompiledwrapper containsapprovaltargethash/lessondata/sourceproof outsideGit; generictemplatealone insufficient to run. SameIDschemeGoogleCalendarAdapter, owner/target/sourcebytes/fullweek guards, durableSENDING beforePOST, per-eventAPIreceipt/externalbinding. Successfulreplayinspect0POST; partialINFLIGHT getsreadonlyinspect, no blindresume/reset/orphanclaim. LedgerSQLite migrationstillunimplemented.5newPython14newNode/full596Python201Node PASS6demos; privatewrapper/combined51globalsyntaxPASS. ActualGooglewrites0/importnotyetuserexecuted; existingTESTscope no longer onlypermission, but oldlegacyhotfixstilluninstalled. docs/NVSU_APPROVED_IMPORT.md.


## Google automation channel preparation — 29.10.2026

User requested actualremoteconnection after Windowsclasp distinction. .github/workflows/google-assistant-bridge.yml uses main-only explicitrequest.json push or manualdispatch, no cron/PR/deployonordinarypush. NativeGoogleAPIworker readonlyscopecheck/targetsecret/noRawLogs; optional RSAOAEP256+AESGCM source artifact to private controller key in ignored .assistant-state. Verify artifactworkflow/run/headSHA/main plusdigest before trusteddecryption; cipheralone not senderauth. Ownerencryptedbackup useslocalpacketAESkey, neverartifactplaintext. Localexporter onlychosenclasp3account/3offlinefields, no network or valueprinting, freshACLfolder. GitHubSecretAPI403/EnvironmentPUT401, no bypass; userUIcredential setup required.13newNode/full596Python214Node PASS6demos, no realGoogleconnection yet until connected_readonly+artifact. Futurelegacy1PUT path requiresprotectedenv/reviewer/mainpolicy/ownwritegrant/pins/full8backup+uploadfirst andseparatecodeapproval; not dispatched. GoogleCalendar/AppsScriptrun/deployment not supportedbyrelayyet;18permissionpersists manualimportunconfirmed. Do not claim unlimitedautonomy/validrefreshforever (ExternalTesting mayexpire7days). docs/GOOGLE_AUTOMATION_CHANNEL.md.


# 30.10.2026 — две минимальные legacy правки установлены в Apps Script

После включения владельцем Apps Script API и owner approval protected run [40936196524](https://github.com/koolagina/telegram-assistant/actions/runs/40936196524) завершился success: encrypted original backup сохранён до записи;1PUT, API accepted=true, post-GET verified=true, status=applied. Независимый read-only run40936525532 (main4a595c4117636b287923baf0ddd76f6057951188) подтвердил target/provenance/integrity:8файлов, ровно1основной файл отличается и точно равен ранее проверенному patchMain(original);7файлов, включая manifest/6helpers, побайтно сохранены. Общий JavaScript синтаксис PASS. Последние локальные targeted15relay+9legacy tests PASS; runtime handlers на реальных Telegram updates не запускались. Активный deployment/version/trigger inventory не проверены; обновление source не считать развёртыванием кандидата2.0.5. Код существующих триггеров может читать изменённый HEAD без нового deployment, но триггеры не создавались/не запускались этой операцией.

| Дефект | Исправление | Проверка | Оставшийся риск |
|---|---|---|---|
| «Не одобрен» давал доступ через substring | accessStatus_: точное сравнение нормализованной строки со статусом «одобрен» | mock regression + actual Google source equality | Не выполнен runtime тест с реальной таблицей/студентом |
| Устаревший callback ACK блокировал очередь | processCallback_: try/catch только answerCallbackQuery, существующая обработка сохранена | mock offset/next-update regression + actual Google source equality | Другие исключения/дубли legacy потока этим патчем не устраняются |

Calendar/Sheets/Drive/user messages/webhook/trigger/deployment операции не выполнялись. Разрешение18Calendar creates сохраняется отдельно; импорт не подтверждён, этот relay Calendar не поддерживает. Кандидат2.0.5 остаётся локальным кандидатом, исходные архивы сохранены. Причина прошлых403 точно не доказана, но после включения пользовательского API этот же ограниченный путь записи сработал. Следующий шаг — отдельная безопасная проверка поведения бота и завершение подключения Calendar, без расширения разрешений молча.



30.10.2026: локальный кандидат против дублей Drive после сбоя Sheets

Воспроизведены3сценария до исправления; новый tools/clasp/legacy-file-recovery.cjs меняет только storeFile_, review diff patches/legacy-file-recovery.patch. SENDING/SAVED Script Properties по chat/message предотвращают повторное create после сохранённой ссылки и запрещают blind retry при неизвестном исходе.8регрессионных tests; полный596Python+224Node PASS,6offline demos. Реальный source8files проверен offline в памяти/совокупный syntax PASS, Google writes0 для нового патча. Не установлен: unknown receipt пока блокирует очередь, recovery/квоты требуют завершения. Подробности [LEGACY_FILE_RECOVERY_CANDIDATE.md](LEGACY_FILE_RECOVERY_CANDIDATE.md). Предыдущие2исправления уже установлены; новые не включены в relay allowlist.



# 30.10.2026 — file candidate: quota guard и безопасная локальная сверка

К tools/clasp/legacy-file-recovery.cjs добавлен350000byte conservativeUTF8 budget/8KiBreserve, без автоматической очистки; SAVEDreuse работает при отказе в новомcreate. Новый tools/clasp/legacy-file-review.cjs — offlinefilteredreceipts only, fixed actions/counts/hashed operation keys, no rawIDs/links/secrets/network/writes.2quota+4reviewtests, полный596Python+230Node PASS,6offline demos. [Подробности и recovery порядок](LEGACY_FILE_RECOVERY_CANDIDATE.md). Unknown Drive outcome всё ещё требует надёжного доказательства/решения владельца; нет заранее известногоDriveID/quarantine, поэтому live установка заблокирована. Следующий local шаг — изучить существующую реализацию кандидата2.0.5 для минимального совместимого переноса. РабочиеGoogleресурсы/relayallowlist не изменены.

