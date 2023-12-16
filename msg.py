import logging
import os
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

def no_diag_msg(message):
    logging.critical(message)
    subprocess.Popen(["xterm", "-hold", "-e", "printf", "%s" % message])
    sys.exit(1)

def cli_msg(message):
    ''' Used for messages that should be printed to stdout regardless of log level. '''
    print(message)

def gtk_info(*args):
    subprocess.Popen(["zenity", "--info", "--width=300", "--height=200", "--text=" + " ".join(args), "--title=Information"])
    
def gtk_progress(title, text):
    subprocess.Popen(["zenity", "--progress", "--title=" + title, "--text=" + text, "--pulsate", "--auto-close", "--no-cancel"])
    
def gtk_warn(*args):
    subprocess.Popen(["zenity", "--warning", "--width=300", "--height=200", "--text=" + " ".join(args), "--title=Warning!"])
    
def gtk_error(*args):
    subprocess.Popen(["zenity", "--error", "--width=300", "--height=200", "--text=" + " ".join(args), "--title=Error!"])   

def logos_info(message):
    if config.DIALOG in ['whiptail', 'dialog', 'curses']:
        cli_msg(message)
    elif config.DIALOG == "zenity":
        gtk_info(message)
        logging.info(message)
    elif config.DIALOG == "kdialog":
        pass

def logos_progress(title, text):
    if config.DIALOG in ['whiptail', 'dialog', 'curses']:
        sys.stdout.write('.')
        sys.stdout.flush()
        time.sleep(0.5)
        # i = 0
        # spinner = "|/-\\"
        # sys.stdout.write(f"\r{text} {spinner[i]}")
        # sys.stdout.flush()
        # i = (i + 1) % len(spinner)
        # time.sleep(0.1)
    elif config.DIALOG == "zenity":
        gtk_progress(title, text)
    elif config.DIALOG == "kdialog":
        pass
    
def logos_warn(message):
    if config.DIALOG in ['whiptail', 'dialog', 'curses']:
        logging.warning(message)
    elif config.DIALOG == "zenity":
        gtk_warn(message)
        logging.warning(message)
    elif config.DIALOG == "kdialog":
        pass

def logos_error(message, secondary=None):
    WIKI_LINK = "https://github.com/ferion11/LogosLinuxInstaller/wiki"
    TELEGRAM_LINK = "https://t.me/linux_logos"
    MATRIX_LINK = "https://matrix.to/#/#logosbible:matrix.org"
    help_message = f"If you need help, please consult:\n{WIKI_LINK}\n{TELEGRAM_LINK}\n{MATRIX_LINK}"
    if config.DIALOG in ['whiptail', 'dialog', 'curses']:
        logging.critical(f"{message}\n{help_message}")
    elif config.DIALOG == "zenity":
        gtk_error(message + "\n" + help_message)
        logging.critical(message)
    elif config.DIALOG == "kdialog":
        pass
    if secondary is None or secondary == "":
        os.remove("/tmp/LogosLinuxInstaller.pid")
        pgid = subprocess.check_output(['ps', '-o', 'pgid=', '-p', str(os.getpid())]).decode().strip()
        subprocess.run(['kill', '-SIGKILL', '-'+pgid], check=True)
    exit(1)

def cli_question(QUESTION_TEXT):
    while True:
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
        
def gtk_question(*args):
    try:
        subprocess.run(['zenity', '--question', '--width=300', '--height=200', '--text', *args, '--title=Question:'])
        return True
    except subprocess.CalledProcessError:
        return False
        
def gtk_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY):
    if not gtk_question(QUESTION_TEXT):
        logos_error('The installation was cancelled!', SECONDARY)
        
def gtk_acknowledge_question(QUESTION_TEXT, NO_TEXT):
    if not gtk_question(QUESTION_TEXT):
        logos_info(NO_TEXT)
        
def logos_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY):
    if config.DIALOG in ['whiptail', 'dialog', 'curses']:
        cli_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY)
    elif config.DIALOG == 'zenity':
        gtk_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY)
    elif config.DIALOG == 'kdialog':
        pass
        
def logos_acknowledge_question(QUESTION_TEXT, NO_TEXT):
    if config.DIALOG in ['whiptail', 'dialog', 'curses']:
        cli_acknowledge_question(QUESTION_TEXT, NO_TEXT)
    elif config.DIALOG == 'zenity':
        gtk_acknowledge_question(QUESTION_TEXT, NO_TEXT)
    elif config.DIALOG == 'kdialog':
        pass
