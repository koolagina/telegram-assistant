"""Compose current source, DOCX extraction and explicitly trusted validation.

Validator is executable application configuration, never loaded from a document.
It must review the whole source, resolve extraction warnings and check semantic
coverage/conflicts. This module verifies binding, not the correctness of that
judgment. No default validator, scheduler, grader, email or journal writes.
"""
from dataclasses import dataclass, field
import json
from assistant_access import identifier
from material_docx import extract_docx
from material_versions import MaterialRead, MaterialError, digest, encoded


@dataclass(frozen=True)
class ValidatedRubrics:
    source_sha256: str
    parser_version: str
    validator_version: str
    resolved_reasons: tuple
    rubrics: dict = field(repr=False)


class MaterialProvider:
    """Callable fetch_current for MaterialCatalog.prepare/finish.

    source.read() must return freshly verified bytes. validator(extracted) is a
    trusted service/callback, not a permissive language-model instruction prompt.
    Each call fetches and validates anew; there is no stale fallback or caching.
    """
    def __init__(self, source, *, validator):
        if not callable(getattr(source, 'read', None)) or not callable(validator):
            raise MaterialError('Explicit source and trusted validator required')
        self._source, self._validator = source, validator

    def __call__(self):
        try:
            content = self._source.read()
            document = extract_docx(content)
            result = self._validator(document)
            if (type(result) is not ValidatedRubrics
                    or result.source_sha256 != document.source_sha256
                    or result.parser_version != document.parser_version
                    or not identifier(result.validator_version)
                    or type(result.resolved_reasons) is not tuple
                    or result.resolved_reasons != document.review_reasons
                    or type(result.rubrics) is not dict or not result.rubrics):
                raise MaterialError('Current criteria require validated source-bound review')
            # Freeze callback-owned criteria and reject non-JSON/NaN data.
            rubrics = json.loads(encoded(result.rubrics))
            for key, rules in rubrics.items():
                if (not identifier(key) or type(rules) is not dict
                        or rules.get('kind') not in ('practice', 'lecture_makeup')
                        or type(rules.get('number')) is not int or rules['number'] < 1
                        or type(rules.get('requirements')) is not list or not rules['requirements']
                        or any(not isinstance(item,str) or not item.strip() for item in rules['requirements'])):
                    raise MaterialError('Current criteria require review')
            # Existing catalog schema retained: version includes both components.
            version = 'pipeline-' + digest([document.parser_version, result.validator_version])
            return MaterialRead(content, rubrics, version)
        except Exception:
            # Providers/validators may include private URLs/text in exceptions.
            raise MaterialError('Current material pipeline failed; review or refresh required') from None
