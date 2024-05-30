import logging
import queue

import time
from pathlib import Path
import curses

import msg
import config
import installer
import tui_curses
import tui_dialog
import utils


class Screen:
    def __init__(self, app, screen_id, queue, event):
        self.app = app
        self.screen_id = screen_id
        self.choice = ""
        self.queue = queue
        self.event = event

    def __str__(self):
        return f"Curses Screen"

    def display(self):
        pass

    def get_stdscr(self):
        return self.app.stdscr

    def get_screen_id(self):
        return self.screen_id

    def get_choice(self):
        return self.choice

    def submit_choice_to_queue(self):
        self.queue.put(self.choice)

    def wait_event(self):
        self.event.wait()

    def is_set(self):
        return self.event.is_set()


class CursesScreen(Screen):
    pass


class DialogScreen(Screen):
    pass


class ConsoleScreen(CursesScreen):
    def __init__(self, app, screen_id, queue, event, title):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_main_window()
        self.title = title

    def display(self):
        self.stdscr.erase()
        tui_curses.title(self.app, self.title)

        self.stdscr.addstr(2, 2, f"---Console---")
        recent_messages = logging.console_log[-6:]
        for i, message in enumerate(recent_messages, 1):
            message_lines = tui_curses.wrap_text(self.app, message)
            for j, line in enumerate(message_lines):
                if 2 + j < self.app.window_height:
                    self.stdscr.addstr(2 + i, 2, f"{message}")

        self.stdscr.noutrefresh()
        curses.doupdate()


class MenuScreen(CursesScreen):
    def __init__(self, app, screen_id, queue, event, question, options, height=None, width=None, menu_height=8):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.question = question
        self.options = options
        self.height = height
        self.width = width
        self.menu_height = menu_height

    def display(self):
        self.stdscr.erase()
        self.choice = tui_curses.menu(
            self.app,
            self.question,
            self.options
        )
        self.stdscr.noutrefresh()
        curses.doupdate()

    def get_question(self):
        return self.question

    def set_options(self, new_options):
        self.options = new_options


class InputScreen(CursesScreen):
    def __init__(self, app, screen_id, queue, event, question, default):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.question = question
        self.default = default

    def display(self):
        self.stdscr.erase()
        self.choice = tui_curses.get_user_input(
            self.app,
            self.question,
            self.default
        )
        self.stdscr.noutrefresh()
        curses.doupdate()

    def get_question(self):
        return self.question

    def get_default(self):
        return self.default


class TextScreen(CursesScreen):
    def __init__(self, app, screen_id, queue, event, text, wait):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.text = text
        self.wait = wait
        self.spinner_index = 0

    def display(self):
        self.stdscr.erase()
        text_start_y, text_lines = tui_curses.text_centered(self.app, self.text)
        if self.wait:
            self.spinner_index = tui_curses.spinner(self.app, self.spinner_index, text_start_y + len(text_lines) + 1)
            time.sleep(0.1)
        self.stdscr.noutrefresh()
        curses.doupdate()

    def get_text(self):
        return self.text


class MenuDialog(DialogScreen):
    def __init__(self, app, screen_id, queue, event, question, options, height=None, width=None, menu_height=8):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.question = question
        self.options = options
        self.height = height
        self.width = width
        self.menu_height = menu_height

    def __str__(self):
        return f"PyDialog Screen"

    def display(self):
        _, _, self.choice = tui_dialog.menu(self.app, self.question, self.options, self.height, self.width,
                                            self.menu_height)

    def get_question(self):
        return self.question

    def set_options(self, new_options):
        self.options = new_options


class InputDialog(DialogScreen):
    def __init__(self, app, screen_id, queue, event, question, default):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.question = question
        self.default = default

    def __str__(self):
        return f"PyDialog Screen"

    def display(self):
        self.choice = tui_dialog.directory_picker(self.app, self.default)
        if self.choice:
            self.choice = Path(self.choice)

    def get_question(self):
        return self.question

    def get_default(self):
        return self.default


class ConfirmDialog(DialogScreen):
    def __init__(self, app, screen_id, queue, event, question, yes_label="Yes", no_label="No"):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.question = question
        self.yes_label = yes_label
        self.no_label = no_label

    def __str__(self):
        return f"PyDialog Screen"

    def display(self):
        _, _, self.choice = tui_dialog.confirm(self.app, self.question, self.yes_label, self.no_label)

    def get_question(self):
        return self.question


class TextDialog(DialogScreen):
    def __init__(self, app, screen_id, queue, event, text, percent=None, wait=False, height=None, width=None,
                 title=None, backtitle=None, colors=True):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.text = text
        self.percent = percent
        self.wait = wait
        self.height = height
        self.width = width
        self.title = title
        self.backtitle = backtitle
        self.colors = colors

    def __str__(self):
        return f"PyDialog Screen"

    def display(self):
        if self.wait:
            logging.info(f"self.wait == True")
            self.percent = installer.get_progress_pct(config.INSTALL_STEP, config.INSTALL_STEPS_COUNT)
            # if not self.app.active_progress:
            #     self.app.active_progress = True
            tui_dialog.progress_bar(self, self.text, self.percent)
            # elif self.percent != 100:
            #     tui_dialog.update_progress_bar(self, self.percent, self.text, True)
            # elif self.percent == 100:
            #     tui_dialog.stop_progress_bar(self)
            #     self.wait = False
        else:
            logging.error(f"self.wait != True")
        #     tui_dialog.text(self, self.text)

        time.sleep(0.1)

    def get_text(self):
        return self.text
