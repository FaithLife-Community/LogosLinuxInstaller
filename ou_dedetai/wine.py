from dataclasses import dataclass
import logging
import os
import re
import shutil
import signal
import subprocess
from pathlib import Path
import tempfile
from typing import Optional

from ou_dedetai.app import App

from . import network
from . import system
from . import utils

def check_wineserver(app: App):
    # FIXME: if the wine version changes, we may need to restart the wineserver
    # (or at least kill it). Gotten into several states in dev where this happend
    # Normally when an msi install failed
    try:
        process = run_wine_proc(app.conf.wineserver_binary, app)
        if not process:
            logging.debug("Failed to spawn wineserver to check it")
            return False
        process.wait()
        return process.returncode == 0
    except Exception:
        return False


def wineserver_kill(app: App):
    if check_wineserver(app):
        process = run_wine_proc(app.conf.wineserver_binary, app, exe_args=["-k"])
        if not process:
            logging.debug("Failed to spawn wineserver to kill it")
            return False
        process.wait()


def wineserver_wait(app: App):
    if check_wineserver(app):
        process = run_wine_proc(app.conf.wineserver_binary, app, exe_args=["-w"])
        if not process:
            logging.debug("Failed to spawn wineserver to wait for it")
            return False
        process.wait()


@dataclass
class WineRelease:
    major: int
    minor: int
    release: Optional[str]


# FIXME: consider raising exceptions on error
def get_wine_release(binary: str) -> tuple[Optional[WineRelease], str]:
    cmd = [binary, "--version"]
    try:
        version_string = subprocess.check_output(cmd, encoding='utf-8').strip()
        logging.debug(f"Version string: {str(version_string)}")
        release: Optional[str]
        try:
            version, release = version_string.split()
        except ValueError:
            # Neither "Devel" nor "Stable" release is noted in version output
            version = version_string
            release = get_wine_branch(binary)

        logging.debug(f"Wine branch of {binary}: {release}")

        if release is not None:
            ver_major = int(version.split('.')[0].lstrip('wine-'))  # remove 'wine-'
            ver_minor = int(version.split('.')[1])
            release = release.lstrip('(').rstrip(')').lower()  # remove parens
        else:
            ver_major = 0
            ver_minor = 0

        wine_release = WineRelease(ver_major, ver_minor, release)
        logging.debug(f"Wine release of {binary}: {str(wine_release)}")

        if ver_major == 0:
            return None, "Couldn't determine wine version."
        else:
            return wine_release, "yes"

    except subprocess.CalledProcessError as e:
        return None, f"Error running command: {e}"

    except ValueError as e:
        return None, f"Error parsing version: {e}"

    except Exception as e:
        return None, f"Error: {e}"


@dataclass
class WineRule:
    major: int
    proton: bool
    minor_bad: list[int]
    allowed_releases: list[str]
    devel_allowed: Optional[int] = None


def check_wine_rules(
    wine_release: Optional[WineRelease],
    release_version: Optional[str],
    faithlife_product_version: str
):
    # Does not check for Staging. Will not implement: expecting merging of
    # commits in time.
    logging.debug(f"Checking {wine_release} for {release_version}.")
    if faithlife_product_version == "10":
        if release_version is not None and utils.check_logos_release_version(release_version, 30, 1): #noqa: E501
            required_wine_minimum = [7, 18]
        else:
            required_wine_minimum = [9, 10]
    elif faithlife_product_version == "9":
        required_wine_minimum = [7, 0]
    else:
        raise ValueError(f"Invalid target version, expecting 9 or 10 but got: {faithlife_product_version} ({type(faithlife_product_version)})")  # noqa: E501

    rules: list[WineRule] = [
        # Proton release tend to use the x.0 release, but can include changes found in devel/staging  # noqa: E501
        # exceptions to minimum
        WineRule(major=7, proton=True, minor_bad=[], allowed_releases=["staging"]),
        # devel permissible at this point
        WineRule(major=8, proton=False, minor_bad=[0], allowed_releases=["staging"], devel_allowed=16), #noqa: E501
        WineRule(major=9, proton=False, minor_bad=[], allowed_releases=["devel", "staging"]) #noqa: E501
    ]

    major_min, minor_min = required_wine_minimum
    if wine_release:
        major = wine_release.major
        minor = wine_release.minor
        release_type = wine_release.release
        result = True, "None"  # Whether the release is allowed; error message
        for rule in rules:
            if major == rule.major:
                # Verify release is allowed
                if release_type not in rule.allowed_releases:
                    if minor >= (rule.devel_allowed or float('inf')):
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
                                f"Wine release needs to be {rule.allowed_releases}. "  # noqa: E501
                                f"Current release: {release_type}."
                            )
                        )
                        break
                # Verify version is allowed
                if minor in rule.minor_bad:
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
                    if not rule.proton:
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


def check_wine_version_and_branch(release_version: Optional[str], test_binary,
                                  faithlife_product_version):
    if not os.path.exists(test_binary):
        reason = "Binary does not exist."
        return False, reason

    if not os.access(test_binary, os.X_OK):
        reason = "Binary is not executable."
        return False, reason

    wine_release, error_message = get_wine_release(test_binary)

    if wine_release is None:
        return False, error_message

    result, message = check_wine_rules(
        wine_release,
        release_version,
        faithlife_product_version
    )
    if not result:
        return result, message

    if wine_release.major > 9:
        pass

    return True, "None"


def initializeWineBottle(wine64_binary: str, app: App) -> Optional[subprocess.Popen[bytes]]: #noqa: E501
    app.status("Initializing wine bottle…")
    logging.debug(f"{wine64_binary=}")
    # Avoid wine-mono window
    wine_dll_override="mscoree="
    logging.debug(f"Running: {wine64_binary} wineboot --init")
    process = run_wine_proc(
        wine64_binary,
        app=app,
        exe='wineboot',
        exe_args=['--init'],
        init=True,
        additional_wine_dll_overrides=wine_dll_override
    )
    return process


def wine_reg_install(app: App, reg_file, wine64_binary):
    reg_file = str(reg_file)
    app.status(f"Installing registry file: {reg_file}")
    process = run_wine_proc(
        wine64_binary,
        app=app,
        exe="regedit.exe",
        exe_args=[reg_file]
    )
    # NOTE: For some reason waiting on this processes results in the reg install failing
    if process is None:
        app.exit("Failed to spawn command to install reg file")
    process.wait()
    if process is None or process.returncode != 0:
        failed = "Failed to install reg file"
        logging.debug(f"{failed}. {process=}")
        app.exit(f"{failed}: {reg_file}")
    elif process.returncode == 0:
        logging.info(f"{reg_file} installed.")
    wineserver_wait(app)


def disable_winemenubuilder(app: App, wine64_binary: str):
    workdir = tempfile.mkdtemp()
    reg_file = Path(workdir) / 'disable-winemenubuilder.reg'
    reg_file.write_text(r'''REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winemenubuilder.exe"=""
''')
    wine_reg_install(app, reg_file, wine64_binary)
    shutil.rmtree(workdir)


def install_msi(app: App):
    app.status(f"Running MSI installer: {app.conf.faithlife_installer_name}.")
    # Execute the .MSI
    wine_exe = app.conf.wine64_binary
    exe_args = ["/i", f"{app.conf.install_dir}/data/{app.conf.faithlife_installer_name}"] #noqa: E501
    if app.conf._overrides.faithlife_install_passive is True:
        exe_args.append('/passive')
    logging.info(f"Running: {wine_exe} msiexec {' '.join(exe_args)}")
    process = run_wine_proc(wine_exe, app, exe="msiexec", exe_args=exe_args)
    return process


def get_winecmd_encoding(app: App) -> Optional[str]:
    # Get wine system's cmd.exe encoding for proper decoding to UTF8 later.
    logging.debug("Getting wine system's cmd.exe encoding.")
    registry_value = get_registry_value(
        'HKCU\\Software\\Wine\\Fonts',
        'Codepages',
        app
    )
    if registry_value is not None:
        codepages: str = registry_value.split(',')
        return codepages[-1]
    else:
        m = "wine.wine_proc: wine.get_registry_value returned None."
        logging.error(m)
        return None


def run_wine_proc(
    winecmd,
    app: App,
    exe=None,
    exe_args=list(),
    init=False,
    additional_wine_dll_overrides: Optional[str] = None
) -> Optional[subprocess.Popen[bytes]]:
    logging.debug("Getting wine environment.")
    env = get_wine_env(app, additional_wine_dll_overrides)
    if isinstance(winecmd, Path):
        winecmd = str(winecmd)
    logging.debug(f"run_wine_proc: {winecmd}; {exe=}; {exe_args=}")

    command = [winecmd]
    if exe is not None:
        command.append(exe)
    if exe_args:
        command.extend(exe_args)

    cmd = f"subprocess cmd: '{' '.join(command)}'"
    logging.debug(cmd)
    try:
        with open(app.conf.app_wine_log_path, 'a') as wine_log:
            print(f"{utils.get_timestamp()}: {cmd}", file=wine_log)
            process = system.popen_command(
                command,
                stdout=wine_log,
                stderr=wine_log,
                env=env,
                start_new_session=True
            )
            if process is not None:
                if process.poll() is None and process.stdout is not None:
                    with process.stdout:
                        for line in iter(process.stdout.readline, b''):
                            if winecmd.endswith('winetricks'):
                                logging.debug(line.decode('cp437').rstrip())
                            else:
                                try:
                                    logging.info(line.decode().rstrip())
                                except UnicodeDecodeError:
                                    if not init and app.conf.wine_output_encoding is not None: # noqa: E501
                                        logging.info(line.decode(app.conf.wine_output_encoding).rstrip())  # noqa: E501
                                    else:
                                        logging.error("wine.run_wine_proc: Error while decoding: wine output encoding could not be found.")  # noqa: E501
                return process
            else:
                return None

    except subprocess.CalledProcessError as e:
        logging.error(f"Exception running '{' '.join(command)}': {e}")

    return process


def run_winetricks(app: App, *args):
    cmd = [*args]
    if "-q" not in args and app.conf.winetricks_binary:
        cmd.insert(0, "-q")
    logging.info(f"running \"winetricks {' '.join(cmd)}\"")
    process = run_wine_proc(app.conf.winetricks_binary, app, exe_args=cmd)
    if process is None:
        app.exit("Failed to spawn winetricks")
    process.wait()
    logging.info(f"\"winetricks {' '.join(cmd)}\" DONE!")
    wineserver_wait(app)
    logging.debug(f"procs using {app.conf.wine_prefix}:")
    for proc in utils.get_procs_using_file(app.conf.wine_prefix):
        logging.debug(f"{proc=}")
    else:
        logging.debug('<None>')


def install_d3d_compiler(app: App):
    cmd = ['d3dcompiler_47']
    run_winetricks(app, *cmd)


def install_fonts(app: App):
    fonts = ['corefonts', 'tahoma']
    if not app.conf.skip_install_fonts:
        for i, f in enumerate(fonts):
            app.status(f"Configuring font: {f}…", i / len(fonts)) # noqa: E501
            args = [f]
            run_winetricks(app, *args)


def install_font_smoothing(app: App):
    logging.info("Setting font smoothing…")
    args = ['settings', 'fontsmooth=rgb']
    run_winetricks(app, *args)


def set_renderer(app: App, renderer: str):
    run_winetricks(app, "-q", "settings", f"renderer={renderer}")


def set_win_version(app: App, exe: str, windows_version: str):
    if exe == "logos":
        # This operation is equivilent to f"winetricks -q settings {windows_version}"
        # but faster
        process = run_wine_proc(
            app.conf.wine_binary,
            app,
            exe_args=('winecfg', '/v', windows_version)
        )
        if process:
            process.wait()

    elif exe == "indexer":
        reg = f"HKCU\\Software\\Wine\\AppDefaults\\{app.conf.faithlife_product}Indexer.exe"  # noqa: E501
        exe_args = [
            'add',
            reg,
            "/v", "Version",
            "/t", "REG_SZ",
            "/d", f"{windows_version}", "/f",
            ]
        process = run_wine_proc(
            app.conf.wine_binary,
            app,
            exe='reg',
            exe_args=exe_args
        )
        if process is None:
            app.exit("Failed to spawn command to set windows version for indexer")
        process.wait()


# FIXME: Consider when to re-run this if it changes.
# Perhaps we should have a "apply installation updates"
# or similar mechanism to ensure all of our latest methods are installed
# including but not limited to: system packages, winetricks options,
# icu files, fonts, registry edits, etc.
#
# Seems like we want to have a more holistic mechanism for ensuring
# all users use the latest and greatest.
# Sort of like an update, but for wine and all of the bits underneath "Logos" itself
def enforce_icu_data_files(app: App):
    app.status("Downloading ICU files…")
    icu_url = app.conf.icu_latest_version_url
    icu_latest_version = app.conf.icu_latest_version

    icu_filename = os.path.basename(icu_url).removesuffix(".tar.gz")
    # Append the version to the file name so it doesn't collide with previous versions
    icu_filename = f"{icu_filename}-{icu_latest_version}.tar.gz"
    network.logos_reuse_download(
        icu_url,
        icu_filename,
        app.conf.download_dir,
        app=app
    )

    app.status("Copying ICU files…")

    drive_c = f"{app.conf.wine_prefix}/drive_c"
    utils.untar_file(f"{app.conf.download_dir}/{icu_filename}", drive_c)

    # Ensure the target directory exists
    icu_win_dir = f"{drive_c}/icu-win/windows"
    if not os.path.exists(icu_win_dir):
        os.makedirs(icu_win_dir)

    shutil.copytree(icu_win_dir, f"{drive_c}/windows", dirs_exist_ok=True)
    app.status("ICU files copied.", 100)



def get_registry_value(reg_path, name, app: App):
    logging.debug(f"Get value for: {reg_path=}; {name=}")
    # FIXME: consider breaking run_wine_proc into a helper function before decoding is attempted # noqa: E501
    # NOTE: Can't use run_wine_proc here because of infinite recursion while
    # trying to determine wine_output_encoding.
    value = None
    env = get_wine_env(app)

    cmd = [
        app.conf.wine64_binary,
        'reg', 'query', reg_path, '/v', name,
    ]
    err_msg = f"Failed to get registry value: {reg_path}\\{name}"
    encoding = app.conf._wine_output_encoding
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
    if result is not None and result.stdout is not None:
        for line in result.stdout.splitlines():
            if line.strip().startswith(name):
                value = line.split()[-1].strip()
                logging.debug(f"Registry value: {value}")
                break
    else:
        logging.critical(err_msg)
    return value


def get_mscoree_winebranch(mscoree_file: Path) -> Optional[str]:
    try:
        with mscoree_file.open('rb') as f:
            for line in f:
                m = re.search(rb'wine-[a-z]+', line)
                if m is not None:
                    return m[0].decode().lstrip('wine-')
    except FileNotFoundError as e:
        logging.error(e)
    return None


def get_wine_branch(binary: str) -> Optional[str]:
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
        while p.returncode is None and p.stdout is not None:
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


def get_wine_env(app: App, additional_wine_dll_overrides: Optional[str]=None):
    wine_env = os.environ.copy()
    winepath = Path(app.conf.wine_binary)
    if winepath.name != 'wine64':  # AppImage
        # Winetricks commands can fail if 'wine64' is not explicitly defined.
        # https://github.com/Winetricks/winetricks/issues/2084#issuecomment-1639259359
        winepath = Path(app.conf.wine64_binary)
    wine_env_defaults = {
        'WINE': str(winepath),
        'WINEDEBUG': app.conf.wine_debug,
        'WINEDLLOVERRIDES': app.conf.wine_dll_overrides,
        'WINELOADER': str(winepath),
        'WINEPREFIX': app.conf.wine_prefix,
        'WINESERVER': app.conf.wineserver_binary,
        # The following seems to cause some winetricks commands to fail; e.g.
        # 'winetricks settings win10' exits with ec = 1 b/c it fails to find
        # %ProgramFiles%, %AppData%, etc.
        # 'WINETRICKS_SUPER_QUIET': '',
    }
    for k, v in wine_env_defaults.items():
        wine_env[k] = v

    if additional_wine_dll_overrides is not None:
        wine_env["WINEDLLOVERRIDES"] += ";" + additional_wine_dll_overrides # noqa: E501

    updated_env = {k: wine_env.get(k) for k in wine_env_defaults.keys()}
    logging.debug(f"Wine env: {updated_env}")
    return wine_env
