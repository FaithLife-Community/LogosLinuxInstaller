import textwrap
import curses
import logging


def get_user_input(question_text):
    logging.debug(f"tui.get_user_input: {question_text}")
    return curses.wrapper(_get_user_input, question_text)


def _get_user_input(stdscr, question_text):
    curses.echo()
    stdscr.addstr(0, 0, question_text)
    stdscr.refresh()
    user_input = stdscr.getstr(1, 0, 50).decode('utf-8')
    curses.noecho()
    return user_input


def confirm(title, question_text):
    logging.debug(f"tui.confirm: {question_text}")
    return curses.wrapper(_confirm, title, question_text)


def convert_yes_no(key):
    if key.lower() == 'y' or key == '\n':
        # '\n' for Enter key, defaults to "Yes"
        return True
    elif key.lower() == 'n':
        return False


def _confirm(stdscr, title, question_text):
    curses.curs_set(0)  # Hide the cursor

    stdscr.clear()
    window_height, window_width = stdscr.getmaxyx()

    # Wrap the title and question text
    wrapped_title = textwrap.fill(title, window_width - 4)
    wrapped_question = textwrap.fill(question_text + " [Y/n]: ", window_width - 4)  # noqa: E501

    # Display the wrapped title text, line by line, centered
    title_lines = wrapped_title.split('\n')
    title_start_y = max(0, window_height // 2 - len(title_lines) // 2)
    for i, line in enumerate(title_lines):
        if i < window_height:
            stdscr.addstr(i, 2, line, curses.A_BOLD)

    # Display the wrapped question text, line by line, centered
    question_lines = wrapped_question.split('\n')
    question_start_y = title_start_y + len(title_lines) - 4
    question_width = max(len(line) for line in question_lines)
    for i, line in enumerate(question_lines):
        if question_start_y + i < window_height:
            x = window_width // 2 - question_width // 2
            stdscr.addstr(question_start_y + i, x, line)

    y = question_start_y + len(question_lines) + 2

    while True:
        key = stdscr.getch()
        key = chr(key)

        value = convert_yes_no(key)
        if value is not None:
            return value

        stdscr.addstr(y, 0, "Type Y[es] or N[o]. ")


def menu(options, title, question_text):
    logging.debug(f"tui.menu: {question_text}")
    return curses.wrapper(_menu, options, title, question_text)


def _menu(stdscr, options, title, question_text):
    # Set up the screen
    curses.curs_set(0)

    current_option = 0
    current_page = 0
    options_per_page = 8
    total_pages = (len(options) - 1) // options_per_page + 1

    while True:
        stdscr.clear()

        window_height, window_width = stdscr.getmaxyx()

        # Wrap the title and question text
        wrapped_title = textwrap.fill(title, window_width - 4)
        wrapped_question = textwrap.fill(question_text, window_width - 4)

        # Display the wrapped title text, line by line, centered
        title_lines = wrapped_title.split('\n')
        title_start_y = max(0, window_height // 2 - len(title_lines) // 2)
        for i, line in enumerate(title_lines):
            if i < window_height:
                stdscr.addstr(i, 2, line, curses.A_BOLD)

        # Display the wrapped question text, line by line, centered
        question_lines = wrapped_question.split('\n')
        question_start_y = title_start_y + len(title_lines) - 4
        question_width = max(len(line) for line in question_lines)
        for i, line in enumerate(question_lines):
            if question_start_y + i < window_height:
                x = window_width // 2 - question_width // 2
                stdscr.addstr(question_start_y + i, x, line)

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
                            f"Binary Path: {wine_binary_path}", window_width - 4)  # noqa: E501
                        option_lines.extend(wine_binary_path_wrapped)
                        wine_binary_desc_wrapped = textwrap.wrap(
                            f"Description: {wine_binary_description}", window_width - 4)  # noqa: E501
                        option_lines.extend(wine_binary_desc_wrapped)
                    else:
                        wine_binary_path = option[1]
                        wine_binary_description = option[2]
                        wine_binary_path_wrapped = textwrap.wrap(
                            f"{wine_binary_path}", window_width - 4)
                        option_lines.extend(wine_binary_path_wrapped)
                        wine_binary_desc_wrapped = textwrap.wrap(
                            f"{wine_binary_description}", window_width - 4)
                        option_lines.extend(wine_binary_desc_wrapped)
                else:
                    option_lines = textwrap.wrap(option, window_width - 4)

                for j, line in enumerate(option_lines):
                    y = options_start_y + i + j
                    x = max(0, window_width // 2 - len(line) // 2)
                    if y < window_height:
                        if index == current_option:
                            stdscr.addstr(y, x, line, curses.A_REVERSE)
                        else:
                            stdscr.addstr(y, x, line)

                if type(option) is list:
                    options_start_y += (len(option_lines))

        # Display pagination information
        page_info = f"Page {current_page + 1}/{total_pages} | Selected Option: {current_option + 1}/{len(options)}"  # noqa: E501
        stdscr.addstr(window_height - 1, 2, page_info, curses.A_BOLD)

        # Refresh the windows
        stdscr.refresh()

        # Get user input
        key = stdscr.getch()

        if key == 65 or key == 259:  # Up arrow
            if current_option == current_page * options_per_page and current_page > 0:  # noqa: E501
                # Move to the previous page
                current_page -= 1
                current_option = min(
                    len(options) - 1,
                    (current_page + 1) * options_per_page - 1
                )
            elif current_option == 0:
                if total_pages == 1:
                    current_option = len(options) - 1
                else:
                    current_page = total_pages - 1
                    current_option = len(options) - 1
            else:
                current_option = max(0, current_option - 1)
        elif key == 66 or key == 258:  # Down arrow
            if current_option == (current_page + 1) * options_per_page - 1 and current_page < total_pages - 1:  # noqa: E501
                # Move to the next page
                current_page += 1
                current_option = min(
                    len(options) - 1,
                    current_page * options_per_page
                )
            elif current_option == len(options) - 1:
                current_page = 0
                current_option = 0
            else:
                current_option = min(len(options) - 1, current_option + 1)
        elif key == ord('\n'):  # Enter key
            choice = options[current_option]
            break

    return choice
