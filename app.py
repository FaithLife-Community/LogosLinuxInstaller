
# References:
#   - https://tkdocs.com/
#   - https://github.com/thw26/LogosLinuxInstaller/blob/master/LogosLinuxInstaller.sh

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
from gui import Gui
from installer import checkExistingInstall
from installer import finish_install
from installer import logos_setup
from msg import cli_msg
from utils import same_size
from utils import getLogosReleases
from utils import getWineBinOptions
from utils import wget
from wine import createWineBinaryList


class InstallerApp(Tk):
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

        # Set root parameters.
        self.w = 675
        self.h = 300
        self.geometry(f"{self.w}x{self.h}")
        self.title("Faithlife Bible Software Installer")
        self.minsize(self.w, self.h)
        # self.resizable(False, False)

        # Make root widget's outer border expand with window.
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

class InstallerWindow(Gui):
    def __init__(self, root, **kwargs):
        super().__init__(**kwargs)

        # Initialize variables from ENV.
        self.wine_exe = config.WINE_EXE
        self.custombinpath = config.CUSTOMBINPATH

        # Set other variables to be used later.
        self.root = root
        self.appimage_same_size = None
        self.logos_same_size = None
        self.icon_same_size = None
        self.tricks_same_size = None
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
        download_events = [
            "<<WgetAppImage>>",
            "<<WgetLogos>>",
            "<<WgetWinetricks>>",
        ]
        for evt in download_events:
            self.root.bind(evt, self.update_download_progress)
        size_events = [
            "<<CheckAppImage>>",
            "<<CheckLogos>>",
            "<<CheckIcon>>",
        ]
        for evt in size_events:
            self.root.bind(evt, self.update_file_size_check_progress)
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
                self.appimage_same_size, '<<WgetAppImage>>', '<<CheckAppImage>>',
            ],
            ['logos', config.LOGOS64_URL, logos_download,
                self.logos_same_size, '<<WgetLogos>>', '<<CheckLogos>>',
            ],
            ['icon', config.LOGOS_ICON_URL, icon_download,
                self.icon_same_size, '<<WgetIcon>>', '<<CheckIcon>>',
            ]
        ]
        if self.winetricksbin.startswith('Download'):
            tricks_url = config.WINETRICKS_URL
            tricks_download = config.WINETRICKSBIN
            self.downloads.append(
                'winetricks', tricks_url, tricks_download,
                    self.tricks_same_size, '<<WgetWinetricks>>', '<<CheckWinetricks>>'
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
            config.LOGOS_ICON_URL = "https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/img/" + config.FLPRODUCTi + "-128-icon.png"
        if config.LOGOS_ICON_FILENAME is None:
            config.LOGOS_ICON_FILENAME = os.path.basename(config.LOGOS_ICON_URL)

        self.okay_button.state(['disabled'])
        # self.messagevar.set('')
        if checkExistingInstall():
            self.root.destroy()
            return 1
        self.wget_q = Queue()
        self.check_q = Queue()
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
        self.statusvar.set(m)
        self.progressvar.set(0)
        self.progress.config(mode='determinate')
        a = (url, dest)
        k = {'q': self.wget_q, 'app': self, 'evt': evt}
        th = Thread(target=wget, name=f"wget-{name}", args=a, kwargs=k, daemon=True)
        th.start()

    def start_check_thread(self, name, url, dest, evt):
        m = f"Checking size of {dest}"
        cli_msg(m)
        self.statusvar.set(m)
        self.progressvar.set(0)
        self.progress.config(mode='indeterminate')
        self.progress.start()
        a = (url, dest)
        k = {'q': self.check_q, 'app': self, 'evt': evt}
        th = Thread(target=same_size, name=f"check-{name}", args=a, kwargs=k, daemon=True)
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
                elif t.name == f"wget-{name}":
                    dl_thread = t

            # self.after(100)
            if not dest.is_file() and dl_thread is None: # no file; no thread started
                cli_msg("Starting download thread.")
                self.start_download_thread(name, url, dest, dl_evt)
                continue
            elif dl_thread is not None: # download thread started
                continue
            elif dest.is_file() and test is None and ch_thread is None: # file downloaded; no check started
                cli_msg("Starting file-check thread.")
                self.start_check_thread(name, url, dest, ch_evt)
                continue
            elif dest.is_file() and test is None and ch_thread is not None: # file downloaded; still checking
                continue
            elif dest.is_file() and test is False and dl_thread is None: # file check failed; restart download
                if name == 'appimage':
                    self.appimage_same_size = None
                elif name == 'logos':
                    self.logos_same_size = None
                elif name == 'icon':
                    self.icon_same_size = None
                cli_msg("Starting download thread.")
                self.start_download_thread(name, url, dest, dl_evt)
                continue
            elif test is True and None not in [ch_thread, dl_thread]:
                continue # some thread still going
            elif test is True and ch_thread is None and dl_thread is None:
                # file is downloaded and verified
                cli_msg("Removing item from download list.")
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


    def update_file_size_check_progress(self, evt=None):
        e, r = self.check_q.get()
        if e == "<<CheckAppImage>>":
            self.appimage_same_size = r
        elif e == "<<CheckLogos>>":
            self.logos_same_size = r
        elif e == "<<CheckIcon>>":
            self.icon_same_size = r
        elif e == "<<CheckWinetricks>>":
            self.tricks_same_size = r
        self.downloads[0][3] = r # "current" download should always be 1st item in self.downloads
        self.progress.stop()
        self.statusvar.set('')
        self.progress.config(mode='determinate')
        self.progressvar.set(0)

    def update_download_progress(self, evt=None):
        d = self.wget_q.get()
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
