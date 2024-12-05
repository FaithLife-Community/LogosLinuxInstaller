
# References:
#   - https://tkdocs.com/
#   - https://github.com/thw26/LogosLinuxInstaller/blob/master/LogosLinuxInstaller.sh  # noqa: E501

import logging
from pathlib import Path
from queue import Queue

import shutil
from threading import Event
import threading
from tkinter import PhotoImage, messagebox
from tkinter import Tk
from tkinter import Toplevel
from tkinter import filedialog as fd
from tkinter.ttk import Style
from typing import Callable, Optional

from ou_dedetai.app import App
from ou_dedetai.constants import PROMPT_OPTION_DIRECTORY, PROMPT_OPTION_FILE
from ou_dedetai.config import EphemeralConfiguration

from . import constants
from . import control
from . import gui
from . import installer
from . import system
from . import utils
from . import wine

class GuiApp(App):
    """Implements the App interface for all windows"""

    _exit_option: Optional[str] = None

    def __init__(self, root: "Root", ephemeral_config: EphemeralConfiguration, **kwargs): #noqa: E501
        super().__init__(ephemeral_config)
        self.root = root

    def _ask(self, question: str, options: list[str] | str) -> Optional[str]:
        # This cannot be run from the main thread as the dialog will never appear
        # since the tinker mainloop hasn't started and we block on a response

        if isinstance(options, list):
            answer_q: Queue[Optional[str]] = Queue()
            answer_event = Event()
            ChoicePopUp(question, options, answer_q, answer_event)

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


class ChoicePopUp:
    """Creates a pop-up with a choice"""
    def __init__(self, question: str, options: list[str], answer_q: Queue[Optional[str]], answer_event: Event, **kwargs): #noqa: E501
        self.root = Toplevel()
        # Set root parameters.
        self.gui = gui.ChoiceGui(self.root, question, options)
        self.root.title(f"Quesiton: {question.strip().strip(':')}")
        self.root.resizable(False, False)
        # Set root widget event bindings.
        self.root.bind(
            "<Return>",
            self.on_confirm_choice
        )
        self.root.bind(
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
        self.root.destroy()

    def on_cancel_released(self, evt=None):
        self.answer_q.put(None)
        self.answer_event.set()
        self.root.destroy()


class InstallerWindow:
    def __init__(self, new_win, root: Root, app: "ControlWindow", **kwargs):
        # Set root parameters.
        self.win = new_win
        self.root = root
        self.win.title(f"{constants.APP_NAME} Installer")
        self.win.resizable(False, False)
        self.gui = gui.InstallerGui(self.win, app)
        self.app = app
        self.conf = app.conf
        self.start_thread = app.start_thread

        # Initialize variables.
        self.config_thread = None

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
        self.gui.wine_dropdown.bind(
            '<<ComboboxSelected>>',
            self.set_wine
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

        # Run commands.
        self.get_winetricks_options()

        self.app.config_updated_hooks += [self._config_updated_hook]
        # Start out enforcing this
        self._config_updated_hook()

    def _config_updated_hook(self):
        """Update the GUI to reflect changes in the configuration/network""" #noqa: E501

        # The product/version dropdown values are static, they will always be populated

        # Tor the GUI, use defaults until user says otherwise.
        if self.conf._raw.faithlife_product is None:
            self.conf.faithlife_product = self.gui.product_dropdown['values'][0]
        self.gui.productvar.set(self.conf.faithlife_product)
        if self.conf._raw.faithlife_product_version is None:
            self.conf.faithlife_product_version = self.gui.version_dropdown['values'][-1] #noqa :E501
        self.gui.versionvar.set(self.conf.faithlife_product_version) # noqa: E501

        # Now that we know product and version are set we can download the releases
        # And use the first one
        # FIXME: consider what to do if network is slow, we may want to do this on a
        # Separate thread to not hang the UI
        self.gui.release_dropdown['values'] = self.conf.faithlife_product_releases
        if self.conf._raw.faithlife_product_release is None:
            self.conf.faithlife_product_release = self.conf.faithlife_product_releases[0] #noqa: E501
        self.gui.releasevar.set(self.conf.faithlife_product_release)

        # Set the install_dir to default, no option in the GUI to change it
        if self.conf._raw.install_dir is None:
            self.conf.install_dir = self.conf.install_dir_default

        self.gui.skipdepsvar.set(not self.conf.skip_install_system_dependencies)
        self.gui.fontsvar.set(not self.conf.skip_install_fonts)

        # Returns either wine_binary if set, or self.gui.wine_dropdown['values'] if it has a value, otherwise '' #noqa: E501
        wine_binary: Optional[str] = self.conf._raw.wine_binary
        if wine_binary is None:
            if len(self.gui.wine_dropdown['values']) > 0:
                wine_binary = self.gui.wine_dropdown['values'][0]
                self.app.conf.wine_binary = wine_binary
            else:
                wine_binary = ''

        self.gui.winevar.set(wine_binary)
        # In case the product changes
        self.root.icon = Path(self.conf.faithlife_product_icon_path)

        wine_choices = utils.get_wine_options(self.app)
        self.gui.wine_dropdown['values'] = wine_choices
        if not self.gui.winevar.get():
            # If no value selected, default to 1st item in list.
            self.gui.winevar.set(self.gui.wine_dropdown['values'][0])

        # At this point all variables are populated, we're ready to install!
        self.set_input_widgets_state('enabled', [self.gui.okay_button])

    def _post_dropdown_change(self):
        """Steps to preform after a dropdown has been updated"""
        # Ensure progress counter is reset.
        self.installer_step = 0
        self.installer_step_count = 0
        # Reset install_dir to default based on possible new value
        self.conf.install_dir = self.conf.install_dir_default

    def get_winetricks_options(self):
        # override config file b/c "Download" accounts for that
        # Type hinting ignored due to https://github.com/python/mypy/issues/3004
        self.conf.winetricks_binary = None # type: ignore[assignment]
        self.gui.tricks_dropdown['values'] = utils.get_winetricks_options() #noqa: E501
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
            self.gui.wine_dropdown,
            self.gui.tricks_dropdown,
            self.gui.okay_button,
        ]
        if widgets == 'all':
            widgets = all_widgets
        for w in widgets:
            w.state(state)

    def set_product(self, evt=None):
        self.conf.faithlife_product = self.gui.productvar.get()
        self.gui.product_dropdown.selection_clear()
        self._post_dropdown_change()

    def set_version(self, evt=None):
        self.conf.faithlife_product_version = self.gui.versionvar.get()
        self.gui.version_dropdown.selection_clear()
        self._post_dropdown_change()

    def set_release(self, evt=None):
        self.conf.faithlife_product_release = self.gui.releasevar.get()
        self.gui.release_dropdown.selection_clear()
        self._post_dropdown_change()

    def set_wine(self, evt=None):
        self.conf.wine_binary = self.gui.winevar.get()
        self.gui.wine_dropdown.selection_clear()
        self._post_dropdown_change()

    def set_winetricks(self, evt=None):
        self.conf.winetricks_binary = self.gui.tricksvar.get()
        self.gui.tricks_dropdown.selection_clear()
        self._post_dropdown_change()

    def set_skip_fonts(self, evt=None):
        self.conf.skip_install_fonts = not self.gui.fontsvar.get()  # invert True/False
        logging.debug(f"> {self.conf.skip_install_fonts=}")

    def set_skip_dependencies(self, evt=None):
        self.conf.skip_install_system_dependencies = self.gui.skipdepsvar.get()  # invert True/False  # noqa: E501
        logging.debug(f"> {self.conf.skip_install_system_dependencies=}") #noqa: E501

    def on_okay_released(self, evt=None):
        # Update desktop panel icon.
        self.start_install_thread()

    def on_cancel_released(self, evt=None):
        self.app.config_updated_hooks.remove(self._config_updated_hook)
        # Reset status
        self.app.clear_status()
        self.win.destroy()
        return 1

    def start_install_thread(self, evt=None):
        def _install():
            """Function to handle the install"""
            installer.install(self.app)
            # Install complete, cleaning up...
            self.app._status("", 0)
            self.gui.okay_button.config(
                text="Exit",
                command=self.on_cancel_released,
            )
            self.gui.okay_button.state(['!disabled'])
            self.win.destroy()
            return 0

        # Setup for the install
        self.app.status('Ready to install!', 0)
        self.set_input_widgets_state('disabled')

        self.start_thread(_install)


class ControlWindow(GuiApp):
    def __init__(self, root, control_gui: gui.ControlGui, 
                 ephemeral_config: EphemeralConfiguration, *args, **kwargs):
        super().__init__(root, ephemeral_config)

        # Set root parameters.
        self.root = root
        self.gui = control_gui
        self.actioncmd: Optional[Callable[[], None]] = None

        text = self.gui.update_lli_label.cget('text')
        ver = constants.LLI_CURRENT_VERSION
        text = f"{text}\ncurrent: v{ver}\nlatest: v{self.conf.app_latest_version}"
        self.gui.update_lli_label.config(text=text)
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
        self.update_latest_lli_release_button()
        self.gui.set_appimage_button.config(command=self.set_appimage)
        self.gui.get_winetricks_button.config(command=self.get_winetricks)
        self.gui.run_winetricks_button.config(command=self.launch_winetricks)

        self._config_update_hook()
        # These can be expanded to change the UI based on config changes.
        self.config_updated_hooks += [self._config_update_hook]

    def edit_config(self):
        control.edit_file(self.conf.config_file_path)

    def run_installer(self, evt=None):
        classname = constants.BINARY_NAME
        installer_window_top = Toplevel()
        InstallerWindow(installer_window_top, self.root, app=self, class_=classname) #noqa: E501

    def run_logos(self, evt=None):
        self.start_thread(self.logos.start)

    def run_action_cmd(self, evt=None):
        if self.actioncmd:
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

    def run_indexing(self):
        self.start_thread(self.logos.index)

    def remove_library_catalog(self):
        control.remove_library_catalog(self)

    def remove_indexes(self):
        self.gui.statusvar.set("Removing indexes…")
        self.start_thread(control.remove_all_index_files, app=self)

    def install_icu(self):
        self.gui.statusvar.set("Installing ICU files…")
        self.start_thread(wine.enforce_icu_data_files, app=self)

    def run_backup(self, evt=None):
        # Prepare progress bar.
        self.gui.progress.state(['!disabled'])
        self.gui.progress.config(mode='determinate')
        self.gui.progressvar.set(0)
        # Start backup thread.
        self.start_thread(control.backup, app=self)

    def run_restore(self, evt=None):
        # FIXME: Allow user to choose restore source?
        # Start restore thread.
        self.start_thread(control.restore, app=self)

    def install_deps(self, evt=None):
        self.status("Installing dependencies…")
        self.start_thread(utils.install_dependencies, self)

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
        self.status(f"Updating to latest {constants.APP_NAME} version…")  # noqa: E501
        self.start_thread(utils.update_to_latest_lli_release, app=self)

    def set_appimage_symlink(self):
        utils.set_appimage_symlink(self)
        self.update_latest_appimage_button()

    def update_to_latest_appimage(self, evt=None):
        self.conf.wine_appimage_path = Path(self.conf.wine_appimage_recommended_file_name)  # noqa: E501
        self.status("Updating to latest AppImage…")
        self.start_thread(self.set_appimage_symlink)

    def set_appimage(self, evt=None):
        # TODO: Separate as advanced feature.
        appimage_filename = self.open_file_dialog("AppImage", "AppImage")
        if not appimage_filename:
            return
        self.conf.wine_appimage_path = appimage_filename
        self.start_thread(self.set_appimage_symlink)

    def get_winetricks(self, evt=None):
        # TODO: Separate as advanced feature.
        self.gui.statusvar.set("Installing Winetricks…")
        self.start_thread(
            system.install_winetricks,
            self.conf.installer_binary_dir,
            app=self
        )

    def launch_winetricks(self, evt=None):
        self.status("Launching Winetricks…")
        # Start winetricks in thread.
        self.start_thread(self.run_winetricks)
        # Start thread to clear status after delay.
        args = [12000, self.clear_status]
        self.start_thread(self.root.after, *args)

    def run_winetricks(self):
        wine.run_winetricks(self)

    def switch_logging(self, evt=None):
        desired_state = self.gui.loggingstatevar.get()
        self._status(f"Switching app logging to '{desired_state}d'…")
        self.gui.logging_button.state(['disabled'])
        self.start_thread(
            self.logos.switch_logging,
            action=desired_state.lower()
        )

    def _status(self, message: str, percent: int | None = None):
        message = message.lstrip("\r")
        if percent is not None:
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
        if message:
            super()._status(message, percent)

    def update_logging_button(self, evt=None):
        state = self.reverse_logging_state_value(self.current_logging_state_value())
        self.gui.loggingstatevar.set(state[:-1].title())
        self.gui.logging_button.state(['!disabled'])

    def update_app_button(self, evt=None):
        if self.is_installed():
            self.gui.app_buttonvar.set(f"Run {self.conf.faithlife_product}")
            self.gui.app_button.config(command=self.run_logos)
            self.gui.get_winetricks_button.state(['!disabled'])
            self.gui.logging_button.state(['!disabled'])
        else:
            self.gui.app_button.config(command=self.run_installer)

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
        self.clear_status()
        self.gui.update_lli_button.state([state])

    def update_latest_appimage_button(self, evt=None):
        state = None
        msg = None
        if not self.is_installed():
            state = "disabled"
            msg = "Please install first"
        elif self.conf._raw.wine_binary_code not in ["Recommended", "AppImage", None]:  # noqa: E501
            state = 'disabled'
            msg = "This button is disabled. The configured install was not created using an AppImage."  # noqa: E501
            self.gui.set_appimage_button.state(['disabled'])
            gui.ToolTip(
                self.gui.set_appimage_button,
                "This button is disabled. The configured install was not created using an AppImage."  # noqa: E501
            )
        elif self.conf._raw.wine_binary is not None:
            status, _ = utils.compare_recommended_appimage_version(self)
            if status == 0:
                state = '!disabled'
            elif status == 1:
                state = 'disabled'
                msg = "This button is disabled. The AppImage is already set to the latest recommended."  # noqa: E501
            elif status == 2:
                state = 'disabled'
                msg = "This button is disabled. The AppImage version is newer than the latest recommended."  # noqa: E501
            else:
                # Failed to check
                state = '!disabled'
        else:
            # Not enough context to figure out if this should be enabled or not
            state = '!disabled'
        if msg:
            gui.ToolTip(self.gui.latest_appimage_button, msg)
        self.clear_status()
        self.gui.latest_appimage_button.state([state])

    def update_run_winetricks_button(self, evt=None):
        if self.conf._raw.winetricks_binary is not None:
            # Path may be stored as relative
            if Path(self.conf._raw.winetricks_binary).is_absolute():
                winetricks_binary = self.conf._raw.winetricks_binary
            elif self.conf._raw.install_dir is not None:
                winetricks_binary = str(Path(self.conf._raw.install_dir) / self.conf._raw.winetricks_binary) #noqa: E501
            else:
                winetricks_binary = None

            if winetricks_binary is not None and utils.file_exists(winetricks_binary):
                state = '!disabled'
            else:
                state = 'disabled'
        else:
            state = 'disabled'
        self.gui.run_winetricks_button.state([state])

    def _config_update_hook(self, evt=None):
        self.update_logging_button()
        self.update_app_button()
        self.update_latest_lli_release_button()
        self.update_latest_appimage_button()
        self.update_run_winetricks_button()


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

    def clear_status(self):
        self._status('', 0)




def control_panel_app(ephemeral_config: EphemeralConfiguration):
    classname = constants.BINARY_NAME
    root = Root(className=classname)

    # Need to title/resize and create the initial gui
    # BEFORE mainloop is started to get sizing correct
    # other things in the ControlWindow constructor are run after mainloop is running
    # To allow them to ask questions while the mainloop is running
    root.title(f"{constants.APP_NAME} Control Panel")
    root.resizable(False, False)
    control_gui = gui.ControlGui(root)

    def _start_control_panel():
        ControlWindow(root, control_gui, ephemeral_config, class_=classname)

    # Start the control panel on a new thread so it can open dialogs
    # as a part of it's constructor
    threading.Thread(
        name=f"{constants.APP_NAME} GUI main loop",
        target=_start_control_panel,
        daemon=True
    ).start()

    root.mainloop()
