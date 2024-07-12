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

# TODO: Fix hitting cancel in Dialog Screens; currently crashes program.

class TUI():
    def __init__(self, stdscr):
        self.stdscr = stdscr
        #if config.current_logos_version is not None:
        self.title = f"Welcome to Logos on Linux ({config.LLI_CURRENT_VERSION})"
        self.subtitle = f"Logos Version: {config.current_logos_version}"
        #else:
        #    self.title = f"Welcome to Logos on Linux ({config.LLI_CURRENT_VERSION})"
        self.console_message = "Starting TUI…"
        self.llirunning = True
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
        self.screen_q = Queue()
        self.choice_q = Queue()
        self.switch_q = Queue()

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
        self.deps_q = Queue()
        self.deps_e = threading.Event()
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
        try:
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

            self.console = tui_screen.ConsoleScreen(self, 0, self.status_q, self.status_e, self.title, self.subtitle, 0)
            self.menu_screen = tui_screen.MenuScreen(self, 0, self.status_q, self.status_e,
                                                     "Main Menu", self.set_tui_menu_options(dialog=False))
            #self.menu_screen = tui_screen.MenuDialog(self, 0, self.status_q, self.status_e, "Main Menu",
            #                                         self.set_tui_menu_options(dialog=True))

            self.main_window.noutrefresh()
            self.menu_window.noutrefresh()
            curses.doupdate()
        except curses.error as e:
            logging.error(f"Curses error in init_curses: {e}")
        except Exception as e:
            self.end_curses()
            logging.error(f"An error occurred in init_curses(): {e}")
            raise

    def end_curses(self):
        try:
            self.stdscr.keypad(False)
            self.stdscr.clear()
            self.main_window.clear()
            self.menu_window.clear()
            curses.nocbreak()
            curses.echo()
        except curses.error as e:
            logging.error(f"Curses error in end_curses: {e}")
        except Exception as e:
            logging.error(f"An error occurred in end_curses(): {e}")

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
        self.active_screen = self.menu_screen

        while self.llirunning:
            if isinstance(self.active_screen, tui_screen.CursesScreen):
                self.main_window.erase()
                self.menu_window.erase()
                self.stdscr.timeout(100)
                self.console.display()

            self.active_screen.display()

            #if (not isinstance(self.active_screen, tui_screen.TextScreen)
            #        and not isinstance(self.active_screen, tui_screen.TextDialog)):
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

            if isinstance(self.active_screen, tui_screen.CursesScreen):
                self.main_window.noutrefresh()
                self.menu_window.noutrefresh()
                curses.doupdate()

    def run(self):
        try:
            self.init_curses()
            self.display()
        finally:
            self.end_curses()
            signal.signal(signal.SIGINT, self.end)

    def task_processor(self, evt=None, task=None):
        if task == 'FLPRODUCT':
            utils.start_thread(self.get_product(config.use_python_dialog))
        elif task == 'TARGETVERSION':
            utils.start_thread(self.get_version(config.use_python_dialog))
        elif task == 'TARGET_RELEASE_VERSION':
            utils.start_thread(self.get_release(config.use_python_dialog))
        elif task == 'INSTALLDIR':
            utils.start_thread(self.get_installdir(config.use_python_dialog))
        elif task == 'WINE_EXE':
            utils.start_thread(self.get_wine(config.use_python_dialog))
        elif task == 'WINETRICKSBIN':
            utils.start_thread(self.get_winetricksbin(config.use_python_dialog))
        elif task == 'INSTALLING':
            utils.start_thread(self.get_waiting(config.use_python_dialog))
        elif task == 'CONFIG':
            utils.start_thread(self.get_config(config.use_python_dialog))
        elif task == 'DONE':
            self.finish_install()
        elif task == 'TUI-RESIZE':
            self.resize_curses()
        elif task == 'TUI-UPDATE-MENU':
            self.menu_screen.set_options(self.set_tui_menu_options(dialog=False))
            #self.menu_screen.set_options(self.set_tui_menu_options(dialog=True))

    def choice_processor(self, stdscr, screen_id, choice):
        if screen_id != 0 and (choice == "Return to Main Menu" or choice == "Exit"):
            self.switch_q.put(1)
            #FIXME: There is some kind of graphical glitch that activates on returning to Main Menu,
            # but not from all submenus.
            # Further, there appear to be issues with how the program exits on Ctrl+C as part of this.
        elif screen_id == 0:
            if choice is None or choice == "Exit":
                msg.logos_warn("Exiting installation.")
                self.tui_screens = []
                self.llirunning = False
                sys.exit(0)
            elif choice.startswith("Install"):
                config.INSTALL_STEPS_COUNT = 0
                config.INSTALL_STEP = 0
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
                appimages = utils.find_appimage_files(utils.which_release())
                appimage_choices = [["AppImage", filename, "AppImage of Wine64"] for filename in
                                    appimages]  # noqa: E501
                appimage_choices.extend(["Input Custom AppImage", "Return to Main Menu"])
                self.menu_options = appimage_choices
                question = "Which AppImage should be used?"
                self.screen_q.put(self.stack_menu(1, self.appimage_q, self.appimage_e, question, appimage_choices))
            elif choice == "Download or Update Winetricks":
                control.set_winetricks()
            elif choice == "Run Winetricks":
                wine.run_winetricks()
            elif choice == "Install d3dcompiler":
                wine.installD3DCompiler()
            elif choice == "Install Fonts":
                wine.installFonts()
            elif choice == "Install ICU":
                wine.installICUDataFiles()
            elif choice.endswith("Logging"):
                wine.switch_logging()
        elif screen_id == 1:
            #FIXME
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
                config.FLPRODUCT = "Logos"
                self.product_q.put(config.FLPRODUCT)
                self.product_e.set()
            elif str(choice).startswith("Verbum"):
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
            if choice:
                config.TARGET_RELEASE_VERSION = choice
                self.release_q.put(config.TARGET_RELEASE_VERSION)
                self.release_e.set()
        elif screen_id == 5:
            if choice:
                config.INSTALLDIR = choice
                config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"
                self.installdir_q.put(config.INSTALLDIR)
                self.installdir_e.set()
        elif screen_id == 6:
            config.WINE_EXE = choice
            if choice:
                self.wine_q.put(config.WINE_EXE)
                self.wine_e.set()
        elif screen_id == 7:
            winetricks_options = utils.get_winetricks_options()
            if choice.startswith("Use"):
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
            if choice:
                self.config_q.put(choice)
                self.config_e.set()
            self.tui_screens = []
        elif screen_id == 10:
            pass
        elif screen_id == 11:
            pass

    def switch_screen(self, dialog):
        if self.active_screen is not None and self.active_screen != self.menu_screen:
            self.tui_screens.pop(0)
        if self.active_screen == self.menu_screen:
            self.menu_screen.choice = "Processing"
            self.menu_screen.running = 0
        if isinstance(self.active_screen, tui_screen.CursesScreen):
            self.stdscr.clear()

    def get_product(self, dialog):
        question = "Choose which FaithLife product the script should install:"  # noqa: E501
        labels = ["Logos", "Verbum", "Return to Main Menu"]
        options = self.which_dialog_options(labels, dialog)
        self.menu_options = options
        self.screen_q.put(self.stack_menu(2, self.product_q, self.product_e, question, options, dialog=dialog))

    def get_version(self, dialog):
        self.product_e.wait()
        question = f"Which version of {config.FLPRODUCT} should the script install?"  # noqa: E501
        labels = ["10", "9", "Return to Main Menu"]
        options = self.which_dialog_options(labels, dialog)
        self.menu_options = options
        self.screen_q.put(self.stack_menu(3, self.version_q, self.version_e, question, options, dialog=dialog))

    def get_release(self, dialog):
        labels = []
        self.screen_q.put(self.stack_text(10, self.version_q, self.version_e, "Waiting to acquire Logos versions…", wait=True, dialog=dialog))
        self.version_e.wait()
        question = f"Which version of {config.FLPRODUCT} {config.TARGETVERSION} do you want to install?"  # noqa: E501
        utils.start_thread(utils.get_logos_releases, True, self)
        self.releases_e.wait()

        if config.TARGETVERSION == '10':
            labels = self.releases_q.get()
        elif config.TARGETVERSION == '9':
            labels = self.releases_q.get()

        if labels is None:
            msg.logos_error("Failed to fetch TARGET_RELEASE_VERSION.")
        labels.append("Return to Main Menu")
        options = self.which_dialog_options(labels, dialog)
        self.menu_options = options
        self.screen_q.put(self.stack_menu(4, self.release_q, self.release_e, question, options, dialog=dialog))

    def get_installdir(self, dialog):
        self.release_e.wait()
        default = f"{str(Path.home())}/{config.FLPRODUCT}Bible{config.TARGETVERSION}"  # noqa: E501
        question = f"Where should {config.FLPRODUCT} files be installed to? [{default}]: "  # noqa: E501
        self.screen_q.put(self.stack_input(5, self.installdir_q, self.installdir_e, question, default, dialog=dialog))

    def get_wine(self, dialog):
        self.installdir_e.wait()
        self.screen_q.put(self.stack_text(10, self.wine_q, self.wine_e, "Waiting to acquire available Wine binaries…", wait=True, dialog=dialog))
        question = f"Which Wine AppImage or binary should the script use to install {config.FLPRODUCT} v{config.TARGET_RELEASE_VERSION} in {config.INSTALLDIR}?"  # noqa: E501
        labels = utils.get_wine_options(
            utils.find_appimage_files(config.TARGET_RELEASE_VERSION),
            utils.find_wine_binary_files(config.TARGET_RELEASE_VERSION)
        )
        labels.append("Return to Main Menu")
        max_length = max(len(label) for label in labels)
        max_length += len(str(len(labels))) + 10
        options = self.which_dialog_options(labels, dialog)
        self.menu_options = options
        self.screen_q.put(self.stack_menu(6, self.wine_q, self.wine_e, question, options, width=max_length, dialog=dialog))

    def get_winetricksbin(self, dialog):
        self.wine_e.wait()
        winetricks_options = utils.get_winetricks_options()
        question = f"Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that {config.FLPRODUCT} requires on Linux."  # noqa: E501
        options = self.which_dialog_options(winetricks_options, dialog)
        self.menu_options = options
        self.screen_q.put(self.stack_menu(7, self.tricksbin_q, self.tricksbin_e, question, options, dialog=dialog))

    def get_waiting(self, dialog):
        self.tricksbin_e.wait()
        text = ["Install is running…\n"] + logging.console_log[-2:]
        processed_text = utils.str_array_to_string(text)
        percent = installer.get_progress_pct(config.INSTALL_STEP, config.INSTALL_STEPS_COUNT)
        self.screen_q.put(self.stack_text(8, self.status_q, self.status_e, processed_text, wait=True, percent=percent,
                        dialog=dialog))

    def get_config(self, dialog):
        question = f"Update config file at {config.CONFIG_FILE}?"
        labels = ["Yes", "No"]
        options = self.which_dialog_options(labels, dialog)
        self.menu_options = options
        self.screen_q.put(self.stack_menu(9, self.config_q, self.config_e, question, options, dialog=dialog))

    def finish_install(self):
        utils.send_task(self, 'TUI-UPDATE-MENU')

    def report_waiting(self, text, dialog):
        #self.screen_q.put(self.stack_text(10, self.status_q, self.status_e, text, wait=True, dialog=dialog))
        logging.console_log.append(text)

    def report_dependencies(self, text, percent, elements, dialog):
        if elements is not None:
            if dialog:
                self.screen_q.put(self.stack_tasklist(11, self.deps_q, self.deps_e, text, elements, percent, dialog=dialog))
                # Without this delay, the reporting works too quickly and instead appears all at once.
                time.sleep(0.1)
            else:
                #TODO
                pass

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
        if config.LLI_LATEST_VERSION and utils.get_runmode() == 'binary':
            logging.debug("Checking if Logos Linux Installers needs updated.")  # noqa: E501
            status, error_message = utils.compare_logos_linux_installer_version()  # noqa: E501
            if status == 0:
                labels.append("Update Logos Linux Installer")
            elif status == 1:
                logging.warning("Logos Linux Installer is up-to-date.")
            elif status == 2:
                logging.warning("Logos Linux Installer is newer than the latest release.")  # noqa: E501
            else:
                logging.error(f"{error_message}")

        if utils.file_exists(config.LOGOS_EXE):
            labels_default = [
                f"Run {config.FLPRODUCT}",
                "Run Indexing",
                "Remove Library Catalog",
                "Remove All Index Files",
                "Edit Config",
                "Back up Data",
                "Restore Data",
            ]
        else:
            labels_default = ["Install Logos Bible Software"]
        labels.extend(labels_default)

        labels_support = [
            "Install Dependencies",
            "Download or Update Winetricks",
            "Run Winetricks",
            "Install d3dcompiler",
            "Install Fonts",
            "Install ICU"
        ]
        labels.extend(labels_support)

        label = "Enable Logging" if config.LOGS == "DISABLED" else "Disable Logging"
        labels.append(label)

        labels.append("Exit")

        options = self.which_dialog_options(labels, dialog=False)

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

    def stack_text(self, screen_id, queue, event, text, wait=False, percent=None, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens, tui_screen.TextDialog(self, screen_id, queue, event, text, wait, percent))
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
                            tui_screen.BuildListDialog(self, screen_id, queue, event, question, options, height, width, list_height))
        else:
            # TODO
            pass

    def stack_checklist(self, screen_id, queue, event, question, options, height=None, width=None, list_height=None, dialog=False):
        if dialog:
            utils.append_unique(self.tui_screens,
                            tui_screen.CheckListDialog(self, screen_id, queue, event, question, options, height, width, list_height))
        else:
            # TODO
            pass


    def update_tty_dimensions(self):
        self.window_height, self.window_width = self.stdscr.getmaxyx()

    def get_main_window(self):
        return self.main_window

    def get_menu_window(self):
        return self.menu_window


def control_panel_app(stdscr):
    os.environ.setdefault('ESCDELAY', '100')
    TUI(stdscr).run()

