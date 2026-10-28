"""Offline synthetic review demo. No credentials, network, files or real students.

The only on-disk state is a TemporaryDirectory SQLite database, deleted on exit.
The validator below is deliberately synthetic; it is not a production validator.
"""
import io
from pathlib import Path
import tempfile
import zipfile
from assignment_review import read_presentation
from content_evidence import Citation, Finding, review_with_findings
from material_pipeline import MaterialProvider, ValidatedRubrics
from material_versions import MaterialCatalog

P='http://schemas.openxmlformats.org/presentationml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'


def synthetic_work(count):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        archive.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'+''.join(f'<p:sldId id="{256+i}" r:id="r{i}"/>' for i in range(count))+'</p:sldIdLst></p:presentation>')
        archive.writestr('ppt/_rels/presentation.xml.rels',f'<Relationships xmlns="{PKG}">'+''.join(f'<Relationship Id="r{i}" Type="{R}/slide" Target="slides/s{i}.xml"/>' for i in range(count))+'</Relationships>')
        for i in range(count):
            archive.writestr(f'ppt/slides/s{i}.xml',f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><a:t>Synthetic example</a:t></p:cSld></p:sld>')
    return stream.getvalue()


class SyntheticSource:
    def read(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:
            archive.writestr(zipfile.ZipInfo('word/document.xml'),'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic example: 40 slides and original diagrams</w:t></w:r></w:p></w:body></w:document>')
        return stream.getvalue()


def synthetic_validator(document):
    return ValidatedRubrics(document.source_sha256,document.parser_version,'synthetic-demo-validator-1',document.review_reasons,
                           {'makeup-3':{'kind':'lecture_makeup','number':3,
                                        'requirements':['Минимум 40 слайдов','Авторские схемы и научная правильность'],
                                        'structural_checks':[{'measure':'slide_count','requirement_index':0,'minimum':40}]}})


def run_demo():
    lines=['# Демонстрация проверки — только искусственные данные','',
           'Нет реальных студентов, сети, писем, оценок и записи в журнал. Валидатор демонстрационный.','',
           '| Случай | Число слайдов | Содержание | Итог |','|---|---|---|---|']
    provider=MaterialProvider(SyntheticSource(),validator=synthetic_validator)
    with tempfile.TemporaryDirectory() as directory:
        with MaterialCatalog(Path(directory)/'state.db',namespace='synthetic-demo') as catalog:
            for count in (39,40):
                evidence=read_presentation(synthetic_work(count))
                # Submission revision identity is content-bound, not a filename.
                plan=catalog.prepare('revision-'+evidence.sha256,'synthetic-material','makeup-3',fetch_current=provider)
                observation=Finding(plan.id,plan.version,evidence.sha256,1,'uncertain','Текст есть, но научная правильность и авторство не проверены.',
                                    (Citation('ppt/slides/s0.xml',0,17,'Synthetic example'),))
                report=review_with_findings(plan,evidence,[observation],reviewer_version='synthetic-demo-reviewer-1')
                if catalog.finish(plan.id,report,fetch_current=provider)!='done':
                    raise RuntimeError('Synthetic source unexpectedly changed')
                label='выполнено' if report['requirements'][0]['status']=='met' else 'не выполнено'
                lines.append(f'| Презентация {count} | {label} ({count}/40) | нужна проверка | решение преподавателя |')
    lines.extend(['','Цитата на слайде 1: «Synthetic example». Подтверждено наличие текста, не качество работы.',
                  'Завершённая локальная запись отчёта не означает принятую отработку.'])
    return '\n'.join(lines)+'\n'

if __name__=='__main__':print(run_demo(),end='')
