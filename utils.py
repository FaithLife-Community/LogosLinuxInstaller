import atexit
import curses
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request

from base64 import b64encode
from pathlib import Path
from xml.etree import ElementTree as ET

import config
from msg import logos_continue_question
from msg import logos_error
from msg import logos_info
from wine import get_pids_using_file
from wine import wineBinaryVersionCheck


class Props():
    def __init__(self, uri=None):
        self.path = None
        self.size = None
        self.md5 = None
        if uri is not None:
            self.path = uri

class FileProps(Props):
    def __init__(self, f=None):
        super().__init__(f)
        self.path = Path(self.path)
        if f is not None:
            self.get_size()
            # self.get_md5()

    def get_size(self):
        if self.path is None:
            return
        self.size = self.path.stat().st_size
        return self.size

    def get_md5(self):
        if self.path is None:
            return
        md5 = hashlib.md5()
        with self.path.open('rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5.update(chunk)
        self.md5 = b64encode(md5.digest()).decode('utf-8')
        return self.md5

class UrlProps(Props):
    def __init__(self, url=None):
        super().__init__(url)
        self.header = None
        if url is not None:
            self.get_header()
            self.get_size()
            # self.get_md5()

    def get_header(self):
        if self.path is None:
            self.header = None
        cmd = ['wget', '--no-verbose', '--spider', '--server-response', self.path]
        p = subprocess.run(cmd, stderr=subprocess.PIPE, text=True)
        self.header = p.stderr
        return self.header

    def get_size(self):
        if self.header is None:
            self.get_header()
        m = re.findall(r'^\s*Content-Length: ([0-9]+)$', self.header, flags=re.MULTILINE)
        if len(m) > 0:
            self.size = int(m[-1])
        return self.size

    def get_md5(self):
        if self.header is None:
            self.get_header()
        m = re.findall(r'^\s*Content-MD5: ([0-9a-zA-Z=+/_-]+)$', self.header, flags=re.MULTILINE)
        if len(m) > 0:
            self.md5 = m[0]
        return self.md5


# Set "global" variables.
def set_default_config():
    get_os()
    get_package_manager()
    if config.CONFIG_FILE is None:
        config.CONFIG_FILE = config.DEFAULT_CONFIG_PATH
    config.PRESENT_WORKING_DIRECTORY = os.getcwd()
    config.MYDOWNLOADS = get_user_downloads_dir()
    os.makedirs(os.path.dirname(config.LOGOS_LOG), exist_ok=True)

def write_config(config_file_path, config_keys=None):
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

    config_data = {key: config.__dict__.get(key) for key in config_keys}

    try:
        with open(config_file_path, 'w') as config_file:
            json.dump(config_data, config_file, indent=4, sort_keys=True)
            config_file.write('\n')

    except IOError as e:
        print(f"Error writing to config file {config_file_path}: {e}")

def die_if_running():
    PIDF = '/tmp/LogosLinuxInstaller.pid' # FIXME: it's not clear when or how this would get created
    
    if os.path.isfile(PIDF):
        with open(PIDF, 'r') as f:
            pid = f.read().strip()
            if logos_continue_question(f"The script is already running on PID {pid}. Should it be killed to allow this instance to run?", "The script is already running. Exiting.", "1"):
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

def debug():
    return config.DEBUG

def die(message):
    logging.critical(message)
    sys.exit(1)

def setDebug():
    config.DEBUG = True
    config.VERBOSE = True
    config.WINEDEBUG = ""
    with open(config.LOGOS_LOG, 'a') as f:
        f.write("Debug mode enabled.\n")

def t(command):
    if shutil.which(command) is not None:
        return True
    else:
        return False

def tl(library):
    try:
        __import__(library)
        return True
    except ImportError:
        return False

def getDialog():
    if not os.environ.get('DISPLAY'):
        logos_error("The installer does not work unless you are running a display", "")
        sys.exit(1)

    if sys.__stdin__.isatty():
        if tl("curses"):
            config.DIALOG = "curses"
            config.GUI = False
            # DIALOG = "whiptail"
            # elif t("dialog"):
            # DIALOG = "dialog"
            # DIALOG_ESCAPE = "--"
            # os.environ['DIALOG_ESCAPE'] = DIALOG_ESCAPE
        else:
            if os.environ.get('XDG_CURRENT_DESKTOP') != "KDE":
                if t("zenity"):
                    config.DIALOG = "zenity"
                    config.GUI = True
                # elif t("kdialog"):
                #     DIALOG = "kdialog"
                #     GUI = True
            elif os.environ.get('XDG_CURRENT_DESKTOP') == "KDE":
                # if t("kdialog"):
                #     DIALOG = "kdialog"
                #     GUI = True
                if t("zenity"):
                    config.DIALOG = "zenity"
                    config.GUI = True
            else:
                logging.critical("No dialog program found. Please install either dialog, whiptail, zenity, or kdialog")
                sys.exit(1)
    else:
        if os.environ.get('XDG_CURRENT_DESKTOP') != "KDE":
            if t("zenity"):
                config.DIALOG = "zenity"
                config.GUI = True
        elif os.environ.get('XDG_CURRENT_DESKTOP') == "KDE":
            # if t("kdialog"):
            #     DIALOG = "kdialog"
            #     GUI = True
            if t("zenity"):
                config.DIALOG = "zenity"
                config.GUI = True
        else:
            no_diag_msg("No dialog program found. Please install either zenity or kdialog.")
            sys.exit(1)

def get_os():
    # Try reading /etc/os-release
    try:
        with open('/etc/os-release', 'r') as f:
            os_release_content = f.read()
        match = re.search(r'^ID=(\S+).*?VERSION_ID=(\S+)', os_release_content, re.MULTILINE)
        if match:
            config.OS_NAME = match.group(1)
            config.OS_RELEASE = match.group(2)
            return config.OS_NAME, config.OS_RELEASE
    except FileNotFoundError:
        pass

    # Try using lsb_release command
    try:
        config.OS_NAME = platform.linux_distribution()[0]
        config.OS_RELEASE = platform.linux_distribution()[1]
        return config.OS_NAME, config.OS_RELEASE
    except AttributeError:
        pass

    # Try reading /etc/lsb-release
    try:
        with open('/etc/lsb-release', 'r') as f:
            lsb_release_content = f.read()
        match = re.search(r'^DISTRIB_ID=(\S+).*?DISTRIB_RELEASE=(\S+)', lsb_release_content, re.MULTILINE)
        if match:
            config.OS_NAME = match.group(1)
            config.OS_RELEASE = match.group(2)
            return config.OS_NAME, config.OS_RELEASE
    except FileNotFoundError:
        pass

    # Try reading /etc/debian_version
    try:
        with open('/etc/debian_version', 'r') as f:
            config.OS_NAME = 'Debian'
            config.OS_RELEASE = f.read().strip()
            return config.OS_NAME, config.OS_RELEASE
    except FileNotFoundError:
        pass

    # Add more conditions for other distributions as needed

    # Fallback to platform module
    config.OS_NAME = platform.system()
    config.OS_RELEASE = platform.release()
    return config.OS_NAME, config.OS_RELEASE

def get_package_manager():

    # Check for superuser command
    if shutil.which('sudo') is not None:
        config.SUPERUSER_COMMAND = "sudo"
    elif shutil.which('doas') is not None:
        config.SUPERUSER_COMMAND = "doas"

    # Check for package manager and associated packages
    if shutil.which('apt') is not None:
        config.PACKAGE_MANAGER_COMMAND = "apt install -y"
        # FIXME: bash is only a dependency for the built-in 'wait' command, which
        #   is currently only used in the gtk_download() function.
        config.PACKAGES = "bash binutils cabextract fuse procps wget winbind"
    elif shutil.which('dnf') is not None:
        config.PACKAGE_MANAGER_COMMAND = "dnf install -y"
        config.PACKAGES = "patch mod_auth_ntlm_winbind samba-winbind cabextract bc libxml2 curl"
    elif shutil.which('yum') is not None:
        config.PACKAGE_MANAGER_COMMAND = "yum install -y"
        config.PACKAGES = "patch mod_auth_ntlm_winbind samba-winbind cabextract bc libxml2 curl"
    elif shutil.which('pamac') is not None:
        config.PACKAGE_MANAGER_COMMAND = "pamac install --no-upgrade --no-confirm"
        config.PACKAGES = "patch wget sed grep gawk cabextract samba bc libxml2 curl"
    elif shutil.which('pacman') is not None:
        config.PACKAGE_MANAGER_COMMAND = 'pacman -Syu --overwrite \* --noconfirm --needed'
        config.PACKAGES = "patch wget sed grep gawk cabextract samba bc libxml2 curl print-manager system-config-printer cups-filters nss-mdns foomatic-db-engine foomatic-db-ppds foomatic-db-nonfree-ppds ghostscript glibc samba extra-rel/apparmor core-rel/libcurl-gnutls winetricks cabextract appmenu-gtk-module patch bc lib32-libjpeg-turbo qt5-virtualkeyboard wine-staging giflib lib32-giflib libpng lib32-libpng libldap lib32-libldap gnutls lib32-gnutls mpg123 lib32-mpg123 openal lib32-openal v4l-utils lib32-v4l-utils libpulse lib32-libpulse libgpg-error lib32-libgpg-error alsa-plugins lib32-alsa-plugins alsa-lib lib32-alsa-lib libjpeg-turbo lib32-libjpeg-turbo sqlite lib32-sqlite libxcomposite lib32-libxcomposite libxinerama lib32-libgcrypt libgcrypt lib32-libxinerama ncurses lib32-ncurses ocl-icd lib32-ocl-icd libxslt lib32-libxslt libva lib32-libva gtk3 lib32-gtk3 gst-plugins-base-libs lib32-gst-plugins-base-libs vulkan-icd-loader lib32-vulkan-icd-loader"
    # Add more conditions for other package managers as needed

def install_packages(*packages):
    command = [config.SUPERUSER_COMMAND, config.PACKAGE_MANAGER_COMMAND] + list(packages)
    subprocess.run(command, check=True)

def have_dep(cmd):
    if shutil.which(cmd) is not None:
        return True
    else:
        return False

def clean_all():
    logos_info("Cleaning all temp files…")
    os.system("rm -fr /tmp/LBS.*")
    os.system(f"rm -fr {config.WORKDIR}")
    os.system(f"rm -f {config.PRESENT_WORKING_DIRECTORY}/wget-log*")
    logos_info("done")

def mkdir_critical(directory):
    try:
        os.mkdir(directory)
    except OSError:
        logos_error(f"Can't create the {directory} directory", "")

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
    cli_msg(f"Downloading '{uri}' to '{destination}'")
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

    pipe_progress = '/tmp/logos_pipe_progress'
    os.mkfifo(pipe_progress)

    pipe_wget = '/tmp/logos_pipe_wget'
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
                    os.kill(int(wget_pid_current), signal.SIGKILL)

            if percent == 100:
                break

            # Update zenity's progress bar
            print(percent)
            print(f"#Downloading: {filename}\ninto: {destination}\n{current} of {total_size} ({percent}%)\nSpeed: {speed}/Sec Estimated time: {remain}")

        # FIXME: This will ultimately fail:
        # - 'wait' is a bash built-in; so the command would need to be ['bash', '-c', 'wait pid']
        # - it will probably also return the error: "pid ### is not a child of this shell"
        subprocess.call(['wait', wget_pid_current])
        wget_return = 0 # this somehow needs to be the return code of the wget process

        for pipe in [pipe_progress, pipe_wget]:
            for pid in get_pids_using_file(pipe, mode='w'):
                os.kill(pid, signal.SIGTERM)
            os.remove(pipe)

        if wget_return != 0 and wget_return != 127:
            raise Exception("ERROR: The installation was cancelled because of an error while attempting a download.\nAttmpted Downloading: {uri}\nTarget Destination: {destination}\nFile Name: {filename}\n- Error Code: WGET_RETURN: {wget_return}")

    logging.info(f"{filename} download finished!")

def set_appimage():
    os.symlink(config.WINE64_APPIMAGE_FILENAME, f"{config.APPDIR_BINDIR}/{config.APPIMAGE_LINK_SELECTION_NAME}")

def make_skel(app_image_filename):
    config.SET_APPIMAGE_FILENAME = app_image_filename

    logging.info(f"* Making skel64 inside {config.INSTALLDIR}")
    os.makedirs(config.APPDIR_BINDIR, exist_ok=True)

    # Making the links
    current_dir = os.getcwd()
    try:
        os.chdir(config.APPDIR_BINDIR)
    except OSError as e:
        die(f"ERROR: Can't open dir: {config.APPDIR_BINDIR}: {e}")
    if not os.path.islink(f"{config.APPDIR_BINDIR}/{config.APPIMAGE_LINK_SELECTION_NAME}"):
        os.symlink(config.SET_APPIMAGE_FILENAME, f"{config.APPDIR_BINDIR}/{config.APPIMAGE_LINK_SELECTION_NAME}")
    for name in ["wine", "wine64", "wineserver"]:
        if not os.path.islink(name):
            os.symlink(config.APPIMAGE_LINK_SELECTION_NAME, name)
    try:
        os.chdir(current_dir)
    except OSError as e:
        die("ERROR: Can't go back to previous dir!: {e}")

    os.makedirs(f"{config.APPDIR}/wine64_bottle", exist_ok=True)

    logging.info("skel64 done!")

def check_commands(commands):
    missing_cmd = []
    for cmd in commands:
        if have_dep(cmd):
            logging.info(f"* Command {cmd} is installed!")
        else:
            logging.warning(f"* Command {cmd} not installed!")
            missing_cmd.append(cmd)

    if missing_cmd:
        if config.PACKAGE_MANAGER_COMMAND:
            message = f"Your {config.OS_NAME} install is missing the command(s): {missing_cmd}. To continue, the script will attempt to install the package(s): {config.PACKAGES} by using ({config.PACKAGE_MANAGER_COMMAND}). Proceed?"
            if config.OS_NAME == "Steam":
                subprocess.run([config.SUPERUSER_COMMAND, "steamos-readonly", "disable"], check=True)
                subprocess.run([config.SUPERUSER_COMMAND, "pacman-key", "--init"], check=True)
                subprocess.run([config.SUPERUSER_COMMAND, "pacman-key", "--populate", "archlinux"], check=True)

            if logos_continue_question(message, config.EXTRA_INFO):
                install_packages(config.PACKAGES)

                if config.OS_NAME == "Steam":
                    subprocess.run([config.SUPERUSER_COMMAND, "sed", '-i', 's/mymachines resolve/mymachines mdns_minimal [NOTFOUND=return] resolve/', '/etc/nsswitch.conf'], check=True)
                    subprocess.run([config.SUPERUSER_COMMAND, "locale-gen"], check=True)
                    subprocess.run([config.SUPERUSER_COMMAND, "systemctl", "enable", "--now", "avahi-daemon"], check=True)
                    subprocess.run([config.SUPERUSER_COMMAND, "systemctl", "enable", "--now", "cups"], check=True)
                    subprocess.run([config.SUPERUSER_COMMAND, "steamos-readonly", "enable"], check=True)
        else:
            logos_error(f"The script could not determine your {config.OS_NAME} install's package manager or it is unsupported. Your computer is missing the command(s) {missing_cmd}. Please install your distro's package(s) associated with {missing_cmd} for {config.OS_NAME}.\n{config.EXTRA_INFO}")

def have_lib(library, ld_library_path):
    ldconfig_cmd = ["ldconfig", "-N", "-v", ":".join(ld_library_path.split(':'))]
    try:
        result = subprocess.run(ldconfig_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, text=True)
        return library in result.stdout
    except subprocess.CalledProcessError:
        return False

def check_libs(libraries):
    ld_library_path = os.environ.get('LD_LIBRARY_PATH', '')
    for library in libraries:
        have_lib_result = have_lib(library, ld_library_path)
        if have_lib_result:
            logging.info(f"* {library} is installed!")
        else:
            if config.PACKAGE_MANAGER_COMMAND:
                message = f"Your {config.OS_NAME} install is missing the library: {library}. To continue, the script will attempt to install the library by using {config.PACKAGE_MANAGER_COMMAND}. Proceed?"
                if logos_continue_question(message, config.EXTRA_INFO):
                    install_packages(config.PACKAGES)
            else:
                logos_error(f"The script could not determine your {config.OS_NAME} install's package manager or it is unsupported. Your computer is missing the library: {library}. Please install the package associated with {library} for {config.OS_NAME}.\n{config.EXTRA_INFO}")

def checkDependencies():
    logging.info("Checking system's for dependencies:")
    cmds = ["wget", "grep"]
    check_commands(cmds)

def checkDependenciesLogos10():
    logging.info("All dependencies found. Continuing…")

def checkDependenciesLogos9():
    logging.info("Checking dependencies for Logos 9.")
    cmds = ["xwd", "cabextract"]
    check_commands(cmds);
    logging.info("All dependencies found. Continuing…")

def createWineBinaryList():
    WineBinPathList = [
        "/usr/local/bin",
        os.path.expanduser("~") + "/bin",
        os.path.expanduser("~") + "/PlayOnLinux/wine/linux-amd64/*/bin",
        os.path.expanduser("~") + "/.steam/steam/steamapps/common/Proton*/files/bin",
        config.CUSTOMBINPATH,
    ]

    # Temporarily modify PATH for additional WINE64 binaries.
    for p in WineBinPathList:
        if p is None:
            continue
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
            logging.info(f"Removing binary: {binary} because {output2}")
    
    return binaries

def file_exists(file_path):
    if file_path is not None:
        expanded_path = os.path.expanduser(file_path)
        return os.path.isfile(expanded_path)
    else:
        return False

def getLogosReleases(q=None, app=None):
    url = f"https://clientservices.logos.com/update/v1/feed/logos{config.TARGETVERSION}/stable.xml"

    try:
        # Fetch XML content using urllib.
        with urllib.request.urlopen(url, timeout=30) as f:
            response = f.read().decode('utf-8')
    except urllib.error.URLError as e:
        logging.critical(f"Error fetching or parsing XML: {e}")
        if q is not None and app is not None:
            q.put(None)
            app.root.event_generate("<<ReleaseCheckProgress>>")
        return None

    # Parse XML
    root = ET.fromstring(response)

    # Define namespaces
    namespaces = {
        'ns0': 'http://www.w3.org/2005/Atom',
        'ns1': 'http://services.logos.com/update/v1/'
    }

    # Extract versions
    releases = []
    # Obtain all listed releases.
    for entry in root.findall('.//ns1:version', namespaces):
        release = entry.text
        releases.append(release)
        #if len(releases) == 5:
        #    break

    if q is not None and app is not None:
        q.put(releases)
        app.root.event_generate("<<ReleaseCheckProgress>>")

    return releases

def getWineBinOptions(binaries):
    WINEBIN_OPTIONS = []
    
    # Add AppImage to list
    if config.TARGETVERSION != "9":
        if config.DIALOG in ["whiptail", "dialog", "curses"]:
            WINEBIN_OPTIONS.append(["AppImage", f'{config.APPDIR_BINDIR}/{config.WINE64_APPIMAGE_FULL_FILENAME}', f"AppImage of Wine64 {config.WINE64_APPIMAGE_FULL_VERSION}"])
        elif config.DIALOG == "zenity":
            WINEBIN_OPTIONS.append(["FALSE", "AppImage", f"AppImage of Wine64 {config.WINE64_APPIMAGE_FULL_VERSION}", os.path.join(config.APPDIR_BINDIR, config.WINE64_APPIMAGE_FULL_FILENAME)])
        elif config.DIALOG == "kdialog":
            no_diag_msg("kdialog not implemented.")
        elif config.DIALOG == 'tk':
            WINEBIN_OPTIONS.append(f"{config.APPDIR_BINDIR}/{config.WINE64_APPIMAGE_FULL_FILENAME}")
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
        if config.DIALOG in ["whiptail", "dialog", "curses"]:
            WINEBIN_OPTIONS.append([WINEBIN_CODE, WINEBIN_PATH, WINEBIN_DESCRIPTION])
        elif config.DIALOG == "zenity":
            WINEBIN_OPTIONS.append([WINEBIN_CODE, WINEBIN_DESCRIPTION, WINEBIN_PATH])
        elif config.DIALOG == "kdialog":
            no_diag_msg("kdialog not implemented.")
        elif config.DIALOG == 'tk':
            WINEBIN_OPTIONS.append(WINEBIN_PATH)
        else:
            no_diag_msg("No dialog tool found.")

    return sorted(WINEBIN_OPTIONS)

def get_user_downloads_dir():
    home = Path.home()
    xdg_config = Path(os.getenv('XDG_CONFIG_HOME', home / '.config'))
    user_dirs_file = xdg_config / 'user-dirs.dirs'
    downloads_path = str(home / 'Downloads')
    if user_dirs_file.is_file():
        with user_dirs_file.open() as f:
            for line in f.readlines():
                if 'DOWNLOAD' in line:
                    downloads_path = line.rstrip().split('=')[1].replace('$HOME', str(home)).strip('"')
                    break
    return downloads_path

def get_system_winetricks():
    try:
        p = subprocess.run(['winetricks', '--version'], capture_output=True, text=True)
        version = int(p.stdout.rstrip()[:8])
        path = shutil.which('winetricks')
        return (path, version)
    except FileNotFoundError:
        return None

def wget(uri, target, q=None, app=None, evt=None):
    cmd = ['wget', '-q', '--show-progress', '--progress=dot', '-c', uri, '-O', target]
    with subprocess.Popen(cmd, stderr=subprocess.PIPE, encoding='UTF8') as proc:
        while True:
            line = proc.stderr.readline()
            if not line:
                break
            m = re.search(r'[0-9]+%', line)
            if m is not None:
                p = m[0].rstrip('%')
                if None not in [q, app, evt]:
                    q.put(p)
                    app.root.event_generate(evt)

def same_size(url, file_path, q=None, app=None, evt=None):
    url_size = UrlProps(url).size
    file_size = FileProps(file_path).size
    res = url_size == file_size
    if None in [q, app, evt]:
        return res
    q.put((evt, res))
    app.root.event_generate(evt)
