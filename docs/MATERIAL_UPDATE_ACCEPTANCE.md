# Обновление материалов и актуальность сохранённых отчётов

30.10.2026 — **завершён локальный блок; реальные файлы и бот не изменены**. Пользователь вне компьютера, его действий сейчас не требуется.

## Найденный дефект

Существующий MaterialCatalog уже проверяет свежий источник при prepare/finish, сохраняет версии и переводит незавершённую проверку в needs_recheck при смене материалов. Однако отображение сохранённых отчётов через ReportReader/Telegram не сравнивало версию проверки с последней загруженной версией каталога. Старый результат мог выглядеть как результат по актуальным критериям.

## Изменения

- `tools/material_versions.py`: `CriteriaSnapshot` и SELECT-only `MaterialCatalog.criteria_snapshot(check_id)`. Один joined SELECT сопоставляет immutable версию проверки с текущим локальным head и наличием задания; схема SQLite и история не меняются. Сбой не подменяется совпадением.
- `tools/report_access.py`: необязательный доверенный local-only `criteria_provider`. После разрешённой загрузки отчёта проверяются точная привязка snapshot к check/assignment/version и корректность полей; после provider снова проверяются права. Чужой пользователь вообще не вызывает provider. Неверная связь блокирует отчёт, исключение provider даёт безопасное `unavailable` без раскрытия исключения.
- Выход ReportReader дополнен `criteria_state` и `criteria_live_verified=false`. Без provider — `not_checked`; с provider — `catalog_matches`, `catalog_changed`, `assignment_removed` либо `unavailable`. Завершённый результат не перезаписывается и не принимается автоматически.
- `tools/report_requests.py`: единый `criteria_notice` в деталях и списке работ; `tools/academic_overview.py` — то же предупреждение в сводке. При изменении материалов явно сказано, что прежний результат сохранён по прежним критериям и нужна сверка преподавателя. Не выводятся source URLs/версии/пути.
- `tools/assistant_demo.py`: подключён provider каталога в существующем синтетическом session reader, включая очередь/перезапуск сценариев. Это только offline wiring.
- `tools/material_update_demo.py`: отдельная synthetic DOCX→trusted fixture validator→catalog→PPTX→report→update демонстрация, добавленная в check-local.sh.

`catalog_matches` означает только совпадение с **последней загруженной локальной версией**, а не свежесть реального файла на Яндекс Диске. UI предупреждает об этом. Метод snapshot не обращается в сеть и не обновляет head. Если remote файл изменился, но runtime ещё его не перечитал, это не может быть обнаружено сравнением local head. Нужен уже существующий fresh prepare/finish provider и будущая согласованная стратегия обновления источника; watcher/cron/polling в этом блоке не добавлены.

Критерии не извлекаются автоматически из произвольных документов без проверки: MaterialProvider по-прежнему требует явно доверенный source-bound validator и разрешение всех review flags. Синтетический validator демонстрации знает только два фиксированных искусственных текста; он не является семантическим проверяющим и не должен попадать в production. Лекция №1 по-прежнему связана с ДЗ №1. Баллы/зачёт/журнал не меняются.

## Приёмка

16 новых `tests/test_report_material_freshness.py`, написанных перед реализацией: исходно отсутствовали criteria_snapshot и provider metadata. Проверены:

- local match с false live flag, отсутствие provider без ложной актуальности;
- обновление материалов, новый version/check, сохранность старого результата;
- удаление задания и ошибка источника без cached fallback;
- исключение provider без утечки и отзыв доступа во время provider;
- чужая snapshot identity и отказ чужому студенту до provider;
- предупреждение в prepared reply, SELECT-only snapshot без total_changes;
- restart и needs_recheck при изменении во время проверки;
- настоящий synthetic DOCX extraction + trusted fixture validation + PPTX parser/structural review + ReportReader.

Демонстрация: одна искусственная презентация на 3 слайда сначала соответствует explicit minimum=3; после source update minimum=4 новая проверка показывает not_met, старая запись остаётся прежней с catalog_changed. Это проверка структуры, не качества содержания и не начисление баллов.

Полный `bash tools/check-local.sh`: **747 Python +448 Node PASS, 11 offline демонстраций**. Лог `/tmp/kulagina-material-update-final-check.txt`. Целевой запуск: `python3 -m unittest discover -s tests -p test_report_material_freshness.py`.

| Дефект/риск | Причина | Исправление | Тест / итог | Остаток |
|---|---|---|---|---|
| Старый отчёт выглядел актуальным | UI не сравнивал версии | CriteriaSnapshot + state + notices | Update/UI PASS | Remote freshness не доказана |
| Перезапись исторического результата | Новый критерий не должен менять старый check | Existing immutable result, отдельный новый check проверены | History/restart PASS | Нет автоматического решения преподавателя |
| Устаревшие критерии при незавершённой проверке | Файл меняется между prepare и finish | Existing needs_recheck проверен сквозно | Mid-check update PASS | Нужен реальный fresh provider |
| Сбой provider скрывается как актуальность | Нельзя считать отсутствие данных совпадением | unavailable/not_checked, строгая identity | Failure/mismatch/revoke PASS | Источник ещё не подключён |

## Следующие условия

Связать actual runtime с проверенным read-only источником файлов; подтвердить source/material identity и свежесть; настроить доверенную проверку извлечённых критериев; выбрать стратегию обновления без двойных watcher; перед реальной отправкой заново авторизовать и подготовить ответ. Сейчас ничего не включается. Real Disk/mail/journal/Calendar/Telegram, Apps Script, relay, secrets и triggers не менялись. Offline tests не подтверждают real integrations.
