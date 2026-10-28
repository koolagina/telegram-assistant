# Подготовка локального ответа на запрос отчёта — 28.10.2026

tools/report_requests.py реализует только in-process команды `/progress REPORT_ID` и `/report REPORT_ID`, возвращающие PreparedReply. Это не включённые Telegram handler/webhook и не почтовая рассылка. Context/reader даёт trusted runtime, из текста извлекается только opaque report reference. Неверные команды/попытка передать дополнительные identity/role/recipient параметры не вызывают payload loader. `/progress` требует student self purpose, `/report` — teacher student.report; ReportReader получил необязательный purpose, который лишь сужает доступ и проверяется до/после load. Смена роли/отзыв во время запроса не разрешает незаметно сменить тип ответа.

Текст обычный: parse_mode=None и link_preview_disabled=True. Требования/наблюдения не интерпретируются как HTML/Markdown, управляющие/Bidi символы удаляются, длина ограничена3500 UTF-16 units (emoji учитываются), сокращение явно помечается. Заголовок всегда сообщает о необходимости проверки преподавателя; grade/credit не обещаются. Внутренние notes приходят только из teacher projection. Отказ одинаков для чужого/неизвестного отчёта. Повторная подготовка заново проверяет текущие права, не кеширует allow.

PreparedReply.status=prepared означает только локально подготовленный текст, не запись об отправке/успехAPI/доставку. Сохранённый текст не является credential: перед будущей отправкой transport должен заново подготовить ответ и сохранить явно указанные параметры форматирования. Email/ChatGPT adapters не реализованы. Для `/progress` без ID ещё нужен trusted resolver/список собственных работ и безопасная пагинация, не произвольный student ID из команды.

10 новых synthetic tests (первый запуск красный без модуля), полный Python **260 PASS**. Проверены self/teacher ответы, command purpose, чужой/unknown одинаковые ответы, revoke, invalid request без чтения, UTF-16/controls, plaintext markup, retry и downgrade during load. Node не перезапускался, GAS не менялся (последний101 PASS). Реальные сообщения/письма/API/журнал/deploy не выполнялись.

---
