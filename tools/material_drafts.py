"""Conservative numbered assignment drafts with verbatim paragraph evidence.

No semantic inference, threshold, approval or grading. Fail closed when the
numbered layout isn't understood. Only standalone heading paragraphs match.
"""
from dataclasses import dataclass, field
import re
from material_docx import ExtractedDocument

HEADING = re.compile(r'^\s*(?:ДЗ|Домашнее\s+задание)\s*№\s*([1-9][0-9]*)(?=\s|[.:—–-]|$)',re.IGNORECASE)

class DraftError(ValueError):
    pass

@dataclass(frozen=True)
class AssignmentDraft:
    kind: str
    number: int
    heading: str = field(repr=False)
    requirements: tuple = field(repr=False)
    paragraph_indices: tuple

@dataclass(frozen=True)
class MaterialDraft:
    source_sha256: str
    parser_version: str
    introduction: tuple = field(repr=False)
    assignments: tuple
    review_reasons: tuple
    draft_version: str = 'numbered-draft-1'
    requires_review: bool = True


def draft_assignments(document, *, kind, expected_numbers):
    """Trusted configuration supplies type and expected complete numbering.

    Paragraph indices are zero-based in ExtractedDocument.paragraphs. Heading
    text may itself contain requirements and must be reviewed with section text.
    All introduction remains explicit, never merged into academic rules.
    """
    if (type(document) is not ExtractedDocument or kind not in ('practice','lecture_makeup')
            or type(expected_numbers) is not tuple or not expected_numbers
            or any(type(n) is not int or n<1 for n in expected_numbers)
            or tuple(sorted(set(expected_numbers))) != expected_numbers):
        raise DraftError('Explicit complete assignment numbering required')
    if document.tables:
        raise DraftError('Table criteria require explicit layout review')
    headings=[]
    for index, paragraph in enumerate(document.paragraphs):
        match=HEADING.match(paragraph)
        if match:headings.append((index,int(match.group(1))))
    if tuple(number for _,number in headings)!=expected_numbers:
        raise DraftError('Assignment layout incomplete or ambiguous; review required')
    assignments=[]
    for position,(start,number) in enumerate(headings):
        stop=headings[position+1][0] if position+1<len(headings) else len(document.paragraphs)
        indices=tuple(i for i in range(start+1,stop) if document.paragraphs[i].strip())
        if not indices:
            raise DraftError('Empty assignment section; review required')
        assignments.append(AssignmentDraft(kind,number,document.paragraphs[start],
                                          tuple(document.paragraphs[i] for i in indices),indices))
    return MaterialDraft(document.source_sha256,document.parser_version,
                         document.paragraphs[:headings[0][0]],tuple(assignments),document.review_reasons)
