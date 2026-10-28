"""End-to-end local demo; all policy identities/materials/work are synthetic.

Uses real private SQLite files under a temporary directory, never Google/Yandex,
Telegram, email, secrets or original work. Synthetic authentication and validator
are deliberate fixtures, NOT production adapters or a launch-ready assistant.
"""
from contextlib import ExitStack
from dataclasses import replace
import datetime as dt
from pathlib import Path
import tempfile
from assistant_access import AccessPolicy,Binding,Context,Enrollment,Student,Teacher,AcademicReadGrant
from assignment_review import read_presentation
from content_evidence import Citation,Finding,review_with_findings
from material_pipeline import MaterialProvider
from material_versions import MaterialCatalog,digest
from report_access import ReportLink,ReportReader
from report_registry import ReportRegistry
from policy_store import PolicyStore
from report_requests import prepare_report_reply,prepare_progress_callback
from review_demo import synthetic_work,SyntheticSource,synthetic_validator

NOW=dt.datetime(2026,10,28,12,tzinfo=dt.timezone(dt.timedelta(hours=5)))
START=NOW-dt.timedelta(days=1);END=NOW+dt.timedelta(days=1)


def synthetic_policy(bindings=None):
    return AccessPolicy(teachers=(Teacher('owner'),),students=(Student('student-a'),Student('student-b')),
        bindings=bindings if bindings is not None else (
            Binding('telegram','103','student','student-a',frozenset({'progress.self'}),confirmed=True),
            Binding('telegram','104','student','student-b',frozenset({'progress.self'}),confirmed=True),
            Binding('telegram','101','teacher','owner',frozenset({'student.report','personal.read'}),confirmed=True)),
        enrollments=(Enrollment('enrollment-a','student-a','discipline','group',START,END),
                     Enrollment('enrollment-b','student-b','discipline','group',START,END)),
        academic_read_grants=(AcademicReadGrant('owner-full','owner',START,END),))

class SyntheticAssistantSession:
    def __init__(self,directory):
        self.directory=Path(directory);self._stack=None
        self.provider=MaterialProvider(SyntheticSource(),validator=synthetic_validator)
    def __enter__(self):
        self.restart_storage();return self
    def __exit__(self,*args):
        if self._stack is not None:self._stack.close();self._stack=None
    def restart_storage(self):
        if self._stack is not None:self._stack.close()
        self._stack=ExitStack()
        try:
            self.catalog=self._stack.enter_context(MaterialCatalog(self.directory/'materials.sqlite3',namespace='synthetic-assistant'))
            self.registry=self._stack.enter_context(ReportRegistry(self.directory/'reports.sqlite3',namespace='synthetic-assistant'))
            self.policies=self._stack.enter_context(PolicyStore(self.directory/'policy.sqlite3',namespace='synthetic-assistant'))
            if self.policies.load()[0]==0:
                self.policies.save(synthetic_policy(),expected_revision=0)  # Explicit fake fixture only.
        except Exception:
            self._stack.close();raise
    @property
    def policy(self):return self.policies.load()[1]
    @policy.setter
    def policy(self,value):
        revision,_=self.policies.load()
        self.policies.save(value,expected_revision=revision)
    def ingest(self,slide_count):
        work=read_presentation(synthetic_work(slide_count))
        plan=self.catalog.prepare('submission-'+digest(['student-a',work.sha256]),'demo-material','makeup-3',fetch_current=self.provider)
        finding=Finding(plan.id,plan.version,work.sha256,1,'uncertain','Нужна содержательная проверка преподавателя.',
                        (Citation('ppt/slides/s0.xml',0,17,'Synthetic example'),))
        report=review_with_findings(plan,work,[finding],reviewer_version='synthetic-demo-1')
        if self.catalog.finish(plan.id,report,fetch_current=self.provider)!='done':raise RuntimeError('Synthetic source unexpectedly changed')
        link=ReportLink('report-'+plan.id,plan.id,'enrollment-a','student-a','discipline','group')
        self.registry.register(link,load_result=self.catalog.result)
        return link.id
    def reader(self):
        # Fresh durable ownership snapshot for each new request/click.
        return ReportReader(self.registry.snapshot(),policy_provider=lambda:self.policy,load_result=self.catalog.result,clock=lambda:NOW)
    def request(self,subject,command):
        return prepare_report_reply(self.reader(),Context('telegram',{'student-a':'103','student-b':'104','owner':'101'}.get(subject,subject),authenticated=True,private=True),command)
    def callback(self,subject,data):
        return prepare_progress_callback(self.reader(),Context('telegram',{'student-a':'103','student-b':'104','owner':'101'}.get(subject,subject),authenticated=True,private=True),data)
    def revoke_student_a(self):
        self.policy=synthetic_policy(tuple(replace(binding,active=False) if binding.subject=='103' else binding for binding in self.policy.bindings.values()))


def run_assistant_demo():
    with tempfile.TemporaryDirectory() as directory:
        with SyntheticAssistantSession(Path(directory)) as session:
            reference=session.ingest(40)
            if session.ingest(40)!=reference:raise RuntimeError('Duplicate ingest changed identity')
            page=session.request('student-a','/progress');button=page.buttons[0][0]
            session.restart_storage()
            result=session.callback('student-a',button.callback_data)
            foreign=session.callback('student-b',button.callback_data)
            session.revoke_student_a();revoked=session.callback('student-a',button.callback_data)
            if result.status!='prepared' or foreign.status!='unavailable' or revoked.status!='unavailable':
                raise RuntimeError('Synthetic access scenario failed')
    return '\n'.join(['# Сквозной сценарий — искусственные данные','',
        'Нет сети, настоящих аккаунтов, писем, баллов и записи в журнал. Authentication и validator демонстрационные.','',
        '- Повторная загрузка одной работы: один отчёт.',
        '- Список работ и кнопка открытия: пройдены.',
        '- Перезапуск хранилища: пройден.',
        '- Чужая кнопка: доступ закрыт.',
        '- Отозванный доступ: закрыт.','',
        'Результат работы: нужна проверка преподавателя. Хранение links не создаёт прав или реальной authentication.',
        'Снимки прав также сохраняются локально с revision CAS. Это не настоящая authentication и не разрешение использовать demonstration identities в production.'])+'\n'

if __name__=='__main__':print(run_assistant_demo(),end='')
