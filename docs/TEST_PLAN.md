# Доступ к локальным отчётам — 28.10.2026

Добавлен tools/report_access.py: ReportReader использует существующую AccessPolicy и trusted ReportLink(report/check/enrollment/student/discipline/group). Link создаётся серверным registry, не из запроса студента. Текущий enrollment должен совпасть с исходной привязкой во всех четырёх полях; переиспользование enrollment ID не переносит чужой отчёт новому студенту. Policy/clock получают свежие значения перед чтением payload и после него. При отзыве/изменении binding/grant запрос блокируется или получает более ограниченную student projection. Нельзя кешировать решение allow как credential.

Студенту доступен только собственный report при действующем enrollment и progress.self; краткий ответ исключает evidence/internal reviewer notes. Преподаватель получает evidence/observations только при student.report для точной discipline/group либо явном full AcademicReadGrant. Full grant владельца включает известную историю, второй преподаватель автоматически его не получает. Unknown/missing/forbidden/corrupt/pending дают одинаковый Report unavailable без private деталей. Loader не вызывается до авторизации. Result check/material identity сверяется с trusted link/хранилищем, неожиданным полям нет выдачи. Выход — detached JSON projection, не ссылка на сохранённый dict.

Поддерживаются существующие channel policy: private confirmed Telegram, scope-bound отдельный ChatGPT context, confirmed email read. Это только разрешение на чтение, не отправка письма или реальный OAuth/TG endpoint. ReportReader не аутентифицирует пользователя; Context, links, policy provider, clock и loader — доверенные runtime adapters. Persistent links/identity registry ещё не реализованы. Повторная проверка уменьшает окно отзыва, но не является транзакцией между registry и отправкой; будущий transport обязан сверять права перед фактической отправкой и применять безопасное форматирование.

13 новых synthetic tests (первый запуск красный до модуля), полный Python **250 PASS**: self/foreign isolation, exact teaching grants, owner full read, revocation/rebind during load, reused enrollment, private/confirmed channel, ChatGPT scope, email read, historical restrictions, pending/version mismatch, detached output и sanitized failures. Node не перезапускался, GAS не менялся (последний101 PASS). Ни реальных student identities, ни выдачи данных, отправок, API calls или записи журнала нет.

| Риск | Защита | Проверка | Остаток |
|---|---|---|---|
| Чужой результат по report ID | current policy до payload | self/foreign и exact grants PASS | Нужен реальный authentication adapter |
| Отозванный доступ к кешу/отчёту | повторная policy перед ответом | revoke и downgrade during load PASS | Сверка перед transport send ещё не подключена |
| Enrollment перепривязан | immutable original relation + current equality | reused enrollment PASS | Нужен durable trusted link registry |
| Внутренние заметки студенту | отдельная минимальная projection | notes/evidence omitted PASS | Утверждённый формат обратной связи ещё не реализован |

Дальше — локальные обработчики запросов/рендеринг, затем защищённые реальные adapters в отдельной среде. Научная semantic evaluation/автопринятие/запись оценок остаются неподключёнными.

---

# Проверка цитат для содержательных наблюдений — 28.10.2026

Добавлен tools/content_evidence.py: принимает Finding от будущего trusted reviewer и проверяет check_id, material_version, submission SHA, requirement index и каждую Citation(part,start,end,quote). Offset — Python Unicode character index в извлечённом тексте слайда, не байты/координаты изображения. Part должен существовать, диапазон — быть непустым/в пределах текста, quote — точно совпадать. Stance supported/contradicted требует цитаты; uncertain может явно остаться без неё. Повторные/неизвестные индексы, bool offsets/indices, невалидные структуры и неподходящие версии отклоняются. Findings канонически сортируются, чтобы retry порядка не менял result; evaluator identity включает reviewer version и сами findings.

Наблюдения добавляются отдельно как content_observation со status needs_review. Они не перезаписывают structural met/not_met и не создают grade/pass/credit. Сохранённый local done по-прежнему содержит needs_teacher_review. Quote подтверждает только происхождение фрагмента: не научную правильность, не полноту, не авторство. Подделать содержательный вывод с настоящей цитатой всё ещё возможно — это граница будущей semantic evaluation, а не решённая этим модулем задача.

9 новых synthetic evidence tests (первый запуск красный без модуля) + 2 offline demo tests; полный Python **237 PASS**. Проверены точная quote, выдуманный текст/смещение/part, старая версия работы/критериев, дубли/неизвестные criteria, отсутствие evidence, сохранение без автопринятия, versioned identity и порядок повторов. Реальные студенческие работы, AI API и внешние сервисы не использовались. Node не перезапускался, GAS не менялся (последний101 PASS).

Нет генератора научных выводов/LLM клиента, утверждённого semantic validator, проверки авторства, real account binding, Telegram/mail transport или записи XLSX. Этот этап готовит проверяемый формат наблюдений, а не завершает автоматическую проверку содержания. Приватные quotes/comments не печатать в общие логи и не выдавать без academic policy. Локальный полный сценарий реализован: `python tools/review_demo.py`, отчёт docs/REVIEW_DEMO.md. Он создаёт только искусственные Word/PPTX в памяти, временную удаляемую SQLite, использует явно демонстрационный validator/reviewer, проверяет39/40слайдов и точную quote. Сеть в demo test запрещена моками. Submission revision ID связан с хешем работы. Никакого real semantic grading этот demo не подтверждает; следующим этапом остаётся semantic evaluation.

---

# Привязка структурного критерия к версии — 28.10.2026

Воспроизведён дефект: review_presentation принимал runtime minimum1 вместо указанного40 для той же версии задания. Новые tests сначала показали 3fail/1error. Исправление в tools/assignment_review.py: единственный однозначный slide_count criterion берётся из plan.rules.structural_checks; legacy runtime arguments могут только совпасть с ним, не заменить его. Без machine criterion/с дублями/bool/невалидными индексами — отказ, а не использование догадки или старого default. Оба аргумента теперь можно опустить. evaluator_version=structural-pilot-2, evaluation key включает material version. Старые completed результаты не переписываются; формат Google Sheets/SQLite не менялся.

Контракт одной версии rules: `structural_checks: [{"measure":"slide_count","requirement_index":0,"minimum":40}]`. Index относится к requirements snapshot; запись должен создавать trusted semantic validator после сверки source evidence, не студент/параметр запуска. На этом этапе поддержан ровно один такой criterion. Само добавление поля не доказывает семантическую правильность.

Добавлен tools/material_criteria.py: консервативная suggestion явного minimum-slides из нумерованного draft с source SHA/parser/draft version, номером задания, индексами requirement/paragraph и дословной quote. Поддержаны standalone «минимум N слайдов»/«не менее N слайдов» (в том числе Объём:) и завершающее предложение «Минимальный объем — N слайдов». Неизвестное/несколько совпадений/условные или примерные фразы требуют review; не выводятся проходной балл, научная правильность и авторство. Suggestion всегда requires_review и не превращается автоматически в ValidatedRubrics. Модуль не является полноценным semantic validator.

На локальном upload M04 первая узкая форма не распознала предложение с описанием работы; это явно остановило extraction. После отдельного красного regression test добавлена подтверждённая форма завершающего предложения. Повторная read-only проверка upload нашла minimum40 для ДЗ3, source quote не публикуется. Свежесть файла на Диске не проверялась.

10 новых tests (4 version-binding +6 suggestions), полный Python **226 PASS**. Все проверки исходников/правил синтетические; реальный M04 только локально read-only для подтверждения известной формулировки. Node не перезапускался (последний101 PASS, GAS не менялся). Нет live downloads, реальных работ студентов, grade/credit/mail/deploy.

| Дефект/риск | Причина | Исправление | Тест/результат | Остаток |
|---|---|---|---|---|
| Подмена40 на1 | runtime параметр не сверялся с snapshot | plan-bound machine rule, mismatch refusal | red→green, boundary/regression PASS | Trusted validator должен подтвердить соответствие тексту |
| Неизвестная формулировка | узкий parser не распознавал итоговое предложение | только исследованная форма с source quote | отдельный red→green + M04 local40 | Неизвестное/двусмысленное по-прежнему review |
| Автопринятие по одному числу | count не проверяет содержание | report needs_teacher_review, без grade/credit | прежние regression PASS | Semantic validation и содержание ещё требуют реализации |

Дальше — безопасная фиксация решения о содержательных критериях и полный отчёт с evidence; автоматическое принятие без порога не включать. Неизвестные правила не угадывать.

---

# Локальный структурный пилот ДЗ — 28.10.2026

Добавлен `tools/assignment_review.py`: bounded PPTX reader и отчёт по явно настроенному критерию минимального числа слайдов. Счёт ведётся по presentation manifest и внутренним slide relationships, с проверкой существования и уникальности частей/IDs, а не по числу файлов ZIP. Лимиты: input16MiB, expanded32MiB, 4096parts/1000slides. Внешние slide relationships, traversal, macro parts, encrypted/duplicate archive entries, DTD/entities, повреждённые или неоднозначные ссылки отклоняются. Ничего не распаковывается на диск, не исполняется, не запрашивается в сети. Текст слайдов остаётся private untrusted evidence. Изображения/вложения/notes/внешние ссылки и научное содержание не анализируются.

Отчёт содержит check/material version, submission SHA-256/reader version, evaluator version/configuration digest, наблюдение о числе слайдов и ссылки на slide parts. Скрытые слайды → needs_review; остальные критерии → needs_review. Конфигурация threshold/index задаётся доверенным приложением и должна быть связана с validated rubric; из студенческого текста она не извлекается. Пример M04: minimum40slides является структурным требованием №3, не проходным баллом. Число кадров комикса не приравнивается к числу слайдов. 40 пустых слайдов не доказывают содержательного выполнения.

Весь report всегда `needs_teacher_review`, credit_written=false, без grade/pass/баллов/автозакрытия лекции. Сохранение через MaterialCatalog.finish(done) означает фиксацию локального отчёта, а не принятие работы. Следующий компонент обязан проверять report.status, а не только storage status. Для изменённой работы нужен новый submission revision ID, привязанный к её content hash, чтобы не перезаписывать старый результат.

14 новых synthetic tests, первый запуск красный до модуля; полный Python **216 PASS**. Проверены границы39/40/41, hidden slides, ссылки на slide parts, неверная конфигурация, повреждённый ZIP/0slides, source hash, version binding, внешние/traversal/duplicate slides, DTD, expansion limit, сохранение report без автопринятия и configuration identity. Node не перезапускался, GAS не менялся (последний101 PASS). Настоящие студенческие файлы, Telegram, почта и журнал не использовались, развёртывания нет.

Дальше: source-grounded semantic criteria validation и дополнительные безопасные structural checks по утверждённым требованиям. Форма из30вопросов, научная правильность, авторство, качество40слайдов/10кадров этим пилотом не подтверждены. Внешние формы/ответы, AI service и проходной порог не подключены/не придуманы.

---

# Сквозной процесс материалов — 28.10.2026

Добавлен `tools/material_pipeline.py`: callable MaterialProvider связывает source.read → extract_docx → явно выбранный trusted validator → MaterialRead для существующего MaterialCatalog. Перед prepare/finish файл читается заново; validator должен вернуть source SHA-256, версию extractor, собственную версию, рассмотренные review flags и структурированные criteria. Несовпадение hash/parser/flags, невалидные rules/JSON, ошибка чтения/Word/validator останавливают процесс без fallback. Версии extractor+validator включены в существующее parser_version через digest, схема SQLite не менялась. Сообщения исключений сторонних компонентов не публикуются.

Это проверка привязки, а не реализованный semantic validator: callback является доверенным кодом приложения и должен доказать полноту/корректность требований. Документ не может назначить такой callback или сам подтвердить criteria. Нет permissive/default validator; criteria-not-validated нельзя снять без явного решения trusted validator по текущему source. Само заполнение полей ValidatedRubrics не доказывает научной правильности. Production validator, оценка содержимого работ и live bindings остаются неподключёнными. Ни проходной порог, ни оценки не придуманы.

10 новых сквозных offline tests и 5 tests черновика требований, исходные запуски красные до реализации. Полный Python **202 PASS**. Сквозной тест использует синтетический Word и mocked Yandex metadata/download, затем настоящую временную SQLite: обновлённые требования → новый version-bound check, изменение перед finish → needs_recheck, старый done сохраняется. Дополнительно: stale approval, unresolved warnings, parser/validator versions, network/parser/validator failure и отсутствие default approval. Реальные сервисы и студенческие работы не использовались. Дополнительно read-only обработан ранее загруженный M04: 100 абзацев, без таблиц, успешно выделены четыре раздела; исходник и контакты не сохранялись в Git. Это локальная проверка upload, не свежести файла на Диске. Node не перезапускался, GAS не менялся (последний101 PASS).

| Риск | Защита | Проверка | Остаток |
|---|---|---|---|
| Старые criteria применяются к новому файлу | hash/parser binding, новый validator result при каждом чтении | stale-validation test PASS | Семантика trusted validator ещё не реализована |
| Источник изменён между prepare/finish | повторная загрузка и version-bound результат | end-to-end update test PASS | Нет распределённой транзакции с Диском |
| Не удалось прочитать/валидировать документ | остановка, pending не становится done | failure tests PASS | Нужен операторский review без тихого автоприёма |
| Обновление переписывает прежнюю оценку | immutable local completed history | history test PASS | Реальные оценки/журнал не подключены |

`tools/material_drafts.py` сохраняет source-bound черновик разделов и дословные требования с индексами абзацев. Вид standalone heading: ДЗ №N или Домашнее задание №N, при ожидаемой точной последовательности. Intro хранится отдельно, heading сохраняется, ничего не преобразуется в числовые баллы. Пропуск/дубль/перестановка номеров, пустой раздел или таблицы требуют layout review. Рисунки/прочие flags сохраняются; черновик никогда не является approved rubric и не заменяет semantic validator. На M04 четыре раздела выделены успешно, но научная правильность/полнота/порог принятия не подтверждены автоматически.

Следующий этап — смысловая проверка полноты черновика требований, затем локальный пилот проверки работы без присуждения реальных баллов. Проходной порог остаётся отдельным решением до автоматического принятия; это не блокирует дальнейшую независимую разработку.

---

# Read-only адаптер публичных DOCX — 28.10.2026

`tools/material_source.py`: явно заданные public_key и путь одного DOCX, без поиска по всей папке, токена, журнала XLSX, записи, кеша и фонового запуска. GET metadata → download descriptor → bounded GET bytes → GET metadata. Проверяются type/size/SHA-256/modified, соответствие bytes размеру и SHA, неизменность metadata во время чтения. Смена источника/HTTP/неполные metadata/целостность — остановка без stale fallback и без автоматических повторов. TLS/proxy по умолчанию, redirects запрещены; download только HTTPS домены yandex.ru/yandex.net и поддомены, без userinfo/нестандартного порта. Signed URL/пути/ответы API не печатаются; неожиданные исключения выдаются обобщённо. Это проверка одной загрузки, не гарантия отсутствия будущего изменения файла и не distributed transaction.

8 новых synthetic tests: fresh each call, source drift, integrity mismatch, destination restrictions, no fallback/leak, explicit DOCX reference, bounded GET/timeout и redirect refusal. Начальный запуск красный без модуля, затем полный Python **187 PASS**. Node не перезапускался (GAS не изменён), последний 101 PASS. Реальных HTTP-запросов/скачиваний учебных файлов/отправок/журнала/deploy в этом этапе нет.

Адаптер готов как локальный кандидат, не подключён к боту, расписанию запуска или MaterialCatalog: `read()` возвращает bytes; `extract_docx()` возвращает untrusted text с review. Требуется отдельный semantic rubric validator, утверждённый порог принятия и проверенные привязки. Полный автоматический grading ещё отсутствует. Источник public; перед будущей production-интеграцией нельзя автоматически делать закрытый журнал публичным или менять sharing. Существующий inventory остаётся metadata-only; права его workflow не расширялись.

---

# Локальное чтение DOCX — 28.10.2026

Добавлен `tools/material_docx.py`: ограниченное чтение ZIP/XML без распаковки на диск, сети и исполнения ссылок. Текст абзацев сохраняет границы runs/tab/break; таблицы возвращаются по строкам/ячейкам. Размер входа до 16 MiB, суммарный распакованный размер до 32 MiB, до 1024 entries. Duplicate parts, macro parts, encrypted entries, DTD/entities, повреждённые архивы/XML отклоняются. Рисунки, relationships, дополнительные части и неизвестная разметка помечаются для review. Это частичное извлечение текста, не доказательство полной поддержки Word и не антивирус.

Каждый результат помечен `criteria-not-validated`: текст не превращается автоматически в утверждённый rubric или MaterialRead. Автоматическое подключение к MaterialCatalog намеренно отсутствует до семантической проверки критериев. Источники остаются данными, а не разрешением удалять почту/начислять баллы. SHA-256 относится к полученным bytes, не доказывает свежесть на Диске.

11 synthetic tests PASS (исходный запуск без модуля красный): текст/переносы, таблицы, malformed/missing XML, DTD, links/review, images/revisions, macros, duplicate parts, expanded-size limit и no automatic rubric. Полный Python **179 PASS**. Node не перезапускался: исходники бота не менялись, последний результат 101 PASS. Настоящие файлы/работы в этом этапе не обрабатывались; сеть, почта, журнал, развёртывание не использовались.

Далее: read-only adapter получения актуального файла, семантическое извлечение требований с контролем полноты и утверждение порога принятия; затем связка с версиями и пилот проверки. Автоплюс/оценка/письмо не включены.

---

# Версии материалов и lecture makeup — 28.10.2026

Добавлены 14 synthetic tests material_versions: update before/during check, no stale fallback при ошибке provider, missing/invalid rubric, parser/rule changes, copied rules, version-bound restart/idempotence, completed-result immutability, concurrent refresh CAS, namespace/permissions, JSON NaN rejection и 1→1 lecture-number mapping. Начальные tests красные до модуля; отдельный mapping test красный до свойства lecture_number. Всё исправлено.

Запущено **168/168 Python PASS**, **101/101 Node PASS**. User-upload M04 прочитан, source/контакты в fixtures не копируются. M02 исключён пользователем. Actual grading, periodic source polling, live DOCX parser и XLSX/почта не реализованы/не запускались. Contract: MATERIAL_VERSIONS.md; source requirements: MATERIALS_CATALOG.md §5.

---

# Поиск согласованных ресурсов Диска — 28.10.2026

Добавлено 8 синтетических inventory tests: pagination, точное/пробельное имя, несколько копий без выбора первой, scan limit без ложной полноты, missing, invalid URL/records/duplicates и безопасный CLI. После красного запуска до модуля все **154 Python PASS** (146 прежних + 8). Реальный Actions run 40647021089: folder_readable, journal not_found_in_scan/0 matches, scan_complete=true, no downloads/writes. Conclusion failure означает отсутствие найденного журнала, не неработающий OAuth. Точное имя/расположение запрошено; повторного scan без новых данных нет. Node не запускался (GAS не менялся). Подробности — YANDEX_CONNECTION.md.

---

# Яндекс Диск / GitHub Actions — 28.10.2026

8 новых mock tests для yandex_disk_probe.py PASS; полный Python suite **146 PASS**. Проверены fixed read-only GET, отсутствие/формат токена, redirect отказ, 401/403/network/JSON/size и минимальный sanitized CLI. Реальный manual GitHub Actions run 40645632279 выполнен один раз: runner/checkout SUCCESS, probe **FAIL token_rejected/HTTP401**; secret передан, доступ к Диску не подтверждён. Не считать локальные 146 PASS успешной авторизацией Яндекса. Node в этом этапе не запускался (GAS не менялся). Результат и безопасные дальнейшие шаги — [YANDEX_CONNECTION.md](YANDEX_CONNECTION.md).

---

# Lecture windows — 28.10.2026

Добавлены 22 синтетических теста `tests/test_lecture_windows.py`: 90s boundary, отсутствие кода в repr/audit, restart/retry без продления, два преподавателя/конкурентные SQLite connections, old vs new request, отсутствие повторного code, один local attendance на Student+Session, revoke operator/substitution, source drift/type/groups, AEAD-bound expiry tamper, wrong key/project, приватный каталог, clock rollback, persistent failed-attempt counter, повторное открытие near lecture end и отсутствие gradebook write.

Первый запуск был красным до модуля; дополнительные четыре красных сценария выявили ошибки revoke/expiry tamper/late retry и исправлены. Исправлен flaky test: случайное совпадение substring кода в random window_id не является утечкой; теперь проверяется схема аудита и значения полей.

Запущены: полный Python **138 PASS** (64+16+36+22), текущий Node **101 PASS**. Windows **22 PASS** отдельно также с pinned cryptography 50.0.2 в существующем venv, pip check PASS. Реальных сервисов/аккаунтов/писем/журнала нет. Authentication, public QR/network limiter, identity resolver, live source и XLSX sync остаются будущими проверками, не покрываются этими цифрами. Контракт: [LECTURE_WINDOWS.md](LECTURE_WINDOWS.md).

---

# Полное академическое чтение пользователя — 28.10.2026

Добавлены 6 синтетических tests в test_assistant_access.py и AcademicReadGrant. До добавления класса запуск был красным. После реализации: **36/36 policy, 116/116 Python, 101/101 Node PASS**.

Проверены: пользователь читает расписание второго преподавателя и все известные Enrollment, включая исторические/неактивные; другой преподаватель и студенты не наследуют расширение; отсутствующая запись не разрешается; full read не даёт lecture.open/code.read, personal.read чужих данных, owner/write/send. Сохраняются confirmed/auth/capabilities, интервалы/revoke и ограничения OAuth scopes. Grant может ссылаться только на известного Teacher с корректным интервалом. Реальная привязка аккаунта, registry persistence и внешние каналы не проверены/не подключены.

---

# Академическая policy — 28.10.2026

Запущены `python -m unittest discover -s tests -p 'test_assistant_access.py'` — **30 PASS**; полный `test_*.py` — **110 PASS** (64 НВГУ + 16 XLSX + 30 policy); `node tests/run-current.cjs` — **101 PASS** (64 + 37). Исторические 69/19 в этом этапе не перезапускались, наборы не складываются как уникальные.

Policy tests используют только вымышленные IDs и не подключаются к каналам. Покрыты два преподавателя/общие grants, личные данные/owner denial, собственный progress, exact group+discipline, подтверждение/отзыв binding, активность личностей/Enrollment, омонимы через запрет идентификации по имени, переводы/интервалы, дубли bindings/IDs, malformed inputs, неизменяемые snapshots, scopes ChatGPT, неподтверждённый email, собственная lecture и направленное session-specific замещение, отсутствие расширения report/personal, `зач`/practice/unknown/cancelled, aware timezone и окно, помещающееся в пару/grant.

Сначала зафиксирован красный запуск без модуля; затем четыре красных сценария воспроизвели overlap Enrollment, короткий grant и malformed request/registry types. Исправления прошли регрессию. Это authorization-модель, не подтверждение реальной authentication. Для настоящего транспорта обязательны подпись/identity/scopes, реальный подтверждённый registry и перечитывание его актуального состояния на запрос; `authenticated=True` из клиентского JSON доверять нельзя.

Подробности: [ACCESS_POLICY.md](ACCESS_POLICY.md). Lecture window, persistent registry, `/progress`, email sending и ChatGPT endpoint остаются отдельными будущими тестами; они не включены в 30 PASS.

---

# Локальное чтение XLSX — 28.10.2026

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/run-current.cjs
```

Актуальный запуск: **80/80 Python PASS** (64 НВГУ + 16 XLSX), **101/101 Node PASS** (64 совместимости + 37 консультаций). Новых зависимостей нет. Google/Telegram/Яндекс API не вызываются.

`tests/test_gradebook_read.py` создаёт только синтетические XLSX во временном каталоге: настоящий журнал и студенческие данные в fixtures не включены. Сначала зафиксирован красный запуск без reader; затем дополнительные три падающих теста воспроизвели скрытие данных объединением, неизвестный тип пустой ячейки и утечку непроверенного атрибута state в структурный вывод. Все три дефекта исправлены и покрыты регрессиями.

Проверены: relationship target вместо предположения sheet1.xml; несколько заголовков групп без назначения академической личности; merged anchor и конфликтующие значения; shared/inline strings; формула отдельно от кеша, пустой кеш отдельно от нуля; происхождение shared formula без ложной подстановки выражения; числа/ошибки; даты 1900/1904 и фиктивное 29.02.1900; реальные позиции итогов; скрытые колонки; CLI/repr без значений; external/traversal/DTD/повреждённые ссылки/ограничения размера.

Дополнительно модуль локально прочитал все 22 листа прикреплённой актуальной книги: 3722 формульные ячейки, 759 пустых/отсутствующих кешей, 286 merges, по шесть структурных А/Т/ДЗ-троек на листе. SHA-256 исходного файла до/после чтения совпадает. Формулы не пересчитывались; результаты оценивания не проверялись. Это чтение локальной копии, не проверка Яндекс API, актуальности файла на Диске, прав или записи XLSX.

Reader не проверяет academic identity, не вычисляет успеваемость, не формирует student reports и не открывает `/progress`. Для них отдельные тесты policy/Enrollment остаются следующей задачей. Подробности: [GRADEBOOK_STRUCTURE_AUDIT.md](GRADEBOOK_STRUCTURE_AUDIT.md).

---

# НВГУ / Google transport: актуальные локальные проверки — 27.10.2026

```bash
python -m unittest discover -s tests -p 'test_nvsu*.py'
node tests/run-current.cjs
node --test tests/regression.cjs
node tests/audit.cjs
```

- Python **64 PASS**: parser 8, sync 24, Google/state 24, source/CLI 8. Все Calendar HTTP замоканы; fixtures очищены, настоящий ADC не используется.
- Текущий Apps Script 2.0.5 **101 PASS** (64 существующего поведения + 37 консультаций). Отдельно исторические regression 69 PASS и audit 19 PASS; они пересекаются с текущими и не являются дополнительными уникальными тестами.
- `tests/test_nvsu_google.py`: default readonly без HTTP-мутаций, explicit Calendar ID, страницы/all-day/manual events, whitelist, детерминированный insert/409, If-Match/412, restart после принятого create/update/delete, SQLite lock/target, fresh source/TTL/hash, новые конфликты, защита linked events, явное локальное подтверждение, expired readonly reconciliation. Два ownership-теста сначала падали, затем исправление проверено.
- `tests/test_nvsu_source.py`: реальный исследованный URL недели через mock fetch, HTTP/MIME/UTF8/size/redirect ошибки, wrong week, невозможная дата, переход года, offline CLI без ADC, приватные файлы и отсутствие apply.
- Отдельный venv: установка `requirements-calendar.txt`, `pip check` PASS. SDK/scopes smoke использует AnonymousCredentials и подменённый google.auth.default; credential-файлы и сеть не используются этим smoke.

Следующая интеграционная приёмка — **не запускалась**: Calendar API/ADC/ACL на согласованной sandbox; readonly plan с фактическими данными; резервная копия/ledger; после отдельного разрешения insert/replay/update/delete своего события, 412/тайм-аут/ручные правки, визуальная сверка текущей/соседних недель с источником. Проверить отсутствие дублей и лишних полей. Не изменять рабочие триггеры/бот. Полноту источника для консультаций не включать до приёмки. Инструкции и демонстрационный план: [NVSU_CONNECTION_PLAN.md](NVSU_CONNECTION_PLAN.md).

---

# План тестирования

## Unit tests
- Проверка статуса доступа: `Одобрен`, `Не одобрен`, `Доступ отключён`, пустое значение, неизвестный пользователь.
- Даты: ISO, dd.MM.yyyy, високосный год, 30 февраля, пустое значение, строка с пробелами.
- Разбор команды и текста поручения: фамилии с пробелами, кириллица, пустые поля, delimiter отсутствует.
- Нормализация ID и сравнение chat ID без потери ведущих/знаковых символов.
- Формирование сообщений, ограничения длины Telegram, обработка ошибок API.

## Integration tests (только на тестовых ресурсах)
- Telegram update обрабатывается один раз даже при повторной доставке.
- Устаревший callback не блокирует следующие updates.
- Ошибка обработки одного update не приводит к вечному блокированию очереди.
- Сбой после отправки Telegram, но до записи статуса, не создаёт бесконтрольные дубликаты.
- Отправка поручения одобренному адресату; отклонение неизвестного/неодобренного.
- Приём текста, документа, фотографии; ошибка сохранения Drive.
- Триггеры: опрос, отправка поручений, напоминания, ежедневная сводка.
- Консультация: конфликт времени, повторная проверка слота, отказ владельца, повторная заявка.
- Парсер расписания: текущая/предыдущая/следующая неделя, пустая страница, HTTP 403/500, изменённая разметка, устаревший кеш.

## Acceptance
- Нет доступа к production-данным из тестов.
- Каждый результат внешнего действия подтверждён ответом сервиса и журналом.
- Успешное локальное тестирование не называется подтверждением production-доставки.
- Перед релизом: резервная копия, журнал изменений, инструкция отката и явное подтверждение владельца.

## Этап 1 — регрессии кандидата 2.0.3

Исполняемый локальный suite: `node --test tests/regression.cjs` из корня проекта. Требуется Node.js с built-in test runner (проверено v24.19.0), сторонних пакетов нет. По умолчанию загружается только новый кандидат, транспорт и Google-сервисы заменены in-memory mocks, реальная сеть/секреты не используются. Clock фиксирован на 26.10.2026, Utilities — ограниченный mock +05:00.

Итог текущего запуска: **58 тестов, 58 PASS, 0 FAIL, 0 skipped**. Большинство defect regression-тестов сначала запускались с правильными ожиданиями на неисправленном коде (red), затем повторялись после исправлений (green); промежуточные результаты сохранены в отчёте. Для сверки исходной проблемы можно использовать `RUN_CANDIDATE=src/telegram_assistant_v2_0_2_candidate.gs node --test tests/regression.cjs`: это диагностический запуск, часть тестов нового API заведомо не поддерживается старой версией. Не считать его release suite для 2.0.2.

| Группа / префикс тестов | Что проверяется |
|---|---|
| `consult:` | Повтор после отказа уведомления/append, разные message IDs, невозможная дата и неодобренный пользователь |
| `file:` | Upload до отказа Sheets, accepted-create timeout, временно невидимый файл, download failure, фактический и заявленный размер, public folder refusal, разные сообщения и фото |
| `recurrence:`, `repeat:` | Отказ marker/append, занятый lock, weekly/off/revoked, draft/confirm, owner-only и неверная cadence |
| `command retry:` | `/assign`, `/repeat`, `/broadcast` не дублируют строки после отказа ответа |
| `reply recovery` | Дата/текст дозаписываются после статуса; последующие ручные «Выполнено»/комментарий сохраняются |
| `queue:` | Durable payload до ack, 3 попытки, следующий update, отказ inbox/DEAD/offset, pre-dispatch attempts, explicit replay |
| `delivery:` | Принятый send + отказ записи, UNKNOWN без resends, flush до send, сохранение message_id до SENT, восстановление task trigger |
| `broadcast:` | Frozen/deduplicated recipients, отказ конечного статуса, oversized draft, revoked → SKIPPED |
| `calendar:` | Accepted create + timeout, отказ записи event ID в заявке, all-day конфликт, неверная длительность, конфликт перед create |
| `timetable:` | Stale no-schedule не блокирует fetch, время и предупреждение fallback, отказ append сохраняет старый snapshot |
| `registry:` | ID без имени/контракта не пишет в первый лист; явная схема сохраняет ручной next step |
| `config:`, `schema:`, `compatibility:`, `static:` | Fail closed без ID, blank/reordered headers, дополнительные колонки, неизменность всех CFG headers/SHA исходников, синтаксис и уникальность функций |
| `regression:`, `lock:`, `idempotency:` | Точный допуск и даты, owner inbox и `/add`, истёкший callback, владение lock, отказ при существующих дублях ID |

`node tests/audit.cjs` — отдельные **19 исторических audit probes** на 1.4.3/2.0.2. Они специально подтверждают наличие старых дефектов; PASS этого файла не доказывает исправление нового кандидата.

### Обязательная изолированная интеграционная приёмка — пока не выполнена

1. Отдельный test bot и тестовый Apps Script project, копии Sheets, закрытая папка и отдельный Calendar; никаких ID production. Не загружать несколько snapshots в один project одновременно.
2. Проверить новые Script Properties из отчёта, OAuth/scopes, реальные заголовки и validation (включая «Черновик»); проверить права новых технических листов. Registry включать только с отдельным ID, явным именем листа и проверенным девятиколоночным контрактом заголовков из отчёта.
3. Реальный typed round-trip дат и времени из Sheets, включая Date из getValues; all-day/recurring события, смежные интервалы, +05:00. Повторно проверить owner confirm и доступ студента.
4. Telegram 429/403/timeout после принятого send; сохранённый message_id/UNKNOWN; повтор delivery/confirm, прерывание execution между каждым внешним действием и checkpoint. Никаких auto reset UNKNOWN в READY.
5. Drive inherited sharing, lookup после create timeout, duplicate names, удалённый/перемещённый файл, отсутствие прав, blob limits и квоты Properties; не публиковать файлы и не очищать markers без сверки.
6. DEAD/replay с частичными side effects, payload limit >45000, сбой сохранения журнала, истечение времени execution; политика retention/архивации payload и технических листов.
7. Документированное исследование реального источника НВГУ и обезличенные successful HTML fixtures для prev/current/next недель; до этого не считать text snapshot структурированным расписанием. Проверить изменённую страницу, 200 maintenance, 403/500 и stale fallback.

Тесты выше в текущем этапе **не запускались**. Локальный suite не является подтверждением Telegram-доставки, GAS trigger execution, Google permissions/consistency или готовности к production. Rollout с backup/rollback и явным разрешением — отдельная задача.

Доступность источника НВГУ проверена отдельной read-only HTTPS-попыткой: прокси отказал в CONNECT (`Tunnel connection failed: 403 Forbidden`). HTML не получен, реальные недели/селекторы не подтверждены. Это не результат парсерного или интеграционного теста; T01 требует разрешённого доступа к `tm.nvsu.ru` либо подтверждённых fixtures.


## Продолжение — кандидат 2.0.4 (текущий)

По умолчанию `node --test tests/regression.cjs` теперь загружает `src/telegram_assistant_v2_0_4_candidate.gs`. Результат: **69 PASS, 0 FAIL, 0 skipped**. Раздел о 58 тестах выше — исторический итог 2.0.3. Старые исходники защищены SHA-256; дополнительно фиксируется SHA 2.0.3.

Новые проверки (`navigation:` и `callback authorization:`):

- Два просмотра одного чата сохраняют разные target URL, callback не длиннее 64 байт.
- Другой чат не использует чужую кнопку; отсутствие ссылок не переназначает старые кнопки.
- TTL 1 час, неизвестные/legacy callbacks, повреждённые записи не вызывают fetch; cleanup не затрагивает секреты и активное состояние других чатов; максимум 40 активных ссылок на чат.
- HTTP, чужой host, подменённый URL отбрасываются.
- Renderer передаёт chat ID; обе ссылки prev/next проходят через реальный router в mock-окружении; отозванный доступ блокирует переход.
- Non-private callback и from.id, отличный от chat ID, не меняют выбранное поручение; прежняя проверка expired acknowledgement остаётся зелёной.

Начальный red-запуск: `RUN_CANDIDATE=src/telegram_assistant_v2_0_3_candidate.gs node --test --test-name-pattern='navigation:|callback authorization:' tests/regression.cjs` на первых восьми тестах дал 1 PASS / 7 FAIL. Это диагностический baseline; текущий полный suite содержит дополнительные проверки.

URL `/test-only/week-*` — явно синтетические fixtures навигации, а не предположение об endpoints реального сайта. Проверка реальных недель/HTML/занятий и Apps Script Properties/TTL в живой sandbox не выполнялась. Для T01 сохранён черновик разрешения домена `tm.nvsu.ru`; backend подтвердил сохранение с необходимостью публикации среды. До применения настроек и повторной загрузки HTTP-доступ не считается работающим.


## Консультации — кандидат 2.0.5 (текущий)

Главная команда: `node tests/run-current.cjs` — **101 PASS, 0 FAIL, 0 skipped**: 64 проверки неизменённого поведения из regression suite, явно запущенные на 2.0.5, плюс 37 проверок в `tests/consultations.cjs`. Runner сохраняет exit status любой упавшей группы. Прежние ожидания 30 минут и отсутствия Calendar event до approve заменены согласованными правилами в новом suite, а не отключены ради зелёного результата.

Исторический `node --test tests/regression.cjs` по умолчанию всё ещё проверяет 2.0.4 — 69 PASS. `node tests/audit.cjs` — 19 исторических probes старых snapshots. Не складывать эти пересекающиеся группы в число уникальных сценариев текущего кандидата. Общая fixture вынесена в `tests/helpers/apps-script.cjs`, прежние suites проверены после рефакторинга.

Новые тесты покрывают:

- 20 минут, 317, 09:00–18:00, lunch 11:40–12:20, weekend, края интервалов и booking/cancel ровно за 30 минут.
- Отсутствие полного источника занятий и частично заполненный Calendar: никакой заявки/резерва; обычная занятость и урок блокируют слот.
- Студенческое меню, все страницы свободного времени, bulk чтение календаря, тему, preview/submit/discard, stale tokens, прерывание `/tasks` без вмешательства в поручения.
- Provisional event сразу после submit; стабильный ID, повторные запросы, accepted-create timeout, failure записи event ID в Sheets, запрет второго резерва в тот же интервал.
- Approve обновляет то же событие, повторно проверяет уроки; студент не может нажать чужое owner-действие.
- Только свои заявки; cancel pending/confirmed, foreign event marker refusal, reject удаляет предварительную запись, delete accepted + timeout завершается повтором без дублей уведомлений.
- Durable consumed-topic key: replay темы не становится ответом на поручение и не перезаписывает новый draft.
- Typed Date/date-only/time-only cells: корректное время события и уведомлений без 1899/UTC-сдвига; неизменность 2.0.4 по SHA и всех CFG headers.

До live sandbox остаются: реальные callback bytes/сроки, Telegram UNKNOWN/429/403, Calendar visibility после create/delete и внешние гонки, scopes/права, валидация новых статусов, запрет чужого delete, полный диапазон занятий/праздники и отсутствие дублей импорта. Владелица подтвердила, что занятия есть лишь частично; флаг полной занятости включать нельзя до проверенного импорта из НВГУ. Проверка скорости чтения общего Calendar ассистентом по расписанию не выполнялась.

### Исследование источника НВГУ и read-only preview

`python -m unittest discover -s tests -p 'test_nvsu_preview.py'` — 8 PASS. Parser также запущен на реально загруженных HTTP 200 HTML трёх недель: 13 занятий / explicit no-schedule / 11 занятий. ICS исследован и не импортировался: содержит даты за пределами выбранной недели и не имеет UID. Сравнение выполнено только с искусственным частичным Calendar JSON; реальные события не читались и не менялись. Методика и provenance очищенных fixtures — в `docs/NVSU_SOURCE.md`.


## Уточнённые правила переноса расписания

`python -m unittest discover -s tests -p 'test_nvsu*.py'` — **32 PASS / 0 FAIL** (8 parser/preview + 24 sync-model). Тесты: только time/title/location в видимом payload, объединение строк разных групп/source IDs, конкретная дата/неделя, empty-week без новых событий, update того же ID по изменённым времени/дисциплине/аудитории/дню, повторный импорт без дублей, смена source ID, первичное ручное совпадение, неоднозначность, ручные изменения, scoped removal и preflight после preview.

`apply_sync_plan` испытывается только с MemoryCalendar. Реальный Google adapter отсутствует, list-backed ledger не является durable storage, совместимость/идемпотентность Google API не заявляется. Перед включением импорта нужны реальные sandbox tests и долговременный ledger. Описание: `docs/NVSU_SYNC_RULES.md`.


## Будущая приёмка режима двух преподавателей — требования 28.10.2026

Сценарии пока не реализованы и не запускались:

- Каждый из двух подтверждённых аккаунтов видит своё расписание на дату/неделю; второй teacher_id в параметре не меняет разрешённый источник.
- Отчёт по разрешённой дисциплине/группе доступен, по чужой — запрещён; явно общая группа доступна обоим в установленной области.
- Второй преподаватель не может читать личные задачи/входящие владельца, управлять его консультациями/календарём или использовать глобальные owner-команды.
- Неодобренный аккаунт, поддельный role/teacher_id, чужая/старая кнопка и отзыв доступа не обходят policy. При смене роли кеш не раскрывает прежние данные.
- Студент получает только собственный `/progress`; назначение преподавательской роли не основано на имени/username или тексте сообщения.
- Telegram, email report и API ChatGPT одинаково проверяют предметные права; подтверждённый email без права на отчёт не получает его.
- Для будущей lecture-registration: своё занятие либо явно назначенное замещение, тип lecture; `зач` не генерирует коды. Просмотр расписания не даёт write/send полномочий.

Это критерии для P1/P3/P5/P6, а не результат существующих 80 Python/101 Node тестов.


## Коды по кнопке и замещение — будущие тесты, согласовано 28.10.2026

До реализации не считать эти сценарии покрытыми:

1. Каждый из двух преподавателей открывает код своей действующей lecture, но не чужой без grant; пользователь открывает lecture второго преподавателя по подтверждённому substitution grant, обратное право не возникает.
2. Код действует [opened_at, opened_at+90s): 89.999 секунды — допустим, ровно 90 — отказ. Предварительный просмотр не создаёт окно; истечение не зависит от часов браузера. Нельзя открывать вне пары или при остатке пары менее 90 секунд/неполном расписании.
3. Повторный callback, retry после потерянного ответа и два одновременных уполномоченных запроса возвращают одно окно без смены кода и продления. Повторный показ не продлевает срок; нет полномочий/отозван grant — нет показа кода.
4. Истекший код не работает после открытия нового; один Student+Session получает не более одного присутствия/плюса при нескольких окнах. `зач`, practice, cancelled, unknown type — кода нет.
5. Аудит различает назначенного и фактического преподавателя/actor/grant; код отсутствует в обычных логах/URL/Git. Защищённый повторный показ и rate limiting не раскрывают код студентам или неуполномоченному преподавателю.
6. Отказ/UNKNOWN Telegram не перегенерирует код и не открывает новое окно. Успех отправки не объявляется прочтением. Утренние письма с кодами автоматически не запускаются; зачётные сводки не отменены.
