
# References:
#   - https://tkdocs.com/
#   - https://github.com/thw26/LogosLinuxInstaller/blob/master/LogosLinuxInstaller.sh

import logging
import os
import sys
import threading
from pathlib import Path
from queue import Queue
from threading import Thread

from tkinter import Tk
from tkinter.filedialog import askdirectory
from tkinter.filedialog import askopenfilename
from tkinter.ttk import Style

import config
from control import open_config_file
from control import remove_all_index_files
from gui import ControlGui
from gui import InstallerGui
from installer import checkExistingInstall
from installer import finish_install
from installer import logos_setup
from msg import cli_msg
from utils import checkDependencies
from utils import verify_downloaded_file
from utils import getLogosReleases
from utils import getWineBinOptions
from utils import net_get
from wine import createWineBinaryList
from wine import get_app_logging_state
from wine import run_logos
from wine import switch_logging


class App(Tk):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.classname = kwargs.get('classname')
        # Set the theme.
        self.style = Style()
        self.style.theme_use('alt')
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

class InstallerWindow(InstallerGui):
    def __init__(self, root, **kwargs):
        super().__init__(**kwargs)

        # Set root parameters.
        self.root = root
        self.root.title("Faithlife Bible Software Installer")
        self.root.w = 675
        self.root.h = 300
        self.root.geometry(f"{self.root.w}x{self.root.h}")
        self.root.minsize(self.root.w, self.root.h)
        # self.root.resizable(False, False)

        # Initialize variables from ENV.
        self.wine_exe = config.WINE_EXE
        self.custombinpath = config.CUSTOMBINPATH

        # Set other variables to be used later.
        self.appimage_verified = None
        self.logos_verified = None
        self.icon_verified = None
        self.tricks_verified = None
        self.set_product()

        # Set widget callbacks and event bindings.
        self.config_filechooser.config(command=self.get_config_file)
        self.product_dropdown.bind('<<ComboboxSelected>>', self.set_product)
        self.version_dropdown.bind('<<ComboboxSelected>>', self.set_version)
        self.release_dropdown.bind('<<ComboboxSelected>>', self.set_release)
        self.release_check_button.config(command=self.on_release_check_released)
        self.bin_filechooser.config(command=self.get_bindir_name)
        self.wine_dropdown.bind('<<ComboboxSelected>>', self.set_wine)
        self.wine_check_button.config(command=self.on_wine_check_released)
        self.tricks_dropdown.bind('<<WinetricksSelected>>', self.set_winetricks)
        self.set_winetricks()
        self.fonts_checkbox.config(command=self.set_skip_fonts)
        self.cancel_button.config(command=self.on_cancel_released)
        self.okay_button.config(command=self.on_okay_released)

        # Set root widget event bindings.
        self.root.bind("<Return>", self.on_okay_released)
        self.root.bind("<Escape>", self.on_cancel_released)
        self.root.bind("<<ReleaseCheckProgress>>", self.update_release_check_progress)
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
            "<<CheckIcon>>",
        ]
        for evt in check_events:
            self.root.bind(evt, self.update_file_check_progress)
        self.root.bind("<<CheckInstallProgress>>", self.update_install_progress)
        self.root.bind("<<VerifyDownloads>>", self.start_verify_downloads_thread)
        self.root.bind("<<StartInstall>>", self.start_install_thread)
        self.install_q = Queue()
        self.root.bind("<<UpdateInstallText>>", self.update_install_text)

    def set_product(self, evt=None):
        self.flproduct = self.productvar.get()
        if self.flproduct.startswith('Logos'):
            config.FLPRODUCT = 'Logos'
            config.FLPRODUCTi = 'logos4' # icon
            config.VERBUM_PATH = '/'
        elif self.flproduct.startswith('Verbum'):
            config.FLPRODUCT = 'Verbum'
            config.FLPRODUCTi = 'verbum' # icon
            config.VERBUM_PATH = '/Verbum/'
        self.product_dropdown.selection_clear()
        self.verify_buttons()

    def set_version(self, evt=None):
        self.targetversion = self.versionvar.get()
        config.TARGETVERSION = self.targetversion
        self.version_dropdown.selection_clear()
        self.verify_buttons()

    def set_release(self, evt=None):
        self.logos_release_version = self.releasevar.get()
        self.release_dropdown.selection_clear()
        self.verify_buttons()

    def set_wine(self, evt=None):
        self.wine_exe = self.winevar.get()
        self.wine_dropdown.selection_clear()
        if config.WINEPREFIX is None:
            config.WINEPREFIX = os.path.join(config.APPDIR, "wine64_bottle")
        self.verify_buttons()

    def set_winetricks(self, evt=None):
        self.winetricksbin = self.tricksvar.get()
        self.tricks_dropdown.selection_clear()
        if config.WINETRICKSBIN is None:
            config.WINETRICKSBIN = '/usr/bin/winetricks' # FIXME: find dynamically

    def verify_buttons(self):
        funcs = [
            self.verify_release_check_button,
            self.verify_wine_check_button,
            self.verify_okay_button,
        ]
        for f in funcs:
            f()

    def verify_release_check_button(self):
        variables = [
            self.flproduct,
            self.targetversion,
        ]
        if all(variables):
            self.release_check_button.state(['!disabled'])
            # self.messagevar.set("Download list of Releases and pick one")

    def verify_wine_check_button(self):
        variables = [
            self.flproduct,
            self.targetversion,
            self.logos_release_version,
        ]
        if all(variables):
            self.wine_check_button.state(['!disabled'])
            # self.messagevar.set("Search for a Wine binary")

    def verify_okay_button(self):
        variables = [
            self.flproduct,
            self.targetversion,
            self.logos_release_version,
            self.wine_exe,
        ]
        if all(variables):
            self.okay_button.state(['!disabled'])
            # self.messagevar.set("Click Install")

    def on_release_check_released(self, evt=None):
        self.progress.config(mode='indeterminate')
        self.release_q = Queue()
        self.release_thread = Thread(
            target=getLogosReleases,
            kwargs={'q': self.release_q, 'app': self},
            daemon=True,
        )
        self.release_thread.start()
        self.progress.start()
        self.statusvar.set("Downloading Release list...")

    def on_wine_check_released(self, evt=None):
        config.LOGOS_RELEASE_VERSION = self.release_version = self.releasevar.get()
        logos_setup()
        self.wine_dropdown['values'] = getWineBinOptions(createWineBinaryList())
        self.winevar.set(self.wine_dropdown['values'][0])
        self.set_wine()

    def get_config_file(self):
        filename =  askopenfilename(
            initialdir='~',
            title="Choose custom Config file...",
        )
        self.config_file = filename if len(filename) > 0 else 'Default'
        self.config_filechooser['text'] = self.config_file if self.config_file is not None else "Choose file..."

    def get_bindir_name(self):
        dirname = askdirectory(
            initialdir='~',
            title="Select Wine binary folder...",
        )
        self.custombinpath = dirname if len(dirname) > 0 else None
        config.CUSTOMBINPATH = self.custombinpath
        self.bin_filechooser['text'] = self.custombinpath if self.custombinpath is not None else "Choose folder..."
        self.bin_filechooser.configure(width=f"{len(dirname)}d")

    def set_skip_fonts(self, evt=None):
        self.skip_fonts = 1 - self.fontsvar.get() # invert True/False

    def set_downloads(self):
        dl_dir = Path(config.MYDOWNLOADS)
        appimage_download = Path(dl_dir / Path(config.WINE64_APPIMAGE_FULL_URL).name)
        logos_download = Path(dl_dir / f"{self.flproduct}_v{self.logos_release_version}-x64.msi")
        icon_download = Path(dl_dir / config.LOGOS_ICON_FILENAME)
        self.downloads = [
            ['appimage', config.WINE64_APPIMAGE_FULL_URL, appimage_download,
                self.appimage_verified, '<<GetAppImage>>', '<<CheckAppImage>>',
            ],
            ['logos', config.LOGOS64_URL, logos_download,
                self.logos_verified, '<<GetLogos>>', '<<CheckLogos>>',
            ],
            ['icon', config.LOGOS_ICON_URL, icon_download,
                self.icon_verified, '<<GetIcon>>', '<<CheckIcon>>',
            ]
        ]
        if self.winetricksbin.startswith('Download'):
            tricks_url = config.WINETRICKS_URL
            tricks_download = config.WINETRICKSBIN
            self.downloads.append(
                'winetricks', tricks_url, tricks_download,
                    self.tricks_verified, '<<GetWinetricks>>', '<<CheckWinetricks>>'
            )
        self.downloads_orig = self.downloads.copy()

    def on_okay_released(self, evt=None):
        # Set required config.
        config.FLPRODUCT = self.flproduct
        config.FLPRODUCTi = config.FLPRODUCT.lower()
        if config.FLPRODUCTi.startswith('logos'):
            config.FLPRODUCTi += '4'
        config.TARGETVERSION = self.targetversion
        config.LOGOS_RELEASE_VERSION = self.logos_release_version
        config.CONFIG_FILE
        if self.config_file is not None and self.config_file != 'Default':
            config.CONFIG_FILE = self.config_file
        if config.WINEPREFIX is None:
            config.WINEPREFIX = os.path.join(config.APPDIR, "wine64_bottle")
        if self.custombinpath is not None:
            config.CUSTOMBINPATH = self.custombinpath
        config.WINE_EXE = self.wine_exe
        if config.WINEBIN_CODE is None:
            config.WINEBIN_CODE = 'AppImage' # FIXME: This should depend on the wine_exe path
        if self.winetricksbin.startswith('System') and self.sys_winetricks is not None:
            config.WINETRICKSBIN = self.sys_winetricks[0]
        elif self.winetricksbin.startswith('Download'):
            config.WINETRICKSBIN = os.path.join(config.APPDIR_BINDIR, "winetricks")
        config.SKIP_FONTS = self.skip_fonts if self.skip_fonts == 1 else 0
        if config.LOGOS_ICON_URL is None:
            config.LOGOS_ICON_URL = f"https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/img/{config.FLPRODUCTi}-128-icon.png"
        if config.LOGOS_ICON_FILENAME is None:
            config.LOGOS_ICON_FILENAME = os.path.basename(config.LOGOS_ICON_URL)

        self.okay_button.state(['disabled'])
        # self.messagevar.set('')
        if checkExistingInstall():
            self.root.destroy()
            return 1
        self.set_downloads()
        self.root.event_generate("<<VerifyDownloads>>")

    def on_cancel_released(self, evt=None):
        self.root.destroy()
        return 1

    def start_verify_downloads_thread(self, evt=None):
        th = threading.Thread(target=self.verify_downloads, daemon=True)
        th.start()

    def start_download_thread(self, name, url, dest, evt):
        m = f"Downloading {url}"
        cli_msg(m)
        logging.info(m)
        self.statusvar.set(m)
        self.progressvar.set(0)
        self.progress.config(mode='determinate')
        a = (url, dest)
        k = {'app': self, 'evt': evt}
        th = Thread(target=net_get, name=f"get-{name}", args=a, kwargs=k, daemon=True)
        th.start()

    def start_check_thread(self, name, url, dest, evt):
        m = f"Verifying file {dest}..."
        cli_msg(m)
        logging.info(m)
        self.statusvar.set(m)
        self.progressvar.set(0)
        self.progress.config(mode='indeterminate')
        self.progress.start()
        a = (url, dest)
        k = {'app': self, 'evt': evt}
        th = Thread(target=verify_downloaded_file, name=f"check-{name}", args=a, kwargs=k, daemon=True)
        th.start()

    def start_install_thread(self, evt=None):
        m = "Installing..."
        cli_msg(m)
        self.statusvar.set(m)
        self.progress.config(mode='indeterminate')
        self.progress.start()
        th = threading.Thread(target=finish_install, kwargs={'app': self}, daemon=True)
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

            # self.after(100)
            if not dest.is_file() and dl_thread is None: # no file; no thread started
                logging.info("Starting download thread.")
                self.start_download_thread(name, url, dest, dl_evt)
                continue
            elif dl_thread is not None: # download thread started
                continue
            elif dest.is_file() and test is None and ch_thread is None: # file downloaded; no check started
                logging.info("Starting file-check thread.")
                self.start_check_thread(name, url, dest, ch_evt)
                continue
            elif dest.is_file() and test is None and ch_thread is not None: # file downloaded; still checking
                continue
            elif dest.is_file() and test is False and dl_thread is None: # file check failed; restart download
                if name == 'appimage':
                    self.appimage_verified = None
                elif name == 'logos':
                    self.logos_verified = None
                elif name == 'icon':
                    self.icon_verified = None
                logging.info("Starting download thread.")
                self.start_download_thread(name, url, dest, dl_evt)
                continue
            elif test is True and None not in [ch_thread, dl_thread]:
                continue # some thread still going
            elif test is True and ch_thread is None and dl_thread is None:
                # file is downloaded and verified
                logging.info(f"Removing item from download list: {self.downloads[0]}.")
                self.downloads.pop(0)
                continue

        ready = 0
        for d in self.downloads_orig:
            if d[3] is True:
                ready += 1
        if ready == len(self.downloads_orig):
            self.root.event_generate('<<StartInstall>>')

    def update_release_check_progress(self, evt=None):
        self.progress.stop()
        self.statusvar.set('')
        self.progress.config(mode='determinate')
        self.progressvar.set(0)
        r = self.release_q.get()
        if r is not None:
            self.release_dropdown['values'] = r
            self.releasevar.set(self.release_dropdown['values'][0])
            self.set_release()
        else:
            self.statusvar.set("Failed to get release list. Check connection and try again.")


    def update_file_check_progress(self, evt=None):
        e, r = self.check_q.get()
        if e == "<<CheckAppImage>>":
            self.appimage_verified = r
        elif e == "<<CheckLogos>>":
            self.logos_verified = r
        elif e == "<<CheckIcon>>":
            self.icon_verified = r
        elif e == "<<CheckWinetricks>>":
            self.tricks_verified = r
        self.downloads[0][3] = r # "current" download should always be 1st item in self.downloads
        self.progress.stop()
        self.statusvar.set('')
        self.progress.config(mode='determinate')
        self.progressvar.set(0)

    def update_download_progress(self, evt=None):
        d = self.get_q.get()
        self.progressvar.set(int(d))

    def update_install_text(self, evt=None):
        text = ''
        if evt is not None:
            text = self.install_q.get()
        self.statusvar.set(text)

    def update_install_progress(self, evt=None):
        self.progress.stop()
        self.progress.config(mode='determinate')
        self.progressvar.set(0)
        self.statusvar.set('')
        self.okay_button.config(
            text="Exit",
            command=self.on_cancel_released,    
        )
        self.okay_button.state(['!disabled'])
        self.root.destroy()
        return 0

class ControlWindow(ControlGui):
    def __init__(self, root, **kwargs):
        super().__init__(**kwargs)

        # Set root parameters.
        self.root = root
        self.root.title("Faithlife Bible Software Control Panel")
        self.root.w = 450
        self.root.h = 300
        self.root.geometry(f"{self.root.w}x{self.root.h}")
        self.root.minsize(self.root.w, self.root.h)
        # self.root.resizable(False, False)

        self.installdir_filechooser.config(text=self.installdir, command=self.get_installdir)
        self.run_button.config(command=self.run_logos)
        self.check_button.config(command=self.check_resources)
        self.check_button.state(['disabled']) # FIXME: needs function
        self.indexes_button.config(command=self.remove_indexes)
        self.loggingstatevar.set('Enable')
        self.logging_button.config(text=self.loggingstatevar.get(), command=self.switch_logging)
        self.logging_button.state(['disabled'])
        self.logging_init_event = '<<InitLoggingButton>>'
        self.logging_event = '<<UpdateLoggingButton>>'
        self.logging_q = Queue()
        
        self.config_button.config(command=self.open_config)
        self.deps_button.config(command=self.reinstall_deps)
        self.deps_button.state(['disabled']) # FIXME: needs function
        self.message_event = '<<ClearMessage>>'

        self.root.bind(self.logging_event, self.update_logging_button)
        self.root.bind(self.logging_init_event, self.initialize_logging_button)
        self.root.bind(self.message_event, self.clear_message)

        # Start function to determine app logging state.
        t = Thread(target=get_app_logging_state, kwargs={'app': self, 'init': True})
        t.start()
        self.messagevar.set('Getting current app logging status...')
        self.progress.state(['!disabled'])
        self.progress.start()

    def check_resources(self, evt=None):
        # FIXME: needs function
        pass

    def get_installdir(self, evt=None):
        dirname = askdirectory(
            initialdir='~',
            title="Choose installation directory..."
        )
        if len(dirname) > 0:
            self.installdir = dirname
        self.installdir_filechooser.config(text=self.installdir)

    def reinstall_deps(self, evt=None):
        checkDependencies()

    def remove_indexes(self, evt=None):
        self.messagevar.set("Removing indexes...")
        t = Thread(target=remove_all_index_files, kwargs={'app': self})
        t.start()

    def run_logos(self, evt=None):
        t = Thread(target=run_logos)
        t.start()

    def open_config(self, evt=None):
        open_config_file()

    def switch_logging(self, evt=None):
        prev_state = self.loggingstatevar.get()
        new_state = 'Enable' if prev_state == 'Disable' else 'Disable'
        kwargs = {
            'action': new_state.lower(),
            'app': self,
        }
        self.messagevar.set(f"Switching app logging to '{prev_state}d'...")
        self.progress.state(['!disabled'])
        self.progress.start()
        self.logging_button.state(['disabled'])
        t = Thread(target=switch_logging, kwargs=kwargs)
        t.start()

    def initialize_logging_button(self, evt=None):
        self.messagevar.set('')
        self.progress.stop()
        self.progress.state(['disabled'])
        state = self.reverse_logging_state_value(self.logging_q.get())
        self.loggingstatevar.set(state[:-1].title())
        self.logging_button.state(['!disabled'])

    def update_logging_button(self, evt=None):
        self.messagevar.set('')
        self.progress.stop()
        self.progress.state(['disabled'])
        state = self.logging_q.get()
        self.loggingstatevar.set(state[:-1].title())
        self.logging_button.state(['!disabled'])

    def clear_message(self, evt=None):
        self.messagevar.set('')

    def reverse_logging_state_value(self, state):
        if state == 'DISABLED':
            return 'ENABLED'
        else:
            return 'DISABLED'
