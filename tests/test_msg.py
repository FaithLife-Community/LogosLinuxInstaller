import unittest
from unittest.mock import patch

import config
import logging
import msg


class TestMsg(unittest.TestCase):
    def test_get_log_level_name(self):
        name = msg.get_log_level_name(logging.DEBUG)
        self.assertEqual(name, 'DEBUG')

    def test_update_log_level(self):
        new_level = logging.DEBUG
        level = None
        msg.update_log_level(new_level)
        for h in logging.getLogger().handlers:
            if isinstance(h, logging.StreamHandler):
                level = h.level
        self.assertEqual(level, new_level)

    @patch('msg.input', create=True)
    def test_cli_acknowledge_question_empty(self, mocked_input):
        mocked_input.side_effect = ['']
        result = msg.cli_acknowledge_question('test', 'no')
        self.assertTrue(result)

    @patch('msg.input', create=True)
    def test_cli_acknowledge_question_no(self, mocked_input):
        mocked_input.side_effect = ['N']
        result = msg.cli_acknowledge_question('test', 'no')
        self.assertFalse(result)

    @patch('msg.input', create=True)
    def test_cli_acknowledge_question_yes(self, mocked_input):
        mocked_input.side_effect = ['Y']
        result = msg.cli_acknowledge_question('test', 'no')
        self.assertTrue(result)

    @patch('msg.input', create=True)
    def test_cli_ask_filepath(self, mocked_input):
        path = "/home/user/Directory"
        mocked_input.side_effect = [f"\"{path}\""]
        result = msg.cli_ask_filepath('test')
        self.assertEqual(path, result)

    @patch('msg.input', create=True)
    def test_cli_continue_question_yes(self, mocked_input):
        mocked_input.side_effect = ['Y']
        result = msg.cli_continue_question('test', 'no', None)
        self.assertIsNone(result)

    @patch('msg.input', create=True)
    def test_cli_question_empty(self, mocked_input):
        mocked_input.side_effect = ['']
        self.assertTrue(msg.cli_question('test'))

    @patch('msg.input', create=True)
    def test_cli_question_no(self, mocked_input):
        mocked_input.side_effect = ['N']
        self.assertFalse(msg.cli_question('test'))

    @patch('msg.input', create=True)
    def test_cli_question_yes(self, mocked_input):
        mocked_input.side_effect = ['Y']
        self.assertTrue(msg.cli_question('test'))

    @patch('msg.input', create=True)
    def test_logos_acknowledge_question_empty(self, mocked_input):
        config.DIALOG = 'curses'
        mocked_input.side_effect = ['']
        result = msg.logos_acknowledge_question('test', 'no')
        self.assertTrue(result)

    @patch('msg.input', create=True)
    def test_logos_acknowledge_question_no(self, mocked_input):
        config.DIALOG = 'curses'
        mocked_input.side_effect = ['N']
        result = msg.logos_acknowledge_question('test', 'no')
        self.assertFalse(result)

    @patch('msg.input', create=True)
    def test_logos_acknowledge_question_yes(self, mocked_input):
        config.DIALOG = 'curses'
        mocked_input.side_effect = ['Y']
        result = msg.logos_acknowledge_question('test', 'no')
        self.assertTrue(result)
