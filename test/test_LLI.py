import argparse
import unittest
from pathlib import Path
from unittest.mock import patch

import config
import LogosLinuxInstaller as LLI


class TestLLICli(unittest.TestCase):
    def setUp(self):
        config.CONFIG_FILE = Path(__file__).parent / 'data' / 'config.json'
        patcher = patch(
            'argparse.ArgumentParser.parse_args',
            return_value=argparse.Namespace(
                skip_fonts=None,
                check_for_updates=None,
                skip_dependencies=None,
                verbose=None,
                debug=None,
                config=None,
                force_root=None,
                custom_binary_path=None,
                delete_log=None,
                passive=None,
                install_app=None,
                run_installed_app=None,
                run_indexing=None,
                remove_library_catalog=None,
                remove_index_files=None,
                edit_config=None,
                install_dependencies=None,
                backup=None,
                restore=None,
                update_self=None,
                update_latest_appimage=None,
                set_appimage=None,
                get_winetricks=None,
                run_winetricks=None,
                toggle_app_logging=None,
                create_shortcuts=None,
                remove_install_dir=None,
                dirlink=None,
                make_skel=None,
                check_resources=None,
            )
        )
        self.parser = LLI.get_parser()
        self.mock_parse_args = patcher.start()
        self.addCleanup(patcher.stop)

    def test_parse_args_backup(self):
        self.mock_parse_args.return_value.backup = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('backup', config.ACTION.__name__)

    def test_parse_args_create_shortcuts(self):
        self.mock_parse_args.return_value.create_shortcuts = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('create_shortcuts', config.ACTION.__name__)

    def test_parse_args_edit_config(self):
        self.mock_parse_args.return_value.edit_config = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('edit_config', config.ACTION.__name__)

    def test_parse_args_install_app(self):
        self.mock_parse_args.return_value.install_app = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('install', config.ACTION.__name__)

    def test_parse_args_install_dependencies(self):
        self.mock_parse_args.return_value.install_dependencies = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('check_dependencies', config.ACTION.__name__)

    def test_parse_args_remove_index_files(self):
        self.mock_parse_args.return_value.remove_index_files = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('remove_all_index_files', config.ACTION.__name__)

    def test_parse_args_remove_install_dir(self):
        self.mock_parse_args.return_value.remove_install_dir = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('remove_install_dir', config.ACTION.__name__)

    def test_parse_args_remove_library_catalog(self):
        self.mock_parse_args.return_value.remove_library_catalog = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('remove_library_catalog', config.ACTION.__name__)

    def test_parse_args_restore(self):
        self.mock_parse_args.return_value.restore = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('restore', config.ACTION.__name__)

    def test_parse_args_run_indexing(self):
        self.mock_parse_args.return_value.run_indexing = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('run_indexing', config.ACTION.__name__)

    def test_parse_args_run_installed_app(self):
        self.mock_parse_args.return_value.run_installed_app = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('run_logos', config.ACTION.__name__)

    def test_parse_args_run_winetricks(self):
        self.mock_parse_args.return_value.run_winetricks = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('run_winetricks', config.ACTION.__name__)

    def test_parse_args_toggle_app_logging(self):
        self.mock_parse_args.return_value.toggle_app_logging = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('switch_logging', config.ACTION.__name__)

    def test_parse_args_update_latest_appimage_disabled(self):
        self.mock_parse_args.return_value.update_latest_appimage = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual('disabled', config.ACTION)

    def test_parse_args_update_latest_appimage_enabled(self):
        config.WINEBIN_CODE = 'AppImage'
        self.mock_parse_args.return_value.update_latest_appimage = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual(
            'update_to_latest_recommended_appimage',
            config.ACTION.__name__
        )

    def test_parse_args_update_self(self):
        self.mock_parse_args.return_value.update_self = True
        LLI.parse_args(self.mock_parse_args.return_value, self.parser)
        self.assertEqual(
            'update_to_latest_lli_release',
            config.ACTION.__name__
        )
