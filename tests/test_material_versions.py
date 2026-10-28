"""Synthetic version/rubric lifecycle. No real documents or grades."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from material_versions import MaterialCatalog, MaterialRead, MaterialError


def source(version=1):
    return MaterialRead(f'synthetic document {version}'.encode(),
                        {'practice-1': {'kind': 'practice', 'number': 1,
                                        'requirements': [f'{version+2} photos']}}, 'parser-1')


class VersionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'versions.sqlite3'

    def store(self):
        return MaterialCatalog(self.path, namespace='synthetic-project')

    def test_each_new_check_reads_source_and_uses_current_rules(self):
        with self.store() as catalog:
            old = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=lambda: source(1))
            new = catalog.prepare('submission-b', 'material-a', 'practice-1', fetch_current=lambda: source(2))
            self.assertNotEqual(old.version, new.version)
            self.assertEqual(old.rules['requirements'], ['3 photos'])
            self.assertEqual(new.rules['requirements'], ['4 photos'])

    def test_same_source_is_idempotent_and_persists_restart(self):
        with self.store() as catalog:
            first = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
        with self.store() as catalog:
            second = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            self.assertEqual(first, second)

    def test_completed_results_are_not_rewritten_when_source_changes(self):
        with self.store() as catalog:
            old = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            self.assertEqual(catalog.finish(old.id, {'outcome': 'synthetic-pass'}, fetch_current=source), 'done')
            catalog.prepare('submission-b', 'material-a', 'practice-1', fetch_current=lambda: source(2))
            self.assertEqual(catalog.result(old.id), {'status': 'done', 'result': {'outcome': 'synthetic-pass'}, 'version': old.version})

    def test_update_during_grading_requires_recheck_instead_of_accepting_old_result(self):
        with self.store() as catalog:
            old = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            self.assertEqual(catalog.finish(old.id, {'outcome': 'synthetic-pass'}, fetch_current=lambda: source(2)), 'needs_recheck')
            self.assertIsNone(catalog.result(old.id)['result'])
            new = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=lambda: source(2))
            self.assertNotEqual(old.id, new.id)

    def test_source_failure_never_silently_uses_old_cached_version(self):
        def unavailable():
            raise RuntimeError('private source URL')
        with self.store() as catalog:
            old = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            with self.assertRaises(MaterialError) as error:
                catalog.prepare('submission-b', 'material-a', 'practice-1', fetch_current=unavailable)
            self.assertNotIn('private', str(error.exception))
            with self.assertRaises(MaterialError):
                catalog.finish(old.id, {'outcome': 'synthetic-pass'}, fetch_current=unavailable)
            self.assertEqual(catalog.result(old.id)['status'], 'pending')

    def test_removed_or_invalid_assignment_does_not_reuse_old_rules(self):
        with self.store() as catalog:
            catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            changed = replace(source(2), rubrics={'practice-2': source().rubrics['practice-1']})
            with self.assertRaises(MaterialError):
                catalog.prepare('submission-b', 'material-a', 'practice-1', fetch_current=lambda: changed)
            with self.assertRaises(MaterialError):
                catalog.prepare('submission-c', 'material-a', 'practice-1', fetch_current=lambda: replace(source(3), rubrics={}))

    def test_parser_or_rules_change_even_with_same_file_creates_version(self):
        with self.store() as catalog:
            a = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            b = catalog.prepare('submission-b', 'material-a', 'practice-1', fetch_current=lambda: replace(source(), parser_version='parser-2'))
            c = catalog.prepare('submission-c', 'material-a', 'practice-1', fetch_current=lambda: replace(source(), rubrics=source(2).rubrics))
            self.assertEqual(len({a.version, b.version, c.version}), 3)

    def test_rules_copy_cannot_mutate_persisted_criteria(self):
        with self.store() as catalog:
            a = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            data = a.rules
            data['requirements'].append('injected')
            b = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            self.assertNotIn('injected', b.rules['requirements'])

    def test_reading_source_cannot_overwrite_a_newer_concurrent_head(self):
        with self.store() as first, self.store() as second:
            first.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            def race():
                second.prepare('submission-b', 'material-a', 'practice-1', fetch_current=lambda: source(2))
                return source(1)
            with self.assertRaises(MaterialError):
                first.prepare('submission-c', 'material-a', 'practice-1', fetch_current=race)

    def test_result_retry_is_idempotent_but_conflicting_result_is_rejected(self):
        with self.store() as catalog:
            job = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            for _ in range(2):
                self.assertEqual(catalog.finish(job.id, {'outcome': 'synthetic-pass'}, fetch_current=source), 'done')
            with self.assertRaises(MaterialError):
                catalog.finish(job.id, {'outcome': 'synthetic-fail'}, fetch_current=source)

    def test_namespace_and_permissions_protect_local_history(self):
        with self.store():
            pass
        with self.assertRaises(MaterialError):
            MaterialCatalog(self.path, namespace='another-project')
        self.assertEqual(self.path.stat().st_mode & 0o077, 0)

    def test_nonfinite_or_empty_source_and_wrong_kind_fail_closed(self):
        for invalid in [replace(source(), document=b''),
                        replace(source(), rubrics={'practice-1': {'kind': 'unknown', 'number': 1, 'requirements': ['x']}}),
                        replace(source(), rubrics={'practice-1': {'kind': 'practice', 'number': 1, 'requirements': ['x'], 'weight': float('nan')}})]:
            with self.store() as catalog:
                with self.assertRaises(MaterialError):
                    catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=lambda: invalid)

    def test_makeup_number_targets_only_corresponding_lecture_not_all_covered_topics(self):
        with self.store() as catalog:
            for number in range(1, 5):
                current = replace(source(), rubrics={'makeup': {'kind': 'lecture_makeup', 'number': number,
                                      'requirements': ['This synthetic task covers the whole course']}})
                job = catalog.prepare(f'submission-{number}', 'material-lecture', 'makeup', fetch_current=lambda: current)
                self.assertEqual(job.lecture_number, number)
            practice = catalog.prepare('practice-submission', 'material-practice', 'practice-1', fetch_current=source)
            self.assertIsNone(practice.lecture_number)

    def test_no_result_cannot_be_reported_as_completed_check(self):
        with self.store() as catalog:
            job = catalog.prepare('submission-a', 'material-a', 'practice-1', fetch_current=source)
            for invalid in [None, {}, [], 'passed']:
                with self.assertRaises(MaterialError):
                    catalog.finish(job.id, invalid, fetch_current=source)
            self.assertEqual(catalog.result(job.id)['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
