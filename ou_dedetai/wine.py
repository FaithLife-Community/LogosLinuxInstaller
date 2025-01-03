import logging
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path
from typing import Optional

from . import config
from . import msg
from . import network
from . import system
from . import utils

from .config import processes


def get_wine_user():
    path: Optional[str] = config.LOGOS_EXE
    normalized_path: str = os.path.normpath(path)
    path_parts = normalized_path.split(os.sep)
    config.wine_user = path_parts[path_parts.index('users') + 1]


def set_logos_paths():
    if config.wine_user is None:
        get_wine_user()
    logos_cmds = [
        config.logos_cef_cmd,
        config.logos_indexer_cmd,
        config.logos_login_cmd,
    ]
    if None in logos_cmds:
        config.logos_cef_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\LogosCEF.exe'  # noqa: E501
        config.logos_indexer_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\LogosIndexer.exe'  # noqa: E501
        config.logos_login_cmd = f'C:\\users\\{config.wine_user}\\AppData\\Local\\Logos\\System\\Logos.exe'  # noqa: E501
    config.logos_indexer_exe = str(Path(utils.find_installed_product()).parent / 'System' / 'LogosIndexer.exe')  # noqa: E501


def check_wineserver():
    try:
        process = run_wine_proc(config.WINESERVER, exe_args=["-p"])
        wait_pid(process)
        return process.returncode == 0
    except Exception:
        return False


def wineserver_kill():
    if check_wineserver():
        process = run_wine_proc(config.WINESERVER_EXE, exe_args=["-k"])
        wait_pid(process)


def wineserver_wait():
    if check_wineserver():
        process = run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])
        wait_pid(process)


# def light_wineserver_wait():
#     command = [f"{config.WINESERVER_EXE}", "-w"]
#     system.wait_on(command)


# def heavy_wineserver_wait():
#     utils.wait_process_using_dir(config.WINEPREFIX)
#     # system.wait_on([f"{config.WINESERVER_EXE}", "-w"])
#     wineserver_wait()


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


def check_wine_rules(wine_release, release_version):
    # Does not check for Staging. Will not implement: expecting merging of
    # commits in time.
    logging.debug(f"Checking {wine_release} for {release_version}.")
    if config.TARGETVERSION == "10":
        if utils.check_logos_release_version(release_version, 30, 1):
            required_wine_minimum = [7, 18]
        else:
            required_wine_minimum = [9, 10]
    elif config.TARGETVERSION == "9":
        required_wine_minimum = [7, 0]
    else:
        raise ValueError(f"Invalid TARGETVERSION: {config.TARGETVERSION} ({type(config.TARGETVERSION)})")  # noqa: E501

    rules = [
        {
            "major": 7,
            "proton": True,  # Proton release tend to use the x.0 release, but can include changes found in devel/staging  # noqa: E501
            "minor_bad": [],  # exceptions to minimum
            "allowed_releases": ["staging"]
        },
        {
            "major": 8,
            "proton": False,
            "minor_bad": [0],
            "allowed_releases": ["staging"],
            "devel_allowed": 16,  # devel permissible at this point
        },
        {
            "major": 9,
            "proton": False,
            "minor_bad": [],
            "allowed_releases": ["devel", "staging"],
        },
    ]

    major_min, minor_min = required_wine_minimum
    if wine_release:
        major, minor, release_type = wine_release
        result = True, "None"  # Whether the release is allowed; error message
        for rule in rules:
            if major == rule["major"]:
                # Verify release is allowed
                if release_type not in rule["allowed_releases"]:
                    if minor >= rule.get("devel_allowed", float('inf')):
                        if release_type not in ["staging", "devel"]:
                            result = (
                                False,
                                (
                                    f"Wine release needs to be devel or staging. "
                                    f"Current release: {release_type}."
                                )
                            )
                            break
                    else:
                        result = (
                            False,
                            (
                                f"Wine release needs to be {rule['allowed_releases']}. "  # noqa: E501
                                f"Current release: {release_type}."
                            )
                        )
                        break
                # Verify version is allowed
                if minor in rule.get("minor_bad", []):
                    result = False, f"Wine version {major}.{minor} will not work."
                    break
                if major < major_min:
                    result = (
                        False,
                        (
                            f"Wine version {major}.{minor} is "
                            f"below minimum required ({major_min}.{minor_min}).")
                    )
                    break
                elif major == major_min and minor < minor_min:
                    if not rule["proton"]:
                        result = (
                            False,
                            (
                                f"Wine version {major}.{minor} is "
                                f"below minimum required ({major_min}.{minor_min}).")  # noqa: E501
                        )
                        break
        logging.debug(f"Result: {result}")
        return result
    else:
        return True, "Default to trusting user override"


def check_wine_version_and_branch(release_version, test_binary):
    if not os.path.exists(test_binary):
        reason = "Binary does not exist."
        return False, reason

    if not os.access(test_binary, os.X_OK):
        reason = "Binary is not executable."
        return False, reason

    wine_release, error_message = get_wine_release(test_binary)

    if wine_release is False and error_message is not None:
        return False, error_message

    result, message = check_wine_rules(wine_release, release_version)
    if not result:
        return result, message

    if wine_release[0] > 9:
        pass

    return True, "None"


def initializeWineBottle(app=None):
    msg.status("Initializing wine bottle…")
    wine_exe = str(utils.get_wine_exe_path().parent / 'wine64')
    logging.debug(f"{wine_exe=}")
    # Avoid wine-mono window
    orig_overrides = config.WINEDLLOVERRIDES
    config.WINEDLLOVERRIDES = f"{config.WINEDLLOVERRIDES};mscoree="
    logging.debug(f"Running: {wine_exe} wineboot --init")
    process = run_wine_proc(
        wine_exe,
        exe='wineboot',
        exe_args=['--init'],
        init=True
    )
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
    # NOTE: For some reason wait_pid results in the reg install failing.
    # wait_pid(process)
    process.wait()
    if process is None or process.returncode != 0:
        failed = "Failed to install reg file"
        logging.debug(f"{failed}. {process=}")
        msg.logos_error(f"{failed}: {reg_file}")
    elif process.returncode == 0:
        logging.info(f"{reg_file} installed.")
    # light_wineserver_wait()
    wineserver_wait()


def disable_winemenubuilder():
    reg_file = Path(config.WORKDIR) / 'disable-winemenubuilder.reg'
    reg_file.write_text(r'''REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winemenubuilder.exe"=""
''')
    wine_reg_install(reg_file)


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

    cmd = f"subprocess cmd: '{' '.join(command)}'"
    with open(config.wine_log, 'a') as wine_log:
        print(f"{config.get_timestamp()}: {cmd}", file=wine_log)
    logging.debug(cmd)
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
    # heavy_wineserver_wait()
    wineserver_wait()
    logging.debug(f"procs using {config.WINEPREFIX}:")
    for proc in utils.get_procs_using_file(config.WINEPREFIX):
        logging.debug(f"{proc=}")
    else:
        logging.debug('<None>')


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
        process = run_wine_proc(
            str(utils.get_wine_exe_path()),
            exe='reg',
            exe_args=exe_args
        )
        wait_pid(process)


def enforce_icu_data_files(app=None):
    repo = "FaithLife-Community/icu"
    json_data = network.get_latest_release_data(repo)
    icu_url = network.get_first_asset_url(json_data)
    icu_latest_version = network.get_tag_name(json_data).lstrip('v')

    if icu_url is None:
        logging.critical(f"Unable to set {config.name_app} release without URL.")  # noqa: E501
        return
    icu_filename = os.path.basename(icu_url).removesuffix(".tar.gz")
    # Append the version to the file name so it doesn't collide with previous versions
    icu_filename = f"{icu_filename}-{icu_latest_version}.tar.gz"
    network.logos_reuse_download(
        icu_url,
        icu_filename,
        config.MYDOWNLOADS,
        app=app
    )
    drive_c = f"{config.INSTALLDIR}/data/wine64_bottle/drive_c"
    utils.untar_file(f"{config.MYDOWNLOADS}/{icu_filename}", drive_c)

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
    if not mscoree64.exists():  #alpine
        mscoree64 = binary_obj.parents[1] / 'lib' / 'wine' / 'x86_64-windows' / 'mscoree.dll'  # noqa: E501
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
