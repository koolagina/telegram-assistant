"""Synthetic metadata only; no access tokens or student files."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from yandex_resource_inventory import inventory, main
from yandex_disk_probe import ProbeError

TARGET = 'synthetic.xlsx'
PUBLIC = 'https://disk.yandex.ru/d/synthetic-id'


class Client:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, endpoint, parameters):
        self.calls.append((endpoint, parameters))
        if endpoint == '/resources/files':
            return {'items': self.pages[parameters['offset']//2]}
        if endpoint == '/resources':
            return {'type': 'file', 'size': 123}
        return {'type': 'dir'}


class InventoryTests(unittest.TestCase):
    def test_pagination_exact_target_and_folder_metadata_only(self):
        client = Client([[{'name': 'unrelated.xlsx', 'path': 'disk:/private/unrelated.xlsx', 'type': 'file'},
                          {'name': 'Synthetic.xlsx', 'path': 'disk:/private/synthetic.xlsx', 'type': 'file'}], []])
        result = inventory(client, TARGET, PUBLIC, page_size=2)
        self.assertEqual(result['journal_status'], 'unique_file_readable')
        self.assertEqual(result['materials_status'], 'folder_readable')
        self.assertEqual(len(client.calls), 4)
        self.assertNotIn('private', json.dumps(result))
        self.assertNotIn('unrelated', json.dumps(result))

    def test_ambiguous_copies_never_pick_first(self):
        client = Client([[{'name': TARGET, 'path': 'disk:/a/synthetic.xlsx', 'type': 'file'},
                          {'name': TARGET, 'path': 'disk:/b/synthetic.xlsx', 'type': 'file'}], []])
        result = inventory(client, TARGET, PUBLIC, page_size=2)
        self.assertEqual(result['journal_status'], 'ambiguous')
        self.assertFalse(any(endpoint == '/resources' for endpoint, _ in client.calls))

    def test_scan_limit_does_not_claim_absence_or_unique_match(self):
        client = Client([[{'name': TARGET, 'path': 'disk:/synthetic.xlsx', 'type': 'file'}]])
        result = inventory(client, TARGET, PUBLIC, page_size=1, max_pages=1)
        self.assertEqual(result['journal_status'], 'scan_incomplete')
        self.assertFalse(any(endpoint == '/resources' for endpoint, _ in client.calls))

    def test_missing_and_whitespace_case_normalization(self):
        client = Client([[]])
        self.assertEqual(inventory(client, TARGET, PUBLIC, page_size=2)['journal_status'], 'not_found_in_scan')
        client = Client([[{'name': ' SYNTHETIC .XLSX ', 'path': 'disk:/synthetic.xlsx', 'type': 'file'}]])
        self.assertEqual(inventory(client, TARGET, PUBLIC, page_size=2)['journal_status'], 'unique_file_readable')

    def test_invalid_public_url_cannot_redirect_secret(self):
        for value in ['http://disk.yandex.ru/d/id', 'https://evil.invalid/d/id', 'https://disk.yandex.ru/d/id?secret=bad']:
            client = Client([[]])
            with self.assertRaises(ProbeError):
                inventory(client, TARGET, value)
            self.assertEqual(client.calls, [])

    def test_duplicate_pages_and_invalid_records_fail_closed(self):
        repeated = {'name': TARGET, 'path': 'disk:/synthetic.xlsx', 'type': 'file'}
        with self.assertRaises(ProbeError):
            inventory(Client([[repeated], [repeated]]), TARGET, PUBLIC, page_size=1)
        with self.assertRaises(ProbeError):
            inventory(Client([[{'name': TARGET, 'path': 'https://evil.invalid', 'type': 'file'}]]), TARGET, PUBLIC)

    def test_main_prints_only_structural_result(self):
        output = io.StringIO()
        with patch.dict('os.environ', {'YANDEX_DISK_TOKEN': 'synthetic-key'}), \
                patch('yandex_resource_inventory.inventory', return_value={'journal_status': 'unique_file_readable', 'materials_status': 'folder_readable', 'writes_performed': False}), \
                contextlib.redirect_stdout(output):
            self.assertEqual(main({'journal_filename': TARGET, 'materials_url': PUBLIC}), 0)
        self.assertNotIn('synthetic-key', output.getvalue())
        self.assertNotIn(PUBLIC, output.getvalue())

    def test_main_sanitizes_errors(self):
        output = io.StringIO()
        with patch('yandex_resource_inventory.DiskClient', side_effect=RuntimeError('private-data')), contextlib.redirect_stdout(output):
            self.assertEqual(main({'journal_filename': TARGET, 'materials_url': PUBLIC}), 1)
        self.assertNotIn('private-data', output.getvalue())


if __name__ == '__main__':
    unittest.main()
