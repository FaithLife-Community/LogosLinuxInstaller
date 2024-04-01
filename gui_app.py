
# References:
#   - https://tkdocs.com/
#   - https://github.com/thw26/LogosLinuxInstaller/blob/master/LogosLinuxInstaller.sh  # noqa: E501

import logging
import os
import threading
from pathlib import Path
from queue import Queue
from threading import Thread

from tkinter import PhotoImage
from tkinter import Tk
from tkinter import Toplevel
from tkinter import filedialog as fd
from tkinter.ttk import Style

import config
import control
import gui
import installer
import msg
import utils
import wine


class Root(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.classname = kwargs.get('classname')
        # Set the theme.
        self.style = Style()
        self.style.theme_use('alt')

        # Update color scheme.
        self.style.configure('TCheckbutton', bordercolor=config.LOGOS_GRAY)
        self.style.configure('TCombobox', bordercolor=config.LOGOS_GRAY)
        self.style.configure('TCheckbutton', indicatorcolor=config.LOGOS_GRAY)
        self.style.configure('TRadiobutton', indicatorcolor=config.LOGOS_GRAY)
        bg_widgets = [
            'TCheckbutton', 'TCombobox', 'TFrame', 'TLabel', 'TRadiobutton'
        ]
        fg_widgets = ['TButton', 'TSeparator']
        for w in bg_widgets:
            self.style.configure(w, background=config.LOGOS_WHITE)
        for w in fg_widgets:
            self.style.configure(w, background=config.LOGOS_GRAY)
        self.style.configure(
            'Horizontal.TProgressbar',
            thickness=10, background=config.LOGOS_BLUE,
            bordercolor=config.LOGOS_GRAY,
            troughcolor=config.LOGOS_GRAY,
        )

        # Justify to the left [('Button.label', {'sticky': 'w'})]
        self.style.layout(
            "TButton", [(
                'Button.border', {
                    'sticky': 'nswe', 'children': [(
                        'Button.focus', {
                            'sticky': 'nswe', 'children': [(
                                'Button.padding', {
                                    'sticky': 'nswe', 'children': [(
                                        'Button.label', {'sticky': 'w'}
                                    )]
                                }
                            )]
                        }
                    )]
                }
            )]
        )

        # Make root widget's outer border expand with window.
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Set panel icon.
        app_dir = Path(__file__).parent
        self.icon = app_dir / 'img' / 'logos4-128-icon.png'
        self.pi = PhotoImage(file=f'{self.icon}')
        self.iconphoto(False, self.pi)


class InstallerWindow():
    def __init__(self, new_win, root, **kwargs):
        # Set root parameters.
        self.win = new_win
        self.root = root
        self.win.title("Faithlife Bible Software Installer")
        self.win.resizable(False, False)
        self.gui = gui.InstallerGui(self.win)

        # Initialize variables.
        self.flproduct = None  # config.FLPRODUCT
        self.release_thread = None
        self.wine_exe = None
        self.wine_thread = None
        self.winetricksbin = None
        self.appimage_verified = None
        self.logos_verified = None
        self.tricks_verified = None
        self.synchronize_config()
        self.set_product()
        self.set_version()

        # Set widget callbacks and event bindings.
        self.gui.product_dropdown.bind(
            '<<ComboboxSelected>>',
            self.set_product
        )
        self.gui.version_dropdown.bind(
            '<<ComboboxSelected>>',
            self.set_version
        )
        self.gui.release_dropdown.bind(
            '<<ComboboxSelected>>',
            self.set_release
        )
        self.gui.release_check_button.config(
            command=self.on_release_check_released
        )
        self.gui.wine_dropdown.bind(
            '<<ComboboxSelected>>',
            self.set_wine
        )
        self.gui.wine_check_button.config(
            command=self.on_wine_check_released
        )
        self.gui.tricks_dropdown.bind(
            '<<WinetricksSelected>>',
            self.set_winetricks
        )
        self.set_winetricks()
        self.gui.fonts_checkbox.config(command=self.set_skip_fonts)
        self.gui.skipdeps_checkbox.config(command=self.set_skip_dependencies)
        self.gui.cancel_button.config(command=self.on_cancel_released)
        self.gui.okay_button.config(command=self.on_okay_released)

        # Set root widget event bindings.
        self.root.bind(
            "<Return>",
            self.on_okay_released
        )
        self.root.bind(
            "<Escape>",
            self.on_cancel_released
        )
        self.root.bind(
            "<<ReleaseCheckProgress>>",
            self.update_release_check_progress
        )
        self.root.bind(
            "<<SetWineExe>>",
            self.update_wine_check_progress
        )
        self.get_q = Queue()
        download_events = [
            "<<GetAppImage>>",
            "<<GetLogos>>",
            "<<GetWinetricks>>",
        ]
        for evt in download_events:
            self.root.bind(evt, self.update_download_progress)
        self.check_q = Queue()
        check_events = [
            "<<CheckAppImage>>",
            "<<CheckLogos>>",
        ]
        for evt in check_events:
            self.root.bind(evt, self.update_file_check_progress)
        self.root.bind(
            "<<CheckInstallProgress>>",
            self.update_install_progress
        )
        self.root.bind(
            "<<VerifyDownloads>>",
            self.start_verify_downloads_thread
        )
        self.root.bind(
            "<<StartInstall>>",
            self.start_install_thread
        )
        self.install_q = Queue()
        self.root.bind(
            "<<UpdateInstallText>>",
            self.update_install_text
        )

    def set_product(self, evt=None):
        self.flproduct = self.gui.productvar.get()
        if self.flproduct.startswith('Logos'):
            config.FLPRODUCT = 'Logos'
            config.FLPRODUCTi = 'logos4'  # icon
            config.VERBUM_PATH = '/'
        elif self.flproduct.startswith('Verbum'):
            config.FLPRODUCT = 'Verbum'
            config.FLPRODUCTi = 'verbum'  # icon
            config.VERBUM_PATH = '/Verbum/'
        else:
            return
        self.gui.product_dropdown.selection_clear()
        self.verify_buttons()

    def set_version(self, evt=None):
        self.gui.targetversion = self.gui.versionvar.get()
        if self.gui.targetversion:
            config.TARGETVERSION = self.gui.targetversion
            self.gui.version_dropdown.selection_clear()
            self.verify_buttons()

    def set_release(self, evt=None):
        if self.gui.releasevar.get()[0] != 'C':  # ignore default text
            self.gui.logos_release_version = self.gui.releasevar.get()
        if self.gui.logos_release_version:
            config.LOGOS_RELEASE_VERSION = self.gui.logos_release_version
            self.gui.release_dropdown.selection_clear()
            self.verify_buttons()

    def set_wine(self, evt=None):
        self.wine_exe = self.gui.winevar.get()
        self.gui.wine_dropdown.selection_clear()
        if config.WINEPREFIX is None:
            config.WINEPREFIX = os.path.join(config.APPDIR, "wine64_bottle")
        self.verify_buttons()

    def set_winetricks(self, evt=None):
        self.winetricksbin = self.gui.tricksvar.get()
        self.gui.tricks_dropdown.selection_clear()
        if config.WINETRICKSBIN is None:
            # FIXME: Find dynamically.
            config.WINETRICKSBIN = '/usr/bin/winetricks'

    def verify_buttons(self):
        funcs = [
            self.verify_release_check_button,
            self.verify_wine_check_button,
            self.verify_okay_button,
        ]
        for f in funcs:
            f()
        self.synchronize_config()

    def verify_release_check_button(self):
        variables = [
            config.FLPRODUCT,
            config.TARGETVERSION,
        ]
        if all(variables):
            # self.messagevar.set("Download list of Releases and pick one")
            if not config.LOGOS_RELEASE_VERSION:
                self.start_release_check()

    def verify_wine_check_button(self):
        variables = [
            config.FLPRODUCT,
            config.TARGETVERSION,
            config.LOGOS_RELEASE_VERSION,
        ]
        if all(variables):
            # self.messagevar.set("Search for a Wine binary")
            if not config.WINE_EXE or not self.wine_exe:
                self.start_wine_check()

    def verify_okay_button(self):
        variables = [
            config.FLPRODUCT,
            config.TARGETVERSION,
            config.LOGOS_RELEASE_VERSION,
            config.WINE_EXE,
        ]
        if all(variables):
            self.gui.okay_button.state(['!disabled'])
            # self.messagevar.set("Click Install")

    def start_release_check(self):
        if self.release_thread and self.release_thread.is_alive():
            return
        self.gui.progress.config(mode='indeterminate')
        self.release_q = Queue()
        self.release_thread = Thread(
            target=utils.get_logos_releases,
            kwargs={'app': self},
            daemon=True,
        )
        self.release_thread.start()
        self.gui.release_check_button.state(['disabled'])
        self.gui.progress.start()
        self.gui.statusvar.set("Downloading Release list...")

    def on_release_check_released(self, evt=None):
        self.start_release_check()

    def run_wine_check(self):
        config.LOGOS_RELEASE_VERSION = self.release_version = self.gui.releasevar.get()  # noqa: E501
        installer.logos_setup()
        self.gui.wine_dropdown['values'] = utils.get_wine_options(
            utils.find_appimage_files(),
            utils.find_wine_binary_files()
        )
        self.root.event_generate('<<SetWineExe>>')

    def start_wine_check(self):
        if self.wine_thread and self.wine_thread.is_alive():
            return
        self.gui.progress.config(mode='indeterminate')
        self.wine_thread = Thread(
            target=self.run_wine_check,
            daemon=True,
        )
        self.wine_thread.start()
        self.gui.wine_check_button.state(['disabled'])
        self.gui.progress.start()
        self.gui.statusvar.set("Searching for valid wine executables...")

    def on_wine_check_released(self, evt=None):
        self.start_wine_check()

    def set_skip_fonts(self, evt=None):
        self.gui.skip_fonts = 1 - self.gui.fontsvar.get()  # invert True/False

    def set_skip_dependencies(self, evt=None):
        self.gui.skip_dependencies = 1 - self.gui.skipdepsvar.get()  # invert True/False  # noqa: E501

    def set_downloads(self):
        dl_dir = Path(config.MYDOWNLOADS)
        appimage_download = Path(dl_dir / Path(config.RECOMMENDED_WINE64_APPIMAGE_FULL_URL).name)  # noqa: E501
        logos_download = Path(dl_dir / f"{self.flproduct}_v{self.gui.logos_release_version}-x64.msi")  # noqa: E501
        self.downloads = [
            [
                'appimage',
                config.RECOMMENDED_WINE64_APPIMAGE_FULL_URL, appimage_download,
                self.appimage_verified,
                '<<GetAppImage>>',
                '<<CheckAppImage>>',
            ],
            [
                'logos',
                config.LOGOS64_URL,
                logos_download,
                self.logos_verified,
                '<<GetLogos>>',
                '<<CheckLogos>>',
            ],
        ]
        if self.winetricksbin.startswith('Download'):
            tricks_url = config.WINETRICKS_URL
            tricks_download = config.WINETRICKSBIN
            self.downloads.append(
                [
                    'winetricks',
                    tricks_url,
                    tricks_download,
                    self.tricks_verified,
                    '<<GetWinetricks>>',
                    '<<CheckWinetricks>>'
                ]
            )
        self.downloads_orig = self.downloads.copy()

    def synchronize_config(self):
        if self.flproduct in ['Logos', 'Verbum']:
            config.FLPRODUCT = self.flproduct
            config.FLPRODUCTi = config.FLPRODUCT.lower()
            if config.FLPRODUCTi.startswith('logos'):
                config.FLPRODUCTi += '4'
        if self.gui.targetversion:
            config.TARGETVERSION = self.gui.targetversion
        if self.gui.logos_release_version:
            config.LOGOS_RELEASE_VERSION = self.gui.logos_release_version
            installer.logos_setup()
        if config.APPDIR:
            if config.WINEPREFIX is None:
                config.WINEPREFIX = os.path.join(config.APPDIR, "wine64_bottle")  # noqa: E501
            if self.wine_exe:
                config.WINE_EXE = self.wine_exe
                if config.WINEBIN_CODE is None:
                    config.WINEBIN_CODE = utils.get_winebin_code_and_desc(config.WINE_EXE)[0]  # noqa: E501
            if self.winetricksbin:
                if self.winetricksbin.startswith('System') and self.gui.sys_winetricks:  # noqa: E501
                    config.WINETRICKSBIN = self.gui.sys_winetricks[0]
                elif self.winetricksbin.startswith('Download'):
                    config.WINETRICKSBIN = os.path.join(config.APPDIR_BINDIR, "winetricks")  # noqa: E501
            if config.LOGOS_ICON_URL is None:
                app_dir = Path(__file__).parent
                config.LOGOS_ICON_URL = app_dir / 'img' / f"{config.FLPRODUCTi}-128-icon.png"  # noqa: E501
            if config.LOGOS_ICON_FILENAME is None:
                config.LOGOS_ICON_FILENAME = os.path.basename(config.LOGOS_ICON_URL)  # noqa: E501
        config.SKIP_FONTS = self.gui.skip_fonts if self.gui.skip_fonts == 1 else 0  # noqa: E501
        config.SKIP_DEPENDENCIES = self.gui.skip_dependencies if self.gui.skip_dependencies == 1 else 0  # noqa: E501

    def on_okay_released(self, evt=None):
        # Set required config.
        self.synchronize_config()
        self.gui.okay_button.state(['disabled'])
        # self.messagevar.set('')
        if installer.check_existing_install():
            logging.debug(f"Install exists: {installer.check_existing_install()}")  # noqa: E501
            self.win.destroy()
            return 1
        self.set_downloads()
        # Update desktop panel icon.
        self.root.icon = config.LOGOS_ICON_URL
        self.root.event_generate("<<VerifyDownloads>>")

    def on_cancel_released(self, evt=None):
        self.win.destroy()
        return 1

    def start_verify_downloads_thread(self, evt=None):
        th = Thread(target=self.verify_downloads, daemon=True)
        th.start()

    def start_download_thread(self, name, url, dest, evt):
        m = f"Downloading {url}"
        msg.cli_msg(m)
        logging.info(m)
        self.gui.statusvar.set(m)
        self.gui.progressvar.set(0)
        self.gui.progress.config(mode='determinate')
        a = (url, dest)
        k = {'app': self, 'evt': evt}
        th = Thread(
            target=utils.net_get,
            name=f"get-{name}",
            args=a,
            kwargs=k,
            daemon=True
        )
        th.start()

    def start_check_thread(self, name, url, dest, evt):
        m = f"Verifying file {dest}..."
        msg.cli_msg(m)
        logging.info(m)
        self.gui.statusvar.set(m)
        self.gui.progressvar.set(0)
        self.gui.progress.config(mode='indeterminate')
        self.gui.progress.start()
        a = (url, dest)
        k = {'app': self, 'evt': evt}
        th = Thread(
            target=utils.verify_downloaded_file,
            name=f"check-{name}",
            args=a,
            kwargs=k,
            daemon=True
        )
        th.start()

    def start_install_thread(self, evt=None):
        m = "Installing..."
        msg.cli_msg(m)
        self.gui.statusvar.set(m)
        self.gui.progress.config(mode='indeterminate')
        self.gui.progress.start()
        th = Thread(
            target=installer.finish_install,
            kwargs={'app': self},
            daemon=True
        )
        th.start()

    def verify_downloads(self, evt=None):
        while len(self.downloads) > 0:
            name, url, dest, test, dl_evt, ch_evt = self.downloads[0]
            ch_thread = None
            dl_thread = None
            for t in threading.enumerate():
                if t.name == f"check-{name}":
                    ch_thread = t
                elif t.name == f"get-{name}":
                    dl_thread = t

            if not dest.is_file() and dl_thread is None:
                # No file; no thread started.
                logging.info("Starting download thread.")
                self.start_download_thread(name, url, dest, dl_evt)
                continue
            elif dl_thread is not None:
                # Download thread started.
                continue
            elif dest.is_file() and test is None and ch_thread is None:
                # File downloaded; no check started.
                logging.info("Starting file-check thread.")
                self.start_check_thread(name, url, dest, ch_evt)
                continue
            elif dest.is_file() and test is None and ch_thread is not None:
                # File downloaded; still checking.
                continue
            elif dest.is_file() and test is False and dl_thread is None:
                # File check failed; restart download.
                if name == 'appimage':
                    self.appimage_verified = None
                elif name == 'logos':
                    self.logos_verified = None
                logging.info("Starting download thread.")
                self.start_download_thread(name, url, dest, dl_evt)
                continue
            elif test is True and None not in [ch_thread, dl_thread]:
                continue  # some thread still going
            elif test is True and ch_thread is None and dl_thread is None:
                # file is downloaded and verified
                logging.info(f"Removing item from download list: {self.downloads[0]}.")  # noqa: E501
                self.downloads.pop(0)
                continue

        ready = 0
        for d in self.downloads_orig:
            if d[3] is True:
                ready += 1
        if ready == len(self.downloads_orig):
            self.root.event_generate('<<StartInstall>>')

    def update_release_check_progress(self, evt=None):
        self.gui.progress.stop()
        self.gui.statusvar.set('')
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)
        r = self.release_q.get()
        if r is not None:
            self.gui.release_dropdown['values'] = r
            self.gui.releasevar.set(self.gui.release_dropdown['values'][0])
            self.set_release()
            self.synchronize_config()
            self.verify_buttons()
        else:
            self.gui.release_check_button.state(['!disabled'])
            self.gui.statusvar.set("Failed to get release list. Check connection and try again.")  # noqa: E501

    def update_wine_check_progress(self, evt=None):
        self.gui.progress.stop()
        self.gui.statusvar.set('')
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)
        self.gui.winevar.set(self.gui.wine_dropdown['values'][0])
        # FIXME: Probably need better test for failure condition:
        if len(self.gui.winevar.get()) == 0:
            self.gui.statusvar.set("No valid Wine binary found!")
            self.gui.wine_check_button.state(['!disabled'])
        self.set_wine()
        self.synchronize_config()
        self.verify_buttons()

    def update_file_check_progress(self, evt=None):
        e, r = self.check_q.get()
        if e == "<<CheckAppImage>>":
            self.appimage_verified = r
        elif e == "<<CheckLogos>>":
            self.logos_verified = r
        elif e == "<<CheckWinetricks>>":
            self.tricks_verified = r
        # "Current" download should always be 1st item in self.downloads:
        self.downloads[0][3] = r
        self.gui.progress.stop()
        self.gui.statusvar.set('')
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)

    def update_download_progress(self, evt=None):
        d = self.get_q.get()
        self.gui.progressvar.set(int(d))

    def update_install_text(self, evt=None):
        text = ''
        if evt is not None:
            text = self.install_q.get()
        self.gui.statusvar.set(text)

    def update_install_progress(self, evt=None):
        self.gui.progress.stop()
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)
        self.gui.statusvar.set('')
        self.gui.okay_button.config(
            text="Exit",
            command=self.on_cancel_released,
        )
        self.gui.okay_button.state(['!disabled'])
        self.root.event_generate('<<InstallFinished>>')
        self.win.destroy()
        return 0


class ControlWindow():
    def __init__(self, root, *args, **kwargs):
        # Set root parameters.
        self.root = root
        self.root.title("Faithlife Bible Software Control Panel")
        self.root.resizable(False, False)
        self.gui = gui.ControlGui(self.root)

        self.configure_app_button()
        self.gui.run_indexing_radio.config(
            command=self.on_action_radio_clicked
        )
        self.gui.remove_library_catalog_radio.config(
            command=self.on_action_radio_clicked
        )
        self.gui.remove_index_files_radio.config(
            command=self.on_action_radio_clicked
        )
        self.gui.actions_button.config(command=self.gui.actioncmd)

        self.gui.loggingstatevar.set('Enable')
        self.gui.logging_button.config(
            text=self.gui.loggingstatevar.get(),
            command=self.switch_logging
        )
        self.gui.logging_button.state(['disabled'])

        self.gui.config_button.config(command=control.edit_config)
        self.gui.deps_button.config(command=self.install_deps)
        self.gui.backup_button.config(command=self.run_backup)
        self.gui.restore_button.config(command=self.run_restore)
        self.gui.update_lli_button.config(
            command=self.update_to_latest_lli_release
        )
        self.gui.latest_appimage_button.config(
            command=self.update_to_latest_appimage
        )
        if config.WINEBIN_CODE != "AppImage" and config.WINEBIN_CODE != "Recommended":  # noqa: E501
            self.gui.latest_appimage_button.state(['disabled'])
            gui.ToolTip(
                self.gui.latest_appimage_button,
                "This button is disabled. The configured install was not created using an AppImage."  # noqa: E501
            )
            self.gui.set_appimage_button.state(['disabled'])
            gui.ToolTip(
                self.gui.set_appimage_button,
                "This button is disabled. The configured install was not created using an AppImage."  # noqa: E501
            )
        self.update_latest_lli_release_button()
        self.update_latest_appimage_button()
        self.gui.set_appimage_button.config(command=self.set_appimage)
        self.gui.get_winetricks_button.config(command=self.get_winetricks)
        self.gui.run_winetricks_button.config(command=self.launch_winetricks)
        self.update_run_winetricks_button()

        self.logging_q = Queue()
        self.root.bind('<<InitLoggingButton>>', self.initialize_logging_button)
        self.root.bind('<<UpdateLoggingButton>>', self.update_logging_button)
        self.message_q = Queue()
        self.root.bind('<<ClearMessage>>', self.clear_message_text)
        self.root.bind('<<UpdateMessage>>', self.update_message_text)
        self.progress_q = Queue()
        self.root.bind(
            '<<StartIndeterminateProgress>>',
            self.start_indeterminate_progress
        )
        self.root.bind(
            '<<StopIndeterminateProgress>>',
            self.stop_indeterminate_progress
        )
        self.root.bind(
            '<<UpdateProgress>>',
            self.update_progress
        )
        self.root.bind(
            "<<UpdateLatestAppImageButton>>",
            self.update_latest_appimage_button
        )
        self.root.bind('<<InstallFinished>>', self.update_app_button)
        # self.root.bind('<<CheckInstallProgress>>', self.update_app_button)

        # Start function to determine app logging state.
        if utils.app_is_installed():
            t = Thread(
                target=wine.get_app_logging_state,
                kwargs={'app': self, 'init': True}
            )
            t.start()
            self.gui.messagevar.set('Getting current app logging status...')
            self.start_indeterminate_progress()

    def configure_app_button(self, evt=None):
        if utils.app_is_installed():
            self.gui.app_buttonvar.set(f"Run {config.FLPRODUCT}")
            self.gui.app_button.config(command=self.run_logos)
        else:
            self.gui.app_button.config(command=self.run_installer)

    def run_installer(self, evt=None):
        classname = "LogosLinuxInstaller"
        self.new_win = Toplevel()
        InstallerWindow(self.new_win, self.root, class_=classname)
        self.root.icon = config.LOGOS_ICON_URL

    def run_logos(self, evt=None):
        t = Thread(target=wine.run_logos)
        t.start()

    def on_action_radio_clicked(self, evt=None):
        if utils.app_is_installed():
            self.gui.actions_button.state(['!disabled'])
            if self.gui.actionsvar.get() == 'run-indexing':
                self.gui.actioncmd = self.run_indexing
            elif self.gui.actionsvar.get() == 'remove-library-catalog':
                self.gui.actioncmd = self.remove_library_catalog
            elif self.gui.actionsvar.get() == 'remove-index-files':
                self.gui.actioncmd = self.remove_indexes

    def run_indexing(self, evt=None):
        t = Thread(target=wine.run_indexing)
        t.start()

    def remove_library_catalog(self, evt=None):
        control.remove_library_catalog()

    def remove_indexes(self, evt=None):
        self.gui.messagevar.set("Removing indexes…")
        t = Thread(
            target=control.remove_all_index_files,
            kwargs={'app': self}
        )
        t.start()

    def run_backup(self, evt=None):
        # Get backup folder.
        if config.BACKUPDIR is None:
            config.BACKUPDIR = fd.askdirectory(
                parent=self.root,
                title=f"Choose folder for {config.FLPRODUCT} backups",
                initialdir=Path().home(),
            )
            if not config.BACKUPDIR:  # user cancelled
                return

        # Prepare progress bar.
        self.gui.progress.state(['!disabled'])
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)
        # Start backup thread.
        t = Thread(target=control.backup, args=[self], daemon=True)
        t.start()

    def run_restore(self, evt=None):
        # FIXME: Allow user to choose restore source?
        # Start restore thread.
        t = Thread(target=control.restore, args=[self], daemon=True)
        t.start()

    def install_deps(self, evt=None):
        utils.check_dependencies()

    def open_file_dialog(self, filetype_name, filetype_extension):
        file_path = fd.askopenfilename(
            title=f"Select {filetype_name}",
            filetypes=[
                (filetype_name, f"*.{filetype_extension}"),
                ("All Files", "*.*")
            ],
        )
        return file_path

    def update_to_latest_lli_release(self, evt=None):
        self.start_indeterminate_progress()
        self.gui.messagevar.set("Updating to latest Logos Linux Installer version…")  # noqa: E501
        t = Thread(
            target=utils.update_to_latest_lli_release,
        )
        t.start()

    def update_to_latest_appimage(self, evt=None):
        config.APPIMAGE_FILE_PATH = config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME  # noqa: E501
        self.start_indeterminate_progress()
        self.gui.messagevar.set("Updating to latest AppImage…")
        t = Thread(
            target=utils.set_appimage_symlink,
            kwargs={'app': self},
            daemon=True,
        )
        t.start()

    def set_appimage(self, evt=None):
        appimage_filename = self.open_file_dialog("AppImage", "AppImage")
        if not appimage_filename:
            return
        config.SELECTED_APPIMAGE_FILENAME = appimage_filename
        t = Thread(
            target=utils.set_appimage_symlink,
            kwargs={'app': self},
            daemon=True,
        )
        t.start()

    def get_winetricks(self, evt=None):
        winetricks_status = installer.set_winetricks()
        if winetricks_status == 0:
            self.gui.messagevar.set("Winetricks is installed.")
        else:
            self.gui.messagevar.set("")
        self.update_run_winetricks_button()

    def launch_winetricks(self, evt=None):
        self.gui.messagevar.set("Launching Winetricks…")
        wine.run_winetricks()

    def switch_logging(self, evt=None):
        prev_state = self.gui.loggingstatevar.get()
        new_state = 'Enable' if prev_state == 'Disable' else 'Disable'
        kwargs = {
            'action': new_state.lower(),
            'app': self,
        }
        self.gui.messagevar.set(f"Switching app logging to '{prev_state}d'...")
        self.gui.progress.state(['!disabled'])
        self.gui.progress.start()
        self.gui.logging_button.state(['disabled'])
        t = Thread(target=wine.switch_logging, kwargs=kwargs)
        t.start()

    def initialize_logging_button(self, evt=None):
        self.gui.messagevar.set('')
        self.gui.progress.stop()
        self.gui.progress.state(['disabled'])
        state = self.reverse_logging_state_value(self.logging_q.get())
        self.gui.loggingstatevar.set(state[:-1].title())
        self.gui.logging_button.state(['!disabled'])

    def update_logging_button(self, evt=None):
        self.gui.messagevar.set('')
        self.gui.progress.stop()
        self.gui.progress.state(['disabled'])
        state = self.logging_q.get()
        self.gui.loggingstatevar.set(state[:-1].title())
        self.gui.logging_button.state(['!disabled'])

    def update_app_button(self, evt=None):
        self.gui.app_button.state(['!disabled'])
        self.gui.app_buttonvar.set(f"Run {config.FLPRODUCT}")
        self.configure_app_button()

    def update_latest_lli_release_button(self, evt=None):
        status, reason = utils.compare_logos_linux_installer_version()
        msg = None
        if status == 0:
            state = '!disabled'
        elif status == 1:
            state = 'disabled'
            msg = "This button is disabled. Logos Linux Installer is up-to-date."  # noqa: E501
        elif status == 2:
            state = 'disabled'
            msg = "This button is disabled. Logos Linux Installer is newer than the latest release."  # noqa: E501
        if msg:
            gui.ToolTip(self.gui.update_lli_button, msg)
        self.clear_message_text()
        self.stop_indeterminate_progress()
        self.gui.update_lli_button.state([state])

    def update_latest_appimage_button(self, evt=None):
        status, reason = utils.compare_recommended_appimage_version()
        msg = None
        if status == 0:
            state = '!disabled'
        elif status == 1:
            state = 'disabled'
            msg = "This button is disabled. The AppImage is already set to the latest recommended."  # noqa: E501
        elif status == 2:
            state = 'disabled'
            msg = "This button is disabled. The AppImage version is newer than the latest recommended."  # noqa: E501
        if msg:
            gui.ToolTip(self.gui.latest_appimage_button, msg)
        self.clear_message_text()
        self.stop_indeterminate_progress()
        self.gui.latest_appimage_button.state([state])

    def update_run_winetricks_button(self, evt=None):
        if utils.file_exists(config.WINETRICKSBIN):
            state = '!disabled'
        else:
            state = 'disabled'
        self.gui.run_winetricks_button.state([state])

    def reverse_logging_state_value(self, state):
        if state == 'DISABLED':
            return 'ENABLED'
        else:
            return 'DISABLED'

    def clear_message_text(self, evt=None):
        self.gui.messagevar.set('')

    def update_progress(self, evt=None):
        progress = self.progress_q.get()
        if not type(progress) is int:
            return
        if progress >= 100:
            self.gui.progressvar.set(0)
            # self.gui.progress.state(['disabled'])
        else:
            self.gui.progressvar.set(progress)

    def update_message_text(self, evt=None):
        self.gui.messagevar.set(self.message_q.get())

    def start_indeterminate_progress(self, evt=None):
        self.gui.progress.state(['!disabled'])
        self.gui.progress.config(mode='indeterminate')
        self.gui.progress.start()

    def stop_indeterminate_progress(self, evt=None):
        self.gui.progress.stop()
        self.gui.progress.state(['disabled'])
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)


def control_panel_app():
    utils.set_debug()
    classname = "LogosLinuxControlPanel"
    root = Root(className=classname)
    ControlWindow(root, class_=classname)
    root.mainloop()
