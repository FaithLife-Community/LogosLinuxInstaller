import logging
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path

import config
import msg
import network
import system
import utils

from main import processes


def set_logos_paths():
    config.login_window_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\Logos.exe'
    config.logos_cef_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\LogosCEF.exe'
    config.logos_indexing_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\LogosIndexer.exe'
    for root, dirs, files in os.walk(os.path.join(config.WINEPREFIX, "drive_c")):  # noqa: E501
        for f in files:
            if f == "LogosIndexer.exe" and root.endswith("Logos/System"):
                config.logos_indexer_exe = os.path.join(root, f)
                break


def get_wine_user():
    path = config.LOGOS_EXE
    normalized_path = os.path.normpath(path)
    path_parts = normalized_path.split(os.sep)
    config.wine_user = path_parts[path_parts.index('users') + 1]


def check_wineserver():
    try:
        process = run_wine_proc(config.WINESERVER, exe_args=["-p"])
        process.wait()
        return process.returncode == 0
    except Exception as e:
        return False


def wineserver_kill():
    if check_wineserver():
        process = run_wine_proc(config.WINESERVER_EXE, exe_args=["-k"])
        process.wait()


#TODO: Review these three commands. The top is the newest and should be preserved.
# Can the other two be refactored out?
def wineserver_wait():
    if check_wineserver():
        process = run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])
        process.wait()


def light_wineserver_wait():
    command = [f"{config.WINESERVER_EXE}", "-w"]
    system.wait_on(command)


def heavy_wineserver_wait():
    utils.wait_process_using_dir(config.WINEPREFIX)
    system.wait_on([f"{config.WINESERVER_EXE}", "-w"])


def end_wine_processes():
    for process_name, process in processes.items():
        if isinstance(process, subprocess.Popen):
            logging.debug(f"Found {process_name} in Processes. Attempting to close {process}.")  # noqa: E501
            try:
                process.terminate()
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                wait_pid(process)


def get_wine_release(binary):
    cmd = [binary, "--version"]
    try:
        version_string = subprocess.check_output(cmd, encoding='utf-8').strip()
        logging.debug(f"Version string: {str(version_string)}")
        try:
            version, release = version_string.split()
        except ValueError:
            # Neither "Devel" nor "Stable" release is noted in version output
            version = version_string
            release = get_wine_branch(binary)

        logging.debug(f"Wine branch of {binary}: {release}")

        if release is not None:
            ver_major = version.split('.')[0].lstrip('wine-')  # remove 'wine-'
            ver_minor = version.split('.')[1]
            release = release.lstrip('(').rstrip(')').lower()  # remove parens
        else:
            ver_major = 0
            ver_minor = 0

        wine_release = [int(ver_major), int(ver_minor), release]
        logging.debug(f"Wine release of {binary}: {str(wine_release)}")

        if ver_major == 0:
            return False, "Couldn't determine wine version."
        else:
            return wine_release, "yes"

    except subprocess.CalledProcessError as e:
        return False, f"Error running command: {e}"

    except ValueError as e:
        return False, f"Error parsing version: {e}"

    except Exception as e:
        return False, f"Error: {e}"


def check_wine_version_and_branch(release_version, test_binary):
    # Does not check for Staging. Will not implement: expecting merging of
    # commits in time.
    if config.TARGETVERSION == "10":
        if utils.check_logos_release_version(release_version, 30, 1):
            wine_minimum = [7, 18]
        else:
            wine_minimum = [9, 10]
    elif config.TARGETVERSION == "9":
        wine_minimum = [7, 0]
    else:
        raise ValueError("TARGETVERSION not set.")

    # Check if the binary is executable. If so, check if TESTBINARY's version
    # is ≥ WINE_MINIMUM, or if it is Proton or a link to a Proton binary, else
    # remove.
    if not os.path.exists(test_binary):
        reason = "Binary does not exist."
        return False, reason

    if not os.access(test_binary, os.X_OK):
        reason = "Binary is not executable."
        return False, reason

    wine_release = []
    wine_release, error_message = get_wine_release(test_binary)

    if wine_release is not False and error_message is not None:
        if wine_release[2] == 'stable':
            return False, "Can't use Stable release"
        elif wine_release[0] < 7:
            return False, "Version is < 7.0"
        elif wine_release[0] == 7:
            if (
                "Proton" in test_binary
                or ("Proton" in os.path.realpath(test_binary) if os.path.islink(test_binary) else False)  # noqa: E501
            ):
                if wine_release[1] == 0:
                    return True, "None"
            elif wine_release[2] != 'staging':
                return False, "Needs to be Staging release"
            elif wine_release[1] < wine_minimum[1]:
                reason = f"{'.'.join(wine_release)} is below minimum required, {'.'.join(wine_minimum)}"  # noqa: E501
                return False, reason
        elif wine_release[0] == 8:
            if wine_release[1] < 1:
                return False, "Version is 8.0"
            elif wine_release[1] < 16:
                if wine_release[2] != 'staging':
                    return False, "Version < 8.16 needs to be Staging release"
        elif wine_release[0] == 9:
            if wine_release[1] < 10:
                return False, "Version < 9.10"
        elif wine_release[0] > 9:
            pass
    else:
        return False, error_message

    return True, "None"


def initializeWineBottle(app=None):
    msg.status("Initializing wine bottle…")
    wine_exe = str(utils.get_wine_exe_path().parent / 'wine64')
    logging.debug(f"{wine_exe=}")
    # Avoid wine-mono window
    orig_overrides = config.WINEDLLOVERRIDES
    config.WINEDLLOVERRIDES = f"{config.WINEDLLOVERRIDES};mscoree="
    logging.debug(f"Running: {wine_exe} wineboot --init")
    process = run_wine_proc(wine_exe, exe='wineboot', exe_args=['--init'], init=True)
    config.WINEDLLOVERRIDES = orig_overrides
    return process


def wine_reg_install(reg_file):
    reg_file = str(reg_file)
    msg.status(f"Installing registry file: {reg_file}")
    process = run_wine_proc(
        str(utils.get_wine_exe_path().parent / 'wine64'),
        exe="regedit.exe",
        exe_args=[reg_file]
    )
    process.wait()
    if process is None or process.returncode != 0:
        failed = "Failed to install reg file"
        logging.debug(f"{failed}. {process=}")
        msg.logos_error(f"{failed}: {reg_file}")
    elif process.returncode == 0:
        logging.info(f"{reg_file} installed.")
    light_wineserver_wait()


def install_msi(app=None):
    msg.status(f"Running MSI installer: {config.LOGOS_EXECUTABLE}.", app)
    # Execute the .MSI
    wine_exe = str(utils.get_wine_exe_path().parent / 'wine64')
    exe_args = ["/i", f"{config.INSTALLDIR}/data/{config.LOGOS_EXECUTABLE}"]
    if config.PASSIVE is True:
        exe_args.append('/passive')
    logging.info(f"Running: {wine_exe} msiexec {' '.join(exe_args)}")
    process = run_wine_proc(wine_exe, exe="msiexec", exe_args=exe_args)
    return process


def wait_pid(process):
    os.waitpid(-process.pid, 0)


def run_wine_proc(winecmd, exe=None, exe_args=list(), init=False):
    logging.debug("Getting wine environment.")
    env = get_wine_env()
    if not init and config.WINECMD_ENCODING is None:
        # Get wine system's cmd.exe encoding for proper decoding to UTF8 later.
        logging.debug("Getting wine system's cmd.exe encoding.")
        registry_value = get_registry_value(
            'HKCU\\Software\\Wine\\Fonts',
            'Codepages'
        )
        if registry_value is not None:
            codepages = registry_value.split(',')  # noqa: E501
            config.WINECMD_ENCODING = codepages[-1]
        else:
            m = "wine.wine_proc: wine.get_registry_value returned None."
            logging.error(m)
    if isinstance(winecmd, Path):
        winecmd = str(winecmd)
    logging.debug(f"run_wine_proc: {winecmd}; {exe=}; {exe_args=}")

    command = [winecmd]
    if exe is not None:
        command.append(exe)
    if exe_args:
        command.extend(exe_args)

    logging.debug(f"subprocess cmd: '{' '.join(command)}'")
    try:
        with open(config.wine_log, 'a') as wine_log:
            process = system.popen_command(
                command,
                stdout=wine_log,
                stderr=wine_log,
                env=env,
                start_new_session=True
            )
            if process is not None:
                if exe is not None and isinstance(process, subprocess.Popen):
                    config.processes[exe] = process
                if process.poll() is None and process.stdout is not None:
                    with process.stdout:
                        for line in iter(process.stdout.readline, b''):
                            if winecmd.endswith('winetricks'):
                                logging.debug(line.decode('cp437').rstrip())
                            else:
                                try:
                                    logging.info(line.decode().rstrip())
                                except UnicodeDecodeError:
                                    if config.WINECMD_ENCODING is not None:
                                        logging.info(line.decode(config.WINECMD_ENCODING).rstrip())  # noqa: E501
                                    else:
                                        logging.error("wine.run_wine_proc: Error while decoding: WINECMD_ENCODING is None.")  # noqa: E501
                # returncode = process.wait()
                #
                # if returncode != 0:
                #     logging.error(f"Error running '{' '.join(command)}': {process.returncode}")  # noqa: E501
                return process
            else:
                return None

    except subprocess.CalledProcessError as e:
        logging.error(f"Exception running '{' '.join(command)}': {e}")

    return process


def run_winetricks(cmd=None):
    process = run_wine_proc(config.WINETRICKSBIN, exe=cmd)
    wait_pid(process)
    wineserver_wait()

def run_winetricks_cmd(*args):
    cmd = [*args]
    msg.status(f"Running winetricks \"{args[-1]}\"")
    logging.info(f"running \"winetricks {' '.join(cmd)}\"")
    process = run_wine_proc(config.WINETRICKSBIN, exe_args=cmd)
    wait_pid(process)
    logging.info(f"\"winetricks {' '.join(cmd)}\" DONE!")
    heavy_wineserver_wait()


def install_d3d_compiler():
    cmd = ['d3dcompiler_47']
    if config.WINETRICKS_UNATTENDED is None:
        cmd.insert(0, '-q')
    run_winetricks_cmd(*cmd)


def install_fonts():
    msg.status("Configuring fonts…")
    fonts = ['corefonts', 'tahoma']
    if not config.SKIP_FONTS:
        for f in fonts:
            args = [f]
            if config.WINETRICKS_UNATTENDED:
                args.insert(0, '-q')
            run_winetricks_cmd(*args)


def install_font_smoothing():
    msg.status("Setting font smoothing…")
    args = ['settings', 'fontsmooth=rgb']
    if config.WINETRICKS_UNATTENDED:
        args.insert(0, '-q')
    run_winetricks_cmd(*args)


def set_renderer(renderer):
    run_winetricks_cmd("-q", "settings", f"renderer={renderer}")


def set_win_version(exe, windows_version):
    if exe == "logos":
        run_winetricks_cmd('-q', 'settings', f'{windows_version}')
    elif exe == "indexer":
        reg = f"HKCU\\Software\\Wine\\AppDefaults\\{config.FLPRODUCT}Indexer.exe"  # noqa: E501
        exe_args = [
            'add',
            reg,
            "/v", "Version",
            "/t", "REG_SZ",
            "/d", f"{windows_version}", "/f",
            ]
        process = run_wine_proc(str(utils.get_wine_exe_path()), exe='reg', exe_args=exe_args)
        wait_pid(process)


def install_icu_data_files(app=None):
    releases_url = "https://api.github.com/repos/FaithLife-Community/icu/releases"  # noqa: E501
    json_data = network.get_latest_release_data(releases_url)
    icu_url = network.get_latest_release_url(json_data)
    # icu_tag_name = utils.get_latest_release_version_tag_name(json_data)
    if icu_url is None:
        logging.critical("Unable to set LogosLinuxInstaller release without URL.")  # noqa: E501
        return
    icu_filename = os.path.basename(icu_url)
    network.logos_reuse_download(
        icu_url,
        icu_filename,
        config.MYDOWNLOADS,
        app=app
    )
    drive_c = f"{config.INSTALLDIR}/data/wine64_bottle/drive_c"
    utils.untar_file(f"{config.MYDOWNLOADS}/icu-win.tar.gz", drive_c)

    # Ensure the target directory exists
    icu_win_dir = f"{drive_c}/icu-win/windows"
    if not os.path.exists(icu_win_dir):
        os.makedirs(icu_win_dir)

    shutil.copytree(icu_win_dir, f"{drive_c}/windows", dirs_exist_ok=True)
    if hasattr(app, 'status_evt'):
        app.status_q.put("ICU files copied.")
        app.root.event_generate(app.status_evt)

    if app:
        if config.DIALOG == "curses":
            app.install_icu_e.set()


def get_registry_value(reg_path, name):
    logging.debug(f"Get value for: {reg_path=}; {name=}")
    # NOTE: Can't use run_wine_proc here because of infinite recursion while
    # trying to determine WINECMD_ENCODING.
    value = None
    env = get_wine_env()

    cmd = [
        str(utils.get_wine_exe_path().parent / 'wine64'),
        'reg', 'query', reg_path, '/v', name,
    ]
    err_msg = f"Failed to get registry value: {reg_path}\\{name}"
    encoding = config.WINECMD_ENCODING
    if encoding is None:
        encoding = 'UTF-8'
    try:
        result = system.run_command(
            cmd,
            encoding=encoding,
            env=env
        )
    except subprocess.CalledProcessError as e:
        if 'non-zero exit status' in str(e):
            logging.warning(err_msg)
            return None
    if result.stdout is not None:
        for line in result.stdout.splitlines():
            if line.strip().startswith(name):
                value = line.split()[-1].strip()
                logging.debug(f"Registry value: {value}")
                break
    else:
        logging.critical(err_msg)
    return value


def get_mscoree_winebranch(mscoree_file):
    try:
        with mscoree_file.open('rb') as f:
            for line in f:
                m = re.search(rb'wine-[a-z]+', line)
                if m is not None:
                    return m[0].decode().lstrip('wine-')
    except FileNotFoundError as e:
        logging.error(e)


def get_wine_branch(binary):
    logging.info(f"Determining wine branch of '{binary}'")
    binary_obj = Path(binary).expanduser().resolve()
    if utils.check_appimage(binary_obj):
        logging.debug(f"Mounting AppImage: {binary_obj}")
        # Mount appimage to inspect files.
        p = subprocess.Popen(
            [binary_obj, '--appimage-mount'],
            stdout=subprocess.PIPE,
            encoding='UTF8'
        )
        branch = None
        while p.returncode is None:
            for line in p.stdout:
                if line.startswith('/tmp'):
                    tmp_dir = Path(line.rstrip())
                    for f in tmp_dir.glob('org.winehq.wine.desktop'):
                        if not branch:
                            for dline in f.read_text().splitlines():
                                try:
                                    k, v = dline.split('=')
                                except ValueError:  # not a key=value line
                                    continue
                                if k == 'X-AppImage-Version':
                                    branch = v.split('_')[0]
                                    logging.debug(f"{branch=}")
                                    break
                p.send_signal(signal.SIGINT)
            p.poll()
        return branch
    else:
        logging.debug("Binary object is not an AppImage.")
    logging.info(f"'{binary}' resolved to '{binary_obj}'")
    mscoree64 = binary_obj.parents[1] / 'lib64' / 'wine' / 'x86_64-windows' / 'mscoree.dll'  # noqa: E501
    return get_mscoree_winebranch(mscoree64)


def get_wine_env():
    wine_env = os.environ.copy()
    winepath = utils.get_wine_exe_path()
    if winepath.name != 'wine64':  # AppImage
        # Winetricks commands can fail if 'wine64' is not explicitly defined.
        # https://github.com/Winetricks/winetricks/issues/2084#issuecomment-1639259359
        winepath = winepath.parent / 'wine64'
    wine_env_defaults = {
        'WINE': str(winepath),
        'WINEDEBUG': config.WINEDEBUG,
        'WINEDLLOVERRIDES': config.WINEDLLOVERRIDES,
        'WINELOADER': str(winepath),
        'WINEPREFIX': config.WINEPREFIX,
        'WINESERVER': config.WINESERVER_EXE,
        # The following seems to cause some winetricks commands to fail; e.g.
        # 'winetricks settings win10' exits with ec = 1 b/c it fails to find
        # %ProgramFiles%, %AppData%, etc.
        # 'WINETRICKS_SUPER_QUIET': '',
    }
    for k, v in wine_env_defaults.items():
        wine_env[k] = v
    # if config.LOG_LEVEL > logging.INFO:
    #     wine_env['WINETRICKS_SUPER_QUIET'] = "1"

    # Config file takes precedence over the above variables.
    cfg = config.get_config_file_dict(config.CONFIG_FILE)
    if cfg is not None:
        for key, value in cfg.items():
            if value is None:
                continue  # or value = ''?
            if key in wine_env_defaults.keys():
                wine_env[key] = value

    updated_env = {k: wine_env.get(k) for k in wine_env_defaults.keys()}
    logging.debug(f"Wine env: {updated_env}")
    return wine_env
