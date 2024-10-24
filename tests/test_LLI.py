import argparse
import logging
import unittest
from pathlib import Path
from unittest.mock import patch

import ou_dedetai.config as config
import ou_dedetai.main as LLI


class TestLLICli(unittest.TestCase):
    # Goal: pass command arguments & verify that the correct variables are set
    # and/or the correct functions are ultimately called.
    def setUp(self):
        self.parser = LLI.get_parser()

    def test_parse_args_backup(self):
        cli_args = self.parser.parse_args(args=['--backup'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('backup', config.ACTION.__name__)

    def test_parse_args_check_updates(self):
        cli_args = self.parser.parse_args(args=['--check-for-updates'])
        LLI.parse_args(cli_args, self.parser)
        self.assertTrue(config.CHECK_UPDATES)

    def test_parse_args_config_file(self):
        user_file_path = str(Path.home() / 'test.json')
        args = ['--config', user_file_path]
        cli_args = self.parser.parse_args(args=args)
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual(user_file_path, config.CONFIG_FILE)

    def test_parse_args_create_shortcuts(self):
        cli_args = self.parser.parse_args(args=['--create-shortcuts'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('create_shortcuts', config.ACTION.__name__)

    def test_parse_args_custom_binary_path_good(self):
        user_path = str(Path.home())
        args = ['--custom-binary-path', user_path]
        cli_args = self.parser.parse_args(args=args)
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual(user_path, config.CUSTOMBINPATH)

    @patch('argparse._sys.exit')  # override error exit command
    def test_parse_args_custom_binary_path_bad(self, mocked_input):
        user_path = '/nonexistent/path'
        args = ['--custom-binary-path', user_path]
        cli_args = self.parser.parse_args(args=args)
        LLI.parse_args(cli_args, self.parser)
        self.assertIsNone(config.CUSTOMBINPATH)

    def test_parse_args_debug(self):
        cli_args = self.parser.parse_args(args=['--debug'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual(config.LOG_LEVEL, logging.DEBUG)

    def test_parse_args_delete_log(self):
        cli_args = self.parser.parse_args(args=['--delete-log'])
        LLI.parse_args(cli_args, self.parser)
        self.assertTrue(config.DELETE_LOG)

    def test_parse_args_edit_config(self):
        cli_args = self.parser.parse_args(args=['--edit-config'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('edit_config', config.ACTION.__name__)

    def test_parse_args_force_root(self):
        cli_args = self.parser.parse_args(args=['--force-root'])
        LLI.parse_args(cli_args, self.parser)
        self.assertTrue(config.LOGOS_FORCE_ROOT)

    def test_parse_args_install_app(self):
        cli_args = self.parser.parse_args(args=['--install-app'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('install_app', config.ACTION.__name__)

    def test_parse_args_install_dependencies(self):
        cli_args = self.parser.parse_args(args=['--install-dependencies'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('install_dependencies', config.ACTION.__name__)

    def test_parse_args_passive(self):
        cli_args = self.parser.parse_args(args=['--passive'])
        LLI.parse_args(cli_args, self.parser)
        self.assertTrue(config.PASSIVE)

    def test_parse_args_remove_index_files(self):
        cli_args = self.parser.parse_args(args=['--remove-index-files'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('remove_index_files', config.ACTION.__name__)

    def test_parse_args_remove_install_dir(self):
        cli_args = self.parser.parse_args(args=['--remove-install-dir'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('remove_install_dir', config.ACTION.__name__)

    def test_parse_args_remove_library_catalog(self):
        cli_args = self.parser.parse_args(args=['--remove-library-catalog'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('remove_library_catalog', config.ACTION.__name__)

    def test_parse_args_restore(self):
        cli_args = self.parser.parse_args(args=['--restore'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('restore', config.ACTION.__name__)

    def test_parse_args_run_indexing(self):
        cli_args = self.parser.parse_args(args=['--run-indexing'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('run_indexing', config.ACTION.__name__)

    def test_parse_args_run_installed_app(self):
        cli_args = self.parser.parse_args(args=['--run-installed-app'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('run_installed_app', config.ACTION.__name__)

    def test_parse_args_run_winetricks(self):
        cli_args = self.parser.parse_args(args=['--run-winetricks'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('run_winetricks', config.ACTION.__name__)

    def test_parse_args_set_appimage_badfile(self):
        config.WINEBIN_CODE = 'AppImage'
        badfile = str(Path(__file__).parent / 'data' / 'config.json')
        args = ['--set-appimage', badfile]
        cli_args = self.parser.parse_args(args=args)
        self.assertRaises(
            argparse.ArgumentTypeError,
            LLI.parse_args, cli_args, self.parser
        )

    def test_parse_args_set_appimage_nofile(self):
        config.WINEBIN_CODE = 'AppImage'
        args = ['--set-appimage', '/path/to/appimage']
        cli_args = self.parser.parse_args(args=args)
        self.assertRaises(
            argparse.ArgumentTypeError,
            LLI.parse_args, cli_args, self.parser
        )

    def test_parse_args_skip_dependencies(self):
        cli_args = self.parser.parse_args(args=['--skip-dependencies'])
        LLI.parse_args(cli_args, self.parser)
        self.assertTrue(config.SKIP_DEPENDENCIES)

    def test_parse_args_skip_fonts(self):
        cli_args = self.parser.parse_args(args=['--skip-fonts'])
        LLI.parse_args(cli_args, self.parser)
        self.assertTrue(config.SKIP_FONTS)

    def test_parse_args_toggle_app_logging(self):
        cli_args = self.parser.parse_args(args=['--toggle-app-logging'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('toggle_app_logging', config.ACTION.__name__)

    def test_parse_args_update_latest_appimage_disabled(self):
        config.WINEBIN_CODE = None
        cli_args = self.parser.parse_args(args=['--update-latest-appimage'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual('disabled', config.ACTION)

    def test_parse_args_update_latest_appimage_enabled(self):
        config.WINEBIN_CODE = 'AppImage'
        cli_args = self.parser.parse_args(args=['--update-latest-appimage'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual(
            'update_latest_appimage',
            config.ACTION.__name__
        )

    def test_parse_args_update_self(self):
        cli_args = self.parser.parse_args(args=['--update-self'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual(
            'update_self',
            config.ACTION.__name__
        )

    def test_parse_args_verbose(self):
        cli_args = self.parser.parse_args(args=['--verbose'])
        LLI.parse_args(cli_args, self.parser)
        self.assertEqual(config.LOG_LEVEL, logging.INFO)


class TestLLI(unittest.TestCase):
    @patch('curses.wrapper')
    def test_run_control_panel_curses(self, mock_curses):
        config.DIALOG = 'curses'
        LLI.run_control_panel()
        self.assertTrue(mock_curses.called)

    @patch('ou_dedetai.tui_app.control_panel_app')
    @patch('ou_dedetai.gui_app.control_panel_app')
    def test_run_control_panel_none(self, mock_gui, mock_tui):
        config.DIALOG = None
        LLI.run_control_panel()
        self.assertTrue(mock_gui.called)

    @patch('ou_dedetai.tui_app.control_panel_app')
    @patch('ou_dedetai.gui_app.control_panel_app')
    def test_run_control_panel_tk(self, mock_gui, mock_tui):
        config.DIALOG = 'tk'
        LLI.run_control_panel()
        self.assertTrue(mock_gui.called)
