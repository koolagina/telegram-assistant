"""Conservative source-grounded suggestions; never approved criteria.

Only a standalone explicit minimum-slide sentence is recognized. Unknown syntax,
conditional statements, examples and ambiguity require semantic review. This is
not a Russian-language semantic parser or an authorization/approval mechanism.
"""
from dataclasses import dataclass, field
import re
from material_drafts import MaterialDraft

MINIMUM=re.compile(r'^\s*(?:Объ[её]м\s*:\s*)?(?:не\s+менее|минимум)\s+([1-9][0-9]*)\s+слайд(?:ов|а)?[.!]?\s*$',re.IGNORECASE)

FINAL_MINIMUM=re.compile(r'(?:^|[.!?]\s+)Минимальный\s+объ[её]м\s*[—–:-]\s*([1-9][0-9]*)\s+слайд(?:ов|а)?[.!]?\s*$',re.IGNORECASE)
CONTEXT=re.compile(r'\b(?:если|например)\b|\bне\s+требуется\b',re.IGNORECASE)

class CriterionError(ValueError):
    pass

@dataclass(frozen=True)
class SlideCriterionSuggestion:
    source_sha256: str
    parser_version: str
    draft_version: str
    assignment_number: int
    requirement_index: int
    paragraph_index: int
    minimum: int
    quote: str = field(repr=False)
    suggestion_version: str = 'slide-suggestion-1'
    requires_review: bool = True


def suggest_slide_criterion(draft, *, assignment_number):
    if type(draft) is not MaterialDraft or type(assignment_number) is not int:
        raise CriterionError('Explicit source draft and assignment required')
    assignments=[item for item in draft.assignments if item.number==assignment_number]
    if len(assignments)!=1:
        raise CriterionError('Assignment not uniquely resolved')
    assignment=assignments[0]
    candidates=[]
    for index,text in enumerate(assignment.requirements):
        if CONTEXT.search(text):
            continue
        match=MINIMUM.fullmatch(text) or FINAL_MINIMUM.search(text)
        if match:
            candidates.append((index,int(match.group(1)),text))
    if len(candidates)!=1:
        raise CriterionError('No unambiguous explicit minimum; semantic review required')
    index,minimum,quote=candidates[0]
    return SlideCriterionSuggestion(draft.source_sha256,draft.parser_version,draft.draft_version,
                                    assignment_number,index,assignment.paragraph_indices[index],minimum,quote)
