import curses
import logging
import signal
import textwrap

from . import config
from . import msg
from . import utils


def wrap_text(app, text):
    # Turn text into wrapped text, line by line, centered
    if "\n" in text:
        lines = text.splitlines()
        wrapped_lines = [textwrap.fill(line, app.window_width - (app.terminal_margin * 2)) for line in lines]
        lines = '\n'.join(wrapped_lines)
    else:
        wrapped_text = textwrap.fill(text, app.window_width - (app.terminal_margin * 2))
        lines = wrapped_text.split('\n')
    return lines


def write_line(app, stdscr, start_y, start_x, text, char_limit, attributes=curses.A_NORMAL):
    try:
        stdscr.addnstr(start_y, start_x, text, char_limit, attributes)
    except curses.error:
        signal.signal(signal.SIGWINCH, app.signal_resize)


def title(app, title_text, title_start_y_adj):
    stdscr = app.get_main_window()
    title_lines = wrap_text(app, title_text)
    title_start_y = max(0, app.window_height // 2 - len(title_lines) // 2)
    last_index = 0
    for i, line in enumerate(title_lines):
        if i < app.window_height:
            write_line(app, stdscr, i + title_start_y_adj, 2, line, app.window_width, curses.A_BOLD)
        last_index = i

    return last_index


def text_centered(app, text, start_y=0):
    stdscr = app.get_menu_window()
    if "\n" in text:
        text_lines = wrap_text(app, text).splitlines()
    else:
        text_lines = wrap_text(app, text)
    text_start_y = start_y
    text_width = max(len(line) for line in text_lines)
    for i, line in enumerate(text_lines):
        if text_start_y + i < app.window_height:
            x = app.window_width // 2 - text_width // 2
            write_line(app, stdscr, text_start_y + i, x, line, app.window_width, curses.A_BOLD)

    return text_start_y, text_lines


def spinner(app, index, start_y=0):
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
    i = index
    text_centered(app, spinner_chars[i], start_y)
    i = (i + 1) % len(spinner_chars)
    return i


#FIXME: Display flickers.
def confirm(app, question_text, height=None, width=None):
    stdscr = app.get_menu_window()
    question_text = question_text + " [Y/n]: "
    question_start_y, question_lines = text_centered(app, question_text)

    y = question_start_y + len(question_lines) + 2

    while True:
        key = stdscr.getch()
        key = chr(key)

        if key.lower() == 'y' or key == '\n':  # '\n' for Enter key, defaults to "Yes"
            return True
        elif key.lower() == 'n':
            return False

        write_line(app, stdscr, y, 0, "Type Y[es] or N[o]. ", app.window_width, curses.A_BOLD)


class CursesDialog:
    def __init__(self, app):
        from ou_dedetai.tui_app import TUI
        self.app: TUI = app
        self.stdscr: curses.window = self.app.get_menu_window()

    def __str__(self):
        return f"Curses Dialog"

    def draw(self):
        pass

    def input(self):
        pass

    def run(self):
        pass


class UserInputDialog(CursesDialog):
    def __init__(self, app, question_text, default_text):
        super().__init__(app)
        self.question_text = question_text
        self.default_text = default_text
        self.user_input = ""
        self.submit = False
        self.question_start_y = None
        self.question_lines = None

    def __str__(self):
        return f"UserInput Curses Dialog"

    def draw(self):
        curses.echo()
        curses.curs_set(1)
        self.stdscr.clear()
        self.question_start_y, self.question_lines = text_centered(self.app, self.question_text)
        self.input()
        curses.curs_set(0)
        curses.noecho()
        self.stdscr.refresh()

    def input(self):
        write_line(self.app, self.stdscr, self.question_start_y + len(self.question_lines) + 2, 10, self.user_input, self.app.window_width)
        key = self.stdscr.getch(self.question_start_y + len(self.question_lines) + 2, 10 + len(self.user_input))

        try:
            if key == -1:  # If key not found, keep processing.
                pass
            elif key == ord('\n'):  # Enter key
                self.submit = True
            elif key == curses.KEY_BACKSPACE or key == 127:
                if len(self.user_input) > 0:
                    self.user_input = self.user_input[:-1]
            else:
                self.user_input += chr(key)
        except KeyboardInterrupt:
            signal.signal(signal.SIGINT, self.app.end)

    def run(self):
        if not self.submit:
            self.draw()
            return "Processing"
        else:
            if self.user_input is None or self.user_input == "":
                self.user_input = self.default_text
            return self.user_input


class PasswordDialog(UserInputDialog):
    def __init__(self, app, question_text, default_text):
        super().__init__(app, question_text, default_text)

        self.obfuscation = ""

    def run(self):
        if not self.submit:
            self.draw()
            return "Processing"
        else:
            if self.user_input is None or self.user_input == "":
                self.user_input = self.default_text
            return self.user_input

    def input(self):
        write_line(self.app, self.stdscr, self.question_start_y + len(self.question_lines) + 2, 10, self.obfuscation,
                   self.app.window_width)
        key = self.stdscr.getch(self.question_start_y + len(self.question_lines) + 2, 10 + len(self.obfuscation))

        try:
            if key == -1:  # If key not found, keep processing.
                pass
            elif key == ord('\n'):  # Enter key
                self.submit = True
            elif key == curses.KEY_BACKSPACE or key == 127:
                if len(self.user_input) > 0:
                    self.user_input = self.user_input[:-1]
                    self.obfuscation = '*' * len(self.user_input[:-1])
            else:
                self.user_input += chr(key)
                self.obfuscation = '*' * (len(self.obfuscation) + 1)
        except KeyboardInterrupt:
            signal.signal(signal.SIGINT, self.app.end)


class MenuDialog(CursesDialog):
    def __init__(self, app, question_text, options):
        super().__init__(app)
        self.user_input = "Processing"
        self.submit = False
        self.question_text = question_text
        self.options = options
        self.question_start_y = None
        self.question_lines = None

    def __str__(self):
        return f"Menu Curses Dialog"

    def draw(self):
        self.stdscr.erase()
        self.app.active_screen.set_options(self.options)
        self.total_pages = (len(self.options) - 1) // self.app.options_per_page + 1

        self.question_start_y, self.question_lines = text_centered(self.app, self.question_text)
        # Display the options, centered
        options_start_y = self.question_start_y + len(self.question_lines) + 2
        for i in range(self.app.options_per_page):
            index = self.app.current_page * self.app.options_per_page + i
            if index < len(self.options):
                option = self.options[index]
                if type(option) is list:
                    option_lines = []
                    wine_binary_code = option[0]
                    if wine_binary_code != "Exit":
                        wine_binary_path = option[1]
                        wine_binary_description = option[2]
                        wine_binary_path_wrapped = textwrap.wrap(
                            f"Binary Path: {wine_binary_path}", self.app.window_width - 4)
                        option_lines.extend(wine_binary_path_wrapped)
                        wine_binary_desc_wrapped = textwrap.wrap(
                            f"Description: {wine_binary_description}", self.app.window_width - 4)
                        option_lines.extend(wine_binary_desc_wrapped)
                    else:
                        wine_binary_path = option[1]
                        wine_binary_description = option[2]
                        wine_binary_path_wrapped = textwrap.wrap(
                            f"{wine_binary_path}", self.app.window_width - 4)
                        option_lines.extend(wine_binary_path_wrapped)
                        wine_binary_desc_wrapped = textwrap.wrap(
                            f"{wine_binary_description}", self.app.window_width - 4)
                        option_lines.extend(wine_binary_desc_wrapped)
                else:
                    option_lines = textwrap.wrap(option, self.app.window_width - 4)

                for j, line in enumerate(option_lines):
                    y = options_start_y + i + j
                    x = max(0, self.app.window_width // 2 - len(line) // 2)
                    if y < self.app.menu_window_height:
                        if index == self.app.current_option:
                            write_line(self.app, self.stdscr, y, x, line, self.app.window_width, curses.A_REVERSE)
                        else:
                            write_line(self.app, self.stdscr, y, x, line, self.app.window_width)
                menu_bottom = y

                if type(option) is list:
                    options_start_y += (len(option_lines))

        # Display pagination information
        page_info = f"Page {self.app.current_page + 1}/{self.total_pages} | Selected Option: {self.app.current_option + 1}/{len(self.options)}"
        write_line(self.app, self.stdscr, max(menu_bottom, self.app.menu_window_height) - 3, 2, page_info, self.app.window_width, curses.A_BOLD)

    def do_menu_up(self):
        if self.app.current_option == self.app.current_page * self.app.options_per_page and self.app.current_page > 0:
            # Move to the previous page
            self.app.current_page -= 1
            self.app.current_option = min(len(self.app.menu_options) - 1, (self.app.current_page + 1) * self.app.options_per_page - 1)
        elif self.app.current_option == 0:
            if self.total_pages == 1:
                self.app.current_option = len(self.app.menu_options) - 1
            else:
                self.app.current_page = self.total_pages - 1
                self.app.current_option = len(self.app.menu_options) - 1
        else:
            self.app.current_option = max(0, self.app.current_option - 1)

    def do_menu_down(self):
        if self.app.current_option == (self.app.current_page + 1) * self.app.options_per_page - 1 and self.app.current_page < self.total_pages - 1:
            # Move to the next page
            self.app.current_page += 1
            self.app.current_option = min(len(self.app.menu_options) - 1, self.app.current_page * self.app.options_per_page)
        elif self.app.current_option == len(self.app.menu_options) - 1:
            self.app.current_page = 0
            self.app.current_option = 0
        else:
            self.app.current_option = min(len(self.app.menu_options) - 1, self.app.current_option + 1)

    def input(self):
        if len(self.app.tui_screens) > 0:
            self.stdscr = self.app.tui_screens[-1].get_stdscr()
        else:
            self.stdscr = self.app.menu_screen.get_stdscr()
        key = self.stdscr.getch()

        try:
            if key == -1:  # If key not found, keep processing.
                pass
            elif key == curses.KEY_UP or key == 259:  # Up arrow
                self.do_menu_up()
            elif key == curses.KEY_DOWN or key == 258:  # Down arrow
                self.do_menu_down()
            elif key == 27:  # Sometimes the up/down arrow key is represented by a series of three keys.
                next_key = self.stdscr.getch()
                if next_key == 91:
                    final_key = self.stdscr.getch()
                    if final_key == 65:
                        self.do_menu_up()
                    elif final_key == 66:
                        self.do_menu_down()
            elif key == ord('\n') or key == 10:  # Enter key
                self.user_input = self.options[self.app.current_option]
            elif key == ord('\x1b'):
                signal.signal(signal.SIGINT, self.app.end)
            # FIXME: do we need to log this?
            # else:
            #     logging.debug(f"Input unknown: {key}")
            #     pass
        except KeyboardInterrupt:
            signal.signal(signal.SIGINT, self.app.end)

        self.stdscr.noutrefresh()

    def run(self):
        #thread = utils.start_thread(self.input, daemon_bool=False)
        #thread.join()
        self.draw()
        self.input()
        return self.user_input

    def set_options(self, new_options):
        self.options = new_options
        self.app.menu_options = new_options
