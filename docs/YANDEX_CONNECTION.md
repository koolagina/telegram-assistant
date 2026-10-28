# Проверка Яндекс Диска через GitHub Actions — 28.10.2026

## Настроенный маршрут

Пользователь сохранил `YANDEX_DISK_TOKEN` в GitHub repository Secrets. Секрет не извлекается в чат/Codex и не включается в Git. Подготовлен `.github/workflows/yandex-disk-read-check.yml`, только `workflow_dispatch`: нет cron, push/PR trigger или постоянного процесса. Основная ветка main, timeout 2 минуты, permissions contents:read, checkout pinned SHA с persist-credentials:false, секрет доступен только probe step. Публикация облачной среды не требуется и не запускалась.

`tools/yandex_disk_probe.py` выполняет один HTTPS GET к фиксированному endpoint cloud-api.yandex.net/v1/disk/resources с path=disk:/ и fields=type. Запрашивается только тип корневого ресурса; списки файлов, имена, содержимое и журнал не читаются. Перенаправления запрещены, TLS verification сохраняется, timeout 20 секунд, ответ ограничен 16 KiB. В stdout только whitelist статуса и writes_performed=false; ни header/token, ни API body/URL ошибки не печатаются. Это проверка одной операции чтения, не доказательство полного набора OAuth scopes и не доступ к безопасной записи XLSX.

## Первый запуск — исторический отказ

[Run 40645632279](https://github.com/koolagina/telegram-assistant/actions/runs/40645632279), исходный commit bf44528, manual dispatch на main.

- Runner/checkout: SUCCESS; GitHub Actions workflow действительно запустился и завершился за несколько секунд.
- Secret env получен непустым (иначе script вернул бы secret_unavailable); его значение не извлекалось и GitHub маскирует его в логе.
- Probe: **FAIL, token_rejected (HTTP 401)**. Яндекс не принял предоставленную авторизацию.
- Повторных запусков после неизменного 401 не выполнялось. Файлы не перечислялись/не менялись, реальные письма/журнал/бот не затронуты.
- Нельзя установить по 401, истёк ли токен, отозван или неверно скопирован; scope mismatch отдельно обрабатывается как HTTP403. Проверка не доказывает наличие рабочего доступа к Диску.

GitHub API не дал текущей integration читать список repository Secrets (403), но это не помешало dispatch и передаче секрета внутри Actions. Дополнительные GitHub credentials не запрашивались. Токен Яндекса в Codex не переносился.

## Действие после первого отказа — выполнено пользователем

В GitHub открыть Settings → Secrets and variables → Actions → YANDEX_DISK_TOKEN → Update и сохранить корректное значение OAuth token. Не ClientID, не Client secret, не полный URL и не слово OAuth с префиксом. При необходимости получить свежий токен существующего приложения с cloud_api:disk.read. Значение вводить только в защищённое поле, не присылать в чат/скриншотах.

После изменения выполнить один новый ручной Run workflow либо запросить запуск из чата. Только read_verified с реальным API считается подтверждением этой операции чтения. Затем отдельно согласованные ресурсы можно инвентаризировать read-only; текущая probe не начинает чтение учебных файлов автоматически. IMAP/Почта, запись Диска/XLSX и рассылка этим workflow не подключаются.

## Локальные проверки

`tests/test_yandex_disk_probe.py`: **8 PASS** — fixed GET/headers, отсутствие секрета, invalid input, redirect refusal, HTTP401/403, network/unknown HTTP, неверный/большой body, безопасный CLI. Первый запуск был красным до реализации модуля. Полный Python suite: **146 PASS** (138 прежних + 8 probe). В реальном GitHub Actions mock не используется: подтверждён именно отказ 401. Текущий Node suite в этом этапе не перезапускался, GAS-код не менялся.


## Актуальная повторная проверка — SUCCESS, 28.10.2026

По просьбе пользователя выполнен один новый manual run после изменения секрета: [40646446786](https://github.com/koolagina/telegram-assistant/actions/runs/40646446786), commit 18c7865. GitHub Actions завершился SUCCESS; probe вернула read_verified, writes_performed=false. Это реальное подтверждение возможности прочитать metadata type корня Диска с текущим GitHub Secret. Предыдущий HTTP401 устранён для этой операции.

Сам токен не извлекался в Codex. Список файлов и учебный журнал не читались/не менялись. Доступ к конкретным папкам/книге, полный набор OAuth scopes, почта, безопасная запись XLSX и постоянная синхронизация этим тестом не проверены. Следующий возможный этап — отдельная read-only проверка согласованного ресурса через Actions, а не перенос токена в чат или публикация среды.


## Проверка согласованных ресурсов — 28.10.2026

Добавлен отдельный ручной `.github/workflows/yandex-resource-inventory.yml` и `tools/yandex_resource_inventory.py`. Проверка читает только метаданные: до 5 страниц по 1000 spreadsheet records, затем точечную metadata проверку единственного совпадения и type публичной папки материалов. Endpoint media_type=spreadsheet/limit/offset проверен по официальной документации https://yandex.ru/dev/disk-api/doc/ru/reference/all-files. Названия/пути посторонних файлов остаются только в памяти runner, не печатаются и не сохраняются в artifacts/Git. Никаких downloads или writes. Неполный scan не объявляется отсутствием или уникальным совпадением; несколько одноимённых копий требуют выбора. Сравнение имени игнорирует регистр/пробелы, не делает произвольного fuzzy-match.

Реальный run [40647021089](https://github.com/koolagina/telegram-assistant/actions/runs/40647021089), commit e7e73ce: API запросы успешно выполнены, материалы folder_readable. journal_status=not_found_in_scan, matching_files=0, scan_complete=true; writes_performed=false, files_downloaded=false. Задание имеет conclusion failure, поскольку требуемый журнал не найден, а не из-за токена/HTTP401. Это отсутствие совпадения среди доступных spreadsheet metadata, не доказательство отсутствия книги во всех ресурсах Яндекса (включая общие/онлайн-документы).

Нужно уточнить точное имя/папку существующего журнала или согласованный authenticated путь. Не просить открыть публичный доступ к студенческому журналу и не публиковать приватный путь/ссылку в Git. Пользователю задан вопрос о расположении. До ответа повторять тот же scan не нужно. Доступ к содержимому папки заданий и чтение/сравнение самой книги — отдельные следующие шаги.

8 inventory mock tests PASS, вместе с probe и прежними модулями **154 Python PASS**. Первый запуск тестов был красным до модуля. Старый minimal probe сохранён (общая validate_token helper выделена без изменения поведения); все прежние tests прошли. Node не перезапускался, GAS не менялся.
