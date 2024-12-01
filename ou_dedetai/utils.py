import atexit
from datetime import datetime
import enum
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
import tarfile
import threading
import time
from ou_dedetai.app import App
from packaging import version
from pathlib import Path
from typing import List, Optional, Tuple

from . import config
from . import constants
from . import msg
from . import network
from . import system
if system.have_dep("dialog"):
    from . import tui_dialog as tui
else:
    from . import tui_curses as tui
from . import wine

# TODO: Move config commands to config.py


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
# XXX: fold this into config
def set_default_config():
    system.get_package_manager()
    if config.CONFIG_FILE is None:
        config.CONFIG_FILE = constants.DEFAULT_CONFIG_PATH


# XXX: remove, no need.
def write_config(config_file_path):
    pass


# XXX: refactor
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
            raise (f"Error writing to config file {config_file_path}: {e}") from e # noqa: E501


def die_if_running(app: App):

    def remove_pid_file():
        if os.path.exists(constants.PID_FILE):
            os.remove(constants.PID_FILE)

    if os.path.isfile(constants.PID_FILE):
        with open(constants.PID_FILE, 'r') as f:
            pid = f.read().strip()
            message = f"The script is already running on PID {pid}. Should it be killed to allow this instance to run?"  # noqa: E501
            if app.approve(message):
                os.kill(int(pid), signal.SIGKILL)

    atexit.register(remove_pid_file)
    with open(constants.PID_FILE, 'w') as f:
        f.write(str(os.getpid()))


def die(message):
    logging.critical(message)
    sys.exit(1)


def restart_lli():
    logging.debug(f"Restarting {constants.APP_NAME}.")
    pidfile = Path(constants.PID_FILE)
    if pidfile.is_file():
        pidfile.unlink()
    os.execv(sys.executable, [sys.executable])
    sys.exit()


def clean_all():
    logging.info("Cleaning all temp files…")
    os.system(f"rm -f {os.getcwd()}/wget-log*")
    logging.info("done")


def get_user_downloads_dir() -> str:
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


# XXX: seems like it should be in control
def install_dependencies(app: App):
    if app.conf.faithlife_product_version:
        targetversion = int(app.conf.faithlife_product_version)
    else:
        targetversion = 10
    app.status(f"Checking Logos {str(targetversion)} dependencies…")

    if targetversion == 10:
        system.install_dependencies(app, target_version=10)  # noqa: E501
    elif targetversion == 9:
        system.install_dependencies(
            app,
            target_version=9
        )
    else:
        logging.error(f"Unknown Target version, expecting 9 or 10 but got: {app.conf.faithlife_product_version}.")

    app.status("Installed dependencies.", 100)


def file_exists(file_path: Optional[str | bytes | Path]) -> bool:
    if file_path is not None:
        expanded_path = os.path.expanduser(file_path)
        return os.path.isfile(expanded_path)
    else:
        return False


def get_current_logos_version(install_dir: str) -> Optional[str]:
    path_regex = f"{install_dir}/data/wine64_bottle/drive_c/users/*/AppData/Local/Logos/System/Logos.deps.json"  # noqa: E501
    file_paths = glob.glob(path_regex)
    logos_version_number: Optional[str] = None
    if file_paths:
        logos_version_file = file_paths[0]
        with open(logos_version_file, 'r') as json_file:
            json_data = json.load(json_file)
        for key in json_data.get('libraries', dict()):
            if key.startswith('Logos') and '/' in key:
                logos_version_number = key.split('/')[1]

        logging.debug(f"{logos_version_number=}")
        if logos_version_number is not None:
            return logos_version_number
        else:
            logging.debug("Couldn't determine installed Logos version.")
            return None
    else:
        logging.debug("Logos.deps.json not found.")
    return None


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

    logos_release_arr = [
        int(ver_major),
        int(ver_minor),
        int(release),
        int(point),
    ]
    return logos_release_arr

def check_logos_release_version(version, threshold, check_version_part):
    if version is not None:
        version_parts = list(map(int, version.split('.')))
        return version_parts[check_version_part - 1] < threshold
    else:
        return False


def filter_versions(versions, threshold, check_version_part):
    return [version for version in versions if check_logos_release_version(version, threshold, check_version_part)]  # noqa: E501


# FIXME: consider where we want this
def get_winebin_code_and_desc(app: App, binary) -> Tuple[str, str | None]:
    """Gets the type of wine in use and it's description
    
    Returns:
        code: One of: Recommended, AppImage, System, Proton, PlayOnLinux, Custom
        description: Description of the above
    """
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
    if isinstance(binary, Path):
        binary = str(binary)
    if binary == f"{app.conf.installer_binary_dir}/{app.conf.wine_appimage_recommended_file_name}":  # noqa: E501
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


def get_wine_options(app: App, appimages, binaries) -> List[str]:  # noqa: E501
    logging.debug(f"{appimages=}")
    logging.debug(f"{binaries=}")
    wine_binary_options = []

    # Add AppImages to list
    wine_binary_options.append(f"{app.conf.installer_binary_dir}/{app.conf.wine_appimage_recommended_file_name}")  # noqa: E501
    wine_binary_options.extend(appimages)

    sorted_binaries = sorted(list(set(binaries)))
    logging.debug(f"{sorted_binaries=}")

    for wine_binary_path in sorted_binaries:
        code, description = get_winebin_code_and_desc(app, wine_binary_path)  # noqa: E501

        # Create wine binary option array
        wine_binary_options.append(wine_binary_path)
    logging.debug(f"{wine_binary_options=}")
    return wine_binary_options


def get_winetricks_options() -> list[str]:
    local_winetricks_path = shutil.which('winetricks')
    winetricks_options = ['Download']
    if local_winetricks_path is not None:
        if check_winetricks_version(local_winetricks_path):
            winetricks_options.insert(0, local_winetricks_path)
        else:
            logging.info("Local winetricks is too old.")
    else:
        logging.info("Local winetricks not found.")
    return winetricks_options

def check_winetricks_version(winetricks_path: str) -> bool:
    # Check if local winetricks version matches expected
    cmd = [winetricks_path, "--version"]
    local_winetricks_version = subprocess.check_output(cmd).split()[0]
    return str(local_winetricks_version) == constants.WINETRICKS_VERSION #noqa: E501


def get_procs_using_file(file_path, mode=None):
    procs = set()
    for proc in psutil.process_iter(['pid', 'open_files', 'name']):
        try:
            if mode is not None:
                paths = [f.path for f in proc.open_files() if f.mode == mode]
            else:
                paths = [f.path for f in proc.open_files()]
            if len(paths) > 0 and file_path in paths:
                procs.add(proc.pid)
        except psutil.AccessDenied:
            pass
    return procs


# def get_pids_using_file(file_path, mode=None):
#     pids = set()
#     for proc in psutil.process_iter(['pid', 'open_files']):
#         try:
#             if mode is not None:
#                 paths = [f.path for f in proc.open_files() if f.mode == mode]
#             else:
#                 paths = [f.path for f in proc.open_files()]
#             if len(paths) > 0 and file_path in paths:
#                 pids.add(proc.pid)
#         except psutil.AccessDenied:
#             pass
#     return pids


# def wait_process_using_dir(directory):
#     logging.info(f"* Starting wait_process_using_dir for {directory}…")

#     # Get pids and wait for them to finish.
#     pids = get_pids_using_file(directory)
#     for pid in pids:
#         logging.info(f"wait_process_using_dir PID: {pid}")
#         psutil.wait(pid)

#     logging.info("* End of wait_process_using_dir.")


def find_installed_product(faithlife_product: str, wine_prefix: str) -> Optional[str]:
    if faithlife_product and wine_prefix:
        drive_c = Path(f"{wine_prefix}/drive_c/")
        name = faithlife_product
        exe = None
        for root, _, files in drive_c.walk(follow_symlinks=False):
            if root.name == name and f"{name}.exe" in files:
                exe = str(root / f"{name}.exe")
                break
        return exe
    return None


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
    msg.status(f"Extracting: '{constants.LOGOS9_WINE64_BOTTLE_TARGZ_NAME}' into: {appdir}")  # noqa: E501
    shutil.unpack_archive(
        f"{srcdir}/{constants.LOGOS9_WINE64_BOTTLE_TARGZ_NAME}",
        appdir
    )

class VersionComparison(enum.Enum):
    OUT_OF_DATE = enum.auto()
    UP_TO_DATE = enum.auto()
    DEVELOPMENT = enum.auto()


def compare_logos_linux_installer_version(app: App) -> Optional[VersionComparison]:
    current = constants.LLI_CURRENT_VERSION
    latest = app.conf.app_latest_version

    if version.parse(current) < version.parse(latest):
        # Current release is older than recommended.
        output = VersionComparison.OUT_OF_DATE
    elif version.parse(current) > version.parse(latest):
        # Installed version is custom.
        output = VersionComparison.DEVELOPMENT
    elif version.parse(current) == version.parse(latest):
        # Current release is latest.
        output = VersionComparison.UP_TO_DATE

    logging.debug(f"LLI self-update check: {output=}")
    return output


def compare_recommended_appimage_version(app: App):
    status = None
    message = None
    wine_release = []
    wine_exe_path = app.conf.wine_binary
    wine_release, error_message = wine.get_wine_release(wine_exe_path)
    if wine_release is not None and wine_release is not False:
        current_version = '.'.join([str(n) for n in wine_release[:2]])
        logging.debug(f"Current wine release: {current_version}")

        recommended_version = app.conf.wine_appimage_recommended_version
        logging.debug(f"Recommended wine release: {recommended_version}")
        if current_version < recommended_version:
            # Current release is older than recommended.
            status = 0
            message = "yes"
        elif current_version == recommended_version:
            # Current release is latest.
            status = 1
            message = "uptodate"
        elif current_version > recommended_version:
            # Installed version is custom
            status = 2
            message = "no"
    else:
        # FIXME: should this raise an exception?
        status = -1
        message = f"Error: {error_message}"

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

        return appimage_check, appimage_type
    else:
        logging.error(f"File does not exist: {expanded_path}")
        return False, None


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


def find_appimage_files(app: App):
    release_version = app.conf.installed_faithlife_product_release or app.conf.faithlife_product_version
    appimages = []
    directories = [
        os.path.expanduser("~") + "/bin",
        app.conf.installer_binary_dir,
        app.conf.download_dir
    ]
    # FIXME: consider what we should do with this, promote to top level config?
    if app.conf._overrides.custom_binary_path is not None:
        directories.append(app.conf._overrides.custom_binary_path)

    if sys.version_info < (3, 12):
        raise RuntimeError("Python 3.12 or higher is required for .rglob() flag `case-sensitive` ")  # noqa: E501

    for d in directories:
        appimage_paths = Path(d).glob('wine*.appimage', case_sensitive=False)
        for p in appimage_paths:
            if p is not None and check_appimage(p):
                output1, output2 = wine.check_wine_version_and_branch(
                    release_version,
                    p,
                    app.conf.faithlife_product_version
                )
                if output1 is not None and output1:
                    appimages.append(str(p))
                else:
                    logging.info(f"AppImage file {p} not added: {output2}")

    # FIXME: consider if this messaging is needed
    # if app:
    #     app.appimage_q.put(appimages)
    #     app.root.event_generate(app.appimage_evt)

    return appimages


def find_wine_binary_files(app: App, release_version):
    wine_binary_path_list = [
        "/usr/local/bin",
        os.path.expanduser("~") + "/bin",
        os.path.expanduser("~") + "/PlayOnLinux/wine/linux-amd64/*/bin",
        os.path.expanduser("~") + "/.steam/steam/steamapps/common/Proton*/files/bin",  # noqa: E501
    ]

    if app.conf._overrides.custom_binary_path is not None:
        wine_binary_path_list.append(app.conf._overrides.custom_binary_path)

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
        output1, output2 = wine.check_wine_version_and_branch(
            release_version,
            binary,
            app.conf.faithlife_product_version
        )
        if output1 is not None and output1:
            continue
        else:
            binaries.remove(binary)
            logging.info(f"Removing binary: {binary} because: {output2}")

    return binaries


def set_appimage_symlink(app: App):
    # This function assumes make_skel() has been run once.
    if app.conf.wine_binary_code not in ["AppImage", "Recommended"]:
        logging.debug("AppImage commands disabled since we're not using an appimage")  # noqa: E501
        return
    if app.conf.wine_appimage_path is None:
        logging.debug("No need to set appimage symlink, as it wasn't set")
        return

    logging.debug(f"config.APPIMAGE_FILE_PATH={app.conf.wine_appimage_path}")
    logging.debug(f"config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME={app.conf.wine_appimage_recommended_file_name}")
    appimage_file_path = Path(app.conf.wine_appimage_path)
    appdir_bindir = Path(app.conf.installer_binary_dir)
    appimage_symlink_path = appdir_bindir / app.conf.wine_appimage_link_file_name
    if appimage_file_path.name == app.conf.wine_appimage_recommended_file_name:  # noqa: E501
        # Default case.
        network.get_recommended_appimage(app)
        selected_appimage_file_path = appdir_bindir / appimage_file_path.name  # noqa: E501
        bindir_appimage = selected_appimage_file_path / app.conf.installer_binary_dir  # noqa: E501
        if not bindir_appimage.exists():
            logging.info(f"Copying {selected_appimage_file_path} to {app.conf.installer_binary_dir}.")  # noqa: E501
            shutil.copy(selected_appimage_file_path, f"{app.conf.installer_binary_dir}")
    else:
        selected_appimage_file_path = appimage_file_path
        # Verify user-selected AppImage.
        if not check_appimage(selected_appimage_file_path):
            app.exit(f"Cannot use {selected_appimage_file_path}.")

        # Determine if user wants their AppImage in the app bin dir.
        copy_question = (
            f"Should the program copy {selected_appimage_file_path} to the"
            f" {app.conf.installer_binary_dir} directory?"
        )
        # Copy AppImage if confirmed.
        if app.approve(copy_question):
            logging.info(f"Copying {selected_appimage_file_path} to {app.conf.installer_binary_dir}.")  # noqa: E501
            dest = appdir_bindir / selected_appimage_file_path.name
            if not dest.exists():
                shutil.copy(selected_appimage_file_path, f"{app.conf.installer_binary_dir}")  # noqa: E501
            selected_appimage_file_path = dest

    delete_symlink(appimage_symlink_path)
    os.symlink(selected_appimage_file_path, appimage_symlink_path)
    app.conf.wine_appimage_path = f"{selected_appimage_file_path.name}"  # noqa: E501

    write_config(config.CONFIG_FILE)


def update_to_latest_lli_release(app: App):
    result = compare_logos_linux_installer_version(app)

    if system.get_runmode() != 'binary':
        logging.error(f"Can't update {constants.APP_NAME} when run as a script.")
    elif result == VersionComparison.OUT_OF_DATE:
        network.update_lli_binary(app=app)
    elif result == VersionComparison.UP_TO_DATE:
        logging.debug(f"{constants.APP_NAME} is already at the latest version.")
    elif result == VersionComparison.DEVELOPMENT:
        logging.debug(f"{constants.APP_NAME} is at a newer version than the latest.") # noqa: 501


# XXX: seems like this should be in control
def update_to_latest_recommended_appimage(app: App):
    if app.conf.wine_binary_code not in ["AppImage", "Recommended"]:
        logging.debug("AppImage commands disabled since we're not using an appimage")  # noqa: E501
        return
    app.conf.wine_appimage_path = app.conf.wine_appimage_recommended_file_name  # noqa: E501
    status, _ = compare_recommended_appimage_version(app)
    if status == 0:
        set_appimage_symlink(app)
    elif status == 1:
        logging.debug("The AppImage is already set to the latest recommended.")
    elif status == 2:
        logging.debug("The AppImage version is newer than the latest recommended.")  # noqa: E501


def get_downloaded_file_path(download_dir: str, filename: str):
    dirs = [
        Path(download_dir),
        Path.home(),
        Path.cwd(),
    ]
    for d in dirs:
        file_path = Path(d) / filename
        if file_path.is_file():
            logging.info(f"'{filename}' exists in {str(d)}.")
            return str(file_path)
    logging.debug(f"File not found: {filename}")


def grep(regexp, filepath):
    fp = Path(filepath)
    found = False
    ct = 0
    if fp.exists():
        with fp.open() as f:
            for line in f:
                ct += 1
                text = line.rstrip()
                if re.search(regexp, text):
                    logging.debug(f"{filepath}:{ct}:{text}")
                    found = True
    return found


def start_thread(task, *args, daemon_bool=True, **kwargs):
    thread = threading.Thread(
        name=f"{task}",
        target=task,
        daemon=daemon_bool,
        args=args,
        kwargs=kwargs
    )
    config.threads.append(thread)
    thread.start()
    return thread


def str_array_to_string(text, delimeter="\n"):
    try:
        processed_text = delimeter.join(text)
        return processed_text
    except TypeError:
        return text


def untar_file(file_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with tarfile.open(file_path, 'r:gz') as tar:
            tar.extractall(path=output_dir)
            logging.debug(f"Successfully extracted '{file_path}' to '{output_dir}'")  # noqa: E501
    except tarfile.TarError as e:
        logging.error(f"Error extracting '{file_path}': {e}")


def is_relative_path(path: str | Path) -> bool:
    if isinstance(path, str):
        path = Path(path)
    return not path.is_absolute()


def get_relative_path(path: Path | str, base_path: str) -> str | Path:
    if is_relative_path(path):
        return path
    else:
        if isinstance(path, Path):
            path = str(path)
        base_path = str(base_path)
        if path.startswith(base_path):
            return path[len(base_path):].lstrip(os.sep)
        else:
            return path


def create_dynamic_path(path, base_path):
    if is_relative_path(path):
        if isinstance(path, str):
            path = Path(path)
        if isinstance(base_path, str):
            base_path = Path(base_path)
        logging.debug(f"dynamic_path: {base_path / path}")
        return base_path / path
    else:
        logging.debug(f"dynamic_path: {Path(path)}")
        return Path(path)


def get_config_var(var):
    if var is not None:
        if callable(var):
            return var()
        return var
    else:
        return None

def stopwatch(start_time=None, interval=10.0):
    if start_time is None:
        start_time = time.time()

    current_time = time.time()
    elapsed_time = current_time - start_time

    if elapsed_time >= interval:
        last_log_time = current_time
        return True, last_log_time
    else:
        return False, start_time

def get_timestamp():
    return datetime.today().strftime('%Y-%m-%dT%H%M%S')

def parse_bool(string: str) -> bool:
    return string.lower() in ['true', '1', 'y', 'yes']