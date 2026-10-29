# 30.10.2026 — reply-recovery установка разрешена, защищённый маршрут подготовлен

Владелец ответил«да»на конкретное предложение установить recoveryдаты/текста/ссылки в поручениях послеpartialreplyсбоя. Не повторять scopepermission; GitHubprotectedapproval остаётся обязательным. Новые requestoperations review_legacy_reply_recovery/apply_legacy_reply_recovery; workerprepare_reply_recovery/apply_reply_recovery, backupfamilylegacy_reply_recovery_v1. Только поверхexactinstalledfile+queue; другойsource/7filedrift/missingparent/crossfamilybackup отказывают. Exactalreadyinstalled распознаётся безPUT. Сохранены full8encryptedbackupbeforePUT/reviewer/main/freshGET/5minreceipt/unknownnoRetry.3новыхrelaytests red→green; full596Python+258Node PASS,6offline demos. Подготовлен толькоread-onlypreflight; новаяsourceустановка/бизнесданные ещё не подтверждены. Никакого массовогоремонтастарыхстрок, poll/trigger/Telegram/Drive/deploy вызовов этим маршрутом нет.

# Кандидат восстановления частично записанного ответа — 30.10.2026

**Только локальный кандидат, не установлен.** Применим к реально проверенному legacy source после file+queue install, не меняет архивные снимки/кандидат2.0.5/Google ресурсы. Рецепт tools/clasp/legacy-reply-recovery.cjs, review diff patches/legacy-reply-recovery.patch.

## Дефект и конкретное изменение

processMessage_ сначала appendRow в «Ответы», затем отдельно пишет статус/дату/текст/ссылку в «Поручения». Сбой послеappend или послечастичнойпроекции оставляет строку ответа. На повторе исходный alreadyInReplies→return пропускает завершение проекции; очередь затем может отметить updateDONE, хотя поручение неполно.3сценария (сбойколонок7/8/9) сначала воспроизведены red.

Заменён только dedupbranch в processMessage_, добавлен recoverLegacyReply_. Ответ находится по chat+message; более1совпадения или одновременное наличие во«Входящие» требуют сверки. Связь берётся из существующей строки ответа (стабильный taskID+chat), не изтекущегоSELECTED_TASK. Только при1совпадении и статусе«Отправлено»/«В работе»/«Доработка»/«Ответ получен» дописываются пустые дата/текст/ссылка; статус ставится последним. Существующие даты сохраняются. Конфликт текста/ссылки проверяется до первой записи и блокирует восстановление, закрытые/ручные reviewстатусы не меняются. Selectedrow очищается лишь если совпадает с текущей строкой этого же поручения; новый выбор другого поручения сохраняется. Unlinkedreply не привязывается наугад. Legacyfallback«строка-N» не является стабильнымID и требует ручной сверки при восстановлении.

Новый fileupload/replyappend не вызывается в recoverybranch. Бизнессхемы/статусы прежние:9полей ответа/11поручения. Общийреестр отсутствует в legacy и не добавляется; candidate2.0.5 функции реестра не переносятся. Новых листов/свойств/Telegramкоманд нет.

## Тесты

12regressiontests:3исходныхpartialfieldfailures; appendacceptedthenfailure; перестановкастрок+newselection;3закрытыхстатуса; conflictsbeforewrites; duplicatesreply/task/inbox; missingtask/unstablefallback/date; unlinked/denieduser; normal9/11schema/patchscope/guard/syntax; совместная durablequeue recovery→DONE безduplicate.

Полный `bash tools/check-local.sh`:596Python+255Node PASS,6offline demos. Совместимость с реально полученным8files source проверена offline в памяти:1changedmain/7preserved/57globalsбезколлизий/fullsyntaxPASS. Это не liveSheets/Telegram приемка. Googlecalls/writes этого нового патча0. Queue/schema проверены ранее реальнымowner-runsetup отдельно; не приписывать эту проверку новомуrecoveryпатчу.

| Дефект | Причина | Исправление | Тест/результат | Оставшийся риск |
|---|---|---|---|---|
| Ответ есть, проекция неполна | duplicatecheck возвращает до завершения полей | repairmissingfields из сохранённой строки |3red→green+appendfailure, PASS | handlerуведомления ещё не восстанавливаются |
| Replay привязывает к другому выбору | опасно использовать currentselectedrow | стабильныйID/chat сохранённого ответа | reorder/newselection, PASS | исходные legacyкнопки/новыеответы всё ещё используют rowindex |
| Старый ответ стирает ручную проверку | безусловный repair небезопасен | closedstatuspreserve/conflict→review | closed/conflict/duplicate, PASS | manualSheetsedit не участвует вScriptLock/CAS |

## Границы и безопасная установка

- Очередь/poller вызывают handler под существующим ScriptLock; напрямую параллельно processMessage_ не запускать. Ручные правки Sheets не защищены lock, атомарногоCAS здесь нет.
- Это ремонт проекции, не exactlyonce всегоhandler: исходная отправка подтверждения/уведомления могла не произойти, а blindresend небезопасен. Уведомления не добавляются в recovery; дальнейший приоритет — отдельный durableoutbox.
- Не исправлена row-based привязка новых ответов/старых кнопок; это отдельный приоритет с typed/stablebinding и тестами устаревшихкнопок.
- Не удаляются/не объединяются существующие дубли и не выбирается неоднозначныйtask. Исходные данные остаются дляоператорскойсверки; через3ошибки существующаяочередь сохраняетDEAD.
- Не добавлена защита входного текста от Sheetsформул; не считать новыйпатч решением этого отдельного риска.
- Relay пока не принимает этот новый патч; разрешение на file+queue не расширять автоматически. Перед liveустановкой требуется согласование данного измененияполей поручений, exactrecipe/full8encryptedbackup/freshsource/reviewerapproval иreadback. Не запускать poll/triggers/deploy/studentmessages длядемонстрации.
