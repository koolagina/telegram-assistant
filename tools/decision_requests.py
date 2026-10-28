"""Owner-only read-only decision menu. No approval/grade/send actions."""
import re
from decision_queue import DecisionQueue,DecisionError,KINDS,TZ
from report_requests import PreparedReply,ReplyButton,_text,_bounded

LABELS={'consultation':'Консультации','review':'Проверки работ','technical':'Технические сбои'}
UNAVAILABLE=PreparedReply('unavailable','Пункт недоступен или изменился. Обновите очередь и проверьте доступ.')


def prepare_decision_reply(service,context,command):
    if type(command) is not str or len(command)>80:
        return PreparedReply('invalid_request','Используйте /decisions.')
    match=re.fullmatch(r'/decisions(?: page ([1-9][0-9]{0,5}|1000000))?',command)
    if match is None:return PreparedReply('invalid_request','Используйте /decisions.')
    return _page(service,context,int(match.group(1) or '1'),None)


def _page(service,context,page,category):
    try:
        if type(service) is not DecisionQueue:raise DecisionError('Unavailable')
        view=service.page(context,page=page,category=category)
    except DecisionError:return UNAVAILABLE
    lines=['Что требует моего решения — '+view.day,
           ' · '.join(LABELS[k]+': '+str(view.counts[k]) for k in KINDS),
           'Страница '+str(page)+((' · '+LABELS[category]) if category else ''),'']
    if view.partial:
        lines.extend(['Сводка неполная: не удалось проверить '+', '.join(LABELS[k].lower() for k in view.warnings)+'.',''])
    buttons=[tuple(ReplyButton(LABELS[k],'dec:p:'+k+':1') for k in KINDS)]
    for number,entry in enumerate(view.items,1):
        marker={'overdue':'Просрочено','today':'Сегодня','pending':'Ожидает решения'}[entry.urgency]
        due=' · '+entry.item.due_at.astimezone(TZ).strftime('%d.%m %H:%M') if entry.item.due_at else ''
        lines.append(f'{number}. [{marker}] '+_text(entry.item.title)[:120]+due)
        buttons.append((ReplyButton('Подробнее '+str(number),'dec:o:'+entry.reference),))
    if not view.items:
        lines.append('Нет доступных пунктов на этой странице.' if page>1 or category or view.partial else 'Решений не требуется по проверенным источникам.')
    navigation=[];filter_name=category or 'all'
    if page>1:navigation.append(ReplyButton('Назад',f'dec:p:{filter_name}:{page-1}'))
    if view.next_page is not None:navigation.append(ReplyButton('Далее',f'dec:p:{filter_name}:{view.next_page}'))
    if navigation:buttons.append(tuple(navigation))
    buttons.append((ReplyButton('Обновить / все пункты','dec:p:all:1'),))
    return PreparedReply('prepared',_bounded('\n'.join(lines)),buttons=tuple(buttons))


def prepare_decision_callback(service,context,data):
    if type(data) is not str or not data.isascii() or len(data)>64:return UNAVAILABLE
    page=re.fullmatch(r'dec:p:(all|consultation|review|technical):([1-9][0-9]{0,5}|1000000)',data)
    if page:return _page(service,context,int(page.group(2)),None if page.group(1)=='all' else page.group(1))
    detail=re.fullmatch(r'dec:o:([a-f0-9]{32})',data)
    if detail is None:return UNAVAILABLE
    try:
        if type(service) is not DecisionQueue:raise DecisionError('Unavailable')
        entry=service.detail(context,detail.group(1));item=entry.item
    except DecisionError:return UNAVAILABLE
    lines=[_text(item.title),'Никакие решения и изменения данных здесь автоматически не выполняются.','']
    if item.due_at:lines.append('К сроку: '+item.due_at.astimezone(TZ).strftime('%d.%m.%Y %H:%M'))
    lines.extend(['\n'.join(_text(line) for line in item.detail.splitlines()),'','Дальнейшие шаги:'])
    lines.extend('• '+_text(step) for step in item.steps)
    if not item.steps:lines.append('• Рассмотреть источник и принять решение отдельно.')
    return PreparedReply('prepared',_bounded('\n'.join(lines)),buttons=((ReplyButton('К очереди','dec:p:all:1'),),))
