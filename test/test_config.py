import json
import os
import unittest

import config


class TestConfig(unittest.TestCase):
    def test_get_config_file_dict_badjson(self):
        config.get_config_file_dict('test/data/config_bad.json')
        self.assertRaises(json.JSONDecodeError)

    def test_get_config_file_dict_empty(self):
        config_dict = config.get_config_file_dict('test/data/config_empty.json')  # noqa: E501
        self.assertEqual(0, len(config_dict))

    def test_get_config_file_dict_json(self):
        config_dict = config.get_config_file_dict('test/data/config.json')
        self.assertEqual(config_dict.get('TARGETVERSION'), '10')

    def test_get_config_file_dict_none(self):
        config.get_config_file_dict('test/data/not_there.json')
        self.assertRaises(FileNotFoundError)

    def test_get_config_file_dict_conf(self):
        config_dict = config.get_config_file_dict('test/data/config.conf')
        self.assertEqual(config_dict.get('TARGETVERSION'), '10')

    def test_get_env_config(self):
        config.FLPRODUCT = None
        os.environ['FLPRODUCT'] = 'Logos'
        config.get_env_config()
        self.assertEqual(os.getenv('FLPRODUCT'), config.FLPRODUCT)

    def test_set_config_env_bad(self):
        self.assertIsNone(config.set_config_env('test/data/config_empty.json'))

    def test_set_env_config_value(self):
        config.TARGETVERSION = None
        config.set_config_env('test/data/config.json')
        self.assertEqual(config.TARGETVERSION, '10')
