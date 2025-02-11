import json
import tempfile
import shutil
import unittest
from pathlib import Path

import ou_dedetai.config as config
import ou_dedetai.utils as utils

URLOBJ = utils.UrlProps('http://ip.me')


class TestUtils(unittest.TestCase):
    def test_check_logos_release_version_false(self):
        result = utils.check_logos_release_version('1.1.1', 1, 3)
        self.assertFalse(result)

    def test_check_logos_release_version_true(self):
        result = utils.check_logos_release_version('1.1.1', 2, 3)
        self.assertTrue(result)

    def test_compare_logos_linux_installer_version_custom(self):
        config.LLI_CURRENT_VERSION = '4.0.1'
        config.LLI_LATEST_VERSION = '4.0.0-alpha.1'
        status, _ = utils.compare_logos_linux_installer_version()
        self.assertEqual(2, status)

    def test_compare_logos_linux_installer_version_notset(self):
        config.LLI_CURRENT_VERSION = None
        config.LLI_LATEST_VERSION = '4.0.1'
        status, _ = utils.compare_logos_linux_installer_version()
        self.assertFalse(status)

    def test_compare_logos_linux_installer_version_uptodate(self):
        config.LLI_CURRENT_VERSION = '4.0.0-alpha.1'
        config.LLI_LATEST_VERSION = '4.0.0-alpha.1'
        status, _ = utils.compare_logos_linux_installer_version()
        self.assertEqual(1, status)

    def test_compare_logos_linux_installer_version_yes(self):
        config.LLI_CURRENT_VERSION = '4.0.0-alpha.1'
        config.LLI_LATEST_VERSION = '4.0.1'
        status, _ = utils.compare_logos_linux_installer_version()
        self.assertEqual(0, status)

    def test_delete_symlink_exists(self):
        target = Path(__file__).parent / 'data' / 'config.json'
        new_symlink = Path('symlink')
        if new_symlink.is_symlink():
            new_symlink.unlink()
        new_symlink.symlink_to(target)
        if new_symlink.is_symlink():
            utils.delete_symlink(new_symlink)
            self.assertFalse(new_symlink.is_symlink())

    def test_delete_symlink_notexists(self):
        new_symlink = Path('symlink')
        utils.delete_symlink(new_symlink)
        self.assertFalse(new_symlink.is_symlink())

    def test_enough_disk_space_false(self):
        self.assertFalse(utils.enough_disk_space(Path.home(), 1024**6))

    def test_enough_disk_space_true(self):
        self.assertTrue(utils.enough_disk_space(Path.home(), 1))

    def test_file_exists_false(self):
        self.assertFalse(utils.file_exists('~/NotGonnaFindIt.exe'))

    def test_file_exists_none(self):
        self.assertFalse(utils.file_exists(None))

    def test_file_exists_true(self):
        self.assertTrue(utils.file_exists('~/.bashrc'))

    def test_fileprops_get_size(self):
        f = Path(__file__).parent / 'data' / 'config_empty.json'
        fo = utils.FileProps(f)
        self.assertEqual(fo.size, 4)

    def test_fileprops_get_md5(self):
        f = Path(__file__).parent / 'data' / 'config_empty.json'
        fo = utils.FileProps(f)
        self.assertEqual(fo.get_md5(), 'W3aw7vmviiMAZz4FU/YJ+Q==')

    def test_filter_versions(self):
        allvers = ['1.0', '1.1', '1.2', '1.3', '1.4', '1.5']
        valvers = ['1.0', '1.1', '1.2', '1.3',]
        filvers = utils.filter_versions(allvers, 4, 2)
        self.assertEqual(valvers, filvers)

    def test_get_downloaded_file_path_found(self):
        config.MYDOWNLOADS = '~/Downloads'
        p = Path(utils.get_downloaded_file_path('README.md'))
        self.assertEqual(p.parent.name, 'LogosLinuxInstaller')

    def test_get_downloaded_file_path_notfound(self):
        config.MYDOWNLOADS = '~/Downloads'
        self.assertIsNone(utils.get_downloaded_file_path('NothingToFind.exe'))

    def test_get_pids_using_file(self):
        with tempfile.TemporaryFile() as tf:
            pids = utils.get_pids_using_file(tf)
        self.assertTrue(isinstance(pids, set))

    def test_get_runmode(self):
        self.assertEqual('script', utils.get_runmode())

    def test_get_wine_options(self):
        config.DIALOG = 'curses'
        binaries = [
            '/usr/bin/wine64.exe',
        ]
        opts = utils.get_wine_options([], binaries)
        opt_codes = [o[0] for o in opts]
        choices = ["Recommended", "System", "Exit"]
        self.assertEqual(choices, opt_codes)

    def test_get_winebincode_appimage(self):
        binary = 'test.AppImage'
        code, _ = utils.get_winebin_code_and_desc(binary)
        self.assertEqual('AppImage', code)

    def test_get_winebincode_pol(self):
        binary = 'test/PlayOnLinux/wine64.exe'
        code, _ = utils.get_winebin_code_and_desc(binary)
        self.assertEqual('PlayOnLinux', code)

    def test_get_winebincode_proton(self):
        binary = 'test/Proton/wine64.exe'
        code, _ = utils.get_winebin_code_and_desc(binary)
        self.assertEqual('Proton', code)

    # def test_get_winebincode_recommended(self):
    #     pass

    def test_get_winebincode_system(self):
        binary = '/usr/bin/wine64.exe'
        code, _ = utils.get_winebin_code_and_desc(binary)
        self.assertEqual('System', code)

    def test_have_lib(self):
        self.assertTrue(utils.have_lib('libgcc', None))

    def test_urlprops_get_headers(self):
        self.assertIsNotNone(URLOBJ.headers)

    def test_urlprops_get_headers_none(self):
        urlobj = utils.UrlProps()
        self.assertIsNone(urlobj.headers)

    def test_urlprops_get_size(self):
        self.assertIsNotNone(URLOBJ.size)

    def test_urlprops_get_size_none(self):
        urlobj = utils.UrlProps()
        self.assertIsNone(urlobj.size)

    def test_urlprops_get_md5(self):
        self.assertIsNone(URLOBJ.md5)

    def test_grep_found(self):
        self.assertTrue(utils.grep(r'LOGOS_DIR', self.grepfile))

    def test_grep_nofile(self):
        self.assertIsNone(utils.grep(r'test', 'thisfiledoesnotexist'))

    def test_grep_notfound(self):
        self.assertFalse(utils.grep(r'TEST_NOT_IN_FILE', self.grepfile))



class TestUtilsConfigFile(unittest.TestCase):
    def setUp(self):
        self.cfg = Path('tests/data/subdir/test_config.json')

    def test_update_config_file(self):
        utils.write_config(str(self.cfg))
        utils.update_config_file(str(self.cfg), 'TARGETVERSION', '100')
        with self.cfg.open() as f:
            cfg_data = json.load(f)
        self.assertEqual(cfg_data.get('TARGETVERSION'), '100')

    def test_write_config_parentdir(self):
        utils.write_config(str(self.cfg))
        self.assertTrue(self.cfg.parent.is_dir())

    def test_write_config_writedata(self):
        utils.write_config(str(self.cfg))
        self.assertTrue(self.cfg.read_text())

    def tearDown(self):
        shutil.rmtree(self.cfg.parent)
