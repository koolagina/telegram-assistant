# Минимальный кандидат: доступ и просроченные кнопки — 29.10.2026

**Подготовлен локально, в Apps Script не установлен.** Это совместимые правки скачанной1.4-подобной версии, не замена её на2.0.5. Основной кандидат репозитория2.0.5/архивы не изменялись. Переданные working source и встроенный ресурсный ID не скопированы в Git.

## Восемь файлов проверены

Все7JS-файлов совместно компилируются;49глобальных функций, дубликатов имён нет. Во всех проверенных JS entrypoints нет doGet/doPost; manifest webapp settings сами по себе не доказывают наличие действующего публичного endpoint/deployment.

| Переданный helper | Соответствие GitHub | Вывод |
|---|---|---|
| ТестСообщения.js | consultation_owner_message_probe.gs побайтно | Сохранить; повторный send не нужен |
| ТестКалендаря.js | consultation_calendar_smoke.gs побайтно | Сохранить; CRUD/cleanup уже завершены, receipt не сбрасывать |
| ПроверкаКалендаря.js | consultation_calendar_preview.gs побайтно | Сохранить |
| СверкаРасписания.js | nvsu_calendar_snapshot.gs после удаления внешних пробелов/переводов строк | Four-week export уже присутствует в реальном source snapshot |
| ПроверкаЗащитыРасписания.js | nvsu_calendar_protection.gs после удаления внешних пробелов/переводов строк | Сохранить; повторная диагностика не нужна |
| ПроверкаПодключения.js | Другой layout/комментарии;10существующих tests на точном uploaded helper PASS | Функциональных различий в этих проверках не найдено; сохраняется переданный файл, не заменяется repo-версией |

Уже установленная `exportKulaginaNvsuNovemberReadOnly` может быть выбрана в редакторе без копирования нового helper. До сих пор получены только однонедельные результаты; наличие four-week функции не является выполненной четырёхнедельной сверкой.

## Только два изменения

См. [полный минимальный diff](../patches/legacy-access-ack.patch). Он не содержит реальных resource IDs/секретов.

| Дефект | Причина | Исправление | Тест | Результат | Оставшийся риск |
|---|---|---|---|---|---|
| «Не одобрен» разрешает доступ | Поиск substring «одобрен» | Только exact trimmed/lowercase «одобрен» | Negative/ambiguous/approved/owner/disabled/unknown states | PASS на моках | Не установлен; прочие нестандартные пометки не получают доступ и требуют явного решения владельца |
| Просроченная кнопка блокирует очередь | ACK exception прерывает handler до offset | Best-effort ACK с фиксированным безопасным log message | Expired+normal ACK, legacy row selection, unauthorized user, следующий update/повторный poll | PASS на моках | Не установлен; иные бизнес-ошибки намеренно не подтверждаются и могут требовать operator recovery |

Не меняются схемы/статусы Sheets, resource bindings, ID таблицы, календарь по умолчанию, Legacy selected-task row format, offset keys, функции trigger setup или набор функций. Разница основного файла строго ограничена2hunks. Manifest и6helpers сохраняются **побайтно**. Это не закрывает все исторические проблемы вложений/доставок/частичных сбоев и не включает консультации или новые академические функции.

## Безопасная воспроизводимая сборка

`tools/clasp/prepare-legacy-candidate.cjs` принимает только отдельную локальную backup папку и новую private destination. CLI жёстко проверяет SHA-256 всех8изученных файлов, не принимает произвольные hash manifests. Изменённый/missing/добавленный файл требует нового сравнения; не обходить guard. `.clasp.json` допускается как local metadata, но не читается/не копируется в кандидат. Auth/client JSON запрещены как неизвестные файлы. Symlinks/вложенные непроверенные каталоги отклоняются.

В памяти применяются2точные замены; проверяются manifest JSON, collisions и совместная JS syntax, затем создаётся новая private папка и записываются8исходных имён. Для прав папки переиспользуется тот же ACL/POSIX0700/0600 код, что у backup preparer. Ошибка записи не выдаёт prepared=true; возможную частичную output папку не использовать/не перезаписывать автоматически. Оригинальный backup никогда не изменяется. Вывод не содержит кода, токенов или IDs; ready_for_push всегда false, remote_access_performed false. Не создаётся target/auth config, не вызывается clasp/login/push/deploy/run и не меняются Script Properties/данные.

Сборщик также проверен **на всех8переданных файлах** в приватной временной копии: hashes совпали;8файлов на выходе,7побайтно неизменны, изменён только основной файл,49функций. Управляемый runner имеет служебный Git marker у временного корня: в fixture изолирован только этот ancestor; Windows CLI оставляет запрет Git-директорий строгим. Исходные загруженные файлы и оригинальный пользовательский Windows backup не менялись. Сам Windows candidate builder ещё не запущен пользователем; Google-интеграция этим не проверена.

Для локальной подготовки на Windows (если понадобится, без разрешения на Google write) сначала проверить код2скриптов в GitHub. Использовать существующую защищённую корневую папку backup, не папку credentials и не Git checkout:

```powershell
$privateRoot = Read-Host 'Полный путь корневой папки KulaginaAssistant-Backup-...'
$offlineTools = Join-Path $privateRoot 'offline-tools'
New-Item -ItemType Directory -Path $offlineTools -ErrorAction Stop | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/koolagina/telegram-assistant/main/tools/clasp/prepare-backup.cjs' -OutFile (Join-Path $offlineTools 'prepare-backup.cjs')
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/koolagina/telegram-assistant/main/tools/clasp/prepare-legacy-candidate.cjs' -OutFile (Join-Path $offlineTools 'prepare-legacy-candidate.cjs')
node (Join-Path $offlineTools 'prepare-legacy-candidate.cjs') --backup (Join-Path $privateRoot 'backup') --destination (Join-Path $privateRoot 'candidate-legacy-access-ack')
```

Это только подготовка файлов. Не запускать push из этой папки/корня репозитория. Файлы кандидата содержат сохранённый реальный resource ID; не публиковать их в Git/issues/публичных архивах. При ошибке остановиться и сообщить безопасный статус, не credentials/raw source.

## Проверки и границы установки

9новыхNode tests сначала red без implementation, затем green: exact negative access/сохранение owner/unknown/disabled, normal/expired ACK и denied user, continuation/offset/replay, unrelated failure still not ACKed, guarded patch/no reapply, exact8files/7preserved/backup untouched, hashes/unknown files/symlinks/existing output, malformed JSON/collisions, partial disk failure/no readiness/no overwrite. Старые6backup/ACL tests также проходят после выделения общего createPrivateDirectory.

Полный `bash tools/check-local.sh`: **591Python +187Node PASS**,6offline demos. Дополнительно10metadata tests на точном uploaded helper PASS; они не включены повторно в187. Actual integration tests этого нового legacy патча не запускались. Ранее успешные getMe/owner message/Calendar CRUD не являются его приёмкой.

До установки нужны отдельное разрешение владельца на изменение рабочего кода, свежая проверка source snapshot (если изменился — остановка), сохранённый оригинальный8file backup и целевой проект. Нынешняя авторизация clasp запрашивала только чтение; новые write scopes не запрашивались. **Push может повлиять на действующие триггеры без deployment.** Установка, обновление OAuth-разрешений, отключение/создание triggers, setupAutomation/initialize, webhook/poller/Calendar/Sheets operations и rollback в рабочий проект в этом этапе не выполнялись.

Rollback-план для будущей разрешённой установки — восстановить полный проверенный исходный8file набор; не сбрасывать offset/Script Properties/бизнес-данные. Такой source rollback не отменяет уже выполненные внешние операции, поэтому его нельзя называть транзакционным откатом данных. Перед реальным выполнением потребуется свежий reviewable план, здесь только локальный кандидат/diff.
