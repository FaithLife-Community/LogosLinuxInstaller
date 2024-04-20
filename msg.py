import logging
import os
import signal
import sys

from pathlib import Path

import config


def get_log_level_name(level):
    name = None
    levels = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    }
    for k, v in levels.items():
        if level == v:
            name = k
            break
    return name


def initialize_logging(stderr_log_level):
    '''
    Log levels:
        Level       Value   Description
        CRITICAL    50      the program can't continue
        ERROR       40      the program has not been able to do something
        WARNING     30      something unexpected happened (maybe neg. effect)
        INFO        20      confirmation that things are working as expected
        DEBUG       10      detailed, dev-level information
        NOTSET      0       all events are handled
    '''

    # Ensure log file parent folders exist.
    log_parent = Path(config.LOGOS_LOG).parent
    if not log_parent.is_dir():
        log_parent.mkdir(parents=True)

    # Define logging handlers.
    file_h = logging.FileHandler(config.LOGOS_LOG, encoding='UTF8')
    file_h.setLevel(logging.DEBUG)
    # stdout_h = logging.StreamHandler(sys.stdout)
    # stdout_h.setLevel(stdout_log_level)
    stderr_h = logging.StreamHandler(sys.stderr)
    stderr_h.setLevel(stderr_log_level)
    handlers = [
        file_h,
        # stdout_h,
        stderr_h,
    ]

    # Set initial config.
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers,
    )


def update_log_level(new_level):
    # Update logging level from config.
    for h in logging.getLogger().handlers:
        if type(h) is logging.StreamHandler:
            h.setLevel(new_level)
    logging.info(f"Terminal log level set to {get_log_level_name(new_level)}")


def cli_msg(message, end='\n'):
    '''Prints message to stdout regardless of log level.'''
    print(message, end=end)


def logos_progress():
    sys.stdout.write('.')
    sys.stdout.flush()
    # i = 0
    # spinner = "|/-\\"
    # sys.stdout.write(f"\r{text} {spinner[i]}")
    # sys.stdout.flush()
    # i = (i + 1) % len(spinner)
    # time.sleep(0.1)


def logos_warn(message):
    if config.DIALOG == 'curses':
        cli_msg(message)


def logos_error(message, secondary=None):
    WIKI_LINK = "https://github.com/FaithLife-Community/LogosLinuxInstaller/wiki"  # noqa: E501
    TELEGRAM_LINK = "https://t.me/linux_logos"
    MATRIX_LINK = "https://matrix.to/#/#logosbible:matrix.org"
    help_message = f"If you need help, please consult:\n{WIKI_LINK}\n{TELEGRAM_LINK}\n{MATRIX_LINK}"  # noqa: E501
    if secondary != "info":
        logging.critical(message)
        cli_msg(help_message)
    else:
        cli_msg(message)

    if secondary is None or secondary == "":
        try:
            os.remove("/tmp/LogosLinuxInstaller.pid")
        except FileNotFoundError:  # no pid file when testing functions
            pass
        os.kill(os.getpgid(os.getpid()), signal.SIGKILL)
    sys.exit(1)


def cli_question(QUESTION_TEXT):
    while True:
        try:
            yn = input(f"{QUESTION_TEXT} [Y/n]: ")
        except KeyboardInterrupt:
            print()
            logos_error("Cancelled with Ctrl+C")

        if yn.lower() == 'y' or yn == '':  # defaults to "Yes"
            return True
        elif yn.lower() == 'n':
            return False
        else:
            cli_msg("Type Y[es] or N[o].")


def cli_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY):
    if not cli_question(QUESTION_TEXT):
        logos_error(NO_TEXT, SECONDARY)


def cli_acknowledge_question(QUESTION_TEXT, NO_TEXT):
    if not cli_question(QUESTION_TEXT):
        cli_msg(NO_TEXT)
        return False
    else:
        return True


def cli_ask_filepath(question_text):
    try:
        answer = input(f"{question_text} ")
    except KeyboardInterrupt:
        print()
        logos_error("Cancelled with Ctrl+C")
    return answer.strip('"').strip("'")


def logos_acknowledge_question(QUESTION_TEXT, NO_TEXT):
    if config.DIALOG == 'curses':
        return cli_acknowledge_question(QUESTION_TEXT, NO_TEXT)


def get_progress_str(percent):
    length = 40
    part_done = round(percent * length / 100)
    part_left = length - part_done
    return f"[{'*' * part_done}{'-' * part_left}]"


def progress(percent, app=None):
    """Updates progressbar values for TUI and GUI."""
    logging.debug(f"Progress: {percent}%")
    if config.DIALOG == 'tk' and app:
        app.progress_q.put(percent)
        app.root.event_generate('<<UpdateProgress>>')
    else:
        cli_msg(get_progress_str(percent))  # provisional


def status(text, app=None):
    """Handles status messages for both TUI and GUI."""
    logging.debug(f"Status: {text}")
    if config.DIALOG == 'tk' and app:
        app.status_q.put(text)
        app.root.event_generate('<<UpdateStatus>>')
    else:
        cli_msg(text)  # provisional
