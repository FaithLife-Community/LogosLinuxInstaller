import gzip
import logging
from logging.handlers import RotatingFileHandler
import os
import shutil
import sys

from pathlib import Path


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

