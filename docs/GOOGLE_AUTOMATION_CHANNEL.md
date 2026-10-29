# Управляемый канал Google через GitHub Actions — 29.10.2026

## Цель и текущие границы

Пользователь попросил подключение, позволяющее ассистенту работать удалённо, без ручного копирования каждого файла Apps Script. **Локальный Windows clasp не даёт этой среде доступа к Google.** Поэтому подготовлен реальный отдельный transport: запрос в Git → GitHub Actions → фиксированные Google API → зашифрованный ответ. Это не новый deployment бота и не cloud environment publication.

Google credential пока не перенесён пользователем в GitHub. Код/тесты/очередь запросов готовы; успешный Google GET ещё не подтверждён этим каналом. Нельзя называть его подключённым до `connected_readonly` и проверки результата. Авторизация на18занятий сохраняется, но Calendar-операции **пока не реализованы этим relay**. Импорт через подготовленный Apps Script runner ещё не подтверждён/отложен пользователем ради настройки автоматического доступа.

Существующий OAuth grant Windows — только script.projects.readonly. Он достаточен для автоматического чтения source, но не записи кода/Calendar/выполнения функций. Для будущей записи потребуется отдельный минимальный Google grant и protected environment; права не повышаются автоматически.

## Что действительно доступно интеграции

Проверено GitHub API: чтение repo/workflows и право Git push доступны. Чтение repository-secrets metadata отклонено403 Resource not accessible by integration. Создание protected environment через API отклонено401 Bad credentials; окружение не было создано этим запросом. Это ответы GitHub, не automatic approval reviewer. Не читать/перехватывать credentials другого провайдера и не менять токены среды для обхода ошибки.

Значение секрета вводит владелец в штатной HTTPS форме GitHub. Actions использует этот secret, ассистент не получает refresh_token/client_secret в чат или через API. Управляемый request-файл нужен, чтобы не зависеть от доступности REST dispatch: разрешённый Git push служит запуском. По изменению обычного кода/README workflow не запускается.

## Однократная настройка чтения на Windows

Подготовлены два проверенных public скрипта: `tools/clasp/prepare-backup.cjs` (общая private-directory/ACL функция) и `tools/clasp/export-google-connection.cjs`. Это не Google login и не upload исходника. Сохранить оба рядом в новой подпапке уже существующей закрытой корневой backup папки.

Пример PowerShell без персональных путей:

```powershell
$googleBridgeRoot = Read-Host 'Полный путь корневой папки KulaginaAssistant-Backup-...'
$googleBridgeTools = Join-Path $googleBridgeRoot 'bridge-tools'
New-Item -ItemType Directory -Force -Path $googleBridgeTools | Out-Null
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/koolagina/telegram-assistant/main/tools/clasp/prepare-backup.cjs' -OutFile (Join-Path $googleBridgeTools 'prepare-backup.cjs')
Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/koolagina/telegram-assistant/main/tools/clasp/export-google-connection.cjs' -OutFile (Join-Path $googleBridgeTools 'export-google-connection.cjs')
$googleBridgePacket = Join-Path $googleBridgeRoot 'google-actions-readonly'
node (Join-Path $googleBridgeTools 'export-google-connection.cjs') --backup-root $googleBridgeRoot --destination $googleBridgePacket
if ($LASTEXITCODE -eq 0) {
    Get-Content -LiteralPath (Join-Path $googleBridgePacket 'connection.json') -Raw -Encoding UTF8 | Set-Clipboard
    Write-Output 'Ключ скопирован. Вставляйте его только в GitHub Secret, не в чат.'
}
```

Exporter читает **только** локальную target config и выбранный default account clasp3, копирует3поля offline OAuth и генерирует key для encrypted backups. Cached access token/другие аккаунты/весь user profile не экспортируются. Source/auth файлы не меняются. Symlink/неверный формат/нет refresh_token/существующая output папка — отказ. Перед записью ACL current user+SYSTEM на Windows или0700/0600 на POSIX. Реальные Windows API вызовы ранее проверены пользователем в backup preparer; новый export пока проверен локальными fixtures, не выполнен на его компьютере.

Затем открыть **Settings → Secrets and variables → Actions → New repository secret**:

- URL: https://github.com/koolagina/telegram-assistant/settings/secrets/actions/new
- Name: **KULAGINA_GOOGLE_READ_CONNECTION_V1**
- Secret: Ctrl+V из подготовленного clipboard, затем Add secret.

Это credential package, не код проекта. **Не вставлять его в чат, issues, repository files, скриншоты или workflow inputs.** Не загружать connection.json/client_secret/.clasprc в чат. После сохранения можно очистить текущий clipboard `Set-Clipboard -Value ''`; это не гарантирует удаления истории clipboard. Сохранить local private packet: ключ нужен для расшифровки owner backups. При повторе использовать существующий файл, не перезаписывать его ради нового ключа.

## Как ассистент запускает проверки

`.github/workflows/google-assistant-bridge.yml` запускается только по изменению `.github/google-bridge/request.json` на main или вручную workflow_dispatch. Входы — ограниченный operation enum и необязательный публичный ключ получателя; Script ID/Google credentials/произвольные URLs не принимаются из request. Timestamp24ч/nonce/schema/main/repo guard проверяются отдельно. Нет schedule/PR triggers/deploy-on-push.

Операции:

| Операция | Google capabilities | Статус |
|---|---|---|
|verify|OAuth refresh/scope verification + projects.getContent|Готова, ждёт reader secret|
|review_legacy_patch|То же чтение + offline diff/encrypted backup|Готова; no Google writes|
|apply_legacy_patch|Только2reviewed source fixes, полный8file payload|Подготовлена, **заблокирована без protected env/write grant/отдельного разрешения на код**|
|Calendar/import18/Apps Script run|Не представлены в enum|Пока не включены; не выдавать за готовые|

Ассистент создаёт новый nonce/issued_at и public receiver key в request, проверяет изменения, коммитит/push. Отдельный checkbox Run workflow пользователю не нужен для таких запросов. Старые/неизвестные/fork/non-main запросы не выполняются. Read concurrency отменяет устаревшее чтение, write concurrency не отменяет начатую запись; каждый job имеет короткий timeout.

## Секреты, исходники и шифрование

`tools/google-actions-bridge.cjs` делает native HTTPS запросы только к fixed Google OAuth/Apps Script endpoints и fixed GitHub environment metadata endpoints. TLS default validation, no redirects,20s timeout, no automatic retry. Credential fields не передаются в URLs/logs; ошибки sanitized. Refresh response/tokeninfo scope проверяется: reader не принимает write/cloud/Drive scopes. Google scope projects.readonly сам по себе не привязан к одному Script ID; дополнительное ограничение выбранным проектом реализует relay.

Source целиком нужен для сравнения, но репозиторий/Actions logs публичны. Поэтому source может выходить только в **google-source-encrypted** artifact: AES-256-GCM (12byte nonce/16byte tag), key wrapped RSA-OAEP SHA256 на public recipient key3072бит контроллера. Private key находится только в ignored private workspace state, не Git/Actions. Публичный ключ не является Google credential. В stdout только counts/booleans/digests/status, не source/file names/Script ID/credentials. После download закрытым ключом расшифровываются файлы в private workspace, не в Git.

Шифрование **не удостоверяет отправителя само по себе**. Контроллер принимает только artifact проверенного workflow/run/repo/main/headSHA и сравнивает run ID/fingerprint с безопасным JSON отчётом; не расшифровывает произвольный присланный ciphertext как доверенное Google-свидетельство. Подмена run ID, ciphertext или укороченный GCM tag отвергаются. Snapshot остаётся источником на момент чтения, не доказательством active deployed version.

Owner backups/diff отдельно encrypted на random backup key из local packet. Raw source/refresh tokens/клиентские credentials не являются artifacts. Retention7days; local original backup и packet/key сохраняются владельцем. Потеря controller private key делает старый source artifact недоступным, но можно запросить новое чтение на новый public key; Google credential от этого не теряется.

## Условия будущего изменения кода

Нужен protected environment **google-assistant-production** с required owner reviewer и selected branch policy ровно main (branch, не tag). Worker сам проверяет protection metadata; если API/правило недоступно — блокирует, не ослабляет guard. Автоматическая настройка environment не удалась401; до ручной настройки write path остаётся нерабочим. Не создавать write secret как repository secret.

Только внутри этого environment: **KULAGINA_GOOGLE_WRITE_CONNECTION_V1**, отдельный Google grant script.projects (без default broad clasp scopes/Calendar/Drive/cloud-platform). Данный grant **не получен** в этой сессии. Reader secret остаётся readonly. Owner environment approval — техническая защита, не замена конкретному согласию пользователя на изменение source. Авторизация18Calendar events не разрешает legacy code hotfix.

Перед PUT worker проверяет все8source hashes из проведённого review, подготавливает только exact approval/ACK patch, сохраняет полный original+candidate в AES-GCM backup. Workflow сначала успешно upload encrypted backup, затем apply с fresh getContent/pin/digest/age/run-ID проверкой. Если original уже совпадает с ожидаемым patched set —0PUT. Изменённый/лишний файл не удаляется: операция отказывает. Manifest и6helpers не заменяются версиями repo/readonly bootstrap. Сам updateContent заменяет полный набор, поэтому payload всегда8файлов.

Один PUT максимум, без retries/auto rollback. API acceptance и финальная GET verification — отдельные поля; google_writes означает попытки RPC, а не гарантированный эффект. При timeout output write_outcome_unknown, следующий review проверяет current source вместо повторного PUT. В Apps Script нет общего atomic compare-and-swap между GET и PUT: параллельное ручное редактирование остаётся материальным риском, поэтому source changes останавливают процесс, но микроскопическое race window не объявляется устранённым. Изменение HEAD может повлиять на triggers без deployment. Новые deployments/triggers/webhook/functions/data/messages не вызываются.

## Проверки и неподтверждённое

13новыхNode tests: readonly/noleak/scopes/context, Google rejection no retry, encrypted review, required protection/pins, uploaded-backup gate/full8preserve, drift/unknown outcome, already applied, cipher tamper, fresh enum request, minimal local export/default profile/no access-token fallback, recipient encryption/cross-run and truncated-tag rejection. Tests red→green; shortened GCM tag отдельно воспроизведён и запрещён.

Полный `bash tools/check-local.sh`: **596Python +214Node PASS**,6offline demos. Новый Google relay пока не выполнял успешных Google API calls; actual encrypted artifact read/decrypt и protected source write требуют отдельной реальной приёмки. Реальная проверка транспорта: [run40894062838](https://github.com/koolagina/telegram-assistant/actions/runs/40894062838), push04c75c5. Requestjob success; readjob ожидаемо остановился connection_not_configured; google_gets0/google_writes0/messages0/source_exposedfalse; writejob skipped. Workflowзарегистрирован/очередь/runnerработают, Googlecredentialещёнеустановлен. Новые runs до readersecret без надобности не создавать. Pipeline success не равен Google connection success.

Если личное OAuth приложение остаётся External/Testing, Google может ограничивать refresh token сроком7дней. Не обещать вечную автоматизацию: status текущего consent приложения не установлен, при expiration нужна штатная повторная авторизация/отдельная настройка consent, без отключения защиты аккаунта. Перевод OAuth consent в Production — отдельная операция, не deployment бота/публикация облачной среды, сейчас не выполнялся.

Отключить reader можно удалением GitHub reader secret/отзывом Google OAuth grant; секреты из GitHub не выдаются обратно в чат. Запись отключается удалением environment write secret/отказом approval. Scheduler отсутствует: постоянного опроса/бесконечной публикации нет.
