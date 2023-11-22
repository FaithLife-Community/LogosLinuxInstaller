#!/usr/bin/env python
import os
import sys
import subprocess
import shutil
import atexit
import datetime
import time
import tempfile
import argparse
import json
import re
import platform # Deprecated in Python 3.8+
import curses
import textwrap
import requests
from xml.etree import ElementTree as ET

# Basic Functionality
#TODO: Fix post-install
#TODO: Test get_os and get_package_manager
#TODO: Verify necessary packages now that we are using python
#TODO: Redo logos_progress
#TODO: Redo all GUI commands
#TODO: Fix python print lines to use logos_error
#TODO: Test optargs and menu options

# AppImage Handling
#TODO: Convert checkAppImages(). See https://github.com/ferion11/LogosLinuxInstaller/pull/193/commits/bfefb3c05c7a9989e81372d77fa785fc75bd4e94
#TODO: Fix set_appimage()
#TODO: Add update_appimage()

# Script updates and ideas
#TODO: Put main menu into a while loop
#TODO: Add an option to reinstall dependencies for SteamOS
#TODO: Add a get_winetricks option to post-install menu
#TODO: Simplify variables? Import environment?

os.environ["LOGOS_SCRIPT_TITLE"] = "Logos Linux Installer"
os.environ["LOGOS_SCRIPT_AUTHOR"] = "Ferion11, John Goodman, T. H. Wright"
os.environ["LOGOS_SCRIPT_VERSION"] = "4.0.0"

# Environment variables
def set_default_env():
    os.environ["WINE64_APPIMAGE_FULL_VERSION"] = "v8.19-devel"
    os.environ["WINE64_APPIMAGE_FULL_URL"] = "https://github.com/ferion11/LogosLinuxInstaller/releases/download/wine-devel-8.19/wine-devel_8.19-x86_64.AppImage"
    os.environ["WINE64_APPIMAGE_FULL_FILENAME"] = os.path.basename(os.environ["WINE64_APPIMAGE_FULL_URL"])
    os.environ["WINE64_APPIMAGE_VERSION"] = "v8.19-devel"
    os.environ["WINE64_APPIMAGE_URL"] = "https://github.com/ferion11/LogosLinuxInstaller/releases/download/wine-devel-8.19/wine-devel_8.19-x86_64.AppImage"
    os.environ["WINE64_BOTTLE_TARGZ_URL"] = "https://github.com/ferion11/wine64_bottle_dotnet/releases/download/v5.11b/wine64_bottle.tar.gz"
    os.environ["WINE64_BOTTLE_TARGZ_NAME"] = "wine64_bottle.tar.gz"
    os.environ["WINE64_APPIMAGE_FILENAME"] = os.path.basename(os.environ["WINE64_APPIMAGE_URL"]).split(".AppImage")[0]
    os.environ["APPIMAGE_LINK_SELECTION_NAME"] = "selected_wine.AppImage"
    os.environ["WINETRICKS_URL"] = "https://raw.githubusercontent.com/Winetricks/winetricks/5904ee355e37dff4a3ab37e1573c56cffe6ce223/src/winetricks"
    os.environ["LAUNCHER_TEMPLATE_URL"] = "https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/Launcher-Template.sh"
    os.environ["CONTROL_PANEL_TEMPLATE_URL"] = "https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/controlPanel-Template.sh"
    os.environ["WINETRICKS_DOWNLOADER"] = "wget"
    os.environ["WINETRICKS_UNATTENDED"] = ""
    os.environ["WORKDIR"] = tempfile.mkdtemp(prefix="/tmp/LBS.")
    os.environ["PRESENT_WORKING_DIRECTORY"] = os.getcwd()
    os.environ["MYDOWNLOADS"] = os.path.expanduser("~/Downloads")
    os.environ.setdefault("LOGOS_FORCE_ROOT", "")
    os.environ.setdefault("WINEBOOT_GUI", "")
    os.environ["EXTRA_INFO"] = "The following packages are usually necessary: winbind cabextract libjpeg8."
    os.environ.setdefault("DEFAULT_CONFIG_PATH", os.path.expanduser("~/.config/Logos_on_Linux/Logos_on_Linux.conf"))
    os.environ.setdefault("LOGOS_LOG", os.path.expanduser("~/.local/state/Logos_on_Linux/install.log"))
    os.makedirs(os.path.dirname(os.environ["LOGOS_LOG"]), exist_ok=True)
    open(os.environ["LOGOS_LOG"], "a").close()
    LOGOS_LOG = os.environ["LOGOS_LOG"]
    os.environ.setdefault("WINEDEBUG", "fixme-all,err-all")
    os.environ.setdefault("DEBUG", "FALSE")
    os.environ.setdefault("VERBOSE", "FALSE")

def get_config_env(config_file_path):
    try:
        with open(config_file_path, 'r') as config_file:
            config = json.load(config_file)

        for key, value in config.items():
            os.environ[key] = str(value)

        return config
    except FileNotFoundError:
        print(f"Error: Config file not found at {config_file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding config file {config_file_path}: {e}")
        return None

def write_config(config_file_path, config_keys=None):
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

    config_data = {key: os.environ[key] for key in config_keys}

    try:
        with open(config_file_path, 'w') as config_file:
            json.dump(config_data, config_file, indent=4)

        return config_data
    except IOError as e:
        print(f"Error writing to config file {config_file_path}: {e}")
        return None

def die_if_running():
    PIDF = '/tmp/LogosLinuxInstaller.pid'
    
    if os.path.isfile(PIDF):
        with open(PIDF, 'r') as f:
            pid = f.read().strip()
            if logos_continue_question("The script is already running on PID {}. Should it be killed to allow this instance to run?".format(pid), "The script is already running. Exiting.", "1"):
                os.kill(int(pid), signal.SIGKILL)
    
    def remove_pid_file():
        if os.path.exists(PIDF):
            os.remove(PIDF)
    
    atexit.register(remove_pid_file)
    with open(PIDF, 'w') as f:
        f.write(str(os.getpid()))

def die_if_root():
    if os.getuid() == 0 and not LOGOS_FORCE_ROOT:
        logos_error("Running Wine/winetricks as root is highly discouraged. Use -f|--force-root if you must run as root. See https://wiki.winehq.org/FAQ#Should_I_run_Wine_as_root.3F", "")

def verbose():
    return os.environ.get("VERBOSE")

def debug():
    return os.environ.get('DEBUG')

def setDebug():
    global DEBUG, VERBOSE, WINEDEBUG
    DEBUG = True
    VERBOSE = True
    WINEDEBUG = ""
    subprocess.run(['set', '-x'])
    with open(LOGOS_LOG, 'a') as file:
        file.write("Debug mode enabled.\n")

def die(message):
    print(message, file=sys.stderr)
    sys.exit(1)

def t(command):
    try:
        subprocess.run(['which', command], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def tl(library):
    try:
        __import__(library)
        return True
    except ImportError:
        return False

def getDialog():
    global DIALOG, GUI

    if not os.environ.get('DISPLAY'):
        logos_error("The installer does not work unless you are running a display", "")
        sys.exit(1)

    DIALOG = ""
    DIALOG_ESCAPE = ""
    GUI = ""

    if sys.__stdin__.isatty():
        if tl("curses"):
            DIALOG = "curses"
            GUI = False
            # DIALOG = "whiptail"
            # elif t("dialog"):
            # DIALOG = "dialog"
            # DIALOG_ESCAPE = "--"
            # os.environ['DIALOG_ESCAPE'] = DIALOG_ESCAPE
        else:
            if os.environ.get('XDG_CURRENT_DESKTOP') != "KDE":
                if t("zenity"):
                    DIALOG = "zenity"
                    GUI = True
                # elif t("kdialog"):
                #     DIALOG = "kdialog"
                #     GUI = True
            elif os.environ.get('XDG_CURRENT_DESKTOP') == "KDE":
                # if t("kdialog"):
                #     DIALOG = "kdialog"
                #     GUI = True
                if t("zenity"):
                    DIALOG = "zenity"
                    GUI = True
            else:
                print("No dialog program found. Please install either dialog, whiptail, zenity, or kdialog")
                sys.exit(1)
    else:
        if os.environ.get('XDG_CURRENT_DESKTOP') != "KDE":
            if t("zenity"):
                DIALOG = "zenity"
                GUI = True
        elif os.environ.get('XDG_CURRENT_DESKTOP') == "KDE":
            # if t("kdialog"):
            #     DIALOG = "kdialog"
            #     GUI = True
            if t("zenity"):
                DIALOG = "zenity"
                GUI = True
        else:
            no_diag_msg("No dialog program found. Please install either zenity or kdialog.")
            sys.exit(1)

    os.environ['DIALOG'] = DIALOG
    os.environ['GUI'] = str(GUI)

def get_os():
    # Try reading /etc/os-release
    try:
        with open('/etc/os-release', 'r') as f:
            os_release_content = f.read()
        match = re.search(r'^ID=(\S+).*?VERSION_ID=(\S+)', os_release_content, re.MULTILINE)
        if match:
            os_name = match.group(1)
            os_release = match.group(2)
            return os_name, os_release
    except FileNotFoundError:
        pass

    # Try using lsb_release command
    try:
        os_name = platform.linux_distribution()[0]
        os_release = platform.linux_distribution()[1]
        return os_name, os_release
    except AttributeError:
        pass

    # Try reading /etc/lsb-release
    try:
        with open('/etc/lsb-release', 'r') as f:
            lsb_release_content = f.read()
        match = re.search(r'^DISTRIB_ID=(\S+).*?DISTRIB_RELEASE=(\S+)', lsb_release_content, re.MULTILINE)
        if match:
            os_name = match.group(1)
            os_release = match.group(2)
            return os_name, os_release
    except FileNotFoundError:
        pass

    # Try reading /etc/debian_version
    try:
        with open('/etc/debian_version', 'r') as f:
            os_name = 'Debian'
            os_release = f.read().strip()
            return os_name, os_release
    except FileNotFoundError:
        pass

    # Add more conditions for other distributions as needed

    # Fallback to platform module
    os_name = platform.system()
    os_release = platform.release()
    return os_name, os_release

def get_package_manager():
    superuser_command = None
    package_manager_command = None
    packages = None

    # Check for superuser command
    if subprocess.run(["command", "-v", "sudo"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
        superuser_command = "sudo"
    elif subprocess.run(["command", "-v", "doas"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
        superuser_command = "doas"

    # Check for package manager and associated packages
    if subprocess.run(["command", "-v", "apt"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
        package_manager_command = "apt install -y"
        packages = "mktemp patch lsof wget find sed grep gawk tr winbind cabextract x11-apps bc libxml2-utils curl fuse3"
    elif subprocess.run(["command", "-v", "dnf"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
        package_manager_command = "dnf install -y"
        packages = "patch mod_auth_ntlm_winbind samba-winbind cabextract bc libxml2 curl"
    elif subprocess.run(["command", "-v", "yum"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
        package_manager_command = "yum install -y"
        packages = "patch mod_auth_ntlm_winbind samba-winbind cabextract bc libxml2 curl"
    elif subprocess.run(["command", "-v", "pamac"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
        package_manager_command = "pamac install --no-upgrade --no-confirm"
        packages = "patch lsof wget sed grep gawk cabextract samba bc libxml2 curl"
    elif subprocess.run(["command", "-v", "pacman"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
        package_manager_command = 'pacman -Syu --overwrite \* --noconfirm --needed'
        packages = "patch lsof wget sed grep gawk cabextract samba bc libxml2 curl print-manager system-config-printer cups-filters nss-mdns foomatic-db-engine foomatic-db-ppds foomatic-db-nonfree-ppds ghostscript glibc samba extra-rel/apparmor core-rel/libcurl-gnutls winetricks cabextract appmenu-gtk-module patch bc lib32-libjpeg-turbo qt5-virtualkeyboard wine-staging giflib lib32-giflib libpng lib32-libpng libldap lib32-libldap gnutls lib32-gnutls mpg123 lib32-mpg123 openal lib32-openal v4l-utils lib32-v4l-utils libpulse lib32-libpulse libgpg-error lib32-libgpg-error alsa-plugins lib32-alsa-plugins alsa-lib lib32-alsa-lib libjpeg-turbo lib32-libjpeg-turbo sqlite lib32-sqlite libxcomposite lib32-libxcomposite libxinerama lib32-libgcrypt libgcrypt lib32-libxinerama ncurses lib32-ncurses ocl-icd lib32-ocl-icd libxslt lib32-libxslt libva lib32-libva gtk3 lib32-gtk3 gst-plugins-base-libs lib32-gst-plugins-base-libs vulkan-icd-loader lib32-vulkan-icd-loader"
    # Add more conditions for other package managers as needed

    return superuser_command, package_manager_command, packages

def install_packages(superuser_command, package_manager_command, *packages):
    command = [superuser_command, package_manager_command] + list(packages)
    subprocess.run(command, check=True)

def have_dep(cmd):
    try:
        subprocess.run(["command -v", cmd], shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def clean_all():
    logos_info("Cleaning all temp files…")
    os.system("rm -fr /tmp/LBS.*")
    os.system("rm -fr {WORKDIR}")
    logos_info("done")

def mkdir_critical(directory):
    try:
        os.mkdir(directory)
    except OSError:
        logos_error(f"Can't create the {directory} directory", "")

def no_diag_msg(message):
    LOGOS_LOG = os.environ.get('LOGOS_LOG')
    with open(LOGOS_LOG, "a") as file:
        file.write(message + "\n")
    subprocess.Popen(["xterm", "-hold", "-e", "printf", "%s" % message])
    die()

def cli_msg(message):
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
    DIALOG = os.environ.get("DIALOG")
    if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
        cli_msg(message)
    elif DIALOG == "zenity":
        gtk_info(message)
        with open(LOGOS_LOG, "a") as file:
            file.write(f"{datetime.now()} {message}\n")
    elif DIALOG == "kdialog":
        pass

def logos_progress(title, text):
    DIALOG = os.environ.get("DIALOG")
    if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
        i = 0
        spinner = "|/-\\"
        sys.stdout.write(f"\r{text} {spinner[i]}")
        sys.stdout.flush()
        i = (i + 1) % len(spinner)
        time.sleep(0.1)
    elif DIALOG == "zenity":
        gtk_progress(title, text)
    elif DIALOG == "kdialog":
        pass
    
def logos_warn(message):
    DIALOG = os.environ.get("DIALOG")
    if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
        cli_msg(message)
    elif DIALOG == "zenity":
        gtk_warn(message)
        with open(LOGOS_LOG, "a") as file:
            file.write(f"{datetime.now()} {message}\n")
    elif DIALOG == "kdialog":
        pass

def logos_error(message, secondary):
    DIALOG = os.environ.get("DIALOG")
    WIKI_LINK = "https://github.com/ferion11/LogosLinuxInstaller/wiki"
    TELEGRAM_LINK = "https://t.me/linux_logos"
    MATRIX_LINK = "https://matrix.to/#/#logosbible:matrix.org"
    help_message = f"If you need help, please consult:\n{WIKI_LINK}\n{TELEGRAM_LINK}\n{MATRIX_LINK}"
    DIALOG = os.environ.get('DIALOG')
    if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
        cli_msg(message + "\n" + help_message)
    elif DIALOG == "zenity":
        gtk_error(message + "\n" + help_message)
        with open(LOGOS_LOG, "a") as file:
            file.write(f"{datetime.now()} {message}\n")
    elif DIALOG == "kdialog":
        pass
    if not secondary or secondary == "":
        subprocess.run(["rm", "/tmp/LogosLinuxInstaller.pid"])
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
    if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
        cli_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY)
    elif os.environ.get('DIALOG') == 'zenity':
        gtk_continue_question(QUESTION_TEXT, NO_TEXT, SECONDARY)
    elif os.environ.get('DIALOG') == 'kdialog':
        pass
        
def logos_acknowledge_question(QUESTION_TEXT, NO_TEXT):
    if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
        cli_acknowledge_question(QUESTION_TEXT, NO_TEXT)
    elif os.environ.get('DIALOG') == 'zenity':
        gtk_acknowledge_question(QUESTION_TEXT, NO_TEXT)
    elif os.environ.get('DIALOG') == 'kdialog':
        pass

def curses_menu(options, title, question_text):
    # Set up the screen
    stdscr = curses.initscr()
    curses.curs_set(0)

    current_option = 0
    current_page = 0
    options_per_page = 5
    total_pages = (len(options) - 1) // options_per_page + 1

    while True:
        stdscr.clear()

        window_height, window_width = stdscr.getmaxyx()
        window_y = window_height // 2 - options_per_page // 2
        window_x = window_width // 2 - max(len(option) for option in options) // 2

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
                    winebin_code = option[0]
                    winebin_path = option[1]
                    winebin_description = option[2]
                    option_lines = []
                    winebin_path_wrapped = textwrap.wrap(f"Binary Path: {winebin_path}", window_width - 4)
                    option_lines.extend(winebin_path_wrapped)
                    winebin_desc_wrapped = textwrap.wrap(f"Description: {winebin_description}", window_width - 4)
                    option_lines.extend(winebin_desc_wrapped)
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
        page_info = f"Page {current_page + 1}/{total_pages} | Selected Option: {current_option + 1}/{len(options)}"
        stdscr.addstr(window_height - 1, 2, page_info, curses.A_BOLD)

        # Refresh the windows
        stdscr.refresh()

        # Get user input
        key = stdscr.getch()

        if key == 65: # Up arrow
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
        elif key == 66: # Down arrow
            if current_option == (current_page + 1) * options_per_page - 1 and current_page < total_pages -1:
                # Move to the next page
                current_page += 1
                current_option = min(len(options) - 1, current_page * options_per_page)
            elif current_option == len(options) - 1:
                current_page = 0
                current_option = 0
            else:
                current_option = min(len(options) - 1, current_option + 1)
        elif key == ord('\n'): # Enter key
            choice = options[current_option]
            break

    curses.endwin()
    return choice

def cli_download(uri, destination):
    filename = os.path.basename(uri)

    if destination != destination.rstrip('/'):
        target = os.path.join(destination, os.path.basename(uri))
        if not os.path.isdir(destination):
            os.makedirs(destination)
    elif os.path.isdir(destination):
        target = os.path.join(destination, os.path.basename(uri))
    else:
        target = destination
        dirname = os.path.dirname(destination)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

    subprocess.call(['wget', '-c', uri, '-O', target])

def gtk_download(uri, destination):
    filename = os.path.basename(uri)

    if destination != destination.rstrip('/'):
        target = os.path.join(destination, os.path.basename(uri))
        if not os.path.isdir(destination):
            os.makedirs(destination)
    elif os.path.isdir(destination):
        target = os.path.join(destination, os.path.basename(uri))
    else:
        target = destination
        dirname = os.path.dirname(destination)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

    pipe_progress = subprocess.Popen(['mktemp'], stdout=subprocess.PIPE).communicate()[0].decode().strip()
    os.mkfifo(pipe_progress)

    pipe_wget = subprocess.Popen(['mktemp'], stdout=subprocess.PIPE).communicate()[0].decode().strip()
    os.mkfifo(pipe_wget)

    subprocess.Popen(['zenity', '--progress', '--title', f'Downloading {filename}...', '--text', f'Downloading: {filename}\ninto: {destination}\n', '--percentage=0', '--auto-close', pipe_wget],
                     stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

    total_size = "Starting..."
    percent = 0
    current = "Starting..."
    speed = "Starting..."
    remain = "Starting..."

    with open(pipe_progress) as progress:
        for data in progress:
            if data.startswith('Length:'):
                result = data.split('(')[-1].split(')')[0].strip()
                if len(result) <= 10:
                    total_size = result

            if any(x.isdigit() for x in data):
                result = next((x for x in data if x.isdigit()), None)
                if len(result) <= 3:
                    percent = int(result)

                result = ''.join(x for x in data if x.isdigit() or x in ['B', 'K', 'M', 'G'])
                if len(result) <= 10:
                    current = result

                result = ''.join(x for x in data if x.isdigit() or x in ['B', 'K', 'M', 'G', '.'])
                if len(result) <= 10:
                    speed = result

                result = ''.join(x for x in data if x.isalnum())
                if len(result) <= 10:
                    remain = result

            if subprocess.call(['pgrep', '-P', str(os.getpid()), 'zenity']) == 0:
                wget_pid_current = subprocess.check_output(['pgrep', '-P', str(os.getpid()), 'wget']).decode().strip()
                if wget_pid_current:
                    subprocess.call(['kill', '-SIGKILL', wget_pid_current])

            if percent == 100:
                break

            # Update zenity's progress bar
            print(percent)
            print(f"#Downloading: {filename}\ninto: {destination}\n{current} of {total_size} ({percent}%)\nSpeed: {speed}/Sec Estimated time: {remain}")

        subprocess.call(['wait', str(os.getpid())])
        wget_return = subprocess.call(['wait', str(os.getpid())])

        subprocess.call(['fuser', '-TERM', '-k', '-w', pipe_progress])
        os.remove(pipe_progress)

        subprocess.call(['fuser', '-TERM', '-k', '-w', pipe_wget])
        os.remove(pipe_wget)

        if wget_return != 0 and wget_return != 127:
            raise Exception("ERROR: The installation was cancelled because of an error while attempting a download.\nAttmpted Downloading: {uri}\nTarget Destination: {destination}\nFile Name: {filename}\n- Error Code: WGET_RETURN: {wget_return}")

    print(f"{filename} download finished!")

def logos_download(uri, destination):
    if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
        cli_download(uri, destination)
    elif os.environ.get('DIALOG') == 'zenity':
        gtk_download(uri, destination)
    elif os.environ.get('DIALOG') == 'kdialog':
        raise NotImplementedError("kdialog not implemented.")
    else:
        raise Exception("No dialog tool found.")

def logos_reuse_download(SOURCEURL, FILE, TARGETDIR):
    INSTALLDIR = os.environ.get('INSTALLDIR')
    DOWNLOADS = os.path.expanduser("~/Downloads")
    DIRS = [
        INSTALLDIR,
        os.getcwd(),
        DOWNLOADS
    ]
    FOUND = 1
    for i in DIRS:
        if os.path.isfile(os.path.join(i, FILE)):
            logos_info(f"{FILE} exists in {i}. Using it…")
            shutil.copy(os.path.join(i, FILE), TARGETDIR)
            logos_progress("Copying…", f"Copying {FILE}\ninto {TARGETDIR}")
            FOUND = 0
            break
    if FOUND == 1:
        logos_info(f"{FILE} does not exist. Downloading…")
        logos_download(SOURCEURL, os.path.join(DOWNLOADS, FILE))
        shutil.copy(os.path.join(DOWNLOADS, FILE), TARGETDIR)
        logos_progress("Copying…", f"Copying: {FILE}\ninto: {TARGETDIR}")

def getAppImage():
    WINE64_APPIMAGE_FULL_URL = os.environ.get('WINE64_APPIMAGE_FULL_URL')
    WINE64_APPIMAGE_FULL_FILENAME = os.environ.get('WINE64_APPIMAGE_FULL_FILENAME')
    APPDIR_BINDIR = os.environ.get('APPDIR_BINDIR')
    logos_reuse_download(WINE64_APPIMAGE_FULL_URL, WINE64_APPIMAGE_FULL_FILENAME, APPDIR_BINDIR)

def wait_process_using_dir(directory):
    #TODO: Something in here is returning a NoneType
    VERIFICATION_DIR = directory
    VERIFICATION_TIME = 7
    VERIFICATION_NUM = 3

    verbose()
    print("* Starting wait_process_using_dir…")
    i = 0
    while True:
        i += 1
        verbose()
        print(f"wait_process_using_dir: loop with i={i}")

        print(f"wait_process_using_dir: sleep {VERIFICATION_TIME}")
        time.sleep(VERIFICATION_TIME)

        try:
            FIRST_PID = subprocess.check_output(["lsof", "-t", VERIFICATION_DIR]).decode().split("\n")[0]
        except subprocess.CalledProcessError:
            FIRST_PID = ""
        verbose()
        print(f"wait_process_using_dir FIRST_PID: {FIRST_PID}")
        if FIRST_PID:
            i = 0
            verbose()
            print(f"wait_process_using_dir: tail --pid={FIRST_PID} -f /dev/null")
            subprocess.run(["tail", "--pid", FIRST_PID, "-f", "/dev/null"])
            continue

        if i >= VERIFICATION_NUM:
            break
    verbose()
    print("* End of wait_process_using_dir.")

def wait_on(cmd):
    command = cmd
    try:
        # Start the process in the background
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        while process.poll() is None:
            logos_progress("Waiting.", f"Waiting on {command} to finish.")

        # Process has finished, check the result
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            print(f"\n{command} has ended properly.")
        else:
            print(f"\nError: {stderr}")
    
    except Exception as e:
        print(f"Error: {e}")

def light_wineserver_wait():
    WINE_EXE = os.environ.get('WINE_EXE')
    WINESERVER_EXE = os.environ.get('WINESERVER_EXE')
    command = [f"{WINESERVER_EXE}", "-w"]
    wait_on(command)

def heavy_wineserver_wait():
    WINE_EXE = os.environ.get('WINE_EXE')
    WINESERVER_EXE = os.environ.get('WINESERVER_EXE')
    WINEPREFIX = os.environ.get('WINEPREFIX')
    wait_on([wait_process_using_dir(WINEPREFIX)])
    wait_on([f"{WINESERVER_EXE}", "-w"])

def make_skel(app_image_filename):
    INSTALLDIR = os.environ.get('INSTALLDIR')
    APPDIR = os.environ.get('APPDIR')
    APPDIR_BINDIR = os.environ.get('APPDIR_BINDIR')
    APPIMAGE_LINK_SELECTION_NAME = os.environ.get('APPIMAGE_LINK_SELECTION_NAME')

    SET_APPIMAGE_FILENAME = app_image_filename

    verbose()
    print(f"* Making skel64 inside {INSTALLDIR}")
    subprocess.run(["mkdir", "-p", APPDIR_BINDIR]) or die(f"can't make dir: {APPDIR_BINDIR}")

    # Making the links
    current_dir = os.getcwd()
    try:
        os.chdir(APPDIR_BINDIR)
    except OSError as e:
        die(f"ERROR: Can't open dir: {APPDIR_BINDIR}: {e}")
    subprocess.run(["ln", "-s", SET_APPIMAGE_FILENAME, f"{APPDIR_BINDIR}/{APPIMAGE_LINK_SELECTION_NAME}"])
    subprocess.run(["ln", "-s", APPIMAGE_LINK_SELECTION_NAME, "wine"])
    subprocess.run(["ln", "-s", APPIMAGE_LINK_SELECTION_NAME, "wine64"])
    subprocess.run(["ln", "-s", APPIMAGE_LINK_SELECTION_NAME, "wineserver"])
    try:
        os.chdir(current_dir)
    except OSError as e:
        die("ERROR: Can't go back to preview dir!: {e}")

    subprocess.run(["mkdir", f"{APPDIR}/wine64_bottle"])

    verbose()
    print("skel64 done!")

def check_commands(superuser_command, package_manager_command, os_name, missing_commands, packages, extra_info):
    missing_cmd = []
    for cmd in missing_commands:
        if have_dep(cmd):
            print(f"* Command {cmd} is installed!")
        else:
            print(f"* Command {cmd} not installed!")
            missing_cmd.append(cmd)

    if missing_cmd:
        if package_manager_command:
            message = f"Your {os_name} install is missing the command(s): {missing_cmd}. To continue, the script will attempt to install the package(s): {packages} by using ({package_manager_command}). Proceed?"
            if os_name == "Steam":
                subprocess.run([superuser_command, "steamos-readonly", "disable"], check=True)
                subprocess.run([superuser_command, "pacman-key", "--init"], check=True)
                subprocess.run([superuser_command, "pacman-key", "--populate", "archlinux"], check=True)

            if logos_continue_question(message, extra_info):
                install_packages(superuser_command, package_manager_command, packages)

                if os_name == "Steam":
                    subprocess.run([superuser_command, "sed", '-i', 's/mymachines resolve/mymachines mdns_minimal [NOTFOUND=return] resolve/', '/etc/nsswitch.conf'], check=True)
                    subprocess.run([superuser_command, "locale-gen"], check=True)
                    subprocess.run([superuser_command, "systemctl", "enable", "--now", "avahi-daemon"], check=True)
                    subprocess.run([superuser_command, "systemctl", "enable", "--now", "cups"], check=True)
                    subprocess.run([superuser_command, "steamos-readonly", "enable"], check=True)
        else:
            logos_error(f"The script could not determine your {os_name} install's package manager or it is unsupported. Your computer is missing the command(s) {missing_cmd}. Please install your distro's package(s) associated with {missing_cmd} for {os_name}.\n{extra_info}")

def have_lib(library, ld_library_path):
    ldconfig_cmd = ["ldconfig", "-N", "-v", ":".join(ld_library_path.split(':'))]
    try:
        result = subprocess.run(ldconfig_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
        return library in result.stdout
    except subprocess.CalledProcessError:
        return False

def check_libs(superuser_command, package_manager_command, libraries, packages):
    ld_library_path = os.environ.get('LD_LIBRARY_PATH')
    for library in libraries:
        have_lib_result = have_lib(library, ld_library_path)
        if have_lib_result:
            print(f"* {library} is installed!")
        else:
            if package_manager_command:
                message = f"Your {os_name} install is missing the library: {library}. To continue, the script will attempt to install the library by using {package_manager_command}. Proceed?"
                if logos_continue_question(message, extra_info):
                    install_packages(superuser_command, package_manager_command, packages)
            else:
                logos_error(f"The script could not determine your {os_name} install's package manager or it is unsupported. Your computer is missing the library: {library}. Please install the package associated with {library} for {os_name}.\n{extra_info}")

def checkDependencies():
    verbose()
    print("Checking system's for dependencies:")
    check_commands("mktemp", "patch", "lsof", "wget", "find", "sed", "grep", "ntlm_auth", "awk", "tr", "bc", "xmllint", "curl")

def checkDependenciesLogos10():
    verbose()
    print("All dependencies found. Continuing…")

def checkDependenciesLogos9():
    verbose()
    print("Checking dependencies for Logos 9.")
    check_commands("xwd", "cabextract");
    verbose()
    print("All dependencies found. Continuing…")

def chooseProduct():
    BACKTITLE = "Choose Product Menu"
    TITLE = "Choose Product"
    QUESTION_TEXT = "Choose which FaithLife product the script should install:"
    if not os.environ.get("FLPRODUCT"):
        DIALOG = os.environ.get("DIALOG")
        if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
            options = ["Logos", "Verbum", "Exit"]
            productChoice = curses_menu(options, TITLE, QUESTION_TEXT)
        elif DIALOG == "zenity":
            process = subprocess.Popen(["zenity", "--width=700", "--height=310", "--title=" + TITLE, "--text=" + QUESTION_TEXT, "--list", "--radiolist", "--column", "S", "--column", "Description", "TRUE", "Logos Bible Software.", "FALSE", "Verbum Bible Software.", "FALSE", "Exit."], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            productChoice, _ = process.communicate()
        elif DIALOG == "kdialog":
            sys.exit("kdialog not implemented.")
        else:
            sys.exit("No dialog tool found")
    else:
        productChoice = os.environ.get("FLPRODUCT")

    print("productChoice:" + str(productChoice))
    if str(productChoice).startswith("Logos"):
        verbose()
        print("Installing Logos Bible Software")
        os.environ["FLPRODUCT"] = "Logos"
        os.environ["FLPRODUCTi"] = "logos4" #This is the variable referencing the icon path name in the repo.
        os.environ["VERBUM_PATH"] = "/"
    elif str(productChoice).startswith("Verbum"):
        verbose()
        print("Installing Verbum Bible Software")
        os.environ["FLPRODUCT"] = "Verbum"
        os.environ["FLPRODUCTi"] = "verbum" #This is the variable referencing the icon path name in the repo.
        os.environ["VERBUM_PATH"] = "/Verbum/"
    elif str(productChoice).startswith("Exit"):
        logos_error("Exiting installation.", "")
    else:
        logos_error("Unknown product. Installation canceled!", "")

    if not os.environ.get("LOGOS_ICON_URL"):
        os.environ["LOGOS_ICON_URL"] = "https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/img/" + os.environ.get("FLPRODUCTi") + "-128-icon.png"

def getLogosReleaseVersion(targetversion):
    os.environ['TARGETVERSION'] = TARGETVERSION = targetversion
    url = f"https://clientservices.logos.com/update/v1/feed/logos{TARGETVERSION}/stable.xml"

    try:
        # Fetch XML content using requests
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad responses

        # Parse XML
        root = ET.fromstring(response.text)
        xmldata = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8")
        # Define namespaces
        namespaces = {
            'ns0': 'http://www.w3.org/2005/Atom',
            'ns1': 'http://services.logos.com/update/v1/'
        }

        # Extract versions
        releases = []
        
        # Obtain last five releases
        for entry in root.findall('.//ns1:version', namespaces):
            release = entry.text
            releases.append(release)
        
            #if len(releases) == 5:
            #    break

        FLPRODUCT = os.environ.get('FLPRODUCT')

        TITLE=f"Choose {FLPRODUCT} {TARGETVERSION} Release"
        QUESTION_TEXT=f"Which version of {FLPRODUCT} {TARGETVERSION} do you want to install?"
        logos_release_version = curses_menu(releases, TITLE, QUESTION_TEXT)
    except requests.RequestException as e:
        print(f"Error fetching or parsing XML: {e}")
        return None

    if logos_release_version is not None:
        global LOGOS_RELEASE_VERSION
        LOGOS_RELEASE_VERSION = logos_release_version
        os.environ["LOGOS_RELEASE_VERSION"] = logos_release_version
    else:
        print("Failed to fetch LOGOS_RELEASE_VERSION.")

def chooseVersion():
    TARGETVERSION = os.environ.get('TARGETVERSION')
    DIALOG = os.environ.get('DIALOG')
    BACKTITLE = "Choose Version Menu"
    TITLE = "Choose Product Version"
    QUESTION_TEXT = f"Which version of {os.environ.get('FLPRODUCT')} should the script install?"
    if TARGETVERSION is None or TARGETVERSION == "":
        if os.environ.get('DIALOG') in ["whiptail", "dialog", "curses"]:
            options = ["10", "9", "Exit"]
            versionChoice = curses_menu(options, TITLE, QUESTION_TEXT)
        elif DIALOG == "zenity":
            command = ["zenity", "--width=700", "--height=310", "--title", TITLE, "--text", QUESTION_TEXT, "--list", "--radiolist", "--column", "S", "--column", "Description", "TRUE", f"{FLPRODUCT} 10", "FALSE", f"{FLPRODUCT} 9", "FALSE", "Exit"]
            versionChoice = subprocess.check_output(command, stderr=subprocess.STDOUT).decode().strip()
        elif DIALOG == "kdialog":
            no_diag_msg("kdialog not implemented.")
        else:
            no_diag_msg("No dialog tool found.")
    else:
        versionChoice = TARGETVERSION
   
    checkDependencies()
    if "10" in versionChoice:
        checkDependenciesLogos10()
        os.environ["TARGETVERSION"] = TARGETVERSION = "10"
    elif "9" in versionChoice:
        checkDependenciesLogos9()
        os.environ["TARGETVERSION"] = TARGETVERSION = "9"
    elif versionChoice == "Exit.":
        exit()
    else:
        logos_error("Unknown version. Installation canceled!", "")

def logos_setup():
    getLogosReleaseVersion(TARGETVERSION)

    global LOGOS_RELEASE_VERSION

    LOGOS64_URL=""
    if LOGOS64_URL is None or LOGOS64_URL == "":
        LOGOS64_URL = f"https://downloads.logoscdn.com/LBS{TARGETVERSION}{os.environ.get('VERBUM_PATH')}Installer/{os.environ.get('LOGOS_RELEASE_VERSION')}/{os.environ.get('FLPRODUCT')}-x64.msi"
        os.environ['LOGOS64_URL'] = LOGOS64_URL

    global LOGOS_VERSION

    if os.environ.get('FLPRODUCT') == "Logos":
        LOGOS_VERSION = LOGOS64_URL.split('/')[5]
    elif os.environ.get('FLPRODUCT') == "Verbum":
        LOGOS_VERSION = LOGOS64_URL.split('/')[6]
    else:
        logos_error("FLPRODUCT not set in config. Please update your config to specify either 'Logos' or 'Verbum'.", "")
    os.environ['LOGOS_VERSION'] = LOGOS_VERSION

    LOGOS64_MSI = os.path.basename(LOGOS64_URL)
    os.environ['LOGOS64_MSI'] = LOGOS64_MSI
    
    if os.environ.get('INSTALLDIR') is None or os.environ.get('INSTALLDIR') == "":
        INSTALLDIR = f"{os.environ.get('HOME')}/{os.environ.get('FLPRODUCT')}Bible{TARGETVERSION}"
        os.environ['INSTALLDIR'] = INSTALLDIR
    if os.environ.get('APPDIR') is None or os.environ.get('APPDIR') == "":
        APPDIR = f"{INSTALLDIR}/data"
        os.environ['APPDIR'] = APPDIR
    if os.environ.get('APPDIR_BINDIR') is None or os.environ.get('APPDIR_BINDIR') == "":
        APPDIR_BINDIR = f"{APPDIR}/bin"
        os.environ['APPDIR_BINDIR'] = APPDIR_BINDIR

def wineBinaryVersionCheck(TESTBINARY):
    TARGETVERSION = os.environ.get('TARGETVERSION')

    # Does not check for Staging. Will not implement: expecting merging of commits in time.
    if TARGETVERSION == "10":
        WINE_MINIMUM = "7.18"
    elif TARGETVERSION == "9":
        WINE_MINIMUM = "7.0"
    else:
        raise ValueError("TARGETVERSION not set.")

    # Check if the binary is executable. If so, check if TESTBINARY's version is ≥ WINE_MINIMUM, or if it is Proton or a link to a Proton binary, else remove.
    if not os.path.exists(TESTBINARY):
        reason = "Binary does not exist."
        return False, reason

    if not os.access(TESTBINARY, os.X_OK):
        reason = "Binary is not executable."
        return False, reason

    cmd = [TESTBINARY, "--version"]
    version_string = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
    version_number = version_string.split("-")[-1]

    if version_number is None:
        reason = "Version is none."
        return False, reason

    TESTWINEVERSION = float(version_number)

    if TESTWINEVERSION == 8.0:
        reason = "Version is 8.0."
        return False, reason

    if "Proton" in TESTBINARY or ("Proton" in os.path.realpath(TESTBINARY) if os.path.islink(TESTBINARY) else False):
        if TESTWINEVERSION == 7.0:
            return True, "None"
        else:
            reason = "Proton version is too low."
            return False, reason

    if TESTWINEVERSION < float(WINE_MINIMUM):
        reason = "Version is below minimum required."
        return False, reason

    return True, "None"

def createWineBinaryList():
    logos_info("Creating binary list.")
    CUSTOMBINPATH = os.environ.get("CUSTOMBINPATH", "")

    WineBinPathList = [
        "/usr/local/bin",
        os.path.expanduser("~") + "/bin",
        os.path.expanduser("~") + "/PlayOnLinux/wine/linux-amd64/*/bin",
        os.path.expanduser("~") + "/.steam/steam/steamapps/common/Proton*/files/bin",
        CUSTOMBINPATH
    ]

    # Temporarily modify PATH for additional WINE64 binaries.
    for p in WineBinPathList:
        if p not in os.environ['PATH'] and os.path.isdir(p):
            os.environ['PATH'] = os.environ['PATH'] + os.pathsep + p

    # Check each directory in PATH for wine64; add to list
    binaries = []
    paths = os.environ["PATH"].split(":")
    for path in paths:
        binary_path = os.path.join(path, "wine64")
        if os.path.exists(binary_path) and os.access(binary_path, os.X_OK):
            binaries.append(binary_path)

    for binary in binaries[:]:
        output1, output2 = wineBinaryVersionCheck(binary)
        if output1 is not None and output1:
            continue
        else:
            binaries.remove(binary)
            print(f"Removing binary:", binary, "because:", output2)
    
    return binaries

def chooseInstallMethod():
    if not os.environ.get("WINEPREFIX"):
        os.environ["WINEPREFIX"] = os.path.join(os.environ["APPDIR"], "wine64_bottle")

    if not os.environ.get("WINE_EXE"):
        binaries = createWineBinaryList()
        WINEBIN_OPTIONS = []
        
        # Add AppImage to list
        if os.environ["TARGETVERSION"] != "9":
            if os.environ.get('DIALOG') in ["whiptail", "dialog", "curses"]:
                WINEBIN_OPTIONS.append(["AppImage", f"{os.environ['APPDIR_BINDIR']}/{os.environ['WINE64_APPIMAGE_FULL_FILENAME']}", f"AppImage of Wine64 {os.environ['WINE64_APPIMAGE_FULL_VERSION']}"])
            elif DIALOG == "zenity":
                WINEBIN_OPTIONS.append(["FALSE", "AppImage", f"AppImage of Wine64 {os.environ['WINE64_APPIMAGE_FULL_VERSION']}", os.path.join(os.environ["APPDIR_BINDIR"], os.environ["WINE64_APPIMAGE_FULL_FILENAME"])])
            elif os.environ["DIALOG"] == "kdialog":
                no_diag_msg("kdialog not implemented.")
            else:
                no_diag_msg("No dialog tool found.")
        
        for binary in binaries:
            WINEBIN_PATH = binary
            
            # Set binary code, description, and path based on path
            if "/usr/bin/" in binary:
                WINEBIN_CODE = "System"
                WINEBIN_DESCRIPTION = "Use the system binary (i.e., /usr/bin/wine64). WINE must be 7.18-staging or later. Stable or Devel do not work."
            elif "Proton" in binary:
                WINEBIN_CODE = "Proton"
                WINEBIN_DESCRIPTION = "Install using the Steam Proton fork of WINE."
            elif "PlayOnLinux" in binary:
                WINEBIN_CODE = "PlayOnLinux"
                WINEBIN_DESCRIPTION = "Install using a PlayOnLinux WINE64 binary."
            else:
                WINEBIN_CODE = "Custom"
                WINEBIN_DESCRIPTION = "Use a WINE64 binary from another directory."

            # Create wine binary option array
            if os.environ.get('DIALOG') in ["whiptail", "dialog", "curses"]:
                WINEBIN_OPTIONS.append([WINEBIN_CODE, WINEBIN_PATH, WINEBIN_DESCRIPTION])
            elif os.environ["DIALOG"] == "zenity":
                WINEBIN_OPTIONS.append([WINEBIN_CODE, WINEBIN_DESCRIPTION, WINEBIN_PATH])
            elif os.environ["DIALOG"] == "kdialog":
                no_diag_msg("kdialog not implemented.")
            else:
                no_diag_msg("No dialog tool found.")

        FLPRODUCT=os.environ.get("FLPRODUCT", "")
        LOGOS_VERSION=os.environ.get("LOGOS_VERSION", "")
        INSTALLDIR=os.environ.get("INSTALLDIR", "")
        BACKTITLE="Choose Wine Binary Menu"
        TITLE="Choose Wine Binary"
        QUESTION_TEXT=f"Which Wine binary and install method should the script use to install {FLPRODUCT} v{LOGOS_VERSION} in {INSTALLDIR}?"

    if os.environ.get('DIALOG') in ["whiptail", "dialog", "curses"]:
        installationChoice = curses_menu(WINEBIN_OPTIONS, TITLE, QUESTION_TEXT)
        WINECHOICE_CODE = installationChoice[0]
        WINE_EXE = installationChoice[1]
    elif os.environ["DIALOG"] == "zenity":
        column_names = ["--column", "Choice", "--column", "Code", "--column", "Description", "--column", "Path"]
        installationChoice = subprocess.check_output(["zenity", "--width=1024", "--height=480", "--title=" + TITLE, "--text=" + QUESTION_TEXT, "--list", "--radiolist"] + column_names + WINEBIN_OPTIONS + ["--print-column=2,3,4"]).decode().strip()
        installArray = installationChoice.split('|')
        WINECHOICE_CODE = installArray[0]
        WINE_EXE = installArray[2]
    elif os.environ["DIALOG"] == "kdialog":
        no_diag_msg("kdialog not implemented.")
    else:
        no_diag_msg("No dialog tool found.")

    os.environ['WINEBIN_CODE'] = WINECHOICE_CODE
    os.environ['WINE_EXE'] = WINE_EXE
    verbose()
    print(f"chooseInstallMethod(): WINEBIN_CODE: {WINECHOICE_CODE}; WINE_EXE: {WINE_EXE}")

def checkExistingInstall():
    # Now that we know what the user wants to install and where, determine whether an install exists and whether to continue.
    INSTALLDIR = os.environ.get('INSTALLDIR')
    if os.path.isdir(INSTALLDIR):
        if any(os.path.isfile(os.path.join(INSTALLDIR, file)) for file in ['Logos.exe', 'Verbum.exe']):
            global EXISTING_LOGOS_INSTALL
            EXISTING_LOGOS_INSTALL = 1
            print(f"An install was found at {INSTALLDIR}. Please remove/rename it or use another location by setting the INSTALLDIR variable.")
        else:
            global EXISTING_LOGOS_DIRECTORY
            EXISTING_LOGOS_DIRECTORY = 1
            print(f"A directory exists at {INSTALLDIR}. Please remove/rename it or use another location by setting the INSTALLDIR variable.")
    else:
        if verbose:
            print(f"Installing to an empty directory at {INSTALLDIR}.")


def beginInstall():
    SKEL = os.environ.get('SKEL')
    REGENERATE = os.environ.get('REGENERATE')
    WINEBIN_CODE = os.environ.get('WINEBIN_CODE')
    FLPRODUCT = os.environ.get('FLPRODUCT')
    TARGETVERSION = os.environ.get('TARGETVERSION')
    WINE64_APPIMAGE_FULL_VERSION = os.environ.get('WINE64_APPIMAGE_FULL_VERSION')
    WINE64_APPIMAGE_FULL_FILENAME = os.environ.get('WINE64_APPIMAGE_FULL_FILENAME')
    APPDIR_BINDIR = os.environ.get('APPDIR_BINDIR')
    WINE_EXE = os.environ.get('WINE_EXE')
    if SKEL == "1":
        if verbose:
            print("Making a skeleton install of the project only. Exiting after completion.")
        make_skel("none.AppImage")
        exit(0)

    if WINEBIN_CODE:
        if WINEBIN_CODE.startswith("AppImage"):
            check_libs("libfuse")
            if verbose:
                print(f"Installing {FLPRODUCT} Bible {TARGETVERSION} using {WINE64_APPIMAGE_FULL_VERSION} AppImage…")
            if not REGENERATE:
                make_skel(WINE64_APPIMAGE_FULL_FILENAME)
                # exporting PATH to internal use if using AppImage, doing backup too:
                os.environ["OLD_PATH"] = os.environ["PATH"]
                os.environ["PATH"] = f"{APPDIR_BINDIR}:{os.environ['PATH']}"
                # Geting the AppImage:
                getAppImage()
                os.chmod(f"{APPDIR_BINDIR}/{WINE64_APPIMAGE_FULL_FILENAME}", 0o755)
                os.environ["WINE_EXE"] = f"{APPDIR_BINDIR}/wine64"
        elif WINEBIN_CODE in ["System", "Proton", "PlayOnLinux", "Custom"]:
            if verbose:
                print(f"Installing {FLPRODUCT} Bible {TARGETVERSION} using a {WINEBIN_CODE} WINE64 binary…")
            if not REGENERATE:
                make_skel("none.AppImage")
        else:
            print("WINEBIN_CODE error. Installation canceled!")
            sys.exit(1)
    else:
        if verbose:
            print("WINEBIN_CODE is not set in your config file.")

    if verbose:
        wine_version = subprocess.check_output([WINE_EXE, "--version"]).decode().strip()
        print(f"Using: {wine_version}")

    # Set WINESERVER_EXE based on WINE_EXE.
    WINESERVER_EXE = os.environ.get('WINESERVER_EXE')
    if not WINESERVER_EXE or WINESERVER_EXE == "":
        wineserver_path = os.path.join(os.path.dirname(WINE_EXE), "wineserver")
        if os.path.exists(wineserver_path):
            os.environ["WINESERVER_EXE"] = WINESERVER_EXE = wineserver_path

        else:
            print(f"{wineserver_path} not found. Please either add it or create a symlink to it, and rerun.")

def run_wine_proc(winecmd, exe, flags):
    env = os.environ.copy()
    WINEPREFIX = os.environ.get('WINEPREFIX')

    if flags is not None or "":
        command = [winecmd, exe, flags]
    else:
        command = [winecmd, exe]

    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={"WINEPREFIX": WINEPREFIX}, text=True)

        if process.returncode != 0:
            print (f"Error 1 running {winecmd} {exe}: {return_code}")

    except subprocess.CalledProcessError as e:
        print (f"Error 2 running {winecmd} {exe}: {e}")

def initializeWineBottle():
    #logos_continue_question(f"Now the script will create and configure the Wine Bottle at {WINEPREFIX}. You can cancel the installation of Mono. Do you wish to continue?", f"The installation was cancelled!", "")
    run_wine_proc(wineboot)
    light_wineserver_wait()

def wine_reg_install(REG_FILENAME):
    WORKDIR = os.environ.get('WORKDIR')
    WINEPREFIX = os.environ.get('WINEPREFIX')
    WINE_EXE = os.environ.get('WINE_EXE')
    FILENAME=str(REG_FILENAME)
    process = subprocess.Popen([WINE_EXE, "regedit.exe", REG_FILENAME], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={"WINEPREFIX": WINEPREFIX}, text=True, cwd=WORKDIR)
    print(f"{FILENAME} installed.")
    light_wineserver_wait()
    
def downloadWinetricks():
    APPDIR_BINDIR = os.environ.get('APPDIR_BINDIR')
    WINETRICKS_URL = os.environ.get('WINETRICKS_URL')
    logos_reuse_download(WINETRICKS_URL, "winetricks", APPDIR_BINDIR)
    os.chmod(f"{APPDIR_BINDIR}/winetricks", 0o755)

def setWinetricks():
    APPDIR_BINDIR = os.environ.get('APPDIR_BINDIR')
    WINETRICKSBIN = os.environ.get('WINETRICKSBIN')
    DIALOG = os.environ.get('DIALOG')
    # Check if local winetricks version available; else, download it
    if not "WINETRICKSBIN" in os.environ:
        if subprocess.call(["which", "winetricks"]) == 0:
            # Check if local winetricks version is up-to-date; if so, offer to use it or to download; else, download it
            local_winetricks_version = subprocess.check_output(["winetricks", "--version"]).split()[0]
            if str(local_winetricks_version) >= "20220411":
                backtitle = "Choose Winetricks Menu"
                title = "Choose Winetricks"
                question_text = "Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that FLPRODUCT requires on Linux."
                if os.environ.get('DIALOG') in ["whiptail", "dialog", "curses"]:
                    options = ["1: Use local winetricks.", "2: Download winetricks from the Internet"]
                    winetricks_choice = curses_menu(options, title, question_text)
                elif os.getenv("DIALOG") == "zenity":
                    winetricks_choice = subprocess.Popen(
                        ["zenity", "--width=700", "--height=310", "--title=" + title, "--text=" + question_text, "--list", "--radiolist", "--column", "S", "--column", "Description", "TRUE", "1- Use local winetricks.", "FALSE", "2- Download winetricks from the Internet."], 
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                elif os.getenv("DIALOG") == "kdialog":
                    sys.exit("kdialog not implemented.")
                else:
                    sys.exit("No dialog tool found.")

                print(f"winetricks_choice: {winetricks_choice}")
                if winetricks_choice.startswith("1"):
                    print("Setting winetricks to the local binary…")
                    os.environ["WINETRICKSBIN"] = subprocess.check_output(["which", "winetricks"]).decode('utf-8').strip()
                elif winetricks_choice.startswith("2"):
                    downloadWinetricks()
                    os.environ["WINETRICKSBIN"] = os.path.join(os.getenv("APPDIR_BINDIR"), "winetricks")
                else:
                    sys.exit("Installation canceled!")
            else:
                print("The system's winetricks is too old. Downloading an up-to-date winetricks from the Internet...")
                downloadWinetricks()
                os.environ["WINETRICKSBIN"] = os.path.join(os.getenv("APPDIR_BINDIR"), "winetricks")
        else:
            print("Local winetricks not found. Downloading winetricks from the Internet…")
            downloadWinetricks()
            os.environ["WINETRICKSBIN"] = os.path.join(os.getenv("APPDIR_BINDIR"), "winetricks")

    print("Winetricks is ready to be used.")

def winetricks_install(*args):
    WINETRICKSBIN = os.environ.get('WINETRICKSBIN')
    verbose and print("winetricks", *args)
    if DIALOG in ["whiptail", "dialog", 'curses']:
        subprocess.call([WINETRICKSBIN, *args])
    elif DIALOG == "zenity":
        pipe_winetricks = tempfile.mktemp()
        os.mkfifo(pipe_winetricks)

        # zenity GUI feedback
        logos_progress("Winetricks " + " ".join(args), "Winetricks installing " + " ".join(args), input=open(pipe_winetricks))

        proc = subprocess.Popen([WINETRICKSBIN, *args], stdout=subprocess.PIPE)
        with open(pipe_winetricks, "w") as pipe:
            for line in proc.stdout:
                pipe.write(line)
                print(line.decode(), end="")

        WINETRICKS_STATUS = proc.wait()
        ZENITY_RETURN = proc.poll()

        os.remove(pipe_winetricks)

        # NOTE: sometimes the process finishes before the wait command, giving the error code 127
        if ZENITY_RETURN == 0 or ZENITY_RETURN == 127:
            if WINETRICKS_STATUS != 0:
                subprocess.call([WINESERVER_EXE, "-k"])
                logos_error("Winetricks Install ERROR: The installation was cancelled because of sub-job failure!\n * winetricks " + " ".join(args) + "\n  - WINETRICKS_STATUS: " + str(WINETRICKS_STATUS), "")
        else:
            subprocess.call([WINESERVER_EXE, "-k"])
            logos_error("The installation was cancelled!\n * ZENITY_RETURN: " + str(ZENITY_RETURN), "")
    elif DIALOG == "kdialog":
        no_diag_msg("kdialog not implemented.")
    else:
        no_diag_msg("No dialog tool found.")

    verbose and print("winetricks", *args, "DONE!")

    heavy_wineserver_wait()

def winetricks_dll_install(*args):
    WINETRICKSBIN = os.environ.get('WINETRICKSBIN')
    verbose and print("winetricks", *args)
    #logos_continue_question("Now the script will install the DLL " + " ".join(args) + ". This may take a while. There will not be any GUI feedback for this. Continue?", "The installation was cancelled!", "")
    subprocess.call([WINETRICKSBIN, *args])
    verbose and print("winetricks", *args, "DONE!")
    heavy_wineserver_wait()

def getPremadeWineBottle():
    WINE64_BOTTLE_TARGZ_URL = os.environ.get('WINE64_BOTTLE_TARGZ_URL')
    WINE64_BOTTLE_TARGZ_NAME = os.environ.get('WINE64_BOTTLE_TARGZ_NAME')
    WORKDIR = os.environ.get('WORKDIR')
    APPDIR = os.environ.get('APPDIR')
    verbose and print("Installing pre-made wineBottle 64bits…")
    logos_reuse_download(WINE64_BOTTLE_TARGZ_URL, WINE64_BOTTLE_TARGZ_NAME, WORKDIR)
    subprocess.call(["tar", "xzf", os.path.join(WORKDIR, WINE64_BOTTLE_TARGZ_NAME), "-C", APPDIR])
    logos_progress("Extracting…", "Extracting: " + WINE64_BOTTLE_TARGZ_NAME + "\ninto: " + APPDIR)

## END WINE BOTTLE AND WINETRICKS FUNCTIONS
## BEGIN LOGOS INSTALL FUNCTIONS 
def installFonts():
    if os.environ.get('WINETRICKS_UNATTENDED') is None:
        if os.environ.get('SKIP_FONTS') is None:
            winetricks_install('-q', 'corefonts')
            winetricks_install('-q', 'tahoma')
    else:
        if os.environ.get('SKIP_FONTS') is None:
            winetricks_install('corefonts')
            winetricks_install('tahoma')
    winetricks_install('-q', 'settings', 'fontsmooth=rgb')

def installD3DCompiler():
    if os.environ.get('WINETRICKS_UNATTENDED') is None:
        winetricks_dll_install('-q', 'd3dcompiler_47')
    else:
        winetricks_dll_install('d3dcompiler_47')

def get_logos_executable():
    LOGOS_EXECUTABLE = os.environ.get('LOGOS_EXECUTABLE')
    LOGOS64_URL = os.environ.get('LOGOS64_URL')
    LOGOS64_MSI = os.environ.get('LOGOS64_MSI')
    FLPRODUCT = os.environ.get('FLPRODUCT')
    LOGOS_VERSION = os.environ.get('LOGOS_VERSION')
    PRESENT_WORKING_DIRECTORY = os.environ.get('PRESENT_WORKING_DIRECTORY')
    APPDIR = os.environ.get('APPDIR')
    HOME = os.environ.get('HOME')
    # This VAR is used to verify the downloaded MSI is latest
    if not LOGOS_EXECUTABLE:
        os.environ["LOGOS_EXECUTABLE"] = LOGOS_EXECUTABLE = f"{FLPRODUCT}_v{LOGOS_VERSION}-x64.msi"
    
    #logos_continue_question(f"Now the script will check for the MSI installer. Then it will download and install {FLPRODUCT} Bible at {WINEPREFIX}. You will need to interact with the installer. Do you wish to continue?", "The installation was cancelled!", "")
    
    # Getting and installing {FLPRODUCT} Bible
    # First check current directory to see if the .MSI is present; if not, check user's Downloads/; if not, download it new. Once found, copy it to WORKDIR for future use.
    verbose() and print(f"Installing {FLPRODUCT}Bible 64bits…")
    if os.path.isfile(f"{PRESENT_WORKING_DIRECTORY}/{LOGOS_EXECUTABLE}"):
        verbose() and print(f"{LOGOS_EXECUTABLE} exists. Using it…")
        shutil.copy(f"{PRESENT_WORKING_DIRECTORY}/{LOGOS_EXECUTABLE}", f"{APPDIR}/")
    elif os.path.isfile(f"{HOME}/Downloads/{LOGOS_EXECUTABLE}"):
        verbose() and print(f"{LOGOS_EXECUTABLE} exists. Using it…")
        shutil.copy(f"{HOME}/Downloads/{LOGOS_EXECUTABLE}", f"{APPDIR}/")
    else:
        verbose() and print(f"{LOGOS_EXECUTABLE} does not exist. Downloading…")
        logos_download(LOGOS64_URL, f"{HOME}/Downloads/")
        shutil.move(f"{HOME}/Downloads/{LOGOS64_MSI}", f"{HOME}/Downloads/{LOGOS_EXECUTABLE}")
        shutil.copy(f"{HOME}/Downloads/{LOGOS_EXECUTABLE}", f"{APPDIR}/")

def install_msi():
    LOGOS_EXECUTABLE = os.environ.get('LOGOS_EXECUTABLE')
    WINEPREFIX = os.environ.get('WINEPREFIX')
    WINE_EXE = os.environ.get('WINE_EXE')
    APPDIR = os.environ.get('APPDIR')
    env = os.environ.copy()
    # Execute the .MSI
    verbose() and print(f"Running: {WINE_EXE} msiexec /i {APPDIR}/{LOGOS_EXECUTABLE}")
    subprocess.run([WINE_EXE, "msiexec", "/i", f"{APPDIR}/{LOGOS_EXECUTABLE}"], env=env)

def installLogos9():
    FLPRODUCT = os.environ.get('FLPRODUCT')
    WINE_EXE = os.environ.get('WINE_EXE')
    getPremadeWineBottle()
    setWinetricks()
    installFonts()
    installD3DCompiler()
    get_logos_executable()
    install_msi()

    if verbose():
        print("======= Set {}Bible Indexing to Vista Mode: =======".format(FLPRODUCT))
    os.system('{} reg add "HKCU\\Software\\Wine\\AppDefaults\\{}Indexer.exe" /v Version /t REG_SZ /d vista /f'.format(WINE_EXE, FLPRODUCT))
    if verbose():
        print("======= {}Bible logging set to Vista mode! =======".format(FLPRODUCT))

def installLogos10():
    WORKDIR = os.environ.get('WORKDIR')
    WINETRICKS_UNATTENDED = os.environ.get('WINETRICKS_UNATTENDED')
    with open(os.path.join(WORKDIR, 'disable-winemenubuilder.reg'), 'w') as reg_file, \
            open(os.path.join(WORKDIR, 'renderer_gdi.reg'), 'w') as gdi_file:
        reg_file.write('''REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\Direct3D]
"DirectDrawRenderer"="gdi"
"renderer"="gdi"
''')
        gdi_file.write('''REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\Direct3D]
"DirectDrawRenderer"="gdi"
"renderer"="gdi"
''')

    wine_reg_install(f"{reg_file}")
    wine_reg_install(f"{gdi_file}")

    setWinetricks()
    installFonts()
    installD3DCompiler()

    if not WINETRICKS_UNATTENDED:
        winetricks_install("-q settings win10")
    else:
        winetricks_install("settings win10")

    get_logos_executable()
    install_msi()

def postInstall():
    LOGOS_EXE = os.environ.get('LOGOS_EXE')
    FLPRODUCT = os.environ.get('FLPRODUCT')
    TARGETVERSION = os.environ.get('TARGETVERSION')
    CONFIG_FILE = os.environ.get('CONFIG_FILE')
    DEFAULT_CONFIG_PATH = os.environ.get('DEFAULT_CONFIG_PATH')
    INSTALLDIR = os.environ.get('INSTALLDIR')
    HOME = os.environ.get('HOME')
    config_keys = ["FLPRODUCT", "FLPRODUCTi", "TARGETVERSION", "INSTALLDIR", "APPDIR", "APPDIR_BINDIR", "WINETRICKSBIN", "WINEPREFIX", "WINEBIN_CODE", "WINE_EXE", "WINESERVER_EXE", "WINE64_APPIMAGE_FULL_URL", "WINE64_APPIMAGE_FULL_FILENAME", "APPIMAGE_LINK_SELECTION_NAME", "LOGOS_EXECUTABLE", "LOGOS_EXE", "LOGOS_DIR", "LOGS", "BACKUPDIR"]

    if os.path.isfile(LOGOS_EXE):
        logos_info(f"{FLPRODUCT} Bible {TARGETVERSION} installed!")
        if not CONFIG_FILE and not os.path.isfile(DEFAULT_CONFIG_PATH):
            os.makedirs(os.path.join(HOME, ".config", "Logos_on_Linux"), exist_ok=True)
            if os.path.isdir(os.path.join(HOME, ".config", "Logos_on_Linux")):
                write_config(CONFIG_FILE, config_keys)
                logos_info(f"A config file was created at {DEFAULT_CONFIG_PATH}.")
            else:
                logos_warn(f"{HOME}/.config/Logos_on_Linux does not exist. Failed to create config file.")
        elif not CONFIG_FILE and os.path.isfile(DEFAULT_CONFIG_PATH):
            if logos_acknowledge_question(f"The script found a config file at {DEFAULT_CONFIG_PATH}. Should the script overwrite the existing config?", "The existing config file was not overwritten."):
                if os.path.isdir(os.path.join(HOME, ".config", "Logos_on_Linux")):
                    write_config(CONFIG_FILE, config_keys)
                else:
                    logos_warn(f"{HOME}/.config/Logos_on_Linux does not exist. Failed to create config file.")
        else:
            # Script was run with a config file. Skip modifying the config.
            pass

        if logos_acknowledge_question("A launch script has been placed in {INSTALLDIR} for your use. The script's name is {FLPRODUCT}.sh.\nDo you want to run it now?\nNOTE: There may be an error on first execution. You can close the error dialog.", "The Script has finished. Exiting…"):
            subprocess.run([os.path.join(INSTALLDIR, f"{FLPRODUCT}.sh")])
        elif verbose:
            print("The script has finished. Exiting…")
    else:
        logos_error("Installation failed. {LOGOS_EXE} not found. Exiting…\nThe {FLPRODUCT} executable was not found. This means something went wrong while installing {FLPRODUCT}. Please contact the Logos on Linux community for help.", "")

def parse_command_line():
    parser = argparse.ArgumentParser(description=f'Installs {os.environ.get("FLPRODUCT")} Bible Software with Wine on Linux.')
    parser.add_argument('--version', '-v', action='version', version=f'{os.environ.get("LOGOS_SCRIPT_TITLE")}, {os.environ.get("LOGOS_SCRIPT_VERSION")} by {os.environ.get("LOGOS_SCRIPT_AUTHOR")}')
    parser.add_argument('--config', '-c', metavar='CONFIG_FILE', help='Use the Logos on Linux config file when setting environment variables. Defaults to ~/.config/Logos_on_Linux/Logos_on_Linux.conf. Optionally can accept a config file provided by the user.')
    parser.add_argument('--verbose', '-V', action='store_true', help='Enable verbose mode')
    parser.add_argument('--skip-fonts', '-F', action='store_true', help='Skip font installations')
    parser.add_argument('--force-root', '-f', action='store_true', help='Set LOGOS_FORCE_ROOT to true, which permits the root user to use the script.')
    parser.add_argument('--reinstall-dependencies', '-I', action='store_true', help="Reinstall your distro's dependencies.")
    parser.add_argument('--regenerate-scripts', '-r', action='store_true', help='Regenerate the Logos.sh and controlPanel.sh scripts.')
    parser.add_argument('--debug', '-D', action='store_true', help='Enable Wine debug output.')
    parser.add_argument('--make-skel', '-k', action='store_true', help='Make a skeleton install only.')
    parser.add_argument('--custom-binary-path', '-b', metavar='CUSTOMBINPATH', help='Specify a custom wine binary path.')
    parser.add_argument('--check-resources', '-R', action='store_true', help='Check resources and exit')
    parser.add_argument('--edit-config', '-e', action='store_true', help='Edit configuration file')
    parser.add_argument('--indexing', '-i', action='store_true', help='Perform indexing')
    parser.add_argument('--backup', '-b', action='store_true', help='Perform backup')
    parser.add_argument('--restore', '-r', action='store_true', help='Perform restore')
    parser.add_argument('--logs', '-l', action='store_true', help='Enable/disable logs')
    parser.add_argument('--dirlink', '-d', action='store_true', help='Create directory link')
    parser.add_argument('--shortcut', '-s', action='store_true', help='Create shortcut')

    args = parser.parse_args()

    if args.config:
        os.environ['CONFIG_FILE'] = CONFIG_FILE
        get_config_env(CONFIG_FILE)

    if args.verbose:
        os.environ["VERBOSE"] = "true"

    if args.skip_fonts:
        os.environ["SKIP_FONTS"] = "1"

    if args.force_root:
        os.environ["LOGOS_FORCE_ROOT"] = "1"

    if args.reinstall_dependencies:
        os.environ["REINSTALL_DEPENDENCIES"] = "1"

    if args.regenerate_scripts:
        os.environ["REGENERATE"] = "1"

    if args.debug:
        setDebug()

    if args.make_skel:
        os.environ["SKEL"] = "1"

    if args.custom_binary_path:
        if os.path.isdir(args.custom_binary_path):
            os.environ["CUSTOMBINPATH"] = args.custom_binary_path
        else:
            sys.stderr.write(f"{LOGOS_SCRIPT_TITLE}: User supplied path: \"{args.custom_binary_path}\". Custom binary path does not exist.\n")
            parser.print_help()
            sys.exit()

def file_exists(file_path):
    if file_path is not None:
        expanded_path = os.path.expanduser(file_path)
        return os.path.isfile(expanded_path)
    else:
        return False

def install():
    # BEGIN PREPARATION
    REGENERATE = os.environ.get('REGENERATE')
    LOGOS_LOG = os.environ.get('LOGOS_LOG')
    if verbose:
        print(datetime.datetime.now())
    chooseProduct()  # We ask user for his Faithlife product's name and set variables.
    if verbose:
        print(datetime.datetime.now())
    chooseVersion()  # We ask user for his Faithlife product's version, set variables, and create project skeleton.
    if verbose:
        print(datetime.datetime.now())
    logos_setup() # We set some basic variables for the install, including retrieving the product's latest release.
    if verbose:
        print(datetime.datetime.now())
    chooseInstallMethod()  # We ask user for his desired install method.
    # END PREPARATION
    
    TARGETVERSION = os.environ.get('TARGETVERSION')
    LOGOS_EXE = os.environ.get('LOGOS_EXE')
    FLPRODUCT = os.environ.get('FLPRODUCT')
    WINEPREFIX = os.environ.get('WINEPREFIX')

    if REGENERATE is None or REGENERATE == "":
        if verbose:
            print(datetime.datetime.now())
        checkExistingInstall()
        
        if verbose:
            print(datetime.datetime.now())
        beginInstall()

        if verbose:
            print(datetime.datetime.now())
        initializeWineBottle()  # We run wineboot.
        
        if TARGETVERSION == "10":
            if verbose:
                print(datetime.datetime.now())
            installLogos10()  # We run the commands specific to Logos 10.
        elif TARGETVERSION == "9":
            if verbose:
                print(datetime.datetime.now())
            installLogos9()  # We run the commands specific to Logos 9.
        else:
            logos_error(f"TARGETVERSION unrecognized: '{TARGETVERSION}'. Installation canceled!", "")
        
        if verbose:
            print(datetime.datetime.now())
        create_starting_scripts()
        
        heavy_wineserver_wait()
        
        clean_all()
        
        LOGOS_EXE = subprocess.run(["find", WINEPREFIX, "-name", f"{FLPRODUCT}.exe"], capture_output=True, text=True).stdout.strip()
        os.environ["LOGOS_EXE"] = LOGOS_EXE
        
        if verbose:
            print(datetime.datetime.now())
        postInstall()
    else:
        create_starting_scripts()
        logos_info("The scripts have been regenerated.")
    
    with open(LOGOS_LOG, "a") as f:
        f.write(output)

def run_logos():
    env = os.environ.copy()
    WINE_EXE = os.environ.get('WINE_EXE')
    LOGOS_EXE = os.environ.get('LOGOS_EXE')
    WINESERVER_EXE = os.environ.get('WINESERVER_EXE')

    run_wine_proc(WINE_EXE, LOGOS_EXE)
    run_wine_proc(WINESERVER_EXE, "-w")

def run_indexing():
    WINEPREFIX = os.environ.get('WINEPREFIX')
    WINE_EXE = os.environ.get('WINE_EXE')
    WINESERVER_EXE = os.environ.get('WINESERVER_EXE')

    for root, dirs, files in os.walk(os.path.join(wineprefix, "drive_c")):
        for file in files:
            if file == "LogosIndexer.exe" and root.endswith("Logos/System"):
                logos_indexer_exe = os.path.join(root, file)
                break

    run_wine_proc(WINESERVER_EXE, "-k")
    run_wine_proc(WINE_EXE, logos_indexer_exe)
    run_wine_proc(WINESERVER_EXE, "-w")

def remove_library_catalog():
    LOGOS_EXE = os.environ.get('LOGOS_EXE')
    LOGOS_DIR = os.path.dirname(LOGO_EXE)
    library_catalog_path = os.path.join(LOGOS_DIR, "Data", "*", "LibraryCatalog")
    pattern = os.path.join(library_catalog_path, "*")
    files_to_remove = glob.glob(pattern)
    for file_to_remove in files_to_remove:
        try:
            os.remove(file_to_remove)
            print(f"Removed: {file_to_remove}")
        except OSError as e:
            print(f"Error removing {file_to_remove}: {e}")

def remove_all_index_files():
    LOGOS_EXE = os.environ.get('LOGOS_EXE')
    LOGOS_DIR = os.path.dirname(LOGO_EXE)
    index_paths = [
        os.path.join(logos_dir, "Data", "*", "BibleIndex"),
        os.path.join(logos_dir, "Data", "*", "LibraryIndex"),
        os.path.join(logos_dir, "Data", "*", "PersonalBookIndex"),
        os.path.join(logos_dir, "Data", "*", "LibraryCatalog")
    ]
    for index_path in index_paths:
        pattern = os.path.join(index_path, "*")
        files_to_remove = glob.glob(pattern)

        for file_to_remove in files_to_remove:
            try:
                os.remove(file_to_remove)
                print(f"Removed: {file_to_remove}")
            except OSError as e:
                print(f"Error removing {file_to_remove}: {e}")

    print("======= Removing all LogosBible index files done! =======")
    exit(0)

def set_appimage(newappimage):
    WINE64_APPIMAGE_FULL_VERSION = os.environ["WINE64_APPIMAGE_FULL_VERSION"]
    WINE64_APPIMAGE_FULL_URL = os.environ["WINE64_APPIMAGE_FULL_URL"]
    WINE64_APPIMAGE_FULL_FILENAME = os.environ["WINE64_APPIMAGE_FULL_FILENAME"]
    WINE64_APPIMAGE_VERSION = os.environ["WINE64_APPIMAGE_VERSION"]
    WINE64_APPIMAGE_URL = os.environ["WINE64_APPIMAGE_URL"]
    WINE64_APPIMAGE_FILENAME = os.environ["WINE64_APPIMAGE_FILENAME"]
    APPIMAGE_LINK_SELECTION_NAME = os.environ["APPIMAGE_LINK_SELECTION_NAME"]
    subprocess.run(["ln", "-s", SET_APPIMAGE_FILENAME, f"{APPDIR_BINDIR}/{APPIMAGE_LINK_SELECTION_NAME}"])

def create_shortcut():
    APPDIR = os.environ.get('APPDIR')
    FLPRODUCT = os.environ.get('FLPRODUCT')
    FLPRODUCTi = os.environ.get('FLPRODUCTi')
    LOGOS_ICON_FILENAME = os.environ.get('LOGOS_ICON_FILENAME')

    if not os.environ.get("LOGOS_ICON_URL"):
        os.environ["LOGOS_ICON_URL"] = "https://raw.githubusercontent.com/ferion11/LogosLinuxInstaller/master/img/" + os.environ.get("FLPRODUCTi") + "-128-icon.png"

    logos_icon_path = os.path.join(APPDIR, "data", LOGOS_ICON_FILENAME)

    if not os.path.isfile(logos_icon_path):
        os.makedirs(os.path.join(APPDIR, "data"), exist_ok=True)
        response = requests.get(LOGOS_ICON_URL, stream=True)
        if response.status_code == 200:
            with open(logos_icon_path, 'wb') as f:
                shutil.copyfileobj(response.raw, f)

    desktop_entry_path = os.path.expanduser(f"~/.local/share/applications/{FLPRODUCT}Bible.desktop")
    if os.path.exists(desktop_entry_path):
        os.remove(desktop_entry_path)

    with open(desktop_entry_path, 'w') as desktop_file:
        desktop_file.write(f"""[Desktop Entry]
Name={FLPRODUCT}Bible
Comment=A Bible Study Library with Built-In Tools
Exec={APPDIR}/Logos.sh
Icon={logos_icon_path}
Terminal=false
Type=Application
Categories=Education;
""")

    os.chmod(desktop_entry_path, 0o755)

def edit_config():
    pass

def backup():
    pass

def restore():
    pass

def run_control_panel():
    env = os.environ.copy()
    WINE_EXE = os.environ.get('WINE_EXE')
    WINESERVER_EXE = os.environ.get('WINESERVER_EXE')

    run_wine_proc(WINE_EXE, "control")
    run_wine_proc(WINESERVER_EXE, "-w")

def run_winetricks():
    env = os.environ.copy()
    WINETRICKSBIN = os.environ.get('WINETRICKSBIN')
    WINESERVER_EXE = os.environ.get('WINESERVER_EXE')

    run_wine_proc(WINETRICKSBIN, "control")
    run_wine_proc(WINESERVER_EXE, "-w")

def disable_logging():
    CONFIG_FILE = os.environ.get('CONFIG_FILE')
    WINEPREFIX = os.environ.get('WINEPREFIX')
    WINE_EXE = os.environ.get('WINE_EXE')
    subprocess.run([WINE_EXE, 'reg', 'add', 'HKCU\\Software\\Logos4\\Logging', '/v', 'Enabled', '/t', 'REG_DWORD', '/d', '0001', '/f'], env={"WINEPREFIX": WINEPREFIX})
    subprocess.run([wineserver_exe, '-w'])

    for line in fileinput.input(CONFIG_FILE, inplace=True):
        print(line.replace('LOGS="ENABLED"', 'LOGS="DISABLED"'), end='')

def enable_logging():
    CONFIG_FILE = os.environ.get('CONFIG_FILE')
    WINEPREFIX = os.environ.get('WINEPREFIX')
    WINE_EXE = os.environ.get('WINE_EXE')
    subprocess.run([WINE_EXE, 'reg', 'add', 'HKCU\\Software\\Logos4\\Logging', '/v', 'Disabled', '/t', 'REG_DWORD', '/d', '0000', '/f'], env={"WINEPREFIX": WINEPREFIX})
    subprocess.run([wineserver_exe, '-w'])

    for line in fileinput.input(CONFIG_FILE, inplace=True):
        print(line.replace('LOGS="DISABLED"', 'LOGS="ENABLED"'), end='')

def main():
    if not os.environ.get("DIALOG"):
        getDialog()
        
    if os.environ.get("GUI") == "true":
        with open(LOGOS_LOG, "a") as f:
            f.write("Running in a GUI. Enabling logging.\n")
        setDebug()

    die_if_running()
    die_if_root()

    os_name, os_release = get_os()

    superuser_command, package_manager_command, packages = get_package_manager()

    parse_command_line()

    LOGOS_SCRIPT_TITLE = os.environ.get('LOGOS_SCRIPT_TITLE')
    LOGOS_SCRIPT_VERSION = os.environ.get('LOGOS_SCRIPT_VERSION')
    LOGOS_SCRIPT_AUTHOR = os.environ.get('LOGOS_SCRIPT_AUTHOR')

    print(f"{os.environ.get('LOGOS_SCRIPT_TITLE')}, {os.environ.get('LOGOS_SCRIPT_VERSION')} by {os.environ.get('LOGOS_SCRIPT_AUTHOR')}.")

    CONFIG_FILE = os.environ.get('CONFIG_FILE')
    options_default = ["Install Logos Bible Software"]
    options_exit = ["Exit"]
    if file_exists(CONFIG_FILE):
        get_config_env(CONFIG_FILE)
        options_installed = [f"Run {FLPRODUCT}", "Run Indexing", "Remove Library Catalog", "Remove All Index Files", "Edit Config", "Reinstall Dependencies", "Back up Data", "Restore Data", "Set AppImage", "Control Panel", "Run Winetricks"]
        if os.environ["LOGS"] == "DISABLED":
            options_installed.extend("Enable Logging")
        else:
            options_installed.extend("Disable Logging")
        options = options_default + options_installed + options_exit
    else:
        set_default_env()
        options = options_default + options_exit

    if os.environ.get('DIALOG') in ['whiptail', 'dialog', 'curses']:
        choice = curses_menu(options, "Welcome to Logos on Linux", "What would you like to do?")
    elif DIALOG == "zenity":
        gtk_info(message)
        with open(LOGOS_LOG, "a") as file:
            file.write(f"{datetime.now()} {message}\n")
    elif DIALOG == "kdialog":
        logos_error("kdialog not implemented.", "")

    if "Install" in choice:
        install()
    elif f"Run {FLPRODUCT}" in choice:
        run_logos()
    elif "Run Indexing" in choice:
        run_indexing()
    elif "Remove Library Catalog" in choice:
        remove_library_catalog()
    elif "Remove All Index Files" in choice:
        remove_all_index_files()
    elif "Edit Config" in choice:
        edit_config()
    elif "Reinstall Dependencies":
        os_name, os_release = get_os()
        superuser_command, package_manager_command, packages = get_package_manager()
        checkDependencies()
    elif "Back up Data" in choice:
        backup()
    elif "Restore Data" in choice:
        restore()
    elif "Set AppImage" in choice:
        set_appimage()
    elif "Control Panel" in choice:
        run_control_panel()
    elif "Run Winetricks" in choice:
        run_winetricks()
    elif "Logging" in choice:
        if os.environ["LOGS"] == "DISABLED":
            enable_logging()
        else:
            disable_logging()
    elif "Exit" in choice:
        sys.exit(0)
    else:
        logos_error("Unknown menu choice.", "")
# END FUNCTION DECLARATIONS
# BEGIN SCRIPT EXECUTION
main()

sys.exit(0)
# END SCRIPT EXECUTION
