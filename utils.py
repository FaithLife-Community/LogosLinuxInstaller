import atexit
import distro
import glob
import inspect
import json
import logging
import os
import psutil
import re
import shutil
import shlex
import signal
import stat
import subprocess
import sys
import threading
import time
import tkinter as tk
import zipfile
from packaging import version
from pathlib import Path
from typing import List, Union

import config
import msg
import network
import wine
import tui_dialog


def get_calling_function_name():
    if 'inspect' in sys.modules:
        stack = inspect.stack()
        caller_frame = stack[1]
        caller_name = caller_frame.function
        return caller_name
    else:
        return "Inspect Not Enabled"


def append_unique(list, item):
    if item not in list:
        list.append(item)
    else:
        msg.logos_warn(f"{item} already in {list}.")


# Set "global" variables.
def set_default_config():
    get_os()
    get_superuser_command()
    get_package_manager()
    if config.CONFIG_FILE is None:
        config.CONFIG_FILE = config.DEFAULT_CONFIG_PATH
    config.PRESENT_WORKING_DIRECTORY = os.getcwd()
    config.MYDOWNLOADS = get_user_downloads_dir()
    os.makedirs(os.path.dirname(config.LOGOS_LOG), exist_ok=True)


def set_runtime_config():
    # Set runtime variables that are dependent on ones from config file.
    if config.INSTALLDIR and not config.WINEPREFIX:
        config.WINEPREFIX = f"{config.INSTALLDIR}/data/wine64_bottle"
    if config.WINE_EXE and not config.WINESERVER_EXE:
        bin_dir = Path(config.WINE_EXE).parent
        config.WINESERVER_EXE = str(bin_dir / 'wineserver')
    if config.FLPRODUCT and config.WINEPREFIX and not config.LOGOS_EXE:
        config.LOGOS_EXE = find_installed_product()


def write_config(config_file_path):
    logging.info(f"Writing config to {config_file_path}")
    os.makedirs(os.path.dirname(config_file_path), exist_ok=True)

    config_data = {key: config.__dict__.get(key) for key in config.core_config_keys}  # noqa: E501

    try:
        for key, value in config_data.items():
            if isinstance(value, Path):
                config_data[key] = str(value)
        with open(config_file_path, 'w') as config_file:
            json.dump(config_data, config_file, indent=4, sort_keys=True)
            config_file.write('\n')

    except IOError as e:
        msg.logos_error(f"Error writing to config file {config_file_path}: {e}")  # noqa: E501


def update_config_file(config_file_path, key, value):
    config_file_path = Path(config_file_path)
    with config_file_path.open(mode='r') as f:
        config_data = json.load(f)

    if config_data.get(key) != value:
        logging.info(f"Updating {str(config_file_path)} with: {key} = {value}")
        config_data[key] = value
        try:
            with config_file_path.open(mode='w') as f:
                json.dump(config_data, f, indent=4, sort_keys=True)
                f.write('\n')
        except IOError as e:
            msg.logos_error(f"Error writing to config file {config_file_path}: {e}")  # noqa: E501


def die_if_running():
    PIDF = '/tmp/LogosLinuxInstaller.pid'

    def remove_pid_file():
        if os.path.exists(PIDF):
            os.remove(PIDF)

    if os.path.isfile(PIDF):
        with open(PIDF, 'r') as f:
            pid = f.read().strip()
            message = f"The script is already running on PID {pid}. Should it be killed to allow this instance to run?"  # noqa: E501
            if config.DIALOG == "tk":
                # TODO: With the GUI this runs in a thread. It's not clear if
                # the messagebox will work correctly. It may need to be
                # triggered from here with an event and then opened from the
                # main thread.
                tk_root = tk.Tk()
                tk_root.withdraw()
                confirm = tk.messagebox.askquestion("Confirmation", message)
                tk_root.destroy()
            elif config.DIALOG == "curses":
                confirm = tui_dialog.confirm("Confirmation", message)
            else:
                confirm = msg.cli_question(message)

            if confirm:
                os.kill(int(pid), signal.SIGKILL)

    atexit.register(remove_pid_file)
    with open(PIDF, 'w') as f:
        f.write(str(os.getpid()))


def die_if_root():
    if os.getuid() == 0 and not config.LOGOS_FORCE_ROOT:
        msg.logos_error("Running Wine/winetricks as root is highly discouraged. Use -f|--force-root if you must run as root. See https://wiki.winehq.org/FAQ#Should_I_run_Wine_as_root.3F")  # noqa: E501


def die(message):
    logging.critical(message)
    sys.exit(1)


def run_command(command, retries=1, delay=0, stdin=None, shell=False):
    if retries < 1:
        retries = 1

    for attempt in range(retries):
        try:
            logging.debug(f"Attempting to execute {command}")
            result = subprocess.run(
                command,
                stdin=stdin,
                check=True,
                text=True,
                shell=shell,
                capture_output=True
            )
            return result
        except subprocess.CalledProcessError as e:
            logging.error(f"Error occurred while executing {command}: {e}")
            if "lock" in str(e):
                logging.debug(f"Database appears to be locked. Retrying in {delay} seconds…")
                time.sleep(delay)
            else:
                raise e
        except Exception as e:
            logging.error(f"An unexpected error occurred when running {command}: {e}")
            return None

    logging.error(f"Failed to execute after {retries} attempts: '{command}'")


def reboot():
    logging.info("Rebooting system.")
    command = f"{config.SUPERUSER_COMMAND} reboot now"
    subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True
    )
    sys.exit(0)


def restart_lli():
    logging.debug("Restarting Logos Linux Installer.")
    pidfile = Path('/tmp/LogosLinuxInstaller.pid')
    if pidfile.is_file():
        pidfile.unlink()
    os.execv(sys.executable, [sys.executable])
    sys.exit()


def set_verbose():
    config.LOG_LEVEL = logging.INFO
    config.WINEDEBUG = ''


def set_debug():
    config.LOG_LEVEL = logging.DEBUG
    config.WINEDEBUG = ""


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


def get_dialog():
    if not os.environ.get('DISPLAY'):
        msg.logos_error("The installer does not work unless you are running a display")  # noqa: E501

    DIALOG = os.getenv('DIALOG')
    config.GUI = False
    # Set config.DIALOG.
    if DIALOG is not None:
        DIALOG = DIALOG.lower()
        if DIALOG not in ['curses', 'tk']:
            msg.logos_error("Valid values for DIALOG are 'curses' or 'tk'.")
        config.DIALOG = DIALOG
    elif sys.__stdin__.isatty():
        config.DIALOG = 'curses'
    else:
        config.DIALOG = 'tk'
    # Set config.GUI.
    if config.DIALOG == 'tk':
        config.GUI = True


def get_os():
    # TODO: Remove if we can verify these are no longer needed commented code.

    # Try reading /etc/os-release
    # try:
    #    with open('/etc/os-release', 'r') as f:
    #        os_release_content = f.read()
    #    match = re.search(
    #        r'^ID=(\S+).*?VERSION_ID=(\S+)',
    #        os_release_content, re.MULTILINE
    #    )
    #    if match:
    #        config.OS_NAME = match.group(1)
    #        config.OS_RELEASE = match.group(2)
    #        return config.OS_NAME, config.OS_RELEASE
    # except FileNotFoundError:
    #    pass

    # Try using lsb_release command
    # try:
    #    config.OS_NAME = platform.linux_distribution()[0]
    #    config.OS_RELEASE = platform.linux_distribution()[1]
    #    return config.OS_NAME, config.OS_RELEASE
    # except AttributeError:
    #    pass

    # Try reading /etc/lsb-release
    # try:
    #    with open('/etc/lsb-release', 'r') as f:
    #        lsb_release_content = f.read()
    #    match = re.search(
    #        r'^DISTRIB_ID=(\S+).*?DISTRIB_RELEASE=(\S+)',
    #        lsb_release_content,
    #        re.MULTILINE
    #    )
    #    if match:
    #        config.OS_NAME = match.group(1)
    #        config.OS_RELEASE = match.group(2)
    #        return config.OS_NAME, config.OS_RELEASE
    # except FileNotFoundError:
    #    pass

    # Try reading /etc/debian_version
    # try:
    #    with open('/etc/debian_version', 'r') as f:
    #        config.OS_NAME = 'Debian'
    #        config.OS_RELEASE = f.read().strip()
    #        return config.OS_NAME, config.OS_RELEASE
    # except FileNotFoundError:
    #    pass

    # Add more conditions for other distributions as needed

    # Fallback to platform module
    config.OS_NAME = distro.id()  # FIXME: Not working. Returns "Linux".
    logging.info(f"OS name: {config.OS_NAME}")
    config.OS_RELEASE = distro.version()
    logging.info(f"OS release: {config.OS_RELEASE}")
    return config.OS_NAME, config.OS_RELEASE


def get_superuser_command():
    if config.DIALOG == 'tk':
        if shutil.which('pkexec'):
            config.SUPERUSER_COMMAND = "pkexec"
        else:
            msg.logos_error("No superuser command found. Please install pkexec.")  # noqa: E501
    else:
        if shutil.which('sudo'):
            config.SUPERUSER_COMMAND = "sudo"
        elif shutil.which('doas'):
            config.SUPERUSER_COMMAND = "doas"
        else:
            msg.logos_error("No superuser command found. Please install sudo or doas.")  # noqa: E501
    logging.debug(f"{config.SUPERUSER_COMMAND=}")


def get_package_manager():
    # Check for package manager and associated packages
    if shutil.which('apt') is not None:  # debian, ubuntu
        config.PACKAGE_MANAGER_COMMAND_INSTALL = "apt install -y"
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = "apt install --download-only -y"
        config.PACKAGE_MANAGER_COMMAND_REMOVE = "apt remove -y"
        config.PACKAGE_MANAGER_COMMAND_QUERY = "dpkg -l"
        config.QUERY_PREFIX = '.i  '
        if distro.id() == "ubuntu" and distro.version() < "24.04":
            fuse = "fuse"
        else:
            fuse = "fuse3"
        config.PACKAGES = f"binutils cabextract {fuse} wget winbind"
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = "appimagelauncher"
    elif shutil.which('dnf') is not None:  # rhel, fedora
        config.PACKAGE_MANAGER_COMMAND_INSTALL = "dnf install -y"
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = "dnf install --downloadonly -y"
        config.PACKAGE_MANAGER_COMMAND_REMOVE = "dnf remove -y"
        config.PACKAGE_MANAGER_COMMAND_QUERY = "dnf list installed"
        config.QUERY_PREFIX = ''
        config.PACKAGES = "patch fuse3 fuse3-libs mod_auth_ntlm_winbind samba-winbind samba-winbind-clients cabextract bc libxml2 curl"  # noqa: E501
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = "appiamgelauncher"
    elif shutil.which('pamac') is not None:  # manjaro
        config.PACKAGE_MANAGER_COMMAND_INSTALL = "pamac install --no-upgrade --no-confirm"  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = "pamac install --download-only --no-confirm"
        config.PACKAGE_MANAGER_COMMAND_REMOVE = "pamac remove --no-confirm"
        config.PACKAGE_MANAGER_COMMAND_QUERY = "pamac list -i"
        config.QUERY_PREFIX = ''
        config.PACKAGES = "patch wget sed grep gawk cabextract samba bc libxml2 curl"  # noqa: E501
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = "appimagelauncher"
    elif shutil.which('pacman') is not None:  # arch, steamOS
        config.PACKAGE_MANAGER_COMMAND_INSTALL = r"pacman -Syu --overwrite * --noconfirm --needed"  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = "pacman -Sw -y"
        config.PACKAGE_MANAGER_COMMAND_REMOVE = r"pacman -R --no-confirm"
        config.PACKAGE_MANAGER_COMMAND_QUERY = "pacman -Q"
        config.QUERY_PREFIX = ''
        if config.OS_NAME == "steamos":  # steamOS
            config.PACKAGES = "patch wget sed grep gawk cabextract samba bc libxml2 curl print-manager system-config-printer cups-filters nss-mdns foomatic-db-engine foomatic-db-ppds foomatic-db-nonfree-ppds ghostscript glibc samba extra-rel/apparmor core-rel/libcurl-gnutls winetricks appmenu-gtk-module lib32-libjpeg-turbo qt5-virtualkeyboard wine-staging giflib lib32-giflib libpng lib32-libpng libldap lib32-libldap gnutls lib32-gnutls mpg123 lib32-mpg123 openal lib32-openal v4l-utils lib32-v4l-utils libpulse lib32-libpulse libgpg-error lib32-libgpg-error alsa-plugins lib32-alsa-plugins alsa-lib lib32-alsa-lib libjpeg-turbo lib32-libjpeg-turbo sqlite lib32-sqlite libxcomposite lib32-libxcomposite libxinerama lib32-libgcrypt libgcrypt lib32-libxinerama ncurses lib32-ncurses ocl-icd lib32-ocl-icd libxslt lib32-libxslt libva lib32-libva gtk3 lib32-gtk3 gst-plugins-base-libs lib32-gst-plugins-base-libs vulkan-icd-loader lib32-vulkan-icd-loader" #noqa: #E501
        else:  # arch
            config.PACKAGES = "patch wget sed grep cabextract samba glibc samba apparmor libcurl-gnutls winetricks appmenu-gtk-module lib32-libjpeg-turbo wine giflib lib32-giflib libpng lib32-libpng libldap lib32-libldap gnutls lib32-gnutls mpg123 lib32-mpg123 openal lib32-openal v4l-utils lib32-v4l-utils libpulse lib32-libpulse libgpg-error lib32-libgpg-error alsa-plugins lib32-alsa-plugins alsa-lib lib32-alsa-lib libjpeg-turbo lib32-libjpeg-turbo sqlite lib32-sqlite libxcomposite lib32-libxcomposite libxinerama lib32-libgcrypt libgcrypt lib32-libxinerama ncurses lib32-ncurses ocl-icd lib32-ocl-icd libxslt lib32-libxslt libva lib32-libva gtk3 lib32-gtk3 gst-plugins-base-libs lib32-gst-plugins-base-libs vulkan-icd-loader lib32-vulkan-icd-loader" # noqa: E501
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = "appimagelauncher"
    # Add more conditions for other package managers as needed

    # Add logging output.
    logging.debug(f"{config.PACKAGE_MANAGER_COMMAND_INSTALL=}")
    logging.debug(f"{config.PACKAGE_MANAGER_COMMAND_QUERY=}")
    logging.debug(f"{config.PACKAGES=}")
    logging.debug(f"{config.L9PACKAGES=}")


def get_runmode():
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return 'binary'
    else:
        return 'script'


def query_packages(packages, elements=None, mode="install", app=None):
    result = ""
    if config.SKIP_DEPENDENCIES:
        return

    missing_packages = []
    conflicting_packages = []

    command = config.PACKAGE_MANAGER_COMMAND_QUERY

    try:
        result = run_command(command, shell=True)
    except Exception as e:
        logging.error(f"Error occurred while executing command: {e}")

    package_list = result.stdout

    logging.debug(f"Checking packages: {packages} in package list.")
    if app is not None:
        if elements is None:
            elements = {}  # Initialize elements if not provided
        elif isinstance(elements, list):
            elements = {element[0]: element[1] for element in elements}

        for p in packages:
            status = "Unchecked"
            for line in package_list.split('\n'):
                if line.strip().startswith(f"{config.QUERY_PREFIX}{p}") and mode == "install":
                    status = "Installed"
                    break
                elif line.strip().startswith(p) and mode == "remove":
                    conflicting_packages.append(p)
                    status = "Conflicting"
                    break

            if status == "Unchecked":
                if mode == "install":
                    missing_packages.append(p)
                    status = "Missing"
                elif mode == "remove":
                    status = "Not Installed"

            logging.debug(f"Setting {p}: {status}")
            elements[p] = status

            if app is not None and config.DIALOG == "curses":
                app.report_dependencies(
                    f"Checking Packages {(packages.index(p) + 1)}/{len(packages)}",
                    100 * (packages.index(p) + 1) // len(packages),
                    elements,
                    dialog=config.use_python_dialog)

    txt = 'None'
    if mode == "install":
        if missing_packages:
            txt = f"Missing packages: {' '.join(missing_packages)}"
        logging.info(f"Missing packages: {txt}")
        return missing_packages, elements
    elif mode == "remove":
        if conflicting_packages:
            txt = f"Conflicting packages: {' '.join(conflicting_packages)}"
        logging.info(f"Conflicting packages: {txt}")
        return conflicting_packages, elements


def download_packages(packages, elements, app=None):
    if config.SKIP_DEPENDENCIES:
        return

    if packages:
        total_packages = len(packages)
        command = f"{config.SUPERUSER_COMMAND} {config.PACKAGE_MANAGER_COMMAND_DOWNLOAD} {' '.join(packages)}"
        logging.debug(f"download_packages cmd: {command}")
        command_args = shlex.split(command)
        result = run_command(command_args, retries=5, delay=15)

        for index, package in enumerate(packages):
            status = "Downloaded" if result.returncode == 0 else "Failed"
            if elements is not None:
                elements[index] = (package, status)

            if app is not None and config.DIALOG == "curses" and elements is not None:
                app.report_dependencies(f"Downloading Packages ({index + 1}/{total_packages})",
                                        100 * (index + 1) // total_packages, elements, dialog=config.use_python_dialog)


def install_packages(packages, elements, app=None):
    if config.SKIP_DEPENDENCIES:
        return

    if packages:
        total_packages = len(packages)
        for index, package in enumerate(packages):
            command = f"{config.SUPERUSER_COMMAND} {config.PACKAGE_MANAGER_COMMAND_INSTALL} {package}"
            logging.debug(f"install_packages cmd: {command}")
            result = run_command(command, retries=5, delay=15)

            if elements is not None:
                elements[index] = (
                    package,
                    "Installed" if result.returncode == 0 else "Failed")

            if app is not None and config.DIALOG == "curses" and elements is not None:
                app.report_dependencies(
                    f"Installing Packages ({index + 1}/{total_packages})",
                    100 * (index + 1) // total_packages,
                    elements,
                    dialog=config.use_python_dialog)


def remove_packages(packages, elements, app=None):
    if config.SKIP_DEPENDENCIES:
        return

    if packages:
        total_packages = len(packages)
        for index, package in enumerate(packages):
            command = f"{config.SUPERUSER_COMMAND} {config.PACKAGE_MANAGER_COMMAND_REMOVE} {package}"
            logging.debug(f"remove_packages cmd: {command}")
            result = run_command(command, retries=5, delay=15)

            if elements is not None:
                elements[index] = (
                    package,
                    "Removed" if result.returncode == 0 else "Failed")

            if app is not None and config.DIALOG == "curses" and elements is not None:
                app.report_dependencies(
                    f"Removing Packages ({index + 1}/{total_packages})",
                    100 * (index + 1) // total_packages,
                    elements,
                    dialog=config.use_python_dialog)


def have_dep(cmd):
    if shutil.which(cmd) is not None:
        return True
    else:
        return False


def check_dialog_version():
    if have_dep("dialog"):
        try:
            result = run_command(["dialog", "--version"])
            version_info = result.stdout.strip()
            if version_info.startswith("Version: "):
                version_info = version_info[len("Version: "):]
            return version_info
        except subprocess.CalledProcessError as e:
            print(f"Error running command: {e.stderr}")
        except FileNotFoundError:
            print("The 'dialog' command is not found. Please ensure it is installed and in your PATH.")
        return None


def test_dialog_version():
    version = check_dialog_version()

    def parse_date(version):
        try:
            return version.split('-')[1]
        except IndexError:
            return ''

    minimum_version = "1.3-20201126-1"

    logging.debug(f"Current dialog version: {version}")
    if version is not None:
        minimum_version = parse_date(minimum_version)
        current_version = parse_date(version)
        logging.debug(f"Minimum dialog version: {minimum_version}. Installed version: {current_version}.")
        return current_version > minimum_version
    else:
        return None


def clean_all():
    logging.info("Cleaning all temp files…")
    os.system("rm -fr /tmp/LBS.*")
    os.system(f"rm -fr {config.WORKDIR}")
    os.system(f"rm -f {config.PRESENT_WORKING_DIRECTORY}/wget-log*")
    logging.info("done")


def mkdir_critical(directory):
    try:
        os.mkdir(directory)
    except OSError:
        msg.logos_error(f"Can't create the {directory} directory")


def get_user_downloads_dir():
    home = Path.home()
    xdg_config = Path(os.getenv('XDG_CONFIG_HOME', home / '.config'))
    user_dirs_file = xdg_config / 'user-dirs.dirs'
    downloads_path = str(home / 'Downloads')
    if user_dirs_file.is_file():
        with user_dirs_file.open() as f:
            for line in f.readlines():
                if 'DOWNLOAD' in line:
                    downloads_path = line.rstrip().split('=')[1].replace(
                        '$HOME',
                        str(home)
                    ).strip('"')
                    break
    return downloads_path


def delete_symlink(symlink_path):
    symlink_path = Path(symlink_path)
    if symlink_path.is_symlink():
        try:
            symlink_path.unlink()
            logging.info(f"Symlink at {symlink_path} removed successfully.")
        except Exception as e:
            logging.error(f"Error removing symlink: {e}")


def preinstall_dependencies_ubuntu():
    try:
        dpkg_output = run_command([config.SUPERUSER_COMMAND, "dpkg", "--add-architecture", "i386"])
        mkdir_output = run_command([config.SUPERUSER_COMMAND, "mkdir", "-pm755", "/etc/apt/keyrings"])
        wget_key_output = run_command(
            [config.SUPERUSER_COMMAND, "wget", "-O", "/etc/apt/keyrings/winehq-archive.key", "https://dl.winehq.org/wine-builds/winehq.key"])
        lsb_release_output = run_command(["lsb_release", "-a"])
        codename = [line for line in lsb_release_output.stdout.split('\n') if "Description" in line][0].split()[1].strip()
        wget_sources_output = run_command([config.SUPERUSER_COMMAND, "wget", "-NP", "/etc/apt/sources.list.d/",
                     f"https://dl.winehq.org/wine-builds/ubuntu/dists/{codename}/winehq-{codename}.sources"])
        apt_update_output = run_command([config.SUPERUSER_COMMAND, "apt", "update"])
        apt_install_output = run_command([config.SUPERUSER_COMMAND, "apt", "install", "--install-recommends", "winehq-staging"])
    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
        print(f"Command output: {e.output}")

def preinstall_dependencies_steamos():
    command = [config.SUPERUSER_COMMAND, "steamos-readonly", "disable"]
    steamsos_readonly_output = run_command(command)
    command = [config.SUPERUSER_COMMAND, "pacman-key", "--init"]
    pacman_key_init_output = run_command(command)
    command = [config.SUPERUSER_COMMAND, "pacman-key", "--populate", "archlinux"]
    pacman_key_populate_output = run_command(command)


def postinstall_dependencies_steamos():
    command =[
            config.SUPERUSER_COMMAND,
            "sed", '-i',
            's/mymachines resolve/mymachines mdns_minimal [NOTFOUND=return] resolve/',  # noqa: E501
            '/etc/nsswitch.conf'
        ]
    sed_output = run_command(command)
    command =[config.SUPERUSER_COMMAND, "locale-gen"]
    locale_gen_output = run_command(command)
    command =[
            config.SUPERUSER_COMMAND,
            "systemctl",
            "enable",
            "--now",
            "avahi-daemon"
        ]
    systemctl_avahi_daemon_output = run_command(command)
    command =[config.SUPERUSER_COMMAND, "systemctl", "enable", "--now", "cups"]
    systemctl_cups = run_command(command)
    command = [config.SUPERUSER_COMMAND, "steamos-readonly", "enable"]
    steamos_readonly_output = run_command(command)


def preinstall_dependencies():
    if config.OS_NAME == "Ubuntu" or config.OS_NAME == "Linux Mint":
        preinstall_dependencies_ubuntu()
    elif config.OS_NAME == "Steam":
        preinstall_dependencies_steamos()


def postinstall_dependencies():
    if config.OS_NAME == "Steam":
        postinstall_dependencies_steamos()


def install_dependencies(packages, badpackages, logos9_packages=None, app=None):
    missing_packages = {}
    conflicting_packages = {}
    package_list = []
    elements = {}
    bad_elements = {}

    if packages:
        package_list = packages.split()

    bad_package_list = []
    if badpackages:
        bad_package_list = badpackages.split()

    if logos9_packages:
        package_list.extend(logos9_packages.split())

    if config.DIALOG == "curses" and app is not None and elements is not None:
        for p in package_list:
            elements[p] = "Unchecked"
    if config.DIALOG == "curses" and app is not None and bad_elements is not None:
        for p in bad_package_list:
            bad_elements[p] = "Unchecked"

    if config.DIALOG == "curses" and app is not None:
        app.report_dependencies("Checking Packages", 0, elements, dialog=config.use_python_dialog)

    if config.PACKAGE_MANAGER_COMMAND_QUERY:
        missing_packages, elements = query_packages(package_list, elements, app=app)
        conflicting_packages, bad_elements = query_packages(bad_package_list, bad_elements, "remove", app=app)

    if config.PACKAGE_MANAGER_COMMAND_INSTALL:
        if missing_packages and conflicting_packages:
            message = f"Your {config.OS_NAME} computer requires installing and removing some software. To continue, the program will attempt to install the package(s): {missing_packages} by using ({config.PACKAGE_MANAGER_COMMAND_INSTALL}) and will remove the package(s): {conflicting_packages} by using ({config.PACKAGE_MANAGER_COMMAND_REMOVE}). Proceed?"  # noqa: E501
            logging.critical(message)
        elif missing_packages:
            message = f"Your {config.OS_NAME} computer requires installing some software. To continue, the program will attempt to install the package(s): {missing_packages} by using ({config.PACKAGE_MANAGER_COMMAND_INSTALL}). Proceed?"  # noqa: E501
            logging.critical(message)
        elif conflicting_packages:
            message = f"Your {config.OS_NAME} computer requires removing some software. To continue, the program will attempt to remove the package(s): {conflicting_packages} by using ({config.PACKAGE_MANAGER_COMMAND_REMOVE}). Proceed?"  # noqa: E501
            logging.critical(message)
        else:
            logging.debug("No missing or conflicting dependencies found.")

        # TODO: Need to send continue question to user based on DIALOG.
        # All we do above is create a message that we never send.
        # Do we need a TK continue question? I see we have a CLI and curses one
        # in msg.py

        preinstall_dependencies()

        # libfuse: for AppImage use. This is the only known needed library.
        check_libs(["libfuse"])

        if missing_packages:
            download_packages(missing_packages, elements, app)
            install_packages(missing_packages, elements, app)

        if conflicting_packages:
            # AppImage Launcher is the only known conflicting package.
            remove_packages(conflicting_packages, bad_elements, app)
            #config.REBOOT_REQUIRED = True
            #TODO: Verify with user before executing

        postinstall_dependencies()

        if config.REBOOT_REQUIRED:
            reboot()

    else:
        msg.logos_error(
            f"The script could not determine your {config.OS_NAME} install's package manager or it is unsupported. Your computer is missing the command(s) {missing_packages}. Please install your distro's package(s) associated with {missing_packages} for {config.OS_NAME}.")  # noqa: E501


def have_lib(library, ld_library_path):
    roots = ['/usr/lib', '/lib']
    if ld_library_path is not None:
        roots = [*ld_library_path.split(':'), *roots]
    for root in roots:
        libs = [lib for lib in Path(root).rglob(f"{library}*")]
        if len(libs) > 0:
            logging.debug(f"'{library}' found at '{libs[0]}'")
            return True
    return False


def check_libs(libraries):
    ld_library_path = os.environ.get('LD_LIBRARY_PATH', '')
    for library in libraries:
        have_lib_result = have_lib(library, ld_library_path)
        if have_lib_result:
            logging.info(f"* {library} is installed!")
        else:
            if config.PACKAGE_MANAGER_COMMAND_INSTALL:
                message = f"Your {config.OS_NAME} install is missing the library: {library}. To continue, the script will attempt to install the library by using {config.PACKAGE_MANAGER_COMMAND_INSTALL}. Proceed?"  # noqa: E501
                if msg.cli_continue_question(message, "", ""):
                    install_packages(config.PACKAGES)
            else:
                msg.logos_error(
                    f"The script could not determine your {config.OS_NAME} install's package manager or it is unsupported. Your computer is missing the library: {library}. Please install the package associated with {library} for {config.OS_NAME}.")  # noqa: E501


def check_dependencies(app=None):
    if config.TARGETVERSION:
        targetversion = int(config.TARGETVERSION)
    else:
        targetversion = 10
    logging.info(f"Checking Logos {str(targetversion)} dependencies…")
    if app:
        app.status_q.put(f"Checking Logos {str(targetversion)} dependencies…")
        if config.DIALOG == "tk":
            app.root.event_generate('<<UpdateStatus>>')

    if targetversion == 10:
        install_dependencies(config.PACKAGES, config.BADPACKAGES, app=app)
    elif targetversion == 9:
        install_dependencies(
            config.PACKAGES,
            config.BADPACKAGES,
            config.L9PACKAGES,
            app=app
        )
    else:
        logging.error(f"TARGETVERSION not found: {config.TARGETVERSION}.")

    if app:
        if config.DIALOG == "tk":
            app.root.event_generate('<<StopIndeterminateProgress>>')


def file_exists(file_path):
    if file_path is not None:
        expanded_path = os.path.expanduser(file_path)
        return os.path.isfile(expanded_path)
    else:
        return False


def get_current_logos_version():
    path_regex = f"{config.INSTALLDIR}/data/wine64_bottle/drive_c/users/*/AppData/Local/Logos/System/Logos.deps.json"
    file_paths = glob.glob(path_regex)
    if file_paths:
        logos_version_file = file_paths[0]
        with open(logos_version_file, 'r') as json_file:
            json_data = json.load(json_file)

        dependencies = json_data["targets"]['.NETCoreApp,Version=v6.0/win10-x64']['Logos/1.0.0']['dependencies']
        logos_version_number = dependencies.get("LogosUpdater.Reference")

        if logos_version_number is not None:
            return logos_version_number
        else:
            logging.debug("Couldn't determine installed Logos version.")
            return None
    else:
        logging.debug(f"Logos.deps.json not found.")


def convert_logos_release(logos_release):
    if logos_release is not None:
        ver_major = logos_release.split('.')[0]
        ver_minor = logos_release.split('.')[1]
        release = logos_release.split('.')[2]
        point = logos_release.split('.')[3]
    else:
        ver_major = 0
        ver_minor = 0
        release = 0
        point = 0

    logos_release_arr = [int(ver_major), int(ver_minor), int(release), int(point)]
    return logos_release_arr


def which_release():
    if config.current_logos_release:
        return config.current_logos_release
    else:
        return config.TARGET_RELEASE_VERSION


def check_logos_release_version(version, threshold, check_version_part):
    if version is not None:
        version_parts = list(map(int, version.split('.')))
        return version_parts[check_version_part - 1] < threshold
    else:
        return False


def filter_versions(versions, threshold, check_version_part):
    return [version for version in versions if check_logos_release_version(version, threshold, check_version_part)]  # noqa: E501


def get_winebin_code_and_desc(binary):
    # Set binary code, description, and path based on path
    codes = {
        "Recommended": "Use the recommended AppImage",
        "AppImage": "AppImage of Wine64",
        "System": "Use the system binary (i.e., /usr/bin/wine64). WINE must be 7.18-staging or later, or 8.16-devel or later, and cannot be version 8.0.",  # noqa: E501
        "Proton": "Install using the Steam Proton fork of WINE.",
        "PlayOnLinux": "Install using a PlayOnLinux WINE64 binary.",
        "Custom": "Use a WINE64 binary from another directory.",
    }
    # TODO: The GUI currently cannot distinguish between the recommended
    # AppImage and another on the system. We need to add some manner of making
    # this distinction in the GUI, which is why the wine binary codes exist.
    # Currently the GUI only accept an array with a single element, the binary
    # itself; this will need to be modified to a two variable array, at the
    # least, even if we hide the wine binary code, but it might be useful to
    # tell the GUI user that a particular AppImage/binary is recommended.
    # Below is my best guess for how to do this with the single element array…
    # Does it work?
    if binary == f"{config.APPDIR_BINDIR}/{config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME}":  # noqa: E501
        code = "Recommended"
    elif binary.lower().endswith('.appimage'):
        code = "AppImage"
    elif "/usr/bin/" in binary:
        code = "System"
    elif "Proton" in binary:
        code = "Proton"
    elif "PlayOnLinux" in binary:
        code = "PlayOnLinux"
    else:
        code = "Custom"
    desc = codes.get(code)
    logging.debug(f"{binary} code & desc: {code}; {desc}")
    return code, desc


def get_wine_options(appimages, binaries, app=None) -> Union[List[List[str]], List[str]]:  # noqa: E501
    logging.debug(f"{appimages=}")
    logging.debug(f"{binaries=}")
    wine_binary_options = []

    # Add AppImages to list
    # if config.DIALOG == 'tk':
    wine_binary_options.append(f"{config.APPDIR_BINDIR}/{config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME}")  # noqa: E501
    wine_binary_options.extend(appimages)
    # else:
    #     appimage_entries = [["AppImage", filename, "AppImage of Wine64"] for filename in appimages]  # noqa: E501
    #     wine_binary_options.append([
    #         "Recommended",  # Code
    #         f'{config.APPDIR_BINDIR}/{config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME}',  # noqa: E501
    #         f"AppImage of Wine64 {config.RECOMMENDED_WINE64_APPIMAGE_FULL_VERSION}"  # noqa: E501
    #         ])
    #     wine_binary_options.extend(appimage_entries)

    sorted_binaries = sorted(list(set(binaries)))
    logging.debug(f"{sorted_binaries=}")

    for WINEBIN_PATH in sorted_binaries:
        WINEBIN_CODE, WINEBIN_DESCRIPTION = get_winebin_code_and_desc(WINEBIN_PATH)  # noqa: E501

        # Create wine binary option array
        # if config.DIALOG == 'tk':
        wine_binary_options.append(WINEBIN_PATH)
        # else:
        #     wine_binary_options.append(
        #         [WINEBIN_CODE, WINEBIN_PATH, WINEBIN_DESCRIPTION]
        #     )
        #
    # if config.DIALOG != 'tk':
    #     wine_binary_options.append(["Exit", "Exit", "Cancel installation."])

    logging.debug(f"{wine_binary_options=}")
    if app:
        app.wines_q.put(wine_binary_options)
        app.root.event_generate(app.wine_evt)
    return wine_binary_options


def get_winetricks_options():
    local_winetricks_path = shutil.which('winetricks')
    winetricks_options = ['Download', 'Return to Main Menu']
    if local_winetricks_path is not None:
        # Check if local winetricks version is up-to-date.
        cmd = ["winetricks", "--version"]
        local_winetricks_version = subprocess.check_output(cmd).split()[0]
        if str(local_winetricks_version) >= "20220411":
            winetricks_options.insert(0, local_winetricks_path)
        else:
            logging.info("Local winetricks is too old.")
    else:
        logging.info("Local winetricks not found.")
    return winetricks_options


def install_winetricks(
    installdir,
    app=None,
    version=config.WINETRICKS_VERSION,
):
    msg.logos_msg(f"Installing winetricks v{version}…")
    base_url = "https://codeload.github.com/Winetricks/winetricks/zip/refs/tags"  # noqa: E501
    zip_name = f"{version}.zip"
    network.logos_reuse_download(
        f"{base_url}/{version}",
        zip_name,
        config.MYDOWNLOADS,
        app=app,
    )
    wtzip = f"{config.MYDOWNLOADS}/{zip_name}"
    logging.debug(f"Extracting winetricks script into {installdir}…")
    with zipfile.ZipFile(wtzip) as z:
        for zi in z.infolist():
            if zi.is_dir():
                continue
            zi.filename = Path(zi.filename).name
            if zi.filename == 'winetricks':
                z.extract(zi, path=installdir)
                break
    os.chmod(f"{installdir}/winetricks", 0o755)
    logging.debug("Winetricks installed.")


def get_pids_using_file(file_path, mode=None):
    pids = set()
    for proc in psutil.process_iter(['pid', 'open_files']):
        try:
            if mode is not None:
                paths = [f.path for f in proc.open_files() if f.mode == mode]
            else:
                paths = [f.path for f in proc.open_files()]
            if len(paths) > 0 and file_path in paths:
                pids.add(proc.pid)
        except psutil.AccessDenied:
            pass
    return pids


def wait_process_using_dir(directory):
    logging.info(f"* Starting wait_process_using_dir for {directory}…")

    # Get pids and wait for them to finish.
    pids = get_pids_using_file(directory)
    for pid in pids:
        logging.info(f"wait_process_using_dir PID: {pid}")
        psutil.wait(pid)

    logging.info("* End of wait_process_using_dir.")


def write_progress_bar(percent, screen_width=80):
    y = '.'
    n = ' '
    l_f = int(screen_width * 0.75)  # progress bar length
    l_y = int(l_f * percent / 100)  # num. of chars. complete
    l_n = l_f - l_y  # num. of chars. incomplete
    if config.DIALOG == 'curses':
        msg.status(f" [{y * l_y}{n * l_n}] {percent:>3}%")
    else:
        print(f" [{y * l_y}{n * l_n}] {percent:>3}%", end='\r')


def app_is_installed():
    return config.LOGOS_EXE is not None and os.access(config.LOGOS_EXE, os.X_OK)  # noqa: E501


def find_installed_product():
    if config.FLPRODUCT and config.WINEPREFIX:
        drive_c = Path(f"{config.WINEPREFIX}/drive_c/")
        name = config.FLPRODUCT
        exe = None
        for root, _, files in drive_c.walk(follow_symlinks=False):
            if root.name == name and f"{name}.exe" in files:
                exe = str(root / f"{name}.exe")
                break
        return exe


def log_current_persistent_config():
    logging.debug("Current persistent config:")
    for k in config.core_config_keys:
        logging.debug(f"{k}: {config.__dict__.get(k)}")


def enough_disk_space(dest_dir, bytes_required):
    free_bytes = shutil.disk_usage(dest_dir).free
    logging.debug(f"{free_bytes=}; {bytes_required=}")
    return free_bytes > bytes_required


def get_path_size(file_path):
    file_path = Path(file_path)
    if not file_path.exists():
        path_size = None
    else:
        path_size = sum(f.stat().st_size for f in file_path.rglob('*')) + file_path.stat().st_size  # noqa: E501
    return path_size


def get_folder_group_size(src_dirs, q):
    src_size = 0
    for d in src_dirs:
        if not d.is_dir():
            continue
        src_size += get_path_size(d)
    q.put(src_size)


def get_copy_progress(dest_path, txfr_size, dest_size_init=0):
    dest_size_now = get_path_size(dest_path)
    if dest_size_now is None:
        dest_size_now = 0
    size_diff = dest_size_now - dest_size_init
    progress = round(size_diff / txfr_size * 100)
    return progress


def get_latest_folder(folder_path):
    folders = [f for f in Path(folder_path).glob('*')]
    if not folders:
        logging.warning(f"No folders found in {folder_path}")
        return None
    folders.sort()
    logging.info(f"Found {len(folders)} backup folders.")
    latest = folders[-1]
    logging.info(f"Latest folder: {latest}")
    return latest


def install_premade_wine_bottle(srcdir, appdir):
    msg.logos_msg(f"Extracting: '{config.LOGOS9_WINE64_BOTTLE_TARGZ_NAME}' into: {appdir}")  # noqa: E501
    shutil.unpack_archive(
        f"{srcdir}/{config.LOGOS9_WINE64_BOTTLE_TARGZ_NAME}",
        appdir
    )


def compare_logos_linux_installer_version():
    if (
        config.LLI_CURRENT_VERSION is not None
        and config.LLI_LATEST_VERSION is not None
    ):
        logging.debug(f"{config.LLI_CURRENT_VERSION=}; {config.LLI_LATEST_VERSION=}")  # noqa: E501
        if (
            version.parse(config.LLI_CURRENT_VERSION)
            < version.parse(config.LLI_LATEST_VERSION)
        ):
            # Current release is older than recommended.
            status = 0
            message = "yes"
        elif (
            version.parse(config.LLI_CURRENT_VERSION)
            == version.parse(config.LLI_LATEST_VERSION)
        ):
            # Current release is latest.
            status = 1
            message = "uptodate"
        elif (
            version.parse(config.LLI_CURRENT_VERSION)
            > version.parse(config.LLI_LATEST_VERSION)
        ):
            # Installed version is custom.
            status = 2
            message = "no"
    else:
        status = False
        message = "config.LLI_CURRENT_VERSION or config.LLI_LATEST_VERSION is not set."  # noqa: E501

    logging.debug(f"{status=}; {message=}")
    return status, message


def compare_recommended_appimage_version():
    wine_release = []
    if config.WINE_EXE is not None:
        wine_release, error_message = wine.get_wine_release(config.WINE_EXE)
        if wine_release is not None and wine_release is not False:
            current_version = '.'.join([str(n) for n in wine_release[:2]])
            logging.debug(f"Current wine release: {current_version}")

            if config.RECOMMENDED_WINE64_APPIMAGE_VERSION:
                logging.debug(f"Recommended wine release: {config.RECOMMENDED_WINE64_APPIMAGE_VERSION}")  # noqa: E501
                if current_version < config.RECOMMENDED_WINE64_APPIMAGE_VERSION:  # noqa: E501
                    # Current release is older than recommended.
                    status = 0
                    message = "yes"
                elif current_version == config.RECOMMENDED_WINE64_APPIMAGE_VERSION:  # noqa: E501
                    # Current release is latest.
                    status = 1
                    message = "uptodate"
                elif current_version > config.RECOMMENDED_WINE64_APPIMAGE_VERSION:  # noqa: E501
                    # Installed version is custom
                    status = 2
                    message = "no"
            else:
                status = False
                message = f"Error: {error_message}"
        else:
            status = False
            message = f"Error: {error_message}"
    else:
        status = False
        message = "config.WINE_EXE is not set."

    logging.debug(f"{status=}; {message=}")
    return status, message


def get_lli_release_version(lli_binary):
    lli_version = None
    # Ensure user-executable by adding 0o001.
    st = lli_binary.stat()
    os.chmod(lli_binary, mode=st.st_mode | stat.S_IXUSR)
    # Get version number.
    cmd = [lli_binary, '--version']
    vstr = subprocess.check_output(cmd, text=True)
    m = re.search(r'\d+\.\d+\.\d+(-[a-z]+\.\d+)?', vstr)
    if m:
        lli_version = m[0]
    return lli_version


def is_appimage(file_path):
    # Ref:
    # - https://cgit.freedesktop.org/xdg/shared-mime-info/commit/?id=c643cab25b8a4ea17e73eae5bc318c840f0e3d4b  # noqa: E501
    # - https://github.com/AppImage/AppImageSpec/blob/master/draft.md#image-format  # noqa: E501
    # Note:
    # result is a tuple: (is AppImage: True|False, AppImage type: 1|2|None)
    # result = (False, None)
    expanded_path = Path(file_path).expanduser().resolve()
    logging.debug(f"Converting path to expanded_path: {expanded_path}")
    if file_exists(expanded_path):
        logging.debug(f"{expanded_path} exists!")
        with file_path.open('rb') as f:
            f.seek(1)
            elf_sig = f.read(3)
            f.seek(8)
            ai_sig = f.read(2)
            f.seek(10)
            v_sig = f.read(1)

        appimage_check = elf_sig == b'ELF' and ai_sig == b'AI'
        appimage_type = int.from_bytes(v_sig)

        return (appimage_check, appimage_type)
    else:
        return (False, None)


def check_appimage(filestr):
    logging.debug(f"Checking if {filestr} is a usable AppImage.")
    if filestr is None:
        logging.error("check_appimage: received None for file.")
        return False

    file_path = Path(filestr)

    appimage, appimage_type = is_appimage(file_path)
    if appimage:
        logging.debug("It is an AppImage!")
        if appimage_type == 1:
            logging.error(f"{file_path}: Can't handle AppImage version {str(appimage_type)} yet.")  # noqa: E501
            return False
        else:
            logging.debug("It is a usable AppImage!")
            return True
    else:
        logging.debug("It is not an AppImage!")
        return False


def find_appimage_files(release_version, app=None):
    appimages = []
    directories = [
        os.path.expanduser("~") + "/bin",
        config.APPDIR_BINDIR,
        config.MYDOWNLOADS
    ]
    if config.CUSTOMBINPATH is not None:
        directories.append(config.CUSTOMBINPATH)

    if sys.version_info < (3, 12):
        raise RuntimeError("Python 3.12 or higher is required for .rglob() flag `case-sensitive` ")  # noqa: E501

    for d in directories:
        appimage_paths = Path(d).rglob('wine*.appimage', case_sensitive=False)
        for p in appimage_paths:
            if p is not None and check_appimage(p):
                output1, output2 = wine.check_wine_version_and_branch(release_version, p)
                if output1 is not None and output1:
                    appimages.append(str(p))
                else:
                    logging.info(f"AppImage file {p} not added: {output2}")

    if app:
        app.appimage_q.put(appimages)
        app.root.event_generate(app.appimage_evt)

    return appimages


def find_wine_binary_files(release_version):
    wine_binary_path_list = [
        "/usr/local/bin",
        os.path.expanduser("~") + "/bin",
        os.path.expanduser("~") + "/PlayOnLinux/wine/linux-amd64/*/bin",
        os.path.expanduser("~") + "/.steam/steam/steamapps/common/Proton*/files/bin",  # noqa: E501
    ]

    if config.CUSTOMBINPATH is not None:
        wine_binary_path_list.append(config.CUSTOMBINPATH)

    # Temporarily modify PATH for additional WINE64 binaries.
    for p in wine_binary_path_list:
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
        output1, output2 = wine.check_wine_version_and_branch(release_version, binary)
        if output1 is not None and output1:
            continue
        else:
            binaries.remove(binary)
            logging.info(f"Removing binary: {binary} because: {output2}")

    return binaries


def set_appimage_symlink(app=None):
    # This function assumes make_skel() has been run once.
    # if config.APPIMAGE_FILE_PATH is None:
    #     config.APPIMAGE_FILE_PATH = config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME  # noqa: E501

    # logging.debug(f"{config.APPIMAGE_FILE_PATH=}")
    # if config.APPIMAGE_FILE_PATH == config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME:  # noqa: E501
    #     get_recommended_appimage()
    #     selected_appimage_file_path = Path(config.APPDIR_BINDIR) / config.APPIMAGE_FILE_PATH  # noqa: E501
    # else:
    #     selected_appimage_file_path = Path(config.APPIMAGE_FILE_PATH)
    selected_appimage_file_path = Path(config.SELECTED_APPIMAGE_FILENAME)

    if not check_appimage(selected_appimage_file_path):
        logging.warning(f"Cannot use {selected_appimage_file_path}.")
        return

    copy_message = (
        f"Should the program copy {selected_appimage_file_path} to the"
        f" {config.APPDIR_BINDIR} directory?"
    )

    # Determine if user wants their AppImage in the Logos on Linux bin dir.
    if selected_appimage_file_path.exists():
        confirm = False
    else:
        if config.DIALOG == "tk":
            # TODO: With the GUI this runs in a thread. It's not clear if the
            # messagebox will work correctly. It may need to be triggered from
            # here with an event and then opened from the main thread.
            tk_root = tk.Tk()
            tk_root.withdraw()
            confirm = tk.messagebox.askquestion("Confirmation", copy_message)
            tk_root.destroy()
        else:
            confirm = tui_dialog.confirm("Confirmation", copy_message)
    # FIXME: What if user cancels the confirmation dialog?

    appimage_symlink_path = Path(f"{config.APPDIR_BINDIR}/{config.APPIMAGE_LINK_SELECTION_NAME}")  # noqa: E501
    delete_symlink(appimage_symlink_path)

    # FIXME: confirm is always False b/c appimage_filepath always exists b/c
    # it's copied in place via logos_reuse_download function above in
    # get_recommended_appimage.
    appimage_filename = selected_appimage_file_path.name
    if confirm is True or confirm == 'yes':
        logging.info(f"Copying {selected_appimage_file_path} to {config.APPDIR_BINDIR}.")  # noqa: E501
        shutil.copy(selected_appimage_file_path, f"{config.APPDIR_BINDIR}")
        os.symlink(selected_appimage_file_path, appimage_symlink_path)
        config.SELECTED_APPIMAGE_FILENAME = f"{appimage_filename}"
    # If not, use the selected AppImage's full path for link creation.
    elif confirm is False or confirm == 'no':
        logging.debug(f"{selected_appimage_file_path} already exists in {config.APPDIR_BINDIR}. No need to copy.")  # noqa: E501
        os.symlink(selected_appimage_file_path, appimage_symlink_path)
        logging.debug("AppImage symlink updated.")
        config.SELECTED_APPIMAGE_FILENAME = f"{selected_appimage_file_path}"
        logging.debug("Updated config with new AppImage path.")
    else:
        logging.error("Error getting user confirmation.")

    write_config(config.CONFIG_FILE)
    if app:
        app.root.event_generate("<<UpdateLatestAppImageButton>>")


def update_to_latest_lli_release(app=None):
    status, _ = compare_logos_linux_installer_version()

    if get_runmode() != 'binary':
        logging.error("Can't update LogosLinuxInstaller when run as a script.")
    elif status == 0:
        network.update_lli_binary(app=app)
    elif status == 1:
        logging.debug(f"{config.LLI_TITLE} is already at the latest version.")
    elif status == 2:
        logging.debug(f"{config.LLI_TITLE} is at a newer version than the latest.") # noqa: 501


def update_to_latest_recommended_appimage():
    config.APPIMAGE_FILE_PATH = config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME  # noqa: E501
    status, _ = compare_recommended_appimage_version()
    if status == 0:
        set_appimage_symlink()
    elif status == 1:
        logging.debug("The AppImage is already set to the latest recommended.")
    elif status == 2:
        logging.debug("The AppImage version is newer than the latest recommended.")  # noqa: E501


def get_downloaded_file_path(filename):
    dirs = [
        config.MYDOWNLOADS,
        Path.home(),
        Path.cwd(),
    ]
    for d in dirs:
        file_path = Path(d) / filename
        if file_path.is_file():
            logging.info(f"'{filename}' exists in {str(d)}.")
            return str(file_path)
    logging.debug(f"File not found: {filename}")


def send_task(app, task):
    logging.debug(f"{task=}")
    app.todo_q.put(task)
    if config.DIALOG == 'tk':
        app.root.event_generate('<<ToDo>>')
    elif config.DIALOG == 'curses':
        app.task_processor(app, task=task)


def grep(regexp, filepath):
    fp = Path(filepath)
    found = False
    ct = 0
    with fp.open() as f:
        for line in f:
            ct += 1
            text = line.rstrip()
            if re.search(regexp, text):
                logging.debug(f"{filepath}:{ct}:{text}")
                found = True
    return found


def start_thread(task, daemon_bool=True, *args):
    thread = threading.Thread(name=f"{task}", target=task, daemon=daemon_bool, args=args)
    thread.start()
    return thread


def str_array_to_string(text, delimeter="\n"):
    try:
        processed_text = delimeter.join(text)
        return processed_text
    except TypeError:
        return text
