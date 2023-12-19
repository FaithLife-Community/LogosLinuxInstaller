import fileinput
import logging
import os
import psutil
import subprocess
import sys
import tempfile
import time

import config
from msg import cli_msg
from msg import logos_error
from msg import logos_progress


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
    logging.info(f"* Starting wait_process_using_dir for {VERIFICATION_DIR}…")

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

        while process.poll() is None:
            logos_progress("Waiting.", f"Waiting on {command} to finish.")
            time.sleep(0.5)

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
    except ValueError: # "Stable" release isn't noted in version output
        version = version_string
        release = '(Stable)'

    ver_major = version.split('.')[0].replace('wine-', '') # remove 'wine-'
    ver_minor = version.split('.')[1]
    release = release.replace('(', '').replace(')', '') # remove parentheses

    try:
        TESTWINEVERSION = [int(ver_major), int(ver_minor), release]
    except ValueError:
        return False, "Couldn't determine wine version."

    if TESTWINEVERSION[2] == 'Stable':
        return False, "Can't use Stable release"
    elif TESTWINEVERSION[0] < 7:
        return False, "Version is < 7.0"
    elif TESTWINEVERSION[0] < 8:
        if "Proton" in TESTBINARY or ("Proton" in os.path.realpath(TESTBINARY) if os.path.islink(TESTBINARY) else False):
            if TESTWINEVERSION[1] == 0:
                return True, "None"
        elif release != 'Staging':
            return False, "Needs to be Staging release"
        elif TESTWINEVERSION[1] < WINE_MINIMUM[1]:
            reason = f"{'.'.join(TESTWINEVERSION)} is below minimum required, {'.'.join(WINE_MINIMUM)}"
            return False, reason
    elif TESTWINEVERSION[0] < 9:
        if TESTWINEVERSION[1] < 1:
            return False, "Version is 8.0"
        elif TESTWINEVERSION[1] < 16:
            if release != 'Staging':
                return False, "Version < 8.16 needs to be Staging release"

    return True, "None"

def initializeWineBottle():
    logging.debug("Starting initializeWineBottle()")
    cli_msg("Initializing wine...")
    #logos_continue_question(f"Now the script will create and configure the Wine Bottle at {WINEPREFIX}. You can cancel the installation of Mono. Do you wish to continue?", f"The installation was cancelled!", "")
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
    # Execute the .MSI
    logging.info(f"Running: {config.WINE_EXE} msiexec /i {config.APPDIR}/{config.LOGOS_EXECUTABLE}")
    run_wine_proc(config.WINE_EXE, exe="msiexec", exe_args=["/i", f"{config.APPDIR}/{config.LOGOS_EXECUTABLE}"])

def run_wine_proc(winecmd, exe=None, exe_args=None):
    env = get_wine_env()

    command = [winecmd]
    if exe is not None:
        command.append(exe)
    if exe_args is not None:
        command.extend(exe_args)

    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)

        if process.returncode != 0:
            logging.error(f"Error 1 running {winecmd} {exe}: {process.returncode}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error 2 running {winecmd} {exe}: {e}")

def run_control_panel():
    run_wine_proc(config.WINE_EXE, exe="control")
    run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])

def run_winetricks():
    run_wine_proc(config.WINETRICKSBIN)
    run_wine_proc(config.WINESERVER_EXE, exe_args=["-w"])

def winetricks_install(*args):
    env = get_wine_env()
    logging.info(f"winetricks {' '.join(args)}")
    if config.DIALOG in ["whiptail", "dialog", 'curses', 'tk']:
        run_wine_proc(config.WINETRICKSBIN, exe_args=args)
    elif config.DIALOG == "zenity":
        pipe_winetricks = tempfile.mktemp()
        os.mkfifo(pipe_winetricks)

        # zenity GUI feedback
        logos_progress("Winetricks " + " ".join(args), "Winetricks installing " + " ".join(args), input=open(pipe_winetricks))

        proc = subprocess.Popen([config.WINETRICKSBIN, *args], stdout=subprocess.PIPE, env=env)
        with open(pipe_winetricks, "w") as pipe:
            for line in proc.stdout:
                pipe.write(line)
                print(line.decode(), end="")

        WINETRICKS_STATUS = proc.wait()
        ZENITY_RETURN = proc.poll()

        os.remove(pipe_winetricks)

        # NOTE: sometimes the process finishes before the wait command, giving the error code 127
        if ZENITY_RETURN == 0 or ZENITY_RETURN == 127:
            if WINETRICKS_STATUS != 0:
                run_wine_proc(config.WINESERVER_EXE, exe_args=['-k'])
                logos_error("Winetricks Install ERROR: The installation was cancelled because of sub-job failure!\n * winetricks " + " ".join(args) + "\n  - WINETRICKS_STATUS: " + str(WINETRICKS_STATUS), "")
        else:
            run_wine_proc(config.WINESERVER_EXE, exe_args=['-k'])
            logos_error("The installation was cancelled!\n * ZENITY_RETURN: " + str(ZENITY_RETURN), "")
    elif config.DIALOG == "kdialog":
        no_diag_msg("kdialog not implemented.")
    else:
        no_diag_msg("No dialog tool found.")

    logging.info(f"winetricks {' '.join(args)} DONE!")

    heavy_wineserver_wait()

def winetricks_dll_install(*args):
    cli_msg(f"Installing '{args[-1]}' with winetricks.")
    env = get_wine_env()
    logging.info(f"winetricks {' '.join(args)}")
    #logos_continue_question("Now the script will install the DLL " + " ".join(args) + ". This may take a while. There will not be any GUI feedback for this. Continue?", "The installation was cancelled!", "")
    run_wine_proc(config.WINETRICKSBIN, exe_args=args)
    logging.info(f"winetricks {' '.join(args)} DONE!")
    heavy_wineserver_wait()

def installFonts():
    fonts = ['corefonts', 'tahoma']
    if not config.SKIP_FONTS:
        for f in fonts:
            args = [f]
            if config.WINETRICKS_UNATTENDED:
                args.insert(0, '-q')
            winetricks_install(*args)

    winetricks_install('-q', 'settings', 'fontsmooth=rgb')

def installD3DCompiler():
    if config.WINETRICKS_UNATTENDED is None:
        winetricks_dll_install('-q', 'd3dcompiler_47')
    else:
        winetricks_dll_install('d3dcompiler_47')

def switch_logging(action=None):
    if action == 'disable':
        value = '0001'
        state = 'DISABLED'
    elif action == 'enable':
        value = '0000'
        state = 'ENABLED'
    else:
        return

    exe_args = ['add', 'HKCU\\Software\\Logos4\\Logging', '/v', 'Enabled', '/t',
        'REG_DWORD', '/d', value, '/f'
    ]
    run_wine_proc(config.WINE_EXE, exe='reg', exe_args=exe_args)
    run_wine_proc(config.WINESERVER_EXE, exe_args=['-w'])
    config.LOGS = state

def disable_logging():
    switch_logging(action='disable')

def enable_logging():
    switch_logging(action='enable')

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
    cfg = config.get_config_env(config.CONFIG_FILE)
    if cfg is not None:
        for key, value in cfg.items():
            if value is None:
                continue # or value = ''?
            wine_env[key] = value

    return wine_env
