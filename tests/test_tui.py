import unittest

import tui


class TestTui(unittest.TestCase):
    def test_convert_yes_no_Y(self):
        self.assertIs(tui.convert_yes_no('Y'), True)

    def test_convert_yes_no_y(self):
        self.assertIs(tui.convert_yes_no('y'), True)

    def test_convert_yes_no_n(self):
        self.assertIs(tui.convert_yes_no('n'), False)

    def test_convert_yes_no_N(self):
        self.assertIs(tui.convert_yes_no('N'), False)

    def test_convert_yes_no_enter(self):
        self.assertIs(tui.convert_yes_no('\n'), True)

    def test_convert_yes_no_other(self):
        self.assertIs(tui.convert_yes_no('other'), None)
