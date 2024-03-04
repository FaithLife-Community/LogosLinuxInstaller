import curses
import glob
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

import config
import tui
import msg
import utils
import wine


def choose_product():
    BACKTITLE = "Choose Product Menu"
    TITLE = "Choose Product"
    QUESTION_TEXT = "Choose which FaithLife product the script should install:"
    if config.FLPRODUCT is None:
        options = ["Logos", "Verbum", "Exit"]
        productChoice = tui.menu(options, TITLE, QUESTION_TEXT)
    else:
        productChoice = config.FLPRODUCT

    logging.info(f"Product: {str(productChoice)}")
    if str(productChoice).startswith("Logos"):
        logging.info("Installing Logos Bible Software")
        config.FLPRODUCT = "Logos"
        config.FLPRODUCTi = "logos4"  # This is the variable referencing the icon path name in the repo.
        config.VERBUM_PATH = "/"
    elif str(productChoice).startswith("Verbum"):
        logging.info("Installing Verbum Bible Software")
        config.FLPRODUCT = "Verbum"
        config.FLPRODUCTi = "verbum"  # This is the variable referencing the icon path name in the repo.
        config.VERBUM_PATH = "/Verbum/"
    elif str(productChoice).startswith("Exit"):
        msg.logos_error("Exiting installation.", "")
    else:
        msg.logos_error("Unknown product. Installation canceled!", "")

    # Set icon variables.
    if config.LOGOS_ICON_URL is None:
        app_dir = Path(__file__).parent
        config.LOGOS_ICON_URL = app_dir / 'img' / f"{config.FLPRODUCTi}-128-icon.png"
    if config.LOGOS_ICON_FILENAME is None:
        config.LOGOS_ICON_FILENAME = os.path.basename(config.LOGOS_ICON_URL)


def get_logos_release_version():
    TITLE = f"Choose {config.FLPRODUCT} {config.TARGETVERSION} Release"
    QUESTION_TEXT = f"Which version of {config.FLPRODUCT} {config.TARGETVERSION} do you want to install?"
    if config.LOGOS_VERSION is None:
        releases = utils.get_logos_releases()
        if releases is None:
            msg.logos_error("Failed to fetch LOGOS_RELEASE_VERSION.")
        releases.append("Exit")
        logos_release_version = tui.menu(releases, TITLE, QUESTION_TEXT)
    else:
        logos_release_version = config.LOGOS_VERSION

    logging.info(f"Release version: {logos_release_version}")
    if logos_release_version == "Exit":
        msg.logos_error("Exiting installation.", "")
    elif logos_release_version is not None:
        config.LOGOS_RELEASE_VERSION = logos_release_version
    else:
        msg.logos_error("Failed to fetch LOGOS_RELEASE_VERSION.")


def choose_version():
    BACKTITLE = "Choose Version Menu"
    TITLE = "Choose Product Version"
    QUESTION_TEXT = f"Which version of {config.FLPRODUCT} should the script install?"
    version_choice = config.TARGETVERSION
    if version_choice is None or version_choice == "":
        options = ["10", "9", "Exit"]
        version_choice = tui.menu(options, TITLE, QUESTION_TEXT)
    logging.info(f"Target version: {config.TARGETVERSION}")

    if "10" in version_choice:
        config.TARGETVERSION = "10"
    elif "9" in version_choice:
        config.TARGETVERSION = "9"
    elif version_choice == "Exit.":
        msg.logos_error("Exiting installation.", "")
    else:
        msg.logos_error("Unknown version. Installation canceled!", "")
    utils.check_dependencies()


def logos_setup():
    if config.LOGOS64_URL is None or config.LOGOS64_URL == "":
        config.LOGOS64_URL = f"https://downloads.logoscdn.com/LBS{config.TARGETVERSION}{config.VERBUM_PATH}Installer/{config.LOGOS_RELEASE_VERSION}/{config.FLPRODUCT}-x64.msi"

    if config.FLPRODUCT == "Logos":
        config.LOGOS_VERSION = config.LOGOS64_URL.split('/')[5]
    elif config.FLPRODUCT == "Verbum":
        config.LOGOS_VERSION = config.LOGOS64_URL.split('/')[6]
    else:
        # This check is for someone who runs an install from a config file.
        msg.logos_error("FLPRODUCT not set in config. Please update your config to specify either 'Logos' or 'Verbum'.",
                        "")

    config.LOGOS64_MSI = os.path.basename(config.LOGOS64_URL)

    if config.INSTALLDIR is None:
        config.INSTALLDIR = f"{os.getenv('HOME')}/{config.FLPRODUCT}Bible{config.TARGETVERSION}"
    if config.APPDIR is None:
        config.APPDIR = f"{config.INSTALLDIR}/data"
    if config.APPDIR_BINDIR is None:
        config.APPDIR_BINDIR = f"{config.APPDIR}/bin"
    variables = {
        'config.FLPRODUCT': config.FLPRODUCT,
        'config.FLPRODUCTi': config.FLPRODUCTi,
        'config.LOGOS_VERSION': config.LOGOS_VERSION,
        'config.INSTALLDIR': config.INSTALLDIR,
        'config.APPDIR': config.APPDIR,
        'config.APPDIR_BINDIR': config.APPDIR_BINDIR,
    }
    for k, v in variables.items():
        logging.debug(f"{k}: {v}")


def choose_install_method():
    if config.WINEPREFIX is None:
        config.WINEPREFIX = os.path.join(config.APPDIR, "wine64_bottle")

    if config.WINE_EXE is None:
        logging.info("Creating binary list.")
        WINEBIN_OPTIONS = utils.get_wine_options(utils.find_appimage_files(), utils.find_wine_binary_files())

        BACKTITLE = "Choose Wine Binary Menu"
        TITLE = "Choose Wine Binary"
        QUESTION_TEXT = f"Which Wine AppImage or binary should the script use to install {config.FLPRODUCT} v{config.LOGOS_VERSION} in {config.INSTALLDIR}?"

        installationChoice = tui.menu(WINEBIN_OPTIONS, TITLE, QUESTION_TEXT)
        config.WINEBIN_CODE = installationChoice[0]
        config.WINE_EXE = installationChoice[1]
        if config.WINEBIN_CODE == "Recommended" or config.WINEBIN_CODE == "AppImage":
            config.SELECTED_APPIMAGE_FILENAME = installationChoice[1]
        elif config.WINEBIN_CODE == "Exit":
            msg.logos_error("Exiting installation.", "")

        logging.info(f"WINEBIN_CODE: {config.WINEBIN_CODE}; WINE_EXE: {config.WINE_EXE}")
    variables = {
        'config.WINEPREFIX': config.WINEPREFIX,
        'config.WINE_EXE': config.WINE_EXE,
        'config.SELECTED_APPIMAGE_FILENAME': config.SELECTED_APPIMAGE_FILENAME,
    }
    for k, v in variables.items():
        logging.debug(f"{k}: {v}")


def check_existing_install(app=None):
    message = "Checking for existing installation..."
    msg.cli_msg(message)
    # Now that we know what the user wants to install and where, determine whether an install exists and whether to continue.
    if app is not None:
        app.install_q.put(message)
        app.root.event_generate("<<UpdateInstallText>>")

    if os.path.isdir(config.INSTALLDIR):
        logging.info(f"INSTALLDIR: {config.INSTALLDIR}")
        drive_c = f"{config.WINEPREFIX}/drive_c"
        names = ['Logos.exe', 'Verbum.exe']
        if os.path.isdir(drive_c) and any(glob.glob(f"{drive_c}/**/{n}", recursive=True) for n in names):
            msg.logos_error(
                f"An install was found at {config.INSTALLDIR}. Please remove/rename it or use another location by setting the INSTALLDIR variable.")
            return True
        else:
            msg.logos_error(
                f"A directory exists at {config.INSTALLDIR}. Please remove/rename it or use another location by setting the INSTALLDIR variable.")
            return True
    else:
        logging.info(f"Installing to an empty directory at {config.INSTALLDIR}.")

    if app is not None:
        app.root.event_generate("<<CheckExistingInstallDone>>")


def begin_install(app=None):
    message = "Preparing installation folder..."
    msg.cli_msg(message)
    if app is not None:
        app.install_q.put(message)
        app.root.event_generate("<<UpdateInstallText>>")

    if config.SKEL == True:
        logging.info("Making a skeleton install of the project only. Exiting after completion.")
        utils.make_skel("none.AppImage")
        sys.exit(0)

    if config.WINEBIN_CODE:
        if config.WINEBIN_CODE.startswith("Recommended"):
            logging.info(
                f"Installing {config.FLPRODUCT} Bible {config.TARGETVERSION} using {config.RECOMMENDED_WINE64_APPIMAGE_FULL_VERSION} AppImage…")
            utils.make_skel(config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME)
            # exporting PATH to internal use if using AppImage, doing backup too:
            os.environ["OLD_PATH"] = os.environ["PATH"]
            os.environ["PATH"] = f"{config.APPDIR_BINDIR}:{os.environ['PATH']}"
            utils.set_appimage_symlink()
            os.chmod(f"{config.APPDIR_BINDIR}/{config.RECOMMENDED_WINE64_APPIMAGE_FULL_FILENAME}", 0o755)
            config.WINE_EXE = f"{config.APPDIR_BINDIR}/wine64"
        elif config.WINEBIN_CODE.startswith("AppImage"):
            logging.info(f"Installing {config.FLPRODUCT} Bible {config.TARGETVERSION} using the selected AppImage…")
            utils.make_skel(config.SELECTED_APPIMAGE_FILENAME)
            os.environ["OLD_PATH"] = os.environ["PATH"]
            os.environ["PATH"] = f"{config.APPDIR_BINDIR}:{os.environ['PATH']}"
            # Because the utils.set_appimage_symlink() assumes make_skel has been run once, we now run it to determine if the user would
            # rather copy their chosen AppImage to the APPDIR_BINDIR. This is assumed in the Recommended install; here
            # we check explicitly.
            utils.set_appimage_symlink()
            os.chmod(f"{config.SELECTED_APPIMAGE_FILENAME}", 0o755)
            config.WINE_EXE = f"{config.APPDIR_BINDIR}/wine64"
        elif config.WINEBIN_CODE in ["System", "Proton", "PlayOnLinux", "Custom"]:
            logging.info(
                f"Installing {config.FLPRODUCT} Bible {config.TARGETVERSION} using a {config.WINEBIN_CODE} WINE64 binary…")
            utils.make_skel("none.AppImage")
        else:
            msg.logos_error("WINEBIN_CODE error. Installation canceled!")
    else:
        logging.info("WINEBIN_CODE is not set in your config file.")

    wine_version = subprocess.check_output([config.WINE_EXE, "--version"]).decode().strip()
    logging.info(f"Using: {wine_version}")

    # Set WINESERVER_EXE based on WINE_EXE.
    if config.WINESERVER_EXE is None:
        wineserver_path = os.path.join(os.path.dirname(config.WINE_EXE), "wineserver")
        if os.path.exists(wineserver_path):
            config.WINESERVER_EXE = wineserver_path

        else:
            msg.logos_error(f"{wineserver_path} not found. Please either add it or create a symlink to it, and rerun.")


def download_winetricks():
    msg.cli_msg("Downloading winetricks…")
    utils.logos_reuse_download(config.WINETRICKS_URL, "winetricks", config.APPDIR_BINDIR)
    os.chmod(f"{config.APPDIR_BINDIR}/winetricks", 0o755)


def set_winetricks():
    msg.cli_msg("Preparing winetricks…")
    # Check if local winetricks version available; else, download it
    if config.WINETRICKSBIN is None or not os.access(config.WINETRICKSBIN, os.X_OK):
        local_winetricks_path = shutil.which('winetricks')
        if local_winetricks_path is not None:
            # Check if local winetricks version is up-to-date; if so, offer to use it or to download; else, download it
            local_winetricks_version = subprocess.check_output(["winetricks", "--version"]).split()[0]
            if str(local_winetricks_version) >= "20220411":
                if config.DIALOG == 'tk':
                    logging.info("Setting winetricks to the local binary…")
                    config.WINETRICKSBIN = local_winetricks_path
                else:
                    backtitle = "Choose Winetricks Menu"
                    title = "Choose Winetricks"
                    question_text = "Should the script use the system's local winetricks or download the latest winetricks from the Internet? The script needs to set some Wine options that FLPRODUCT requires on Linux."

                    options = ["1: Use local winetricks.", "2: Download winetricks from the Internet"]
                    winetricks_choice = tui.menu(options, title, question_text)

                    logging.debug(f"winetricks_choice: {winetricks_choice}")
                    if winetricks_choice.startswith("1"):
                        logging.info("Setting winetricks to the local binary…")
                        config.WINETRICKSBIN = local_winetricks_path
                        return 0
                    elif winetricks_choice.startswith("2"):
                        download_winetricks()
                        config.WINETRICKSBIN = os.path.join(config.APPDIR_BINDIR, "winetricks")
                        return 0
                    else:
                        msg.cli_msg("Installation canceled!")
                        sys.exit(0)
            else:
                msg.cli_msg(
                    "The system's winetricks is too old. Downloading an up-to-date winetricks from the Internet...")
                download_winetricks()
                config.WINETRICKSBIN = os.path.join(config.APPDIR_BINDIR, "winetricks")
                return 0
        else:
            msg.cli_msg("Local winetricks not found. Downloading winetricks from the Internet…")
            download_winetricks()
            config.WINETRICKSBIN = os.path.join(config.APPDIR_BINDIR, "winetricks")
            return 0
    return 0


# This function is for Logos 9.
def get_premade_wine_bottle():
    msg.cli_msg("Installing pre-made wineBottle 64bits…")
    logging.info(f"Downloading {config.LOGOS9_WINE64_BOTTLE_TARGZ_URL} to {config.WORKDIR}")
    utils.logos_reuse_download(config.LOGOS9_WINE64_BOTTLE_TARGZ_URL, config.LOGOS9_WINE64_BOTTLE_TARGZ_NAME,
                               config.WORKDIR)
    msg.cli_msg(f"Extracting: {config.LOGOS9_WINE64_BOTTLE_TARGZ_NAME}\ninto: {config.APPDIR}")
    shutil.unpack_archive(os.path.join(config.WORKDIR, config.LOGOS9_WINE64_BOTTLE_TARGZ_NAME), config.APPDIR)


## END WINE BOTTLE AND WINETRICKS FUNCTIONS
## BEGIN LOGOS INSTALL FUNCTIONS
def get_logos_executable():
    PRESENT_WORKING_DIRECTORY = config.PRESENT_WORKING_DIRECTORY
    HOME = os.environ.get('HOME')
    # This VAR is used to verify the downloaded MSI is latest
    config.LOGOS_EXECUTABLE = f"{config.FLPRODUCT}_v{config.LOGOS_VERSION}-x64.msi"

    # cli_continue_question(f"Now the script will check for the MSI installer. Then it will download and install {FLPRODUCT} Bible at {WINEPREFIX}. You will need to interact with the installer. Do you wish to continue?", "The installation was cancelled!", "")

    # Getting and installing {FLPRODUCT} Bible
    logging.info(f"Installing {config.FLPRODUCT}Bible 64bits…")
    utils.logos_reuse_download(config.LOGOS64_URL, config.LOGOS_EXECUTABLE, f"{config.APPDIR}/")


def install_logos9(app):
    message = "Configuring wine bottle and installing app..."
    msg.cli_msg(message)
    if app is not None:
        app.install_q.put(message)
        app.root.event_generate("<<UpdateInstallText>>")

    get_premade_wine_bottle()
    set_winetricks()
    wine.installFonts()
    wine.installD3DCompiler()
    get_logos_executable()
    wine.install_msi()
    env = wine.get_wine_env()

    logging.info(f"======= Set {config.FLPRODUCT}Bible Indexing to Vista Mode: =======")
    subprocess.run(
        f'{config.WINE_EXE} reg add "HKCU\\Software\\Wine\\AppDefaults\\{config.FLPRODUCT}Indexer.exe" /v Version /t REG_SZ /d vista /f',
        shell=True, env=env)
    logging.info(f"======= {config.FLPRODUCT}Bible logging set to Vista mode! =======")


def install_logos10(app=None):
    message = "Configuring wine bottle and installing app..."
    msg.cli_msg(message)
    if app is not None:
        app.install_q.put(message)
        app.root.event_generate("<<UpdateInstallText>>")

    reg_file = os.path.join(config.WORKDIR, 'disable-winemenubuilder.reg')
    gdi_file = os.path.join(config.WORKDIR, 'renderer_gdi.reg')
    with open(reg_file, 'w') as f:
        f.write(r'''REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\DllOverrides]
"winemenubuilder.exe"=""
''')
    with open(gdi_file, 'w') as f:
        f.write(r'''REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\Direct3D]
"DirectDrawRenderer"="gdi"
"renderer"="gdi"
''')

    wine.wine_reg_install(reg_file)
    wine.wine_reg_install(gdi_file)

    set_winetricks()
    wine.installFonts()
    wine.installD3DCompiler()

    if not config.WINETRICKS_UNATTENDED:
        wine.winetricks_install("-q", "settings", "win10")
    else:
        wine.winetricks_install("settings", "win10")

    get_logos_executable()
    wine.install_msi()


def post_install(app):
    message = "Finishing installation..."
    msg.cli_msg(message)
    if app is not None:
        app.install_q.put(message)
        app.root.event_generate("<<UpdateInstallText>>")

    HOME = os.environ.get('HOME')

    logging.debug("post-install config:")
    for k in config.persistent_config_keys:
        logging.debug(f"{k}: {config.__dict__.get(k)}")

    if os.path.isfile(config.LOGOS_EXE):
        message = f"{config.FLPRODUCT} Bible {config.TARGETVERSION} installed!"
        msg.cli_msg(message)
        logging.info(message)

        if not os.path.isfile(config.CONFIG_FILE):  # config.CONFIG_FILE is set in main() function
            logging.info(f"No config file at {config.CONFIG_FILE}")
            os.makedirs(os.path.join(HOME, ".config", "Logos_on_Linux"), exist_ok=True)
            if os.path.isdir(os.path.join(HOME, ".config", "Logos_on_Linux")):
                utils.write_config(config.CONFIG_FILE)
                logging.info(f"A config file was created at {config.CONFIG_FILE}.")
            else:
                msg.logos_warn(f"{HOME}/.config/Logos_on_Linux does not exist. Failed to create config file.")
        elif os.path.isfile(config.CONFIG_FILE):
            logging.info(f"Config file exists at {config.CONFIG_FILE}.")
            # Compare existing config file contents with installer config.
            logging.info(f"Comparing its contents with current config.")
            current_config_file_dict = config.get_config_file_dict(config.CONFIG_FILE)
            different = False
            for key in config.persistent_config_keys:
                if current_config_file_dict.get(key) != config.__dict__.get(key):
                    different = True
                    break
            if different is True and msg.logos_acknowledge_question(f"Update config file at {config.CONFIG_FILE}?",
                                                                    "The existing config file was not overwritten."):
                logging.info(f"Updating config file.")
                utils.write_config(config.CONFIG_FILE)
        else:
            # Script was run with a config file. Skip modifying the config.
            pass

        # Copy executable to config.APPDIR.
        runmode = utils.get_runmode()
        if runmode == 'binary':
            launcher_exe = Path(f"{config.INSTALLDIR}/LogosLinuxInstaller")
            if launcher_exe.is_file():
                logging.debug(f"Removing existing launcher binary.")
                launcher_exe.unlink()
            logging.info(f"Creating launcher binary by copying this installer binary to {launcher_exe}.")
            shutil.copy(sys.executable, launcher_exe)
            create_shortcuts()

        # NOTE: Can't launch installed app from installer if control panel is
        # running in a loop b/c of die_if_running function.
        #     if config.DIALOG == 'tk':
        #         subprocess.Popen(str(launcher_exe))
        #     elif msg.logos_acknowledge_question(f"An executable has been placed at {launcher_exe}.\nDo you want to run it now?\nNOTE: There may be an error on first execution. You can close the error dialog.", "The Script has finished. Exiting…"):
        #         subprocess.Popen([str(launcher_exe)])
        # elif runmode == 'script':
        #     if config.DIALOG == 'tk':
        #         subprocess.Popen(sys.argv[0])
        #     elif msg.logos_acknowledge_question(f"Run {config.FLPRODUCT} now?", "The Script has finished. Exiting…"):
        #         subprocess.Popen(sys.argv[0])
        message = "The Script has finished. Exiting…"
        msg.cli_msg(message)
        logging.info(message)
    else:
        msg.logos_error(
            f"Installation failed. {config.LOGOS_EXE} not found. Exiting…\nThe {config.FLPRODUCT} executable was not found. This means something went wrong while installing {config.FLPRODUCT}. Please contact the Logos on Linux community for help.")


def install():
    prepare_install()
    finish_install()


def prepare_install():
    choose_product()  # We ask user for his Faithlife product's name and set variables.
    choose_version()  # We ask user for his Faithlife product's version, set variables, and create project skeleton.
    get_logos_release_version()
    logos_setup()  # We set some basic variables for the install, including retrieving the product's latest release.
    choose_install_method()  # We ask user for his desired install method.


def finish_install(app=None):
    message = "Beginning installation..."
    msg.cli_msg(message)
    if app is not None:
        app.install_q.put(message)
        app.root.event_generate("<<UpdateInstallText>>")

    if check_existing_install(app):
        msg.logos_error("Existing installation.")
    begin_install(app)
    wine.initializeWineBottle(app)  # We run wineboot.
    if config.TARGETVERSION == "10":
        install_logos10(app)  # We run the commands specific to Logos 10.
    elif config.TARGETVERSION == "9":
        install_logos9(app)  # We run the commands specific to Logos 9.
    else:
        msg.logos_error(f"TARGETVERSION unrecognized: '{config.TARGETVERSION}'. Installation canceled!")

    wine.heavy_wineserver_wait()
    utils.clean_all()

    # Find and set LOGOS_EXE.    
    exes = [e for e in glob.glob(f"{config.WINEPREFIX}/drive_c/**/{config.FLPRODUCT}.exe", recursive=True) if
            'Pending' not in e]
    if len(exes) < 1:
        msg.logos_error("Logos was not installed.")
    config.LOGOS_EXE = exes[0]

    post_install(app)

    if app is not None:
        app.root.event_generate("<<CheckInstallProgress>>")


def create_desktop_file(name, contents):
    launcher_path = os.path.expanduser(f"~/.local/share/applications/{name}")
    if os.path.exists(launcher_path):
        logging.info(f"Removing desktop launcher at {launcher_path}.")
        os.remove(launcher_path)

    logging.info(f"Creating desktop launcher at {launcher_path}.")
    with open(launcher_path, 'w') as f:
        f.write(contents)
    os.chmod(launcher_path, 0o755)


def create_shortcuts():
    # Set icon variables.
    if config.LOGOS_ICON_URL is None:
        app_dir = Path(__file__).parent
        config.LOGOS_ICON_URL = app_dir / 'img' / f"{config.FLPRODUCTi}-128-icon.png"
    if config.LOGOS_ICON_FILENAME is None:
        config.LOGOS_ICON_FILENAME = os.path.basename(config.LOGOS_ICON_URL)

    logos_icon_path = os.path.join(config.APPDIR, config.LOGOS_ICON_FILENAME)

    if not os.path.isfile(logos_icon_path):
        os.makedirs(config.APPDIR, exist_ok=True)
        shutil.copy(f"{config.LOGOS_ICON_URL}", logos_icon_path)
    else:
        logging.info(f"Icon found at {logos_icon_path}.")

    desktop_files = [
        (
            f"{config.FLPRODUCT}Bible.desktop",
            f"""[Desktop Entry]
Name={config.FLPRODUCT}Bible
Comment=A Bible Study Library with Built-In Tools
Exec={config.INSTALLDIR}/LogosLinuxInstaller --run-installed-app
Icon={logos_icon_path}
Terminal=false
Type=Application
Categories=Education;
"""
        ),
        (
            f"{config.FLPRODUCT}Bible-ControlPanel.desktop",
            f"""[Desktop Entry]
Name={config.FLPRODUCT}Bible Control Panel
Comment=Perform various tasks for {config.FLPRODUCT} app
Exec={config.INSTALLDIR}/LogosLinuxInstaller
Icon={logos_icon_path}
Terminal=false
Type=Application
Categories=Education;
"""
        ),
    ]
    for f, c in desktop_files:
        create_desktop_file(f, c)
