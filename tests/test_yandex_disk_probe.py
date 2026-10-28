"""Synthetic HTTPS mocks; never read the real GitHub secret."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from yandex_disk_probe import probe, main, ProbeError, NoRedirect, ENDPOINT


class Response:
    def __init__(self, body=b'{"type":"dir"}', status=200):
        self.body, self.status = body, status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        return self.body[:size]


class ProbeTests(unittest.TestCase):
    def test_only_fixed_metadata_get_and_minimal_result(self):
        requests = []
        def fetch(request, timeout):
            requests.append(request)
            self.assertEqual(timeout, 20)
            return Response()
        result = probe('synthetic-key', opener=fetch)
        self.assertEqual(result, {'status': 'read_verified', 'writes_performed': False})
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].full_url, ENDPOINT)
        self.assertEqual(requests[0].get_method(), 'GET')
        self.assertEqual(requests[0].get_header('Authorization'), 'OAuth synthetic-key')
        self.assertNotIn('synthetic-key', json.dumps(result))

    def test_missing_invalid_token_never_calls_network(self):
        for token in ['', None, 'contains space', 'abc\r\nInjected: header']:
            with self.assertRaises(ProbeError):
                probe(token, opener=lambda *a, **kw: self.fail('must not call network'))

    def test_redirect_never_forwards_authorization(self):
        with self.assertRaises(ProbeError):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.invalid/')

    def test_401_403_safe_reason_no_response_body_or_token(self):
        for status, reason in [(401, 'token_rejected'), (403, 'read_permission_denied')]:
            def fetch(*args, **kwargs):
                raise HTTPError(ENDPOINT, status, 'synthetic-secret', {}, io.BytesIO(b'private data'))
            with self.assertRaises(ProbeError) as error:
                probe('synthetic-key', opener=fetch)
            self.assertEqual(str(error.exception), reason)

    def test_unknown_http_and_network_errors_are_sanitized(self):
        for exception in [HTTPError(ENDPOINT, 500, 'synthetic-key', {}, None), URLError('synthetic-key'), TimeoutError('synthetic-key')]:
            def fetch(*args, **kwargs):
                raise exception
            with self.assertRaises(ProbeError) as error:
                probe('synthetic-key', opener=fetch)
            self.assertNotIn('synthetic-key', str(error.exception))

    def test_invalid_or_large_response_fails_closed(self):
        for body in [b'not json', b'[]', b'{"type":"file"}', b'x'*20000]:
            with self.assertRaises(ProbeError):
                probe('synthetic-key', opener=lambda *a, **kw: Response(body))

    def test_main_missing_secret_is_actionable_without_traceback(self):
        output = io.StringIO()
        with patch.dict('os.environ', {}, clear=True), contextlib.redirect_stdout(output):
            self.assertEqual(main(), 1)
        self.assertEqual(json.loads(output.getvalue())['status'], 'secret_unavailable')

    def test_main_emits_only_sanitized_result(self):
        output = io.StringIO()
        with patch.dict('os.environ', {'YANDEX_DISK_TOKEN': 'synthetic-key'}), \
                patch('yandex_disk_probe.probe', return_value={'status': 'read_verified', 'writes_performed': False}), \
                contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        self.assertNotIn('synthetic-key', output.getvalue())


if __name__ == '__main__':
    unittest.main()
