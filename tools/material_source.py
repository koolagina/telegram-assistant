"""Read-only public DOCX refresh. No token, cache, scheduler or grade writer."""
import hashlib
import json
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener
from yandex_disk_probe import NoRedirect

MAX_DOCUMENT = 16 * 1024 * 1024
API = 'https://cloud-api.yandex.net/v1/disk/public/resources'

class SourceError(ValueError):
    pass

class ReadTransport:
    """GET only, TLS/proxy defaults retained, redirects refused, bounded reads."""
    def __init__(self): self._open = build_opener(NoRedirect()).open
    def binary(self, url, limit):
        with self._open(Request(url,method='GET'),timeout=20) as response:
            if response.status != 200: raise SourceError('Source HTTP failure')
            result=response.read(limit+1)
        if len(result)>limit: raise SourceError('Source size limit exceeded')
        return result
    def json(self,url):
        return json.loads(self.binary(url,65536))

class PublicMaterialSource:
    def __init__(self, public_key, path, *, transport=None):
        if (not isinstance(public_key,str) or not re.fullmatch(r'https://disk\.yandex\.ru/d/[A-Za-z0-9_-]+',public_key)
                or not isinstance(path,str) or not path.startswith('/') or not path.lower().endswith('.docx')
                or any(part in ('','..','.') for part in path[1:].split('/'))
                or any(c in path for c in ('\\','?','#')) or any(ord(c)<32 for c in path)):
            raise SourceError('Explicit public DOCX reference required')
        self._key,self._path=public_key,path
        self._transport=transport if transport is not None else ReadTransport()

    def _url(self,download=False):
        params={'public_key':self._key,'path':self._path}
        if not download: params['fields']='type,size,sha256,modified'
        return API+('/download' if download else '')+'?'+urlencode(params)

    def _metadata(self):
        data=self._transport.json(self._url())
        if (not isinstance(data,dict) or data.get('type')!='file'
                or type(data.get('size')) is not int or not 0<data['size']<=MAX_DOCUMENT
                or not isinstance(data.get('sha256'),str) or not re.fullmatch('[a-fA-F0-9]{64}',data['sha256'])
                or not isinstance(data.get('modified'),str) or not data['modified']):
            raise SourceError('Current source metadata unavailable')
        return data['size'],data['sha256'].lower(),data['modified']

    def read(self):
        try:
            before=self._metadata()
            descriptor=self._transport.json(self._url(download=True))
            if not isinstance(descriptor,dict) or descriptor.get('method')!='GET':
                raise SourceError('Invalid download descriptor')
            href=descriptor.get('href')
            if not isinstance(href,str) or any(ord(c)<33 for c in href):
                raise SourceError('Invalid download reference')
            parsed=urlsplit(href)
            host=parsed.hostname or ''
            if (parsed.scheme!='https' or parsed.username is not None or parsed.password is not None
                    or parsed.port not in (None,443) or parsed.fragment
                    or not any(host==base or host.endswith('.'+base) for base in ('yandex.ru','yandex.net'))):
                raise SourceError('Download destination refused')
            content=self._transport.binary(href,MAX_DOCUMENT)
            if (type(content) is not bytes or len(content)!=before[0]
                    or hashlib.sha256(content).hexdigest()!=before[1]):
                raise SourceError('Downloaded source integrity mismatch')
            if self._metadata()!=before:
                raise SourceError('Source changed during download; refresh required')
            return content
        except SourceError: raise
        except Exception:
            raise SourceError('Current source read failed; no cached fallback') from None
