import logging
import distro
import os
import shlex
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import config
import msg
import network


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
        if distro.id() == "debian":
            binutils = "binutils binutils-common binutils-x86-64-linux-gnu libbinutils libctf-nobfd0 libctf0 libgprofng0"
        else:
            binutils = "binutils"
        if distro.id() == "ubuntu" and distro.version() < "24.04":
            fuse = "fuse"
        else:
            fuse = "fuse3"
        config.PACKAGES = f"{binutils} cabextract {fuse} wget winbind"
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
