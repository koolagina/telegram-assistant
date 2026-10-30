# Академические меню и сводки → долговременная очередь

30.10.2026. **Завершено локально; не развёрнуто.** Пользователь вне компьютера, действий сейчас не требуется. В этом блоке не читались реальные данные и не выполнялись Telegram/Google запросы.

## Найденный пробел и исправление

Предыдущие локальные меню и сводки подключались к `TelegramReportAdapter`, но `ReportWorker` не передавал их фабрики при обработке сохранённых updates. Реальный локальный inbox→dispatch путь их не поддерживал. Исправлено в `tools/report_worker.py`: необязательные `overview_factory` и `academic_menu_factory`, проверка callable и передача адаптеру. Оба default=None, dispatch по-прежнему default-off. Новая очередь, новый транспорт или новое разрешение на отправку не добавлены. Existing decision/report маршруты сохранены, SQLite-схемы не менялись.

Используются существующие `TelegramInbox` (store-before-ack), `DispatchLedger` (durable claim и квитанции) и `TelegramReportAdapter` (verified provider/private sender/bot checks). При маршрутизации ответ готовится только для определения обработчика. Непосредственно перед попыткой вызывается `prepare_batch` заново: текущая фабрика строит menu/overview, policy проверяет текущие права и версии. Сохранённый routing reply не отправляется.

- Утрата доступа или устаревшая/чужая кнопка → `cancelled`, без send.
- Изменение разрешённого каталога перед отправкой menu → готовится новый текст; callback старого каталога блокируется.
- Успешный ответ Telegram API → `api_confirmed`, **не подтверждение доставки**.
- Тайм-аут/неизвестный ответ → `unknown`, автоматического повтора нет.
- Принятый send и сбой записи финальной квитанции → `inflight_or_unknown`, pending сохраняется, автоматического повтора нет.
- Квитанция сохранена, mark inbox не выполнен → следующий запуск завершает mark по квитанции без нового чтения payload/проверки старого доступа/send.
- Другой обработчик уже выполняет попытку → `inflight`, без второй отправки.
- Неподдерживаемые/неподключённые команды остаются pending/deferred для других обработчиков, не удаляются.

Это защита от повторов попыток, а не exactly-once доставка. После неизвестного исхода возможен пропуск ответа: требуется сверка оператором, слепой retry запрещён. Разные настоящие Telegram updates считаются разными запросами; повторное намеренное нажатие пользователем может получить новый ответ. Callback acknowledgement (`answerCallbackQuery`) этим блоком не добавлен: он остаётся отдельной транспортной задачей; факт получения callback не означает снятие индикатора Telegram.

## Границы исполнения

Reader/menu/overview factories и их loaders должны выполнять только локальное чтение/вычисления. Fresh preparation выполняется внутри claim-транзакции dispatch ledger. Нельзя подставлять туда сетевой XLSX/Google/provider: remote preload должен выполняться снаружи, со свежестью и provenance, а затем локальная проверка прав/версий. Mock-флаг не разрешает live-отправки. Не гарантируется атомарность между несколькими источниками, policy и Telegram; после локальной проверки может произойти отзыв, а уже принятый API ответ нельзя отозвать этой моделью.

Inbox хранит приватные исходные updates; dispatch ledger — hash payload и метаданные попытки, не текст сводки. Retention/backup/доступ к каталогам остаются обязанностью будущего runtime. Не выводить содержимое SQLite, фабрик, payload или пользовательские идентификаторы в общие логи.

Нельзя запускать Python poller одновременно с рабочим Apps Script poller: требуется единственный согласованный владелец offset. Этот блок не включает scheduler, CLI для live запуска, загрузку секретов, webhook или миграцию рабочего бота.

## Приёмка

18 новых `tests/test_academic_worker.py`: сначала воспроизведён неподдерживаемый factory-параметр worker. Затем actual SQLite inbox/ledger + настоящие локальные menu/overview readers + mock sender проверили:

- menu и direct overview через одну очередь, default-off и deferred;
- revoke между routing и dispatch, изменившийся каталог/кнопка, устаревший журнал, чужой студент;
- новый текст вместо сохранённого routing reply;
- replay, повторное открытие SQLite после рестарта, параллельный worker;
- send timeout, API rejection, ошибка finalize после принятого send;
- ошибка inbox mark и восстановление без нового send;
- ошибка фабрики до claim без потери update;
- callback→сводка→квитанция;
- отсутствие открытых SQLite-транзакций во время mock send.

Расширен `tools/academic_overview_demo.py`: временные приватные SQLite-хранилища, mock menu send, replay без send, mock overview send, revoke и cancelled без send. Вывод — только агрегаты искусственного сценария. Два mock API-confirmed не считаются реальными отправками или доставкой.

Полный `bash tools/check-local.sh`: **713 Python +448 Node PASS, 10 offline демонстраций**. Итоговый лог `/tmp/kulagina-academic-worker-final-check.txt`. Целевой запуск: `python3 -m unittest discover -s tests -p test_academic_worker.py`.

| Дефект/риск | Причина | Изменение / проверка | Итог | Остаток |
|---|---|---|---|---|
| Menu/overview отсутствовали в worker | Фабрики не передавались адаптеру | Необязательные параметры + actual queue тесты | PASS локально | Runtime не подключён |
| Ответ мог устареть до dispatch | Routing не является разрешением | Повторная подготовка через existing ledger | Revoke/catalog PASS | Race после проверки остаётся |
| Повтор send при восстановлении | Partial mark/finalize или потерянный ACK | Existing durable receipt/unknown semantics проверены для новых маршрутов | Restart/mark/unknown PASS | Нужна ручная сверка unknown |
| Два worker отправляют одно | Параллельная обработка pending | Existing claim до send, проверка peer state | Concurrent PASS | Требуется один согласованный poll owner |

Следующий реальный этап: подтверждённая runtime-авторизация, mapping/identity/provenance, единый poll owner и согласованный ограниченный тестовый отправитель/получатель. Пока пользователь без компьютера, ничего из этого не включать и не требовать ручных шагов. Рабочий Apps Script, таблицы, календарь, секреты, relay и триггеры не изменялись.
