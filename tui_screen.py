import curses
import logging
from pathlib import Path
import time

import msg
import tui


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


class ConsoleScreen(Screen):
    def __init__(self, app, screen_id, queue, event, title):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_main_window()
        self.title = title

    def display(self):
        self.stdscr.erase()
        tui.title(self.app, self.title)

        self.stdscr.addstr(2, 2, f"---Console---")
        recent_messages = logging.console_log[-6:]
        for i, message in enumerate(recent_messages, 1):
            message_lines = tui.wrap_text(self.app, message)
            for j, line in enumerate(message_lines):
                if 2 + j < self.app.window_height:
                    self.stdscr.addstr(2 + i, 2, f"{message}")

        self.stdscr.noutrefresh()
        curses.doupdate()


class MenuScreen(Screen):
    def __init__(self, app, screen_id, queue, event, question, options):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.question = question
        self.options = options

    def display(self):
        self.stdscr.erase()
        self.choice = tui.menu(
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


class InputScreen(Screen):
    def __init__(self, app, screen_id, queue, event, question, default):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.question = question
        self.default = default

    def display(self):
        self.choice = tui.directory_picker(self.app, self.default)
        if self.choice:
            self.choice = Path(self.choice)
        # self.stdscr.erase()
        # self.choice = tui.get_user_input(
        #     self.app,
        #     self.question,
        #     self.default
        # )
        # self.stdscr.noutrefresh()
        # curses.doupdate()

    def get_question(self):
        return self.question

    def get_default(self):
        return self.default


class TextScreen(Screen):
    def __init__(self, app, screen_id, queue, event, text, wait):
        super().__init__(app, screen_id, queue, event)
        self.stdscr = self.app.get_menu_window()
        self.text = text
        self.wait = wait
        self.spinner_index = 0

    def display(self):
        self.stdscr.erase()
        text_start_y, text_lines = tui.text_centered(self.app, self.text)
        if self.wait:
            self.spinner_index = tui.spinner(self.app, self.spinner_index, text_start_y + len(text_lines) + 1)
            time.sleep(0.1)
        self.stdscr.noutrefresh()
        curses.doupdate()

    def get_text(self):
        return self.text
