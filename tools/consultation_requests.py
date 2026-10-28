"""LOCAL sandbox UI with explicit mutations. Not a report-worker preparer.

Caller supplies a trusted authenticated Context, never identity from callback
text. Do NOT wire these handlers to prepare_fresh, a sender retry or production:
they write local intents/plans. A real command dispatcher needs separate durable
update processing and a reviewed external executor. No such executor is present.
"""
import datetime as dt
import re
from consultation_actions import ConsultationActions,ActionError,TZ
from report_requests import PreparedReply,ReplyButton,_bounded,_text

UNAVAILABLE=PreparedReply('unavailable','Действие недоступно или изменилось. Обновите заявку и проверьте источники.')
LABELS={'approve':'Подтвердить консультацию','reject':'Отклонить заявку','propose':'Предложить другое время'}


def consultation_card(service,context,booking_id):
    try:
        if type(service) is not ConsultationActions:raise ActionError('Unavailable')
        reference=service.reference(context,booking_id);booking=service.resolve(context,reference)
        text=('Локальный кандидат — консультация\nЗаявка: '+_text(booking.id)+'\n'
              +booking.starts_at.astimezone(TZ).strftime('%d.%m.%Y %H:%M')+' · 20 минут · кабинет 317\n'
              +'Статус локальной модели: '+_text(booking.status)+'\n'
              +'Календарь и сообщения не изменяются. Каждое действие требует отдельного подтверждения.')
        buttons=((ReplyButton('Подтвердить','con:a:approve:'+reference),ReplyButton('Отклонить','con:a:reject:'+reference)),
                 (ReplyButton('Предложить время','con:p:'+reference),))
        return PreparedReply('prepared',_bounded(text),buttons=buttons)
    except Exception:return UNAVAILABLE


def _preview(intent):
    text=('Подтвердить действие: '+LABELS[intent.action]+'?\nЗаявка: '+_text(intent.booking_id)+'\n'
          +intent.starts_at.astimezone(TZ).strftime('%d.%m.%Y %H:%M')+' · кабинет 317\n'
          +'Подтверждение действует до '+intent.expires_at.astimezone(TZ).strftime('%H:%M')+'.\n'
          +'Будет сохранён только локальный план. Реальные операции отключены.')
    if intent.action=='propose':text+='\nПрежний резерв остаётся до согласия студента; встреча не переносится автоматически.'
    return PreparedReply('prepared',_bounded(text),buttons=((ReplyButton('Да, сохранить план','con:c:'+intent.token),ReplyButton('Назад / отменить','con:x:'+intent.token)),))


def handle_local_consultation_callback(service,context,data):
    try:
        if type(service) is not ConsultationActions or type(data) is not str or not data.isascii() or len(data)>64:raise ActionError('Unavailable')
        match=re.fullmatch(r'con:a:(approve|reject):([a-f0-9]{32})',data)
        if match:
            booking=service.resolve(context,match.group(2))
            # Revision checked again by preview/confirm; token is not authorization.
            return _preview(service.preview(context,booking.id,match.group(1)))
        match=re.fullmatch(r'con:p:([a-f0-9]{32})',data)
        if match:
            service.resolve(context,match.group(1))
            return PreparedReply('prepared','Введите время по Екатеринбургу:\n/consult_propose '+match.group(1)+' YYYY-MM-DD HH:MM\nПрежний резерв будет сохранён; это только предложение.')
        match=re.fullmatch(r'con:([cx]):([a-f0-9]{32})',data)
        if not match:raise ActionError('Unavailable')
        if match.group(1)=='x':
            service.cancel(context,match.group(2))
            return PreparedReply('prepared','Подтверждение отменено. Заявка и календарь не изменены.')
        plan=service.confirm(context,match.group(2))
        return PreparedReply('prepared','Локальный план сохранён: '+LABELS[plan['action']]+'.\nОперации календаря и уведомления не выполнены. Статус рабочего бота не изменён.')
    except Exception:return UNAVAILABLE


def handle_local_proposal(service,context,command):
    try:
        if type(service) is not ConsultationActions or type(command) is not str or len(command)>120:raise ActionError('Unavailable')
        match=re.fullmatch(r'/consult_propose ([a-f0-9]{32}) (\d{4}-\d{2}-\d{2} \d{2}:\d{2})',command,flags=re.ASCII)
        if not match:raise ActionError('Unavailable')
        booking=service.resolve(context,match.group(1))
        start=dt.datetime.strptime(match.group(2),'%Y-%m-%d %H:%M').replace(tzinfo=TZ)
        return _preview(service.preview(context,booking.id,'propose',proposed_start=start))
    except Exception:return UNAVAILABLE
