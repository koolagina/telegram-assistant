# План изолированной приёмки консультаций

Подготовлен29.10.2026. **Не запускался и не разрешён к исполнению на реальных ресурсах.** Сначала пользователь выбирает отдельные тестовые ресурсы; затем формируется конкретный private preview и отдельно согласуются реальные действия. Ни один ресурс/secret ниже не считается существующим или настроенным только из-за этого документа.

## Уже подготовлено локально

- Candidate code: `tools/consultation_consent.py`, `consultation_bound_worker.py`, `consultation_executor.py`, `consultation_calendar.py`, `consultation_workflow.py`; read-only export helper `src/tools/consultation_snapshot_export.gs` не установлен.
- GAS-кандидат `src/telegram_assistant_v2_0_5_candidate.gs` и архивы сохранены. Какая версия реально развёрнута, не проверено. Python candidate не подключён к действующему боту/webhook/triggers.
- `bash tools/check-local.sh`: **577Python PASS +110Node PASS**,6offline demos. Исходные данные/участники/полнота/согласие в tests/demos synthetic. SDK credentials, действующие токены и реальные учебные файлы не использовались.
- `python tools/consultation_workflow_demo.py` воспроизводит private inbox→card→original review→confirm→claim→accepted mock Calendar timeout→read-only reconcile→atomic local status/jobs→student unknown/owner API-confirmed. Один mock PATCH, без blind retries.

## Что должен определить пользователь

1. Отдельный test bot, который не обслуживает студентов и не используется текущим poller/webhook. Если такого нет, его создаёт владелец Telegram через официальный BotFather; этот чат не имеет доступа к его аккаунту. Реальный token не присылать в чат/скриншот/Git.
2. Отдельный пустой test Calendar, на котором допустимы только специально подготовленные synthetic consultation events. Не выбирать production Calendar/primary. Указать конкретный ресурс через согласованную закрытую конфигурацию; доступ Google пока не подтверждён.
3. Два явно подтверждённых test chat subjects: владелец и тестовый студент, начавшие диалог с test bot. Real студент/учебный журнал/личные письма не нужны. Если второго аккаунта нет, student send остаётся mock до отдельного выбора участника.

Только **предлагаемые имена будущей private конфигурации**, не установленные env/Script Properties: `KULAGINA_TEST_TELEGRAM_TOKEN`, `KULAGINA_TEST_BOT_ID`, `KULAGINA_TEST_CALENDAR_ID`, `KULAGINA_TEST_OWNER_CHAT_ID`, `KULAGINA_TEST_STUDENT_CHAT_ID`. Google credentials — через отдельно настроенный trusted runtime provider с согласованными scopes; интерактивный login/расширение scopes автоматически не запускать. Идентификаторы доступа/значения не коммитить. Яндекс token для этой приёмки не нужен и не проверяется.

## Первый реальный шаг — только после разрешения на чтение

- Verify getMe == явно выбранный test bot ID. Наличие token не доказательство правильного бота.
- Проверить identity/timezone/read access конкретного test Calendar; list events в одном будущем тестовом рабочем окне. Непустой/чужой/непроверенный календарь не считать автоматически безопасным.
- Убедиться, что нет второго polling owner. При конфликте webhook/getUpdates остановиться; **не** вызывать deleteWebhook/setupAutomation/установку triggers.
- Зарегистрировать только два test bindings в отдельном private test policy namespace; без real users/history. Source backend остаётся fixture SQLite, не настоящая Google Таблица.
- Подготовить приватный dry-run с точными resource/event IDs, временем и адресатами, ownership/ETag и anticipated API operations. Только после этого запрашивается/применяется разрешение на конкретные записи/отправки; общий `+` не считать отменой прежнего запрета реальных операций.

## Предлагаемый ограниченный write/send сценарий для последующего согласования

- Два synthetic cases: approve и reject. Создание не более двух **явно тестовых** предварительных events, вне обеда в одном будущем рабочем окне; преподавательское расписание не импортируется и не подменяется fake production completeness.
- Один conditional confirm PATCH, один conditional reject DELETE; финальный cleanup второго event только по надёжному test ownership + актуальному fingerprint/ETag. Не более двух DELETE суммарно. Перед bootstrap create нужен durable operation checkpoint; использовать существующий Calendar transport и recovery, не blind create после timeout.
- Не более10sendMessage в два разрешённых test chats: до6UI replies (card/review/confirm на2cases) и4business notices. Отправки только synthetic text. При unknown/error не повторять автоматически, результаты отдельно для каждого адресата. Фактическая доставка/прочтение не устанавливаются.
- Короткие bounded getUpdates только test bot, private durable inbox, без raw payload/PII/token в логах. Никакого постоянно запущенного сервера, cloud publication, Apps Script deployment, webhook/trigger изменения.
- Проверить repeat/restart после каждого stage, отсутствие новых events/notice duplicates, original source/event change denial, per-recipient outcome. Fault injection на первом реальном прогоне не выполнять без отдельного согласованного плана; аварийные сценарии уже проверяются локально.

Этот список — **предварительный** объём, не готовый запуск с неизвестными IDs. Реальный harness/bindings/preview формируются после выбора ресурсов. При отсутствии credentials/подтверждённого identity/source/ownership действие останавливается, значения не угадываются.

## Что приёмка не докажет

- SQLite source claim/CAS не является Google Sheets claim/CAS; working Sheets/backend/writer coordination здесь не участвуют. Реальный adapter и участие всех writers нужны до production, отдельная книга/аутентифицированный transport для них ещё не подключены.
- Synthetic busy completeness в test fixture не означает завершённый/проверенный НВГУ import. Нельзя менять `ASSISTANT_CALENDAR_HAS_ALL_LESSONS` у рабочего бота.
- Нет интеграционной проверки реального журнала/grades, email, ChatGPT protected connection, student progress из настоящей книги, lecture attendance sync или скорости реакции стороннего schedule assistant.
- Последующая student cancellation, student agreement на propose, verified orphan/operator recovery и production rollout — отдельные задачи. Назад в review не отменяет уже подтверждённую встречу.

## Результат будущей приёмки

Сохранить без secret/PII: git revision, выбранный test namespace, actual read/write/send outcomes и ограничения, repeat/restart evidence, что удалены только test-owned events либо почему cleanup заблокирован. Отдельно отметить remaining events/unknown sends, source statuses и отсутствие delivery proof. Если реальные вызовы не выполнялись, результат только «локально проверено», как сейчас.
