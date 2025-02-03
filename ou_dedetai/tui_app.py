import logging
import os
import signal
import sys
import threading
import time
import curses
from pathlib import Path
from queue import Queue
from typing import Any, Optional

from ou_dedetai.app import App
from ou_dedetai.constants import (
    PROMPT_OPTION_DIRECTORY,
    PROMPT_OPTION_FILE
)
from ou_dedetai.config import EphemeralConfiguration

from . import control
from . import constants
from . import installer
from . import logos
from . import msg
from . import system
from . import tui_curses
from . import tui_screen
from . import utils
from . import wine

console_message = ""


class ReturningToMainMenu(Exception):
    """Exception raised when user returns to the main menu
    
    effectively stopping execution on the executing thread where this exception 
    originated from"""


# TODO: Fix hitting cancel in Dialog Screens; currently crashes program.
class TUI(App):
    def __init__(self, stdscr: curses.window, ephemeral_config: EphemeralConfiguration):
        super().__init__(ephemeral_config)
        self.stdscr = stdscr
        self.set_title()
        # else:
        #    self.title = f"Welcome to {constants.APP_NAME} ({constants.LLI_CURRENT_VERSION})"  # noqa: E501
        self.console_message = "Starting TUI…"
        self.llirunning = True
        self.active_progress = False
        self.tmp = ""

        # Generic ask/response events/threads
        self.ask_answer_queue: Queue[str] = Queue()
        self.ask_answer_event = threading.Event()

        # Queues
        self.main_thread = threading.Thread()
        self.status_q: Queue[str] = Queue()
        self.status_e = threading.Event()
        self.todo_q: Queue[str] = Queue()
        self.todo_e = threading.Event()
        self.screen_q: Queue[None] = Queue()
        self.choice_q: Queue[str] = Queue()
        self.switch_q: Queue[int] = Queue()

        # Install and Options
        self.password_q: Queue[str] = Queue()
        self.password_e = threading.Event()
        self.appimage_q: Queue[str] = Queue()
        self.appimage_e = threading.Event()
        self._installer_thread: Optional[threading.Thread] = None

        self.terminal_margin = 0
        self.resizing = False
        # These two are updated in set_window_dimensions
        self.console_log_lines = 0
        self.options_per_page = 0

        # Window and Screen Management
        self.tui_screens: list[tui_screen.Screen] = []
        self.menu_options: list[Any] = []

        # Default height and width to something reasonable so these values are always
        # ints, on each loop these values will be updated to their real values
        self.window_height = self.window_width = 80
        self.main_window_height = self.menu_window_height = 80
        # Default to a value to allow for int type
        self.main_window_min: int = 0
        self.menu_window_min: int = 0

        self.menu_window_ratio: Optional[float] = None
        self.main_window_ratio: Optional[float] = None
        self.main_window_ratio = None
        self.main_window: Optional[curses.window] = None
        self.menu_window: Optional[curses.window] = None
        self.resize_window: Optional[curses.window] = None

        # For menu dialogs.
        # a new MenuDialog is created every loop, so we can't store it there.
        self.current_option: int = 0
        self.current_page: int = 0
        self.total_pages: int = 0

        # Start internal property variables, shouldn't be accessed directly, see their 
        # corresponding @property functions
        self._menu_screen: Optional[tui_screen.MenuScreen] = None
        self._active_screen: Optional[tui_screen.Screen] = None
        self._console: Optional[tui_screen.ConsoleScreen] = None
        # End internal property values

        # Lines for the on-screen console log
        self.console_log: list[str] = []

        # Turn off using python dialog for now, as it wasn't clear when it should have
        # been used before. And doesn't add value.
        # Before some function calls didn't pass use_python_dialog falling back to False
        # now it all respects use_python_dialog
        # some menus may open in dialog that didn't before.
        self.use_python_dialog: bool = False
        if "dialog" in sys.modules and ephemeral_config.terminal_app_prefer_dialog is not False: #noqa: E501
            result = system.test_dialog_version()

            if result is None:
                logging.debug(
                    "The 'dialog' package was not found. Falling back to Python Curses."
                )  # noqa: E501
            elif result:
                logging.debug("Dialog version is up-to-date.")
                self.use_python_dialog = True
            else:
                logging.error(
                    "Dialog version is outdated. The program will fall back to Curses."
                )  # noqa: E501
        # FIXME: remove this hard-coding after considering whether we want to continue 
        # to support both
        self.use_python_dialog = False

        logging.debug(f"Use Python Dialog?: {self.use_python_dialog}")
        self.set_window_dimensions()

        self.config_updated_hooks += [self._config_update_hook]

    def set_title(self):
        self.title = f"Welcome to {constants.APP_NAME} {constants.LLI_CURRENT_VERSION} ({self.conf.app_release_channel})"  # noqa: E501
        product_name = self.conf._raw.faithlife_product or constants.FAITHLIFE_PRODUCTS[0] #noqa: E501
        if self.is_installed():
            self.subtitle = f"{product_name} Version: {self.conf.installed_faithlife_product_release} ({self.conf.faithlife_product_release_channel})"  # noqa: E501
        else:
            self.subtitle = f"{product_name} not installed"
        # Reset the console to force a re-draw
        self._console = None

    @property
    def active_screen(self) -> tui_screen.Screen:
        if self._active_screen is None:
            self._active_screen = self.menu_screen
            if self._active_screen is None:
                raise ValueError("Curses hasn't been initialized yet")
        return self._active_screen

    @active_screen.setter
    def active_screen(self, value: tui_screen.Screen):
        self._active_screen = value

    @property
    def menu_screen(self) -> tui_screen.MenuScreen:
        if self._menu_screen is None:
            self._menu_screen = tui_screen.MenuScreen(
                self,
                0,
                self.status_q,
                self.status_e,
                "Main Menu",
                self.set_tui_menu_options(),
            )  # noqa: E501
        return self._menu_screen
    
    @property
    def console(self) -> tui_screen.ConsoleScreen:
        if self._console is None:
            self._console = tui_screen.ConsoleScreen(
                self, 0, self.status_q, self.status_e, self.title, self.subtitle, 0
            )  # noqa: E501
        return self._console

    @property
    def recent_console_log(self) -> list[str]:
        """Outputs console log trimmed by the maximum length"""
        return self.console_log[-self.console_log_lines:]

    def set_window_dimensions(self):
        self.update_tty_dimensions()
        curses.resizeterm(self.window_height, self.window_width)
        self.main_window_ratio = 0.25
        if self.console_log:
            min_console_height = len(tui_curses.wrap_text(self, self.console_log[-1]))
        else:
            min_console_height = 2
        self.main_window_min = (
            len(tui_curses.wrap_text(self, self.title))
            + len(tui_curses.wrap_text(self, self.subtitle))
            + min_console_height
        )
        self.menu_window_ratio = 0.75
        self.menu_window_min = 3
        self.main_window_height = max(
            int(self.window_height * self.main_window_ratio), self.main_window_min
        )  # noqa: E501#noqa: E501
        self.menu_window_height = max(
            self.window_height - self.main_window_height,
            int(self.window_height * self.menu_window_ratio),
            self.menu_window_min,
        )  # noqa: E501
        self.console_log_lines = max(self.main_window_height - self.main_window_min, 1)
        self.options_per_page = max(self.window_height - self.main_window_height - 6, 1)
        self.main_window = curses.newwin(self.main_window_height, curses.COLS, 0, 0)
        self.menu_window = curses.newwin(
            self.menu_window_height, curses.COLS, self.main_window_height + 1, 0
        )  # noqa: E501
        resize_lines = tui_curses.wrap_text(self, "Screen too small.")
        self.resize_window = curses.newwin(len(resize_lines) + 1, curses.COLS, 0, 0)

    @staticmethod
    def set_curses_style():
        curses.start_color()
        curses.use_default_colors()
        curses.init_color(curses.COLOR_BLUE, 0, 510, 1000)  # Logos Blue
        curses.init_color(curses.COLOR_CYAN, 906, 906, 906)  # Logos Gray
        curses.init_color(curses.COLOR_WHITE, 988, 988, 988)  # Logos White
        curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_WHITE)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLUE)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_BLUE)
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)

    def set_curses_colors(self):
        if self.conf.curses_colors == "Logos":
            self.stdscr.bkgd(" ", curses.color_pair(3))
            if self.main_window:
                self.main_window.bkgd(" ", curses.color_pair(3))
            if self.menu_window:
                self.menu_window.bkgd(" ", curses.color_pair(3))
        elif self.conf.curses_colors == "Light":
            self.stdscr.bkgd(" ", curses.color_pair(6))
            if self.main_window:
                self.main_window.bkgd(" ", curses.color_pair(6))
            if self.menu_window:
                self.menu_window.bkgd(" ", curses.color_pair(6))
        elif self.conf.curses_colors == "Dark":
            self.stdscr.bkgd(" ", curses.color_pair(7))
            if self.main_window:
                self.main_window.bkgd(" ", curses.color_pair(7))
            if self.menu_window:
                self.menu_window.bkgd(" ", curses.color_pair(7))

    def update_windows(self):
        if isinstance(self.active_screen, tui_screen.CursesScreen):
            if self.main_window:
                self.main_window.erase()
            if self.menu_window:
                self.menu_window.erase()
            self.stdscr.timeout(100)
            self.console.display()

    def clear(self):
        self.stdscr.clear()
        if self.main_window:
            self.main_window.clear()
        if self.menu_window:
            self.menu_window.clear()
        if self.resize_window:
            self.resize_window.clear()

    def refresh(self):
        if self.main_window:
            self.main_window.noutrefresh()
        if self.menu_window:
            self.menu_window.noutrefresh()
        if self.resize_window:
            self.resize_window.noutrefresh()
        curses.doupdate()

    def init_curses(self):
        try:
            if curses.has_colors():
                self.set_curses_style()
                self.set_curses_colors()

            curses.curs_set(0)
            curses.noecho()
            curses.cbreak()
            self.stdscr.keypad(True)

            # Reset console/menu_screen. They'll be initialized next access
            self._console = None
            self._menu_screen = tui_screen.MenuScreen(
                self,
                0,
                self.status_q,
                self.status_e,
                "Main Menu",
                self.set_tui_menu_options(),
            )  # noqa: E501
            # self.menu_screen = tui_screen.MenuDialog(self, 0, self.status_q, self.status_e, "Main Menu", self.set_tui_menu_options(dialog=True)) #noqa: E501
            self.refresh()
        except curses.error as e:
            logging.error(f"Curses error in init_curses: {e}")
        except Exception as e:
            self.end_curses()
            logging.error(f"An error occurred in init_curses(): {e}")
            raise

    def end_curses(self):
        try:
            self.stdscr.keypad(False)
            curses.nocbreak()
            curses.echo()
        except curses.error as e:
            logging.error(f"Curses error in end_curses: {e}")
            raise
        except Exception as e:
            logging.error(f"An error occurred in end_curses(): {e}")
            raise

    def end(self, signal, frame):
        logging.debug("Exiting…")
        self.llirunning = False
        curses.endwin()

    def update_main_window_contents(self):
        self.clear()
        self.title = f"Welcome to {constants.APP_NAME} {constants.LLI_CURRENT_VERSION} ({self.conf.app_release_channel})"  # noqa: E501
        self.subtitle = f"Logos Version: {self.conf.installed_faithlife_product_release} ({self.conf.faithlife_product_release_channel})"  # noqa: E501
        # Reset internal variable, it'll be reset next access
        self._console = None
        self.menu_screen.set_options(self.set_tui_menu_options())
        self.refresh()

    # ERR: On a sudden resize, the Curses menu is not properly resized,
    # and we are not currently dynamically passing the menu options based
    # on the current screen, but rather always passing the tui menu options.
    # To replicate, open Terminator, run LLI full screen, then his Ctrl+A.
    # The menu should survive, but the size does not resize to the new screen,
    # even though the resize signal is sent. See tui_curses, line #251 and
    # tui_screen, line #98.
    def resize_curses(self):
        self.resizing = True
        curses.endwin()
        self.update_tty_dimensions()
        self.set_window_dimensions()
        self.clear()
        self.init_curses()
        self.refresh()
        logging.debug("Window resized.")
        self.resizing = False

    def signal_resize(self, signum, frame):
        self.resize_curses()
        self.choice_q.put("resize")

        if self.use_python_dialog:
            if (
                isinstance(self.active_screen, tui_screen.TextDialog)
                and self.active_screen.text == "Screen Too Small"
            ):
                self.choice_q.put("Return to Main Menu")
        else:
            if self.active_screen.screen_id == 14:
                self.update_tty_dimensions()
                if self.window_height > 9:
                    self.switch_q.put(1)
                elif self.window_width > 34:
                    self.switch_q.put(1)

    def draw_resize_screen(self):
        self.clear()
        if self.window_width > 10:
            margin = self.terminal_margin
        else:
            margin = 0
        resize_lines = tui_curses.wrap_text(self, "Screen too small.")
        self.resize_window = curses.newwin(len(resize_lines) + 1, curses.COLS, 0, 0)
        for i, line in enumerate(resize_lines):
            if i < self.window_height:
                tui_curses.write_line(
                    self,
                    self.resize_window,
                    i,
                    margin,
                    line,
                    self.window_width - self.terminal_margin,
                    curses.A_BOLD,
                )
        self.refresh()

    def display(self):
        signal.signal(signal.SIGWINCH, self.signal_resize)
        signal.signal(signal.SIGINT, self.end)
        msg.initialize_tui_logging()

        # Makes sure status stays shown
        timestamp = utils.get_timestamp()
        self.status_q.put(f"{timestamp} {self.console_message}")
        self.report_waiting(f"{self.console_message}")  # noqa: E501

        self.active_screen = self.menu_screen
        last_time = time.time()
        self.logos.monitor()

        while self.llirunning:
            if self.window_height >= 10 and self.window_width >= 35:
                self.terminal_margin = 2
                if not self.resizing:
                    self.update_windows()

                    self.active_screen.display()

                    if self.choice_q.qsize() > 0:
                        self.choice_processor(
                            self.menu_window,
                            self.active_screen.screen_id,
                            self.choice_q.get(),
                        )

                    if self.screen_q.qsize() > 0:
                        self.screen_q.get()
                        self.switch_q.put(1)

                    if self.switch_q.qsize() > 0:
                        self.switch_q.get()
                        self.switch_screen()

                    if len(self.tui_screens) == 0:
                        self.active_screen = self.menu_screen
                    else:
                        self.active_screen = self.tui_screens[-1]

                    if not isinstance(self.active_screen, tui_screen.DialogScreen):
                        run_monitor, last_time = utils.stopwatch(last_time, 2.5)
                        if run_monitor:
                            self.logos.monitor()
                            self.menu_screen.set_options(self.set_tui_menu_options())

                    if isinstance(self.active_screen, tui_screen.CursesScreen):
                        self.refresh()
            elif self.window_width >= 10:
                if self.window_width < 10:
                    # Avoid drawing errors on very small screens
                    self.terminal_margin = 1
                self.draw_resize_screen()
            elif self.window_width < 10:
                self.terminal_margin = 0  # Avoid drawing errors on very small screens

    def run(self):
        try:
            self.init_curses()
            self.display()
        except KeyboardInterrupt:
            self.end_curses()
            signal.signal(signal.SIGINT, self.end)
        finally:
            self.end_curses()
            signal.signal(signal.SIGINT, self.end)

    def installing_pw_waiting(self):
        # self.start_thread(self.get_waiting, screen_id=15)
        pass

    def choice_processor(self, stdscr, screen_id, choice):
        screen_actions = {
            0: self.main_menu_select,
            1: self.custom_appimage_select,
            2: self.handle_ask_response,
            8: self.waiting,
            10: self.waiting_releases,
            12: self.logos.start,
            13: self.waiting_finish,
            14: self.waiting_resize,
            15: self.password_prompt,
            18: self.utilities_menu_select,
            19: self.renderer_select,
            20: self.win_ver_logos_select,
            21: self.win_ver_index_select,
            24: self.confirm_restore_dir,
            25: self.choose_restore_dir,
        }

        # Capture menu exiting before processing in the rest of the handler
        if screen_id not in [0, 2] and (choice in ["Return to Main Menu", "Exit"]):
            if choice == "Return to Main Menu":
                self.tui_screens = []
            self.reset_screen()
            self.switch_q.put(1)
            # FIXME: There is some kind of graphical glitch that activates on returning
            # to Main Menu, but not from all submenus.
            # Further, there appear to be issues with how the program exits on Ctrl+C as
            # part of this.
        else:
            action = screen_actions.get(screen_id)
            if action:
                # Start the action in a new thread to not interrupt the input thread
                self.start_thread(
                    action,
                    choice,
                    daemon_bool=False,
                )
            else:
                pass

    def reset_screen(self):
        self.active_screen.running = 0
        self.active_screen.choice = "Processing"
        self.current_option = 0
        self.current_page = 0
        self.total_pages = 0

    def go_to_main_menu(self):
        self.reset_screen()
        self.menu_screen.choice = "Processing"
        self.choice_q.put("Return to Main Menu")

    def main_menu_select(self, choice):
        def _install():
            try:
                installer.install(app=self)
                self.go_to_main_menu()
            except ReturningToMainMenu:
                pass
        if choice is None or choice == "Exit":
            logging.info("Exiting installation.")
            self.tui_screens = []
            self.llirunning = False
        elif choice.startswith("Install"):
            self.reset_screen()
            self.installer_step = 0
            self.installer_step_count = 0
            if self._installer_thread is not None:
                # The install thread should have completed with ReturningToMainMenu
                # Check just in case
                if self._installer_thread.is_alive():
                    raise Exception("Previous install is still running")
                # Reset user choices and try again!
                self.conf.faithlife_product = None # type: ignore[assignment]
            self._installer_thread = self.start_thread(
                _install,
                daemon_bool=True,
            )

        elif choice.startswith(f"Update {constants.APP_NAME}"):
            utils.update_to_latest_lli_release(self)
        elif self.conf._raw.faithlife_product and choice == f"Run {self.conf._raw.faithlife_product}": #noqa: E501
            self.reset_screen()
            self.logos.start()
            self.menu_screen.set_options(self.set_tui_menu_options())
            self.switch_q.put(1)
        elif self.conf._raw.faithlife_product and choice == f"Stop {self.conf.faithlife_product}": #noqa: E501
            self.reset_screen()
            self.logos.stop()
            self.menu_screen.set_options(self.set_tui_menu_options())
            self.switch_q.put(1)
        elif choice == "Run Indexing":
            self.active_screen.running = 0
            self.active_screen.choice = "Processing"
            self.logos.index()
        elif choice == "Remove Library Catalog":
            self.active_screen.running = 0
            self.active_screen.choice = "Processing"
            control.remove_library_catalog(self)
        elif choice.startswith("Utilities"):
            self.reset_screen()
            self.screen_q.put(
                self.stack_menu(
                    18,
                    self.todo_q,
                    self.todo_e,
                    "Utilities Menu",
                    self.set_utilities_menu_options(),
                )
            )  # noqa: E501
        elif choice == "Change Color Scheme":
            self.status("Changing color scheme")
            self.conf.cycle_curses_color_scheme()
            self.go_to_main_menu()

    def utilities_menu_select(self, choice):
        if choice == "Remove Library Catalog":
            self.reset_screen()
            control.remove_library_catalog(self)
            self.go_to_main_menu()
        elif choice == "Remove All Index Files":
            self.reset_screen()
            control.remove_all_index_files(self)
            self.go_to_main_menu()
        elif choice == "Edit Config":
            self.reset_screen()
            control.edit_file(self.conf.config_file_path)
            self.go_to_main_menu()
        elif choice == "Reload Config":
            self.conf.reload()
            self.go_to_main_menu()
        elif choice == "Change Logos Release Channel":
            self.reset_screen()
            self.conf.toggle_faithlife_product_release_channel()
            self.update_main_window_contents()
            self.go_to_main_menu()
        elif choice == f"Change {constants.APP_NAME} Release Channel":
            self.reset_screen()
            self.conf.toggle_installer_release_channel()
            self.update_main_window_contents()
            self.go_to_main_menu()
        elif choice == "Install Dependencies":
            self.reset_screen()
            self.update_windows()
            utils.install_dependencies(self)
            self.go_to_main_menu()
        elif choice == "Back Up Data":
            self.reset_screen()
            self.start_thread(self.do_backup)
        elif choice == "Restore Data":
            self.reset_screen()
            self.start_thread(self.do_backup)
        elif choice == "Update to Latest AppImage":
            self.reset_screen()
            utils.update_to_latest_recommended_appimage(self)
            self.go_to_main_menu()
        # This isn't an option in set_utilities_menu_options
        # This code path isn't reachable and isn't tested post-refactor
        elif choice == "Set AppImage":
            # TODO: Allow specifying the AppImage File
            appimages = self.conf.wine_app_image_files
            appimage_choices = appimages
            appimage_choices.extend(["Input Custom AppImage", "Return to Main Menu"])
            self.menu_options = appimage_choices
            question = "Which AppImage should be used?"
            self.screen_q.put(
                self.stack_menu(
                    1, self.appimage_q, self.appimage_e, question, appimage_choices
                )
            )  # noqa: E501
        elif choice == "Install ICU":
            self.reset_screen()
            wine.enforce_icu_data_files(self)
            self.go_to_main_menu()
        elif choice.endswith("Logging"):
            self.reset_screen()
            self.logos.switch_logging()
            self.go_to_main_menu()

    def custom_appimage_select(self, choice: str):
        if choice == "Input Custom AppImage":
            appimage_filename = self.ask("Enter AppImage filename: ", [PROMPT_OPTION_FILE]) #noqa: E501
        else:
            appimage_filename = choice
        self.conf.wine_appimage_path = Path(appimage_filename)
        utils.set_appimage_symlink(self)
        if not self.menu_window:
            raise ValueError("Curses hasn't been initialized")
        self.menu_screen.choice = "Processing"
        self.appimage_q.put(str(self.conf.wine_appimage_path))
        self.appimage_e.set()

    def waiting(self, choice):
        pass

    def waiting_releases(self, choice):
        pass

    def waiting_finish(self, choice):
        pass

    def waiting_resize(self, choice):
        pass

    def password_prompt(self, choice):
        if choice:
            self.menu_screen.choice = "Processing"
            self.password_q.put(choice)
            self.password_e.set()

    def renderer_select(self, choice):
        if choice in ["gdi", "gl", "vulkan"]:
            self.reset_screen()
            self.status(f"Changing renderer to {choice}.", 0)
            wine.set_renderer(self, self.conf.wine64_binary, choice)
            self.status(f"Changed renderer to {choice}.", 100)
            self.go_to_main_menu()

    def win_ver_logos_select(self, choice):
        if choice in ["vista", "win7", "win8", "win10", "win11"]:
            self.reset_screen()
            self.status(f"Changing Windows version for Logos to {choice}.", 0)
            wine.set_win_version(self, "logos", choice)
            self.status(f"Changed Windows version for Logos to {choice}.", 100)
            self.go_to_main_menu()

    def win_ver_index_select(self, choice):
        if choice in ["vista", "win7", "win8", "win10", "win11"]:
            self.reset_screen()
            self.status(f"Changing Windows version for Indexer to {choice}.", 0)
            wine.set_win_version(self, "indexer", choice)
            self.status(f"Changed Windows version for Indexer to {choice}.", 100)
            self.go_to_main_menu()

    def switch_screen(self):
        if (
            self.active_screen is not None
            and self.active_screen != self.menu_screen
            and len(self.tui_screens) > 0
        ):  # noqa: E501
            self.tui_screens.pop(0)
        if self.active_screen == self.menu_screen:
            self.menu_screen.choice = "Processing"
            self.menu_screen.running = 0
        if isinstance(self.active_screen, tui_screen.CursesScreen):
            self.clear()

    _exit_option = "Return to Main Menu"

    def _ask(self, question: str, options: list[str] | str) -> Optional[str]:
        self.ask_answer_event.clear()
        if isinstance(options, str):
            answer = options
        elif isinstance(options, list):
            self.menu_options = self.which_dialog_options(options)
            self.screen_q.put(
                self.stack_menu(
                    2, Queue(), threading.Event(), question, self.menu_options
                )
            )  # noqa: E501

            # Now wait for it to complete.
            self.ask_answer_event.wait()
            answer = self.ask_answer_queue.get()

        self.ask_answer_event.clear()
        if answer in [PROMPT_OPTION_DIRECTORY, PROMPT_OPTION_FILE]:
            self.screen_q.put(
                self.stack_input(
                    2,
                    Queue(),
                    threading.Event(),
                    question,
                    os.path.expanduser("~/"),
                )
            )  # noqa: E501
            # Now wait for it to complete
            self.ask_answer_event.wait()
            new_answer = self.ask_answer_queue.get()
            if answer == PROMPT_OPTION_DIRECTORY:
                # Make the directory if it doesn't exit.
                # form a terminal UI, it's not easy for the user to manually
                os.makedirs(new_answer, exist_ok=True)

            answer = new_answer

        if answer == self._exit_option:
            self.tui_screens = []
            self.reset_screen()
            self.switch_q.put(1)
            raise ReturningToMainMenu

        return answer

    def handle_ask_response(self, choice: str):
        self.ask_answer_queue.put(choice)
        self.ask_answer_event.set()

    def _status(self, message: str, percent: int | None = None):
        message = message.lstrip("\r")
        if self.console_log[-1] == message:
            return
        self.console_log.append(message)
        self.screen_q.put(
            self.stack_text(
                8,
                self.status_q,
                self.status_e,
                message,
                wait=True,
                percent=percent or 0,
            )
        )

    def _config_update_hook(self):
        self.update_main_window_contents()
        self.set_curses_colors()
        self.set_title()

    # def get_password(self, dialog):
    #     question = (f"Logos Linux Installer needs to run a command as root. "
    #                 f"Please provide your password to provide escalation privileges.")
    #     self.screen_q.put(self.stack_password(15, self.password_q, self.password_e, question, dialog=dialog)) #noqa: E501

    def confirm_restore_dir(self, choice):
        if choice:
            if choice == "Yes":
                self.tmp = "Yes"
            else:
                self.tmp = "No"
            self.todo_e.set()

    def choose_restore_dir(self, choice):
        if choice:
            self.tmp = choice
            self.todo_e.set()

    def do_backup(self):
        self.todo_e.wait()
        self.todo_e.clear()
        if self.tmp == "backup":
            control.backup(self)
        else:
            control.restore(self)
        self.go_to_main_menu()

    def report_waiting(self, text):
        # self.screen_q.put(self.stack_text(10, self.status_q, self.status_e, text, wait=True, dialog=dialog)) #noqa: E501
        self.console_log.append(text)

    def which_dialog_options(self, labels: list[str]) -> list[Any]: #noqa: E501
        # curses - list[str]
        # dialog - list[tuple[str, str]] 
        options: list[Any] = []
        option_number = 1
        for label in labels:
            if self.use_python_dialog:
                options.append((str(option_number), label))
                option_number += 1
            else:
                options.append(label)
        return options

    def set_tui_menu_options(self):
        labels = []
        if system.get_runmode() == "binary":
            status = utils.compare_logos_linux_installer_version(self)
            if status == utils.VersionComparison.OUT_OF_DATE:
                labels.append(f"Update {constants.APP_NAME}")
            elif status == utils.VersionComparison.UP_TO_DATE:
                # logging.debug("Logos Linux Installer is up-to-date.")
                pass
            elif status == utils.VersionComparison.DEVELOPMENT:
                # logging.debug("Logos Linux Installer is newer than the latest release.")  # noqa: E501
                pass
            else:
                logging.error(f"Unknown result: {status}")

        if self.is_installed():
            if self.logos.logos_state in [logos.State.STARTING, logos.State.RUNNING]:  # noqa: E501
                run = f"Stop {self.conf.faithlife_product}"
            elif self.logos.logos_state in [logos.State.STOPPING, logos.State.STOPPED]:  # noqa: E501
                run = f"Run {self.conf.faithlife_product}"

            if self.logos.indexing_state == logos.State.RUNNING:
                indexing = "Stop Indexing"
            elif self.logos.indexing_state == logos.State.STOPPED:
                indexing = "Run Indexing"
            labels_default = [run, indexing]
        else:
            labels_default = ["Install Logos Bible Software"]
        labels.extend(labels_default)

        labels_support = ["Utilities →"]
        labels.extend(labels_support)

        labels_options = ["Change Color Scheme"]
        labels.extend(labels_options)

        labels.append("Exit")

        options = self.which_dialog_options(labels)

        return options

    def set_renderer_menu_options(self):
        labels = []
        labels_support = ["gdi", "gl", "vulkan"]
        labels.extend(labels_support)

        labels.append("Return to Main Menu")

        options = self.which_dialog_options(labels)

        return options

    def set_win_ver_menu_options(self):
        labels = []
        labels_support = ["vista", "win7", "win8", "win10", "win11"]
        labels.extend(labels_support)

        labels.append("Return to Main Menu")

        options = self.which_dialog_options(labels)

        return options

    def set_utilities_menu_options(self):
        labels = []
        if self.is_installed():
            labels_catalog = [
                "Remove Library Catalog",
                "Remove All Index Files",
                "Install ICU",
            ]
            labels.extend(labels_catalog)

        labels_utilities = ["Install Dependencies", "Edit Config", "Reload Config"]
        labels.extend(labels_utilities)

        if self.is_installed():
            labels_utils_installed = [
                "Change Logos Release Channel",
                f"Change {constants.APP_NAME} Release Channel",
                # "Back Up Data",
                # "Restore Data"
            ]
            labels.extend(labels_utils_installed)

        label = (
            "Enable Logging"
            if self.conf.faithlife_product_logging
            else "Disable Logging"
        )  # noqa: E501
        labels.append(label)

        labels.append("Return to Main Menu")

        options = self.which_dialog_options(labels)

        return options

    def stack_menu(
        self,
        screen_id,
        queue,
        event,
        question,
        options,
        height=None,
        width=None,
        menu_height=8,
    ):  # noqa: E501
        if self.use_python_dialog:
            utils.append_unique(
                self.tui_screens,
                tui_screen.MenuDialog(
                    self,
                    screen_id,
                    queue,
                    event,
                    question,
                    options,
                    height,
                    width,
                    menu_height,
                ),
            )  # noqa: E501
        else:
            utils.append_unique(
                self.tui_screens,
                tui_screen.MenuScreen(
                    self,
                    screen_id,
                    queue,
                    event,
                    question,
                    options,
                    height,
                    width,
                    menu_height,
                ),
            )  # noqa: E501

    def stack_input(self, screen_id, queue, event, question: str, default):
        if self.use_python_dialog:
            utils.append_unique(
                self.tui_screens,
                tui_screen.InputDialog(
                    self, screen_id, queue, event, question, default
                ),
            )  # noqa: E501
        else:
            utils.append_unique(
                self.tui_screens,
                tui_screen.InputScreen(
                    self, screen_id, queue, event, question, default
                ),
            )  # noqa: E501

    def stack_password(
        self, screen_id, queue, event, question, default=""
    ):  # noqa: E501
        if self.use_python_dialog:
            utils.append_unique(
                self.tui_screens,
                tui_screen.PasswordDialog(
                    self, screen_id, queue, event, question, default
                ),
            )  # noqa: E501
        else:
            utils.append_unique(
                self.tui_screens,
                tui_screen.PasswordScreen(
                    self, screen_id, queue, event, question, default
                ),
            )  # noqa: E501

    def stack_confirm(
        self,
        screen_id,
        queue,
        event,
        question,
        no_text,
        secondary,
        options=["Yes", "No"],
    ):  # noqa: E501
        if self.use_python_dialog:
            yes_label = options[0]
            no_label = options[1]
            utils.append_unique(
                self.tui_screens,
                tui_screen.ConfirmDialog(
                    self,
                    screen_id,
                    queue,
                    event,
                    question,
                    no_text,
                    secondary,
                    yes_label=yes_label,
                    no_label=no_label,
                ),
            )  # noqa: E501
        else:
            utils.append_unique(
                self.tui_screens,
                tui_screen.ConfirmScreen(
                    self, screen_id, queue, event, question, no_text, secondary, options
                ),
            )  # noqa: E501

    def stack_text(
        self, screen_id, queue, event, text, wait=False, percent=None
    ):  # noqa: E501
        if self.use_python_dialog:
            utils.append_unique(
                self.tui_screens,
                tui_screen.TextDialog(
                    self, screen_id, queue, event, text, wait, percent
                ),
            )  # noqa: E501
        else:
            utils.append_unique(
                self.tui_screens,
                tui_screen.TextScreen(self, screen_id, queue, event, text, wait),
            )  # noqa: E501

    def stack_tasklist(
        self, screen_id, queue, event, text, elements, percent
    ):  # noqa: E501
        logging.debug(f"Elements stacked: {elements}")
        if self.use_python_dialog:
            utils.append_unique(
                self.tui_screens,
                tui_screen.TaskListDialog(
                    self, screen_id, queue, event, text, elements, percent
                ),
            )  # noqa: E501
        else:
            # TODO: curses version
            pass

    def stack_buildlist(
        self,
        screen_id,
        queue,
        event,
        question,
        options,
        height=None,
        width=None,
        list_height=None,
    ):  # noqa: E501
        if self.use_python_dialog:
            utils.append_unique(
                self.tui_screens,
                tui_screen.BuildListDialog(
                    self,
                    screen_id,
                    queue,
                    event,
                    question,
                    options,
                    height,
                    width,
                    list_height,
                ),
            )  # noqa: E501
        else:
            # TODO
            pass

    def stack_checklist(
        self,
        screen_id,
        queue,
        event,
        question,
        options,
        height=None,
        width=None,
        list_height=None,
    ):
        if self.use_python_dialog:
            utils.append_unique(
                self.tui_screens,
                tui_screen.CheckListDialog(
                    self,
                    screen_id,
                    queue,
                    event,
                    question,
                    options,
                    height,
                    width,
                    list_height,
                ),
            )  # noqa: E501
        else:
            # TODO
            pass

    def update_tty_dimensions(self):
        self.window_height, self.window_width = self.stdscr.getmaxyx()

    def get_menu_window(self):
        return self.menu_window


def control_panel_app(stdscr: curses.window, ephemeral_config: EphemeralConfiguration):
    os.environ.setdefault("ESCDELAY", "100")
    TUI(stdscr, ephemeral_config).run()
