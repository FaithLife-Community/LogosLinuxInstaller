
# References:
#   - https://tkdocs.com/
#   - https://github.com/thw26/LogosLinuxInstaller/blob/master/LogosLinuxInstaller.sh  # noqa: E501

import logging
from pathlib import Path
from queue import Queue

from tkinter import PhotoImage
from tkinter import Tk
from tkinter import Toplevel
from tkinter import filedialog as fd
from tkinter.ttk import Style

import config
import control
import gui
import installer
import logos
import network
import system
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
        self.config_thread = None
        self.wine_exe = None
        self.winetricksbin = None
        self.appimages = None
        # self.appimage_verified = None
        # self.logos_verified = None
        # self.tricks_verified = None

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
            '<<ComboboxSelected>>',
            self.set_winetricks
        )
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
            '<<StartIndeterminateProgress>>',
            self.start_indeterminate_progress
        )
        self.root.bind(
            "<<SetWineExe>>",
            self.update_wine_check_progress
        )
        self.get_q = Queue()
        self.get_evt = "<<GetFile>>"
        self.root.bind(self.get_evt, self.update_download_progress)
        self.check_evt = "<<CheckFile>>"
        self.root.bind(self.check_evt, self.update_file_check_progress)
        self.status_q = Queue()
        self.status_evt = "<<UpdateStatus>>"
        self.root.bind(self.status_evt, self.update_status_text)
        self.progress_q = Queue()
        self.root.bind(
            "<<UpdateProgress>>",
            self.update_progress
        )
        self.todo_q = Queue()
        self.root.bind(
            "<<ToDo>>",
            self.todo
        )
        self.product_q = Queue()
        self.version_q = Queue()
        self.releases_q = Queue()
        self.release_q = Queue()
        self.wine_q = Queue()
        self.tricksbin_q = Queue()

        # Run commands.
        self.get_winetricks_options()
        self.start_ensure_config()

    def start_ensure_config(self):
        # Ensure progress counter is reset.
        config.INSTALL_STEP = 1
        config.INSTALL_STEPS_COUNT = 0
        self.config_thread = utils.start_thread(
            installer.ensure_installation_config,
            app=self,
        )

    def get_winetricks_options(self):
        config.WINETRICKSBIN = None  # override config file b/c "Download" accounts for that  # noqa: E501
        self.gui.tricks_dropdown['values'] = utils.get_winetricks_options()
        self.gui.tricksvar.set(self.gui.tricks_dropdown['values'][0])

    def set_input_widgets_state(self, state, widgets='all'):
        if state == 'enabled':
            state = ['!disabled']
        elif state == 'disabled':
            state = ['disabled']
        all_widgets = [
            self.gui.product_dropdown,
            self.gui.version_dropdown,
            self.gui.release_dropdown,
            self.gui.release_check_button,
            self.gui.wine_dropdown,
            self.gui.wine_check_button,
            self.gui.tricks_dropdown,
            self.gui.okay_button,
        ]
        if widgets == 'all':
            widgets = all_widgets
        for w in widgets:
            w.state(state)

    def todo(self, evt=None, task=None):
        logging.debug(f"GUI todo: {task=}")
        widgets = []
        if not task:
            if not self.todo_q.empty():
                task = self.todo_q.get()
            else:
                return
        self.set_input_widgets_state('enabled')
        if task == 'FLPRODUCT':
            # Disable all input widgets after Version.
            widgets = [
                self.gui.version_dropdown,
                self.gui.release_dropdown,
                self.gui.release_check_button,
                self.gui.wine_dropdown,
                self.gui.wine_check_button,
                self.gui.okay_button,
            ]
            self.set_input_widgets_state('disabled', widgets=widgets)
            if not self.gui.productvar.get():
                self.gui.productvar.set(self.gui.product_dropdown['values'][0])
            self.set_product()
        elif task == 'TARGETVERSION':
            # Disable all input widgets after Version.
            widgets = [
                self.gui.release_dropdown,
                self.gui.release_check_button,
                self.gui.wine_dropdown,
                self.gui.wine_check_button,
                self.gui.okay_button,
            ]
            self.set_input_widgets_state('disabled', widgets=widgets)
            if not self.gui.versionvar.get():
                self.gui.versionvar.set(self.gui.version_dropdown['values'][1])
            self.set_version()
        elif task == 'TARGET_RELEASE_VERSION':
            # Disable all input widgets after Release.
            widgets = [
                self.gui.wine_dropdown,
                self.gui.wine_check_button,
                self.gui.okay_button,
            ]
            self.set_input_widgets_state('disabled', widgets=widgets)
            self.start_releases_check()
        elif task == 'WINE_EXE':
            # Disable all input widgets after Wine Exe.
            widgets = [
                self.gui.okay_button,
            ]
            self.set_input_widgets_state('disabled', widgets=widgets)
            self.start_wine_versions_check(config.TARGET_RELEASE_VERSION)
        elif task == 'WINETRICKSBIN':
            # Disable all input widgets after Winetricks.
            widgets = [
                self.gui.okay_button,
            ]
            self.set_input_widgets_state('disabled', widgets=widgets)
            self.set_winetricks()
        elif task == 'INSTALL':
            self.gui.statusvar.set('Ready to install!')
            self.gui.progressvar.set(0)
        elif task == 'INSTALLING':
            self.set_input_widgets_state('disabled')
        elif task == 'DONE':
            self.update_install_progress()
        elif task == 'CONFIG':
            logging.info("Updating config file.")
            utils.write_config(config.CONFIG_FILE)

    def set_product(self, evt=None):
        if self.gui.productvar.get().startswith('C'):  # ignore default text
            return
        self.gui.flproduct = self.gui.productvar.get()
        self.gui.product_dropdown.selection_clear()
        if evt:  # manual override; reset dependent variables
            logging.debug(f"User changed FLPRODUCT to '{self.gui.flproduct}'")
            config.FLPRODUCT = None
            config.FLPRODUCTi = None
            config.VERBUM_PATH = None

            config.TARGETVERSION = None
            self.gui.versionvar.set('')

            config.TARGET_RELEASE_VERSION = None
            self.gui.releasevar.set('')

            config.INSTALLDIR = None
            config.APPDIR_BINDIR = None

            config.WINE_EXE = None
            self.gui.winevar.set('')
            config.SELECTED_APPIMAGE_FILENAME = None
            config.WINEBIN_CODE = None

            self.start_ensure_config()
        else:
            self.product_q.put(self.gui.flproduct)

    def set_version(self, evt=None):
        self.gui.targetversion = self.gui.versionvar.get()
        self.gui.version_dropdown.selection_clear()
        if evt:  # manual override; reset dependent variables
            logging.debug(f"User changed TARGETVERSION to '{self.gui.targetversion}'")  # noqa: E501
            config.TARGETVERSION = None
            self.gui.releasevar.set('')
            config.TARGET_RELEASE_VERSION = None
            self.gui.releasevar.set('')

            config.INSTALLDIR = None
            config.APPDIR_BINDIR = None

            config.WINE_EXE = None
            self.gui.winevar.set('')
            config.SELECTED_APPIMAGE_FILENAME = None
            config.WINEBIN_CODE = None

            self.start_ensure_config()
        else:
            self.version_q.put(self.gui.targetversion)

    def start_releases_check(self):
        # Disable button; clear list.
        self.gui.release_check_button.state(['disabled'])
        # self.gui.releasevar.set('')
        self.gui.release_dropdown['values'] = []
        # Setup queue, signal, thread.
        self.release_evt = "<<ReleaseCheckProgress>>"
        self.root.bind(
            self.release_evt,
            self.update_release_check_progress
        )
        # Start progress.
        self.gui.progress.config(mode='indeterminate')
        self.gui.progress.start()
        self.gui.statusvar.set("Downloading Release list…")
        # Start thread.
        utils.start_thread(network.get_logos_releases, app=self)

    def set_release(self, evt=None):
        if self.gui.releasevar.get()[0] == 'C':  # ignore default text
            return
        self.gui.logos_release_version = self.gui.releasevar.get()
        self.gui.release_dropdown.selection_clear()
        if evt:  # manual override
            config.TARGET_RELEASE_VERSION = self.gui.logos_release_version
            logging.debug(f"User changed TARGET_RELEASE_VERSION to '{self.gui.logos_release_version}'")  # noqa: E501

            config.INSTALLDIR = None
            config.APPDIR_BINDIR = None

            config.WINE_EXE = None
            self.gui.winevar.set('')
            config.SELECTED_APPIMAGE_FILENAME = None
            config.WINEBIN_CODE = None

            self.start_ensure_config()
        else:
            self.release_q.put(self.gui.logos_release_version)

    def start_find_appimage_files(self, release_version):
        # Setup queue, signal, thread.
        self.appimage_q = Queue()
        self.appimage_evt = "<<FindAppImageProgress>>"
        self.root.bind(
            self.appimage_evt,
            self.update_find_appimage_progress
        )
        # Start progress.
        self.gui.progress.config(mode='indeterminate')
        self.gui.progress.start()
        self.gui.statusvar.set("Finding available wine AppImages…")
        # Start thread.
        utils.start_thread(
            utils.find_appimage_files,
            release_version=release_version,
            app=self,
        )

    def start_wine_versions_check(self, release_version):
        if self.appimages is None:
            self.appimages = []
            # self.start_find_appimage_files(release_version)
            # return
        # Setup queue, signal, thread.
        self.wines_q = Queue()
        self.wine_evt = "<<WineCheckProgress>>"
        self.root.bind(
            self.wine_evt,
            self.update_wine_check_progress
        )
        # Start progress.
        self.gui.progress.config(mode='indeterminate')
        self.gui.progress.start()
        self.gui.statusvar.set("Finding available wine binaries…")
        # Start thread.
        utils.start_thread(
            utils.get_wine_options,
            self.appimages,
            utils.find_wine_binary_files(release_version),
            app=self,
        )

    def set_wine(self, evt=None):
        self.gui.wine_exe = self.gui.winevar.get()
        self.gui.wine_dropdown.selection_clear()
        if evt:  # manual override
            logging.debug(f"User changed WINE_EXE to '{self.gui.wine_exe}'")
            config.WINE_EXE = None
            config.SELECTED_APPIMAGE_FILENAME = None
            config.WINEBIN_CODE = None

            self.start_ensure_config()
        else:
            self.wine_q.put(
                utils.get_relative_path(
                    utils.get_config_var(self.gui.wine_exe),
                    config.INSTALLDIR
                )
            )

    def set_winetricks(self, evt=None):
        self.gui.winetricksbin = self.gui.tricksvar.get()
        self.gui.tricks_dropdown.selection_clear()
        if evt:  # manual override
            config.WINETRICKSBIN = None
            self.start_ensure_config()
        else:
            self.tricksbin_q.put(self.gui.winetricksbin)

    def on_release_check_released(self, evt=None):
        self.start_releases_check()

    def on_wine_check_released(self, evt=None):
        self.gui.wine_check_button.state(['disabled'])
        self.start_wine_versions_check(config.TARGET_RELEASE_VERSION)

    def set_skip_fonts(self, evt=None):
        self.gui.skip_fonts = 1 - self.gui.fontsvar.get()  # invert True/False
        config.SKIP_FONTS = self.gui.skip_fonts
        logging.debug(f"> {config.SKIP_FONTS=}")

    def set_skip_dependencies(self, evt=None):
        self.gui.skip_dependencies = 1 - self.gui.skipdepsvar.get()  # invert True/False  # noqa: E501
        config.SKIP_DEPENDENCIES = self.gui.skip_dependencies
        logging.debug(f"> {config.SKIP_DEPENDENCIES=}")

    def on_okay_released(self, evt=None):
        # Update desktop panel icon.
        self.root.icon = config.LOGOS_ICON_URL
        self.start_install_thread()

    def on_cancel_released(self, evt=None):
        self.win.destroy()
        return 1

    def start_install_thread(self, evt=None):
        self.gui.progress.config(mode='determinate')
        utils.start_thread(installer.ensure_launcher_shortcuts, app=self)

    def start_indeterminate_progress(self, evt=None):
        self.gui.progress.state(['!disabled'])
        self.gui.progressvar.set(0)
        self.gui.progress.config(mode='indeterminate')
        self.gui.progress.start()

    def stop_indeterminate_progress(self, evt=None):
        self.gui.progress.stop()
        self.gui.progress.state(['disabled'])
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)
        self.gui.statusvar.set('')

    def update_release_check_progress(self, evt=None):
        self.stop_indeterminate_progress()
        self.gui.release_check_button.state(['!disabled'])
        if not self.releases_q.empty():
            self.gui.release_dropdown['values'] = self.releases_q.get()
            self.gui.releasevar.set(self.gui.release_dropdown['values'][0])
            self.set_release()
        else:
            self.gui.statusvar.set("Failed to get release list. Check connection and try again.")  # noqa: E501

    def update_find_appimage_progress(self, evt=None):
        self.stop_indeterminate_progress()
        if not self.appimage_q.empty():
            self.appimages = self.appimage_q.get()
            self.start_wine_versions_check(config.TARGET_RELEASE_VERSION)

    def update_wine_check_progress(self, evt=None):
        if evt and self.wines_q.empty():
            return
        self.gui.wine_dropdown['values'] = self.wines_q.get()
        if not self.gui.winevar.get():
            # If no value selected, default to 1st item in list.
            self.gui.winevar.set(self.gui.wine_dropdown['values'][0])
        self.set_wine()
        self.stop_indeterminate_progress()
        self.gui.wine_check_button.state(['!disabled'])

    def update_file_check_progress(self, evt=None):
        self.gui.progress.stop()
        self.gui.statusvar.set('')
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)

    def update_download_progress(self, evt=None):
        d = self.get_q.get()
        self.gui.progressvar.set(int(d))

    def update_progress(self, evt=None):
        progress = self.progress_q.get()
        if not type(progress) is int:
            return
        if progress >= 100:
            self.gui.progressvar.set(0)
            # self.gui.progress.state(['disabled'])
        else:
            self.gui.progressvar.set(progress)

    def update_status_text(self, evt=None, status=None):
        text = ''
        if evt:
            text = self.status_q.get()
        elif status:
            text = status
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
        self.actioncmd = None
        self.logos = logos.LogosManager(app=self)

        text = self.gui.update_lli_label.cget('text')
        ver = config.LLI_CURRENT_VERSION
        new = config.LLI_LATEST_VERSION
        text = f"{text}\ncurrent: v{ver}\nlatest: v{new}"
        self.gui.update_lli_label.config(text=text)
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
        self.gui.install_icu_radio.config(
            command=self.on_action_radio_clicked
        )
        self.gui.actions_button.config(command=self.run_action_cmd)

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
        self.logging_event = '<<UpdateLoggingButton>>'
        self.root.bind(self.logging_event, self.update_logging_button)
        self.status_q = Queue()
        self.status_evt = '<<UpdateControlStatus>>'
        self.root.bind(self.status_evt, self.update_status_text)
        self.root.bind('<<ClearStatus>>', self.clear_status_text)
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
        self.get_q = Queue()
        self.get_evt = "<<GetFile>>"
        self.root.bind(self.get_evt, self.update_download_progress)
        self.check_evt = "<<CheckFile>>"
        self.root.bind(self.check_evt, self.update_file_check_progress)

        # Start function to determine app logging state.
        if utils.app_is_installed():
            self.gui.statusvar.set('Getting current app logging status…')
            self.start_indeterminate_progress()
            utils.start_thread(self.logos.get_app_logging_state)

    def configure_app_button(self, evt=None):
        if utils.app_is_installed():
            # wine.set_logos_paths()
            self.gui.app_buttonvar.set(f"Run {config.FLPRODUCT}")
            self.gui.app_button.config(command=self.run_logos)
            self.gui.get_winetricks_button.state(['!disabled'])
        else:
            self.gui.app_button.config(command=self.run_installer)

    def run_installer(self, evt=None):
        classname = "LogosLinuxInstaller"
        self.installer_win = Toplevel()
        InstallerWindow(self.installer_win, self.root, class_=classname)
        self.root.icon = config.LOGOS_ICON_URL

    def run_logos(self, evt=None):
        utils.start_thread(self.logos.start)

    def run_action_cmd(self, evt=None):
        self.actioncmd()

    def on_action_radio_clicked(self, evt=None):
        logging.debug("gui_app.ControlPanel.on_action_radio_clicked START")
        if utils.app_is_installed():
            self.gui.actions_button.state(['!disabled'])
            if self.gui.actionsvar.get() == 'run-indexing':
                self.actioncmd = self.run_indexing
            elif self.gui.actionsvar.get() == 'remove-library-catalog':
                self.actioncmd = self.remove_library_catalog
            elif self.gui.actionsvar.get() == 'remove-index-files':
                self.actioncmd = self.remove_indexes
            elif self.gui.actionsvar.get() == 'install-icu':
                self.actioncmd = self.install_icu

    def run_indexing(self, evt=None):
        utils.start_thread(self.logos.index)

    def remove_library_catalog(self, evt=None):
        control.remove_library_catalog()

    def remove_indexes(self, evt=None):
        self.gui.statusvar.set("Removing indexes…")
        utils.start_thread(control.remove_all_index_files, app=self)

    def install_icu(self, evt=None):
        self.gui.statusvar.set("Installing ICU files…")
        utils.start_thread(wine.install_icu_data_files, app=self)

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
        utils.start_thread(control.backup, app=self)

    def run_restore(self, evt=None):
        # FIXME: Allow user to choose restore source?
        # Start restore thread.
        utils.start_thread(control.restore, app=self)

    def install_deps(self, evt=None):
        self.start_indeterminate_progress()
        utils.start_thread(utils.check_dependencies)

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
        self.gui.statusvar.set("Updating to latest Logos Linux Installer version…")  # noqa: E501
        utils.start_thread(utils.update_to_latest_lli_release, app=self)

    def update_to_latest_appimage(self, evt=None):
        config.APPIMAGE_FILE_PATH = config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME  # noqa: E501
        self.start_indeterminate_progress()
        self.gui.statusvar.set("Updating to latest AppImage…")
        utils.start_thread(utils.set_appimage_symlink, app=self)

    def set_appimage(self, evt=None):
        # TODO: Separate as advanced feature.
        appimage_filename = self.open_file_dialog("AppImage", "AppImage")
        if not appimage_filename:
            return
        # config.SELECTED_APPIMAGE_FILENAME = appimage_filename
        config.APPIMAGE_FILE_PATH = appimage_filename
        utils.start_thread(utils.set_appimage_symlink, app=self)

    def get_winetricks(self, evt=None):
        # TODO: Separate as advanced feature.
        self.gui.statusvar.set("Installing Winetricks…")
        utils.start_thread(
            system.install_winetricks,
            config.APPDIR_BINDIR,
            app=self
        )
        self.update_run_winetricks_button()

    def launch_winetricks(self, evt=None):
        self.gui.statusvar.set("Launching Winetricks…")
        # Start winetricks in thread.
        utils.start_thread(wine.run_winetricks)
        # Start thread to clear status after delay.
        args = [12000, self.root.event_generate, '<<ClearStatus>>']
        utils.start_thread(self.root.after, *args)

    def switch_logging(self, evt=None):
        desired_state = self.gui.loggingstatevar.get()
        self.gui.statusvar.set(f"Switching app logging to '{desired_state}d'…")
        self.start_indeterminate_progress()
        self.gui.progress.state(['!disabled'])
        self.gui.progress.start()
        self.gui.logging_button.state(['disabled'])
        utils.start_thread(
            self.logos.switch_logging,
            action=desired_state.lower()
        )

    def initialize_logging_button(self, evt=None):
        self.gui.statusvar.set('')
        self.gui.progress.stop()
        self.gui.progress.state(['disabled'])
        state = self.reverse_logging_state_value(self.logging_q.get())
        self.gui.loggingstatevar.set(state[:-1].title())
        self.gui.logging_button.state(['!disabled'])

    def update_logging_button(self, evt=None):
        self.gui.statusvar.set('')
        self.gui.progress.stop()
        self.gui.progress.state(['disabled'])
        new_state = self.reverse_logging_state_value(self.logging_q.get())
        new_text = new_state[:-1].title()
        logging.debug(f"Updating app logging button text to: {new_text}")
        self.gui.loggingstatevar.set(new_text)
        self.gui.logging_button.state(['!disabled'])

    def update_app_button(self, evt=None):
        self.gui.app_button.state(['!disabled'])
        self.gui.app_buttonvar.set(f"Run {config.FLPRODUCT}")
        self.configure_app_button()
        self.update_run_winetricks_button()
        self.gui.logging_button.state(['!disabled'])

    def update_latest_lli_release_button(self, evt=None):
        status, reason = utils.compare_logos_linux_installer_version()
        msg = None
        if system.get_runmode() != 'binary':
            state = 'disabled'
            msg = "This button is disabled. Can't run self-update from script."
        elif status == 0:
            state = '!disabled'
        elif status == 1:
            state = 'disabled'
            msg = "This button is disabled. Logos Linux Installer is up-to-date."  # noqa: E501
        elif status == 2:
            state = 'disabled'
            msg = "This button is disabled. Logos Linux Installer is newer than the latest release."  # noqa: E501
        if msg:
            gui.ToolTip(self.gui.update_lli_button, msg)
        self.clear_status_text()
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
        self.clear_status_text()
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

    def clear_status_text(self, evt=None):
        self.gui.statusvar.set('')

    def update_file_check_progress(self, evt=None):
        self.gui.progress.stop()
        self.gui.statusvar.set('')
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)

    def update_download_progress(self, evt=None):
        d = self.get_q.get()
        self.gui.progressvar.set(int(d))

    def update_progress(self, evt=None):
        progress = self.progress_q.get()
        if not type(progress) is int:
            return
        if progress >= 100:
            self.gui.progressvar.set(0)
            # self.gui.progress.state(['disabled'])
        else:
            self.gui.progressvar.set(progress)

    def update_status_text(self, evt=None):
        if evt:
            self.gui.statusvar.set(self.status_q.get())
            self.root.after(3000, self.update_status_text)
        else:  # clear status text if called manually and no progress shown
            if self.gui.progressvar.get() == 0:
                self.gui.statusvar.set('')

    def start_indeterminate_progress(self, evt=None):
        self.gui.progress.state(['!disabled'])
        self.gui.progressvar.set(0)
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
