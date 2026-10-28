"""One read-only metadata request. Never list files or print API bodies/secrets.

Intended for a manually dispatched GitHub Actions job, not scheduled processing.
This verifies this particular read operation, not the token's complete scopes.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

ENDPOINT = 'https://cloud-api.yandex.net/v1/disk/resources?path=disk%3A%2F&fields=type'
MAX_RESPONSE = 16384


class ProbeError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError('redirect_refused')


def validate_token(token):
    if not isinstance(token, str) or not token.strip():
        raise ProbeError('secret_unavailable')
    token = token.strip()
    if not token.isascii() or any(c.isspace() or ord(c) < 33 for c in token) or len(token) > 4096:
        raise ProbeError('secret_format_invalid')
    return token


def probe(token, *, opener=None):
    token = validate_token(token)
    request = Request(ENDPOINT, headers={'Authorization': 'OAuth ' + token, 'Accept': 'application/json'}, method='GET')
    open_url = opener or build_opener(NoRedirect()).open
    try:
        with open_url(request, timeout=20) as response:
            if response.status != 200:
                raise ProbeError('unexpected_http_status')
            body = response.read(MAX_RESPONSE+1)
        if len(body) > MAX_RESPONSE:
            raise ProbeError('invalid_api_response')
        data = json.loads(body)
        if not isinstance(data, dict) or data.get('type') != 'dir':
            raise ProbeError('invalid_api_response')
        return {'status': 'read_verified', 'writes_performed': False}
    except ProbeError:
        raise
    except HTTPError as error:
        reason = {401: 'token_rejected', 403: 'read_permission_denied', 429: 'rate_limited'}.get(error.code, 'http_request_failed')
        raise ProbeError(reason) from None
    except (URLError, TimeoutError, OSError):
        raise ProbeError('network_request_failed') from None
    except (ValueError, TypeError):
        raise ProbeError('invalid_api_response') from None


def main():
    try:
        result = probe(os.environ.get('YANDEX_DISK_TOKEN'))
    except ProbeError as error:
        result = {'status': str(error), 'writes_performed': False}
    except Exception:
        result = {'status': 'probe_failed', 'writes_performed': False}
    print(json.dumps(result))
    return 0 if result['status'] == 'read_verified' else 1


if __name__ == '__main__':
    raise SystemExit(main())
