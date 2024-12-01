
# References:
#   - https://tkdocs.com/
#   - https://github.com/thw26/LogosLinuxInstaller/blob/master/LogosLinuxInstaller.sh  # noqa: E501

import logging
from pathlib import Path
from queue import Queue

import shutil
from threading import Event
from tkinter import PhotoImage, messagebox
from tkinter import Tk
from tkinter import Toplevel
from tkinter import filedialog as fd
from tkinter.ttk import Style
from typing import Optional

from ou_dedetai.app import App
from ou_dedetai.constants import PROMPT_OPTION_DIRECTORY, PROMPT_OPTION_FILE
from ou_dedetai.config import EphemeralConfiguration

from . import constants
from . import control
from . import gui
from . import installer
from . import network
from . import system
from . import utils
from . import wine

class GuiApp(App):
    """Implements the App interface for all windows"""

    _exit_option: Optional[str] = None

    def __init__(self, root: "Root", ephemeral_config: EphemeralConfiguration, **kwargs):
        super().__init__(ephemeral_config)
        self.root = root

    def _ask(self, question: str, options: list[str] | str) -> Optional[str]:
        answer_q = Queue()
        answer_event = Event()
        def spawn_dialog():
            # Create a new popup (with it's own event loop)
            pop_up = ChoicePopUp(question, options, answer_q, answer_event)

            # Run the mainloop in this thread
            pop_up.mainloop()
        if isinstance(options, list):
            utils.start_thread(spawn_dialog)

            answer_event.wait()
            answer: Optional[str] = answer_q.get()
        elif isinstance(options, str):
            answer = options

        if answer == PROMPT_OPTION_DIRECTORY:
            answer = fd.askdirectory(
                parent=self.root,
                title=question,
                initialdir=Path().home(),
            )
        elif answer == PROMPT_OPTION_FILE:
            answer = fd.askopenfilename(
                parent=self.root,
                title=question,
                initialdir=Path().home(),
            )
        return answer

    def approve(self, question: str, context: str | None = None) -> bool:
        return messagebox.askquestion(question, context) == 'yes'

    def exit(self, reason: str, intended: bool = False):
        # Create a little dialog before we die so the user can see why this happened
        if not intended:
            gui.show_error(reason, detail=constants.SUPPORT_MESSAGE, fatal=True)
        self.root.destroy()
        return super().exit(reason, intended)
    
    @property
    def superuser_command(self) -> str:
        """Command when root privileges are needed.
        
        Raises:
            SuperuserCommandNotFound - if no command is found

        pkexec if found"""
        if shutil.which('pkexec'):
            return "pkexec"
        else:
            raise system.SuperuserCommandNotFound("No superuser command found. Please install pkexec.")  # noqa: E501

class Root(Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs)
        self.classname = kwargs.get('classname')
        # Set the theme.
        self.style = Style()
        self.style.theme_use('alt')

        # Update color scheme.
        self.style.configure('TCheckbutton', bordercolor=constants.LOGOS_GRAY)
        self.style.configure('TCombobox', bordercolor=constants.LOGOS_GRAY)
        self.style.configure('TCheckbutton', indicatorcolor=constants.LOGOS_GRAY)
        self.style.configure('TRadiobutton', indicatorcolor=constants.LOGOS_GRAY)
        bg_widgets = [
            'TCheckbutton', 'TCombobox', 'TFrame', 'TLabel', 'TRadiobutton'
        ]
        fg_widgets = ['TButton', 'TSeparator']
        for w in bg_widgets:
            self.style.configure(w, background=constants.LOGOS_WHITE)
        for w in fg_widgets:
            self.style.configure(w, background=constants.LOGOS_GRAY)
        self.style.configure(
            'Horizontal.TProgressbar',
            thickness=10, background=constants.LOGOS_BLUE,
            bordercolor=constants.LOGOS_GRAY,
            troughcolor=constants.LOGOS_GRAY,
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
        self.icon = constants.APP_IMAGE_DIR / 'icon.png'
        self.pi = PhotoImage(file=f'{self.icon}')
        self.iconphoto(False, self.pi)


class ChoicePopUp(Tk):
    """Creates a pop-up with a choice"""
    def __init__(self, question: str, options: list[str], answer_q: Queue, answer_event: Event, **kwargs):
        # Set root parameters.
        super().__init__()
        self.title(f"Quesiton: {question.strip().strip(':')}")
        self.resizable(False, False)
        self.gui = gui.ChoiceGui(self, question, options)
        # Set root widget event bindings.
        self.bind(
            "<Return>",
            self.on_confirm_choice
        )
        self.bind(
            "<Escape>",
            self.on_cancel_released
        )
        self.gui.cancel_button.config(command=self.on_cancel_released)
        self.gui.okay_button.config(command=self.on_confirm_choice)
        self.answer_q = answer_q
        self.answer_event = answer_event

    def on_confirm_choice(self, evt=None):
        if self.gui.answer_dropdown.get() == gui.ChoiceGui._default_prompt:
            return
        answer = self.gui.answer_dropdown.get()
        self.answer_q.put(answer)
        self.answer_event.set()
        self.destroy()

    def on_cancel_released(self, evt=None):
        self.answer_q.put(None)
        self.answer_event.set()
        self.destroy()


class InstallerWindow(GuiApp):
    def __init__(self, new_win, root: Root, app: App, **kwargs):
        super().__init__(root, app.conf._overrides)
        # Set root parameters.
        self.win = new_win
        self.root = root
        self.win.title(f"{constants.APP_NAME} Installer")
        self.win.resizable(False, False)
        self.gui = gui.InstallerGui(self.win, app)

        # Initialize variables.
        self.config_thread = None
        self.appimages = None

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
        self.status_q = Queue()
        self.status_evt = "<<UpdateStatus>>"
        self.root.bind(self.status_evt, self.update_status_text)
        self.releases_q = Queue()
        self.wine_q = Queue()

        # Run commands.
        self.get_winetricks_options()

    def _config_updated_hook(self):
        """Update the GUI to reflect changes in the configuration if they were prompted separately""" #noqa: E501
        # The configuration enforces dependencies, if product is unset, so will it's 
        # dependents (version and release)
        # XXX: test this hook. Interesting thing is, this may never be called in 
        # production, as it's only called (presently) when the separate prompt returns
        # Returns either from config or the dropdown
        self.gui.productvar.set(self.conf._raw.faithlife_product or self.gui.product_dropdown['values'][0]) #noqa: E501
        self.gui.versionvar.set(self.conf._raw.faithlife_product_version or self.gui.version_dropdown['values'][-1]) #noqa: E501
        self.gui.releasevar.set(self.conf._raw.faithlife_product_release or self.gui.release_dropdown['values'][0]) #noqa: E501
        # Returns either wine_binary if set, or self.gui.wine_dropdown['values'] if it has a value, otherwise '' #noqa: E501
        self.gui.winevar.set(self.conf._raw.wine_binary or next(iter(self.gui.wine_dropdown['values']), '')) #noqa: E501

    def start_ensure_config(self):
        # Ensure progress counter is reset.
        self.installer_step = 0
        self.installer_step_count = 0
        self.config_thread = utils.start_thread(
            installer.ensure_installation_config,
            app=self,
        )

    def get_winetricks_options(self):
        self.conf.winetricks_binary = None  # override config file b/c "Download" accounts for that  # noqa: E501
        self.gui.tricks_dropdown['values'] = utils.get_winetricks_options() + ['Return to Main Menu']
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

    def _install_started_hook(self):
        self.gui.statusvar.set('Ready to install!')
        self.gui.progressvar.set(0)
        self.set_input_widgets_state('disabled')

    def set_product(self, evt=None):
        if self.gui.productvar.get().startswith('C'):  # ignore default text
            return
        self.conf.faithlife_product = self.gui.productvar.get()
        self.gui.product_dropdown.selection_clear()
        if evt:  # manual override; reset dependent variables
            logging.debug(f"User changed faithlife_product to '{self.conf.faithlife_product}'")
            self.gui.versionvar.set('')
            self.gui.releasevar.set('')
            self.gui.winevar.set('')

            self.start_ensure_config()

    def set_version(self, evt=None):
        self.conf.faithlife_product_version = self.gui.versionvar.get()
        self.gui.version_dropdown.selection_clear()
        if evt:  # manual override; reset dependent variables
            logging.debug(f"User changed Target Version to '{self.conf.faithlife_product_version}'")  # noqa: E501
            self.gui.releasevar.set('')

            self.gui.winevar.set('')

            self.start_ensure_config()

    def get_logos_releases(self):
        filtered_releases = network.get_logos_releases(self)
        self.releases_q.put(filtered_releases)
        self.root.event_generate(self.release_evt)

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
        utils.start_thread(self.get_logos_releases)

    def set_release(self, evt=None):
        if self.gui.releasevar.get()[0] == 'C':  # ignore default text
            return
        self.conf.faithlife_product_release = self.gui.releasevar.get()
        self.gui.release_dropdown.selection_clear()
        if evt:  # manual override
            logging.debug(f"User changed release version to '{self.conf.faithlife_product_release}'")  # noqa: E501

            self.gui.winevar.set('')

            self.start_ensure_config()

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

        def get_wine_options(app: InstallerWindow, app_images, binaries):
            app.wines_q.put(utils.get_wine_options(app, app_images, binaries))
            app.root.event_generate(app.wine_evt)

        # Start thread.
        utils.start_thread(
            get_wine_options,
            self,
            self.appimages,
            utils.find_wine_binary_files(self, release_version),
        )

    def set_wine(self, evt=None):
        self.conf.wine_binary = self.gui.winevar.get()
        self.gui.wine_dropdown.selection_clear()
        if evt:  # manual override
            logging.debug(f"User changed wine binary to '{self.conf.wine_binary}'")

            self.start_ensure_config()
        else:
            self.wine_q.put(
                utils.get_relative_path(
                    utils.get_config_var(self.conf.wine_binary),
                    self.conf.install_dir
                )
            )

    def set_winetricks(self, evt=None):
        self.conf.winetricks_binary = self.gui.tricksvar.get()
        self.gui.tricks_dropdown.selection_clear()
        if evt:  # manual override
            self.conf.winetricks_binary = None
            self.start_ensure_config()

    def on_release_check_released(self, evt=None):
        self.start_releases_check()

    def on_wine_check_released(self, evt=None):
        self.gui.wine_check_button.state(['disabled'])
        self.start_wine_versions_check(self.conf.faithlife_product_release)

    def set_skip_fonts(self, evt=None):
        self.conf.skip_install_fonts = 1 - self.gui.fontsvar.get()  # invert True/False
        logging.debug(f"> config.SKIP_FONTS={self.conf.skip_install_fonts}")

    def set_skip_dependencies(self, evt=None):
        self.conf.skip_install_system_dependencies = 1 - self.gui.skipdepsvar.get()  # invert True/False  # noqa: E501
        logging.debug(f"> config.SKIP_DEPENDENCIES={self.conf.skip_install_system_dependencies}") #noqa: E501

    def on_okay_released(self, evt=None):
        # Update desktop panel icon.
        self.root.icon = self.conf.faithlife_product_icon_path
        self.start_install_thread()

    def on_cancel_released(self, evt=None):
        self.win.destroy()
        return 1

    def start_install_thread(self, evt=None):
        self.gui.progress.config(mode='determinate')
        utils.start_thread(installer.install, app=self)

    # XXX: where should this live? here or ControlWindow?
    def _status(self, message: str, percent: int | None = None):
        if percent:
            self.gui.progress.stop()
            self.gui.progress.state(['disabled'])
            self.gui.progress.config(mode='determinate')
            self.gui.progressvar.set(percent)
        else:
            self.gui.progress.state(['!disabled'])
            self.gui.progressvar.set(0)
            self.gui.progress.config(mode='indeterminate')
            self.gui.progress.start()
        self.gui.statusvar.set(message)
        super()._status(message, percent)

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
            self.start_wine_versions_check(self.conf.faithlife_product_release)

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

    def update_download_progress(self, evt=None):
        d = self.get_q.get()
        self.gui.progressvar.set(int(d))

    def update_status_text(self, evt=None, status=None):
        text = ''
        if evt:
            text = self.status_q.get()
        elif status:
            text = status
        self.gui.statusvar.set(text)

    def _install_complete_hook(self):
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


class ControlWindow(GuiApp):
    def __init__(self, root, ephemeral_config: EphemeralConfiguration, *args, **kwargs):
        super().__init__(root, ephemeral_config)
        # Set root parameters.
        self.root = root
        self.root.title(f"{constants.APP_NAME} Control Panel")
        self.root.resizable(False, False)
        self.gui = gui.ControlGui(self.root, app=self)
        self.actioncmd = None

        text = self.gui.update_lli_label.cget('text')
        ver = constants.LLI_CURRENT_VERSION
        text = f"{text}\ncurrent: v{ver}\nlatest: v{self.conf.app_latest_version}"
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

        self.gui.config_button.config(command=self.edit_config)
        self.gui.deps_button.config(command=self.install_deps)
        self.gui.backup_button.config(command=self.run_backup)
        self.gui.restore_button.config(command=self.run_restore)
        self.gui.update_lli_button.config(
            command=self.update_to_latest_lli_release
        )
        self.gui.latest_appimage_button.config(
            command=self.update_to_latest_appimage
        )
        if self.conf.wine_binary_code != "AppImage" and self.conf.wine_binary_code != "Recommended":  # noqa: E501
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
        self.status_q = Queue()
        self.status_evt = '<<UpdateControlStatus>>'
        self.root.bind(self.status_evt, self.update_status_text)
        self.root.bind('<<ClearStatus>>', self.clear_status_text)
        self.root.bind(
            '<<StartIndeterminateProgress>>',
            self.start_indeterminate_progress
        )
        self.root.bind(
            "<<UpdateLatestAppImageButton>>",
            self.update_latest_appimage_button
        )
        self.root.bind('<<InstallFinished>>', self.update_app_button)
        self.get_q = Queue()
        self.get_evt = "<<GetFile>>"
        self.root.bind(self.get_evt, self.update_download_progress)

        self.installer_window = None

        self.update_logging_button()

    def edit_config(self):
        control.edit_file(self.conf.config_file_path)

    def configure_app_button(self, evt=None):
        if self.is_installed():
            # wine.set_logos_paths()
            self.gui.app_buttonvar.set(f"Run {self.conf.faithlife_product}")
            self.gui.app_button.config(command=self.run_logos)
            self.gui.get_winetricks_button.state(['!disabled'])
        else:
            self.gui.app_button.config(command=self.run_installer)

    def run_installer(self, evt=None):
        classname = constants.BINARY_NAME
        installer_window_top = Toplevel()
        self.installer_window = InstallerWindow(installer_window_top, self.root, app=self, class_=classname)
        self.root.icon = self.conf.faithlife_product_icon_path

    def run_logos(self, evt=None):
        utils.start_thread(self.logos.start)

    def run_action_cmd(self, evt=None):
        self.actioncmd()

    def on_action_radio_clicked(self, evt=None):
        logging.debug("gui_app.ControlPanel.on_action_radio_clicked START")
        if self.is_installed():
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
        control.remove_library_catalog(self)

    def remove_indexes(self, evt=None):
        self.gui.statusvar.set("Removing indexes…")
        utils.start_thread(control.remove_all_index_files, app=self)

    def install_icu(self, evt=None):
        self.gui.statusvar.set("Installing ICU files…")
        utils.start_thread(wine.enforce_icu_data_files, app=self)

    def run_backup(self, evt=None):
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
        utils.start_thread(utils.install_dependencies, self)

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
        self.gui.statusvar.set(f"Updating to latest {constants.APP_NAME} version…")  # noqa: E501
        utils.start_thread(utils.update_to_latest_lli_release, app=self)

    def set_appimage_symlink(self):
        utils.set_appimage_symlink(self)
        self.update_latest_appimage_button()

    def update_to_latest_appimage(self, evt=None):
        self.conf.wine_appimage_path = self.conf.wine_appimage_recommended_file_name  # noqa: E501
        self.start_indeterminate_progress()
        self.gui.statusvar.set("Updating to latest AppImage…")
        utils.start_thread(self.set_appimage_symlink)

    def set_appimage(self, evt=None):
        # TODO: Separate as advanced feature.
        appimage_filename = self.open_file_dialog("AppImage", "AppImage")
        if not appimage_filename:
            return
        self.conf.wine_appimage_path = appimage_filename
        utils.start_thread(self.set_appimage_symlink)

    def get_winetricks(self, evt=None):
        # TODO: Separate as advanced feature.
        self.gui.statusvar.set("Installing Winetricks…")
        utils.start_thread(
            system.install_winetricks,
            self.conf.installer_binary_dir,
            app=self
        )
        self.update_run_winetricks_button()

    def launch_winetricks(self, evt=None):
        self.gui.statusvar.set("Launching Winetricks…")
        # Start winetricks in thread.
        utils.start_thread(self.run_winetricks)
        # Start thread to clear status after delay.
        args = [12000, self.root.event_generate, '<<ClearStatus>>']
        utils.start_thread(self.root.after, *args)

    def run_winetricks(self):
        wine.run_winetricks(self)

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
    
    def _config_updated_hook(self) -> None:
        self.update_logging_button()
        if self.installer_window is not None:
            self.installer_window._config_updated_hook()
        return super()._config_updated_hook()

    # XXX: should this live here or in installerWindow?
    def _status(self, message: str, percent: int | None = None):
        if percent:
            self.gui.progress.stop()
            self.gui.progress.state(['disabled'])
            self.gui.progress.config(mode='determinate')
            self.gui.progressvar.set(percent)
        else:
            self.gui.progress.state(['!disabled'])
            self.gui.progressvar.set(0)
            self.gui.progress.config(mode='indeterminate')
            self.gui.progress.start()
        self.gui.statusvar.set(message)
        super()._status(message, percent)

    def update_logging_button(self, evt=None):
        self.gui.statusvar.set('')
        self.gui.progress.stop()
        self.gui.progress.state(['disabled'])
        state = self.reverse_logging_state_value(self.current_logging_state_value())
        self.gui.loggingstatevar.set(state[:-1].title())
        self.gui.logging_button.state(['!disabled'])

    def update_app_button(self, evt=None):
        self.gui.app_button.state(['!disabled'])
        # XXX: we may need another hook here to update the product version should it change #noqa: E501
        self.gui.app_buttonvar.set(f"Run {self.conf.faithlife_product}")
        self.configure_app_button()
        self.update_run_winetricks_button()
        self.gui.logging_button.state(['!disabled'])

    def update_latest_lli_release_button(self, evt=None):
        msg = None
        result = utils.compare_logos_linux_installer_version(self)
        if system.get_runmode() != 'binary':
            state = 'disabled'
            msg = "This button is disabled. Can't run self-update from script."
        elif result == utils.VersionComparison.OUT_OF_DATE:
            state = '!disabled'
        elif result == utils.VersionComparison.UP_TO_DATE:
            state = 'disabled'
            msg = f"This button is disabled. {constants.APP_NAME} is up-to-date."  # noqa: E501
        elif result == utils.VersionComparison.DEVELOPMENT:
            state = 'disabled'
            msg = f"This button is disabled. {constants.APP_NAME} is newer than the latest release."  # noqa: E501
        if msg:
            gui.ToolTip(self.gui.update_lli_button, msg)
        self.clear_status_text()
        self.stop_indeterminate_progress()
        self.gui.update_lli_button.state([state])

    def update_latest_appimage_button(self, evt=None):
        status, reason = utils.compare_recommended_appimage_version(self)
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

    def stop_indeterminate_progress(self, evt=None):
        self.gui.progress.stop()
        self.gui.progress.state(['disabled'])
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)

    def update_run_winetricks_button(self, evt=None):
        if utils.file_exists(self.conf.winetricks_binary):
            state = '!disabled'
        else:
            state = 'disabled'
        self.gui.run_winetricks_button.state([state])

    def current_logging_state_value(self) -> str:
        if self.conf.faithlife_product_logging:
            return 'ENABLED'
        else:
            return 'DISABLED'

    def reverse_logging_state_value(self, state) ->str:
        if state == 'DISABLED':
            return 'ENABLED'
        else:
            return 'DISABLED'

    def clear_status_text(self, evt=None):
        self.gui.statusvar.set('')

    def update_download_progress(self, evt=None):
        d = self.get_q.get()
        self.gui.progressvar.set(int(d))

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



def control_panel_app(ephemeral_config: EphemeralConfiguration):
    classname = constants.BINARY_NAME
    root = Root(className=classname)
    ControlWindow(root, ephemeral_config, class_=classname)
    root.mainloop()
