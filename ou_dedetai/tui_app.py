import logging
import os
import signal
import threading
import time
import curses
from pathlib import Path
from queue import Queue
from typing import Optional

from ou_dedetai.app import App
from ou_dedetai.constants import PROMPT_OPTION_DIRECTORY, PROMPT_OPTION_FILE
from ou_dedetai.config import EphemeralConfiguration

from . import config
from . import control
from . import constants
from . import installer
from . import logos
from . import msg
from . import network
from . import system
from . import tui_curses
from . import tui_screen
from . import utils
from . import wine

console_message = ""


# TODO: Fix hitting cancel in Dialog Screens; currently crashes program.
class TUI(App):
    def __init__(self, stdscr: curses.window, ephemeral_config: EphemeralConfiguration):
        super().__init__(ephemeral_config)
        self.stdscr = stdscr
        self.title = f"Welcome to {constants.APP_NAME} {constants.LLI_CURRENT_VERSION} ({self.conf.app_release_channel})"  # noqa: E501
        self.subtitle = f"Logos Version: {self.conf.installed_faithlife_product_release} ({self.conf.faithlife_product_release_channel})"  # noqa: E501
        # else:
        #    self.title = f"Welcome to {constants.APP_NAME} ({constants.LLI_CURRENT_VERSION})"  # noqa: E501
        self.console_message = "Starting TUI…"
        self.llirunning = True
        self.active_progress = False
        self.logos = logos.LogosManager(app=self)
        self.tmp = ""

        # Generic ask/response events/threads
        self.ask_answer_queue = Queue()
        self.ask_answer_event = threading.Event()

        # Queues
        self.main_thread = threading.Thread()
        self.get_q = Queue()
        self.get_e = threading.Event()
        self.status_q = Queue()
        self.status_e = threading.Event()
        self.progress_q = Queue()
        self.progress_e = threading.Event()
        self.todo_q = Queue()
        self.todo_e = threading.Event()
        self.screen_q = Queue()
        self.choice_q = Queue()
        self.switch_q = Queue()

        # Install and Options
        self.manualinstall_q = Queue()
        self.manualinstall_e = threading.Event()
        self.deps_q = Queue()
        self.deps_e = threading.Event()
        self.finished_q = Queue()
        self.finished_e = threading.Event()
        self.config_q = Queue()
        self.config_e = threading.Event()
        self.confirm_q = Queue()
        self.confirm_e = threading.Event()
        self.password_q = Queue()
        self.password_e = threading.Event()
        self.appimage_q = Queue()
        self.appimage_e = threading.Event()
        self.install_icu_q = Queue()
        self.install_logos_q = Queue()
        self.install_logos_e = threading.Event()

        self.terminal_margin = 0
        self.resizing = False
        # These two are updated in set_window_dimensions
        self.console_log_lines = 0
        self.options_per_page = 0

        # Window and Screen Management
        self.tui_screens = []
        self.menu_options = []
        self.window_height = self.window_width = self.console = self.menu_screen = self.active_screen = None
        self.main_window_ratio = self.main_window_ratio = self.menu_window_ratio = self.main_window_min = None
        self.menu_window_min = self.main_window_height = self.menu_window_height = self.main_window = None
        self.menu_window = self.resize_window = None
        self.set_window_dimensions()

    def set_window_dimensions(self):
        self.update_tty_dimensions()
        curses.resizeterm(self.window_height, self.window_width)
        self.main_window_ratio = 0.25
        if config.console_log:
            min_console_height = len(tui_curses.wrap_text(self, config.console_log[-1]))
        else:
            min_console_height = 2
        self.main_window_min = len(tui_curses.wrap_text(self, self.title)) + len(
            tui_curses.wrap_text(self, self.subtitle)) + min_console_height
        self.menu_window_ratio = 0.75
        self.menu_window_min = 3
        self.main_window_height = max(int(self.window_height * self.main_window_ratio), self.main_window_min)
        self.menu_window_height = max(self.window_height - self.main_window_height, int(self.window_height * self.menu_window_ratio), self.menu_window_min)
        self.console_log_lines = max(self.main_window_height - self.main_window_min, 1)
        self.options_per_page = max(self.window_height - self.main_window_height - 6, 1)
        self.main_window = curses.newwin(self.main_window_height, curses.COLS, 0, 0)
        self.menu_window = curses.newwin(self.menu_window_height, curses.COLS, self.main_window_height + 1, 0)
        resize_lines = tui_curses.wrap_text(self, "Screen too small.")
        self.resize_window = curses.newwin(len(resize_lines) + 1, curses.COLS, 0, 0)

    @staticmethod
    def set_curses_style():
        curses.start_color()
        curses.use_default_colors()
        curses.init_color(curses.COLOR_BLUE, 0, 510, 1000) # Logos Blue
        curses.init_color(curses.COLOR_CYAN, 906, 906, 906) # Logos Gray
        curses.init_color(curses.COLOR_WHITE, 988, 988, 988) # Logos White
        curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_CYAN)
        curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_WHITE)
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLUE)
        curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_BLUE)
        curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_BLACK)

    def set_curses_colors(self):
        if self.conf.curses_colors == "Logos":
            self.stdscr.bkgd(' ', curses.color_pair(3))
            self.main_window.bkgd(' ', curses.color_pair(3))
            self.menu_window.bkgd(' ', curses.color_pair(3))
        elif self.conf.curses_colors == "Light":
            self.stdscr.bkgd(' ', curses.color_pair(6))
            self.main_window.bkgd(' ', curses.color_pair(6))
            self.menu_window.bkgd(' ', curses.color_pair(6))
        elif self.conf.curses_colors == "Dark":
            self.stdscr.bkgd(' ', curses.color_pair(7))
            self.main_window.bkgd(' ', curses.color_pair(7))
            self.menu_window.bkgd(' ', curses.color_pair(7))

    def update_windows(self):
        if isinstance(self.active_screen, tui_screen.CursesScreen):
            self.main_window.erase()
            self.menu_window.erase()
            self.stdscr.timeout(100)
            self.console.display()

    def clear(self):
        self.stdscr.clear()
        self.main_window.clear()
        self.menu_window.clear()
        self.resize_window.clear()

    def refresh(self):
        self.main_window.noutrefresh()
        self.menu_window.noutrefresh()
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

            self.console = tui_screen.ConsoleScreen(self, 0, self.status_q, self.status_e, self.title, self.subtitle, 0)
            self.menu_screen = tui_screen.MenuScreen(self, 0, self.status_q, self.status_e,
                                                         "Main Menu", self.set_tui_menu_options(dialog=False))
            #self.menu_screen = tui_screen.MenuDialog(self, 0, self.status_q, self.status_e, "Main Menu",
            #                                         self.set_tui_menu_options(dialog=True))
            self.refresh()
        except curses.error as e:
            logging.error(f"Curses error in init_curses: {e}")
        except Exception as e:
            self.end_curses()
            logging.error(f"An error occurred in init_curses(): {e}")
            raise

    def _config_updated_hook(self):
        self.set_curses_colors()

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

    def _install_complete_hook(self):
        # Update the contents going back to the start
        self.update_main_window_contents()

    def update_main_window_contents(self):
        self.clear()
        self.title = f"Welcome to {constants.APP_NAME} {constants.LLI_CURRENT_VERSION} ({self.conf.app_release_channel})"  # noqa: E501
        self.subtitle = f"Logos Version: {self.conf.installed_faithlife_product_release} ({self.conf.faithlife_product_release_channel})"  # noqa: E501
        self.console = tui_screen.ConsoleScreen(self, 0, self.status_q, self.status_e, self.title, self.subtitle, 0)  # noqa: E501
        self.menu_screen.set_options(self.set_tui_menu_options(dialog=False))
        # self.menu_screen.set_options(self.set_tui_menu_options(dialog=True))
        self.switch_q.put(1)
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
        msg.status("Window resized.", self)
        self.resizing = False

    def signal_resize(self, signum, frame):
        self.resize_curses()
        self.choice_q.put("resize")

        if config.use_python_dialog:
            if isinstance(self.active_screen, tui_screen.TextDialog) and self.active_screen.text == "Screen Too Small":
                self.choice_q.put("Return to Main Menu")
        else:
            if self.active_screen.get_screen_id == 14:
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
                tui_curses.write_line(self, self.resize_window, i, margin, line, self.window_width - self.terminal_margin, curses.A_BOLD)
        self.refresh()

    def display(self):
        signal.signal(signal.SIGWINCH, self.signal_resize)
        signal.signal(signal.SIGINT, self.end)
        msg.initialize_tui_logging()
        msg.status(self.console_message, self)
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
                            self.active_screen.get_screen_id(),
                            self.choice_q.get())

                    if self.screen_q.qsize() > 0:
                        self.screen_q.get()
                        self.switch_q.put(1)

                    if self.switch_q.qsize() > 0:
                        self.switch_q.get()
                        self.switch_screen(config.use_python_dialog)

                    if len(self.tui_screens) == 0:
                        self.active_screen = self.menu_screen
                    else:
                        self.active_screen = self.tui_screens[-1]

                    if not isinstance(self.active_screen, tui_screen.DialogScreen):
                        run_monitor, last_time = utils.stopwatch(last_time, 2.5)
                        if run_monitor:
                            self.logos.monitor()
                            self.menu_screen.set_options(self.set_tui_menu_options(dialog=False))

                    if isinstance(self.active_screen, tui_screen.CursesScreen):
                        self.refresh()
            elif self.window_width >= 10:
                if self.window_width < 10:
                    self.terminal_margin = 1  # Avoid drawing errors on very small screens
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
        utils.start_thread(self.get_waiting, config.use_python_dialog, screen_id=15)

    def choice_processor(self, stdscr, screen_id, choice):
        screen_actions = {
            0: self.main_menu_select,
            1: self.custom_appimage_select,
            2: self.handle_ask_response,
            3: self.handle_ask_file_response,
            4: self.handle_ask_directory_response,
            8: self.waiting,
            10: self.waiting_releases,
            11: self.winetricks_menu_select,
            12: self.logos.start,
            13: self.waiting_finish,
            14: self.waiting_resize,
            15: self.password_prompt,
            16: self.install_dependencies_confirm,
            17: self.manual_install_confirm,
            18: self.utilities_menu_select,
            19: self.renderer_select,
            20: self.win_ver_logos_select,
            21: self.win_ver_index_select,
            24: self.confirm_restore_dir,
            25: self.choose_restore_dir
        }

        # Capture menu exiting before processing in the rest of the handler
        if screen_id != 0 and (choice == "Return to Main Menu" or choice == "Exit"):
            self.reset_screen()
            self.switch_q.put(1)
            #FIXME: There is some kind of graphical glitch that activates on returning to Main Menu,
            # but not from all submenus.
            # Further, there appear to be issues with how the program exits on Ctrl+C as part of this.
        else:
            action = screen_actions.get(screen_id)
            if action:
                action(choice)
            else:
                pass

    def reset_screen(self):
        self.active_screen.running = 0
        self.active_screen.choice = "Processing"

    def go_to_main_menu(self):
        self.menu_screen.choice = "Processing"
        self.choice_q.put("Return to Main Menu")

    def main_menu_select(self, choice):
        if choice is None or choice == "Exit":
            msg.logos_warn("Exiting installation.")
            self.tui_screens = []
            self.llirunning = False
        elif choice.startswith("Install"):
            self.reset_screen()
            self.installer_step = 0
            self.installer_step_count = 0
            utils.start_thread(
                installer.install,
                daemon_bool=True,
                app=self,
            )
        elif choice.startswith(f"Update {constants.APP_NAME}"):
            utils.update_to_latest_lli_release(self)
        elif choice == f"Run {self.conf.faithlife_product}":
            self.reset_screen()
            self.logos.start()
            self.menu_screen.set_options(self.set_tui_menu_options(dialog=False))
            self.switch_q.put(1)
        elif choice == f"Stop {self.conf.faithlife_product}":
            self.reset_screen()
            self.logos.stop()
            self.menu_screen.set_options(self.set_tui_menu_options(dialog=False))
            self.switch_q.put(1)
        elif choice == "Run Indexing":
            self.active_screen.running = 0
            self.active_screen.choice = "Processing"
            self.logos.index()
        elif choice == "Remove Library Catalog":
            self.active_screen.running = 0
            self.active_screen.choice = "Processing"
            control.remove_library_catalog(self)
        elif choice.startswith("Winetricks"):
            self.reset_screen()
            self.screen_q.put(self.stack_menu(11, self.todo_q, self.todo_e, "Winetricks Menu",
                                              self.set_winetricks_menu_options(), dialog=config.use_python_dialog))
            self.choice_q.put("0")
        elif choice.startswith("Utilities"):
            self.reset_screen()
            self.screen_q.put(self.stack_menu(18, self.todo_q, self.todo_e, "Utilities Menu",
                                              self.set_utilities_menu_options(), dialog=config.use_python_dialog))
            self.choice_q.put("0")
        elif choice == "Change Color Scheme":
            self.conf.cycle_curses_color_scheme()
            msg.status("Changing color scheme", self)
            self.reset_screen()
            utils.write_config(config.CONFIG_FILE)

    def winetricks_menu_select(self, choice):
        if choice == "Download or Update Winetricks":
            self.reset_screen()
            control.set_winetricks(self)
            self.go_to_main_menu()
        elif choice == "Run Winetricks":
            self.reset_screen()
            wine.run_winetricks(self)
            self.go_to_main_menu()
        elif choice == "Install d3dcompiler":
            self.reset_screen()
            wine.install_d3d_compiler(self)
        elif choice == "Install Fonts":
            self.reset_screen()
            wine.install_fonts(self)
            self.go_to_main_menu()
        elif choice == "Set Renderer":
            self.reset_screen()
            self.screen_q.put(self.stack_menu(19, self.todo_q, self.todo_e,
                                              "Choose Renderer",
                                              self.set_renderer_menu_options(),
                                              dialog=config.use_python_dialog))
            self.choice_q.put("0")
        elif choice == "Set Windows Version for Logos":
            self.reset_screen()
            self.screen_q.put(self.stack_menu(20, self.todo_q, self.todo_e,
                                              "Set Windows Version for Logos",
                                              self.set_win_ver_menu_options(),
                                              dialog=config.use_python_dialog))
            self.choice_q.put("0")
        elif choice == "Set Windows Version for Indexer":
            self.reset_screen()
            self.screen_q.put(self.stack_menu(21, self.todo_q, self.todo_e,
                                              "Set Windows Version for Indexer",
                                              self.set_win_ver_menu_options(),
                                              dialog=config.use_python_dialog))
            self.choice_q.put("0")

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
        elif choice == "Change Logos Release Channel":
            self.reset_screen()
            self.conf.toggle_faithlife_product_release_channel()
            self.update_main_window_contents()
            self.go_to_main_menu()
        elif choice == f"Change {constants.APP_NAME} Release Channel":
            self.reset_screen()
            self.conf.toggle_installer_release_channel()
            network.set_logoslinuxinstaller_latest_release_config()
            self.update_main_window_contents()
            self.go_to_main_menu()
        elif choice == "Install Dependencies":
            self.reset_screen()
            msg.status("Checking dependencies…", self)
            self.update_windows()
            utils.install_dependencies(self)
            self.go_to_main_menu()
        elif choice == "Back Up Data":
            self.reset_screen()
            utils.start_thread(self.do_backup)
        elif choice == "Restore Data":
            self.reset_screen()
            utils.start_thread(self.do_backup)
        elif choice == "Update to Latest AppImage":
            self.reset_screen()
            utils.update_to_latest_recommended_appimage(self)
            self.go_to_main_menu()
        elif choice == "Set AppImage":
            # TODO: Allow specifying the AppImage File
            appimages = utils.find_appimage_files()
            appimage_choices = [["AppImage", filename, "AppImage of Wine64"] for filename in
                                appimages]  # noqa: E501
            appimage_choices.extend(["Input Custom AppImage", "Return to Main Menu"])
            self.menu_options = appimage_choices
            question = "Which AppImage should be used?"
            self.screen_q.put(self.stack_menu(1, self.appimage_q, self.appimage_e, question, appimage_choices))
        elif choice == "Install ICU":
            self.reset_screen()
            wine.enforce_icu_data_files()
            self.go_to_main_menu()
        elif choice.endswith("Logging"):
            self.reset_screen()
            wine.switch_logging()
            self.go_to_main_menu()

    def custom_appimage_select(self, choice):
        #FIXME
        if choice == "Input Custom AppImage":
            appimage_filename = tui_curses.get_user_input(self, "Enter AppImage filename: ", "")
        else:
            appimage_filename = choice
        self.conf.wine_appimage_path = appimage_filename
        utils.set_appimage_symlink(self)
        self.menu_screen.choice = "Processing"
        self.appimage_q.put(self.conf.wine_appimage_path)
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

    def install_dependencies_confirm(self, choice):
        if choice:
            if choice == "No":
                self.go_to_main_menu()
            else:
                self.menu_screen.choice = "Processing"
                self.confirm_e.set()
                self.screen_q.put(self.stack_text(13, self.todo_q, self.todo_e,
                                                  "Installing dependencies…\n", wait=True,
                                                  dialog=config.use_python_dialog))

    def renderer_select(self, choice):
        if choice in ["gdi", "gl", "vulkan"]:
            self.reset_screen()
            wine.set_renderer(self, choice)
            msg.status(f"Changed renderer to {choice}.", self)
            self.go_to_main_menu()

    def win_ver_logos_select(self, choice):
        if choice in ["vista", "win7", "win8", "win10", "win11"]:
            self.reset_screen()
            wine.set_win_version(self, "logos", choice)
            msg.status(f"Changed Windows version for Logos to {choice}.", self)
            self.go_to_main_menu()

    def win_ver_index_select(self, choice):
        if choice in ["vista", "win7", "win8", "win10", "win11"]:
            self.reset_screen()
            wine.set_win_version(self, "indexer", choice)
            msg.status(f"Changed Windows version for Indexer to {choice}.", self)
            self.go_to_main_menu()

    def manual_install_confirm(self, choice):
        if choice:
            if choice == "Continue":
                self.menu_screen.choice = "Processing"
                self.manualinstall_e.set()
                self.screen_q.put(self.stack_text(13, self.todo_q, self.todo_e,
                                                  "Installing dependencies…\n", wait=True,
                                                  dialog=config.use_python_dialog))

    def switch_screen(self, dialog):
        if self.active_screen is not None and self.active_screen != self.menu_screen and len(self.tui_screens) > 0:
            self.tui_screens.pop(0)
        if self.active_screen == self.menu_screen:
            self.menu_screen.choice = "Processing"
            self.menu_screen.running = 0
        if isinstance(self.active_screen, tui_screen.CursesScreen):
            self.clear()

    _exit_option = "Return to Main Menu"

    def _ask(self, question: str, options: list[str] | str) -> Optional[str]:
        if isinstance(options, str):
            answer = options

        if isinstance(options, list):
            options = self.which_dialog_options(options, config.use_python_dialog)
            self.menu_options = options
            self.screen_q.put(self.stack_menu(2, Queue(), threading.Event(), question, options, dialog=config.use_python_dialog))

            # Now wait for it to complete
            self.ask_answer_event.wait()
            answer = self.ask_answer_queue.get()

        if answer  == PROMPT_OPTION_DIRECTORY or answer ==  PROMPT_OPTION_FILE:
            stack_index = 3 if answer == PROMPT_OPTION_FILE else 4
            self.screen_q.put(self.stack_input(stack_index, Queue(), threading.Event(), question,
                                               os.path.expanduser(f"~/"), dialog=config.use_python_dialog))
            # Now wait for it to complete
            self.ask_answer_event.wait()
            answer = self.ask_answer_queue.get()

        return answer

    def handle_ask_response(self, choice: Optional[str]):
        if choice is not None:
            self.ask_answer_queue.put(choice)
            self.ask_answer_event.set()
            self.switch_screen(config.use_python_dialog)

    def handle_ask_file_response(self, choice: Optional[str]):
        # XXX: can there be some sort of feedback if this file path isn't valid?
        if choice is not None and Path(choice).exists() and Path(choice).is_file():
            self.handle_ask_response(choice)

    def handle_ask_directory_response(self, choice: Optional[str]):
        # XXX: can there be some sort of feedback if this directory path isn't valid?
        if choice is not None and Path(choice).exists() and Path(choice).is_dir():
            self.handle_ask_response(choice)

    def status(self, message: str, percent: int | None = None):
        # XXX: update some screen? Something like get_waiting?
        pass

    def _install_started_hook(self):
        self.get_waiting(self, config.use_python_dialog)

    def get_waiting(self, dialog, screen_id=8):
        text = ["Install is running…\n"]
        processed_text = utils.str_array_to_string(text)
        
        percent = installer.get_progress_pct(self.installer_step, self.installer_step_count)
        self.screen_q.put(self.stack_text(screen_id, self.status_q, self.status_e, processed_text,
                                          wait=True, percent=percent, dialog=dialog))

    # def get_password(self, dialog):
    #     question = (f"Logos Linux Installer needs to run a command as root. "
    #                 f"Please provide your password to provide escalation privileges.")
    #     self.screen_q.put(self.stack_password(15, self.password_q, self.password_e, question, dialog=dialog))

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
        if self.tmp == 'backup':
            control.backup(self)
        else:
            control.restore(self)
        self.go_to_main_menu()

    def report_waiting(self, text, dialog):
        #self.screen_q.put(self.stack_text(10, self.status_q, self.status_e, text, wait=True, dialog=dialog))
        config.console_log.append(text)

    def which_dialog_options(self, labels, dialog=False):
        options = []
        option_number = 1
        for label in labels:
            if dialog:
                options.append((str(option_number), label))
                option_number += 1
            else:
                options.append(label)
        return options

    def set_tui_menu_options(self, dialog=False):
        labels = []
        if system.get_runmode() == 'binary':
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
            labels_default = [
                run,
                indexing
            ]
        else:
            labels_default = ["Install Logos Bible Software"]
        labels.extend(labels_default)

        labels_support = [
            "Utilities →",
            "Winetricks →"
        ]
        labels.extend(labels_support)

        labels_options = [
            "Change Color Scheme"
        ]
        labels.extend(labels_options)

        labels.append("Exit")

        options = self.which_dialog_options(labels, dialog=False)

        return options

    def set_winetricks_menu_options(self, dialog=False):
        labels = []
        labels_support = [
            "Download or Update Winetricks",
            "Run Winetricks",
            "Install d3dcompiler",
            "Install Fonts",
            "Set Renderer",
            "Set Windows Version for Logos",
            "Set Windows Version for Indexer"
        ]
        labels.extend(labels_support)

        labels.append("Return to Main Menu")

        options = self.which_dialog_options(labels, dialog=False)

        return options

    def set_renderer_menu_options(self, dialog=False):
        labels = []
        labels_support = [
            "gdi",
            "gl",
            "vulkan"
        ]
        labels.extend(labels_support)

        labels.append("Return to Main Menu")

        options = self.which_dialog_options(labels, dialog=False)

        return options

    def set_win_ver_menu_options(self, dialog=False):
        labels = []
        labels_support = [
            "vista",
            "win7",
            "win8",
            "win10",
            "win11"
        ]
        labels.extend(labels_support)

        labels.append("Return to Main Menu")

        options = self.which_dialog_options(labels, dialog=False)

        return options

    def set_utilities_menu_options(self, dialog=False):
        labels = []
        if self.is_installed():
            labels_catalog = [
                "Remove Library Catalog",
                "Remove All Index Files",
                "Install ICU"
            ]
            labels.extend(labels_catalog)

        labels_utilities = [
            "Install Dependencies",
            "Edit Config"
        ]
        labels.extend(labels_utilities)

        if self.is_installed():
            labels_utils_installed = [
                "Change Logos Release Channel",
                f"Change {constants.APP_NAME} Release Channel",
                # "Back Up Data",
                # "Restore Data"
            ]
            labels.extend(labels_utils_installed)

        label = "Enable Logging" if self.conf.faithlife_product_logging else "Disable Logging" #noqa: E501
        labels.append(label)

        labels.append("Return to Main Menu")

        options = self.which_dialog_options(labels, dialog=False)

        return options

    def stack_menu(self, screen_id, queue, event, question, options, height=None, width=None, menu_height=8, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                                tui_screen.MenuDialog(self, screen_id, queue, event, question, options,
                                                      height, width, menu_height))
        else:
            utils.append_unique(self.tui_screens,
                                tui_screen.MenuScreen(self, screen_id, queue, event, question, options,
                                                      height, width, menu_height))

    def stack_input(self, screen_id, queue, event, question, default, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                                tui_screen.InputDialog(self, screen_id, queue, event, question, default))
        else:
            utils.append_unique(self.tui_screens,
                                tui_screen.InputScreen(self, screen_id, queue, event, question, default))

    def stack_password(self, screen_id, queue, event, question, default="", dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                                tui_screen.PasswordDialog(self, screen_id, queue, event, question, default))
        else:
            utils.append_unique(self.tui_screens,
                                tui_screen.PasswordScreen(self, screen_id, queue, event, question, default))

    def stack_confirm(self, screen_id, queue, event, question, no_text, secondary, options=["Yes", "No"], dialog=False):
        if dialog:
            yes_label = options[0]
            no_label = options[1]
            utils.append_unique(self.tui_screens,
                                tui_screen.ConfirmDialog(self, screen_id, queue, event, question, no_text, secondary,
                                                         yes_label=yes_label, no_label=no_label))
        else:
            utils.append_unique(self.tui_screens,
                                tui_screen.ConfirmScreen(self, screen_id, queue, event, question, no_text, secondary,
                                                         options))

    def stack_text(self, screen_id, queue, event, text, wait=False, percent=None, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                                tui_screen.TextDialog(self, screen_id, queue, event, text, wait, percent))
        else:
            utils.append_unique(self.tui_screens, tui_screen.TextScreen(self, screen_id, queue, event, text, wait))

    def stack_tasklist(self, screen_id, queue, event, text, elements, percent, dialog=False):
        logging.debug(f"Elements stacked: {elements}")
        if dialog:
            utils.append_unique(self.tui_screens, tui_screen.TaskListDialog(self, screen_id, queue, event, text,
                                                                            elements, percent))
        else:
            #TODO: curses version
            pass

    def stack_buildlist(self, screen_id, queue, event, question, options, height=None, width=None, list_height=None, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                            tui_screen.BuildListDialog(self, screen_id, queue, event, question, options,
                                                       height, width, list_height))
        else:
            # TODO
            pass

    def stack_checklist(self, screen_id, queue, event, question, options,
                        height=None, width=None, list_height=None, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                                tui_screen.CheckListDialog(self, screen_id, queue, event, question, options,
                                                           height, width, list_height))
        else:
            # TODO
            pass

    def update_tty_dimensions(self):
        self.window_height, self.window_width = self.stdscr.getmaxyx()

    def get_main_window(self):
        return self.main_window

    def get_menu_window(self):
        return self.menu_window


def control_panel_app(stdscr: curses.window, ephemeral_config: EphemeralConfiguration):
    os.environ.setdefault('ESCDELAY', '100')
    TUI(stdscr, ephemeral_config).run()
