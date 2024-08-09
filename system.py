import logging
import distro
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import config
import msg
import network


# TODO: Add a Popen variant to run_command to replace functions in control.py
# and wine.py
def run_command(command, retries=1, delay=0, verify=False, **kwargs):
    check = kwargs.get("check", True)
    text = kwargs.get("text", True)
    capture_output = kwargs.get("capture_output", True)
    shell = kwargs.get("shell", False)
    env = kwargs.get("env", None)
    cwd = kwargs.get("cwd", None)
    encoding = kwargs.get("encoding", None)
    input = kwargs.get("input", None)
    stdin = kwargs.get("stdin", None)
    stdout = kwargs.get("stdout", None)
    stderr = kwargs.get("stderr", None)

    if retries < 1:
        retries = 1

    if isinstance(command, str) and not shell:
        command = command.split()

    for attempt in range(retries):
        try:
            result = subprocess.run(
                command,
                check=check,
                text=text,
                shell=shell,
                capture_output=capture_output,
                input=input,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                encoding=encoding,
                cwd=cwd,
                env=env
            )
            return result
        except subprocess.CalledProcessError as e:
            logging.error(f"Error occurred while executing {command}: {e}")
            if "lock" in str(e):
                logging.debug(f"Database appears to be locked. Retrying in {delay} seconds…")  # noqa: E501
                time.sleep(delay)
            else:
                raise e
        except Exception as e:
            logging.error(f"An unexpected error occurred when running {command}: {e}")  # noqa: E501
            return None

    logging.error(f"Failed to execute after {retries} attempts: '{command}'")
    return None


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
        if shutil.which('pkexec'):
            config.SUPERUSER_COMMAND = "pkexec"
        elif shutil.which('sudo'):
            config.SUPERUSER_COMMAND = "sudo"
        elif shutil.which('doas'):
            config.SUPERUSER_COMMAND = "doas"
        else:
            msg.logos_error("No superuser command found. Please install sudo or doas.")  # noqa: E501
    logging.debug(f"{config.SUPERUSER_COMMAND=}")


def get_package_manager():
    # Check for package manager and associated packages
    if shutil.which('apt') is not None:  # debian, ubuntu
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["apt", "install", "-y"]
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["apt", "install", "--download-only", "-y"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["apt", "remove", "-y"]
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["dpkg", "-l"]
        config.QUERY_PREFIX = '.i  '
        config.PACKAGES = "binutils cabextract fuse3 wget winbind"
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = "appimagelauncher"
    elif shutil.which('dnf') is not None:  # rhel, fedora
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["dnf", "install", "-y"]
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["dnf", "install", "--downloadonly", "-y"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["dnf", "remove", "-y"]
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["dnf", "list", "installed"]
        config.QUERY_PREFIX = ''
        config.PACKAGES = "patch fuse3 fuse3-libs mod_auth_ntlm_winbind samba-winbind samba-winbind-clients cabextract bc libxml2 curl"  # noqa: E501
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = "appiamgelauncher"
    elif shutil.which('pamac') is not None:  # manjaro
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["pamac", "install", "--no-upgrade", "--no-confirm"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["pamac", "install", "--no-upgrade", "--download-only", "--no-confirm"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["pamac", "remove", "--no-confirm"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["pamac", "list", "-i"]
        config.QUERY_PREFIX = ''
        config.PACKAGES = "patch wget sed grep gawk cabextract samba bc libxml2 curl"  # noqa: E501
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = "appimagelauncher"
    elif shutil.which('pacman') is not None:  # arch, steamOS
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["pacman", "-Syu", "--overwrite", r"*", "--noconfirm", "--needed"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["pacman", "-Sw", "-y"]
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["pacman", "-R", "--no-confirm"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["pacman", "-Q"]
        config.QUERY_PREFIX = ''
        if config.OS_NAME == "steamos":  # steamOS
            config.PACKAGES = "patch wget sed grep gawk cabextract samba bc libxml2 curl print-manager system-config-printer cups-filters nss-mdns foomatic-db-engine foomatic-db-ppds foomatic-db-nonfree-ppds ghostscript glibc samba extra-rel/apparmor core-rel/libcurl-gnutls winetricks appmenu-gtk-module lib32-libjpeg-turbo qt5-virtualkeyboard wine-staging giflib lib32-giflib libpng lib32-libpng libldap lib32-libldap gnutls lib32-gnutls mpg123 lib32-mpg123 openal lib32-openal v4l-utils lib32-v4l-utils libpulse lib32-libpulse libgpg-error lib32-libgpg-error alsa-plugins lib32-alsa-plugins alsa-lib lib32-alsa-lib libjpeg-turbo lib32-libjpeg-turbo sqlite lib32-sqlite libxcomposite lib32-libxcomposite libxinerama lib32-libgcrypt libgcrypt lib32-libxinerama ncurses lib32-ncurses ocl-icd lib32-ocl-icd libxslt lib32-libxslt libva lib32-libva gtk3 lib32-gtk3 gst-plugins-base-libs lib32-gst-plugins-base-libs vulkan-icd-loader lib32-vulkan-icd-loader"  # noqa: #E501
        else:  # arch
            config.PACKAGES = "patch wget sed grep cabextract samba glibc samba apparmor libcurl-gnutls winetricks appmenu-gtk-module lib32-libjpeg-turbo wine giflib lib32-giflib libpng lib32-libpng libldap lib32-libldap gnutls lib32-gnutls mpg123 lib32-mpg123 openal lib32-openal v4l-utils lib32-v4l-utils libpulse lib32-libpulse libgpg-error lib32-libgpg-error alsa-plugins lib32-alsa-plugins alsa-lib lib32-alsa-lib libjpeg-turbo lib32-libjpeg-turbo sqlite lib32-sqlite libxcomposite lib32-libxcomposite libxinerama lib32-libgcrypt libgcrypt lib32-libxinerama ncurses lib32-ncurses ocl-icd lib32-ocl-icd libxslt lib32-libxslt libva lib32-libva gtk3 lib32-gtk3 gst-plugins-base-libs lib32-gst-plugins-base-libs vulkan-icd-loader lib32-vulkan-icd-loader"  # noqa: E501
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
        result = run_command(command)
    except Exception as e:
        logging.error(f"Error occurred while executing command: {e}")
        logging.error(result.stderr)

    package_list = result.stdout

    if app is not None:
        if elements is None:
            elements = {}  # Initialize elements if not provided
        elif isinstance(elements, list):
            elements = {element[0]: element[1] for element in elements}

        for p in packages:
            status = "Unchecked"
            l_num = 0
            for line in package_list.split('\n'):
                l_num += 1
                if config.PACKAGE_MANAGER_COMMAND_QUERY[0] == 'dpkg':
                    parts = line.strip().split()
                    if l_num < 6 or len(parts) < 2:  # skip header, etc.
                        continue
                    state = parts[0]
                    pkg = parts[1].split(':')[0]  # remove :arch if present
                    if pkg == p and state[1] == 'i':
                        if mode == 'install':
                            status = "Installed"
                        elif mode == 'remove':
                            status == 'Conflicting'
                        break
                else:
                    if line.strip().startswith(f"{config.QUERY_PREFIX}{p}") and mode == "install":  # noqa: E501
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

            elements[p] = status

            logging.debug(f"Setting Status of {p}: {status}")

    if mode == "install":
        if missing_packages:
            txt = f"Missing packages: {' '.join(missing_packages)}"
            logging.info(f"{txt}")
        return missing_packages, elements
    elif mode == "remove":
        if conflicting_packages:
            txt = f"Conflicting packages: {' '.join(conflicting_packages)}"
            logging.info(f"Conflicting packages: {txt}")
        return conflicting_packages, elements


def install_packages(packages, elements, app=None):
    if config.SKIP_DEPENDENCIES:
        return
    # if config.SUPERUSER_COMMAND == "sudo" or config.SUPERUSER_COMMAND == "pkexec":  # noqa: E501
    #     superuser_stdin = ["sudo", "-S"]
    # else:
    #     superuser_stdin = ["doas", "-n"]

    if packages:
        msg.status(f"Installing Missing Packages: {packages}", app)
        command = [config.SUPERUSER_COMMAND, *config.PACKAGE_MANAGER_COMMAND_INSTALL, *packages]  # noqa: E501
        # TODO: Handle non-zero exit status.
        result = run_command(command)


def remove_packages(packages, elements, app=None):
    if config.SKIP_DEPENDENCIES:
        return
    # password = get_password(app)
    # if config.SUPERUSER_COMMAND == "sudo" or config.SUPERUSER_COMMAND == "pkexec":  # noqa: E501
    #     superuser_stdin = ["sudo", "-S"]
    # else:
    #     superuser_stdin = ["doas", "-n"]

    if packages:
        msg.status(f"Removing Conflicting Packages: {packages}", app)
        command = [config.SUPERUSER_COMMAND, *config.PACKAGE_MANAGER_COMMAND_REMOVE, *packages]  # noqa: E501
        # TODO: Handle non-zero exit status.
        result = run_command(command)


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
            print("The 'dialog' command is not found. Please ensure it is installed and in your PATH.")  # noqa: E501
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
        logging.debug(f"Minimum dialog version: {minimum_version}. Installed version: {current_version}.")  # noqa: E501
        return current_version > minimum_version
    else:
        return None


def preinstall_dependencies_steamos(app=None):
    # password = get_password(app)
    # if config.SUPERUSER_COMMAND == "sudo" or config.SUPERUSER_COMMAND == "pkexec":  # noqa: E501
    #     superuser_stdin = ["sudo", "-S"]
    # else:
    #     superuser_stdin = ["doas", "-n"]
    try:
        logging.debug("Disabling read only, updating pacman keys…")
        command = [
            config.SUPERUSER_COMMAND, "steamos-readonly", "disable", "&&",
            config.SUPERUSER_COMMAND, "pacman-key", "--init", "&&",
            config.SUPERUSER_COMMAND, "pacman-key", "--populate", "archlinux"
        ]
        run_command(command, verify=True)
        # logging.debug("Updating pacman keys…")
        # command = superuser_stdin + ["pacman-key", "--init"]
        # run_command(command, input=password, verify=True)
        # command = superuser_stdin + ["pacman-key", "--populate", "archlinux"]  # noqa: E501
        # run_command(command, input=password, verify=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"An error occurred: {e}")
        logging.error(f"Command output: {e.output}")


def postinstall_dependencies_steamos(app=None):
    # if config.SUPERUSER_COMMAND == "sudo" or config.SUPERUSER_COMMAND == "pkexec":  # noqa: E501
    #     superuser_stdin = ["sudo", "-S"]
    # else:
    #     superuser_stdin = ["doas", "-n"]
    try:
        logging.debug("Updating DNS settings & locales, enabling services & read-only system…")  # noqa: E501
        command = [
            config.SUPERUSER_COMMAND, "sed", '-i',
            's/mymachines resolve/mymachines mdns_minimal [NOTFOUND=return] resolve/',  # noqa: E501
            '/etc/nsswitch.conf', '&&',
            config.SUPERUSER_COMMAND, "locale-gen", '&&',
            config.SUPERUSER_COMMAND, "systemctl", "enable", "--now", "avahi-daemon", "&&",  # noqa: E501
            config.SUPERUSER_COMMAND, "systemctl", "enable", "--now", "cups", "&&",  # noqa: E501
            config.SUPERUSER_COMMAND, "steamos-readonly", "enable",
        ]
        # command = superuser_stdin + [
        #     config.SUPERUSER_COMMAND,
        #     "sed", '-i',
        #     's/mymachines resolve/mymachines mdns_minimal [NOTFOUND=return] resolve/',  # noqa: E501
        #     '/etc/nsswitch.conf'
        # ]
        # run_command(command, input=password, verify=True)
        # logging.debug("Updating locales…")
        # command = [config.SUPERUSER_COMMAND, "locale-gen"]
        # run_command(command, input=password, verify=True)
        # logging.debug("Enabling avahi…")
        # command = superuser_stdin + [
        #     "systemctl",
        #     "enable",
        #     "--now",
        #     "avahi-daemon"
        # ]
        # run_command(command, input=password, verify=True)
        # logging.debug("Enabling cups…")
        # command = superuser_stdin + ["systemctl", "enable", "--now", "cups"]  # noqa: E501
        # run_command(command, input=password, verify=True)
        # logging.debug("Enabling read only…")
        # command = superuser_stdin + ["steamos-readonly", "enable"]
        run_command(command, verify=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"An error occurred: {e}")
        logging.error(f"Command output: {e.output}")


def preinstall_dependencies(app=None):
    logging.debug("Performing pre-install dependencies…")
    if config.OS_NAME == "Steam":
        preinstall_dependencies_steamos(app)
    else:
        logging.debug("No pre-install dependencies required.")


def postinstall_dependencies(app=None):
    logging.debug("Performing post-install dependencies…")
    if config.OS_NAME == "Steam":
        postinstall_dependencies_steamos(app)
    else:
        logging.debug("No post-install dependencies required.")


def install_dependencies(packages, badpackages, logos9_packages=None, app=None):  # noqa: E501
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
    if config.DIALOG == "curses" and app is not None and bad_elements is not None:  # noqa: E501
        for p in bad_package_list:
            bad_elements[p] = "Unchecked"

    if config.PACKAGE_MANAGER_COMMAND_QUERY:
        logging.debug("Querying packages…")
        missing_packages, elements = query_packages(
            package_list,
            elements,
            app=app
        )
        conflicting_packages, bad_elements = query_packages(
            bad_package_list,
            bad_elements,
            "remove",
            app=app
        )

    if config.PACKAGE_MANAGER_COMMAND_INSTALL:
        if missing_packages and conflicting_packages:
            message = f"Your {config.OS_NAME} computer requires installing and removing some software. To continue, the program will attempt to install the following package(s) by using '{config.PACKAGE_MANAGER_COMMAND_INSTALL}':\n{missing_packages}\nand will remove the following package(s) by using '{config.PACKAGE_MANAGER_COMMAND_REMOVE}':\n{conflicting_packages}\nProceed?"  # noqa: E501
            # logging.critical(message)
        elif missing_packages:
            message = f"Your {config.OS_NAME} computer requires installing some software. To continue, the program will attempt to install the following package(s) by using '{config.PACKAGE_MANAGER_COMMAND_INSTALL}':\n{missing_packages}\nProceed?"  # noqa: E501
            # logging.critical(message)
        elif conflicting_packages:
            message = f"Your {config.OS_NAME} computer requires removing some software. To continue, the program will attempt to remove the following package(s) by using '{config.PACKAGE_MANAGER_COMMAND_REMOVE}':\n{conflicting_packages}\nProceed?"  # noqa: E501
            # logging.critical(message)
        else:
            logging.debug("No missing or conflicting dependencies found.")

        # TODO: Need to send continue question to user based on DIALOG.
        # All we do above is create a message that we never send.
        # Do we need a TK continue question? I see we have a CLI and curses one
        # in msg.py

        if app and config.DIALOG == 'tk':
            app.root.event_generate('<<StartIndeterminateProgress>>')
            msg.status("Installing pre-install dependencies…", app)
        preinstall_dependencies(app)

        # libfuse: for AppImage use. This is the only known needed library.
        if config.OS_NAME == "fedora":
            fuse = "fuse"
        else:
            fuse = "libfuse"
        check_libs([f"{fuse}"], app=app)

        if missing_packages:
            if app and config.DIALOG == 'tk':
                app.root.event_generate('<<StartIndeterminateProgress>>')
            # msg.status("Downloading packages…", app)
            # download_packages(missing_packages, elements, app)
            if app and config.DIALOG == 'tk':
                app.root.event_generate('<<StartIndeterminateProgress>>')
            msg.status("Installing packages…", app)
            install_packages(missing_packages, elements, app)
        else:
            logging.debug("No missing packages detected.")

        if conflicting_packages:
            # AppImage Launcher is the only known conflicting package.
            remove_packages(conflicting_packages, bad_elements, app)
            # config.REBOOT_REQUIRED = True
            # TODO: Verify with user before executing
        else:
            logging.debug("No conflicting packages detected.")

        postinstall_dependencies(app)

        if config.REBOOT_REQUIRED:
            reboot()

    else:
        msg.logos_error(
            f"The script could not determine your {config.OS_NAME} install's package manager or it is unsupported. "  # noqa: E501
            f"Your computer is missing the command(s) {missing_packages}. "
            f"Please install your distro's package(s) associated with {missing_packages} for {config.OS_NAME}.")  # noqa: E501


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


def check_libs(libraries, app=None):
    ld_library_path = os.environ.get('LD_LIBRARY_PATH', '')
    for library in libraries:
        have_lib_result = have_lib(library, ld_library_path)
        if have_lib_result:
            logging.info(f"* {library} is installed!")
        else:
            if config.PACKAGE_MANAGER_COMMAND_INSTALL:
                # message = f"Your {config.OS_NAME} install is missing the library: {library}. To continue, the script will attempt to install the library by using {config.PACKAGE_MANAGER_COMMAND_INSTALL}. Proceed?"  # noqa: E501
                # if msg.cli_continue_question(message, "", ""):
                elements = {}

                if config.DIALOG == "curses" and app is not None and elements is not None:  # noqa: E501
                    for p in libraries:
                        elements[p] = "Unchecked"

                install_packages(config.PACKAGES, elements, app=app)
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
