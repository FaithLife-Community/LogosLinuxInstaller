import textwrap
import curses
import logging


def get_user_input(question_text):
    screen = curses.initscr()
    curses.echo()
    screen.addstr(0, 0, question_text)
    screen.refresh()
    user_input = screen.getstr(1, 0, 50).decode('utf-8')
    curses.noecho()
    return user_input


def confirm(title, question_text):
    screen = curses.initscr()
    curses.curs_set(0)  # Hide the cursor

    screen.clear()
    window_height, window_width = screen.getmaxyx()

    # Wrap the title and question text
    wrapped_title = textwrap.fill(title, window_width - 4)
    wrapped_question = textwrap.fill(question_text + " [Y/n]: ", window_width - 4)

    # Display the wrapped title text, line by line, centered
    title_lines = wrapped_title.split('\n')
    title_start_y = max(0, window_height // 2 - len(title_lines) // 2)
    for i, line in enumerate(title_lines):
        if i < window_height:
            screen.addstr(i, 2, line, curses.A_BOLD)

    # Display the wrapped question text, line by line, centered
    question_lines = wrapped_question.split('\n')
    question_start_y = title_start_y + len(title_lines) - 4
    question_width = max(len(line) for line in question_lines)
    for i, line in enumerate(question_lines):
        if question_start_y + i < window_height:
            x = window_width // 2 - question_width // 2
            screen.addstr(question_start_y + i, x, line)

    y = question_start_y + len(question_lines) + 2

    while True:
        key = screen.getch()
        key = chr(key)

        if key.lower() == 'y' or key == '\n':  # '\n' for Enter key, defaults to "Yes"
            return True
        elif key.lower() == 'n':
            return False

        screen.addstr(y, 0, "Type Y[es] or N[o]. ")


def menu(options, title, question_text):
    # Set up the screen
    screen = curses.initscr()
    curses.curs_set(0)

    current_option = 0
    current_page = 0
    options_per_page = 5
    total_pages = (len(options) - 1) // options_per_page + 1

    while True:
        screen.clear()

        window_height, window_width = screen.getmaxyx()
        # window_y = window_height // 2 - options_per_page // 2
        # window_x = window_width // 2 - max(len(option) for option in options) // 2

        # Wrap the title and question text
        wrapped_title = textwrap.fill(title, window_width - 4)
        wrapped_question = textwrap.fill(question_text, window_width - 4)

        # Display the wrapped title text, line by line, centered
        title_lines = wrapped_title.split('\n')
        title_start_y = max(0, window_height // 2 - len(title_lines) // 2)
        for i, line in enumerate(title_lines):
            if i < window_height:
                screen.addstr(i, 2, line, curses.A_BOLD)

        # Display the wrapped question text, line by line, centered
        question_lines = wrapped_question.split('\n')
        question_start_y = title_start_y + len(title_lines) - 4
        question_width = max(len(line) for line in question_lines)
        for i, line in enumerate(question_lines):
            if question_start_y + i < window_height:
                x = window_width // 2 - question_width // 2
                screen.addstr(question_start_y + i, x, line)

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
                            f"Binary Path: {wine_binary_path}", window_width - 4)
                        option_lines.extend(wine_binary_path_wrapped)
                        wine_binary_desc_wrapped = textwrap.wrap(
                            f"Description: {wine_binary_description}", window_width - 4)
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
                            screen.addstr(y, x, line, curses.A_REVERSE)
                        else:
                            screen.addstr(y, x, line)

                if type(option) is list:
                    options_start_y += (len(option_lines))

        # Display pagination information
        page_info = f"Page {current_page + 1}/{total_pages} | Selected Option: {current_option + 1}/{len(options)}"
        screen.addstr(window_height - 1, 2, page_info, curses.A_BOLD)

        # Refresh the windows
        screen.refresh()

        # Get user input
        key = screen.getch()

        if key == 65:  # Up arrow
            if current_option == current_page * options_per_page and current_page > 0:
                # Move to the previous page
                current_page -= 1
                current_option = min(len(options) - 1, (current_page + 1) * options_per_page - 1)
            elif current_option == 0:
                if total_pages == 1:
                    current_option = len(options) - 1
                else:
                    current_page = total_pages - 1
                    current_option = len(options) - 1
            else:
                current_option = max(0, current_option - 1)
        elif key == 66:  # Down arrow
            if current_option == (current_page + 1) * options_per_page - 1 and current_page < total_pages - 1:
                # Move to the next page
                current_page += 1
                current_option = min(len(options) - 1, current_page * options_per_page)
            elif current_option == len(options) - 1:
                current_page = 0
                current_option = 0
            else:
                current_option = min(len(options) - 1, current_option + 1)
        elif key == ord('\n'):  # Enter key
            choice = options[current_option]
            break

    curses.endwin()
    return choice
