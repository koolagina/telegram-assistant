# Минимальный legacy-кандидат: файлы и durable очередь — 30.10.2026

**Статус: локальный, не установлен; новая запись Google не разрешена.** Это конкретный набор двух патчей к установленному legacy source с уже исправленными accessStatus_/callback ACK. Не замена всем кандидатом2.0.5. [Файловая часть](LEGACY_FILE_RECOVERY_CANDIDATE.md).

## Проверяемый состав

- tools/clasp/legacy-file-recovery.cjs / patches/legacy-file-recovery.patch: только storeFile_, durable SENDING/SAVED receipt, повторное использование подтверждённой ссылки, запрет blind create, conservative quota guard.
- tools/clasp/legacy-update-queue.cjs / patches/legacy-update-queue.patch: замена pollTelegramUpdates и6необходимых helper-функций из уже существующей2.0.5 (withScriptLock_,appendOnce_,updateInbox_,inboxItem_,processInboxItem_,replayDeadUpdate_). Не создаётся второй общий queue engine.
- Две адаптации queue:3попытки в локальной функции без измененияCFG/статусов бизнесопераций; строгая схема технического листа и проверка payload.update_id относительно ключа. Новых Telegram команд нет, replay — только операторский Apps Script helper.
- Реальные8файлов последнего подтверждённого source обработаны только в памяти:1основной файл меняется, остальные7побайтно сохранены;55globalfunctions без коллизий; full syntax PASS. Manifest/триггеры/deployment/свойства ресурсов/календарь/архивы/кандидат2.0.5 не менялись.

## Конкретное изменение Google Sheets после разрешения

Существующие бизнес-листы, заголовки и колонки не перестраиваются. При первом разрешённом poll добавляется только лист «Очередь updates» с6полями: «Ключ», «Статус», «Попытки», «Payload JSON», «Обновлено», «Ошибка». Если лист с таким именем уже имеет другую схему — отказ без перезаписи. Extra owner columns сохраняются. Payload содержит пользовательские данные: лист наследует права существующей книги, это не публичный лог. Не выводить его в Actions/репозиторий/чат.

Сначала append+flush original payload, затем PROCESSING+attempt count, затем handler. Успех DONE; ошибка RETRY, после3попыток DEAD. Только после подтверждённого DONE/DEAD сдвигается Telegram offset; DEAD означает сохранено для ручной сверки, а не успешно обработано. При сбое queue append/flush/terminal persistence offset не продвигается. Если успешный handler уже отмечен DONE, ошибка записи offset не приводит к повторному handler.

Для неизвестного Drive create маркерSENDING не снимается: повторное создание остановлено, update после3попыток остаётся в DEAD, следующие updates продолжаются. Существующий файл не удаляется и не публикуется. Ручной replay не сбрасывает файловый marker и не перематывает offset. Без подтверждения фактического Drive результата автоматического adoption/пересоздания нет.

## Тесты и фактические границы

8queue tests, первые3red на старомpoll: poison/DEAD/следующийupdate; appendfail; DONE+offsetfail; DEADpersistfail; headerconflict; explicitreplay+payloadidentity; интеграция legacyprocess+fileguard (1unknowncreate,1DEAD,1следующийответ); patchscope/collision/syntax. Новые tests/legacy-update-queue.cjs включены в tools/check-local.sh.

Итог полного `bash tools/check-local.sh`:596Python+238Node PASS,6offline demos. Реальные Apps Script handlers/Drive/Sheets/Telegram для этого кандидата не вызывались. Это локальное доказательство сценариев, не real integration acceptance.

## Риски и предварительная приёмка

- Добавление durable queue — изменение процесса обработки и дополнительное хранение оригинальных сообщений в настоящей книге. Требуется отдельное разрешение владельца; ранее разрешённые2sourcefixes не покрывают этот объём. Установка source может повлиять на существующий trigger без нового deployment.
- Нет exactly-once всех побочных эффектов legacyкоманд/уведомлений. Если handler частично выполнился до ошибки, он может повторить непокрытые операции; DEAD ограничивает повторы, не отменяет их. Частичная проекция ответа в «Поручения» остаётся следующим отдельным дефектом.
- Receipt budget — conservative guard, не атомарная квотаGoogle. Очистка/TTL не добавлялись. Старые receipts требуют контролируемого долговременного ledger/архивации; переполнение не разрешает дубли.
- Очередь хранится без автоудаления; нужен контроль роста/прав и read-only обзор DEAD. Не очищать её перед откатом.
- Snapshotbackups/pinchecks обязательны перед liveinstall; source race GET→PUT остаётся. Текущий Google relay не принимает этот новый патч: его writeallowlist пока только старые2fixes. Расширять маршрут и запускать только после отдельного решения по этому конкретному объёму.
- После разрешения подготовить новый full8encryptedbackup, обновитьsource, rereadexactpatch/7filespreserved; затем отдельная ограниченная liveприёмка на согласованных syntheticupdates. Не создавать trigger/не запускать рабочийpoll и сообщения студентам автоматически.

## План отката

Не откатывать данные и не удалять receipts/queue. Перед sourcerollback отдельно read-only проверить PROCESSING/RETRY/DEAD иoffset: возвращение старогоpoll при непросмотренномSENDING может вернуть дубли. Без такой сверки нет автоматического rollback. Надёжное восстановление требует сохранения источника операции, а не очистки состояния.
