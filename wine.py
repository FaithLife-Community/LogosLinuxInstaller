import logging
import os
import psutil
import re
import signal
import subprocess
import time
from pathlib import Path

import config
from msg import cli_msg
from msg import logos_error
from msg import logos_progress
from utils import is_appimage
from utils import wait_process_using_dir


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

def wait_process_using_dir(directory):
    logging.info(f"* Starting wait_process_using_dir for {directory}…")

    # Get pids and wait for them to finish.
    pids = get_pids_using_file(directory)
    for pid in pids:    
        logging.info(f"wait_process_using_dir PID: {pid}")
        psutil.wait(pid)

    logging.info("* End of wait_process_using_dir.")

def wait_on(command):
    try:
        # Start the process in the background
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        cli_msg(f"Waiting on \"{' '.join(command)}\" to finish.", end='')
        while process.poll() is None:
            logos_progress()
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
            logging.info(f"Removing binary: {binary} because: {output2}")
    
    return binaries

def light_wineserver_wait():
    command = [f"{config.WINESERVER_EXE}", "-w"]
    wait_on(command)

def heavy_wineserver_wait():
    wait_process_using_dir(config.WINEPREFIX)
    wait_on([f"{config.WINESERVER_EXE}", "-w"])

def wineBinaryVersionCheck(TESTBINARY):
    # Does not check for Staging. Will not implement: expecting merging of commits in time.
    if config.TARGETVERSION == "10":
        WINE_MINIMUM = [7, 18]
    elif config.TARGETVERSION == "9":
        WINE_MINIMUM = [7, 0]
    else:
        raise ValueError("TARGETVERSION not set.")

    # Check if the binary is executable. If so, check if TESTBINARY's version is ≥ WINE_MINIMUM, or if it is Proton or a link to a Proton binary, else remove.
    if not os.path.exists(TESTBINARY):
        reason = "Binary does not exist."
        return False, reason

    if not os.access(TESTBINARY, os.X_OK):
        reason = "Binary is not executable."
        return False, reason

    cmd = [TESTBINARY, "--version"]
    version_string = subprocess.check_output(cmd, encoding='utf-8').strip()
    try:
        version, release = version_string.split()
    except ValueError: # neither "Devel" nor "Stable" release is noted in version output
        version = version_string
        release = get_wine_branch(TESTBINARY)

    ver_major = version.split('.')[0].lstrip('wine-') # remove 'wine-'
    ver_minor = version.split('.')[1]
    release = release.lstrip('(').rstrip(')').lower() # remove parentheses

    try:
        TESTWINEVERSION = [int(ver_major), int(ver_minor), release]
    except ValueError:
        return False, "Couldn't determine wine version."

    if TESTWINEVERSION[2] == 'stable':
        return False, "Can't use Stable release"
    elif TESTWINEVERSION[0] < 7:
        return False, "Version is < 7.0"
    elif TESTWINEVERSION[0] < 8:
        if "Proton" in TESTBINARY or ("Proton" in os.path.realpath(TESTBINARY) if os.path.islink(TESTBINARY) else False):
            if TESTWINEVERSION[1] == 0:
                return True, "None"
        elif release != 'staging':
            return False, "Needs to be Staging release"
        elif TESTWINEVERSION[1] < WINE_MINIMUM[1]:
            reason = f"{'.'.join(TESTWINEVERSION)} is below minimum required, {'.'.join(WINE_MINIMUM)}"
            return False, reason
    elif TESTWINEVERSION[0] < 9:
        if TESTWINEVERSION[1] < 1:
            return False, "Version is 8.0"
        elif TESTWINEVERSION[1] < 16:
            if release != 'staging':
                return False, "Version < 8.16 needs to be Staging release"

    return True, "None"

def initializeWineBottle(app):
    cli_msg(f"Initializing wine bottle...")
    if app is not None:
        app.install_q.put("Initializing wine bottle...")
        app.root.event_generate("<<UpdateInstallText>>")

    config.WINEDLLOVERRIDES = f"{config.WINEDLLOVERRIDES};mscoree=" # avoid wine-mono window
    run_wine_proc(config.WINE_EXE, exe='wineboot', exe_args=['--init'])
    config.WINEDLLOVERRIDES = ';'.join([o for o in config.WINEDLLOVERRIDES.split(';') if o != 'mscoree='])
    light_wineserver_wait()

def wine_reg_install(REG_FILE):
    cli_msg(f"Installing registry file: {REG_FILE}")
    env = get_wine_env()
    p = subprocess.run(
        [config.WINE_EXE, "regedit.exe", REG_FILE],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        cwd=config.WORKDIR,
    )
    if p.returncode == 0:
        logging.info(f"{REG_FILE} installed.")
    elif p.returncode != 0:
        logos_error(f"Failed to install reg file: {REG_FILE}")
    light_wineserver_wait()

def install_msi():
    cli_msg(f"Running MSI installer: {config.LOGOS_EXECUTABLE}.")
    # Execute the .MSI
    exe_args = ["/i", f"{config.APPDIR}/{config.LOGOS_EXECUTABLE}"]
    if config.PASSIVE is True:
        exe_args.append('/passive')
    logging.info(f"Running: {config.WINE_EXE} msiexec {' '.join(exe_args)}")
    run_wine_proc(config.WINE_EXE, exe="msiexec", exe_args=exe_args)

def run_wine_proc(winecmd, exe=None, exe_args=list()):
    env = get_wine_env()
    if config.WINECMD_ENCODING is None:
        # Get wine system's cmd.exe encoding for proper decoding to UTF8 later.
        codepages = get_registry_value('HKCU\\Software\\Wine\\Fonts', 'Codepages').split(',')
        config.WINECMD_ENCODING = codepages[-1]
    logging.debug(f"run_wine_proc: {winecmd} {exe} {' '.join(exe_args)}")

    command = [winecmd]
    if exe is not None:
        command.append(exe)
    if len(exe_args) > 0:
        command.extend(exe_args)

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        with process.stdout:
            for line in iter(process.stdout.readline, b''):
                if winecmd.endswith('winetricks'):
                    logging.debug(line.decode().rstrip())
                else:
                    try:
                        logging.info(line.decode().rstrip())
                    except UnicodeDecodeError:
                        logging.info(line.decode(config.WINECMD_ENCODING).rstrip())
        returncode = process.wait()

        if returncode != 0:
            logging.error(f"Error 1 running {winecmd} {exe}: {process.returncode}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error 2 running {winecmd} {exe}: {e}")

def run_winetricks():
    run_wine_proc(config.WINETRICKSBIN)
    run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])

def winetricks_install(*args):
    cmd = ['-v', *args]
    cli_msg(f"Running winetricks \"{args[-1]}\"")
    logging.info(f"running \"winetricks {' '.join(cmd)}\"")
    run_wine_proc(config.WINETRICKSBIN, exe_args=cmd)
    logging.info(f"\"winetricks {' '.join(cmd)}\" DONE!")
    heavy_wineserver_wait()

def installFonts():
    cli_msg("Configuring fonts...")
    fonts = ['corefonts', 'tahoma']
    if not config.SKIP_FONTS:
        for f in fonts:
            args = [f]
            if config.WINETRICKS_UNATTENDED:
                args.insert(0, '-q')
            winetricks_install(*args)

    winetricks_install('-q', 'settings', 'fontsmooth=rgb')

def installD3DCompiler():
    cmd = ['d3dcompiler_47']
    if config.WINETRICKS_UNATTENDED is None:
        cmd.insert(0, '-q')
    winetricks_install(*cmd)

def get_registry_value(reg_path, name):
    value = None
    env = get_wine_env()
    cmd = [config.WINE_EXE, 'reg', 'query', reg_path, '/v', name]
    stdout = subprocess.run(
        cmd, capture_output=True,
        text=True, encoding=config.WINECMD_ENCODING,
        env=env).stdout
    for line in stdout.splitlines():
        if line.strip().startswith(name):
            value = line.split()[-1].strip()
            break
    return value

def get_app_logging_state(app=None, init=False):
    state = 'DISABLED'
    current_value = get_registry_value('HKCU\\Software\\Logos4\\Logging', 'Enabled')
    if current_value == '0x1':
        state = 'ENABLED'
    if app is not None:
        app.logging_q.put(state)
        if init:
            app.root.event_generate(app.logging_init_event)
        else:
            app.root.event_generate(app.logging_event)
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
        logging.debug(f"app logging {current_state = }")
        if current_state == state_enabled:
            value = value_disabled
            state = state_disabled
        else:
            value = value_enabled
            state = state_enabled

    logging.info(f"Setting app logging to '{state}'.")
    exe_args = ['add', 'HKCU\\Software\\Logos4\\Logging', '/v', 'Enabled', '/t',
        'REG_DWORD', '/d', value, '/f'
    ]
    run_wine_proc(config.WINE_EXE, exe='reg', exe_args=exe_args)
    run_wine_proc(config.WINESERVER_EXE, exe_args=['-w'])
    config.LOGS = state
    if app is not None:
        app.logging_q.put(state)
        app.root.event_generate(app.logging_event)

def get_wine_branch(binary):
    logging.info(f"Determining wine branch of '{binary}'")
    binary_obj = Path(binary).expanduser().resolve()
    appimage, appimage_type = is_appimage(binary_obj)
    if appimage:
        if appimage_type == 1:
            logging.error(f"Can't handle AppImage type {str(appimage_type)} yet.")
        # Mount appimage to inspect files.
        p = subprocess.Popen([binary_obj, '--appimage-mount'], stdout=subprocess.PIPE, encoding='UTF8')
        while p.returncode is None:
            for line in p.stdout:
                if line.startswith('/tmp'):
                    tmp_dir = Path(line.rstrip())
                    for f in tmp_dir.glob('**/lib64/**/mscoree.dll'):
                        branch = get_mscoree_winebranch(f)
                        break
                p.send_signal(signal.SIGINT)
            p.poll()
        return branch
    logging.info(f"'{binary}' resolved to '{binary_obj}'")
    mscoree64 = binary_obj.parents[1] / 'lib64' / 'wine' / 'x86_64-windows' / 'mscoree.dll'
    return get_mscoree_winebranch(mscoree64)

def get_mscoree_winebranch(mscoree_file):
    try:
        with mscoree_file.open('rb') as f:
            for line in f:
                m = re.search(rb'wine-[a-z]+', line)
                if m is not None:
                    return m[0].decode().lstrip('wine-')
    except FileNotFoundError as e:
        logging.error(e)

def get_wine_env():
    wine_env = os.environ.copy()
    wine_env['WINE'] = config.WINE_EXE # used by winetricks
    wine_env['WINE_EXE'] = config.WINE_EXE
    wine_env['WINEDEBUG'] = config.WINEDEBUG
    wine_env['WINEDLLOVERRIDES'] = config.WINEDLLOVERRIDES
    wine_env['WINEPREFIX'] = config.WINEPREFIX
    if config.LOG_LEVEL > logging.INFO:
        wine_env['WINETRICKS_SUPER_QUIET'] = "1"

    # Config file takes precedence over the above variables.
    cfg = config.get_config_file_dict(config.CONFIG_FILE)
    if cfg is not None:
        for key, value in cfg.items():
            if value is None:
                continue # or value = ''?
            wine_env[key] = value

    return wine_env

def run_logos():
    run_wine_proc(config.WINE_EXE, exe=config.LOGOS_EXE)
    run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])

def run_indexing():
    for root, dirs, files in os.walk(os.path.join(config.WINEPREFIX, "drive_c")):
        for f in files:
            if f == "LogosIndexer.exe" and root.endswith("Logos/System"):
                logos_indexer_exe = os.path.join(root, f)
                break

    run_wine_proc(config.WINESERVER_EXE, exe_args=["-k"])
    run_wine_proc(config.WINE_EXE, exe=logos_indexer_exe)
    run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])
