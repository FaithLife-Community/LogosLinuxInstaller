'''
Install steps:
- Make choices
  - choose product
  - choose version
  - set install directory
  - choose release
  - choose wine executable
  - choose winetricks executable
  - choose whether to install fonts
  - choose whether to check system dependencies
  - set remaining config variables
- Do downloads & dependency installs
  - install system dependencies
  - download/install wine executable
  - download/install winetricks executable
  - download installer
- Do wine install
  - make install folder
  - ensure wine executable is defined and accessible
    - make symlinks if appimage
    - check wine --version
    - set wineserver exe variable
  - run wineboot
  - run winetricks
  - run MSI installer
'''

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

import config
import installer
import msg
import tui
import utils
import wine


def ensure_product_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    config.INSTALL_STEP += 1
    text = "Ensuring product choice…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.FLPRODUCT')
    logging.debug('- config.FLPRODUCTi')
    logging.debug('- config.VERBUM_PATH')

    if not config.FLPRODUCT:
        TITLE = "Choose Product"
        QUESTION_TEXT = "Choose which FaithLife product the script should install:"  # noqa: E501
        options = ["Logos", "Verbum", "Exit"]
        product_choice = tui.menu(options, TITLE, QUESTION_TEXT)
        logging.info(f"Product: {str(product_choice)}")
        if str(product_choice).startswith("Logos"):
            logging.info("Installing Logos Bible Software")
            config.FLPRODUCT = "Logos"
        elif str(product_choice).startswith("Verbum"):
            logging.info("Installing Verbum Bible Software")
            config.FLPRODUCT = "Verbum"
        elif str(product_choice).startswith("Exit"):
            msg.logos_error("Exiting installation.", "")
        else:
            msg.logos_error("Unknown product. Installation canceled!", "")

    if config.FLPRODUCT == 'Logos':
        config.FLPRODUCTi = 'logos4'
        config.VERBUM_PATH = "/"
    elif config.FLPRODUCT == 'Verbum':
        config.FLPRODUCTi = 'verbum'
        config.VERBUM_PATH = "/Verbum/"

    logging.debug(f"> {config.FLPRODUCT=}")
    logging.debug(f"> {config.FLPRODUCTi=}")
    logging.debug(f"> {config.VERBUM_PATH=}")


def ensure_version_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_product_choice(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring version choice…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.TARGETVERSION')

    if not config.TARGETVERSION:
        TITLE = "Choose Product Version"
        QUESTION_TEXT = f"Which version of {config.FLPRODUCT} should the script install?"  # noqa: E501
        options = ["10", "9", "Exit"]
        version_choice = tui.menu(options, TITLE, QUESTION_TEXT)
        logging.info(f"Target version: {version_choice}")
        if "10" in version_choice:
            config.TARGETVERSION = "10"
        elif "9" in version_choice:
            config.TARGETVERSION = "9"
        elif version_choice == "Exit.":
            msg.logos_error("Exiting installation.", "")
        else:
            msg.logos_error("Unknown version. Installation canceled!", "")
    logging.debug(f"> {config.TARGETVERSION=}")


def ensure_install_dirs(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_version_choice(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring installation directories…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.INSTALLDIR')
    logging.debug('- config.WINEPREFIX')
    logging.debug('- data/bin')
    logging.debug('- data/wine64_bottle')

    if config.INSTALLDIR is None:
        config.INSTALLDIR = f"{os.getenv('HOME')}/{config.FLPRODUCT}Bible{config.TARGETVERSION}"  # noqa: E501
    logging.debug(f"> {config.INSTALLDIR=}")
    if config.WINEPREFIX is None:
        config.WINEPREFIX = f"{config.INSTALLDIR}/data/wine64_bottle"
    logging.debug(f"> {config.WINEPREFIX=}")

    bin_dir = Path(f"{config.INSTALLDIR}/data/bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    logging.debug(f"> {bin_dir} exists: {bin_dir.is_dir()}")

    wine_dir = Path(f"{config.WINEPREFIX}")
    wine_dir.mkdir(parents=True, exist_ok=True)
    logging.debug(f"> {wine_dir} exists: {wine_dir.is_dir()}")


def ensure_release_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_install_dirs(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring release choice…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.LOGOS_RELEASE_VERSION')

    if not config.LOGOS_RELEASE_VERSION:
        TITLE = f"Choose {config.FLPRODUCT} {config.TARGETVERSION} Release"
        QUESTION_TEXT = f"Which version of {config.FLPRODUCT} {config.TARGETVERSION} do you want to install?"  # noqa: E501
        releases = utils.get_logos_releases()
        if releases is None:
            msg.logos_error("Failed to fetch LOGOS_RELEASE_VERSION.")
        releases.append("Exit")
        logos_release_version = tui.menu(releases, TITLE, QUESTION_TEXT)
        logging.info(f"Release version: {logos_release_version}")
        if logos_release_version == "Exit":
            msg.logos_error("Exiting installation.", "")
        elif logos_release_version:
            config.LOGOS_RELEASE_VERSION = logos_release_version
        else:
            msg.logos_error("Failed to fetch LOGOS_RELEASE_VERSION.")
    logging.debug(f"> {config.LOGOS_RELEASE_VERSION=}")


def ensure_wine_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_release_choice(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring wine executable choice…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.SELECTED_APPIMAGE_FILENAME')
    logging.debug('- config.WINE_EXE')
    logging.debug('- config.WINEBIN_CODE')

    if config.WINE_EXE is None:
        # Set relevant config based on up-to-date details from URL.
        utils.set_recommended_appimage_config()

        logging.info("Creating binary list.")
        TITLE = "Choose Wine Binary"
        QUESTION_TEXT = f"Which Wine AppImage or binary should the script use to install {config.FLPRODUCT} v{config.LOGOS_RELEASE_VERSION} in {config.INSTALLDIR}?"  # noqa: E501
        WINEBIN_OPTIONS = utils.get_wine_options(
            utils.find_appimage_files(),
            utils.find_wine_binary_files()
        )

        installation_choice = tui.menu(WINEBIN_OPTIONS, TITLE, QUESTION_TEXT)
        config.WINEBIN_CODE = installation_choice[0]
        config.WINE_EXE = installation_choice[1]
        if config.WINEBIN_CODE == "Exit":
            msg.logos_error("Exiting installation.", "")

    # Set WINEBIN_CODE and SELECTED_APPIMAGE_FILENAME.
    if config.WINE_EXE.lower().endswith('.appimage'):
        config.SELECTED_APPIMAGE_FILENAME = config.WINE_EXE
    if not config.WINEBIN_CODE:
        config.WINEBIN_CODE = utils.get_winebin_code_and_desc(config.WINE_EXE)[0]  # noqa: E501

    logging.debug(f"> {config.SELECTED_APPIMAGE_FILENAME=}")
    logging.debug(f"> {config.WINEBIN_CODE=}")
    logging.debug(f"> {config.WINE_EXE=}")


def ensure_winetricks_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_wine_choice(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring winetricks executable choice…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.WINETRICKSBIN')

    # Check if local winetricks version available; else, download it.
    if config.WINETRICKSBIN is None:
        msg.cli_msg("Preparing winetricks…")
        local_winetricks_path = shutil.which('winetricks')
        if local_winetricks_path is not None:
            # Check if local winetricks version is up-to-date; if so, offer to
            # use it or to download; else, download it.
            msg.cli_msg(f"Checking {local_winetricks_path} version…")
            cmd = ["winetricks", "--version"]
            local_winetricks_version = subprocess.check_output(cmd).split()[0]
            if str(local_winetricks_version) >= "20220411":
                if config.DIALOG == 'tk':
                    logging.info("Setting winetricks to the local binary…")
                    config.WINETRICKSBIN = local_winetricks_path
                else:
                    title = "Choose Winetricks"
                    question_text = "Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that FLPRODUCT requires on Linux."  # noqa: E501

                    options = [
                        "1: Use local winetricks.",
                        "2: Download winetricks from the Internet"
                    ]
                    winetricks_choice = tui.menu(options, title, question_text)

                    logging.debug(f"winetricks_choice: {winetricks_choice}")
                    if winetricks_choice.startswith("1"):
                        logging.info("Setting winetricks to the local binary…")
                        config.WINETRICKSBIN = local_winetricks_path
                    elif winetricks_choice.startswith("2"):
                        config.WINETRICKSBIN = f"{config.INSTALLDIR}/data/bin/winetricks"  # noqa: E501
                    else:
                        msg.logos_error("Installation canceled!")
            else:
                msg.cli_msg("The system's winetricks is too old. Winetricks will be downloaded from the Internet.")  # noqa: E501
                config.WINETRICKSBIN = f"{config.INSTALLDIR}/data/bin/winetricks"  # noqa: E501
        else:
            msg.cli_msg("Local winetricks not found. Winetricks will be downloaded from the Internet.")  # noqa: E501
            config.WINETRICKSBIN = f"{config.INSTALLDIR}/data/bin/winetricks"
    logging.debug(f"> {config.WINETRICKSBIN=}")


def ensure_install_fonts_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_winetricks_choice(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring install fonts choice…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.SKIP_FONTS')

    logging.debug(f"> {config.SKIP_FONTS=}")


def ensure_check_sys_deps_choice(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_install_fonts_choice(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring check system dependencies choice…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.SKIP_DEPENDENCIES')

    logging.debug(f"> {config.SKIP_DEPENDENCIES=}")


def ensure_installation_config(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_check_sys_deps_choice(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring installation config is set…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.LOGOS_ICON_URL')
    logging.debug('- config.LOGOS_ICON_FILENAME')
    logging.debug('- config.LOGOS_VERSION')
    logging.debug('- config.LOGOS64_MSI')
    logging.debug('- config.LOGOS64_URL')

    # Set icon variables.
    if config.LOGOS_ICON_URL is None:
        app_dir = Path(__file__).parent
        logos_icon_url = app_dir / 'img' / f"{config.FLPRODUCTi}-128-icon.png"
        config.LOGOS_ICON_URL = str(logos_icon_url)
    if config.LOGOS_ICON_FILENAME is None:
        config.LOGOS_ICON_FILENAME = logos_icon_url.name

    if not config.LOGOS64_URL:
        config.LOGOS64_URL = f"https://downloads.logoscdn.com/LBS{config.TARGETVERSION}{config.VERBUM_PATH}Installer/{config.LOGOS_RELEASE_VERSION}/{config.FLPRODUCT}-x64.msi"  # noqa: E501

    config.LOGOS_VERSION = config.LOGOS_RELEASE_VERSION
    config.LOGOS64_MSI = Path(config.LOGOS64_URL).name

    logging.debug(f"> {config.LOGOS_ICON_URL=}")
    logging.debug(f"> {config.LOGOS_ICON_FILENAME=}")
    logging.debug(f"> {config.LOGOS_VERSION=}")
    logging.debug(f"> {config.LOGOS64_MSI=}")
    logging.debug(f"> {config.LOGOS64_URL=}")


def ensure_sys_deps(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_installation_config(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring system dependencies are met…"
    m = get_message_str(text)
    msg.cli_msg(m)

    if not config.SKIP_DEPENDENCIES:
        utils.get_package_manager()
        utils.check_dependencies()
        logging.debug("> Done.")
    else:
        logging.debug("> Skipped.")


def ensure_wine_executables(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_sys_deps(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring wine executables are available…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- config.WINESERVER_EXE')
    logging.debug('- wine')
    logging.debug('- wine64')
    logging.debug('- wineserver')

    # Add INSTALLDIR/data/bin to PATH.
    os.environ['PATH'] = f"{config.INSTALLDIR}/data/bin:{os.getenv('PATH')}"

    # Ensure AppImage symlink.
    appimage_link = Path(f"{config.INSTALLDIR}/data/bin/{config.APPIMAGE_LINK_SELECTION_NAME}")  # noqa: E501
    if not os.access(config.WINE_EXE, os.X_OK):
        # if config.WINEBIN_CODE.startswith("Recommended"):
        #     appimage_filename = config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME  # noqa: E501
        #     utils.set_appimage_symlink()
        #     os.chmod(f"{config.APPDIR_BINDIR}/{appimage_filename}", 0o755)
        # elif config.WINEBIN_CODE.startswith("AppImage"):
        #     appimage_filename = config.SELECTED_APPIMAGE_FILENAME
        #     utils.set_appimage_symlink()
        #     os.chmod(f"{config.APPDIR_BINDIR}/{appimage_filename}", 0o755)
        if config.WINEBIN_CODE in ['AppImage', 'Recommended']:
            appimage_filename = Path(config.SELECTED_APPIMAGE_FILENAME).name
            if not config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME:
                utils.set_recommended_appimage_config()
            utils.get_recommended_appimage()
            utils.set_appimage_symlink()
            os.chmod(f"{config.INSTALLDIR}/data/bin/{appimage_filename}", 0o755)  # noqa: E501
        elif config.WINEBIN_CODE in ["System", "Proton", "PlayOnLinux", "Custom"]:  # noqa: E501
            appimage_filename = "none.AppImage"
        else:
            msg.logos_error("WINEBIN_CODE error. Installation canceled!")

        appimage_link.unlink(missing_ok=True)  # remove & replace
        appimage_link.symlink_to(f"./{appimage_filename}")  # noqa: E501

    # Ensure wine executables symlinks.
    for name in ["wine", "wine64", "wineserver"]:
        p = Path(f"{config.INSTALLDIR}/data/bin/{name}")
        p.unlink(missing_ok=True)
        p.symlink_to(f"./{config.APPIMAGE_LINK_SELECTION_NAME}")

    # Set WINESERVER_EXE.
    config.WINESERVER_EXE = f"{config.INSTALLDIR}/data/bin/wineserver"

    logging.debug(f"> {config.WINESERVER_EXE=}")
    logging.debug(f"> wine path: {shutil.which('wine')}")
    logging.debug(f"> wine64 path: {shutil.which('wine64')}")
    logging.debug(f"> wineserver path: {shutil.which('wineserver')}")


def ensure_winetricks_executable(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_wine_executables(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring winetricks executable is available…"
    m = get_message_str(text)
    msg.cli_msg(m)

    if not os.access(config.WINETRICKSBIN, os.X_OK):
        Path(config.WINETRICKSBIN).unlink(missing_ok=True)
        # The choice of System winetricks was made previously. Here we are only
        # concerned about whether or not the downloaded winetricks is usable.
        msg.cli_msg("Downloading winetricks from the Internet…")
        config.APPDIR_BINDIR = f"{config.INSTALLDIR}/data/bin"  # needed only for download_winetricks  # noqa: E501
        installer.download_winetricks()
        del config.APPDIR_BINDIR
    logging.debug(f"> {config.WINETRICKSBIN} is executable?: {os.access(config.WINETRICKSBIN, os.X_OK)}")  # noqa: E501


def ensure_product_installer(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_winetricks_executable(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring product installer is downloaded…"
    m = get_message_str(text)
    msg.cli_msg(m)

    # This VAR is used to verify the downloaded MSI is latest
    config.LOGOS_EXECUTABLE = f"{config.FLPRODUCT}_v{config.LOGOS_VERSION}-x64.msi"  # noqa: E501
    installer = Path(f"{config.INSTALLDIR}/data/{config.LOGOS_EXECUTABLE}")
    if not installer.is_file():
        # Getting {FLPRODUCT} Bible.
        msg.cli_msg(f"Ensuring {config.FLPRODUCT}Bible 64bits is available…")
        utils.logos_reuse_download(
            config.LOGOS64_URL,
            config.LOGOS_EXECUTABLE,
            f"{config.INSTALLDIR}/data/"
        )
    logging.debug(f"> {str(installer)} exists?: {installer.is_file()}")


def ensure_wineprefix_init(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_product_installer(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring wineprefix is initialized…"
    m = get_message_str(text)
    msg.cli_msg(m)

    init_file = Path(f"{config.WINEPREFIX}/system.reg")
    if not init_file.is_file():
        wine.initializeWineBottle()
    logging.debug(f"> {init_file} exists?: {init_file.is_file()}")


def ensure_winetricks_applied(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_wineprefix_init(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring winetricks & other settings are applied…"
    m = get_message_str(text)
    msg.cli_msg(m)
    logging.debug('- disable winemenubuilder')
    logging.debug('- settings renderer=gdi')
    logging.debug('- corefonts')
    logging.debug('- tahoma')
    logging.debug('- settings fontsmooth=rgb')
    logging.debug('- d3dcompiler_47')

    usr_reg = Path(f"{config.WINEPREFIX}/user.reg")
    sys_reg = Path(f"{config.WINEPREFIX}/system.reg")
    if not grep(r'"winemenubuilder.exe"=""', usr_reg):
        reg_file = os.path.join(config.WORKDIR, 'disable-winemenubuilder.reg')
        with open(reg_file, 'w') as f:
            f.write(r'''REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winemenubuilder.exe"=""
''')
        wine.wine_reg_install(reg_file)

    if not grep(r'"renderer"="gdi"', usr_reg):
        wine.winetricks_install("-q", "settings", "renderer=gdi")

    if not config.SKIP_FONTS and not grep(r'"Tahoma \(TrueType\)"="tahoma.ttf"', sys_reg):  # noqa: E501
        wine.installFonts()

    if not grep(r'"\*d3dcompiler_47"="native"', usr_reg):  # noqa: E501
        wine.installD3DCompiler()

    if not grep(r'"ProductName"="Microsoft Windows 10"', sys_reg):
        if not config.WINETRICKS_UNATTENDED:
            wine.winetricks_install("-q", "settings", "win10")
        else:
            wine.winetricks_install("settings", "win10")
    logging.debug("> Done.")


def ensure_product_installed(app=None):
    config.INSTALL_STEPS_COUNT += 1
    ensure_winetricks_applied(app=app)
    config.INSTALL_STEP += 1
    text = "Ensuring product is installed…"
    m = get_message_str(text)
    msg.cli_msg(m)

    if not utils.find_installed_product():
        wine.install_msi()
        config.LOGOS_EXE = utils.find_installed_product()
    logging.debug(f"> Product path: {config.LOGOS_EXE}")


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


def get_progress_pct(current, total):
    return round(current * 100 / total)


def get_progress_str(percent):
    length = 20
    part_done = round(percent * length / 100)
    part_left = length - part_done
    return f"Installer: [{'*' * part_done}{'-' * part_left}]"


def get_message_str(text):
    pct = get_progress_pct(config.INSTALL_STEP, config.INSTALL_STEPS_COUNT)
    return f"{get_progress_str(pct)} {text}"


def setup():
    # config.set_config_env(config.CONFIG_FILE)
    config.DIALOG = 'curses'
    config.FLPRODUCT = 'Logos'
    config.TARGETVERSION = '10'
    config.LOGOS_RELEASE_VERSION = '29.1.0.0022'
    config.WINE_EXE = '/home/nate/LogosBible10/data/bin/wine-devel_8.19-x86_64.AppImage'  # noqa: E501
    config.WINETRICKSBIN = '/usr/bin/winetricks'
    config.CONFIG_FILE = '/home/nate/.config/Logos_on_Linux/alt_installer_test.json'  # noqa: E501
