from typing import Optional
import distro
import logging
import os
import psutil
import platform
import shutil
import struct
import subprocess
import sys
import time
import zipfile
from pathlib import Path


from . import config
from . import msg
from . import network
from . import utils


# TODO: Replace functions in control.py and wine.py with Popen command.
def run_command(command, retries=1, delay=0, **kwargs) -> Optional[subprocess.CompletedProcess[any]]:  # noqa: E501
    check = kwargs.get("check", True)
    text = kwargs.get("text", True)
    capture_output = kwargs.get("capture_output", True)
    shell = kwargs.get("shell", False)
    env = kwargs.get("env", None)
    cwd = kwargs.get("cwd", None)
    encoding = kwargs.get("encoding", None)
    cmdinput = kwargs.get("input", None)
    stdin = kwargs.get("stdin", None)
    stdout = kwargs.get("stdout", None)
    stderr = kwargs.get("stderr", None)
    timeout = kwargs.get("timeout", None)
    bufsize = kwargs.get("bufsize", -1)
    executable = kwargs.get("executable", None)
    pass_fds = kwargs.get("pass_fds", ())
    errors = kwargs.get("errors", None)
    preexec_fn = kwargs.get("preexec_fn", None)
    close_fds = kwargs.get("close_fds", True)
    universal_newlines = kwargs.get("universal_newlines", None)
    startupinfo = kwargs.get("startupinfo", None)
    creationflags = kwargs.get("creationflags", 0)
    restore_signals = kwargs.get("restore_signals", True)
    start_new_session = kwargs.get("start_new_session", False)
    user = kwargs.get("user", None)
    group = kwargs.get("group", None)
    extra_groups = kwargs.get("extra_groups", None)
    umask = kwargs.get("umask", -1)
    pipesize = kwargs.get("pipesize", -1)
    process_group = kwargs.get("process_group", None)

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
                input=cmdinput,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                encoding=encoding,
                cwd=cwd,
                env=env,
                timeout=timeout,
                bufsize=bufsize,
                executable=executable,
                errors=errors,
                pass_fds=pass_fds,
                preexec_fn=preexec_fn,
                close_fds=close_fds,
                universal_newlines=universal_newlines,
                startupinfo=startupinfo,
                creationflags=creationflags,
                restore_signals=restore_signals,
                start_new_session=start_new_session,
                user=user,
                group=group,
                extra_groups=extra_groups,
                umask=umask,
                pipesize=pipesize,
                process_group=process_group
            )
            return result
        except subprocess.CalledProcessError as e:
            logging.error(f"Error occurred in run_command() while executing \"{command}\": {e}")  # noqa: E501
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


def popen_command(command, retries=1, delay=0, **kwargs):
    shell = kwargs.get("shell", False)
    env = kwargs.get("env", None)
    cwd = kwargs.get("cwd", None)
    stdin = kwargs.get("stdin", None)
    stdout = kwargs.get("stdout", None)
    stderr = kwargs.get("stderr", None)
    bufsize = kwargs.get("bufsize", -1)
    executable = kwargs.get("executable", None)
    pass_fds = kwargs.get("pass_fds", ())
    preexec_fn = kwargs.get("preexec_fn", None)
    close_fds = kwargs.get("close_fds", True)
    universal_newlines = kwargs.get("universal_newlines", None)
    startupinfo = kwargs.get("startupinfo", None)
    creationflags = kwargs.get("creationflags", 0)
    restore_signals = kwargs.get("restore_signals", True)
    start_new_session = kwargs.get("start_new_session", False)
    user = kwargs.get("user", None)
    group = kwargs.get("group", None)
    extra_groups = kwargs.get("extra_groups", None)
    umask = kwargs.get("umask", -1)
    pipesize = kwargs.get("pipesize", -1)
    process_group = kwargs.get("process_group", None)
    encoding = kwargs.get("encoding", None)
    errors = kwargs.get("errors", None)
    text = kwargs.get("text", None)

    if retries < 1:
        retries = 1

    if isinstance(command, str) and not shell:
        command = command.split()

    for attempt in range(retries):
        try:
            process = subprocess.Popen(
                command,
                shell=shell,
                env=env,
                cwd=cwd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                bufsize=bufsize,
                executable=executable,
                pass_fds=pass_fds,
                preexec_fn=preexec_fn,
                close_fds=close_fds,
                universal_newlines=universal_newlines,
                startupinfo=startupinfo,
                creationflags=creationflags,
                restore_signals=restore_signals,
                start_new_session=start_new_session,
                user=user,
                group=group,
                extra_groups=extra_groups,
                umask=umask,
                pipesize=pipesize,
                process_group=process_group,
                encoding=encoding,
                errors=errors,
                text=text
            )
            return process

        except subprocess.CalledProcessError as e:
            logging.error(f"Error occurred in popen_command() while executing \"{command}\": {e}")  # noqa: E501
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


def get_pids(query):
    results = []
    for process in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if process.info['cmdline'] is not None and query in process.info['cmdline']:  # noqa: E501
                results.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):  # noqa: E501
            pass
    return results


def get_logos_pids():
    config.processes[config.LOGOS_EXE] = get_pids(config.LOGOS_EXE)
    config.processes[config.logos_login_cmd] = get_pids(config.logos_login_cmd)
    config.processes[config.logos_cef_cmd] = get_pids(config.logos_cef_cmd)
    config.processes[config.logos_indexer_exe] = get_pids(config.logos_indexer_exe)  # noqa: E501


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


def get_dialog():
    if not os.environ.get('DISPLAY'):
        msg.logos_error("The installer does not work unless you are running a display")  # noqa: E501

    dialog = os.getenv('DIALOG')
    # Set config.DIALOG.
    if dialog is not None:
        dialog = dialog.lower()
        if dialog not in ['cli', 'curses', 'tk']:
            msg.logos_error("Valid values for DIALOG are 'cli', 'curses' or 'tk'.")  # noqa: E501
        config.DIALOG = dialog
    elif sys.__stdin__.isatty():
        config.DIALOG = 'curses'
    else:
        config.DIALOG = 'tk'


def get_architecture():
    machine = platform.machine().lower()
    bits = struct.calcsize("P") * 8

    if "x86_64" in machine or "amd64" in machine:
        architecture = "x86_64"
    elif "i386" in machine or "i686" in machine:
        architecture = "x86_32"
    elif "arm" in machine or "aarch64" in machine:
        if bits == 64:
            architecture = "ARM64"
        else:
            architecture = "ARM32"
    elif "riscv" in machine or "riscv64" in machine:
        if bits == 64:
            architecture = "RISC-V 64"
        else:
            architecture = "RISC-V 32"
    else:
        architecture = "Unknown"

    return architecture, bits


def install_elf_interpreter():
    # TODO: This probably needs to be changed to another install step that requests the user to choose a specific
    # ELF interpreter between box64, FEX-EMU, and hangover. That or else we have to pursue a particular interpreter
    # for the install routine, depending on what's needed
    logging.critical("ELF interpretation is not yet coded in the installer.")
    # if "x86_64" not in config.architecture:
    #     if config.ELFPACKAGES is not None:
    #         utils.install_packages(config.ELFPACKAGES)
    #     else:
    #         logging.critical(f"ELFPACKAGES is not set.")
    #         sys.exit(1)
    # else:
    #     logging.critical(f"ELF interpreter is not needed.")


def check_architecture():
    if "x86_64" in config.architecture:
        pass
    elif "ARM64" in config.architecture:
        logging.critical("Unsupported architecture. Requires box64 or FEX-EMU or Wine Hangover to be integrated.")
        install_elf_interpreter()
    elif "RISC-V 64" in config.architecture:
        logging.critical("Unsupported architecture. Requires box64 or FEX-EMU or Wine Hangover to be integrated.")
        install_elf_interpreter()
    elif "x86_32" in config.architecture:
        logging.critical("Unsupported architecture. Requires box64 or FEX-EMU or Wine Hangover to be integrated.")
        install_elf_interpreter()
    elif "ARM32" in config.architecture:
        logging.critical("Unsupported architecture. Requires box64 or FEX-EMU or Wine Hangover to be integrated.")
        install_elf_interpreter()
    elif "RISC-V 32" in config.architecture:
        logging.critical("Unsupported architecture. Requires box64 or FEX-EMU or Wine Hangover to be integrated.")
        install_elf_interpreter()
    else:
        logging.critical("System archictecture unknown.")


def get_os():
    # FIXME: Not working? Returns "Linux" on some systems? On Ubuntu 24.04 it
    # correctly returns "ubuntu".
    config.OS_NAME = distro.id()
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
    major_ver = distro.major_version()
    logging.debug(f"{config.OS_NAME=}; {major_ver=}")
    # Check for package manager and associated packages.
    # NOTE: cabextract and sed are included in the appimage, so they are not
    # included as system dependencies.
    if shutil.which('apt') is not None:  # debian, ubuntu, & derivatives
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["apt", "install", "-y"]
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["apt", "install", "--download-only", "-y"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["apt", "remove", "-y"]
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["dpkg", "-l"]
        config.QUERY_PREFIX = '.i  '
        # Set default package list.
        config.PACKAGES = (
            "libfuse2 "  # appimages
            "binutils wget winbind "  # wine
            "p7zip-full "  # winetricks
        )
        # NOTE: Package names changed together for Ubuntu 24+, Debian 13+, and
        # derivatives. This does not include an exhaustive list of distros that
        # use 'apt', so others will have to be added as users report issues.
        # Ref:
        # - https://askubuntu.com/a/445496
        # - https://en.wikipedia.org/wiki/Linux_Mint
        # - https://en.wikipedia.org/wiki/Elementary_OS
        # - https://github.com/which-distro/os-release/tree/main
        if (
            (config.OS_NAME == 'debian' and major_ver >= '13')
            or (config.OS_NAME == 'ubuntu' and major_ver >= '24')
            or (config.OS_NAME == 'linuxmint' and major_ver >= '22')
            or (config.OS_NAME == 'elementary' and major_ver >= '8')
        ):
            config.PACKAGES = (
                "libfuse3-3 "  # appimages
                "binutils wget winbind "  # wine
                "7zip "  # winetricks
            )
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.ELFPACKAGES = ""
        config.BADPACKAGES = ""  # appimagelauncher handled separately
    elif shutil.which('dnf') is not None:  # rhel, fedora
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["dnf", "install", "-y"]
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["dnf", "install", "--downloadonly", "-y"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["dnf", "remove", "-y"]
        # Fedora < 41 uses dnf4, while Fedora  41 uses dnf5. The dnf list
        # command is sligtly different between the two.
        # https://discussion.fedoraproject.org/t/after-f41-upgrade-dnf-says-no-packages-are-installed/135391  # noqa: E501
        # Fedora < 41
        # config.PACKAGE_MANAGER_COMMAND_QUERY = ["dnf", "list", "installed"]
        # Fedora 41
        # config.PACKAGE_MANAGER_COMMAND_QUERY = ["dnf", "list", "--installed"]
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["rpm", "-qa"]  # workaround
        config.QUERY_PREFIX = ''
        # config.PACKAGES = "patch fuse3 fuse3-libs mod_auth_ntlm_winbind samba-winbind samba-winbind-clients cabextract bc libxml2 curl"  # noqa: E501
        config.PACKAGES = (
            "fuse fuse-libs "  # appimages
            "mod_auth_ntlm_winbind samba-winbind samba-winbind-clients "  # wine  # noqa: E501
            "p7zip-plugins "  # winetricks
        )
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.ELFPACKAGES = ""
        config.BADPACKAGES = ""  # appimagelauncher handled separately
    elif shutil.which('zypper') is not None:  # opensuse
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["zypper", "--non-interactive", "install"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["zypper", "download"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["zypper", "--non-interactive", "remove"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["zypper", "se", "-si"]
        config.QUERY_PREFIX = 'i  | '
        config.PACKAGES = (
            "fuse2 "  # appimages
            "samba wget "  # wine
            "7zip "  # winetricks
            "curl gawk grep "  # other
        )
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = ""  # appimagelauncher handled separately
    elif shutil.which('apk') is not None:  # alpine
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["apk", "--no-interactive", "add"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["apk", "--no-interactive", "fetch"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["apk", "--no-interactive", "del"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["apk", "list", "-i"]
        config.QUERY_PREFIX = ''
        config.PACKAGES = (
            "bash bash-completion"  # bash support
            "gcompat"  # musl to glibc
            "fuse-common fuse"  # appimages
            "wget curl"  # network
            "7zip"  # winetricks
            "samba sed grep gawk bash bash-completion"  # other
        )
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.BADPACKAGES = ""  # appimagelauncher handled separately
    elif shutil.which('pamac') is not None:  # manjaro
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["pamac", "install", "--no-upgrade", "--no-confirm"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["pamac", "install", "--no-upgrade", "--download-only", "--no-confirm"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["pamac", "remove", "--no-confirm"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["pamac", "list", "-i"]
        config.QUERY_PREFIX = ''
        config.PACKAGES = (
            "fuse2 "  # appimages
            "samba wget "  # wine
            "p7zip "  # winetricks
            "curl gawk grep "  # other
        )
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.ELFPACKAGES = ""
        config.BADPACKAGES = ""  # appimagelauncher handled separately
    elif shutil.which('pacman') is not None:  # arch, steamOS
        config.PACKAGE_MANAGER_COMMAND_INSTALL = ["pacman", "-Syu", "--overwrite", "\\*", "--noconfirm", "--needed"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_DOWNLOAD = ["pacman", "-Sw", "-y"]
        config.PACKAGE_MANAGER_COMMAND_REMOVE = ["pacman", "-R", "--no-confirm"]  # noqa: E501
        config.PACKAGE_MANAGER_COMMAND_QUERY = ["pacman", "-Q"]
        config.QUERY_PREFIX = ''
        if config.OS_NAME == "steamos":  # steamOS
            config.PACKAGES = "patch wget sed grep gawk cabextract samba bc libxml2 curl print-manager system-config-printer cups-filters nss-mdns foomatic-db-engine foomatic-db-ppds foomatic-db-nonfree-ppds ghostscript glibc samba extra-rel/apparmor core-rel/libcurl-gnutls winetricks appmenu-gtk-module lib32-libjpeg-turbo qt5-virtualkeyboard wine-staging giflib lib32-giflib libpng lib32-libpng libldap lib32-libldap gnutls lib32-gnutls mpg123 lib32-mpg123 openal lib32-openal v4l-utils lib32-v4l-utils libpulse lib32-libpulse libgpg-error lib32-libgpg-error alsa-plugins lib32-alsa-plugins alsa-lib lib32-alsa-lib libjpeg-turbo lib32-libjpeg-turbo sqlite lib32-sqlite libxcomposite lib32-libxcomposite libxinerama lib32-libgcrypt libgcrypt lib32-libxinerama ncurses lib32-ncurses ocl-icd lib32-ocl-icd libxslt lib32-libxslt libva lib32-libva gtk3 lib32-gtk3 gst-plugins-base-libs lib32-gst-plugins-base-libs vulkan-icd-loader lib32-vulkan-icd-loader"  # noqa: #E501
        else:  # arch
            # config.PACKAGES = "patch wget sed grep cabextract samba glibc samba apparmor libcurl-gnutls winetricks appmenu-gtk-module lib32-libjpeg-turbo wine giflib lib32-giflib libpng lib32-libpng libldap lib32-libldap gnutls lib32-gnutls mpg123 lib32-mpg123 openal lib32-openal v4l-utils lib32-v4l-utils libpulse lib32-libpulse libgpg-error lib32-libgpg-error alsa-plugins lib32-alsa-plugins alsa-lib lib32-alsa-lib libjpeg-turbo lib32-libjpeg-turbo sqlite lib32-sqlite libxcomposite lib32-libxcomposite libxinerama lib32-libgcrypt libgcrypt lib32-libxinerama ncurses lib32-ncurses ocl-icd lib32-ocl-icd libxslt lib32-libxslt libva lib32-libva gtk3 lib32-gtk3 gst-plugins-base-libs lib32-gst-plugins-base-libs vulkan-icd-loader lib32-vulkan-icd-loader"  # noqa: E501
            config.PACKAGES = (
                "fuse2 "  # appimages
                "binutils libwbclient samba wget "  # wine
                "p7zip "  # winetricks
                "openjpeg2 libxcomposite libxinerama "  # display
                "ocl-icd vulkan-icd-loader "  # hardware
                "alsa-plugins gst-plugins-base-libs libpulse openal "  # audio
                "libva mpg123 v4l-utils "  # video
                "libxslt sqlite "  # misc
            )
        config.L9PACKAGES = ""  # FIXME: Missing Logos 9 Packages
        config.ELFPACKAGES = ""
        config.BADPACKAGES = ""  # appimagelauncher handled separately
    else:
        # Add more conditions for other package managers as needed.
        msg.logos_error("Your package manager is not yet supported. Please contact the developers.")  # noqa: E501

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


def query_packages(packages, mode="install", app=None):
    result = ""
    missing_packages = []
    conflicting_packages = []
    command = config.PACKAGE_MANAGER_COMMAND_QUERY

    try:
        result = run_command(command)
    except Exception as e:
        logging.error(f"Error occurred while executing command: {e}")
        logging.error(e.output)
    package_list = result.stdout

    logging.debug(f"packages to check: {packages}")
    status = {package: "Unchecked" for package in packages}

    for p in packages:
        logging.debug(f"Checking for: {p}")
        l_num = 0
        for line in package_list.split('\n'):
            # logging.debug(f"{line=}")
            l_num += 1
            if config.PACKAGE_MANAGER_COMMAND_QUERY[0] == 'dpkg':
                parts = line.strip().split()
                if l_num < 6 or len(parts) < 2:  # skip header, etc.
                    continue
                state = parts[0]
                pkg = parts[1].split(':')[0]  # remove :arch if present
                if pkg == p and state[1] == 'i':
                    if mode == 'install':
                        status[p] = "Installed"
                    elif mode == 'remove':
                        conflicting_packages.append(p)
                        status[p] = 'Conflicting'
                    break
            else:
                if line.strip().startswith(f"{config.QUERY_PREFIX}{p}") and mode == "install":  # noqa: E501
                    logging.debug(f"'{p}' installed: {line}")
                    status[p] = "Installed"
                    break
                elif line.strip().startswith(p) and mode == "remove":
                    conflicting_packages.append(p)
                    status[p] = "Conflicting"
                    break

        if status[p] == "Unchecked":
            if mode == "install":
                missing_packages.append(p)
                status[p] = "Missing"
            elif mode == "remove":
                status[p] = "Not Installed"
        logging.debug(f"{p} status: {status.get(p)}")

    logging.debug(f"Packages status: {status}")

    if mode == "install":
        if missing_packages:
            txt = f"Missing packages: {' '.join(missing_packages)}"
            logging.info(f"{txt}")
        return missing_packages
    elif mode == "remove":
        if conflicting_packages:
            txt = f"Conflicting packages: {' '.join(conflicting_packages)}"
            logging.info(f"Conflicting packages: {txt}")
        return conflicting_packages


def have_dep(cmd):
    if shutil.which(cmd) is not None:
        return True
    else:
        return False


def check_dialog_version():
    if have_dep("dialog"):
        try:
            result = run_command(["dialog", "--version"])
            if result is None:
                print("Failed to run the 'dialog' command.")  # noqa: E501
                return None
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
    version: Optional[str] = check_dialog_version()

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


def remove_appimagelauncher(app=None):
    pkg = "appimagelauncher"
    cmd = [config.SUPERUSER_COMMAND, *config.PACKAGE_MANAGER_COMMAND_REMOVE, pkg]  # noqa: E501
    msg.status("Removing AppImageLauncher…", app)
    try:
        logging.debug(f"Running command: {cmd}")
        run_command(cmd)
    except subprocess.CalledProcessError as e:
        if e.returncode == 127:
            logging.error("User cancelled appimagelauncher removal.")
        else:
            logging.error(f"An error occurred: {e}")
            logging.error(f"Command output: {e.output}")
        msg.logos_error("Failed to uninstall AppImageLauncher.")
        sys.exit(1)
    logging.info("System reboot is required.")
    sys.exit()


def preinstall_dependencies_steamos():
    logging.debug("Disabling read only, updating pacman keys…")
    command = [
        config.SUPERUSER_COMMAND, "steamos-readonly", "disable", "&&",
        config.SUPERUSER_COMMAND, "pacman-key", "--init", "&&",
        config.SUPERUSER_COMMAND, "pacman-key", "--populate", "archlinux",
    ]
    return command


def postinstall_dependencies_steamos():
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
    return command


def postinstall_dependencies_alpine():
    user = os.getlogin()
    command = [
        config.SUPERUSER_COMMAND, "modprobe", "fuse", "&&",
        config.SUPERUSER_COMMAND, "rc-update", "add", "fuse", "boot", "&&",
        config.SUPERUSER_COMMAND, "sed", "-i", "'s/#user_allow_other/user_allow_other/g'", "/etc/fuse.conf", "&&",
        config.SUPERUSER_COMMAND, "addgroup", "fuse", "&&",
        config.SUPERUSER_COMMAND, "adduser", f"{user}", "fuse", "&&",
        config.SUPERUSER_COMMAND, "rc-service", "fuse", "restart",
    ]
    return command


def preinstall_dependencies(app=None):
    command = []
    logging.debug("Performing pre-install dependencies…")
    if config.OS_NAME == "Steam":
        command = preinstall_dependencies_steamos()
    else:
        logging.debug("No pre-install dependencies required.")
    return command


def postinstall_dependencies(app=None):
    command = []
    logging.debug("Performing post-install dependencies…")
    if config.OS_NAME == "Steam":
        command = postinstall_dependencies_steamos()
    if config.OS_NAME == "alpine":
        command = postinstall_dependencies_alpine()
    else:
        logging.debug("No post-install dependencies required.")
    return command


def install_dependencies(packages, bad_packages, logos9_packages=None, app=None):  # noqa: E501
    if config.SKIP_DEPENDENCIES:
        return

    install_deps_failed = False
    manual_install_required = False
    message = None
    no_message = None
    secondary = None
    command = []
    preinstall_command = []
    install_command = []
    remove_command = []
    postinstall_command = []
    missing_packages = {}
    conflicting_packages = {}
    package_list = []
    bad_package_list = []
    bad_os = ['fedora', 'arch', 'alpine']

    if packages:
        package_list = packages.split()

    if bad_packages:
        bad_package_list = bad_packages.split()

    if logos9_packages:
        package_list.extend(logos9_packages.split())

    if config.PACKAGE_MANAGER_COMMAND_QUERY:
        logging.debug("Querying packages…")
        missing_packages = query_packages(
            package_list,
            app=app
        )
        conflicting_packages = query_packages(
            bad_package_list,
            mode="remove",
            app=app
        )

    if config.PACKAGE_MANAGER_COMMAND_INSTALL:
        if config.OS_NAME in bad_os:
            message = False
            no_message = False
            secondary = False
        elif missing_packages and conflicting_packages:
            message = f"Your {config.OS_NAME} computer requires installing and removing some software.\nProceed?"  # noqa: E501
            no_message = "User refused to install and remove software via the application"  # noqa: E501
            secondary = f"To continue, the program will attempt to install the following package(s) by using '{config.PACKAGE_MANAGER_COMMAND_INSTALL}':\n{missing_packages}\nand will remove the following package(s) by using '{config.PACKAGE_MANAGER_COMMAND_REMOVE}':\n{conflicting_packages}"  # noqa: E501
        elif missing_packages:
            message = f"Your {config.OS_NAME} computer requires installing some software.\nProceed?"  # noqa: E501
            no_message = "User refused to install software via the application."  # noqa: E501
            secondary = f"To continue, the program will attempt to install the following package(s) by using '{config.PACKAGE_MANAGER_COMMAND_INSTALL}':\n{missing_packages}"  # noqa: E501
        elif conflicting_packages:
            message = f"Your {config.OS_NAME} computer requires removing some software.\nProceed?"  # noqa: E501
            no_message = "User refused to remove software via the application."  # noqa: E501
            secondary = f"To continue, the program will attempt to remove the following package(s) by using '{config.PACKAGE_MANAGER_COMMAND_REMOVE}':\n{conflicting_packages}"  # noqa: E501
        else:
            message = None

        if message is None:
            logging.debug("No missing or conflicting dependencies found.")
        elif not message:
            m = "Your distro requires manual dependency installation."
            logging.error(m)
        else:
            msg.logos_continue_question(message, no_message, secondary, app)
            if config.DIALOG == "curses":
                app.confirm_e.wait()

        # TODO: Need to send continue question to user based on DIALOG.
        # All we do above is create a message that we never send.
        # Do we need a TK continue question? I see we have a CLI and curses one
        # in msg.py

        preinstall_command = preinstall_dependencies()

        if missing_packages:
            install_command = config.PACKAGE_MANAGER_COMMAND_INSTALL + missing_packages  # noqa: E501
        else:
            logging.debug("No missing packages detected.")

        if conflicting_packages:
            # TODO: Verify with user before executing
            # AppImage Launcher is the only known conflicting package.
            remove_command = config.PACKAGE_MANAGER_COMMAND_REMOVE + conflicting_packages  # noqa: E501
            config.REBOOT_REQUIRED = True
            logging.info("System reboot required.")
        else:
            logging.debug("No conflicting packages detected.")

        postinstall_command = postinstall_dependencies(app)

        if preinstall_command:
            command.extend(preinstall_command)
        if install_command:
            if command:
                command.append('&&')
            command.extend(install_command)
        if remove_command:
            if command:
                command.append('&&')
            command.extend(remove_command)
        if postinstall_command:
            if command:
                command.append('&&')
            command.extend(postinstall_command)
        if not command:  # nothing to run; avoid running empty pkexec command
            if app:
                msg.status("All dependencies are met.", app)
                if config.DIALOG == "curses":
                    app.installdeps_e.set()
            return

        if app and config.DIALOG == 'tk':
            app.root.event_generate('<<StartIndeterminateProgress>>')
        msg.status("Installing dependencies…", app)
        final_command = [
            f"{config.SUPERUSER_COMMAND}", 'sh', '-c', '"', *command, '"'
        ]
        command_str = ' '.join(final_command)
        # TODO: Fix fedora/arch handling.
        if config.OS_NAME in ['fedora', 'arch']:
            manual_install_required = True
            sudo_command = command_str.replace("pkexec", "sudo")
            message = "The system needs to install/remove packages, but it requires manual intervention."  # noqa: E501
            detail = (
                "Please run the following command in a terminal, then restart "
                f"{config.name_app}:\n{sudo_command}\n"
            )
            if config.DIALOG == "tk":
                if hasattr(app, 'root'):
                    detail += "\nThe command has been copied to the clipboard."  # noqa: E501
                    app.root.clipboard_clear()
                    app.root.clipboard_append(sudo_command)
                    app.root.update()
                msg.logos_error(
                    message,
                    detail=detail,
                    app=app,
                    parent='installer_win'
                )
            elif config.DIALOG == 'cli':
                msg.logos_error(message + "\n" + detail)
            install_deps_failed = True

        if manual_install_required and app and config.DIALOG == "curses":
            app.screen_q.put(
                app.stack_confirm(
                    17,
                    app.manualinstall_q,
                    app.manualinstall_e,
                    f"Please run the following command in a terminal, then select \"Continue\" when finished.\n\n{config.name_app}:\n{sudo_command}\n",  # noqa: E501
                    "User cancelled dependency installation.",  # noqa: E501
                    message,
                    options=["Continue", "Return to Main Menu"], dialog=config.use_python_dialog))  # noqa: E501
            app.manualinstall_e.wait()

        if not install_deps_failed and not manual_install_required:
            if config.DIALOG == 'cli':
                command_str = command_str.replace("pkexec", "sudo")
            try:
                logging.debug(f"Attempting to run this command: {command_str}")
                run_command(command_str, shell=True)
            except subprocess.CalledProcessError as e:
                if e.returncode == 127:
                    logging.error("User cancelled dependency installation.")
                else:
                    logging.error(f"An error occurred in install_dependencies(): {e}")  # noqa: E501
                    logging.error(f"Command output: {e.output}")
                install_deps_failed = True
    else:
        msg.logos_error(
            f"The script could not determine your {config.OS_NAME} install's package manager or it is unsupported. "  # noqa: E501
            f"Your computer is missing the command(s) {missing_packages}. "
            f"Please install your distro's package(s) associated with {missing_packages} for {config.OS_NAME}.")  # noqa: E501

    if config.REBOOT_REQUIRED:
        question = "Should the program reboot the host now?"  # noqa: E501
        no_text = "The user has chosen not to reboot."
        secondary = "The system has installed or removed a package that requires a reboot."  # noqa: E501
        if msg.logos_continue_question(question, no_text, secondary):
            reboot()
        else:
            logging.error("Cannot proceed until reboot. Exiting.")
            sys.exit(1)

    if install_deps_failed:
        if app:
            if config.DIALOG == "curses":
                app.choice_q.put("Return to Main Menu")
    else:
        if app:
            if config.DIALOG == "curses":
                app.installdeps_e.set()


def install_winetricks(
        installdir,
        app=None,
        version=config.WINETRICKS_VERSION,
):
    msg.status(f"Installing winetricks v{version}…")
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
    config.WINETRICKSBIN = f"{installdir}/winetricks"
    logging.debug("Winetricks installed.")
