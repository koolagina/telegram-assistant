# Восстановление очередей: read-only план и проверка квитанций

**Локальный блок завершён; в рабочем боте не установлен.** Пользователь вне компьютера, действий сейчас не требуется. Реальные ресурсы, отправки, календарь и журнал не затрагивались.

## Воспроизведённый дефект и исправление

Три регрессионных теста перед исправлением показали:

1. `DispatchLedger.result` принимал `api_confirmed` без message ID, после чего ReportWorker отмечал update как handled.
2. Квитанция `api_rejected` без error code принималась как корректная.
3. CallbackAckLedger аналогично принимал `api_rejected` без кода.

`tools/report_dispatch.py`: теперь проверяются допустимые phases и комбинации metadata: confirmed требует положительный Telegram message ID и отсутствие error code; rejected — отсутствие message ID и целочисленный error code 100–599; sending/cancelled/unknown — отсутствие обоих. Повреждённая квитанция вызывает DispatchError. Existing worker сохраняет pending/needs_recovery, не готовит новый ответ и не выполняет send.

`tools/callback_ack.py`: проверяется update ID и корректность callback receipt/error code. Invalid receipt не превращается в not_attempted и не повторяется. Валидные схемы и статусы сохранены, migrations/reset/очистка не добавлены.

Эта проверка выявляет неполные/противоречивые поля, **не доказывает подлинность вручную подделанной правдоподобной квитанции**. Приватность/целостность storage и подтверждённый transport остаются обязательными.

## Новый read-only план сверки

`tools/recovery_review.py`, `review_recovery(inbox, ledger, callback_ledger=None, limit=100)`:

- принимает только уже открытые trusted local stores, проверяет schema v1/namespace/bot и cursor;
- читает SELECT только status/phase и operational receipt metadata, не payload/ФИО/сводки/критерии;
- сопоставляет inbox, business dispatch и callback ACK отдельно;
- выдаёт фиксированные issues/actions для проверки оператором, без raw update/message/query IDs, payload hashes и путей;
- возвращает opaque reference и snapshot_hash; они не authentication, не гарантированная анонимизация, не доказательство целостности всей БД и не разрешение на действие;
- ограничен 1–1000 операциями; при превышении complete=false. complete означает полноту bounded metadata scan, не успешное восстановление;
- **не применяет** план: writes/messages=0, ready_for_apply=false всегда. Apply endpoint отсутствует.

Состояния:

| Наблюдение | План сверки | Запрещённый автоматический вывод |
|---|---|---|
| Pending без business receipt | Повторно маршрутизировать только с актуальной policy | «Раз pending, можно отправлять» |
| Pending + валидный confirmed/cancelled | Проверить receipt и согласовать только mark | Повторять send |
| Unknown/rejected | Ручная сверка, без resend | Считать недоставленным и повторить |
| Sending | Проверить активный процесс, не захватывать claim | Объявлять orphan по одному статусу/возрасту |
| Receipt без inbox | Проверить retention или утрату inbox | Восстановить payload догадкой |
| Handled/blocked противоречат receipt | Ручная сверка без send | Тихо исправлять статусы |
| ACK без business receipt | ACK не доказывает отправку, нужны текущие права | Считать сводку отправленной |
| Callback unknown/sending/rejected | Независимая техническая сверка | Повторять message ради ACK |
| Неполная receipt metadata | Invalid, ручная сверка | Закрывать очередь как handled |

Снимки нескольких SQLite-соединений не атомарны при активных workers: план advisory, перед любым разрешённым действием нужен свежий read. Snapshot hash покрывает только выбранные metadata; не user payload, всю историю, real API и внешние процессы. Возраст записей не используется как доказательство безопасного takeover. Raw references при необходимости связываются только внутри доверенного operator runtime; public resolver не добавлен.

## Тесты

24 новых `tests/test_recovery_review.py`: отсутствие модуля до реализации; 3 конкретных FAIL для неполных квитанций до исправления; после — safe refusal и сохранение pending. Также pending/confirmed/unknown/sending, conflicts, orphan receipt, ACK-only и ACK unknown, SQL trace SELECT-only без PAYLOAD, unchanged total_changes, безопасный output, stable references/changing snapshot, bounded incomplete, invalid limit/state/namespace и восстановление реального локального worker после mark failure без повторного send.

`tools/recovery_demo.py`: реальные временные приватные SQLite stores, mock send API, остановка между receipt и mark, mark-only recovery через существующий ReportWorker без loader/send, затем unknown и блокировка без retry. Выход — агрегаты, без пользовательских данных. Добавлен в `tools/check-local.sh`.

Полный `bash tools/check-local.sh`: **797 Python +448 Node PASS, 12 offline демонстраций**. Лог `/tmp/kulagina-recovery-final-check.txt`. Целевой запуск: `python3 -m unittest discover -s tests -p test_recovery_review.py`.

| Дефект | Причина | Исправление | Тест | Итог / остаток |
|---|---|---|---|---|
| Повреждённый confirmed закрывал inbox | Проверялся phase, но не message ID | Строгая DispatchLedger.result metadata validation | Corrupt confirmed→pending | PASS; правдоподобная подделка не выявляется |
| Некорректный rejected считался квитанцией | Не было обязательного error code | Business/ACK validation | Missing error→error | PASS; реальный API не проверен |
| Нет плана сверки отдельных операций | Были только общие counts | SELECT-only recovery review | Cases/privacy/bounds | PASS; apply отсутствует |
| Partial receipt/mark может провоцировать resend | Pending не означает not-sent | Existing recovery проверено сквозно | Actual mark failure/demo | PASS; unknown остаётся ручным |

## Дальше

При будущем подключении — приватный согласованный operator context, consistent backup/retention, inventory единственного poll owner и bounded live-приёмка. Не запускать worker на production ради диагностики: он может отправлять данные или менять очередь. Не удалять SQLite/WAL, claims и receipts, не сбрасывать offset и не применять план автоматически. Нового remote доступа, scheduler, секретов, GitHub relay operations, Apps Script patch/deployment или real-data probe этим блоком не добавлено.
