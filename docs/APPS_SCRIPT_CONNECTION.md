# Подключение GitHub ↔ Apps Script: сначала резервная копия

Согласован только подготовительный этап: чтение текущего проекта, резервная копия и сравнение. `clasp`3.4.1 установлен/проверен локально, зависимости зафиксированы в `tools/clasp/package-lock.json`. Google OAuth ещё не выполнен, исходники Apps Script не скачаны, запись/deployment/триггеры не запускались. Версия фактически развёрнутого бота неизвестна: заголовок открытого файла не является доказательством deployment.

Важно: **push меняет код проекта**. Даже без нового deployment действующие триггеры могут начать выполнять изменённые функции. Поэтому обычный push сейчас не допускается. Отдельная загрузка helper через неполный набор файлов тоже опасна: Apps Script updateContent заменяет содержимое проекта целиком, может удалить отсутствующие файлы. Не клонировать репозиторий с архивами поверх Apps Script и не подключать push-on-commit.

## Подготовка на Windows

Нужен Node.js20или новее с npm. В PowerShell проверить:

```powershell
node --version
npm.cmd --version
```

Если команды отсутствуют, установить актуальный Node.js LTS с https://nodejs.org/ и заново открыть PowerShell. Права администратора для шагов ниже не нужны; не отключать корпоративные политики. Версии/ошибки можно сообщить в чат без личных данных.

Скачать и просмотреть вспомогательный preparer, затем создать **новую** локальную папку вне Git/OneDrive. Script ID взять в настройках текущего Apps Script проекта, не deployment ID. Значение вводится только локально:

```powershell
$setupFile = Join-Path $env:TEMP 'kulagina-prepare-backup.cjs'
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/koolagina/telegram-assistant/main/tools/clasp/prepare-backup.cjs' -OutFile $setupFile
notepad.exe $setupFile
```

После просмотра выполнить:

```powershell
$scriptId = Read-Host 'Script ID текущего проекта Apps Script'
$backupRoot = Join-Path $env:LOCALAPPDATA ('KulaginaAssistant-Backup-' + [guid]::NewGuid().ToString('N'))
node $setupFile --destination $backupRoot --script-id $scriptId
```

Preparer только создаёт локальные папки/config/инструкцию, не авторизуется и не вызывает Google/clasp. Проверяет explicit Script ID, fresh destination вне Git/symlink ancestors. На Windows до создания auth/bootstrap применяет ACL только текущему пользователю и SYSTEM через whoami/icacls; если ACL не удалось установить, останавливается. Реальная Windows-проверка ещё не выполнена, ACL branch локально проверен моками. На POSIX каталоги0700/файлы0600. Существующие файлы не перезаписываются.

## Однократный вход и скачивание

Preparer выведет **две команды** и сохранит их в `COMMANDS.txt` новой папки. Выполнять по одной:

1. `login --use-project-scopes` с явными auth/bootstrap путями: браузер локального Windows-компьютера, аккаунт с доступом к нужному Apps Script. Локальный временный manifest запрашивает **только `script.projects.readonly`**; исходный Google manifest не меняется. Не добавлять include-clasp-scopes/extra-scopes/ADC и не использовать login без этого manifest: default clasp login запрашивает гораздо более широкие права. Если consent показывает неожиданные права — остановиться и сообщить только их описание. Не отправлять callback URL, OAuth code, token или `.clasprc.json` в чат/Git/скриншотах. Login может сообщить unknown user, поскольку scope профиля не запрашивается; это не подтверждает и не опровергает доступ к проекту.
2. `pull` с явным auth и **новой локальной backup** папкой: скачивает текущий исходный код и manifest, ничего не меняет на сервере. Не добавлять --force/deleteUnusedFiles и не повторять pull в уже просмотренную резервную копию после локальных правок — для нового снимка нужна новая папка.

Если Google требует включить пользовательский Apps Script API: это отдельная от Calendar API настройка https://script.google.com/home/usersettings . Сначала сообщить безопасный текст ошибки; настройки не менять автоматически. В этой сессии API-настройка не проверена/не изменена.

Все OAuth credentials остаются в отдельной папке `credentials`, не внутри `backup`. Частная копия кода тоже может содержать секреты/ID: её нельзя публиковать целиком или слепо добавлять в Git. Резервная копия source не включает Script Properties, пользовательские данные, triggers и весь deployment history — это отдельная инвентаризация без печати значений секретов.

**Локальная авторизация Windows не авторизует Codex cloud.** Сейчас нет подключённого Google identity/Apps Script connector в этой среде. Preparer не пересылает credentials и не настраивает удалённый сервер/Actions. Для дальнейшей работы достаточно сообщить успех/безопасную ошибку, не auth files и не полный терминальный transcript. Способ передачи проверенной копии для сравнения либо защищённого cloud connection выбирается отдельно; автоматический push пока не подготовлен/не разрешён.

## Что проверено и что дальше

- `npm install --ignore-scripts`, clasp3.4.1 version/help, команды login/pull/clone изучены на установленном CLI без авторизации. Node24в среде соответствует требованию>=20.
- На настоящем scope builder установленного clasp offline проверено: use-project-scopes + readonly-only manifest не добавляет default write scopes. OAuth consent/Google GET ещё не выполнялись.
-6Node tests: local-only setup/readonly scopes, no overwrite/Git/ID guards, symlink parent, Windows ACL ordering/failure, private files/explicit auth/project paths/no ADC. Сначала tests red без preparer, затем green. Windows ACL вызовы mocked, реальный PowerShell/Google login не проверены.
- Полный `bash tools/check-local.sh`: **591Python +178Node PASS**,6offline demos.

После успешного pull: сохранить исходную копию, проверить конфликты глобальных функций/manifest/существующих helpers, сравнить её с рабочим кандидатом2.0.5 и подготовить отдельный reviewable allowlist/полный набор проекта. Любую будущую запись отдельно согласовывать с учётом триггеров; bootstrap manifest не переносить в рабочий проект. Нет автоматического deployment, push или смены webhook.
