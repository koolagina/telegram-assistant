# Локальные кнопки /progress — 28.10.2026

PreparedReply получил immutable rows ReplyButton(label,callback_data): отдельная кнопка открытия каждой работы, назад/далее для страниц, возврат к списку из результата. Это только модель inline keyboard, не вызов Telegram API и не включённый processCallback_ рабочего GAS. Старые текстовые команды сохранены.

Callback ASCII ≤64bytes: progress:p:N для страницы, progress:o:REFERENCE для открытия. Reference — первые32hex SHA-256 digest исходной связи report/check/enrollment/student/discipline/group. Это не секрет/подпись/access token; lookup всегда повторно требует current self policy, read заново проверяет purpose/ownership. Смена связи в trusted registry делает старую reference неразрешимой; если digest совпал у нескольких связей, отказ, не первый match. Reference не включает права владельца и не разрешает открывать чужое при пересылке. Stable hash не является anonymization guarantee или rate limiter; private callbacks не логировать.

prepare_progress_callback допускает только две явные формы, не выполняет произвольные commands/roles/recipients. Каждый click заново готовит ответ через существующий policy-gated flow. Повторный click здесь read-only, не отправляет уведомление и не начисляет баллы. Перед реальным send/answerCallbackQuery будущий transport отдельно проверяет актуальные права/контекст, соблюдает private chat и formatting. Нет реального callback receipt/delivery/expiry/replay journal: это navigation references, не операции записи.

8 новых synthetic tests, первый запуск красный без callback implementation; полный Python **278 PASS**. Проверены own open/back, forwarded foreign denial, revoked binding, replaced check reference, malformed/overlong payload без чтения, self page navigation, forced collision rejection, Unicode longID callback bytes. Node не перезапускался (последний101 PASS), GAS не менялся. TG/почта/журнал/production не затронуты.

Следующий шаг — локальный сквозной сценарий request→page→button→report с настоящим внутренним хранилищем и synthetic identities; реальная интеграция/identity registry persistence/semantic grading остаются отдельно неподключёнными.

---

# /progress без ID и self-only страницы — 28.10.2026

В tools/report_access.py добавлен list_self: Student определяется только по действующему confirmed Context/Binding и progress.self; caller не задаёт student_id. Link registry неизменяемый и trusted, принадлежность enrollment сверяется текущей policy. Чужие links не загружаются и не входят в пагинацию. Порядок стабилен по opaque report id; по5своих links на страницу, page — целое1..1000000, не credential. Page numbers не гарантируют неизменный набор при замене registry; это не cursor snapshot.

В tools/report_requests.py bare `/progress` открывает первую страницу, `/progress page N` — указанную. Собственная работа открывается существующим `/progress REPORT_ID`. Страница показывает только краткие assignment/status и reference, без внутренних observations. Пустая страница явно пуста. Если payload собственного отчёта pending/corrupt/unavailable, показывается только подтверждённая self reference и «результат пока недоступен»; до этого и перед возвратом повторно проверяются актуальная self identity/права. Отзыв или rebind на другого студента во время чтения не возвращают прежнюю страницу. Teacher/group chat/unconfirmed/scopeless Context не получают student list. Общий list всех студентов не реализован.

10 новых tests, исходный запуск2fail/6error до реализации; полный Python **270 PASS**. Проверены bare command, foreign links без чтения/подсчёта, disjoint pages5+2, denied contexts, invalid page безpayload, revoke/rebind duringload, empty page, invalid identity parameters и own pending slot. Node не перезапускался (последний101 PASS, GAS не менялся). Никаких реальных Telegram updates, доставок, почты, записей Excel или deploy.

Это локальный кандидат обработчика, а не установленная команда рабочего бота. Перед transport send заново получать разрешённый ответ; PreparedReply не receipt и не cached authorization. Permanent identity/link storage, real TG authentication/transport, OAuth/email service и semantic grading остаются неподключёнными. Текущий список касается только локальных review reports, не полного ΣА/ΣТ/ΣДЗ учебного журнала.

---

# Подготовка локального ответа на запрос отчёта — 28.10.2026

tools/report_requests.py реализует только in-process команды `/progress REPORT_ID` и `/report REPORT_ID`, возвращающие PreparedReply. Это не включённые Telegram handler/webhook и не почтовая рассылка. Context/reader даёт trusted runtime, из текста извлекается только opaque report reference. Неверные команды/попытка передать дополнительные identity/role/recipient параметры не вызывают payload loader. `/progress` требует student self purpose, `/report` — teacher student.report; ReportReader получил необязательный purpose, который лишь сужает доступ и проверяется до/после load. Смена роли/отзыв во время запроса не разрешает незаметно сменить тип ответа.

Текст обычный: parse_mode=None и link_preview_disabled=True. Требования/наблюдения не интерпретируются как HTML/Markdown, управляющие/Bidi символы удаляются, длина ограничена3500 UTF-16 units (emoji учитываются), сокращение явно помечается. Заголовок всегда сообщает о необходимости проверки преподавателя; grade/credit не обещаются. Внутренние notes приходят только из teacher projection. Отказ одинаков для чужого/неизвестного отчёта. Повторная подготовка заново проверяет текущие права, не кеширует allow.

PreparedReply.status=prepared означает только локально подготовленный текст, не запись об отправке/успехAPI/доставку. Сохранённый текст не является credential: перед будущей отправкой transport должен заново подготовить ответ и сохранить явно указанные параметры форматирования. Email/ChatGPT adapters не реализованы. Актуальное дополнение ниже/выше реализует локальные bare `/progress` и self-only pagination; arbitrary student ID по-прежнему не принимается.

10 новых synthetic tests (первый запуск красный без модуля), полный Python **260 PASS**. Проверены self/teacher ответы, command purpose, чужой/unknown одинаковые ответы, revoke, invalid request без чтения, UTF-16/controls, plaintext markup, retry и downgrade during load. Node не перезапускался, GAS не менялся (последний101 PASS). Реальные сообщения/письма/API/журнал/deploy не выполнялись.

---
