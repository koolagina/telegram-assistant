# Исходные данные решения владельца — локальный кандидат

29.10.2026. `tools/consultation_consent.py` и `consultation_bound_worker.py` связывают verified local inbox, показанные владельцу данные, original-evidence BoundPlan, local source claim и существующий workflow. Это fixture SQLite/моки, **не подключённая Google/Telegram интеграция**. Реальные ресурсы не читались/не менялись, полное расписание НВГУ не объявляется импортированным.

## Просмотр и подтверждение

Карточка показывает исходные student/topic/date/status. Owner-only opaque reference включает row version и local booking revision. Нажатие approve/reject читает актуальные source/event/ownership/availability и создаёт OwnerReview: исходная версия строки, fingerprint события, первоначальный local booking, actor, core intent token, показанные student/topic/calendar title и expiry. Не формируется executable plan до финального подтверждения.

Новая клавиатура `bcon:a:*`, `bcon:c:*`, `bcon:x:*`; это references, не credentials. Owner gate выполняется **перед** приватным чтением и после проверок. Final confirm разрешён только тому же authenticated subject. Пересылка/подделка reference не выдаёт права. Старые `con:*` и `/consult_propose` продолжают обслуживаться локальным handler; предложение другого времени не исполняется как перенос.

Финальное нажатие заново читает original source/event/verified hold/current student и занятость. Изменение темы/адресата/времени/заметок/ETag/полноты/прав, expired/cancelled review требует нового просмотра. Первая подтверждающая попытка сохраняет started_at durable; retry не сдвигает consent timestamp или expiry. Source state и Calendar fingerprints не восстанавливаются заново как будто пользователь видел новые данные.

После local core confirm одна source SQLite-транзакция публикует immutable BoundPlan **и** source claim. Вложенный claim использует SAVEPOINT; publication failure откатывает их оба. Core и source — разные private DB: local core plan может остаться после failed publication, но без registry publication не исполним; bounded retry проверяет старую evidence, восстанавливает тот же plan и сохраняет первый timestamp. Orphan core intents/plans не удаляются/не переводятся в ready автоматически; после expiry нужен operator review. Никакой внешней mutation до публикации нет.

Confirmed registry loader — trusted private provider для executor, не public endpoint/LLM tool. Исторический confirmed plan возвращается при повторном confirm после проверки текущего owner/actor, без чтения уже изменённого Calendar или нового исполнения. «Назад» отменяет только draft, не подтверждённую встречу. source claims и jobs не уничтожаются этой кнопкой.

## Worker

BoundConsultationWorker требует совпадение project/bot у private inbox, UI DispatchLedger, source state и явно bound local core. Runtime выбирает либо bound consultation worker, либо прежний unbound worker для этих commands, **не два независимых consumer одних routes**. ReportWorker и другие handlers получают неподдержанные updates deferred/pending; общий production dispatcher/ack/scheduler по-прежнему отсутствует.

- Bcon previews имеют idempotency key из trusted project/bot/update ID/canonical payload hash; retry одного verified update возвращает тот же review, не создаёт новые intents.
- Confirm/cancel idempotent по review token; raw role/actor из callback не принимаются. Context создаётся из strict private numeric Bot API identity.
- Calendar read/pre-consent проверка выполняются **вне SQLite транзакций core/source**. Fresh callback UI DispatchLedger только заново проверяет owner и возвращает подготовленный ответ; не вызывает consent/Calendar handler.
- Legacy proposal handlers сохраняют прежнюю atomic core action receipt. Их доступность не отменяет будущего student agreement.
- `actions_enabled`, `dispatch_enabled`, `workflow_enabled` выключены по умолчанию. Workflow выполняется только отдельным явным флагом и matching local source/port. Уведомления студентов/владельца остаются отдельным шагом, никогда не отправляются неявно из UI dispatch.
- Unknown UI send блокируется, не повторяет consent/Calendar. Mark failure восстанавливается из UI receipt без нового private read/send, даже после revoke. Local source finalization/job outcomes отделены от UI API response/delivery.

`workflow_reviews` — дополнительная private SQLite таблица в существующем fixture source store. Старый четырёхтабличный local store открывается, добавление registry выполняется отдельно, старые source/claim/outbox записи сохраняются. Бэкапы нескольких DB должны быть согласованными, содержимое views/tokens приватно и не для Git/логов.

## Проверка

Полная локальная приёмка: **572 Python PASS +110 Node PASS**. Новые24tests:14registry +10bound worker. Tests first; red→green дополнительная регрессия — current owner gate перенесён перед private review lookup (direct confirm/cancel). Проверены original topic/event/identity, cancelled/expired review, repeated verified update, publication failure/retry timestamp, state restart, current actor, no automatic Calendar action without explicit flag, complete bound workflow, UI unknown/mark failure/revoke, calendar reads вне DB locks, legacy proposal path, unsupported reports deferred.

Настоящие OAuth/scopes, Google source claim/CAS, writer coordination, полнота НВГУ, operator recovery и sandbox rollout пока не проверялись. Прямой bypass registry, импорт старых unbound plans, создание fake consent на реальных ресурсах и выставление полноты из пустого Calendar запрещены. Этот local bridge не снимает ни одного production ограничения.


Актуальная комплексная проверка после safe description fix:577Python/110Node PASS,6offline demos. CONSULTATION_WORKFLOW_DEMO.md теперь проходит synthetic Bot API inbox и этот registry, без ручного создания BoundPlan в demo. Реальная приёмка требует отдельно выбранных ресурсов: CONSULTATION_SANDBOX_ACCEPTANCE.md.
