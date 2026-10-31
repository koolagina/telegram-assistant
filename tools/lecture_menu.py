"""Local private teacher selection for current verified lectures, default unwired.

Titles/rooms come from a trusted registry, not parsed from commands or inferred.
References are navigation only; source and current grants are rechecked on click.
No codes during listing. Opening a selected code mutates local WindowStore only.
No authentication, real timetable import, sending or journal sync here.
"""
from dataclasses import dataclass,field
import re
from zoneinfo import ZoneInfo
from assistant_access import AccessPolicy,Context,aware,identifier
from lecture_windows import LectureWindows,source_digest
from lecture_requests import prepare_lecture_reply
from report_requests import PreparedReply,ReplyButton,_text,_bounded
from material_versions import digest

class LectureMenuError(ValueError):
    pass

@dataclass(frozen=True)
class LectureLabel:
    lecture_id: str
    title: str = field(repr=False)
    room: str = field(default='',repr=False)

UNAVAILABLE=PreparedReply('unavailable','Занятие недоступно. Откройте /lectures заново и проверьте доступ.')

class LectureMenu:
    def __init__(self,labels,*,service):
        try:
            if type(service) is not LectureWindows:raise ValueError()
            records={}
            for label in labels:
                if (type(label) is not LectureLabel or not identifier(label.lecture_id) or label.lecture_id in records
                        or type(label.title) is not str or not _text(label.title) or len(label.title)>120
                        or type(label.room) is not str or len(label.room)>40):raise ValueError()
                records[label.lecture_id]=label
                if len(records)>10000:raise ValueError()
            self._labels=records;self._service=service
            self._revision=digest([(k,v.title,v.room) for k,v in sorted(records.items())])
        except Exception:raise LectureMenuError('Invalid trusted lecture catalog') from None

    def _available(self,context):
        policy=self._service.policy_provider();now=self._service.clock()
        if type(policy) is not AccessPolicy or type(context) is not Context or not aware(now):raise LectureMenuError()
        principal=policy._principal(context)
        if (principal is None or principal.role!='teacher' or context.channel!='telegram'
                or not {'lecture.open','lecture.code.read'}<=principal.capabilities):raise LectureMenuError()
        rows=[]
        for lecture in policy.lectures.values():
            label=self._labels.get(lecture.id)
            if label is not None and policy.authorize(context,'lecture.code.read',lecture.id,now=now).allowed:
                rows.append((lecture,label))
        return principal,sorted(rows,key=lambda pair:(pair[0].starts_at,pair[0].id))

    def _reference(self,context,principal,lecture=None):
        return digest([self._revision,context.channel,context.subject,principal.entity_id,
                       source_digest(lecture) if lecture else 'page'])[:32]

    def prepare(self,context,command):
        if type(command) is not str:return PreparedReply('invalid_request','Откройте /lectures.')
        match=re.fullmatch(r'/lectures(?: page ([1-9][0-9]{0,5}|1000000))?',command)
        if match is None:return PreparedReply('invalid_request','Откройте /lectures.')
        return self._page(context,int(match[1] or '1'))

    def _page(self,context,page):
        try:
            principal,rows=self._available(context);selected=rows[(page-1)*5:page*5]
            lines=['Текущие лекции','Список из локального проверенного расписания; свежесть облачного источника не подтверждена.','Страница '+str(page)];buttons=[]
            for lecture,label in selected:
                time=lecture.starts_at.astimezone(ZoneInfo('Asia/Yekaterinburg')).strftime('%H:%M')+'–'+lecture.ends_at.astimezone(ZoneInfo('Asia/Yekaterinburg')).strftime('%H:%M')
                lines.append(time+' · '+_text(label.title)+(' · ауд. '+_text(label.room) if label.room else ''))
                buttons.append((ReplyButton(_text(label.title)[:60],'lect:o:'+self._reference(context,principal,lecture)),))
            if not selected:lines.append('Сейчас нет доступных подтверждённых лекций на этой странице.')
            ref=self._reference(context,principal);nav=[]
            if page>1:nav.append(ReplyButton('Назад',f'lect:p:{ref}:{page-1}'))
            if page*5<len(rows):nav.append(ReplyButton('Далее',f'lect:p:{ref}:{page+1}'))
            if nav:buttons.append(tuple(nav))
            current,latest=self._available(context)
            if current!=principal or [(l.id,source_digest(l)) for l,_ in rows]!=[(l.id,source_digest(l)) for l,_ in latest]:raise LectureMenuError()
            return PreparedReply('prepared',_bounded('\n'.join(lines)),buttons=tuple(buttons))
        except Exception:return UNAVAILABLE

    def callback(self,context,data,*,request_id):
        try:
            if type(data) is not str or len(data.encode())>64 or not identifier(request_id):raise LectureMenuError()
            principal,rows=self._available(context)
            page=re.fullmatch(r'lect:p:([a-f0-9]{32}):([1-9][0-9]{0,5}|1000000)',data)
            if page:
                if page[1]!=self._reference(context,principal):raise LectureMenuError()
                return self._page(context,int(page[2]))
            opened=re.fullmatch(r'lect:o:([a-f0-9]{32})',data)
            if opened is None:raise LectureMenuError()
            matches=[lecture for lecture,_ in rows if self._reference(context,principal,lecture)==opened[1]]
            if len(matches)!=1:raise LectureMenuError()
            lecture=matches[0]
            reply=prepare_lecture_reply(self._service,context,'/lecturecode '+lecture.id,request_id=request_id,expected_source=source_digest(lecture))
            if reply.status!='prepared':return UNAVAILABLE
            # Do not return a code if source/role changed during the local action.
            current,latest=self._available(context)
            if current!=principal or not any(l.id==lecture.id and source_digest(l)==source_digest(lecture) for l,_ in latest):raise LectureMenuError()
            self._service.show(context,lecture.id)  # Rechecks opening authority/expiry/AEAD.
            return PreparedReply('prepared',reply.text,buttons=((ReplyButton('К текущим лекциям','lect:p:'+self._reference(context,principal)+':1'),),))
        except Exception:return UNAVAILABLE
