Последний локальный блок: [меню дисциплин и студентов](docs/ACADEMIC_MENU_ACCEPTANCE.md) — 695 Python +448 Node PASS; не развёрнуто.

Актуальный локальный блок: [единая учебная сводка](docs/ACADEMIC_OVERVIEW_ACCEPTANCE.md) — 673 Python +448 Node PASS, 10 offline демонстраций; не развёрнут.

Последний локальный блок: [защищённое чтение прогресса из журнала](docs/ACADEMIC_PROGRESS_ACCEPTANCE.md). 649 Python +448 Node PASS; не подключён к рабочим ресурсам.

# Kulagina Telegram Assistant

## Актуальное состояние — 30 октября 2026

**Начните с [единой карты проекта](docs/PROJECT_OVERVIEW.md):** что установлено в Apps Script, что остаётся локальным кандидатом, архитектура, нерешённые подключения и план управления через Telegram, ChatGPT и MAX.

В рабочий legacy-проект уже установлены согласованные узкие исправления, включая очередь, постоянную привязку ответов, защиту текстовых полей и уведомления. Кандидат 2.0.5 целиком не развёрнут. Последняя локальная проверка: 629 Python +448 Node успешно; это не подтверждение всех реальных интеграций. После отзыва неопознанного OAuth-разрешения текущий runtime-доступ к Sheets ещё не проверен.

[Большой блок task-workflow-1](docs/TASK_WORKFLOW_ACCEPTANCE.md) завершён локально: единый кандидат и 35 новых сквозных/сборочных тестов; рабочая установка ещё не выполнена.

[Блок расписания и консультаций](docs/SCHEDULE_CONSULTATION_ACCEPTANCE.md) также завершён локально: 55 новых тестов, проверка полноты и межъязыковой цикл заявки. Реальная запись студентов и runtime provider не подключены.

**Разделы ниже — исторические этапы.** Фразы «не установлен» и старые количества тестов относятся к указанному этапу, а не заменяют актуальную карту.

Проект разработки Telegram-бота «Ассистент Кулагиной Л. С.» на Google Apps Script с Google Sheets и Google Drive.

## Подготовлен автоматический Google channel

[GitHub Actions relay](docs/GOOGLE_AUTOMATION_CHANNEL.md) позволит читать текущий Apps Script без ручных source uploads: fixed request queue, readonly OAuth, source encrypted до контроллера. Git→Actions запуск проверен (run40894062838), worker остановился connection_not_configured с0Googlecalls. Google credential нужно однократно сохранить в GitHub Secret; **успешное подключение пока не подтверждено**. Protected write path только для reviewed2fixes подготовлен, но без writegrant/environment/usercodeapproval не исполняется. Calendar-операции этим relay пока не поддержаны. **596 Python +214 Node PASS**,6offline demos.

## Импорт18занятий согласован, runner готов

[Ограниченный ручной Apps Script runner](docs/NVSU_APPROVED_IMPORT.md) подготовлен для согласованных18созданий09–22ноября. Existing planner/ID scheme, свежая source/Calendar проверка, no updates/deletes/unknown resend. Свежий НВГУ не изменил утверждённые payloads. Реальный запуск ещё впереди; Google-доступ остаётся у пользователя, повторного разрешения на эти18не требуется. **596 Python +201 Node PASS**,6offline demos.

## Минимальный кандидат рабочего исходника подготовлен

Все8backupфайлов проверены:49глобальных функций, без конфликтов. [Кандидат и diff](docs/LEGACY_ACCESS_ACK_CANDIDATE.md) исправляют только negative approval и expiredcallback; manifest/6helpers сохраняются побайтно. **Не установлен**, writeавторизация/Googlewrites не выполнялись. Полный suite **591 Python +187 Node PASS**,6offline demos. Four-week export уже есть в полученном Apps Script source, codecopy для него не нужен.

## Четыре недели ноября сравнены

Полный пользовательский Calendarbatch сопоставлен со свежим НВГУ:02–08ноября11занятий совпадают; на09–15и16–22ноября отсутствуют по9;23–29ноября источник/календарь пусты. [Предварительный план](docs/NVSU_NOVEMBER_REVIEW.md): **18добавлений,0изменений/удалений**, без исполнения. Флаг полноты/консультации не включены, реальные записи требуют отдельного разрешения и свежей сверки.78Python+13Node targetedtests PASS; код в этом шаге не менялся.

## Причины защиты событий проверены

Пользовательская read-only диагностика завершена: у11событий присутствует поле участников, у5описание. Число участников и содержимое не раскрыты; пустой массив тоже считается причиной защиты. Существующие события сохраняются. Повторять проверку не нужно. Принадлежность синхронизатору и остальные недели ещё требуют проверки; автоматизация не развёрнута. [Результат и следующие условия](docs/NVSU_PRIVATE_COMPARISON.md). Последний локальный suite: **590 Python +168 Node PASS**,6offline demos.

## Сверка НВГУ: неделя 2–8 ноября совпадает

Пользовательский Calendar-снимок проверен по checksum и сопоставлен со свежим НВГУ: **11 занятий, 11 точных совпадений времени/дисциплины/аудитории, пропусков и дублей совпадений нет**. Изменения событий не нужны по этому снимку. Все события защищены; ownership/полнота остальных недель ещё не доказаны, запись студентов и автоматизация не включены. [Результат и границы](docs/NVSU_PRIVATE_COMPARISON.md). Локально **590 Python +160 Node PASS**, 6 offline demos.

## Предыдущий шаг: успешный Calendar TEST

По журналу пользователя одно временное TEST-событие успешно создано, обновлено и удалено; cleanup завершён, повторять тест не нужно. [Результат и границы проверки](docs/CONSULTATION_PERSONAL_RESOURCES.md). Полнота расписания ещё не проверена: следующий этап — read-only сравнение НВГУ с календарём, без импорта и запуска записи студентов. Последняя локальная проверка: **577 Python +151 Node PASS**, 6 offline demos. Новый бот не развёрнут.

## Текущий шаг: Calendar preview после получения owner test

Пользователь подтвердил получение одного реального test сообщения; API ack и metadata Calendar ранее проверены manual runners. Read-only Calendar REST preview подготовлен, ещё не запускался: [инструкция](docs/CONSULTATION_PERSONAL_RESOURCES.md). Новые события не создавались, расписание не объявлено полным. **577Python +140Node PASS**,6offline demos (`bash tools/check-local.sh`).

## Проверка реального подключения — текущий шаг

Пользовательский manual metadata probe подтвердил Telegram getMe и доступ к выбранному Calendar с нужным часовым поясом; send/write ещё не проверялись. Подготовлен idempotent owner-only test message runner, не запущенный на реальном проекте. [Инструкция](docs/CONSULTATION_PERSONAL_RESOURCES.md). Полная локальная проверка: **577Python +130Node PASS**,6demos. Не является deployment или проверкой полноты расписания.

## Проверка подключения на ресурсах владельца

Владелец разрешил ограниченные тесты на своих ботe/Calendar. Подготовлена read-only проверка в существующем Apps Script без токенов в чате и без публикации среды: [инструкция](docs/CONSULTATION_PERSONAL_RESOURCES.md). Доступ из этой сессии ещё не подтверждён, реальных bot/Calendar вызовов не было. Актуально **577Python +120Node PASS** (`bash tools/check-local.sh`).

## Актуальная локальная приёмка

**577Python +110Node PASS**,6offline demos: `bash tools/check-local.sh`. Комплексный цикл approve/reject проходит original-evidence consent, Calendar recovery, local fixture CAS/status и independent notices; exact legacy bot description обновляется без потери заметок. [Пример](docs/CONSULTATION_WORKFLOW_DEMO.md), [отчёт](docs/AUDIT_REPORT.md), [план отдельной sandbox-приёмки](docs/CONSULTATION_SANDBOX_ACCEPTANCE.md). Рабочие ресурсы/бот не изменены; реальная версия deployment не подтверждена. SQLite source не заменяет real Google Sheets adapter.

## Исходные данные подтверждения — текущая локальная проверка

Реестр original-evidence review и bound worker связывают отдельное owner confirm со строкой/событием, не заменяют исходные данные после решения. Calendar reads вне DB locks, legacy proposals сохранены; всё opt-in/mock-only. **572Python +110Node PASS** (`bash tools/check-local.sh`). [Контракт](docs/CONSULTATION_CONSENT.md). Рабочие ресурсы не подключены.

## Финализация и уведомления — локальная проверка

Local fixture CAS/claim связывает Calendar receipt со статусом заявки и двумя независимыми business-key notice jobs. Сбой уведомления не повторяет Calendar. **548Python +110Node PASS**,6offline demos (`bash tools/check-local.sh`). [Контракт](docs/CONSULTATION_WORKFLOW.md), [пример](docs/CONSULTATION_WORKFLOW_DEMO.md). Это SQLite модель, не подключённая Google Таблица; реальные отправки/записи отсутствуют.

## Календарный этап консультаций — текущая локальная проверка

Готов выключенный по умолчанию executor с исходной привязкой решения, ETag, durable claim и read-only восстановлением после timeout. **521 Python +110 Node PASS** (`bash tools/check-local.sh`). [Контракт и ограничения](docs/CONSULTATION_EXECUTOR.md), [пример одного mock PATCH и восстановления](docs/CONSULTATION_EXECUTION_DEMO.md). Это отдельный Calendar stage: реальные API не вызывались, статусы источника и уведомления не записываются; live включение требует source CAS/verified bindings и отдельной приёмки.

## Обработчик консультаций — текущий локальный кандидат

Кнопки проходят durable inbox, атомарную запись локального решения/ответа и отдельный UI dispatch с новой проверкой прав. Повтор/restart не создаёт второй handler/план; сбой local receipt откатывает решение. **483 Python +110 Node PASS** (`bash tools/check-local.sh`). [Контракт](docs/CONSULTATION_WORKER.md), [пример](docs/CONSULTATION_ACTIONS_DEMO.md). Реальные отправки и календарные операции не выполнялись, рабочий бот не изменён.

## Входные данные консультаций — текущая локальная проверка

Подготовлены read-only export helper и строгие нормализаторы заявок/занятости. Изменения получателя или события инвалидируют старые кнопки; полнота занятий требует отдельного проверенного подтверждения. **459 Python +110 Node PASS** (`bash tools/check-local.sh`). [Контракт и оставшиеся подключения](docs/CONSULTATION_FEED.md). Настоящие Google ресурсы не читались/не менялись, helper не установлен.

## Решения по консультациям — локальный сценарий

Карточка с тремя действиями, отдельное подтверждение, повторные проверки занятости/прав и durable план без дублей. Реальный Calendar/Telegram executor отключён и ещё не реализован; рабочий GAS не менялся. [Контракт](docs/CONSULTATION_ACTIONS.md), [пример диалога](docs/CONSULTATION_ACTIONS_DEMO.md). Локально: `python tools/consultation_demo.py`. Актуальная полная проверка: **430 Python +101 Node PASS**.

## Очередь решений владельца — текущий локальный кандидат

`/decisions`: консультации, проверки работ и технические сбои; фильтры, сроки и подробности. Доступ только владельцу, source failures явно помечают неполную сводку. Никаких автоматических решений/оценок/отправок. **400 Python +101 Node PASS**. [Пример меню](docs/DECISION_QUEUE_DEMO.md), [контракт и ограничения](docs/DECISION_QUEUE.md). Команда рабочего GAS-бота ещё не включена. Локальная приёмка: `bash tools/check-local.sh`.

## ВАЖНО: статус исходников

- `src/archive/telegram_assistant_v1_4_3_reference.gs` — доступный исторический снимок версии 1.4.3. Это **не подтверждённая копия текущего развёрнутого production-проекта**.
- `src/telegram_assistant_v2_0_2_candidate.gs` — кандидат для аудита, **не устанавливать в рабочий проект до прохождения тестов**.
- Ни одна версия в этом пакете не считается production-ready только на основании наличия файла или локальной проверки синтаксиса.

## Основные зависимости и интеграции

- Google Apps Script
- Google Sheets: таблица «Поручения студентам» (ID хранить в конфигурации, не разбрасывать по коду)
- Google Drive для вложений
- Telegram Bot API
- Google Calendar
- Официальная страница расписания НВГУ: `https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/3648` (проверить актуальность и устойчивость структуры перед реализацией парсера)

## Принцип работы

Сначала аудит и воспроизводимые тесты; затем изолированная тестовая среда; только после успешной проверки — ручное развёртывание в production. Не подключать кандидатов к реальной таблице и реальному боту для тестов.


## Текущий локальный кандидат

`src/telegram_assistant_v2_0_5_candidate.gs` — консультации по согласованным правилам, предварительные записи и меню. Подробности: [сценарий консультаций](docs/CONSULTATIONS.md), [актуальный аудит](docs/AUDIT_REPORT.md). Проверки: `node tests/run-current.cjs`. Предыдущие snapshots сохранены. Кандидат не развёрнут; для записи нужен полный проверенный источник занятий, которого пока нет.


## Подготовка синхронизации НВГУ с Calendar

Используются существующие `tools/nvsu_preview.py` и `tools/nvsu_sync.py`; добавлены Google transport, SQLite-журнал и read-only CLI `tools/nvsu_calendar.py`. Реальное подключение ещё не проверено; бот и триггеры не изменены. [Предварительный план и команды](docs/NVSU_CONNECTION_PLAN.md), [результаты проверок](docs/TEST_PLAN.md). Offline tests требуют только Python; Google transport — отдельный venv с `requirements-calendar.txt`.


## Локальное чтение учебного журнала без подключения Яндекса

`python tools/gradebook_read.py PATH_TO_LOCAL_XLSX` печатает только структурный отчёт без имён и оценок. Модуль не вычисляет формулы, не записывает файл и не определяет student identity. Данные загруженного журнала не хранятся в Git. [Аудит и ограничения reader](docs/GRADEBOOK_STRUCTURE_AUDIT.md), [единый план](docs/UNIFIED_ASSISTANT_PLAN.md).

Полный локальный Python suite: `python -m unittest discover -s tests -p 'test_*.py'` — 168 PASS (НВГУ, XLSX, policy, lecture windows, Yandex mocks, material versions); текущий бот: `node tests/run-current.cjs` — 101 PASS. Это не проверка реальных API или развёртывания.


## Локальная академическая policy

`tools/assistant_access.py` — проверка прав двух преподавателей, собственных данных студента и временного замещения по конкретной лекции. [Контракт и границы доверия](docs/ACCESS_POLICY.md). Это не authentication и не включённый режим бота: настоящий registry и transport adapters отсутствуют. Полный Python suite — **168 PASS**, из них 36 policy и 22 lecture windows; текущий бот — 101 PASS. Сеть и реальные данные не используются.

Пользователю предусмотрено явное полное академическое чтение (AcademicReadGrant), включая расписание второго преподавателя и все известные учебные данные студентов; второму преподавателю оно автоматически не передаётся. Это ещё не live-привязка аккаунта.


## Локальные lecture-коды

`tools/lecture_windows.py` реализует SQLite/AES-GCM ядро 90-секундных окон и проверяет `assistant_access` policy. Нужна `cryptography`: `python -m pip install -r requirements-lecture.txt`. [Контракт, ключи и ограничения](docs/LECTURE_WINDOWS.md). Telegram/QR/реальная identity и запись в журнал ещё не подключены. Локальное событие регистрации не означает сохранённый плюс в XLSX. Полный Python suite — 168 PASS; последний запуск бота — 101 PASS.


## Проверка GitHub Secret для Яндекс Диска

Actions → **Yandex Disk read-only check** → Run workflow: одно ручное metadata-чтение без списка файлов/изменений. Использует repository Secret YANDEX_DISK_TOKEN, без передачи в Codex. [Фактический результат](docs/YANDEX_CONNECTION.md): повторный run 40646446786 SUCCESS/read_verified, metadata корня прочитаны; первый HTTP401 устранён. Учебные файлы/Почта/запись ещё не проверены. Публикация среды не нужна.

Read-only metadata discovery доступно отдельным manual workflow **Yandex approved resource metadata**. Первый personal-files scan не нашёл книгу. После уточнения общей ссылки journal найден в public-resource metadata (1 XLSX + 5 DOCX), размер/MD5 совпадают с загруженной копией. Никаких файлов не скачано/не изменено. См. docs/YANDEX_CONNECTION.md.


## Каталог учебных материалов

[Аудит DOCX](docs/MATERIALS_CATALOG.md): прочитаны 4/5 файлов, включая загруженные задания отработки лекций; вопросы M02 исключены пользователем. Выделены задания шести практик, четырёх отработок и расхождения старых инструкций с ТЗ. Назначения оценок/автоответов нет, оригиналы в Git не включены.


## Обновления заданий

[Каталог материалов](docs/MATERIALS_CATALOG.md) дополнен M04 из upload; вопросы M02 пользователь исключил из обязательных. Lecture makeup связываются по номерам 1→1, 2→2, 3→3, 4→4. `tools/material_versions.py` — локальная история source/criteria и version-bound checks: новое содержимое → новая версия, смена во время pending проверки → needs_recheck, completed results не меняются. [Контракт и ограничения](docs/MATERIAL_VERSIONS.md): live parser/watcher/grader ещё не подключены. Полный Python suite 168 PASS, Node 101 PASS.


## Локальный разбор материалов Word

`tools/material_docx.py` извлекает текст/таблицы с ограничениями ZIP/XML, помечает неподдержанные элементы для review. Это не автоматическое утверждение критериев; подключение к Диску/оценке пока отсутствует. 11 новых synthetic tests, текущий полный Python suite **179 PASS**. Подробности — [контракт материалов](docs/MATERIAL_VERSIONS.md).


## Чтение актуального публичного DOCX

`tools/material_source.py`: read-only адаптер конкретного файла, проверяет SHA-256/размер и метаданные до/после скачивания, при ошибке останавливается без старого кеша. 8 новых mock tests; полный Python **187 PASS**. Реальная загрузка и автоматическая связка с проверкой работ ещё не включены. [Подробности](docs/MATERIAL_VERSIONS.md).


Демонстрация без сети и настоящих данных: `python tools/review_demo.py`. [Пример отчёта](docs/REVIEW_DEMO.md).
