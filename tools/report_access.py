"""Policy-gated local report projections, not authentication or a transport.

Links, context, registry provider, clock and storage loader MUST be supplied by
trusted server code. Never construct ReportLink/Context from student input.
No persistent link registry, Telegram/ChatGPT/email endpoint or sending here.
"""
from dataclasses import dataclass
import json
from types import MappingProxyType
from assistant_access import AccessPolicy, identifier, live, aware

class ReportAccessError(ValueError):
    pass

@dataclass(frozen=True)
class ReportLink:
    id: str
    check_id: str
    enrollment_id: str
    student_id: str
    discipline_id: str
    group_id: str


def _pick(value,keys):
    return {key:value[key] for key in keys if key in value}


class ReportReader:
    def __init__(self, links, *, policy_provider, load_result, clock):
        records={}
        for link in links:
            if (type(link) is not ReportLink or any(not identifier(value) for value in vars(link).values())
                    or link.id in records):
                raise ReportAccessError('Invalid trusted report registry')
            records[link.id]=link
        if not all(callable(value) for value in (policy_provider,load_result,clock)):
            raise ReportAccessError('Trusted runtime adapters required')
        self._links=MappingProxyType(records)
        self._policy=policy_provider;self._load=load_result;self._clock=clock

    def _mode(self,link,context):
        policy=self._policy();now=self._clock()
        if type(policy) is not AccessPolicy or not aware(now):
            raise ReportAccessError('Report unavailable')
        enrollment=policy.enrollments.get(link.enrollment_id)
        if (enrollment is None or enrollment.student_id!=link.student_id
                or enrollment.discipline_id!=link.discipline_id or enrollment.group_id!=link.group_id):
            raise ReportAccessError('Report unavailable')
        if policy.authorize(context,'student.report',enrollment.id,now=now).allowed:
            return 'teacher'
        if live(enrollment,now) and policy.authorize(context,'progress.self',enrollment.student_id,now=now).allowed:
            return 'student'
        raise ReportAccessError('Report unavailable')

    def read(self,report_id,context,*,purpose=None):
        try:
            if not identifier(report_id) or report_id not in self._links:
                raise ReportAccessError('Report unavailable')
            link=self._links[report_id]
            if purpose not in (None,'progress.self','student.report'):
                raise ReportAccessError('Report unavailable')
            initial_mode=self._mode(link,context)  # Deny before loading payload.
            required_mode={'progress.self':'student','student.report':'teacher'}.get(purpose)
            if required_mode is not None and initial_mode!=required_mode:
                raise ReportAccessError('Report unavailable')
            row=self._load(link.check_id)
            if (type(row) is not dict or row.get('status')!='done' or type(row.get('result')) is not dict):
                raise ReportAccessError('Report unavailable')
            report=row['result']
            if (report.get('check_id')!=link.check_id or report.get('material_version')!=row.get('version')
                    or not identifier(row.get('version')) or report.get('status')!='needs_teacher_review'
                    or report.get('credit_written') is not False or type(report.get('requirements')) is not list):
                raise ReportAccessError('Report unavailable')
            # Recheck current binding/grants after storage access, including role downgrade.
            mode=self._mode(link,context)
            if required_mode is not None and mode!=required_mode:
                raise ReportAccessError('Report unavailable')
            result=_pick(report,('assignment_id','status','credit_written'))
            result['requirements']=[]
            for item in report['requirements']:
                if (type(item) is not dict or not isinstance(item.get('requirement'),str)
                        or item.get('status') not in ('met','not_met','needs_review')):
                    raise ReportAccessError('Report unavailable')
                projected=_pick(item,('requirement_index','requirement','status'))
                if mode=='teacher':
                    if 'evidence' in item:
                        projected['evidence']=[_pick(e,('kind','value','minimum','parts','has_hidden_slides')) for e in item['evidence']]
                    if 'content_observation' in item:
                        observation=item['content_observation']
                        projected['content_observation']=_pick(observation,('stance','comment','status'))
                        if 'citations' in observation:
                            projected['content_observation']['citations']=[_pick(c,('part','start','end','quote')) for c in observation['citations']]
                result['requirements'].append(projected)
            # Return a detached JSON copy; mutations cannot change stored history.
            return json.loads(json.dumps(result,allow_nan=False))
        except Exception:
            # Same safe response for missing/forbidden/corrupt report, no oracle/log leak.
            raise ReportAccessError('Report unavailable') from None
