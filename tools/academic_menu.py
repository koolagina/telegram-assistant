"""Read-only local academic selection, not authentication or a deployed menu.

Entries/labels and policy MUST come from the confirmed server registry, never
from student text/LLM output. Hash references are navigation, not credentials.
No names are inferred from a workbook, no data is written or sent. The runtime
must construct a fresh menu and reprepare immediately before actual dispatch.
"""
from dataclasses import dataclass,field
import hashlib
import json
import re
from academic_progress import ProgressReader,ProgressError
from academic_overview import AcademicOverview,render_overview
from assistant_access import AccessPolicy,Context,aware,identifier
from report_requests import PreparedReply,ReplyButton,_text,_bounded

class MenuError(ValueError):
    pass

@dataclass(frozen=True)
class MenuEntry:
    enrollment_id: str
    student_label: str = field(repr=False)
    teacher_label: str = field(repr=False)

UNAVAILABLE=PreparedReply('unavailable','Сводка недоступна. Откройте меню заново и проверьте доступ.')

class AcademicMenu:
    def __init__(self,entries,*,journal,overview,policy_provider,clock):
        try:
            if type(journal) is not ProgressReader or type(overview) is not AcademicOverview or not callable(policy_provider) or not callable(clock):raise ValueError()
            records={}
            for entry in entries:
                if (type(entry) is not MenuEntry or not identifier(entry.enrollment_id) or entry.enrollment_id in records
                        or any(type(v) is not str or not _text(v) or len(v)>120 for v in (entry.student_label,entry.teacher_label))):raise ValueError()
                records[entry.enrollment_id]=entry
                if len(records)>10000:raise ValueError()
            self._entries=tuple(sorted(records.values(),key=lambda e:e.enrollment_id))
            self._revision=hashlib.sha256(json.dumps([(e.enrollment_id,e.student_label,e.teacher_label) for e in self._entries],ensure_ascii=True).encode()).hexdigest()
            self._journal=journal;self._overview=overview;self._policy=policy_provider;self._clock=clock
        except Exception:raise MenuError('Invalid trusted academic menu') from None

    def _principal(self,context,mode):
        policy=self._policy();now=self._clock()
        if type(policy) is not AccessPolicy or not aware(now) or type(context) is not Context:raise MenuError()
        # Reuse policy's canonical authenticated binding checks, including group,
        # sender, confirmed/active registry entity and channel restrictions.
        binding=policy._principal(context)
        purpose='progress.self' if mode=='s' else 'student.report'
        if (mode not in ('s','t') or binding is None or binding.role!=('student' if mode=='s' else 'teacher')
                or purpose not in binding.capabilities or context.channel!='telegram'):raise MenuError()
        return purpose

    def _allowed(self,context,mode):
        purpose=self._principal(context,mode);allowed=[]
        for entry in self._entries:
            try:self._journal.authorize_enrollment(entry.enrollment_id,context,purpose=purpose)
            except ProgressError:continue
            allowed.append(entry)
        self._principal(context,mode)
        return purpose,allowed

    def _ref(self,context,mode,entry=None):
        data=[self._revision,context.channel,context.subject,mode,entry.enrollment_id if entry else 'page']
        return hashlib.sha256(json.dumps(data,ensure_ascii=True).encode()).hexdigest()[:32]

    def prepare(self,context,command):
        if type(command) is not str:return PreparedReply('invalid_request','Откройте /overview или /student.')
        match=re.fullmatch(r'/(overview|student)(?: page ([1-9][0-9]{0,5}|1000000))?',command)
        if match is None:return PreparedReply('invalid_request','Откройте /overview или /student.')
        return self._page(context,'s' if match[1]=='overview' else 't',int(match[2] or '1'))

    def _page(self,context,mode,page):
        try:
            purpose,entries=self._allowed(context,mode)
            selected=entries[(page-1)*5:page*5];buttons=[]
            lines=['Мои дисциплины' if mode=='s' else 'Студенты и дисциплины','Страница '+str(page)]
            for entry in selected:
                label=_text(entry.student_label if mode=='s' else entry.teacher_label)
                lines.append(label)
                buttons.append((ReplyButton(label[:60],'acad:'+mode+':o:'+self._ref(context,mode,entry)+':1'),))
            if not selected:lines.append('Нет доступных записей на этой странице. Это не означает отсутствие задолженности.')
            nav=[];ref=self._ref(context,mode)
            if page>1:nav.append(ReplyButton('Назад',f'acad:{mode}:p:{ref}:{page-1}'))
            if page*5<len(entries):nav.append(ReplyButton('Далее',f'acad:{mode}:p:{ref}:{page+1}'))
            if nav:buttons.append(tuple(nav))
            # Recheck each displayed label before returning personal information.
            for entry in selected:self._journal.authorize_enrollment(entry.enrollment_id,context,purpose=purpose)
            self._principal(context,mode)
            return PreparedReply('prepared',_bounded('\n'.join(lines)),buttons=tuple(buttons))
        except Exception:return UNAVAILABLE

    def callback(self,context,data):
        try:
            if type(data) is not str or len(data.encode())>64:raise MenuError()
            match=re.fullmatch(r'acad:([st]):([op]):([a-f0-9]{32}):([1-9][0-9]{0,5}|1000000)',data)
            if match is None:raise MenuError()
            mode,operation,reference=match[1],match[2],match[3];page=int(match[4])
            purpose,entries=self._allowed(context,mode)
            if operation=='p':
                if reference!=self._ref(context,mode):raise MenuError()
                return self._page(context,mode,page)
            matches=[e for e in entries if self._ref(context,mode,e)==reference]
            if len(matches)!=1:raise MenuError()
            entry=matches[0]
            result=self._overview.read(entry.enrollment_id,context,purpose=purpose,page=page)
            reply=render_overview(result,purpose=purpose,next_command=('/overview' if mode=='s' else '/student')+' '+entry.enrollment_id)
            self._journal.authorize_enrollment(entry.enrollment_id,context,purpose=purpose)
            self._principal(context,mode)
            # Returning to the menu also rechecks the current policy.
            nav=[]
            if page>1:nav.append(ReplyButton('Предыдущие работы',f'acad:{mode}:o:{reference}:{page-1}'))
            if result['reviews']['next_page'] is not None:nav.append(ReplyButton('Следующие работы',f'acad:{mode}:o:{reference}:{page+1}'))
            buttons=([tuple(nav)] if nav else [])+[(ReplyButton('К выбору',f'acad:{mode}:p:{self._ref(context,mode)}:1'),)]
            return PreparedReply('prepared',reply.text,buttons=tuple(buttons))
        except Exception:return UNAVAILABLE
