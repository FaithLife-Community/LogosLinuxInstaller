import fileinput
import logging
import os
import subprocess
import sys
import tempfile
import time

import config
from msg import cli_msg
from msg import logos_error
from msg import logos_progress


def wait_process_using_dir(directory):
    VERIFICATION_DIR = directory
    VERIFICATION_TIME = 7
    VERIFICATION_NUM = 3

    logging.info(f"* Starting wait_process_using_dir for {VERIFICATION_DIR}…")
    i = 0
    while True:
        i += 1
        logging.info(f"wait_process_using_dir: loop with i={i}")

        cli_msg(f"wait_process_using_dir: sleep {VERIFICATION_TIME}")
        time.sleep(VERIFICATION_TIME)

        try:
            FIRST_PID = subprocess.check_output(["lsof", "-t", VERIFICATION_DIR]).decode().split("\n")[0]
        except subprocess.CalledProcessError:
            FIRST_PID = ""

        logging.info(f"wait_process_using_dir FIRST_PID: {FIRST_PID}")
        if FIRST_PID:
            i = 0
            logging.info(f"wait_process_using_dir: tail --pid={FIRST_PID} -f /dev/null")
            subprocess.run(["tail", "--pid", FIRST_PID, "-f", "/dev/null"])
            continue

        if i >= VERIFICATION_NUM:
            break

    logging.info("* End of wait_process_using_dir.")

def wait_on(command):
    try:
        # Start the process in the background
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        sys.stdout.write(f"Waiting on '{' '.join(command)}' to finish.")
        while process.poll() is None:
            logos_progress("Waiting.", f"Waiting on {command} to finish.")
        print() # FIXME: a workaround until spinner output is fixed

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
    # FIXME: Does the following wineboot only work if there's a system installation of wine?
    #   I don't see the script creating LogosBible10/data/bin/wineboot...
    run_wine_proc('wineboot')
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
    env = get_wine_env()
    # Execute the .MSI
    logging.info(f"Running: {config.WINE_EXE} msiexec /i {config.APPDIR}/{config.LOGOS_EXECUTABLE}")
    subprocess.run([config.WINE_EXE, "msiexec", "/i", f"{config.APPDIR}/{config.LOGOS_EXECUTABLE}"], env=env)

def run_wine_proc(winecmd, exe=None, flags=None):
    env = get_wine_env()

    command = [winecmd]
    if exe is not None:
        command.append(exe)
    if flags is not None:
        command.extend(flags)

    try:
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)

        if process.returncode != 0:
            logging.error(f"Error 1 running {winecmd} {exe}: {process.returncode}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Error 2 running {winecmd} {exe}: {e}")

def run_control_panel():
    run_wine_proc(config.WINE_EXE, exe="control")
    run_wine_proc(config.WINESERVER_EXE, flags=["-w"])

def run_winetricks():
    run_wine_proc(config.WINETRICKSBIN, exe="control") # FIXME: "control" seems like an accident here...
    run_wine_proc(config.WINESERVER_EXE, flags=["-w"])

def winetricks_install(*args):
    cli_msg(f"Installing '{args[-1]}' with winetricks.")
    env = get_wine_env()
    cmd = [config.WINETRICKSBIN, '-v', *args]
    # if config.LOG_LEVEL < logging.INFO:
    #     # "winetricks -v" just activates "set -x", which is more like DEBUG than
    #     #   VERBOSE/INFO. So only adding '-v' if logging is set to DEBUG.
    #     cmd.insert(1, '-v')
    logging.info(f"winetricks {' '.join(args)}")
    if config.DIALOG in ["whiptail", "dialog", 'curses', 'tk']:
        # Ref: https://stackoverflow.com/a/21978778
        p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        with p.stdout:
            for oline in iter(p.stdout.readline, b''):
                logging.info(oline.decode().rstrip())
        returncode = p.wait()
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
                subprocess.call([config.WINESERVER_EXE, "-k"], env=env)
                logos_error("Winetricks Install ERROR: The installation was cancelled because of sub-job failure!\n * winetricks " + " ".join(args) + "\n  - WINETRICKS_STATUS: " + str(WINETRICKS_STATUS), "")
        else:
            subprocess.call([config.WINESERVER_EXE, "-k"], env=env)
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
    cmd = [config.WINETRICKSBIN, '-v', *args]
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with p.stdout:
        for oline in iter(p.stdout.readline, b''):
            logging.info(oline.decode().rstrip())
    returncode = p.wait()
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

def disable_logging():
    env = get_wine_env()
    cmd = [
        config.WINE_EXE, 'reg', 'add', 'HKCU\\Software\\Logos4\\Logging',
        '/v', 'Enabled', '/t', 'REG_DWORD', '/d', '0001', '/f'
    ]
    subprocess.run(cmd, env=env)
    subprocess.run([wineserver_exe, '-w'])

    for line in fileinput.input(config.CONFIG_FILE, inplace=True):
        print(line.replace('LOGS="ENABLED"', 'LOGS="DISABLED"'), end='')

def enable_logging():
    env = get_wine_env()
    cmd = [
        config.WINE_EXE, 'reg', 'add', 'HKCU\\Software\\Logos4\\Logging',
        '/v', 'Disabled', '/t', 'REG_DWORD', '/d', '0000', '/f'
    ]
    subprocess.run(cmd, env=env)
    subprocess.run([wineserver_exe, '-w'])

    for line in fileinput.input(config.CONFIG_FILE, inplace=True):
        print(line.replace('LOGS="DISABLED"', 'LOGS="ENABLED"'), end='')

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
