import json
import os
import unittest
from pathlib import Path

import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.testdir = Path(__file__).parent
        self.datadir = self.testdir / 'data'

    def test_get_config_file_dict_badjson(self):
        config.get_config_file_dict(f"{self.datadir}/config_bad.json")
        self.assertRaises(json.JSONDecodeError)

    def test_get_config_file_dict_empty(self):
        config_dict = config.get_config_file_dict(f"{self.datadir}/config_empty.json")  # noqa: E501
        self.assertEqual(0, len(config_dict))

    def test_get_config_file_dict_json(self):
        config_dict = config.get_config_file_dict(f"{self.datadir}/config.json")  # noqa: E501
        self.assertEqual(config_dict.get('TARGETVERSION'), '10')

    def test_get_config_file_dict_none(self):
        config.get_config_file_dict(f"{self.datadir}/not_there.json")
        self.assertRaises(FileNotFoundError)

    def test_get_config_file_dict_conf(self):
        config_dict = config.get_config_file_dict(f"{self.datadir}/config.conf")  # noqa: E501
        self.assertEqual(config_dict.get('TARGETVERSION'), '10')

    def test_get_env_config(self):
        config.FLPRODUCT = None
        os.environ['FLPRODUCT'] = 'Logos'
        config.get_env_config()
        self.assertEqual(os.getenv('FLPRODUCT'), config.FLPRODUCT)

    def test_set_config_env_bad(self):
        self.assertIsNone(config.set_config_env(f"{self.datadir}/config_empty.json"))  # noqa: E501

    def test_set_env_config_value(self):
        config.TARGETVERSION = None
        config.set_config_env('tests/data/config.json')
        self.assertEqual(config.TARGETVERSION, '10')
