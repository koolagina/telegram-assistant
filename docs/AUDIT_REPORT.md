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

# M04 и версионирование проверок — 28.10.2026

Прочитан пользовательский upload lecture makeup: 4 задания, требования и weights, никаких контактов/документов в Git. M02 не нужен по решению пользователя. Явно подтверждено ДЗ №1→Л1, №2→Л2, №3→Л3, №4→Л4. Более широкая тема не закрывает другие lectures. M04 также содержит старое >60 — глобальное >56 из ТЗ не меняется. ИИ-графика с доработкой разрешена в comic; веса rubric не задают pass threshold.

Добавлено local MaterialCatalog: source/rubric/parser hash revisions, snapshot checks, re-fetch в prepare/finish, no stale fallback, CAS head, needs_recheck при изменении, immutable completed results. 14 synthetic tests, начальный красный импорт и красный lecture mapping test, затем **168 Python / 101 Node PASS**. Это не live watcher/parser/grader: нет обработки настоящих студенческих работ, оценки/плюса/письма. Подробности MATERIAL_VERSIONS.md и актуальный MATERIALS_CATALOG.md §5.

---

# Аудит материалов: 3/5 DOCX — 28.10.2026

Прочитаны инструкция студентам (M01), дистанционная ссылка (M03) и задания шести практик (M05). Вопросы к практикам (M02) и lecture makeup (M04) не скачались из-за HTTP500/503; их содержание/критерии не утверждаются. Источники только в private temporary storage вне Git, без контактов/приглашений в отчётах.

Найдены конфликтующие пороги >60/57 и состав суммы, минимумы отработок и неоднозначные формулировки автомата; сохраняется приоритет нового пользовательского ТЗ (>56, ΣА+ΣТ+ΣДЗ, все обязательные лекции закрыты). Удаление писем из текста не выполняется/не считается доказанным фильтром. Один email может содержать несколько Submission; формы и rubric требуют отдельной mapping/приёмки. Возможные научные/редакторские ошибки примеров не являются основанием обвинять студентов.

Каталог с конкретными форматами шести работ и версиями: [MATERIALS_CATALOG.md](MATERIALS_CATALOG.md). Нет оценивания, писем, новых tests/кода, записи журнала или deployment. Для завершения нужны два недоступных DOCX; повторять неизменные запросы не требуется.

---

# Источник журнала установлен — 28.10.2026

По уточнённой пользователем общей ссылке выполнено только чтение public-resource metadata без OAuth/GitHub secret. Папка содержит 1 XLSX и 5 DOCX, без вложенных папок. XLSX однозначно совпадает с загруженным журналом по нормализованному имени, размеру и MD5 metadata; remote content не скачивался, формулы/данные повторно не читались и не менялись.

Предыдущий personal-files scan не охватывал этот public-resource контекст; больше не требуется спрашивать имя/расположение найденной книги. Журнал и материалы находятся в папке по общей ссылке: рекомендовано отдельное закрытое хранение журнала, но sharing/перемещение не выполнялись. Полный путь/hash/другие filenames не публиковались. Официальный источник metadata — API public/resources. Подробнее docs/YANDEX_CONNECTION.md. Tests не запускались, код/бот/среда не менялись.

---

# Read-only метаданные журнала/материалов — 28.10.2026

Подготовлен manual workflow yandex-resource-inventory.yml и bounded inventory module. Только metadata, fixed API host/GET, без публичных списков имён/путей, downloads и writes; неоднозначность/неполный scan закрыты. 8 новых synthetic tests, весь Python **154 PASS**; GAS/Node не менялись и Node не запускался.

Run [40647021089](https://github.com/koolagina/telegram-assistant/actions/runs/40647021089) завершился за несколько секунд: папка материалов доступна, журнал с загруженным именем не найден среди доступных spreadsheet metadata (0, scan_complete=true). Токен работает; failure относится к отсутствию целевого совпадения. Реальная книга не скачивалась/не менялась. Уточняется точное имя/папка; публичный доступ к студенческому журналу не запрашивается. Docs: YANDEX_CONNECTION.md.

---

# Проверка токена Яндекс Диска через GitHub Actions — 28.10.2026

Добавлены tools/yandex_disk_probe.py, 8 синтетических tests и ручной workflow .github/workflows/yandex-disk-read-check.yml. Один GET запрашивает только type корня Диска, redirect запрещён, секрет/response body не печатаются. Нет автоматического расписания и внешних записей. Локально **146 Python PASS**; Node не перезапускался.

Реальный run 40645632279: runner/checkout SUCCESS, secret передан, Яндекс вернул **HTTP401/token_rejected**. Это integration failure, доступ не готов. Причина неверного/просроченного/отозванного значения не установлена; до обновления GitHub secret повтор не выполняется. Документ: [YANDEX_CONNECTION.md](YANDEX_CONNECTION.md). Cloud environment publication, Почта и учебный журнал не затронуты.

---

# Локальный контроллер lecture-кодов — 28.10.2026

Реализован `tools/lecture_windows.py` с private SQLite WAL/FULL, AES-GCM, stable request recovery и текущей `assistant_access` policy. Одно 90s окно на lecture, единственный local attendance на lecture+student, без продления/слепого recreate после неизвестного delivery. Ключ явно задаётся secure runtime provider; настоящий ключ/registry/transport не подключены.

22 tests PASS. Четыре дополнительных красных сценария выявили и исправили регистрацию после revoke исходного operator/grant, подмену срока в базе и late retry при остатке пары менее 90s. Метаданные окна теперь связаны AEAD; исходные права проверяются и при регистрации. Code/repr/audit не раскрывают plaintext. Source drift и `зач`/unknown/cancelled закрыты; failed-attempt counter хранится локально (5 ошибок на фиксированную минуту для lecture+resolved student).

Полный suite **138 Python PASS**, текущий бот **101 Node PASS**; pinned cryptography 50.0.2 также проверена (22 PASS/pip check PASS). Нет реальных сообщений, формы, attendance в настоящем журнале или deployment. Local receipt = not_synced; стандартные tests не подтверждают API authentication, актуальность registry/source, network limiter или безопасную запись XLSX. Подробнее: [LECTURE_WINDOWS.md](LECTURE_WINDOWS.md).

---

# Уточнение доступа пользователя — 28.10.2026

По явному запросу добавлен AcademicReadGrant в tools/assistant_access.py: полное чтение академических расписаний и студенческих данных проекта, включая известную историю. Стандартные Teacher grants, student self-access и отдельное lecture-замещение не расширяются автоматически. Send/write/private/owner полномочия full read не выдаёт.

6 новых синтетических tests, первоначально красный импорт до класса, затем **36 policy / 116 Python / 101 Node PASS**. Учтены отсутствие reverse grant, история/missing IDs, auth/capabilities/scopes и revoke/expiry. Рабочий бот, реальные аккаунты и внешние ресурсы не менялись. Подробности: ACCESS_POLICY.md и REQUIREMENTS.md, раздел I.

---

# Локальная академическая identity/policy — 28.10.2026

Добавлены `tools/assistant_access.py`, `tests/test_assistant_access.py`, контракт [ACCESS_POLICY.md](ACCESS_POLICY.md). Два преподавателя получают предметные grants; student progress — только self; замещение — отдельное временное право на конкретную lecture без обратного доступа/чужих отчётов. Неизвестные роли/операции запрещены, IDs точные, bindings подтверждаются явно, snapshots неизменяемы. Email/ChatGPT не получают send/write/code полномочий; ChatGPT scopes только сужают серверные grants.

**30/30 policy, 110/110 Python и 101/101 Node PASS**. Четыре дополнительных красных сценария воспроизвели неоднозначное Enrollment, недостаточный срок замещения и некорректные request/registry types; исправлены. Проверены confirm/revoke, пересечения дисциплин/групп, переводы, immutable данные, `зач`/cancelled, временные границы и отсутствие ID-утечки через различающиеся отказы. Только синтетические IDs; реальные accounts/grades/тайные значения не использовались.

Ограничение: это не authentication и не подключённые Telegram/OAuth/email/registry. Context должен создаваться доверенным адаптером, а реестр перечитываться в актуальной версии; старый snapshot сам не обновится после revoke. Надёжные идентификация/хранение/grant administration, карта workbook и каналов остаются работой следующих этапов. `/progress`, lecture-коды, отправка писем и запись XLSX в production не включены. Рабочие ресурсы, snapshots Apps Script и публикация среды не изменены.

---

# Локальный XLSX reader — 28.10.2026

Поверх предыдущего структурного аудита добавлены `tools/gradebook_read.py` и 16 синтетических тестов. Reader только читает локальную копию, не исполняет формулы и не пересохраняет книгу; raw cells остаются в памяти, публичный CLI выводит структуру без имён/оценок. Проверяет relationships, shared strings/formulas, отсутствующий кеш, merged anchors/конфликты, hidden columns, даты Excel, неподдерживаемые структуры и ограничения архива/XML. Типы ошибок не раскрывают cell values.

| Дефект/риск | Причина | Исправление | Тест и результат | Остаточное ограничение |
|---|---|---|---|---|
| Пустая формула становится нулём | Отсутствующий кеш смешивается с числовым 0 | Cell.is_formula/cache_present/value разделены; shared_origin сохраняется | missing cache vs explicit zero: PASS | Формулы не вычисляются, кеш может устареть |
| Потеря значения merged cell | Чтение не опорной ячейки даёт пустоту | Sheet.cell разрешает anchor; конфликтующие непустые дочерние ячейки отклоняются | merged anchor/hidden conflict: PASS | Нет назначения строк академическим личностям |
| Неправильная группа/координата | Имя листа и фиксированная итоговая колонка ненадёжны | Structural layout по содержимому; все группы только кандидаты | two group headers, Y/Z вместо AA/AB: PASS | Полная карта группы/студента требует review и identity |
| Ошибки дат | Разные эпохи Excel и фиктивный leap day | Система 1900/1904, invalid_date для serial60 | 1900 boundaries/1904/fraction: PASS | Исходные даты 2025 года не меняются автоматически |
| Раскрытие/небезопасный разбор | Вывод raw cells, произвольные атрибуты, XML/ZIP | Минимальный summary; state whitelist; DTD/external/path/size checks | CLI privacy/invalid state/unsafe archive: PASS | Raw Python objects содержат ПДн; их нельзя отдавать каналам напрямую |

Начальные тесты были красными до добавления модуля. Затем три дополнительных теста воспроизвели отсутствие проверок merged content, empty unknown cell type и state; после исправления все зелёные. Запущено **80/80 Python** (64 НВГУ + 16 XLSX) и **101/101 Node**. Локальное чтение реального прикреплённого файла: 22 листа, 3722 формульные ячейки, 759 отсутствующих/пустых кешей, 286 merges; checksum неизменна. Это не интеграционный тест Яндекса и не проверка выставленных оценок.

Персональные данные/журнал/токены в код и fixtures не включены. Apps Script snapshots и внешние ресурсы не изменены. `/progress`, предметные роли двух преподавателей, подтверждённая identity и API ChatGPT остаются нереализованными. Подробности: [GRADEBOOK_STRUCTURE_AUDIT.md](GRADEBOOK_STRUCTURE_AUDIT.md), [UNIFIED_ASSISTANT_PLAN.md](UNIFIED_ASSISTANT_PLAN.md).

---

# Подготовка реальной синхронизации НВГУ — 27.10.2026

Актуальный результат: добавлен Google Calendar v3 transport и durable SQLite ledger поверх прежних parser/sync. Реальные Calendar API, Apps Script, Telegram и триггеры не запускались; `.gs` снимки сохранены. Подробные предварительный план, команды и условия подключения: [NVSU_CONNECTION_PLAN.md](NVSU_CONNECTION_PLAN.md). Ниже сохранена история предыдущих этапов; утверждения «адаптера нет» относятся к прежнему состоянию.

| Дефект / недостающая часть | Причина | Файлы и исправление | Тест / результат | Остаточный риск |
|---|---|---|---|---|
| Нет Google transport | Ранее только протокольная модель | `tools/nvsu_google.py`: ADC lazy, readonly default, явный target, пагинация; поля только summary/start/end/location | HTTP-моки: readonly, страницы, all-day, whitelist — PASS | Реальные OAuth/ACL/API не проверены |
| Дубли после неизвестного результата create | Потеря ответа не означает отказ API | Детерминированный event ID, GET/409 recovery; `nvsu_state.py` сохраняет pending/checkpoint перед вызовом | Принятый insert + timeout + reopen — PASS | Eventual consistency требует сверки; не заявляется exactly-once |
| Потеря состояния после сбоя | Прежний ledger в памяти | SQLite WAL/FULL, target/schema bound, lock, PREPARED/APPLYING/COMMITTED; `nvsu_sync.apply_sync_plan` hooks | Reopen create/update/delete, single writer — PASS | Нужны устойчивый диск и согласованный backup |
| Затирание существующих событий | Точное совпадение не доказывает владение | Связь `linked_existing` защищена; явное `confirm_existing_binding` только локально и после fresh/ETag проверки; manual/recurring/notes защищены | Два теста сначала воспроизвели отсутствие подтверждения; после реализации PASS | Решение о передаче конкретных ручных записей ещё не принималось |
| Изменения между preview и применением | Устаревшие source/Calendar snapshots | План hash + срок 15 минут, источник повторно проверяется, ETag If-Match, конфликт preflight | Подмена/истечение, changed source/ETag/new overlap, 412 — PASS | Чужая конкурентная запись между preflight и create не блокируется API |
| Неизвестный эффект после истечения плана | Автоматический replay небезопасен | `reconcile_plan`: только чтение, unresolved блокирует новый план | Expired insert reconciliation, no extra writes — PASS | Неоднозначный результат требует ручной проверки |
| Нет проверенного получения выбранной недели | Нельзя считать HTTP failure пустым расписанием | `tools/nvsu_source.py` использует прежний `parse_week`; проверенные URL, redirect allowlist, HTTP/MIME/UTF8/size; `tools/nvsu_calendar.py` готовит план без apply | 8 source/CLI tests, граница года, no guessed week — PASS | Живой источник в этом этапе повторно не запрашивался |

Результаты: **64/64 Python PASS**; текущий Apps Script кандидат **101/101 PASS**; отдельно исторические **69/69 regression** и **19/19 audit probes**, включая старые дефекты. Наборы Node пересекаются. Зависимости `requirements-calendar.txt` установлены в отдельный временный venv; `pip check` PASS; auth construction smoke с подменённым ADC PASS, реальные credentials не читались.

Предварительная демонстрация: очищенная неделя 02–08.11.2026, 11 занятий; искусственный snapshot с одним точным совпадением → bind_existing 1, create 10, update/delete 0. Это fixture/snapshot, не план настоящего Calendar; применение технически запрещено. Целевой Calendar ID отсутствует; событий и прав не проверяли. До подключения нужны явно выбранная sandbox, разрешённое readonly чтение, свежий фактический план, разбор review, backup и отдельно согласованная проверка записи. Полнота календаря для консультаций пока не подтверждена.

---

# Уточнение переноса занятий — 27.10.2026

Согласованные правила внесены в parser и локальную модель синхронизации; `.gs` candidates и рабочие ресурсы не изменены. Подробный контракт и ограничения — `docs/NVSU_SYNC_RULES.md`.

| Дефект/требование | Причина | Изменение | Проверка | Результат | Остаточный риск |
|---|---|---|---|---|---|
| Лишние сведения в событии | Раньше parser возвращал тип занятия и groups | `nvsu_preview.parse_week`: только имя дисциплины, время и аудитория; `nvsu_sync.event_payload`: whitelist start/end/title/location | Нет groups/description/type в Calendar adapter payload | PASS | Исторические ручные описания сами по себе не очищаются |
| Дубли групповых занятий | Различающиеся групповые строки могли иметь разные IDs | Объединение по времени, дисциплине, аудитории; refs объединяются только во внешнем ledger | Дублирование строки с другим source ID/группой даёт одно занятие | PASS | Неоднозначные разные предметы/аудитории в одно время требуют сверки |
| Неправильная неделя / empty-week | Нельзя интерпретировать чужую неделю или сбой как пустое расписание | Requested date обязателен в CLI; mismatch отклоняется до empty-result; явное no-schedule — занятий нет | Другая неделя при no-schedule, failed/incomplete source | PASS | Актуальность самого HTTP-источника должен обеспечить будущий fetch adapter |
| Create вместо update | Mutable time/название не годятся как единственный постоянный ключ | `nvsu_sync.plan_sync`: внешний event ID ledger, неизменённые вхождения сначала, однозначные изменения обновляют тот же ID | Time/title/room/day change, changed source ID, повторный импорт | PASS | Без связей произвольную ручную запись нельзя безопасно идентифицировать автоматически |
| Риск потери ручных данных | Автоматическое удаление/замена по сходству | Ручные правки/пересечения/неоднозначность → review; delete только неизменённых owned events в проверенной неделе | Manual edit, чужое событие, другая неделя, preflight drift | PASS | Реальный Google adapter/права ещё не испытаны |

Python suite — **30/32 PASS** (8 прежних + 24 sync-model). Добавленные тесты сначала воспроизвели отсутствие sync-модуля; затем отдельные три красных теста выявили риск create/delete при смене source ID или времени ручной записи. Эти случаи исправлены и покрыты регрессиями. Дополнительно два падающих теста выявили удаление ручных заметок в описании owned-события; теперь такие изменения и их появление после preview блокируют применение плана. CLI формирует JSON-план без записи Calendar; обязательны конкретная дата и явные Calendar/bindings файлы. Поля source_refs/event IDs — внутренние связи, не описание события.

`apply_sync_plan` — только протокольная модель с in-memory adapter, не Google-клиент. Она не доказывает долговременность checkpoints или exactly-once API. Реальная синхронизация ещё не подключена к Apps Script; нормальный следующий шаг — перенос протокола в адаптер с durable ledger и проверка в отдельном тестовом Calendar. Рабочие события не создавались, не менялись и не удалялись.

---

# Консультации: кандидат 2.0.5 — 27.10.2026

Согласованы и реализованы в отдельном `src/telegram_assistant_v2_0_5_candidate.gs`: 20 минут, кабинет 317, будни 09:00–18:00, обед 11:40–12:20, запись/отмена минимум за 30 минут и личное подтверждение владелицей. `/consultations` у студента открывает «Записаться», «Мои заявки», «Правила консультаций»; у владелицы сохранён список ожидающих заявок. Полный сценарий, состояния и ограничения — в `docs/CONSULTATIONS.md`.

**Только локальные проверки:** `node tests/run-current.cjs` — **101/101 PASS**, из них 64 прежних проверки неизменяемого поведения на новом кандидате и 37 проверок консультаций. Отдельно исторический suite 2.0.4 — 69/69 PASS, исторические audit probes 1.4.3/2.0.2 — 19 PASS. Эти группы не складываются в число уникальных сценариев. Внешние API Google/Telegram, рабочий Calendar, Telegram и Apps Script triggers не запускались; ничего не развёрнуто.

## Изменения

| Требование/дефект | Причина | Реализация / файлы | Проверка | Результат | Ограничение |
|---|---|---|---|---|---|
| Меню и запись без знания команд | Раньше требовалась текстовая команда | 2.0.5: `sendConsultationMenu_`, `beginConsultationBooking_`, `showConsultationDay_`, `handleConsultationBookingCallback_` — день, слоты, тема, preview, submit | Полный диалог и отказ от отправки; страницы времени; не более 64 байт в callbacks | PASS | Выводится ближайшая неделя; слой реального расписания ещё не подключён |
| Приём по заданным правилам | Были произвольные 10–180 минут и не ограниченные часы | `consultationPolicy_`, `consultationSlotCheck_`, `consultationAvailability_` — фиксированные правила, целиком допустимый интервал, два источника занятости | 09:00/17:40, поздний конец, lunch crossing, weekend, граница 30/29 минут, lesson/Calendar conflict | PASS | Праздники/отпуск отмечать блокирующими событиями; отдельный производственный календарь не реализован |
| Предварительная запись в общем Calendar | Раньше событие появлялось только после approve | `studentRequestConsultation_`, `createCalendarEventOnce_`: provisional title, location «Кабинет 317», тот же стабильный request key и ledger | Повтор, accepted-create timeout, сбой event-ID write, запрет второго резерва на тот же слот | PASS | Это занятое событие с пометкой ожидания, не автоматически одобренная встреча; возможна внешняя гонка между проверкой и create |
| Личное подтверждение и уведомления | Нужно отделять резерв от согласованной встречи | `ownerApproveConsultation_`, `consultationNotice_`, расширенный `sendOnce_(...,extra)` — обновление того же события, owner-only callbacks и outbox | Один event ID до/после approve, новая занятость, student не может approve/reject | PASS | UNKNOWN в Telegram outbox всё ещё требует сверки; реальная задержка чтения другим ассистентом неизвестна |
| «Мои заявки» и отмена | Не было student списка и безопасного удаления | `studentConsultations_`, `studentCancelConsultation_`, `finishConsultationCancellation_`, `notifyConsultationCancellation_` — только свои, deadline, проверка marker перед delete, обе стороны уведомляются | Чужая заявка/чужое событие не меняются; own pending/confirmed, 30/29 минут, delete timeout и повтор | PASS | Последние 10 заявок без пагинации; UNKNOWN delete может требовать replay/ручной сверки |
| Отказ освобождает предварительный слот | Старый reject только менял Sheets | Новый `ownerRejectConsultation_` использует ту же проверенную delete/recovery-цепочку | Reject удаляет одно событие и уведомляет owner/student | PASS | Подтверждённые встречи не отклоняются этой командой; поздняя отмена — через связь с преподавателем |
| Тема не должна попадать в ответы на поручение | Повтор старого message после диалога мог стать обычным ответом | `consumedConsultationTopic_`, `handleConsultationDraftMessage_`, общий mock helper — durable key сообщения темы в «Снимки операций»; чужой/новый draft не затирается | Replay темы после submit и при новом draft; `/tasks` и обычный ответ сохраняют старый маршрут | PASS | Технические снимки содержат тему и требуют политики retention |
| Даты Sheets | Date/time cells могли содержать 1899 и UTC-сдвиг в уведомлениях | `consultationStart_` и timezone formatting уведомлений; raw `new Date(locale string)` не используется | Typed Date и time-only Date: Calendar start и уведомления в Asia/Yekaterinburg | PASS | Реальный Sheets round-trip и исторические значения всё равно требуют sandbox-теста |

## Полнота занятий: уточнение владелицы

Последний ответ: **часть занятий уже внесена, часть нет**. Следовательно, целевой Google Календарь нельзя считать полным расписанием. Для реального включения записи нужно сначала получить недостающие занятия из подтверждённого источника НВГУ и сверить их с уже существующими событиями. Кандидат отказывает в создании заявки без полного источника занятий; тест с частично заполненным Calendar подтверждает это поведение.

В коде предусмотрены `ASSISTANT_TEACHING_CALENDAR_ID` для проверенного полного источника занятий либо `ASSISTANT_CALENDAR_HAS_ALL_LESSONS=true` для полного целевого Calendar. **В текущей ситуации второй флаг включать нельзя.** Никакие значения Script Properties не устанавливались.

После уточнения задачи источник проверен повторно: runtime-доступ восстановлен, HTML и связанные ICS получены с HTTP 200. Реальная структура недель исследована без догадок; обнаружено, что ICS выходит за выбранную неделю и не содержит UID. Реализован отдельный read-only parser/preview `tools/nvsu_preview.py`: 8 unit tests PASS и успешный разбор трёх реальных HTML-ответов (13 занятий, explicit no-schedule, 11 занятий). Подробности — `docs/NVSU_SOURCE.md`. Google Calendar не читался и не менялся; перенос parser в Apps Script и импорт с записью ещё не выполнены.

Импорт с записью пока **не реализован**. Чтение источника и локальное dry-run сравнение с искусственным Calendar уже выполнены отдельно. Следующий шаг — перенести подтверждённые типизированные данные и диапазон/свежесть в адаптер Apps Script и выполнить dry-run против отдельного тестового Google Calendar. Существующие ручные события не удалять и не перезаписывать; уникальные совпадения считать уже имеющимися, неоднозначные пересечения отправлять на сверку. Создание только недостающих занятий должно иметь отдельный стабильный source key/ledger и тест повторного импорта. Подтверждать полноту источника можно только после проверки всех выбранных дней/недель, а не по наличию нескольких событий.

## Сохранность и тестовая архитектура

Версии 1.4.3/2.0.2/2.0.3/2.0.4 не изменены. SHA-256 2.0.4 защищён новым тестом: `4879bc848dffdd15e64d55f6390b024b3a83c4fc64ceb92f17c527beacfca041`. Бизнес-массивы `CFG.*Headers` сохранены. В существующих 11 колонках консультаций добавлены новые значения статусов; фактические validation rules нужно проверить в копии без автоматической миграции.

Reusable mock вынесен в `tests/helpers/apps-script.cjs`; прежний `tests/regression.cjs` проверен после рефакторинга. Новые сценарии — `tests/consultations.cjs`. `tests/run-current.cjs` явно запускает новый кандидат: 64 сохранённых проверок плюс 37 новых. Старые ожидания «30 минут по умолчанию» / «событие только после approve» заменены новыми пользовательскими правилами; они не скрываются как проходящие тесты 2.0.5. Для истории их исходный suite продолжает запускаться на неизменённом 2.0.4.

Тесты сначала дали красный результат на 2.0.4 для отсутствующего меню/политики/отмены, предварительной записи и typed Date, затем стали зелёными на новом кандидате. Диалог отдельно начинался с пяти падающих проверок. Дополнительно воспроизведены и исправлены replay темы и неверный формат уведомления с датой 1899. Ошибки ожиданий, связанные с прежней 30-минутной политикой, отделены от ошибок новой реализации.

Указание AGENTS.md о Calendar уточнено только в пункте 11: владелица явно разрешила предварительный резерв до личного подтверждения. Это не разрешение на production. Реальные секреты/ID, webhook, триггеры и рабочие таблицы не менялись.

---

# Продолжение: кандидат 2.0.4 — навигация недель и callback-авторизация

Подготовлен отдельный `src/telegram_assistant_v2_0_4_candidate.gs`. Версии 1.4.3, 2.0.2 и 2.0.3 не изменены. Бизнес-заголовки Sheets и технические листы из 2.0.3 сохранены. Развёртывание и реальные интеграционные проверки не выполнялись. Следующие разделы отчёта сохраняют историю предыдущих этапов.

| Дефект | Причина | Исправление в 2.0.4 | Тест | Результат | Остаточный риск |
|---|---|---|---|---|---|
| T02: кнопка открывает чужую/другую неделю | Общие `TIMETABLE_PREV_URL` / `TIMETABLE_NEXT_URL` перезаписывались каждым просмотром | `timetableKeyboard_(links,chatId)` выдаёт отдельный случайный token с неизменяемой URL и chat ID; `sendTimetablePage_` передаёт chat ID; `handleWeekCallback_` разрешает только соответствующий чат | Два просмотра одного чата, два чата, обе кнопки через `processCallback_` | PASS локально | Сами ссылки недель пока извлекаются старой эвристикой; реальное значение недели не подтверждено |
| T02: бесконтрольное хранение и устаревшие кнопки | Не было срока действия или связи кнопки с первоначальным адресом | Новый namespace `TIMETABLE_LINK_<token>`: JSON с chatId/url/createdAt/expiresAt, TTL 1 час, максимум 40 живых ссылок на чат; истёкшие/повреждённые записи очищаются; кнопка после вытеснения предлагает снова `/schedule` | TTL, corrupted record, 45 просмотров, отсутствие ссылок и сохранность другого чата | PASS локально | Общая квота Properties зависит от числа чатов; при её исчерпании остаётся явный сбой, авто-очистки других активных чатов нет |
| T02: опасный или потерявший контекст адрес | Старые общие callback не содержат исходный URL; HTTP и чужой host могли попасть в состояние | `validTimetableUrl_`: только HTTPS и точный `tm.nvsu.ru`, ограничение длины, запрет control/backslash/fragment; в callback только token (37 байт); legacy `week:prev/next` не восстанавливаются из глобальных значений | HTTP/чужой host/подменённый record/legacy/неизвестный token | PASS локально | Redirect policy самого `fetchTimetable_` не изменена; TLS/redirects и живые ссылки требуют проверки источника |
| A02: неверный автор callback | Проверялся chat ID, но не from.id и private type | `processCallback_` отклоняет non-private, чужого автора и payload без chat до побочных действий; действующий access gate сохраняется | Чужой автор, group; правильный автор; доступ отозван после выдачи кнопки; прежний expired-callback test | PASS локально | A03 (старые индексные кнопки поручений/selected) пока открыт; реальная Telegram-доставка не проверялась |

## Проверки и сохранность

Сначала добавлено 8 проверок корректного поведения и выполнен red-запуск на 2.0.3: **1 PASS / 7 FAIL**. Подтверждены перезапись адреса, использование чужой кнопки, отсутствие scope/TTL и пропуск callback другого автора. Затем исправлен только отдельный новый кандидат.

Итог: `node --test tests/regression.cjs` — **69 PASS / 0 FAIL / 0 skipped** (58 предыдущих и 11 новых проверок). `node tests/audit.cjs` — прежние 19 исторических audit probes; они продолжают воспроизводить дефекты 1.4.3/2.0.2, не служат подтверждением исправлений 2.0.4. Проверены синтаксис и уникальность имён функций; все исходные бизнес-массивы Headers совпадают с 2.0.2. SHA-256 неизменного кандидата 2.0.3: `8665a6627d3ccd59f3dc8ea871c1bd42768adcbc244a72b4737427b7ab0bf361`.

Все URL вида `/test-only/week-*` в новых тестах — **синтетические адреса**, не найденные endpoints НВГУ. Новая навигация не добавляет и не угадывает selector, параметр недели или API. Хранение кнопки привязано к чату и исходному target URL, а не к Telegram message_id; старую кнопку можно использовать повторно в своём чате до TTL или вытеснения, она открывает прежний адрес. Извлечение самой ссылки и parser занятий остаются непроверенными.

## T01: сетевой блокер и черновик настроек

Доступность публичного URL расписания повторно проверена через HTTPS с включённой TLS-проверкой: отказ прокси `Tunnel connection failed: 403 Forbidden`; HTML не получен. В конфигурации облачной среды обнаружена restricted network policy без `tm.nvsu.ru`. Доступного отдельного web/browser-инструмента для чтения страницы нет.

Через инструмент настройки среды сохранён **только** `network.allowed_domains = ["tm.nvsu.ru"]` в черновик; прежний custom list был пуст, preset package_managers сохранён автоматически. Ответ backend: `status=saved`, `requires_publish=true`. Scripts, secrets, runtime variables и repository membership не менялись. Сохранение черновика не применяет доступ к работающей машине и не публикует среду. Восстановление соединения не подтверждено.

Для применения изменения пользователю нужно проверить и сохранить его в настройках облачной среды, затем опубликовать среду. После изменения runtime следует повторить загрузку и исследовать реальные страницы выбранных недель. До этого **T01 остаётся открытым**, HTML не подменяется выдуманными fixtures, полнота занятий и корректная выбранная неделя не объявляются проверенными. Production-бот, webhook, Apps Script settings/триггеры и реальные Google-ресурсы не изменялись.

---

# Этап 1: кандидат 2.0.3 — критические дефекты

Дата: 26.10.2026. Новый файл: `src/telegram_assistant_v2_0_3_candidate.gs`. Проверки: `tests/regression.cjs`. **58/58 локальных тестов прошли; внешние интеграции не запускались. Развёртывание запрещено до sandbox-приёмки.** Ниже сохранён первичный аудит 2.0.2 как исторический материал: его номера строк и выводы относятся к 2.0.2, а не к новому кандидату.

Обе исходные версии сохранены побайтно; их SHA-256 проверяется тестом. Production, действующий бот, webhook, триггеры, реальные Google-ресурсы и Script Properties не изменялись. Новый кандидат — отдельный файл; не следует одновременно загружать несколько snapshots в один Apps Script project: они определяют одинаковые глобальные функции и CFG.

## Что исправлено и чем подтверждено

| Дефект | Причина | Файл / функции и исправление | Тесты в `tests/regression.cjs` | Результат | Оставшийся риск |
|---|---|---|---|---|---|
| U02: дубли заявок | Случайный ID и запись до потенциально падающего уведомления | 2.0.3: `studentRequestConsultation_`, `messageKey_`, `appendOnce_`, `processMessage_`: ключ по chat/message, поиск перед append под lock; отдельное сообщение остаётся отдельной заявкой | `consult: duplicate delivery…`, `append accepted then throws…`, invalid/denied | Локально исправлено | Дедупликация новых записей не объединяет старые дубли; первоначальные уведомления о заявке всё ещё могут повторяться |
| F01/F02: дубли и потеря файлов | Upload до append, ошибки сохранения превращались в успешный ответ | `storeFile_`, `attachmentFolder_`: постоянное имя по chat/message/file identity в явно заданной закрытой папке, marker до create, поиск существующего файла; ошибки пробрасываются, ответ не отмечается успешно принятым; фактический размер blob проверяется | `file:`: failed append, accepted create timeout, invisible file, download error, oversized metadata/blob, private photo, public folder | Локально исправлены проверенные сценарии | При неизвестном результате и невидимом файле — остановка для сверки; нельзя очищать marker вслепую. Требуются проверка inherited permissions и реального Drive consistency |
| R01/R02: дубли повторов и запуск без подтверждения | Marker после append, нет lock/unique lookup, правило сразу активно | `generateRecurringAssignments`, `…Locked_`, `ownerCreateRecurring_`, новая `ownerConfirmRecurring_`: общий lock, проверка rule/date ID, восстановление marker без повторного append; новые правила — «Черновик», включение `/confirmrepeat ID`; неизвестная cadence пропускается | `recurrence:` marker/task append failures, busy lock, weekly/off/disabled; `repeat:` draft/confirm и denied | Локально исправлено в покрытых сценариях | Некорректная «Последняя выдача», пропущенные периоды и политика catch-up пока не исправлены; legacy «Да» сохраняет прежнее поведение |
| U02: дубли `/assign`, `/repeat`, `/broadcast` | Новые случайные ID при повторе одного сообщения | `ownerAssignTask_`, `ownerCreateRecurring_`, `ownerPrepareBroadcast_` получают message_id, используют детерминированный ID и appendOnce_; новые owner helpers явно проверяют роль | `command retry:` все три команды, отказ уведомления после записи | Локально исправлены дубли бизнес-записей | Не все служебные ответы переведены на durable outbox; реестр может иметь отдельные ошибки синхронизации |
| S01: hardcoded книги и запись при неверной схеме | Встроенные resource IDs, пустые/переставленные заголовки молча принимались | `ss_`, `requiredProperty_`, `tab_`: ID только из конфигурации, нет fallback; существующий обязательный префикс заголовков проверяется до записи в данный лист; дополнительные пользовательские колонки не изменяются | `config:`, `schema:`, `compatibility:` все CFG headers и исходные SHA | Частично исправлен S01 | Это не автоматическая проверка, что введённый ID принадлежит sandbox. Registry теперь также требует явное имя листа и проверенный девятиколоночный контракт; принадлежность книги sandbox проверяет оператор |
| S01/G01: неверный лист реестра и потеря next step | Выбор первого листа и перезапись колонки 7 | `registrySheet_`, `syncGeneralTask_`, `updateGeneralTaskStatus_`: явные имя листа и девять проверенных заголовков, без создания/миграции; next step сохраняется, неоднозначный ID отвергается | `registry:` ID без схемы не меняет первый лист; explicit sheet сохраняет next step | Локально исправлены выбор листа и сохранение поля | Нет durable sync/reconcile, автоматического backfill и project links; ошибки синхронизации всё ещё логируются |
| U03: неполное восстановление ответа | Статус «Ответ получен» исключал дозапись даты/текста/ссылки | `processMessageLocked_`: дозаполнение каждого пустого поля отдельно; очистка соответствующего selected; registry status повторяется; последующие ручные статусы не затираются | `reply recovery…`, completed task preservation | Локально исправлены поля восстановления | Cache уведомления owner по-прежнему не durable; подтверждение получения студенту после partial failure может отсутствовать |
| U01: потеря poison update | Offset уходил вперёд без сохранённого payload; kill не учитывался как попытка | `updateInbox_`, `processInboxItem_`, `pollTelegramUpdates`, `replayDeadUpdate_`: durable payload, попытка до dispatch, DONE/DEAD до offset; операторский replay без перемотки offset | `queue:` poison/next, failed inbox, offset failure, pre-dispatch attempts, failed DEAD save, replay | Локально исправлены проверенные окна потери | Нет автоматической гарантии exactly-once всех side effects; replay требует сверки. Payload >45000 символов останавливает очередь без ack; нет retention/архивации, full payload содержит персональные данные |
| U04: повтор после частичного send | При неизвестном результате выставлялась «Ошибка отправки»; message_id не был долговременным checkpoint | `deliverySheet_`, `sendOnce_`, `sendPendingTasks`, `finishTaskDelivery_`: READY → SENDING → SENT/UNKNOWN, flush до send, message_id сохраняется; известный успех восстанавливает поручение, неизвестный не переотправляется | `delivery:` failed task write, ambiguous send, failed flush, normal repeat, message ID checkpoint и trigger recovery | Локально исправлено в покрытых сценариях | Telegram exactly-once не обещается. При ответе сервера без сохранённого message_id требуется ручная сверка; 429/403 пока также консервативно UNKNOWN, без auto retry |
| B01/B02: дубли адресатов, невозможность recovery рассылки | Адресаты определялись только в confirm, не было результатов по адресатам | `operationSnapshot_`, `ownerPrepareBroadcast_`, `ownerConfirmBroadcast_`: зафиксированный на preview дедуплицированный список, отдельные исходящие ключи, возобновление известных результатов, SKIPPED для отозванного доступа, лимит текста 3000 | `broadcast:` dedup/snapshot, final status failure, oversized, revoked recipient | Локально исправлено в покрытых сценариях | Legacy черновик без snapshot отклоняется; UNKNOWN/SENDING требуют сверки. Общая квота/429 и автоматическое завершение больших рассылок требуют отдельного этапа |
| C02/C03/C01: события после потери ответа / частичной записи, некорректная длительность | Event ID фиксировался после create, без поиска результата; длительность из Sheets не проверялась | `calendar_`, `createCalendarEventOnce_`, `ownerCreateEvent_`, `ownerApproveConsultation_`: отдельный Calendar ID, operation ledger и request marker, поиск созданного события; event ID до конечного статуса; два conflict-check, duration validation, owner guard и outbox уведомления подтверждения | `calendar:` create timeout recovery, consultation write failure, all-day/invalid duration, concurrent conflict before create | Локально исправлены проверенные сценарии | Между последним getEvents и create внешние редакторы всё ещё могут создать конфликт. Нет предложения альтернатив. Даты из реальной Sheets могут быть Date, а не строки; это sandbox-blocker |
| T03: устаревший no-schedule и утрата снимка | Старый STATUS блокировал fetch; clearContents до сохранения | `sendTimetableTo_`, `sendTimetablePage_`, `saveTimetableState_`, `timetableState_`: всегда свежая попытка, stale/time/source на fallback, append-only snapshots; нет вывода «занятий нет» из непроверенного текста | `timetable:` stale no-schedule, fallback timestamp, failed snapshot append | Локально исправлено | T01 (проверенный parser/недели/полнота) и T02 (shared week links) **открыты**; вывод — непроверенный текст страницы, не структурированное расписание |

Все изменения в таблице относятся только к новому кандидату. `tests/audit.cjs` намеренно продолжает проверять исторические 1.4.3/2.0.2 и воспроизводить их дефекты: его 19 PASS не являются доказательством исправления 2.0.3.

## Тесты до исправлений и итог

Для первых трёх групп сначала созданы тесты с корректными ожиданиями и запущены на 2.0.2: 16 тестов, **5 PASS / 11 FAIL**. Среди FAIL — реальные duplicate counts, проглоченная ошибка upload и отсутствие блокировки. Затем только в новой копии внесены исправления: 16/16 PASS.

Дальше каждый новый набор сначала запускался на текущем ещё неисправленном кандидате: schema/команды/recovery — 5 FAIL; durable queue — 5 FAIL; task delivery — 3 FAIL; repeat confirmation/broadcast snapshot — 5 FAIL; Calendar — 4 FAIL; stale/snapshot timetable — 3 FAIL; два дополнительных delivery/broadcast checkpoint — 2 FAIL; trigger checkpoint recovery — 1 FAIL; registry fail-closed/next-step — 2 FAIL. После исправления каждого набора запускался весь накопленный regression suite. Эти числа — последовательные промежуточные запуски, их не следует складывать в число конечных тестов. Удаление встроенных ID из новой копии отдельно подтверждено smoke/static-проверкой; для этого изменения не заявляется отдельный предварительный red-тест.

Итог на Node v24.19.0:

```sh
cd /workspace/telegram-assistant
node --test tests/regression.cjs  # 58 tests, 58 pass, 0 fail, 0 skipped
node tests/audit.cjs             # 19 historical audit probes, 19 pass
```

Регрессионный harness запускает настоящий код кандидата в VM с in-memory Sheets, Properties, Cache, Drive, Calendar, transport и lock. Fault injection доступен до/после append/create, при setValue/flush/send/offset write. Clock зафиксирован на 26.10.2026. Utilities имитирует только используемые форматы и +05:00. Проверяются также доступ «Не одобрен», невозможные даты, owner inbox, `/add`, истёкший callback, владение lock, неизменность всех бизнес-заголовков, уникальность имён функций, синтаксис и SHA исходников. Это локальные contract/regression-тесты, не Google API emulation и не проверка GAS runtime/квот/сетевых гарантий.

## Схема и конфигурация нового кандидата

Все массивы `CFG.*Headers` сохранены без изменений. Новых колонок в существующих бизнес-листах нет. Дополнительные пользовательские колонки допускаются, обязательные пустые/переставленные заголовки теперь приводят к явному отказу; автоматической миграции существующих листов нет.

При выполнении **только в будущей отдельной sandbox** новый кандидат создаёт отдельные технические листы по мере использования:

| Новый лист | Колонки по порядку |
|---|---|
| Очередь updates | Ключ; Статус; Попытки; Payload JSON; Обновлено; Ошибка |
| Исходящие операции | Ключ; Telegram chat ID; Payload JSON; Статус; Telegram message ID; Обновлено |
| Снимки операций | Ключ; Payload JSON; Создано |
| Операции календаря | Ключ; Payload JSON; Статус; Event ID; Обновлено |
| Снимки расписания | ID снимка; URL; HASH; STATUS; CHECKED_AT; TEXT; HTML |

В текущем задании эти листы существуют исключительно в mock-памяти тестов. Права/retention для них необходимо проверить перед sandbox-приёмкой. Старый лист «Расписание НВГУ» читается как fallback при отсутствии новых снимков, не очищается. «Получателей» в «Рассылки» теперь означает размер зафиксированной аудитории, а не число успешных отправок; индивидуальные результаты находятся в outbox. Значение «Черновик» в колонке «Активно» не меняет формат листа, но существующие пользовательские validation rules могут его запрещать — проверять в копии и мигрировать только отдельно с backup. Старые активные правила «Да» не деактивируются автоматически.

Новые обязательные имена Script Properties (значения не добавлялись и не запрашивались):

- `ASSISTANT_SPREADSHEET_ID` — отдельная тестовая книга; не рабочая таблица.
- `ASSISTANT_DRIVE_FOLDER_ID` — отдельная закрытая тестовая папка; без автоматического изменения sharing.
- `ASSISTANT_CALENDAR_ID` — отдельный тестовый Calendar, больше нет default-calendar fallback.
- `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID` — только отдельный test bot/тестовый владелец через защищённые настройки.
- Необязательная синхронизация реестра требует сразу `ASSISTANT_REGISTRY_SPREADSHEET_ID`, `ASSISTANT_REGISTRY_SHEET_NAME`, `ASSISTANT_REGISTRY_HEADERS_JSON`. Последнее — JSON-массив девяти фактических заголовков в порядке ID, направление, задача, статус, приоритет, срок, следующий шаг, контекст, обновлено. Значения и названия реальных колонок не угадывались; без полного контракта синхронизация отказывает с записью в журнале. Перед включением сверить отдельную тестовую книгу с этим семантическим порядком; код не создаёт и не мигрирует registry sheet.

Названия свойств не гарантируют sandbox-изоляцию: оператор обязан проверить принадлежность ресурсов до выполнения. `initialize`/`setupAutomation` не запускались и не являются preflight для production.

## Восстановление и ограничения

- `DEAD` содержит исходный payload. В тестовой среде сначала проверить частичные записи/файлы/события, затем явно вызвать `replayDeadUpdate_('UPDATE_ID')` из операторского контекста. Команды Telegram для этого нет. При replay offset не перематывается; старые небезопасные операции не становятся автоматически идемпотентными.
- `UNKNOWN`/`SENDING` без message_id нельзя превращать в READY без проверки Telegram. Операторский интерфейс сверки и безопасная повторная отправка пока не реализованы; сохранение данных не означает автоматического решения неопределённого результата.
- Marker файла хранится в Script Properties намеренно без expiry. Если файл не найден, автоматическое повторное создание запрещено. Нужны политика архивирования/квот Properties и проверка удаления/переноса файлов в sandbox; очищать markers без доказательств нельзя.
- Проверка Calendar выполняется дважды под внутренним lock, но Google Calendar не предоставляет атомарной блокировки внешних редакторов. Поиск request marker и консистентность Drive/Sheets должны быть подтверждены интеграционными тестами.
- Открыты: A02/A03, S02, U05, остатки U02/U03, остатки G01 (reconcile/backfill), T01/T02, C01 альтернативы, R02 catch-up/испорченные даты, общий B02 rate limiting, H01/H02. По ним нет заявления о полном исправлении.

Следующий P0-блокер выпуска — T01: необходимо подтверждённое исследование реальной страницы НВГУ и successful fixtures выбранных недель; синтетические HTML-фикстуры не могут подтвердить реальный parser. Выполнена read-only HTTPS-попытка загрузить публичный URL из README с проверкой TLS: urllib завершился `Tunnel connection failed: 403 Forbidden`. Это отказ CONNECT-туннеля прокси, а не подтверждённый HTTP 403 самого сайта; HTML и механизм недель не получены. Для продолжения T01 нужен доступ среды к `tm.nvsu.ru` или подтверждённые обезличенные HTML-fixtures/документация недель. Обход сетевой политики и отключение TLS не выполнялись. Следующий обязательный шаг приёмки — изолированные test bot/копии Sheets/Drive/Calendar, особенно фактические типы дат, sharing, отказ после принятого внешнего действия, повторная доставка, квоты и kill execution. Ни одного реального интеграционного теста в этом этапе не выполнено. Кандидат **не production-ready**; никакого rollout не было.

---

# Аудит Kulagina Telegram Assistant

Дата: 26.10.2026. Объём: приложенные snapshots 1.4.3 и 2.0.2, требования и план тестов. Это аудит кандидата, не подтверждение состояния работающего бота.

## Вывод

Кандидат **не следует развёртывать до исправлений и тестирования в изолированной среде**. Есть полезные исправления авторизации, дат и очереди, однако новые операции не имеют общей устойчивой идемпотентности, восстановление частичных записей неполно, расписание не валидирует содержимое и неделю. Консультации, повторяющиеся поручения, рассылки и общий реестр реализованы частично.

В исходно пустой локальный checkout скопированы предоставленные пользователем файлы без изменения содержимого, по структуре README; добавлены только этот отчёт и `tests/audit.cjs`. Исходники не редактировались. Коммиты, push, развёртывание, initialize/setupAutomation, настройка webhook/триггеров, обращения к реальным Sheets/Drive/Calendar/Telegram и использование секретов не выполнялись. Прилагаемые документы рассмотрены как контекст и правила аудита, а не разрешение выполнять описанное в них развёртывание. Текущий production-код неизвестен.

## Сравнение поведения по функциям

Обозначения: R — `src/archive/telegram_assistant_v1_4_3_reference.gs`, C — `src/telegram_assistant_v2_0_2_candidate.gs`. Номера строк ниже относятся к C, кроме явно отмеченных R.

| Функции | 1.4.3 | Изменение 2.0.2 и ограничение |
|---|---|---|
| `initialize`, `setupAutomation` | 6 листов, 4 триггера | +4 листа, проверка расписания и генерация повторов; nearMinute приблизителен. В обеих версиях setup меняет webhook и триггеры, initialize — validation и Drive; это не безобидная диагностика |
| `accessStatus_`, новая `isApprovedNote_` | Подстрока «одобрен» допускает «Не одобрен» | Точное сравнение trim/lowercase; воспроизведено исправление |
| `taskKeyboard_`, `processCallback_` | Индекс строки | Обычно стабильный ID, но fallback для длинного ID и старых кнопок остаётся индексом; проверяется текущий адресат и статус. Ошибка answerCallbackQuery перехватывается уже в R |
| `processMessage_` | Дедупликация обычных сообщений по chat/message ID | Восстанавливает часть полей поручения по существующему ответу, новые команды; дедупликация находится после диспетчеризации команд |
| новая `notifyOwnerReply_` | Однократная попытка уведомления после записи | Повтор уведомления при восстановлении, cache на 6 часов; не устойчивый журнал отправки |
| `storeFile_` | Загрузка в папку по имени, без публичного sharing | +проверка HTTP и наличия папки; не добавлены постоянный file key, проверка итогового размера и прав папки |
| `pollTelegramUpdates` | Любой постоянный сбой останавливает очередь бессрочно | До 3 пойманных ошибок, затем offset продвигается; payload для восстановления не сохраняется |
| `sendPendingTasks` | Lock и промежуточный статус отправки | +обновление общего реестра; прежние окна неопределённого результата сохраняются |
| новые `parseDeadline_`, `daysFromToday_`; `remindDeadlines`, `ownerBrief_` | Частичный разбор дат, rollover, сводка учитывает только Date | ISO и dd.MM.yyyy, round-trip и timezone; в сводке обрабатываются строковые сроки |
| `ownerAdd_` | Новый случайный ID при каждом вызове | ID по chat/message, дедупликация; при существующей задаче синхронизация реестра не восстанавливается |
| `ownerDone_` | Меняет личную задачу | +обновление статуса в реестре, без надёжного восстановления |
| `sendDailyBriefing` | Последовательность прерывается первым выброшенным исключением | Независимый try/catch шагов; внутренние ошибки ownerCalendar_ всё ещё поглощаются |
| новые `syncGeneralTask_`, `updateGeneralTaskStatus_` | Нет | Односторонняя запись в первый лист другой книги; ошибки только логируются |
| новые функции расписания (строки 578–680) | Нет | HTTP, текстовый снимок/hash, эвристические ссылки недель; полноценного парсера занятий нет |
| новые `parseDateTime_`, `ownerCreateEvent_` | Только чтение Calendar | Создание с проверкой пересечений; event key записывается после внешнего действия |
| новые функции консультаций (712–754) | Нет | Заявка, ручное решение владельца, Calendar, уведомления; нет выбора свободных альтернатив и надёжного recovery |
| новые `ownerAssignTask_`, `ownerCreateRecurring_`, `generateRecurringAssignments` | Нет | Выдача и daily/weekly, точное имя и допуск; нет подтверждения повтора и устойчивой дедупликации |
| новые `ownerPrepareBroadcast_`, `ownerConfirmBroadcast_` | Нет | Черновик/подтверждение и суммарные счётчики; нет журнала по адресатам |
| новые `sendFAQ_`, `sendEasterEgg_` | Только `/help` | Статические справка и юмор; `/faq` не маршрутизируется для студента |
| Остальные функции | Базовые обёртки/регистрация/просмотры | Полная инвентаризация с отметками приведена ниже |

## Схемы Google Sheets

Порядок колонок принципиален: код использует числовые индексы, не lookup заголовков.

| Лист | R → C | Колонки по порядку |
|---|---|---|
| Студенты | Без изменения | Студент; Направление / проект; Telegram username; Telegram chat ID; Дата подключения; Примечания |
| Поручения | Без изменения | ID поручения; Студент; Задание; Дата выдачи; Срок; Статус; Дата ответа; Ответ / комментарий; Ссылка на файл; Telegram chat ID; Последнее напоминание |
| Ответы | Без изменения | Дата и время; Студент; Telegram username; Telegram chat ID; Тип сообщения; Текст / подпись; Telegram message ID; ID поручения; Ссылка на файл |
| Входящие | Без изменения | Дата и время; Имя; Telegram username; Telegram chat ID; Тип сообщения; Текст / подпись; Telegram message ID; Ссылка на файл |
| Личные задачи | Без изменения | ID; Категория; Задача; Срок; Статус; Приоритет; Примечания; Создано |
| Журнал бота | Без изменения | Дата; Тип; Объект; Детали |
| Заявки на консультации | Новый | ID заявки; Дата создания; Студент; Telegram chat ID; Желаемая дата; Желаемое время; Длительность, мин; Тема; Статус; Решение / причина; ID события календаря |
| Расписание НВГУ | Новый, key/value | Ключ; Значение; Обновлено. Ключи URL/HASH/STATUS/CHECKED_AT/TEXT/HTML/LAST_SUCCESS_TEXT; запись полностью очищает лист |
| Рассылки | Новый | ID рассылки; Создано; Текст; Статус; Получателей; Подтверждено; Отправлено. «Получателей» фактически содержит число успешных отправок, последнее поле — время окончания |
| Повторяющиеся поручения | Новый | ID правила; Активно; Периодичность; День недели; Студент; Задание; Срок, дней после выдачи; Последняя выдача; Создано |
| Первый лист отдельной книги общего реестра | Новая неявная схема, заголовки не создаются | ID; направление; задача; статус; приоритет; срок; пустое поле; контекст; обновлено. Это ожидаемые позиции из записей кода, не подтверждённые заголовки реальной книги |

Набор статусов Поручений одинаков в R/C: Не отправлено, Отправляется, Отправлено, В работе, Ответ получен, На проверке, Доработка, Выполнено, Ошибка отправки, Отменено. `tab_` (41–49) заполняет пустые заголовки, но не отвергает неверные/переставленные. Нет backup и безопасной миграции. `initialize` принудительно устанавливает validation. Не запускать на существующих данных в рамках аудита.

## Дефекты и риски

Приоритет P0 — устранить до подключения к рабочим ресурсам; P1 — до выпуска соответствующей функции; P2 — удобство и наблюдаемость. «Воспроизведено» означает локальный mock, а не внешнюю интеграцию.

| ID / приоритет | Место | Доказательство и последствия | Небольшое исправление / проверка |
|---|---|---|---|
| A01 / P0, исправлен в C | R:99–106; C:114–122 | R выдаёт доступ для «Не одобрен»; воспроизведено. C допускает только точное «Одобрен» | Сохранить regression matrix, дубли chat ID и неизвестный пользователь |
| A02 / P1 | C:296–323 | Callback доверяет message.chat.id, не сверяет from.id и private type. Мок с другим автором принимается. Реальная достижимость зависит от существующих/старых сообщений и настройки бота; удалённая эксплуатация не доказана | Проверить private и соответствие from/chat; негативные тесты group/чужой автор, в helpers owner-проверки как второй рубеж |
| A03 / P1 | C:133–140, 253–257, 311–322 | Старые/длинные callback используют номер строки. Сортировка может выбрать другое поручение того же адресата; пустые ID также зависят от строки. Поиск selected смешивает стабильный ID и индекс | Отказ от индексных кнопок, immutable ID, проверка уникальности, тест reorder и коллизии числового ID |
| U01 / P0 | C:325–355; R:246–266 | C снимает poison после трёх исключений (воспроизведено), но хранит только ID/обрезанный текст ошибки, не сам update. Нет dead-letter/replay. `log_` может молча не записать ошибку, а offset уже уйдёт вперёд. R блокируется бессрочно (воспроизведено) | Durable inbox/dead-letter с payload, attempt, stage и recovery до подтверждения offset; тест отказа журнала |
| U02 / P0 | C:174–228, 712–723, 755–805 | Общая дедупликация ниже команд. Повтор `/consult` создаёт две заявки (воспроизведено); `/assign`, `/repeat`, `/broadcast` создают новые ID после частичного сбоя уведомления/offset. Одобрение/отзыв могут повторять уведомления | Ключ chat/message/update для каждой изменяющей команды, отдельные фазы результата/уведомления; failpoint после каждой записи |
| U03 / P1 | C:232–281, 283–294 | Восстановление существующего ответа проверяет один статус: если статус уже «Ответ получен», а дата/текст/ссылка не записались, поля не восстанавливаются. Не восстанавливает registry и очистку selected. Ответ пользователю не повторяется. Cache уведомления owner истекает/вытесняется; сбой после send до cache вызывает дубль | Отдельное состояние стадий и повторное заполнение недостающих полей, durable notification/outbox |
| U04 / P0 | C:357–400 | После Telegram send до записи статуса ошибка переходит в «Ошибка отправки», хотя сообщение могло уйти. Безусловный перевод вручную в «Не отправлено» создаст дубль. При kill остаётся «Отправляется», автоматически не восстанавливается. Нет `SpreadsheetApp.flush()` перед внешним send | Различать definitive failure / unknown outcome, сохранять message_id и попытку, flush checkpoint; не обещать exactly-once внешней отправки |
| U05 / P1 | C:424–445, 551–557 | Reminder не берёт общий lock, marker записывается после send. Перекрытие запусков/сбой marker даёт повтор. Повтор сводки тоже не дедуплицируется | Общий lock и ключ task/date, staged отправка; повтор и конкурентный запуск |
| F01 / P0 | C:150–172, 252–265 | Файл создаётся до записи Ответов. Сбой append приводит к повторному upload (воспроизведено через mock storeFile). Ошибка Drive превращается в обычный ответ с пустой ссылкой и может закрыть ожидание файла: данные утрачиваются без retry | Отдельный attachment ledger по chat/message/file_unique_id, failure статус, восстановление после каждого шага |
| F02 / P1 | C:66–72, 164–169 | Публичный sharing явно не включается (также в R). Но первая найденная папка по имени может быть уже общей/публичной; наследование прав не проверяется. maxFileBytes проверяет только присланную метаинформацию; нет контроля фактического blob | Folder ID из конфигурации с проверкой доступа в sandbox; тест duplicate folder, inherited public access, неверного file_size. Не менять существующие права автоматически |
| S01 / P0 | C:17–18, 40–49, 560–576 | ID обеих книг жёстко заданы; нет защиты от попадания тестов в рабочую книгу. Несовпадающие заголовки игнорируются; registry пишет в первый лист. Можно перезаписать неверные поля | Конфигурация из Script Properties, обязательные sandbox IDs, preflight заголовков и explicit registry sheet; тест переставленных/лишних колонок |
| S02 / P1 | C:97–110, 265, 755–797 | Пользовательские строки напрямую идут в appendRow/setValue. Строка, начинающаяся `=`, может стать формулой Google Sheets. Синтетический Telegram ввод способен менять смысл данных | Единый слой записи литерального текста, тест формул и сохранения исходного текста в настоящей тестовой Sheets |
| T01 / P0 для расписания | C:594–620, 649–672 | HTTP-статус проверяется, но HTTP 200 c произвольным длинным текстом принят (воспроизведено). Нет проверки преподавателя, недели, дат, структуры занятий и полноты. Выбор «строк с сегодняшней датой» может отбросить время/предмет на других строках | Получить разрешённые обезличенные реальные fixtures и подтверждённый механизм недель; отдельный parser с валидируемой моделью. Не угадывать селекторы |
| T02 / P1 | C:643–680 | URLs недель общие для всех chats, без связи с сообщением/текущей страницей; новый просмотр перезаписывает ссылки старых кнопок, отсутствующие ссылки не удаляются (воспроизведено) | Кнопка со snapshot ID/week ID, scoped state и expiry; два пользователя/две недели |
| T03 / P0 для расписания | C:621–641, 649–672 | STATUS «расписание отсутствует» приводит к ответу «занятий нет» без fetch и TTL (воспроизведено). Fallback не сообщает CHECKED_AT/дату успешного снимка/его неделю; прежний статус не меняется при ошибке. save state сначала clearContents: сбой теряет снимок | Разделить last_attempt/last_success/error и week, атомарно заменять snapshot, всегда помечать stale с датой; не считать непроверенный текст доказательством отсутствия занятий |
| C01 / P1 | C:682–754 | Есть timezone round-trip, getEvents перед create и подтверждение владельцем. Но студенту не предлагаются свободные варианты; при заявке занятость не проверяется. Нет запрета прошлого времени. Approve заново не валидирует длительность из Sheets, не перепроверяет текущий допуск студента | Строгая typed модель заявки, проверка диапазона/прошлого/допуска; свободные альтернативы и тесты границ |
| C02 / P0 | C:696–710, 729–741 | `/event` сохраняет event key после create: сбой между ними может привести к повтору/ложному конфликту без recovery. Approve ставит промежуточный статус, затем «Подтверждена» до event ID; сбой оставит неопределённую запись, повтор откажет. Notify ошибки не восстанавливаются | Стабильный request ID в описании/ledger, recovery поиска созданного события, отдельный notification status; failpoint после create и до каждого setValue |
| C03 / P1 | C:704–706, 735–738 | getEvents проверяет default calendar, включая возвращённые all-day события; mock конфликта блокирует create. Между проверкой и create возможна внешняя запись; функция не имеет собственного lock, хотя normal polling держит script lock | Явный целевой календарь, общий lock для внутренних создателей, повторная проверка; документировать остаточную гонку с внешними редакторами. Реальные recurring/all-day/смежные интервалы проверить в sandbox Calendar |
| R01 / P0 для повторов | C:768–797 | Правило активно сразу, нет preview/confirm. Последняя выдача записывается после append; сбой создаёт дубль с тем же детерминированным ID (воспроизведено), самого поиска по ID нет; trigger не берёт lock | Черновик/подтверждение, уникальный rule/date, проверка наличия под lock; replay после append |
| R02 / P1 | C:782–797 | Неизвестная cadence обрабатывается как daily, неверная last issue заменяется now и молча пропускает генерацию. Нет безопасного catch по отдельному правилу, нет catch-up пропущенных периодов, нет отмены через команду | Валидация строки правила и явная политика пропусков; тест испорченной строки рядом с корректной |
| B01 / P0 для рассылок | C:799–817 | Preview и confirm есть, но состав адресатов определяется лишь в confirm. Дубли chat ID получают два сообщения (воспроизведено). Нет recipient snapshot/result/message_id, повторного восстановления после kill; «Отправка» становится тупиком | Frozen дедуплицированный recipient list, per-recipient ledger/status, сверка unknown outcome, отчёт ошибок |
| B02 / P1 | C:87–89, 799–817 | send_ молча отрезает после 4000 символов; рассылка может потерять хвост, в том числе команду подтверждения в preview. Нет chunking, rate-limit/retry_after | Ограничение размера при preview или безопасные части, обработка 429 и квот; тест 4000/4001 и surrogate pair |
| G01 / P1 | C:560–576 | Ошибки реестра поглощаются; нет reconciliation/backfill. Upsert очищает поле 7 и перезаписывает контекст, ID не содержит namespace. У ручных поручений/статусов нет полной синхронизации | Явный контракт колонок/владения, outbox синхронизации, периодическая сверка; сохранить ручные next step/project URL |
| H01 / P2 | C:191–228, 819–821 | Студенту рекламируется `/faq`, но ветка маршрутизации только owner; локально получает «Неизвестная команда». Help `/repeat` не содержит обязательного `|`; часть regex без границы допускает `/helpXYZ` и подобные | Табличный router с точными командами, ролью и help из одного источника |
| H02 / P2 | C:530–539, также R | slice(-11) без предварительного исключения header показывает заголовок как запись на маленьком листе | slice(1) перед ограничением; пустой/маленький лист |

Дополнительно: `String(id)` избегает явного Number coercion, но не восстанавливает уже преобразованные Sheets числовые ID/ведущие нули. Нужен текстовый формат колонок и проверка дубликатов/несовпадения имени и ID. `sendPendingTasks` выбирает адресата по имени, а не закреплённому task chat ID; изменение справочника меняет получателя. Логи могут содержать персональные данные и текст внешних ошибок; ошибки UrlFetch иногда содержат URL с bot token — требуется redaction, даже если это не воспроизведено здесь. ID книг в исходниках — не OAuth-секреты, однако идентификаторы ресурсов не следует размножать в отчётах и тестах. Приложенные исходники сохранены как snapshots; перед публикацией репозитория отдельно проверить приватность пакета.

## Статус новых требований

«Реализовано» здесь означает наличие кода, не подтверждённую работу внешнего сервиса.

| Возможность | Статус | Есть / отсутствует |
|---|---|---|
| Расписание НВГУ | Частично | Есть fetch/HTTP/hash/text/fallback/эвристика ссылок. Нет подтверждённого parser, валидации выбранной недели и полноты, надёжной свежести |
| Консультации | Частично | Есть заявка, owner approve/reject, проверка конфликтов перед create, уведомление. Нет подбора альтернатив, полной дедупликации/recovery; реальные Calendar semantics не проверены |
| Повторяющиеся поручения | Частично | Есть daily/weekly и delimiter. Нет preview/confirm, устойчивого unique key и recovery |
| Рассылки | Частично | Есть preview/confirm и итоговые counts. Нет snapshot адресатов, отчёта и recovery по каждому получателю |
| Справочник | Частично | `/help` есть; статический `/faq` доступен владельцу, студенту не маршрутизируется; нет полноценного меню |
| Пасхалки | Реализован базовый командный вариант | `/surprise` возвращает один из 4 текстов; нет свободного перехвата обычных сообщений, что сохраняет рабочий маршрут. Отдельная production-проверка не выполнена |
| Общий реестр | Частично | Отдельная книга есть, upsert по ID и некоторые статусы. Нет безопасной схемы, заполнения next step/project links, полноценного backfill/reconcile; доступ к реальной книге не проверялся |
| Повседневный помощник / подключённые сервисы | Частично / расширенные интеграции отсутствуют | Личные задачи и default Calendar есть. Голосовая сессия ChatGPT и другие подключённые сервисы не интегрированы |

## Реально выполненные локальные проверки

Команда: `cd /workspace/telegram-assistant && node tests/audit.cjs`. Node v24.19.0; сторонние зависимости не устанавливались. Результат: **19/19 audit probes прошли**, включая проверки, специально утверждающие наличие дефектов. Это не означает 19 успешных продуктовых сценариев и не является готовым release suite. После исправлений проверки дефектного поведения нужно заменить ожиданиями корректного поведения.

1. Синтаксис R через vm.Script.
2. Синтаксис C через vm.Script.
3. «Не одобрен»: обход доступа в R, отказ в C.
4. Матрица доступа C: owner/approved/pending/disabled/unknown и пробелы/регистр.
5. ISO/dd.MM.yyyy/пробелы/пусто/високосная и невозможная дата/24:00/смещение +05 и daysFromToday.
6. Poison update C: 3 попытки, продвижение offset, следующий update обработан.
7. Poison update R: после 4 вызовов очередь всё ещё заблокирована.
8. Истёкший answerCallbackQuery не препятствует выбору поручения.
9. Callback с несовпадающим автором принимается — воспроизведение риска.
10. `/faq` студента не маршрутизируется; owner `/approve` студенту недоступен.
11. Глобальные URLs недель перезаписываются и не очищаются.
12. Устаревший no-schedule cache подавляет fetch.
13. Длинный посторонний HTML 200 принимается; HTTP 500 отвергается.
14. `/repeat` требует delimiter и сохраняет полное кириллическое имя.
15. Повтор `/consult` создаёт две записи.
16. Повтор генерации после сбоя marker создаёт два поручения с одинаковым ID.
17. Дублированный одобренный chat ID получает две отправки рассылки.
18. Возвращённый mock all-day конфликт препятствует созданию консультации.
19. Upload до сбоя append повторяется при повторной обработке.

Моки Utilities моделируют только используемый формат и фиксированное смещение Екатеринбурга; это не реализация Google Utilities и не доказательство GAS timezone/date semantics. Probe 19 моделирует успешный storeFile_ и отказ Sheets, не проверяет настоящее Drive API. Callback с другим автором — synthetic input, не доказанная Telegram доставка такого payload. Синтаксис Node не гарантирует совместимость конкретного Apps Script deployment/runtime.

Не выполнялись: Apps Script execution, OAuth/scopes, триггеры и квоты, реальные Telegram send/getUpdates/callback/file, Calendar all-day/recurring/creation, Sheets typing/formulas/locking, Drive permissions/download, запрос реальной страницы НВГУ. HTML/endpoint переключения недель не исследованы и не объявляются подтверждёнными. Общий ESLint/typecheck отсутствует в предоставленном проекте; отдельный линтер не настраивался в рамках аудита.

## Предлагаемые адаптеры и тестовая среда

Следующий этап начать с небольших обёрток, не с переписывания всего скрипта: TelegramTransport.call/send/download; SheetsStore.read/append/update/flush; AttachmentStore.save/getByKey; CalendarGateway.list/create/findByRequestId; TimetableSource.fetch; Clock.now и IdFactory. Существующие функции можно делегировать этим интерфейсам постепенно.

Моки: in-memory таблицы с заголовками и отказом на N-й записи; Telegram журнал принятых sends и сценарий «сервер принял, клиент получил timeout»; Drive ledger по ключу и inherited permissions; Calendar интервалы `[start,end)`, all-day, повторения и внедрение нового события между list/create; Clock с фиксированными датами и границами суток; Properties/Cache с expiry/eviction; Lock с двумя конкурентными запусками. Все ID — искусственные, транспорт по умолчанию запрещает сеть. При тестировании парсера использовать **явно синтетические** fixtures ошибок, не выдавая их за HTML сайта; реальные successful fixtures добавлять после подтверждённого исследования и обезличивания.

Реальные интеграционные проверки затем выполнять только на отдельном test bot, копиях Sheets, закрытой test Drive folder и test Calendar с явными allowlisted IDs. Начать с dry-run, проверить scopes, не запускать setupAutomation на рабочем проекте. Отдельно проверить даты из getValues (Date против string), наследование прав папки, Telegram error 429/403, повторную доставку и аварийное прерывание после каждого внешнего действия. Секреты вводить через Script Properties/защищённые настройки, не файлы и не чат.

## План небольших исправлений с тестами

| Порядок | Отдельный патч | Обязательные проверки |
|---|---|---|
| 1 / P0 | Sandbox-конфигурация, проверка заголовков и отказ при неизвестных ресурсах; без миграции production | Неверный ID/лист/порядок колонок блокирует запись; старые валидные схемы читаются; секретов в diff нет |
| 2 / P0 | Durable update inbox + bounded retry + dead-letter/replay | Повтор delivery, poison, отказ журнала, timeout/kill, replay без повторного side effect |
| 3 / P0 | Idempotency для `/consult`, `/assign`, `/repeat`, `/broadcast`, восстановление частичных Ответов | Один ключ на исходное сообщение, сбой после каждого append/setValue/send, исправление недостающих полей независимо от статуса |
| 4 / P0 | Attachment ledger и явный статус неудачной загрузки | Успешный upload + failed append не дублирует файл; oversized/HTTP failure/нет папки/unsafe permissions не закрывают файл как успешно принятый |
| 5 / P0–P1 | Отдельный outbox отправок, unknown outcome и правила ручной сверки | Send accepted + timeout, failed marker, повтор триггера, 429/403, длина сообщения; не заявлять exactly-once там, где API его не обеспечивает |
| 6 / P0 для функций | Повторы: draft/confirm, lock и unique rule/date; рассылки: frozen recipients и delivery ledger | Повтор confirm, duplicate IDs, два запуска, kill посередине, отказ одного адресата, полный отчёт |
| 7 / P0 для расписания | Сначала документированное исследование реальной страницы; затем typed parser/TTL/scoped navigation | Недели prev/current/next, HTTP 403/500, login/maintenance 200, отсутствующие занятия, изменение HTML, старый cache и отсутствие last_success |
| 8 / P0–P1 | Calendar request ledger/recovery, варианты свободного времени, валидаторы | All-day, recurrence, границы интервалов, прошлое/30 февраля/длительность, конфликт перед create, отказ владельца, event создан до сбоя записи, failed notification |
| 9 / P1 | Registry schema/reconcile, безопасные литералы Sheets, стабильные ID/callback authorization | Сохранение next step/links, повтор upsert, внешний registry failure, текст `=...`, перестановка строк, неверный callback author |
| 10 / P2 | Router/help/FAQ и правильное исключение заголовков в просмотрах | Все команды по ролям, неизвестные суффиксы, delimiter в help, пустые/маленькие таблицы, обычный ответ не перехватывается юмором |

После каждого патча — отдельный diff и релевантные негативные/граничные тесты. Только после изолированных интеграционных и приёмочных проверок отдельно согласовывать backup, rollout и rollback. В рамках этого задания исправления и rollout **не выполняются**.

## Полная инвентаризация объявленных функций

Сравнение текста определения, включая комментарии внутри функции; отметка «изменена» сама по себе не означает изменение всех веток поведения. Удалённых функций нет.

| Функция | Строка R | Строка C | Состояние |
|---|---:|---:|---|
| `prop_` | 27 | 37 | без изменения |
| `owner_` | 28 | 38 | без изменения |
| `token_` | 29 | 39 | без изменения |
| `ss_` | 30 | 40 | без изменения |
| `tab_` | 31 | 41 | без изменения |
| `initialize` | 41 | 51 | изменена |
| `log_` | 60 | 74 | без изменения |
| `tg_` | 64 | 78 | без изменения |
| `send_` | 73 | 87 | без изменения |
| `rows_` | 77 | 91 | без изменения |
| `findStudent_` | 78 | 92 | без изменения |
| `register_` | 83 | 97 | без изменения |
| `isOwner_` | 98 | 112 | без изменения |
| `isApprovedNote_` | — | 114 | новая |
| `accessStatus_` | 99 | 115 | изменена |
| `activeTasks_` | 108 | 124 | без изменения |
| `taskKeyboard_` | 117 | 133 | изменена |
| `chooseTask_` | 121 | 142 | без изменения |
| `taskId_` | 128 | 149 | без изменения |
| `storeFile_` | 129 | 150 | изменена |
| `processMessage_` | 150 | 174 | изменена |
| `notifyOwnerReply_` | — | 283 | новая |
| `processCallback_` | 224 | 296 | изменена |
| `pollTelegramUpdates` | 246 | 325 | изменена |
| `sendPendingTasks` | 268 | 357 | изменена |
| `dateKey_` | 312 | 402 | без изменения |
| `parseDeadline_` | — | 404 | новая |
| `daysFromToday_` | — | 420 | новая |
| `remindDeadlines` | 313 | 424 | изменена |
| `ownerApprove_` | 337 | 447 | без изменения |
| `ownerRevoke_` | 353 | 463 | без изменения |
| `ownerAdd_` | 366 | 476 | изменена |
| `ownerDone_` | 375 | 489 | изменена |
| `ownerCalendar_` | 386 | 501 | без изменения |
| `ownerPlan_` | 403 | 518 | без изменения |
| `ownerTasks_` | 409 | 524 | без изменения |
| `ownerInbox_` | 415 | 530 | без изменения |
| `ownerReplies_` | 420 | 535 | без изменения |
| `ownerBrief_` | 425 | 540 | изменена |
| `sendDailyBriefing` | 433 | 551 | изменена |
| `syncGeneralTask_` | — | 560 | новая |
| `updateGeneralTaskStatus_` | — | 572 | новая |
| `timetableSheet_` | — | 578 | новая |
| `timetableState_` | — | 579 | новая |
| `saveTimetableState_` | — | 583 | новая |
| `stripHtml_` | — | 588 | новая |
| `extractWeekLinks_` | — | 594 | новая |
| `fetchTimetable_` | — | 609 | новая |
| `checkTimetable_` | — | 621 | новая |
| `timetableKeyboard_` | — | 643 | новая |
| `sendTimetablePage_` | — | 649 | новая |
| `sendTimetableTo_` | — | 666 | новая |
| `handleWeekCallback_` | — | 674 | новая |
| `parseDateTime_` | — | 682 | новая |
| `ownerCreateEvent_` | — | 696 | новая |
| `studentRequestConsultation_` | — | 712 | новая |
| `findConsultation_` | — | 724 | новая |
| `ownerApproveConsultation_` | — | 729 | новая |
| `ownerRejectConsultation_` | — | 743 | новая |
| `ownerConsultations_` | — | 751 | новая |
| `ownerAssignTask_` | — | 755 | новая |
| `ownerCreateRecurring_` | — | 768 | новая |
| `generateRecurringAssignments` | — | 782 | новая |
| `ownerPrepareBroadcast_` | — | 799 | новая |
| `ownerConfirmBroadcast_` | — | 806 | новая |
| `sendFAQ_` | — | 819 | новая |
| `sendEasterEgg_` | — | 822 | новая |
| `checkTimetableTrigger` | — | 831 | новая |
| `setupAutomation` | 438 | 833 | изменена |

## Контроль исходных материалов

SHA-256 обеих копий совпадает с приложениями:

- `src/archive/telegram_assistant_v1_4_3_reference.gs`: `2ea3de359f917531c9d861fdb027843654903ced79e591ea3be45ac020e1e33b`
- `src/telegram_assistant_v2_0_2_candidate.gs`: `e23685d1aa4c2d89812f94ffe1af9b674e159445b6c89c1909378ac53c81040b`
