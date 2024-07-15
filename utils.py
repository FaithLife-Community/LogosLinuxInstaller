import atexit
import glob
import inspect
import json
import logging
import os
import psutil
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import tkinter as tk
from packaging import version
from pathlib import Path
from typing import List, Union

import config
import msg
import network
import system
import tui_dialog
import wine

#TODO: Move config commands to config.py


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
    system.get_os()
    system.get_superuser_command()
    system.get_package_manager()
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


def log_current_persistent_config():
    logging.debug("Current persistent config:")
    for k in config.core_config_keys:
        logging.debug(f"{k}: {config.__dict__.get(k)}")


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
        system.install_dependencies(config.PACKAGES, config.BADPACKAGES, app=app)
    elif targetversion == 9:
        system.install_dependencies(
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

    if system.get_runmode() != 'binary':
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
