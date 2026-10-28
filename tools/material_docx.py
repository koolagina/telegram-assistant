"""Bounded local Word text extraction. Never executes links or approves criteria."""
from dataclasses import dataclass, field
import hashlib
import io
import zipfile
import xml.etree.ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MAX_INPUT = 16 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024

class DocxError(ValueError):
    pass

@dataclass(frozen=True)
class ExtractedDocument:
    source_sha256: str
    paragraphs: tuple = field(repr=False)
    tables: tuple = field(repr=False)
    review_reasons: tuple
    parser_version: str = 'docx-text-1'

    @property
    def requires_review(self):
        return bool(self.review_reasons)


def _paragraph(element):
    parts = []
    for item in element.iter():
        if item.tag == W + 't': parts.append(item.text or '')
        elif item.tag == W + 'tab': parts.append('\t')
        elif item.tag in (W + 'br', W + 'cr'): parts.append('\n')
    return ''.join(parts)


def extract_docx(content):
    """Return untrusted text and table cells, not MaterialRead/validated rubrics.

    All output needs semantic review. Unknown parts/features are reported, never
    interpreted as empty/complete criteria. No extraction to disk or network.
    """
    if type(content) is not bytes or not 0 < len(content) <= MAX_INPUT:
        raise DocxError('Invalid document size/type')
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if (len(entries) > 1024 or len(names) != len(set(names))
                    or sum(entry.file_size for entry in entries) > MAX_EXPANDED
                    or any(entry.flag_bits & 1 for entry in entries)
                    or any('vba' in name.lower() for name in names)):
                raise DocxError('Unsupported document archive')
            raw = archive.read('word/document.xml')
            # Reject DTD/entities including UTF-16/32 encodings before XML parsing.
            scan = raw.replace(b'\x00', b'').upper()
            if b'<!DOCTYPE' in scan or b'<!ENTITY' in scan:
                raise DocxError('XML declarations forbidden')
            root = ET.fromstring(raw)
            if root.tag != W + 'document':
                raise DocxError('Invalid Word document')
            body = root.find(W + 'body')
            if body is None:
                raise DocxError('Missing document body')
            reasons = {'criteria-not-validated'}
            allowed = {W + name for name in ('document','body','p','pPr','r','rPr','t','tab','br','cr','tbl','tblPr','tblGrid','gridCol','tr','trPr','tc','tcPr','sectPr')}
            if any(item.tag not in allowed for item in root.iter()):
                reasons.add('unsupported-content')
            if any(name.endswith('.rels') for name in names):
                reasons.add('relationships')
            if any(name.startswith(('word/media/', 'word/embeddings/')) or name.startswith(('word/header','word/footer','word/footnotes','word/endnotes','word/comments')) for name in names):
                reasons.add('additional-content')
            paragraphs = tuple(_paragraph(item) for item in body if item.tag == W + 'p')
            tables = tuple(tuple(tuple('\n'.join(_paragraph(p) for p in cell.findall(W + 'p')) for cell in row.findall(W + 'tc')) for row in table.findall(W + 'tr')) for table in body if table.tag == W + 'tbl')
            return ExtractedDocument(hashlib.sha256(content).hexdigest(), paragraphs, tables, tuple(sorted(reasons)))
    except DocxError:
        raise
    except (zipfile.BadZipFile, KeyError, ET.ParseError, RuntimeError, NotImplementedError, OSError, ValueError):
        raise DocxError('Document cannot be safely extracted') from None
