# Kulagina Telegram Assistant

Проект разработки Telegram-бота «Ассистент Кулагиной Л. С.» на Google Apps Script с Google Sheets и Google Drive.

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

Полный локальный Python suite: `python -m unittest discover -s tests -p 'test_*.py'` — 138 PASS (НВГУ, XLSX, academic policy, lecture windows); текущий бот: `node tests/run-current.cjs` — 101 PASS. Это не проверка реальных API или развёртывания.


## Локальная академическая policy

`tools/assistant_access.py` — проверка прав двух преподавателей, собственных данных студента и временного замещения по конкретной лекции. [Контракт и границы доверия](docs/ACCESS_POLICY.md). Это не authentication и не включённый режим бота: настоящий registry и transport adapters отсутствуют. Полный Python suite — **138 PASS**, из них 36 policy и 22 lecture windows; текущий бот — 101 PASS. Сеть и реальные данные не используются.

Пользователю предусмотрено явное полное академическое чтение (AcademicReadGrant), включая расписание второго преподавателя и все известные учебные данные студентов; второму преподавателю оно автоматически не передаётся. Это ещё не live-привязка аккаунта.


## Локальные lecture-коды

`tools/lecture_windows.py` реализует SQLite/AES-GCM ядро 90-секундных окон и проверяет `assistant_access` policy. Нужна `cryptography`: `python -m pip install -r requirements-lecture.txt`. [Контракт, ключи и ограничения](docs/LECTURE_WINDOWS.md). Telegram/QR/реальная identity и запись в журнал ещё не подключены. Локальное событие регистрации не означает сохранённый плюс в XLSX. Полный Python suite — 138 PASS, бот — 101 PASS.
