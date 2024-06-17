import unittest
from pathlib import Path

import installer


class TestInstaller(unittest.TestCase):
    def setUp(self):
        self.grepfile = Path(__file__).parent / 'data' / 'config.json'

    def test_get_progress_pct_divbyzero(self):
        pct = installer.get_progress_pct(3, 0)
        self.assertEqual(0, pct)

    def test_get_progress_pct_normal(self):
        pct = installer.get_progress_pct(5, 10)
        self.assertEqual(50, pct)

    def test_get_progress_pct_over100(self):
        pct = installer.get_progress_pct(15, 10)
        self.assertEqual(100, pct)

    def test_grep_found(self):
        self.assertTrue(installer.grep(r'LOGOS_DIR', self.grepfile))

    def test_grep_nofile(self):
        self.assertIsNone(installer.grep(r'test', 'thisfiledoesnotexist'))

    def test_grep_notfound(self):
        self.assertFalse(installer.grep(r'TEST_NOT_IN_FILE', self.grepfile))
