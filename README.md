# Kulagina Telegram Assistant

Проект разработки Telegram-бота «Ассистент Кулагиной Л. С.» на Google Apps Script с Google Sheets и Google Drive.

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
