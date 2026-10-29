# Завершение заявки и независимые уведомления — локальный кандидат

29.10.2026. `tools/consultation_workflow.py`: SQLite **fixture backend**, claim/CAS, Calendar-stage orchestration, atomic source status + two outbox jobs. Не настоящий Google Sheets adapter: никакой рабочей таблицы этот код не читал/не менял. Все Calendar/Telegram calls в проверках — моки. GAS snapshots, 11колонок и статусы сохраняются.

## Порядок

1. Current owner gate, strict original-evidence BoundPlan и preflight существующего executor. Только после успешного preflight local source получает durable claim, привязанный к версии строки/immutable plan.
2. Calendar executor выполняет conditional operation либо возвращает свой durable outcome. Source claim не освобождается по таймеру. Все cooperating local CAS writers обязаны уважать claim; ручной SQL/Google Sheets этим **не блокируются**.
3. Unknown/inflight не финализирует заявку, не создаёт уведомления. Наблюдённый Calendar outcome сохраняется в technical claim; source stage не выдаёт его за отсутствие попытки. Reconcile/read-only используется отдельно, без повторной mutation.
4. `ExecutionEvidence` читается из существующего Calendar journal с current owner gate, plan hash, exact resource/request/operation identity. Произвольное `{'status':'calendar_api_confirmed'}` не является доказательством. `prepare/evidence` в executor добавлены как trusted private APIs, не endpoints.
5. При положительном settled Calendar outcome транзакция source backend сверяет исходную row revision и пишет **только статус/пустую причину**. Approve→«Подтверждена», reject→«Отклонена». Custom decision note и event ID сохраняются, даже при reject, как в GAS. Остальные поля не меняются; canonical локальная строка остаётся11колоночной.
6. Та же SQLite-транзакция создаёт два уникальных notice jobs: student и owner, с business keys от plan/role/entity и сохранёнными subjects. Status/jobs либо фиксируются вместе, либо откатываются. Календарь в этой транзакции не вызывается.
7. Уведомления обрабатываются отдельным явно включаемым шагом. Сбой/unknown первого адресата не препятствует второму; повтор не вызывает Calendar/finalization и не создаёт новых jobs.

`ConsultationWorkflow.advance(...workflow_enabled=False)` и `ConsultationState.notify(...notifications_enabled=False)` выключены по умолчанию. Enabling flags не разрешает real resources. Backend.seed/snapshot/feed — trusted fixture/admin internals, не API студентов/ChatGPT и не импорт настоящего журнала.

## Локальная CAS и восстановление

Private SQLite WAL/FULL, project/owner/source/calendar/bot metadata. `edit(context,id,expected_revision,row)` проверяет текущего владельца, exact original revision и отсутствие claim. Конкурирующие edits не затирают друг друга. Захваченная начальная заявка не меняется через этот метод, включая после финализации: следующие отмены/переносы потребуют отдельного перехода, а не сброса/удаления истории.

Если Calendar подтвердил изменение, но финализация source сорвалась, повтор читает Calendar receipt и повторяет только local status/jobs transaction. Ошибка создания второго notice также откатывает первый и статус. Revoke во время этой транзакции откатывает её; после восстановления прав можно завершить по прежнему receipt без нового Calendar запроса.

Если независимый writer проигнорировал claim и изменил строку, исходная версия не совпадёт: новый текст/получатель не перезаписываются, уведомления не создаются. Уже выполненное Calendar действие **не откатывается вслепую**; требуется сверка. Это моделирует failure boundary, не решает Google cross-service transaction. Перед live use нужен verified source claim/CAS adapter и координация всех writers.

## Business outbox

У notice есть собственный строковый business key; он не маскируется под Telegram update ID. Phase ready→sending фиксируется durable до потенциального send, вместе с payload hash. sender вызывается вне SQLite transaction, только sendMessage/plain text/link previews off. UI replies, уведомления о встрече, Calendar stage и source stage имеют разные outcomes.

Перед каждой отправкой заново проверяются owner права, current confirmed/active binding получателя на тот же entity, актуальная finalized row revision и source stage. Rebinding/revoke/stale row → cancelled, не перенаправление на новый найденный аккаунт. Сохранённый subject не является perpetual permission. Owner reply/notice — не student full access.

- Verified configured bot/private chat/message_id→api_confirmed, но delivered всегда unknown (`None`), read receipt отсутствует.
- Valid API rejection→api_rejected; timeout/malformed/wrong bot→unknown. Ни один из них автоматически не повторяется.
- Process stop/ошибка сохранения результата оставляет sending→inflight_or_unknown. Active peer не объявляется failed; другой notice может обрабатываться независимо. Надёжно отличить orphan нужен отдельный monitor/operator workflow.
- Получатель с unknown outcome не переводится обратно в ready при повторе или restart. Ошибка первого notice receipt не лишает второго попытки; Calendar никогда не вызывается из notice handler.

БД содержит приватные subjects/names/text/callback identifiers в других stores. Не логировать/публиковать/коммитить, coordinated backup обязателен. Ручное удаление DB/сброс sending не восстановление. Отдельный admin retry/rebind/recovery здесь отсутствует.

## Приёмка и предел

`bash tools/check-local.sh`: **548 Python PASS +110 Node PASS**,6offline demos. Новые27tests: CAS/claim/два writers, conditional Calendar outcome→atomic status/jobs, partial SQLite failure/revoke/manual edit, independent notices, restart/parallel sender/interruption/wrong bot/rebind/rejection, no duplicate send, plain outcome dictionary denied. Тесты написаны до реализации; additional red→green: rebind при claim и неверный not_attempted в pending technical status.

[End-to-end пример](CONSULTATION_WORKFLOW_DEMO.md): один mock PATCH с потерянным ответом, read-only reconcile, локальный статус подтверждён, student notice unknown, owner notice API-confirmed. Mock отправок2, реальных HTTP/Google записей/Telegram сообщений0.

Не подключены real owner-consent evidence bridge, authenticated live sources/identity/full-import verifier, Google source claim/CAS/writer coordination, Calendar busy race solution, Google source finalization/notice rollout и sandbox acceptance. Последующая student cancellation/propose agreement, operator orphan recovery и безопасное разделение legacy description status/notes — отдельные задачи. Наличие local CAS не закрывает ни одну из этих Google интеграционных границ.

| Дефект/риск | Причина | Исправление | Тест/результат | Остаток |
|---|---|---|---|---|
| Calendar повторяется из-за сбоя статуса | Общий retry всего сценария | Stage receipt, отдельно source retry | Partial source transaction failure PASS | Реальный Sheet CAS ещё нет |
| Одно уведомление лишает другого попытки | Общий send state/exception | Per-business-key durable jobs/outcomes | Student timeout/receipt failure→owner success PASS | Нет delivery/read proof |
| Дубль при restart/parallel send | Claim после внешнего send | Claim до send, unknown/inflight не retry | Restart/peer/process stop PASS | Verified orphan recovery отдельно |
| Новый студент получил старое решение | Subject переиспользован без identity check | Claim + fresh per-notice same-entity binding | Rebind red→green + dispatch cancel PASS | Real registry ещё не подключён |
| Source показывает not_attempted после Calendar unknown | Technical outcome не синхронизирован | Journal evidence записывается в source claim | Red→green PASS | Это observed outcome, не shared transaction |
| Manual writer проигнорировал source claim | Внешний writer не координируется | Final CAS denies overwrite, no jobs | Manual edit-after-Calendar PASS | Нужна реальная координация writers |
