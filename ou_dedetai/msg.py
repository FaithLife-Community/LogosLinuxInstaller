import gzip
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import shutil
import sys

from pathlib import Path

from . import config
from . import constants
from . import utils
from .gui import ask_question
from .gui import show_error


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


def initialize_logging(log_level: str | int, app_log_path: str):
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

    # Ensure the application log's directory exists
    os.makedirs(os.path.dirname(app_log_path), exist_ok=True)

    # Ensure log file parent folders exist.
    log_parent = Path(app_log_path).parent
    if not log_parent.is_dir():
        log_parent.mkdir(parents=True)

    logging.debug(f"Installer log file: {app_log_path}")

    # Define logging handlers.
    file_h = GzippedRotatingFileHandler(
        app_log_path,
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
    stderr_h.setLevel(log_level)
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


def initialize_tui_logging():
    current_logger = logging.getLogger()
    for h in current_logger.handlers:
        if h.name == 'terminal':
            current_logger.removeHandler(h)
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


# XXX: remove in favor of app.status("message", percent)
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
    # XXX: shouldn't this always use logging.warning?
    if config.DIALOG == 'curses':
        logging.warning(message)
    else:
        logos_msg(message)


# XXX: move this to app as... message?
def ui_message(message, secondary=None, detail=None, app=None, parent=None, fatal=False):  # noqa: E501
    if detail is None:
        detail = ''
    # XXX: move these to constants and output them on error
    WIKI_LINK = f"{constants.REPOSITORY_LINK}/wiki"
    TELEGRAM_LINK = "https://t.me/linux_logos"
    MATRIX_LINK = "https://matrix.to/#/#logosbible:matrix.org"
    help_message = f"If you need help, please consult:\n{WIKI_LINK}\n{TELEGRAM_LINK}\n{MATRIX_LINK}"  # noqa: E501
    if config.DIALOG == 'tk':
        show_error(
            message,
            detail=f"{detail}\n\n{help_message}",
            app=app,
            fatal=fatal,
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


def logos_warning(message, secondary=None, detail=None, app=None, parent=None):
    ui_message(message, secondary=secondary, detail=detail, app=app, parent=parent)  # noqa: E501
    logging.error(message)


def get_progress_str(percent):
    length = 40
    part_done = round(percent * length / 100)
    part_left = length - part_done
    return f"[{'*' * part_done}{'-' * part_left}]"


# XXX: remove in favor of app.status
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


# XXX: move this to app.status
def status(text, app=None, end='\n'):
    def strip_timestamp(msg, timestamp_length=20):
        return msg[timestamp_length:]

    timestamp = utils.get_timestamp()
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
