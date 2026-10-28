"""Offline source refresh protocol."""
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from material_source import PublicMaterialSource, SourceError

class Transport:
    def __init__(self): self.data=b'docx bytes'; self.calls=[]; self.changed=False; self.fail=False
    def json(self,url):
        self.calls.append(url)
        if self.fail: raise OSError('sensitive URL')
        if '/download?' in url: return {'href':'https://downloader.disk.yandex.ru/file?signature=private','method':'GET'}
        return {'type':'file','size':len(self.data),'sha256':hashlib.sha256(self.data).hexdigest(), 'modified':'new' if self.changed and len(self.calls)>1 else 'old'}
    def binary(self,url,limit): return self.data

class SourceTests(unittest.TestCase):
    def source(self,t): return PublicMaterialSource('https://disk.yandex.ru/d/synthetic','/assignment.docx',transport=t)
    def test_fresh_each_call_no_cache(self):
        t=Transport(); s=self.source(t)
        self.assertEqual(s.read(),b'docx bytes'); t.data=b'updated'; self.assertEqual(s.read(),b'updated')
        self.assertEqual(len(t.calls),6)
    def test_change_during_download_blocks(self):
        t=Transport(); t.changed=True
        with self.assertRaises(SourceError): self.source(t).read()
    def test_hash_mismatch_blocks(self):
        t=Transport(); t.binary=lambda *a:b'corrupted'
        with self.assertRaises(SourceError): self.source(t).read()
    def test_download_host_and_scheme_restricted(self):
        for url in ['http://downloader.disk.yandex.ru/a','https://evil.test/a','https://yandex.ru.evil.test/a','https://user:pass@yandex.ru/a']:
            t=Transport(); old=t.json
            t.json=lambda u: {'href':url,'method':'GET'} if '/download?' in u else old(u)
            with self.assertRaises(SourceError): self.source(t).read()
    def test_failure_does_not_fall_back_or_leak(self):
        t=Transport(); s=self.source(t); s.read(); t.fail=True
        with self.assertRaises(SourceError) as error:s.read()
        self.assertNotIn('sensitive',str(error.exception))
    def test_explicit_docx_reference_required(self):
        for path in ['/journal.xlsx','/../a.docx','relative.docx','/a.docx?secret']:
            with self.assertRaises(SourceError): PublicMaterialSource('https://disk.yandex.ru/d/synthetic',path,transport=Transport())

class TransportTests(unittest.TestCase):
    def test_get_only_bounded_read_and_timeout(self):
        from material_source import ReadTransport
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):self.limit=n;return b'abcd'
        response=Response(); seen=[]
        t=ReadTransport()
        def opened(request,timeout):seen.append((request.get_method(),timeout));return response
        t._open=opened
        with self.assertRaises(SourceError):t.binary('https://example.invalid',3)
        self.assertEqual(response.limit,4)
        self.assertEqual(seen,[('GET',20)])
    def test_redirect_handler_refuses_redirect(self):
        from yandex_disk_probe import NoRedirect, ProbeError
        with self.assertRaises(ProbeError):NoRedirect().redirect_request(None,None,302,'redirect',{},'https://evil.invalid')
