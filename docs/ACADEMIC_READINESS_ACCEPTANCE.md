# Проверка локальной готовности академического runtime

30.10.2026 — **локальный инструмент и план подключения; production не изменён**.

## Что сделано

`tools/academic_readiness.py`, `inspect_academic_runtime` принимает уже открытые доверенные ReportWorker/AccessPolicy/ProgressReader/AcademicOverview/AcademicMenu. Не принимает секреты, пути, HTTP или произвольный JSON. Проверяет точные типы, metadata schema v1/namespace/bot обоих SQLite-хранилищ, валидный cursor без его вывода, структурную связь переданных readers, mapping↔enrollment, report links↔enrollment и наличие mapping для каталога.

Возвращает агрегатный отчёт с состоянием `consistent`, `needs_review` или `blocked`; фиксированные коды проблем; counts pending/handled/blocked и sending/confirmed/rejected/cancelled/unknown; число pending с финальной квитанцией, требующих согласования состояния inbox. Сам не выполняет mark/repair/retry. Sending может принадлежать активному процессу; инспектор не называет его orphan и не снимает claim. API-confirmed не называется доставленным.

Структурный счётчик `confirmed_active_binding_records` не доказывает активность entity, временных grants, текущий login или права на конкретную запись. Фабрики не вызываются: наличие callable не подтверждает результат их будущей сборки. Их соответствие отмечено отдельным unverified. Приватные атрибуты проверяются только в текущих локальных классах; это связанный с версией проекта диагностический API, не стабильный внешний протокол.

Все SQLite-запросы — SELECT метаданных/статусов/операционных update IDs; нет чтения update payload, текста сводки, ФИО, workbook cells, секретов или реальных API. IDs используются только внутри локального cross-store сопоставления и не выводятся. До 10000 pending проверяются по receipt; при превышении проверка явно incomplete, count=None, требуется review. Это ограничение нагрузки, не очистка очереди. Сводка двух SQLite-соединений не является общей атомарной транзакцией: при активном worker она может отражать промежуточный момент, поэтому только advisory.

`ready_for_live=false`, `live_verified=false`, writes/messages=0, polling_started=false всегда. Отдельно указаны unverified: authenticated transport, factory results, real resource access, source freshness, single poll owner, deployment, bounded live acceptance, retention/backup. Нет automatic launch gate, создания расписания, принятия approvals или изменения конфигурации.

`tools/academic_overview_demo.py` расширен: в искусственном actual-SQLite сценарии inspector показывает consistent до revoke и blocked после, worker делает только mock sends и cancellation. Диагностика ничего дополнительно не отправляет. Печатаются агрегаты, без identities/текстов/путей.

Подготовлен единый [checklist подключения](ACADEMIC_CONNECTION_CHECKLIST.md) с подтверждённым/неизвестным состоянием, требуемым свидетельством и порядком будущей ограниченной приёмки. Сейчас пользователь без компьютера: ручных действий не запрашивать.

## Тесты

18 новых `tests/test_academic_readiness.py`: сначала отсутствие модуля, затем local consistency без live green; no payload/factory/send; safe summary; unknown/sending/rejected; recoverable final receipt без mark; закрытая БД; missing bindings; readers mismatch; total_changes/cursor неизменны; default-off factories; неизвестные статусы; SQL trace только SELECT без PAYLOAD; policy/mapping/report mismatch; metadata namespace mismatch; orphan catalog; bounded pending scan с явным incomplete.

Полный `bash tools/check-local.sh`: **731 Python +448 Node PASS, 10 offline демонстраций**. Лог `/tmp/kulagina-readiness-final-check.txt`. Целевой запуск: `python3 -m unittest discover -s tests -p test_academic_readiness.py`.

| Пробел | Причина | Изменение | Проверка / результат | Оставшийся риск |
|---|---|---|---|---|
| Нет единой диагностики сборки | Состояние распределено между readers и stores | Fixed aggregate inspector | Consistency/mismatch PASS | Не исполняет фабрики, runtime не доказан |
| Ошибочно принять local PASS за live | Тесты не проверяют реальные права | Always false live flags + unverified list | No live green PASS | Требуется ограниченная live-приёмка |
| Слепой повтор после сбоя | pending не означает not-sent | Receipt counts и fixed review reasons | Unknown/final receipt PASS | Ручная сверка, без repair |
| Утечка при диагностике | Сырые payload/исключения приватны | SELECT metadata only, aggregate output, fixed errors | SQL trace/privacy PASS | Даже агрегаты использовать в доверенном контексте |

Рабочие Apps Script/таблицы/календарь, токены, relay, триггеры, webhook и deployment не менялись. Нового реального диагностического запуска не было. Следующий этап подключения остаётся отдельно ограниченным и согласуемым; новые локальные проверки не заменяют разрешений пользователя.
