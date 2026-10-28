"""Validate citations for supplied observations; not a semantic evaluator.

Findings come from a future trusted reviewer. Exact quotes prove provenance,
not scientific correctness, originality, coverage or an entitlement to credit.
No LLM/external service, transport, authorization or automatic approval here.
"""
from dataclasses import dataclass, field, asdict
from assistant_access import identifier
from assignment_review import review_presentation, ReviewError
from material_versions import digest

@dataclass(frozen=True)
class Citation:
    part: str
    start: int
    end: int
    quote: str = field(repr=False)

@dataclass(frozen=True)
class Finding:
    check_id: str
    material_version: str
    submission_sha256: str
    requirement_index: int
    stance: str
    comment: str = field(repr=False)
    citations: tuple = field(repr=False)


def review_with_findings(plan, work, findings, *, reviewer_version):
    """Compose a new report; never promote supplied claims to final statuses.

    Offsets use Python Unicode character indexes in reader-extracted slide text,
    not byte offsets or screen coordinates. Quotes must match exactly. Caller
    must not expose these private excerpts without the project's academic policy.
    """
    if (not identifier(reviewer_version) or type(findings) not in (list,tuple)
            or len(findings)>1000):
        raise ReviewError('Explicit bounded reviewer observations required')
    report=review_presentation(plan,work)
    parts={slide.part:slide.text for slide in work.slides}
    seen=set();validated=[]
    for finding in findings:
        if (type(finding) is not Finding or finding.check_id!=plan.id
                or finding.material_version!=plan.version or finding.submission_sha256!=work.sha256
                or type(finding.requirement_index) is not int
                or not 0<=finding.requirement_index<len(report['requirements'])
                or finding.requirement_index in seen
                or finding.stance not in ('supported','contradicted','uncertain')
                or not isinstance(finding.comment,str) or not finding.comment.strip() or len(finding.comment)>10000
                or type(finding.citations) is not tuple or len(finding.citations)>100
                or (finding.stance!='uncertain' and not finding.citations)):
            raise ReviewError('Ambiguous or unbound content observation')
        seen.add(finding.requirement_index)
        for citation in finding.citations:
            if (type(citation) is not Citation or not isinstance(citation.part,str)
                    or citation.part not in parts or type(citation.start) is not int or type(citation.end) is not int
                    or not 0<=citation.start<citation.end<=len(parts[citation.part])
                    or not isinstance(citation.quote,str) or not citation.quote.strip()
                    or parts[citation.part][citation.start:citation.end]!=citation.quote):
                raise ReviewError('Citation does not match current work')
        observation={'stance':finding.stance,'comment':finding.comment,
                     'citations':[asdict(citation) for citation in finding.citations],
                     'status':'needs_review'}
        report['requirements'][finding.requirement_index]['content_observation']=observation
        validated.append(asdict(finding))
    # Canonical order so retrying the same observations remains idempotent.
    validated.sort(key=lambda item:item['requirement_index'])
    report['structural_evaluation_key']=report['evaluation_key']
    report['content_reviewer_version']=reviewer_version
    report['content_evidence_version']='quote-binding-1'
    report['evaluation_key']=digest([report['structural_evaluation_key'],'quote-binding-1',reviewer_version,validated])
    return report
