"""Executable synthetic demo stays offline."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from review_demo import run_demo

class DemoTests(unittest.TestCase):
    def test_complete_offline_demo(self):
        with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('Network forbidden')):
            report=run_demo()
        self.assertIn('не выполнено (39/40)',report)
        self.assertIn('выполнено (40/40)',report)
        self.assertEqual(report.count('| решение преподавателя |'),2)
    def test_report_is_explicitly_synthetic_and_not_credit(self):
        report=run_demo()
        self.assertIn('только искусственные данные',report)
        self.assertIn('не означает принятую отработку',report)
