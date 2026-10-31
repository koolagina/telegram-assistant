# Выбор текущей лекции кнопкой

**Локальный блок завершён; рабочий бот не включён и не изменён.** Пользователь вне компьютера, действий сейчас не требуется. Реальных расписаний, кодов, отправок или записей журнала в блоке нет.

## Реализация

`tools/lecture_menu.py` добавляет `LectureMenu` и явный доверенный `LectureLabel(lecture_id, title, room)`. Команда-кандидат `/lectures` показывает преподавателю только текущие lecture/confirmed/verified занятия, на которые существующая policy разрешает lecture.code.read и binding имеет lecture.open/code.read. Лектор видит своё занятие, владелец — при точном действующем substitution grant. Полный академический read сам по себе не даёт права открытия кода.

Текст: дисциплина, время Екатеринбурга, аудитория; без технического lecture ID, групп/потоков и кода. Пять записей на страницу, кнопки выбора/страниц/возврата. Listing read-only, не открывает окно и не меняет WindowStore. Пустой список означает отсутствие доступных **подтверждённых локальных** лекций, не доказательство отсутствия реальных занятий. Свежесть облачного источника UI не обещает.

Callback reference ≤64 байт связан с subject, channel, teacher entity, каталогом labels и `source_digest(lecture)` — дата/время/дисциплина/назначенный teacher/группы/kind/status/verified и lecture ID. Hash — навигация, не authentication или разрешение. Токен другого преподавателя, изменённого каталога/занятия, завершившейся лекции или отозванного замещения не открывает код. Роли/список проверяются вновь при каждом клике; собственная история и future lectures не предлагаются.

`LectureWindows.open` получил optional `expected_source`: после текущей авторизации и **до** clock/window writes проверяет ожидаемую идентичность занятия. Это закрывает гонку между menu selection и открытием: старый callback не открывает окно для нового источника под тем же lecture ID. Существующие direct commands остаются совместимыми без expected_source. В `prepare_lecture_reply` передаётся trusted expected_source из menu, не пользовательское поле.

После local open menu снова проверяет роли/source и через existing service.show — текущую opening authority/expiry/AEAD. Изменение после создания local window блокирует возврат кода; окно не удаляется/не принимается автоматически. Нет атомарности с внешней policy и Telegram: после локальной проверки остаётся общий race; перед send existing worker заново готовит ответ.

Повтор того же update использует прежний stable bot/update request, не продлевает окно и не открывает новое после expiry. **Новый явный клик** с новым update может открыть новое 90-секундное окно после истечения старого, пока действуют занятие и права; это ожидаемая отдельная операция. Новые клики в ещё активное окно переиспользуют его. При завершении занятия code open недоступен.

## Интеграция локального стенда

`TelegramReportAdapter` / `ReportWorker`: optional `lecture_menu_factory`, default=None, type/callable checks, `/lectures` и `lect:` routes. Private sender/chat и original bot ID проверки сохранены. Callback использует внутренний request ID configured bot + actual update. Existing no-text CallbackAckLedger подтверждает кнопку отдельно, DispatchLedger защищает message send от повтора, expired/stale response становится cancelled. Нет новых таблиц, scopes, trigger, CLI или live bootstrap.

`tools/lecture_attendance_demo.py` расширен до цепочки: menu listing без кода → кнопка owner-substitution → один mock callback ACK и code message → две student commands → одна attendance → отказ на 90-й секунде. Actual temporary private SQLite/fixture key/искусственная policy, никаких real API; code/reply/input не печатаются.

Студенческая `/attend ID_лекции КОД` из предыдущего блока сохранена: новый menu предназначен **преподавателю**, не вводит student selection state/QR/public form. Студенту по-прежнему нужен согласованный способ получить lecture reference и ввод кода; это отдельный следующий UI-этап, без выдачи teacher code студенту.

## Приёмка

20 новых тестов, написанных до соответствующих реализаций:

- 15 `tests/test_lecture_menu.py`: current teacher selection, owner substitution/revoke, student/group/unverified contexts denied, source/catalog change, завершение/exam/unverified lecture, cross-teacher token, repeat/new-click без extension, expired same request, listing без writes/code, malformed input/labels, source race до open, pagination/64 bytes, revoke, expected_source до writes;
- 5 `tests/test_lecture_menu_worker.py`: actual queue→menu→callback→window→mock send/ACK, default-off/deferred, changed source cancelled с no-text ACK, чужой bot callback, invalid factory.

Полный `bash tools/check-local.sh`: **842 Python +448 Node PASS, 13 offline демонстраций**. Лог `/tmp/kulagina-lecture-menu-final-check.txt`. Целевой запуск: `python3 -m unittest discover -s tests -p 'test_lecture_menu*.py'`.

| Пробел / риск | Причина | Реализация | Тест / итог | Остаток |
|---|---|---|---|---|
| Преподавателю нужен technical lecture ID | Был direct command | Текущий private teacher menu | Selection/pagination PASS | Реальный каталог не подключён |
| Старый callback открывает изменённый lesson ID | Источник может смениться между lookup/open | Source-bound ref + expected_source внутри open | Source-race/no-writes PASS | Race после проверки с внешними ресурсами остаётся |
| Чужая/отозванная кнопка даёт код | UI не является разрешением | Current policy/teacher/source/authority checks | Foreign/revoke/expired PASS | Authentication registry ещё нужен |
| Повтор preparation создаёт лишнее окно | Worker готовит дважды | Existing stable request/active reuse | Repeat/worker PASS | Новое явное действие после expiry допустимо |

## Следующий этап подключения

Подтверждённый source лекций, явный каталог title/room, stable lecture identities, реальные confirmed bindings и substitutions, private persistent encryption key/state/retention, единственный poll owner и ограниченная live-приёмка. Verified flag в искусственной policy не является проверкой реального расписания. Не копировать весь 2.0.5 поверх working legacy; local Python menu не установлен source relay. Никаких production/таблиц/Calendar/Google settings/секретов/писем/триггеров/deployment не меняли.
