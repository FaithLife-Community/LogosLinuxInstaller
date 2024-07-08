import curses
import logging
import signal
import textwrap

import config
import msg
import utils


def wrap_text(app, text):
    # Turn text into wrapped text, line by line, centered
    wrapped_text = textwrap.fill(text, app.window_width - 4)
    lines = wrapped_text.split('\n')
    return lines


def title(app, title_text, title_start_y_adj):
    stdscr = app.get_main_window()
    title_lines = wrap_text(app, title_text)
    title_start_y = max(0, app.window_height // 2 - len(title_lines) // 2)
    last_index = 0
    for i, line in enumerate(title_lines):
        if i < app.window_height:
            stdscr.addstr(i + title_start_y_adj, 2, line, curses.A_BOLD)
        last_index = i

    return last_index


def text_centered(app, text, start_y=0):
    stdscr = app.get_menu_window()
    text_lines = wrap_text(app, text)
    text_start_y = start_y
    text_width = max(len(line) for line in text_lines)
    for i, line in enumerate(text_lines):
        if text_start_y + i < app.window_height:
            x = app.window_width // 2 - text_width // 2
            stdscr.addstr(text_start_y + i, x, line)

    return text_start_y, text_lines


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

        stdscr.addstr(y, 0, "Type Y[es] or N[o]. ")


def spinner(app, index, start_y=0):
    spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
    i = index
    text_centered(app, spinner_chars[i], start_y)
    i = (i + 1) % len(spinner_chars)

    return i


def get_user_input(app, question_text, default_text):
    stdscr = app.get_menu_window()
    curses.echo()
    curses.curs_set(1)
    user_input = input_keyboard(app, question_text, default_text)
    curses.curs_set(0)
    curses.noecho()

    return user_input


def input_keyboard(app, question_text, default):
    stdscr = app.get_menu_window()
    done = False
    choice = ""

    stdscr.clear()
    question_start_y, question_lines = text_centered(app, question_text)

    try:
        while done is False:
            curses.echo()
            key = stdscr.getch(question_start_y + len(question_lines) + 2, 10 + len(choice))
            if key == -1:  # If key not found, keep processing.
                pass
            elif key == ord('\n'):  # Enter key
                if choice is None or not choice:
                    choice = default
                logging.debug(f"Selected Path: {choice}")
                done = True
            elif key == curses.KEY_RESIZE:
                utils.send_task(app, 'RESIZE')
            elif key == curses.KEY_BACKSPACE or key == 127:
                if len(choice) > 0:
                    choice = choice[:-1]
                    stdscr.addstr(question_start_y + len(question_lines) + 2, 10, ' ' * (len(choice) + 1))
                    stdscr.addstr(question_start_y + len(question_lines) + 2, 10, choice)
            else:
                choice += chr(key)
                stdscr.addch(question_start_y + len(question_lines) + 2, 10 + len(choice) - 1, chr(key))
            stdscr.refresh()
        curses.noecho()

        stdscr.refresh()
        if done:
            return choice
    except KeyboardInterrupt:
        signal.signal(signal.SIGINT, app.end)


def do_menu_up(app):
    if config.current_option == config.current_page * config.options_per_page and config.current_page > 0:
        # Move to the previous page
        config.current_page -= 1
        config.current_option = min(len(app.menu_options) - 1, (config.current_page + 1) * config.options_per_page - 1)
    elif config.current_option == 0:
        if config.total_pages == 1:
            config.current_option = len(app.menu_options) - 1
        else:
            config.current_page = config.total_pages - 1
            config.current_option = len(app.menu_options) - 1
    else:
        config.current_option = max(0, config.current_option - 1)


def do_menu_down(app):
    if config.current_option == (config.current_page + 1) * config.options_per_page - 1 and config.current_page < config.total_pages - 1:
        # Move to the next page
        config.current_page += 1
        config.current_option = min(len(app.menu_options) - 1, config.current_page * config.options_per_page)
    elif config.current_option == len(app.menu_options) - 1:
        config.current_page = 0
        config.current_option = 0
    else:
        config.current_option = min(len(app.menu_options) - 1, config.current_option + 1)

def menu(app, question_text, options):
    stdscr = app.get_menu_window()
    current_option = config.current_option
    current_page = config.current_page
    options_per_page = config.options_per_page
    config.total_pages = (len(options) - 1) // options_per_page + 1

    app.menu_options = options

    while True:
        stdscr.erase()
        question_start_y, question_lines = text_centered(app, question_text)

        # Display the options, centered
        options_start_y = question_start_y + len(question_lines) + 2
        for i in range(options_per_page):
            index = current_page * options_per_page + i
            if index < len(options):
                option = options[index]
                if type(option) is list:
                    option_lines = []
                    wine_binary_code = option[0]
                    if wine_binary_code != "Exit":
                        wine_binary_path = option[1]
                        wine_binary_description = option[2]
                        wine_binary_path_wrapped = textwrap.wrap(
                            f"Binary Path: {wine_binary_path}", app.window_width - 4)
                        option_lines.extend(wine_binary_path_wrapped)
                        wine_binary_desc_wrapped = textwrap.wrap(
                            f"Description: {wine_binary_description}", app.window_width - 4)
                        option_lines.extend(wine_binary_desc_wrapped)
                    else:
                        wine_binary_path = option[1]
                        wine_binary_description = option[2]
                        wine_binary_path_wrapped = textwrap.wrap(
                            f"{wine_binary_path}", app.window_width - 4)
                        option_lines.extend(wine_binary_path_wrapped)
                        wine_binary_desc_wrapped = textwrap.wrap(
                            f"{wine_binary_description}", app.window_width - 4)
                        option_lines.extend(wine_binary_desc_wrapped)
                else:
                    option_lines = textwrap.wrap(option, app.window_width - 4)

                for j, line in enumerate(option_lines):
                    y = options_start_y + i + j
                    x = max(0, app.window_width // 2 - len(line) // 2)
                    if y < app.menu_window_height:
                        if index == current_option:
                            stdscr.addstr(y, x, line, curses.A_REVERSE)
                        else:
                            stdscr.addstr(y, x, line)

                if type(option) is list:
                    options_start_y += (len(option_lines))

        # Display pagination information
        page_info = f"Page {config.current_page + 1}/{config.total_pages} | Selected Option: {config.current_option + 1}/{len(options)}"
        stdscr.addstr(app.menu_window_height - 1, 2, page_info, curses.A_BOLD)

        # Refresh the windows
        stdscr.noutrefresh()

        # Get user input
        thread = utils.start_thread(menu_keyboard, True, app)
        thread.join()

        stdscr.noutrefresh()

        return app.choice


def menu_keyboard(app):
    if len(app.tui_screens) > 0:
        stdscr = app.tui_screens[-1].get_stdscr()
    else:
        stdscr = app.menu_screen.get_stdscr()
    options = app.menu_options
    key = stdscr.getch()
    choice = ""

    try:
        if key == -1:  # If key not found, keep processing.
            pass
        elif key == curses.KEY_RESIZE:
            utils.send_task(app, 'RESIZE')
        elif key == curses.KEY_UP or key == 259:  # Up arrow
            do_menu_up(app)
        elif key == curses.KEY_DOWN or key == 258:  # Down arrow
            do_menu_down(app)
        elif key == 27:  # Sometimes the up/down arrow key is represented by a series of three keys.
            next_key = stdscr.getch()
            if next_key == 91:
                final_key = stdscr.getch()
                if final_key == 65:
                    do_menu_up(app)
                elif final_key == 66:
                    do_menu_down(app)
        elif key == ord('\n'):  # Enter key
            choice = options[config.current_option]
            # Reset for next menu
            config.current_option = 0
            config.current_page = 0
        elif key == ord('\x1b'):
            signal.signal(signal.SIGINT, app.end)
        else:
            msg.status("Input unknown.", app)
            pass
    except KeyboardInterrupt:
        signal.signal(signal.SIGINT, app.end)

    stdscr.refresh()
    if choice:
        app.choice = choice
    else:
        return "Processing"
