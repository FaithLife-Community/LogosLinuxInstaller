import unittest
from pathlib import Path

import ou_dedetai.installer as installer


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
