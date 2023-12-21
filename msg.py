import logging
import os
import signal
import subprocess
import sys
import time

import config


def initialize_logging(stderr_log_level):
    '''
    Log levels:
        Level       Value   Description
        CRITICAL    50      the program can't continue
        ERROR       40      the program has not been able to do something
        WARNING     30      something unexpected happened that might a neg. affect
        INFO        20      confirmation that things are working as expected
        DEBUG       10      detailed, dev-level information
        NOTSET      0       all events are handled
    '''

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
    cli_msg(f"Installer log file: {config.LOGOS_LOG}")

def cli_msg(message):
    ''' Used for messages that should be printed to stdout regardless of log level. '''
    print(message)

def logos_info(message):
    if config.DIALOG == 'curses':
        cli_msg(message)

def logos_progress(title, text):
    if config.DIALOG == 'curses':
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(0.5)
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
    WIKI_LINK = "https://github.com/ferion11/LogosLinuxInstaller/wiki"
    TELEGRAM_LINK = "https://t.me/linux_logos"
    MATRIX_LINK = "https://matrix.to/#/#logosbible:matrix.org"
    help_message = f"If you need help, please consult:\n{WIKI_LINK}\n{TELEGRAM_LINK}\n{MATRIX_LINK}"
    if config.DIALOG == 'curses':
        logging.critical(f"{message}\n{help_message}")

    if secondary is None or secondary == "":
        os.remove("/tmp/LogosLinuxInstaller.pid")
        os.kill(os.getpgid(os.getpid()), signal.SIGKILL)
    exit(1)

def cli_question(QUESTION_TEXT):
    while True:
        # FIXME: By convention, the capitalized y/n letter tends to be the
        # default if the user just hits <Enter>.
        yn = input(f"{QUESTION_TEXT} [Y/n]: ")
        
        if yn.lower() == 'y':
            return True
        elif yn.lower() == 'n':
            return False
        else:
            print("Type Y[es] or N[o].")
            
def cli_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY):
    if not cli_question(QUESTION_TEXT):
        logos_error(NO_TEXT, SECONDARY)
        
def cli_acknowledge_question(QUESTION_TEXT, NO_TEXT):
    if not cli_question(QUESTION_TEXT):
        logos_info(NO_TEXT)
        return False
    else:
        return True
        
def logos_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY):
    if config.DIALOG == 'curses':
        cli_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY)
        
def logos_acknowledge_question(QUESTION_TEXT, NO_TEXT):
    if config.DIALOG == 'curses':
        return cli_acknowledge_question(QUESTION_TEXT, NO_TEXT)
