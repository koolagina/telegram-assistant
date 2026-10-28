"""Bounded metadata discovery of explicitly approved resources. No downloads.

File names/paths exist only in process memory. Public stdout contains statuses
and counts, never file names, paths, URLs, tokens or API response bodies.
"""
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener
from yandex_disk_probe import ProbeError, NoRedirect, validate_token

ALLOWED = frozenset({'/resources/files', '/resources', '/public/resources'})


class DiskClient:
    def __init__(self, token):
        self.token = validate_token(token)
        self.opener = build_opener(NoRedirect())

    def get(self, endpoint, parameters):
        if endpoint not in ALLOWED:
            raise ProbeError('endpoint_not_allowed')
        url = 'https://cloud-api.yandex.net/v1/disk' + endpoint + '?' + urlencode(parameters)
        request = Request(url, headers={'Authorization': 'OAuth '+self.token, 'Accept': 'application/json'}, method='GET')
        try:
            with self.opener.open(request, timeout=10) as response:
                if response.status != 200:
                    raise ProbeError('unexpected_http_status')
                body = response.read(2*1024*1024+1)
            if len(body) > 2*1024*1024:
                raise ProbeError('response_too_large')
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ProbeError('invalid_api_response')
            return result
        except ProbeError:
            raise
        except HTTPError as error:
            raise ProbeError({401: 'token_rejected', 403: 'read_permission_denied',
                              404: 'resource_unavailable', 429: 'rate_limited'}.get(error.code, 'http_request_failed')) from None
        except (URLError, OSError):
            raise ProbeError('network_request_failed') from None
        except (ValueError, TypeError):
            raise ProbeError('invalid_api_response') from None


def normalized(value):
    return ''.join(unicodedata.normalize('NFC', value).casefold().split())


def inventory(client, journal_filename, materials_url, *, page_size=1000, max_pages=5):
    parsed = urlsplit(materials_url)
    if (parsed.scheme != 'https' or parsed.netloc != 'disk.yandex.ru'
            or not re.fullmatch(r'/d/[A-Za-z0-9_-]+', parsed.path)
            or parsed.query or parsed.fragment):
        raise ProbeError('invalid_materials_reference')
    if not isinstance(journal_filename, str) or not journal_filename.lower().endswith('.xlsx') or '/' in journal_filename or '\\' in journal_filename:
        raise ProbeError('invalid_journal_filename')
    matches, seen, complete = [], set(), False
    for page in range(max_pages):
        # media_type=spreadsheet is documented in the official all-files API.
        result = client.get('/resources/files', dict(media_type='spreadsheet', limit=page_size,
                            offset=page*page_size, fields='items.name,items.path,items.type'))
        items = result.get('items')
        if not isinstance(items, list) or len(items) > page_size:
            raise ProbeError('invalid_inventory_page')
        for item in items:
            if (not isinstance(item, dict) or item.get('type') != 'file'
                    or not isinstance(item.get('name'), str) or not isinstance(item.get('path'), str)
                    or not item['path'].startswith('disk:/') or item['path'] in seen):
                raise ProbeError('invalid_or_repeated_inventory_record')
            seen.add(item['path'])
            if normalized(item['name']) == normalized(journal_filename):
                matches.append(item['path'])
        if len(items) < page_size:
            complete = True
            break
    if not complete:
        status = 'scan_incomplete'
    elif len(matches) > 1:
        status = 'ambiguous'
    elif not matches:
        status = 'not_found_in_scan'
    else:
        metadata = client.get('/resources', dict(path=matches[0], fields='type,size'))
        if metadata.get('type') != 'file' or type(metadata.get('size')) is not int or metadata['size'] < 1:
            raise ProbeError('journal_metadata_not_verified')
        status = 'unique_file_readable'
    folder = client.get('/public/resources', dict(public_key=materials_url, fields='type'))
    return dict(journal_status=status, matching_files=len(matches), scan_complete=complete,
                materials_status='folder_readable' if folder.get('type') == 'dir' else 'not_a_folder',
                writes_performed=False, files_downloaded=False)


def main(inputs=None):
    try:
        if inputs is None:
            inputs = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())['inputs']
        client = DiskClient(os.environ.get('YANDEX_DISK_TOKEN'))
        result = inventory(client, inputs['journal_filename'], inputs['materials_url'])
    except ProbeError as error:
        result = {'status': str(error), 'writes_performed': False, 'files_downloaded': False}
    except Exception:
        result = {'status': 'inventory_failed', 'writes_performed': False, 'files_downloaded': False}
    print(json.dumps(result))
    return 0 if result.get('journal_status') == 'unique_file_readable' and result.get('materials_status') == 'folder_readable' else 1


if __name__ == '__main__':
    raise SystemExit(main())
