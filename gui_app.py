
# References:
#   - https://tkdocs.com/
#   - https://github.com/thw26/LogosLinuxInstaller/blob/master/LogosLinuxInstaller.sh

import logging
import os
import threading
from pathlib import Path
from queue import Queue
from threading import Thread

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
        bg_widgets = ['TCheckbutton', 'TCombobox', 'TFrame', 'TLabel', 'TRadiobutton']
        fg_widgets = ['TButton', 'TSeparator']
        for w in bg_widgets:
            self.style.configure(w, background=config.LOGOS_WHITE)
        for w in fg_widgets:
            self.style.configure(w, background=config.LOGOS_GRAY)
        self.style.configure(
            'Horizontal.TProgressbar', thickness=10, background=config.LOGOS_BLUE,
            bordercolor=config.LOGOS_GRAY, troughcolor=config.LOGOS_GRAY
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

class InstallerWindow():
    def __init__(self, root, **kwargs):
        # super().__init__(**kwargs)

        # Set root parameters.
        self.root = root
        self.root.title("Faithlife Bible Software Installer")
        # self.root.w = 675
        # self.root.h = 200
        # self.root.geometry(f"{self.root.w}x{self.root.h}")
        # self.root.minsize(self.root.w, self.root.h)
        self.root.resizable(False, False)
        self.gui = gui.InstallerGui(self.root)

        # Initialize variables from ENV.
        self.wine_exe = config.WINE_EXE

        # Set other variables to be used later.
        self.appimage_verified = None
        self.logos_verified = None
        self.icon_verified = None
        self.tricks_verified = None
        self.set_product()

        # Set widget callbacks and event bindings.
        self.gui.product_dropdown.bind('<<ComboboxSelected>>', self.set_product)
        self.gui.version_dropdown.bind('<<ComboboxSelected>>', self.set_version)
        self.gui.release_dropdown.bind('<<ComboboxSelected>>', self.set_release)
        self.gui.release_check_button.config(command=self.on_release_check_released)
        self.gui.wine_dropdown.bind('<<ComboboxSelected>>', self.set_wine)
        self.gui.wine_check_button.config(command=self.on_wine_check_released)
        self.gui.tricks_dropdown.bind('<<WinetricksSelected>>', self.set_winetricks)
        self.set_winetricks()
        self.gui.fonts_checkbox.config(command=self.set_skip_fonts)
        self.gui.skipdeps_checkbox.config(command=self.set_skip_dependencies)
        self.gui.cancel_button.config(command=self.on_cancel_released)
        self.gui.okay_button.config(command=self.on_okay_released)

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
        self.flproduct = self.gui.productvar.get()
        if self.flproduct.startswith('Logos'):
            config.FLPRODUCT = 'Logos'
            config.FLPRODUCTi = 'logos4' # icon
            config.VERBUM_PATH = '/'
        elif self.flproduct.startswith('Verbum'):
            config.FLPRODUCT = 'Verbum'
            config.FLPRODUCTi = 'verbum' # icon
            config.VERBUM_PATH = '/Verbum/'
        self.gui.product_dropdown.selection_clear()
        self.verify_buttons()

    def set_version(self, evt=None):
        self.gui.targetversion = self.gui.versionvar.get()
        config.TARGETVERSION = self.gui.targetversion
        self.gui.version_dropdown.selection_clear()
        self.verify_buttons()

    def set_release(self, evt=None):
        self.gui.logos_release_version = self.gui.releasevar.get()
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
            self.gui.targetversion,
        ]
        if all(variables):
            self.gui.release_check_button.state(['!disabled'])
            # self.messagevar.set("Download list of Releases and pick one")

    def verify_wine_check_button(self):
        variables = [
            self.flproduct,
            self.gui.targetversion,
            self.gui.logos_release_version,
        ]
        if all(variables):
            self.gui.wine_check_button.state(['!disabled'])
            # self.messagevar.set("Search for a Wine binary")

    def verify_okay_button(self):
        variables = [
            self.flproduct,
            self.gui.targetversion,
            self.gui.logos_release_version,
            self.wine_exe,
        ]
        if all(variables):
            self.gui.okay_button.state(['!disabled'])
            # self.messagevar.set("Click Install")

    def on_release_check_released(self, evt=None):
        self.gui.progress.config(mode='indeterminate')
        self.release_q = Queue()
        self.release_thread = Thread(
            target=utils.get_logos_releases,
            kwargs={'q': self.release_q, 'app': self},
            daemon=True,
        )
        self.release_thread.start()
        self.gui.progress.start()
        self.gui.statusvar.set("Downloading Release list...")

    def on_wine_check_released(self, evt=None):
        config.LOGOS_RELEASE_VERSION = self.release_version = self.gui.releasevar.get()
        installer.logos_setup()
        self.gui.wine_dropdown['values'] = utils.get_wine_options(utils.find_appimage_files(), utils.find_wine_binary_files())
        self.gui.winevar.set(self.gui.wine_dropdown['values'][0])
        self.set_wine()

    def set_skip_fonts(self, evt=None):
        self.gui.skip_fonts = 1 - self.gui.fontsvar.get() # invert True/False

    def set_skip_dependencies(self, evt=None):
        self.gui.skip_dependencies = 1 - self.gui.skipdepsvar.get() # invert True/False

    def set_downloads(self):
        dl_dir = Path(config.MYDOWNLOADS)
        appimage_download = Path(dl_dir / Path(config.RECOMMENDED_WINE64_APPIMAGE_FULL_URL).name)
        logos_download = Path(dl_dir / f"{self.flproduct}_v{self.gui.logos_release_version}-x64.msi")
        icon_download = Path(dl_dir / config.LOGOS_ICON_FILENAME)
        self.downloads = [
            ['appimage', config.RECOMMENDED_WINE64_APPIMAGE_FULL_URL, appimage_download,
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
        config.TARGETVERSION = self.gui.targetversion
        config.LOGOS_RELEASE_VERSION = self.gui.logos_release_version
        if config.WINEPREFIX is None:
            config.WINEPREFIX = os.path.join(config.APPDIR, "wine64_bottle")
        config.WINE_EXE = self.wine_exe
        if config.WINEBIN_CODE is None:
            config.WINEBIN_CODE = utils.get_winebin_code_and_desc(config.WINE_EXE)[0]
        if self.winetricksbin.startswith('System') and self.gui.sys_winetricks is not None:
            config.WINETRICKSBIN = self.gui.sys_winetricks[0]
        elif self.winetricksbin.startswith('Download'):
            config.WINETRICKSBIN = os.path.join(config.APPDIR_BINDIR, "winetricks")
        config.SKIP_FONTS = self.gui.skip_fonts if self.gui.skip_fonts == 1 else 0
        config.SKIP_DEPENDENCIES = self.gui.skip_dependencies if self.gui.skip_dependencies == 1 else 0
        if config.LOGOS_ICON_URL is None:
            config.LOGOS_ICON_URL = f"https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/img/{config.FLPRODUCTi}-128-icon.png"
        if config.LOGOS_ICON_FILENAME is None:
            config.LOGOS_ICON_FILENAME = os.path.basename(config.LOGOS_ICON_URL)

        self.gui.okay_button.state(['disabled'])
        # self.messagevar.set('')
        if installer.check_existing_install():
            self.root.destroy()
            return 1
        self.set_downloads()
        self.root.event_generate("<<VerifyDownloads>>")

    def on_cancel_released(self, evt=None):
        self.root.destroy()
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
        th = Thread(target=utils.net_get, name=f"get-{name}", args=a, kwargs=k, daemon=True)
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
        th = Thread(target=utils.verify_downloaded_file, name=f"check-{name}", args=a, kwargs=k, daemon=True)
        th.start()

    def start_install_thread(self, evt=None):
        m = "Installing..."
        msg.cli_msg(m)
        self.gui.statusvar.set(m)
        self.gui.progress.config(mode='indeterminate')
        self.gui.progress.start()
        th = Thread(target=installer.finish_install, kwargs={'app': self}, daemon=True)
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
        self.gui.progress.stop()
        self.gui.statusvar.set('')
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)
        r = self.release_q.get()
        if r is not None:
            self.gui.release_dropdown['values'] = r
            self.gui.releasevar.set(self.gui.release_dropdown['values'][0])
            self.set_release()
        else:
            self.gui.statusvar.set("Failed to get release list. Check connection and try again.")

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
        # self.root.event_generate('<<InstallFinished>>') FIXME: doesn't seem to pass to control panel window
        self.root.destroy()
        return 0

class ControlWindow():
    def __init__(self, root, *args, **kwargs):
        # super().__init__(**kwargs)

        # Set root parameters.
        self.root = root
        self.root.title("Faithlife Bible Software Control Panel")
        # self.root.w = 450
        # self.root.h = 375
        # self.root.geometry(f"{self.root.w}x{self.root.h}")
        # self.root.minsize(self.root.w, self.root.h)
        self.root.resizable(False, False)
        self.gui = gui.ControlGui(self.root)

        if utils.app_is_installed():
            self.gui.app_buttonvar.set(f"Run {config.FLPRODUCT}")
            self.gui.app_button.config(command=self.run_logos)
        else:
            self.gui.app_button.config(command=self.run_installer)
        self.gui.run_indexing_radio.config(command=self.on_action_radio_clicked)
        self.gui.remove_library_catalog_radio.config(command=self.on_action_radio_clicked)
        self.gui.remove_index_files_radio.config(command=self.on_action_radio_clicked)
        self.gui.actions_button.config(command=self.gui.actioncmd)

        self.gui.loggingstatevar.set('Enable')
        self.gui.logging_button.config(text=self.gui.loggingstatevar.get(), command=self.switch_logging)
        self.gui.logging_button.state(['disabled'])
        
        self.gui.config_button.config(command=control.edit_config)
        self.gui.deps_button.config(command=self.install_deps)
        self.gui.backup_button.config(command=self.run_backup)
        self.gui.restore_button.config(command=self.run_restore)
        self.gui.appimage_button.config(command=self.set_appimage)
        if config.WINEBIN_CODE != "AppImage":
            self.gui.appimage_button.state(['disabled'])
            gui.ToolTip(self.gui.appimage_button, "This button is disabled. The configured install was not created using an AppImage.")
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
        self.root.bind('<<StartIndeterminateProgress>>', self.start_indeterminate_progress)
        self.root.bind('<<StopIndeterminateProgress>>', self.stop_indeterminate_progress)
        self.root.bind('<<UpdateProgress>>', self.update_progress)
        # FIXME: The followig event doesn't seem to be received in this window when
        #`  generated in the installer window.
        # self.root.bind('<<InstallFinished>>', self.update_app_button)
        # self.root.bind('<<CheckInstallProgress>>', self.update_app_button)

        # Start function to determine app logging state.
        t = Thread(target=wine.get_app_logging_state, kwargs={'app': self, 'init': True})
        if utils.app_is_installed():
            t.start()
            self.gui.messagevar.set('Getting current app logging status...')
            self.gui.progress.state(['!disabled'])
            self.gui.progress.start()


    def run_installer(self, evt=None):
        # self.root.control_win.destroy()
        classname = "LogosLinuxInstaller"
        self.new_win = Toplevel(self.root)
        self.app = InstallerWindow(self.new_win, class_=classname)

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
        t = Thread(target=control.remove_all_index_files, kwargs={'app': self})
        t.start()

    def run_backup(self, evt=None):
        # Get backup folder.
        if config.BACKUPDIR is None:
            config.BACKUPDIR = fd.askdirectory(
                parent=self.root,
                title=f"Choose folder for {config.FLPRODUCT} backups",
                initialdir=Path().home(),
            )
            if not config.BACKUPDIR: # user cancelled
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
            filetypes=[(filetype_name, f"*.{filetype_extension}"), ("All Files", "*.*")],
        )

        return file_path

    def set_appimage(self, evt=None):
        appimage_filename = self.open_file_dialog("AppImage", "AppImage")
        if not appimage_filename:
            return
        config.SELECTED_APPIMAGE_FILENAME = appimage_filename
        utils.set_appimage_symlink()

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
        self.gui.progress.state(['!disabled'])
        self.gui.progress.config(mode='determinate')

def control_panel_app():
    utils.set_debug()
    classname = "LogosLinuxControlPanel"
    root = Root(className=classname)
    app = ControlWindow(root, class_=classname)
    root.mainloop()
