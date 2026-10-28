"""Read-only decision projections. Call only under the owner queue service.

ConsultationRecord is a normalized trusted export, not a guessed Google API
schema/HTML parser. Existing 11-column GAS sheet is untouched. Real Sheet/date
binding must explicitly supply aware datetimes, never assume its completeness.
"""
from dataclasses import dataclass,field
from assistant_access import aware,identifier
from decision_queue import DecisionItem,DecisionSnapshot
from material_versions import digest
from report_access import ReportLink

@dataclass(frozen=True)
class ConsultationRecord:
    id: str
    status: str
    starts_at: object
    created_at: object
    student_label: str = field(repr=False)
    topic: str = field(repr=False)

@dataclass(frozen=True)
class ConsultationBatch:
    records: tuple = field(repr=False)
    observed_at: object
    complete: bool = True

class ConsultationSource:
    def __init__(self,owner_id,load_records):self.owner=owner_id;self.load=load_records
    def __call__(self,context,policy,now):
        batch=self.load()
        if type(batch) is not ConsultationBatch or type(batch.records) is not tuple or not aware(batch.observed_at) or type(batch.complete) is not bool:
            raise ValueError('Dated verified consultation snapshot required')
        records=batch.records;unique={}
        known={'Ожидает решения','Обработка — требуется сверка при сбое','Подтверждена','Отклонена','Отменена','Создаётся предварительная запись','Отклонение выполняется','Отмена выполняется'}
        for record in records:
            if (type(record) is not ConsultationRecord or not identifier(record.id) or record.status not in known
                    or not aware(record.starts_at) or (record.created_at is not None and not aware(record.created_at))
                    or type(record.student_label) is not str or type(record.topic) is not str):
                raise ValueError('Consultation source requires review')
            if record.id in unique and unique[record.id]!=record:raise ValueError('Conflicting consultation copies')
            unique[record.id]=record
        items=[]
        for record in unique.values():
            if record.status not in ('Ожидает решения','Обработка — требуется сверка при сбое'):continue
            items.append(DecisionItem('consultation',record.id,self.owner,'Решить заявку на консультацию',
                'Студент: '+record.student_label+'\nТема: '+record.topic+'\nСтатус: '+record.status,
                record.created_at,record.starts_at,1 if 'сверка' in record.status else 2,
                steps=('Проверить время и занятость.','После сверки времени подтвердить заявку, отклонить или предложить другое время отдельно.')))
        return DecisionSnapshot(tuple(items),batch.observed_at,batch.complete)

class ReviewSource:
    def __init__(self,owner_id,load_links,load_result):self.owner=owner_id;self.links=load_links;self.load=load_result
    def __call__(self,context,policy,now):
        items=[]
        for link in self.links():
            if type(link) is not ReportLink:raise ValueError('Invalid report ownership')
            enrollment=policy.enrollments.get(link.enrollment_id)
            relation=(link.enrollment_id,link.student_id,link.discipline_id,link.group_id)
            if (enrollment is None or (enrollment.id,enrollment.student_id,enrollment.discipline_id,enrollment.group_id)!=relation
                    or not policy.authorize(context,'student.report',link.enrollment_id,now=now).allowed):continue
            row=self.load(link.check_id)  # Authorization BEFORE private payload read.
            if type(row) is not dict:raise ValueError('Invalid report state')
            if row.get('status')=='pending':continue
            if row.get('status')=='needs_recheck':
                title='Перепроверить работу';detail='Требования изменились во время проверки. Нужна новая проверка по актуальной версии.';priority=1
            elif row.get('status')=='done':
                report=row.get('result')
                if (type(report) is not dict or report.get('check_id')!=link.check_id
                        or report.get('material_version')!=row.get('version') or report.get('credit_written') is not False
                        or report.get('status')!='needs_teacher_review' or type(report.get('requirements')) is not list):
                    raise ValueError('Current review source not verified')
                states=[item.get('status') for item in report['requirements'] if type(item) is dict]
                if len(states)!=len(report['requirements']) or any(x not in ('met','not_met','needs_review') for x in states):raise ValueError('Invalid requirement state')
                title='Проверить работу '+str(report.get('assignment_id',''))
                detail=f"Студент: {link.student_id}\nПризнак не выполнен: {states.count('not_met')}; нужна проверка: {states.count('needs_review')}."
                priority=1 if 'not_met' in states else 2
            else:raise ValueError('Unknown report state')
            detail+='\nОткрыть отчёт: /report '+link.id
            items.append(DecisionItem('review',link.id,self.owner,title,detail,None,None,priority,enrollment=relation,
                steps=('Разобрать требования и подтверждающие фрагменты.','Принятие работы, сообщение студенту и баллы требуют отдельного действия.'),source_version=digest(row)))
        return DecisionSnapshot(tuple(items),now)

class DispatchSource:
    def __init__(self,owner_id,load_attention):self.owner=owner_id;self.load=load_attention
    def __call__(self,context,policy,now):
        items=[]
        labels={'unknown':'Исход отправки неизвестен. Не повторять вслепую.',
                'inflight_or_unknown':'Попытка выполняется либо завершилась без сохранённого ответа. Требуется сверка.',
                'api_rejected':'API отклонил отправку. Автоматический повтор не выполняется.'}
        for row in self.load():
            if (type(row) is not dict or type(row.get('update_id')) is not int or row['update_id']<0 or row.get('status') not in labels):raise ValueError('Invalid dispatch attention state')
            if row['status']=='inflight_or_unknown' and row.get('review_required') is not True:continue
            detail=labels[row['status']]+'\nUpdate: '+str(row['update_id'])
            code=row.get('api_error_code')
            if code is not None:
                if type(code) is not int:raise ValueError('Invalid API error code')
                detail+='\nКод API: '+str(code)
            items.append(DecisionItem('technical',str(row['update_id']),self.owner,'Сверить отправку',detail,None,None,1,
                steps=('Сверить исход операции и доступ адресата.','Не считать ответ API доказательством доставки; повтор требует отдельного решения.'),source_version=digest(row)))
        return DecisionSnapshot(tuple(items),now)
