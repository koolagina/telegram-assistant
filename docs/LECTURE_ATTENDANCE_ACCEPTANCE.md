# Коды лекций и личная отметка посещаемости

**Локальный блок завершён; в рабочем боте не включён.** Реальные коды, аккаунты, сообщения и записи журнала не создавались. Пользователь без компьютера, ручных действий сейчас не требуется.

## Найденный дефект хранилища

WindowStore мог открыть чужую SQLite-базу, добавить свои таблицы и инициализировать её как lecture state. Неполный набор таблиц или удалённая metadata также могли дополняться автоматически; malformed last_clock не выявлялся при открытии.

В `tools/lecture_windows.py` до создания схемы проверяется существующий набор таблиц. Допускается новый пустой store либо ровно текущие шесть таблиц. Неполный/чужой набор отвергается без добавления таблиц. Для существующего store требуется полный набор metadata, namespace/schema/key check и корректный канонический last_clock. Нет автоинициализации вместо утраченной metadata. Ошибки содержимого сводятся к безопасному WindowError. Валидная существующая схема не менялась, чужие данные не удаляются и не мигрируют.

## Личная регистрация с отдельным правом

`assistant_access.py`: добавлена capability `attendance.register`. Это **отдельное право записи локальной отметки**, не следствие `progress.self`. Действует только для student в private authenticated Telegram с подтверждённой binding и живым enrollment. ChatGPT/API scopes и email этим правом не расширены. Ни одному реальному аккаунту или сохранённой policy право автоматически не выдавалось.

`LectureWindows.register_authenticated(context, lecture_id, code)` получает student identity из trusted policy, без student ID в пользовательской команде. Внутри register повторно проверяются текущие права именно на исходного student: revoke/rebinding между разрешением identity и транзакцией не может отметить старого/другого студента. Существующий raw `register(lecture_id, student_id, code)` оставлен совместимым **для внутреннего доверенного кода**, не для публичного endpoint; любой новый transport должен использовать authenticated path.

Сохранены существующие правила: окно 90 секунд по server clock, lecture.kind=lecture/confirmed/verified, реальные границы занятия, активные teacher/substitution и enrollment/group/course; code не используется повторно для этой лекции; повтор open не продлевает окно; expired request не создаёт новое окно без явного нового действия. Локальный лимит неверных попыток 5/student/lecture/minute сохранён; он не заменяет сетевое rate limiting и authentication. Код не доказывает физическое присутствие: им могут поделиться. Журнал не меняется, journal_status=not_synced.

## Локальные команды-кандидаты

`tools/lecture_requests.py`:

- `/lecturecode ID_лекции` — лектору либо владельцу при подтверждённом замещении, по существующим lecture.open/code.read grants; не требовать ожидания между кодами, активное окно переиспользуется;
- `/attend ID_лекции КОД` — только самому студенту с explicit attendance.register, без аргумента student ID.

Это технические команды, не готовое меню выбора актуальной пары. Reply plain text, без parse_mode/link previews. Код показан только разрешённому преподавателю; ответ студенту не повторяет код и явно сообщает о локальной записи без переноса в журнал. Экзамен/зачёт и неподтверждённое занятие не открывают окно.

`TelegramReportAdapter` и `ReportWorker` получили optional `lecture_service_factory`, default=None. Проверяются trusted service type и private sender; request ID строится внутри адаптера из configured bot ID + actual Telegram update ID, а не из текста. Повторная routing/fresh preparation не создаёт второе окно/attendance. Существующая DispatchLedger защищает message attempt от повторов; unknown не повторяется автоматически. Рабочий Apps Script не использует эти Python-команды.

**Подготовка этих ответов изменяет локальный WindowStore.** Open/attendance могут сохраниться при первом разрешённом routing до сбоя/отзыва или до отказа отправки. `cancelled` message receipt не означает, что локальных изменений ранее не было. Между WindowStore и dispatch/inbox нет общей транзакции; автоматический rollback отметки/окна не добавлен. Повтор использует стабильный request и уникальную lecture/student attendance identity. Перед send права всё равно проверяются заново; истёкший/revoked код не отправляется. Runtime providers/loaders local-only, не выполнять сетевое чтение под SQLite transaction.

## Приёмка

25 новых тестов:

- `tests/test_lecture_hardening.py` — 12: четыре конкретных FAIL для foreign/partial/missing-meta/malformed-clock до исправления; authenticated self, отсутствие write из progress-read, private/auth/sender checks, revoke/rebind между registry reads, ровно expiry boundary, revoked substitution, teacher не может зарегистрироваться как student;
- `tests/test_lecture_requests.py` — 7: owner substitute/lecturer получают одно окно, повторная отметка одна, student code denied, unverified/exam denied, malformed commands без изменений, expired replay не создаёт новое окно;
- `tests/test_lecture_worker.py` — 6: actual SQLite queue→service→fake API, default-off/deferred, одно окно при double preparation, одна attendance, revoke до отправки, student не impersonates teacher, stable request across worker runs.

Существующие lecture tests дополнительно проверяют concurrent connections, key/AEAD binding, clock rollback, code reuse/rate limit и operator/substitution audit; они прошли в общем наборе.

Новая `tools/lecture_attendance_demo.py`: actual temporary encrypted WindowStore + inbox/dispatch, artificial policy/clock/key, mock owner-substitution code request, две команды student attendance, один локальный attendance record, отказ на точной границе 90 секунд. Ни код, ни reply body, ни input command не выводятся. Демонстрационный ключ не является реальным секретом и используется только для удаляемого temporary state.

Полный `bash tools/check-local.sh`: **822 Python +448 Node PASS, 13 offline демонстраций**. Лог `/tmp/kulagina-lecture-final-check.txt`.

| Дефект/пробел | Причина | Исправление | Проверка | Оставшийся риск |
|---|---|---|---|---|
| Чужая БД дополнялась lecture tables | Не проверялся существующий набор | Strict table/metadata isolation | Foreign/partial FAIL→PASS | Не восстановление повреждённой БД |
| Нельзя безопасно привязать self attendance | Raw API предполагал trusted student ID | Confirmed Context + explicit capability + повторная policy | Revoke/rebind/self PASS | Authentication provider ещё не подключён |
| Чтение прогресса могло ошибочно стать основанием write | Нужна отдельная семантика прав | attendance.register, без auto grants | Read-only denied PASS | Реальные права не выдавались |
| Команды не подключались к очереди | Lecture controller был отдельным | Optional factory, stable bot/update request | Worker/dedup/default-off PASS | Нет live rollout/меню пары/QR |

## Дальше

Подтверждённый источник реальных занятий и session-specific substitutions, identity registry и explicit capability для согласованных студентов; сохранённый private encryption key, backup/retention local state и безопасное восстановление; удобный выбор текущей пары; отдельная ограниченная live-приёмка. Нужны внешние authentication/rate limits; QR/public form, утренняя почта, Google journal sync и automatic attendance credit не реализованы этим блоком. Код хранится зашифрованно в WindowStore, но Telegram /attend input попадёт в private inbox: не логировать его и определить retention перед подключением. Никаких live source/API/триггеров/deployment не было.
