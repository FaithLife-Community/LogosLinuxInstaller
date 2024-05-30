import logging
import os
import sys
import signal
import threading
import time
import curses
from pathlib import Path
from queue import Queue

import config
import control
import tui_curses
import tui_dialog
import tui_screen
import installer
import msg
import utils
import wine

console_message = ""


class TUI():
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.title = f"Welcome to Logos on Linux ({config.LLI_CURRENT_VERSION})"
        self.console_message = "Starting TUI…"
        self.choice = "Processing"
        self.active_progress = False

        # Queues
        self.main_thread = threading.Thread()
        self.get_q = Queue()
        self.get_e = threading.Event()
        self.input_q = Queue()
        self.input_e = threading.Event()
        self.status_q = Queue()
        self.status_e = threading.Event()
        self.progress_q = Queue()
        self.progress_e = threading.Event()
        self.todo_q = Queue()
        self.todo_e = threading.Event()

        # Install and Options
        self.product_q = Queue()
        self.product_e = threading.Event()
        self.version_q = Queue()
        self.version_e = threading.Event()
        self.releases_q = Queue()
        self.releases_e = threading.Event()
        self.release_q = Queue()
        self.release_e = threading.Event()
        self.installdir_q = Queue()
        self.installdir_e = threading.Event()
        self.wine_q = Queue()
        self.wine_e = threading.Event()
        self.tricksbin_q = Queue()
        self.tricksbin_e = threading.Event()
        self.finished_q = Queue()
        self.finished_e = threading.Event()
        self.config_q = Queue()
        self.config_e = threading.Event()
        self.appimage_q = Queue()
        self.appimage_e = threading.Event()

        # Window and Screen Management
        self.window_height = ""
        self.window_width = ""
        self.update_tty_dimensions()
        self.main_window_height = 9
        self.menu_window_height = 14
        self.tui_screens = []
        self.menu_options = []
        self.threads = []
        self.threads_started = []
        self.main_window = curses.newwin(self.main_window_height, curses.COLS, 0, 0)
        self.menu_window = curses.newwin(self.menu_window_height, curses.COLS, 9, 0)
        self.console = None
        self.menu_screen = None
        self.active_screen = None

    def init_curses(self):
        if curses.has_colors():
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
            self.stdscr.bkgd(' ', curses.color_pair(3))
            self.main_window.bkgd(' ', curses.color_pair(3))
            self.menu_window.bkgd(' ', curses.color_pair(3))

        curses.curs_set(0)
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)

        self.console = tui_screen.ConsoleScreen(self, 0, self.status_q, self.status_e, self.title)
        self.menu_screen = tui_screen.MenuScreen(self, 0, self.status_q, self.status_e, "Main Menu", self.set_tui_menu_options(curses=True))

        self.main_window.noutrefresh()
        self.menu_window.noutrefresh()
        curses.doupdate()

    def end_curses(self):
        self.stdscr.keypad(False)
        self.stdscr.clear()
        self.main_window.clear()
        self.menu_window.clear()
        curses.nocbreak()
        curses.echo()
        curses.endwin()

    def end(self, signal, frame):
        logging.debug("Exiting…")
        self.stdscr.clear()
        curses.endwin()
        for thread in self.threads_started:
            thread.join()

        sys.exit(0)

    def resize_curses(self):
        curses.endwin()
        self.stdscr = curses.initscr()
        curses.curs_set(0)
        self.stdscr.clear()
        self.stdscr.noutrefresh()
        self.update_tty_dimensions()
        self.main_window = curses.newwin(self.main_window_height, curses.COLS, 0, 0)
        self.console = tui_screen.ConsoleScreen(self.main_window, 0, self.status_q, self.status_e, self.title)
        self.menu_window = curses.newwin(self.menu_window_height, curses.COLS, 7, 0)
        self.main_window.noutrefresh()
        self.menu_window.noutrefresh()
        curses.doupdate()
        msg.status("Resizing window.", self)

    def display(self):
        signal.signal(signal.SIGINT, self.end)
        msg.initialize_curses_logging(self.stdscr)
        msg.status(self.console_message, self)

        while True:
            if len(self.tui_screens) > 0:
                self.active_screen = self.tui_screens[-1]
            else:
                self.active_screen = self.menu_screen

            if isinstance(self.active_screen, tui_screen.CursesScreen):
                self.main_window.erase()
                self.menu_window.erase()
                self.stdscr.timeout(100)
                self.console.display()

            self.active_screen.display()

            if (not isinstance(self.active_screen, tui_screen.TextScreen)
                    and not isinstance(self.active_screen, tui_screen.TextDialog)):
                self.choice_processor(
                    self.menu_window,
                    self.active_screen.get_screen_id(),
                    self.active_screen.get_choice())
                self.choice = "Processing"  # Reset for next round

            if isinstance(self.active_screen, tui_screen.CursesScreen):
                self.main_window.noutrefresh()
                self.menu_window.noutrefresh()

    def run(self):
        self.init_curses()

        self.display()

        self.end_curses()

        signal.signal(signal.SIGINT, self.end)

    def task_processor(self, evt=None, task=None):
        if task == 'FLPRODUCT':
            utils.start_thread(self.get_product)
        elif task == 'TARGETVERSION':
            utils.start_thread(self.get_version)
        elif task == 'LOGOS_RELEASE_VERSION':
            utils.start_thread(self.get_release)
        elif task == 'INSTALLDIR':
            utils.start_thread(self.get_installdir)
        elif task == 'WINE_EXE':
            utils.start_thread(self.get_wine)
        elif task == 'WINETRICKSBIN':
            utils.start_thread(self.get_winetricksbin)
        elif task == 'INSTALLING':
            utils.start_thread(self.get_waiting)
        elif task == 'CONFIG':
            utils.start_thread(self.get_config)
        elif task == 'DONE':
            self.finish_install()
        elif task == 'TUI-RESIZE':
            self.resize_curses()
        elif task == 'TUI-UPDATE-MENU':
            self.menu_screen.set_options(self.set_tui_menu_options(curses=True))

    def choice_processor(self, stdscr, screen_id, choice):
        if choice == "Processing":
            pass
        elif screen_id != 0 and (choice == "Return to Main Menu" or choice == "Exit"):
            msg.logos_warn("Exiting installation.")
            self.tui_screens = []
        elif screen_id == 0:
            if choice is None or choice == "Exit":
                sys.exit(0)
            elif choice.startswith("Install"):
                utils.start_thread(installer.ensure_launcher_shortcuts, True, self)
            elif choice.startswith("Update Logos Linux Installer"):
                utils.update_to_latest_lli_release()
            elif choice == f"Run {config.FLPRODUCT}":
                wine.run_logos()
            elif choice == "Run Indexing":
                wine.run_indexing()
            elif choice == "Remove Library Catalog":
                control.remove_library_catalog()
            elif choice == "Remove All Index Files":
                control.remove_all_index_files()
            elif choice == "Edit Config":
                control.edit_config()
            elif choice == "Install Dependencies":
                utils.check_dependencies()
            elif choice == "Back up Data":
                control.backup()
            elif choice == "Restore Data":
                control.restore()
            elif choice == "Update to Latest AppImage":
                utils.update_to_latest_recommended_appimage()
            elif choice == "Set AppImage":
                # TODO: Allow specifying the AppImage File
                appimages = utils.find_appimage_files()
                appimage_choices = [["AppImage", filename, "AppImage of Wine64"] for filename in
                                    appimages]  # noqa: E501
                appimage_choices.extend(["Input Custom AppImage", "Return to Main Menu"])
                self.menu_options = appimage_choices
                question = "Which AppImage should be used?"
                self.stack_menu(1, self.appimage_q, self.appimage_e, question, appimage_choices)
            elif choice == "Download or Update Winetricks":
                control.set_winetricks()
            elif choice == "Run Winetricks":
                wine.run_winetricks()
            elif choice.endswith("Logging"):
                wine.switch_logging()
            else:
                msg.logos_error("Unknown menu choice.")
        elif screen_id == 1:
            if choice == "Input Custom AppImage":
                appimage_filename = tui_curses.get_user_input(self, "Enter AppImage filename: ", "")
            else:
                appimage_filename = choice
            config.SELECTED_APPIMAGE_FILENAME = appimage_filename
            utils.set_appimage_symlink()
            self.appimage_q.put(config.SELECTED_APPIMAGE_FILENAME)
            self.appimage_e.set()
        elif screen_id == 2:
            if str(choice).startswith("Logos"):
                logging.info("Installing Logos Bible Software")
                config.FLPRODUCT = "Logos"
                self.product_q.put(config.FLPRODUCT)
                self.product_e.set()
            elif str(choice).startswith("Verbum"):
                logging.info("Installing Verbum Bible Software")
                config.FLPRODUCT = "Verbum"
                self.product_q.put(config.FLPRODUCT)
                self.product_e.set()
        elif screen_id == 3:
            if "10" in choice:
                config.TARGETVERSION = "10"
                self.version_q.put(config.TARGETVERSION)
                self.version_e.set()
            elif "9" in choice:
                config.TARGETVERSION = "9"
                self.version_q.put(config.TARGETVERSION)
                self.version_e.set()
        elif screen_id == 4:
            logging.info(f"Release version: {choice}")
            if choice:
                config.LOGOS_RELEASE_VERSION = choice
                self.release_q.put(config.LOGOS_RELEASE_VERSION)
                self.release_e.set()
        elif screen_id == 5:
            if choice:
                config.INSTALLDIR = choice
                config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"
                self.installdir_q.put(config.INSTALLDIR)
                self.installdir_e.set()
        elif screen_id == 6:
            config.WINEBIN_CODE = choice[0]
            config.WINE_EXE = choice[1]
            if choice:
                self.wine_q.put(config.WINE_EXE)
                self.wine_e.set()
        elif screen_id == 7:
            winetricks_options = utils.get_winetricks_options()
            if choice.startswith("Use"):
                logging.info("Setting winetricks to the local binary…")
                config.WINETRICKSBIN = winetricks_options[0]
                self.tricksbin_q.put(config.WINETRICKSBIN)
                self.tricksbin_e.set()
            elif choice.startswith("Download"):
                self.tricksbin_q.put("Download")
                self.tricksbin_e.set()
        elif screen_id == 8:
            if config.install_finished:
                self.finished_q.put(True)
                self.finished_e.set()
        elif screen_id == 9:
            logging.info("Updating config file.")
            if choice:
                self.config_q.put(choice)
                self.config_e.set()
            self.tui_screens = []

    def get_product(self):
        question = "Choose which FaithLife product the script should install:"  # noqa: E501
        options = [("0", "Logos"), ("1", "Verbum"), ("2", "Exit")]
        self.menu_options = options
        self.stack_menu(2, self.product_q, self.product_e, question, options, dialog=True)
        self.stdscr.clear()

    def get_version(self):
        question = f"Which version of {config.FLPRODUCT} should the script install?"  # noqa: E501
        options = [("0", "10"), ("1", "9"), ("2", "Exit")]
        self.menu_options = options
        self.stack_menu(3, self.version_q, self.version_e, question, options, dialog=True)
        self.tui_screens.pop(0)
        self.stdscr.clear()

    def get_release(self):
        question = f"Which version of {config.FLPRODUCT} {config.TARGETVERSION} do you want to install?"  # noqa: E501
        utils.start_thread(utils.get_logos_releases, True, self)
        self.releases_e.wait()

        if config.TARGETVERSION == '10':
            options = self.releases_q.get()
        elif config.TARGETVERSION == '9':
            options = self.releases_q.get()

        if options is None:
            msg.logos_error("Failed to fetch LOGOS_RELEASE_VERSION.")
        options.append("Exit")
        enumerated_options = [(str(i), option) for i, option in enumerate(options, start=1)]
        self.menu_options = enumerated_options
        self.stack_menu(4, self.release_q, self.release_e, question, enumerated_options, dialog=True)
        self.tui_screens.pop(0)
        self.stdscr.clear()

    def get_installdir(self):
        default = f"{str(Path.home())}/{config.FLPRODUCT}Bible{config.TARGETVERSION}"  # noqa: E501
        question = f"Where should {config.FLPRODUCT} files be installed to? [{default}]: "  # noqa: E501
        self.stack_input(5, self.installdir_q, self.installdir_e, question, default, dialog=True)
        self.tui_screens.pop(0)
        self.stdscr.clear()

    def get_wine(self):
        logging.info("Creating binary list.")
        question = f"Which Wine AppImage or binary should the script use to install {config.FLPRODUCT} v{config.LOGOS_RELEASE_VERSION} in {config.INSTALLDIR}?"  # noqa: E501
        options = utils.get_wine_options(
            utils.find_appimage_files(),
            utils.find_wine_binary_files()
        )
        max_length = max(len(option) for option in options)
        enumerated_options = [(str(i), option) for i, option in enumerate(options, start=1)]
        max_length += len(str(len(options))) + 10
        self.menu_options = enumerated_options
        self.stack_menu(6, self.wine_q, self.wine_e, question, enumerated_options, width=max_length, dialog=True)
        self.tui_screens.pop(0)
        self.stdscr.clear()

    def get_winetricksbin(self):
        winetricks_options = utils.get_winetricks_options()
        if len(winetricks_options) > 1:
            question = f"Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that {config.FLPRODUCT} requires on Linux."  # noqa: E501
            options = [
                ("1", "Use local winetricks."),
                ("2", "Download winetricks from the Internet.")
            ]
            self.menu_options = options
            self.stack_menu(7, self.tricksbin_q, self.tricksbin_e, question, options, dialog=True)
            self.tui_screens.pop(0)
        self.stdscr.clear()

    def get_waiting(self):
        text = ["Install is running…\n"] + logging.console_log[-2:]
        processed_text = utils.str_array_to_string(text)
        self.stack_text(8, self.status_q, self.status_e, processed_text, True, True)
        self.tui_screens.pop(0)
        self.stdscr.clear()

    def get_config(self):
        question = f"Update config file at {config.CONFIG_FILE}?"
        options = ["Yes", "No"]
        self.menu_options = options
        self.stack_menu(9, self.config_q, self.config_e, question, options, dialog=True)
        self.tui_screens.pop(0)
        self.stdscr.clear()

    def finish_install(self):
        utils.send_task(self, 'TUI-UPDATE-MENU')

    def set_tui_menu_options(self, curses=False):
        options_first = []
        if curses:
            if config.LLI_LATEST_VERSION and utils.get_runmode() == 'binary':
                logging.debug("Checking if Logos Linux Installers needs updated.")  # noqa: E501
                status, error_message = utils.compare_logos_linux_installer_version()  # noqa: E501
                if status == 0:
                    options_first.append("Update Logos Linux Installer")
                elif status == 1:
                    logging.warning("Logos Linux Installer is up-to-date.")
                elif status == 2:
                    logging.warning("Logos Linux Installer is newer than the latest release.")  # noqa: E501
                else:
                    logging.error(f"{error_message}")

            options_support = [
                "Install Dependencies",
                "Download or Update Winetricks",
                "Run Winetricks"
            ]
            options_exit = ["Exit"]

            if utils.file_exists(config.LOGOS_EXE):
                if config.LOGS == "DISABLED":
                    options_support.append("Enable Logging")
                else:
                    options_support.append("Disable Logging")
                options_default = [
                    f"Run {config.FLPRODUCT}",
                    "Run Indexing",
                    "Remove Library Catalog",
                    "Remove All Index Files",
                    "Edit Config",
                    "Back up Data",
                    "Restore Data",
                ]
            else:
                options_default = ["Install Logos Bible Software"]
        else:
            if config.LLI_LATEST_VERSION and utils.get_runmode() == 'binary':
                logging.debug("Checking if Logos Linux Installers needs updated.")  # noqa: E501
                status, error_message = utils.compare_logos_linux_installer_version()  # noqa: E501
                if status == 0:
                    options_first.append("Update Logos Linux Installer")
                elif status == 1:
                    logging.warning("Logos Linux Installer is up-to-date.")
                elif status == 2:
                    logging.warning("Logos Linux Installer is newer than the latest release.")  # noqa: E501
                else:
                    logging.error(f"{error_message}")

            options_support = [
                "Install Dependencies",
                "Download or Update Winetricks",
                "Run Winetricks"
            ]
            options_exit = ["Exit"]

            if utils.file_exists(config.LOGOS_EXE):
                if config.LOGS == "DISABLED":
                    options_support.append(("14", "Enable Logging"))
                else:
                    options_support.append(("14", "Disable Logging"))
                options_default = [
                    ("3", f"Run {config.FLPRODUCT}"),
                    ("4", "Run Indexing"),
                    ("5", "Remove Library Catalog"),
                    ("6", "Remove All Index Files"),
                    ("7", "Edit Config"),
                    ("8", "Back up Data"),
                    ("9", "Restore Data"),
                ]
            else:
                options_default = [("2", "Install Logos Bible Software")]

        options = options_first + options_default + options_support + options_exit  # noqa: E501

        return options

    def stack_menu(self, screen_id, queue, event, question, options, height=None, width=None, menu_height=8, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                            tui_screen.MenuDialog(self, screen_id, queue, event, question, options, height, width, menu_height))
        else:
            utils.append_unique(self.tui_screens,
                            tui_screen.MenuScreen(self, screen_id, queue, event, question, options, height, width, menu_height))

    def stack_input(self, screen_id, queue, event, question, default, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                            tui_screen.InputDialog(self, screen_id, queue, event, question, default))
        else:
            utils.append_unique(self.tui_screens,
                            tui_screen.InputScreen(self, screen_id, queue, event, question, default))

    def stack_confirm(self, screen_id, queue, event, question, options, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                            tui_screen.ConfirmDialog(self, screen_id, queue, event, question, options))
        else:
            #TODO: curses version
            pass

    def stack_text(self, screen_id, queue, event, text, wait, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                                tui_screen.TextDialog(self, screen_id, queue, event, text, wait))
        else:
            utils.append_unique(self.tui_screens,
                            tui_screen.TextScreen(self, screen_id, queue, event, text, wait))

    def update_tty_dimensions(self):
        self.window_height, self.window_width = self.stdscr.getmaxyx()

    def get_main_window(self):
        return self.main_window

    def get_menu_window(self):
        return self.menu_window


def control_panel_app(stdscr):
    os.environ.setdefault('ESCDELAY', '100')
    TUI(stdscr).run()

