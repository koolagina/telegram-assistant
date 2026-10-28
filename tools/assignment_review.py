"""Local PPTX structural pilot. No semantic grader, marks, credit or network.

Only explicitly configured minimum slide count is checked. Slide text is
untrusted evidence, never executable instructions. Drawings, images, authorship,
scientific correctness, navigation and conclusions require content review.
"""
from dataclasses import dataclass, field
import hashlib
import io
import posixpath
import zipfile
import xml.etree.ElementTree as ET
from material_versions import CheckPlan, digest

P='{http://schemas.openxmlformats.org/presentationml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A='{http://schemas.openxmlformats.org/drawingml/2006/main}'
PKG='{http://schemas.openxmlformats.org/package/2006/relationships}'
SLIDE_REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide'
MAX_INPUT=16*1024*1024
MAX_EXPANDED=32*1024*1024

class ReviewError(ValueError):
    pass

@dataclass(frozen=True)
class SlideEvidence:
    part: str
    text: str = field(repr=False)
    hidden: bool = False

@dataclass(frozen=True)
class PresentationEvidence:
    sha256: str
    slides: tuple = field(repr=False)
    reader_version: str = 'pptx-evidence-1'
    requires_content_review: bool = True

    @property
    def slide_count(self):return len(self.slides)


def _xml(archive,name):
    raw=archive.read(name)
    scan=raw.replace(b'\x00',b'').upper()
    if b'<!DOCTYPE' in scan or b'<!ENTITY' in scan:
        raise ReviewError('Unsafe XML declarations')
    return ET.fromstring(raw)


def read_presentation(content):
    if type(content) is not bytes or not 0<len(content)<=MAX_INPUT:
        raise ReviewError('Invalid presentation size/type')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries=archive.infolist();names=[entry.filename for entry in entries]
            if (len(entries)>4096 or len(names)!=len(set(names))
                    or sum(entry.file_size for entry in entries)>MAX_EXPANDED
                    or any(entry.flag_bits & 1 for entry in entries)
                    or any('vba' in name.lower() for name in names)):
                raise ReviewError('Unsupported presentation archive')
            presentation=_xml(archive,'ppt/presentation.xml')
            relationships=_xml(archive,'ppt/_rels/presentation.xml.rels')
            if presentation.tag!=P+'presentation' or relationships.tag!=PKG+'Relationships':
                raise ReviewError('Invalid presentation structure')
            links={}
            for link in relationships:
                if link.tag!=PKG+'Relationship' or not link.get('Id') or link.get('Id') in links:
                    raise ReviewError('Ambiguous presentation relationships')
                links[link.get('Id')]=link
            slide_list=presentation.find(P+'sldIdLst')
            if slide_list is None or not 0<len(slide_list)<=1000:
                raise ReviewError('Missing or excessive slides')
            slides=[];seen=set();ids=set()
            for item in slide_list:
                relationship=links.get(item.get(R+'id'))
                if (item.tag!=P+'sldId' or not item.get('id') or item.get('id') in ids
                        or relationship is None or relationship.get('Type')!=SLIDE_REL
                        or relationship.get('TargetMode','Internal')!='Internal'):
                    raise ReviewError('Invalid slide reference')
                ids.add(item.get('id'))
                target=relationship.get('Target','')
                if (not target.startswith('slides/') or '\\' in target
                        or any(part in ('','..','.') for part in target.split('/'))
                        or not target.endswith('.xml')):
                    raise ReviewError('Slide target refused')
                part=posixpath.join('ppt',target)
                if part in seen:raise ReviewError('Repeated slide target')
                seen.add(part)
                slide=_xml(archive,part)
                if slide.tag!=P+'sld' or slide.get('show','1') not in ('0','1','true','false'):
                    raise ReviewError('Invalid slide structure')
                slides.append(SlideEvidence(part,'\n'.join(t.text or '' for t in slide.iter(A+'t')),slide.get('show') in ('0','false')))
            return PresentationEvidence(hashlib.sha256(content).hexdigest(),tuple(slides))
    except ReviewError:raise
    except Exception:
        raise ReviewError('Presentation could not be safely read') from None


def review_presentation(plan, evidence, *, slide_requirement_index, minimum_slides):
    """Generate observations from an explicitly configured trusted criterion.

    Threshold/index are application configuration, not inferred from submission.
    They are included in the result and evaluator digest for reproducibility.
    The caller must bind this configuration to its validated rubric before use.
    """
    if type(plan) is not CheckPlan or type(evidence) is not PresentationEvidence:
        raise ReviewError('Explicit versioned plan and presentation evidence required')
    requirements=plan.rules.get('requirements')
    if (type(requirements) is not list or not requirements
            or any(not isinstance(item,str) or not item.strip() for item in requirements)
            or type(slide_requirement_index) is not int or not 0<=slide_requirement_index<len(requirements)
            or type(minimum_slides) is not int or minimum_slides<1):
        raise ReviewError('Explicit structural requirement configuration required')
    configuration={'requirement_index':slide_requirement_index,'minimum_slides':minimum_slides}
    checks=[]
    hidden=any(slide.hidden for slide in evidence.slides)
    for index,requirement in enumerate(requirements):
        item={'requirement_index':index,'requirement':requirement,'status':'needs_review','evidence':[]}
        if index==slide_requirement_index:
            item.update(status='needs_review' if hidden else ('met' if evidence.slide_count>=minimum_slides else 'not_met'),
                        evidence=[{'kind':'slide_count','value':evidence.slide_count,'minimum':minimum_slides,
                                   'parts':[slide.part for slide in evidence.slides], 'has_hidden_slides':hidden}])
        checks.append(item)
    return {'check_id':plan.id,'material_version':plan.version,'assignment_id':plan.assignment_id,
            'submission_sha256':evidence.sha256,'submission_reader_version':evidence.reader_version,
            'evaluator_version':'structural-pilot-1','configuration':configuration,
            'evaluation_key':digest([plan.id,evidence.sha256,evidence.reader_version,'structural-pilot-1',configuration]),
            'status':'needs_teacher_review','requirements':checks,'credit_written':False}
