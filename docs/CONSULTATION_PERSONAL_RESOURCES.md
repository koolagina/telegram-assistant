# Ограниченные тесты на ресурсах владельца

29.10.2026 пользователь явно разрешил: **«можно тестить в моих»**. Это уточнение приоритетнее прежнего локального требования использовать только отдельный test bot/Calendar. Не требовать повторно создания отдельных ресурсов или того же разрешения. Оно не разрешает рассылки студентам, изменение рабочих встреч/журнала, запуск второго poller, изменение webhook/triggers/deploy или прав доступа.

## Полученная реальная metadata-проверка

По присланному пользователем JSON ручного запуска29.10.2026 в12:30:08: telegram credential_present/verified=true,status=verified; calendar configured/read_access_verified/timezone_matches=true,status=accessible; owner_target.configured=true,identity_verified=false; ready_for_private_preview=true. Writes/messages0,polling_started=false. Это свидетельство ручного getMe/Calendar metadata в пользовательском Apps Script, не запуска из Codex и не подтверждение send/write/полноты НВГУ/deployment. Реальные IDs/token/названия в репозиторий не включены. Предыдущий report12:25 показывал отсутствие Calendar setting; пользователь затем настроил ASSISTANT_CALENDAR_ID в своём редакторе.

## Одно сообщение владельцу — проверка уже выполнена

Подготовлен `src/tools/consultation_owner_message_probe.gs`. Добавить только его в отдельный `.gs` файл существующего проекта и выбрать `testKulaginaOwnerMessageOnce`; он сам выводит sanitized JSON. Это первый **реальный send** при ручном запуске: один фиксированный неперсональный test text в существующий OWNER_CHAT_ID. Ни сообщений студентам, ни Calendar/Sheets/polling/webhook/triggers/deploy.

Receipt `KULAGINA_OWNER_MESSAGE_PROBE_V1` фиксируется в новом отдельном Script Property до HTTP. Значения рабочих token/owner/calendar properties не меняются. Short ScriptLock только при claim/receipt, не держится во время HTTP и не запускает вторую очередь. Повтор/restart не send; unknown/sending/rejected/смена target требуют review, не удаления/reset этого ключа. При malformed bot/private chat/message ID response outcome unknown.

Ожидаемый первый JSON: status=api_confirmed,messages_attempted_this_run=1,api_accepted=true,delivered=null. Это API acknowledgement, а не доказательство доставки: пользователь отдельно сообщает, появилось ли test сообщение в Telegram. На повторе status=already_api_confirmed и attempts0. При ошибке прислать только JSON, без Script Properties/токена/HTTP traces; не сбрасывать receipt для повторной попытки.

10новыхNode VM tests до реализации; полный577Python/140Node PASS,6offline demos. Первый send на момент подготовки ещё не выполнялся; последующий API ack и user receipt зафиксированы ниже. Повторять его не требуется. Доступ из Codex остаётся отдельным вопросом, этот runner credentials в чат не передаёт.

## Подтверждённый владельцем test message

Пользователь предоставил JSON ручного запуска12:57:58: status=api_confirmed,messages_attempted_this_run=1,api_accepted=true,delivered=null. На отдельный вопрос о получении ответил «да». Поэтому API acceptance и human-observed receipt **этого конкретного** owner test сообщения подтверждены по пользовательским данным. Telegram API delivered остаётся null; не распространять этот результат на студентов/другие сообщения или общий end-to-end bot deployment. Повторять owner-message runner не требуется.

## Следующий шаг — read-only Calendar REST preview

`src/tools/consultation_calendar_preview.gs` подготовлен, **ещё не запускался на настоящем ресурсе**. Создать отдельный файл `ПроверкаКалендаря`, вставить только этот код, выбрать `previewKulaginaCalendarTest` и выполнить. Прислать только JSON. Existing code/settings не менять, «Развернуть»/initialize/setupAutomation/poller не запускать.

Helper использует тот же explicit ASSISTANT_CALENDAR_ID и собственный OAuth текущего Apps Script (ScriptApp.getOAuthToken); token/ID/сведения о встречах не печатает и в чат не передаёт. Только fixed-origin HTTPS GET Calendar v3 metadata и узких20min windows, no redirects/TLS verify. CalendarApp read gate сохраняет существующую авторизацию. Нет create/PATCH/DELETE, sendMessage/getUpdates, Sheet access или property updates.

Ищется **только один временный TEST slot**, не консультация студенту: будни,10:00 или10:40,20мин, ближайшие8календарных дней, минимум30мин на момент возврата после API read. Уже занятое окно пропускается, не распечатываются названия/участники/описания событий. Не более13REST GET requests; unread next page не равна пустому календарю. Original working bot/poller не меняются.

При status=preview_ready пользователь видит exact RFC3339 start/end в Asia/Yekaterinburg; Calendar writes0/messages0/write_access_verified=false/teaching_schedule_verified=false. Пустое окно выбранного Calendar не доказывает отсутствие неимпортированных занятий. Test event по этому preview ещё не создаётся: сначала нужны реальные date/API результаты. При403/accessNotConfigured или иной ошибке код не включает API/права сам; прислать sanitized JSON для диагностики.

10новыхNode VM tests first red→green, включая slow read/30min regression и unread page. Полный577Python/140Node PASS,6offline demos. Actual Calendar REST preview/create/update/delete ещё не подтверждены; metadata native CalendarApp уже подтверждена пользователем.

## Текущий доступ из чата

Проверены только безопасные признаки runtime, без чтения/печати secret values:

- Telegram bot token/owner chat ID/calendar ID не настроены в проверенных runtime переменных.
- Google SDK selectors присутствуют, но runtime identity manifest connections пуст и ready Google connection не предоставлен. Наличие этих переменных не подтверждает credentials/доступ к конкретному Calendar.
- Сервисных инструментов Telegram/Google Calendar/Apps Script в текущем наборе нет. Доступ к GitHub не даёт доступ к Script Properties или Google аккаунту.
- Старые tokens/IDs из архивных snapshots/скриншотов не используются. Яндекс credential к этой проверке не относится.

Поэтому реальные getMe/Calendar запросы от ассистента не выполнялись. Настройки/публикация cloud environment не менялись, копирование токенов в чат не требуется.

## Первый шаг без передачи секретов

Самостоятельный helper `src/tools/consultation_connection_probe.gs` был добавлен и запущен пользователем в его реальном проекте; результат metadata зафиксирован выше. Инструкция ниже оставлена как справка, повторять её сейчас не требуется.

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

Полный `bash tools/check-local.sh`: **577Python PASS +140Node PASS** (101base+9export+10metadata+10owner+10Calendar preview),6offline demos. Metadata helper и owner-message helper запущены пользователем; Calendar REST preview пока только локально проверен. Calendar events/working bot code/triggers не менялись.

Google source claim/CAS/coordinated writers/full-import verification остаются не реализованными в live backend. Разрешение тестировать собственный Calendar не делает SQLite fixture настоящей Google Таблицей и не разрешает deployment.
