import gzip
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import shutil
import sys
import time

from pathlib import Path

import config
from gui import ask_question
from gui import show_error


class GzippedRotatingFileHandler(RotatingFileHandler):
    def doRollover(self):
        super().doRollover()

        if self.backupCount > 0:
            for i in range(self.backupCount - 1, 0, -1):
                source = f"{self.baseFilename}.{i}.gz"
                destination = f"{self.baseFilename}.{i + 1}.gz"
                if os.path.exists(source):
                    if os.path.exists(destination):
                        os.remove(destination)
                    os.rename(source, destination)

            last_log = self.baseFilename + ".1"
            gz_last_log = self.baseFilename + ".1.gz"

            if os.path.exists(last_log) and os.path.getsize(last_log) > 0:
                with open(last_log, 'rb') as f_in:
                    with gzip.open(gz_last_log, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(last_log)


class DeduplicateFilter(logging.Filter):
    def __init__(self):
        super().__init__()
        self.last_log = None

    def filter(self, record):
        current_message = record.getMessage()
        if current_message == self.last_log:
            return False
        self.last_log = current_message
        return True


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
    file_h = GzippedRotatingFileHandler(
        config.LOGOS_LOG,
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='UTF8'
    )
    file_h.name = "logfile"
    file_h.setLevel(logging.DEBUG)
    file_h.addFilter(DeduplicateFilter())
    # stdout_h = logging.StreamHandler(sys.stdout)
    # stdout_h.setLevel(stdout_log_level)
    stderr_h = logging.StreamHandler(sys.stderr)
    stderr_h.name = "terminal"
    stderr_h.setLevel(stderr_log_level)
    stderr_h.addFilter(DeduplicateFilter())
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


def initialize_curses_logging():
    current_logger = logging.getLogger()
    for h in current_logger.handlers:
        if h.name == 'terminal':
            break


def update_log_level(new_level):
    # Update logging level from config.
    for h in logging.getLogger().handlers:
        if type(h) is logging.StreamHandler:
            h.setLevel(new_level)
    logging.info(f"Terminal log level set to {get_log_level_name(new_level)}")


def cli_msg(message, end='\n'):
    '''Prints message to stdout regardless of log level.'''
    print(message, end=end)


def logos_msg(message, end='\n'):
    if config.DIALOG == 'curses':
        pass
    else:
        cli_msg(message, end)


def logos_progress():
    if config.DIALOG == 'curses':
        pass
    else:
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
        logging.warning(message)
    else:
        logos_msg(message)


# TODO: I think detail is doing the same thing as secondary.
def logos_error(message, secondary=None, detail=None, app=None, parent=None):
    if detail is None:
        detail = ''
    logging.critical(message)
    WIKI_LINK = "https://github.com/FaithLife-Community/LogosLinuxInstaller/wiki"  # noqa: E501
    TELEGRAM_LINK = "https://t.me/linux_logos"
    MATRIX_LINK = "https://matrix.to/#/#logosbible:matrix.org"
    help_message = f"If you need help, please consult:\n{WIKI_LINK}\n{TELEGRAM_LINK}\n{MATRIX_LINK}"  # noqa: E501
    if config.DIALOG == 'tk':
        show_error(
            message,
            detail=f"{detail}\n\n{help_message}",
            app=app,
            parent=parent
        )
    elif config.DIALOG == 'curses':
        if secondary != "info":
            status(message)
            status(help_message)
        else:
            logos_msg(message)
    else:
        logos_msg(message)

    if secondary is None or secondary == "":
        try:
            os.remove("/tmp/LogosLinuxInstaller.pid")
        except FileNotFoundError:  # no pid file when testing functions
            pass
        os.kill(os.getpgid(os.getpid()), signal.SIGKILL)

    if hasattr(app, 'destroy'):
        app.destroy()
    sys.exit(1)


def cli_question(question_text, secondary):
    while True:
        try:
            cli_msg(secondary)
            yn = input(f"{question_text} [Y/n]: ")
        except KeyboardInterrupt:
            print()
            logos_error("Cancelled with Ctrl+C")

        if yn.lower() == 'y' or yn == '':  # defaults to "Yes"
            return True
        elif yn.lower() == 'n':
            return False
        else:
            logos_msg("Type Y[es] or N[o].")


def cli_continue_question(question_text, no_text, secondary):
    if not cli_question(question_text, secondary):
        logos_error(no_text)


def gui_continue_question(question_text, no_text, secondary):
    if ask_question(question_text, secondary) == 'no':
        logos_error(no_text)


def cli_acknowledge_question(question_text, no_text, secondary):
    if not cli_question(question_text, secondary):
        logos_msg(no_text)
        return False
    else:
        return True


def cli_ask_filepath(question_text):
    try:
        answer = input(f"{question_text} ")
        return answer.strip('"').strip("'")
    except KeyboardInterrupt:
        print()
        logos_error("Cancelled with Ctrl+C")


def logos_continue_question(question_text, no_text, secondary, app=None):
    if config.DIALOG == 'tk':
        gui_continue_question(question_text, no_text, secondary)
    elif config.DIALOG == 'cli':
        cli_continue_question(question_text, no_text, secondary)
    elif config.DIALOG == 'curses':
        app.screen_q.put(
            app.stack_confirm(
                16,
                app.confirm_q,
                app.confirm_e,
                question_text,
                no_text,
                secondary,
                dialog=config.use_python_dialog
            )
        )
    else:
        logos_error(f"Unhandled question: {question_text}")


def logos_acknowledge_question(question_text, no_text, secondary):
    if config.DIALOG == 'curses':
        pass
    else:
        return cli_acknowledge_question(question_text, no_text, secondary)


def get_progress_str(percent):
    length = 40
    part_done = round(percent * length / 100)
    part_left = length - part_done
    return f"[{'*' * part_done}{'-' * part_left}]"


def progress(percent, app=None):
    """Updates progressbar values for TUI and GUI."""
    if config.DIALOG == 'tk' and app:
        app.progress_q.put(percent)
        app.root.event_generate('<<UpdateProgress>>')
        logging.info(f"Progress: {percent}%")
    elif config.DIALOG == 'curses':
        if app:
            status(f"Progress: {percent}%", app)
        else:
            status(f"Progress: {get_progress_str(percent)}", app)
    else:
        logos_msg(get_progress_str(percent))  # provisional


def status(text, app=None, end='\n'):
    def strip_timestamp(msg, timestamp_length=20):
        return msg[timestamp_length:]

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    """Handles status messages for both TUI and GUI."""
    if app is not None:
        if config.DIALOG == 'tk':
            app.status_q.put(text)
            app.root.event_generate(app.status_evt)
            logging.info(f"{text}")
        elif config.DIALOG == 'curses':
            if len(config.console_log) > 0:
                last_msg = strip_timestamp(config.console_log[-1])
                if last_msg != text:
                    app.status_q.put(f"{timestamp} {text}")
                    app.report_waiting(f"{app.status_q.get()}", dialog=config.use_python_dialog)  # noqa: E501
                    logging.info(f"{text}")
            else:
                app.status_q.put(f"{timestamp} {text}")
                app.report_waiting(f"{app.status_q.get()}", dialog=config.use_python_dialog)  # noqa: E501
                logging.info(f"{text}")
        else:
            logging.info(f"{text}")
    else:
        # Prints message to stdout regardless of log level.
        logos_msg(text, end=end)
