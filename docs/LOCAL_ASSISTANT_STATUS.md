# Локальный кандидат единого помощника — 28.10.2026

Основной GAS-кандидат: `src/telegram_assistant_v2_0_5_candidate.gs`; он не изменён этим этапом. Python-компоненты находятся в `tools/`. Архивные snapshots сохранены. Какая версия реально развёрнута, по локальному репозиторию не подтверждено; новых deploy/триггеров/webhook не выполнялось.

| Компонент | Реализовано локально | Ещё не подключено/не доказано |
|---|---|---|
| Материалы | Проверка source metadata/hash, Word text/drafts, версии и история | Live bindings, полный semantic validator; публичный DOCX adapter тестировался моками |
| Проверка работ | Manifest PPTX count, version-bound minimum, exact evidence quotes | Научная оценка, авторство, графика/формы, автооценка/проходной порог |
| Хранилище результатов | MaterialCatalog SQLite, immutable done, needs_recheck | Реальный ingestion/backup runtime; done не означает принятую отработку |
| Принадлежность | ReportRegistry private SQLite, immutable links, unique check, retry | Trusted publication adapter для реальных submission/enrollment |
| Права | AccessPolicy, PolicyStore version snapshots/CAS/no older fallback | Реальная authentication и административная процедура подтверждения/отзыва |
| Запросы | Self list/page/buttons, teacher report, current-policy gating, verified-input TG parser | Проверка происхождения TG source/HTTP client, endpoints, sends/receipts/delivery |
| Учебный журнал | Read-only локальное чтение структуры XLSX | Полный расчёт успеваемости, синхронизация отметок, запись реального журнала |
| Production | Исходники и локальные тесты | Разрешённая sandbox-приёмка, bindings, rollout |

## Проверка одной командой

```bash
bash tools/check-local.sh
```

Нужны Python с зависимостью из `requirements-lecture.txt` и Node.js. Скрипт не устанавливает пакеты, не использует секреты, сеть, рабочие таблицы или отправки. Создаёт только временные SQLite в synthetic demos, удаляемые при завершении. Отдельные команды:

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/run-current.cjs
python tools/review_demo.py
python tools/assistant_demo.py
```

Подтверждено: **313 Python +101 Node PASS**. Демо прошло работу с настоящими локальными SQLite, собственную/чужую кнопку, повторную загрузку, страницы, перезапуск, отзыв прав, stale write и сбои публикации до/после accepted commit. Ни один такой тест не подтверждает реальную доставку или работу production API.

## Данные и восстановление

Все registry/policy entries в демо искусственные. Не переносить `synthetic_policy`/confirmed fake bindings в рабочую систему. `PolicyStore` сам по себе пуст и deny-all до явного trusted provisioning. Снимок JSON — приватные данные, не конфигурация из публичного запроса и не место для секретов.

Данные SQLite/WAL и `.assistant-state/` исключены из Git. Хранилища имеют отдельный project namespace, directory0700/file0600; это локальные права файлов, не шифрование или защита от администратора машины. Результат фиксируется до публикации immutable link: незавершённая публикация повторяется, не меняя владельца. Для замены ошибочной ownership relation нужен отдельный проверяемый процесс, не overwrite.

Backup/restore нескольких DB должен быть согласован; не копировать только main SQLite без WAL. Старый backup policy может вернуть ранее отозванные grants: внешний anti-rollback witness и реальная административная сверка не реализованы. Повреждённый текущий снимок не заменяется более старым автоматически.

## Дальнейшая последовательность

1. Подготовить проверяемый authentication/provisioning adapter для отдельной тестовой среды; не считать Telegram username, email из текста или ChatGPT args подтверждённой identity.
2. Подключить trusted ingestion и актуальные материалы, утвердить полноту критериев. Проходной порог нужен до автоматического принятия; сейчас все отчёты требуют преподавателя.
3. Добавить transport с повторной проверкой прав перед фактической отправкой, безопасным форматированием, различением prepared/API success/delivery и восстановлением частичных сбоев.
4. Провести отдельно разрешённую интеграционную приёмку на test bot/resources, затем согласованный rollout. Реальные письма, изменения журнала и production не входят в текущие локальные действия.

Telegram adapter принимает только инъецируемый trusted verified polling transport; произвольный JSON не аутентифицируется. Новый модуль не выполняет getUpdates/offset/ack и не подключён к существующему poller. Fake numeric subjects демонстрации не являются реальными bindings.
