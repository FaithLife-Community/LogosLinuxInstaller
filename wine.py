import logging
import os
import psutil
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import config
import msg
import network
import system
import utils

from main import processes


def get_pids_using_file(file_path, mode=None):
    # Make list (set) of pids using 'directory'.
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


def wait_on(command):
    try:
        # Start the process in the background
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        msg.logos_msg(f"Waiting on \"{' '.join(command)}\" to finish.", end='')
        time.sleep(1.0)
        while process.poll() is None:
            msg.logos_progress()
            time.sleep(0.5)
        print()

        # Process has finished, check the result
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            logging.info(f"\"{' '.join(command)}\" has ended properly.")
        else:
            logging.error(f"Error: {stderr}")

    except Exception as e:
        logging.critical(f"{e}")


def light_wineserver_wait():
    command = [f"{config.WINESERVER_EXE}", "-w"]
    wait_on(command)


def heavy_wineserver_wait():
    utils.wait_process_using_dir(config.WINEPREFIX)
    wait_on([f"{config.WINESERVER_EXE}", "-w"])


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
    msg.logos_msg("Initializing wine bottle...")

    # Avoid wine-mono window
    orig_overrides = config.WINEDLLOVERRIDES
    config.WINEDLLOVERRIDES = f"{config.WINEDLLOVERRIDES};mscoree="
    run_wine_proc(str(utils.get_wine_exe_path()), exe='wineboot', exe_args=['--init'])
    config.WINEDLLOVERRIDES = orig_overrides
    light_wineserver_wait()


def wine_reg_install(reg_file):
    msg.logos_msg(f"Installing registry file: {reg_file}")
    env = get_wine_env()
    result = system.run_command(
        [str(utils.get_wine_exe_path()), "regedit.exe", reg_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=config.WORKDIR,
        capture_output=False
    )
    if result is None or result.returncode != 0:
        msg.logos_error(f"Failed to install reg file: {reg_file}")
    elif result.returncode == 0:
        logging.info(f"{reg_file} installed.")
    light_wineserver_wait()


def install_msi():
    msg.logos_msg(f"Running MSI installer: {config.LOGOS_EXECUTABLE}.")
    # Execute the .MSI
    exe_args = ["/i", f"{config.INSTALLDIR}/data/{config.LOGOS_EXECUTABLE}"]
    if config.PASSIVE is True:
        exe_args.append('/passive')
    logging.info(f"Running: {utils.get_wine_exe_path()} msiexec {' '.join(exe_args)}")
    run_wine_proc(str(utils.get_wine_exe_path()), exe="msiexec", exe_args=exe_args)


def run_wine_proc(winecmd, exe=None, exe_args=list()):
    env = get_wine_env()
    if config.WINECMD_ENCODING is None:
        # Get wine system's cmd.exe encoding for proper decoding to UTF8 later.
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
    wine_env_vars = {k: v for k, v in env.items() if k.startswith('WINE')}
    logging.debug(f"wine environment: {wine_env_vars}")

    command = [winecmd]
    if exe is not None:
        command.append(exe)
    if exe_args:
        command.extend(exe_args)
    logging.debug(f"subprocess cmd: '{' '.join(command)}'")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env
        )
        if exe is not None and isinstance(process, subprocess.Popen):
            processes[exe] = process
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
        returncode = process.wait()

        if returncode != 0:
            logging.error(f"Error running '{' '.join(command)}': {process.returncode}")  # noqa: E501

    except subprocess.CalledProcessError as e:
        logging.error(f"Exception running '{' '.join(command)}': {e}")


def run_winetricks(cmd=None):
    run_wine_proc(config.WINETRICKSBIN, exe=cmd)
    run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])


def winetricks_install(*args):
    cmd = [*args]
    msg.logos_msg(f"Running winetricks \"{args[-1]}\"")
    logging.info(f"running \"winetricks {' '.join(cmd)}\"")
    run_wine_proc(config.WINETRICKSBIN, exe_args=cmd)
    logging.info(f"\"winetricks {' '.join(cmd)}\" DONE!")
    heavy_wineserver_wait()


def installD3DCompiler():
    cmd = ['d3dcompiler_47']
    if config.WINETRICKS_UNATTENDED is None:
        cmd.insert(0, '-q')
    winetricks_install(*cmd)


def installFonts():
    msg.logos_msg("Configuring fonts…")
    fonts = ['corefonts', 'tahoma']
    if not config.SKIP_FONTS:
        for f in fonts:
            args = [f]
            if config.WINETRICKS_UNATTENDED:
                args.insert(0, '-q')
            winetricks_install(*args)

    winetricks_install('-q', 'settings', 'fontsmooth=rgb')


def installICUDataFiles(app=None):
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


def get_registry_value(reg_path, name):
    value = None
    env = get_wine_env()
    cmd = [str(utils.get_wine_exe_path()), 'reg', 'query', reg_path, '/v', name]
    err_msg = f"Failed to get registry value: {reg_path}\\{name}"
    try:
        result = system.run_command(
            cmd,
            encoding=config.WINECMD_ENCODING,
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
                break
    else:
        logging.critical(err_msg)
    return value


def get_app_logging_state(app=None, init=False):
    state = 'DISABLED'
    current_value = get_registry_value(
        'HKCU\\Software\\Logos4\\Logging',
        'Enabled'
    )
    if current_value == '0x1':
        state = 'ENABLED'
    if app is not None:
        app.logging_q.put(state)
        if init:
            app.root.event_generate('<<InitLoggingButton>>')
        else:
            app.root.event_generate('<<UpdateLoggingButton>>')
    return state


def switch_logging(action=None, app=None):
    state_disabled = 'DISABLED'
    value_disabled = '0000'
    state_enabled = 'ENABLED'
    value_enabled = '0001'
    if action == 'disable':
        value = value_disabled
        state = state_disabled
    elif action == 'enable':
        value = value_enabled
        state = state_enabled
    else:
        current_state = get_app_logging_state()
        logging.debug(f"app logging {current_state=}")
        if current_state == state_enabled:
            value = value_disabled
            state = state_disabled
        else:
            value = value_enabled
            state = state_enabled

    logging.info(f"Setting app logging to '{state}'.")
    exe_args = [
        'add', 'HKCU\\Software\\Logos4\\Logging', '/v', 'Enabled',
        '/t', 'REG_DWORD', '/d', value, '/f'
    ]
    run_wine_proc(str(utils.get_wine_exe_path()), exe='reg', exe_args=exe_args)
    run_wine_proc(config.WINESERVER_EXE, exe_args=['-w'])
    config.LOGS = state
    if app is not None:
        app.logging_q.put(state)
        app.root.event_generate(app.logging_event)


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
        'WINE_EXE': str(utils.get_wine_exe_path()),
        'WINEDEBUG': config.WINEDEBUG,
        'WINEDLLOVERRIDES': config.WINEDLLOVERRIDES,
        'WINELOADER': str(winepath),
        'WINEPREFIX': config.WINEPREFIX,
        'WINETRICKS_SUPER_QUIET': '',
    }
    for k, v in wine_env_defaults.items():
        wine_env[k] = v
    if config.LOG_LEVEL > logging.INFO:
        wine_env['WINETRICKS_SUPER_QUIET'] = "1"

    # Config file takes precedence over the above variables.
    cfg = config.get_config_file_dict(config.CONFIG_FILE)
    if cfg is not None:
        for key, value in cfg.items():
            if value is None:
                continue  # or value = ''?
            if key in wine_env_defaults.keys():
                wine_env[key] = value

    return wine_env


def run_logos(app=None):
    logos_release = utils.convert_logos_release(config.current_logos_version)
    wine_release, _ = get_wine_release(str(utils.get_wine_exe_path()))

    # TODO: Find a way to incorporate check_wine_version_and_branch()
    if 30 > logos_release[0] > 9 and (wine_release[0] < 7 or (wine_release[0] == 7 and wine_release[1] < 18)):  # noqa: E501
        txt = "Can't run Logos 10+ with Wine below 7.18."
        logging.critical(txt)
        msg.status(txt, app)
    if logos_release[0] > 29 and wine_release[0] < 9 and wine_release[1] < 10:
        txt = "Can't run Logos 30+ with Wine below 9.10."
        logging.critical(txt)
        msg.status(txt, app)
    else:
        run_wine_proc(str(utils.get_wine_exe_path()), exe=config.LOGOS_EXE)
        run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])


def run_indexing():
    logos_indexer_exe = None
    for root, dirs, files in os.walk(os.path.join(config.WINEPREFIX, "drive_c")):  # noqa: E501
        for f in files:
            if f == "LogosIndexer.exe" and root.endswith("Logos/System"):
                logos_indexer_exe = os.path.join(root, f)
                break

    if logos_indexer_exe is not None:
        run_wine_proc(config.WINESERVER_EXE, exe_args=["-k"])
        run_wine_proc(str(utils.get_wine_exe_path()), exe=logos_indexer_exe)
        run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])
    else:
        logging.error("LogosIndexer.exe not found.")


def end_wine_processes():
    for process_name, process in processes.items():
        if isinstance(process, subprocess.Popen):
            logging.debug(f"Found {process_name} in Processes. Attempting to close {process}.")  # noqa: E501
            try:
                process.terminate()
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
