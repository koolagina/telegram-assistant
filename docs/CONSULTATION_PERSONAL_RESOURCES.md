# Ограниченные тесты на ресурсах владельца

29.10.2026 пользователь явно разрешил: **«можно тестить в моих»**. Это уточнение приоритетнее прежнего локального требования использовать только отдельный test bot/Calendar. Не требовать повторно создания отдельных ресурсов или того же разрешения. Оно не разрешает рассылки студентам, изменение рабочих встреч/журнала, запуск второго poller, изменение webhook/triggers/deploy или прав доступа.

## Текущий доступ из чата

Проверены только безопасные признаки runtime, без чтения/печати secret values:

- Telegram bot token/owner chat ID/calendar ID не настроены в проверенных runtime переменных.
- Google SDK selectors присутствуют, но runtime identity manifest connections пуст и ready Google connection не предоставлен. Наличие этих переменных не подтверждает credentials/доступ к конкретному Calendar.
- Сервисных инструментов Telegram/Google Calendar/Apps Script в текущем наборе нет. Доступ к GitHub не даёт доступ к Script Properties или Google аккаунту.
- Старые tokens/IDs из архивных snapshots/скриншотов не используются. Яндекс credential к этой проверке не относится.

Поэтому реальные getMe/Calendar запросы от ассистента не выполнялись. Настройки/публикация cloud environment не менялись, копирование токенов в чат не требуется.

## Первый шаг без передачи секретов

Подготовлен самостоятельный helper `src/tools/consultation_connection_probe.gs`, не установленный/не запущенный в реальном проекте.

1. Открыть **существующий Apps Script проект своего бота**.
2. Добавить отдельный `.gs` файл и вставить **только** содержимое `src/tools/consultation_connection_probe.gs`. Не копировать архивные версии бота и не заменять рабочие функции.
3. Выбрать `showKulaginaConnectionProbe` и нажать **«Выполнить»** в редакторе. Не нажимать «Развернуть», не запускать initialize/setupAutomation/pollTelegramUpdates.
4. Скопировать из журнала выполнения только JSON, который вывела эта функция, в чат. В нём нет token/chat/calendar IDs/name/username/данных встреч. Не присылать Script Properties, debugger locals, HTTP traces или секреты.

Helper читает существующие `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `ASSISTANT_CALENDAR_ID` из Script Properties, **не** из cloud env; не записывает их. Если setting отсутствует, возвращает not_configured, не выбирает ресурс по умолчанию и не создаёт его. Не исправлять настройки/Calendar timezone вслепую по этому результату.

Реальные вызовы при ручном запуске:

- Один fixed-origin HTTPS POST **getMe**, no redirects/TLS verification on; подтверждение bot identity по token prefix/is_bot/safe numeric ID. Token находится только внутри protocol URL, не в отчёте/exception logs.
- `CalendarApp.getCalendarById` только явно указанного target; `getId/getTimeZone` metadata, **без** getEvents/Sheets/Drive.
- Обычный console.log только sanitized JSON. Нет sendMessage/getUpdates/getWebhook/deleteWebhook, создания/изменения/удаления events или triggers.

`ready_for_private_preview=true` означает лишь возможность следующего private read-only preview. Не доказывает write access, владельца Telegram subject, доставку, полноту занятий или работу интеграции. Другая timezone не объявляется отсутствием read access: accessible_timezone_review требует учитывать её в preview, ничего не меняет автоматически. owner_target.configured — только корректность private routing value, identity_verified остаётся false.

## Следующий минимальный тест на своих ресурсах

После проверки доступа/точных bindings и private preview использовать только новую запись с явным TEST-префиксом/уникальным test operation ID в незанятом будущем окне. Предлагаемый предел:1test hold create,1confirm update и cleanup только этого test-owned event при проверенных ownership/ETag;1test message исключительно владельцу. Это не запись настоящего студента и не изменение текущих занятий.

Не перечитывать/поглощать production updates, не запускать наш bounded worker рядом с текущим poller. Для первого connection smoke test polling не нужен. Все Calendar states/requests должны иметь durable pre-side-effect journal и unknown recovery, никаких blind retries. При ручном изменении test event cleanup останавливается для сверки.

Пока cloud credentials не подключены, реальный тест будет выполняться через контролируемый ручной runner либо отдельно согласованный authenticated connection; добавлять публичный unauthenticated endpoint/публиковать бота ради доступа нельзя. Дальнейший runner готовится по реальному sanitized результату, без подстановки неизвестных bindings.

## Что проверено локально

10новых Node VM tests: metadata-only allowlist, no getUpdates/sends, no secret/ID logs, sanitized network/API/config failures, token/bot mismatch/bool IDs/malformed/oversize JSON, explicit Calendar identity, owner routing guard, runner console output. Tests сначала красные до helper, затем зелёные.

Полный `bash tools/check-local.sh`: **577Python PASS +120Node PASS** (101base+9export+10probe),6offline demos. Helper не запускался на настоящем Apps Script. Рабочие ресурсы не менялись.

Google source claim/CAS/coordinated writers/full-import verification остаются не реализованными в live backend. Разрешение тестировать собственный Calendar не делает SQLite fixture настоящей Google Таблицей и не разрешает deployment.
