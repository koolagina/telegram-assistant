"""Default-unwired local lecture commands; no sends, API or journal writes.

Trusted transport supplies Context and stable request_id, never user text. This
preparation may create a local window/attendance record. Repeated preparation
uses durable window request dedup and unique lecture/student attendance identity.
Code text is private; never log reply.text or input /attend messages.
"""
import re
from zoneinfo import ZoneInfo
from assistant_access import identifier
from lecture_windows import LectureWindows,WindowError
from report_requests import PreparedReply


def prepare_lecture_reply(service,context,command,*,request_id):
    if type(command) is not str or len(command)>300 or not identifier(request_id):
        return PreparedReply('invalid_request','Используйте /lecturecode ID_лекции или /attend ID_лекции КОД.')
    opened=re.fullmatch(r'/lecturecode ([^\s]+)',command)
    attended=re.fullmatch(r'/attend ([^\s]+) ([0-9]{4})',command)
    if opened is None and attended is None:
        return PreparedReply('invalid_request','Используйте /lecturecode ID_лекции или /attend ID_лекции КОД.')
    try:
        if type(service) is not LectureWindows:raise WindowError()
        if opened is not None:
            window=service.open(context,opened[1],request_id)
            expires=window.expires_at.astimezone(ZoneInfo('Asia/Yekaterinburg')).strftime('%H:%M:%S')
            return PreparedReply('prepared','Код лекции: '+window.code+'\nДействует до '+expires+' (Екатеринбург).\nОкно — 90 секунд с момента открытия. Повторный запрос его не продлевает.')
        result=service.register_authenticated(context,attended[1],attended[2])
        if not result.accepted:raise WindowError()
        return PreparedReply('prepared','Отметка сохранена локально. В журнал ещё не перенесена; это не подтверждение физического присутствия.')
    except Exception:
        return PreparedReply('unavailable','Операция недоступна. Проверьте доступ, занятие и срок действия кода.')
